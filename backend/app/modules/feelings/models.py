from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import UuidPkMixin


class FeelingCheckIn(UuidPkMixin, Base):
    """Registro emocional del niño.

    Acompaña, no diagnostica: nunca genera alertas ni participa en la
    priorización operativa.
    """

    __tablename__ = "feeling_check_ins"

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mood: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operation_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True, nullable=True)
