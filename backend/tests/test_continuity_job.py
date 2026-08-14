"""Trabajo periódico de continuidad.

Lo esencial: correrlo dos veces no debe cambiar nada respecto a correrlo una.
"""

from datetime import timedelta

from sqlalchemy import func, select

from app.core.time import utcnow
from app.jobs.process_continuity import run
from app.modules.alerts.models import BarrierAlert
from app.modules.milestones.models import Milestone
from app.modules.notifications.models import NotificationOutbox
from app.seed import MATEO_ID
from tests.conftest import auth


async def test_marks_overdue_milestone_as_missed(client, caregiver_token, session, seeded):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone_id = route.json()["nextMilestoneId"]

    milestone = await session.get(Milestone, milestone_id)
    milestone.scheduled_at = utcnow() - timedelta(hours=48)
    await session.commit()

    report = await run(session)
    assert report.milestones_marked_missed == 1

    await session.refresh(milestone)
    assert milestone.status == "missed"


async def test_job_is_idempotent(client, caregiver_token, session, seeded):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone = await session.get(Milestone, route.json()["nextMilestoneId"])
    milestone.scheduled_at = utcnow() - timedelta(hours=48)
    await session.commit()

    first = await run(session)
    notifications_after_first = await session.scalar(
        select(func.count()).select_from(NotificationOutbox)
    )

    second = await run(session)
    third = await run(session)
    notifications_after_third = await session.scalar(
        select(func.count()).select_from(NotificationOutbox)
    )

    assert first.milestones_marked_missed == 1
    assert second.milestones_marked_missed == 0
    assert third.milestones_marked_missed == 0
    assert notifications_after_first == notifications_after_third


async def test_confirmed_milestone_is_never_marked_missed(
    client, caregiver_token, session, seeded
):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone_id = route.json()["nextMilestoneId"]

    await client.post(
        f"/api/v1/milestones/{milestone_id}/confirmations",
        headers=auth(caregiver_token),
        json={},
    )
    milestone = await session.get(Milestone, milestone_id)
    milestone.scheduled_at = utcnow() - timedelta(hours=72)
    await session.commit()

    report = await run(session)
    await session.refresh(milestone)
    assert report.milestones_marked_missed == 0
    assert milestone.status != "missed"


async def test_detects_barriers_past_the_response_window(client, caregiver_token, session, seeded):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    created = await client.post(
        f"/api/v1/milestones/{route.json()['nextMilestoneId']}/barriers",
        headers=auth(caregiver_token),
        json={"category": "transport"},
    )

    alert = await session.get(BarrierAlert, created.json()["id"])
    alert.created_at = utcnow() - timedelta(hours=72)
    await session.commit()

    report = await run(session)
    assert report.overdue_barriers == 1


async def test_risk_escalates_even_before_the_job_runs(client, caregiver_token, session, seeded):
    """El semáforo no depende de que el trabajo periódico haya corrido."""
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    created = await client.post(
        f"/api/v1/milestones/{route.json()['nextMilestoneId']}/barriers",
        headers=auth(caregiver_token),
        json={"category": "transport"},
    )

    alert = await session.get(BarrierAlert, created.json()["id"])
    alert.created_at = utcnow() - timedelta(hours=72)
    await session.commit()

    # Sin ejecutar el job, la consulta ya devuelve rojo.
    refreshed = await client.get(
        f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token)
    )
    assert refreshed.json()["patient"]["operationalRisk"] == "red"
