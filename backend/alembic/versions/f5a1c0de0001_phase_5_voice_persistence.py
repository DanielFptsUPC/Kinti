"""phase 5 voice, referrals and appointment persistence

Revision ID: f5a1c0de0001
Revises: 8a5c70ba54d1
Create Date: 2026-08-14 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5a1c0de0001"
down_revision: str | None = "8a5c70ba54d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_hours",
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("site", sa.String(length=120), nullable=False),
        sa.Column("spoken_location", sa.String(length=240), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("administrative_source", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "closes_at > opens_at", name="ck_service_hours_time_order"
        ),
        sa.CheckConstraint(
            "status IN ('published', 'retired')", name="ck_service_hours_status"
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6", name="ck_service_hours_weekday"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service",
            "site",
            "weekday",
            "opens_at",
            "version",
            name="uq_service_hours_version",
        ),
    )
    op.create_index(
        "ix_service_hours_published",
        "service_hours",
        ["service", "status", "valid_from"],
        unique=False,
    )

    op.create_table(
        "referral_cases",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("origin_facility", sa.String(length=180), nullable=False),
        sa.Column("origin_region", sa.String(length=100), nullable=False),
        sa.Column("origin_province", sa.String(length=100), nullable=False),
        sa.Column("requested_specialty", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("missing_requirements", sa.JSON(), nullable=True),
        sa.Column("external_identifier", sa.String(length=160), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('received', 'in_review', 'observed', 'approved')",
            name="ck_referral_cases_status",
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_identifier"),
    )
    op.create_index(
        "ix_referral_cases_origin",
        "referral_cases",
        ["origin_region", "origin_province", "origin_facility"],
        unique=False,
    )
    op.create_index(
        "ix_referral_cases_patient_status",
        "referral_cases",
        ["patient_id", "status"],
        unique=False,
    )

    op.create_table(
        "appointment_slots",
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("site", sa.String(length=120), nullable=False),
        sa.Column("spoken_location", sa.String(length=240), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("professional_key", sa.String(length=120), nullable=False),
        sa.Column("equivalence_group", sa.String(length=80), nullable=False),
        sa.Column("available_places", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("availability_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("external_key", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "available_places >= 0", name="ck_appointment_slots_available_places"
        ),
        sa.CheckConstraint(
            "ends_at > starts_at", name="ck_appointment_slots_time_order"
        ),
        sa.CheckConstraint(
            "status IN ('available', 'blocked', 'cancelled')",
            name="ck_appointment_slots_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source", "external_key", name="uq_appointment_slots_source_external"
        ),
    )
    op.create_index(
        "ix_appointment_slots_equivalence",
        "appointment_slots",
        ["equivalence_group", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointment_slots_search",
        "appointment_slots",
        ["service", "status", "starts_at"],
        unique=False,
    )

    op.create_table(
        "voice_sessions",
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_call_key", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("speech_rate", sa.String(length=16), nullable=False),
        sa.Column("consent_status", sa.String(length=16), nullable=False),
        sa.Column("reprompt_count", sa.Integer(), nullable=False),
        sa.Column("transfer_reason", sa.String(length=80), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("last_event_key", sa.String(length=160), nullable=True),
        sa.Column("last_response_json", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "consent_status IN ('unknown', 'granted', 'declined')",
            name="ck_voice_sessions_consent",
        ),
        sa.CheckConstraint(
            "reprompt_count >= 0", name="ck_voice_sessions_reprompts"
        ),
        sa.CheckConstraint(
            "state IN ("
            "'welcome', 'identify_intent', 'service_hours', 'verify_identity', "
            "'find_referral', 'explain_referral', 'collect_travel', 'search_slots', "
            "'present_options', 'hold_slot', 'confirm_action', 'revalidate', "
            "'submit_request', "
            "'request_submitted', 'appointment_confirmed', 'teach_back', "
            "'human_handoff', 'completed'"
            ")",
            name="ck_voice_sessions_state",
        ),
        sa.CheckConstraint("version >= 1", name="ck_voice_sessions_version"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voice_sessions_actor_id", "voice_sessions", ["actor_id"], unique=False
    )
    op.create_index(
        "ix_voice_sessions_patient_id", "voice_sessions", ["patient_id"], unique=False
    )
    op.create_index(
        "ix_voice_sessions_provider_call_key",
        "voice_sessions",
        ["provider_call_key"],
        unique=True,
    )
    op.create_index(
        "ix_voice_sessions_state_started",
        "voice_sessions",
        ["state", "started_at"],
        unique=False,
    )

    op.create_table(
        "voice_events",
        sa.Column("voice_session_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("resulting_state", sa.String(length=40), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('incoming', 'turn', 'status', 'recovery')",
            name="ck_voice_events_type",
        ),
        sa.ForeignKeyConstraint(
            ["voice_session_id"], ["voice_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "voice_session_id",
            "event_type",
            "event_key",
            name="uq_voice_events_session_type_key",
        ),
    )
    op.create_index(
        "ix_voice_events_session_created",
        "voice_events",
        ["voice_session_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "appointment_requests",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("referral_id", sa.Uuid(), nullable=True),
        sa.Column("voice_session_id", sa.Uuid(), nullable=True),
        sa.Column("request_kind", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_operation_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_slot_ids", sa.JSON(), nullable=True),
        sa.Column("submission_operation_id", sa.Uuid(), nullable=True),
        sa.Column("selected_slot_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("required_equivalence_group", sa.String(length=80), nullable=True),
        sa.Column("origin_region", sa.String(length=100), nullable=True),
        sa.Column("origin_province", sa.String(length=100), nullable=True),
        sa.Column("arrival_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrival_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("travel_minutes", sa.Integer(), nullable=True),
        sa.Column("needs_lodging", sa.Boolean(), nullable=False),
        sa.Column("needs_transport", sa.Boolean(), nullable=False),
        sa.Column("can_stay_more_than_one_day", sa.Boolean(), nullable=False),
        sa.Column("external_identifier", sa.String(length=160), nullable=True),
        sa.Column("external_result", sa.String(length=80), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "request_kind IN ('new', 'reschedule', 'consolidate')",
            name="ck_appointment_requests_kind",
        ),
        sa.CheckConstraint(
            "source IN ('voice', 'app', 'staff')",
            name="ck_appointment_requests_source",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'draft', 'proposal_ready', 'awaiting_confirmation', 'submitted', "
            "'confirmed', 'rejected', 'expired', 'human_handoff'"
            ")",
            name="ck_appointment_requests_status",
        ),
        sa.CheckConstraint(
            "status <> 'confirmed' OR ("
            "external_identifier IS NOT NULL AND external_result = 'confirmed'"
            ")",
            name="ck_appointment_requests_confirmed_evidence",
        ),
        sa.CheckConstraint("version >= 1", name="ck_appointment_requests_version"),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["referral_id"], ["referral_cases.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["selected_slot_id"], ["appointment_slots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["voice_session_id"], ["voice_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_operation_id"),
        sa.UniqueConstraint("submission_operation_id"),
    )
    op.create_index(
        "ix_appointment_requests_operation_id",
        "appointment_requests",
        ["operation_id"],
        unique=True,
    )
    op.create_index(
        "ix_appointment_requests_patient_status",
        "appointment_requests",
        ["patient_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_appointment_requests_requested_by",
        "appointment_requests",
        ["requested_by"],
        unique=False,
    )

    op.create_table(
        "appointment_holds",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_version", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('held', 'consumed', 'expired', 'released')",
            name="ck_appointment_holds_status",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["appointment_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"], ["appointment_slots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_appointment_holds_operation_id",
        "appointment_holds",
        ["operation_id"],
        unique=True,
    )
    op.create_index(
        "ix_appointment_holds_request",
        "appointment_holds",
        ["request_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_appointment_holds_active_slot",
        "appointment_holds",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status = 'held'"),
    )

    op.create_table(
        "callback_requests",
        sa.Column("voice_session_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("contact_reference", sa.String(length=255), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_code", sa.String(length=80), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested', 'assigned', 'completed', 'cancelled', 'expired')",
            name="ck_callback_requests_status",
        ),
        sa.CheckConstraint(
            "reason_code IN ("
            "'requested_by_caller', 'two_comprehension_failures', "
            "'clinical_or_safety', 'recognition_failed_twice', "
            "'workflow_handoff', 'provider_failed', 'runtime_recovery', "
            "'manual_handoff', 'identity_unverified'"
            ")",
            name="ck_callback_requests_reason",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["voice_session_id"], ["voice_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_callback_requests_operation_id",
        "callback_requests",
        ["operation_id"],
        unique=True,
    )
    op.create_index(
        "ix_callback_requests_queue",
        "callback_requests",
        ["status", "sla_due_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_callback_requests_queue", table_name="callback_requests")
    op.drop_index("ix_callback_requests_operation_id", table_name="callback_requests")
    op.drop_table("callback_requests")

    op.drop_index("uq_appointment_holds_active_slot", table_name="appointment_holds")
    op.drop_index("ix_appointment_holds_request", table_name="appointment_holds")
    op.drop_index("ix_appointment_holds_operation_id", table_name="appointment_holds")
    op.drop_table("appointment_holds")

    op.drop_index(
        "ix_appointment_requests_requested_by", table_name="appointment_requests"
    )
    op.drop_index(
        "ix_appointment_requests_patient_status", table_name="appointment_requests"
    )
    op.drop_index(
        "ix_appointment_requests_operation_id", table_name="appointment_requests"
    )
    op.drop_table("appointment_requests")

    op.drop_index("ix_voice_events_session_created", table_name="voice_events")
    op.drop_table("voice_events")

    op.drop_index("ix_voice_sessions_state_started", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_provider_call_key", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_patient_id", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_actor_id", table_name="voice_sessions")
    op.drop_table("voice_sessions")

    op.drop_index("ix_appointment_slots_search", table_name="appointment_slots")
    op.drop_index("ix_appointment_slots_equivalence", table_name="appointment_slots")
    op.drop_table("appointment_slots")

    op.drop_index("ix_referral_cases_patient_status", table_name="referral_cases")
    op.drop_index("ix_referral_cases_origin", table_name="referral_cases")
    op.drop_table("referral_cases")

    op.drop_index("ix_service_hours_published", table_name="service_hours")
    op.drop_table("service_hours")
