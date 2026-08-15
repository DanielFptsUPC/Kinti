"""Puertos de la capa de IA.

Todo lo sustituible vive detrás de un `Protocol`: modelo multimodal, embeddings,
extracción de documentos, recuperación de conocimiento y almacenamiento de
medios. El dominio depende sólo de estas interfaces, nunca de un SDK concreto.

Eso permite dos cosas que importan: cambiar de proveedor sin tocar rutas ni casos
de uso, y correr toda la suite con implementaciones determinísticas y sin red.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

# --------------------------------------------------------------------- tipos

Modality = Literal["text", "audio", "image"]
ModelTask = Literal["assistant", "voice_intent"]

Intent = Literal[
    "institutional_faq",
    "next_milestone_query",
    "attendance_confirmation",
    "report_barrier",
    "request_callback",
    "administrative_document_question",
    "clinical_or_safety_concern",
    "voice_service_hours",
    "voice_referral_status",
    "voice_appointment",
    "voice_human_help",
    "voice_repeat",
    "voice_slow_down",
    "voice_did_not_understand",
    "voice_back",
    "voice_clinical_or_safety",
    "voice_unknown",
    "unknown",
]

Confidence = Literal["supported", "insufficient_evidence", "refused"]

#: Categorías de imagen que Kinti no interpreta bajo ninguna circunstancia.
CLINICAL_IMAGE_CATEGORIES = frozenset(
    {"prescription", "lab_result", "lesion", "clinical_document"}
)


@dataclass(frozen=True)
class MediaRef:
    """Referencia a un archivo ya almacenado en un bucket privado."""

    bucket: str
    path: str
    mime_type: str
    size_bytes: int
    checksum: str
    duration_seconds: float | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    """Fragmento recuperado, con todo lo necesario para citarlo."""

    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    document_title: str
    document_version: str
    section: str | None
    page: int | None
    content: str
    score: float


@dataclass(frozen=True)
class Citation:
    chunk_id: UUID
    document_title: str
    document_version: str
    section: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class ProposedAction:
    """Intención de escritura que el modelo propone.

    Es sólo una propuesta: FastAPI valida permisos, esquema y confirmación antes
    de convertirla en un comando idempotente. El modelo nunca escribe.
    """

    kind: Literal["report_barrier", "confirm_attendance", "request_callback"]
    #: Texto que se muestra al usuario para que confirme conscientemente.
    summary: str
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRequest:
    """Lo único que se envía al proveedor. Contexto mínimo, por diseño."""

    system_prompt_version: str
    question: str
    modality: Modality
    #: Selecciona un contrato estructurado especializado sin cambiar de proveedor.
    task: ModelTask = "assistant"
    chunks: tuple[RetrievedChunk, ...] = ()
    media: MediaRef | None = None
    language: str = "es-PE"


@dataclass(frozen=True)
class ModelResponse:
    intent: Intent
    answer: str
    citations: tuple[Citation, ...] = ()
    confidence: Confidence = "insufficient_evidence"
    needs_human: bool = False
    proposed_action: ProposedAction | None = None
    #: Salida estructurada sin interpretar. El caso de uso consumidor debe
    #: validarla con su propio esquema antes de confiar en ella.
    structured_output: dict[str, object] | None = None
    #: Métricas sin contenido sensible.
    latency_ms: int = 0
    model_id: str = "fake"
    usage_units: int = 0


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str = "es-PE"
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractedDocument:
    """Resultado de extraer texto de un archivo."""

    text: str
    pages: int
    #: Baja confianza obliga a revisión humana antes de publicar.
    confidence: float = 1.0
    sections: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalFilters:
    """Filtros que el repositorio aplica **siempre**, antes de rankear."""

    audience: str = "caregiver"
    language: str = "es"
    now: datetime | None = None
    category: str | None = None


# ------------------------------------------------------------------ puertos


class MultimodalModel(Protocol):
    """Proveedor de generación. Texto, audio grabado e imagen."""

    @property
    def model_id(self) -> str: ...

    async def generate(self, request: ModelRequest) -> ModelResponse: ...

    async def transcribe(self, media: MediaRef, audio: bytes) -> TranscriptionResult: ...


class EmbeddingProvider(Protocol):
    """Generación de vectores. La dimensión es parte del contrato."""

    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class DocumentExtractor(Protocol):
    """Extracción de texto desde PDF textual, PDF escaneado o imagen."""

    async def extract(self, media: MediaRef, content: bytes) -> ExtractedDocument: ...


class KnowledgeRetriever(Protocol):
    """Búsqueda híbrida sobre conocimiento publicado y vigente."""

    async def search(
        self, query: str, embedding: list[float], filters: RetrievalFilters, top_k: int
    ) -> list[RetrievedChunk]: ...


class MediaStorage(Protocol):
    """Almacenamiento privado. Nunca expone URLs públicas permanentes."""

    async def put(self, bucket: str, path: str, content: bytes, mime_type: str) -> MediaRef: ...

    async def get(self, ref: MediaRef) -> bytes: ...

    async def signed_url(self, ref: MediaRef, expires_in_seconds: int) -> str: ...

    async def delete(self, ref: MediaRef) -> None: ...
