"""Sincronización del outbox: instantánea canónica e idempotencia.

La garantía que se prueba aquí es la razón de ser de la fase: una operación
reenviada tras un corte de red no puede duplicarse.
"""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.core.time import utcnow
from app.modules.alerts.models import BarrierAlert
from app.modules.milestones.models import AttendanceConfirmation
from app.seed import LUCIA_ID, MATEO_ID
from tests.conftest import auth


async def mateo_next_milestone(client, token) -> str:
    route = await client.get(f"/api/v1/patients/{MATEO_ID}/route", headers=auth(token))
    return route.json()["nextMilestoneId"]


async def push(client, token, operations: list[dict]) -> list[dict]:
    response = await client.post(
        "/api/v1/sync/operations", headers=auth(token), json={"operations": operations}
    )
    assert response.status_code == 200, response.text
    return response.json()["results"]


# ------------------------------------------------------------------ bootstrap


async def test_bootstrap_returns_only_authorized_context(client, caregiver_token):
    response = await client.get("/api/v1/sync/bootstrap", headers=auth(caregiver_token))
    assert response.status_code == 200
    body = response.json()

    assert [p["id"] for p in body["patients"]] == [str(MATEO_ID)]
    assert all(m["patientId"] == str(MATEO_ID) for m in body["milestones"])
    assert body["user"]["role"] == "caregiver"
    assert body["serverTime"]


async def test_bootstrap_excludes_other_families(client, lucia_token):
    body = (await client.get("/api/v1/sync/bootstrap", headers=auth(lucia_token))).json()
    assert [p["id"] for p in body["patients"]] == [str(LUCIA_ID)]


async def test_care_team_bootstrap_covers_every_assignment(client, care_team_token):
    body = (await client.get("/api/v1/sync/bootstrap", headers=auth(care_team_token))).json()
    assert len(body["patients"]) == 3


# --------------------------------------------------------------- idempotencia


async def test_same_operation_id_applies_once(client, caregiver_token, session):
    """El reintento offline no duplica la confirmación."""
    milestone_id = await mateo_next_milestone(client, caregiver_token)
    operation = {
        "operationId": str(uuid4()),
        "type": "confirm_attendance",
        "targetId": milestone_id,
        "payload": {},
    }

    first = await push(client, caregiver_token, [operation])
    second = await push(client, caregiver_token, [operation])

    assert first[0]["status"] == "applied"
    assert second[0]["status"] == "already_applied"

    count = await session.scalar(
        select(func.count()).select_from(AttendanceConfirmation)
    )
    assert count == 1


async def test_duplicate_barrier_is_not_created_twice(client, caregiver_token, session):
    milestone_id = await mateo_next_milestone(client, caregiver_token)
    operation = {
        "operationId": str(uuid4()),
        "type": "report_barrier",
        "targetId": milestone_id,
        "payload": {"category": "transport", "note": "Sin pasajes"},
    }

    await push(client, caregiver_token, [operation])
    repeat = await push(client, caregiver_token, [operation])
    assert repeat[0]["status"] == "already_applied"

    # Se cuentan sólo las alertas de este paciente: el seed precarga otras.
    count = await session.scalar(
        select(func.count()).select_from(BarrierAlert).where(BarrierAlert.patient_id == MATEO_ID)
    )
    assert count == 1


async def test_same_operation_repeated_inside_one_batch(client, caregiver_token, session):
    """Incluso dentro del mismo lote, la segunda copia se reconoce como aplicada."""
    milestone_id = await mateo_next_milestone(client, caregiver_token)
    operation = {
        "operationId": str(uuid4()),
        "type": "report_barrier",
        "targetId": milestone_id,
        "payload": {"category": "lodging"},
    }

    results = await push(client, caregiver_token, [operation, operation])
    assert [r["status"] for r in results] == ["applied", "already_applied"]
    count = await session.scalar(
        select(func.count()).select_from(BarrierAlert).where(BarrierAlert.patient_id == MATEO_ID)
    )
    assert count == 1


# ------------------------------------------------------------------ rechazos


async def test_caregiver_cannot_push_care_team_operations(client, caregiver_token):
    results = await push(
        client,
        caregiver_token,
        [
            {
                "operationId": str(uuid4()),
                "type": "resolve_alert",
                "targetId": str(uuid4()),
                "payload": {"actionTaken": "guidance"},
            }
        ],
    )
    assert results[0]["status"] == "rejected"
    assert results[0]["errorCode"] == "forbidden"


