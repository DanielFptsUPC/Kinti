/**
 * Cola de operaciones pendientes de sincronizar.
 *
 * Es la pieza que hace que una solicitud de ayuda sobreviva a un corte de red y
 * a un reinicio de la aplicación. Nada se borra de aquí hasta que el servidor
 * confirma que la operación quedó aplicada (o que ya lo estaba).
 */

import type { OperationType, OutboxOperation } from "@/domain/entities";
import type { SqlDatabase } from "@/infrastructure/database/schema";

interface OutboxRow {
  operation_id: string;
  type: OperationType;
  target_id: string;
  payload: string;
  created_at: string;
  attempts: number;
  next_attempt_at: string;
  last_error: string | null;
  status: "pending" | "rejected";
}

/** Espera creciente entre reintentos, con techo para no dormir la cola. */
export const RETRY_BACKOFF_SECONDS = [0, 5, 15, 60, 300];

export function backoffSeconds(attempts: number): number {
  const index = Math.min(attempts, RETRY_BACKOFF_SECONDS.length - 1);
  return RETRY_BACKOFF_SECONDS[index];
}

function toOperation(row: OutboxRow): OutboxOperation {
  return {
    operationId: row.operation_id,
    type: row.type,
    targetId: row.target_id,
    payload: JSON.parse(row.payload) as Record<string, unknown>,
    createdAt: row.created_at,
    attempts: row.attempts,
    nextAttemptAt: row.next_attempt_at,
    lastError: row.last_error ?? undefined,
    status: row.status,
  };
}

export async function enqueue(
  db: SqlDatabase,
  operation: {
    operationId: string;
    type: OperationType;
    targetId: string;
    payload: Record<string, unknown>;
  },
  now: Date = new Date(),
): Promise<void> {
  const iso = now.toISOString();
  await db.runAsync(
    `INSERT OR IGNORE INTO outbox_operations
       (operation_id, type, target_id, payload, created_at, attempts, next_attempt_at, status)
     VALUES (?, ?, ?, ?, ?, 0, ?, 'pending')`,
    [
      operation.operationId,
      operation.type,
      operation.targetId,
      JSON.stringify(operation.payload),
      iso,
      iso,
    ],
  );
}

/** Operaciones listas para enviar, en el mismo orden en que el usuario actuó. */
export async function due(db: SqlDatabase, now: Date = new Date()): Promise<OutboxOperation[]> {
  const rows = await db.getAllAsync<OutboxRow>(
    `SELECT * FROM outbox_operations
      WHERE status = 'pending' AND next_attempt_at <= ?
      ORDER BY created_at ASC`,
    [now.toISOString()],
  );
  return rows.map(toOperation);
}

export async function all(db: SqlDatabase): Promise<OutboxOperation[]> {
  const rows = await db.getAllAsync<OutboxRow>(
    "SELECT * FROM outbox_operations ORDER BY created_at ASC",
  );
  return rows.map(toOperation);
}

/** Cuántas operaciones siguen esperando. Alimenta el indicador de la interfaz. */
export async function pendingCount(db: SqlDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ total: number }>(
    "SELECT COUNT(*) AS total FROM outbox_operations WHERE status = 'pending'",
  );
  return row?.total ?? 0;
}

export async function rejectedCount(db: SqlDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ total: number }>(
    "SELECT COUNT(*) AS total FROM outbox_operations WHERE status = 'rejected'",
  );
  return row?.total ?? 0;
}

/** El servidor la aplicó (o ya la tenía): se retira de la cola. */
export async function remove(db: SqlDatabase, operationId: string): Promise<void> {
  await db.runAsync("DELETE FROM outbox_operations WHERE operation_id = ?", [operationId]);
}

/**
 * Error temporal: se reintenta más tarde con espera creciente.
 */
export async function scheduleRetry(
  db: SqlDatabase,
  operationId: string,
  error: string,
  now: Date = new Date(),
): Promise<void> {
  const row = await db.getFirstAsync<{ attempts: number }>(
    "SELECT attempts FROM outbox_operations WHERE operation_id = ?",
    [operationId],
  );
  const attempts = (row?.attempts ?? 0) + 1;
  const nextAttempt = new Date(now.getTime() + backoffSeconds(attempts) * 1000);

  await db.runAsync(
    `UPDATE outbox_operations
        SET attempts = ?, next_attempt_at = ?, last_error = ?
      WHERE operation_id = ?`,
    [attempts, nextAttempt.toISOString(), error, operationId],
  );
}

/**
 * Rechazo definitivo (permiso o validación).
 *
 * No se reintenta sola y tampoco se borra en silencio: queda visible para que
 * la persona sepa que su solicitud no se registró. Nunca se descarta callando
 * un pedido de ayuda.
 */
export async function markRejected(
  db: SqlDatabase,
  operationId: string,
  errorCode: string,
): Promise<void> {
  await db.runAsync(
    "UPDATE outbox_operations SET status = 'rejected', last_error = ? WHERE operation_id = ?",
    [errorCode, operationId],
  );
}

/** El usuario reconoce el rechazo y lo descarta de la lista. */
export async function discard(db: SqlDatabase, operationId: string): Promise<void> {
  await db.runAsync(
    "DELETE FROM outbox_operations WHERE operation_id = ? AND status = 'rejected'",
    [operationId],
  );
}
