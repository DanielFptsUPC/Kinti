/**
 * Modo local: la demostración de la Fase 1, sin backend.
 *
 * Conserva el mismo almacenamiento (`kinti-demo-storage`) y la misma forma de
 * los datos que la Fase 1, de manera que un dispositivo que ya venía usando la
 * aplicación no pierde su estado. Toda la lógica sigue viniendo de `src/logic`,
 * que es la implementación de referencia con la que el backend guarda paridad.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

import { SEED_ALERTS, SEED_FEELINGS, SEED_MILESTONES, SEED_PATIENTS } from "@/data/seed";
import type {
  AppNotification,
  BarrierAlert,
  EmotionKey,
  FeelingCheckIn,
  Milestone,
  Patient,
} from "@/domain/entities";
import type {
  CreateMilestoneInput,
  KintiRepository,
  KintiState,
  ReportBarrierInput,
  ResolveAlertInput,
} from "@/domain/repositories/KintiRepository";
import {
  confirmMilestoneAttendance,
  createBarrierAlert,
  markFamilyContacted,
  rescheduleMilestone,
  resolveBarrierAlert,
} from "@/logic/alerts";
import { computePatientOperationalRisk, computePatientRouteStatus } from "@/logic/risk";

/** Clave heredada de la Fase 1. No se renombra: es lo que permite conservar el estado. */
export const LEGACY_STORAGE_KEY = "kinti-demo-storage";

interface PersistedShape {
  state?: {
    selectedPatientId?: string;
    patients?: Patient[];
    milestones?: Milestone[];
    alerts?: BarrierAlert[];
    feelings?: FeelingCheckIn[];
    notifications?: AppNotification[];
  };
  version?: number;
}

function generateId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function recomputePatients(state: KintiState): Patient[] {
  return state.patients.map((patient) => ({
    ...patient,
    operationalRisk: computePatientOperationalRisk(patient.id, state.milestones, state.alerts),
    routeStatus: computePatientRouteStatus(patient.id, state.milestones, state.alerts),
  }));
}

function seedState(): KintiState {
  const base: KintiState = {
    patients: SEED_PATIENTS,
    milestones: SEED_MILESTONES,
    alerts: SEED_ALERTS,
    feelings: SEED_FEELINGS,
    notifications: [],
  };
  return { ...base, patients: recomputePatients(base) };
}

const NOTIFICATION_COPY: Record<string, { title: string; body: string }> = {
  barrier_received: {
    title: "Barrera reportada",
    body: "Una familia informó una dificultad y espera respuesta.",
  },
  alert_resolved: {
    title: "Solicitud atendida",
    body: "El equipo registró una acción sobre tu solicitud.",
  },
  milestone_rescheduled: {
    title: "Nueva fecha coordinada",
    body: "Tu ruta se actualizó con la nueva cita.",
  },
  confirmation_request: {
    title: "¿Podrán asistir?",
    body: "Confírmanos para que el equipo sepa cómo acompañarlos.",
  },
};

function notify(state: KintiState, type: string, patientId: string): AppNotification[] {
  const copy = NOTIFICATION_COPY[type];
  if (!copy) return state.notifications;
  return [
    {
      id: generateId("notif"),
      type,
      patientId,
      title: copy.title,
      body: copy.body,
      createdAt: new Date().toISOString(),
    },
    ...state.notifications,
  ];
}

export class LocalRepository implements KintiRepository {
  readonly mode = "local" as const;

  private state: KintiState | null = null;

  async load(): Promise<KintiState> {
    if (this.state) return this.state;

    const raw = await AsyncStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) {
      this.state = seedState();
      await this.persist();
      return this.state;
    }

