import {
  readMetadata,
  readState,
  writeMetadata,
  writeSnapshot,
} from "@/infrastructure/database/cache";
import { enqueue, pendingCount } from "@/infrastructure/database/outbox";
import { createMigratedDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";
import type { Snapshot } from "@/domain/entities";

let db: TestDatabase;

beforeEach(async () => {
  db = await createMigratedDatabase();
});

afterEach(() => {
  db.close();
});

function snapshot(overrides: Partial<Snapshot> = {}): Snapshot {
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
    milestones: [
      {
        id: "m-1",
        patientId: "p-mateo",
        type: "follow_up",
        title: "Control hematológico",
        status: "upcoming",
        attendanceConfirmed: false,
      },
    ],
    alerts: [],
    feelings: [],
    notifications: [],
    serverTime: "2026-08-13T12:00:00.000Z",
    ...overrides,
  };
}

describe("writeSnapshot / readState", () => {
  it("round-trips the canonical snapshot", async () => {
    await writeSnapshot(db, snapshot());

    const state = await readState(db);
    expect(state.patients).toHaveLength(1);
    expect(state.patients[0].displayName).toBe("Mateo");
    expect(state.milestones[0].title).toBe("Control hematológico");
  });

  it("replaces the cache rather than merging into it", async () => {
    await writeSnapshot(db, snapshot());

    // El servidor manda: lo que ya no viene en la instantánea desaparece.
    await writeSnapshot(db, snapshot({ patients: [], milestones: [] }));

    const state = await readState(db);
    expect(state.patients).toHaveLength(0);
    expect(state.milestones).toHaveLength(0);
  });

  it("does not touch the outbox when reconciling", async () => {
    await enqueue(db, {
      operationId: "op-1",
      type: "report_barrier",
      targetId: "m-1",
      payload: {},
    });

    await writeSnapshot(db, snapshot());

    expect(await pendingCount(db)).toBe(1);
  });

  it("reconciles a locally created alert without duplicating it", async () => {
    await writeSnapshot(
      db,
      snapshot({
        alerts: [
          {
            id: "local:op-1",
            patientId: "p-mateo",
            milestoneId: "m-1",
            category: "transport",
            risk: "yellow",
            status: "open",
            familyContacted: false,
            createdAt: "2026-08-13T12:00:00.000Z",
          },
        ],
      }),
    );

    // El servidor devuelve la misma alerta con su identificador definitivo.
    await writeSnapshot(
      db,
      snapshot({
        alerts: [
          {
            id: "server-uuid",
            patientId: "p-mateo",
            milestoneId: "m-1",
            category: "transport",
            risk: "yellow",
            status: "open",
            familyContacted: false,
            createdAt: "2026-08-13T12:00:00.000Z",
          },
        ],
      }),
    );

    const state = await readState(db);
    expect(state.alerts).toHaveLength(1);
    expect(state.alerts[0].id).toBe("server-uuid");
  });
});

describe("metadata", () => {
  it("stores and overwrites a value", async () => {
    await writeMetadata(db, "lastSyncAt", "2026-08-13T12:00:00.000Z");
    expect(await readMetadata(db, "lastSyncAt")).toBe("2026-08-13T12:00:00.000Z");

    await writeMetadata(db, "lastSyncAt", "2026-08-13T13:00:00.000Z");
    expect(await readMetadata(db, "lastSyncAt")).toBe("2026-08-13T13:00:00.000Z");
  });

  it("returns null for an unknown key", async () => {
    expect(await readMetadata(db, "desconocida")).toBeNull();
  });
});
