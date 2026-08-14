import type {
  AlertActionType,
  BarrierAlert,
  BarrierCategory,
  Milestone,
} from "@/types";

function generateId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export interface CreateBarrierAlertInput {
  patientId: string;
  milestoneId: string;
  category: BarrierCategory;
  note?: string;
}

/** Reporting a barrier always creates an open alert; the semaphore escalates it later if unresolved. */
export function createBarrierAlert(
  input: CreateBarrierAlertInput,
  now: Date = new Date(),
): BarrierAlert {
  return {
    id: generateId("alert"),
    patientId: input.patientId,
    milestoneId: input.milestoneId,
    category: input.category,
    note: input.note?.trim() ? input.note.trim() : undefined,
    risk: "yellow",
    status: "open",
    familyContacted: false,
    createdAt: now.toISOString(),
  };
}

/** Marking the family as contacted moves an open alert into progress. */
export function markFamilyContacted(alert: BarrierAlert): BarrierAlert {
  return {
    ...alert,
    familyContacted: true,
    status: alert.status === "open" ? "in_progress" : alert.status,
  };
}

/** La derivación cambia el responsable operativo, pero no cierra la barrera. */
export function referAlertToSocialWork(
  alert: BarrierAlert,
  internalNote?: string,
): BarrierAlert {
  if (alert.status === "resolved") return alert;
  return {
    ...alert,
    status: "in_progress",
    actionTaken: "social_work_referral",
    internalNote: internalNote?.trim() ? internalNote.trim() : alert.internalNote,
  };
}

export interface ResolveBarrierAlertInput {
  actionTaken: AlertActionType;
  internalNote?: string;
}

export function resolveBarrierAlert(
  alert: BarrierAlert,
  input: ResolveBarrierAlertInput,
  now: Date = new Date(),
): BarrierAlert {
  return {
    ...alert,
    status: "resolved",
    actionTaken: input.actionTaken,
    internalNote: input.internalNote?.trim() ? input.internalNote.trim() : alert.internalNote,
    resolvedAt: now.toISOString(),
  };
}

/** Applying a new date closes the loop: the milestone re-enters the family route as rescheduled. */
export function rescheduleMilestone(
  milestone: Milestone,
  newScheduledAt: string,
): Milestone {
  return {
    ...milestone,
    status: "rescheduled",
    scheduledAt: newScheduledAt,
    attendanceConfirmed: false,
  };
}

export function confirmMilestoneAttendance(milestone: Milestone): Milestone {
  return {
    ...milestone,
    attendanceConfirmed: true,
    status: milestone.status === "unscheduled" ? "upcoming" : milestone.status,
  };
}
