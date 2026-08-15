"""Gestión de conocimiento institucional.

Publicar es un acto deliberado con responsable: sólo el equipo asistencial puede
hacerlo, y sólo después de que la versión haya sido procesada y revisada.
"""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CareTeamUser, SessionDep
from app.api.v1 import schemas
from app.core.errors import DomainError, invalid
from app.modules.assistant.providers import build_embeddings, build_media_storage
from app.modules.knowledge import ingestion
from app.modules.knowledge.content import KNOWLEDGE_BUCKET
from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)

router = APIRouter(tags=["conocimiento"])


def _document_out(document: KnowledgeDocument) -> schemas.DocumentOut:
    return schemas.DocumentOut(
        id=document.id,
        slug=document.slug,
        title=document.title,
        category=document.category,
        audience=document.audience,
        language=document.language,
        is_active=document.is_active,
    )


def _version_out(version: KnowledgeDocumentVersion) -> schemas.VersionOut:
    return schemas.VersionOut(
        id=version.id,
        document_id=version.document_id,
        version=version.version,
        status=version.status,
        checksum=version.checksum,
        published_at=version.published_at,
        retired_at=version.retired_at,
    )


@router.get("/knowledge/documents", response_model=list[schemas.DocumentOut])
async def list_documents(user: CareTeamUser, session: SessionDep) -> list[schemas.DocumentOut]:
    rows = await session.scalars(
        select(KnowledgeDocument).order_by(KnowledgeDocument.title)
    )
    return [_document_out(d) for d in rows]


@router.post("/knowledge/documents", response_model=schemas.DocumentOut)
async def create_document(
    body: schemas.CreateDocumentRequest, user: CareTeamUser, session: SessionDep
) -> schemas.DocumentOut:
    existing = await session.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.slug == body.slug)
    )
    if existing is not None:
        raise invalid("duplicate_slug", "Ya existe un documento con ese identificador").as_http()

    document = KnowledgeDocument(
        slug=body.slug,
        title=body.title,
        category=body.category,
        audience=body.audience,
        language=body.language,
    )
    session.add(document)
    await session.commit()
    return _document_out(document)


@router.post(
    "/knowledge/documents/{document_id}/versions", response_model=schemas.VersionOut
)
async def create_version(
    document_id: UUID,
    body: schemas.CreateVersionRequest,
    user: CareTeamUser,
    session: SessionDep,
) -> schemas.VersionOut:
    document = await session.get(KnowledgeDocument, document_id)
    if document is None:
        from app.core.errors import not_found

        raise not_found("Documento no encontrado").as_http()

    content = body.content.encode("utf-8")
    storage = build_media_storage()
    media = await storage.put(
        KNOWLEDGE_BUCKET,
        f"{document.slug}/{body.version}",
        content,
        body.mime_type,
    )

    try:
        version = await ingestion.register_version(
            session, actor=user, document=document, version=body.version, media=media
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _version_out(version)


@router.post("/knowledge/versions/{version_id}/process", response_model=schemas.VersionOut)
async def process_version(
    version_id: UUID, user: CareTeamUser, session: SessionDep
) -> schemas.VersionOut:
    """Extrae, fragmenta y embebe. Deja la versión pendiente de revisión."""
    try:
        version = await ingestion.get_version(session, version_id)
        storage = build_media_storage()
        from app.modules.assistant.ports import MediaRef

        content = await storage.get(
            MediaRef(
                bucket=version.storage_bucket,
                path=version.storage_path,
                mime_type=version.mime_type,
                size_bytes=0,
                checksum=version.checksum,
            )
        )
        await ingestion.process_version(
            session,
            version=version,
            text=content.decode("utf-8"),
            embeddings=build_embeddings(),
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _version_out(version)


@router.post("/knowledge/versions/{version_id}/publish", response_model=schemas.VersionOut)
async def publish_version(
    version_id: UUID, user: CareTeamUser, session: SessionDep
) -> schemas.VersionOut:
    try:
        version = await ingestion.get_version(session, version_id)
        await ingestion.publish_version(session, actor=user, version=version)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _version_out(version)


@router.post("/knowledge/versions/{version_id}/retire", response_model=schemas.VersionOut)
async def retire_version(
    version_id: UUID, user: CareTeamUser, session: SessionDep
) -> schemas.VersionOut:
    try:
        version = await ingestion.get_version(session, version_id)
        await ingestion.retire_version(session, actor=user, version=version)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _version_out(version)


@router.get(
    "/knowledge/versions/{version_id}/preview", response_model=schemas.VersionPreviewOut
)
async def preview_version(
    version_id: UUID, user: CareTeamUser, session: SessionDep
) -> schemas.VersionPreviewOut:
    try:
        version = await ingestion.get_version(session, version_id)
    except DomainError as exc:
        raise exc.as_http() from exc

    count = await session.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(
            KnowledgeChunk.version_id == version.id
        )
    )
    sections = await session.scalars(
        select(KnowledgeChunk.section)
        .where(KnowledgeChunk.version_id == version.id, KnowledgeChunk.section.is_not(None))
        .distinct()
    )
    return schemas.VersionPreviewOut(
        version=_version_out(version),
        chunk_count=count or 0,
        sections=[s for s in sections if s],
    )
