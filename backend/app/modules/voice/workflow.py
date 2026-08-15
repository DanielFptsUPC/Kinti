"""Máquina de estados pura para la llamada por turnos de Fase 5A."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from app.modules.voice import policy
from app.modules.voice.ports import (
    AppointmentHold,
    AppointmentSlot,
    AvailabilityQuery,
    IdentityEvidence,
    PresentedOption,
    ReferralGateway,
    ReferralLookup,
    ReferralStatus,
    RequestStatus,
    SchedulingGateway,
    ServiceHoursRepository,
    SpeechRate,
    TaskQueue,
    TravelConstraints,
    TurnInput,
    TurnOutput,
    VoiceState,
)


@dataclass
class VoiceSession:
    session_id: str
    provider_session_id: str
    caller_hint: str | None
    state: VoiceState = VoiceState.WELCOME
    speech_rate: SpeechRate = "slow"
    intent: str | None = None
    actor_id: str | None = None
    patient_id: str | None = None
    referral_id: str | None = None
    travel_step: int = 0
    travel_answers: dict[str, str] = field(default_factory=dict)
    travel: TravelConstraints | None = None
    options: tuple[AppointmentSlot, ...] = ()
    selected_slot: AppointmentSlot | None = None
    hold: AppointmentHold | None = None
    request_id: str | None = None
    outcome: RequestStatus | None = None
    comprehension_failures: int = 0
    teach_back_failures: int = 0
    last_prompt: str = ""
    initial_output: TurnOutput | None = None
    last_output: TurnOutput | None = None
    history: list[TurnOutput] = field(default_factory=list)
    processed_events: dict[str, TurnOutput] = field(default_factory=dict)


class InMemoryVoiceAppointmentWorkflow:
    """Flujo determinista sin persistencia, red ni modelo generativo.

    La implementación conserva estado en memoria para el simulador y las pruebas.
    Un adaptador posterior puede persistir ``VoiceSession`` después de cada
    turno sin modificar estas transiciones.
    """

    def __init__(
        self,
        *,
        referrals: ReferralGateway,
        scheduling: SchedulingGateway,
        service_hours: ServiceHoursRepository,
        task_queue: TaskQueue,
        today: Callable[[], date] = date.today,
        max_reprompts: int = 2,
    ) -> None:
        if max_reprompts < 1:
            raise ValueError("max_reprompts debe ser al menos uno")
        self._referrals = referrals
        self._scheduling = scheduling
        self._service_hours = service_hours
        self._task_queue = task_queue
        self._today = today
        self._max_reprompts = max_reprompts
        self._sessions: dict[str, VoiceSession] = {}
        self._provider_sessions: dict[str, str] = {}

    async def start(
        self, *, provider_session_id: str, caller_hint: str | None = None
    ) -> TurnOutput:
        existing_id = self._provider_sessions.get(provider_session_id)
        if existing_id is not None:
            existing = self._sessions[existing_id]
            if existing.initial_output is None:  # pragma: no cover - construcción defensiva
                raise RuntimeError("La sesión existente no tiene una respuesta inicial")
            return existing.initial_output

        session_id = str(uuid4())
        session = VoiceSession(
            session_id=session_id,
            provider_session_id=provider_session_id,
            caller_hint=caller_hint,
        )
        self._sessions[session_id] = session
        self._provider_sessions[provider_session_id] = session_id
        output = self._respond(
            session,
            state=VoiceState.WELCOME,
            prompt=policy.WELCOME_PROMPT,
            expects_input=True,
            allowed_dtmf=("1", "2", "0", "8", "9", "*"),
            remember=False,
        )
        session.initial_output = output
        return output

    async def handle_turn(
        self, *, session_id: str, event_id: str, turn: TurnInput
    ) -> TurnOutput:
        if not event_id.strip():
            raise ValueError("event_id es obligatorio para que el turno sea idempotente")
        session = self.get_session(session_id)
        replay = session.processed_events.get(event_id)
        if replay is not None:
            return replay

        if policy.is_clinical_or_safety_question(turn.value):
            output = await self._handoff(
                session,
                reason="clinical_or_safety",
                prompt=policy.CLINICAL_HANDOFF_MESSAGE,
            )
        else:
            command = policy.accessibility_command(turn)
            if command == policy.AccessibilityCommand.HUMAN:
                output = await self._handoff(session, reason="requested_by_caller")
            elif command == policy.AccessibilityCommand.REPEAT:
                output = self._repeat(session, prefix="Claro. ")
            elif command == policy.AccessibilityCommand.SLOW_DOWN:
                session.speech_rate = "slow"
                output = self._repeat(session, prefix="Hablaré más despacio. ")
            elif command == policy.AccessibilityCommand.DID_NOT_UNDERSTAND:
                output = await self._reprompt(session, "Lo explicaré de otra manera. ")
            elif command == policy.AccessibilityCommand.BACK:
                output = await self._back(session)
            else:
                output = await self._dispatch(session, turn)

        session.processed_events[event_id] = output
        return output

    def get_session(self, session_id: str) -> VoiceSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError("Sesión de voz no encontrada") from exc

    async def _dispatch(self, session: VoiceSession, turn: TurnInput) -> TurnOutput:
        if session.state == VoiceState.WELCOME:
            return await self._welcome(session, turn)
        if session.state == VoiceState.IDENTIFY_INTENT:
            return await self._identify_intent(session, turn)
        if session.state == VoiceState.SERVICE_HOURS:
            return await self._service_hours_turn(session, turn)
        if session.state == VoiceState.VERIFY_IDENTITY:
            return await self._verify_identity(session, turn)
        if session.state == VoiceState.FIND_REFERRAL:
            return await self._find_referral(session, turn)
        if session.state == VoiceState.COLLECT_TRAVEL:
            return await self._collect_travel(session, turn)
        if session.state == VoiceState.PRESENT_OPTIONS:
            return await self._choose_option(session, turn)
        if session.state == VoiceState.CONFIRM_ACTION:
            return await self._confirm_action(session, turn)
        if session.state == VoiceState.TEACH_BACK:
            return await self._teach_back(session, turn)
        if session.last_output is None:  # pragma: no cover - construcción defensiva
            raise RuntimeError("La sesión no tiene una respuesta para repetir")
        return session.last_output

    async def _welcome(self, session: VoiceSession, turn: TurnInput) -> TurnOutput:
        if policy.parse_yes_no(turn) is None:
            return await self._reprompt(session)
        self._understood(session)
        return self._respond(
            session,
            state=VoiceState.IDENTIFY_INTENT,
            prompt=policy.INTENT_PROMPT,
            expects_input=True,
            allowed_dtmf=("1", "2", "3", "0", "8", "9", "*"),
        )

    async def _identify_intent(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        intent = policy.parse_intent(turn)
        if intent is None:
            return await self._reprompt(session)
        self._understood(session)
        session.intent = intent
        if intent == "hours":
            return self._respond(
                session,
                state=VoiceState.SERVICE_HOURS,
                prompt="¿De qué servicio desea escuchar el horario?",
                expects_input=True,
                allowed_dtmf=("0", "8", "9", "*"),
            )
        return self._respond(
            session,
            state=VoiceState.VERIFY_IDENTITY,
            prompt=policy.VERIFY_IDENTITY_PROMPT,
            expects_input=True,
            allowed_dtmf=("0", "8", "9", "*"),
        )

    async def _service_hours_turn(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        rows = await self._service_hours.find(turn.value, on_date=self._today())
        if not rows:
            return await self._reprompt(
                session,
                "No encontré un horario publicado para ese servicio. ",
            )
        self._understood(session)
        return self._respond(
            session,
            state=VoiceState.COMPLETED,
            prompt=policy.format_service_hours(rows),
            expects_input=False,
        )

    async def _verify_identity(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        match = await self._referrals.verify_identity(
            IdentityEvidence(
                caller_hint=session.caller_hint,
                spoken_or_typed=turn.value,
            )
        )
        if match is None or match.confidence != "verified":
            return await self._reprompt(
                session,
                "No pude verificar la relación con seguridad. ",
            )
        self._understood(session)
        session.actor_id = match.actor_id
        session.patient_id = match.patient_id
        return self._respond(
            session,
            state=VoiceState.FIND_REFERRAL,
            prompt=policy.FIND_REFERRAL_PROMPT,
            expects_input=True,
            allowed_dtmf=("0", "8", "9", "*"),
        )

    async def _find_referral(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        if session.patient_id is None:  # pragma: no cover - invariante del flujo
            raise RuntimeError("No se puede buscar una referencia sin paciente verificado")
        result = await self._referrals.lookup(
            ReferralLookup(patient_id=session.patient_id, origin_facility=turn.value)
        )
        self._understood(session)
        explanation = policy.referral_message(result)
        if result.status != ReferralStatus.APPROVED or result.referral_id is None:
            return await self._handoff(
                session,
                reason=f"referral_{result.status.value.lower()}",
                prompt=f"{explanation} {policy.HUMAN_HANDOFF_MESSAGE}",
            )

        session.referral_id = result.referral_id
        session.travel_step = 0
        return self._respond(
            session,
            state=VoiceState.COLLECT_TRAVEL,
            prompt=f"{explanation} ¿Desde qué departamento y provincia viajará?",
            expects_input=True,
            allowed_dtmf=("0", "8", "9", "*"),
        )

    async def _collect_travel(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        value = turn.value.strip()
        if not value:
            return await self._reprompt(session)

        if session.travel_step == 0:
            session.travel_answers["origin"] = value
            session.travel_step = 1
            self._understood(session)
            return self._same_state_question(session, "¿Qué día puede llegar?")
        if session.travel_step == 1:
            session.travel_answers["arrival"] = value
            session.travel_step = 2
            self._understood(session)
            return self._same_state_question(session, "¿Hasta qué día puede quedarse?")
        if session.travel_step == 2:
            session.travel_answers["return"] = value
            session.travel_step = 3
            self._understood(session)
            return self._same_state_question(
                session,
                "¿Puede permanecer más de un día?",
                allowed_dtmf=("1", "2", "0", "8", "9", "*"),
            )
        if session.travel_step == 3:
            can_stay = policy.parse_yes_no(turn)
            if can_stay is None:
                return await self._reprompt(session)
            session.travel_answers["can_stay"] = "yes" if can_stay else "no"
            session.travel_step = 4
            self._understood(session)
            return self._same_state_question(
                session,
                "¿Necesita apoyo de alojamiento o transporte?",
            )

        self._understood(session)
        travel = TravelConstraints(
            origin=session.travel_answers["origin"],
            arrival_window=session.travel_answers["arrival"],
            return_deadline=session.travel_answers["return"],
            can_stay_more_than_one_day=session.travel_answers["can_stay"] == "yes",
            support_needs=policy.parse_support_needs(value),
        )
        session.travel = travel
        if travel.support_needs:
            await self._task_queue.enqueue(
                kind="declared_travel_support",
                operation_id=f"travel-support:{session.session_id}",
                payload={
                    "session_id": session.session_id,
                    "needs": ",".join(travel.support_needs),
                },
            )
        return await self._search_and_present(session)

    async def _search_and_present(
        self, session: VoiceSession, *, changed: bool = False
    ) -> TurnOutput:
        query = self._availability_query(session)
        session.options = tuple((await self._scheduling.availability(query))[:2])
        if not session.options:
            return await self._handoff(session, reason="no_available_slot")

        prefix = "La disponibilidad cambió. " if changed else "Encontré alternativas. "
        return self._respond(
            session,
            state=VoiceState.PRESENT_OPTIONS,
            prompt=prefix + self._options_prompt(session.options),
            expects_input=True,
            allowed_dtmf=tuple(str(index) for index in range(1, len(session.options) + 1))
            + ("0", "8", "9", "*"),
            options=self._presented_options(session.options),
        )

    async def _choose_option(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        number = policy.parse_option_number(turn, len(session.options))
        if number is None:
            return await self._reprompt(session)
        self._understood(session)
        slot = session.options[number - 1]
        session.request_id = session.request_id or f"request:{session.session_id}"
        hold = await self._scheduling.hold(
            request_id=session.request_id,
            slot=slot,
            operation_id=f"hold:{session.session_id}:{slot.slot_id}",
        )
        if hold is None:
            return await self._search_and_present(session, changed=True)
        session.selected_slot = slot
        session.hold = hold
        summary = policy.speak_date_es_pe(slot.starts_at)
        return self._respond(
            session,
            state=VoiceState.CONFIRM_ACTION,
            prompt=(
                f"Voy a repetir. Usted eligió {summary}. "
                "¿Desea enviar esta solicitud?"
            ),
            expects_input=True,
            allowed_dtmf=("1", "2", "0", "8", "9", "*"),
        )

    async def _confirm_action(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        confirmed = policy.parse_yes_no(turn)
        if confirmed is None:
            return await self._reprompt(session)
        self._understood(session)
        if not confirmed:
            if session.hold is not None:
                await self._scheduling.release(session.hold)
            session.selected_slot = None
            session.hold = None
            return self._respond(
                session,
                state=VoiceState.PRESENT_OPTIONS,
                prompt="De acuerdo. " + self._options_prompt(session.options),
                expects_input=True,
                allowed_dtmf=tuple(str(index) for index in range(1, len(session.options) + 1))
                + ("0", "8", "9", "*"),
                options=self._presented_options(session.options),
            )

        if session.hold is None or session.selected_slot is None or session.patient_id is None:
            return await self._handoff(session, reason="missing_hold")
        if not await self._scheduling.revalidate(session.hold):
            session.hold = None
            session.selected_slot = None
            return await self._search_and_present(session, changed=True)

        result = await self._scheduling.submit(
            request_id=session.request_id or f"request:{session.session_id}",
            patient_id=session.patient_id,
            hold=session.hold,
            operation_id=f"submit:{session.session_id}",
        )
        if result.status not in {RequestStatus.SUBMITTED, RequestStatus.CONFIRMED}:
            return await self._handoff(session, reason="submission_not_completed")

        session.request_id = result.request_id
        session.outcome = result.status
        if result.status == RequestStatus.CONFIRMED:
            status_message = "La agenda autorizada confirmó la cita."
        else:
            status_message = (
                "La solicitud fue enviada. Programación todavía debe responder; "
                "esto aún no es una cita confirmada."
            )
        return self._respond(
            session,
            state=VoiceState.TEACH_BACK,
            prompt=(
                f"{status_message} Para asegurarme de haber explicado bien, "
                "¿qué día vendrá?"
            ),
            expects_input=True,
            allowed_dtmf=("0", "8", "9"),
            outcome=result.status,
        )

    async def _teach_back(
        self, session: VoiceSession, turn: TurnInput
    ) -> TurnOutput:
        if session.selected_slot is None:  # pragma: no cover - invariante del flujo
            return await self._handoff(session, reason="missing_teach_back_slot")
        if policy.teach_back_matches(turn.value, session.selected_slot.starts_at):
            self._understood(session)
            return self._respond(
                session,
                state=VoiceState.COMPLETED,
                prompt="Gracias. La explicación terminó y su solicitud conserva su estado.",
                expects_input=False,
                outcome=session.outcome,
            )

        session.teach_back_failures += 1
        if session.teach_back_failures >= self._max_reprompts:
            return await self._handoff(session, reason="teach_back_not_understood")
        summary = policy.speak_date_es_pe(session.selected_slot.starts_at)
        return self._respond(
            session,
            state=VoiceState.TEACH_BACK,
            prompt=f"Lo explicaré nuevamente: {summary}. ¿Qué día vendrá?",
            expects_input=True,
            allowed_dtmf=("0", "8", "9"),
            outcome=session.outcome,
            remember=False,
        )

    async def _reprompt(
        self, session: VoiceSession, prefix: str = "No pude entender su respuesta. "
    ) -> TurnOutput:
        session.comprehension_failures += 1
        if session.comprehension_failures >= self._max_reprompts:
            return await self._handoff(session, reason="two_comprehension_failures")
        return self._repeat(session, prefix=prefix)

    def _repeat(self, session: VoiceSession, *, prefix: str) -> TurnOutput:
        prompt = session.last_prompt or policy.WELCOME_PROMPT
        return self._respond(
            session,
            state=session.state,
            prompt=prefix + prompt,
            expects_input=session.last_output.expects_input if session.last_output else True,
            allowed_dtmf=session.last_output.allowed_dtmf if session.last_output else (),
            options=session.last_output.options if session.last_output else (),
            outcome=session.outcome,
            remember=False,
            update_last_prompt=False,
        )

    async def _back(self, session: VoiceSession) -> TurnOutput:
        if session.outcome in {RequestStatus.SUBMITTED, RequestStatus.CONFIRMED}:
            return self._repeat(
                session,
                prefix="La solicitud ya conserva su estado. ",
            )
        if session.state == VoiceState.COLLECT_TRAVEL and session.travel_step > 0:
            session.travel_step -= 1
            return self._respond(
                session,
                state=VoiceState.COLLECT_TRAVEL,
                prompt=self._travel_question(session.travel_step),
                expects_input=True,
                allowed_dtmf=("0", "8", "9", "*"),
                remember=False,
            )
        if session.state == VoiceState.CONFIRM_ACTION and session.hold is not None:
            await self._scheduling.release(session.hold)
            session.hold = None
            session.selected_slot = None
        if not session.history:
            return self._repeat(session, prefix="Estamos al inicio. ")
        previous = session.history.pop()
        return self._respond(
            session,
            state=previous.state,
            prompt=previous.prompt,
            expects_input=previous.expects_input,
            allowed_dtmf=previous.allowed_dtmf,
            options=previous.options,
            outcome=previous.outcome,
            remember=False,
        )

    async def _handoff(
        self,
        session: VoiceSession,
        *,
        reason: str,
        prompt: str = policy.HUMAN_HANDOFF_MESSAGE,
    ) -> TurnOutput:
        payload = {"session_id": session.session_id, "reason": reason}
        if session.patient_id is not None:
            payload["patient_id"] = session.patient_id
        await self._task_queue.enqueue(
            kind="human_callback",
            operation_id=f"callback:{session.session_id}",
            payload=payload,
        )
        if session.outcome not in {RequestStatus.SUBMITTED, RequestStatus.CONFIRMED}:
            session.outcome = RequestStatus.HUMAN_HANDOFF
        return self._respond(
            session,
            state=VoiceState.HUMAN_HANDOFF,
            prompt=prompt,
            expects_input=False,
            outcome=session.outcome,
        )

    def _same_state_question(
        self,
        session: VoiceSession,
        prompt: str,
        *,
        allowed_dtmf: tuple[str, ...] = ("0", "8", "9", "*"),
    ) -> TurnOutput:
        return self._respond(
            session,
            state=VoiceState.COLLECT_TRAVEL,
            prompt=prompt,
            expects_input=True,
            allowed_dtmf=allowed_dtmf,
            remember=False,
        )

    def _respond(
        self,
        session: VoiceSession,
        *,
        state: VoiceState,
        prompt: str,
        expects_input: bool,
        allowed_dtmf: tuple[str, ...] = (),
        options: tuple[PresentedOption, ...] = (),
        outcome: RequestStatus | None = None,
        remember: bool = True,
        update_last_prompt: bool = True,
    ) -> TurnOutput:
        policy.assert_accessible_prompt(prompt)
        if remember and session.last_output is not None and state != session.state:
            session.history.append(session.last_output)
        session.state = state
        if update_last_prompt:
            session.last_prompt = prompt
        output = TurnOutput(
            session_id=session.session_id,
            state=state,
            prompt=prompt,
            expects_input=expects_input,
            speech_rate=session.speech_rate,
            allowed_dtmf=allowed_dtmf,
            options=options,
            outcome=outcome if outcome is not None else session.outcome,
        )
        session.last_output = output
        return output

    def _availability_query(self, session: VoiceSession) -> AvailabilityQuery:
        if session.patient_id is None or session.referral_id is None or session.travel is None:
            raise RuntimeError("La consulta de cupos requiere identidad, referencia y viaje")
        return AvailabilityQuery(
            patient_id=session.patient_id,
            referral_id=session.referral_id,
            travel=session.travel,
        )

    @staticmethod
    def _options_prompt(options: tuple[AppointmentSlot, ...]) -> str:
        spoken = " ".join(
            policy.format_option(number, slot)
            for number, slot in enumerate(options, start=1)
        )
        if len(options) == 1:
            return f"{spoken} ¿Desea la opción uno?"
        return f"{spoken} ¿Prefiere la opción uno o la opción dos?"

    @staticmethod
    def _presented_options(
        options: tuple[AppointmentSlot, ...]
    ) -> tuple[PresentedOption, ...]:
        return tuple(
            PresentedOption(
                number=number,
                slot_id=slot.slot_id,
                spoken_text=policy.format_option(number, slot),
            )
            for number, slot in enumerate(options, start=1)
        )

    @staticmethod
    def _understood(session: VoiceSession) -> None:
        session.comprehension_failures = 0

    @staticmethod
    def _travel_question(step: int) -> str:
        return (
            "¿Desde qué departamento y provincia viajará?",
            "¿Qué día puede llegar?",
            "¿Hasta qué día puede quedarse?",
            "¿Puede permanecer más de un día?",
            "¿Necesita apoyo de alojamiento o transporte?",
        )[step]
