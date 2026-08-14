from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import UuidPkMixin

NOTIFICATION_TYPES = (
    "upcoming_milestone",
    "confirmation_request",
    "barrier_received",
    "milestone_rescheduled",
    "alert_resolved",
    "milestone_missed",
)


class NotificationOutbox(UuidPkMixin, Base):
    """Cola de avisos.

    En esta fase alimenta el centro de notificaciones dentro de la aplicación.
    Los adaptadores de push o SMS reales son extensiones posteriores: por eso
    el registro guarda estado e intentos aunque el envío sea sólo local.
    """

    __tablename__ = "notification_outbox"

    recipient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    patient_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: Evita duplicar el mismo aviso cuando el job de continuidad vuelve a correr.
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