async def test_operation_on_another_family_is_rejected(client, caregiver_token, lucia_token):
    lucia_route = await client.get(
        f"/api/v1/patients/{LUCIA_ID}/route", headers=auth(lucia_token)
    )
    lucia_milestone = lucia_route.json()["nextMilestoneId"]

    results = await push(
        client,
        caregiver_token,
        [
            {
                "operationId": str(uuid4()),
                "type": "confirm_attendance",
                "targetId": lucia_milestone,
                "payload": {},
            }
        ],
    )
    assert results[0]["status"] == "rejected"
    assert results[0]["errorCode"] == "not_found"


async def test_invalid_payload_is_rejected_without_breaking_the_batch(client, caregiver_token):
    """Una operación inválida no descarta las que sí eran válidas."""
    milestone_id = await mateo_next_milestone(client, caregiver_token)

    results = await push(
        client,
        caregiver_token,
        [
            {
                "operationId": str(uuid4()),
                "type": "confirm_attendance",
                "targetId": milestone_id,
                "payload": {},
            },
            {
                "operationId": str(uuid4()),
                "type": "report_barrier",
                "targetId": milestone_id,
                "payload": {"category": "no-existe"},
            },
        ],
    )
    assert results[0]["status"] == "applied"
    assert results[1]["status"] == "rejected"
    assert results[1]["errorCode"] == "invalid_payload"


async def test_unknown_operation_type_is_rejected(client, caregiver_token):
    response = await client.post(
        "/api/v1/sync/operations",
        headers=auth(caregiver_token),
        json={
            "operations": [
                {
                    "operationId": str(uuid4()),
                    "type": "borrar_todo",
                    "targetId": str(MATEO_ID),
                    "payload": {},
                }
            ]
        },
    )
    # El tipo no existe en el contrato: lo detiene la validación del esquema.
    assert response.status_code == 422


async def test_batch_size_is_limited(client, caregiver_token):
    milestone_id = await mateo_next_milestone(client, caregiver_token)
    operations = [
        {
            "operationId": str(uuid4()),
            "type": "confirm_attendance",
            "targetId": milestone_id,
            "payload": {},
        }
        for _ in range(60)
    ]
    response = await client.post(
        "/api/v1/sync/operations", headers=auth(caregiver_token), json={"operations": operations}
    )
    assert response.status_code == 413


# ------------------------------------------------- circuito completo por sync


async def test_full_offline_circuit_through_two_sessions(
    client, caregiver_token, care_team_token, session
):
    """Familia offline → sync → equipo resuelve → familia recibe la nueva fecha."""
    milestone_id = await mateo_next_milestone(client, caregiver_token)

    # 1. La familia reporta la barrera desde su outbox (estuvo sin conexión).
    barrier_op = {
        "operationId": str(uuid4()),
        "type": "report_barrier",
        "targetId": milestone_id,
        "payload": {"category": "transport"},
    }
    assert (await push(client, caregiver_token, [barrier_op]))[0]["status"] == "applied"

    # 2. El equipo, en otra sesión, ve la alerta priorizada.
    alerts = await client.get(
        "/api/v1/care-team/alerts?status=pending", headers=auth(care_team_token)
    )
    alert_id = alerts.json()[0]["id"]

    # 3. Contacta y resuelve reprogramando, también por el canal de sincronización.
    new_date = (utcnow() + timedelta(days=6)).replace(microsecond=0)
    results = await push(
        client,
        care_team_token,
        [
            {
                "operationId": str(uuid4()),
                "type": "mark_family_contacted",
                "targetId": alert_id,
                "payload": {},
            },
            {
                "operationId": str(uuid4()),
                "type": "resolve_alert",
                "targetId": alert_id,
                "payload": {
                    "actionTaken": "transport_coordination",
                    "newScheduledAt": new_date.isoformat(),
                },
            },
        ],
    )
    assert [r["status"] for r in results] == ["applied", "applied"]

    # 4. La familia sincroniza y recibe la instantánea canónica actualizada.
    snapshot = (
        await client.get("/api/v1/sync/bootstrap", headers=auth(caregiver_token))
    ).json()
    milestone = next(m for m in snapshot["milestones"] if m["id"] == milestone_id)
    assert milestone["status"] == "rescheduled"
    assert milestone["scheduledAt"].startswith(new_date.date().isoformat())
    assert snapshot["alerts"][0]["status"] == "resolved"
    # Y tiene un aviso esperándola en su centro de notificaciones.
    assert any(n["type"] == "alert_resolved" for n in snapshot["notifications"])
