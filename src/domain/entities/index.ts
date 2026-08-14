/**
 * Entidades del dominio.
 *
 * La Fase 1 las definió en `src/types`. Se re-exportan desde aquí para que el
 * código nuevo importe de `@/domain/entities` sin tener que mover todos los
 * archivos existentes de golpe; `src/types` sigue siendo la definición única.
 */

export * from "@/types";

/** Usuario autenticado del piloto. El niño no tiene credenciales propias. */
export interface SessionUser {
  id: string;
  email: string;
  displayName: string;
  role: "caregiver" | "care_team";
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
