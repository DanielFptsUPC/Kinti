/**
 * Acceso a la base SQLite local.
 *
 * `expo-sqlite` se carga de forma perezosa para que las pruebas y el modo local
 * no necesiten el módulo nativo: quien no abre la base, no lo importa.
 */

import { migrate, type SqlDatabase } from "@/infrastructure/database/schema";

export const DATABASE_NAME = "kinti-local.db";

let instance: SqlDatabase | null = null;

export async function getDatabase(): Promise<SqlDatabase> {
  if (instance) return instance;

  const SQLite = await import("expo-sqlite");
  const db = (await SQLite.openDatabaseAsync(DATABASE_NAME)) as unknown as SqlDatabase;
  await migrate(db);
  instance = db;
  return instance;
}

/** Permite inyectar una base en memoria en las pruebas. */
export function setDatabaseForTesting(db: SqlDatabase | null): void {
  instance = db;
}
