"""Persistencia, idempotencia y concurrencia del MVP telefónico."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.errors import DomainError
from app.core.time import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.identity.models import User
from app.modules.patients.models import Patient
from app.modules.voice.models import (
    AppointmentHold,
    AppointmentRequest,
    AppointmentSlot,
    CallbackRequest,
    ReferralCase,
    ServiceHour,
    VoiceEvent,
    VoiceSession,
)
from app.modules.voice.persistence import (
    create_appointment_request,
    create_callback_request,
    get_or_create_voice_session,
    handoff_appointment_request,
    hold_slot,
    list_appointment_requests,
    list_service_hours,
    lookup_referral,
    prepare_slot_proposals,
    record_voice_event,
    revalidate_hold,
    submit_manual_request,
)
from app.seed import (
    APPOINTMENT_SLOT_IDS,
    CAREGIVER_MATEO_EMAIL,
    MATEO_ID,
    REFERRAL_IDS,
    SEEDED_APPOINTMENT_REQUEST_ID,
    seed,
)


async def _actor_and_patient(session):
    actor = await session.scalar(select(User).where(User.email == CAREGIVER_MATEO_EMAIL))
    patient = await session.get(Patient, MATEO_ID)
    assert actor is not None and patient is not None
    return actor, patient


async def _approved_referral(session) -> ReferralCase:
    referral = await session.get(ReferralCase, REFERRAL_IDS[3])
    assert referral is not None and referral.status == "approved"
    return referral


async def test_phase_5_seed_is_idempotent_and_covers_required_scenarios(session):
    await seed(session)
    await seed(session)

    async def count(model) -> int:
        value = await session.scalar(select(func.count()).select_from(model))
        return int(value or 0)

    assert await count(ServiceHour) == 5
    assert await count(ReferralCase) == 6
    assert await count(AppointmentSlot) == 8
    assert await count(VoiceSession) == 3
    assert await count(AppointmentRequest) == 1
    assert await count(CallbackRequest) == 1

    referrals = list(await session.scalars(select(ReferralCase)))
    assert {row.status for row in referrals} == {
        "received",
        "in_review",
        "observed",
        "approved",
    }
    assert len({row.origin_region for row in referrals}) == 3
    assert len({row.origin_facility for row in referrals}) >= 3

    slots = list(await session.scalars(select(AppointmentSlot)))
    equivalents = [row for row in slots if row.equivalence_group == "hema-equivalent"]
    assert len({row.professional_key for row in equivalents}) == 2
    assert any(row.equivalence_group == "other-specialty" for row in slots)
    first = await session.get(AppointmentSlot, APPOINTMENT_SLOT_IDS[0])
    conflicting = await session.get(AppointmentSlot, APPOINTMENT_SLOT_IDS[1])
    assert first is not None and conflicting is not None
    assert (first.starts_at, first.ends_at) == (conflicting.starts_at, conflicting.ends_at)
    assert any(row.expires_at and row.expires_at < utcnow() for row in slots)
    assert any(row.available_places == 0 for row in slots)

    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    assert request is not None
    assert request.needs_lodging and request.needs_transport
    callback = await session.scalar(select(CallbackRequest))
    assert callback is not None and callback.contact_reference.startswith("user:")


async def test_confirmed_status_requires_institutional_evidence(session, seeded):
    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    assert request is not None
    request.status = "confirmed"

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_hours_and_referral_lookup_never_confuse_unknown_or_ambiguous_data(
    session, seeded
):
    hours = await list_service_hours(session)
    assert len(hours) == 5
    assert all(row.status == "published" for row in hours)

    _, mateo = await _actor_and_patient(session)
    referral = await lookup_referral(
        session,
        patient=mateo,
        origin_facility="Hospital Carlos Monge Medrano",
    )
    assert referral is not None and referral.status == "approved"
    assert (
        await lookup_referral(
            session,
            patient=mateo,
            origin_facility="Establecimiento inexistente",
        )
        is None
    )
    with pytest.raises(DomainError) as missing_evidence:
        await lookup_referral(session, patient=mateo)
    assert missing_evidence.value.code == "referral_lookup_evidence_required"


async def test_proposals_are_capped_persisted_and_idempotent(session, seeded):
    actor, _ = await _actor_and_patient(session)
    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    assert request is not None
    operation_id = uuid4()

    first = await prepare_slot_proposals(
        session,
        actor=actor,
        request=request,
        operation_id=operation_id,
        limit=99,
    )
    second = await prepare_slot_proposals(
        session,
        actor=actor,
        request=request,
        operation_id=operation_id,
        limit=99,
    )

    assert 0 < len(first) <= 2
    assert [row.id for row in second] == [row.id for row in first]
    assert all(row.equivalence_group == "hema-equivalent" for row in first)
    assert all(row.available_places > 0 for row in first)
    assert request.status == "proposal_ready"
    assert request.proposal_slot_ids == [str(row.id) for row in first]
    events = list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "prepare_appointment_proposals",
                AuditEvent.entity_id == request.id,
            )
        )
    )
    assert len(events) == 1


async def test_hold_requires_availability_version_and_manual_submit_is_not_confirmation(
    session, seeded
):
    actor, _ = await _actor_and_patient(session)
    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    assert request is not None
    proposals = await prepare_slot_proposals(
        session,
        actor=actor,
        request=request,
        operation_id=uuid4(),
    )
    slot = proposals[0]

    with pytest.raises(DomainError) as changed:
        await hold_slot(
            session,
            actor=actor,
            request=request,
            slot_id=slot.id,
            operation_id=uuid4(),
            expected_availability_version=slot.availability_version + 1,
        )
    assert changed.value.code == "availability_changed"
    assert changed.value.http_status == 409

    hold_operation = uuid4()
    hold = await hold_slot(
        session,
        actor=actor,
        request=request,
        slot_id=slot.id,
        operation_id=hold_operation,
        expected_availability_version=slot.availability_version,
    )
    repeated = await hold_slot(
        session,
        actor=actor,
        request=request,
        slot_id=slot.id,
        operation_id=hold_operation,
        expected_availability_version=slot.availability_version,
    )
    assert repeated.id == hold.id

    submit_operation = uuid4()
    submitted = await submit_manual_request(
        session,
        actor=actor,
        hold_id=hold.id,
        operation_id=submit_operation,
    )
    repeated_submit = await submit_manual_request(
        session,
        actor=actor,
        hold_id=hold.id,
        operation_id=submit_operation,
    )
    assert repeated_submit.id == submitted.id
    assert submitted.status == "submitted"
    assert submitted.status != "confirmed"
    assert submitted.external_result == "manual_review_required"
    assert hold.status == "consumed"


async def test_revalidation_expires_a_hold_when_availability_changes(session, seeded):
    actor, _ = await _actor_and_patient(session)
    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    assert request is not None
    proposals = await prepare_slot_proposals(
        session, actor=actor, request=request, operation_id=uuid4()
    )
    slot = proposals[0]
    hold = await hold_slot(
        session,
        actor=actor,
        request=request,
        slot_id=slot.id,
        operation_id=uuid4(),
        expected_availability_version=slot.availability_version,
    )
    slot.availability_version += 1
    await session.flush()

    assert await revalidate_hold(session, actor=actor, hold_id=hold.id) is False
    assert hold.status == "expired"
    assert request.status == "proposal_ready"


async def test_two_concurrent_requests_cannot_hold_the_same_slot(session, seeded):
    actor, patient = await _actor_and_patient(session)
    referral = await _approved_referral(session)
    requests: list[AppointmentRequest] = []
    for _ in range(2):
        request = await create_appointment_request(
            session,
            actor=actor,
            patient=patient,
            operation_id=uuid4(),
            source="voice",
            referral=referral,
            required_equivalence_group="hema-equivalent",
        )
        await prepare_slot_proposals(
            session, actor=actor, request=request, operation_id=uuid4()
        )
        requests.append(request)
    slot_id = UUID(requests[0].proposal_slot_ids[0])
    await session.commit()

    async def attempt(request_id, operation_id):
        async with SessionLocal() as isolated:
            local_actor = await isolated.get(User, actor.id)
            local_request = await isolated.get(AppointmentRequest, request_id)
            assert local_actor is not None and local_request is not None
            try:
                await hold_slot(
                    isolated,
                    actor=local_actor,
                    request=local_request,
                    slot_id=slot_id,
                    operation_id=operation_id,
                    expected_availability_version=1,
                )
                await isolated.commit()
                return "held"
            except DomainError as exc:
                await isolated.rollback()
                return exc.code

    results = await asyncio.gather(
        attempt(requests[0].id, uuid4()),
        attempt(requests[1].id, uuid4()),
    )
    assert sorted(results) == ["held", "slot_held"]


async def test_hold_requires_an_approved_unexpired_proposal(session, seeded):
    actor, _ = await _actor_and_patient(session)
    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    slot = await session.get(AppointmentSlot, APPOINTMENT_SLOT_IDS[0])
    assert request is not None and slot is not None

    with pytest.raises(DomainError) as without_proposal:
        await hold_slot(
            session,
            actor=actor,
            request=request,
            slot_id=slot.id,
            operation_id=uuid4(),
            expected_availability_version=slot.availability_version,
        )
    assert without_proposal.value.code == "proposal_required"

    proposals = await prepare_slot_proposals(
        session, actor=actor, request=request, operation_id=uuid4()
    )
    request.proposal_expires_at = utcnow() - timedelta(seconds=1)
    with pytest.raises(DomainError) as expired:
        await hold_slot(
            session,
            actor=actor,
            request=request,
            slot_id=proposals[0].id,
            operation_id=uuid4(),
            expected_availability_version=proposals[0].availability_version,
        )
    assert expired.value.code == "proposal_expired"


async def test_concurrent_retries_create_one_request_callback_and_voice_session(
    session, seeded
):
    actor, patient = await _actor_and_patient(session)
    referral = await _approved_referral(session)
    actor_id = actor.id
    patient_id = patient.id
    referral_id = referral.id
    request_operation = uuid4()
    callback_operation = uuid4()
    provider_key = f"call:concurrent-{uuid4()}"
    await session.commit()

    async def create_request_once():
        async with SessionLocal() as isolated:
            local_actor = await isolated.get(User, actor_id)
            local_patient = await isolated.get(Patient, patient_id)
            local_referral = await isolated.get(ReferralCase, referral_id)
            assert local_actor and local_patient and local_referral
            row = await create_appointment_request(
                isolated,
                actor=local_actor,
                patient=local_patient,
                operation_id=request_operation,
                source="voice",
                referral=local_referral,
            )
            await isolated.commit()
            return row.id

    async def create_callback_once():
        async with SessionLocal() as isolated:
            local_actor = await isolated.get(User, actor_id)
            local_patient = await isolated.get(Patient, patient_id)
            assert local_actor and local_patient
            row = await create_callback_request(
                isolated,
                operation_id=callback_operation,
                contact_reference=f"contact:{actor_id}",
                reason_code="workflow_handoff",
                sla_due_at=utcnow() + timedelta(hours=1),
                actor=local_actor,
                patient=local_patient,
            )
            await isolated.commit()
            return row.id

    async def create_voice_once():
        async with SessionLocal() as isolated:
            row = await get_or_create_voice_session(
                isolated,
                provider="fake",
                provider_call_key=provider_key,
                policy_version="voice-test-1",
            )
            await isolated.commit()
            return row.id

    request_ids = await asyncio.gather(create_request_once(), create_request_once())
    callback_ids = await asyncio.gather(create_callback_once(), create_callback_once())
    voice_ids = await asyncio.gather(create_voice_once(), create_voice_once())

    assert len(set(request_ids)) == len(set(callback_ids)) == len(set(voice_ids)) == 1
    assert (
        await session.scalar(
            select(func.count()).select_from(AppointmentRequest).where(
                AppointmentRequest.operation_id == request_operation
            )
        )
        == 1
    )
    assert (
        await session.scalar(
            select(func.count()).select_from(CallbackRequest).where(
                CallbackRequest.operation_id == callback_operation
            )
        )
        == 1
    )
    assert (
        await session.scalar(
            select(func.count()).select_from(VoiceSession).where(
                VoiceSession.provider_call_key == provider_key
            )
        )
        == 1
    )


async def test_voice_events_and_callbacks_are_safe_audited_and_idempotent(session, seeded):
    actor, patient = await _actor_and_patient(session)
    voice = await get_or_create_voice_session(
        session,
        provider="fake",
        provider_call_key="call:test-safe-event",
        policy_version="voice-test-1",
    )
    voice.actor_id = actor.id
    voice.patient_id = patient.id
    event_key = "event:opaque-001"
    response = {"prompt_code": "ask_origin", "expects_input": True}

    first = await record_voice_event(
        session,
        voice_session=voice,
        event_key=event_key,
        next_state="find_referral",
        response=response,
        context={"intent": "referral_lookup"},
        expected_version=1,
    )
    second = await record_voice_event(
        session,
        voice_session=voice,
        event_key=event_key,
        next_state="find_referral",
        response=response,
    )
    assert first == second == response
    assert (
        await session.scalar(select(func.count()).select_from(VoiceEvent))
        == 1
    )
    voice_events = list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "voice_state_transition",
                AuditEvent.entity_id == voice.id,
            )
        )
    )
    assert len(voice_events) == 1
    assert set(voice_events[0].metadata_json or {}) == {
        "state",
        "event_hash",
        "event_type",
        "reprompt_count",
    }

    with pytest.raises(DomainError) as sensitive:
        await record_voice_event(
            session,
            voice_session=voice,
            event_key="event:unsafe",
            next_state="find_referral",
            response={"transcript": "contenido que no debe persistirse"},
        )
    assert sensitive.value.code == "sensitive_voice_payload"

    with pytest.raises(DomainError) as raw_contact:
        await create_callback_request(
            session,
            operation_id=uuid4(),
            contact_reference="+51999999999",
            reason_code="requested_by_caller",
            sla_due_at=utcnow() + timedelta(hours=1),
            actor=actor,
            patient=patient,
            voice_session=voice,
        )
    assert raw_contact.value.code == "opaque_contact_required"

    with pytest.raises(DomainError) as disguised_phone:
        await create_callback_request(
            session,
            operation_id=uuid4(),
            contact_reference="user:+51999999999",
            reason_code="requested_by_caller",
            sla_due_at=utcnow() + timedelta(hours=1),
            actor=actor,
            patient=patient,
            voice_session=voice,
        )
    assert disguised_phone.value.code == "opaque_contact_required"

    with pytest.raises(DomainError) as foreign_contact:
        await create_callback_request(
            session,
            operation_id=uuid4(),
            contact_reference=f"contact:{uuid4()}",
            reason_code="requested_by_caller",
            sla_due_at=utcnow() + timedelta(hours=1),
            actor=actor,
            patient=patient,
            voice_session=voice,
        )
    assert foreign_contact.value.code == "contact_reference_not_owned"

    callback_operation = uuid4()
    callback = await create_callback_request(
        session,
        operation_id=callback_operation,
        contact_reference=f"contact:{actor.id}",
        reason_code="requested_by_caller",
        sla_due_at=utcnow() + timedelta(hours=1),
        actor=actor,
        patient=patient,
        voice_session=voice,
    )
    repeated = await create_callback_request(
        session,
        operation_id=callback_operation,
        contact_reference=f"contact:{actor.id}",
        reason_code="requested_by_caller",
        sla_due_at=utcnow() + timedelta(hours=1),
        actor=actor,
        patient=patient,
        voice_session=voice,
    )
    assert repeated.id == callback.id
    callback_events = list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "create_callback_request",
                AuditEvent.entity_id == callback.id,
            )
        )
    )
    assert len(callback_events) == 1
    dumped = str(callback_events[0].metadata_json).lower()
    assert "phone" not in dumped and "transcript" not in dumped


async def test_terminal_voice_session_cannot_be_reopened(session, seeded):
    voice = await get_or_create_voice_session(
        session,
        provider="fake",
        provider_call_key="call:test-terminal-state",
        policy_version="voice-test-1",
    )
    terminal_response = {"state": "completed", "expectsInput": False}
    await record_voice_event(
        session,
        voice_session=voice,
        event_key="event:terminal",
        next_state="completed",
        response=terminal_response,
    )

    replay = await record_voice_event(
        session,
        voice_session=voice,
        event_key="event:late-turn",
        next_state="identify_intent",
        response={"state": "identify_intent"},
    )

    assert replay == terminal_response
    assert voice.state == "completed"


async def test_handoff_is_idempotent_and_patient_role_is_forbidden(session, seeded):
    actor, patient = await _actor_and_patient(session)
    request = await session.get(AppointmentRequest, SEEDED_APPOINTMENT_REQUEST_ID)
    voice = await session.get(VoiceSession, request.voice_session_id)
    assert request is not None and voice is not None
    operation_id = uuid4()

    handed_off, callback = await handoff_appointment_request(
        session,
        actor=actor,
        patient=patient,
        request=request,
        operation_id=operation_id,
        contact_reference=f"contact:{actor.id}",
        reason_code="requested_by_caller",
        sla_due_at=utcnow() + timedelta(hours=2),
        voice_session=voice,
    )
    repeated, repeated_callback = await handoff_appointment_request(
        session,
        actor=actor,
        patient=patient,
        request=request,
        operation_id=operation_id,
        contact_reference=f"contact:{actor.id}",
        reason_code="requested_by_caller",
        sla_due_at=utcnow() + timedelta(hours=2),
        voice_session=voice,
    )
    assert handed_off.status == repeated.status == "human_handoff"
    assert callback.id == repeated_callback.id

    patient_user = await session.scalar(select(User).where(User.role == "patient"))
    assert patient_user is not None
    with pytest.raises(DomainError) as denied:
        await list_appointment_requests(session, actor=patient_user, patient=patient)
    assert denied.value.http_status == 403


async def test_operation_ids_are_unique_even_if_callers_bypass_services(session, seeded):
    first = await session.scalar(select(AppointmentRequest))
    assert first is not None
    duplicate = AppointmentRequest(
        patient_id=first.patient_id,
        requested_by=first.requested_by,
        request_kind="new",
        source="voice",
        status="draft",
        operation_id=first.operation_id,
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    # La restricción parcial también existe en PostgreSQL aunque el servicio
    # ya serializa sobre el slot. Esta aserción deja explícito el doble cierre.
    assert AppointmentHold.__table__.indexes
