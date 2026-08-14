"""Paridad de reglas con `src/logic/__tests__/risk.test.ts`.

Cada prueba es la traducción literal de su equivalente en TypeScript, con los
mismos valores y el mismo reloj fijo. Si una de las dos implementaciones cambia
sin la otra, esta suite lo detecta.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_routes.rules import (
    DEFAULT_BARRIER_RESPONSE_WINDOW_HOURS as WINDOW,
)
from app.modules.care_routes.rules import (
    AlertView,
    MilestoneView,
    compute_milestone_risk,
    compute_patient_operational_risk,
    compute_route_status,
    get_active_milestones,
    get_next_milestone,
    is_overdue,
)

NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=UTC)


def milestone(**overrides) -> MilestoneView:
    base = {
        "id": "m-1",
        "patient_id": "p-1",
        "status": "upcoming",
        "attendance_confirmed": False,
        "scheduled_at": datetime(2026, 8, 15, 9, 0, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return MilestoneView(**base)


def alert(**overrides) -> AlertView:
    base = {"id": "a-1", "milestone_id": "m-1", "status": "open", "created_at": NOW}
    base.update(overrides)
    return AlertView(**base)


# --------------------------------------------------------------- riesgo del hito


def test_green_when_confirmed_and_no_barrier():
    assert compute_milestone_risk(milestone(attendance_confirmed=True), [], NOW) == "green"


def test_yellow_when_pending_confirmation():
    assert compute_milestone_risk(milestone(attendance_confirmed=False), [], NOW) == "yellow"


def test_yellow_when_barrier_just_reported():
    assert compute_milestone_risk(milestone(), [alert(created_at=NOW)], NOW) == "yellow"


def test_red_once_open_barrier_passes_window():
    stale = NOW - timedelta(hours=WINDOW + 1)
    assert compute_milestone_risk(milestone(), [alert(created_at=stale)], NOW) == "red"


def test_stays_yellow_while_in_progress_even_past_window():
    stale = NOW - timedelta(hours=WINDOW + 5)
    in_progress = alert(status="in_progress", created_at=stale)
    assert compute_milestone_risk(milestone(), [in_progress], NOW) == "yellow"


def test_red_when_missed_regardless_of_alerts():
    assert compute_milestone_risk(milestone(status="missed"), [], NOW) == "red"


def test_ignores_resolved_alerts():
    resolved = alert(status="resolved")
    assert compute_milestone_risk(milestone(attendance_confirmed=True), [resolved], NOW) == "green"


def test_green_for_unscheduled_milestone():
    """No hay fecha que confirmar todavía: sólo está pendiente de programación."""
    pending = milestone(status="unscheduled", scheduled_at=None, attendance_confirmed=False)
    assert compute_milestone_risk(pending, [], NOW) == "green"


def test_unscheduled_milestone_with_open_barrier_is_still_flagged():
    pending = milestone(status="unscheduled", scheduled_at=None)
    assert compute_milestone_risk(pending, [alert()], NOW) == "yellow"


@pytest.mark.parametrize("window", [1, 24, 48, 72])
def test_window_is_configurable(window: int):
    just_past = NOW - timedelta(hours=window + 1)
    just_before = NOW - timedelta(hours=window - 0.5)
    assert compute_milestone_risk(milestone(), [alert(created_at=just_past)], NOW, window) == "red"
    assert (
        compute_milestone_risk(milestone(), [alert(created_at=just_before)], NOW, window)
        == "yellow"
    )


# ------------------------------------------------------------ priorización


def test_excludes_completed_and_prioritizes_missed():
    completed = milestone(id="m-done", status="completed")
    upcoming = milestone(
        id="m-upcoming", status="upcoming", scheduled_at=datetime(2026, 8, 20, 9, tzinfo=UTC)
    )
    missed = milestone(
        id="m-missed", status="missed", scheduled_at=datetime(2026, 8, 1, 9, tzinfo=UTC)
    )

    active = get_active_milestones("p-1", [completed, upcoming, missed])
    assert [m.id for m in active] == ["m-missed", "m-upcoming"]
    assert get_next_milestone("p-1", [completed, upcoming, missed]).id == "m-missed"


def test_sorts_upcoming_by_nearest_date():
    soon = milestone(id="m-soon", scheduled_at=datetime(2026, 8, 13, 9, tzinfo=UTC))
    later = milestone(id="m-later", scheduled_at=datetime(2026, 9, 1, 9, tzinfo=UTC))
    assert get_next_milestone("p-1", [later, soon]).id == "m-soon"


def test_unscheduled_sorts_after_scheduled():
    scheduled = milestone(id="m-sched", scheduled_at=datetime(2026, 12, 1, 9, tzinfo=UTC))
    unscheduled = milestone(id="m-none", status="unscheduled", scheduled_at=None)
    assert get_next_milestone("p-1", [unscheduled, scheduled]).id == "m-sched"


# ------------------------------------------------------- riesgo del paciente


def test_patient_risk_is_worst_case():
    green = milestone(id="m-green", attendance_confirmed=True)
    missed = milestone(id="m-missed", status="missed")
    assert compute_patient_operational_risk("p-1", [green, missed], [], NOW) == "red"


def test_patient_risk_green_without_active_milestones():
    completed = milestone(status="completed")
    assert compute_patient_operational_risk("p-1", [completed], [], NOW) == "green"


def test_patient_risk_ignores_other_patients():
    other = milestone(id="m-other", patient_id="p-2", status="missed")
    mine = milestone(id="m-mine", attendance_confirmed=True)
    assert compute_patient_operational_risk("p-1", [mine, other], [], NOW) == "green"


# ------------------------------------------------------------ estado de ruta


def test_route_on_track_without_next_milestone():
    assert compute_route_status(None, []) == "on_track"


def test_route_confirmation_needed():
    assert compute_route_status(milestone(attendance_confirmed=False), []) == "confirmation_needed"


def test_route_support_needed_with_open_barrier():
    needs_support = milestone(status="support_needed")
    assert compute_route_status(needs_support, [alert()]) == "support_needed"


def test_route_on_track_when_confirmed():
    assert compute_route_status(milestone(attendance_confirmed=True), []) == "on_track"


# ------------------------------------------------------------------ vencimiento


def test_is_overdue_respects_tolerance():
    past = milestone(scheduled_at=NOW - timedelta(hours=10))
    assert is_overdue(past, NOW, tolerance_hours=6) is True
    assert is_overdue(past, NOW, tolerance_hours=24) is False


def test_confirmed_milestone_is_never_overdue():
    past = milestone(scheduled_at=NOW - timedelta(hours=100), attendance_confirmed=True)
    assert is_overdue(past, NOW, tolerance_hours=6) is False


def test_unscheduled_milestone_is_never_overdue():
    assert is_overdue(milestone(status="unscheduled", scheduled_at=None), NOW, 6) is False
