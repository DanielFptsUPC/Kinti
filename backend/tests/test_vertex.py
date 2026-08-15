"""Adaptador de Vertex AI, contra un SDK simulado.

No hay credenciales de GCP en ningún entorno donde corra esta suite, así que
estas pruebas no llegan a la red — mockean `client.aio.models.*` y verifican la
única parte que este adaptador controla de verdad: construir la petición y
validar la respuesta. Que el modelo real responda razonablemente es un
`google-genai` bien invocado; que una respuesta malformada se trate como
abstención en vez de mostrarse a medias es responsabilidad de este archivo, y
es justo lo que se prueba aquí.

Ejecutar esto en verde **no** cierra la nota "escrito pero NO verificado" del
módulo — para eso hace falta correr la evaluación del §20 contra el servicio
real. Cierra, en cambio, un problema distinto y real: hasta ahora, un cambio
que rompiera `_parse` o `_build_contents` no lo habría notado nadie hasta el
primer despliegue con credenciales.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.assistant.ports import ModelRequest, RetrievedChunk
from app.modules.assistant.vertex import VertexEmbeddingProvider, VertexGeminiModel


def make_model(**overrides) -> VertexGeminiModel:
    defaults = {"project": "kinti-demo", "model_id": "gemini-2.5-flash", "region": "us-central1"}
    return VertexGeminiModel(**{**defaults, **overrides})


def make_chunk(**overrides) -> RetrievedChunk:
    defaults = {
        "chunk_id": uuid4(),
        "document_id": uuid4(),
        "version_id": uuid4(),
        "document_title": "Antes de tu atención",
        "document_version": "1.1",
        "section": "Horario del laboratorio",
        "page": None,
        "content": "El laboratorio central atiende los martes de 7:00 a 13:00 horas.",
        "score": 0.9,
    }
    return RetrievedChunk(**{**defaults, **overrides})


def fake_response(text: str, total_tokens: int = 42) -> SimpleNamespace:
    """Doble mínimo de `GenerateContentResponse`: sólo lo que `_parse*` lee."""
    return SimpleNamespace(
        text=text, usage_metadata=SimpleNamespace(total_token_count=total_tokens)
    )


def with_generate_content(model: VertexGeminiModel, response: SimpleNamespace) -> AsyncMock:
    """Sustituye el cliente real por uno cuyo único método usado está mockeado."""
    mock_generate = AsyncMock(return_value=response)
    models = SimpleNamespace(generate_content=mock_generate)
    fake_client = SimpleNamespace(aio=SimpleNamespace(models=models))
    model._client = lambda: fake_client  # type: ignore[method-assign]
    return mock_generate


# --------------------------------------------------------------- construcción


def test_rejects_the_latest_alias():
    with pytest.raises(ValueError, match="latest"):
        make_model(model_id="gemini-2.5-flash-latest")


def test_requires_an_explicit_project():
    # No es opcional con valor por defecto: sin `project=`, Python ya rechaza
    # la llamada antes de tocar el SDK.
    with pytest.raises(TypeError):
        VertexGeminiModel(model_id="gemini-2.5-flash", region="us-central1")  # type: ignore[call-arg]


# ----------------------------------------------------------- construir el prompt


def test_contents_carry_the_sources_and_the_question():
    model = make_model()
    chunk = make_chunk()
    request = ModelRequest(
        system_prompt_version="test",
        question="¿a qué hora atiende el laboratorio?",
        modality="text",
        chunks=(chunk,),
    )

    contents = model._build_contents(request)

    assert len(contents) == 1
    text = contents[0]["parts"][0]["text"] + contents[0]["parts"][1]["text"]
    assert str(chunk.chunk_id) in text
    assert chunk.document_title in text
    assert chunk.content in text
    assert "¿a qué hora atiende el laboratorio?" in text


def test_voice_intent_task_ignores_chunks():
    """Kinti Voz clasifica una expresión breve; nunca recibe fuentes de RAG."""
    model = make_model()
    request = ModelRequest(
        system_prompt_version="test",
        question="a qué hora abre el laboratorio",
        modality="text",
        task="voice_intent",
        chunks=(make_chunk(),),
    )

    contents = model._build_contents(request)

    joined = " ".join(part["text"] for part in contents[0]["parts"])
    assert "FUENTES APROBADAS" not in joined
    assert "EXPRESIÓN A CLASIFICAR" in joined


# -------------------------------------------------------------- respuesta válida


async def test_generate_parses_a_well_formed_response():
    model = make_model()
    chunk = make_chunk()
    request = ModelRequest(
        system_prompt_version="test", question="¿qué llevo?", modality="text", chunks=(chunk,)
    )
    payload = (
        '{"intent": "institutional_faq", "answer": "Lleva tu documento de identidad.", '
        f'"citations": [{{"chunkId": "{chunk.chunk_id}", "documentVersion": "1.1"}}], '
        '"confidence": "supported", "needsHuman": false}'
    )
    with_generate_content(model, fake_response(payload))

    response = await model.generate(request)

    assert response.intent == "institutional_faq"
    assert response.confidence == "supported"
    assert response.needs_human is False
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == chunk.chunk_id
    assert response.usage_units == 42
    assert response.model_id == "gemini-2.5-flash"


async def test_generate_drops_citations_for_chunks_never_delivered():
    """Un `chunkId` inventado no puede colarse como fuente real.

    El modelo recibe los fragmentos por texto; no hay nada que le impida
    devolver un identificador que se inventó. Esta es la única defensa.
    """
    model = make_model()
    real_chunk = make_chunk()
    request = ModelRequest(
        system_prompt_version="test",
        question="¿qué llevo?",
        modality="text",
        chunks=(real_chunk,),
    )
    payload = (
        '{"intent": "institutional_faq", "answer": "x", '
        f'"citations": [{{"chunkId": "{uuid4()}", "documentVersion": "1.1"}}], '
        '"confidence": "supported", "needsHuman": false}'
    )
    with_generate_content(model, fake_response(payload))

    response = await model.generate(request)

    assert response.citations == ()


async def test_generate_only_accepts_the_action_kinds_the_domain_knows():
    model = make_model()
    request = ModelRequest(
        system_prompt_version="test", question="no tengo para el pasaje", modality="text"
    )
    payload = (
        '{"intent": "report_barrier", "answer": "Entiendo.", "citations": [], '
        '"confidence": "supported", "needsHuman": false, '
        '"proposedAction": {"kind": "delete_everything", "summary": "x"}}'
    )
    with_generate_content(model, fake_response(payload))

    response = await model.generate(request)

    assert response.proposed_action is None


# ------------------------------------------------------- respuesta malformada


async def test_invalid_json_becomes_abstention_not_a_crash():
    model = make_model()
    request = ModelRequest(system_prompt_version="test", question="hola", modality="text")
    with_generate_content(model, fake_response("esto no es JSON"))

    response = await model.generate(request)

    assert response.confidence == "insufficient_evidence"
    assert response.needs_human is True
    assert response.answer == ""


async def test_a_json_array_is_not_a_valid_object_payload():
    """JSON sintácticamente válido pero no un objeto pasaba el `try` de
    `json.loads` y reventaba en el primer `payload.get(...)` con
    `AttributeError`, en vez de abstenerse."""
    model = make_model()
    request = ModelRequest(system_prompt_version="test", question="hola", modality="text")
    with_generate_content(model, fake_response("[1, 2, 3]"))

    response = await model.generate(request)

    assert response.confidence == "insufficient_evidence"
    assert response.needs_human is True


async def test_a_citation_that_is_not_an_object_is_ignored_not_a_crash():
    model = make_model()
    request = ModelRequest(system_prompt_version="test", question="hola", modality="text")
    payload = (
        '{"intent": "institutional_faq", "answer": "x", "citations": ["not-an-object"], '
        '"confidence": "supported", "needsHuman": false}'
    )
    with_generate_content(model, fake_response(payload))

    response = await model.generate(request)

    assert response.citations == ()


# ------------------------------------------------------------- intención de voz


async def test_voice_intent_parses_the_structured_output():
    model = make_model()
    request = ModelRequest(
        system_prompt_version="test",
        question="a que hora abren",
        modality="text",
        task="voice_intent",
    )
    payload = (
        '{"intent": "voice_service_hours", "suggestedTool": "get_service_hours", '
        '"confidenceScore": 0.92, "needsHuman": false}'
    )
    with_generate_content(model, fake_response(payload))

    response = await model.generate(request)

    assert response.intent == "voice_service_hours"
    assert response.structured_output == {
        "intent": "voice_service_hours",
        "suggested_tool": "get_service_hours",
        "confidence": 0.92,
        "needs_human": False,
    }
    assert response.answer == ""


async def test_voice_intent_flags_free_text_the_contract_does_not_allow():
    """El esquema de voz no tiene `answer`: si aparece, el modelo se salió del
    contrato y no hay que confiar en el resto de la respuesta tampoco."""
    model = make_model()
    request = ModelRequest(
        system_prompt_version="test", question="hola", modality="text", task="voice_intent"
    )
    payload = (
        '{"intent": "voice_unknown", "suggestedTool": "none", "confidenceScore": 0.1, '
        '"needsHuman": true, "answer": "Debería explicarte esto con más detalle..."}'
    )
    with_generate_content(model, fake_response(payload))

    response = await model.generate(request)

    assert response.answer == "unexpected_free_output"


async def test_voice_intent_invalid_json_becomes_unknown():
    model = make_model()
    request = ModelRequest(
        system_prompt_version="test", question="hola", modality="text", task="voice_intent"
    )
    with_generate_content(model, fake_response("no es json"))

    response = await model.generate(request)

    assert response.intent == "voice_unknown"
    assert response.confidence == "insufficient_evidence"


# -------------------------------------------------------------------- embeddings


def with_embed_content(provider: VertexEmbeddingProvider, *vectors: list[float]) -> AsyncMock:
    embeddings = [SimpleNamespace(values=v) for v in vectors]
    mock_embed = AsyncMock(return_value=SimpleNamespace(embeddings=embeddings))
    models = SimpleNamespace(embed_content=mock_embed)
    fake_client = SimpleNamespace(aio=SimpleNamespace(models=models))
    provider._client = lambda: fake_client  # type: ignore[method-assign]
    return mock_embed


async def test_embedding_provider_returns_vectors_of_the_declared_dimension():
    provider = VertexEmbeddingProvider(
        project="kinti-demo", model_id="text-embedding-005", region="us-central1", dimension=8
    )
    with_embed_content(provider, [0.1] * 8)

    vectors = await provider.embed(["texto de prueba"])

    assert vectors == [[0.1] * 8]


async def test_embedding_provider_rejects_a_dimension_mismatch():
    """Mezclar dimensiones es un error de datos, no una degradación: la columna
    `vector(768)` lo rechazaría más tarde y peor — mejor fallar aquí."""
    provider = VertexEmbeddingProvider(
        project="kinti-demo", model_id="text-embedding-005", region="us-central1", dimension=768
    )
    with_embed_content(provider, [0.1] * 8)

    with pytest.raises(ValueError, match="dimensión"):
        await provider.embed(["texto de prueba"])
