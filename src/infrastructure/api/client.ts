/**
 * Cliente HTTP del backend de Kinti.
 *
 * Distingue tres desenlaces, porque el outbox reacciona distinto a cada uno:
 * fallo de red (reintentar), rechazo de permiso o validación (no reintentar) y
 * sesión expirada (renovar y repetir una vez).
 */

import { env } from "@/config/env";
import type {
  AppNotification,
  AssistantMessage,
  CompanionCategory,
  CompanionView,
  DevelopmentBand,
  FeelingCheckIn,
  OperationsDashboard,
  PatientAccount,
  Snapshot,
  SupportRequest,
  SupportRequestType,
  SyncOperationResult,
} from "@/domain/entities";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  saveTokens,
  type TokenPair,
} from "@/infrastructure/auth/tokenStore";

/** Fallo de conexión: la operación sigue siendo válida, sólo no llegó. */
export class NetworkError extends Error {
  constructor(message = "Sin conexión con el servidor") {
    super(message);
    this.name = "NetworkError";
  }
}

/** El servidor respondió y rechazó. Reintentarlo sin cambios no sirve. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  /** Errores que no se resuelven reintentando: permisos, validación, no encontrado. */
  get isPermanent(): boolean {
    return this.status === 403 || this.status === 404 || this.status === 422;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  authenticated?: boolean;
  /** Evita bucles infinitos de renovación. */
  retryOnUnauthorized?: boolean;
}

function url(path: string): string {
  return `${env.apiUrl}/api/v1${path}`;
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "unknown";
  let message = "No pudimos completar la acción";
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "object" && detail !== null) {
      code = String(detail.code ?? code);
      message = String(detail.message ?? message);
    } else if (Array.isArray(detail)) {
      // Error de validación de FastAPI: no se muestra crudo al usuario.
      code = "invalid_payload";
      message = "Revisa los datos ingresados";
    }
  } catch {
    // Cuerpo no interpretable: se conservan los mensajes genéricos.
  }
  return new ApiError(response.status, code, message);
}

async function refreshSession(): Promise<boolean> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(url("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    if (!response.ok) {
      await clearTokens();
      return false;
    }
    const tokens = (await response.json()) as TokenPair;
    await saveTokens(tokens);
    return true;
  } catch {
    // Sin red no se puede renovar; la sesión no se descarta por eso.
    return false;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = "GET",
    body,
    authenticated = true,
    retryOnUnauthorized = true,
  } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authenticated) {
    const token = await getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url(path), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    throw new NetworkError(error instanceof Error ? error.message : undefined);
  }

  if (response.status === 401 && authenticated && retryOnUnauthorized) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return request<T>(path, { ...options, retryOnUnauthorized: false });
    }
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// --------------------------------------------------------------------- API

export interface LoginResult extends TokenPair {
  tokenType: string;
  expiresIn: number;
}

