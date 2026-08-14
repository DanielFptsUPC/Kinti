"""Pipeline de ingesta de conocimiento institucional.

    subida privada → validación → extracción → normalización
    → fragmentación → embeddings → revisión humana → publicación

Dos reglas gobiernan todo el flujo:

- **Guardar un archivo no es publicarlo.** Sólo una versión `published` y vigente
  puede llegar a una familia. La revisión humana es un paso obligatorio, no una
  cortesía.
- **La ingesta es idempotente y reanudable.** El checksum evita reingerir
  contenido idéntico, y reprocesar una versión reemplaza sus fragmentos en lugar
  de acumularlos.
"""

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import invalid, not_found
from app.core.time import utcnow
from app.modules.assistant.ports import EmbeddingProvider, MediaRef
from app.modules.assistant.safety import sanitize_document_text
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
)

#: Un fragmento demasiado corto pierde contexto; demasiado largo diluye la
#: recuperación. Estos valores funcionan para guías institucionales breves.
MAX_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 80

#: Por debajo de esta confianza de extracción, la versión exige revisión humana
#: y no puede publicarse directamente.
MIN_EXTRACTION_CONFIDENCE = 0.7


def checksum_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class Chunk:
    content: str
    position: int
    section: str | None
    page: int | None


_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def chunk_text(text: str) -> list[Chunk]:
    """Fragmenta por unidades completas de sentido.

    Se corta en párrafos y se respetan los encabezados, que se arrastran como
    `section` a cada fragmento. Nunca se parte a mitad de párrafo: separar una
    advertencia de la acción que la acompaña produce un fragmento que, recuperado
    solo, dice lo contrario de lo que decía el documento.
    """
    chunks: list[Chunk] = []
    section: str | None = None
    buffer: list[str] = []
    position = 0

    def flush() -> None:
        nonlocal buffer, position
        if not buffer:
            return
        content = "\n\n".join(buffer).strip()
        buffer = []
        if len(content) < MIN_CHUNK_CHARS and chunks:
            # Un resto corto se adjunta al fragmento anterior en vez de quedar
            # suelto sin contexto suficiente para ser útil.
            previous = chunks[-1]
            chunks[-1] = Chunk(
                content=f"{previous.content}\n\n{content}",
                position=previous.position,
                section=previous.section,
                page=previous.page,
            )
            return
        if not content:
            return
        chunks.append(Chunk(content=content, position=position, section=section, page=None))
        position += 1

    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue

        heading = _HEADING.match(block)
        if heading:
            flush()
            section = heading.group(2)
            continue

        candidate_len = sum(len(b) for b in buffer) + len(block)
        if buffer and candidate_len > MAX_CHUNK_CHARS:
            flush()
        buffer.append(block)

    flush()
    return chunks


async def register_version(
    session: AsyncSession,
    *,
    actor: User,
    document: KnowledgeDocument,
    version: str,
    media: MediaRef,
) -> KnowledgeDocumentVersion:
    """Registra una versión nueva en estado `draft`.

    Si ya existe una versión con el mismo checksum, se devuelve esa: reingerir
    contenido idéntico no aporta nada y duplicaría embeddings.
    """
    existing = await session.scalar(
        select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.document_id == document.id,
            KnowledgeDocumentVersion.checksum == media.checksum,
        )
    )
    if existing is not None:
        return existing

    record = KnowledgeDocumentVersion(
        document_id=document.id,
        version=version,
        checksum=media.checksum,
        storage_bucket=media.bucket,
        storage_path=media.path,
        mime_type=media.mime_type,
        status="draft",
        author_id=actor.id,
    )
    session.add(record)
    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="register_knowledge_version",
        entity_type="knowledge_document_version",
        entity_id=record.id,
        metadata={"document_id": document.id, "version": version},
    )
    return record


