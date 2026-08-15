"""Contrato HTTP de Kinti Voz.

Los estados son canónicos y separados del texto que se pronuncia. Ningún
esquema acepta audio, transcripciones, DNI ni un número telefónico crudo.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word.capitalize() for word in rest)


class VoiceApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)
]
Region = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
OpaqueReference = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=255)
]

ReferralStatus = Literal["received", "in_review", "observed", "approved"]
RequestStatus = Literal[
    "draft",
    "proposal_ready",
    "awaiting_confirmation",
    "submitted",
    "confirmed",
    "rejected",
    "expired",
    "human_handoff",
]
HoldStatus = Literal["held", "consumed", "expired", "released"]
CallbackStatus = Literal["requested", "assigned", "completed", "cancelled", "expired"]
CallbackReason = Literal[
    "requested_by_caller",
    "two_comprehension_failures",
    "clinical_or_safety",
    "recognition_failed_twice",
    "workflow_handoff",
    "provider_failed",
    "runtime_recovery",
    "manual_handoff",
    "identity_unverified",
]
VoiceStateValue = Literal[
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
]
VoiceOutcome = Literal[
    "DRAFT",
    "PROPOSAL_READY",
    "AWAITING_CONFIRMATION",
    "SUBMITTED",
    "CONFIRMED",
    "REJECTED",
    "EXPIRED",
    "HUMAN_HANDOFF",
]


class ServiceHourOut(VoiceApiModel):
    id: UUID
    service: str
    site: str
    spoken_location: str
    timezone: str
    weekday: int
    opens_at: time
    closes_at: time
    valid_from: date
    valid_until: date | None = None
    version: int
    status: Literal["published", "retired"]
    updated_at: datetime


class ReferralLookupRequest(VoiceApiModel):
    patient_id: UUID
    origin_facility: Label | None = None
    origin_region: Region | None = None
    origin_province: Region | None = None
    external_identifier: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=160)
    ] = None


class ReferralOut(VoiceApiModel):
    id: UUID
    patient_id: UUID
    origin_facility: str
    origin_region: str
    origin_province: str
    requested_specialty: str
    status: ReferralStatus
    missing_requirements: list[str] = Field(default_factory=list)
    last_synced_at: datetime | None = None
    source: str
    updated_at: datetime


class AppointmentRequestCreate(VoiceApiModel):
    patient_id: UUID
    referral_id: UUID | None = None
    request_kind: Literal["new", "reschedule", "consolidate"] = "new"
    origin_region: Region | None = None
    origin_province: Region | None = None
    arrival_window_start: datetime | None = None
    arrival_window_end: datetime | None = None
    return_deadline: datetime | None = None
    travel_minutes: int | None = Field(default=None, ge=0, le=4320)
    needs_lodging: bool = False
    needs_transport: bool = False
    can_stay_more_than_one_day: bool = False
    operation_id: UUID


class AppointmentProposalRequest(VoiceApiModel):
    operation_id: UUID
    max_options: int = Field(default=2, ge=1, le=2)


class AppointmentConfirmRequest(VoiceApiModel):
    selected_slot_id: UUID
    expected_availability_version: int = Field(ge=1)
    confirmed: Literal[True]
    operation_id: UUID


class HumanHandoffRequest(VoiceApiModel):
    reason_code: CallbackReason
    contact_reference: OpaqueReference
    operation_id: UUID


class AppointmentSlotOut(VoiceApiModel):
    id: UUID
    service: str
    site: str
    spoken_location: str
    starts_at: datetime
    ends_at: datetime
    professional_key: str
    equivalence_group: str
    available_places: int
    availability_version: int
    status: Literal["available", "blocked", "cancelled"]
    source: str


class AppointmentHoldOut(VoiceApiModel):
    id: UUID
    request_id: UUID
    slot_id: UUID
    status: HoldStatus
    expires_at: datetime
    availability_version: int


class AppointmentRequestOut(VoiceApiModel):
    id: UUID
    patient_id: UUID
    requested_by: UUID
    referral_id: UUID | None = None
    voice_session_id: UUID | None = None
    request_kind: Literal["new", "reschedule", "consolidate"]
    source: Literal["voice", "app", "staff"]
    status: RequestStatus
    selected_slot_id: UUID | None = None
    proposal_expires_at: datetime | None = None
    external_result: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class AppointmentProposalsOut(VoiceApiModel):
    request: AppointmentRequestOut
    options: list[AppointmentSlotOut] = Field(max_length=2)


class AppointmentConfirmationOut(VoiceApiModel):
    request: AppointmentRequestOut
    hold: AppointmentHoldOut
    # ``submitted`` es deliberadamente distinto de ``confirmed``.
    outcome: Literal["submitted", "confirmed"]


class HumanHandoffOut(VoiceApiModel):
    request: AppointmentRequestOut
    callback: CallbackOut


class CallbackCreateRequest(VoiceApiModel):
    patient_id: UUID | None = None
    voice_session_id: UUID | None = None
    contact_reference: OpaqueReference
    reason_code: CallbackReason
    operation_id: UUID


class CallbackOut(VoiceApiModel):
    id: UUID
    voice_session_id: UUID | None = None
    actor_id: UUID | None = None
    patient_id: UUID | None = None
    reason_code: CallbackReason
    status: CallbackStatus
    sla_due_at: datetime
    assigned_to: UUID | None = None
    completed_at: datetime | None = None
    outcome_code: str | None = None
    created_at: datetime
    updated_at: datetime


class VoiceSessionOut(VoiceApiModel):
    id: UUID
    provider: str
    state: VoiceStateValue
    actor_id: UUID | None = None
    patient_id: UUID | None = None
    language: str
    speech_rate: Literal["slow", "normal"]
    consent_status: Literal["unknown", "granted", "declined"]
    reprompt_count: int
    transfer_reason: str | None = None
    policy_version: str
    version: int
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VoiceTurnJsonRequest(VoiceApiModel):
    """Payload firmado del adaptador fake; el simulador puro no usa HTTP."""

    session_id: UUID
    event_id: Code
    modality: Literal["speech", "dtmf"]
    value: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class VoiceIncomingJsonRequest(VoiceApiModel):
    """Inicio firmado del proveedor fake, sólo con un identificador sintético."""

    provider_session_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]


class VoiceStatusJsonRequest(VoiceApiModel):
    provider_session_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]
    event_id: Code
    status: Literal["initiated", "ringing", "in_progress", "completed", "failed"]


class PresentedOptionOut(VoiceApiModel):
    number: int
    slot_id: str
    spoken_text: str


class VoiceTurnOut(VoiceApiModel):
    session_id: str
    state: VoiceStateValue
    prompt: str
    expects_input: bool
    speech_rate: Literal["slow", "normal"]
    allowed_dtmf: list[str]
    options: list[PresentedOptionOut]
    outcome: VoiceOutcome | None = None
