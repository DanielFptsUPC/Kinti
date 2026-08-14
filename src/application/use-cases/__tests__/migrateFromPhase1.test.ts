import {
  CURRENT_MIGRATION_VERSION,
  MIGRATION_VERSION_KEY,
  migrateFromPhase1,
  type MigrationStorage,
} from "@/application/use-cases/migrateFromPhase1";
import { LEGACY_STORAGE_KEY } from "@/infrastructure/repositories/LocalRepository";

function memoryStorage(initial: Record<string, string> = {}): MigrationStorage & {
  dump(): Record<string, string>;
} {
  const data = { ...initial };
  return {
    async getItem(key) {
      return data[key] ?? null;
    },
    async setItem(key, value) {
      data[key] = value;
    },
    dump: () => ({ ...data }),
  };
}

const LEGACY_PAYLOAD = JSON.stringify({
  state: { patients: [], milestones: [], alerts: [], feelings: [] },
  version: 0,
});

describe("migrateFromPhase1", () => {
  it("runs once and records its version", async () => {
    const storage = memoryStorage();

    const first = await migrateFromPhase1(storage);
    const second = await migrateFromPhase1(storage);

    expect(first.ran).toBe(true);
    expect(second.ran).toBe(false);
    expect(storage.dump()[MIGRATION_VERSION_KEY]).toBe(CURRENT_MIGRATION_VERSION);
  });

  it("detects an existing Phase 1 state", async () => {
    const storage = memoryStorage({ [LEGACY_STORAGE_KEY]: LEGACY_PAYLOAD });

    const result = await migrateFromPhase1(storage);

    expect(result.legacyStateFound).toBe(true);
  });

  it("never deletes the Phase 1 state: local mode keeps reading it", async () => {
    const storage = memoryStorage({ [LEGACY_STORAGE_KEY]: LEGACY_PAYLOAD });

    await migrateFromPhase1(storage);

    expect(storage.dump()[LEGACY_STORAGE_KEY]).toBe(LEGACY_PAYLOAD);
  });

  it("reports when there was nothing to migrate", async () => {
    const result = await migrateFromPhase1(memoryStorage());
    expect(result.legacyStateFound).toBe(false);
  });
});
