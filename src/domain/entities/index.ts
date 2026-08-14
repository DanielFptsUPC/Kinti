/**
 * Entidades del dominio.
 *
 * La Fase 1 las definió en `src/types`. Se re-exportan desde aquí para que el
 * código nuevo importe de `@/domain/entities` sin tener que mover todos los
 * archivos existentes de golpe; `src/types` sigue siendo la definición única.
 */

export * from "@/types";

/**
 * Usuario autenticado del piloto.
 *
 * Desde la Fase 4 el menor **sí** tiene credenciales propias (`patient`), con
 * un alias en vez de correo. Su sesión no comparte nada con la del cuidador.
 */
export interface SessionUser {
  id: string;
  email: string;
  displayName: string;
  role: "caregiver" | "care_team" | "patient";
}

// --------------------------------------------------------- Kinti Compañero

/** Banda de desarrollo que elige el cuidador; decide el catálogo y el tono. */
export type DevelopmentBand = "early" | "middle" | "adolescent";

export type CompanionCategory =
  | "breathing"
  | "music"
  | "drawing"
  | "stories"
  | "comfort_object"
  | "caregiver_messages"
  | "immediate_preparation";

export interface CompanionActivity {
  key: CompanionCategory;
  title: string;
  /** `0` significa «sin cronómetro»: la actividad dura lo que el niño quiera. */
  durationSeconds: number;
}

/**
 * Preparación inmediata (RF-NNA-12).
 *
 * Deliberadamente **no** tiene título ni tipo de hito: se dice cuándo, qué
 * llevar y con quién, nunca qué procedimiento es.
 */
export interface ImmediatePreparation {
  when: string;
  bring?: string | null;
  company: string;
}

/**
 * Todo lo que el menor puede ver, y nada más.
 *
 * Es una lista blanca cerrada: no incluye hitos, semáforos, alertas, barreras
 * ni riesgo. Añadir un campo aquí es una decisión explícita.
 */
export interface CompanionView {
  greeting: string;
  chosenName?: string | null;
  avatarKey?: string | null;
  comfortObject?: string | null;
  developmentBand: DevelopmentBand;
  activities: CompanionActivity[];
  immediatePreparation?: ImmediatePreparation | null;
}

/** Formas de pedir apoyo. El sistema las transmite; no interpreta su causa. */
export type SupportRequestType =
  | "want_to_talk"
  | "feeling_scared"
  | "need_help"
  | "want_company";

export const SUPPORT_REQUEST_LABEL: Record<SupportRequestType, string> = {
  want_to_talk: "Quiero hablar",
  feeling_scared: "Tengo miedo",
  need_help: "Necesito ayuda",
  want_company: "Quiero compañía",
};

/**
 * La cuenta del menor vista por el adulto que la administra.
 *
 * No expone el PIN ni ningún identificador de sesión: sirve para saber si la
 * cuenta está activa y qué contenido se le habilitó.
 */
export interface PatientAccount {
  patientId: string;
  alias: string;
  status: "active" | "suspended" | "locked";
  developmentBand: DevelopmentBand;
  enabledCategories: Record<string, boolean>;
  consentedAt?: string | null;
}

export interface SupportRequest {
  id: string;
  patientId: string;
  requestType: SupportRequestType;
  status: "open" | "acknowledged" | "closed";
  createdAt: string;
  acknowledgedAt?: string | null;
}

/** Aviso del centro de notificaciones interno. */
export interface AppNotification {
  id: string;
  type: string;
  patientId?: string;
  title: string;
  body: string;
  createdAt: string;
  readAt?: string;
}

/** Tipos de comando que el outbox puede reenviar al servidor. */
export type OperationType =
  | "confirm_attendance"
  | "report_barrier"
  | "record_feeling"
  | "mark_family_contacted"
  | "refer_social_work"
  | "resolve_alert"
  | "create_milestone"
  | "reschedule_milestone";

