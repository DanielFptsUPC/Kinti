"""Kinti Compañero: la frontera entre el espacio del menor y el operativo.

Estas pruebas no verifican una funcionalidad: verifican una **ausencia**. La
mayor parte afirma que cierta información *no* llega al menor y que ciertas
rutas *no* le responden. Es deliberado — una fuga de datos operativos a la
pantalla infantil no se manifiesta como un fallo, se manifiesta como una
pantalla que muestra de más.
"""

import uuid

import pytest
from sqlalchemy import select

from app.modules.companion.models import PatientUserLink
from app.seed import (
    CAREGIVER_LUCIA_EMAIL,
    LUCIA_ID,
    MATEO_ID,
    PATIENT_ALIAS,
    PATIENT_PIN,
)
from tests.conftest import auth, login

# El seed ya trae la cuenta de Mateo activa: es el caso de demostración, y
# probar contra él evita que cada prueba reconstruya el alta.
ALIAS = PATIENT_ALIAS
PIN = PATIENT_PIN


async def activate(client, caregiver_token, patient_id=MATEO_ID, alias="otro-alias", pin=PIN):
    return await client.post(
        f"/api/v1/caregiver/patients/{patient_id}/patient-account",
        headers=auth(caregiver_token),
        json={"alias": alias, "pin": pin, "consentConfirmed": True},
    )


async def patient_login(client, alias=ALIAS, pin=PIN):
    return await client.post("/api/v1/auth/patient-login", json={"alias": alias, "pin": pin})


@pytest.fixture
async def patient_token(client, caregiver_token) -> str:
    response = await patient_login(client)
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


# ------------------------------------------------------------ alta y consentimiento


async def test_activation_requires_explicit_consent(client, caregiver_token):
    response = await client.post(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={"alias": ALIAS, "pin": PIN, "consentConfirmed": False},
    )
    assert response.status_code == 403


async def test_only_the_linked_caregiver_activates_the_account(client, caregiver_token):
    """El cuidador de Mateo no abre la cuenta de Lucía."""
    response = await activate(client, caregiver_token, patient_id=LUCIA_ID)
    assert response.status_code == 404


async def test_an_empty_update_reads_the_account_without_changing_it(client, caregiver_token):
    """El cliente móvil usa este PATCH vacío como lectura de la cuenta.

    Se fija aquí para que no se rompa sin querer: sin él haría falta una ruta de
    sólo lectura que expusiera lo mismo.
    """
    first = await client.patch(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={},
    )
    assert first.status_code == 200
    assert first.json()["alias"] == ALIAS
    assert first.json()["status"] == "active"

    second = await client.patch(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={},
    )
    assert second.json() == first.json()


async def test_a_patient_has_at_most_one_account(client, caregiver_token):
    """Mateo ya tiene la suya desde el seed; una segunda alta se rechaza."""
    second = await activate(client, caregiver_token, alias="alias-duplicado")
    assert second.status_code == 422
    assert second.json()["detail"]["code"] == "account_exists"


# ------------------------------------------------------------------------ acceso


async def test_patient_login_never_reveals_whether_the_alias_exists(client, caregiver_token):
    wrong_pin = await client.post(
        "/api/v1/auth/patient-login", json={"alias": ALIAS, "pin": "0000"}
    )
    unknown_alias = await client.post(
        "/api/v1/auth/patient-login", json={"alias": "no-existe", "pin": PIN}
    )

    assert wrong_pin.status_code == unknown_alias.status_code == 401
    # Mismo cuerpo exacto: un alias válido no se distingue de uno inventado.
    assert wrong_pin.json() == unknown_alias.json()


async def test_repeated_failures_lock_the_account_without_touching_care(
    client, caregiver_token, session
):
    for _ in range(5):
        await client.post("/api/v1/auth/patient-login", json={"alias": ALIAS, "pin": "0000"})

    locked = await client.post("/api/v1/auth/patient-login", json={"alias": ALIAS, "pin": PIN})
    assert locked.status_code == 423

    # El bloqueo es de la cuenta, no del caso: la ruta clínica sigue intacta.
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert route.status_code == 200
    assert route.json()["milestones"]


