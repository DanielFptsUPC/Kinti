/**
 * Modo local: debe seguir comportándose como la Fase 1 y conservar el estado
 * que ya estuviera guardado en el dispositivo.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  LEGACY_STORAGE_KEY,
  LocalRepository,
} from "@/infrastructure/repositories/LocalRepository";

let repository: LocalRepository;

beforeEach(async () => {
  await AsyncStorage.clear();
  repository = new LocalRepository();
});

describe("load", () => {
  it("starts from the demo seed when there is nothing stored", async () => {
    const state = await repository.load();

    expect(state.patients.map((p) => p.displayName)).toEqual(["Lucía", "Mateo", "Valentina"]);
    expect(state.milestones.length).toBeGreaterThan(0);
  });

  it("writes the seed under the Phase 1 storage key", async () => {
    await repository.load();
    expect(await AsyncStorage.getItem(LEGACY_STORAGE_KEY)).not.toBeNull();
  });

  it("restores a state persisted by Phase 1", async () => {
    await AsyncStorage.setItem(
      LEGACY_STORAGE_KEY,
      JSON.stringify({
        state: {
          patients: [
            {
              id: "p-solo",
              displayName: "Paciente previo",
              age: 9,
              avatarKey: "x",
              routeStatus: "on_track",
              operationalRisk: "green",
              contactPhone: "+51 900 000 000 (ficticio)",
              caregiverName: "Cuidador previo",
            },
          ],
          milestones: [],
          alerts: [],
          feelings: [],
        },
        version: 0,
      }),
    );

    const state = await repository.load();
    expect(state.patients).toHaveLength(1);
    expect(state.patients[0].displayName).toBe("Paciente previo");
  });

  it("falls back to the demo instead of breaking on corrupted storage", async () => {
    await AsyncStorage.setItem(LEGACY_STORAGE_KEY, "{ esto no es json");

    const state = await repository.load();
    expect(state.patients).toHaveLength(3);
  });
});

describe("derived state", () => {
  it("recomputes the semaphore instead of trusting what was stored", async () => {
    const state = await repository.load();
    const lucia = state.patients.find((p) => p.displayName === "Lucía");
    const valentina = state.patients.find((p) => p.displayName === "Valentina");

    expect(lucia?.operationalRisk).toBe("green");
    expect(valentina?.operationalRisk).toBe("red");
  });
});

describe("commands", () => {
  it("confirming attendance turns the route green", async () => {
    const initial = await repository.load();
    const mateo = initial.patients.find((p) => p.displayName === "Mateo")!;
    const next = initial.milestones.find(
      (m) => m.patientId === mateo.id && m.status === "upcoming",
    )!;

    const state = await repository.confirmAttendance(next.id);
    const updated = state.patients.find((p) => p.id === mateo.id);

    expect(state.milestones.find((m) => m.id === next.id)?.attendanceConfirmed).toBe(true);
    expect(updated?.routeStatus).toBe("on_track");
    expect(updated?.operationalRisk).toBe("green");
  });

  it("reporting a barrier opens an alert and notifies the team", async () => {
    const initial = await repository.load();
    const mateo = initial.patients.find((p) => p.displayName === "Mateo")!;
    const next = initial.milestones.find(
      (m) => m.patientId === mateo.id && m.status === "upcoming",
    )!;

    const state = await repository.reportBarrier({
      patientId: mateo.id,
      milestoneId: next.id,
      category: "transport",
    });

    expect(state.alerts).toHaveLength(1);
    expect(state.alerts[0].status).toBe("open");
    expect(state.milestones.find((m) => m.id === next.id)?.status).toBe("support_needed");
    expect(state.notifications.some((n) => n.type === "barrier_received")).toBe(true);
  });

  it("resolving with a new date reschedules and reopens confirmation", async () => {
    const initial = await repository.load();
    const mateo = initial.patients.find((p) => p.displayName === "Mateo")!;
    const next = initial.milestones.find(
      (m) => m.patientId === mateo.id && m.status === "upcoming",
    )!;

    const reported = await repository.reportBarrier({
      patientId: mateo.id,
      milestoneId: next.id,
      category: "transport",
    });
    const newDate = new Date("2026-09-01T14:00:00.000Z").toISOString();

    const state = await repository.resolveAlert(reported.alerts[0].id, {
      actionTaken: "transport_coordination",
      newScheduledAt: newDate,
    });

    const milestone = state.milestones.find((m) => m.id === next.id);
    expect(state.alerts[0].status).toBe("resolved");
    expect(milestone?.status).toBe("rescheduled");
    expect(milestone?.scheduledAt).toBe(newDate);
    expect(milestone?.attendanceConfirmed).toBe(false);
  });

  it("persists across repository instances", async () => {
    const initial = await repository.load();
    const next = initial.milestones.find((m) => m.status === "upcoming")!;
    await repository.confirmAttendance(next.id);

    const reopened = new LocalRepository();
    const state = await reopened.load();

    expect(state.milestones.find((m) => m.id === next.id)?.attendanceConfirmed).toBe(true);
  });

  it("restores the demo data on request", async () => {
    const initial = await repository.load();
    const next = initial.milestones.find((m) => m.status === "upcoming")!;
    await repository.confirmAttendance(next.id);

    const state = await repository.resetDemoData();

    expect(state.alerts).toHaveLength(0);
    expect(state.notifications).toHaveLength(0);
    expect(state.patients).toHaveLength(3);
  });
});
