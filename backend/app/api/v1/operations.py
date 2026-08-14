"""Tablero operativo derivado del documento oficial del Desafío 3.

Los puntajes muestran carga y capacidad observables; nunca reasignan pacientes,
modifican protocolos ni sustituyen decisiones del personal autorizado.
"""

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import CareTeamUser, SessionDep
from app.api.v1 import schemas
from app.core.time import utcnow
from app.modules.operations import service
from app.modules.patients import service as patients_service

router = APIRouter(prefix="/operations", tags=["operación asistencial"])


@router.get("/workload", response_model=schemas.WorkloadResponse)
async def workload(user: CareTeamUser, session: SessionDep) -> schemas.WorkloadResponse:
    rows = await service.workload(session)
    scores = [row.weighted_load for row in rows]
    return schemas.WorkloadResponse(
        rows=[
            schemas.WorkloadRow(
                professional_id=row.professional.id,
                professional_name=row.professional.display_name,
                assigned_patients=row.assigned_patients,
                red_patients=row.red_patients,
                yellow_patients=row.yellow_patients,
                open_alerts=row.open_alerts,
                missed_milestones=row.missed_milestones,
                weighted_load=row.weighted_load,
            )
            for row in rows
        ],
        max_difference=(max(scores) - min(scores)) if scores else 0,
        generated_at=utcnow(),
        disclaimer=(
            "Indicador operativo transparente. La reasignación corresponde a la jefatura "
            "y debe considerar complejidad clínica no contenida en este piloto."
        ),
    )


@router.get("/capacity", response_model=schemas.CapacityResponse)
async def capacity(
    user: CareTeamUser,
    session: SessionDep,
    day: datetime | None = Query(default=None),
) -> schemas.CapacityResponse:
    start, end = service.default_window(day or utcnow())
    rows = await service.capacity(session, date_from=start, date_to=end)
    return schemas.CapacityResponse(
        slots=[
            schemas.CapacitySlotOut(
                id=row.slot.id,
                service=row.slot.service,
                starts_at=row.slot.starts_at,
                ends_at=row.slot.ends_at,
                available_places=row.slot.available_places,
                scheduled_patients=row.scheduled_patients,
                occupancy_percent=row.occupancy_percent,
                state=row.state,
            )
            for row in rows
        ],
        generated_at=utcnow(),
        disclaimer=(
            "Capacidad de demostración. No confirma una cita ni cambia la programación clínica."
        ),
    )


@router.get("/social-work", response_model=schemas.SocialWorkQueueResponse)
async def social_work(
    user: CareTeamUser, session: SessionDep
) -> schemas.SocialWorkQueueResponse:
    patient_ids = await patients_service.authorized_patient_ids(session, user)
    rows = await service.social_work_queue(session, patient_ids)
    return schemas.SocialWorkQueueResponse(
        rows=[
            schemas.SocialWorkQueueRow(
                alert_id=alert.id,
                patient_id=patient.id,
                patient_name=patient.display_name,
                category=alert.category,
                alert_status=alert.status,
                coordination_status=status,
                family_contacted=alert.first_contact_at is not None,
                created_at=alert.created_at,
            )
            for alert, patient, status in rows
        ],
        generated_at=utcnow(),
    )
