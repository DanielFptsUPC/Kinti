"""Orquestador conversacional.

Decide, para cada mensaje, por dónde debe ir la respuesta:

    seguridad → operativo → RAG → abstención

El orden importa. La política de seguridad corre **primero** y puede cortocircuitar
todo lo demás; los datos personales se leen del dominio autorizado y nunca de
embeddings; y si no hay evidencia, se responde que no se sabe.

El modelo **propone**. Este módulo valida, y las escrituras exigen confirmación
explícita del usuario más un `operationId` idempotente.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import to_display, utcnow
from app.modules.assistant import safety
from app.modules.assistant.models import (
    AiRun,
    ConversationMessage,
    ConversationSession,
    RetrievalEvidence,
    SafetyEvent,
)
from app.modules.assistant.ports import (
    Citation,
    EmbeddingProvider,
    KnowledgeRetriever,
    MediaRef,
    ModelRequest,
    MultimodalModel,
    ProposedAction,
    RetrievalFilters,
)
from app.modules.care_routes import rules
from app.modules.identity.models import User
from app.modules.milestones.models import Milestone
from app.modules.patients import service as patients_service


@dataclass
class AssistantReply:
    """Lo que se devuelve al cliente. Sin razonamiento interno, sin puntajes."""

    message_id: UUID
    intent: str
    answer: str
    citations: list[Citation]
    confidence: str
    needs_human: bool
    proposed_action: ProposedAction | None = None


class ConversationOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        *,
        model: MultimodalModel,
        embeddings: EmbeddingProvider,
        retriever: KnowledgeRetriever,
    ) -> None:
        self._session = session
        self._model = model
        self._embeddings = embeddings
        self._retriever = retriever

    async def start_session(
        self, *, user: User, patient_id: UUID | None = None
    ) -> ConversationSession:
        """Abre un hilo, verificando que el paciente esté autorizado."""
        if patient_id is not None:
            # Comprueba el vínculo: un UUID ajeno produce 404, no 403.
            await patients_service.require_patient_access(self._session, user, patient_id)

        record = ConversationSession(
            user_id=user.id,
            patient_id=patient_id,
            channel="mobile",
            status="open",
            policy_version=safety.POLICY_VERSION,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def handle_message(
        self,
        *,
        user: User,
        conversation: ConversationSession,
        text: str,
        modality: str = "text",
        media: MediaRef | None = None,
        audio_bytes: bytes | None = None,
        operation_id: UUID | None = None,
    ) -> AssistantReply:
        if conversation.user_id != user.id:
            from app.core.errors import not_found

            raise not_found("Conversación no encontrada")

        # Un mensaje reenviado no se procesa dos veces.
        if operation_id is not None:
            existing = await self._find_by_operation(operation_id)
            if existing is not None:
                return await self._reply_from(existing)

        question = text
        if modality == "audio" and media is not None and audio_bytes is not None:
            transcription = await self._model.transcribe(media, audio_bytes)
            question = transcription.text

        message = ConversationMessage(
            session_id=conversation.id,
            role="user",
            modality=modality,
            content=question,
            status="processing",
            operation_id=operation_id,
        )
        self._session.add(message)
        await self._session.flush()

        # --- 1. Seguridad, antes que nada -----------------------------------
        verdict = safety.classify(question)
        if verdict.action == "refuse_and_transfer":
            return await self._refuse(conversation, message, verdict)
        if verdict.action == "strip_and_continue":
            await self._record_safety(conversation, message, verdict)

        # --- 2. El modelo clasifica y propone -------------------------------
        started = utcnow()
        chunks: list = []
        intent_probe = await self._model.generate(
            ModelRequest(
                system_prompt_version=safety.POLICY_VERSION,
                question=question,
                modality=modality,  # type: ignore[arg-type]
            )
        )

        # --- 3. Datos operativos: dominio autorizado, nunca embeddings ------
        if intent_probe.intent == "next_milestone_query":
            answer = await self._answer_next_milestone(user, conversation)
            return await self._finish(
                conversation, message, intent_probe, answer=answer, chunks=[], started=started
            )

        # --- 4. Pregunta informativa: recuperar y citar ---------------------
        if intent_probe.intent in ("institutional_faq", "unknown"):
            vector = (await self._embeddings.embed([question]))[0]
            settings = get_settings()
            chunks = await self._retriever.search(
                question,
                vector,
                RetrievalFilters(audience="caregiver", language="es", now=utcnow()),
                top_k=settings.rag_top_k,
            )
            response = await self._model.generate(
                ModelRequest(
                    system_prompt_version=safety.POLICY_VERSION,
                    question=question,
                    modality=modality,  # type: ignore[arg-type]
                    chunks=tuple(chunks),
                )
            )
            return await self._finish(
                conversation, message, response, answer=response.answer,
                chunks=chunks, started=started,
            )

        # --- 5. Acción propuesta (barrera, contacto) ------------------------
        return await self._finish(
            conversation, message, intent_probe,
            answer=intent_probe.answer, chunks=[], started=started,
        )

    # ------------------------------------------------------------- internos

    async def _answer_next_milestone(
        self, user: User, conversation: ConversationSession
    ) -> str:
        """Responde desde el dominio, no desde el índice vectorial.

        Una cita se reprograma; un embedding conserva el momento en que se
        generó. Preguntar por la próxima atención tiene que leer la fuente viva.
        """
        from sqlalchemy import select

        patient_id = conversation.patient_id
        if patient_id is None:
            allowed = await patients_service.authorized_patient_ids(self._session, user)
            if not allowed:
                return "Todavía no tengo un paciente vinculado a tu cuenta."
            patient_id = allowed[0]

        rows = await self._session.scalars(
            select(Milestone).where(Milestone.patient_id == patient_id)
        )
        views = [
            rules.MilestoneView(
                id=str(m.id),
                patient_id=str(m.patient_id),
                status=m.status,
                attendance_confirmed=m.attendance_confirmed,
                scheduled_at=m.scheduled_at,
            )
            for m in rows
        ]
        nxt = rules.get_next_milestone(str(patient_id), views)
        if nxt is None:
            return "Por ahora no hay una próxima atención programada."

        milestone = await self._session.get(Milestone, UUID(nxt.id))
        if milestone is None or milestone.scheduled_at is None:
            return (
                "Tu siguiente paso todavía no tiene fecha asignada. "
                "El equipo te avisará apenas se programe."
            )

        when = to_display(milestone.scheduled_at)
        place = f" en {milestone.location}" if milestone.location else ""
        return (
            f"Tu próxima atención es {milestone.title}, "
            f"el {when.strftime('%d/%m/%Y a las %H:%M')}{place}."
        )

    async def _refuse(
        self,
        conversation: ConversationSession,
        message: ConversationMessage,
        verdict: safety.SafetyVerdict,
    ) -> AssistantReply:
        """Ruta determinística de seguridad: texto aprobado y transferencia."""
        await self._record_safety(conversation, message, verdict)

        message.intent = "clinical_or_safety_concern"
        message.confidence = "refused"
        message.status = "answered"
        message.needs_human = True
        message.proposed_action = {
            "kind": "request_callback",
            "summary": "Solicitar que el equipo asistencial te contacte",
        }
        await self._session.flush()

        return AssistantReply(
            message_id=message.id,
            intent="clinical_or_safety_concern",
            answer=verdict.message or safety.CLINICAL_TRANSFER_MESSAGE,
            citations=[],
            confidence="refused",
            needs_human=True,
            proposed_action=ProposedAction(
                kind="request_callback",
                summary="Solicitar que el equipo asistencial te contacte",
            ),
        )

    async def _finish(
        self,
        conversation: ConversationSession,
        message: ConversationMessage,
        response,
        *,
        answer: str,
        chunks: list,
        started,
    ) -> AssistantReply:
        # Última puerta antes de mostrar: sin citas válidas no hay respuesta
        # informativa, por convincente que suene.
        has_citations = bool(response.citations)
        verdict = safety.validate_response(
            response.intent, has_citations, response.confidence
        )
        if verdict.action == "refuse_and_transfer":
            return await self._refuse(conversation, message, verdict)

        if response.confidence == "insufficient_evidence" or (
            response.intent == "institutional_faq" and not has_citations
        ):
            answer = safety.INSUFFICIENT_EVIDENCE_MESSAGE
            confidence = "insufficient_evidence"
        else:
            confidence = response.confidence

        message.intent = response.intent
        message.confidence = confidence
        message.needs_human = response.needs_human
        message.status = (
            "awaiting_confirmation" if response.proposed_action else "answered"
        )
        if response.proposed_action:
            message.proposed_action = {
                "kind": response.proposed_action.kind,
                "summary": response.proposed_action.summary,
                "payload": response.proposed_action.payload,
            }

        for position, chunk in enumerate(chunks):
            self._session.add(
                RetrievalEvidence(
                    message_id=message.id,
                    chunk_id=chunk.chunk_id,
                    position=position,
                    score=chunk.score,
                    created_at=utcnow(),
                )
            )

        self._session.add(
            AiRun(
                message_id=message.id,
                provider="fake" if "fake" in self._model.model_id else "vertex",
                model_id=self._model.model_id,
                prompt_version=safety.POLICY_VERSION,
                latency_ms=int((utcnow() - started).total_seconds() * 1000),
                usage_units=response.usage_units,
                outcome=confidence,
                created_at=utcnow(),
            )
        )
        await self._session.flush()

        return AssistantReply(
            message_id=message.id,
            intent=response.intent,
            answer=answer,
            citations=list(response.citations),
            confidence=confidence,
            needs_human=response.needs_human,
            proposed_action=response.proposed_action,
        )

    async def _record_safety(
        self,
        conversation: ConversationSession,
        message: ConversationMessage,
        verdict: safety.SafetyVerdict,
    ) -> None:
        self._session.add(
            SafetyEvent(
                session_id=conversation.id,
                message_id=message.id,
                category=verdict.category,
                action=verdict.action,
                needs_human_review=verdict.needs_human,
                created_at=utcnow(),
            )
        )
        await self._session.flush()

    async def _find_by_operation(self, operation_id: UUID) -> ConversationMessage | None:
        from sqlalchemy import select

        return await self._session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.operation_id == operation_id
            )
        )

    async def _reply_from(self, message: ConversationMessage) -> AssistantReply:
        action = message.proposed_action
        return AssistantReply(
            message_id=message.id,
            intent=message.intent or "unknown",
            answer="",
            citations=[],
            confidence=message.confidence or "insufficient_evidence",
            needs_human=message.needs_human,
            proposed_action=(
                ProposedAction(
                    kind=action["kind"],
                    summary=action["summary"],
                    payload=action.get("payload", {}),
                )
                if action
                else None
            ),
        )


def new_operation_id() -> UUID:
    return uuid4()
