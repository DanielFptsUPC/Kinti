"""Conocimiento institucional versionado.

Aquí vive **sólo** contenido general y aprobable: guías, indicaciones
administrativas, material educativo. Nunca hitos, barreras, sentimientos, notas
ni conversaciones — un embedding no sabe de permisos, y indexar datos de un
paciente los volvería recuperables por similitud desde otra sesión.

Un documento no se recupera por existir: debe estar `published` y vigente.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin

#: Dimensión de los embeddings. Cambiarla exige reindexado versionado: mezclar
#: vectores de dimensiones distintas es un error de datos, no una degradación.
EMBEDDING_DIMENSION = 768

#: Ciclo de vida de una versión. Sólo `published` puede recuperarse.
VERSION_STATUSES = (
    "draft",
    "processing",
    "review_required",
    "published",
    "retired",
    "failed",
)

AUDIENCES = ("caregiver", "care_team", "child", "public")


class KnowledgeDocument(UuidPkMixin, TimestampMixin, Base):
    """Identidad lógica de un documento, estable entre versiones."""

    __tablename__ = "knowledge_documents"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    audience: Mapped[str] = mapped_column(String(32), nullable=False, default="caregiver")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="es")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KnowledgeDocumentVersion(UuidPkMixin, TimestampMixin, Base):
    """Una revisión concreta, con su archivo original y su aprobación.

    Publicar una versión nueva **retira** la anterior en lugar de borrarla: la
    evidencia histórica debe seguir siendo explicable.
    """

    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
        # Filtro que precede a todo ranking: sólo publicadas y vigentes.
        Index("ix_knowledge_versions_published", "status", "valid_from", "valid_until"),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Evita reingerir contenido idéntico.
    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    storage_bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeChunk(UuidPkMixin, TimestampMixin, Base):
    """Fragmento recuperable, con todo lo necesario para citarlo.

    El embedding y su modelo se guardan juntos: sin saber con qué modelo se
    generó un vector, no se puede razonar sobre su compatibilidad.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        # GIN sobre la columna generada: búsqueda léxica en español.
        Index("ix_knowledge_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
        # HNSW con distancia coseno, la métrica de los embeddings usados.
        # Parámetros conservadores: el corpus del piloto no justifica un índice
        # caro de construir.
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(300), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    #: Columna generada que PostgreSQL mantiene sincronizada con `content`.
    #: Se declara aquí —además de crearse en la migración— para que el modelo y
    #: el esquema real no diverjan; `test_models_match_the_migrated_schema` lo
    #: comprueba en cada ejecución.
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('spanish', coalesce(content, ''))", persisted=True),
        nullable=True,
    )


class KnowledgeIngestionJob(UuidPkMixin, TimestampMixin, Base):
    """Traza de un procesamiento: reanudable y auditable."""

    __tablename__ = "knowledge_ingestion_jobs"

    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    #: Mensaje ya sanitizado: nunca contenido del documento ni secretos.
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extractor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
