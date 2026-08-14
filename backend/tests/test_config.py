"""Lectura de configuración desde entorno.

`KINTI_CORS_ORIGINS` se documenta como lista separada por comas. Sin `NoDecode`,
pydantic-settings intenta interpretarla como JSON y el proceso ni siquiera
arranca, así que esta prueba cubre la forma documentada.
"""

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in ("KINTI_CORS_ORIGINS",):
        monkeypatch.delenv(key, raising=False)


def _settings(**env) -> Settings:
    return Settings(_env_file=None, **env)


def test_cors_origins_accepts_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv(
        "KINTI_CORS_ORIGINS", "http://localhost:8081,http://192.168.1.43:8081"
    )
    assert _settings().cors_origins == [
        "http://localhost:8081",
        "http://192.168.1.43:8081",
    ]


def test_cors_origins_trims_whitespace_and_drops_empties(monkeypatch):
    monkeypatch.setenv("KINTI_CORS_ORIGINS", " http://a ,, http://b , ")
    assert _settings().cors_origins == ["http://a", "http://b"]


def test_cors_origins_accepts_a_single_value(monkeypatch):
    monkeypatch.setenv("KINTI_CORS_ORIGINS", "http://solo")
    assert _settings().cors_origins == ["http://solo"]


def test_cors_origins_falls_back_to_the_development_default():
    assert _settings().cors_origins == [
        "http://localhost:8081",
        "http://localhost:19006",
    ]


def test_domain_windows_are_configurable(monkeypatch):
    monkeypatch.setenv("KINTI_BARRIER_RESPONSE_WINDOW_HOURS", "72")
    monkeypatch.setenv("KINTI_MISSED_TOLERANCE_HOURS", "12")
    settings = _settings()
    assert settings.barrier_response_window_hours == 72
    assert settings.missed_tolerance_hours == 12


def test_is_local_reflects_the_environment(monkeypatch):
    monkeypatch.setenv("KINTI_ENVIRONMENT", "production")
    assert _settings().is_local is False
    monkeypatch.setenv("KINTI_ENVIRONMENT", "local")
    assert _settings().is_local is True
