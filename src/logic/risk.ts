import type {
  BarrierAlert,
  Milestone,
  OperationalRisk,
  RouteStatus,
} from "@/types";

/** Simulated window a reported barrier has before it escalates to red. */
export const BARRIER_RESPONSE_WINDOW_HOURS = 48;

const ACTIVE_MILESTONE_PRIORITY: Record<Milestone["status"], number> = {
  missed: 0,
  support_needed: 1,
  upcoming: 2,
  rescheduled: 2,
  unscheduled: 3,
  completed: 99,
};

function hoursBetween(fromIso: string, now: Date): number {
  return (now.getTime() - new Date(fromIso).getTime()) / (1000 * 60 * 60);
}

function scheduledTime(milestone: Milestone): number {
  if (!milestone.scheduledAt) return Number.POSITIVE_INFINITY;
  return new Date(milestone.scheduledAt).getTime();
}

/** Non-completed milestones for a patient, ordered by how urgently they need attention. */
export function getActiveMilestones(
  patientId: string,
  milestones: Milestone[],
): Milestone[] {
  return milestones
    .filter((m) => m.patientId === patientId && m.status !== "completed")
    .sort((a, b) => {
      const priorityDiff =
        ACTIVE_MILESTONE_PRIORITY[a.status] - ACTIVE_MILESTONE_PRIORITY[b.status];
      if (priorityDiff !== 0) return priorityDiff;
      return scheduledTime(a) - scheduledTime(b);
    });
}

/** The milestone shown to the family as "tu siguiente paso". */
export function getNextMilestone(
  patientId: string,
  milestones: Milestone[],
): Milestone | undefined {
  return getActiveMilestones(patientId, milestones)[0];
}

function openAlertsFor(milestoneId: string, alerts: BarrierAlert[]): BarrierAlert[] {
  return alerts.filter(
    (a) => a.milestoneId === milestoneId && a.status !== "resolved",
  );
}

/**
 * Operational risk for a single milestone.
 * green: confirmed and no barrier reported.
 * yellow: pending confirmation or barrier reported.
 * red: missed activity, or a barrier still open past the simulated response window.
 */
export function computeMilestoneRisk(
  milestone: Milestone,
  alerts: BarrierAlert[],
  now: Date = new Date(),
): OperationalRisk {
  if (milestone.status === "missed") return "red";

  const openAlert = alerts.find(
    (a) => a.milestoneId === milestone.id && a.status === "open",
  );
  if (openAlert) {
    return hoursBetween(openAlert.createdAt, now) > BARRIER_RESPONSE_WINDOW_HOURS
      ? "red"
      : "yellow";
  }

  const hasInProgressAlert = alerts.some(
    (a) => a.milestoneId === milestone.id && a.status === "in_progress",
  );
  if (hasInProgressAlert || milestone.status === "support_needed") return "yellow";

  // Un hito sin fecha no está "pendiente de confirmación": no hay nada que
  // confirmar todavía. Sólo está pendiente de programación, y eso no pone en
  // riesgo la continuidad de la familia.
  if (milestone.status === "unscheduled") return "green";

  if (!milestone.attendanceConfirmed) return "yellow";

  return "green";
}

/** Worst-case operational risk across a patient's active milestones. */
export function computePatientOperationalRisk(
  patientId: string,
  milestones: Milestone[],
  alerts: BarrierAlert[],
  now: Date = new Date(),
): OperationalRisk {
  const active = getActiveMilestones(patientId, milestones);
  if (active.length === 0) return "green";
  const risks = active.map((m) => computeMilestoneRisk(m, alerts, now));
  if (risks.includes("red")) return "red";
  if (risks.includes("yellow")) return "yellow";
  return "green";
}

/** Route status shown to the family: what they need to do about their next step. */
export function computeRouteStatus(
  nextMilestone: Milestone | undefined,
  alerts: BarrierAlert[],
): RouteStatus {
  if (!nextMilestone) return "on_track";

  const hasOpenBarrier = openAlertsFor(nextMilestone.id, alerts).length > 0;
  if (
    hasOpenBarrier ||
    nextMilestone.status === "support_needed" ||
    nextMilestone.status === "missed"
  ) {
    return "support_needed";
  }
  if (!nextMilestone.attendanceConfirmed) return "confirmation_needed";
  return "on_track";
}

export function computePatientRouteStatus(
  patientId: string,
  milestones: Milestone[],
  alerts: BarrierAlert[],
): RouteStatus {
  return computeRouteStatus(getNextMilestone(patientId, milestones), alerts);
}
