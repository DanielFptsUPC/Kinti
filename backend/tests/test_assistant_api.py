"""API conversacional y de conocimiento, extremo a extremo por HTTP."""

import pytest

from app.modules.assistant.providers import reset_for_testing
from app.seed import LUCIA_ID, MATEO_ID
from tests.conftest import auth
from tests.test_knowledge import GUIDE

GUIDE_SLUG = "que-llevar"


@pytest.fixture(autouse=True)
def _clean_storage():
    reset_for_testing()
    yield
    reset_for_testing()


async def publish_guide(client, care_team_token, text: str = GUIDE, version: str = "1.0") -> str:
    """Recorre el ciclo completo: documento → versión → procesar → publicar."""
    document = await client.post(
        "/api/v1/knowledge/documents",
        headers=auth(care_team_token),
        json={"slug": GUIDE_SLUG, "title": "Guía institucional", "category": "orientacion"},
    )
    if document.status_code != 200:
        listing = await client.get("/api/v1/knowledge/documents", headers=auth(care_team_token))
        document_id = next(d["id"] for d in listing.json() if d["slug"] == GUIDE_SLUG)
    else:
        document_id = document.json()["id"]

    created = await client.post(
        f"/api/v1/knowledge/documents/{document_id}/versions",
        headers=auth(care_team_token),
        json={"version": version, "content": text},
    )
    version_id = created.json()["id"]

    await client.post(
        f"/api/v1/knowledge/versions/{version_id}/process", headers=auth(care_team_token)
    )
    await client.post(
        f"/api/v1/knowledge/versions/{version_id}/publish", headers=auth(care_team_token)
    )
    return version_id


