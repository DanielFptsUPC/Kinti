/**
 * Composición de la infraestructura según el modo de ejecución.
 *
 * Este es el **único** lugar donde se decide entre modo local y conectado. Las
 * pantallas y el estado global reciben un `KintiRepository` y un `SyncPort` sin
 * saber cuál es cuál.
 */

import { env } from "@/config/env";
import type { KintiRepository, SyncPort } from "@/domain/repositories/KintiRepository";
import { getDatabase } from "@/infrastructure/database";
import type { SqlDatabase } from "@/infrastructure/database/schema";
import { LocalRepository } from "@/infrastructure/repositories/LocalRepository";
import { RemoteRepository } from "@/infrastructure/repositories/RemoteRepository";
import { NoopSyncEngine, SyncEngine } from "@/infrastructure/sync/syncEngine";

export interface Container {
  repository: KintiRepository;
  sync: SyncPort;
  /** Sólo existe en modo conectado. */
  database: SqlDatabase | null;
}

let container: Container | null = null;

export async function getContainer(): Promise<Container> {
  if (container) return container;

  if (env.dataMode === "local") {
    container = {
      repository: new LocalRepository(),
      sync: new NoopSyncEngine(),
      database: null,
    };
    return container;
  }

  const database = await getDatabase();
  container = {
    repository: new RemoteRepository(database),
    sync: new SyncEngine(database),
    database,
  };
  return container;
}

/** Permite inyectar dobles en las pruebas y reiniciar entre casos. */
export function setContainerForTesting(next: Container | null): void {
  container = next;
}
