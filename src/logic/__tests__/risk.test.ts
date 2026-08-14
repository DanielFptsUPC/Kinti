import {
  BARRIER_RESPONSE_WINDOW_HOURS,
  computeMilestoneRisk,
  computePatientOperationalRisk,
  computeRouteStatus,
  getActiveMilestones,
  getNextMilestone,
} from "@/logic/risk";
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

describe("computeMilestoneRisk", () => {
  it("is green when confirmed and no barrier exists", () => {
    const milestone = makeMilestone({ attendanceConfirmed: true });
    expect(computeMilestoneRisk(milestone, [], NOW)).toBe("green");
  });

  it("is yellow when pending confirmation with no barrier", () => {
    const milestone = makeMilestone({ attendanceConfirmed: false });
    expect(computeMilestoneRisk(milestone, [], NOW)).toBe("yellow");
  });

  it("is yellow when a barrier was just reported (within the response window)", () => {
    const milestone = makeMilestone({ attendanceConfirmed: false });
    const alert = makeAlert({ createdAt: NOW.toISOString() });
    expect(computeMilestoneRisk(milestone, [alert], NOW)).toBe("yellow");
  });

  it("escalates to red once an open barrier passes the response window", () => {
    const milestone = makeMilestone({ attendanceConfirmed: false });
    const staleCreatedAt = new Date(
      NOW.getTime() - (BARRIER_RESPONSE_WINDOW_HOURS + 1) * 60 * 60 * 1000,
    ).toISOString();
    const alert = makeAlert({ createdAt: staleCreatedAt });
    expect(computeMilestoneRisk(milestone, [alert], NOW)).toBe("red");
  });

  it("stays yellow while a barrier is in progress, even past the window", () => {
    const milestone = makeMilestone({ attendanceConfirmed: false });
    const staleCreatedAt = new Date(
      NOW.getTime() - (BARRIER_RESPONSE_WINDOW_HOURS + 5) * 60 * 60 * 1000,
    ).toISOString();
    const alert = makeAlert({ status: "in_progress", createdAt: staleCreatedAt });
    expect(computeMilestoneRisk(milestone, [alert], NOW)).toBe("yellow");
  });

  it("is red when the milestone itself is missed, regardless of alerts", () => {
    const milestone = makeMilestone({ status: "missed", attendanceConfirmed: false });
    expect(computeMilestoneRisk(milestone, [], NOW)).toBe("red");
  });

  it("ignores resolved alerts", () => {
    const milestone = makeMilestone({ attendanceConfirmed: true });
    const alert = makeAlert({ status: "resolved" });
    expect(computeMilestoneRisk(milestone, [alert], NOW)).toBe("green");
  });

  it("is green for an unscheduled milestone: there is no date to confirm yet", () => {
    const milestone = makeMilestone({
      status: "unscheduled",
      scheduledAt: undefined,
      attendanceConfirmed: false,
    });
    expect(computeMilestoneRisk(milestone, [], NOW)).toBe("green");
  });

  it("still flags an unscheduled milestone that has an open barrier", () => {
    const milestone = makeMilestone({ status: "unscheduled", scheduledAt: undefined });
    expect(computeMilestoneRisk(milestone, [makeAlert()], NOW)).toBe("yellow");
  });
});

describe("getActiveMilestones / getNextMilestone", () => {
  it("excludes completed milestones and prioritizes missed over upcoming", () => {
    const completed = makeMilestone({ id: "m-done", status: "completed" });
    const upcoming = makeMilestone({
      id: "m-upcoming",
      status: "upcoming",
      scheduledAt: "2026-08-20T09:00:00.000Z",
    });
    const missed = makeMilestone({
      id: "m-missed",
      status: "missed",
      scheduledAt: "2026-08-01T09:00:00.000Z",
    });

    const active = getActiveMilestones("p-1", [completed, upcoming, missed]);
    expect(active.map((m) => m.id)).toEqual(["m-missed", "m-upcoming"]);
    expect(getNextMilestone("p-1", [completed, upcoming, missed])?.id).toBe("m-missed");
  });

  it("sorts upcoming milestones by the nearest scheduled date", () => {
    const soon = makeMilestone({ id: "m-soon", scheduledAt: "2026-08-13T09:00:00.000Z" });
    const later = makeMilestone({ id: "m-later", scheduledAt: "2026-09-01T09:00:00.000Z" });
    expect(getNextMilestone("p-1", [later, soon])?.id).toBe("m-soon");
  });
});

describe("computePatientOperationalRisk", () => {
  it("returns the worst-case risk across all active milestones", () => {
    const green = makeMilestone({ id: "m-green", attendanceConfirmed: true });
    const missed = makeMilestone({ id: "m-missed", status: "missed" });
    expect(computePatientOperationalRisk("p-1", [green, missed], [], NOW)).toBe("red");
  });

  it("is green when the patient has no active milestones", () => {
    const completed = makeMilestone({ status: "completed" });
    expect(computePatientOperationalRisk("p-1", [completed], [], NOW)).toBe("green");
  });
});

describe("computeRouteStatus", () => {
  it("is on_track when there is no next milestone", () => {
    expect(computeRouteStatus(undefined, [])).toBe("on_track");
  });

  it("is confirmation_needed when pending confirmation with no barrier", () => {
    const milestone = makeMilestone({ attendanceConfirmed: false });
    expect(computeRouteStatus(milestone, [])).toBe("confirmation_needed");
  });

  it("is support_needed when a barrier is open for the next milestone", () => {
    const milestone = makeMilestone({ status: "support_needed", attendanceConfirmed: false });
    const alert = makeAlert();
    expect(computeRouteStatus(milestone, [alert])).toBe("support_needed");
  });

  it("is on_track once confirmed and free of barriers", () => {
    const milestone = makeMilestone({ attendanceConfirmed: true });
    expect(computeRouteStatus(milestone, [])).toBe("on_track");
  });
});
