"""Clasificación tipada y fail-closed de intenciones de Kinti Voz."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.modules.assistant.fakes import FakeMultimodalModel
from app.modules.assistant.ports import (
    Intent,
    MediaRef,
    ModelRequest,
    ModelResponse,
    ProposedAction,
    TranscriptionResult,
)
from app.modules.assistant.vertex import (
    VOICE_INTENT_RESPONSE_SCHEMA,
    VertexGeminiModel,
)
from app.modules.voice.intents import (
    IntentExtractionStatus,
    SuggestedVoiceTool,
    VoiceIntent,
    VoiceIntentExtractor,
)


class StubModel:
    model_id = "stub-intent-model"

    def __init__(
        self,
        *,
        response: ModelResponse | None = None,
        error: Exception | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.response = response
        self.error = error
        self.delay_seconds = delay_seconds
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response

    async def transcribe(self, media: MediaRef, audio: bytes) -> TranscriptionResult:
        raise AssertionError("la extracción de intención no debe transcribir audio")


def _response(
    *,
    intent: Intent = "voice_service_hours",
    tool: object = "get_service_hours",
    structured_output: dict[str, object] | None = None,
    proposed_action: ProposedAction | None = None,
    answer: str = "",
) -> ModelResponse:
    output = structured_output
    if output is None:
        output = {
            "intent": intent,
            "suggested_tool": tool,
            "confidence": 0.94,
            "needs_human": False,
        }
    return ModelResponse(
        intent=intent,
        answer=answer,
        confidence="supported",
        needs_human=bool(output.get("needs_human", False)),
        proposed_action=proposed_action,
        structured_output=output,
        model_id="stub-intent-model",
    )


@pytest.mark.parametrize(
    ("utterance", "intent", "tool"),
    [
        (
            "¿A qué hora atienden hematología?",
            VoiceIntent.SERVICE_HOURS,
            SuggestedVoiceTool.GET_SERVICE_HOURS,
        ),
        (
            "Quiero saber cómo va el papel de referencia",
            VoiceIntent.REFERRAL_STATUS,
            SuggestedVoiceTool.LOOKUP_REFERRAL,
        ),
        (
            "Necesito una fecha para que atiendan a mi niño",
            VoiceIntent.APPOINTMENT,
            SuggestedVoiceTool.SEARCH_APPOINTMENT_OPTIONS,
        ),
    ],
)
async def test_fake_provider_classifies_supported_voice_intents(utterance, intent, tool):
    result = await VoiceIntentExtractor(FakeMultimodalModel()).extract(utterance)

    assert result.status == IntentExtractionStatus.CLASSIFIED
    assert result.candidate.intent == intent
    assert result.candidate.suggested_tool == tool
    assert result.candidate.confidence > 0.9


async def test_request_uses_specialized_task_without_rag_or_media():
    model = StubModel(response=_response())

    result = await VoiceIntentExtractor(model).extract("Necesito conocer el horario")

    assert result.status == IntentExtractionStatus.CLASSIFIED
    assert len(model.requests) == 1
    request = model.requests[0]
    assert request.task == "voice_intent"
    assert request.chunks == ()
    assert request.media is None
    assert request.modality == "text"


async def test_provider_failure_returns_safe_unknown_intent():
    model = StubModel(error=RuntimeError("provider unavailable"))

    result = await VoiceIntentExtractor(model).extract("Quiero consultar una cita")

    assert result.status == IntentExtractionStatus.PROVIDER_ERROR
    assert result.candidate.intent == VoiceIntent.UNKNOWN
    assert result.candidate.suggested_tool == SuggestedVoiceTool.NONE
    assert result.candidate.confidence == 0.0


async def test_provider_timeout_returns_safe_unknown_intent():
    model = StubModel(response=_response(), delay_seconds=0.05)

    result = await VoiceIntentExtractor(model, timeout_seconds=0.001).extract(
        "Quiero consultar una cita"
    )

    assert result.status == IntentExtractionStatus.TIMEOUT
    assert result.candidate.intent == VoiceIntent.UNKNOWN
    assert result.candidate.suggested_tool == SuggestedVoiceTool.NONE


@pytest.mark.parametrize(
    "output",
    [
        None,
        {
            "intent": "voice_service_hours",
            "suggested_tool": "get_service_hours",
            "confidence": "high",
            "needs_human": False,
        },
        {
            "intent": "voice_service_hours",
            "suggested_tool": "get_service_hours",
            "confidence": 0.9,
            "needs_human": False,
            "state": "appointment_confirmed",
        },
    ],
)
async def test_malformed_output_is_never_partially_accepted(output):
    response = (
        ModelResponse(intent="voice_unknown", answer="", structured_output=None)
        if output is None
        else _response(structured_output=output)
    )

    result = await VoiceIntentExtractor(StubModel(response=response)).extract("horario")

    assert result.status == IntentExtractionStatus.MALFORMED_OUTPUT
    assert result.candidate.intent == VoiceIntent.UNKNOWN
    assert result.candidate.suggested_tool == SuggestedVoiceTool.NONE


@pytest.mark.parametrize(
    "response",
    [
        _response(tool="delete_patient"),
        _response(tool="lookup_referral"),
        _response(
            proposed_action=ProposedAction(
                kind="request_callback",
                summary="Ejecutar una acción sin confirmación",
            )
        ),
        _response(answer="La cita está confirmada"),
    ],
)
async def test_forbidden_action_or_tool_is_rejected(response):
    result = await VoiceIntentExtractor(StubModel(response=response)).extract("horario")

    assert result.status == IntentExtractionStatus.REJECTED_OUTPUT
    assert result.candidate.intent == VoiceIntent.UNKNOWN
    assert result.candidate.suggested_tool == SuggestedVoiceTool.NONE


async def test_clinical_question_is_intercepted_before_the_model():
    model = StubModel(error=AssertionError("el modelo no debe recibir contenido clínico"))

    result = await VoiceIntentExtractor(model).extract(
        "Mi niño tiene fiebre, ¿qué dosis le doy?"
    )

    assert result.status == IntentExtractionStatus.POLICY_OVERRIDE
    assert result.candidate.intent == VoiceIntent.CLINICAL_OR_SAFETY
    assert result.candidate.suggested_tool == SuggestedVoiceTool.NONE
    assert result.candidate.needs_human is True
    assert model.requests == []


async def test_accessibility_command_is_deterministic_and_skips_the_model():
    model = StubModel(error=AssertionError("la política oral debe resolver el comando"))

    result = await VoiceIntentExtractor(model).extract("Por favor, repita otra vez")

    assert result.status == IntentExtractionStatus.POLICY_OVERRIDE
    assert result.candidate.intent == VoiceIntent.REPEAT
    assert result.candidate.suggested_tool == SuggestedVoiceTool.NONE
    assert model.requests == []


def test_vertex_voice_schema_and_parser_keep_the_same_closed_lists():
    intent_values = VOICE_INTENT_RESPONSE_SCHEMA["properties"]["intent"]["enum"]
    tool_values = VOICE_INTENT_RESPONSE_SCHEMA["properties"]["suggestedTool"]["enum"]
    assert set(intent_values) == {intent.value for intent in VoiceIntent}
    assert set(tool_values) == {tool.value for tool in SuggestedVoiceTool}
    assert VOICE_INTENT_RESPONSE_SCHEMA["additionalProperties"] is False

    provider = VertexGeminiModel(
        project="kinti-demo", model_id="gemini-2.5-flash-001", region="us-central1"
    )
    raw = SimpleNamespace(
        text=json.dumps(
            {
                "intent": "voice_referral_status",
                "suggestedTool": "lookup_referral",
                "confidenceScore": 0.91,
                "needsHuman": False,
            }
        ),
        usage_metadata=SimpleNamespace(total_token_count=12),
    )

    parsed = provider._parse_voice_intent(raw, latency_ms=7)

    assert parsed.structured_output == {
        "intent": "voice_referral_status",
        "suggested_tool": "lookup_referral",
        "confidence": 0.91,
        "needs_human": False,
    }
    assert parsed.usage_units == 12


async def test_vertex_parser_does_not_launder_an_extra_state_field():
    provider = VertexGeminiModel(project="kinti-demo", model_id="gemini-test", region="us-central1")
    raw = SimpleNamespace(
        text=json.dumps(
            {
                "intent": "voice_appointment",
                "suggestedTool": "search_appointment_options",
                "confidenceScore": 0.99,
                "needsHuman": False,
                "state": "appointment_confirmed",
            }
        ),
        usage_metadata=None,
    )

    parsed = provider._parse_voice_intent(raw, latency_ms=1)
    result = await VoiceIntentExtractor(StubModel(response=parsed)).extract("cita")

    assert result.status == IntentExtractionStatus.REJECTED_OUTPUT
    assert result.candidate.intent == VoiceIntent.UNKNOWN
