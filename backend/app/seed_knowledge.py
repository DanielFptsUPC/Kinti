"""Siembra el corpus institucional del asistente de cuidadores.

Recorre `KnowledgeDocument`, `KnowledgeDocumentVersion` y `KnowledgeChunk`
mediante el mismo pipeline que expone la API (`register_version` →
`process_version` → `publish_version`): no hay un atajo que escriba filas
directamente, porque entonces la siembra dejaría de probar el camino real que
usará el equipo asistencial al publicar contenido nuevo.

Es idempotente. `register_version` deduplica por checksum del contenido, así
que repetir la siembra tras editar `content.py` sólo reprocesa las versiones que
cambiaron; el resto se salta sin tocar sus embeddings.

    python -m app.seed_knowledge

Esa deduplicación por checksum tiene una consecuencia que hay que conocer al
**cambiar de proveedor de embeddings** (por ejemplo, de `fake` a `vertex`): el
texto de un documento no cambia sólo porque cambie quién lo embebe, así que una
corrida normal encontraría el mismo checksum y saltaría el reprocesamiento —
los chunks existentes se quedarían para siempre con vectores del proveedor
anterior, mezclados en la misma columna con los nuevos. `--reindex` fuerza el
reprocesamiento de todo el corpus con el proveedor configurado, sin importar el
checksum:

    python -m app.seed_knowledge --reindex

Requiere que ya exista la cuenta de equipo asistencial (`python -m app.seed`
corrido antes): la firma como autora y revisora de cada versión.
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.modules.assistant.ports import EmbeddingProvider, MediaStorage
from app.modules.assistant.providers import build_embeddings, build_media_storage
from app.modules.identity import service as identity
from app.modules.identity.models import User
from app.modules.knowledge import ingestion
from app.modules.knowledge.content import DOCUMENTS, KNOWLEDGE_BUCKET, DocumentSpec
from app.modules.knowledge.models import KnowledgeDocument, KnowledgeDocumentVersion
from app.seed import CARE_TEAM_EMAIL


async def _get_or_create_document(session: AsyncSession, spec: DocumentSpec) -> KnowledgeDocument:
    document = await session.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.slug == spec.slug)
    )
    if document is not None:
        return document

    document = KnowledgeDocument(
        slug=spec.slug,
        title=spec.title,
        category=spec.category,
        audience=spec.audience,
        language=spec.language,
    )
    session.add(document)
    await session.flush()
    return document


async def seed_one(
    session: AsyncSession,
    spec: DocumentSpec,
    *,
    actor: User,
    embeddings: EmbeddingProvider,
    storage: MediaStorage,
    force: bool = False,
) -> tuple[KnowledgeDocumentVersion, str]:
    """Publica una versión y describe lo que hizo, para el resumen en consola.

    Devuelve la versión resultante y una de cuatro palabras: `publicado`
    (procesada y publicada en esta corrida), `vigente` (ya estaba publicada con
    este mismo contenido, nada que hacer), `reindexado` (`force=True`: se
    volvió a embeber contenido que ya estaba publicado) u `omitido` (el
    documento no produjo fragmentos utilizables — ver `ingestion.process_version`).
    """
    document = await _get_or_create_document(session, spec)

    content = spec.text.encode("utf-8")
    media = await storage.put(
        KNOWLEDGE_BUCKET, f"{spec.slug}/{spec.version}.md", content, "text/markdown"
    )

    version = await ingestion.register_version(
        session, actor=actor, document=document, version=spec.version, media=media
    )

    if version.status == "published":
        if not force:
            return version, "vigente"
        # `process_version` reemplaza los fragmentos de esta versión en vez de
        # acumularlos, así que reincrustarla en el sitio es seguro: no crea una
        # versión nueva ni retira nada.
        await ingestion.process_version(
            session, version=version, text=spec.text, embeddings=embeddings
        )
        await ingestion.publish_version(session, actor=actor, version=version)
        return version, "reindexado"

    # Cualquier otro estado —`draft` en el caso normal, o `processing`/`failed`
    # si una corrida anterior no llegó a terminar— se reprocesa: reprocesar
    # reemplaza los fragmentos en vez de acumularlos, así que repetirlo no tiene
    # costo salvo el de recalcular embeddings.
    if version.status != "review_required":
        await ingestion.process_version(
            session, version=version, text=spec.text, embeddings=embeddings
        )

    if version.status == "review_required":
        await ingestion.publish_version(session, actor=actor, version=version)
        return version, "publicado"

    # `failed`: el documento no produjo fragmentos (contenido vacío tras
    # sanear). No debería ocurrir con el corpus versionado, pero silenciarlo
    # sería peor que reportarlo.
    return version, "omitido"


async def seed_knowledge(session: AsyncSession, *, force: bool = False) -> list[tuple[str, str]]:
    """Publica `DOCUMENTS` completo. Devuelve `(título, resultado)` por documento."""
    actor = await identity.get_by_email(session, CARE_TEAM_EMAIL)
    if actor is None:
        raise RuntimeError(
            f"No existe la cuenta {CARE_TEAM_EMAIL}. Corre `python -m app.seed` primero."
        )

    embeddings = build_embeddings()
    storage = build_media_storage()

    results = []
    for spec in DOCUMENTS:
        version, outcome = await seed_one(
            session, spec, actor=actor, embeddings=embeddings, storage=storage, force=force
        )
        results.append((spec.title, outcome))
    await session.commit()
    return results


async def main() -> None:
    force = "--reindex" in sys.argv
    async with SessionLocal() as session:
        results = await seed_knowledge(session, force=force)
    print("Corpus institucional sembrado:")
    for title, outcome in results:
        print(f"  [{outcome}] {title}")


if __name__ == "__main__":
    asyncio.run(main())
