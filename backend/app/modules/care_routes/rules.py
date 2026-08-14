"""Reglas de riesgo operativo. Puerto directo de `src/logic/risk.ts`.

Este módulo es deliberadamente puro: no importa FastAPI, SQLAlchemy ni la
configuración global. Recibe vistas ligeras y un instante `now` explícito, de
modo que las pruebas de paridad con TypeScript puedan fijar el reloj.

El semáforo representa riesgo operativo de interrupción de la ruta, nunca
gravedad clínica.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

MilestoneStatus = Literal[
    "completed", "upcoming", "unscheduled", "support_needed", "rescheduled", "missed"
]
AlertStatus = Literal["open", "in_progress", "resolved"]
OperationalRisk = Literal["green", "yellow", "red"]
RouteStatus = Literal["on_track", "confirmation_needed", "support_needed"]

#: Ventana simulada por defecto antes de que una barrera abierta escale a rojo.
DEFAULT_BARRIER_RESPONSE_WINDOW_HOURS = 48

#: Orden de urgencia entre hitos activos. Coincide con ACTIVE_MILESTONE_PRIORITY del cliente.
ACTIVE_MILESTONE_PRIORITY: dict[str, int] = {
    "missed": 0,
    "support_needed": 1,
    "upcoming": 2,
    "rescheduled": 2,
    "unscheduled": 3,
    "completed": 99,
}

_FAR_FUTURE = float("inf")


@dataclass(frozen=True)
class MilestoneView:
    id: str
    patient_id: str
    status: MilestoneStatus
    attendance_confirmed: bool
    scheduled_at: datetime | None = None


@dataclass(frozen=True)
class AlertView:
    id: str
    milestone_id: str
    status: AlertStatus
    created_at: datetime


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _hours_between(start: datetime, now: datetime) -> float:
    return (_aware(now) - _aware(start)).total_seconds() / 3600


def _scheduled_key(milestone: MilestoneView) -> float:
    if milestone.scheduled_at is None:
        return _FAR_FUTURE
    return _aware(milestone.scheduled_at).timestamp()


def get_active_milestones(
    patient_id: str, milestones: list[MilestoneView]
) -> list[MilestoneView]:
    """Hitos no completados del paciente, ordenados por urgencia y luego por fecha."""
    active = [m for m in milestones if m.patient_id == patient_id and m.status != "completed"]
    return sorted(
        active,
        key=lambda m: (ACTIVE_MILESTONE_PRIORITY[m.status], _scheduled_key(m)),
    )


def get_next_milestone(
    patient_id: str, milestones: list[MilestoneView]
) -> MilestoneView | None:
    """El hito que la familia ve como «tu siguiente paso»."""
    active = get_active_milestones(patient_id, milestones)
    return active[0] if active else None


def compute_milestone_risk(
    milestone: MilestoneView,
    alerts: list[AlertView],
    now: datetime,
    window_hours: int = DEFAULT_BARRIER_RESPONSE_WINDOW_HOURS,
) -> OperationalRisk:
    """Riesgo operativo de un hito.

    verde: confirmado y sin barreras.
    amarillo: pendiente de confirmación, o barrera reportada.
    rojo: inasistencia, o barrera abierta que superó la ventana de respuesta.
    """
    if milestone.status == "missed":
        return "red"

    open_alert = next(
        (a for a in alerts if a.milestone_id == milestone.id and a.status == "open"), None
    )
    if open_alert is not None:
        return "red" if _hours_between(open_alert.created_at, now) > window_hours else "yellow"

    has_in_progress = any(
        a.milestone_id == milestone.id and a.status == "in_progress" for a in alerts
    )
    if has_in_progress or milestone.status == "support_needed":
        return "yellow"

    # Un hito sin fecha no está "pendiente de confirmación": no hay nada que
    # confirmar todavía. Sólo está pendiente de programación, y eso no pone en
    # riesgo la continuidad de la familia.
    if milestone.status == "unscheduled":
        return "green"

    if not milestone.attendance_confirmed:
        return "yellow"

    return "green"


def compute_patient_operational_risk(
    patient_id: str,
    milestones: list[MilestoneView],
    alerts: list[AlertView],
    now: datetime,
    window_hours: int = DEFAULT_BARRIER_RESPONSE_WINDOW_HOURS,
) -> OperationalRisk:
    """Peor riesgo entre los hitos activos del paciente."""
    active = get_active_milestones(patient_id, milestones)
    if not active:
        return "green"
    risks = [compute_milestone_risk(m, alerts, now, window_hours) for m in active]
    if "red" in risks:
        return "red"
    if "yellow" in risks:
        return "yellow"
    return "green"


def compute_route_status(
    next_milestone: MilestoneView | None, alerts: list[AlertView]
) -> RouteStatus:
    """Estado que ve la familia: qué debe hacer respecto a su siguiente paso."""
    if next_milestone is None:
        return "on_track"

    has_open_barrier = any(
        a.milestone_id == next_milestone.id and a.status != "resolved" for a in alerts
    )
    if (
        has_open_barrier
        or next_milestone.status == "support_needed"
        or next_milestone.status == "missed"
    ):
        return "support_needed"
    if not next_milestone.attendance_confirmed:
        return "confirmation_needed"
    return "on_track"


def compute_patient_route_status(
    patient_id: str, milestones: list[MilestoneView], alerts: list[AlertView]
) -> RouteStatus:
    return compute_route_status(get_next_milestone(patient_id, milestones), alerts)


def compute_alert_risk(
    alert: AlertView, now: datetime, window_hours: int = DEFAULT_BARRIER_RESPONSE_WINDOW_HOURS
) -> OperationalRisk:
    """Riesgo derivado de una alerta. El cliente nunca puede imponerlo."""
    if alert.status == "resolved":
        return "green"
    if alert.status == "open" and _hours_between(alert.created_at, now) > window_hours:
        return "red"
    return "yellow"


def is_overdue(
    milestone: MilestoneView, now: datetime, tolerance_hours: int
) -> bool:
    """Un hito programado que ya pasó su tolerancia sin confirmación de asistencia."""
    if milestone.status in ("completed", "missed", "unscheduled"):
        return False
    if milestone.scheduled_at is None:
        return False
    if milestone.attendance_confirmed:
        return False
    return _hours_between(milestone.scheduled_at, now) > tolerance_hours
