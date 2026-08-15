"""Extracción controlada de intenciones para Kinti Voz.

El modelo sólo clasifica una frase y sugiere una herramienta de una lista
cerrada. No recibe conocimiento RAG ni resultados operativos, no ejecuta la
herramienta y no decide la transición de la máquina de estados.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from app.modules.assistant.ports import ModelRequest, ModelResponse, MultimodalModel
from app.modules.voice import policy
from app.modules.voice.ports import TurnInput

VOICE_INTENT_PROMPT_VERSION = "kinti-voice-intent-es-PE@1"
MAX_UTTERANCE_CHARS = 500


class VoiceIntent(StrEnum):
    """Intenciones que el modelo puede proponer, nunca ejecutar."""

    SERVICE_HOURS = "voice_service_hours"
    REFERRAL_STATUS = "voice_referral_status"
    APPOINTMENT = "voice_appointment"
    HUMAN_HELP = "voice_human_help"
    REPEAT = "voice_repeat"
    SLOW_DOWN = "voice_slow_down"
    DID_NOT_UNDERSTAND = "voice_did_not_understand"
    BACK = "voice_back"
    CLINICAL_OR_SAFETY = "voice_clinical_or_safety"
    UNKNOWN = "voice_unknown"


class SuggestedVoiceTool(StrEnum):
    """Herramientas que el dominio podría evaluar después de clasificar."""

    NONE = "none"
    GET_SERVICE_HOURS = "get_service_hours"
    LOOKUP_REFERRAL = "lookup_referral"
    SEARCH_APPOINTMENT_OPTIONS = "search_appointment_options"
    REQUEST_CALLBACK = "request_callback"


class IntentExtractionStatus(StrEnum):
    CLASSIFIED = "classified"
    POLICY_OVERRIDE = "policy_override"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    MALFORMED_OUTPUT = "malformed_output"
    REJECTED_OUTPUT = "rejected_output"


class VoiceIntentCandidate(BaseModel):
    """Única forma de salida aceptada desde el proveedor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: VoiceIntent
    suggested_tool: SuggestedVoiceTool
    confidence: Annotated[float, Field(strict=True, ge=0.0, le=1.0)]
    needs_human: StrictBool


