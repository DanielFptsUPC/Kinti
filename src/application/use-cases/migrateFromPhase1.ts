/**
 * Migración desde el almacenamiento de la Fase 1.
 *
 * Regla central: en modo conectado **no se sube nada** del estado antiguo al
 * servidor. Ese estado se generó localmente con datos de demostración y sin
 * ninguna noción de vínculo familiar; subirlo mezclaría datos de una sesión que
 * nunca existió en el backend.
 *
 * Lo que sí se hace es conservarlo intacto para que el modo local siga
 * funcionando, y dejar constancia de que la migración ya corrió.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

import { LEGACY_STORAGE_KEY } from "@/infrastructure/repositories/LocalRepository";

export const MIGRATION_VERSION_KEY = "kinti.migrationVersion";
export const CURRENT_MIGRATION_VERSION = "2";

export interface MigrationResult {
  ran: boolean;
  legacyStateFound: boolean;
  version: string;
}

export interface MigrationStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

/**
 * Ejecuta la migración una sola vez.
 *
 * Es idempotente: la versión guardada evita repetir el proceso en cada arranque.
 */
export async function migrateFromPhase1(
  storage: MigrationStorage = AsyncStorage,
): Promise<MigrationResult> {
  const currentVersion = await storage.getItem(MIGRATION_VERSION_KEY);
  const legacyState = await storage.getItem(LEGACY_STORAGE_KEY);
  const legacyStateFound = legacyState !== null;

  if (currentVersion === CURRENT_MIGRATION_VERSION) {
    return { ran: false, legacyStateFound, version: CURRENT_MIGRATION_VERSION };
  }

  // El estado de Fase 1 se deja donde está: el modo local lo sigue leyendo.
  await storage.setItem(MIGRATION_VERSION_KEY, CURRENT_MIGRATION_VERSION);
  return { ran: true, legacyStateFound, version: CURRENT_MIGRATION_VERSION };
}
