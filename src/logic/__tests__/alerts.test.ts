import {
  confirmMilestoneAttendance,
  createBarrierAlert,
  markFamilyContacted,
  referAlertToSocialWork,
  rescheduleMilestone,
  resolveBarrierAlert,
} from "@/logic/alerts";
import { computeRouteStatus } from "@/logic/risk";
import type { BarrierAlert, Milestone } from "@/types";

const NOW = new Date("2026-08-12T12:00:00.000Z");

function makeMilestone(overrides: Partial<Milestone> = {}): Milestone {
  return {
    id: "m-1",
    patientId: "p-1",
    type: "follow_up",
    title: "Control hematológico",
    status: "upcoming",
    attendanceConfirmed: false,
    scheduledAt: "2026-08-15T09:00:00.000Z",
    ...overrides,
  };
}

describe("createBarrierAlert", () => {
  it("creates an open alert with yellow risk and a trimmed note", () => {
    const alert = createBarrierAlert(
      { patientId: "p-1", milestoneId: "m-1", category: "transport", note: "  Sin pasaje  " },
      NOW,
    );
    expect(alert.status).toBe("open");
    expect(alert.risk).toBe("yellow");
    expect(alert.familyContacted).toBe(false);
    expect(alert.note).toBe("Sin pasaje");
    expect(alert.createdAt).toBe(NOW.toISOString());
  });

  it("omits an empty note instead of storing whitespace", () => {
    const alert = createBarrierAlert(
      { patientId: "p-1", milestoneId: "m-1", category: "other", note: "   " },
      NOW,
    );
    expect(alert.note).toBeUndefined();
  });
});

describe("markFamilyContacted", () => {
  function makeAlert(overrides: Partial<BarrierAlert> = {}): BarrierAlert {
    return {
      id: "a-1",
      patientId: "p-1",
      milestoneId: "m-1",
      category: "transport",
      risk: "yellow",
      status: "open",
      familyContacted: false,
      createdAt: NOW.toISOString(),
      ...overrides,
    };
  }

  it("moves an open alert into progress", () => {
    const alert = markFamilyContacted(makeAlert({ status: "open" }));
    expect(alert.status).toBe("in_progress");
    expect(alert.familyContacted).toBe(true);
  });

  it("does not change the status of an already resolved alert", () => {
    const alert = markFamilyContacted(makeAlert({ status: "resolved" }));
    expect(alert.status).toBe("resolved");
    expect(alert.familyContacted).toBe(true);
  });
});

describe("referAlertToSocialWork", () => {
  it("keeps the alert in progress instead of resolving it", () => {
    const alert: BarrierAlert = {
      id: "a-social",
      patientId: "p-1",
      milestoneId: "m-1",
      category: "financial",
      risk: "yellow",
      status: "open",
      familyContacted: false,
      createdAt: NOW.toISOString(),
    };
    const referred = referAlertToSocialWork(alert, " Evaluar apoyo de traslado ");
    expect(referred.status).toBe("in_progress");
    expect(referred.actionTaken).toBe("social_work_referral");
    expect(referred.internalNote).toBe("Evaluar apoyo de traslado");
    expect(referred.resolvedAt).toBeUndefined();
  });
});

describe("resolveBarrierAlert", () => {
  it("closes the alert with the chosen action and a resolved timestamp", () => {
    const alert: BarrierAlert = {
      id: "a-1",
      patientId: "p-1",
      milestoneId: "m-1",
      category: "transport",
      risk: "yellow",
      status: "in_progress",
      familyContacted: true,
      createdAt: "2026-08-10T09:00:00.000Z",
    };
    const resolved = resolveBarrierAlert(
      alert,
      { actionTaken: "transport_coordination", internalNote: "Se coordinó movilidad" },
      NOW,
    );
    expect(resolved.status).toBe("resolved");
    expect(resolved.actionTaken).toBe("transport_coordination");
    expect(resolved.internalNote).toBe("Se coordinó movilidad");
    expect(resolved.resolvedAt).toBe(NOW.toISOString());
  });
});

describe("rescheduleMilestone / confirmMilestoneAttendance", () => {
  it("rescheduling clears the previous confirmation and updates the date", () => {
    const milestone = makeMilestone({ status: "support_needed", attendanceConfirmed: false });
    const rescheduled = rescheduleMilestone(milestone, "2026-09-01T09:00:00.000Z");
    expect(rescheduled.status).toBe("rescheduled");
    expect(rescheduled.scheduledAt).toBe("2026-09-01T09:00:00.000Z");
    expect(rescheduled.attendanceConfirmed).toBe(false);
  });

  it("confirming attendance promotes an unscheduled milestone to upcoming", () => {
    const milestone = makeMilestone({ status: "unscheduled" });
    const confirmed = confirmMilestoneAttendance(milestone);
    expect(confirmed.attendanceConfirmed).toBe(true);
    expect(confirmed.status).toBe("upcoming");
  });
});

describe("end-to-end: reporting and resolving a barrier updates route status", () => {
  it("takes the family from support_needed back to confirmation_needed after resolution", () => {
    let milestone = makeMilestone({ status: "upcoming", attendanceConfirmed: false });
    const alert = createBarrierAlert(
      { patientId: "p-1", milestoneId: milestone.id, category: "transport" },
      NOW,
    );
    milestone = { ...milestone, status: "support_needed" };

    expect(computeRouteStatus(milestone, [alert])).toBe("support_needed");

    const resolvedAlert = resolveBarrierAlert(
      alert,
      { actionTaken: "transport_coordination", internalNote: "Movilidad coordinada" },
      NOW,
    );
    milestone = { ...milestone, status: "upcoming" };

    expect(computeRouteStatus(milestone, [resolvedAlert])).toBe("confirmation_needed");
  });
});
