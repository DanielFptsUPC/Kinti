"""Piezas compartidas por los modelos de todos los módulos.

Los estados se guardan como texto y no como ENUM nativo de PostgreSQL: mantiene
las migraciones simples y permite ejecutar la suite de pruebas sobre SQLite sin
cambiar el comportamiento. La validación de valores vive en los esquemas Pydantic
y en las reglas de dominio.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow

# Vocabulario compartido con `src/types/index.ts` del cliente móvil.
ROLES = ("caregiver", "care_team")
MILESTONE_STATUSES = (
    "completed",
    "upcoming",
    "unscheduled",
    "support_needed",
    "rescheduled",
    "missed",
)
MILESTONE_TYPES = ("consultation", "laboratory", "procedure", "treatment", "follow_up")
BARRIER_CATEGORIES = (
    "transport",
    "lodging",
    "financial",
    "schedule",
    "instructions",
    "communication",
    "health_difficulty",
    "other",
)
ALERT_STATUSES = ("open", "in_progress", "resolved")
ALERT_ACTIONS = (
    "guidance",
    "reschedule",
    "social_work_referral",
    "lodging_coordination",
    "transport_coordination",
    "other",
)
EMOTIONS = ("calm", "unsure", "worried", "tired")
OPERATIONAL_RISKS = ("green", "yellow", "red")
ROUTE_STATUSES = ("on_track", "confirmation_needed", "support_needed")


def new_uuid() -> UUID:
    return uuid4()


class UuidPkMixin:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
