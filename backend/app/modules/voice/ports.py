"""Contratos puros de Kinti Voz.

Este módulo no conoce FastAPI, SQLAlchemy, Twilio, Gemini ni Supabase. Los
tipos representan hechos del dominio y las interfaces mantienen sustituibles
la telefonía, voz, referencias, agenda, horarios y cola de tareas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal, Protocol


class VoiceState(StrEnum):
    WELCOME = "welcome"
    IDENTIFY_INTENT = "identify_intent"
    SERVICE_HOURS = "service_hours"
    VERIFY_IDENTITY = "verify_identity"
    FIND_REFERRAL = "find_referral"
    EXPLAIN_REFERRAL = "explain_referral"
    COLLECT_TRAVEL = "collect_travel"
    SEARCH_SLOTS = "search_slots"
    PRESENT_OPTIONS = "present_options"
    HOLD_SLOT = "hold_slot"
    CONFIRM_ACTION = "confirm_action"
    REVALIDATE = "revalidate"
    SUBMIT_REQUEST = "submit_request"
    REQUEST_SUBMITTED = "request_submitted"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    TEACH_BACK = "teach_back"
    HUMAN_HANDOFF = "human_handoff"
    COMPLETED = "completed"


class ReferralStatus(StrEnum):
    RECEIVED = "RECEIVED"
    IN_REVIEW = "IN_REVIEW"
    OBSERVED = "OBSERVED"
    APPROVED = "APPROVED"
    NOT_FOUND = "NOT_FOUND"


class RequestStatus(StrEnum):
    DRAFT = "DRAFT"
    PROPOSAL_READY = "PROPOSAL_READY"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class HoldStatus(StrEnum):
    HELD = "HELD"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"


InputModality = Literal["speech", "dtmf"]
SpeechRate = Literal["slow", "normal"]


@dataclass(frozen=True)
class TurnInput:
    modality: InputModality
    value: str


@dataclass(frozen=True)
class PresentedOption:
    number: int
    slot_id: str
    spoken_text: str


@dataclass(frozen=True)
class TurnOutput:
    session_id: str
    state: VoiceState
    prompt: str
    expects_input: bool
    speech_rate: SpeechRate = "normal"
    allowed_dtmf: tuple[str, ...] = ()
    options: tuple[PresentedOption, ...] = ()
    outcome: RequestStatus | None = None


@dataclass(frozen=True)
class IdentityEvidence:
    caller_hint: str | None
    spoken_or_typed: str


@dataclass(frozen=True)
class IdentityMatch:
    actor_id: str
    patient_id: str
    confidence: Literal["verified", "uncertain"] = "verified"


@dataclass(frozen=True)
class ReferralLookup:
    patient_id: str
    origin_facility: str
    optional_reference: str | None = None


@dataclass(frozen=True)
class ReferralResult:
    status: ReferralStatus
    referral_id: str | None = None
    missing_requirement_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TravelConstraints:
    origin: str
    arrival_window: str
    return_deadline: str
    can_stay_more_than_one_day: bool
    support_needs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AvailabilityQuery:
    patient_id: str
    referral_id: str
    travel: TravelConstraints


@dataclass(frozen=True)
class AppointmentSlot:
    slot_id: str
    service: str
    starts_at: datetime
    availability_version: str
    related_activity: str | None = None


@dataclass(frozen=True)
class AppointmentHold:
    hold_id: str
    request_id: str
    slot: AppointmentSlot
    expires_at: datetime
    status: HoldStatus = HoldStatus.HELD


@dataclass(frozen=True)
class SubmissionResult:
    request_id: str
    status: RequestStatus
    external_reference: str | None = None


@dataclass(frozen=True)
class ServiceHour:
    service: str
    site: str
    spoken_location: str
    timezone: str
    weekday: int
    opens_at: time
    closes_at: time
    valid_from: date
    valid_until: date | None
    version: str
    status: Literal["published", "retired"] = "published"


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str = "es-PE"
    confidence: float = 1.0


@dataclass(frozen=True)
class QueuedTask:
    kind: str
    operation_id: str
    payload: dict[str, str] = field(default_factory=dict)


class TelephonyGateway(Protocol):
    def render(self, output: TurnOutput) -> str: ...


class SpeechToTextPort(Protocol):
    async def transcribe(self, audio: bytes, language: str = "es-PE") -> TranscriptionResult: ...


class TextToSpeechPort(Protocol):
    async def synthesize(
        self, text: str, *, language: str = "es-PE", speech_rate: SpeechRate = "normal"
    ) -> bytes: ...


class ReferralGateway(Protocol):
    async def verify_identity(self, evidence: IdentityEvidence) -> IdentityMatch | None: ...

    async def lookup(self, query: ReferralLookup) -> ReferralResult: ...


class SchedulingGateway(Protocol):
    async def availability(self, query: AvailabilityQuery) -> list[AppointmentSlot]: ...

    async def hold(
        self, *, request_id: str, slot: AppointmentSlot, operation_id: str
    ) -> AppointmentHold | None: ...

    async def revalidate(self, hold: AppointmentHold) -> bool: ...

    async def release(self, hold: AppointmentHold) -> None: ...

    async def submit(
        self,
        *,
        request_id: str,
        patient_id: str,
        hold: AppointmentHold,
        operation_id: str,
    ) -> SubmissionResult: ...


class ServiceHoursRepository(Protocol):
    async def find(self, spoken_service: str, *, on_date: date) -> list[ServiceHour]: ...


class VoiceAppointmentWorkflow(Protocol):
    async def start(
        self, *, provider_session_id: str, caller_hint: str | None = None
    ) -> TurnOutput: ...

    async def handle_turn(
        self, *, session_id: str, event_id: str, turn: TurnInput
    ) -> TurnOutput: ...


class TaskQueue(Protocol):
    async def enqueue(
        self, *, kind: str, operation_id: str, payload: dict[str, str]
    ) -> QueuedTask: ...
