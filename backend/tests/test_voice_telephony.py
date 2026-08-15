from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from app.modules.voice.ports import TurnOutput, VoiceState
from app.modules.voice.telephony import (
    InvalidTelephonySignature,
    TwilioTurnTelephonyGateway,
    fake_webhook_signature,
    twilio_request_signature,
    validate_fake_webhook,
)


def test_twilio_signature_matches_documented_algorithm() -> None:
    url = "https://voz.example.org/api/v1/voice/turn"
    form = {"CallSid": "CA123", "Digits": "1"}
    expected_payload = f"{url}CallSidCA123Digits1".encode()
    expected = base64.b64encode(
        hmac.new(b"secret", expected_payload, hashlib.sha1).digest()
    ).decode()

    assert twilio_request_signature(url=url, form=form, auth_token="secret") == expected


def test_twilio_validation_uses_configured_public_url_not_host_header() -> None:
    gateway = TwilioTurnTelephonyGateway(
        auth_token="secret", webhook_base_url="https://voz.example.org"
    )
    form = {"CallSid": "CA123"}
    signature = twilio_request_signature(
        url="https://voz.example.org/api/v1/voice/incoming",
        form=form,
        auth_token="secret",
    )

    gateway.validate(
        path="/api/v1/voice/incoming", query="", form=form, signature=signature
    )
    with pytest.raises(InvalidTelephonySignature):
        gateway.validate(
            path="/api/v1/voice/turn", query="", form=form, signature=signature
        )


def test_twiml_collects_voice_and_dtmf_without_recording() -> None:
    gateway = TwilioTurnTelephonyGateway(
        auth_token="secret", webhook_base_url="https://voz.example.org"
    )
    output = TurnOutput(
        session_id="session-1",
        state=VoiceState.IDENTIFY_INTENT,
        prompt="¿Qué necesita hacer?",
        expects_input=True,
        speech_rate="slow",
        allowed_dtmf=("1", "2", "3"),
    )

    xml = gateway.render(output)

    assert 'input="speech dtmf"' in xml
    assert 'action="https://voz.example.org/api/v1/voice/turn"' in xml
    assert 'speechTimeout="5"' in xml
    assert "¿Qué necesita hacer?" in xml
    assert "<Record" not in xml
    assert "<Stream" not in xml


def test_fake_webhook_signature_is_required() -> None:
    body = b'{"eventId":"evt-1"}'
    signature = fake_webhook_signature(body=body, secret="test-secret")

    validate_fake_webhook(body=body, signature=signature, secret="test-secret")
    with pytest.raises(InvalidTelephonySignature):
        validate_fake_webhook(body=body, signature="bad", secret="test-secret")


@pytest.mark.parametrize(
    "base_url",
    ["http://voz.example.org", "https://", "https://voz.example.org?unsafe=1"],
)
def test_twilio_gateway_rejects_noncanonical_base_url(base_url: str) -> None:
    with pytest.raises(ValueError):
        TwilioTurnTelephonyGateway(auth_token="secret", webhook_base_url=base_url)
