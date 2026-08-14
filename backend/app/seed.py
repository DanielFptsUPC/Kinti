"""Datos sintéticos reproducibles del piloto.

Reproduce los tres casos de la Fase 1 (Lucía verde, Mateo amarillo, Valentina
roja) y crea las cuentas de demostración. Es idempotente: si los usuarios ya
existen, no duplica nada.

    python -m app.seed

Todos los nombres, teléfonos y hitos son ficticios. No hay DNI, número de
historia clínica ni diagnóstico atribuible a una persona real.
"""

import asyncio
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.time import utcnow
from app.modules.alerts.models import BarrierAlert
from app.modules.companion.models import PatientContentSettings, PatientUserLink
from app.modules.companion.service import DEFAULT_ENABLED
from app.modules.identity.models import User
from app.modules.milestones.models import Milestone
from app.modules.operations.models import AmbulatoryCapacitySlot
from app.modules.patients.models import CaregiverPatientLink, CareTeamAssignment, Patient

# UUID fijos para que el seed sea reproducible y las pruebas puedan referenciarlos.
LUCIA_ID = UUID("11111111-1111-4111-8111-111111111111")
MATEO_ID = UUID("22222222-2222-4222-8222-222222222222")
VALENTINA_ID = UUID("33333333-3333-4333-8333-333333333333")

CAREGIVER_MATEO_EMAIL = "cuidador.mateo@kinti.demo"
CAREGIVER_LUCIA_EMAIL = "cuidador.lucia@kinti.demo"
CARE_TEAM_EMAIL = "equipo@kinti.demo"
CARE_TEAM_SECOND_EMAIL = "equipo.turno2@kinti.demo"

#: Cuenta del menor para la demostración. El alias sustituye al correo: un niño
#: puede no tener uno, y exigirlo convertiría la cuenta en un dato de contacto
#: personal que el piloto no necesita.
PATIENT_ALIAS = "mateo-colibri"
PATIENT_PIN = "2468"


def _at(days: int, hour: int = 9, minute: int = 0):
    base = utcnow() + timedelta(days=days)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


