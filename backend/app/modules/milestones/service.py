"""Comandos sobre hitos.

El servidor es la autoridad sobre fechas y estados: estas funciones son el único
lugar donde un hito cambia, y todas suben `version` para que el cliente pueda
detectar que su copia quedó atrás.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import invalid, not_found
from app.core.time import as_utc, utcnow
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.milestones.models import AttendanceConfirmation, Milestone
from app.modules.notifications import service as notifications


async def get_milestone(session: AsyncSession, milestone_id: UUID) -> Milestone:
    milestone = await session.scalar(select(Milestone).where(Milestone.id == milestone_id))
    if milestone is None:
        raise not_found("Hito no encontrado")
    return milestone


def _touch(milestone: Milestone, actor: User) -> None:
    milestone.version += 1
    milestone.updated_by = actor.id
    milestone.updated_at = utcnow()


async def confirm_attendance(
    session: AsyncSession,
    *,
    actor: User,
    milestone: Milestone,
    operation_id: UUID | None = None,
) -> Milestone:
    """La familia confirma que podrá asistir.

    Es idempotente por naturaleza: confirmar dos veces deja el mismo estado.
    """
    if milestone.status == "missed":
        raise invalid("milestone_missed", "El hito ya fue registrado como inasistencia")

    already_confirmed = milestone.attendance_confirmed
    milestone.attendance_confirmed = True
    if milestone.status == "unscheduled":
        milestone.status = "upcoming"
    _touch(milestone, actor)

    if not already_confirmed:
        session.add(
            AttendanceConfirmation(
                milestone_id=milestone.id,
                caregiver_id=actor.id,
                confirmed_at=utcnow(),
                operation_id=operation_id,
            )
        )

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="confirm_attendance",
        entity_type="milestone",
        entity_id=milestone.id,
        metadata={"patient_id": milestone.patient_id, "version": milestone.version},
    )
    return milestone


async def create_milestone(
    session: AsyncSession,
    *,
    actor: User,
    patient_id: UUID,
    type: str,
    title: str,
    scheduled_at: datetime | None = None,
    location: str | None = None,
    preparation: str | None = None,
    service: str | None = None,
    confirmation_deadline: datetime | None = None,
) -> Milestone:
    """El equipo registra el siguiente paso de la familia."""
    milestone = Milestone(
        patient_id=patient_id,
        type=type,
        title=title,
        scheduled_at=as_utc(scheduled_at) if scheduled_at else None,
        location=location,
        preparation=preparation,
        service=service,
        confirmation_deadline=(
            as_utc(confirmation_deadline) if confirmation_deadline else None
        ),
        status="upcoming" if scheduled_at else "unscheduled",
        attendance_confirmed=False,
        version=1,
        created_by=actor.id,
        updated_by=actor.id,
    )
    session.add(milestone)
    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="create_milestone",
        entity_type="milestone",
        entity_id=milestone.id,
        metadata={"patient_id": patient_id, "type": type},
    )
    await notifications.notify_patient_circle(
        session,
        patient_id=patient_id,
        notification_type="confirmation_request",
        dedupe_key=f"confirmation_request:{milestone.id}",
        audience="caregivers",
        payload={"milestoneId": str(milestone.id), "title": title},
    )
    return milestone


async def reschedule(
    session: AsyncSession,
    *,
    actor: User,
    milestone: Milestone,
    new_scheduled_at: datetime,
) -> Milestone:
    """Aplica una nueva fecha oficial.

    Reprogramar reabre la confirmación: la familia debe volver a decir si podrá
    asistir a la fecha nueva.
    """
    new_date = as_utc(new_scheduled_at)
    if new_date < utcnow():
        raise invalid("date_in_past", "La nueva fecha no puede estar en el pasado")

    milestone.scheduled_at = new_date
    milestone.status = "rescheduled"
    milestone.attendance_confirmed = False
    _touch(milestone, actor)

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="reschedule_milestone",
        entity_type="milestone",
        entity_id=milestone.id,
        metadata={
            "patient_id": milestone.patient_id,
            "new_scheduled_at": new_date.isoformat(),
            "version": milestone.version,
        },
    )
    await notifications.notify_patient_circle(
        session,
        patient_id=milestone.patient_id,
        notification_type="milestone_rescheduled",
        dedupe_key=f"rescheduled:{milestone.id}:{milestone.version}",
        audience="caregivers",
        payload={"milestoneId": str(milestone.id), "scheduledAt": new_date.isoformat()},
    )
    return milestone


async def mark_missed(session: AsyncSession, *, milestone: Milestone) -> Milestone:
    """Marca inasistencia. Lo ejecuta el trabajo periódico, no un usuario."""
    milestone.status = "missed"
    milestone.version += 1
    milestone.updated_at = utcnow()

    await audit.record_event(
        session,
        actor_id=None,
        action="mark_missed",
        entity_type="milestone",
        entity_id=milestone.id,
        metadata={"patient_id": milestone.patient_id, "source": "process_continuity"},
    )
    return milestone
