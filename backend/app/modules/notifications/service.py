from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.notifications.models import NotificationOutbox
from app.modules.patients.models import CaregiverPatientLink, CareTeamAssignment

#: Texto que ve el usuario. Sin lenguaje culpabilizador y sin contenido clínico.
NOTIFICATION_COPY: dict[str, tuple[str, str]] = {
    "upcoming_milestone": ("Tu siguiente paso está cerca", "Revisa la fecha y el lugar."),
    "confirmation_request": (
        "¿Podrán asistir?",
        "Confírmanos para que el equipo sepa cómo acompañarlos.",
    ),
    "barrier_received": (
        "Barrera reportada",
        "Una familia informó una dificultad y espera respuesta.",
    ),
    "milestone_rescheduled": ("Nueva fecha coordinada", "Tu ruta se actualizó con la nueva cita."),
    "alert_resolved": ("Solicitud atendida", "El equipo registró una acción sobre tu solicitud."),
    "milestone_missed": (
        "No pudimos confirmar tu asistencia",
        "El equipo revisará el caso para reprogramar.",
    ),
}


async def enqueue(
    session: AsyncSession,
    *,
    recipient_id: UUID,
    notification_type: str,
    dedupe_key: str,
    patient_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    scheduled_for: datetime | None = None,
) -> NotificationOutbox | None:
    """Encola un aviso. Devuelve `None` si ya existía uno con la misma clave.

    La deduplicación por `dedupe_key` es lo que hace idempotente al trabajo
    periódico: correrlo dos veces no genera avisos repetidos.
    """
    existing = await session.scalar(
        select(NotificationOutbox).where(NotificationOutbox.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return None

    notification = NotificationOutbox(
        recipient_id=recipient_id,
        patient_id=patient_id,
        type=notification_type,
        payload=payload,
        status="pending",
        attempts=0,
        scheduled_for=scheduled_for or utcnow(),
        dedupe_key=dedupe_key,
    )
    session.add(notification)
    return notification


async def recipients_for_patient(session: AsyncSession, patient_id: UUID) -> dict[str, list[UUID]]:
    """Usuarios que deben enterarse de algo que ocurre con un paciente."""
    caregivers = list(
        await session.scalars(
            select(CaregiverPatientLink.caregiver_id).where(
                CaregiverPatientLink.patient_id == patient_id,
                CaregiverPatientLink.is_active.is_(True),
            )
        )
    )
    team = list(
        await session.scalars(
            select(CareTeamAssignment.user_id).where(
                CareTeamAssignment.patient_id == patient_id,
                CareTeamAssignment.is_active.is_(True),
            )
        )
    )
    return {"caregivers": caregivers, "care_team": team}


async def notify_patient_circle(
    session: AsyncSession,
    *,
    patient_id: UUID,
    notification_type: str,
    dedupe_key: str,
    audience: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Encola un aviso para la familia, el equipo o ambos."""
    circle = await recipients_for_patient(session, patient_id)
    targets: list[UUID] = []
    if audience in ("caregivers", "both"):
        targets += circle["caregivers"]
    if audience in ("care_team", "both"):
        targets += circle["care_team"]

    for recipient_id in targets:
        await enqueue(
            session,
            recipient_id=recipient_id,
            notification_type=notification_type,
            dedupe_key=f"{dedupe_key}:{recipient_id}",
            patient_id=patient_id,
            payload=payload,
        )


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[NotificationOutbox]:
    rows = await session.scalars(
        select(NotificationOutbox)
        .where(NotificationOutbox.recipient_id == user_id)
        .order_by(NotificationOutbox.scheduled_for.desc())
        .limit(50)
    )
    return list(rows)
