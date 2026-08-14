"""Trabajo periódico de continuidad.

Detecta hitos vencidos y barreras que superaron la ventana de respuesta, genera
auditoría y encola avisos.

Es idempotente por construcción: un hito ya marcado como `missed` se ignora, y
los avisos se deduplican por `dedupe_key`. Ejecutarlo diez veces seguidas
produce exactamente el mismo estado que ejecutarlo una vez.

    python -m app.jobs.process_continuity

El riesgo NO depende de que este trabajo haya corrido: las consultas lo derivan
igual con el reloj del servidor. El job existe para materializar la inasistencia
y avisar, no para que el semáforo funcione.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.time import utcnow
from app.modules.alerts.models import BarrierAlert
from app.modules.care_routes import rules
from app.modules.care_routes.service import to_alert_view, to_milestone_view
from app.modules.milestones import service as milestones_service
from app.modules.milestones.models import Milestone
from app.modules.notifications import service as notifications


@dataclass
class ContinuityReport:
    milestones_marked_missed: int = 0
    overdue_barriers: int = 0
    notifications_created: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "milestonesMarkedMissed": self.milestones_marked_missed,
            "overdueBarriers": self.overdue_barriers,
            "notificationsCreated": self.notifications_created,
        }


async def run(session: AsyncSession) -> ContinuityReport:
    settings = get_settings()
    now = utcnow()
    report = ContinuityReport()

    # --- Hitos vencidos sin confirmación de asistencia -----------------------
    candidates = await session.scalars(
        select(Milestone).where(
            Milestone.status.in_(["upcoming", "rescheduled", "support_needed"]),
            Milestone.scheduled_at.is_not(None),
            Milestone.attendance_confirmed.is_(False),
        )
    )
    for milestone in candidates:
        if not rules.is_overdue(
            to_milestone_view(milestone), now, settings.missed_tolerance_hours
        ):
            continue
        await milestones_service.mark_missed(session, milestone=milestone)
        report.milestones_marked_missed += 1

        await notifications.notify_patient_circle(
            session,
            patient_id=milestone.patient_id,
            notification_type="milestone_missed",
            dedupe_key=f"missed:{milestone.id}",
            audience="both",
            payload={"milestoneId": str(milestone.id)},
        )

    # --- Barreras abiertas que superaron la ventana de respuesta -------------
    open_alerts = await session.scalars(
        select(BarrierAlert).where(BarrierAlert.status == "open")
    )
    for alert in open_alerts:
        risk = rules.compute_alert_risk(
            to_alert_view(alert), now, settings.barrier_response_window_hours
        )
        if risk != "red":
            continue
        report.overdue_barriers += 1
        await notifications.notify_patient_circle(
            session,
            patient_id=alert.patient_id,
            notification_type="barrier_received",
            dedupe_key=f"barrier_overdue:{alert.id}",
            audience="care_team",
            payload={"alertId": str(alert.id), "overdue": True},
        )

    # Los objetos nuevos que siguen pendientes en la sesión son los avisos creados.
    report.notifications_created = sum(
        1 for obj in session.new if obj.__class__.__name__ == "NotificationOutbox"
    )

    await session.commit()
    return report


async def main() -> None:
    async with SessionLocal() as session:
        report = await run(session)
    print("process_continuity:", report.as_dict())


if __name__ == "__main__":
    asyncio.run(main())
