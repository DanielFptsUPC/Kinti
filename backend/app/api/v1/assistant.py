"""Endpoints conversacionales.

El asistente vive detrás de la misma frontera de autorización que el resto: el
cliente móvil no toca la base ni el proveedor de IA, y toda escritura pasa por
los mismos comandos idempotentes de la Fase 2.
"""

from uuid import UUID, uuid4

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CaregiverUser, SessionDep
from app.api.v1 import schemas
from app.core.config import get_settings
from app.core.errors import DomainError, invalid, not_found
from app.modules.alerts import service as alerts_service
from app.modules.assistant.models import ConversationMedia, ConversationMessage, ConversationSession
from app.modules.assistant.orchestrator import AssistantReply, ConversationOrchestrator
from app.modules.assistant.ports import MediaRef
from app.modules.assistant.providers import build_embeddings, build_media_storage, build_model
from app.modules.care_routes import rules
from app.modules.knowledge.retriever import PostgresKnowledgeRetriever
from app.modules.milestones import service as milestones_service
from app.modules.milestones.models import Milestone
from app.modules.patients import service as patients_service

router = APIRouter(tags=["asistente"])

#: MIME permitidos. Se valida el declarado y, para audio, la duración.
ALLOWED_MIME = {
    "audio": {"audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm"},
    "image": {"image/jpeg", "image/png", "image/webp"},
}


def _orchestrator(session) -> ConversationOrchestrator:
    return ConversationOrchestrator(
        session,
        model=build_model(),
        embeddings=build_embeddings(),
        retriever=PostgresKnowledgeRetriever(session),
    )


def _to_out(reply: AssistantReply) -> schemas.AssistantMessageOut:
    return schemas.AssistantMessageOut(
        message_id=reply.message_id,
        intent=reply.intent,
        answer=reply.answer,
        citations=[
            schemas.CitationOut(
                chunk_id=c.chunk_id,
                document_title=c.document_title,
                document_version=c.document_version,
                section=c.section,
                page=c.page,
            )
            for c in reply.citations
        ],
        confidence=reply.confidence,
        needs_human=reply.needs_human,
        proposed_action=(
            schemas.ProposedActionOut(
                kind=reply.proposed_action.kind,
                summary=reply.proposed_action.summary,
                payload=reply.proposed_action.payload,
            )
            if reply.proposed_action
            else None
        ),
    )


async def _load_session(session, user, session_id: UUID) -> ConversationSession:
    record = await session.get(ConversationSession, session_id)
    # Una conversación ajena responde 404, no 403: no se confirma que exista.
    if record is None or record.user_id != user.id:
        raise not_found("Conversación no encontrada")
    return record


