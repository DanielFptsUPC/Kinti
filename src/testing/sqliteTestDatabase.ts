/**
 * Base SQLite en memoria para las pruebas.
 *
 * Adapta `node:sqlite` a la misma interfaz que expone `expo-sqlite`, de modo que
 * el esquema, las migraciones, la caché y el outbox se ejercitan contra SQLite
 * de verdad y no contra un doble que reimplemente su comportamiento.
 */

import { DatabaseSync } from "node:sqlite";

import type { SqlDatabase } from "@/infrastructure/database/schema";
import { migrate } from "@/infrastructure/database/schema";

export interface TestDatabase extends SqlDatabase {
  close(): void;
}

export function createTestDatabase(): TestDatabase {
  const db = new DatabaseSync(":memory:");

  return {
    async execAsync(source: string): Promise<void> {
      db.exec(source);
    },

    async runAsync(source: string, params: unknown[] = []): Promise<unknown> {
      return db.prepare(source).run(...(params as never[]));
    },

    async getAllAsync<T>(source: string, params: unknown[] = []): Promise<T[]> {
      return db.prepare(source).all(...(params as never[])) as T[];
    },

    async getFirstAsync<T>(source: string, params: unknown[] = []): Promise<T | null> {
      const row = db.prepare(source).get(...(params as never[]));
      return (row ?? null) as T | null;
    },

    close(): void {
      db.close();
    },
  };
}

/** Base ya migrada, lista para usar. */
export async function createMigratedDatabase(): Promise<TestDatabase> {
  const db = createTestDatabase();
  await migrate(db);
  return db;
}
