"""Persistencia operativa de Kinti Voz.

Estas tablas guardan estados y resultados canónicos, nunca audio ni una
transcripción completa. Referencias, disponibilidad y solicitudes son datos
dinámicos: no pertenecen al índice RAG.
"""

from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow
from app.modules.common import TimestampMixin, UuidPkMixin

SERVICE_HOUR_STATUSES = ("published", "retired")
REFERRAL_STATUSES = ("received", "in_review", "observed", "approved")
APPOINTMENT_SLOT_STATUSES = ("available", "blocked", "cancelled")
APPOINTMENT_REQUEST_KINDS = ("new", "reschedule", "consolidate")
APPOINTMENT_REQUEST_SOURCES = ("voice", "app", "staff")
APPOINTMENT_REQUEST_STATUSES = (
    "draft",
    "proposal_ready",
    "awaiting_confirmation",
    "submitted",
    "confirmed",
    "rejected",
    "expired",
    "human_handoff",
)
APPOINTMENT_HOLD_STATUSES = ("held", "consumed", "expired", "released")
VOICE_SESSION_STATES = (
    "welcome",
    "identify_intent",
    "service_hours",
    "verify_identity",
    "find_referral",
    "explain_referral",
    "collect_travel",
    "search_slots",
    "present_options",
    "hold_slot",
    "confirm_action",
    "revalidate",
    "submit_request",
    "request_submitted",
    "appointment_confirmed",
    "teach_back",
    "human_handoff",
    "completed",
)
VOICE_CONSENT_STATUSES = ("unknown", "granted", "declined")
VOICE_EVENT_TYPES = ("incoming", "turn", "status", "recovery")
CALLBACK_REQUEST_STATUSES = ("requested", "assigned", "completed", "cancelled", "expired")
CALLBACK_REASON_CODES = (
    "requested_by_caller",
    "two_comprehension_failures",
    "clinical_or_safety",
    "recognition_failed_twice",
    "workflow_handoff",
    "provider_failed",
    "runtime_recovery",
    "manual_handoff",
    "identity_unverified",
)


class ServiceHour(UuidPkMixin, TimestampMixin, Base):
    """Horario institucional versionado; no representa disponibilidad de citas."""

    __tablename__ = "service_hours"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_service_hours_weekday"),
        CheckConstraint("closes_at > opens_at", name="ck_service_hours_time_order"),
        CheckConstraint(
            "status IN ('published', 'retired')", name="ck_service_hours_status"
        ),
        UniqueConstraint(
            "service",
            "site",
            "weekday",
            "opens_at",
            "version",
            name="uq_service_hours_version",
        ),
        Index("ix_service_hours_published", "service", "status", "valid_from"),
    )

    service: Mapped[str] = mapped_column(String(120), nullable=False)
    site: Mapped[str] = mapped_column(String(120), nullable=False)
    spoken_location: Mapped[str] = mapped_column(String(240), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Lima")
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    opens_at: Mapped[time] = mapped_column(Time(), nullable=False)
    closes_at: Mapped[time] = mapped_column(Time(), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="published")
    administrative_source: Mapped[str] = mapped_column(String(200), nullable=False)


class ReferralCase(UuidPkMixin, TimestampMixin, Base):
    """Espejo sintético/manual del estado administrativo de una referencia."""

    __tablename__ = "referral_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'in_review', 'observed', 'approved')",
            name="ck_referral_cases_status",
        ),
        Index("ix_referral_cases_patient_status", "patient_id", "status"),
        Index(
            "ix_referral_cases_origin",
            "origin_region",
            "origin_province",
            "origin_facility",
        ),
    )

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    origin_facility: Mapped[str] = mapped_column(String(180), nullable=False)
    origin_region: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_province: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_specialty: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    missing_requirements: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    external_identifier: Mapped[str | None] = mapped_column(
        String(160), unique=True, nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="synthetic")


class AppointmentSlot(UuidPkMixin, TimestampMixin, Base):
    """Alternativa de un gateway de agenda; nunca es por sí sola una cita."""

    __tablename__ = "appointment_slots"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointment_slots_time_order"),
        CheckConstraint(
            "available_places >= 0", name="ck_appointment_slots_available_places"
        ),
        CheckConstraint(
            "status IN ('available', 'blocked', 'cancelled')",
            name="ck_appointment_slots_status",
        ),
        UniqueConstraint(
            "source", "external_key", name="uq_appointment_slots_source_external"
        ),
        Index("ix_appointment_slots_search", "service", "status", "starts_at"),
        Index("ix_appointment_slots_equivalence", "equivalence_group", "starts_at"),
    )

    service: Mapped[str] = mapped_column(String(120), nullable=False)
    site: Mapped[str] = mapped_column(String(120), nullable=False)
    spoken_location: Mapped[str] = mapped_column(String(240), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    professional_key: Mapped[str] = mapped_column(String(120), nullable=False)
    equivalence_group: Mapped[str] = mapped_column(String(80), nullable=False)
    available_places: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="available")
    availability_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="synthetic")
    external_key: Mapped[str] = mapped_column(String(160), nullable=False)


