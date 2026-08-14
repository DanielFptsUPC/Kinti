from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.modules.identity.models import User
from app.modules.patients.models import CaregiverPatientLink, CareTeamAssignment, Patient


async def authorized_patient_ids(session: AsyncSession, user: User) -> list[UUID]:
    """Pacientes que este usuario puede ver.

    Para un cuidador son sus vínculos familiares activos; para el equipo, sus
    asignaciones activas. Esta lista es la base de todo el control de acceso:
    ninguna consulta debe salirse de ella.
    """
    if user.role == "caregiver":
        rows = await session.scalars(
            select(CaregiverPatientLink.patient_id).where(
                CaregiverPatientLink.caregiver_id == user.id,
                CaregiverPatientLink.is_active.is_(True),
            )
        )
    else:
        rows = await session.scalars(
            select(CareTeamAssignment.patient_id).where(
                CareTeamAssignment.user_id == user.id,
                CareTeamAssignment.is_active.is_(True),
            )
        )
    return list(rows)


async def require_patient_access(session: AsyncSession, user: User, patient_id: UUID) -> Patient:
    """Carga un paciente sólo si el usuario está autorizado.

    Un UUID ajeno produce 404, no 403: así no se puede enumerar qué pacientes
    existen probando identificadores.
    """
    allowed = await authorized_patient_ids(session, user)
    if patient_id not in allowed:
        raise not_found("Paciente no encontrado")
    patient = await session.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None:
        raise not_found("Paciente no encontrado")
    return patient


async def list_patients(session: AsyncSession, patient_ids: list[UUID]) -> list[Patient]:
    if not patient_ids:
        return []
    rows = await session.scalars(
        select(Patient).where(Patient.id.in_(patient_ids)).order_by(Patient.display_name)
    )
    return list(rows)
