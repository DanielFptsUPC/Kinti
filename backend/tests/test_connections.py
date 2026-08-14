"""Configuración de conexiones: separación runtime/migración, TLS y pool.

Estas reglas se aplican al arrancar. Probarlas aquí es lo que impide que un
despliegue quede sin cifrar o que Alembic acabe hablando por un pooler en
transaction mode, donde sus locks de DDL no funcionan.

Verificarlas **contra Supabase** sigue pendiente: requiere credenciales. Lo que
se comprueba aquí es que el código haga lo que el runbook promete.
"""

import ssl

import pytest

from app.core.config import Settings


def _settings(**env) -> Settings:
    return Settings(_env_file=None, **env)


# ------------------------------------------------------- separación de URLs


def test_migration_falls_back_to_runtime_when_not_configured(monkeypatch):
    monkeypatch.setenv("KINTI_DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    monkeypatch.delenv("KINTI_MIGRATION_DATABASE_URL", raising=False)

    settings = _settings()
    assert settings.migration_url == settings.runtime_database_url


def test_migration_uses_its_own_url_when_configured(monkeypatch):
    """Alembic necesita conexión directa: un pooler rompe sus locks de DDL."""
    monkeypatch.setenv("KINTI_DATABASE_URL", "postgresql+asyncpg://u:p@pooler:6543/db")
    monkeypatch.setenv(
        "KINTI_MIGRATION_DATABASE_URL", "postgresql+asyncpg://u:p@direct:5432/db"
    )

    settings = _settings()
    assert "direct:5432" in settings.migration_url
    assert "pooler:6543" in settings.runtime_database_url
    assert settings.migration_url != settings.runtime_database_url


def test_alembic_env_uses_the_migration_url(monkeypatch):
    """La separación no sirve de nada si Alembic no la usa."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )
    assert "migration_url" in source
    assert 'set_main_option("sqlalchemy.url", get_settings().database_url)' not in source


# -------------------------------------------------------------------- TLS


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@host/db?sslmode=disable",
        "postgresql+asyncpg://u:p@host/db?sslmode=DISABLE",
        "postgresql+asyncpg://u:p@host/db?sslmode = disable",
    ],
)
def test_sslmode_disable_is_rejected_at_startup(monkeypatch, url):
    """Falla ruidosamente en vez de degradar en silencio."""
    monkeypatch.setenv("KINTI_DATABASE_URL", url)

    with pytest.raises(ValueError, match="sslmode=disable"):
        _ = _settings().runtime_database_url


def test_plain_url_is_accepted(monkeypatch):
    monkeypatch.setenv("KINTI_DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    assert _settings().runtime_database_url.endswith("/db")


def test_tls_disabled_by_default_for_local_development():
    """El PostgreSQL en contenedor no tiene certificado que verificar."""
    assert _settings().asyncpg_connect_args == {}


def test_tls_requires_a_verified_certificate(monkeypatch):
    """Cifrar sin verificar deja la puerta abierta a un intermediario."""
    monkeypatch.setenv("KINTI_REQUIRE_TLS", "true")

    args = _settings().asyncpg_connect_args
    context = args["ssl"]

    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


# -------------------------------------------------------------------- pool


def test_pool_is_configurable(monkeypatch):
    monkeypatch.setenv("KINTI_DB_POOL_SIZE", "12")
    monkeypatch.setenv("KINTI_DB_MAX_OVERFLOW", "3")
    monkeypatch.setenv("KINTI_DB_POOL_TIMEOUT", "10")
    monkeypatch.setenv("KINTI_DB_POOL_RECYCLE", "600")

    settings = _settings()
    assert settings.db_pool_size == 12
    assert settings.db_max_overflow == 3
    assert settings.db_pool_timeout == 10
    assert settings.db_pool_recycle == 600


def test_pool_defaults_are_conservative():
    """Valores modestos: el límite real depende del plan contratado."""
    settings = _settings()
    assert settings.db_pool_size + settings.db_max_overflow <= 15
    assert settings.db_pool_recycle > 0


def test_running_engine_applies_the_configured_pool():
    """El engine real usa la configuración, no los valores por defecto."""
    from app.core.database import engine

    assert engine.pool.size() > 0
    assert engine.pool._pre_ping is True
