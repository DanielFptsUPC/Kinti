from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import UuidPkMixin


class AuditEvent(UuidPkMixin, Base):
    """Rastro de cada escritura relevante.

    `metadata_json` guarda datos mínimos y no sensibles: identificadores y
    categorías. Nunca notas familiares o internas completas, ni tokens.
    """

    __tablename__ = "audit_events"

    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
