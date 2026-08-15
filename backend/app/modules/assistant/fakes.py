"""Implementaciones determinísticas para pruebas y desarrollo.

Son el proveedor **por defecto**: un despliegue mal configurado no debe empezar a
gastar dinero ni a enviar datos a un tercero por omisión. Activar el proveedor
real es una decisión consciente (`KINTI_AI_PROVIDER=vertex`).

Nada aquí llama a la red. Las mismas entradas producen siempre las mismas
salidas, para que una prueba que falla sea una prueba que encontró algo.
"""

import hashlib
import math
import re
import unicodedata

from app.modules.assistant.ports import (
    Citation,
    EmbeddingProvider,
    ExtractedDocument,
    Intent,
    MediaRef,
    ModelRequest,
    ModelResponse,
    MultimodalModel,
    ProposedAction,
    TranscriptionResult,
)
from app.modules.assistant.safety import POLICY_VERSION

DEFAULT_DIMENSION = 768


class FakeEmbeddingProvider(EmbeddingProvider):
    """Embeddings derivados de un hash del texto.

    No tienen semántica real, pero sí las dos propiedades que las pruebas
    necesitan: son estables entre ejecuciones y textos parecidos comparten
    términos, de modo que la búsqueda léxica sigue siendo significativa.
    """

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return f"fake-embedding-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        # Un vector por token, sumados: dos textos que comparten palabras quedan
        # más cerca que dos que no comparten ninguna.
        vector = [0.0] * self._dimension
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, len(digest), 2):
                index = int.from_bytes(digest[i : i + 2], "big") % self._dimension
                vector[index] += 1.0

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            # Vector unitario estable para texto vacío; nunca se devuelve el cero,
            # que la distancia coseno no sabe interpretar.
            vector[0] = 1.0
            return vector
        return [v / norm for v in vector]


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if len(t) > 2]


class FakeMultimodalModel(MultimodalModel):
    """Modelo de reglas explícitas.

    Reproduce el contrato completo —intención, citas, abstención, acción
    propuesta— sin ninguna inferencia. Sirve para probar el orquestador, la
    política de seguridad y la API sin depender de un proveedor externo.
    """

    def __init__(self, model_id: str = "fake-multimodal-1") -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.task == "voice_intent":
            return _classify_voice_intent(request.question, self._model_id)

        question = request.question.lower()

        # Barrera explícita: propone acción, nunca la ejecuta.
        barrier = _detect_barrier(question)
        if barrier is not None:
            category, summary = barrier
            return ModelResponse(
                intent="report_barrier",
                answer=(
                    "Entiendo. Puedo avisar al equipo para que te acompañe con esto. "
                    "¿Confirmas que registre tu solicitud?"
                ),
                confidence="supported",
                proposed_action=ProposedAction(
                    kind="report_barrier",
                    summary=summary,
                    payload={"category": category},
                ),
                model_id=self._model_id,
            )

        if _mentions(question, ("proxima cita", "próxima cita", "cuando es mi", "cuándo es mi")):
            # El orquestador la resuelve con el servicio operativo, no con RAG.
            return ModelResponse(
                intent="next_milestone_query",
                answer="",
                confidence="supported",
                model_id=self._model_id,
            )

        if _mentions(question, ("que me llamen", "contacto", "hablar con alguien")):
            return ModelResponse(
                intent="request_callback",
                answer="Puedo registrar una solicitud para que el equipo te contacte. ¿Confirmas?",
                confidence="supported",
                proposed_action=ProposedAction(
                    kind="request_callback",
                    summary="Solicitar que el equipo asistencial te contacte",
                ),
                model_id=self._model_id,
            )

        # Pregunta informativa: sin fragmentos no hay respuesta, hay abstención.
        if not request.chunks:
            return ModelResponse(
                intent="institutional_faq",
                answer="",
                confidence="insufficient_evidence",
                model_id=self._model_id,
            )

        best = request.chunks[0]
        return ModelResponse(
            intent="institutional_faq",
            answer=_summarize(best.content),
            citations=tuple(
                Citation(
                    chunk_id=c.chunk_id,
                    document_title=c.document_title,
                    document_version=c.document_version,
                    section=c.section,
                    page=c.page,
                )
                for c in request.chunks[:3]
            ),
            confidence="supported",
            model_id=self._model_id,
        )

    async def transcribe(self, media: MediaRef, audio: bytes) -> TranscriptionResult:
        """Transcripción simulada.

        Devuelve el contenido como texto UTF-8 si lo es. Permite escribir pruebas
        de audio legibles sin depender de un motor de voz.
        """
        try:
            text = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""
        return TranscriptionResult(text=text, confidence=1.0 if text else 0.0)


#: Marcadores de carencia o imposibilidad. Sin uno de estos, mencionar un tema
#: no es reportar una barrera: «¿dónde consulto por alojamiento?» es una
#: pregunta informativa, y tratarla como una solicitud de ayuda generaría una
#: alerta que nadie pidió.
_LACK = (
    "no tengo",
    "no tenemos",
    "no me alcanza",
    "no nos alcanza",
    "no puedo",
    "no podre",
    "no podré",
    "no podemos",
    "no llega",
    "no hay",
    "sin plata",
    "sin dinero",
    "me falta",
    "nos falta",
)

