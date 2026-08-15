"""Vertical HTTP de Kinti Voz: contrato, seguridad e idempotencia."""

from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import func, select

from app.api.v1.voice import get_voice_workflow
from app.modules.voice.models import (
    AppointmentHold,
    CallbackRequest,
    VoiceEvent,
    VoiceSession,
)
from app.modules.voice.telephony import fake_webhook_signature
from app.seed import (
    MATEO_ID,
    PATIENT_ALIAS,
    PATIENT_PIN,
    REFERRAL_IDS,
    SEEDED_APPOINTMENT_REQUEST_ID,
)
from tests.conftest import auth


async def test_published_service_hours_are_available_to_an_adult(
    client, caregiver_token
) -> None:
    response = await client.get("/api/v1/service-hours", headers=auth(caregiver_token))

    assert response.status_code == 200, response.text
    assert len(response.json()) == 5
    assert all(row["status"] == "published" for row in response.json())


async def test_referral_lookup_is_scoped_to_the_authorized_patient(
    client, caregiver_token
) -> None:
    own = await client.post(
        "/api/v1/referrals/lookup",
        headers=auth(caregiver_token),
        json={"patientId": str(MATEO_ID), "externalIdentifier": "SYN-REF-004"},
    )
    foreign = await client.get(
        f"/api/v1/referrals/{REFERRAL_IDS[0]}", headers=auth(caregiver_token)
    )

    assert own.status_code == 200, own.text
    assert own.json()["status"] == "approved"
    assert foreign.status_code == 404


async def test_propose_confirm_and_retry_never_claim_a_fake_confirmation(
    client, caregiver_token, session
) -> None:
    proposal_operation = str(uuid4())
    proposed = await client.post(
        f"/api/v1/appointment-requests/{SEEDED_APPOINTMENT_REQUEST_ID}/proposals",
        headers=auth(caregiver_token),
        json={"operationId": proposal_operation, "maxOptions": 2},
    )
    assert proposed.status_code == 200, proposed.text
    body = proposed.json()
    assert body["request"]["status"] == "proposal_ready"
    assert 1 <= len(body["options"]) <= 2

    selected = body["options"][0]
    confirm_operation = str(uuid4())
    payload = {
        "selectedSlotId": selected["id"],
        "expectedAvailabilityVersion": selected["availabilityVersion"],
        "confirmed": True,
        "operationId": confirm_operation,
    }
    first = await client.post(
        f"/api/v1/appointment-requests/{SEEDED_APPOINTMENT_REQUEST_ID}/confirm",
        headers=auth(caregiver_token),
        json=payload,
    )
    replay = await client.post(
        f"/api/v1/appointment-requests/{SEEDED_APPOINTMENT_REQUEST_ID}/confirm",
        headers=auth(caregiver_token),
        json=payload,
    )

    assert first.status_code == replay.status_code == 200, first.text + replay.text
    assert first.json()["outcome"] == "submitted"
    assert first.json()["request"]["status"] == "submitted"
    assert "confirmada" not in json.dumps(first.json(), ensure_ascii=False).lower()
    hold_count = await session.scalar(select(func.count()).select_from(AppointmentHold))
    assert hold_count == 1


async def test_care_team_lists_callbacks_but_caregiver_cannot_use_team_queue(
    client, caregiver_token, care_team_token
) -> None:
    team = await client.get(
        "/api/v1/voice/callback-requests", headers=auth(care_team_token)
    )
    family = await client.get(
        "/api/v1/voice/callback-requests", headers=auth(caregiver_token)
    )

    assert team.status_code == 200, team.text
    assert len(team.json()) == 1
    assert "contactReference" not in team.json()[0]
    assert family.status_code == 403

    central = await client.get(
        "/api/v1/voice/callback-requests?includeUnverified=true",
        headers=auth(care_team_token),
    )
    assert central.status_code == 403


async def test_authenticated_callback_requires_owned_contact_and_patient(
    client, caregiver_token, session
) -> None:
    response = await client.post(
        "/api/v1/voice/callback-requests",
        headers=auth(caregiver_token),
        json={
            "patientId": str(MATEO_ID),
            "contactReference": f"contact:{uuid4()}",
            "reasonCode": "requested_by_caller",
            "operationId": str(uuid4()),
        },
    )

    assert response.status_code == 422, response.text
    count = await session.scalar(select(func.count()).select_from(CallbackRequest))
    assert count == 1  # sólo el callback sintético del seed


async def test_patient_role_is_rejected_from_every_adult_voice_surface(
    client, caregiver_token
) -> None:
    del caregiver_token  # activa y siembra la cuenta restringida del menor
    login = await client.post(
        "/api/v1/auth/patient-login",
        json={"alias": PATIENT_ALIAS, "pin": PATIENT_PIN},
    )
    assert login.status_code == 200, login.text
    patient_headers = auth(login.json()["accessToken"])

    hours = await client.get("/api/v1/service-hours", headers=patient_headers)
    requests = await client.get(
        f"/api/v1/appointment-requests?patientId={MATEO_ID}",
        headers=patient_headers,
    )
    callback = await client.post(
        "/api/v1/voice/callback-requests",
        headers=patient_headers,
        json={
            "contactReference": "user:patient-must-not-pass",
            "reasonCode": "requested_by_caller",
            "operationId": str(uuid4()),
        },
    )

    assert hours.status_code == requests.status_code == callback.status_code == 403


async def _signed_post(client, path: str, payload: dict, secret: str = "test-secret"):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = fake_webhook_signature(body=raw, secret=secret)
    return await client.post(
        path,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Kinti-Signature": signature,
        },
    )


