export type Role = "child" | "caregiver" | "care_team";

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