@router.post("/assistant/sessions", response_model=schemas.SessionOut)
async def start_session(
    body: schemas.StartSessionRequest, user: CaregiverUser, session: SessionDep
) -> schemas.SessionOut:
    try:
        record = await _orchestrator(session).start_session(
            user=user, patient_id=body.patient_id
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return schemas.SessionOut(
        id=record.id,
        patient_id=record.patient_id,
        status=record.status,
        policy_version=record.policy_version,
        created_at=record.created_at,
    )


@router.get("/assistant/sessions/{session_id}", response_model=schemas.SessionOut)
async def get_session(
    session_id: UUID, user: CaregiverUser, session: SessionDep
) -> schemas.SessionOut:
    try:
        record = await _load_session(session, user, session_id)
    except DomainError as exc:
        raise exc.as_http() from exc

    return schemas.SessionOut(
        id=record.id,
        patient_id=record.patient_id,
        status=record.status,
        policy_version=record.policy_version,
        created_at=record.created_at,
    )


@router.post(
    "/assistant/sessions/{session_id}/messages",
    response_model=schemas.AssistantMessageOut,
)
async def send_message(
    session_id: UUID,
    body: schemas.SendMessageRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.AssistantMessageOut:
    try:
        conversation = await _load_session(session, user, session_id)

        media: MediaRef | None = None
        audio_bytes: bytes | None = None
        if body.media_id is not None:
            stored = await session.get(ConversationMedia, body.media_id)
            if stored is None or stored.session_id != conversation.id:
                raise not_found("Archivo no encontrado")
            media = MediaRef(
                bucket=stored.bucket,
                path=stored.path,
                mime_type=stored.mime_type,
                size_bytes=stored.size_bytes,
                checksum=stored.checksum,
                duration_seconds=stored.duration_seconds,
            )
            audio_bytes = await build_media_storage().get(media)

        reply = await _orchestrator(session).handle_message(
            user=user,
            conversation=conversation,
            text=body.text,
            modality=body.modality,
            media=media,
            audio_bytes=audio_bytes,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _to_out(reply)


@router.post(
    "/assistant/messages/{message_id}/confirm-action",
    response_model=schemas.AssistantMessageOut,
)
async def confirm_action(
    message_id: UUID,
    body: schemas.ConfirmActionRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.AssistantMessageOut:
    """Convierte una acción propuesta en un comando idempotente.

    Es el único punto donde una conversación escribe. El modelo no llega hasta
    aquí: llega la confirmación explícita de la persona.
    """
    try:
        message = await session.get(ConversationMessage, message_id)
        if message is None:
            raise not_found("Mensaje no encontrado")
        conversation = await _load_session(session, user, message.session_id)

        if not message.proposed_action:
            raise invalid("no_action", "Este mensaje no propone ninguna acción")

        # Confirmar dos veces no duplica: se devuelve el resultado anterior.
        if message.action_confirmed_at is not None:
            return _reply_for_confirmed(message)

        action = message.proposed_action
        operation_id = body.operation_id or uuid4()
        patient_id = conversation.patient_id
        if patient_id is None:
            allowed = await patients_service.authorized_patient_ids(session, user)
            if not allowed:
                raise not_found("Paciente no encontrado")
            patient_id = allowed[0]
        await patients_service.require_patient_access(session, user, patient_id)

        if action["kind"] in ("report_barrier", "request_callback"):
            milestone = await _next_milestone(session, patient_id)
            if milestone is None:
                raise invalid("no_milestone", "No hay un próximo paso al que asociar la solicitud")

            category = (
                action.get("payload", {}).get("category", "other")
                if action["kind"] == "report_barrier"
                else "communication"
            )
            alert = await alerts_service.report_barrier(
                session,
                actor=user,
                milestone=milestone,
                category=category,
                note=None,
                operation_id=operation_id,
            )
            message.resulting_operation_id = alert.id

        elif action["kind"] == "confirm_attendance":
            milestone = await _next_milestone(session, patient_id)
            if milestone is None:
                raise invalid("no_milestone", "No hay un próximo paso que confirmar")
            await milestones_service.confirm_attendance(
                session, actor=user, milestone=milestone, operation_id=operation_id
            )
            message.resulting_operation_id = milestone.id

        from app.core.time import utcnow

        message.action_confirmed_at = utcnow()
        message.status = "answered"
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _reply_for_confirmed(message)


def _reply_for_confirmed(message: ConversationMessage) -> schemas.AssistantMessageOut:
    return schemas.AssistantMessageOut(
        message_id=message.id,
        intent=message.intent or "unknown",
        answer="Listo. El equipo revisará tu solicitud.",
        citations=[],
        confidence="supported",
        needs_human=True,
        proposed_action=None,
    )


async def _next_milestone(session, patient_id: UUID) -> Milestone | None:
    rows = await session.scalars(select(Milestone).where(Milestone.patient_id == patient_id))
    milestones = list(rows)
    views = [
        rules.MilestoneView(
            id=str(m.id),
            patient_id=str(m.patient_id),
            status=m.status,
            attendance_confirmed=m.attendance_confirmed,
            scheduled_at=m.scheduled_at,
        )
        for m in milestones
    ]
    nxt = rules.get_next_milestone(str(patient_id), views)
    if nxt is None:
        return None
    return next((m for m in milestones if str(m.id) == nxt.id), None)


@router.post("/assistant/media/upload-intent", response_model=schemas.MediaUploadIntentResponse)
async def upload_intent(
    body: schemas.MediaUploadIntentRequest, user: CaregiverUser, session: SessionDep
) -> schemas.MediaUploadIntentResponse:
    """Reserva una ruta opaca y devuelve una URL firmada de corta duración.

    El nombre no incluye datos de la persona: sólo un identificador aleatorio.
    """
    settings = get_settings()

    if body.mime_type not in ALLOWED_MIME[body.modality]:
        raise invalid("unsupported_media", "Tipo de archivo no permitido").as_http()
    if body.size_bytes > settings.max_media_bytes:
        raise invalid("media_too_large", "El archivo supera el tamaño permitido").as_http()
    if (
        body.modality == "audio"
        and body.duration_seconds is not None
        and body.duration_seconds > settings.max_audio_seconds
    ):
        raise invalid("audio_too_long", "El audio supera la duración permitida").as_http()

    from datetime import timedelta

    from app.core.time import utcnow

    conversation = await session.scalar(
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id)
        .order_by(ConversationSession.created_at.desc())
    )
    if conversation is None:
        raise not_found("No hay una conversación abierta").as_http()

    extension = body.mime_type.split("/")[-1]
    record = ConversationMedia(
        session_id=conversation.id,
        bucket="kinti-conversation-media",
        path=f"{uuid4()}.{extension}",
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        checksum="",
        duration_seconds=body.duration_seconds,
        processing_status="pending",
        expires_at=utcnow() + timedelta(hours=settings.media_retention_hours),
    )
    session.add(record)
    await session.commit()

    storage = build_media_storage()
    url = await storage.signed_url(
        MediaRef(
            bucket=record.bucket,
            path=record.path,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            checksum="",
        ),
        expires_in_seconds=600,
    )
    return schemas.MediaUploadIntentResponse(
        media_id=record.id, upload_url=url, expires_in_seconds=600
    )
