import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_voice_defaults_are_safe_and_fake() -> None:
    settings = Settings(_env_file=None)

    assert settings.telephony_provider == "fake"
    assert settings.voice_mode == "turn"
    assert settings.voice_recording_enabled is False
    assert settings.voice_transcript_retention_enabled is False


def test_non_local_fake_webhook_rejects_the_development_secret(monkeypatch) -> None:
    monkeypatch.setenv("KINTI_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError, match="WEBHOOK_SECRET"):
        Settings(_env_file=None)


def test_twilio_cannot_start_without_complete_configuration(monkeypatch) -> None:
    monkeypatch.setenv("KINTI_TELEPHONY_PROVIDER", "twilio")

    with pytest.raises(ValidationError, match="TWILIO_ACCOUNT_SID"):
        Settings(_env_file=None)


def test_twilio_with_complete_credentials_remains_behind_the_real_call_gate(
    monkeypatch,
) -> None:
    monkeypatch.setenv("KINTI_TELEPHONY_PROVIDER", "twilio")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+51000000000")
    monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://voz.example.org")

    with pytest.raises(ValidationError, match="workflow durable"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "name",
    ["KINTI_VOICE_RECORDING_ENABLED", "KINTI_VOICE_TRANSCRIPT_RETENTION_ENABLED"],
)
def test_sensitive_retention_is_closed_in_phase_5a(monkeypatch, name: str) -> None:
    monkeypatch.setenv(name, "true")

    with pytest.raises(ValidationError, match="no admite"):
        Settings(_env_file=None)
