/**
 * Comportamiento del motor de sincronización frente a cada desenlace del
 * servidor. Lo que se prueba aquí es que un reintento nunca duplique una
 * solicitud y que un corte de red nunca la pierda.
 */

import type { Snapshot, SyncOperationResult } from "@/domain/entities";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import { readState } from "@/infrastructure/database/cache";
import { enqueue, pendingCount, rejectedCount } from "@/infrastructure/database/outbox";
import { SyncEngine } from "@/infrastructure/sync/syncEngine";
import { createMigratedDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";

jest.mock("@/infrastructure/api/client", () => {
  const actual = jest.requireActual("@/infrastructure/api/client");
  return {
    ...actual,
    api: {
      pushOperations: jest.fn(),
      bootstrap: jest.fn(),
      login: jest.fn(),
      logout: jest.fn(),
      markNotificationRead: jest.fn(),
    },
  };
});

const pushOperations = api.pushOperations as jest.Mock;
const bootstrap = api.bootstrap as jest.Mock;

const SERVER_TIME = "2026-08-13T12:30:00.000Z";

function emptySnapshot(): Snapshot {
  return {
    user: { id: "u-1", email: "cuidador@kinti.demo", displayName: "Jorge", role: "caregiver" },
    patients: [],
    milestones: [],
    alerts: [],
    feelings: [],
    notifications: [],
    serverTime: SERVER_TIME,
  };
}

let db: TestDatabase;
let engine: SyncEngine;

beforeEach(async () => {
  db = await createMigratedDatabase();
  engine = new SyncEngine(db);
  pushOperations.mockReset();
  bootstrap.mockReset();
  bootstrap.mockResolvedValue(emptySnapshot());
});

afterEach(() => {
  db.close();
});

async function queueBarrier(operationId = "op-1"): Promise<void> {
  await enqueue(db, {
    operationId,
    type: "report_barrier",
    targetId: "m-1",
    payload: { category: "transport" },
  });
}

function result(operationId: string, status: SyncOperationResult["status"], errorCode?: string) {
  return { operationId, status, errorCode: errorCode ?? null };
}

describe("flush", () => {
  it("removes an applied operation from the queue", async () => {
    await queueBarrier();
    pushOperations.mockResolvedValue([result("op-1", "applied")]);

    const summary = await engine.flush();

    expect(summary.applied).toBe(1);
    expect(summary.pending).toBe(0);
    expect(await pendingCount(db)).toBe(0);
  });

  it("treats a duplicate resend as already applied without queueing it again", async () => {
    await queueBarrier();
    pushOperations.mockResolvedValue([result("op-1", "already_applied")]);

    const summary = await engine.flush();

    expect(summary.alreadyApplied).toBe(1);
    expect(summary.applied).toBe(0);
    expect(await pendingCount(db)).toBe(0);
  });

  it("keeps the operation queued when the network is down", async () => {
    await queueBarrier();
    pushOperations.mockRejectedValue(new NetworkError());

    const summary = await engine.flush();

    expect(summary.error).toBe("offline");
    expect(summary.pending).toBe(1);
    // La solicitud sigue viva, sólo esperando.
    expect(await pendingCount(db)).toBe(1);
    expect(await rejectedCount(db)).toBe(0);
  });

  it("does not resend an operation that was already accepted", async () => {
    await queueBarrier();
    pushOperations.mockResolvedValue([result("op-1", "applied")]);
    await engine.flush();

    pushOperations.mockClear();
    await engine.flush();

    // El segundo intento ya no tiene nada que enviar: no hay duplicación posible.
    expect(pushOperations).not.toHaveBeenCalled();
  });

  it("marks a rejected operation instead of retrying it forever", async () => {
    await queueBarrier();
    pushOperations.mockResolvedValue([result("op-1", "rejected", "forbidden")]);

    const summary = await engine.flush();

    expect(summary.rejected).toBe(1);
    expect(await rejectedCount(db)).toBe(1);
    expect(await pendingCount(db)).toBe(0);
  });

  it("marks operations as rejected on a permanent API error", async () => {
    await queueBarrier();
    pushOperations.mockRejectedValue(new ApiError(403, "forbidden", "No permitido"));

    const summary = await engine.flush();

    expect(summary.rejected).toBe(1);
    expect(await rejectedCount(db)).toBe(1);
  });

  it("schedules a retry on a transient server error", async () => {
    await queueBarrier();
    pushOperations.mockRejectedValue(new ApiError(500, "server_error", "Falla temporal"));

    const summary = await engine.flush();

    expect(summary.error).toBe("server_error");
    expect(await pendingCount(db)).toBe(1);
  });
});

describe("reconciliation", () => {
  it("replaces the cache with the canonical snapshot", async () => {
    bootstrap.mockResolvedValue({
      ...emptySnapshot(),
      patients: [
        {
          id: "p-mateo",
          displayName: "Mateo",
          age: 11,
          avatarKey: "mateo",
          routeStatus: "on_track",
          operationalRisk: "green",
          contactPhone: "+51 900 000 002 (ficticio)",
          caregiverName: "Jorge, papá de Mateo",
        },
      ],
    });

    const summary = await engine.flush();

    expect(summary.syncedAt).toBe(SERVER_TIME);
    const state = await readState(db);
    expect(state.patients[0].displayName).toBe("Mateo");
  });

  it("reports offline when the snapshot cannot be fetched", async () => {
    bootstrap.mockRejectedValue(new NetworkError());

    const summary = await engine.flush();

    expect(summary.error).toBe("offline");
  });

  it("fetches the snapshot even with an empty queue", async () => {
    await engine.flush();
    expect(bootstrap).toHaveBeenCalledTimes(1);
  });
});

describe("pendingCount", () => {
  it("reflects what the sync indicator should show", async () => {
    expect(await engine.pendingCount()).toBe(0);

    await queueBarrier("op-1");
    await queueBarrier("op-2");

    expect(await engine.pendingCount()).toBe(2);
  });
});
