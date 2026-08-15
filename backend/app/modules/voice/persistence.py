"""Casos de uso persistentes y deterministas de Kinti Voz Fase 5A.

El módulo no depende de telefonía, STT, TTS ni de un modelo generativo. Los
adaptadores entregan resultados canónicos y esta capa aplica idempotencia,
vigencia, autorización adulta y concurrencia sobre PostgreSQL.
"""

import hashlib
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError, forbidden, invalid, not_found
from app.core.time import utcnow
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.patients.models import Patient
from app.modules.voice.models import (
    APPOINTMENT_REQUEST_KINDS,
    APPOINTMENT_REQUEST_SOURCES,
    APPOINTMENT_SLOT_STATUSES,
    CALLBACK_REASON_CODES,
    CALLBACK_REQUEST_STATUSES,
    REFERRAL_STATUSES,
    SERVICE_HOUR_STATUSES,
    VOICE_EVENT_TYPES,
    VOICE_SESSION_STATES,
    AppointmentHold,
    AppointmentRequest,
    AppointmentSlot,
    CallbackRequest,
    ReferralCase,
    ServiceHour,
    VoiceEvent,
    VoiceSession,
)

_SENSITIVE_STRUCTURED_KEYS = {
    "audio",
    "audio_bytes",
    "caller_id",
    "dni",
    "document_number",
    "full_name",
    "phone",
    "phone_number",
    "recording",
    "recording_url",
    "transcript",
}


def _require_adult(actor: User | None) -> None:
    if actor is not None and actor.role == "patient":
        raise forbidden("El espacio del paciente no organiza referencias ni citas")
    if actor is not None and actor.role not in {"caregiver", "care_team"}:
        raise forbidden()


def _require_choice(value: str, choices: tuple[str, ...], field: str) -> None:
    if value not in choices:
        raise invalid(f"invalid_{field}", f"Valor no válido para {field}")


