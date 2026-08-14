/**
 * Reglas del espacio Compañero.
 *
 * Paridad con `backend/tests/test_companion_parity.py`: cada caso de aquí tiene
 * su traducción literal allí, con los mismos valores y el mismo reloj fijo. Si
 * una de las dos implementaciones cambia sin la otra, una de las dos suites cae.
 */

import {
  ACTIVITIES,
  buildCompanionView,
  buildImmediatePreparation,
  GREETINGS,
} from "@/domain/rules/companion";
import type { Milestone } from "@/types";

const NOW = new Date("2026-08-14T12:00:00.000Z");

function milestone(overrides: Partial<Milestone> = {}): Milestone {
  return {
    id: "m-1",
    patientId: "p-1",
    type: "procedure",
    title: "Procedimiento ambulatorio",
    scheduledAt: "2026-08-15T09:00:00.000Z",
    preparation: "Ayuno de 8 horas y tu peluche",
    status: "upcoming",
    attendanceConfirmed: false,
    ...overrides,
  };
}

// ------------------------------------------------------------ lista blanca

describe("la vista del menor", () => {
  it("expone exactamente los campos permitidos y ninguno más", () => {
    const view = buildCompanionView({ milestones: [milestone()] }, NOW);

    expect(Object.keys(view).sort()).toEqual([
      "activities",
      "avatarKey",
      "chosenName",
      "comfortObject",
      "developmentBand",
      "greeting",
      "immediatePreparation",
    ]);
  });

  it("no filtra el nombre clínico del procedimiento", () => {
    const view = buildCompanionView({ milestones: [milestone()] }, NOW);
    expect(JSON.stringify(view)).not.toContain("Procedimiento ambulatorio");
  });

  it("no incluye ningún hito, aunque los reciba para calcular la preparación", () => {
    const view = buildCompanionView({ milestones: [milestone()] }, NOW) as unknown as Record<
      string,
      unknown
    >;
    expect(view.milestones).toBeUndefined();
    expect(view.operationalRisk).toBeUndefined();
    expect(view.routeStatus).toBeUndefined();
  });

  it("usa la banda media por defecto", () => {
    const view = buildCompanionView({}, NOW);
    expect(view.developmentBand).toBe("middle");
    expect(view.greeting).toBe(GREETINGS.middle);
  });
});

// -------------------------------------------------------- catálogo y filtros

describe("las actividades", () => {
  it("cambian con la banda de desarrollo", () => {
    const early = buildCompanionView({ developmentBand: "early" }, NOW);
    expect(early.activities.map((a) => a.key)).toEqual(["breathing", "music", "drawing"]);

    const adolescent = buildCompanionView({ developmentBand: "adolescent" }, NOW);
    expect(adolescent.activities.map((a) => a.key)).toEqual(["breathing", "music", "stories"]);
  });

  it("respetan lo que el cuidador deshabilita, sin arrastrar a las demás", () => {
    const view = buildCompanionView({ enabledCategories: { stories: false } }, NOW);
    const keys = view.activities.map((a) => a.key);

    expect(keys).not.toContain("stories");
    expect(keys).toContain("breathing");
    expect(keys).toContain("music");
  });

  it("están todas habilitadas si el cuidador no configuró nada", () => {
    const view = buildCompanionView({}, NOW);
    expect(view.activities).toHaveLength(ACTIVITIES.middle.length);
  });
});

// ------------------------------------------------------ preparación inmediata

describe("la preparación inmediata", () => {
  it("dice cuándo, qué llevar y con quién — y nada más", () => {
    const preparation = buildImmediatePreparation([milestone()], NOW);
    expect(preparation).not.toBeNull();
    expect(Object.keys(preparation as object).sort()).toEqual(["bring", "company", "when"]);
    expect(preparation?.bring).toBe("Ayuno de 8 horas y tu peluche");
  });

  it("calla si el hito está más allá de 48 horas", () => {
    const distant = milestone({ scheduledAt: "2026-08-20T09:00:00.000Z" });
    expect(buildImmediatePreparation([distant], NOW)).toBeNull();
  });

  it("calla si el hito ya pasó", () => {
    const past = milestone({ scheduledAt: "2026-08-13T09:00:00.000Z" });
    expect(buildImmediatePreparation([past], NOW)).toBeNull();
  });

  it("elige el más próximo dentro de la ventana", () => {
    const later = milestone({ id: "m-later", scheduledAt: "2026-08-16T09:00:00.000Z" });
    const sooner = milestone({
      id: "m-sooner",
      scheduledAt: "2026-08-14T18:00:00.000Z",
      preparation: "Tu carnet",
    });

    expect(buildImmediatePreparation([later, sooner], NOW)?.bring).toBe("Tu carnet");
  });

  it("desaparece si el cuidador deshabilita esa categoría", () => {
    const view = buildCompanionView(
      { milestones: [milestone()], enabledCategories: { immediate_preparation: false } },
      NOW,
    );
    expect(view.immediatePreparation).toBeNull();
  });

  it("ignora los hitos ya completados", () => {
    const done = milestone({ status: "completed" });
    expect(buildImmediatePreparation([done], NOW)).toBeNull();
  });
});