    try {
      const parsed = JSON.parse(raw) as PersistedShape;
      const persisted = parsed.state ?? {};
      const restored: KintiState = {
        patients: persisted.patients ?? SEED_PATIENTS,
        milestones: persisted.milestones ?? SEED_MILESTONES,
        alerts: persisted.alerts ?? SEED_ALERTS,
        feelings: persisted.feelings ?? SEED_FEELINGS,
        // La Fase 1 no tenía notificaciones: se inicializan vacías.
        notifications: persisted.notifications ?? [],
      };
      this.state = { ...restored, patients: recomputePatients(restored) };
    } catch {
      // Estado corrupto: se vuelve a la demostración en vez de dejar la app rota.
      this.state = seedState();
    }
    return this.state;
  }

  private async commit(next: KintiState): Promise<KintiState> {
    this.state = { ...next, patients: recomputePatients(next) };
    await this.persist();
    return this.state;
  }

  private async persist(): Promise<void> {
    if (!this.state) return;
    const payload: PersistedShape = { state: { ...this.state }, version: 0 };
    await AsyncStorage.setItem(LEGACY_STORAGE_KEY, JSON.stringify(payload));
  }

  async confirmAttendance(milestoneId: string): Promise<KintiState> {
    const state = await this.load();
    return this.commit({
      ...state,
      milestones: state.milestones.map((m) =>
        m.id === milestoneId ? confirmMilestoneAttendance(m) : m,
      ),
    });
  }

  async reportBarrier(input: ReportBarrierInput): Promise<KintiState> {
    const state = await this.load();
    const alert = createBarrierAlert(input);
    const next: KintiState = {
      ...state,
      alerts: [...state.alerts, alert],
      milestones: state.milestones.map((m) =>
        m.id === input.milestoneId && m.status !== "missed"
          ? { ...m, status: "support_needed" as const }
          : m,
      ),
    };
    return this.commit({
      ...next,
      notifications: notify(next, "barrier_received", input.patientId),
    });
  }

  async recordFeeling(patientId: string, mood: EmotionKey): Promise<KintiState> {
    const state = await this.load();
    const feeling: FeelingCheckIn = {
      id: generateId("feeling"),
      patientId,
      mood,
      createdAt: new Date().toISOString(),
    };
    return this.commit({ ...state, feelings: [...state.feelings, feeling] });
  }

  async markFamilyContacted(alertId: string): Promise<KintiState> {
    const state = await this.load();
    return this.commit({
      ...state,
      alerts: state.alerts.map((a) => (a.id === alertId ? markFamilyContacted(a) : a)),
    });
  }

  async resolveAlert(alertId: string, input: ResolveAlertInput): Promise<KintiState> {
    const state = await this.load();
    const target = state.alerts.find((a) => a.id === alertId);
    if (!target) return state;

    const alerts = state.alerts.map((a) =>
      a.id === alertId ? resolveBarrierAlert(a, input) : a,
    );
    const milestones = state.milestones.map((m) => {
      if (m.id !== target.milestoneId) return m;
      if (input.newScheduledAt) return rescheduleMilestone(m, input.newScheduledAt);
      return m.status === "support_needed" ? { ...m, status: "upcoming" as const } : m;
    });

    let next: KintiState = { ...state, alerts, milestones };
    if (input.newScheduledAt) {
      next = { ...next, notifications: notify(next, "milestone_rescheduled", target.patientId) };
    }
    next = { ...next, notifications: notify(next, "alert_resolved", target.patientId) };
    return this.commit(next);
  }

  async createMilestone(input: CreateMilestoneInput): Promise<KintiState> {
    const state = await this.load();
    const milestone: Milestone = {
      id: generateId("m"),
      patientId: input.patientId,
      type: input.type,
      title: input.title,
      scheduledAt: input.scheduledAt,
      location: input.location,
      preparation: input.preparation,
      service: input.service,
      confirmationDeadline: input.confirmationDeadline,
      status: input.scheduledAt ? "upcoming" : "unscheduled",
      attendanceConfirmed: false,
    };
    const next: KintiState = { ...state, milestones: [...state.milestones, milestone] };
    return this.commit({
      ...next,
      notifications: notify(next, "confirmation_request", input.patientId),
    });
  }

  async rescheduleMilestone(milestoneId: string, newScheduledAt: string): Promise<KintiState> {
    const state = await this.load();
    const target = state.milestones.find((m) => m.id === milestoneId);
    const next: KintiState = {
      ...state,
      milestones: state.milestones.map((m) =>
        m.id === milestoneId ? rescheduleMilestone(m, newScheduledAt) : m,
      ),
    };
    return this.commit({
      ...next,
      notifications: target
        ? notify(next, "milestone_rescheduled", target.patientId)
        : next.notifications,
    });
  }

  async markNotificationRead(notificationId: string): Promise<KintiState> {
    const state = await this.load();
    return this.commit({
      ...state,
      notifications: state.notifications.map((n) =>
        n.id === notificationId ? { ...n, readAt: new Date().toISOString() } : n,
      ),
    });
  }

  async resetDemoData(): Promise<KintiState> {
    this.state = seedState();
    await this.persist();
    return this.state;
  }
}
