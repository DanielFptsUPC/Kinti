"""Flujo familiar: consultar la ruta, confirmar asistencia y reportar barreras."""

from app.seed import MATEO_ID
from tests.conftest import auth


async def next_milestone_id(client, token) -> str:
    response = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(token))
    return response.json()["nextMilestoneId"]


async def test_route_exposes_derived_state(client, caregiver_token):
    response = await client.get(
        f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token)
    )
    body = response.json()

    assert body["patient"]["operationalRisk"] == "yellow"
    assert body["patient"]["routeStatus"] == "confirmation_needed"
    # Se afirma el comportamiento, no el tamaño del seed: la ruta trae hitos y
    # todos pertenecen al paciente consultado.
    assert body["milestones"]
    assert all(m["patientId"] == str(MATEO_ID) for m in body["milestones"])
    # El siguiente paso es un hito activo pendiente de confirmar, no uno completado.
    next_milestone = next(m for m in body["milestones"] if m["id"] == body["nextMilestoneId"])
    assert next_milestone["status"] != "completed"
    assert next_milestone["attendanceConfirmed"] is False


async def test_confirming_the_next_step_puts_the_route_on_track(client, caregiver_token):
    """El estado de ruta habla del siguiente paso, no de todos los hitos."""
    milestone_id = await next_milestone_id(client, caregiver_token)

    response = await client.post(
        f"/api/v1/milestones/{milestone_id}/confirmations",
        headers=auth(caregiver_token),
        json={},
    )
    assert response.status_code == 200
    assert response.json()["attendanceConfirmed"] is True

    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert route.json()["patient"]["routeStatus"] == "on_track"


async def test_patient_risk_aggregates_every_active_milestone(client, caregiver_token):
    """Verde exige que no quede ningún hito programado sin confirmar.

    Confirmar sólo el siguiente deja al paciente en amarillo mientras otro hito
    activo siga pendiente: el semáforo es el peor caso, no el del primero.
    """
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    pending = [
        m
        for m in route.json()["milestones"]
        if m["status"] in ("upcoming", "rescheduled") and not m["attendanceConfirmed"]
    ]
    assert len(pending) > 1, "el caso pierde sentido con un solo hito pendiente"

    # Confirmar sólo el primero no basta.
    await client.post(
        f"/api/v1/milestones/{pending[0]['id']}/confirmations",
        headers=auth(caregiver_token),
        json={},
    )
    after_one = await client.get(
        f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token)
    )
    assert after_one.json()["patient"]["operationalRisk"] == "yellow"

    # Con todos confirmados, sí.
    for milestone in pending[1:]:
        await client.post(
            f"/api/v1/milestones/{milestone['id']}/confirmations",
            headers=auth(caregiver_token),
            json={},
        )
    final = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert final.json()["patient"]["operationalRisk"] == "green"


async def test_confirming_twice_is_harmless(client, caregiver_token):
    milestone_id = await next_milestone_id(client, caregiver_token)
    for _ in range(2):
        response = await client.post(
            f"/api/v1/milestones/{milestone_id}/confirmations",
            headers=auth(caregiver_token),
            json={},
        )
        assert response.status_code == 200
        assert response.json()["attendanceConfirmed"] is True


async def test_report_barrier_opens_alert_and_moves_route(client, caregiver_token):
    milestone_id = await next_milestone_id(client, caregiver_token)

    response = await client.post(
        f"/api/v1/milestones/{milestone_id}/barriers",
        headers=auth(caregiver_token),
        json={"category": "transport", "note": "No tenemos pasajes esta semana"},
    )
    assert response.status_code == 200
    alert = response.json()
    assert alert["category"] == "transport"
    assert alert["status"] == "open"
    assert alert["risk"] == "yellow"
    assert alert["familyContacted"] is False

    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert route.json()["patient"]["routeStatus"] == "support_needed"


async def test_barrier_note_length_is_limited(client, caregiver_token):
    milestone_id = await next_milestone_id(client, caregiver_token)
    response = await client.post(
        f"/api/v1/milestones/{milestone_id}/barriers",
        headers=auth(caregiver_token),
        json={"category": "other", "note": "x" * 5000},
    )
    assert response.status_code == 422


async def test_invalid_barrier_category_is_rejected(client, caregiver_token):
    milestone_id = await next_milestone_id(client, caregiver_token)
    response = await client.post(
        f"/api/v1/milestones/{milestone_id}/barriers",
        headers=auth(caregiver_token),
        json={"category": "categoria-inventada"},
    )
    assert response.status_code == 422


async def test_record_feeling_does_not_change_risk(client, caregiver_token):
    """El estado emocional acompaña; no altera el semáforo ni crea alertas."""
    before = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))

    response = await client.post(
        f"/api/v1/patients/{MATEO_ID}/feelings",
        headers=auth(caregiver_token),
        json={"mood": "worried"},
    )
    assert response.status_code == 200
    assert response.json()["mood"] == "worried"

    after = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert (
        after.json()["patient"]["operationalRisk"]
        == before.json()["patient"]["operationalRisk"]
    )
    assert after.json()["alerts"] == before.json()["alerts"]
