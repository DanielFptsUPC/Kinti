"""Simulador reproducible de llamadas de Kinti Voz.

Uso::

    python -m app.modules.voice.simulator approved-travel-repeat
    python -m app.modules.voice.simulator two-failures
    python -m app.modules.voice.simulator clinical
    python -m app.modules.voice.simulator all
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from app.modules.voice.fakes import FakeVoiceAppointmentWorkflow
from app.modules.voice.ports import InputModality, TurnInput, TurnOutput


@dataclass(frozen=True)
class ScenarioTurn:
    modality: InputModality
    value: str


SCENARIOS: dict[str, tuple[ScenarioTurn, ...]] = {
    "approved-travel-repeat": (
        ScenarioTurn("speech", "sí"),
        ScenarioTurn("speech", "quiero revisar la referencia"),
        ScenarioTurn("speech", "soy el cuidador de Mateo, clave 2468"),
        ScenarioTurn("speech", "Hospital Regional de Puno"),
        ScenarioTurn("speech", "Puno, San Román"),
        ScenarioTurn("speech", "veintitrés de agosto"),
        ScenarioTurn("speech", "veinticinco de agosto"),
        ScenarioTurn("speech", "sí"),
        ScenarioTurn("speech", "necesito alojamiento"),
        ScenarioTurn("speech", "repita más despacio"),
        ScenarioTurn("speech", "opción uno"),
        ScenarioTurn("speech", "sí"),
        ScenarioTurn("speech", "lunes veinticuatro de agosto"),
    ),
    "two-failures": (
        ScenarioTurn("speech", "tal vez"),
        ScenarioTurn("speech", "no sé qué responder"),
    ),
    "clinical": (
        ScenarioTurn("speech", "mi niño tiene fiebre y necesita una dosis"),
    ),
}


async def run_scenario(name: str, *, echo: bool = True) -> list[TurnOutput]:
    workflow = FakeVoiceAppointmentWorkflow()
    outputs = [await workflow.start(provider_session_id=f"simulated-{name}")]
    if echo:
        _print_output(outputs[-1])

    for index, scenario_turn in enumerate(SCENARIOS[name], start=1):
        if echo:
            print(f"PERSONA [{scenario_turn.modality}]: {scenario_turn.value}")
        output = await workflow.handle_turn(
            session_id=outputs[0].session_id,
            event_id=f"{name}-{index}",
            turn=TurnInput(modality=scenario_turn.modality, value=scenario_turn.value),
        )
        outputs.append(output)
        if echo:
            _print_output(output)
    return outputs


def _print_output(output: TurnOutput) -> None:
    print(f"KINTI [{output.state.value}, velocidad={output.speech_rate}]: {output.prompt}")


async def _main(selected: str) -> None:
    names = tuple(SCENARIOS) if selected == "all" else (selected,)
    for name in names:
        print(f"\n=== Escenario: {name} ===")
        await run_scenario(name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador determinista de Kinti Voz")
    parser.add_argument("scenario", choices=(*SCENARIOS, "all"), nargs="?", default="all")
    args = parser.parse_args()
    asyncio.run(_main(args.scenario))


if __name__ == "__main__":
    main()
