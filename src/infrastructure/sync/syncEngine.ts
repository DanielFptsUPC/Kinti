/**
 * Motor de sincronización.
 *
 * Envía el outbox en orden y después recupera la instantánea canónica. No hay
 * mezcla ni resolución de conflictos campo a campo: el servidor manda sobre
 * fechas oficiales y estados asistenciales, así que su instantánea reemplaza la
 * caché completa. Las acciones de la familia viajan como comandos, no como un
 * reemplazo de registros, y por eso no se pisan entre sí.
 */

import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import { writeMetadata, writeSnapshot } from "@/infrastructure/database/cache";
import * as outbox from "@/infrastructure/database/outbox";
import type { SqlDatabase } from "@/infrastructure/database/schema";
import type { SyncPort, SyncSummary } from "@/domain/repositories/KintiRepository";

export const LAST_SYNC_KEY = "lastSyncAt";

/** Tamaño máximo de lote; coincide con el límite que aplica el servidor. */
const MAX_BATCH = 50;

export class SyncEngine implements SyncPort {
  constructor(private readonly db: SqlDatabase) {}

  async pendingCount(): Promise<number> {
    return outbox.pendingCount(this.db);
  }

  async flush(): Promise<SyncSummary> {
    const summary: SyncSummary = { applied: 0, alreadyApplied: 0, rejected: 0, pending: 0 };

    const operations = (await outbox.due(this.db)).slice(0, MAX_BATCH);

    if (operations.length > 0) {
      try {
        const results = await api.pushOperations(
          operations.map((op) => ({
            operationId: op.operationId,
            type: op.type,
            targetId: op.targetId,
            payload: op.payload,
          })),
        );

        for (const result of results) {
          if (result.status === "applied") {
            summary.applied += 1;
            await outbox.remove(this.db, result.operationId);
          } else if (result.status === "already_applied") {
            // El reintento llegó dos veces: el servidor la reconoció y no duplicó nada.
            summary.alreadyApplied += 1;
            await outbox.remove(this.db, result.operationId);
          } else {
            // Permiso o validación: reintentarlo solo no arreglaría nada.
            summary.rejected += 1;
            await outbox.markRejected(this.db, result.operationId, result.errorCode ?? "rejected");
          }
        }
      } catch (error) {
        if (error instanceof NetworkError) {
          // Sin conexión: las operaciones siguen en la cola intactas.
          for (const op of operations) {
            await outbox.scheduleRetry(this.db, op.operationId, "network");
          }
          summary.pending = await this.pendingCount();
          summary.error = "offline";
          return summary;
        }
        if (error instanceof ApiError && error.isPermanent) {
          for (const op of operations) {
            await outbox.markRejected(this.db, op.operationId, error.code);
          }
          summary.rejected += operations.length;
        } else {
          for (const op of operations) {
            await outbox.scheduleRetry(this.db, op.operationId, "server_error");
          }
          summary.pending = await this.pendingCount();
          summary.error = "server_error";
          return summary;
        }
      }
    }

    // Instantánea canónica: es lo que reconcilia la interfaz sin duplicar entidades.
    try {
      const snapshot = await api.bootstrap();
      await writeSnapshot(this.db, snapshot);
      summary.syncedAt = snapshot.serverTime;
      await writeMetadata(this.db, LAST_SYNC_KEY, snapshot.serverTime);
    } catch (error) {
      summary.error = error instanceof NetworkError ? "offline" : "server_error";
    }

    summary.pending = await this.pendingCount();
    return summary;
  }
}

/** En modo local no hay nada que enviar: la cola siempre está vacía. */
export class NoopSyncEngine implements SyncPort {
  async pendingCount(): Promise<number> {
    return 0;
  }

  async flush(): Promise<SyncSummary> {
    return { applied: 0, alreadyApplied: 0, rejected: 0, pending: 0 };
  }
}
