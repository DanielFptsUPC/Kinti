from sqlalchemy import select

from app.modules.operations.models import AmbulatoryCapacitySlot
from app.modules.patients.models import CareTeamAssignment
from tests.conftest import auth


async def test_caregiver_cannot_read_operational_dashboard(client, caregiver_token):
    response = await client.get("/api/v1/operations/workload", headers=auth(caregiver_token))
    assert response.status_code == 403


async def test_workload_is_transparent_and_does_not_reassign(
    client, care_team_token, session, seeded
):
    assignments = select(CareTeamAssignment.user_id, CareTeamAssignment.patient_id)
    before = set((await session.execute(assignments)).all())
    response = await client.get("/api/v1/operations/workload", headers=auth(care_team_token))
    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 2
    assert body["maxDifference"] > 0
    assert "jefatura" in body["disclaimer"]
    after = set((await session.execute(assignments)).all())
    assert before == after


async def test_capacity_counts_only_milestones_inside_each_slot(
    client, care_team_token, session, seeded
):
    slot = await session.scalar(
        select(AmbulatoryCapacitySlot).order_by(AmbulatoryCapacitySlot.starts_at)
    )
    response = await client.get(
        "/api/v1/operations/capacity",
        params={"day": slot.starts_at.isoformat()},
        headers=auth(care_team_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["slots"]) == 3
    assert any(row["scheduledPatients"] == 2 for row in body["slots"])
    assert all(
        row["state"] in {"underused", "balanced", "high", "overbooked"}
        for row in body["slots"]
    )


async def test_social_work_queue_exposes_recovery_state(client, care_team_token, seeded):
    response = await client.get("/api/v1/operations/social-work", headers=auth(care_team_token))
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert any(row["patientName"] == "Valentina" for row in rows)
    assert all(
        row["coordinationStatus"] in {"pending", "contacted", "referred", "resolved"}
        for row in rows
    )
