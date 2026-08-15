/**
 * `child` es el atajo de la demostración local, donde nadie inicia sesión.
 * `patient` es la cuenta real del menor que emite el servidor: distinta del
 * cuidador, limitada a un único registro asistencial y sin alcance operativo.
 * Ambos llevan a la misma pantalla, **Mi espacio con Kinti**.
 */
export type Role = "child" | "patient" | "caregiver" | "care_team";

export type RouteStatus = "on_track" | "confirmation_needed" | "support_needed";

export type MilestoneStatus =
  | "completed"
  | "upcoming"
  | "unscheduled"
  | "support_needed"
  | "rescheduled"
  | "missed";

export type OperationalRisk = "green" | "yellow" | "red";

export type MilestoneType =
  | "consultation"
  | "laboratory"
  | "procedure"
  | "treatment"
  | "follow_up";

export const MILESTONE_TYPE_LABEL: Record<MilestoneType, string> = {
  consultation: "Consulta hematológica",
  laboratory: "Laboratorio",
  procedure: "Procedimiento",
  treatment: "Tratamiento",
  follow_up: "Control de seguimiento",
};

export interface Patient {
  id: string;
  displayName: string;
  age: number;
  avatarKey: string;
  routeStatus: RouteStatus;
  operationalRisk: OperationalRisk;
  contactPhone: string;
  caregiverName: string;
}

export interface Milestone {
  id: string;
  patientId: string;
  type: MilestoneType;
  title: string;
  scheduledAt?: string;
  location?: string;
  preparation?: string;
  service?: string;
  confirmationDeadline?: string;
  status: MilestoneStatus;
  attendanceConfirmed: boolean;
}

export type BarrierCategory =
  | "transport"
  | "lodging"
  | "financial"
  | "schedule"
  | "instructions"
  | "communication"
  | "health_difficulty"
  | "other";

export const BARRIER_CATEGORY_LABEL: Record<BarrierCategory, string> = {
  transport: "Transporte",
  lodging: "Alojamiento",
  financial: "Dificultad económica",
  schedule: "Fecha u horario",
  instructions: "No comprendí la indicación",
  communication: "No puedo comunicarme con el servicio",
  health_difficulty: "Dificultad de salud del niño",
  other: "Otra dificultad",
};

export type AlertActionType =
  | "guidance"
  | "reschedule"
  | "social_work_referral"
  | "lodging_coordination"
  | "transport_coordination"
  | "other";

export const ALERT_ACTION_LABEL: Record<AlertActionType, string> = {
  guidance: "Orientación",
  reschedule: "Reprogramación",
  social_work_referral: "Derivación a trabajo social",
  lodging_coordination: "Coordinación de alojamiento",
  transport_coordination: "Coordinación de transporte",
  other: "Otra acción",
};

export interface BarrierAlert {
  id: string;
  patientId: string;
  milestoneId: string;
  category: BarrierCategory;
  note?: string;
  risk: OperationalRisk;
  status: "open" | "in_progress" | "resolved";
  familyContacted: boolean;
  actionTaken?: AlertActionType;
  internalNote?: string;
  createdAt: string;
  resolvedAt?: string;
}

export type EmotionKey = "calm" | "unsure" | "worried" | "tired";

export const EMOTION_LABEL: Record<EmotionKey, string> = {
  calm: "Tranquilo",
  unsure: "Con dudas",
  worried: "Preocupado",
  tired: "Cansado",
};

export interface FeelingCheckIn {
  id: string;
  patientId: string;
  mood: EmotionKey;
  createdAt: string;
}

// ---------------------------------------------------------------- Kinti Voz

/**
 * Estados canónicos de una solicitud. `submitted` confirma únicamente que la
 * solicitud fue enviada; sólo `confirmed` representa una cita confirmada por
 * la agenda autorizada.
 */
export type AppointmentRequestStatus =
  | "draft"
  | "proposal_ready"
  | "awaiting_confirmation"
  | "submitted"
  | "confirmed"
  | "rejected"
  | "expired"
  | "human_handoff";

export type AppointmentRequestKind = "new" | "reschedule" | "consolidate";
export type AppointmentRequestSource = "voice" | "app" | "staff";

export interface AppointmentRequest {
  id: string;
  patientId: string;
  requestedBy: string;
  referralId: string | null;
  voiceSessionId: string | null;
  requestKind: AppointmentRequestKind;
  source: AppointmentRequestSource;
  status: AppointmentRequestStatus;
  selectedSlotId: string | null;
  proposalExpiresAt: string | null;
  externalResult: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface AppointmentSlot {
  id: string;
  service: string;
  site: string;
  spokenLocation: string;
  startsAt: string;
  endsAt: string;
  professionalKey: string;
  equivalenceGroup: string;
  availablePlaces: number;
  availabilityVersion: number;
  status: "available" | "blocked" | "cancelled";
  source: string;
}

export interface AppointmentHold {
  id: string;
  requestId: string;
  slotId: string;
  status: "held" | "consumed" | "expired" | "released";
  expiresAt: string;
  availabilityVersion: number;
}

export interface AppointmentProposals {
  request: AppointmentRequest;
  options: AppointmentSlot[];
}

export interface AppointmentConfirmation {
  request: AppointmentRequest;
  hold: AppointmentHold;
  /** El servidor conserva explícitamente la diferencia entre ambos desenlaces. */
  outcome: "submitted" | "confirmed";
}

export interface CreateAppointmentRequestInput {
  patientId: string;
  referralId?: string | null;
  requestKind?: AppointmentRequestKind;
  originRegion?: string | null;
  originProvince?: string | null;
  arrivalWindowStart?: string | null;
  arrivalWindowEnd?: string | null;
  returnDeadline?: string | null;
  travelMinutes?: number | null;
  needsLodging?: boolean;
  needsTransport?: boolean;
  canStayMoreThanOneDay?: boolean;
  operationId: string;
}

export interface PrepareAppointmentProposalsInput {
  operationId: string;
  maxOptions?: number;
}

export interface ConfirmAppointmentRequestInput {
  selectedSlotId: string;
  expectedAvailabilityVersion: number;
  confirmed: true;
  operationId: string;
}

export interface HandoffAppointmentRequestInput {
  reasonCode: VoiceCallbackReason;
  /** Referencia opaca del proveedor; nunca un teléfono en claro. */
  contactReference: string;
  operationId: string;
}

export type VoiceCallbackStatus =
  | "requested"
  | "assigned"
  | "completed"
  | "cancelled"
  | "expired";

export type VoiceCallbackReason =
  | "requested_by_caller"
  | "two_comprehension_failures"
  | "clinical_or_safety"
  | "recognition_failed_twice"
  | "workflow_handoff"
  | "provider_failed"
  | "runtime_recovery"
  | "manual_handoff"
  | "identity_unverified";

export interface VoiceCallbackRequest {
  id: string;
  voiceSessionId: string | null;
  actorId: string | null;
  patientId: string | null;
  reasonCode: VoiceCallbackReason;
  status: VoiceCallbackStatus;
  slaDueAt: string;
  assignedTo: string | null;
  completedAt: string | null;
  outcomeCode: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AppointmentHandoff {
  request: AppointmentRequest;
  callback: VoiceCallbackRequest;
}
