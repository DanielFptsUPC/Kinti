"""Endpoints del equipo asistencial.

El semáforo que devuelven estos endpoints es riesgo operativo de interrupción de
la ruta, nunca gravedad clínica.
"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CareTeamUser, SessionDep
from app.api.v1 import schemas
from app.core.errors import DomainError
from app.modules.alerts import service as alerts_service
from app.modules.care_routes import service as care_routes
from app.modules.milestones import service as milestones_service
from app.modules.patients import service as patients_service

router = APIRouter(tags=["equipo asistencial"])


@router.get("/care-team/overview", response_model=schemas.OverviewResponse)
async def overview(user: CareTeamUser, session: SessionDep) -> schemas.OverviewResponse:
    patient_ids = await patients_service.authorized_patient_ids(session, user)
    context = await care_routes.load_context(session, patient_ids)

    counts = {"green": 0, "yellow": 0, "red": 0}
    for patient in context.patients:
        counts[care_routes.patient_payload(context, patient)["operational_risk"]] += 1

    return schemas.OverviewResponse(
        counts=schemas.RiskCounts(**counts),
        open_alerts=sum(1 for a in context.alerts if a.status != "resolved"),
        generated_at=context.now,
    )


@router.get("/care-team/patients", response_model=list[schemas.CareTeamPatientRow])
async def list_patients(
    user: CareTeamUser,
    session: SessionDep,
    risk: str | None = Query(default=None, pattern="^(green|yellow|red)$"),
    status: str | None = Query(
        default=None, pattern="^(all|pending_confirmation|with_barrier|missed)$"
    ),
) -> list[schemas.CareTeamPatientRow]:
    patient_ids = await patients_service.authorized_patient_ids(session, user)
    context = await care_routes.load_context(session, patient_ids)

    rows: list[schemas.CareTeamPatientRow] = []
    for patient in context.patients:
        payload = care_routes.patient_payload(context, patient)
        has_open_barrier = any(
            a.patient_id == patient.id and a.status != "resolved" for a in context.alerts
        )
        has_missed = any(
            m.patient_id == patient.id and m.status == "missed" for m in context.milestones
        )

        if risk is not None and payload["operational_risk"] != risk:
            continue
        if status == "pending_confirmation" and payload["route_status"] != "confirmation_needed":
            continue
        if status == "with_barrier" and not has_open_barrier:
            continue
        if status == "missed" and not has_missed:
            continue

        if has_missed:
            reason = "Inasistencia registrada"
        elif has_open_barrier:
            reason = "Barrera reportada"
        elif payload["route_status"] == "confirmation_needed":
            reason = "Pendiente de confirmación"
        else:
            reason = "Sin pendientes"

        next_milestone = care_routes.next_milestone_for(context, patient.id)
        rows.append(
            schemas.CareTeamPatientRow(
                patient=schemas.PatientOut.model_validate(payload),
                next_milestone=(
                    schemas.MilestoneOut.model_validate(
                        care_routes.milestone_payload(next_milestone)
                    )
                    if next_milestone
                    else None
                ),
                has_open_barrier=has_open_barrier,
                has_missed=has_missed,
                reason=reason,
            )
        )

    risk_order = {"red": 0, "yellow": 1, "green": 2}
    rows.sort(key=lambda r: (risk_order[r.patient.operational_risk], r.patient.display_name))
    return rows


@router.get("/care-team/alerts", response_model=list[schemas.AlertOut])
async def list_alerts(
    user: CareTeamUser,
    session: SessionDep,
    status: str | None = Query(default=None, pattern="^(open|in_progress|resolved|pending)$"),
    risk: str | None = Query(default=None, pattern="^(green|yellow|red)$"),
) -> list[schemas.AlertOut]:
    patient_ids = await patients_service.authorized_patient_ids(session, user)
    context = await care_routes.load_context(session, patient_ids)

    payloads = [care_routes.alert_payload(context, a) for a in context.alerts]
    if status == "pending":
        payloads = [p for p in payloads if p["status"] != "resolved"]
    elif status is not None:
        payloads = [p for p in payloads if p["status"] == status]
    if risk is not None:
        payloads = [p for p in payloads if p["risk"] == risk]

    payloads.sort(key=lambda p: p["created_at"], reverse=True)
    return [schemas.AlertOut.model_validate(p) for p in payloads]


@router.get("/alerts/{alert_id}", response_model=schemas.AlertDetail)
async def get_alert(
    alert_id: UUID, user: CareTeamUser, session: SessionDep
) -> schemas.AlertDetail:
    try:
        alert = await alerts_service.get_alert(session, alert_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
    except DomainError as exc:
        raise exc.as_http() from exc

    context = await care_routes.load_context(session, [alert.patient_id])
    milestone = next(m for m in context.milestones if m.id == alert.milestone_id)
    patient = context.patients[0]

    return schemas.AlertDetail(
        alert=schemas.AlertOut.model_validate(care_routes.alert_payload(context, alert)),
        milestone=schemas.MilestoneOut.model_validate(care_routes.milestone_payload(milestone)),
        patient=schemas.PatientOut.model_validate(care_routes.patient_payload(context, patient)),
    )


@router.post("/alerts/{alert_id}/contact", response_model=schemas.AlertOut)
async def contact_family(
    alert_id: UUID,
    body: schemas.ContactFamilyRequest,
    user: CareTeamUser,
    session: SessionDep,
) -> schemas.AlertOut:
    try:
        alert = await alerts_service.get_alert(session, alert_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
        await alerts_service.mark_family_contacted(session, actor=user, alert=alert)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    context = await care_routes.load_context(session, [alert.patient_id])
    stored = next(a for a in context.alerts if a.id == alert_id)
    return schemas.AlertOut.model_validate(care_routes.alert_payload(context, stored))


@router.post("/alerts/{alert_id}/refer-social-work", response_model=schemas.AlertOut)
async def refer_social_work(
    alert_id: UUID,
    body: schemas.ReferSocialWorkRequest,
    user: CareTeamUser,
    session: SessionDep,
) -> schemas.AlertOut:
    try:
        alert = await alerts_service.get_alert(session, alert_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
        await alerts_service.refer_to_social_work(
            session,
            actor=user,
            alert=alert,
            internal_note=body.internal_note,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    context = await care_routes.load_context(session, [alert.patient_id])
    stored = next(a for a in context.alerts if a.id == alert_id)
    return schemas.AlertOut.model_validate(care_routes.alert_payload(context, stored))


@router.post("/alerts/{alert_id}/resolve", response_model=schemas.AlertOut)
async def resolve_alert(
    alert_id: UUID,
    body: schemas.ResolveAlertRequest,
    user: CareTeamUser,
    session: SessionDep,
) -> schemas.AlertOut:
    try:
        alert = await alerts_service.get_alert(session, alert_id)
        await patients_service.require_patient_access(session, user, alert.patient_id)
        await alerts_service.resolve(
            session,
            actor=user,
            alert=alert,
            action_taken=body.action_taken,
            internal_note=body.internal_note,
            new_scheduled_at=body.new_scheduled_at,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    context = await care_routes.load_context(session, [alert.patient_id])
    stored = next(a for a in context.alerts if a.id == alert_id)
    return schemas.AlertOut.model_validate(care_routes.alert_payload(context, stored))


@router.post("/patients/{patient_id}/milestones", response_model=schemas.MilestoneOut)
async def create_milestone(
    patient_id: UUID,
    body: schemas.CreateMilestoneRequest,
    user: CareTeamUser,
    session: SessionDep,
) -> schemas.MilestoneOut:
    try:
        await patients_service.require_patient_access(session, user, patient_id)
        milestone = await milestones_service.create_milestone(
            session,
            actor=user,
            patient_id=patient_id,
            type=body.type,
            title=body.title,
            scheduled_at=body.scheduled_at,
            location=body.location,
            preparation=body.preparation,
            service=body.service,
            confirmation_deadline=body.confirmation_deadline,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    await session.refresh(milestone)
    return schemas.MilestoneOut.model_validate(care_routes.milestone_payload(milestone))


@router.post("/milestones/{milestone_id}/reschedule", response_model=schemas.MilestoneOut)
async def reschedule_milestone(
    milestone_id: UUID,
    body: schemas.RescheduleMilestoneRequest,
    user: CareTeamUser,
    session: SessionDep,
) -> schemas.MilestoneOut:
    try:
        milestone = await milestones_service.get_milestone(session, milestone_id)
        await patients_service.require_patient_access(session, user, milestone.patient_id)
        await milestones_service.reschedule(
            session, actor=user, milestone=milestone, new_scheduled_at=body.new_scheduled_at
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    await session.refresh(milestone)
    return schemas.MilestoneOut.model_validate(care_routes.milestone_payload(milestone))
