"""Migraciones sobre PostgreSQL vacío.

La suite completa ya corre sobre una base creada por `alembic upgrade head`
(ver `conftest.database`). Estas pruebas comprueban que el esquema resultante es
el esperado y que el modelo declarado no se desvió de la migración.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.core.database import engine
from app.models import Base

EXPECTED_TABLES = {
    "ambulatory_capacity_slots",
    "alembic_version",
    "attendance_confirmations",
    "audit_events",
    "barrier_alerts",
    "care_team_assignments",
    "caregiver_patient_links",
    "feeling_check_ins",
    "interventions",
    "milestones",
    "notification_outbox",
    "patients",
    "processed_operations",
    "users",
}


async def test_every_table_exists_after_upgrade(database):
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    assert EXPECTED_TABLES.issubset(tables)


async def test_models_match_the_migrated_schema(database):
    """No debe quedar deriva entre los modelos y la migración aplicada."""

    def _diff(sync_conn):
        context = MigrationContext.configure(sync_conn)
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as conn:
        diff = await conn.run_sync(_diff)

    assert diff == [], f"El esquema migrado difiere de los modelos: {diff}"


async def test_operation_id_is_unique(database):
    """La restricción única es lo que sostiene la idempotencia del outbox."""
    async with engine.connect() as conn:
        constraints = await conn.run_sync(
            lambda sync: inspect(sync).get_unique_constraints("processed_operations")
        )
    columns = {tuple(c["column_names"]) for c in constraints}
    indexes = await _unique_index_columns("processed_operations")
    assert ("operation_id",) in columns | indexes


async def _unique_index_columns(table: str) -> set[tuple[str, ...]]:
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync: inspect(sync).get_indexes(table))
    return {tuple(i["column_names"]) for i in indexes if i.get("unique")}


async def test_notification_dedupe_key_is_unique(database):
    async with engine.connect() as conn:
        constraints = await conn.run_sync(
            lambda sync: inspect(sync).get_unique_constraints("notification_outbox")
        )
    columns = {tuple(c["column_names"]) for c in constraints}
    assert ("dedupe_key",) in columns | await _unique_index_columns("notification_outbox")
