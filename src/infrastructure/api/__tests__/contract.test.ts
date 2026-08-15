/**
 * Prueba de contrato entre el backend y el cliente.
 *
 * Compara el esquema OpenAPI real (`openapi.json`, regenerado con
 * `npm run api:contract`) contra los tipos TypeScript del dominio.
 *
 * La detección es bidireccional:
 *  - un campo nuevo en el DTO de Python que el cliente no conozca hace fallar
 *    la comparación de claves;
 *  - un campo nuevo en el tipo TypeScript hace fallar la **compilación**, porque
 *    cada lista de claves está tipada como `Record<keyof T, true>` y TypeScript
 *    exige que estén todas.
 */

import schema from "@/infrastructure/api/openapi.json";
import type {
  AppNotification,
  BarrierAlert,
  FeelingCheckIn,
  Milestone,
  OperationType,
  Patient,
  SessionUser,
} from "@/domain/entities";
import type {
  AppointmentHold,
  AppointmentRequest,
  AppointmentSlot,
  VoiceCallbackRequest,
} from "@/types";

type Keys<T> = Record<keyof T, true>;

/** Propiedades declaradas por el esquema para un componente. */
function schemaProperties(name: string): string[] {
  const component = (schema.components.schemas as Record<string, { properties?: object }>)[name];
  expect(component).toBeDefined();
  return Object.keys(component.properties ?? {}).sort();
}

function typeKeys<T>(keys: Keys<T>): string[] {
  return Object.keys(keys).sort();
}

describe("paridad de entidades", () => {
  it("Patient coincide con PatientOut", () => {
    const keys = typeKeys<Patient>({
      id: true,
      displayName: true,
      age: true,
      avatarKey: true,
      routeStatus: true,
      operationalRisk: true,
      contactPhone: true,
      caregiverName: true,
    });
    expect(schemaProperties("PatientOut")).toEqual(keys);
  });

  it("Milestone coincide con MilestoneOut salvo el control de concurrencia", () => {
    const keys = typeKeys<Milestone>({
      id: true,
      patientId: true,
      type: true,
      title: true,
      scheduledAt: true,
      location: true,
      preparation: true,
      service: true,
      confirmationDeadline: true,
      status: true,
      attendanceConfirmed: true,
    });
    // `version` sólo lo usa el servidor para detectar escrituras concurrentes;
    // el cliente no necesita representarlo en su entidad de dominio.
    expect(schemaProperties("MilestoneOut")).toEqual([...keys, "version"].sort());
  });

  it("BarrierAlert coincide con AlertOut", () => {
    const keys = typeKeys<BarrierAlert>({
      id: true,
      patientId: true,
      milestoneId: true,
      category: true,
      note: true,
      risk: true,
      status: true,
      familyContacted: true,
      actionTaken: true,
      internalNote: true,
      createdAt: true,
      resolvedAt: true,
    });
    expect(schemaProperties("AlertOut")).toEqual(keys);
  });

  it("FeelingCheckIn coincide con FeelingOut", () => {
    const keys = typeKeys<FeelingCheckIn>({
      id: true,
      patientId: true,
      mood: true,
      createdAt: true,
    });
    expect(schemaProperties("FeelingOut")).toEqual(keys);
  });

  it("AppNotification coincide con NotificationOut", () => {
    const keys = typeKeys<AppNotification>({
      id: true,
      type: true,
      patientId: true,
      title: true,
      body: true,
      createdAt: true,
      readAt: true,
    });
    expect(schemaProperties("NotificationOut")).toEqual(keys);
  });

  it("SessionUser coincide con UserProfile", () => {
    const keys = typeKeys<SessionUser>({
      id: true,
      email: true,
      displayName: true,
      role: true,
    });
    expect(schemaProperties("UserProfile")).toEqual(keys);
  });
});

