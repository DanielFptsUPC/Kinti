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

describe("paridad de comandos sincronizables", () => {
  it("los tipos de operación son exactamente los que acepta el servidor", () => {
    const clientTypes: OperationType[] = [
      "confirm_attendance",
      "report_barrier",
      "record_feeling",
      "mark_family_contacted",
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
    ];
    for (const path of used) {
      expect(Object.keys(schema.paths)).toContain(path);
    }
  });

  it("mantiene todo bajo /api/v1, salvo los chequeos de infraestructura", () => {
    // `/health` y `/health/db` viven fuera del contrato versionado a propósito:
    // los consumen la plataforma de despliegue y el diagnóstico operativo, no la
    // aplicación, así que no deben quedar atados a la versión de la API.
    const outside = Object.keys(schema.paths).filter((p) => !p.startsWith("/api/v1"));
    expect(outside.sort()).toEqual(["/health", "/health/db"]);
  });
});
