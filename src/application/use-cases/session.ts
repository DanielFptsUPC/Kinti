/**
 * Casos de uso de sesión del piloto.
 *
 * Iniciar sesión trae la instantánea canónica y con ella el rol y los pacientes
 * autorizados: en modo conectado el usuario nunca elige libremente su rol.
 * Cerrar sesión borra tokens y datos locales vinculados a esa sesión.
 */

import type { CompanionView, SessionUser } from "@/domain/entities";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import { writeSnapshot } from "@/infrastructure/database/cache";
import { clearAll, type SqlDatabase } from "@/infrastructure/database/schema";
import {
  clearTokens,
  getSessionKind,
  hasSession,
  saveTokens,
} from "@/infrastructure/auth/tokenStore";

export interface SignInResult {
  user: SessionUser;
  patientIds: string[];
}

/**
 * Sesión del menor.
 *
 * No trae instantánea ni escribe la caché operativa: lo único que obtiene es su
 * espacio Compañero. Esa asimetría con `signIn` es intencionada — el
 * dispositivo no debe conservar hitos ni alertas mientras el niño lo usa.
 */
export interface PatientSignInResult {
  companion: CompanionView;
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

/** Mensajes del acceso infantil: sin culpa y siempre con salida hacia un adulto. */
export function friendlyPatientAuthMessage(error: unknown): string {
  if (error instanceof NetworkError) {
    return "No pudimos conectarnos. Pide ayuda a tu adulto.";
  }
  if (error instanceof ApiError) {
    if (error.status === 423) {
      return "Descansa un momento y vuelve a intentarlo con tu adulto.";
    }
    // El servidor devuelve el mismo mensaje para alias inexistente y PIN
    // equivocado; aquí no se intenta afinarlo más.
    return error.message;
  }
  return "Algo no salió bien. Pide ayuda a tu adulto.";
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

/**
 * Inicia la sesión del menor y limpia toda la caché operativa del dispositivo.
 *
 * El `clearAll` no es higiene: si el equipo lo usaba antes un cuidador, sus
 * hitos y alertas seguirían en SQLite mientras el niño tiene el teléfono en la
 * mano. Entrar al espacio Compañero los borra.
 */
export async function signInAsPatient(
  db: SqlDatabase,
  alias: string,
  pin: string,
): Promise<PatientSignInResult> {
  const tokens = await api.patientLogin(alias, pin);
  await clearAll(db);
  await saveTokens(
    { accessToken: tokens.accessToken, refreshToken: tokens.refreshToken },
    "patient",
  );

  return { companion: await api.companionView() };
}

/** Restaura una sesión infantil existente, si la guardada es de ese tipo. */
export async function restorePatientSession(): Promise<PatientSignInResult | null> {
  if (!(await hasSession())) return null;
  if ((await getSessionKind()) !== "patient") return null;

  try {
    return { companion: await api.companionView() };
  } catch (error) {
    if (error instanceof NetworkError) return null;
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      // 403 aquí significa cuenta suspendida por el adulto: la sesión termina.
      await clearTokens();
    }
    return null;
  }
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

/** Restaura una sesión adulta al abrir la aplicación. */
export async function restoreSession(db: SqlDatabase): Promise<SignInResult | null> {
  if (!(await hasSession())) return null;
  // Una sesión infantil no pide la instantánea: el servidor la rechaza, y
  // pedirla igualmente cerraría la sesión del niño por un 403 esperado.
  if ((await getSessionKind()) === "patient") return null;

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
