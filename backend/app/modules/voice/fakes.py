"""Implementaciones deterministas de todos los puertos de Kinti Voz."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.voice import policy
from app.modules.voice.ports import (
    AppointmentHold,
    AppointmentSlot,
    AvailabilityQuery,
    HoldStatus,
    IdentityEvidence,
    IdentityMatch,
    QueuedTask,
    ReferralLookup,
    ReferralResult,
    ReferralStatus,
    RequestStatus,
    ServiceHour,
    SpeechRate,
    SubmissionResult,
    TranscriptionResult,
    TurnOutput,
)
from app.modules.voice.workflow import InMemoryVoiceAppointmentWorkflow


class FakeTelephonyGateway:
    def render(self, output: TurnOutput) -> str:
        return output.prompt


class FakeSpeechToText:
    def __init__(self, transcript: str | None = None) -> None:
        self.transcript = transcript
        self.calls = 0

    async def transcribe(
        self, audio: bytes, language: str = "es-PE"
    ) -> TranscriptionResult:
        self.calls += 1
        text = self.transcript if self.transcript is not None else audio.decode("utf-8")
        return TranscriptionResult(text=text, language=language)


class FakeTextToSpeech:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, SpeechRate]] = []

    async def synthesize(
        self,
        text: str,
        *,
        language: str = "es-PE",
        speech_rate: SpeechRate = "normal",
    ) -> bytes:
        self.calls.append((text, language, speech_rate))
        return f"{language}|{speech_rate}|{text}".encode()


class FakeReferralGateway:
    """Coincidencias sintéticas; el Caller ID nunca basta por sí solo."""

    def __init__(
        self,
        *,
        identity_terms: tuple[str, ...] = ("mateo", "2468"),
        referrals: dict[str, ReferralResult] | None = None,
    ) -> None:
        self.identity_terms = tuple(policy.normalize(term) for term in identity_terms)
        self.referrals = referrals or {
            "puno": ReferralResult(
                status=ReferralStatus.APPROVED,
                referral_id="referral-puno-approved",
            ),
            "cusco": ReferralResult(
                status=ReferralStatus.IN_REVIEW,
                referral_id="referral-cusco-review",
            ),
            "ayacucho": ReferralResult(
                status=ReferralStatus.OBSERVED,
                referral_id="referral-ayacucho-observed",
                missing_requirement_codes=("ADMIN_DOCUMENT",),
            ),
        }
        self.identity_calls = 0
        self.lookup_calls = 0

    async def verify_identity(self, evidence: IdentityEvidence) -> IdentityMatch | None:
        self.identity_calls += 1
        spoken = policy.normalize(evidence.spoken_or_typed)
        # El teléfono de origen no participa en esta decisión: sólo sería una pista.
        if not any(term in spoken for term in self.identity_terms):
            return None
        return IdentityMatch(actor_id="caregiver-mateo", patient_id="patient-mateo")

    async def lookup(self, query: ReferralLookup) -> ReferralResult:
        self.lookup_calls += 1
        facility = policy.normalize(query.origin_facility)
        for term, result in self.referrals.items():
            if policy.normalize(term) in facility:
                return result
        return ReferralResult(status=ReferralStatus.NOT_FOUND)


class ManualReferralGateway(FakeReferralGateway):
    """Cola manual determinista; nunca aprueba algo que no esté precargado."""


class FakeSchedulingGateway:
    """Agenda sintética que como máximo envía una solicitud manual.

    Aunque tenga slots, esta implementación jamás devuelve ``CONFIRMED``. Un
    slot fake demuestra el flujo, no representa autoridad institucional.
    """

    def __init__(self, slots: list[AppointmentSlot] | None = None) -> None:
        self.slots = slots or _default_slots()
        self.invalidated_slot_ids: set[str] = set()
        self.released_hold_ids: set[str] = set()
        self.holds_by_operation: dict[str, AppointmentHold] = {}
        self.submissions_by_request: dict[str, SubmissionResult] = {}
        self.availability_calls = 0
        self.hold_calls = 0
        self.revalidate_calls = 0
        self.release_calls = 0
        self.submit_calls = 0

    async def availability(self, query: AvailabilityQuery) -> list[AppointmentSlot]:
        self.availability_calls += 1
        return [slot for slot in self.slots if slot.slot_id not in self.invalidated_slot_ids]

    async def hold(
        self, *, request_id: str, slot: AppointmentSlot, operation_id: str
    ) -> AppointmentHold | None:
        existing = self.holds_by_operation.get(operation_id)
        if existing is not None:
            return existing
        self.hold_calls += 1
        if slot.slot_id in self.invalidated_slot_ids:
            return None
        hold = AppointmentHold(
            hold_id=f"hold-{len(self.holds_by_operation) + 1}",
            request_id=request_id,
            slot=slot,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        self.holds_by_operation[operation_id] = hold
        return hold

    async def revalidate(self, hold: AppointmentHold) -> bool:
        self.revalidate_calls += 1
        return (
            hold.status == HoldStatus.HELD
            and hold.hold_id not in self.released_hold_ids
            and hold.slot.slot_id not in self.invalidated_slot_ids
        )

    async def release(self, hold: AppointmentHold) -> None:
        self.release_calls += 1
        self.released_hold_ids.add(hold.hold_id)
        for operation_id, stored in tuple(self.holds_by_operation.items()):
            if stored.hold_id == hold.hold_id:
                self.holds_by_operation[operation_id] = replace(
                    stored,
                    status=HoldStatus.RELEASED,
                )

    async def submit(
        self,
        *,
        request_id: str,
        patient_id: str,
        hold: AppointmentHold,
        operation_id: str,
    ) -> SubmissionResult:
        existing = self.submissions_by_request.get(request_id)
        if existing is not None:
            return existing
        self.submit_calls += 1
        if not await self.revalidate(hold):
            return SubmissionResult(request_id=request_id, status=RequestStatus.REJECTED)
        result = SubmissionResult(request_id=request_id, status=RequestStatus.SUBMITTED)
        self.submissions_by_request[request_id] = result
        return result


class ManualSchedulingGateway(FakeSchedulingGateway):
    """Adaptador de revisión humana: también termina en ``SUBMITTED``."""


class FakeServiceHoursRepository:
    def __init__(self, rows: list[ServiceHour] | None = None) -> None:
        self.rows = rows or [
            ServiceHour(
                service="Hematología pediátrica",
                site="Sede principal",
                spoken_location="consulta externa, tercer piso",
                timezone="America/Lima",
                weekday=0,
                opens_at=time(8),
                closes_at=time(14),
                valid_from=date(2026, 1, 1),
                valid_until=None,
                version="2026.1",
            )
        ]
        self.calls = 0

    async def find(self, spoken_service: str, *, on_date: date) -> list[ServiceHour]:
        self.calls += 1
        query = policy.normalize(spoken_service)
        return [
            row
            for row in self.rows
            if row.status == "published"
            and row.valid_from <= on_date
            and (row.valid_until is None or row.valid_until >= on_date)
            and (
                query in policy.normalize(row.service)
                or policy.normalize(row.service) in query
                or any(word in policy.normalize(row.service) for word in query.split())
            )
        ]


class FakeTaskQueue:
    def __init__(self) -> None:
        self.tasks_by_operation: dict[str, QueuedTask] = {}
        self.enqueue_calls = 0

    @property
    def tasks(self) -> list[QueuedTask]:
        return list(self.tasks_by_operation.values())

    async def enqueue(
        self, *, kind: str, operation_id: str, payload: dict[str, str]
    ) -> QueuedTask:
        existing = self.tasks_by_operation.get(operation_id)
        if existing is not None:
            return existing
        self.enqueue_calls += 1
        task = QueuedTask(kind=kind, operation_id=operation_id, payload=dict(payload))
        self.tasks_by_operation[operation_id] = task
        return task


class FakeVoiceAppointmentWorkflow(InMemoryVoiceAppointmentWorkflow):
    """Workflow listo para pruebas sin configurar ninguna dependencia externa."""

    def __init__(
        self,
        *,
        referrals: FakeReferralGateway | None = None,
        scheduling: FakeSchedulingGateway | None = None,
        service_hours: FakeServiceHoursRepository | None = None,
        task_queue: FakeTaskQueue | None = None,
        max_reprompts: int = 2,
    ) -> None:
        self.fake_referrals = referrals or FakeReferralGateway()
        self.fake_scheduling = scheduling or FakeSchedulingGateway()
        self.fake_service_hours = service_hours or FakeServiceHoursRepository()
        self.fake_task_queue = task_queue or FakeTaskQueue()
        super().__init__(
            referrals=self.fake_referrals,
            scheduling=self.fake_scheduling,
            service_hours=self.fake_service_hours,
            task_queue=self.fake_task_queue,
            today=lambda: date(2026, 8, 14),
            max_reprompts=max_reprompts,
        )


def _default_slots() -> list[AppointmentSlot]:
    lima = ZoneInfo("America/Lima")
    return [
        AppointmentSlot(
            slot_id="slot-1",
            service="Hematología pediátrica",
            starts_at=datetime(2026, 8, 24, 10, tzinfo=lima),
            availability_version="v1",
            related_activity="el análisis a las ocho de la mañana",
        ),
        AppointmentSlot(
            slot_id="slot-2",
            service="Hematología pediátrica",
            starts_at=datetime(2026, 8, 25, 14, 30, tzinfo=lima),
            availability_version="v1",
        ),
        AppointmentSlot(
            slot_id="slot-3-not-spoken",
            service="Hematología pediátrica",
            starts_at=datetime(2026, 8, 26, 9, tzinfo=lima),
            availability_version="v1",
        ),
    ]
