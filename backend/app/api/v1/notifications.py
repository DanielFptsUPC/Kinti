"""Centro de notificaciones interno.

En esta fase el `notification_outbox` no sale del sistema: alimenta una vista
dentro de la aplicación. Los adaptadores de push o SMS reales se conectarían
aquí sin cambiar el dominio.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdultUser, SessionDep
from app.api.v1 import schemas
from app.core.time import utcnow
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import NotificationOutbox
from app.modules.notifications.service import NOTIFICATION_COPY

router = APIRouter(tags=["notificaciones"])


def _to_schema(item: NotificationOutbox) -> schemas.NotificationOut:
    title, body = NOTIFICATION_COPY.get(item.type, ("Aviso", ""))
    return schemas.NotificationOut(
        id=item.id,
        type=item.type,
        patient_id=item.patient_id,
        title=title,
        body=body,
        created_at=item.scheduled_for,
        read_at=item.read_at,
    )


@router.get("/notifications", response_model=list[schemas.NotificationOut])
async def list_notifications(
    user: AdultUser, session: SessionDep
) -> list[schemas.NotificationOut]:
    items = await notifications_service.list_for_user(session, user.id)
    return [_to_schema(item) for item in items]


@router.post("/notifications/{notification_id}/read", response_model=schemas.NotificationOut)
async def mark_read(
    notification_id: UUID, user: AdultUser, session: SessionDep
) -> schemas.NotificationOut:
    item = await session.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.id == notification_id,
            NotificationOutbox.recipient_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Notificación no encontrada"},
        )
    if item.read_at is None:
        item.read_at = utcnow()
        item.status = "read"
        await session.commit()
    return _to_schema(item)
