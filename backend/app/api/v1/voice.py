"""API de Kinti Voz Fase 5A.

Los webhooks del proveedor están separados de los casos de uso autenticados.
La voz se procesa por turnos, nunca se graba, y la entrada pronunciada no se
persiste ni se registra en auditoría.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import date, timedelta
from functools import lru_cache
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from starlette.datastructures import FormData

from app.api.deps import AdultUser, CareTeamUser, SessionDep
from app.api.v1 import voice_schemas as schemas
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.core.time import utcnow
from app.modules.patients import service as patients_service
from app.modules.voice import persistence, policy
from app.modules.voice.fakes import (
    FakeReferralGateway,
    FakeSchedulingGateway,
    FakeVoiceAppointmentWorkflow,
    ManualReferralGateway,
    ManualSchedulingGateway,
)
from app.modules.voice.models import AppointmentRequest, ReferralCase, VoiceSession
from app.modules.voice.ports import RequestStatus, TurnInput, TurnOutput, VoiceState
from app.modules.voice.telephony import (
    InvalidTelephonySignature,
    TwilioTurnTelephonyGateway,
    validate_fake_webhook,
)

router = APIRouter(tags=["kinti-voz"])

_SIGNED_WEBHOOK_HEADERS = [
    {
        "in": "header",
        "name": "X-Twilio-Signature",
        "required": False,
        "schema": {"type": "string"},
        "description": "Obligatoria cuando el proveedor es Twilio.",
    },
    {
        "in": "header",
        "name": "X-Kinti-Signature",
        "required": False,
        "schema": {"type": "string"},
        "description": "HMAC-SHA256 obligatorio para el proveedor fake HTTP.",
    },
]


def _webhook_openapi(
    json_model: type[schemas.VoiceApiModel], form_properties: dict[str, Any]
) -> dict[str, Any]:
    return {
        "parameters": _SIGNED_WEBHOOK_HEADERS,
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": json_model.model_json_schema(by_alias=True)
                },
                "application/x-www-form-urlencoded": {
                    "schema": {"type": "object", "properties": form_properties}
                },
            },
        },
    }


class _MultiValueForm(dict[str, str | list[str]]):
    """Mapping compatible con RequestValidator sin descartar valores repetidos."""

    def getlist(self, key: str) -> list[str]:
        value = self[key]
        return [value] if isinstance(value, str) else list(value)

    getall = getlist


@lru_cache
def get_voice_workflow() -> FakeVoiceAppointmentWorkflow:
    """Runtime fake determinista; producción real permanece detrás del gate."""
    settings = get_settings()
    referrals = (
        ManualReferralGateway()
        if settings.referral_provider == "manual"
        else FakeReferralGateway()
    )
    scheduling = (
        ManualSchedulingGateway()
        if settings.scheduling_provider == "manual"
        else FakeSchedulingGateway()
    )
    return FakeVoiceAppointmentWorkflow(
        referrals=referrals,
        scheduling=scheduling,
        max_reprompts=settings.voice_max_reprompts,
    )


def _opaque(value: str, secret: str, *, namespace: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{namespace}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"hmac:{digest}"


def _event_key(value: str, secret: str, *, scope: str) -> str:
    return "event:" + hmac.new(
        secret.encode("utf-8"), f"{scope}:{value}".encode(), hashlib.sha256
    ).hexdigest()


def _form_values(form: FormData) -> _MultiValueForm:
    values = _MultiValueForm()
    for key in form:
        raw_values = form.getlist(key)
        if not all(isinstance(value, str) for value in raw_values):
            raise HTTPException(status_code=422, detail="Formulario telefónico no válido")
        strings = [str(value) for value in raw_values]
        values[key] = strings[0] if len(strings) == 1 else strings
    return values


def _first(form: _MultiValueForm, key: str) -> str:
    value = form.get(key, "")
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _turn_out(output: TurnOutput) -> schemas.VoiceTurnOut:
    return schemas.VoiceTurnOut(
        session_id=output.session_id,
        state=output.state.value,
        prompt=output.prompt,
        expects_input=output.expects_input,
        speech_rate=output.speech_rate,
        allowed_dtmf=list(output.allowed_dtmf),
        options=[
            schemas.PresentedOptionOut(
                number=option.number,
                slot_id=option.slot_id,
                spoken_text=option.spoken_text,
            )
            for option in output.options
        ],
        outcome=output.outcome.value if output.outcome else None,
    )


def _call_timed_out(voice_session: VoiceSession, settings: Settings) -> bool:
    return utcnow() - voice_session.started_at >= timedelta(
        seconds=settings.voice_max_call_seconds
    )


def _timeout_output(session_id: str) -> TurnOutput:
    return TurnOutput(
        session_id=session_id,
        state=VoiceState.HUMAN_HANDOFF,
        prompt=(
            "La llamada llegó a su tiempo máximo. "
            + policy.HUMAN_HANDOFF_MESSAGE
        ),
        expects_input=False,
        speech_rate="slow",
        outcome=RequestStatus.HUMAN_HANDOFF,
    )


def _recovery_handoff_output(session_id: str) -> TurnOutput:
    return TurnOutput(
        session_id=session_id,
        state=VoiceState.HUMAN_HANDOFF,
        prompt=(
            "No puedo retomar este turno con seguridad después de una interrupción. "
            + policy.HUMAN_HANDOFF_MESSAGE
        ),
        expects_input=False,
        speech_rate="slow",
        outcome=RequestStatus.HUMAN_HANDOFF,
    )


def _runtime_state_was_lost(
    voice_session: VoiceSession, output: TurnOutput
) -> bool:
    if voice_session.version <= 1:
        return False
    context = voice_session.context_json or {}
    return context.get("workflowSessionId") != output.session_id


def _terminal_output(voice_session: VoiceSession) -> TurnOutput:
    context = voice_session.context_json or {}
    session_id = str(context.get("workflowSessionId") or voice_session.id)
    if voice_session.state == "human_handoff":
        return TurnOutput(
            session_id=session_id,
            state=VoiceState.HUMAN_HANDOFF,
            prompt=policy.HUMAN_HANDOFF_MESSAGE,
            expects_input=False,
            speech_rate="slow",
            outcome=RequestStatus.HUMAN_HANDOFF,
        )
    return TurnOutput(
        session_id=session_id,
        state=VoiceState.COMPLETED,
        prompt="La llamada ha finalizado.",
        expects_input=False,
        speech_rate="slow",
    )


def _terminal_response(voice_session: VoiceSession) -> schemas.VoiceTurnOut:
    try:
        return schemas.VoiceTurnOut.model_validate(
            voice_session.last_response_json or {}
        )
    except ValidationError:
        return _turn_out(_terminal_output(voice_session))


async def _event_replay(
    session: SessionDep,
    *,
    voice_session: VoiceSession,
    event_type: str,
    event_key: str,
) -> schemas.VoiceTurnOut | None:
    response = await persistence.get_voice_event_response(
        session,
        voice_session=voice_session,
        event_type=event_type,
        event_key=event_key,
    )
    return schemas.VoiceTurnOut.model_validate(response) if response else None


async def _persist_turn(
    session: SessionDep,
    *,
    voice_session: VoiceSession,
    event_key: str,
    output: TurnOutput,
    event_type: str,
    transfer_reason: str | None = None,
) -> schemas.VoiceTurnOut:
    response = _turn_out(output)
    payload = response.model_dump(mode="json", by_alias=True)
    replay = await persistence.record_voice_event(
        session,
        voice_session=voice_session,
        event_key=event_key,
        next_state=output.state.value,
        response=payload,
        event_type=event_type,
        context={"workflowSessionId": output.session_id},
        transfer_reason=transfer_reason
        or ("workflow_handoff" if output.state.value == "human_handoff" else None),
        expected_version=voice_session.version,
    )
    return schemas.VoiceTurnOut.model_validate(replay)


async def _create_voice_callback(
    session: SessionDep,
    *,
    voice_session: VoiceSession,
    contact_reference: str,
    reason_code: str,
) -> None:
    await persistence.create_callback_request(
        session,
        # Una sesión sólo puede abrir un callback automático, aunque el
        # proveedor reintente turnos o el webhook de estado llegue después.
        operation_id=uuid5(
            NAMESPACE_URL, f"kinti:voice-session:{voice_session.id}:callback"
        ),
        contact_reference=contact_reference,
        reason_code=reason_code,
        sla_due_at=utcnow() + timedelta(hours=24),
        voice_session=voice_session,
    )


def _twilio_gateway(settings: Settings) -> TwilioTurnTelephonyGateway:
    return TwilioTurnTelephonyGateway(
        auth_token=settings.twilio_auth_token,
        webhook_base_url=settings.twilio_webhook_base_url,
        language=settings.voice_language,
    )


async def _twilio_form(request: Request, settings: Settings) -> _MultiValueForm:
    form = _form_values(await request.form())
    gateway = _twilio_gateway(settings)
    try:
        gateway.validate(
            path=request.url.path,
            query=request.url.query,
            form=form,
            signature=request.headers.get("X-Twilio-Signature"),
        )
    except InvalidTelephonySignature as exc:
        raise HTTPException(status_code=403, detail="Firma telefónica inválida") from exc
    return form


async def _fake_body(
    request: Request, settings: Settings, model: type[schemas.VoiceApiModel]
) -> tuple[bytes, schemas.VoiceApiModel]:
    raw = await request.body()
    try:
        validate_fake_webhook(
            body=raw,
            signature=request.headers.get("X-Kinti-Signature"),
            secret=settings.telephony_webhook_secret,
        )
    except InvalidTelephonySignature as exc:
        raise HTTPException(status_code=403, detail="Firma telefónica inválida") from exc
    try:
        return raw, model.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.post(
    "/voice/incoming",
    response_model=schemas.VoiceTurnOut,
    responses={
        200: {
            "description": "JSON fake o TwiML firmado",
            "content": {"application/xml": {"schema": {"type": "string"}}},
        }
    },
    openapi_extra=_webhook_openapi(
        schemas.VoiceIncomingJsonRequest,
        {
            "CallSid": {"type": "string"},
            "From": {"type": "string"},
        },
    ),
)
async def voice_incoming(request: Request, session: SessionDep) -> Any:
    """Inicia un turno firmado. Twilio recibe XML; el proveedor fake, JSON."""
    settings = get_settings()
    workflow = get_voice_workflow()
    try:
        if settings.telephony_provider == "twilio":
            form = await _twilio_form(request, settings)
            call_sid = _first(form, "CallSid")
            if not call_sid:
                raise HTTPException(status_code=422, detail="CallSid es obligatorio")
            provider_key = _opaque(call_sid, settings.twilio_auth_token, namespace="call")
            idempotency = request.headers.get("I-Twilio-Idempotency-Token") or (
                request.headers.get("X-Twilio-Signature") or call_sid
            )
            event_key = _event_key(
                idempotency,
                settings.twilio_auth_token,
                scope=f"{provider_key}:incoming",
            )
            output = await workflow.start(provider_session_id=provider_key)
            stored = await persistence.get_or_create_voice_session(
                session,
                provider="twilio",
                provider_call_key=provider_key,
                policy_version=policy.VOICE_POLICY_VERSION,
                language=settings.voice_language,
                speech_rate=settings.voice_default_speech_rate,
            )
            recovered = _runtime_state_was_lost(stored, output)
            if recovered:
                output = _recovery_handoff_output(output.session_id)
                event_key = _event_key(
                    str(stored.id),
                    settings.twilio_auth_token,
                    scope=f"{provider_key}:recovery",
                )
            response = await _persist_turn(
                session,
                voice_session=stored,
                event_key=event_key,
                output=output,
                event_type="recovery" if recovered else "incoming",
                transfer_reason="runtime_recovery" if recovered else None,
            )
            if recovered and settings.voice_callback_enabled:
                await _create_voice_callback(
                    session,
                    voice_session=stored,
                    contact_reference=provider_key,
                    reason_code="runtime_recovery",
                )
            await session.commit()
            return Response(
                _twilio_gateway(settings).render(response), media_type="application/xml"
            )

        raw, parsed = await _fake_body(
            request, settings, schemas.VoiceIncomingJsonRequest
        )
        assert isinstance(parsed, schemas.VoiceIncomingJsonRequest)
        provider_key = _opaque(
            parsed.provider_session_id,
            settings.telephony_webhook_secret,
            namespace="fake-call",
        )
        output = await workflow.start(provider_session_id=provider_key)
        stored = await persistence.get_or_create_voice_session(
            session,
            provider="fake",
            provider_call_key=provider_key,
            policy_version=policy.VOICE_POLICY_VERSION,
            language=settings.voice_language,
            speech_rate=settings.voice_default_speech_rate,
        )
        recovered = _runtime_state_was_lost(stored, output)
        event_key = _event_key(
            raw.hex(),
            settings.telephony_webhook_secret,
            scope=f"{provider_key}:incoming",
        )
        if recovered:
            output = _recovery_handoff_output(output.session_id)
            event_key = _event_key(
                str(stored.id),
                settings.telephony_webhook_secret,
                scope=f"{provider_key}:recovery",
            )
        response = await _persist_turn(
            session,
            voice_session=stored,
            event_key=event_key,
            output=output,
            event_type="recovery" if recovered else "incoming",
            transfer_reason="runtime_recovery" if recovered else None,
        )
        if recovered and settings.voice_callback_enabled:
            await _create_voice_callback(
                session,
                voice_session=stored,
                contact_reference=provider_key,
                reason_code="runtime_recovery",
            )
        await session.commit()
        return JSONResponse(response.model_dump(mode="json", by_alias=True))
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.post(
    "/voice/turn",
    response_model=schemas.VoiceTurnOut,
    responses={
        200: {
            "description": "JSON fake o TwiML firmado",
            "content": {"application/xml": {"schema": {"type": "string"}}},
        }
    },
    openapi_extra=_webhook_openapi(
        schemas.VoiceTurnJsonRequest,
        {
            "CallSid": {"type": "string"},
            "SpeechResult": {"type": "string", "maxLength": 500},
            "Digits": {"type": "string", "maxLength": 20},
        },
    ),
)
async def voice_turn(request: Request, session: SessionDep) -> Any:
    """Procesa voz o DTMF con la misma máquina, sin persistir lo pronunciado."""
    settings = get_settings()
    workflow = get_voice_workflow()
    try:
        if settings.telephony_provider == "twilio":
            form = await _twilio_form(request, settings)
            call_sid = _first(form, "CallSid")
            if not call_sid:
                raise HTTPException(status_code=422, detail="CallSid es obligatorio")
            provider_key = _opaque(call_sid, settings.twilio_auth_token, namespace="call")
            initial = await workflow.start(provider_session_id=provider_key)
            raw_input = _first(form, "Digits")
            modality = "dtmf" if raw_input else "speech"
            raw_input = raw_input or _first(form, "SpeechResult")
            if len(raw_input) > 500:
                raise HTTPException(status_code=422, detail="Turno demasiado largo")
            token = request.headers.get("I-Twilio-Idempotency-Token") or (
                request.headers.get("X-Twilio-Signature") or call_sid
            )
            event_key = _event_key(
                token,
                settings.twilio_auth_token,
                scope=f"{provider_key}:turn",
            )
            stored = await session.scalar(
                select(VoiceSession)
                .where(VoiceSession.provider_call_key == provider_key)
                .with_for_update()
            )
            if stored is None:
                raise HTTPException(status_code=404, detail="Sesión de voz no encontrada")
            replay = await _event_replay(
                session,
                voice_session=stored,
                event_type="turn",
                event_key=event_key,
            )
            if replay is not None:
                return Response(
                    _twilio_gateway(settings).render(replay),
                    media_type="application/xml",
                )
            if stored.state in {"completed", "human_handoff"}:
                return Response(
                    _twilio_gateway(settings).render(_terminal_response(stored)),
                    media_type="application/xml",
                )
            recovered = _runtime_state_was_lost(stored, initial)
            output = (
                _recovery_handoff_output(initial.session_id)
                if recovered
                else _timeout_output(initial.session_id)
                if _call_timed_out(stored, settings)
                else await workflow.handle_turn(
                    session_id=initial.session_id,
                    event_id=event_key,
                    turn=TurnInput(modality=modality, value=raw_input),
                )
            )
            response = await _persist_turn(
                session,
                voice_session=stored,
                event_key=event_key,
                output=output,
                event_type="recovery" if recovered else "turn",
                transfer_reason="runtime_recovery" if recovered else None,
            )
            if output.state.value == "human_handoff" and settings.voice_callback_enabled:
                contact = _opaque(
                    _first(form, "From") or call_sid,
                    settings.twilio_auth_token,
                    namespace="contact",
                )
                await _create_voice_callback(
                    session,
                    voice_session=stored,
                    contact_reference=contact,
                    reason_code="runtime_recovery" if recovered else "workflow_handoff",
                )
            await session.commit()
            return Response(
                _twilio_gateway(settings).render(response), media_type="application/xml"
            )

        _, parsed = await _fake_body(request, settings, schemas.VoiceTurnJsonRequest)
        assert isinstance(parsed, schemas.VoiceTurnJsonRequest)
        workflow_session_id = str(parsed.session_id)
        try:
            runtime_session = workflow.get_session(workflow_session_id)
        except KeyError:
            runtime_session = None
        if runtime_session is None:
            stored = await persistence.get_voice_session_by_workflow_id(
                session, workflow_session_id=workflow_session_id
            )
        else:
            stored = await session.scalar(
                select(VoiceSession)
                .where(
                    VoiceSession.provider_call_key
                    == runtime_session.provider_session_id
                )
                .with_for_update()
            )
        if stored is None:
            raise HTTPException(status_code=404, detail="Sesión de voz no encontrada")
        event_key = _event_key(
            parsed.event_id,
            settings.telephony_webhook_secret,
            scope=f"{stored.provider_call_key}:turn",
        )
        replay = await _event_replay(
            session,
            voice_session=stored,
            event_type="turn",
            event_key=event_key,
        )
        if replay is not None:
            return JSONResponse(replay.model_dump(mode="json", by_alias=True))
        if stored.state in {"completed", "human_handoff"}:
            response = _terminal_response(stored)
            return JSONResponse(response.model_dump(mode="json", by_alias=True))
        recovered = runtime_session is None
        output = (
            _recovery_handoff_output(workflow_session_id)
            if recovered
            else _timeout_output(workflow_session_id)
            if _call_timed_out(stored, settings)
            else await workflow.handle_turn(
                session_id=workflow_session_id,
                event_id=event_key,
                turn=TurnInput(modality=parsed.modality, value=parsed.value),
            )
        )
        response = await _persist_turn(
            session,
            voice_session=stored,
            event_key=event_key,
            output=output,
            event_type="recovery" if recovered else "turn",
            transfer_reason="runtime_recovery" if recovered else None,
        )
        if output.state.value == "human_handoff" and settings.voice_callback_enabled:
            await _create_voice_callback(
                session,
                voice_session=stored,
                contact_reference=stored.provider_call_key,
                reason_code="runtime_recovery" if recovered else "workflow_handoff",
            )
        await session.commit()
        return JSONResponse(response.model_dump(mode="json", by_alias=True))
    except KeyError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.post(
    "/voice/status",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra=_webhook_openapi(
        schemas.VoiceStatusJsonRequest,
        {
            "CallSid": {"type": "string"},
            "CallStatus": {"type": "string"},
            "From": {"type": "string"},
        },
    ),
)
async def voice_status(request: Request, session: SessionDep) -> Response:
    """Registra estado estructurado; un fallo abre callback, nunca una cita."""
    settings = get_settings()
    try:
        if settings.telephony_provider == "twilio":
            form = await _twilio_form(request, settings)
            call_sid = _first(form, "CallSid")
            provider_key = _opaque(call_sid, settings.twilio_auth_token, namespace="call")
            reported = _first(form, "CallStatus")
            token = request.headers.get("I-Twilio-Idempotency-Token") or (
                request.headers.get("X-Twilio-Signature") or f"{call_sid}:{reported}"
            )
            secret = settings.twilio_auth_token
            contact = _opaque(
                _first(form, "From") or call_sid, secret, namespace="contact"
            )
        else:
            raw, parsed = await _fake_body(
                request, settings, schemas.VoiceStatusJsonRequest
            )
            assert isinstance(parsed, schemas.VoiceStatusJsonRequest)
            provider_key = _opaque(
                parsed.provider_session_id,
                settings.telephony_webhook_secret,
                namespace="fake-call",
            )
            reported = parsed.status
            token = parsed.event_id
            secret = settings.telephony_webhook_secret
            contact = provider_key

        stored = await session.scalar(
            select(VoiceSession)
            .where(VoiceSession.provider_call_key == provider_key)
            .with_for_update()
        )
        if stored is None:
            raise HTTPException(status_code=404, detail="Sesión de voz no encontrada")
        event_key = _event_key(token, secret, scope=f"{provider_key}:status")
        terminal = reported in {"completed", "failed", "canceled", "busy", "no-answer"}
        failed = reported in {"failed", "canceled", "busy", "no-answer"}
        if terminal:
            context = stored.context_json or {}
            workflow_session_id = str(
                context.get("workflowSessionId") or stored.id
            )
            output = TurnOutput(
                session_id=workflow_session_id,
                state=VoiceState.HUMAN_HANDOFF if failed else VoiceState.COMPLETED,
                prompt=(
                    policy.HUMAN_HANDOFF_MESSAGE
                    if failed
                    else "La llamada ha finalizado."
                ),
                expects_input=False,
                speech_rate="slow",
                outcome=RequestStatus.HUMAN_HANDOFF if failed else None,
            )
            await _persist_turn(
                session,
                voice_session=stored,
                event_key=event_key,
                output=output,
                event_type="status",
                transfer_reason="provider_failed" if failed else None,
            )
        if failed and settings.voice_callback_enabled:
            await _create_voice_callback(
                session,
                voice_session=stored,
                contact_reference=contact,
                reason_code="provider_failed",
            )
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.get("/service-hours", response_model=list[schemas.ServiceHourOut])
async def service_hours(
    user: AdultUser,
    session: SessionDep,
    service: str | None = None,
    site: str | None = None,
    weekday: int | None = Query(default=None, ge=0, le=6),
    active_on: date | None = Query(default=None, alias="activeOn"),
) -> list[schemas.ServiceHourOut]:
    del user
    try:
        rows = await persistence.list_service_hours(
            session,
            service=service,
            site=site,
            weekday=weekday,
            active_on=active_on,
        )
        return [schemas.ServiceHourOut.model_validate(row) for row in rows]
    except DomainError as exc:
        raise exc.as_http() from exc


def _referral_out(referral: ReferralCase) -> schemas.ReferralOut:
    return schemas.ReferralOut(
        id=referral.id,
        patient_id=referral.patient_id,
        origin_facility=referral.origin_facility,
        origin_region=referral.origin_region,
        origin_province=referral.origin_province,
        requested_specialty=referral.requested_specialty,
        status=referral.status,
        missing_requirements=list(referral.missing_requirements or []),
        last_synced_at=referral.last_synced_at,
        source=referral.source,
        updated_at=referral.updated_at,
    )


@router.get("/referrals/{referral_id}", response_model=schemas.ReferralOut)
async def get_referral(
    referral_id: UUID, user: AdultUser, session: SessionDep
) -> schemas.ReferralOut:
    try:
        row = await session.scalar(select(ReferralCase).where(ReferralCase.id == referral_id))
        if row is None:
            raise DomainError("not_found", "Referencia no encontrada", 404)
        try:
            patient = await patients_service.require_patient_access(
                session, user, row.patient_id
            )
        except DomainError as exc:
            raise DomainError("not_found", "Referencia no encontrada", 404) from exc
        referral = await persistence.get_referral(
            session, referral_id=referral_id, patient=patient
        )
        return _referral_out(referral)
    except DomainError as exc:
        raise exc.as_http() from exc


@router.post("/referrals/lookup", response_model=schemas.ReferralOut)
async def lookup_referral(
    body: schemas.ReferralLookupRequest, user: AdultUser, session: SessionDep
) -> schemas.ReferralOut:
    try:
        patient = await patients_service.require_patient_access(
            session, user, body.patient_id
        )
        referral = await persistence.lookup_referral(
            session,
            patient=patient,
            origin_facility=body.origin_facility,
            origin_region=body.origin_region,
            origin_province=body.origin_province,
            external_identifier=body.external_identifier,
        )
        if referral is None:
            raise DomainError("not_found", "Referencia no encontrada", 404)
        return _referral_out(referral)
    except DomainError as exc:
        raise exc.as_http() from exc


async def _authorized_request(
    session: SessionDep, user: AdultUser, request_id: UUID
) -> tuple[Any, AppointmentRequest]:
    row = await session.scalar(
        select(AppointmentRequest).where(AppointmentRequest.id == request_id)
    )
    if row is None:
        raise DomainError("not_found", "Solicitud de cita no encontrada", 404)
    try:
        patient = await patients_service.require_patient_access(session, user, row.patient_id)
        stored = await persistence.get_appointment_request(
            session, actor=user, patient=patient, request_id=request_id
        )
    except DomainError as exc:
        if exc.code == "not_found":
            raise DomainError("not_found", "Solicitud de cita no encontrada", 404) from exc
        raise
    return patient, stored


@router.post(
    "/appointment-requests",
    response_model=schemas.AppointmentRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment_request(
    body: schemas.AppointmentRequestCreate, user: AdultUser, session: SessionDep
) -> schemas.AppointmentRequestOut:
    try:
        patient = await patients_service.require_patient_access(
            session, user, body.patient_id
        )
        referral = None
        if body.referral_id:
            referral = await persistence.get_referral(
                session, referral_id=body.referral_id, patient=patient
            )
        request_row = await persistence.create_appointment_request(
            session,
            actor=user,
            patient=patient,
            operation_id=body.operation_id,
            source="staff" if user.role == "care_team" else "app",
            request_kind=body.request_kind,
            referral=referral,
            origin_region=body.origin_region,
            origin_province=body.origin_province,
            arrival_window_start=body.arrival_window_start,
            arrival_window_end=body.arrival_window_end,
            return_deadline=body.return_deadline,
            travel_minutes=body.travel_minutes,
            needs_lodging=body.needs_lodging,
            needs_transport=body.needs_transport,
            can_stay_more_than_one_day=body.can_stay_more_than_one_day,
        )
        await session.commit()
        await session.refresh(request_row)
        return schemas.AppointmentRequestOut.model_validate(request_row)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.get("/appointment-requests", response_model=list[schemas.AppointmentRequestOut])
async def list_appointment_requests(
    user: AdultUser,
    session: SessionDep,
    patient_id: UUID = Query(alias="patientId"),
    request_status: list[str] | None = Query(default=None, alias="status"),
) -> list[schemas.AppointmentRequestOut]:
    try:
        patient = await patients_service.require_patient_access(session, user, patient_id)
        rows = await persistence.list_appointment_requests(
            session, actor=user, patient=patient, statuses=request_status
        )
        return [schemas.AppointmentRequestOut.model_validate(row) for row in rows]
    except DomainError as exc:
        raise exc.as_http() from exc


@router.get(
    "/appointment-requests/{request_id}", response_model=schemas.AppointmentRequestOut
)
async def get_appointment_request(
    request_id: UUID, user: AdultUser, session: SessionDep
) -> schemas.AppointmentRequestOut:
    try:
        _, row = await _authorized_request(session, user, request_id)
        return schemas.AppointmentRequestOut.model_validate(row)
    except DomainError as exc:
        raise exc.as_http() from exc


@router.post(
    "/appointment-requests/{request_id}/proposals",
    response_model=schemas.AppointmentProposalsOut,
)
async def propose_appointment_slots(
    request_id: UUID,
    body: schemas.AppointmentProposalRequest,
    user: AdultUser,
    session: SessionDep,
) -> schemas.AppointmentProposalsOut:
    try:
        _, row = await _authorized_request(session, user, request_id)
        options = await persistence.prepare_slot_proposals(
            session,
            actor=user,
            request=row,
            operation_id=body.operation_id,
            limit=body.max_options,
        )
        await session.commit()
        await session.refresh(row)
        return schemas.AppointmentProposalsOut(
            request=schemas.AppointmentRequestOut.model_validate(row),
            options=[schemas.AppointmentSlotOut.model_validate(slot) for slot in options],
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.post(
    "/appointment-requests/{request_id}/confirm",
    response_model=schemas.AppointmentConfirmationOut,
)
async def confirm_appointment_request(
    request_id: UUID,
    body: schemas.AppointmentConfirmRequest,
    user: AdultUser,
    session: SessionDep,
) -> schemas.AppointmentConfirmationOut:
    try:
        _, row = await _authorized_request(session, user, request_id)
        hold = await persistence.hold_slot(
            session,
            actor=user,
            request=row,
            slot_id=body.selected_slot_id,
            operation_id=body.operation_id,
            expected_availability_version=body.expected_availability_version,
        )
        # Un retry posterior al commit encuentra el mismo hold ya consumido.
        # Eso es éxito idempotente, no un cambio de disponibilidad.
        if (
            hold.status == "consumed"
            and row.submission_operation_id == body.operation_id
            and row.status in {"submitted", "confirmed"}
        ):
            return schemas.AppointmentConfirmationOut(
                request=schemas.AppointmentRequestOut.model_validate(row),
                hold=schemas.AppointmentHoldOut.model_validate(hold),
                outcome="confirmed" if row.status == "confirmed" else "submitted",
            )
        if not await persistence.revalidate_hold(
            session, actor=user, hold_id=hold.id
        ):
            await session.commit()
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "availability_changed",
                    "message": "La alternativa cambió; consulte nuevas propuestas",
                },
            )
        submitted = await persistence.submit_manual_request(
            session,
            actor=user,
            hold_id=hold.id,
            operation_id=body.operation_id,
        )
        await session.commit()
        await session.refresh(submitted)
        await session.refresh(hold)
        return schemas.AppointmentConfirmationOut(
            request=schemas.AppointmentRequestOut.model_validate(submitted),
            hold=schemas.AppointmentHoldOut.model_validate(hold),
            outcome="submitted",
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.post(
    "/appointment-requests/{request_id}/human-handoff",
    response_model=schemas.HumanHandoffOut,
)
async def handoff_appointment_request(
    request_id: UUID,
    body: schemas.HumanHandoffRequest,
    user: AdultUser,
    session: SessionDep,
) -> schemas.HumanHandoffOut:
    try:
        patient, row = await _authorized_request(session, user, request_id)
        updated, callback = await persistence.handoff_appointment_request(
            session,
            actor=user,
            patient=patient,
            request=row,
            operation_id=body.operation_id,
            contact_reference=body.contact_reference,
            reason_code=body.reason_code,
            sla_due_at=utcnow() + timedelta(hours=24),
        )
        await session.commit()
        await session.refresh(updated)
        await session.refresh(callback)
        return schemas.HumanHandoffOut(
            request=schemas.AppointmentRequestOut.model_validate(updated),
            callback=schemas.CallbackOut.model_validate(callback),
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.post(
    "/voice/callback-requests",
    response_model=schemas.CallbackOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_callback_request(
    body: schemas.CallbackCreateRequest, user: AdultUser, session: SessionDep
) -> schemas.CallbackOut:
    try:
        patient = None
        if body.patient_id:
            patient = await patients_service.require_patient_access(
                session, user, body.patient_id
            )
        voice_session = None
        if body.voice_session_id:
            try:
                voice_session = await persistence.get_voice_session(
                    session, session_id=body.voice_session_id, actor=user
                )
                if voice_session.patient_id:
                    linked_patient = await patients_service.require_patient_access(
                        session, user, voice_session.patient_id
                    )
                    if patient is not None and patient.id != linked_patient.id:
                        raise DomainError(
                            "not_found", "Sesión de voz no encontrada", 404
                        )
                    patient = linked_patient
            except DomainError as exc:
                if exc.code == "not_found":
                    raise DomainError(
                        "not_found", "Sesión de voz no encontrada", 404
                    ) from exc
                raise
        if patient is None:
            raise DomainError(
                "patient_required",
                "El callback autenticado requiere un paciente autorizado",
                422,
            )
        callback = await persistence.create_callback_request(
            session,
            operation_id=body.operation_id,
            contact_reference=body.contact_reference,
            reason_code=body.reason_code,
            sla_due_at=utcnow() + timedelta(hours=24),
            actor=user,
            patient=patient,
            voice_session=voice_session,
        )
        await session.commit()
        await session.refresh(callback)
        return schemas.CallbackOut.model_validate(callback)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc


@router.get("/voice/callback-requests", response_model=list[schemas.CallbackOut])
async def list_callback_requests(
    user: CareTeamUser,
    session: SessionDep,
    patient_id: UUID | None = Query(default=None, alias="patientId"),
    callback_status: list[str] | None = Query(default=None, alias="status"),
    include_unverified: bool = Query(
        default=False,
        alias="includeUnverified",
        description=(
            "Reservado para una futura mesa central con autorización explícita"
        ),
    ),
) -> list[schemas.CallbackOut]:
    try:
        if include_unverified:
            raise DomainError(
                "central_intake_not_configured",
                "La cola central no verificada no está habilitada",
                403,
            )
        if patient_id:
            await patients_service.require_patient_access(session, user, patient_id)
            allowed_patient_ids = [patient_id]
        else:
            allowed_patient_ids = await patients_service.authorized_patient_ids(
                session, user
            )
        rows = await persistence.list_callback_requests(
            session,
            actor=user,
            patient_ids=allowed_patient_ids,
            statuses=callback_status,
            include_unverified=include_unverified,
        )
        return [schemas.CallbackOut.model_validate(row) for row in rows]
    except DomainError as exc:
        raise exc.as_http() from exc


@router.get("/voice/sessions/{session_id}", response_model=schemas.VoiceSessionOut)
async def get_voice_session(
    session_id: UUID, user: AdultUser, session: SessionDep
) -> schemas.VoiceSessionOut:
    try:
        row = await persistence.get_voice_session(
            session, session_id=session_id, actor=user
        )
        if row.patient_id:
            try:
                await patients_service.require_patient_access(session, user, row.patient_id)
            except DomainError as exc:
                raise DomainError(
                    "not_found", "Sesión de voz no encontrada", 404
                ) from exc
        elif user.role != "care_team":
            raise DomainError("not_found", "Sesión de voz no encontrada", 404)
        return schemas.VoiceSessionOut.model_validate(row)
    except DomainError as exc:
        raise exc.as_http() from exc