async def process_version(
    session: AsyncSession,
    *,
    version: KnowledgeDocumentVersion,
    text: str,
    embeddings: EmbeddingProvider,
    extraction_confidence: float = 1.0,
    extractor: str = "fake-extractor",
) -> KnowledgeIngestionJob:
    """Extrae, fragmenta y embebe. **No publica.**

    Al terminar la versión queda en `review_required`: alguien tiene que mirarla
    antes de que una familia pueda recibirla.
    """
    job = KnowledgeIngestionJob(
        version_id=version.id,
        status="processing",
        extractor=extractor,
        embedding_model=embeddings.model_id,
        extraction_confidence=extraction_confidence,
    )
    session.add(job)
    version.status = "processing"
    await session.flush()

    # Todo documento es contenido no confiable: las instrucciones incrustadas se
    # neutralizan antes de que puedan llegar al prompt del modelo.
    clean = sanitize_document_text(text)
    chunks = chunk_text(clean)

    if not chunks:
        job.status = "failed"
        job.error = "El documento no produjo fragmentos utilizables"
        job.finished_at = utcnow()
        version.status = "failed"
        await session.flush()
        return job

    # Reprocesar reemplaza: reindexar no debe duplicar fragmentos.
    await session.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.version_id == version.id)
    )

    vectors = await embeddings.embed([c.content for c in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        session.add(
            KnowledgeChunk(
                document_id=version.document_id,
                version_id=version.id,
                position=chunk.position,
                content=chunk.content,
                section=chunk.section,
                page=chunk.page,
                embedding=vector,
                embedding_model=embeddings.model_id,
            )
        )

    job.chunks_created = len(chunks)
    job.status = "completed"
    job.finished_at = utcnow()
    version.status = "review_required"
    await session.flush()
    return job


async def publish_version(
    session: AsyncSession, *, actor: User, version: KnowledgeDocumentVersion
) -> KnowledgeDocumentVersion:
    """Publica una versión revisada y retira la anterior.

    La anterior se **retira**, no se borra: una respuesta pasada debe seguir
    siendo explicable con la evidencia que la sustentó.
    """
    if version.status != "review_required":
        raise invalid(
            "not_reviewable",
            "Sólo puede publicarse una versión procesada y pendiente de revisión",
        )

    job = await session.scalar(
        select(KnowledgeIngestionJob)
        .where(KnowledgeIngestionJob.version_id == version.id)
        .order_by(KnowledgeIngestionJob.created_at.desc())
    )
    if job and (job.extraction_confidence or 1.0) < MIN_EXTRACTION_CONFIDENCE:
        raise invalid(
            "low_confidence",
            "La extracción tuvo baja confianza y requiere corrección antes de publicar",
        )

    now = utcnow()
    previous = await session.scalars(
        select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.document_id == version.document_id,
            KnowledgeDocumentVersion.status == "published",
            KnowledgeDocumentVersion.id != version.id,
        )
    )
    for old in previous:
        old.status = "retired"
        old.retired_at = now

    version.status = "published"
    version.published_at = now
    version.reviewer_id = actor.id
    if version.valid_from is None:
        version.valid_from = now
    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="publish_knowledge_version",
        entity_type="knowledge_document_version",
        entity_id=version.id,
        metadata={"document_id": version.document_id, "version": version.version},
    )
    return version


async def retire_version(
    session: AsyncSession, *, actor: User, version: KnowledgeDocumentVersion
) -> KnowledgeDocumentVersion:
    """Retira una versión: deja de recuperarse, pero su evidencia permanece."""
    if version.status != "published":
        raise invalid("not_published", "Sólo puede retirarse una versión publicada")

    version.status = "retired"
    version.retired_at = utcnow()
    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="retire_knowledge_version",
        entity_type="knowledge_document_version",
        entity_id=version.id,
        metadata={"document_id": version.document_id},
    )
    return version


async def get_version(session: AsyncSession, version_id: UUID) -> KnowledgeDocumentVersion:
    version = await session.get(KnowledgeDocumentVersion, version_id)
    if version is None:
        raise not_found("Versión de documento no encontrada")
    return version
