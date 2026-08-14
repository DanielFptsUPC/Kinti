from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin


class Milestone(UuidPkMixin, TimestampMixin, Base):
    """Hito asistencial. El servidor es la autoridad sobre su fecha y su estado."""

    __tablename__ = "milestones"

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    preparation: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confirmation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unscheduled")
    attendance_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Control de concurrencia optimista: sube en cada escritura del servidor.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AttendanceConfirmation(UuidPkMixin, Base):
    """Registro de que una familia confirmó asistencia a un hito.

    `operation_id` conserva el identificador idempotente que envió el cliente,
    de modo que un reintento offline no genera una segunda confirmación.
    """

    __tablename__ = "attendance_confirmations"

    milestone_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("milestones.id", ondelete="CASCADE"), index=True, nullable=False
    )
    caregiver_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operation_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True, nullable=True)