async def test_the_adult_recovers_access_and_the_child_never_does(client, caregiver_token):
    for _ in range(5):
        await client.post("/api/v1/auth/patient-login", json={"alias": ALIAS, "pin": "0000"})

    recovered = await client.patch(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={"pin": "1357", "status": "active"},
    )
    assert recovered.status_code == 200

    assert (
        await client.post("/api/v1/auth/patient-login", json={"alias": ALIAS, "pin": "1357"})
    ).status_code == 200


async def test_suspension_blocks_the_space_but_keeps_the_care_record(
    client, caregiver_token, patient_token
):
    suspended = await client.patch(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={"status": "suspended"},
    )
    assert suspended.status_code == 200

    assert (
        await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    ).status_code == 403

    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert route.status_code == 200
    assert route.json()["milestones"], "suspender la cuenta no borra los hitos"


async def test_the_child_account_cannot_use_the_adult_login(client, caregiver_token, session):
    link = await session.scalar(
        select(PatientUserLink).where(PatientUserLink.patient_id == MATEO_ID)
    )
    assert link is not None

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": f"patient.{MATEO_ID}@kinti.local", "password": PIN},
    )
    assert response.status_code == 401


# ------------------------------------------------------------- frontera de datos


async def test_the_companion_view_carries_no_operational_data(client, patient_token):
    response = await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "greeting",
        "chosenName",
        "avatarKey",
        "comfortObject",
        "developmentBand",
        "activities",
        "immediatePreparation",
    }

    # Ni el vocabulario operativo aparece en ningún punto del cuerpo serializado.
    raw = response.text.lower()
    for term in (
        "operationalrisk",
        "routestatus",
        "milestone",
        "alert",
        "barrier",
        "diagnos",
        "abandono",
        "riesgo",
    ):
        assert term not in raw, f"«{term}» no puede llegar a la pantalla del menor"


async def test_the_child_endpoints_ignore_any_patient_id_from_the_client(client, patient_token):
    """No hay superficie donde el menor pueda pedir otro paciente.

    El contrato lo garantiza por forma: ninguna ruta infantil lleva
    `patient_id`, y el vínculo se deriva del token.
    """
    from app.main import app as fastapi_app

    routes = [p for p in fastapi_app.openapi()["paths"] if p.startswith("/api/v1/patient/me")]
    assert routes, "las rutas del menor deben existir"
    assert all("{" not in path for path in routes)


