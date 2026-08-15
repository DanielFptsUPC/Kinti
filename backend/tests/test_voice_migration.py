"""Garantías estructurales de la migración de Kinti Voz."""

from sqlalchemy import inspect

from app.core.database import engine
from app.modules.voice.models import VOICE_SESSION_STATES
from app.modules.voice.ports import VoiceState

VOICE_TABLES = {
    "appointment_holds",
    "appointment_requests",
    "appointment_slots",
    "callback_requests",
    "referral_cases",
    "service_hours",
    "voice_events",
    "voice_sessions",
}


async def test_phase_5_tables_exist_after_upgrade(database):
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    assert tables >= VOICE_TABLES


async def test_every_external_write_has_a_required_unique_operation_id(database):
    async with engine.connect() as conn:
        for table in ("appointment_requests", "appointment_holds", "callback_requests"):
            columns = await conn.run_sync(
                lambda sync, table=table: inspect(sync).get_columns(table)
            )
            operation = next(column for column in columns if column["name"] == "operation_id")
            assert operation["nullable"] is False

            constraints = await conn.run_sync(
                lambda sync, table=table: inspect(sync).get_unique_constraints(table)
            )
            indexes = await conn.run_sync(
                lambda sync, table=table: inspect(sync).get_indexes(table)
            )
            unique_columns = {
                tuple(item["column_names"])
                for item in [*constraints, *indexes]
                if item.get("unique")
            }
            assert ("operation_id",) in unique_columns


async def test_voice_session_has_no_raw_media_or_identity_columns(database):
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync: {item["name"] for item in inspect(sync).get_columns("voice_sessions")}
        )
    forbidden = {"audio", "recording", "transcript", "phone", "caller_id", "dni"}
    assert columns.isdisjoint(forbidden)
    assert {
        "policy_version",
        "context_json",
        "last_event_key",
        "last_response_json",
        "version",
    } <= columns


async def test_voice_event_ledger_is_scoped_and_contains_no_spoken_input(database):
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync: {item["name"] for item in inspect(sync).get_columns("voice_events")}
        )
        constraints = await conn.run_sync(
            lambda sync: inspect(sync).get_unique_constraints("voice_events")
        )
    assert columns.isdisjoint({"speech", "utterance", "audio", "transcript", "phone"})
    assert {
        "voice_session_id",
        "event_type",
        "event_key",
        "resulting_state",
        "response_json",
    } <= columns
    assert any(
        item["column_names"] == ["voice_session_id", "event_type", "event_key"]
        for item in constraints
    )


async def test_active_hold_is_unique_per_slot(database):
    async with engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda sync: inspect(sync).get_indexes("appointment_holds")
        )
    active = next(item for item in indexes if item["name"] == "uq_appointment_holds_active_slot")
    assert active["unique"] is True
    assert active["column_names"] == ["slot_id"]


def test_persisted_voice_states_match_the_domain_enum():
    assert tuple(state.value for state in VoiceState) == VOICE_SESSION_STATES