_BARRIERS: list[tuple[str, tuple[str, ...], str]] = [
    (
        "transport",
        ("pasaje", "movilidad", "transporte", "como llegar", "bus", "combi", "carro"),
        "Reportar una dificultad de transporte para tu próxima atención",
    ),
    (
        "financial",
        ("dinero", "plata", "economic", "pagar", "costo"),
        "Reportar una dificultad económica para tu próxima atención",
    ),
    (
        "lodging",
        ("donde quedarme", "donde dormir", "alojamiento", "hospedaje", "donde parar"),
        "Reportar una dificultad de alojamiento para tu próxima atención",
    ),
    (
        "schedule",
        ("ese dia", "ese día", "otro horario", "cambiar la fecha", "asistir", "ir ese"),
        "Reportar una dificultad de fecha u horario",
    ),
]


def _detect_barrier(question: str) -> tuple[str, str] | None:
    """Requiere tema **y** carencia.

    Distinguir «no tengo para el pasaje» de «cuánto cuesta el pasaje» es la
    diferencia entre registrar una solicitud de ayuda real y molestar al equipo
    con una consulta informativa.
    """
    if not any(marker in question for marker in _LACK):
        return None

    for category, keywords, summary in _BARRIERS:
        if any(k in question for k in keywords):
            return category, summary
    return None


def _mentions(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _summarize(content: str) -> str:
    """Primera oración del fragmento: respuesta breve y trazable a su fuente."""
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    return sentences[0] if sentences else content[:200]


def _classify_voice_intent(question: str, model_id: str) -> ModelResponse:
    """Clasificador local para probar Kinti Voz sin proveedor ni red."""
    value = _normalize(question)
    intent: Intent = "voice_unknown"
    suggested_tool = "none"
    needs_human = False
    confidence = 0.2

    if _mentions(
        value,
        (
            "fiebre",
            "sangrado",
            "dolor",
            "dosis",
            "medicamento",
            "resultado",
            "emergencia",
        ),
    ):
        intent = "voice_clinical_or_safety"
        needs_human = True
        confidence = 1.0
    elif _mentions(value, ("persona", "humano", "operador", "hablar con alguien")):
        intent = "voice_human_help"
        suggested_tool = "request_callback"
        needs_human = True
        confidence = 0.98
    elif _mentions(value, ("repita", "repetir", "otra vez")):
        intent = "voice_repeat"
        confidence = 0.99
    elif _mentions(value, ("mas despacio", "hable lento", "mas lento")):
        intent = "voice_slow_down"
        confidence = 0.99
    elif _mentions(value, ("no entendi", "no comprendi")):
        intent = "voice_did_not_understand"
        confidence = 0.99
    elif _mentions(value, ("volver", "atras", "regresar")):
        intent = "voice_back"
        confidence = 0.99
    elif _mentions(value, ("horario", "a que hora", "cuando atienden", "cuando abren")):
        intent = "voice_service_hours"
        suggested_tool = "get_service_hours"
        confidence = 0.96
    elif _mentions(value, ("referencia", "derivacion", "papel del hospital")):
        intent = "voice_referral_status"
        suggested_tool = "lookup_referral"
        confidence = 0.95
    elif _mentions(value, ("cita", "turno", "fecha para atender", "fecha para que atiendan")):
        intent = "voice_appointment"
        suggested_tool = "search_appointment_options"
        confidence = 0.95

    return ModelResponse(
        intent=intent,
        answer="",
        confidence=("supported" if intent != "voice_unknown" else "insufficient_evidence"),
        needs_human=needs_human,
        structured_output={
            "intent": intent,
            "suggested_tool": suggested_tool,
            "confidence": confidence,
            "needs_human": needs_human,
        },
        model_id=model_id,
    )


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold().strip())
    without_marks = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks)


class FakeDocumentExtractor:
    """Extractor que asume texto plano UTF-8."""

    async def extract(self, media: MediaRef, content: bytes) -> ExtractedDocument:
        try:
            text = content.decode("utf-8")
            confidence = 1.0
        except UnicodeDecodeError:
            text = ""
            confidence = 0.0
        return ExtractedDocument(text=text, pages=1, confidence=confidence)


class FakeMediaStorage:
    """Almacenamiento en memoria con la misma interfaz que el bucket privado."""

    def __init__(self) -> None:
        self._files: dict[tuple[str, str], bytes] = {}

    async def put(self, bucket: str, path: str, content: bytes, mime_type: str) -> MediaRef:
        self._files[(bucket, path)] = content
        return MediaRef(
            bucket=bucket,
            path=path,
            mime_type=mime_type,
            size_bytes=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
        )

    async def get(self, ref: MediaRef) -> bytes:
        return self._files[(ref.bucket, ref.path)]

    async def signed_url(self, ref: MediaRef, expires_in_seconds: int) -> str:
        # URL opaca y con expiración explícita, como la real.
        return f"memory://{ref.bucket}/{ref.path}?expires_in={expires_in_seconds}"

    async def delete(self, ref: MediaRef) -> None:
        self._files.pop((ref.bucket, ref.path), None)


PROMPT_VERSION = POLICY_VERSION
