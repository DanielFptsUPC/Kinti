"""Infraestructura de pruebas.

La suite corre contra **PostgreSQL real**, no contra SQLite: el piloto se valida
sobre el mismo motor que usa en ejecución. Requiere `docker compose up -d db`.

Se usa una base separada (`kinti_test`) que se crea si falta y se limpia entre
pruebas, para no tocar nunca los datos de demostración.
"""

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Debe fijarse ANTES de importar cualquier módulo de `app`: la configuración y el
# engine se construyen en tiempo de importación.
DEFAULT_ADMIN_URL = "postgresql://kinti:kinti@localhost:5433/postgres"
TEST_DB_NAME = "kinti_test"
os.environ.setdefault(
    "KINTI_DATABASE_URL",
    f"postgresql+asyncpg://kinti:kinti@localhost:5433/{TEST_DB_NAME}",
)
os.environ.setdefault(
    "KINTI_JWT_SECRET", "secreto-de-pruebas-suficientemente-largo-para-hmac-sha256"
)
os.environ.setdefault("KINTI_ENVIRONMENT", "test")

import asyncio  # noqa: E402

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import (  # noqa: E402
    CARE_TEAM_EMAIL,
    CARE_TEAM_SECOND_EMAIL,
    CAREGIVER_LUCIA_EMAIL,
    CAREGIVER_MATEO_EMAIL,
    seed,
)

SEED_PASSWORD = "Kinti.Demo.2026"

_LIST_TABLES = text(
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
)


async def _all_tables(conn) -> list[str]:
    """Tablas reales de la base, consultadas en el momento.

    Se descubren en vez de mantenerse en una lista fija: cada fase añade tablas,
    y una lista desactualizada no falla de forma evidente — deja tablas sin
    limpiar entre pruebas o rompe la migración con `DuplicateTable`.
    """
    result = await conn.execute(_LIST_TABLES)
    return [row[0] for row in result]


def _upgrade_to_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


async def _ensure_test_database() -> None:
    conn = await asyncpg.connect(DEFAULT_ADMIN_URL)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def database() -> None:
    """Crea la base de pruebas y aplica las migraciones desde cero."""
    await _ensure_test_database()

    async with engine.begin() as conn:
        for table in await _all_tables(conn):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    # Alembic abre su propio `asyncio.run`, así que corre en otro hilo: llamarlo
    # aquí dentro reventaría contra el event loop de pytest.
    await asyncio.to_thread(_upgrade_to_head)

    yield

    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(database) -> None:
    """Deja la base vacía antes de cada prueba.

    `alembic_version` se conserva: borrarla haría creer a Alembic que el esquema
    no está migrado.
    """
    async with engine.begin() as conn:
        tables = [t for t in await _all_tables(conn) if t != "alembic_version"]
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE TABLE {joined} CASCADE"))
    yield


@pytest.fixture
async def session():
    async with SessionLocal() as db:
        yield db


@pytest.fixture
async def seeded(session):
    """Carga los tres casos sintéticos y devuelve los correos de demostración."""
    return await seed(session)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def login(client: AsyncClient, email: str, password: str = SEED_PASSWORD) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def caregiver_token(client, seeded) -> str:
    return await login(client, CAREGIVER_MATEO_EMAIL)


@pytest.fixture
async def lucia_token(client, seeded) -> str:
    return await login(client, CAREGIVER_LUCIA_EMAIL)


@pytest.fixture
async def care_team_token(client, seeded) -> str:
    return await login(client, CARE_TEAM_EMAIL)


@pytest.fixture
async def care_team_second_token(client, seeded) -> str:
    return await login(client, CARE_TEAM_SECOND_EMAIL)
