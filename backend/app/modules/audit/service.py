from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.audit.models import AuditEvent

#: Claves que jamás deben terminar en un evento de auditoría. Fase 5 añade
#: telefonía, pero no convierte la auditoría en una copia de la llamada.
_FORBIDDEN_KEYS = {
    "note",
    "internal_note",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "phone",
    "phone_number",
    "caller",
    "caller_id",
    "from",
    "to",
    "dni",
    "document_number",
    "transcript",
    "speech_result",
    "audio",
    "recording",
    "raw_body",
}


def _safe_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {
            key: _safe_value(item)
            for key, item in value.items()
            if key.lower() not in _FORBIDDEN_KEYS and item is not None
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return value


def _sanitize(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Deja pasar sólo metadatos mínimos.

    Se auditan identificadores y categorías, nunca el texto que escribió la
    familia o el profesional: el rastro debe permitir reconstruir *qué* pasó sin
    replicar contenido sensible.
    """
    if not metadata:
        return None
    clean = {
        key: _safe_value(value)
        for key, value in metadata.items()
        if key.lower() not in _FORBIDDEN_KEYS and value is not None
    }
    return clean or None


async def record_event(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Registra una escritura relevante. El llamador hace el commit."""
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        occurred_at=utcnow(),
        metadata_json=_sanitize(metadata),
    )
    session.add(event)
    return event
