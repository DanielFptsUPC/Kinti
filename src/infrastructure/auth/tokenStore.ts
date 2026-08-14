/**
 * Almacén de credenciales de sesión.
 *
 * Los tokens viven **sólo** en SecureStore (Keychain / Keystore), nunca en
 * AsyncStorage: AsyncStorage es texto plano legible con acceso al dispositivo.
 * Cerrar sesión los borra por completo.
 */

import * as SecureStore from "expo-secure-store";

const ACCESS_KEY = "kinti.accessToken";
const REFRESH_KEY = "kinti.refreshToken";
const KIND_KEY = "kinti.sessionKind";

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
  await SecureStore.setItemAsync(ACCESS_KEY, tokens.accessToken);
  await SecureStore.setItemAsync(REFRESH_KEY, tokens.refreshToken);
  await SecureStore.setItemAsync(KIND_KEY, kind);
}

export async function getSessionKind(): Promise<SessionKind | null> {
  const stored = await SecureStore.getItemAsync(KIND_KEY);
  return stored === "patient" || stored === "adult" ? stored : null;
}

export async function getAccessToken(): Promise<string | null> {
  return SecureStore.getItemAsync(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_KEY);
}

export async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
  await SecureStore.deleteItemAsync(KIND_KEY);
}

export async function hasSession(): Promise<boolean> {
  return (await getAccessToken()) !== null;
}
