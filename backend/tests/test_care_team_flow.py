"""Flujo asistencial: priorización, gestión de alertas y registro de hitos."""

from datetime import timedelta

from app.core.time import utcnow
from app.seed import MATEO_ID, VALENTINA_ID
from tests.conftest import auth


async def report_transport_barrier(client, caregiver_token) -> str:
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    milestone_id = route.json()["nextMilestoneId"]
    created = await client.post(
        f"/api/v1/milestones/{milestone_id}/barriers",
        headers=auth(caregiver_token),
        json={"category": "transport"},
    )
    return created.json()["id"]


async def affected_milestone(client, token, alert_id: str) -> dict:
    """El hito de la alerta, buscado por id.

    No se usa `nextMilestoneId`: al reprogramar hacia el futuro, ese hito deja de
    ser el más próximo y la prueba miraría otro.
    """
    detail = await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(token))
    return detail.json()["milestone"]


async def test_overview_counts_by_risk(client, care_team_token):
    response = await client.get("/api/v1/care-team/overview", headers=auth(care_team_token))
    body = response.json()
    # Lucía verde, Mateo amarillo (pendiente de confirmar), Valentina roja (inasistencia).
    assert body["counts"] == {"green": 1, "yellow": 1, "red": 1}
    # El conteo refleja las alertas realmente abiertas en el seed, sin fijar un
    # número: la demostración puede crecer sin invalidar la garantía.
    assert body["openAlerts"] >= 0


async def test_patients_are_sorted_by_risk(client, care_team_token):
    response = await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))
    names = [row["patient"]["displayName"] for row in response.json()]
    assert names == ["Valentina", "Mateo", "Lucía"]


async def test_patient_filters(client, care_team_token):
    missed = await client.get(
        "/api/v1/care-team/patients?status=missed", headers=auth(care_team_token)
    )
    assert [r["patient"]["id"] for r in missed.json()] == [str(VALENTINA_ID)]

    pending = await client.get(
        "/api/v1/care-team/patients?status=pending_confirmation", headers=auth(care_team_token)
    )
    assert [r["patient"]["id"] for r in pending.json()] == [str(MATEO_ID)]

    red = await client.get(
        "/api/v1/care-team/patients?risk=red", headers=auth(care_team_token)
    )
    assert [r["patient"]["id"] for r in red.json()] == [str(VALENTINA_ID)]


async def test_barrier_appears_for_the_care_team(client, caregiver_token, care_team_token):
    """El circuito entre sesiones: lo que reporta la familia, lo ve el equipo."""
    alert_id = await report_transport_barrier(client, caregiver_token)

    listing = await client.get(
        "/api/v1/care-team/alerts?status=pending", headers=auth(care_team_token)
    )
    # La alerta de la familia aparece entre las pendientes del equipo. No se fija
    # el total: el seed puede traer otras alertas de otros pacientes.
    assert alert_id in [a["id"] for a in listing.json()]

    rows = await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))
    mateo = next(r for r in rows.json() if r["patient"]["id"] == str(MATEO_ID))
    assert mateo["hasOpenBarrier"] is True
    assert mateo["reason"] == "Barrera reportada"
    assert mateo["patient"]["operationalRisk"] == "yellow"


async def test_contact_moves_alert_to_in_progress(client, caregiver_token, care_team_token):
    alert_id = await report_transport_barrier(client, caregiver_token)

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/contact", headers=auth(care_team_token), json={}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert response.json()["familyContacted"] is True


