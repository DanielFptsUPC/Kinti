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

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

export async function saveTokens(tokens: TokenPair): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_KEY, tokens.accessToken);
  await SecureStore.setItemAsync(REFRESH_KEY, tokens.refreshToken);
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
}

export async function hasSession(): Promise<boolean> {
  return (await getAccessToken()) !== null;
}
