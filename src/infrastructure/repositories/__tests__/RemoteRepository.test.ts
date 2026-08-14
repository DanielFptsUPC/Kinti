/**
 * Modo conectado: cada comando debe verse de inmediato en la interfaz y quedar
 * encolado, tenga o no conexión.
 */

import { writeSnapshot } from "@/infrastructure/database/cache";
import { all, pendingCount } from "@/infrastructure/database/outbox";
import {
  LOCAL_ID_PREFIX,
  RemoteRepository,
} from "@/infrastructure/repositories/RemoteRepository";
import { createMigratedDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";
import type { Snapshot } from "@/domain/entities";

// `expo-crypto` se simula globalmente en `jest.setup.js`.
const MILESTONE = {
  id: "m-1",
  patientId: "p-mateo",
  type: "follow_up" as const,
  title: "Control hematológico",
  status: "upcoming" as const,
  attendanceConfirmed: false,
};

function snapshot(): Snapshot {
  return {
    user: { id: "u-1", email: "cuidador@kinti.demo", displayName: "Jorge", role: "caregiver" },
    patients: [
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
    ],
    milestones: [MILESTONE],
    alerts: [],
    feelings: [],
    notifications: [],
    serverTime: "2026-08-13T12:00:00.000Z",
  };
}

let db: TestDatabase;
let repository: RemoteRepository;

beforeEach(async () => {
  db = await createMigratedDatabase();
  await writeSnapshot(db, snapshot());
  repository = new RemoteRepository(db);
});

afterEach(() => {
  db.close();
});

describe("confirmAttendance", () => {
  it("updates the cache optimistically and queues the operation", async () => {
    const state = await repository.confirmAttendance("m-1");

    expect(state.milestones[0].attendanceConfirmed).toBe(true);

    const queued = await all(db);
    expect(queued).toHaveLength(1);
    expect(queued[0].type).toBe("confirm_attendance");
    expect(queued[0].targetId).toBe("m-1");
  });

  it("survives a reload: the optimistic state was written to SQLite", async () => {
    await repository.confirmAttendance("m-1");

    const reopened = new RemoteRepository(db);
    const state = await reopened.load();

    expect(state.milestones[0].attendanceConfirmed).toBe(true);
    expect(await pendingCount(db)).toBe(1);
  });
});

describe("reportBarrier", () => {
  it("shows the alert right away with a local identifier", async () => {
    const state = await repository.reportBarrier({
      patientId: "p-mateo",
      milestoneId: "m-1",
      category: "transport",
      note: "  Sin pasajes  ",
    });

    expect(state.alerts).toHaveLength(1);
    expect(state.alerts[0].id.startsWith(LOCAL_ID_PREFIX)).toBe(true);
    expect(state.alerts[0].note).toBe("Sin pasajes");
    expect(state.milestones[0].status).toBe("support_needed");
  });

  it("queues the barrier with its category, so nothing is lost offline", async () => {
    await repository.reportBarrier({
      patientId: "p-mateo",
      milestoneId: "m-1",
      category: "transport",
    });

    const [queued] = await all(db);
    expect(queued.type).toBe("report_barrier");
    expect(queued.payload).toMatchObject({ category: "transport" });
  });

  it("gives every report its own operationId", async () => {
    await repository.reportBarrier({
      patientId: "p-mateo",
      milestoneId: "m-1",
      category: "transport",
    });
    await repository.reportBarrier({
      patientId: "p-mateo",
      milestoneId: "m-1",
      category: "lodging",
    });

    const queued = await all(db);
    expect(new Set(queued.map((q) => q.operationId)).size).toBe(2);
  });
});

describe("care team commands", () => {
  it("queues a reschedule and applies the new date locally", async () => {
    const newDate = "2026-09-01T14:00:00.000Z";
    const state = await repository.rescheduleMilestone("m-1", newDate);

    expect(state.milestones[0].status).toBe("rescheduled");
    expect(state.milestones[0].scheduledAt).toBe(newDate);
    expect(state.milestones[0].attendanceConfirmed).toBe(false);

    const [queued] = await all(db);
    expect(queued.type).toBe("reschedule_milestone");
    expect(queued.payload).toMatchObject({ newScheduledAt: newDate });
  });

  it("queues a new milestone as unscheduled when it has no date", async () => {
    const state = await repository.createMilestone({
      patientId: "p-mateo",
      type: "follow_up",
      title: "Control de seguimiento",
    });

    const created = state.milestones.find((m) => m.title === "Control de seguimiento");
    expect(created?.status).toBe("unscheduled");
    expect((await all(db))[0].type).toBe("create_milestone");
  });
});

describe("feelings", () => {
  it("records the mood locally and queues it", async () => {
    const state = await repository.recordFeeling("p-mateo", "worried");

    expect(state.feelings).toHaveLength(1);
    expect(state.feelings[0].mood).toBe("worried");
    // Nunca crea una alerta: acompaña, no diagnostica.
    expect(state.alerts).toHaveLength(0);
    expect((await all(db))[0].type).toBe("record_feeling");
  });
});
