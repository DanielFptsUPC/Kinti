from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.audit.models import AuditEvent

#: Claves que jamás deben terminar en un evento de auditoría.
_FORBIDDEN_KEYS = {"note", "internal_note", "password", "token", "access_token", "refresh_token"}


def _sanitize(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Deja pasar sólo metadatos mínimos.

    Se auditan identificadores y categorías, nunca el texto que escribió la
    familia o el profesional: el rastro debe permitir reconstruir *qué* pasó sin
    replicar contenido sensible.
    """
    if not metadata:
        return None
    clean = {k: v for k, v in metadata.items() if k not in _FORBIDDEN_KEYS and v is not None}
    return {k: (str(v) if isinstance(v, UUID) else v) for k, v in clean.items()} or None


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
