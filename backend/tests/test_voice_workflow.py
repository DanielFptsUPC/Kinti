"""Pruebas puras de la política y máquina de estados de Kinti Voz."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.voice import policy
from app.modules.voice.fakes import (
    FakeReferralGateway,
    FakeSchedulingGateway,
    FakeVoiceAppointmentWorkflow,
    ManualSchedulingGateway,
)
from app.modules.voice.ports import (
    AvailabilityQuery,
    ReferralResult,
    ReferralStatus,
    RequestStatus,
    TravelConstraints,
    TurnInput,
    VoiceState,
)
from app.modules.voice.simulator import run_scenario


async def _turn(
    workflow: FakeVoiceAppointmentWorkflow,
    session_id: str,
    event_id: str,
    value: str,
    modality: str = "speech",
):
    return await workflow.handle_turn(
        session_id=session_id,
        event_id=event_id,
        turn=TurnInput(modality="dtmf" if modality == "dtmf" else "speech", value=value),
    )


async def _drive_to_options(
    workflow: FakeVoiceAppointmentWorkflow,
    *,
    prefix: str = "flow",
):
    output = await workflow.start(provider_session_id=f"provider-{prefix}")
    session_id = output.session_id
    values = (
        ("sí", "speech"),
        ("referencia", "speech"),
        ("Mateo 2468", "speech"),
        ("Hospital Regional de Puno", "speech"),
        ("Puno, San Román", "speech"),
        ("veintitrés de agosto", "speech"),
        ("veinticinco de agosto", "speech"),
        ("1", "dtmf"),
        ("necesito alojamiento", "speech"),
    )
    outputs = [output]
    for index, (value, modality) in enumerate(values, start=1):
        outputs.append(
            await _turn(
                workflow,
                session_id,
                f"{prefix}-{index}",
                value,
                modality,
            )
        )
    return session_id, outputs


def test_date_is_spoken_completely_in_peruvian_spanish():
    value = datetime(2026, 8, 24, 10, tzinfo=ZoneInfo("America/Lima"))
    spoken = policy.speak_date_es_pe(value)
    assert spoken == (
        "lunes veinticuatro de agosto de dos mil veintiséis, "
        "a las diez de la mañana"
    )


@pytest.mark.asyncio
async def test_full_flow_asks_one_question_and_presents_at_most_two_options():
    workflow = FakeVoiceAppointmentWorkflow()
    _, outputs = await _drive_to_options(workflow)

    assert all(output.prompt.count("?") <= 1 for output in outputs)
    options = outputs[-1]
    assert options.state == VoiceState.PRESENT_OPTIONS
    assert len(options.options) == 2
    assert "lunes veinticuatro de agosto de dos mil veintiséis" in options.prompt
    assert "diez de la mañana" in options.prompt
    assert "slot-3-not-spoken" not in {option.slot_id for option in options.options}


@pytest.mark.asyncio
async def test_repeat_slow_down_and_back_are_available_without_advancing():
    workflow = FakeVoiceAppointmentWorkflow()
    first = await workflow.start(provider_session_id="accessibility")

    repeated = await _turn(workflow, first.session_id, "repeat", "repita")
    assert repeated.state == VoiceState.WELCOME
    assert policy.WELCOME_PROMPT in repeated.prompt

    slower = await _turn(workflow, first.session_id, "slow", "más despacio")
    assert slower.state == VoiceState.WELCOME
    assert slower.speech_rate == "slow"

    intent = await _turn(workflow, first.session_id, "yes", "sí")
    assert intent.state == VoiceState.IDENTIFY_INTENT
    back = await _turn(workflow, first.session_id, "back", "volver")
    assert back.state == VoiceState.WELCOME
    assert back.speech_rate == "slow"


@pytest.mark.asyncio
async def test_two_comprehension_failures_create_one_handoff():
    workflow = FakeVoiceAppointmentWorkflow()
    first = await workflow.start(provider_session_id="two-failures")

    reprompt = await _turn(workflow, first.session_id, "failure-1", "no entendí")
    handoff = await _turn(workflow, first.session_id, "failure-2", "no entendí")

    assert reprompt.state == VoiceState.WELCOME
    assert handoff.state == VoiceState.HUMAN_HANDOFF
    assert handoff.outcome == RequestStatus.HUMAN_HANDOFF
    assert len(workflow.fake_task_queue.tasks) == 1
    assert workflow.fake_task_queue.tasks[0].kind == "human_callback"


@pytest.mark.asyncio
async def test_clinical_question_uses_static_message_and_handoff():
    workflow = FakeVoiceAppointmentWorkflow()
    first = await workflow.start(provider_session_id="clinical")

    output = await _turn(
        workflow,
        first.session_id,
        "clinical-1",
        "Mi niño tiene fiebre, qué dosis le doy",
    )

    assert output.state == VoiceState.HUMAN_HANDOFF
    assert output.prompt == policy.CLINICAL_HANDOFF_MESSAGE
    assert "dosis" not in output.prompt.casefold()
    assert workflow.fake_task_queue.tasks[0].payload["reason"] == "clinical_or_safety"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", list(VoiceState))
async def test_human_help_is_available_from_every_state(state: VoiceState):
    workflow = FakeVoiceAppointmentWorkflow()
    first = await workflow.start(provider_session_id=f"human-{state.value}")
    workflow.get_session(first.session_id).state = state

    output = await _turn(workflow, first.session_id, f"human-event-{state.value}", "una persona")

    assert output.state == VoiceState.HUMAN_HANDOFF
    assert len(workflow.fake_task_queue.tasks) == 1


@pytest.mark.asyncio
async def test_dtmf_and_speech_take_equivalent_paths():
    speech = FakeVoiceAppointmentWorkflow()
    dtmf = FakeVoiceAppointmentWorkflow()
    speech_start = await speech.start(provider_session_id="speech")
    dtmf_start = await dtmf.start(provider_session_id="dtmf")

    speech_intent = await _turn(speech, speech_start.session_id, "s-1", "sí")
    dtmf_intent = await _turn(dtmf, dtmf_start.session_id, "d-1", "1", "dtmf")
    assert speech_intent.state == dtmf_intent.state == VoiceState.IDENTIFY_INTENT

    speech_verify = await _turn(speech, speech_start.session_id, "s-2", "referencia")
    dtmf_verify = await _turn(dtmf, dtmf_start.session_id, "d-2", "1", "dtmf")
    assert speech_verify.state == dtmf_verify.state == VoiceState.VERIFY_IDENTITY

    speech_id, _ = await _drive_to_options(speech, prefix="speech-options")
    dtmf_id, _ = await _drive_to_options(dtmf, prefix="dtmf-options")
    speech_choice = await _turn(speech, speech_id, "s-choice", "opción uno")
    dtmf_choice = await _turn(dtmf, dtmf_id, "d-choice", "1", "dtmf")
    assert speech_choice.state == dtmf_choice.state == VoiceState.CONFIRM_ACTION
    assert (
        speech.get_session(speech_id).selected_slot.slot_id
        == dtmf.get_session(dtmf_id).selected_slot.slot_id
        == "slot-1"
    )

    speech_result = await _turn(speech, speech_id, "s-confirm", "sí")
    dtmf_result = await _turn(dtmf, dtmf_id, "d-confirm", "1", "dtmf")
    assert speech_result.state == dtmf_result.state == VoiceState.TEACH_BACK
    assert speech_result.outcome == dtmf_result.outcome == RequestStatus.SUBMITTED


@pytest.mark.asyncio
async def test_replayed_event_returns_same_output_without_second_hold():
    workflow = FakeVoiceAppointmentWorkflow()
    session_id, _ = await _drive_to_options(workflow, prefix="replay")

    first = await _turn(workflow, session_id, "same-event", "opción uno")
    hold_calls = workflow.fake_scheduling.hold_calls
    replay = await _turn(workflow, session_id, "same-event", "opción dos")

    assert replay == first
    assert workflow.fake_scheduling.hold_calls == hold_calls == 1
    assert workflow.get_session(session_id).selected_slot.slot_id == "slot-1"


@pytest.mark.asyncio
async def test_replayed_start_returns_the_original_welcome_turn():
    workflow = FakeVoiceAppointmentWorkflow()
    first = await workflow.start(provider_session_id="replayed-start")
    await _turn(workflow, first.session_id, "advance", "sí")

    replay = await workflow.start(provider_session_id="replayed-start")

    assert replay == first
    assert replay.state == VoiceState.WELCOME


@pytest.mark.asyncio
@pytest.mark.parametrize("gateway_type", [FakeSchedulingGateway, ManualSchedulingGateway])
async def test_fake_and_manual_scheduling_never_confirm(gateway_type):
    gateway = gateway_type()
    travel = TravelConstraints(
        origin="Puno, San Román",
        arrival_window="23 de agosto",
        return_deadline="25 de agosto",
        can_stay_more_than_one_day=True,
    )
    query = AvailabilityQuery(
        patient_id="patient-mateo",
        referral_id="referral-approved",
        travel=travel,
    )
    slot = (await gateway.availability(query))[0]
    hold = await gateway.hold(request_id="request-1", slot=slot, operation_id="hold-1")
    assert hold is not None

    result = await gateway.submit(
        request_id="request-1",
        patient_id="patient-mateo",
        hold=hold,
        operation_id="submit-1",
    )

    assert result.status == RequestStatus.SUBMITTED
    assert result.status != RequestStatus.CONFIRMED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "origin"),
    [
        (ReferralStatus.RECEIVED, "Hospital de Piura"),
        (ReferralStatus.IN_REVIEW, "Hospital de Cusco"),
        (ReferralStatus.OBSERVED, "Hospital de Ayacucho"),
    ],
)
async def test_non_approved_referral_never_searches_slots(status, origin):
    referrals = FakeReferralGateway(
        referrals={
            policy.normalize(origin): ReferralResult(
                status=status,
                referral_id=f"referral-{status.value.lower()}",
            )
        }
    )
    workflow = FakeVoiceAppointmentWorkflow(referrals=referrals)
    first = await workflow.start(provider_session_id=f"referral-{status.value}")
    session_id = first.session_id
    for event, value in enumerate(("sí", "referencia", "Mateo", origin), start=1):
        output = await _turn(workflow, session_id, f"event-{event}", value)

    assert output.state == VoiceState.HUMAN_HANDOFF
    assert workflow.fake_scheduling.availability_calls == 0


@pytest.mark.asyncio
async def test_teach_back_reexplains_once_then_requests_human_help():
    workflow = FakeVoiceAppointmentWorkflow()
    session_id, _ = await _drive_to_options(workflow, prefix="teach-back")
    await _turn(workflow, session_id, "choose", "opción uno")
    submitted = await _turn(workflow, session_id, "confirm", "sí")
    assert submitted.outcome == RequestStatus.SUBMITTED

    repeated = await _turn(workflow, session_id, "wrong-1", "no recuerdo")
    handoff = await _turn(workflow, session_id, "wrong-2", "otro día")

    assert repeated.state == VoiceState.TEACH_BACK
    assert handoff.state == VoiceState.HUMAN_HANDOFF
    # Pedir ayuda no borra una solicitud que ya fue enviada.
    assert handoff.outcome == RequestStatus.SUBMITTED


@pytest.mark.asyncio
async def test_service_hours_come_from_versioned_repository():
    workflow = FakeVoiceAppointmentWorkflow()
    first = await workflow.start(provider_session_id="hours")
    await _turn(workflow, first.session_id, "hours-1", "sí")
    ask_service = await _turn(workflow, first.session_id, "hours-2", "horario")
    output = await _turn(workflow, first.session_id, "hours-3", "hematología")

    assert ask_service.state == VoiceState.SERVICE_HOURS
    assert output.state == VoiceState.COMPLETED
    assert "lunes" in output.prompt
    assert "ocho de la mañana" in output.prompt


@pytest.mark.asyncio
async def test_cli_scenarios_cover_success_failures_and_clinical_handoff():
    approved = await run_scenario("approved-travel-repeat", echo=False)
    failures = await run_scenario("two-failures", echo=False)
    clinical = await run_scenario("clinical", echo=False)

    assert approved[-1].state == VoiceState.COMPLETED
    assert any(output.speech_rate == "slow" for output in approved)
    assert failures[-1].state == VoiceState.HUMAN_HANDOFF
    assert clinical[-1].state == VoiceState.HUMAN_HANDOFF
