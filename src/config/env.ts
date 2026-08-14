/**
 * Configuración de ejecución.
 *
 * `EXPO_PUBLIC_*` se incrusta en el bundle, así que aquí sólo viven valores no
 * secretos: el modo de datos y la URL del backend. Ningún token, clave ni
 * credencial puede pasar por estas variables.
 */

export type DataMode = "local" | "remote";

function readMode(): DataMode {
  return process.env.EXPO_PUBLIC_DATA_MODE === "remote" ? "remote" : "local";
}

export const env = {
  /** `local` conserva la demostración de Fase 1 sin backend. */
  dataMode: readMode(),
  apiUrl: (process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, ""),
  /** `__DEV__` habilita atajos de desarrollo (entrar en modo local, restaurar demo). */
  isDev: __DEV__,
} as const;

export const isRemoteMode = env.dataMode === "remote";