async def _get_or_create_user(
    session: AsyncSession, *, email: str, display_name: str, role: str, password: str
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _get_or_create_patient(session: AsyncSession, patient_id: UUID, **fields) -> Patient:
    patient = await session.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is not None:
        return patient
    patient = Patient(id=patient_id, **fields)
    session.add(patient)
    await session.flush()
    return patient


async def _link_caregiver(session: AsyncSession, caregiver: User, patient: Patient) -> None:
    existing = await session.scalar(
        select(CaregiverPatientLink).where(
            CaregiverPatientLink.caregiver_id == caregiver.id,
            CaregiverPatientLink.patient_id == patient.id,
        )
    )
    if existing is None:
        session.add(
            CaregiverPatientLink(
                caregiver_id=caregiver.id,
                patient_id=patient.id,
                relationship_kind="apoderado",
                is_active=True,
            )
        )


async def _assign_care_team(session: AsyncSession, user: User, patient: Patient) -> None:
    existing = await session.scalar(
        select(CareTeamAssignment).where(
            CareTeamAssignment.user_id == user.id,
            CareTeamAssignment.patient_id == patient.id,
        )
    )
    if existing is None:
        session.add(CareTeamAssignment(user_id=user.id, patient_id=patient.id, is_active=True))


async def _add_capacity_slots(session: AsyncSession, user: User) -> None:
    """Franjas ficticias que permiten mostrar subutilización y saturación."""
    base = _at(1, 8, 0)
    rows = [
        (base, base + timedelta(hours=2), 4),
        (base + timedelta(hours=2), base + timedelta(hours=4), 2),
        (base + timedelta(hours=4), base + timedelta(hours=6), 4),
    ]
    for starts_at, ends_at, places in rows:
        exists = await session.scalar(
            select(AmbulatoryCapacitySlot.id).where(
                AmbulatoryCapacitySlot.service == "Clínica de día",
                AmbulatoryCapacitySlot.starts_at == starts_at,
            )
        )
        if exists is None:
            session.add(
                AmbulatoryCapacitySlot(
                    service="Clínica de día",
                    starts_at=starts_at,
                    ends_at=ends_at,
                    available_places=places,
                    expected_session_minutes=120,
                    created_by=user.id,
                )
            )


async def _add_milestones(session: AsyncSession, patient_id: UUID, rows: list[dict]) -> None:
    existing = await session.scalar(
        select(Milestone.id).where(Milestone.patient_id == patient_id).limit(1)
    )
    if existing is not None:
        return
    for row in rows:
        # `service` es un valor por defecto que cada fila puede sobrescribir
        # (por ejemplo, «Clínica de día»). Pasarlo como argumento fijo chocaba
        # con las filas que ya lo traen.
        session.add(
            Milestone(
                patient_id=patient_id,
                **{"service": "Hematología pediátrica", **row},
            )
        )


async def _activate_companion_account(
    session: AsyncSession, caregiver: User, patient: Patient
) -> None:
    """Cuenta de Kinti Compañero para Mateo.

    Se crea aquí, y no con `companion.activate_account`, porque ese camino exige
    un vínculo cuidador–paciente que el seed aún no ha registrado en este punto.
    El resultado es el mismo: alias, PIN y consentimiento del apoderado.
    """
    existing = await session.scalar(
        select(PatientUserLink).where(PatientUserLink.patient_id == patient.id)
    )
    if existing is not None:
        return

    account = User(
        email=f"patient.{patient.id}@kinti.local",
        display_name=PATIENT_ALIAS,
        password_hash=hash_password(PATIENT_PIN),
        role="patient",
        is_active=True,
    )
    session.add(account)
    await session.flush()

    session.add(
        PatientUserLink(
            user_id=account.id,
            patient_id=patient.id,
            status="active",
            activated_by=caregiver.id,
            consented_at=utcnow(),
        )
    )
    session.add(
        PatientContentSettings(
            patient_id=patient.id,
            development_band="middle",
            enabled_categories=dict(DEFAULT_ENABLED),
            updated_by=caregiver.id,
        )
    )
    await session.flush()


async def seed(session: AsyncSession) -> dict[str, str]:
    settings = get_settings()
    password = settings.seed_password

    caregiver_mateo = await _get_or_create_user(
        session,
        email=CAREGIVER_MATEO_EMAIL,
        display_name="Jorge, papá de Mateo",
        role="caregiver",
        password=password,
    )
    caregiver_lucia = await _get_or_create_user(
        session,
        email=CAREGIVER_LUCIA_EMAIL,
        display_name="Rosa, mamá de Lucía",
        role="caregiver",
        password=password,
    )
    care_team = await _get_or_create_user(
        session,
        email=CARE_TEAM_EMAIL,
        display_name="Gestora de continuidad (demo)",
        role="care_team",
        password=password,
    )
    care_team_second = await _get_or_create_user(
        session,
        email=CARE_TEAM_SECOND_EMAIL,
        display_name="Equipo hematológico B (demo)",
        role="care_team",
        password=password,
    )

    lucia = await _get_or_create_patient(
        session,
        LUCIA_ID,
        display_name="Lucía",
        age=8,
        avatar_key="lucia",
        caregiver_name="Rosa, mamá de Lucía",
        contact_phone="+51 900 000 001 (ficticio)",
    )
    mateo = await _get_or_create_patient(
        session,
        MATEO_ID,
        display_name="Mateo",
        age=11,
        avatar_key="mateo",
        caregiver_name="Jorge, papá de Mateo",
        contact_phone="+51 900 000 002 (ficticio)",
    )
    valentina = await _get_or_create_patient(
        session,
        VALENTINA_ID,
        display_name="Valentina",
        age=6,
        avatar_key="valentina",
        caregiver_name="Milagros, mamá de Valentina",
        contact_phone="+51 900 000 003 (ficticio)",
    )

    await _activate_companion_account(session, caregiver_mateo, mateo)

    await _link_caregiver(session, caregiver_mateo, mateo)
    await _link_caregiver(session, caregiver_lucia, lucia)
    for patient in (lucia, mateo, valentina):
        await _assign_care_team(session, care_team, patient)
    await _assign_care_team(session, care_team_second, lucia)

    # Lucía — verde: próximo control confirmado.
    await _add_milestones(
        session,
        LUCIA_ID,
        [
            {
                "type": "consultation",
                "title": "Consulta hematológica inicial",
                "scheduled_at": _at(-30),
                "location": "Consulta externa — Piso 3",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "laboratory",
                "title": "Laboratorio de control",
                "scheduled_at": _at(-20),
                "location": "Laboratorio central",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "procedure",
                "title": "Procedimiento ambulatorio",
                "scheduled_at": _at(-10),
                "location": "Sala de procedimientos",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "follow_up",
                "title": "Control hematológico",
                "scheduled_at": _at(5, 9, 30),
                "location": "Consulta externa — Piso 3, consultorio 5",
                "preparation": "Acudir en ayunas de 4 horas.",
                "confirmation_deadline": _at(3),
                "status": "upcoming",
                "attendance_confirmed": True,
            },
            {
                "type": "treatment",
                "title": "Sesión ambulatoria",
                "scheduled_at": _at(1, 10, 30),
                "location": "Clínica de día",
                "service": "Clínica de día",
                "status": "upcoming",
                "attendance_confirmed": True,
            },
            {
                "type": "follow_up",
                "title": "Control de seguimiento",
                "status": "unscheduled",
                "attendance_confirmed": False,
            },
        ],
    )

    # Mateo — amarillo: próximo control pendiente de confirmación.
    await _add_milestones(
        session,
        MATEO_ID,
        [
            {
                "type": "consultation",
                "title": "Consulta hematológica inicial",
                "scheduled_at": _at(-25),
                "location": "Consulta externa — Piso 3",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "laboratory",
                "title": "Laboratorio de control",
                "scheduled_at": _at(-15),
                "location": "Laboratorio central",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "procedure",
                "title": "Procedimiento ambulatorio",
                "scheduled_at": _at(-5),
                "location": "Sala de procedimientos",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "follow_up",
                "title": "Control hematológico",
                "scheduled_at": _at(2, 10, 0),
                "location": "Consulta externa — Piso 3, consultorio 2",
                "preparation": "Traer el último resultado de laboratorio.",
                "confirmation_deadline": _at(1),
                "status": "upcoming",
                "attendance_confirmed": False,
            },
            {
                "type": "follow_up",
                "title": "Control de seguimiento",
                "status": "unscheduled",
                "attendance_confirmed": False,
            },
            {
                "type": "treatment",
                "title": "Sesión ambulatoria",
                "scheduled_at": _at(1, 10, 45),
                "location": "Clínica de día",
                "service": "Clínica de día",
                "status": "upcoming",
                "attendance_confirmed": False,
            },
        ],
    )

    # Valentina — rojo: control vencido con inasistencia pendiente de contacto.
    await _add_milestones(
        session,
        VALENTINA_ID,
        [
            {
                "type": "consultation",
                "title": "Consulta hematológica inicial",
                "scheduled_at": _at(-40),
                "location": "Consulta externa — Piso 3",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "laboratory",
                "title": "Laboratorio de control",
                "scheduled_at": _at(-28),
                "location": "Laboratorio central",
                "status": "completed",
                "attendance_confirmed": True,
            },
            {
                "type": "follow_up",
                "title": "Control hematológico",
                "scheduled_at": _at(-4, 9, 0),
                "location": "Consulta externa — Piso 3, consultorio 1",
                "preparation": "Acudir en ayunas de 4 horas.",
                "confirmation_deadline": _at(-5),
                "status": "missed",
                "attendance_confirmed": False,
            },
            {
                "type": "procedure",
                "title": "Procedimiento ambulatorio",
                "status": "unscheduled",
                "attendance_confirmed": False,
            },
        ],
    )

    # Una alerta sintética de inasistencia permite demostrar la cola de recuperación.
    existing_alert = await session.scalar(
        select(BarrierAlert.id).where(BarrierAlert.patient_id == VALENTINA_ID).limit(1)
    )
    if existing_alert is None:
        missed = await session.scalar(
            select(Milestone).where(
                Milestone.patient_id == VALENTINA_ID, Milestone.status == "missed"
            )
        )
        if missed is not None:
            session.add(
                BarrierAlert(
                    patient_id=VALENTINA_ID,
                    milestone_id=missed.id,
                    category="communication",
                    note="No fue posible confirmar el motivo de la inasistencia (dato ficticio).",
                    status="open",
                    reported_by=care_team.id,
                )
            )

    await _add_capacity_slots(session, care_team)

    await session.commit()
    return {
        "caregiver_mateo": CAREGIVER_MATEO_EMAIL,
        "caregiver_lucia": CAREGIVER_LUCIA_EMAIL,
        "care_team": CARE_TEAM_EMAIL,
        "care_team_second": CARE_TEAM_SECOND_EMAIL,
        "password": password,
        "patient_alias": PATIENT_ALIAS,
        "patient_pin": PATIENT_PIN,
    }


async def main() -> None:
    async with SessionLocal() as session:
        accounts = await seed(session)
    print("Datos sintéticos cargados. Cuentas de demostración:")
    for key, value in accounts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
