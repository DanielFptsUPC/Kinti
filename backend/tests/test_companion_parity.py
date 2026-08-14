"""Paridad del espacio Compañero con `src/domain/rules/__tests__/companion.test.ts`.

Hay dos implementaciones de la lista blanca porque hay dos modos de datos: el
servidor la aplica en `companion/service.py` y la demostración local la calcula
en `companion.ts`. Cada caso de aquí es la traducción literal de su equivalente
en TypeScript, con los mismos valores y el mismo reloj fijo. Si una de las dos
cambia sin la otra, una de las dos suites cae — que es exactamente el punto: una
divergencia silenciosa acabaría enseñando en modo local lo que el conectado
prohíbe.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.companion import service as companion
from app.modules.companion.models import PatientContentSettings, PatientUserLink
from app.modules.milestones.models import Milestone
from app.modules.patients.models import Patient

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)

PATIENT_ID = uuid4()


def make_milestone(**overrides) -> Milestone:
    base = {
        "id": uuid4(),
        "patient_id": PATIENT_ID,
        "type": "procedure",
        "title": "Procedimiento ambulatorio",
        "scheduled_at": datetime(2026, 8, 15, 9, 0, 0, tzinfo=UTC),
        "preparation": "Ayuno de 8 horas y tu peluche",
        "status": "upcoming",
        "attendance_confirmed": False,
    }
    base.update(overrides)
    return Milestone(**base)


@pytest.fixture
async def linked_patient(session):
    """Un paciente con cuenta activa, sin pasar por el seed."""
    patient = Patient(
        id=PATIENT_ID,
        display_name="Paciente de paridad",
        age=9,
        avatar_key="hummingbird",
        contact_phone="999999999",
        caregiver_name="Adulto responsable",
    )
    session.add(patient)
    await session.flush()
    # El vínculo no se persiste: `build_companion_view` sólo lee `patient_id`, y
    # crear una cuenta completa aquí añadiría ruido al caso que se quiere probar.
    link = PatientUserLink(patient_id=PATIENT_ID, user_id=uuid4(), status="active")
    return patient, link


# ------------------------------------------------------------ lista blanca


async def test_the_view_exposes_exactly_the_allowed_fields(session, linked_patient):
    _, link = linked_patient
    view = await companion.build_companion_view(session, link, NOW)

    assert sorted(view) == [
        "activities",
        "avatar_key",
        "chosen_name",
        "comfort_object",
        "development_band",
        "greeting",
        "immediate_preparation",
    ]


async def test_the_clinical_title_never_leaks(session, linked_patient):
    _, link = linked_patient
    session.add(make_milestone())
    await session.flush()

    view = await companion.build_companion_view(session, link, NOW)
    assert "Procedimiento ambulatorio" not in str(view)


async def test_the_view_carries_no_milestones_or_risk(session, linked_patient):
    _, link = linked_patient
    session.add(make_milestone())
    await session.flush()

    view = await companion.build_companion_view(session, link, NOW)
    assert "milestones" not in view
    assert "operational_risk" not in view
    assert "route_status" not in view


async def test_the_middle_band_is_the_default(session, linked_patient):
    _, link = linked_patient
    view = await companion.build_companion_view(session, link, NOW)

    assert view["development_band"] == "middle"
    assert view["greeting"] == companion.GREETINGS["middle"]


# -------------------------------------------------------- catálogo y filtros


async def test_activities_change_with_the_development_band(session, linked_patient):
    _, link = linked_patient
    settings = PatientContentSettings(patient_id=PATIENT_ID, development_band="early")
    session.add(settings)
    await session.flush()

    early = await companion.build_companion_view(session, link, NOW)
    assert [a["key"] for a in early["activities"]] == ["breathing", "music", "drawing"]

    settings.development_band = "adolescent"
    await session.flush()

    adolescent = await companion.build_companion_view(session, link, NOW)
    assert [a["key"] for a in adolescent["activities"]] == ["breathing", "music", "stories"]


async def test_disabling_one_category_does_not_drag_the_others(session, linked_patient):
    _, link = linked_patient
    enabled = dict(companion.DEFAULT_ENABLED)
    enabled["stories"] = False
    session.add(PatientContentSettings(patient_id=PATIENT_ID, enabled_categories=enabled))
    await session.flush()

    view = await companion.build_companion_view(session, link, NOW)
    keys = [a["key"] for a in view["activities"]]

    assert "stories" not in keys
    assert "breathing" in keys
    assert "music" in keys


async def test_everything_is_enabled_when_nothing_was_configured(session, linked_patient):
    _, link = linked_patient
    view = await companion.build_companion_view(session, link, NOW)

    assert len(view["activities"]) == len(companion.ACTIVITIES["middle"])


# ------------------------------------------------------ preparación inmediata


async def test_preparation_says_when_what_to_bring_and_with_whom(session, linked_patient):
    session.add(make_milestone())
    await session.flush()

    preparation = await companion._immediate_preparation(session, PATIENT_ID, NOW)
    assert preparation is not None
    assert sorted(preparation) == ["bring", "company", "when"]
    assert preparation["bring"] == "Ayuno de 8 horas y tu peluche"


async def test_preparation_is_silent_beyond_the_window(session, linked_patient):
    session.add(make_milestone(scheduled_at=datetime(2026, 8, 20, 9, 0, 0, tzinfo=UTC)))
    await session.flush()

    assert await companion._immediate_preparation(session, PATIENT_ID, NOW) is None


async def test_preparation_is_silent_once_the_milestone_passed(session, linked_patient):
    session.add(
        make_milestone(
            scheduled_at=datetime(2026, 8, 13, 9, 0, 0, tzinfo=UTC), status="missed"
        )
    )
    await session.flush()

    preparation = await companion._immediate_preparation(session, PATIENT_ID, NOW)
    assert preparation is None


async def test_preparation_disappears_when_the_caregiver_disables_it(session, linked_patient):
    _, link = linked_patient
    enabled = dict(companion.DEFAULT_ENABLED)
    enabled["immediate_preparation"] = False
    session.add(
        PatientContentSettings(
            patient_id=PATIENT_ID,
            enabled_categories=enabled,
            show_immediate_preparation=False,
        )
    )
    session.add(make_milestone())
    await session.flush()

    view = await companion.build_companion_view(session, link, NOW)
    assert view["immediate_preparation"] is None


async def test_preparation_ignores_completed_milestones(session, linked_patient):
    session.add(make_milestone(status="completed", attendance_confirmed=True))
    await session.flush()

    assert await companion._immediate_preparation(session, PATIENT_ID, NOW) is None
