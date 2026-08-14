/**
 * Modo conectado: caché SQLite + outbox + API.
 *
 * Cada comando sigue siempre el mismo camino, tenga o no conexión:
 *
 *   1. valida localmente lo que puede validarse;
 *   2. aplica la actualización optimista a la caché, para que la interfaz
 *      responda de inmediato;
 *   3. encola la operación con su `operationId`;
 *   4. deja el envío al motor de sincronización.
 *
 * Nunca se bloquea una solicitud de ayuda por falta de conexión.
 */

import { randomUUID } from "expo-crypto";

import type { BarrierAlert, EmotionKey, FeelingCheckIn, Milestone } from "@/domain/entities";
import type {
  CreateMilestoneInput,
  KintiRepository,
  KintiState,
  ReportBarrierInput,
  ResolveAlertInput,
} from "@/domain/repositories/KintiRepository";
import { applyOptimisticState, readState } from "@/infrastructure/database/cache";
import * as outbox from "@/infrastructure/database/outbox";
import type { SqlDatabase } from "@/infrastructure/database/schema";
import {
  confirmMilestoneAttendance,
  markFamilyContacted,
  rescheduleMilestone,
  resolveBarrierAlert,
} from "@/logic/alerts";

/** Prefijo de los identificadores creados por el cliente antes de que el servidor asigne el suyo. */
export const LOCAL_ID_PREFIX = "local:";

export function newOperationId(): string {
  return randomUUID();
}

export function isLocalId(id: string): boolean {
  return id.startsWith(LOCAL_ID_PREFIX);
}

export class RemoteRepository implements KintiRepository {
  readonly mode = "remote" as const;

  constructor(private readonly db: SqlDatabase) {}

  async load(): Promise<KintiState> {
    return readState(this.db);
  }

  private async commit(next: KintiState): Promise<KintiState> {
    await applyOptimisticState(this.db, next);
    return next;
  }

  private async enqueue(
    type: Parameters<typeof outbox.enqueue>[1]["type"],
    targetId: string,
    payload: Record<string, unknown> = {},
  ): Promise<string> {
    const operationId = newOperationId();
    await outbox.enqueue(this.db, { operationId, type, targetId, payload });
    return operationId;
  }

  // ------------------------------------------------------------- familia

  async confirmAttendance(milestoneId: string): Promise<KintiState> {
    const state = await this.load();
    await this.enqueue("confirm_attendance", milestoneId);
    return this.commit({
      ...state,
      milestones: state.milestones.map((m) =>
        m.id === milestoneId ? confirmMilestoneAttendance(m) : m,
      ),
    });
  }

  async reportBarrier(input: ReportBarrierInput): Promise<KintiState> {
    const state = await this.load();
    const operationId = await this.enqueue("report_barrier", input.milestoneId, {
      category: input.category,
      note: input.note,
    });

    // La alerta se muestra ya, con un id local; el servidor asignará el suyo y la
    // próxima instantánea canónica la reemplazará.
    const optimistic: BarrierAlert = {
      id: `${LOCAL_ID_PREFIX}${operationId}`,
      patientId: input.patientId,
      milestoneId: input.milestoneId,
      category: input.category,
      note: input.note?.trim() ? input.note.trim() : undefined,
      risk: "yellow",
      status: "open",
      familyContacted: false,
      createdAt: new Date().toISOString(),
    };

    return this.commit({
      ...state,
      alerts: [...state.alerts, optimistic],
      milestones: state.milestones.map((m) =>
        m.id === input.milestoneId && m.status !== "missed"
          ? { ...m, status: "support_needed" as const }
          : m,
      ),
    });
  }

  async recordFeeling(patientId: string, mood: EmotionKey): Promise<KintiState> {
    const state = await this.load();
    const operationId = await this.enqueue("record_feeling", patientId, { mood });

    const feeling: FeelingCheckIn = {
      id: `${LOCAL_ID_PREFIX}${operationId}`,
      patientId,
      mood,
      createdAt: new Date().toISOString(),
    };
    return this.commit({ ...state, feelings: [...state.feelings, feeling] });
  }

  // --------------------------------------------------- equipo asistencial

  async markFamilyContacted(alertId: string): Promise<KintiState> {
    const state = await this.load();
    await this.enqueue("mark_family_contacted", alertId);
    return this.commit({
      ...state,
      alerts: state.alerts.map((a) => (a.id === alertId ? markFamilyContacted(a) : a)),
    });
  }

  async resolveAlert(alertId: string, input: ResolveAlertInput): Promise<KintiState> {
    const state = await this.load();
    const target = state.alerts.find((a) => a.id === alertId);
    if (!target) return state;

    await this.enqueue("resolve_alert", alertId, {
      actionTaken: input.actionTaken,
      internalNote: input.internalNote,
      newScheduledAt: input.newScheduledAt,
    });

    const alerts = state.alerts.map((a) =>
      a.id === alertId ? resolveBarrierAlert(a, input) : a,
    );
    const milestones = state.milestones.map((m) => {
      if (m.id !== target.milestoneId) return m;
      if (input.newScheduledAt) return rescheduleMilestone(m, input.newScheduledAt);
      return m.status === "support_needed" ? { ...m, status: "upcoming" as const } : m;
    });

    return this.commit({ ...state, alerts, milestones });
  }

  async createMilestone(input: CreateMilestoneInput): Promise<KintiState> {
    const state = await this.load();
    const operationId = await this.enqueue("create_milestone", input.patientId, {
      type: input.type,
      title: input.title,
      scheduledAt: input.scheduledAt,
      location: input.location,
      preparation: input.preparation,
      service: input.service,
      confirmationDeadline: input.confirmationDeadline,
    });

    const milestone: Milestone = {
      id: `${LOCAL_ID_PREFIX}${operationId}`,
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
    return this.commit({ ...state, milestones: [...state.milestones, milestone] });
  }

  async rescheduleMilestone(milestoneId: string, newScheduledAt: string): Promise<KintiState> {
    const state = await this.load();
    await this.enqueue("reschedule_milestone", milestoneId, { newScheduledAt });
    return this.commit({
      ...state,
      milestones: state.milestones.map((m) =>
        m.id === milestoneId ? rescheduleMilestone(m, newScheduledAt) : m,
      ),
    });
  }

  async markNotificationRead(notificationId: string): Promise<KintiState> {
    const state = await this.load();
    // Marcar leído no es una operación de dominio: si falla, no se reintenta.
    return this.commit({
      ...state,
      notifications: state.notifications.map((n) =>
        n.id === notificationId ? { ...n, readAt: new Date().toISOString() } : n,
      ),
    });
  }
}
