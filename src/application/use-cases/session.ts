/**
 * Casos de uso de sesión del piloto.
 *
 * Iniciar sesión trae la instantánea canónica y con ella el rol y los pacientes
 * autorizados: en modo conectado el usuario nunca elige libremente su rol.
 * Cerrar sesión borra tokens y datos locales vinculados a esa sesión.
 */

import type { SessionUser } from "@/domain/entities";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import { writeSnapshot } from "@/infrastructure/database/cache";
import { clearAll, type SqlDatabase } from "@/infrastructure/database/schema";
import { clearTokens, hasSession, saveTokens } from "@/infrastructure/auth/tokenStore";

export interface SignInResult {
  user: SessionUser;
  patientIds: string[];
}

/** Mensajes para la persona, sin filtrar detalles técnicos del servidor. */
export function friendlyAuthMessage(error: unknown): string {
  if (error instanceof NetworkError) {
    return "No pudimos conectar con el servidor. Revisa tu conexión e inténtalo otra vez.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) return "Correo o contraseña incorrectos.";
    return "No pudimos iniciar sesión en este momento.";
  }
  return "Ocurrió un problema inesperado. Inténtalo nuevamente.";
}

export async function signIn(
  db: SqlDatabase,
  email: string,
  password: string,
): Promise<SignInResult> {
  const tokens = await api.login(email, password);
  await saveTokens({ accessToken: tokens.accessToken, refreshToken: tokens.refreshToken });

  // La caché local se inicializa desde `/sync/bootstrap`, no desde datos previos.
  const snapshot = await api.bootstrap();
  await writeSnapshot(db, snapshot);

  return {
    user: snapshot.user,
    patientIds: snapshot.patients.map((patient) => patient.id),
  };
}

export async function signOut(db: SqlDatabase): Promise<void> {
  try {
    await api.logout();
  } catch {
    // Que el servidor no responda no puede impedir cerrar sesión en el dispositivo.
  }
  await clearTokens();
  await clearAll(db);
}

/** Restaura una sesión existente al abrir la aplicación. */
export async function restoreSession(db: SqlDatabase): Promise<SignInResult | null> {
  if (!(await hasSession())) return null;

  try {
    const snapshot = await api.bootstrap();
    await writeSnapshot(db, snapshot);
    return { user: snapshot.user, patientIds: snapshot.patients.map((p) => p.id) };
  } catch (error) {
    if (error instanceof NetworkError) {
      // Sin conexión se sigue trabajando con la caché: la sesión no se pierde.
      return null;
    }
    if (error instanceof ApiError && error.status === 401) {
      await signOut(db);
    }
    return null;
  }
}
