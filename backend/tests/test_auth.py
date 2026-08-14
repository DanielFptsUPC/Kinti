"""Identidad del piloto: login, renovación, cierre y perfil."""

from app.seed import CARE_TEAM_EMAIL, CAREGIVER_MATEO_EMAIL, MATEO_ID
from tests.conftest import SEED_PASSWORD, auth, login


async def test_login_returns_token_pair(client, seeded):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": CAREGIVER_MATEO_EMAIL, "password": SEED_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accessToken"]
    assert body["refreshToken"]
    assert body["tokenType"] == "bearer"
    assert body["expiresIn"] > 0


async def test_login_rejects_wrong_password(client, seeded):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": CAREGIVER_MATEO_EMAIL, "password": "contraseña-incorrecta"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"


async def test_login_does_not_reveal_unknown_accounts(client, seeded):
    """Un correo inexistente responde igual que una contraseña incorrecta."""
    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "nadie@kinti.demo", "password": SEED_PASSWORD},
    )
    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": CAREGIVER_MATEO_EMAIL, "password": "x"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


async def test_refresh_issues_new_tokens(client, seeded):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": CAREGIVER_MATEO_EMAIL, "password": SEED_PASSWORD},
    )
    refresh_token = login_response.json()["refreshToken"]

    response = await client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_token})
    assert response.status_code == 200
    assert response.json()["accessToken"]


async def test_access_token_is_not_accepted_as_refresh(client, seeded):
    """Los tipos de token no son intercambiables."""
    access = await login(client, CAREGIVER_MATEO_EMAIL)
    response = await client.post("/api/v1/auth/refresh", json={"refreshToken": access})
    assert response.status_code == 401


async def test_me_lists_only_linked_patients(client, seeded):
    token = await login(client, CAREGIVER_MATEO_EMAIL)
    response = await client.get("/api/v1/me", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "caregiver"
    assert body["patientIds"] == [str(MATEO_ID)]


async def test_care_team_sees_every_assigned_patient(client, seeded):
    token = await login(client, CARE_TEAM_EMAIL)
    response = await client.get("/api/v1/me", headers=auth(token))
    assert response.json()["user"]["role"] == "care_team"
    assert len(response.json()["patientIds"]) == 3


async def test_endpoints_require_a_token(client, seeded):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_garbage_token_is_rejected(client, seeded):
    response = await client.get("/api/v1/me", headers=auth("no-es-un-jwt"))
    assert response.status_code == 401


async def test_logout_succeeds(client, seeded):
    token = await login(client, CAREGIVER_MATEO_EMAIL)
    response = await client.post("/api/v1/auth/logout", headers=auth(token))
    assert response.status_code == 204
