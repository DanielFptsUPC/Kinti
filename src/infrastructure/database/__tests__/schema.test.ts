import { clearAll, clearCache, migrate, SCHEMA_VERSION } from "@/infrastructure/database/schema";
import { createTestDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";

let db: TestDatabase;

beforeEach(() => {
  db = createTestDatabase();
});

afterEach(() => {
  db.close();
});

async function tableNames(): Promise<string[]> {
  const rows = await db.getAllAsync<{ name: string }>(
    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name",
  );
  return rows.map((row) => row.name);
}

describe("migrate", () => {
  it("creates the cache, outbox and metadata tables", async () => {
    await migrate(db);
    expect(await tableNames()).toEqual(
      expect.arrayContaining([
        "cached_alerts",
        "cached_feelings",
        "cached_milestones",
        "cached_notifications",
        "cached_patients",
        "outbox_operations",
        "sync_metadata",
      ]),
    );
  });

  it("records the schema version so it does not re-run", async () => {
    await migrate(db);
    const row = await db.getFirstAsync<{ user_version: number }>("PRAGMA user_version");
    expect(row?.user_version).toBe(SCHEMA_VERSION);
  });

  it("is safe to run repeatedly", async () => {
    await migrate(db);
    await db.runAsync("INSERT INTO cached_patients (id, data) VALUES (?, ?)", ["p-1", "{}"]);

    await migrate(db);

    const rows = await db.getAllAsync("SELECT id FROM cached_patients");
    expect(rows).toHaveLength(1);
  });
});

describe("clearing", () => {
  beforeEach(async () => {
    await migrate(db);
    await db.runAsync("INSERT INTO cached_patients (id, data) VALUES (?, ?)", ["p-1", "{}"]);
    await db.runAsync(
      `INSERT INTO outbox_operations
         (operation_id, type, target_id, payload, created_at, next_attempt_at)
       VALUES ('op-1', 'report_barrier', 'm-1', '{}', '2026-08-13T00:00:00.000Z', '2026-08-13T00:00:00.000Z')`,
    );
  });

  it("clearCache keeps pending operations: a help request is never dropped", async () => {
    await clearCache(db);

    expect(await db.getAllAsync("SELECT id FROM cached_patients")).toHaveLength(0);
    expect(await db.getAllAsync("SELECT operation_id FROM outbox_operations")).toHaveLength(1);
  });

  it("clearAll wipes everything, as required on sign out", async () => {
    await clearAll(db);

    expect(await db.getAllAsync("SELECT id FROM cached_patients")).toHaveLength(0);
    expect(await db.getAllAsync("SELECT operation_id FROM outbox_operations")).toHaveLength(0);
    expect(await db.getAllAsync("SELECT key FROM sync_metadata")).toHaveLength(0);
  });
});
