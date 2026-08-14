from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alerts.models import BarrierAlert
from app.modules.care_routes import service as care_routes
from app.modules.identity.models import User
from app.modules.interventions.models import Intervention
from app.modules.milestones.models import Milestone
from app.modules.operations.models import AmbulatoryCapacitySlot
from app.modules.patients.models import CareTeamAssignment, Patient

AMBULATORY_SERVICES = {"Clínica de día", "Hematología ambulatoria"}


@dataclass(frozen=True)
class WorkloadRow:
    professional: User
    assigned_patients: int
    red_patients: int
    yellow_patients: int
    open_alerts: int
    missed_milestones: int
    weighted_load: int


@dataclass(frozen=True)
class CapacityRow:
    slot: AmbulatoryCapacitySlot
    scheduled_patients: int

    @property
    def occupancy_percent(self) -> int:
        if self.slot.available_places <= 0:
            return 0
        return ceil(self.scheduled_patients * 100 / self.slot.available_places)

    @property
    def state(self) -> str:
        if self.scheduled_patients > self.slot.available_places:
            return "overbooked"
        if self.occupancy_percent >= 85:
            return "high"
        if self.occupancy_percent < 40:
            return "underused"
        return "balanced"


def social_work_status(alert: BarrierAlert, action_types: set[str]) -> str:
    if alert.status == "resolved" and "social_work_referral" in action_types:
        return "resolved"
    if "social_work_referral" in action_types:
        return "referred"
    if alert.status == "in_progress":
        return "contacted"
    return "pending"


async def workload(session: AsyncSession) -> list[WorkloadRow]:
    professionals = list(
        await session.scalars(
            select(User)
            .where(User.role == "care_team", User.is_active.is_(True))
            .order_by(User.display_name)
        )
    )
    rows: list[WorkloadRow] = []
    for professional in professionals:
        patient_ids = list(
            await session.scalars(
                select(CareTeamAssignment.patient_id).where(
                    CareTeamAssignment.user_id == professional.id,
                    CareTeamAssignment.is_active.is_(True),
                )
            )
        )
        context = await care_routes.load_context(session, patient_ids)
        red = yellow = 0
        for patient in context.patients:
            risk = care_routes.patient_payload(context, patient)["operational_risk"]
            red += risk == "red"
            yellow += risk == "yellow"
        open_alerts = sum(1 for alert in context.alerts if alert.status != "resolved")
        missed = sum(1 for milestone in context.milestones if milestone.status == "missed")
        # Puntaje transparente de carga operativa, no recomendación clínica.
        weighted = len(patient_ids) + (yellow * 2) + (red * 4) + open_alerts + (missed * 2)
        rows.append(
            WorkloadRow(
                professional=professional,
                assigned_patients=len(patient_ids),
                red_patients=red,
                yellow_patients=yellow,
                open_alerts=open_alerts,
                missed_milestones=missed,
                weighted_load=weighted,
            )
        )
    return sorted(rows, key=lambda row: (-row.weighted_load, row.professional.display_name))


async def capacity(
    session: AsyncSession, *, date_from: datetime, date_to: datetime
) -> list[CapacityRow]:
    slots = list(
        await session.scalars(
            select(AmbulatoryCapacitySlot)
            .where(
                AmbulatoryCapacitySlot.starts_at >= date_from,
                AmbulatoryCapacitySlot.starts_at < date_to,
            )
            .order_by(AmbulatoryCapacitySlot.starts_at)
        )
    )
    rows: list[CapacityRow] = []
    for slot in slots:
        scheduled = await session.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(
                Milestone.service == slot.service,
                Milestone.scheduled_at >= slot.starts_at,
                Milestone.scheduled_at < slot.ends_at,
                Milestone.status.in_(["upcoming", "rescheduled", "support_needed"]),
            )
        )
        rows.append(CapacityRow(slot=slot, scheduled_patients=int(scheduled or 0)))
    return rows


async def social_work_queue(session: AsyncSession) -> list[tuple[BarrierAlert, Patient, str]]:
    alerts = list(
        await session.scalars(
            select(BarrierAlert)
            .where(BarrierAlert.status != "resolved")
            .order_by(BarrierAlert.created_at)
        )
    )
    rows: list[tuple[BarrierAlert, Patient, str]] = []
    for alert in alerts:
        patient = await session.get(Patient, alert.patient_id)
        if patient is None:
            continue
        action_types = set(
            await session.scalars(
                select(Intervention.action_type).where(Intervention.alert_id == alert.id)
            )
        )
        rows.append((alert, patient, social_work_status(alert, action_types)))
    return rows


def default_window(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)