export const api = {
  async login(email: string, password: string): Promise<LoginResult> {
    return request<LoginResult>("/auth/login", {
      method: "POST",
      body: { email, password },
      authenticated: false,
    });
  },

  /**
   * Puerta del menor: alias y PIN, sin correo ni teléfono (RF-NNA-05).
   *
   * Devuelve un token `patient` que el servidor limita a un único registro
   * asistencial. **No sirve** para `/sync/bootstrap` ni para ninguna pantalla
   * adulta: esas rutas lo rechazan con 403.
   */
  async patientLogin(alias: string, pin: string): Promise<LoginResult> {
    return request<LoginResult>("/auth/patient-login", {
      method: "POST",
      body: { alias, pin },
      authenticated: false,
    });
  },

  async logout(): Promise<void> {
    await request<void>("/auth/logout", { method: "POST" });
  },

  // ------------------------------------------------------ Kinti Compañero

  async companionView(): Promise<CompanionView> {
    return request<CompanionView>("/patient/me/companion");
  },

  async recordOwnFeeling(mood: string, operationId?: string): Promise<FeelingCheckIn> {
    return request<FeelingCheckIn>("/patient/me/feelings", {
      method: "POST",
      body: { mood, operationId },
    });
  },

  async requestSupport(
    requestType: SupportRequestType,
    operationId?: string,
  ): Promise<SupportRequest> {
    return request<SupportRequest>("/patient/me/support-requests", {
      method: "POST",
      body: { requestType, operationId },
    });
  },

  async saveCompanionPreferences(preferences: {
    chosenName?: string;
    avatarKey?: string;
    comfortObject?: string;
  }): Promise<CompanionView> {
    return request<CompanionView>("/patient/me/preferences", {
      method: "POST",
      body: preferences,
    });
  },

  async bootstrap(): Promise<Snapshot> {
    return request<Snapshot>("/sync/bootstrap");
  },

  async pushOperations(
    operations: {
      operationId: string;
      type: string;
      targetId: string;
      payload: Record<string, unknown>;
    }[],
  ): Promise<SyncOperationResult[]> {
    const response = await request<{ results: SyncOperationResult[] }>("/sync/operations", {
      method: "POST",
      body: { operations },
    });
    return response.results;
  },

  async markNotificationRead(notificationId: string): Promise<AppNotification> {
    return request<AppNotification>(`/notifications/${notificationId}/read`, { method: "POST" });
  },

  async operationsDashboard(day?: string): Promise<OperationsDashboard> {
    const capacityPath = day
      ? `/operations/capacity?day=${encodeURIComponent(day)}`
      : "/operations/capacity";
    const [workload, capacity, socialWork] = await Promise.all([
      request<OperationsDashboard["workload"]>("/operations/workload"),
      request<OperationsDashboard["capacity"]>(capacityPath),
      request<OperationsDashboard["socialWork"]>("/operations/social-work"),
    ]);
    return { workload, capacity, socialWork };
  },

  // ------------------------------- administración adulta del espacio infantil

  async activatePatientAccount(
    patientId: string,
    body: { alias: string; pin: string; consentConfirmed: boolean },
  ): Promise<PatientAccount> {
    return request<PatientAccount>(`/caregiver/patients/${patientId}/patient-account`, {
      method: "POST",
      body,
    });
  },

  async updatePatientAccount(
    patientId: string,
    body: {
      status?: "active" | "suspended";
      pin?: string;
      developmentBand?: DevelopmentBand;
      enabledCategories?: Partial<Record<CompanionCategory, boolean>>;
    },
  ): Promise<PatientAccount> {
    return request<PatientAccount>(`/caregiver/patients/${patientId}/patient-account`, {
      method: "PATCH",
      body,
    });
  },

  async patientSupportRequests(patientId: string): Promise<SupportRequest[]> {
    return request<SupportRequest[]>(`/caregiver/patients/${patientId}/support-requests`);
  },

  async acknowledgeSupportRequest(requestId: string): Promise<SupportRequest> {
    return request<SupportRequest>(`/caregiver/support-requests/${requestId}/acknowledge`, {
      method: "POST",
    });
  },

  // ----------------------------------------------------------- asistente

  async startAssistantSession(patientId?: string): Promise<{ id: string }> {
    return request<{ id: string }>("/assistant/sessions", {
      method: "POST",
      body: { patientId },
    });
  },

  async sendAssistantMessage(
    sessionId: string,
    text: string,
    operationId?: string,
  ): Promise<AssistantMessage> {
    return request<AssistantMessage>(`/assistant/sessions/${sessionId}/messages`, {
      method: "POST",
      body: { text, modality: "text", operationId },
    });
  },

  async confirmAssistantAction(
    messageId: string,
    operationId?: string,
  ): Promise<AssistantMessage> {
    return request<AssistantMessage>(`/assistant/messages/${messageId}/confirm-action`, {
      method: "POST",
      body: { operationId },
    });
  },
};