class VoiceIntentExtraction(BaseModel):
    """Resultado seguro, incluso cuando el proveedor falla."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: IntentExtractionStatus
    candidate: VoiceIntentCandidate
    model_id: str | None = None


_EXPECTED_TOOL = {
    VoiceIntent.SERVICE_HOURS: SuggestedVoiceTool.GET_SERVICE_HOURS,
    VoiceIntent.REFERRAL_STATUS: SuggestedVoiceTool.LOOKUP_REFERRAL,
    VoiceIntent.APPOINTMENT: SuggestedVoiceTool.SEARCH_APPOINTMENT_OPTIONS,
    VoiceIntent.HUMAN_HELP: SuggestedVoiceTool.REQUEST_CALLBACK,
    VoiceIntent.REPEAT: SuggestedVoiceTool.NONE,
    VoiceIntent.SLOW_DOWN: SuggestedVoiceTool.NONE,
    VoiceIntent.DID_NOT_UNDERSTAND: SuggestedVoiceTool.NONE,
    VoiceIntent.BACK: SuggestedVoiceTool.NONE,
    VoiceIntent.CLINICAL_OR_SAFETY: SuggestedVoiceTool.NONE,
    VoiceIntent.UNKNOWN: SuggestedVoiceTool.NONE,
}

_COMMAND_INTENT = {
    policy.AccessibilityCommand.REPEAT: VoiceIntent.REPEAT,
    policy.AccessibilityCommand.SLOW_DOWN: VoiceIntent.SLOW_DOWN,
    policy.AccessibilityCommand.DID_NOT_UNDERSTAND: VoiceIntent.DID_NOT_UNDERSTAND,
    policy.AccessibilityCommand.BACK: VoiceIntent.BACK,
    policy.AccessibilityCommand.HUMAN: VoiceIntent.HUMAN_HELP,
}


class VoiceIntentExtractor:
    """Adaptador fail-closed sobre el puerto multimodal existente."""

    def __init__(self, model: MultimodalModel, *, timeout_seconds: float = 2.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser mayor que cero")
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def extract(
        self, text: str, *, language: str = "es-PE"
    ) -> VoiceIntentExtraction:
        """Clasifica sin consultar RAG ni suministrar datos operativos al modelo."""
        if policy.is_clinical_or_safety_question(text):
            return _policy_result(
                VoiceIntent.CLINICAL_OR_SAFETY,
                needs_human=True,
            )

        command = policy.accessibility_command(TurnInput(modality="speech", value=text))
        if command is not None:
            intent = _COMMAND_INTENT[command]
            return _policy_result(
                intent,
                needs_human=intent is VoiceIntent.HUMAN_HELP,
            )

        request = ModelRequest(
            system_prompt_version=VOICE_INTENT_PROMPT_VERSION,
            question=text.strip()[:MAX_UTTERANCE_CHARS],
            modality="text",
            task="voice_intent",
            chunks=(),
            media=None,
            language=language,
        )
        try:
            response = await asyncio.wait_for(
                self._model.generate(request), timeout=self._timeout_seconds
            )
        except TimeoutError:
            return _fallback(IntentExtractionStatus.TIMEOUT, self._model.model_id)
        except Exception:
            return _fallback(IntentExtractionStatus.PROVIDER_ERROR, self._model.model_id)

        return self._validate(response)

    def _validate(self, response: ModelResponse) -> VoiceIntentExtraction:
        raw = response.structured_output
        if not isinstance(raw, dict):
            return _fallback(IntentExtractionStatus.MALFORMED_OUTPUT, response.model_id)

        raw_tool = raw.get("suggested_tool")
        allowed_tools = {tool.value for tool in SuggestedVoiceTool}
        if not isinstance(raw_tool, str) or raw_tool not in allowed_tools:
            return _fallback(IntentExtractionStatus.REJECTED_OUTPUT, response.model_id)

        if response.proposed_action is not None or response.citations or response.answer:
            return _fallback(IntentExtractionStatus.REJECTED_OUTPUT, response.model_id)

        try:
            candidate = VoiceIntentCandidate.model_validate(raw)
        except ValidationError:
            return _fallback(IntentExtractionStatus.MALFORMED_OUTPUT, response.model_id)

        expected_human = candidate.intent in {
            VoiceIntent.HUMAN_HELP,
            VoiceIntent.CLINICAL_OR_SAFETY,
        }
        if (
            response.intent != candidate.intent.value
            or response.needs_human != candidate.needs_human
            or candidate.needs_human != expected_human
            or _EXPECTED_TOOL[candidate.intent] != candidate.suggested_tool
        ):
            return _fallback(IntentExtractionStatus.REJECTED_OUTPUT, response.model_id)

        return VoiceIntentExtraction(
            status=IntentExtractionStatus.CLASSIFIED,
            candidate=candidate,
            model_id=response.model_id,
        )


def _policy_result(intent: VoiceIntent, *, needs_human: bool) -> VoiceIntentExtraction:
    return VoiceIntentExtraction(
        status=IntentExtractionStatus.POLICY_OVERRIDE,
        candidate=VoiceIntentCandidate(
            intent=intent,
            suggested_tool=_EXPECTED_TOOL[intent],
            confidence=1.0,
            needs_human=needs_human,
        ),
    )


def _fallback(
    status: IntentExtractionStatus, model_id: str | None
) -> VoiceIntentExtraction:
    return VoiceIntentExtraction(
        status=status,
        candidate=VoiceIntentCandidate(
            intent=VoiceIntent.UNKNOWN,
            suggested_tool=SuggestedVoiceTool.NONE,
            confidence=0.0,
            needs_human=False,
        ),
        model_id=model_id,
    )
