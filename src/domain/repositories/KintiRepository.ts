/**
 * Puerto de datos.
 *
 * Es la única frontera entre las pantallas y el origen de los datos. El modo
 * local (Fase 1, sin backend) y el modo conectado (caché SQLite + outbox + API)
 * implementan este mismo contrato, de modo que ninguna pantalla necesita saber
 * en cuál está corriendo.
 *
 * Cada mutación devuelve el estado visible resultante: en modo conectado eso es
 * la actualización optimista, que después se reconcilia con la instantánea
 * canónica del servidor.
 */

import type {
  AppNotification,
  BarrierAlert,
  BarrierCategory,
  EmotionKey,
  FeelingCheckIn,
  Milestone,
  MilestoneType,
  Patient,
} from "@/domain/entities";

export interface KintiState {
  patients: Patient[];
  milestones: Milestone[];
  alerts: BarrierAlert[];
  feelings: FeelingCheckIn[];
  notifications: AppNotification[];
}

export const EMPTY_STATE: KintiState = {
  patients: [],
  milestones: [],
  alerts: [],
  feelings: [],
  notifications: [],
};

export interface ReportBarrierInput {
  patientId: string;
  milestoneId: string;
  category: BarrierCategory;
  note?: string;
}

export interface ResolveAlertInput {
  actionTaken: NonNullable<BarrierAlert["actionTaken"]>;
  internalNote?: string;
  newScheduledAt?: string;
}

export interface CreateMilestoneInput {
  patientId: string;
  type: MilestoneType;
  title: string;
  scheduledAt?: string;
  location?: string;
  preparation?: string;
  service?: string;
  confirmationDeadline?: string;
}

export interface KintiRepository {
  readonly mode: "local" | "remote";

  /** Estado inicial para pintar la interfaz. */
  load(): Promise<KintiState>;

  // --- comandos de la familia
  confirmAttendance(milestoneId: string): Promise<KintiState>;
  reportBarrier(input: ReportBarrierInput): Promise<KintiState>;
  recordFeeling(patientId: string, mood: EmotionKey): Promise<KintiState>;

  // --- comandos del equipo asistencial
  markFamilyContacted(alertId: string): Promise<KintiState>;
  resolveAlert(alertId: string, input: ResolveAlertInput): Promise<KintiState>;
  createMilestone(input: CreateMilestoneInput): Promise<KintiState>;
  rescheduleMilestone(milestoneId: string, newScheduledAt: string): Promise<KintiState>;

  markNotificationRead(notificationId: string): Promise<KintiState>;

  /**
   * Restaura los datos de demostración.
   * Sólo existe en modo local: nunca debe exponerse contra un backend.
   */
  resetDemoData?(): Promise<KintiState>;
}

export interface SyncSummary {
  applied: number;
  alreadyApplied: number;
  rejected: number;
  pending: number;
  syncedAt?: string;
  error?: string;
}

/** Motor de sincronización. En modo local no hay nada que enviar. */
export interface SyncPort {
  pendingCount(): Promise<number>;
  flush(): Promise<SyncSummary>;
}
