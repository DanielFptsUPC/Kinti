"""Sincronización: instantánea canónica y aplicación del outbox.

Para el volumen del piloto no hay sincronización delta: `/sync/bootstrap`
devuelve el contexto autorizado completo y el cliente reconstruye su caché desde
ahí. Es más simple de razonar y elimina toda una clase de errores de mezcla.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.v1 import schemas
from app.core.config import get_settings
from app.core.time import utcnow
from app.modules.care_routes import service as care_routes
from app.modules.feelings.models import FeelingCheckIn
from app.modules.notifications import service as notifications_service
from app.modules.notifications.service import NOTIFICATION_COPY
from app.modules.patients import service as patients_service
from app.modules.sync import service as sync_service

router = APIRouter(tags=["sincronización"])


@router.get("/sync/bootstrap", response_model=schemas.BootstrapResponse)
async def bootstrap(user: CurrentUser, session: SessionDep) -> schemas.BootstrapResponse:
    patient_ids = await patients_service.authorized_patient_ids(session, user)
    context = await care_routes.load_context(session, patient_ids)

    feelings: list[schemas.FeelingOut] = []
    if patient_ids:
        rows = await session.scalars(
            select(FeelingCheckIn).where(FeelingCheckIn.patient_id.in_(patient_ids))
        )
        feelings = [
            schemas.FeelingOut.model_validate(care_routes.feeling_payload(f)) for f in rows
        ]

    stored_notifications = await notifications_service.list_for_user(session, user.id)
    notifications = []
    for item in stored_notifications:
        title, body = NOTIFICATION_COPY.get(item.type, ("Aviso", ""))
        notifications.append(
            schemas.NotificationOut(
                id=item.id,
                type=item.type,
                patient_id=item.patient_id,
                title=title,
                body=body,
                created_at=item.scheduled_for,
                read_at=item.read_at,
            )
        )

    return schemas.BootstrapResponse(
        user=schemas.UserProfile(
            id=user.id, email=user.email, display_name=user.display_name, role=user.role
        ),
        patients=[
            schemas.PatientOut.model_validate(care_routes.patient_payload(context, p))
            for p in context.patients
        ],
        milestones=[
            schemas.MilestoneOut.model_validate(care_routes.milestone_payload(m))
            for m in context.milestones
        ],
        alerts=[
            schemas.AlertOut.model_validate(care_routes.alert_payload(context, a))
            for a in context.alerts
        ],
        feelings=feelings,
        notifications=notifications,
        server_time=utcnow(),
    )


@router.post("/sync/operations", response_model=schemas.SyncOperationsResponse)
async def push_operations(
    body: schemas.SyncOperationsRequest, user: CurrentUser, session: SessionDep
) -> schemas.SyncOperationsResponse:
    settings = get_settings()
    if len(body.operations) > settings.max_sync_batch:
        raise HTTPException(
            # 413 literal: Starlette renombró la constante entre versiones.
            status_code=413,
            detail={
                "code": "batch_too_large",
                "message": f"Máximo {settings.max_sync_batch} operaciones por lote",
            },
        )

    results = await sync_service.apply_operations(session, user, body.operations)
    return schemas.SyncOperationsResponse(results=results)
