/**
 * Esquema local SQLite y sus migraciones versionadas.
 *
 * La caché es una copia desechable de la instantánea del servidor: se puede
 * borrar entera sin perder nada. Lo que NO es desechable es `outbox_operations`
 * — ahí viven las solicitudes de la familia que todavía no llegaron al backend,
 * y perderlas equivaldría a descartar un pedido de ayuda.
 */

export interface SqlDatabase {
  execAsync(source: string): Promise<void>;
  runAsync(source: string, params?: unknown[]): Promise<unknown>;
  getAllAsync<T>(source: string, params?: unknown[]): Promise<T[]>;
  getFirstAsync<T>(source: string, params?: unknown[]): Promise<T | null>;
}

/** Cada entrada es una migración; el índice + 1 es su versión. */
export const MIGRATIONS: string[] = [
  // v1 — caché de dominio, outbox y metadatos de sincronización.
  `
  CREATE TABLE IF NOT EXISTS cached_patients (
    id TEXT PRIMARY KEY NOT NULL,
    data TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS cached_milestones (
    id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    data TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS cached_alerts (
    id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    data TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS cached_feelings (
    id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    data TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS cached_notifications (
    id TEXT PRIMARY KEY NOT NULL,
    data TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS outbox_operations (
    operation_id TEXT PRIMARY KEY NOT NULL,
    type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
  );
  CREATE INDEX IF NOT EXISTS idx_outbox_created ON outbox_operations (created_at);
  CREATE TABLE IF NOT EXISTS sync_metadata (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT
  );
  `,
];

export const SCHEMA_VERSION = MIGRATIONS.length;

/**
 * Aplica las migraciones que falten.
 *
 * Usa `PRAGMA user_version`, que SQLite guarda en la cabecera del archivo: es la
 * forma estándar de versionar un esquema local sin una tabla auxiliar.
 */
export async function migrate(db: SqlDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ user_version: number }>("PRAGMA user_version");
  const current = row?.user_version ?? 0;

  for (let version = current; version < MIGRATIONS.length; version += 1) {
    await db.execAsync(MIGRATIONS[version]);
  }

  if (current < MIGRATIONS.length) {
    await db.execAsync(`PRAGMA user_version = ${MIGRATIONS.length}`);
  }
  return MIGRATIONS.length;
}

/** Borra la caché pero conserva el outbox: las solicitudes pendientes no se tiran. */
export async function clearCache(db: SqlDatabase): Promise<void> {
  await db.execAsync(`
    DELETE FROM cached_patients;
    DELETE FROM cached_milestones;
    DELETE FROM cached_alerts;
    DELETE FROM cached_feelings;
    DELETE FROM cached_notifications;
  `);
}

/** Borrado total al cerrar sesión: no debe quedar nada de la sesión anterior. */
export async function clearAll(db: SqlDatabase): Promise<void> {
  await clearCache(db);
  await db.execAsync(`
    DELETE FROM outbox_operations;
    DELETE FROM sync_metadata;
  `);
}
