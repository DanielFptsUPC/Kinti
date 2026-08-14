import type { BarrierAlert, FeelingCheckIn, Milestone, Patient } from "@/types";

function atOffset(days: number, hour = 9, minute = 0): string {
  const date = new Date();
  date.setHours(hour, minute, 0, 0);
  date.setDate(date.getDate() + days);
  return date.toISOString();
}

export const SEED_PATIENTS: Patient[] = [
  {
    id: "p-lucia",
    displayName: "Lucía",
    age: 8,
    avatarKey: "lucia",
    routeStatus: "on_track",
    operationalRisk: "green",
    contactPhone: "+51 900 000 001 (ficticio)",
    caregiverName: "Rosa, mamá de Lucía",
  },
  {
    id: "p-mateo",
    displayName: "Mateo",
    age: 11,
    avatarKey: "mateo",
    routeStatus: "confirmation_needed",
    operationalRisk: "yellow",
    contactPhone: "+51 900 000 002 (ficticio)",
    caregiverName: "Jorge, papá de Mateo",
  },
  {
    id: "p-valentina",
    displayName: "Valentina",
    age: 6,
    avatarKey: "valentina",
    routeStatus: "support_needed",
    operationalRisk: "red",
    contactPhone: "+51 900 000 003 (ficticio)",
    caregiverName: "Milagros, mamá de Valentina",
  },
];

export const SEED_MILESTONES: Milestone[] = [
  // Lucía — verde: próximo control confirmado
  {
    id: "m-lucia-1",
    patientId: "p-lucia",
    type: "consultation",
    title: "Consulta hematológica inicial",
    scheduledAt: atOffset(-30),
    location: "Consulta externa — Piso 3",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-lucia-2",
    patientId: "p-lucia",
    type: "laboratory",
    title: "Laboratorio de control",
    scheduledAt: atOffset(-20),
    location: "Laboratorio central",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-lucia-3",
    patientId: "p-lucia",
    type: "procedure",
    title: "Procedimiento ambulatorio",
    scheduledAt: atOffset(-10),
    location: "Sala de procedimientos",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-lucia-4",
    patientId: "p-lucia",
    type: "follow_up",
    title: "Control hematológico",
    scheduledAt: atOffset(5, 9, 30),
    location: "Consulta externa — Piso 3, consultorio 5",
    preparation: "Acudir en ayunas de 4 horas.",
    service: "Hematología pediátrica",
    confirmationDeadline: atOffset(3),
    status: "upcoming",
    attendanceConfirmed: true,
  },
  {
    id: "m-lucia-5",
    patientId: "p-lucia",
    type: "follow_up",
    title: "Control de seguimiento",
    service: "Hematología pediátrica",
    status: "unscheduled",
    attendanceConfirmed: false,
  },
];

const mateoMilestones: Milestone[] = [
  {
    id: "m-mateo-1",
    patientId: "p-mateo",
    type: "consultation",
    title: "Consulta hematológica inicial",
    scheduledAt: atOffset(-25),
    location: "Consulta externa — Piso 3",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-mateo-2",
    patientId: "p-mateo",
    type: "laboratory",
    title: "Laboratorio de control",
    scheduledAt: atOffset(-15),
    location: "Laboratorio central",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-mateo-3",
    patientId: "p-mateo",
    type: "procedure",
    title: "Procedimiento ambulatorio",
    scheduledAt: atOffset(-5),
    location: "Sala de procedimientos",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-mateo-4",
    patientId: "p-mateo",
    type: "follow_up",
    title: "Control hematológico",
    scheduledAt: atOffset(2, 10, 0),
    location: "Consulta externa — Piso 3, consultorio 2",
    preparation: "Traer el último resultado de laboratorio.",
    service: "Hematología pediátrica",
    confirmationDeadline: atOffset(1),
    status: "upcoming",
    attendanceConfirmed: false,
  },
  {
    id: "m-mateo-5",
    patientId: "p-mateo",
    type: "follow_up",
    title: "Control de seguimiento",
    service: "Hematología pediátrica",
    status: "unscheduled",
    attendanceConfirmed: false,
  },
];

const valentinaMilestones: Milestone[] = [
  {
    id: "m-valentina-1",
    patientId: "p-valentina",
    type: "consultation",
    title: "Consulta hematológica inicial",
    scheduledAt: atOffset(-40),
    location: "Consulta externa — Piso 3",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-valentina-2",
    patientId: "p-valentina",
    type: "laboratory",
    title: "Laboratorio de control",
    scheduledAt: atOffset(-28),
    location: "Laboratorio central",
    service: "Hematología pediátrica",
    status: "completed",
    attendanceConfirmed: true,
  },
  {
    id: "m-valentina-3",
    patientId: "p-valentina",
    type: "follow_up",
    title: "Control hematológico",
    scheduledAt: atOffset(-4, 9, 0),
    location: "Consulta externa — Piso 3, consultorio 1",
    preparation: "Acudir en ayunas de 4 horas.",
    service: "Hematología pediátrica",
    confirmationDeadline: atOffset(-5),
    status: "missed",
    attendanceConfirmed: false,
  },
  {
    id: "m-valentina-4",
    patientId: "p-valentina",
    type: "procedure",
    title: "Procedimiento ambulatorio",
    service: "Hematología pediátrica",
    status: "unscheduled",
    attendanceConfirmed: false,
  },
];

SEED_MILESTONES.push(...mateoMilestones, ...valentinaMilestones);

export const SEED_ALERTS: BarrierAlert[] = [];

export const SEED_FEELINGS: FeelingCheckIn[] = [];
