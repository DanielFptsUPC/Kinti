/**
 * Lectura y escritura de la caché local.
 *
 * Las entidades se guardan como JSON en una columna `data`, con los campos que
 * hacen falta para filtrar (`patient_id`) promovidos a columnas. Para el volumen
 * del piloto es suficiente y evita tener que migrar el esquema cada vez que el
 * contrato de la API gana un campo.
 */

import type {
  AppNotification,
  BarrierAlert,
  FeelingCheckIn,
  Milestone,
  Patient,
  Snapshot,
} from "@/domain/entities";
import type { KintiState } from "@/domain/repositories/KintiRepository";
import type { SqlDatabase } from "@/infrastructure/database/schema";

interface Row {
  data: string;
}

function parseAll<T>(rows: Row[]): T[] {
  return rows.map((row) => JSON.parse(row.data) as T);
}

export async function readState(db: SqlDatabase): Promise<KintiState> {
  const [patients, milestones, alerts, feelings, notifications] = await Promise.all([
    db.getAllAsync<Row>("SELECT data FROM cached_patients"),
    db.getAllAsync<Row>("SELECT data FROM cached_milestones"),
    db.getAllAsync<Row>("SELECT data FROM cached_alerts"),
    db.getAllAsync<Row>("SELECT data FROM cached_feelings"),
    db.getAllAsync<Row>("SELECT data FROM cached_notifications"),
  ]);

  return {
    patients: parseAll<Patient>(patients),
    milestones: parseAll<Milestone>(milestones),
    alerts: parseAll<BarrierAlert>(alerts),
    feelings: parseAll<FeelingCheckIn>(feelings),
    notifications: parseAll<AppNotification>(notifications),
  };
}

/**
 * Reemplaza la caché con la instantánea canónica del servidor.
 *
 * Es un reemplazo completo, no una mezcla: el servidor manda sobre fechas
 * oficiales y estados asistenciales, así que cualquier resto local que no venga
 * en la instantánea debe desaparecer. Lo que sobrevive es el outbox.
 */
export async function writeSnapshot(db: SqlDatabase, snapshot: Snapshot): Promise<void> {
  await db.execAsync(`
    DELETE FROM cached_patients;
    DELETE FROM cached_milestones;
    DELETE FROM cached_alerts;
    DELETE FROM cached_feelings;
    DELETE FROM cached_notifications;
  `);

  for (const patient of snapshot.patients) {
    await db.runAsync("INSERT INTO cached_patients (id, data) VALUES (?, ?)", [
      patient.id,
      JSON.stringify(patient),
    ]);
  }
  for (const milestone of snapshot.milestones) {
    await db.runAsync(
      "INSERT INTO cached_milestones (id, patient_id, data) VALUES (?, ?, ?)",
      [milestone.id, milestone.patientId, JSON.stringify(milestone)],
    );
  }
  for (const alert of snapshot.alerts) {
    await db.runAsync("INSERT INTO cached_alerts (id, patient_id, data) VALUES (?, ?, ?)", [
      alert.id,
      alert.patientId,
      JSON.stringify(alert),
    ]);
  }
  for (const feeling of snapshot.feelings) {
    await db.runAsync("INSERT INTO cached_feelings (id, patient_id, data) VALUES (?, ?, ?)", [
      feeling.id,
      feeling.patientId,
      JSON.stringify(feeling),
    ]);
  }
  for (const notification of snapshot.notifications) {
    await db.runAsync("INSERT INTO cached_notifications (id, data) VALUES (?, ?)", [
      notification.id,
      JSON.stringify(notification),
    ]);
  }
}

/**
 * Aplica una actualización optimista sobre la caché.
 *
 * Escribe el estado que el usuario acaba de provocar para que la interfaz
 * responda de inmediato, incluso sin conexión. La verdad definitiva llega
 * después con `writeSnapshot`.
 */
export async function applyOptimisticState(db: SqlDatabase, state: KintiState): Promise<void> {
  await writeSnapshot(db, {
    ...state,
    user: { id: "", email: "", displayName: "", role: "caregiver" },
    serverTime: new Date().toISOString(),
  } as Snapshot);
}

export async function readMetadata(db: SqlDatabase, key: string): Promise<string | null> {
  const row = await db.getFirstAsync<{ value: string | null }>(
    "SELECT value FROM sync_metadata WHERE key = ?",
    [key],
  );
  return row?.value ?? null;
}

export async function writeMetadata(
  db: SqlDatabase,
  key: string,
  value: string | null,
): Promise<void> {
  await db.runAsync(
    "INSERT INTO sync_metadata (key, value) VALUES (?, ?) " +
      "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
    [key, value],
  );
}