class VoiceSession(UuidPkMixin, TimestampMixin, Base):
    """Estado durable de una llamada, sin número crudo, audio ni transcripción."""

    __tablename__ = "voice_sessions"
    __table_args__ = (
        CheckConstraint(
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
        CheckConstraint(
            "consent_status IN ('unknown', 'granted', 'declined')",
            name="ck_voice_sessions_consent",
        ),
        CheckConstraint("reprompt_count >= 0", name="ck_voice_sessions_reprompts"),
        CheckConstraint("version >= 1", name="ck_voice_sessions_version"),
        Index("ix_voice_sessions_state_started", "state", "started_at"),
    )

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_call_key: Mapped[str] = mapped_column(
        String(160), unique=True, index=True, nullable=False
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="welcome")
    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    patient_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="SET NULL"), index=True, nullable=True
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="es-PE")
    speech_rate: Mapped[str] = mapped_column(String(16), nullable=False, default="slow")
    consent_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown"
    )
    reprompt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transfer_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    context_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_event_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoiceEvent(UuidPkMixin, TimestampMixin, Base):
    """Ledger idempotente de respuestas técnicas; nunca guarda la entrada oral."""

    __tablename__ = "voice_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('incoming', 'turn', 'status', 'recovery')",
            name="ck_voice_events_type",
        ),
        UniqueConstraint(
            "voice_session_id",
            "event_type",
            "event_key",
            name="uq_voice_events_session_type_key",
        ),
        Index("ix_voice_events_session_created", "voice_session_id", "created_at"),
    )

    voice_session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    resulting_state: Mapped[str] = mapped_column(String(40), nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AppointmentRequest(UuidPkMixin, TimestampMixin, Base):
    """Solicitud de cita; `submitted` no significa `confirmed`."""

    __tablename__ = "appointment_requests"
    __table_args__ = (
        CheckConstraint(
            "request_kind IN ('new', 'reschedule', 'consolidate')",
            name="ck_appointment_requests_kind",
        ),
        CheckConstraint(
            "source IN ('voice', 'app', 'staff')", name="ck_appointment_requests_source"
        ),
        CheckConstraint(
            "status IN ("
            "'draft', 'proposal_ready', 'awaiting_confirmation', 'submitted', "
            "'confirmed', 'rejected', 'expired', 'human_handoff'"
            ")",
            name="ck_appointment_requests_status",
        ),
        CheckConstraint(
            "status <> 'confirmed' OR ("
            "external_identifier IS NOT NULL AND external_result = 'confirmed'"
            ")",
            name="ck_appointment_requests_confirmed_evidence",
        ),
        CheckConstraint("version >= 1", name="ck_appointment_requests_version"),
        Index("ix_appointment_requests_patient_status", "patient_id", "status"),
        Index("ix_appointment_requests_requested_by", "requested_by"),
    )

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    requested_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    referral_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("referral_cases.id", ondelete="SET NULL"), nullable=True
    )
    voice_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("voice_sessions.id", ondelete="SET NULL"), nullable=True
    )
    request_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="new")
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True, nullable=False)
    proposal_operation_id: Mapped[UUID | None] = mapped_column(
        Uuid, unique=True, nullable=True
    )
    proposal_slot_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    submission_operation_id: Mapped[UUID | None] = mapped_column(
        Uuid, unique=True, nullable=True
    )
    selected_slot_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("appointment_slots.id", ondelete="SET NULL"), nullable=True
    )
    proposal_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    required_equivalence_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origin_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    arrival_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrival_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    return_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    travel_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    needs_lodging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_transport: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_stay_more_than_one_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    external_identifier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    external_result: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AppointmentHold(UuidPkMixin, TimestampMixin, Base):
    """Retención temporal local que siempre debe revalidarse al confirmar."""

    __tablename__ = "appointment_holds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('held', 'consumed', 'expired', 'released')",
            name="ck_appointment_holds_status",
        ),
        Index(
            "uq_appointment_holds_active_slot",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'held'"),
        ),
        Index("ix_appointment_holds_request", "request_id", "status"),
    )

    request_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("appointment_requests.id", ondelete="CASCADE"), nullable=False
    )
    slot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("appointment_slots.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="held")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    availability_version: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CallbackRequest(UuidPkMixin, TimestampMixin, Base):
    """Cola manual de devolución de llamada con contacto opaco."""

    __tablename__ = "callback_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'assigned', 'completed', 'cancelled', 'expired')",
            name="ck_callback_requests_status",
        ),
        CheckConstraint(
            "reason_code IN ("
            "'requested_by_caller', 'two_comprehension_failures', "
            "'clinical_or_safety', 'recognition_failed_twice', "
            "'workflow_handoff', 'provider_failed', 'runtime_recovery', "
            "'manual_handoff', 'identity_unverified'"
            ")",
            name="ck_callback_requests_reason",
        ),
        Index("ix_callback_requests_queue", "status", "sla_due_at"),
    )

    voice_session_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("voice_sessions.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    patient_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    contact_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested")
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_to: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