describe("paridad de Kinti Voz", () => {
  it("AppointmentRequest coincide con AppointmentRequestOut", () => {
    const keys = typeKeys<AppointmentRequest>({
      id: true,
      patientId: true,
      requestedBy: true,
      referralId: true,
      voiceSessionId: true,
      requestKind: true,
      source: true,
      status: true,
      selectedSlotId: true,
      proposalExpiresAt: true,
      externalResult: true,
      version: true,
      createdAt: true,
      updatedAt: true,
    });
    expect(schemaProperties("AppointmentRequestOut")).toEqual(keys);
  });

  it("AppointmentSlot coincide con AppointmentSlotOut", () => {
    const keys = typeKeys<AppointmentSlot>({
      id: true,
      service: true,
      site: true,
      spokenLocation: true,
      startsAt: true,
      endsAt: true,
      professionalKey: true,
      equivalenceGroup: true,
      availablePlaces: true,
      availabilityVersion: true,
      status: true,
      source: true,
    });
    expect(schemaProperties("AppointmentSlotOut")).toEqual(keys);
  });

  it("AppointmentHold coincide con AppointmentHoldOut", () => {
    const keys = typeKeys<AppointmentHold>({
      id: true,
      requestId: true,
      slotId: true,
      status: true,
      expiresAt: true,
      availabilityVersion: true,
    });
    expect(schemaProperties("AppointmentHoldOut")).toEqual(keys);
  });

  it("VoiceCallbackRequest coincide con CallbackOut", () => {
    const keys = typeKeys<VoiceCallbackRequest>({
      id: true,
      voiceSessionId: true,
      actorId: true,
      patientId: true,
      reasonCode: true,
      status: true,
      slaDueAt: true,
      assignedTo: true,
      completedAt: true,
      outcomeCode: true,
      createdAt: true,
      updatedAt: true,
    });
    expect(schemaProperties("CallbackOut")).toEqual(keys);
  });
});

describe("paridad de comandos sincronizables", () => {
  it("los tipos de operación son exactamente los que acepta el servidor", () => {
    const clientTypes: OperationType[] = [
      "confirm_attendance",
      "report_barrier",
      "record_feeling",
      "mark_family_contacted",
      "refer_social_work",
      "resolve_alert",
      "create_milestone",
      "reschedule_milestone",
    ];

    const operation = schema.components.schemas.SyncOperation as {
      properties: { type: { enum?: string[]; $ref?: string } };
    };
    const serverTypes = operation.properties.type.enum ?? [];

    expect(serverTypes.slice().sort()).toEqual(clientTypes.slice().sort());
  });

  it("los estados de resultado son los que el outbox sabe interpretar", () => {
    const result = schema.components.schemas.SyncOperationResult as {
      properties: { status: { enum?: string[] } };
    };
    expect(result.properties.status.enum?.slice().sort()).toEqual([
      "already_applied",
      "applied",
      "rejected",
    ]);
  });
});

describe("cobertura de endpoints", () => {
  it("expone todas las rutas que el cliente consume", () => {
    const used = [
      "/api/v1/auth/login",
      "/api/v1/auth/refresh",
      "/api/v1/auth/logout",
      "/api/v1/sync/bootstrap",
      "/api/v1/sync/operations",
      "/api/v1/notifications/{notification_id}/read",
      "/api/v1/auth/patient-login",
      "/api/v1/patient/me/companion",
      "/api/v1/patient/me/feelings",
      "/api/v1/patient/me/support-requests",
      "/api/v1/patient/me/preferences",
      "/api/v1/appointment-requests",
      "/api/v1/appointment-requests/{request_id}/proposals",
      "/api/v1/appointment-requests/{request_id}/confirm",
      "/api/v1/appointment-requests/{request_id}/human-handoff",
      "/api/v1/voice/callback-requests",
    ];
    for (const path of used) {
      expect(Object.keys(schema.paths)).toContain(path);
    }
  });

  it("no expone ninguna ruta infantil parametrizada por paciente", () => {
    // La frontera es de forma, no de comprobación: si ninguna ruta del menor
    // acepta un identificador, no hay superficie donde pedir otro paciente.
    const childRoutes = Object.keys(schema.paths).filter((p) =>
      p.startsWith("/api/v1/patient/me"),
    );
    expect(childRoutes.length).toBeGreaterThan(0);
    expect(childRoutes.filter((p) => p.includes("{"))).toEqual([]);
  });

  it("mantiene todo bajo /api/v1, salvo los chequeos de infraestructura", () => {
    // `/health` y `/health/db` viven fuera del contrato versionado a propósito:
    // los consumen la plataforma de despliegue y el diagnóstico operativo, no la
    // aplicación, así que no deben quedar atados a la versión de la API.
    const outside = Object.keys(schema.paths).filter((p) => !p.startsWith("/api/v1"));
    expect(outside.sort()).toEqual(["/health", "/health/db"]);
  });
});
