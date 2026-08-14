from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.audit import service as audit
from app.modules.feelings.models import FeelingCheckIn
from app.modules.identity.models import User


async def record_feeling(
    session: AsyncSession,
    *,
    actor: User,
    patient_id: UUID,
    mood: str,
    operation_id: UUID | None = None,
) -> FeelingCheckIn:
    """Guarda cómo se siente el niño.

    Acompaña, no diagnostica: no crea alertas, no altera el semáforo y no
    participa en ninguna priorización.
    """
    feeling = FeelingCheckIn(
        patient_id=patient_id,
        mood=mood,
        created_at=utcnow(),
        recorded_by=actor.id,
        operation_id=operation_id,
    )
    session.add(feeling)
    await session.flush()

    await audit.record_event(
        session,
        actor_id=actor.id,
        action="record_feeling",
        entity_type="feeling_check_in",
        entity_id=feeling.id,
        metadata={"patient_id": patient_id},
    )
    return feeling
