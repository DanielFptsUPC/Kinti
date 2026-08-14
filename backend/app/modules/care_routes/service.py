"""Modelo de lectura: convierte filas en las vistas que consume el cliente.

Todo lo derivado (riesgo operativo, estado de ruta, siguiente hito, riesgo de la
alerta) se calcula aquí en cada consulta, usando el reloj del servidor. Nunca se
lee de la base ni se acepta del cliente.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.modules.alerts.models import BarrierAlert
from app.modules.care_routes import rules
from app.modules.feelings.models import FeelingCheckIn
from app.modules.interventions.models import Intervention
from app.modules.milestones.models import Milestone
from app.modules.patients.models import Patient


@dataclass
class PatientContext:
    """Todo lo necesario para derivar el estado de un conjunto de pacientes."""

    patients: list[Patient]
    milestones: list[Milestone]
    alerts: list[BarrierAlert]
    interventions: dict[UUID, Intervention]
    now: datetime


def to_milestone_view(milestone: Milestone) -> rules.MilestoneView:
    return rules.MilestoneView(
        id=str(milestone.id),
        patient_id=str(milestone.patient_id),
        status=milestone.status,
        attendance_confirmed=milestone.attendance_confirmed,
        scheduled_at=as_utc(milestone.scheduled_at) if milestone.scheduled_at else None,
    )


def to_alert_view(alert: BarrierAlert) -> rules.AlertView:
    return rules.AlertView(
        id=str(alert.id),
        milestone_id=str(alert.milestone_id),
        status=alert.status,
        created_at=as_utc(alert.created_at),
    )


async def load_context(session: AsyncSession, patient_ids: list[UUID]) -> PatientContext:
    """Carga en bloque el estado de los pacientes autorizados."""
    if not patient_ids:
        return PatientContext([], [], [], {}, utcnow())

    patients = list(
        await session.scalars(
            select(Patient).where(Patient.id.in_(patient_ids)).order_by(Patient.display_name)
        )
    )
    milestones = list(
        await session.scalars(select(Milestone).where(Milestone.patient_id.in_(patient_ids)))
    )
    alerts = list(
        await session.scalars(select(BarrierAlert).where(BarrierAlert.patient_id.in_(patient_ids)))
    )

    interventions: dict[UUID, Intervention] = {}
    if alerts:
        alert_ids = [a.id for a in alerts]
        rows = await session.scalars(
            select(Intervention)
            .where(Intervention.alert_id.in_(alert_ids))
            .order_by(Intervention.performed_at)
        )
        # La última intervención de cada alerta es la que se muestra como acción tomada.
        for intervention in rows:
            interventions[intervention.alert_id] = intervention

    return PatientContext(patients, milestones, alerts, interventions, utcnow())


def patient_payload(context: PatientContext, patient: Patient) -> dict:
    settings = get_settings()
    milestone_views = [to_milestone_view(m) for m in context.milestones]
    alert_views = [to_alert_view(a) for a in context.alerts]
    patient_key = str(patient.id)

    return {
        "id": patient.id,
        "display_name": patient.display_name,
        "age": patient.age,
        "avatar_key": patient.avatar_key,
        "caregiver_name": patient.caregiver_name,
        "contact_phone": patient.contact_phone,
        "operational_risk": rules.compute_patient_operational_risk(
            patient_key,
            milestone_views,
            alert_views,
            context.now,
            settings.barrier_response_window_hours,
        ),
        "route_status": rules.compute_patient_route_status(
            patient_key, milestone_views, alert_views
        ),
    }


def milestone_payload(milestone: Milestone) -> dict:
    return {
        "id": milestone.id,
        "patient_id": milestone.patient_id,
        "type": milestone.type,
        "title": milestone.title,
        "scheduled_at": as_utc(milestone.scheduled_at) if milestone.scheduled_at else None,
        "location": milestone.location,
        "preparation": milestone.preparation,
        "service": milestone.service,
        "confirmation_deadline": (
            as_utc(milestone.confirmation_deadline) if milestone.confirmation_deadline else None
        ),
        "status": milestone.status,
        "attendance_confirmed": milestone.attendance_confirmed,
        "version": milestone.version,
    }


def alert_payload(context: PatientContext, alert: BarrierAlert) -> dict:
    settings = get_settings()
    intervention = context.interventions.get(alert.id)
    return {
        "id": alert.id,
        "patient_id": alert.patient_id,
        "milestone_id": alert.milestone_id,
        "category": alert.category,
        "note": alert.note,
        "status": alert.status,
        "risk": rules.compute_alert_risk(
            to_alert_view(alert), context.now, settings.barrier_response_window_hours
        ),
        "family_contacted": alert.first_contact_at is not None,
        "action_taken": intervention.action_type if intervention else None,
        "internal_note": intervention.internal_note if intervention else None,
        "created_at": as_utc(alert.created_at),
        "resolved_at": as_utc(alert.resolved_at) if alert.resolved_at else None,
    }


def feeling_payload(feeling: FeelingCheckIn) -> dict:
    return {
        "id": feeling.id,
        "patient_id": feeling.patient_id,
        "mood": feeling.mood,
        "created_at": as_utc(feeling.created_at),
    }


def next_milestone_for(context: PatientContext, patient_id: UUID) -> Milestone | None:
    view = rules.get_next_milestone(
        str(patient_id), [to_milestone_view(m) for m in context.milestones]
    )
    if view is None:
        return None
    return next((m for m in context.milestones if str(m.id) == view.id), None)
