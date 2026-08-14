"""Comandos sobre barreras y alertas.

La familia sólo puede abrir una alerta; contactar, intervenir y cerrar es
potestad del equipo asistencial. Esa asimetría se aplica en el servidor, no en
la interfaz.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import invalid, not_found
from app.core.time import utcnow
from app.modules.alerts.models import BarrierAlert
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.interventions.models import Intervention
from app.modules.milestones import service as milestones_service
from app.modules.milestones.models import Milestone
from app.modules.notifications import service as notifications


async def get_alert(session: AsyncSession, alert_id: UUID) -> BarrierAlert:
    alert = await session.scalar(select(BarrierAlert).where(BarrierAlert.id == alert_id))
    if alert is None:
        raise not_found("Alerta no encontrada")
    return alert


async def report_barrier(
    session: AsyncSession,
    *,
    actor: User,
    milestone: Milestone,
    category: str,
    note: str | None = None,
    operation_id: UUID | None = None,
) -> BarrierAlert:
    """La familia informa una dificultad para cumplir su siguiente paso.

    Nunca se rechaza por falta de conexión ni se convierte en triaje clínico:
    sólo abre una alerta operativa para que alguien la revise.
    """
    alert = BarrierAlert(
        patient_id=milestone.patient_id,
        milestone_id=milestone.id,
        category=category,
        note=note or None,
        status="open",
        reported_by=actor.id,
        operation_id=operation_id,
    )
    session.add(alert)

    # Una inasistencia ya registrada es un estado más grave: no se degrada.
    if milestone.status != "missed":
        milestone.status = "support_needed"
        milestone.version += 1
        milestone.updated_at = utcnow()

    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="report_barrier",
        entity_type="barrier_alert",
        entity_id=alert.id,
        metadata={
            "patient_id": milestone.patient_id,
            "milestone_id": milestone.id,
            "category": category,
        },
    )
    await notifications.notify_patient_circle(
        session,
        patient_id=milestone.patient_id,
        notification_type="barrier_received",
        dedupe_key=f"barrier_received:{alert.id}",
        audience="care_team",
        payload={"alertId": str(alert.id), "category": category},
    )
    return alert


async def mark_family_contacted(
    session: AsyncSession, *, actor: User, alert: BarrierAlert
) -> BarrierAlert:
    """Registra el primer contacto con la familia y pasa la alerta a gestión."""
    if alert.status == "resolved":
        raise invalid("alert_resolved", "La alerta ya fue resuelta")

    if alert.first_contact_at is None:
        alert.first_contact_at = utcnow()
        alert.first_contact_by = actor.id
    if alert.status == "open":
        alert.status = "in_progress"
    alert.updated_at = utcnow()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="mark_family_contacted",
        entity_type="barrier_alert",
        entity_id=alert.id,
        metadata={"patient_id": alert.patient_id},
    )
    return alert


async def refer_to_social_work(
    session: AsyncSession,
    *,
    actor: User,
    alert: BarrierAlert,
    internal_note: str | None = None,
    operation_id: UUID | None = None,
) -> BarrierAlert:
    """Deriva el caso sin cerrarlo: Servicio Social debe poder gestionarlo y devolverlo."""
    if alert.status == "resolved":
        raise invalid("alert_resolved", "La alerta ya fue resuelta")

    existing = await session.scalar(
        select(Intervention).where(
            Intervention.alert_id == alert.id,
            Intervention.action_type == "social_work_referral",
        )
    )
    if existing is not None:
        return alert

    session.add(
        Intervention(
            alert_id=alert.id,
            action_type="social_work_referral",
            internal_note=internal_note or None,
            performed_by=actor.id,
            performed_at=utcnow(),
            operation_id=operation_id,
        )
    )
    alert.status = "in_progress"
    alert.updated_at = utcnow()
    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="refer_social_work",
        entity_type="barrier_alert",
        entity_id=alert.id,
        metadata={
            "patient_id": alert.patient_id,
            "area": "social_work",
            "action_taken": "social_work_referral",
        },
    )
    return alert


async def resolve(
    session: AsyncSession,
    *,
    actor: User,
    alert: BarrierAlert,
    action_taken: str,
    internal_note: str | None = None,
    new_scheduled_at: datetime | None = None,
    operation_id: UUID | None = None,
) -> BarrierAlert:
    """Cierra el circuito: registra la intervención y devuelve la ruta a la familia."""
    if alert.status == "resolved":
        raise invalid("alert_resolved", "La alerta ya fue resuelta")
    if action_taken == "social_work_referral":
        raise invalid(
            "referral_not_resolution",
            "Derivar a Servicio Social mantiene la alerta en gestión",
        )
    if action_taken == "reschedule" and new_scheduled_at is None:
        raise invalid("date_required", "Una reprogramación necesita una nueva fecha")

    milestone = await milestones_service.get_milestone(session, alert.milestone_id)

    session.add(
        Intervention(
            alert_id=alert.id,
            action_type=action_taken,
            internal_note=internal_note or None,
            performed_by=actor.id,
            performed_at=utcnow(),
            new_scheduled_at=new_scheduled_at,
            operation_id=operation_id,
        )
    )

    alert.status = "resolved"
    alert.resolved_at = utcnow()
    alert.resolved_by = actor.id
    alert.updated_at = utcnow()

    if new_scheduled_at is not None:
        await milestones_service.reschedule(
            session, actor=actor, milestone=milestone, new_scheduled_at=new_scheduled_at
        )
    elif milestone.status == "support_needed":
        # Sin nueva fecha, el hito vuelve a su curso normal.
        milestone.status = "upcoming"
        milestone.version += 1
        milestone.updated_by = actor.id
        milestone.updated_at = utcnow()

    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="resolve_alert",
        entity_type="barrier_alert",
        entity_id=alert.id,
        metadata={
            "patient_id": alert.patient_id,
            "action_taken": action_taken,
            "rescheduled": new_scheduled_at is not None,
        },
    )
    await notifications.notify_patient_circle(
        session,
        patient_id=alert.patient_id,
        notification_type="alert_resolved",
        dedupe_key=f"alert_resolved:{alert.id}",
        audience="caregivers",
        payload={"alertId": str(alert.id), "actionTaken": action_taken},
    )
    return alert
