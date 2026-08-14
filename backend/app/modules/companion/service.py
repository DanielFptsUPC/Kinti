"""Reglas del espacio Compañero.

La función más importante de este módulo es `build_companion_view`: define, en un
único lugar, **qué puede ver un menor**. Todo lo demás del dominio —hitos,
alertas, riesgo, barreras, capacidad— queda fuera por construcción, no por
omisión de la interfaz.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, invalid, not_found
from app.core.time import to_display, utcnow
from app.modules.audit import service as audit
from app.modules.companion.models import (
    CONTENT_CATEGORIES,
    CompanionPreferences,
    PatientContentSettings,
    PatientSupportRequest,
    PatientUserLink,
)
from app.modules.identity.models import User
from app.modules.milestones.models import Milestone
from app.modules.notifications import service as notifications
from app.modules.patients.models import CaregiverPatientLink, Patient

#: Bloqueo tras intentos fallidos. Nunca afecta la ruta clínica del paciente.
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=15)

#: Categorías habilitadas si el cuidador no ha configurado nada. Se eligen las
#: que no requieren juicio adulto previo.
DEFAULT_ENABLED = {
    "breathing": True,
    "music": True,
    "drawing": True,
    "stories": True,
    "comfort_object": True,
    "caregiver_messages": True,
    "immediate_preparation": True,
}

#: Actividades por banda de desarrollo. Contenido pendiente de revisión por
#: Psicología; el catálogo es la estructura, no la aprobación.
ACTIVITIES: dict[str, tuple[dict, ...]] = {
    "early": (
        {"key": "breathing", "title": "Respira con Kinti", "duration_seconds": 60},
        {"key": "music", "title": "Una canción tranquila", "duration_seconds": 120},
        {"key": "drawing", "title": "Dibuja lo que quieras", "duration_seconds": 0},
    ),
    "middle": (
        {"key": "breathing", "title": "Respira con Kinti", "duration_seconds": 90},
        {"key": "music", "title": "Música para calmarse", "duration_seconds": 180},
        {"key": "drawing", "title": "Dibuja cómo te sientes", "duration_seconds": 0},
        {"key": "stories", "title": "Un cuento corto", "duration_seconds": 240},
    ),
    "adolescent": (
        {"key": "breathing", "title": "Respiración guiada", "duration_seconds": 120},
        {"key": "music", "title": "Elige tu música", "duration_seconds": 0},
        {"key": "stories", "title": "Una historia breve", "duration_seconds": 300},
    ),
}

GREETINGS = {
    "early": "¡Hola! Soy Kinti y hoy vuelo contigo.",
    "middle": "Hola, soy Kinti. Estoy aquí contigo.",
    "adolescent": "Hola. Soy Kinti; este espacio es tuyo.",
}


# --------------------------------------------------------------- vínculo


async def get_link_for_user(session: AsyncSession, user: User) -> PatientUserLink:
    """Deriva el paciente **desde el token**, nunca desde el cliente.

    Es la garantía central del §9.1: ningún endpoint infantil acepta un
    `patient_id` arbitrario.
    """
    if user.role != "patient":
        raise forbidden("Esta sección corresponde al espacio del paciente")

    link = await session.scalar(
        select(PatientUserLink).where(PatientUserLink.user_id == user.id)
    )
    if link is None:
        raise not_found("Cuenta sin paciente vinculado")
    if link.status != "active":
        raise forbidden("La cuenta está suspendida. Pide ayuda a tu adulto responsable.")
    return link


async def require_caregiver_of(
    session: AsyncSession, caregiver: User, patient_id: UUID
) -> None:
    """Sólo un cuidador vinculado administra la cuenta del menor."""
    if caregiver.role != "caregiver":
        raise forbidden("Sólo el cuidador vinculado administra la cuenta del paciente")

    link = await session.scalar(
        select(CaregiverPatientLink).where(
            CaregiverPatientLink.caregiver_id == caregiver.id,
            CaregiverPatientLink.patient_id == patient_id,
            CaregiverPatientLink.is_active.is_(True),
        )
    )
    if link is None:
        raise not_found("Paciente no encontrado")


# --------------------------------------------------- alta y administración


async def activate_account(
    session: AsyncSession,
    *,
    caregiver: User,
    patient_id: UUID,
    alias: str,
    pin_hash: str,
) -> tuple[User, PatientUserLink]:
    """Crea la cuenta del menor bajo consentimiento del apoderado.

    No exige correo ni teléfono del niño: se genera un identificador interno a
    partir del alias, porque un menor puede no tener línea propia.
    """
    await require_caregiver_of(session, caregiver, patient_id)

    existing = await session.scalar(
        select(PatientUserLink).where(PatientUserLink.patient_id == patient_id)
    )
    if existing is not None:
        raise invalid("account_exists", "Este paciente ya tiene una cuenta")

    # Identificador interno, no una dirección real: nunca se envía correo.
    internal_id = f"patient.{patient_id}@kinti.local"
    account = User(
        email=internal_id,
        display_name=alias,
        password_hash=pin_hash,
        role="patient",
        is_active=True,
    )
    session.add(account)
    await session.flush()

    link = PatientUserLink(
        user_id=account.id,
        patient_id=patient_id,
        status="active",
        activated_by=caregiver.id,
        consented_at=utcnow(),
    )
    session.add(link)

    settings = await session.scalar(
        select(PatientContentSettings).where(PatientContentSettings.patient_id == patient_id)
    )
    if settings is None:
        session.add(
            PatientContentSettings(
                patient_id=patient_id,
                development_band="middle",
                enabled_categories=dict(DEFAULT_ENABLED),
                updated_by=caregiver.id,
            )
        )

    await session.flush()
    await audit.record_event(
        session,
        actor_id=caregiver.id,
        action="activate_patient_account",
        entity_type="patient_user_link",
        entity_id=link.id,
        metadata={"patient_id": patient_id},
    )
    return account, link


async def set_account_status(
    session: AsyncSession, *, caregiver: User, patient_id: UUID, status: str
) -> PatientUserLink:
    """Suspende o reactiva la cuenta. **Nunca borra el registro asistencial.**"""
    await require_caregiver_of(session, caregiver, patient_id)

    link = await session.scalar(
        select(PatientUserLink).where(PatientUserLink.patient_id == patient_id)
    )
    if link is None:
        raise not_found("Este paciente no tiene cuenta")

    link.status = status
    link.suspended_at = utcnow() if status == "suspended" else None
    if status == "active":
        # Reactivar limpia el bloqueo por intentos fallidos.
        link.failed_attempts = 0
        link.locked_until = None
    await session.flush()

    await audit.record_event(
        session,
        actor_id=caregiver.id,
        action="set_patient_account_status",
        entity_type="patient_user_link",
        entity_id=link.id,
        metadata={"patient_id": patient_id, "status": status},
    )
    return link


async def update_content_settings(
    session: AsyncSession,
    *,
    caregiver: User,
    patient_id: UUID,
    development_band: str | None = None,
    enabled_categories: dict | None = None,
) -> PatientContentSettings:
    """El cuidador decide qué contenido está habilitado."""
    await require_caregiver_of(session, caregiver, patient_id)

    settings = await session.scalar(
        select(PatientContentSettings).where(PatientContentSettings.patient_id == patient_id)
    )
    if settings is None:
        settings = PatientContentSettings(
            patient_id=patient_id, enabled_categories=dict(DEFAULT_ENABLED)
        )
        session.add(settings)

    if development_band is not None:
        settings.development_band = development_band
    if enabled_categories is not None:
        merged = dict(settings.enabled_categories or DEFAULT_ENABLED)
        merged.update(
            {k: bool(v) for k, v in enabled_categories.items() if k in CONTENT_CATEGORIES}
        )
        settings.enabled_categories = merged
        settings.show_immediate_preparation = merged.get("immediate_preparation", True)

    settings.updated_by = caregiver.id
    await session.flush()
    return settings


# ------------------------------------------------------------ vista del menor


async def build_companion_view(
    session: AsyncSession, link: PatientUserLink, now: datetime | None = None
) -> dict:
    """Lo **único** que el menor puede ver.

    Se construye por lista blanca: aquí no entra ningún hito, alerta, riesgo,
    barrera, derivación ni dato operativo. Añadir algo a esta vista es una
    decisión deliberada, no un descuido de la interfaz.
    """
    settings = await session.scalar(
        select(PatientContentSettings).where(
            PatientContentSettings.patient_id == link.patient_id
        )
    )
    band = settings.development_band if settings else "middle"
    enabled = dict((settings.enabled_categories if settings else None) or DEFAULT_ENABLED)

    preferences = await session.scalar(
        select(CompanionPreferences).where(
            CompanionPreferences.patient_id == link.patient_id
        )
    )

    catalogue = ACTIVITIES.get(band, ACTIVITIES["middle"])
    activities = [a for a in catalogue if enabled.get(a["key"], True)]

    preparation = None
    if enabled.get("immediate_preparation", True) and (
        settings is None or settings.show_immediate_preparation
    ):
        preparation = await _immediate_preparation(session, link.patient_id, now)

    return {
        "greeting": GREETINGS.get(band, GREETINGS["middle"]),
        "chosen_name": preferences.chosen_name if preferences else None,
        "avatar_key": preferences.avatar_key if preferences else None,
        "comfort_object": preferences.comfort_object if preferences else None,
        "development_band": band,
        "activities": activities,
        "immediate_preparation": preparation,
    }


async def _immediate_preparation(
    session: AsyncSession, patient_id: UUID, now: datetime | None = None
) -> dict | None:
    """Preparación inmediata, **sin nombre clínico del procedimiento**.

    Se comunica cuándo y qué llevar. El título del hito («Procedimiento
    ambulatorio», «Laboratorio de control») no se muestra: RF-NNA-04 lo prohíbe
    por defecto, y esa información corresponde al cuidador.
    """
    from app.modules.care_routes import rules
    from app.modules.care_routes import service as care_routes

    milestones = list(
        await session.scalars(select(Milestone).where(Milestone.patient_id == patient_id))
    )
    views = [care_routes.to_milestone_view(m) for m in milestones]
    nxt = rules.get_next_milestone(str(patient_id), views)
    if nxt is None:
        return None

    milestone = next((m for m in milestones if str(m.id) == nxt.id), None)
    if milestone is None or milestone.scheduled_at is None:
        return None

    # Sólo se anuncia si es inminente: un calendario a futuro es carga
    # informativa que no le corresponde al menor.
    scheduled = milestone.scheduled_at.replace(tzinfo=UTC)
    hours = (scheduled - (now or utcnow())).total_seconds() / 3600
    if hours < 0 or hours > 48:
        return None

    when = to_display(milestone.scheduled_at)
    return {
        "when": when.strftime("%d/%m a las %H:%M"),
        "bring": milestone.preparation,
        "company": "Vas a ir con tu adulto de confianza.",
    }


# ------------------------------------------------------- emociones y apoyo


async def create_support_request(
    session: AsyncSession,
    *,
    account: User,
    link: PatientUserLink,
    request_type: str,
    operation_id: UUID | None = None,
) -> PatientSupportRequest:
    """Registra la petición y avisa al adulto. No interpreta su causa.

    Es idempotente por `operation_id`: un menor con la conexión intermitente
    puede reintentar sin que su adulto reciba el mismo aviso dos veces.
    """
    if operation_id is not None:
        existing = await session.scalar(
            select(PatientSupportRequest).where(
                PatientSupportRequest.operation_id == operation_id
            )
        )
        if existing is not None:
            return existing

    request = PatientSupportRequest(
        patient_id=link.patient_id,
        requested_by=account.id,
        request_type=request_type,
        status="open",
        created_at=utcnow(),
        operation_id=operation_id,
    )
    session.add(request)
    await session.flush()

    await notifications.notify_patient_circle(
        session,
        patient_id=link.patient_id,
        notification_type="patient_support_request",
        dedupe_key=f"support:{request.id}",
        audience="caregivers",
        payload={"requestType": request_type},
    )
    await audit.record_event(
        session,
        actor_id=account.id,
        action="patient_support_request",
        entity_type="patient_support_request",
        entity_id=request.id,
        metadata={"patient_id": link.patient_id, "request_type": request_type},
    )
    return request


async def list_support_requests(
    session: AsyncSession, patient_id: UUID
) -> list[PatientSupportRequest]:
    rows = await session.scalars(
        select(PatientSupportRequest)
        .where(PatientSupportRequest.patient_id == patient_id)
        .order_by(PatientSupportRequest.created_at.desc())
        .limit(50)
    )
    return list(rows)


async def acknowledge_support_request(
    session: AsyncSession, *, adult: User, request: PatientSupportRequest
) -> PatientSupportRequest:
    if request.status == "open":
        request.status = "acknowledged"
        request.acknowledged_at = utcnow()
        request.acknowledged_by = adult.id
        await session.flush()
    return request


async def update_preferences(
    session: AsyncSession,
    *,
    link: PatientUserLink,
    chosen_name: str | None = None,
    avatar_key: str | None = None,
    comfort_object: str | None = None,
) -> CompanionPreferences:
    preferences = await session.scalar(
        select(CompanionPreferences).where(
            CompanionPreferences.patient_id == link.patient_id
        )
    )
    if preferences is None:
        preferences = CompanionPreferences(patient_id=link.patient_id)
        session.add(preferences)

    if chosen_name is not None:
        preferences.chosen_name = chosen_name
    if avatar_key is not None:
        preferences.avatar_key = avatar_key
    if comfort_object is not None:
        preferences.comfort_object = comfort_object

    await session.flush()
    return preferences


# ------------------------------------------------------------------ acceso


def is_locked(link: PatientUserLink, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return link.locked_until is not None and link.locked_until.replace(tzinfo=UTC) > now


async def register_failed_attempt(session: AsyncSession, link: PatientUserLink) -> None:
    """Bloquea temporalmente tras varios intentos, sin tocar la ruta clínica."""
    link.failed_attempts += 1
    if link.failed_attempts >= MAX_FAILED_ATTEMPTS:
        link.locked_until = utcnow() + LOCK_DURATION
        link.failed_attempts = 0
    await session.flush()


async def register_successful_attempt(session: AsyncSession, link: PatientUserLink) -> None:
    link.failed_attempts = 0
    link.locked_until = None
    await session.flush()


async def find_link_by_alias(
    session: AsyncSession, patient_alias: str
) -> tuple[User, PatientUserLink] | None:
    """Busca la cuenta por alias visual, sin exigir correo al menor."""
    account = await session.scalar(
        select(User).where(User.display_name == patient_alias, User.role == "patient")
    )
    if account is None:
        return None
    link = await session.scalar(
        select(PatientUserLink).where(PatientUserLink.user_id == account.id)
    )
    if link is None:
        return None
    return account, link


async def patient_display_name(session: AsyncSession, patient_id: UUID) -> str:
    patient = await session.get(Patient, patient_id)
    return patient.display_name if patient else ""
