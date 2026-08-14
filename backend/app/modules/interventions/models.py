from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import UuidPkMixin


class Intervention(UuidPkMixin, Base):
    """Acción asistencial registrada sobre una alerta. Es el rastro de gestión."""

    __tablename__ = "interventions"

    alert_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("barrier_alerts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(48), nullable=False)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    operation_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True, nullable=True)
