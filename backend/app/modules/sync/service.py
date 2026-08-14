"""Aplicación de operaciones del outbox móvil.

Garantía central de la fase: una operación identificada por `operationId` se
aplica **exactamente una vez**, aunque el cliente la reenvíe tras un corte de
red, un reinicio de la aplicación o un reintento con espera creciente.

La unicidad la sostiene la restricción única de `processed_operations`, no una
comprobación previa en memoria: dos envíos simultáneos del mismo lote terminan
igual.
"""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import schemas
from app.core.errors import DomainError, forbidden, not_found
from app.core.time import utcnow
from app.modules.alerts import service as alerts_service
from app.modules.feelings import service as feelings_service
from app.modules.identity.models import User
from app.modules.milestones import service as milestones_service
from app.modules.patients import service as patients_service
from app.modules.sync.models import ProcessedOperation

#: Qué rol puede emitir cada comando. Se valida aquí y en cada endpoint REST.
OPERATION_ROLES: dict[str, str] = {
    "confirm_attendance": "caregiver",
    "report_barrier": "caregiver",
    "record_feeling": "caregiver",
    "mark_family_contacted": "care_team",
    "refer_social_work": "care_team",
    "resolve_alert": "care_team",
    "create_milestone": "care_team",
    "reschedule_milestone": "care_team",
}


async def _already_processed(session: AsyncSession, operation_id: UUID) -> bool:
    found = await session.scalar(
        select(ProcessedOperation.id).where(ProcessedOperation.operation_id == operation_id)
    )
    return found is not None


async def _dispatch(
    session: AsyncSession, user: User, operation: schemas.SyncOperation
) -> tuple[str, UUID | None]:
    """Ejecuta un comando ya autorizado por rol. Devuelve (resumen, entidad)."""
    kind = operation.type
    payload = operation.payload

    if kind == "confirm_attendance":
        milestone = await milestones_service.get_milestone(session, operation.target_id)
        await patients_service.require_patient_access(session, user, milestone.patient_id)
        await milestones_service.confirm_attendance(
            session, actor=user, milestone=milestone, operation_id=operation.operation_id
        )
        return "attendance_confirmed", milestone.id

    if kind == "report_barrier":
        body = schemas.ReportBarrierRequest.model_validate(payload)
        milestone = await milestones_service.get_milestone(session, operation.target_id)
        await patients_service.require_patient_access(session, user, milestone.patient_id)
        alert = await alerts_service.report_barrier(
            session,
            actor=user,
            milestone=milestone,
            category=body.category,
            note=body.note,
            operation_id=operation.operation_id,
        )
        return "barrier_reported", alert.id

    if kind == "record_feeling":
        body = schemas.RecordFeelingRequest.model_validate(payload)
        await patients_service.require_patient_access(session, user, operation.target_id)
        feeling = await feelings_service.record_feeling(
            session,
            actor=user,
            patient_id=operation.target_id,
            mood=body.mood,
            operation_id=operation.operation_id,
        )
        return "feeling_recorded", feeling.id

    if kind == "mark_family_contacted":
        alert = await alerts_service.get_alert(session, operation.target_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
        await alerts_service.mark_family_contacted(session, actor=user, alert=alert)
        return "family_contacted", alert.id

    if kind == "refer_social_work":
        body = schemas.ReferSocialWorkRequest.model_validate(payload)
        alert = await alerts_service.get_alert(session, operation.target_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
        await alerts_service.refer_to_social_work(
            session,
            actor=user,
            alert=alert,
            internal_note=body.internal_note,
            operation_id=operation.operation_id,
        )
        return "social_work_referred", alert.id

    if kind == "resolve_alert":
        body = schemas.ResolveAlertRequest.model_validate(payload)
        alert = await alerts_service.get_alert(session, operation.target_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
        await alerts_service.resolve(
            session,
            actor=user,
            alert=alert,
            action_taken=body.action_taken,
            internal_note=body.internal_note,
            new_scheduled_at=body.new_scheduled_at,
            operation_id=operation.operation_id,
        )
        return "alert_resolved", alert.id

    if kind == "create_milestone":
        body = schemas.CreateMilestoneRequest.model_validate(payload)
        await patients_service.require_patient_access(session, user, operation.target_id)
        milestone = await milestones_service.create_milestone(
            session,
            actor=user,
            patient_id=operation.target_id,
            type=body.type,
            title=body.title,
            scheduled_at=body.scheduled_at,
            location=body.location,
            preparation=body.preparation,
            service=body.service,
            confirmation_deadline=body.confirmation_deadline,
        )
        return "milestone_created", milestone.id

    if kind == "reschedule_milestone":
        body = schemas.RescheduleMilestoneRequest.model_validate(payload)
        milestone = await milestones_service.get_milestone(session, operation.target_id)
        await patients_service.require_patient_access(session, user, milestone.patient_id)
        await milestones_service.reschedule(
            session, actor=user, milestone=milestone, new_scheduled_at=body.new_scheduled_at
        )
        return "milestone_rescheduled", milestone.id

    raise not_found("Tipo de operación desconocido")


async def apply_operation(
    session: AsyncSession, user: User, operation: schemas.SyncOperation
) -> schemas.SyncOperationResult:
    """Aplica una operación aislada en su propia transacción.

    Que cada operación confirme por separado es intencional: un lote donde la
    tercera es inválida no debe descartar las dos que ya se aplicaron bien.
    """
    if await _already_processed(session, operation.operation_id):
        return schemas.SyncOperationResult(
            operation_id=operation.operation_id, status="already_applied"
        )

    required_role = OPERATION_ROLES.get(operation.type)
    if required_role is None:
        return schemas.SyncOperationResult(
            operation_id=operation.operation_id, status="rejected", error_code="unknown_operation"
        )
    if user.role != required_role:
        return schemas.SyncOperationResult(
            operation_id=operation.operation_id, status="rejected", error_code="forbidden"
        )

    try:
        summary, entity_id = await _dispatch(session, user, operation)
        session.add(
            ProcessedOperation(
                operation_id=operation.operation_id,
                user_id=user.id,
                operation_type=operation.type,
                processed_at=utcnow(),
                result_summary=summary,
                entity_id=entity_id,
            )
        )
        await session.commit()
    except IntegrityError:
        # Otra petición ganó la carrera por el mismo operationId.
        await session.rollback()
        return schemas.SyncOperationResult(
            operation_id=operation.operation_id, status="already_applied"
        )
    except DomainError as exc:
        await session.rollback()
        return schemas.SyncOperationResult(
            operation_id=operation.operation_id, status="rejected", error_code=exc.code
        )
    except ValidationError:
        await session.rollback()
        return schemas.SyncOperationResult(
            operation_id=operation.operation_id, status="rejected", error_code="invalid_payload"
        )

    return schemas.SyncOperationResult(operation_id=operation.operation_id, status="applied")


async def apply_operations(
    session: AsyncSession, user: User, operations: list[schemas.SyncOperation]
) -> list[schemas.SyncOperationResult]:
    """Aplica un lote ordenado, respetando el orden en que la familia actuó."""
    results: list[schemas.SyncOperationResult] = []
    for operation in operations:
        results.append(await apply_operation(session, user, operation))
    return results


def forbid_role(user: User, required: str) -> None:
    """Puerta de rol para los endpoints REST equivalentes."""
    if user.role != required:
        raise forbidden()
