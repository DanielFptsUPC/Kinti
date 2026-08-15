/**
 * Almacén de credenciales de sesión.
 *
 * En iOS y Android los tokens viven **sólo** en SecureStore (Keychain /
 * Keystore), nunca en AsyncStorage: AsyncStorage es texto plano legible con
 * acceso al dispositivo. Cerrar sesión los borra por completo.
 *
 * `expo-secure-store` no tiene implementación en navegador —no existe un
 * Keychain al que llamar— y lanza `getValueWithKeyAsync is not a function` en
 * cuanto se usa ahí. En web se cae a `localStorage`, que no ofrece la misma
 * garantía (es legible por cualquier script en la página), pero sigue siendo
 * mejor que no tener sesión persistente; el modo web de este piloto es para
 * demostración, no para manejar credenciales sensibles de producción.
 */

import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const ACCESS_KEY = "kinti.accessToken";
const REFRESH_KEY = "kinti.refreshToken";
const KIND_KEY = "kinti.sessionKind";

interface KeyValueStore {
  setItemAsync(key: string, value: string): Promise<void>;
  getItemAsync(key: string): Promise<string | null>;
  deleteItemAsync(key: string): Promise<void>;
}

const webStore: KeyValueStore = {
  async setItemAsync(key, value) {
    globalThis.localStorage?.setItem(key, value);
  },
  async getItemAsync(key) {
    return globalThis.localStorage?.getItem(key) ?? null;
  },
  async deleteItemAsync(key) {
    globalThis.localStorage?.removeItem(key);
  },
};

const store: KeyValueStore = Platform.OS === "web" ? webStore : SecureStore;

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

/**
 * A quién pertenece la sesión guardada.
 *
 * El dispositivo aloja **una** sesión a la vez, y saber de qué tipo es importa
 * al arrancar: una sesión infantil no debe pedir la instantánea operativa (el
 * servidor la rechazaría) ni montar Kinti Familia.
 */
export type SessionKind = "adult" | "patient";

export async function saveTokens(
  tokens: TokenPair,
  kind: SessionKind = "adult",
): Promise<void> {
  await store.setItemAsync(ACCESS_KEY, tokens.accessToken);
  await store.setItemAsync(REFRESH_KEY, tokens.refreshToken);
  await store.setItemAsync(KIND_KEY, kind);
}

export async function getSessionKind(): Promise<SessionKind | null> {
  const stored = await store.getItemAsync(KIND_KEY);
  return stored === "patient" || stored === "adult" ? stored : null;
}

export async function getAccessToken(): Promise<string | null> {
  return store.getItemAsync(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return store.getItemAsync(REFRESH_KEY);
}

export async function clearTokens(): Promise<void> {
  await store.deleteItemAsync(ACCESS_KEY);
  await store.deleteItemAsync(REFRESH_KEY);
  await store.deleteItemAsync(KIND_KEY);
}

export async function hasSession(): Promise<boolean> {
  return (await getAccessToken()) !== null;
}
