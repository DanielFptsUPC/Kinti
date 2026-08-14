/**
 * Reglas del espacio Compañero, en paridad con `app/modules/companion/service.py`.
 *
 * Existen dos implementaciones porque hay dos modos de datos: contra el backend
 * la vista llega ya filtrada por el servidor, y en la demostración local se
 * construye aquí. La lista blanca debe ser **la misma** en ambos casos, o el
 * modo local acabaría enseñando lo que el conectado prohíbe. `companion.test.ts`
 * y `tests/test_companion_parity.py` verifican que no diverjan.
 */

import type {
  CompanionActivity,
  CompanionCategory,
  CompanionView,
  DevelopmentBand,
  ImmediatePreparation,
} from "@/domain/entities";
import type { Milestone } from "@/types";

/** Categorías habilitadas si el cuidador no ha configurado nada. */
export const DEFAULT_ENABLED: Record<CompanionCategory, boolean> = {
  breathing: true,
  music: true,
  drawing: true,
  stories: true,
  comfort_object: true,
  caregiver_messages: true,
  immediate_preparation: true,
};

/**
 * Catálogo por banda de desarrollo.
 *
 * El contenido está pendiente de revisión por Psicología (RF-NNA-14): esta
 * tabla aporta la estructura, no la aprobación clínica del texto.
 */
export const ACTIVITIES: Record<DevelopmentBand, CompanionActivity[]> = {
  early: [
    { key: "breathing", title: "Respira con Kinti", durationSeconds: 60 },
    { key: "music", title: "Una canción tranquila", durationSeconds: 120 },
    { key: "drawing", title: "Dibuja lo que quieras", durationSeconds: 0 },
  ],
  middle: [
    { key: "breathing", title: "Respira con Kinti", durationSeconds: 90 },
    { key: "music", title: "Música para calmarse", durationSeconds: 180 },
    { key: "drawing", title: "Dibuja cómo te sientes", durationSeconds: 0 },
    { key: "stories", title: "Un cuento corto", durationSeconds: 240 },
  ],
  adolescent: [
    { key: "breathing", title: "Respiración guiada", durationSeconds: 120 },
    { key: "music", title: "Elige tu música", durationSeconds: 0 },
    { key: "stories", title: "Una historia breve", durationSeconds: 300 },
  ],
};

export const GREETINGS: Record<DevelopmentBand, string> = {
  early: "¡Hola! Soy Kinti y hoy vuelo contigo.",
  middle: "Hola, soy Kinti. Estoy aquí contigo.",
  adolescent: "Hola. Soy Kinti; este espacio es tuyo.",
};

/** Ventana de la preparación inmediata: más allá es carga que no le toca al menor. */
export const PREPARATION_WINDOW_HOURS = 48;

export interface CompanionInput {
  developmentBand?: DevelopmentBand;
  enabledCategories?: Partial<Record<CompanionCategory, boolean>>;
  chosenName?: string | null;
  avatarKey?: string | null;
  comfortObject?: string | null;
  /** Hitos del paciente. Sólo se usan para decidir la preparación inmediata. */
  milestones?: Milestone[];
}

function formatWhen(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)} a las ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/**
 * Preparación inmediata sin nombre clínico del procedimiento (RF-NNA-04).
 *
 * Se busca el hito programado más próximo y sólo se anuncia si cae dentro de la
 * ventana. El `title` del hito nunca sale de esta función.
 */
export function buildImmediatePreparation(
  milestones: Milestone[],
  now: Date = new Date(),
): ImmediatePreparation | null {
  const upcoming = milestones
    .filter((m) => m.status !== "completed" && Boolean(m.scheduledAt))
    .map((m) => ({ milestone: m, at: new Date(m.scheduledAt as string) }))
    .filter(({ at }) => {
      const hours = (at.getTime() - now.getTime()) / 3_600_000;
      return hours >= 0 && hours <= PREPARATION_WINDOW_HOURS;
    })
    .sort((a, b) => a.at.getTime() - b.at.getTime())[0];

  if (!upcoming) return null;

  return {
    when: formatWhen(upcoming.milestone.scheduledAt as string),
    bring: upcoming.milestone.preparation ?? null,
    company: "Vas a ir con tu adulto de confianza.",
  };
}

/**
 * Construye la vista del menor por lista blanca.
 *
 * Recibe hitos para poder calcular la preparación inmediata, pero **no devuelve
 * ninguno**: lo que sale de aquí es exactamente `CompanionView`.
 */
export function buildCompanionView(
  input: CompanionInput,
  now: Date = new Date(),
): CompanionView {
  const band = input.developmentBand ?? "middle";
  const enabled = { ...DEFAULT_ENABLED, ...(input.enabledCategories ?? {}) };

  const activities = ACTIVITIES[band].filter((activity) => enabled[activity.key] !== false);

  const preparation =
    enabled.immediate_preparation !== false
      ? buildImmediatePreparation(input.milestones ?? [], now)
      : null;

  return {
    greeting: GREETINGS[band],
    chosenName: input.chosenName ?? null,
    avatarKey: input.avatarKey ?? null,
    comfortObject: input.comfortObject ?? null,
    developmentBand: band,
    activities,
    immediatePreparation: preparation,
  };
}