/** Una operación pendiente de sincronizar. */
export interface OutboxOperation {
  operationId: string;
  type: OperationType;
  targetId: string;
  payload: Record<string, unknown>;
  createdAt: string;
  attempts: number;
  /** Instante a partir del cual conviene reintentar (espera creciente). */
  nextAttemptAt: string;
  lastError?: string;
  /** Una operación rechazada deja de reintentarse sola y se muestra al usuario. */
  status: "pending" | "rejected";
}

export type SyncOperationStatus = "applied" | "already_applied" | "rejected";

export interface SyncOperationResult {
  operationId: string;
  status: SyncOperationStatus;
  errorCode?: string | null;
}

/** Instantánea canónica del servidor: reemplaza la caché completa. */
export interface Snapshot {
  user: SessionUser;
  patients: import("@/types").Patient[];
  milestones: import("@/types").Milestone[];
  alerts: import("@/types").BarrierAlert[];
  feelings: import("@/types").FeelingCheckIn[];
  notifications: AppNotification[];
  serverTime: string;
}

// --------------------------------------------------------------- asistente

export type AssistantIntent =
  | "institutional_faq"
  | "next_milestone_query"
  | "attendance_confirmation"
  | "report_barrier"
  | "request_callback"
  | "administrative_document_question"
  | "clinical_or_safety_concern"
  | "unknown";

export type AssistantConfidence = "supported" | "insufficient_evidence" | "refused";

/** Cita comprensible: título, versión y sección. Nunca una URL permanente. */
export interface AssistantCitation {
  chunkId: string;
  documentTitle: string;
  documentVersion: string;
  section?: string;
  page?: number;
}

export interface AssistantProposedAction {
  kind: "report_barrier" | "confirm_attendance" | "request_callback";
  /** Texto que se muestra para que la persona confirme conscientemente. */
  summary: string;
  payload?: Record<string, unknown>;
}

/** Respuesta del asistente, ya validada por el servidor. */
export interface AssistantMessage {
  messageId: string;
  intent: AssistantIntent;
  answer: string;
  citations: AssistantCitation[];
  confidence: AssistantConfidence;
  needsHuman: boolean;
  proposedAction?: AssistantProposedAction | null;
}

/** Turno tal como se pinta en pantalla. */
export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: AssistantCitation[];
  proposedAction?: AssistantProposedAction | null;
  needsHuman?: boolean;
  /** Un turno encolado sin conexión se muestra como pendiente, nunca respondido. */
  pending?: boolean;
  confirmed?: boolean;
}

// -------------------------------------------------- coordinación asistencial

export interface OperationalWorkloadRow {
  professionalId: string;
  professionalName: string;
  assignedPatients: number;
  redPatients: number;
  yellowPatients: number;
  openAlerts: number;
  missedMilestones: number;
  weightedLoad: number;
}

export interface WorkloadResponse {
  rows: OperationalWorkloadRow[];
  maxDifference: number;
  generatedAt: string;
  disclaimer: string;
}

export type CapacityState = "underused" | "balanced" | "high" | "overbooked";

export interface AmbulatoryCapacitySlot {
  id: string;
  service: string;
  startsAt: string;
  endsAt: string;
  availablePlaces: number;
  scheduledPatients: number;
  occupancyPercent: number;
  state: CapacityState;
}

export interface CapacityResponse {
  slots: AmbulatoryCapacitySlot[];
  generatedAt: string;
  disclaimer: string;
}

export type SocialWorkStatus = "pending" | "contacted" | "referred" | "resolved";

export interface SocialWorkQueueRow {
  alertId: string;
  patientId: string;
  patientName: string;
  category: import("@/types").BarrierCategory;
  alertStatus: "open" | "in_progress" | "resolved";
  coordinationStatus: SocialWorkStatus;
  familyContacted: boolean;
  createdAt: string;
}

export interface SocialWorkQueueResponse {
  rows: SocialWorkQueueRow[];
  generatedAt: string;
}

export interface OperationsDashboard {
  workload: WorkloadResponse;
  capacity: CapacityResponse;
  socialWork: SocialWorkQueueResponse;
}
