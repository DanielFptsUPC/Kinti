import {
  backoffSeconds,
  discard,
  due,
  enqueue,
  markRejected,
  pendingCount,
  rejectedCount,
  remove,
  scheduleRetry,
} from "@/infrastructure/database/outbox";
import { createMigratedDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";

const NOW = new Date("2026-08-13T12:00:00.000Z");

let db: TestDatabase;

beforeEach(async () => {
  db = await createMigratedDatabase();
});

afterEach(() => {
  db.close();
});

function operation(overrides: Partial<Parameters<typeof enqueue>[1]> = {}) {
  return {
    operationId: "op-1",
    type: "report_barrier" as const,
    targetId: "m-1",
    payload: { category: "transport" },
    ...overrides,
  };
}

describe("enqueue", () => {
  it("stores the operation with its payload intact", async () => {
    await enqueue(db, operation(), NOW);

    const [stored] = await due(db, NOW);
    expect(stored.operationId).toBe("op-1");
    expect(stored.type).toBe("report_barrier");
    expect(stored.targetId).toBe("m-1");
    expect(stored.payload).toEqual({ category: "transport" });
    expect(stored.status).toBe("pending");
  });

  it("ignores a repeated operationId instead of queueing it twice", async () => {
    await enqueue(db, operation(), NOW);
    await enqueue(db, operation(), NOW);

    expect(await pendingCount(db)).toBe(1);
  });

  it("survives being re-read: the queue is what persists across restarts", async () => {
    await enqueue(db, operation(), NOW);

    // Releer desde cero equivale a reabrir la aplicación.
    expect(await pendingCount(db)).toBe(1);
    expect((await due(db, NOW))[0].payload).toEqual({ category: "transport" });
  });
});

describe("due", () => {
  it("returns operations in the order the person performed them", async () => {
    await enqueue(db, operation({ operationId: "op-1" }), new Date("2026-08-13T10:00:00.000Z"));
    await enqueue(db, operation({ operationId: "op-2" }), new Date("2026-08-13T11:00:00.000Z"));

    expect((await due(db, NOW)).map((o) => o.operationId)).toEqual(["op-1", "op-2"]);
  });

  it("withholds an operation whose retry time has not arrived", async () => {
    await enqueue(db, operation(), NOW);
    await scheduleRetry(db, "op-1", "network", NOW);

    expect(await due(db, NOW)).toHaveLength(0);
    // Sigue pendiente: esperar no es perderla.
    expect(await pendingCount(db)).toBe(1);
  });

  it("returns it again once the backoff elapses", async () => {
    await enqueue(db, operation(), NOW);
    await scheduleRetry(db, "op-1", "network", NOW);

    const later = new Date(NOW.getTime() + 60_000);
    expect(await due(db, later)).toHaveLength(1);
  });
});

describe("backoffSeconds", () => {
  it("grows with each attempt and then holds at its ceiling", () => {
    expect(backoffSeconds(1)).toBeLessThan(backoffSeconds(2));
    expect(backoffSeconds(2)).toBeLessThan(backoffSeconds(3));
    expect(backoffSeconds(99)).toBe(backoffSeconds(4));
  });
});

describe("outcomes", () => {
  it("removes an operation the server applied", async () => {
    await enqueue(db, operation(), NOW);
    await remove(db, "op-1");

    expect(await pendingCount(db)).toBe(0);
  });

  it("keeps a rejected operation visible instead of discarding it silently", async () => {
    await enqueue(db, operation(), NOW);
    await markRejected(db, "op-1", "forbidden");

    expect(await pendingCount(db)).toBe(0);
    expect(await rejectedCount(db)).toBe(1);
    // Y no se reintenta sola.
    expect(await due(db, NOW)).toHaveLength(0);
  });

  it("only discards a rejected operation when it is acknowledged", async () => {
    await enqueue(db, operation(), NOW);

    await discard(db, "op-1");
    expect(await pendingCount(db)).toBe(1);

    await markRejected(db, "op-1", "forbidden");
    await discard(db, "op-1");
    expect(await rejectedCount(db)).toBe(0);
  });

  it("counts attempts so the retry keeps backing off", async () => {
    await enqueue(db, operation(), NOW);
    await scheduleRetry(db, "op-1", "network", NOW);
    await scheduleRetry(db, "op-1", "network", NOW);

    const [stored] = await due(db, new Date(NOW.getTime() + 3_600_000));
    expect(stored.attempts).toBe(2);
    expect(stored.lastError).toBe("network");
  });
});