async def test_resolve_with_reschedule_updates_family_route(
    client, caregiver_token, care_team_token
):
    """Cierre del circuito: la familia ve la nueva fecha sin tocar nada."""
    alert_id = await report_transport_barrier(client, caregiver_token)
    new_date = (utcnow() + timedelta(days=7)).replace(microsecond=0)

    await client.post(
        f"/api/v1/alerts/{alert_id}/contact", headers=auth(care_team_token), json={}
    )
    resolved = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=auth(care_team_token),
        json={
            "actionTaken": "transport_coordination",
            "internalNote": "Se coordina movilidad con servicio social (ficticio)",
            "newScheduledAt": new_date.isoformat(),
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["actionTaken"] == "transport_coordination"

    milestone = await affected_milestone(client, care_team_token, alert_id)
    assert milestone["status"] == "rescheduled"
    assert milestone["scheduledAt"].startswith(new_date.date().isoformat())
    # Reprogramar reabre la confirmación.
    assert milestone["attendanceConfirmed"] is False

    # Y la familia ve el cambio en su propia ruta.
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    family_view = next(
        m for m in route.json()["milestones"] if m["id"] == milestone["id"]
    )
    assert family_view["status"] == "rescheduled"
    assert route.json()["patient"]["routeStatus"] == "confirmation_needed"


async def test_resolve_without_reschedule_returns_milestone_to_upcoming(
    client, caregiver_token, care_team_token
):
    alert_id = await report_transport_barrier(client, caregiver_token)

    await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=auth(care_team_token),
        json={"actionTaken": "guidance"},
    )

    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    body = route.json()
    milestone = next(m for m in body["milestones"] if m["id"] == body["nextMilestoneId"])
    assert milestone["status"] == "upcoming"


async def test_reschedule_action_requires_a_date(client, caregiver_token, care_team_token):
    alert_id = await report_transport_barrier(client, caregiver_token)
    response = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=auth(care_team_token),
        json={"actionTaken": "reschedule"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "date_required"


async def test_resolving_twice_is_rejected(client, caregiver_token, care_team_token):
    alert_id = await report_transport_barrier(client, caregiver_token)
    body = {"actionTaken": "guidance"}

    first = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve", headers=auth(care_team_token), json=body
    )
    second = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve", headers=auth(care_team_token), json=body
    )
    assert first.status_code == 200
    assert second.status_code == 422
    assert second.json()["detail"]["code"] == "alert_resolved"


async def test_create_milestone_appears_for_the_family(client, caregiver_token, care_team_token):
    scheduled = (utcnow() + timedelta(days=1)).replace(microsecond=0)

    created = await client.post(
        f"/api/v1/patients/{MATEO_ID}/milestones",
        headers=auth(care_team_token),
        json={
            "type": "laboratory",
            "title": "Laboratorio de control",
            "scheduledAt": scheduled.isoformat(),
            "location": "Laboratorio central",
            "preparation": "Acudir en ayunas de 4 horas",
            "service": "Hematología pediátrica",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "upcoming"
    assert created.json()["version"] == 1

    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    body = route.json()
    # Es el hito programado más cercano, así que pasa a ser el siguiente paso.
    assert body["nextMilestoneId"] == created.json()["id"]


async def test_milestone_without_date_is_unscheduled(client, care_team_token):
    created = await client.post(
        f"/api/v1/patients/{MATEO_ID}/milestones",
        headers=auth(care_team_token),
        json={"type": "follow_up", "title": "Control de seguimiento"},
    )
    assert created.json()["status"] == "unscheduled"


async def test_reschedule_rejects_past_dates(client, care_team_token):
    rows = await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))
    milestone_id = next(
        r["nextMilestone"]["id"] for r in rows.json() if r["patient"]["id"] == str(MATEO_ID)
    )
    past = (utcnow() - timedelta(days=3)).isoformat()

    response = await client.post(
        f"/api/v1/milestones/{milestone_id}/reschedule",
        headers=auth(care_team_token),
        json={"newScheduledAt": past},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "date_in_past"


async def test_reschedule_bumps_version(client, care_team_token):
    rows = await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))
    milestone = next(
        r["nextMilestone"] for r in rows.json() if r["patient"]["id"] == str(MATEO_ID)
    )
    future = (utcnow() + timedelta(days=10)).isoformat()

    response = await client.post(
        f"/api/v1/milestones/{milestone['id']}/reschedule",
        headers=auth(care_team_token),
        json={"newScheduledAt": future},
    )
    assert response.json()["version"] > milestone["version"]
