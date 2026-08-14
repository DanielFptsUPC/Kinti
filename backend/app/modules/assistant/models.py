"""Conversación, evidencia y seguridad.

Tres reglas que gobiernan estas tablas:

- **No se persiste cadena de pensamiento.** Sólo el resultado estructurado.
- **El texto conversacional no se duplica** en auditoría, logs ni analítica.
- Los medios tienen **retención corta** y expiración explícita.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin

MESSAGE_ROLES = ("user", "assistant", "system")
MODALITIES = ("text", "audio", "image")
MESSAGE_STATUSES = ("pending", "processing", "answered", "failed", "awaiting_confirmation")


class ConversationSession(UuidPkMixin, TimestampMixin, Base):
    """Hilo de conversación de un usuario autorizado."""

    __tablename__ = "conversation_sessions"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: Paciente en contexto, siempre uno que el usuario tenga autorizado.
    patient_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="mobile")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    #: Versión de políticas vigente al abrir: una respuesta pasada debe seguir
    #: siendo explicable con las reglas que la produjeron.
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationMessage(UuidPkMixin, TimestampMixin, Base):
    """Mensaje del usuario o del asistente."""

    __tablename__ = "conversation_messages"

    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    modality: Mapped[str] = mapped_column(String(16), nullable=False, default="text")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    intent: Mapped[str | None] = mapped_column(String(48), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Acción propuesta pendiente de confirmación. Nunca se aplica sola.
    proposed_action: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    action_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Idempotencia: el mismo mensaje reenviado no se procesa dos veces.
    operation_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True, nullable=True)
    #: Comando resultante, si la acción llegó a confirmarse.
    resulting_operation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationMedia(UuidPkMixin, TimestampMixin, Base):
    """Audio o imagen adjunta, en bucket privado y con expiración."""

    __tablename__ = "conversation_media"

    message_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        index=True, nullable=True,
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Ruta opaca: sin nombre, DNI, diagnóstico ni correo.
    path: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiRun(UuidPkMixin, Base):
    """Métricas de una llamada al proveedor.

    Guarda proveedor, modelo, prompt versionado, latencia y unidades. **No**
    guarda el prompt completo, la respuesta íntegra ni razonamiento interno.
    """

    __tablename__ = "ai_runs"

    message_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        index=True, nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    model_id: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    safety_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RetrievalEvidence(UuidPkMixin, Base):
    """Qué fragmento sustentó qué respuesta, y en qué posición del ranking."""

    __tablename__ = "retrieval_evidence"

    message_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    chunk_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SafetyEvent(UuidPkMixin, Base):
    """Registro estructurado de una activación de la política de seguridad."""

    __tablename__ = "safety_events"

    session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        index=True, nullable=True,
    )
    message_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
