"""Endpoints del contexto familiar.

Cada uno vuelve a comprobar el vínculo cuidador–paciente en el servidor: ocultar
un botón en la interfaz nunca es control de acceso.
"""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CaregiverUser, SessionDep
from app.api.v1 import schemas
from app.core.errors import DomainError
from app.modules.alerts import service as alerts_service
from app.modules.care_routes import service as care_routes
from app.modules.feelings import service as feelings_service
from app.modules.milestones import service as milestones_service
from app.modules.patients import service as patients_service

router = APIRouter(tags=["familia"])


@router.get("/patients/{patient_id}/route", response_model=schemas.RouteResponse)
async def get_route(
    patient_id: UUID, user: CaregiverUser, session: SessionDep
) -> schemas.RouteResponse:
    try:
        await patients_service.require_patient_access(session, user, patient_id)
    except DomainError as exc:
        raise exc.as_http() from exc

    context = await care_routes.load_context(session, [patient_id])
    patient = context.patients[0]
    next_milestone = care_routes.next_milestone_for(context, patient_id)

    return schemas.RouteResponse(
        patient=schemas.PatientOut.model_validate(care_routes.patient_payload(context, patient)),
        milestones=[
            schemas.MilestoneOut.model_validate(care_routes.milestone_payload(m))
            for m in context.milestones
        ],
        alerts=[
            schemas.AlertOut.model_validate(care_routes.alert_payload(context, a))
            for a in context.alerts
        ],
        next_milestone_id=next_milestone.id if next_milestone else None,
    )


@router.post("/milestones/{milestone_id}/confirmations", response_model=schemas.MilestoneOut)
async def confirm_attendance(
    milestone_id: UUID,
    body: schemas.ConfirmAttendanceRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.MilestoneOut:
    try:
        milestone = await milestones_service.get_milestone(session, milestone_id)
        await patients_service.require_patient_access(session, user, milestone.patient_id)
        await milestones_service.confirm_attendance(
            session, actor=user, milestone=milestone, operation_id=body.operation_id
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    await session.refresh(milestone)
    return schemas.MilestoneOut.model_validate(care_routes.milestone_payload(milestone))


@router.post("/milestones/{milestone_id}/barriers", response_model=schemas.AlertOut)
async def report_barrier(
    milestone_id: UUID,
    body: schemas.ReportBarrierRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.AlertOut:
    try:
        milestone = await milestones_service.get_milestone(session, milestone_id)
        await patients_service.require_patient_access(session, user, milestone.patient_id)
        alert = await alerts_service.report_barrier(
            session,
            actor=user,
            milestone=milestone,
            category=body.category,
            note=body.note,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    context = await care_routes.load_context(session, [milestone.patient_id])
    stored = next(a for a in context.alerts if a.id == alert.id)
    return schemas.AlertOut.model_validate(care_routes.alert_payload(context, stored))


@router.post("/patients/{patient_id}/feelings", response_model=schemas.FeelingOut)
async def record_feeling(
    patient_id: UUID,
    body: schemas.RecordFeelingRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.FeelingOut:
    try:
        await patients_service.require_patient_access(session, user, patient_id)
        feeling = await feelings_service.record_feeling(
            session,
            actor=user,
            patient_id=patient_id,
            mood=body.mood,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return schemas.FeelingOut.model_validate(care_routes.feeling_payload(feeling))
