from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin


class Patient(UuidPkMixin, TimestampMixin, Base):
    """Paciente ficticio.

    `operational_risk` y `route_status` NO se persisten: son valores derivados
    que el servidor recalcula en cada consulta a partir de hitos y alertas.
    """

    __tablename__ = "patients"

    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    avatar_key: Mapped[str] = mapped_column(String(64), nullable=False)
    caregiver_name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(64), nullable=False)


class CaregiverPatientLink(UuidPkMixin, TimestampMixin, Base):
    """Vínculo familiar: define qué pacientes puede ver y operar un cuidador."""

    __tablename__ = "caregiver_patient_links"
    __table_args__ = (UniqueConstraint("caregiver_id", "patient_id", name="uq_caregiver_patient"),)

    caregiver_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="apoderado")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CareTeamAssignment(UuidPkMixin, TimestampMixin, Base):
    """Asignación asistencial: define sobre qué pacientes puede actuar el equipo."""

    __tablename__ = "care_team_assignments"
    __table_args__ = (UniqueConstraint("user_id", "patient_id", name="uq_care_team_patient"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
