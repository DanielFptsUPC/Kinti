"""Control de acceso por rol, vínculo familiar y asignación asistencial.

Ocultar un botón en la interfaz no es control de acceso: cada endpoint tiene que
negar por su cuenta.
"""

from uuid import uuid4

from app.seed import LUCIA_ID, MATEO_ID, VALENTINA_ID
from tests.conftest import auth


async def test_caregiver_cannot_read_another_familys_patient(client, caregiver_token):
    """El cuidador de Mateo no puede ver la ruta de Lucía."""
    response = await client.get(
        f"/api/v1/patients/{LUCIA_ID}/route", headers=auth(caregiver_token)
    )
    assert response.status_code == 404


async def test_caregiver_reads_their_own_patient(client, caregiver_token):
    response = await client.get(
        f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token)
    )
    assert response.status_code == 200
    assert response.json()["patient"]["displayName"] == "Mateo"


async def test_unknown_uuid_answers_404_not_403(client, caregiver_token):
    """No se puede enumerar pacientes probando UUID ajenos."""
    response = await client.get(f"/api/v1/patients/{uuid4()}/route", headers=auth(caregiver_token))
    assert response.status_code == 404


async def test_caregiver_cannot_use_care_team_endpoints(client, caregiver_token):
    overview = await client.get("/api/v1/care-team/overview", headers=auth(caregiver_token))
    assert overview.status_code == 403

    created = await client.post(
        f"/api/v1/patients/{MATEO_ID}/milestones",
        headers=auth(caregiver_token),
        json={"type": "follow_up", "title": "Intento no autorizado"},
    )
    assert created.status_code == 403


async def test_care_team_cannot_use_family_endpoints(client, care_team_token, seeded):
    """Confirmar asistencia y reportar barreras corresponde a la familia."""
    route = await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))
    milestone_id = next(
        row["nextMilestone"]["id"]
        for row in route.json()
        if row["patient"]["id"] == str(MATEO_ID)
    )

    response = await client.post(
        f"/api/v1/milestones/{milestone_id}/confirmations",
        headers=auth(care_team_token),
        json={},
    )
    assert response.status_code == 403


async def test_caregiver_cannot_confirm_another_familys_milestone(
    client, caregiver_token, care_team_token
):
    rows = (await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))).json()
    lucia_milestone = next(
        row["nextMilestone"]["id"] for row in rows if row["patient"]["id"] == str(LUCIA_ID)
    )

    response = await client.post(
        f"/api/v1/milestones/{lucia_milestone}/confirmations",
        headers=auth(caregiver_token),
        json={},
    )
    assert response.status_code == 404


async def test_care_team_without_assignment_cannot_act(client, care_team_token, session, seeded):
    """Quitar la asignación quita el acceso, aunque el rol siga siendo asistencial."""
    from sqlalchemy import update

    from app.modules.patients.models import CareTeamAssignment

    await session.execute(
        update(CareTeamAssignment)
        .where(CareTeamAssignment.patient_id == VALENTINA_ID)
        .values(is_active=False)
    )
    await session.commit()

    response = await client.get("/api/v1/care-team/patients", headers=auth(care_team_token))
    ids = [row["patient"]["id"] for row in response.json()]
    assert str(VALENTINA_ID) not in ids

    created = await client.post(
        f"/api/v1/patients/{VALENTINA_ID}/milestones",
        headers=auth(care_team_token),
        json={"type": "follow_up", "title": "Sin asignación"},
    )
    assert created.status_code == 404


async def test_client_cannot_impose_operational_risk(client, caregiver_token):
    """El semáforo es autoridad del servidor: lo que mande el cliente se ignora."""
    response = await client.get(
        f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token)
    )
    patient = response.json()["patient"]
    # Mateo arranca amarillo por confirmación pendiente, sin importar el cuerpo enviado.
    assert patient["operationalRisk"] == "yellow"
    assert patient["routeStatus"] == "confirmation_needed"