async def test_signed_fake_call_persists_state_but_not_spoken_content(
    client, session
) -> None:
    provider_id = f"synthetic-{uuid4()}"
    incoming = await _signed_post(
        client, "/api/v1/voice/incoming", {"providerSessionId": provider_id}
    )
    assert incoming.status_code == 200, incoming.text

    sensitive_utterance = "mi niño tiene fiebre y mi teléfono no debe guardarse"
    turn = await _signed_post(
        client,
        "/api/v1/voice/turn",
        {
            "sessionId": incoming.json()["sessionId"],
            "eventId": f"event-{uuid4()}",
            "modality": "speech",
            "value": sensitive_utterance,
        },
    )

    assert turn.status_code == 200, turn.text
    assert turn.json()["state"] == "human_handoff"
    stored = (await session.scalars(select(VoiceSession))).one()
    durable = json.dumps(
        {"context": stored.context_json, "response": stored.last_response_json},
        ensure_ascii=False,
    )
    assert sensitive_utterance not in durable
    callbacks = await session.scalar(select(func.count()).select_from(CallbackRequest))
    assert callbacks == 1


async def test_invalid_fake_signature_creates_nothing(client, session) -> None:
    response = await client.post(
        "/api/v1/voice/incoming",
        content=b'{"providerSessionId":"synthetic-invalid"}',
        headers={"Content-Type": "application/json", "X-Kinti-Signature": "bad"},
    )

    assert response.status_code == 403
    count = await session.scalar(select(func.count()).select_from(VoiceSession))
    assert count == 0


async def test_late_webhook_replay_does_not_move_durable_state_backwards(
    client, session
) -> None:
    provider_id = f"synthetic-replay-{uuid4()}"
    incoming = await _signed_post(
        client, "/api/v1/voice/incoming", {"providerSessionId": provider_id}
    )
    session_id = incoming.json()["sessionId"]
    first_event = f"event-{uuid4()}"
    first_payload = {
        "sessionId": session_id,
        "eventId": first_event,
        "modality": "speech",
        "value": "sí",
    }
    first = await _signed_post(client, "/api/v1/voice/turn", first_payload)
    second = await _signed_post(
        client,
        "/api/v1/voice/turn",
        {
            "sessionId": session_id,
            "eventId": f"event-{uuid4()}",
            "modality": "speech",
            "value": "quiero una cita",
        },
    )
    late_replay = await _signed_post(client, "/api/v1/voice/turn", first_payload)

    assert first.json()["state"] == late_replay.json()["state"] == "identify_intent"
    assert second.json()["state"] == "verify_identity"
    stored = (await session.scalars(select(VoiceSession))).one()
    assert stored.state == "verify_identity"
    events = await session.scalar(select(func.count()).select_from(VoiceEvent))
    assert events == 3  # incoming + dos turnos; el replay no duplica


async def test_old_turn_replay_survives_process_restart(client, session) -> None:
    provider_id = f"synthetic-durable-replay-{uuid4()}"
    incoming = await _signed_post(
        client, "/api/v1/voice/incoming", {"providerSessionId": provider_id}
    )
    payload = {
        "sessionId": incoming.json()["sessionId"],
        "eventId": f"event-{uuid4()}",
        "modality": "speech",
        "value": "sí",
    }
    first = await _signed_post(client, "/api/v1/voice/turn", payload)

    get_voice_workflow.cache_clear()
    replay = await _signed_post(client, "/api/v1/voice/turn", payload)

    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    stored = (await session.scalars(select(VoiceSession))).one()
    assert stored.state == "identify_intent"
    assert await session.scalar(select(func.count()).select_from(VoiceEvent)) == 2


async def test_late_turn_after_terminal_status_returns_terminal_response(
    client, session
) -> None:
    provider_id = f"synthetic-terminal-{uuid4()}"
    incoming = await _signed_post(
        client, "/api/v1/voice/incoming", {"providerSessionId": provider_id}
    )
    status_response = await _signed_post(
        client,
        "/api/v1/voice/status",
        {
            "providerSessionId": provider_id,
            "eventId": f"status-{uuid4()}",
            "status": "completed",
        },
    )
    late = await _signed_post(
        client,
        "/api/v1/voice/turn",
        {
            "sessionId": incoming.json()["sessionId"],
            "eventId": f"event-{uuid4()}",
            "modality": "speech",
            "value": "quiero una cita",
        },
    )

    assert status_response.status_code == 204, status_response.text
    assert late.status_code == 200, late.text
    assert late.json()["state"] == "completed"
    stored = (await session.scalars(select(VoiceSession))).one()
    assert stored.state == "completed"


async def test_process_restart_hands_off_instead_of_resetting_durable_state(
    client, session
) -> None:
    provider_id = f"synthetic-restart-{uuid4()}"
    payload = {"providerSessionId": provider_id}
    incoming = await _signed_post(client, "/api/v1/voice/incoming", payload)
    await _signed_post(
        client,
        "/api/v1/voice/turn",
        {
            "sessionId": incoming.json()["sessionId"],
            "eventId": f"event-{uuid4()}",
            "modality": "speech",
            "value": "sí",
        },
    )

    get_voice_workflow.cache_clear()
    recovered = await _signed_post(client, "/api/v1/voice/incoming", payload)

    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["state"] == "human_handoff"
    stored = (await session.scalars(select(VoiceSession))).one()
    assert stored.state == "human_handoff"
    callbacks = await session.scalar(select(func.count()).select_from(CallbackRequest))
    assert callbacks == 1
