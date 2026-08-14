from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import UuidPkMixin


class ProcessedOperation(UuidPkMixin, Base):
    """Registro de idempotencia del outbox móvil.

    La unicidad de `operation_id` es lo que impide que un reintento offline
    duplique una confirmación, una barrera o una intervención.
    """

    __tablename__ = "processed_operations"

    operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    operation_type: Mapped[str] = mapped_column(String(48), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