async def open_session(client, token, patient_id=MATEO_ID) -> str:
    response = await client.post(
        "/api/v1/assistant/sessions",
        headers=auth(token),
        json={"patientId": str(patient_id)},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def ask(client, token, session_id, text, **body):
    return await client.post(
        f"/api/v1/assistant/sessions/{session_id}/messages",
        headers=auth(token),
        json={"text": text, **body},
    )


# ------------------------------------------------------------- conocimiento


async def test_only_care_team_can_publish_knowledge(client, caregiver_token):
    response = await client.post(
        "/api/v1/knowledge/documents",
        headers=auth(caregiver_token),
        json={"slug": "x", "title": "X", "category": "orientacion"},
    )
    assert response.status_code == 403


async def test_publishing_lifecycle(client, care_team_token):
    version_id = await publish_guide(client, care_team_token)

    preview = await client.get(
        f"/api/v1/knowledge/versions/{version_id}/preview", headers=auth(care_team_token)
    )
    body = preview.json()
    assert body["version"]["status"] == "published"
    assert body["chunkCount"] > 0
    assert body["sections"]


async def test_cannot_publish_before_processing(client, care_team_token):
    document = await client.post(
        "/api/v1/knowledge/documents",
        headers=auth(care_team_token),
        json={"slug": "sin-procesar", "title": "X", "category": "orientacion"},
    )
    created = await client.post(
        f"/api/v1/knowledge/documents/{document.json()['id']}/versions",
        headers=auth(care_team_token),
        json={"version": "1.0", "content": GUIDE},
    )
    response = await client.post(
        f"/api/v1/knowledge/versions/{created.json()['id']}/publish",
        headers=auth(care_team_token),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "not_reviewable"


async def test_retiring_removes_it_from_answers(client, caregiver_token, care_team_token):
    version_id = await publish_guide(client, care_team_token)
    session_id = await open_session(client, caregiver_token)

    before = await ask(client, caregiver_token, session_id, "¿qué documentos debo llevar?")
    assert before.json()["citations"]

    await client.post(
        f"/api/v1/knowledge/versions/{version_id}/retire", headers=auth(care_team_token)
    )

    after = await ask(client, caregiver_token, session_id, "¿qué documentos debo llevar?")
    assert after.json()["confidence"] == "insufficient_evidence"
    assert after.json()["citations"] == []


# ---------------------------------------------------------------- sesiones


async def test_care_team_cannot_open_a_family_conversation(client, care_team_token):
    response = await client.post(
        "/api/v1/assistant/sessions", headers=auth(care_team_token), json={}
    )
    assert response.status_code == 403


async def test_cannot_open_a_session_for_another_family(client, caregiver_token):
    response = await client.post(
        "/api/v1/assistant/sessions",
        headers=auth(caregiver_token),
        json={"patientId": str(LUCIA_ID)},
    )
    assert response.status_code == 404


async def test_cannot_read_another_users_session(client, caregiver_token, lucia_token):
    session_id = await open_session(client, caregiver_token)
    response = await client.get(
        f"/api/v1/assistant/sessions/{session_id}", headers=auth(lucia_token)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- mensajes


async def test_institutional_question_returns_citations(
    client, caregiver_token, care_team_token
):
    await publish_guide(client, care_team_token)
    session_id = await open_session(client, caregiver_token)

    response = await ask(client, caregiver_token, session_id, "¿qué documentos debo llevar?")
    body = response.json()

    assert body["intent"] == "institutional_faq"
    assert body["confidence"] == "supported"
    assert body["citations"]
    assert body["citations"][0]["documentTitle"]
    assert body["citations"][0]["documentVersion"] == "1.0"


async def test_question_without_knowledge_abstains(client, caregiver_token):
    session_id = await open_session(client, caregiver_token)
    response = await ask(client, caregiver_token, session_id, "¿qué documentos debo llevar?")

    assert response.json()["confidence"] == "insufficient_evidence"
    assert response.json()["citations"] == []


async def test_next_appointment_uses_the_domain(client, caregiver_token):
    session_id = await open_session(client, caregiver_token)
    response = await ask(client, caregiver_token, session_id, "¿cuándo es mi próxima cita?")

    body = response.json()
    assert body["intent"] == "next_milestone_query"
    assert body["citations"] == []
    assert "próxima atención" in body["answer"]


async def test_clinical_question_is_transferred(client, caregiver_token):
    session_id = await open_session(client, caregiver_token)
    response = await ask(client, caregiver_token, session_id, "¿puedo cambiar la dosis?")

    body = response.json()
    assert body["intent"] == "clinical_or_safety_concern"
    assert body["needsHuman"] is True
    assert body["citations"] == []


# ------------------------------------------------------- acción y confirmación


async def test_barrier_requires_explicit_confirmation(client, caregiver_token, session):
    from sqlalchemy import func, select

    from app.modules.alerts.models import BarrierAlert

    session_id = await open_session(client, caregiver_token)
    response = await ask(
        client, caregiver_token, session_id, "no tengo para el pasaje"
    )
    body = response.json()

    assert body["intent"] == "report_barrier"
    assert body["proposedAction"]["kind"] == "report_barrier"

    before = await session.scalar(
        select(func.count()).select_from(BarrierAlert).where(BarrierAlert.patient_id == MATEO_ID)
    )
    assert before == 0, "no debe existir alerta antes de confirmar"

    confirm = await client.post(
        f"/api/v1/assistant/messages/{body['messageId']}/confirm-action",
        headers=auth(caregiver_token),
        json={},
    )
    assert confirm.status_code == 200

    after = await session.scalar(
        select(func.count()).select_from(BarrierAlert).where(BarrierAlert.patient_id == MATEO_ID)
    )
    assert after == 1


async def test_confirming_twice_does_not_duplicate(client, caregiver_token, session):
    from sqlalchemy import func, select

    from app.modules.alerts.models import BarrierAlert

    session_id = await open_session(client, caregiver_token)
    body = (await ask(client, caregiver_token, session_id, "no tengo para el pasaje")).json()

    for _ in range(2):
        response = await client.post(
            f"/api/v1/assistant/messages/{body['messageId']}/confirm-action",
            headers=auth(caregiver_token),
            json={},
        )
        assert response.status_code == 200

    count = await session.scalar(
        select(func.count()).select_from(BarrierAlert).where(BarrierAlert.patient_id == MATEO_ID)
    )
    assert count == 1


async def test_resending_a_message_is_idempotent(client, caregiver_token):
    from uuid import uuid4

    session_id = await open_session(client, caregiver_token)
    operation_id = str(uuid4())

    first = await ask(
        client, caregiver_token, session_id, "no tengo para el pasaje",
        operationId=operation_id,
    )
    second = await ask(
        client, caregiver_token, session_id, "no tengo para el pasaje",
        operationId=operation_id,
    )
    assert first.json()["messageId"] == second.json()["messageId"]


async def test_cannot_confirm_another_users_action(client, caregiver_token, lucia_token):
    session_id = await open_session(client, caregiver_token)
    body = (await ask(client, caregiver_token, session_id, "no tengo para el pasaje")).json()

    response = await client.post(
        f"/api/v1/assistant/messages/{body['messageId']}/confirm-action",
        headers=auth(lucia_token),
        json={},
    )
    assert response.status_code == 404


# ------------------------------------------------------------------- medios


async def test_upload_intent_rejects_unsupported_types(client, caregiver_token):
    await open_session(client, caregiver_token)
    response = await client.post(
        "/api/v1/assistant/media/upload-intent",
        headers=auth(caregiver_token),
        json={"modality": "image", "mimeType": "application/x-msdownload", "sizeBytes": 100},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_media"


async def test_upload_intent_rejects_oversized_files(client, caregiver_token):
    await open_session(client, caregiver_token)
    response = await client.post(
        "/api/v1/assistant/media/upload-intent",
        headers=auth(caregiver_token),
        json={"modality": "image", "mimeType": "image/jpeg", "sizeBytes": 99_000_000},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "media_too_large"


async def test_upload_intent_rejects_long_audio(client, caregiver_token):
    await open_session(client, caregiver_token)
    response = await client.post(
        "/api/v1/assistant/media/upload-intent",
        headers=auth(caregiver_token),
        json={
            "modality": "audio",
            "mimeType": "audio/ogg",
            "sizeBytes": 1000,
            "durationSeconds": 9999,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "audio_too_long"


async def test_upload_intent_returns_an_opaque_path(client, caregiver_token):
    await open_session(client, caregiver_token)
    response = await client.post(
        "/api/v1/assistant/media/upload-intent",
        headers=auth(caregiver_token),
        json={"modality": "audio", "mimeType": "audio/ogg", "sizeBytes": 2048,
              "durationSeconds": 5},
    )
    body = response.json()
    assert body["expiresInSeconds"] > 0
    # La ruta no lleva nombre, correo ni identificadores de la persona.
    assert "mateo" not in body["uploadUrl"].lower()
    assert "@" not in body["uploadUrl"]
