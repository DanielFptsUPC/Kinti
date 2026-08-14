"""Composición de proveedores de IA.

Único lugar donde se decide qué implementación se usa. Cambiar de proveedor es
cambiar una variable de entorno: ni las rutas, ni los casos de uso, ni el dominio
se enteran.

`fake` es el valor por defecto a propósito. Un despliegue mal configurado no debe
empezar a gastar dinero ni a enviar datos a un tercero por omisión.
"""

from app.core.config import get_settings
from app.modules.assistant.fakes import (
    FakeDocumentExtractor,
    FakeEmbeddingProvider,
    FakeMediaStorage,
    FakeMultimodalModel,
)
from app.modules.assistant.ports import (
    DocumentExtractor,
    EmbeddingProvider,
    MediaStorage,
    MultimodalModel,
)

#: El almacenamiento en memoria debe ser un singleton: un archivo subido en una
#: petición tiene que seguir existiendo en la siguiente.
_media_storage: MediaStorage | None = None


class UnavailableProvider(RuntimeError):
    """El proveedor está configurado pero no puede usarse todavía."""


def build_model() -> MultimodalModel:
    settings = get_settings()

    if settings.ai_provider == "fake":
        return FakeMultimodalModel()

    if settings.ai_provider == "vertex":
        from app.modules.assistant.vertex import VertexGeminiModel

        if not settings.ai_model_id or not settings.ai_region:
            raise UnavailableProvider(
                "Vertex requiere KINTI_AI_MODEL_ID y KINTI_AI_REGION explícitos. "
                "No se admite el alias 'latest': un modelo que cambia bajo los "
                "pies invalida toda evaluación previa."
            )
        return VertexGeminiModel(
            model_id=settings.ai_model_id,
            region=settings.ai_region,
            timeout_seconds=settings.ai_timeout_seconds,
            max_output_tokens=settings.ai_max_output_tokens,
        )

    raise UnavailableProvider(f"Proveedor de IA desconocido: {settings.ai_provider}")


def build_embeddings() -> EmbeddingProvider:
    settings = get_settings()

    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(dimension=settings.embedding_dimension)

    if settings.embedding_provider == "vertex":
        from app.modules.assistant.vertex import VertexEmbeddingProvider

        if not settings.embedding_model_id:
            raise UnavailableProvider("Vertex requiere KINTI_EMBEDDING_MODEL_ID explícito")
        return VertexEmbeddingProvider(
            model_id=settings.embedding_model_id,
            region=settings.ai_region,
            dimension=settings.embedding_dimension,
        )

    raise UnavailableProvider(
        f"Proveedor de embeddings desconocido: {settings.embedding_provider}"
    )


def build_media_storage() -> MediaStorage:
    global _media_storage
    settings = get_settings()

    if settings.storage_provider == "supabase":
        from app.modules.assistant.supabase_storage import SupabaseMediaStorage

        if not settings.supabase_url or not settings.supabase_service_key:
            raise UnavailableProvider(
                "Supabase Storage requiere KINTI_SUPABASE_URL y KINTI_SUPABASE_SERVICE_KEY"
            )
        return SupabaseMediaStorage(
            url=settings.supabase_url, service_key=settings.supabase_service_key
        )

    if _media_storage is None:
        _media_storage = FakeMediaStorage()
    return _media_storage


def build_extractor() -> DocumentExtractor:
    return FakeDocumentExtractor()


def reset_for_testing() -> None:
    """Limpia el almacenamiento en memoria entre pruebas."""
    global _media_storage
    _media_storage = None
