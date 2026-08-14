from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin


class AmbulatoryCapacitySlot(UuidPkMixin, TimestampMixin, Base):
    """Capacidad sintética por franja; no representa una agenda clínica real."""

    __tablename__ = "ambulatory_capacity_slots"
    __table_args__ = (
        UniqueConstraint("service", "starts_at", name="uq_capacity_service_start"),
    )

    service: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_places: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_session_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