def _assert_safe_structure(value: Any) -> None:
    """Impide que los JSON durables se conviertan en transcripciones o PII."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() in _SENSITIVE_STRUCTURED_KEYS:
                raise invalid(
                    "sensitive_voice_payload", "El estado de voz contiene datos sensibles"
                )
            _assert_safe_structure(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_safe_structure(nested)


def _assert_opaque_contact(contact_reference: str) -> tuple[str, str]:
    value = contact_reference.strip()
    try:
        kind, token = value.split(":", 1)
    except ValueError:
        kind, token = "", ""

    valid = False
    if kind in {"contact", "user"}:
        try:
            UUID(token)
            valid = True
        except ValueError:
            pass
    elif kind == "hmac":
        valid = re.fullmatch(r"[0-9a-f]{64}", token) is not None
    elif kind == "vault":
        valid = re.fullmatch(r"[A-Za-z0-9_-]{16,200}", token) is not None

    if not valid or len(value) > 255:
        raise invalid(
            "opaque_contact_required",
            "El callback requiere una referencia opaca, no un teléfono crudo",
        )
    return kind, token


async def list_service_hours(
    session: AsyncSession,
    *,
    service: str | None = None,
    site: str | None = None,
    weekday: int | None = None,
    active_on: date | None = None,
) -> list[ServiceHour]:
    """Lista horarios publicados y vigentes; nunca infiere que exista cupo."""
    current = active_on or utcnow().date()
    query = select(ServiceHour).where(
        ServiceHour.status == "published",
        ServiceHour.valid_from <= current,
        or_(ServiceHour.valid_until.is_(None), ServiceHour.valid_until >= current),
    )
    if service is not None:
        query = query.where(func.lower(ServiceHour.service) == service.strip().lower())
    if site is not None:
        query = query.where(func.lower(ServiceHour.site) == site.strip().lower())
    if weekday is not None:
        if weekday < 0 or weekday > 6:
            raise invalid("invalid_weekday", "El día de semana debe estar entre 0 y 6")
        query = query.where(ServiceHour.weekday == weekday)
    rows = await session.scalars(
        query.order_by(ServiceHour.service, ServiceHour.weekday, ServiceHour.opens_at)
    )
    return list(rows)


async def get_referral(
    session: AsyncSession, *, referral_id: UUID, patient: Patient
) -> ReferralCase:
    """Un UUID ajeno responde como inexistente para impedir enumeración."""
    referral = await session.scalar(
        select(ReferralCase).where(
            ReferralCase.id == referral_id,
            ReferralCase.patient_id == patient.id,
        )
    )
    if referral is None:
        raise not_found("Referencia no encontrada")
    return referral


async def lookup_referral(
    session: AsyncSession,
    *,
    patient: Patient,
    origin_facility: str | None = None,
    origin_region: str | None = None,
    origin_province: str | None = None,
    external_identifier: str | None = None,
) -> ReferralCase | None:
    """Busca dentro de un paciente ya verificado y no devuelve coincidencias ambiguas."""
    has_origin = bool(origin_facility) or bool(origin_region and origin_province)
    if not external_identifier and not has_origin:
        raise invalid(
            "referral_lookup_evidence_required",
            "La búsqueda necesita establecimiento, región/provincia o identificador",
        )

    query = select(ReferralCase).where(ReferralCase.patient_id == patient.id)
    if external_identifier:
        query = query.where(ReferralCase.external_identifier == external_identifier.strip())
    if origin_facility:
        query = query.where(
            func.lower(ReferralCase.origin_facility) == origin_facility.strip().lower()
        )
    if origin_region:
        query = query.where(
            func.lower(ReferralCase.origin_region) == origin_region.strip().lower()
        )
    if origin_province:
        query = query.where(
            func.lower(ReferralCase.origin_province) == origin_province.strip().lower()
        )

    rows = list(await session.scalars(query.order_by(ReferralCase.created_at).limit(2)))
    return rows[0] if len(rows) == 1 else None


async def create_appointment_request(
    session: AsyncSession,
    *,
    actor: User,
    patient: Patient,
    operation_id: UUID,
    source: str,
    request_kind: str = "new",
    referral: ReferralCase | None = None,
    voice_session: VoiceSession | None = None,
    required_equivalence_group: str | None = None,
    origin_region: str | None = None,
    origin_province: str | None = None,
    arrival_window_start: datetime | None = None,
    arrival_window_end: datetime | None = None,
    return_deadline: datetime | None = None,
    travel_minutes: int | None = None,
    needs_lodging: bool = False,
    needs_transport: bool = False,
    can_stay_more_than_one_day: bool = False,
) -> AppointmentRequest:
    _require_adult(actor)
    _require_choice(source, APPOINTMENT_REQUEST_SOURCES, "source")
    _require_choice(request_kind, APPOINTMENT_REQUEST_KINDS, "request_kind")

    existing = await session.scalar(
        select(AppointmentRequest).where(AppointmentRequest.operation_id == operation_id)
    )
    if existing is not None:
        if existing.patient_id != patient.id or existing.requested_by != actor.id:
            raise invalid("operation_conflict", "La operación pertenece a otra solicitud")
        return existing

    if referral is not None and referral.patient_id != patient.id:
        raise not_found("Referencia no encontrada")
    if voice_session is not None and voice_session.patient_id not in {None, patient.id}:
        raise not_found("Sesión de voz no encontrada")
    if (
        arrival_window_start
        and arrival_window_end
        and arrival_window_end < arrival_window_start
    ):
        raise invalid("invalid_arrival_window", "La ventana de llegada no es válida")
    if (
        arrival_window_start
        and return_deadline
        and return_deadline <= arrival_window_start
    ):
        raise invalid("invalid_return_deadline", "El retorno debe ser posterior a la llegada")
    if travel_minutes is not None and travel_minutes < 0:
        raise invalid("invalid_travel_minutes", "El tiempo de viaje no puede ser negativo")

    request = AppointmentRequest(
        patient_id=patient.id,
        requested_by=actor.id,
        referral_id=referral.id if referral else None,
        voice_session_id=voice_session.id if voice_session else None,
        request_kind=request_kind,
        source=source,
        status="draft",
        operation_id=operation_id,
        required_equivalence_group=required_equivalence_group,
        origin_region=origin_region,
        origin_province=origin_province,
        arrival_window_start=arrival_window_start,
        arrival_window_end=arrival_window_end,
        return_deadline=return_deadline,
        travel_minutes=travel_minutes,
        needs_lodging=needs_lodging,
        needs_transport=needs_transport,
        can_stay_more_than_one_day=can_stay_more_than_one_day,
    )
    try:
        async with session.begin_nested():
            session.add(request)
            await session.flush()
    except IntegrityError:
        concurrent = await session.scalar(
            select(AppointmentRequest).where(
                AppointmentRequest.operation_id == operation_id
            )
        )
        if concurrent is None:
            raise
        if concurrent.patient_id != patient.id or concurrent.requested_by != actor.id:
            raise invalid(
                "operation_conflict", "La operación pertenece a otra solicitud"
            ) from None
        return concurrent
    await audit.record_event(
        session,
        actor_id=actor.id,
        action="create_appointment_request",
        entity_type="appointment_request",
        entity_id=request.id,
        metadata={
            "patient_id": patient.id,
            "source": source,
            "request_kind": request_kind,
        },
    )
    return request


async def list_appointment_requests(
    session: AsyncSession,
    *,
    actor: User,
    patient: Patient,
    statuses: Sequence[str] | None = None,
) -> list[AppointmentRequest]:
    _require_adult(actor)
    query = select(AppointmentRequest).where(AppointmentRequest.patient_id == patient.id)
    if statuses:
        unknown = set(statuses) - {
            "draft",
            "proposal_ready",
            "awaiting_confirmation",
            "submitted",
            "confirmed",
            "rejected",
            "expired",
            "human_handoff",
        }
        if unknown:
            raise invalid("invalid_request_status", "Estado de solicitud no válido")
        query = query.where(AppointmentRequest.status.in_(statuses))
    rows = await session.scalars(query.order_by(AppointmentRequest.created_at.desc()))
    return list(rows)


async def get_appointment_request(
    session: AsyncSession,
    *,
    actor: User,
    patient: Patient,
    request_id: UUID,
) -> AppointmentRequest:
    _require_adult(actor)
    request = await session.scalar(
        select(AppointmentRequest).where(
            AppointmentRequest.id == request_id,
            AppointmentRequest.patient_id == patient.id,
        )
    )
    if request is None:
        raise not_found("Solicitud de cita no encontrada")
    return request


async def list_slot_proposals(
    session: AsyncSession,
    *,
    request: AppointmentRequest,
    now: datetime | None = None,
    limit: int = 2,
) -> list[AppointmentSlot]:
    """Devuelve como máximo dos alternativas vigentes; no crea una reserva."""
    if limit <= 0:
        return []
    current = now or utcnow()

    if request.referral_id is None:
        raise invalid("referral_required", "La solicitud todavía no tiene referencia")
    referral = await session.get(ReferralCase, request.referral_id)
    if referral is None or referral.patient_id != request.patient_id:
        raise not_found("Referencia no encontrada")
    if referral.status != "approved":
        raise invalid(
            "referral_not_approved",
            "La referencia aún no permite ofrecer alternativas de cita",
        )

    active_hold = (
        select(AppointmentHold.id)
        .where(
            AppointmentHold.slot_id == AppointmentSlot.id,
            AppointmentHold.status == "held",
            AppointmentHold.expires_at > current,
        )
        .exists()
    )
    query = select(AppointmentSlot).where(
        AppointmentSlot.service == referral.requested_specialty,
        AppointmentSlot.status == "available",
        AppointmentSlot.available_places > 0,
        AppointmentSlot.starts_at > current,
        or_(AppointmentSlot.expires_at.is_(None), AppointmentSlot.expires_at > current),
        ~active_hold,
    )
    if request.required_equivalence_group:
        query = query.where(
            AppointmentSlot.equivalence_group == request.required_equivalence_group
        )
    if request.arrival_window_end:
        query = query.where(AppointmentSlot.starts_at >= request.arrival_window_end)
    elif request.arrival_window_start:
        query = query.where(AppointmentSlot.starts_at >= request.arrival_window_start)
    if request.return_deadline:
        query = query.where(AppointmentSlot.ends_at <= request.return_deadline)

    rows = await session.scalars(
        query.order_by(AppointmentSlot.starts_at, AppointmentSlot.professional_key).limit(
            min(limit, 2)
        )
    )
    return list(rows)


async def prepare_slot_proposals(
    session: AsyncSession,
    *,
    actor: User,
    request: AppointmentRequest,
    operation_id: UUID,
    now: datetime | None = None,
    limit: int = 2,
) -> list[AppointmentSlot]:
    """Persiste el resultado de POST proposals y lo repite por `operation_id`."""
    _require_adult(actor)
    current = now or utcnow()
    locked = await session.scalar(
        select(AppointmentRequest)
        .where(AppointmentRequest.id == request.id)
        .with_for_update()
    )
    if locked is None:
        raise not_found("Solicitud de cita no encontrada")

    if locked.proposal_operation_id == operation_id:
        slots_by_id = {
            str(slot.id): slot
            for slot in await session.scalars(
                select(AppointmentSlot).where(
                    AppointmentSlot.id.in_(
                        [UUID(value) for value in (locked.proposal_slot_ids or [])]
                    )
                )
            )
        }
        return [
            slots_by_id[value]
            for value in (locked.proposal_slot_ids or [])
            if value in slots_by_id
        ]

    proposals = await list_slot_proposals(
        session, request=locked, now=current, limit=limit
    )
    if not proposals:
        locked.status = "human_handoff"
        locked.proposal_slot_ids = []
        locked.proposal_operation_id = operation_id
        locked.proposal_expires_at = None
        locked.version += 1
        locked.updated_at = current
        await session.flush()
        await audit.record_event(
            session,
            actor_id=actor.id,
            action="prepare_appointment_proposals",
            entity_type="appointment_request",
            entity_id=locked.id,
            metadata={
                "patient_id": locked.patient_id,
                "options_count": 0,
                "result": "human_handoff",
            },
        )
        return []

    expiry_candidates = [current + timedelta(minutes=15)]
    expiry_candidates.extend(slot.starts_at for slot in proposals)
    expiry_candidates.extend(slot.expires_at for slot in proposals if slot.expires_at)
    locked.status = "proposal_ready"
    locked.proposal_slot_ids = [str(slot.id) for slot in proposals]
    locked.proposal_operation_id = operation_id
    locked.proposal_expires_at = min(expiry_candidates)
    locked.version += 1
    locked.updated_at = current
    await session.flush()
    await audit.record_event(
        session,
        actor_id=actor.id,
        action="prepare_appointment_proposals",
        entity_type="appointment_request",
        entity_id=locked.id,
        metadata={
            "patient_id": locked.patient_id,
            "options_count": len(proposals),
            "result": "proposal_ready",
        },
    )
    return proposals


def _slot_is_valid(slot: AppointmentSlot, *, now: datetime) -> bool:
    return (
        slot.status == "available"
        and slot.available_places > 0
        and slot.starts_at > now
        and (slot.expires_at is None or slot.expires_at > now)
    )


async def hold_slot(
    session: AsyncSession,
    *,
    actor: User,
    request: AppointmentRequest,
    slot_id: UUID,
    operation_id: UUID,
    expected_availability_version: int,
    now: datetime | None = None,
    hold_minutes: int = 15,
) -> AppointmentHold:
    """Toma el slot bajo lock; dos solicitudes concurrentes no pueden retenerlo."""
    _require_adult(actor)
    if hold_minutes <= 0:
        raise invalid("invalid_hold_duration", "La retención debe tener duración positiva")
    current = now or utcnow()

    existing = await session.scalar(
        select(AppointmentHold).where(AppointmentHold.operation_id == operation_id)
    )
    if existing is not None:
        if existing.request_id != request.id or existing.slot_id != slot_id:
            raise invalid("operation_conflict", "La operación pertenece a otra retención")
        return existing

    locked_request = await session.scalar(
        select(AppointmentRequest)
        .where(AppointmentRequest.id == request.id)
        .with_for_update()
    )
    if locked_request is None:
        raise not_found("Solicitud de cita no encontrada")
    if locked_request.status != "proposal_ready":
        raise invalid(
            "proposal_required",
            "La solicitud necesita una propuesta vigente antes de confirmar",
        )
    if (
        not locked_request.proposal_slot_ids
        or locked_request.proposal_expires_at is None
        or locked_request.proposal_expires_at <= current
    ):
        raise invalid("proposal_expired", "La propuesta venció; debe consultar de nuevo")

    slot = await session.scalar(
        select(AppointmentSlot).where(AppointmentSlot.id == slot_id).with_for_update()
    )
    if slot is None or not _slot_is_valid(slot, now=current):
        raise invalid("slot_unavailable", "La alternativa ya no está disponible")
    if slot.availability_version != expected_availability_version:
        raise DomainError(
            "availability_changed",
            "La disponibilidad cambió; debe consultar las alternativas de nuevo",
            409,
        )
    if str(slot.id) not in locked_request.proposal_slot_ids:
        raise invalid("slot_not_proposed", "La alternativa no pertenece a la propuesta")
    referral = await session.get(ReferralCase, locked_request.referral_id)
    if (
        referral is None
        or referral.patient_id != locked_request.patient_id
        or referral.status != "approved"
        or slot.service != referral.requested_specialty
    ):
        raise invalid(
            "referral_not_approved",
            "La referencia vigente no permite confirmar esta alternativa",
        )
    if (
        locked_request.required_equivalence_group
        and slot.equivalence_group != locked_request.required_equivalence_group
    ):
        raise invalid(
            "slot_not_equivalent", "La alternativa no cumple la equivalencia autorizada"
        )
    if (
        locked_request.arrival_window_end
        and slot.starts_at < locked_request.arrival_window_end
    ):
        raise invalid("slot_outside_travel_window", "La alternativa no respeta el viaje")
    if (
        locked_request.arrival_window_start
        and locked_request.arrival_window_end is None
        and slot.starts_at < locked_request.arrival_window_start
    ):
        raise invalid("slot_outside_travel_window", "La alternativa no respeta el viaje")
    if locked_request.return_deadline and slot.ends_at > locked_request.return_deadline:
        raise invalid("slot_outside_travel_window", "La alternativa no respeta el viaje")

    # La espera por el lock puede haber permitido que el primer intento se
    # confirme. Se vuelve a comprobar la idempotencia dentro de la sección crítica.
    existing = await session.scalar(
        select(AppointmentHold).where(AppointmentHold.operation_id == operation_id)
    )
    if existing is not None:
        return existing

    holds = list(
        await session.scalars(
            select(AppointmentHold)
            .where(
                AppointmentHold.slot_id == slot.id,
                AppointmentHold.status == "held",
            )
            .with_for_update()
        )
    )
    for active in holds:
        if active.expires_at <= current:
            active.status = "expired"
            active.updated_at = current
        else:
            raise invalid("slot_held", "Otra solicitud ya retuvo esta alternativa")

    expires_at = min(current + timedelta(minutes=hold_minutes), slot.starts_at)
    if slot.expires_at is not None:
        expires_at = min(expires_at, slot.expires_at)
    hold = AppointmentHold(
        request_id=locked_request.id,
        slot_id=slot.id,
        status="held",
        expires_at=expires_at,
        availability_version=slot.availability_version,
        operation_id=operation_id,
    )
    session.add(hold)
    locked_request.selected_slot_id = slot.id
    locked_request.proposal_expires_at = expires_at
    locked_request.status = "awaiting_confirmation"
    locked_request.version += 1
    locked_request.updated_at = current
    await session.flush()
    await audit.record_event(
        session,
        actor_id=actor.id,
        action="hold_appointment_slot",
        entity_type="appointment_hold",
        entity_id=hold.id,
        metadata={
            "patient_id": locked_request.patient_id,
            "request_id": locked_request.id,
            "slot_id": slot.id,
            "availability_version": slot.availability_version,
        },
    )
    return hold


async def revalidate_hold(
    session: AsyncSession,
    *,
    actor: User,
    hold_id: UUID,
    now: datetime | None = None,
) -> bool:
    _require_adult(actor)
    current = now or utcnow()
    hold = await session.scalar(
        select(AppointmentHold).where(AppointmentHold.id == hold_id).with_for_update()
    )
    if hold is None:
        raise not_found("Retención no encontrada")
    request = await session.scalar(
        select(AppointmentRequest)
        .where(AppointmentRequest.id == hold.request_id)
        .with_for_update()
    )
    slot = await session.scalar(
        select(AppointmentSlot).where(AppointmentSlot.id == hold.slot_id).with_for_update()
    )
    if request is None or slot is None:
        raise not_found("Solicitud o alternativa no encontrada")

    valid = (
        hold.status == "held"
        and hold.expires_at > current
        and hold.availability_version == slot.availability_version
        and _slot_is_valid(slot, now=current)
    )
    if not valid and hold.status == "held":
        hold.status = "expired"
        hold.updated_at = current
        request.status = "proposal_ready"
        request.version += 1
        request.updated_at = current
    return valid


async def submit_manual_request(
    session: AsyncSession,
    *,
    actor: User,
    hold_id: UUID,
    operation_id: UUID,
    now: datetime | None = None,
) -> AppointmentRequest:
    """Envía a revisión humana; este adaptador jamás produce `confirmed`."""
    _require_adult(actor)
    current = now or utcnow()

    repeated = await session.scalar(
        select(AppointmentRequest).where(
            AppointmentRequest.submission_operation_id == operation_id
        )
    )
    if repeated is not None:
        return repeated

    hold = await session.scalar(
        select(AppointmentHold).where(AppointmentHold.id == hold_id).with_for_update()
    )
    if hold is None:
        raise not_found("Retención no encontrada")
    request = await session.scalar(
        select(AppointmentRequest)
        .where(AppointmentRequest.id == hold.request_id)
        .with_for_update()
    )
    slot = await session.scalar(
        select(AppointmentSlot).where(AppointmentSlot.id == hold.slot_id).with_for_update()
    )
    if request is None or slot is None:
        raise not_found("Solicitud o alternativa no encontrada")

    if request.submission_operation_id is not None:
        if request.submission_operation_id == operation_id:
            return request
        raise invalid("request_already_submitted", "La solicitud ya fue enviada")
    valid = (
        hold.status == "held"
        and hold.expires_at > current
        and hold.availability_version == slot.availability_version
        and _slot_is_valid(slot, now=current)
    )
    if not valid:
        if hold.status == "held":
            hold.status = "expired"
            hold.updated_at = current
        request.status = "proposal_ready"
        request.version += 1
        raise invalid("hold_expired", "La alternativa cambió; debe consultar de nuevo")

    hold.status = "consumed"
    hold.consumed_at = current
    hold.updated_at = current
    slot.available_places -= 1
    slot.availability_version += 1
    slot.updated_at = current
    request.status = "submitted"
    request.submission_operation_id = operation_id
    request.external_result = "manual_review_required"
    request.selected_slot_id = slot.id
    request.version += 1
    request.updated_at = current
    await session.flush()
    await audit.record_event(
        session,
        actor_id=actor.id,
        action="submit_appointment_request",
        entity_type="appointment_request",
        entity_id=request.id,
        metadata={
            "patient_id": request.patient_id,
            "slot_id": slot.id,
            "result": "submitted_manual_review",
        },
    )
    return request


async def get_or_create_voice_session(
    session: AsyncSession,
    *,
    provider: str,
    provider_call_key: str,
    policy_version: str,
    language: str = "es-PE",
    speech_rate: str = "slow",
    started_at: datetime | None = None,
) -> VoiceSession:
    """El identificador debe llegar seudonimizado por el gateway."""
    if not provider_call_key.startswith(("call:", "hmac:")):
        raise invalid("pseudonymous_call_key_required", "La llamada requiere una clave opaca")
    existing = await session.scalar(
        select(VoiceSession).where(VoiceSession.provider_call_key == provider_call_key)
    )
    if existing is not None:
        return existing
    record = VoiceSession(
        provider=provider,
        provider_call_key=provider_call_key,
        state="welcome",
        policy_version=policy_version,
        language=language,
        speech_rate=speech_rate,
        started_at=started_at or utcnow(),
    )
    try:
        async with session.begin_nested():
            session.add(record)
            await session.flush()
    except IntegrityError:
        concurrent = await session.scalar(
            select(VoiceSession).where(
                VoiceSession.provider_call_key == provider_call_key
            )
        )
        if concurrent is None:
            raise
        return concurrent
    return record


async def get_voice_session(
    session: AsyncSession,
    *,
    session_id: UUID,
    actor: User | None = None,
) -> VoiceSession:
    _require_adult(actor)
    query = select(VoiceSession).where(VoiceSession.id == session_id)
    if actor is not None and actor.role == "caregiver":
        query = query.where(VoiceSession.actor_id == actor.id)
    record = await session.scalar(query)
    if record is None:
        raise not_found("Sesión de voz no encontrada")
    return record


async def list_voice_sessions(
    session: AsyncSession,
    *,
    actor: User,
    patient: Patient | None = None,
    states: Sequence[str] | None = None,
) -> list[VoiceSession]:
    _require_adult(actor)
    query = select(VoiceSession)
    if actor.role == "caregiver":
        query = query.where(VoiceSession.actor_id == actor.id)
    if patient is not None:
        query = query.where(VoiceSession.patient_id == patient.id)
    if states:
        unknown = set(states) - set(VOICE_SESSION_STATES)
        if unknown:
            raise invalid("invalid_voice_state", "Estado de sesión no válido")
        query = query.where(VoiceSession.state.in_(states))
    rows = await session.scalars(query.order_by(VoiceSession.started_at.desc()))
    return list(rows)


async def get_voice_session_by_workflow_id(
    session: AsyncSession, *, workflow_session_id: str
) -> VoiceSession | None:
    """Resuelve una sesión seudónima tras reiniciar el proceso del simulador."""
    return await session.scalar(
        select(VoiceSession)
        .where(
            VoiceSession.context_json["workflowSessionId"].as_string()
            == workflow_session_id
        )
        .with_for_update()
    )


async def get_voice_event_response(
    session: AsyncSession,
    *,
    voice_session: VoiceSession,
    event_type: str,
    event_key: str,
) -> dict[str, Any] | None:
    _require_choice(event_type, VOICE_EVENT_TYPES, "voice_event_type")
    event = await session.scalar(
        select(VoiceEvent).where(
            VoiceEvent.voice_session_id == voice_session.id,
            VoiceEvent.event_type == event_type,
            VoiceEvent.event_key == event_key,
        )
    )
    return dict(event.response_json) if event is not None else None


async def record_voice_event(
    session: AsyncSession,
    *,
    voice_session: VoiceSession,
    event_key: str,
    next_state: str,
    response: dict[str, Any],
    event_type: str = "turn",
    context: dict[str, Any] | None = None,
    expected_version: int | None = None,
    reprompt_delta: int = 0,
    transfer_reason: str | None = None,
) -> dict[str, Any]:
    """Persiste una transición y devuelve la misma respuesta ante un retry."""
    _require_choice(next_state, VOICE_SESSION_STATES, "voice_state")
    _require_choice(event_type, VOICE_EVENT_TYPES, "voice_event_type")
    _assert_safe_structure(response)
    if context is not None:
        _assert_safe_structure(context)
    if reprompt_delta < 0:
        raise invalid("invalid_reprompt_delta", "El contador de repreguntas no puede disminuir")

    locked = await session.scalar(
        select(VoiceSession)
        .where(VoiceSession.id == voice_session.id)
        .with_for_update()
    )
    if locked is None:
        raise not_found("Sesión de voz no encontrada")
    replay = await session.scalar(
        select(VoiceEvent).where(
            VoiceEvent.voice_session_id == locked.id,
            VoiceEvent.event_type == event_type,
            VoiceEvent.event_key == event_key,
        )
    )
    if replay is not None:
        return dict(replay.response_json)
    if locked.state in {"completed", "human_handoff"}:
        if locked.last_response_json:
            return dict(locked.last_response_json)
        raise DomainError(
            "voice_session_closed",
            "La sesión de voz ya terminó",
            409,
        )
    if expected_version is not None and locked.version != expected_version:
        raise DomainError(
            "voice_state_changed", "La sesión avanzó; recargue su estado", 409
        )

    event = VoiceEvent(
        voice_session_id=locked.id,
        event_type=event_type,
        event_key=event_key,
        resulting_state=next_state,
        response_json=response,
    )
    session.add(event)
    locked.state = next_state
    locked.context_json = context
    locked.last_event_key = event_key
    locked.last_response_json = response
    locked.reprompt_count += reprompt_delta
    locked.transfer_reason = transfer_reason
    locked.version += 1
    locked.updated_at = utcnow()
    if next_state in {"completed", "human_handoff"}:
        locked.ended_at = utcnow()
    await session.flush()
    await audit.record_event(
        session,
        actor_id=locked.actor_id,
        action="voice_state_transition",
        entity_type="voice_session",
        entity_id=locked.id,
        metadata={
            "state": next_state,
            "event_hash": hashlib.sha256(event_key.encode("utf-8")).hexdigest()[:16],
            "event_type": event_type,
            "reprompt_count": locked.reprompt_count,
        },
    )
    return dict(response)


async def create_callback_request(
    session: AsyncSession,
    *,
    operation_id: UUID,
    contact_reference: str,
    reason_code: str,
    sla_due_at: datetime,
    actor: User | None = None,
    patient: Patient | None = None,
    voice_session: VoiceSession | None = None,
) -> CallbackRequest:
    _require_adult(actor)
    contact_kind, contact_token = _assert_opaque_contact(contact_reference)
    _require_choice(reason_code, CALLBACK_REASON_CODES, "callback_reason")
    if actor is not None and (
        contact_kind not in {"contact", "user"}
        or UUID(contact_token) != actor.id
    ):
        raise invalid(
            "contact_reference_not_owned",
            "La referencia de contacto no pertenece al usuario autenticado",
        )
    existing = await session.scalar(
        select(CallbackRequest).where(CallbackRequest.operation_id == operation_id)
    )
    if existing is not None:
        expected_actor = actor.id if actor else None
        expected_patient = patient.id if patient else None
        if existing.actor_id != expected_actor or existing.patient_id != expected_patient:
            raise invalid("operation_conflict", "La operación pertenece a otro callback")
        return existing
    if sla_due_at <= utcnow():
        raise invalid("invalid_callback_sla", "El SLA del callback debe ser futuro")
    if (
        voice_session is not None
        and patient is not None
        and voice_session.patient_id not in {None, patient.id}
    ):
        raise not_found("Sesión de voz no encontrada")

    callback = CallbackRequest(
        voice_session_id=voice_session.id if voice_session else None,
        actor_id=actor.id if actor else None,
        patient_id=patient.id if patient else None,
        contact_reference=contact_reference.strip(),
        reason_code=reason_code,
        status="requested",
        sla_due_at=sla_due_at,
        operation_id=operation_id,
    )
    try:
        async with session.begin_nested():
            session.add(callback)
            await session.flush()
    except IntegrityError:
        concurrent = await session.scalar(
            select(CallbackRequest).where(CallbackRequest.operation_id == operation_id)
        )
        if concurrent is None:
            raise
        expected_actor = actor.id if actor else None
        expected_patient = patient.id if patient else None
        if (
            concurrent.actor_id != expected_actor
            or concurrent.patient_id != expected_patient
        ):
            raise invalid(
                "operation_conflict", "La operación pertenece a otro callback"
            ) from None
        return concurrent
    await audit.record_event(
        session,
        actor_id=callback.actor_id,
        action="create_callback_request",
        entity_type="callback_request",
        entity_id=callback.id,
        metadata={
            "patient_id": callback.patient_id,
            "reason_code": callback.reason_code,
            "status": callback.status,
        },
    )
    return callback


async def list_callback_requests(
    session: AsyncSession,
    *,
    actor: User,
    patient_ids: Sequence[UUID],
    statuses: Sequence[str] | None = None,
    include_unverified: bool = False,
) -> list[CallbackRequest]:
    _require_adult(actor)
    query = select(CallbackRequest)
    allowed = tuple(set(patient_ids))
    if include_unverified:
        raise forbidden("La mesa central no verificada todavía no está configurada")
    if allowed:
        query = query.where(CallbackRequest.patient_id.in_(allowed))
    else:
        return []
    if statuses:
        unknown = set(statuses) - set(CALLBACK_REQUEST_STATUSES)
        if unknown:
            raise invalid("invalid_callback_status", "Estado de callback no válido")
        query = query.where(CallbackRequest.status.in_(statuses))
    rows = await session.scalars(
        query.order_by(CallbackRequest.sla_due_at, CallbackRequest.created_at)
    )
    return list(rows)


async def get_callback_request(
    session: AsyncSession,
    *,
    actor: User,
    callback_id: UUID,
    patient_ids: Sequence[UUID],
    include_unverified: bool = False,
) -> CallbackRequest:
    _require_adult(actor)
    query = select(CallbackRequest).where(CallbackRequest.id == callback_id)
    allowed = tuple(set(patient_ids))
    if include_unverified:
        raise forbidden("La mesa central no verificada todavía no está configurada")
    if allowed:
        query = query.where(CallbackRequest.patient_id.in_(allowed))
    else:
        raise not_found("Solicitud de devolución de llamada no encontrada")
    callback = await session.scalar(query)
    if callback is None:
        raise not_found("Solicitud de devolución de llamada no encontrada")
    return callback


async def handoff_appointment_request(
    session: AsyncSession,
    *,
    actor: User,
    patient: Patient,
    request: AppointmentRequest,
    operation_id: UUID,
    contact_reference: str,
    reason_code: str,
    sla_due_at: datetime,
    voice_session: VoiceSession | None = None,
) -> tuple[AppointmentRequest, CallbackRequest]:
    """Conserva la solicitud y abre ayuda humana idempotente desde cualquier estado."""
    _require_adult(actor)
    if request.patient_id != patient.id:
        raise not_found("Solicitud de cita no encontrada")
    callback = await create_callback_request(
        session,
        operation_id=operation_id,
        contact_reference=contact_reference,
        reason_code=reason_code,
        sla_due_at=sla_due_at,
        actor=actor,
        patient=patient,
        voice_session=voice_session,
    )
    locked = await session.scalar(
        select(AppointmentRequest)
        .where(AppointmentRequest.id == request.id)
        .with_for_update()
    )
    if locked is None:
        raise not_found("Solicitud de cita no encontrada")
    transitioned = locked.status != "confirmed" and locked.status != "human_handoff"
    if transitioned:
        locked.status = "human_handoff"
        locked.version += 1
        locked.updated_at = utcnow()
    if voice_session is not None and voice_session.state != "human_handoff":
        voice_session.state = "human_handoff"
        voice_session.transfer_reason = reason_code
        voice_session.ended_at = utcnow()
        voice_session.version += 1
        voice_session.updated_at = utcnow()
    await session.flush()
    if transitioned:
        await audit.record_event(
            session,
            actor_id=actor.id,
            action="handoff_appointment_request",
            entity_type="appointment_request",
            entity_id=locked.id,
            metadata={
                "patient_id": patient.id,
                "reason_code": reason_code,
                "callback_id": callback.id,
            },
        )
    return locked, callback


def validate_model_constants() -> None:
    """Mantiene importadas y comprobables las taxonomías de persistencia."""
    assert set(SERVICE_HOUR_STATUSES) == {"published", "retired"}
    assert set(REFERRAL_STATUSES) == {"received", "in_review", "observed", "approved"}
    assert set(APPOINTMENT_SLOT_STATUSES) == {"available", "blocked", "cancelled"}
    assert "requested" in CALLBACK_REQUEST_STATUSES