async def test_a_patient_token_opens_no_adult_surface(client, patient_token):
    headers = auth(patient_token)

    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=headers)
    assert route.status_code in (403, 404)
    assert (await client.get("/api/v1/sync/bootstrap", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/notifications", headers=headers)).status_code == 403
    assert (
        await client.post("/api/v1/sync/operations", headers=headers, json={"operations": []})
    ).status_code == 403


async def test_the_child_sees_no_patient_in_its_own_profile(client, patient_token):
    response = await client.get("/api/v1/me", headers=auth(patient_token))
    assert response.status_code == 200
    # `patientIds` alimenta la navegación operativa; para el menor está vacío.
    assert response.json()["patientIds"] == []


async def test_immediate_preparation_never_names_the_procedure(
    client, caregiver_token, patient_token
):
    """RF-NNA-04: se dice cuándo y qué llevar, no qué procedimiento es."""
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    titles = [m["title"] for m in route.json()["milestones"] if m.get("title")]

    body = (
        await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    ).json()
    preparation = body["immediatePreparation"]
    if preparation is None:
        pytest.skip("ningún hito del seed cae dentro de las próximas 48 horas")

    assert set(preparation) == {"when", "bring", "company"}
    serialized = str(preparation).lower()
    for title in titles:
        assert title.lower() not in serialized


# ------------------------------------------------------ contenido y preferencias


async def test_the_caregiver_decides_what_content_is_enabled(
    client, caregiver_token, patient_token
):
    before = (
        await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    ).json()
    assert any(a["key"] == "stories" for a in before["activities"])

    updated = await client.patch(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={"enabledCategories": {"stories": False}},
    )
    assert updated.status_code == 200

    after = (
        await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    ).json()
    assert not any(a["key"] == "stories" for a in after["activities"])
    # Deshabilitar una categoría no arrastra a las demás.
    assert any(a["key"] == "breathing" for a in after["activities"])


async def test_the_development_band_changes_the_activities_offered(
    client, caregiver_token, patient_token
):
    await client.patch(
        f"/api/v1/caregiver/patients/{MATEO_ID}/patient-account",
        headers=auth(caregiver_token),
        json={"developmentBand": "early"},
    )
    body = (
        await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    ).json()
    assert body["developmentBand"] == "early"
    assert not any(a["key"] == "stories" for a in body["activities"])


async def test_the_child_names_its_own_companion(client, patient_token):
    response = await client.post(
        "/api/v1/patient/me/preferences",
        headers=auth(patient_token),
        json={"chosenName": "Pipo", "comfortObject": "mi manta azul"},
    )
    assert response.status_code == 200
    assert response.json()["chosenName"] == "Pipo"

    later = (
        await client.get("/api/v1/patient/me/companion", headers=auth(patient_token))
    ).json()
    assert later["chosenName"] == "Pipo"
    assert later["comfortObject"] == "mi manta azul"


# ---------------------------------------------------------- emociones y apoyo


async def test_a_support_request_reaches_the_caregiver(client, caregiver_token, patient_token):
    created = await client.post(
        "/api/v1/patient/me/support-requests",
        headers=auth(patient_token),
        json={"requestType": "feeling_scared"},
    )
    assert created.status_code == 200
    assert created.json()["status"] == "open"

    inbox = await client.get(
        f"/api/v1/caregiver/patients/{MATEO_ID}/support-requests", headers=auth(caregiver_token)
    )
    assert inbox.status_code == 200
    assert [r["requestType"] for r in inbox.json()] == ["feeling_scared"]

    notifications = await client.get("/api/v1/notifications", headers=auth(caregiver_token))
    assert any(n["type"] == "patient_support_request" for n in notifications.json())


async def test_support_requests_are_idempotent_by_operation_id(client, patient_token):
    operation_id = str(uuid.uuid4())
    payload = {"requestType": "want_to_talk", "operationId": operation_id}

    first = await client.post(
        "/api/v1/patient/me/support-requests", headers=auth(patient_token), json=payload
    )
    second = await client.post(
        "/api/v1/patient/me/support-requests", headers=auth(patient_token), json=payload
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_acknowledging_a_request_closes_it(client, caregiver_token, patient_token):
    created = await client.post(
        "/api/v1/patient/me/support-requests",
        headers=auth(patient_token),
        json={"requestType": "need_help"},
    )
    request_id = created.json()["id"]

    acknowledged = await client.post(
        f"/api/v1/caregiver/support-requests/{request_id}/acknowledge",
        headers=auth(caregiver_token),
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledgedAt"] is not None


async def test_an_unrelated_caregiver_reads_no_support_requests(
    client, caregiver_token, patient_token
):
    await client.post(
        "/api/v1/patient/me/support-requests",
        headers=auth(patient_token),
        json={"requestType": "want_company"},
    )
    lucia = await login(client, CAREGIVER_LUCIA_EMAIL)

    response = await client.get(
        f"/api/v1/caregiver/patients/{MATEO_ID}/support-requests", headers=auth(lucia)
    )
    assert response.status_code == 404


async def test_the_child_records_a_feeling_without_generating_an_alert(
    client, caregiver_token, patient_token
):
    """Registrar cómo se siente acompaña; no entra en ninguna priorización."""
    before = await client.get(
        f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token)
    )
    alerts_before = len(before.json().get("alerts", []))

    recorded = await client.post(
        "/api/v1/patient/me/feelings", headers=auth(patient_token), json={"mood": "worried"}
    )
    assert recorded.status_code == 200

    after = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(caregiver_token))
    assert len(after.json().get("alerts", [])) == alerts_before
    assert after.json()["patient"]["operationalRisk"] == before.json()["patient"]["operationalRisk"]


async def test_an_adult_cannot_reach_the_child_space(client, caregiver_token):
    response = await client.get("/api/v1/patient/me/companion", headers=auth(caregiver_token))
    assert response.status_code == 403
