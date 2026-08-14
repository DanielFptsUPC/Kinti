"""Auditoría de escrituras.

Cada intervención deja rastro, y ese rastro no puede contener el texto que
escribió la familia ni la nota interna del profesional.
"""

from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.seed import MATEO_ID
from tests.conftest import auth


async def actions(session) -> list[str]:
    rows = await session.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at))
    return list(rows)


async def test_confirming_attendance_is_audited(client, caregiver_token, session):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone_id = route.json()["nextMilestoneId"]

    await client.post(
        f"/api/v1/milestones/{milestone_id}/confirmations",
        headers=auth(caregiver_token),
        json={},
    )
    assert "confirm_attendance" in await actions(session)


async def test_full_circuit_leaves_a_complete_trail(
    client, caregiver_token, care_team_token, session
):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone_id = route.json()["nextMilestoneId"]

    created = await client.post(
        f"/api/v1/milestones/{milestone_id}/barriers",
        headers=auth(caregiver_token),
        json={"category": "transport", "note": "No tenemos pasajes"},
    )
    alert_id = created.json()["id"]

    await client.post(f"/api/v1/alerts/{alert_id}/contact", headers=auth(care_team_token), json={})
    await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=auth(care_team_token),
        json={"actionTaken": "transport_coordination", "internalNote": "Nota interna ficticia"},
    )

    recorded = await actions(session)
    assert "report_barrier" in recorded
    assert "mark_family_contacted" in recorded
    assert "resolve_alert" in recorded


async def test_audit_never_stores_free_text_notes(
    client, caregiver_token, care_team_token, session
):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone_id = route.json()["nextMilestoneId"]

    family_note = "Mi hijo se siente mal y no tenemos dinero"
    created = await client.post(
        f"/api/v1/milestones/{milestone_id}/barriers",
        headers=auth(caregiver_token),
        json={"category": "financial", "note": family_note},
    )
    internal_note = "Coordinado con trabajo social, expediente ficticio 123"
    await client.post(
        f"/api/v1/alerts/{created.json()['id']}/refer-social-work",
        headers=auth(care_team_token),
        json={"internalNote": internal_note},
    )

    events = list(await session.scalars(select(AuditEvent)))
    dumped = str([event.metadata_json for event in events])
    assert family_note not in dumped
    assert internal_note not in dumped
    # Pero sí queda el qué: categoría y acción.
    assert "financial" in dumped
    assert "social_work_referral" in dumped


async def test_audit_records_the_actor(client, caregiver_token, session):
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    await client.post(
        f"/api/v1/milestones/{route.json()['nextMilestoneId']}/confirmations",
        headers=auth(caregiver_token),
        json={},
    )
    event = await session.scalar(
        select(AuditEvent).where(AuditEvent.action == "confirm_attendance")
    )
    assert event.actor_id is not None
    assert event.entity_type == "milestone"
