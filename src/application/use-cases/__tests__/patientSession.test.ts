/**
 * Sesión del menor.
 *
 * Lo crítico aquí es la **separación**: entrar al espacio Compañero no debe
 * dejar en el dispositivo nada de la sesión adulta anterior, y al arrancar la
 * aplicación una sesión infantil no puede intentar la restauración adulta —
 * pediría la instantánea operativa, el servidor la rechazaría con 403 y el niño
 * acabaría expulsado por un error esperado.
 */

import {
  friendlyPatientAuthMessage,
  restorePatientSession,
  restoreSession,
  signIn,
  signInAsPatient,
} from "@/application/use-cases/session";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import * as tokenStore from "@/infrastructure/auth/tokenStore";
import { readState } from "@/infrastructure/database/cache";
import { createMigratedDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";
import type { CompanionView, Snapshot } from "@/domain/entities";

jest.mock("@/infrastructure/api/client", () => {
  const actual = jest.requireActual("@/infrastructure/api/client");
  return {
    ...actual,
    api: {
      login: jest.fn(),
      logout: jest.fn(),
      bootstrap: jest.fn(),
      patientLogin: jest.fn(),
      companionView: jest.fn(),
    },
  };
});

const login = api.login as jest.Mock;
const bootstrap = api.bootstrap as jest.Mock;
const patientLogin = api.patientLogin as jest.Mock;
const companionView = api.companionView as jest.Mock;

function companion(): CompanionView {
  return {
    greeting: "Hola, soy Kinti. Estoy aquí contigo.",
    chosenName: null,
    avatarKey: null,
    comfortObject: null,
    developmentBand: "middle",
    activities: [{ key: "breathing", title: "Respira con Kinti", durationSeconds: 90 }],
    immediatePreparation: null,
  };
}

function snapshot(): Snapshot {
  return {
    user: {
      id: "u-1",
      email: "cuidador.mateo@kinti.demo",
      displayName: "Jorge, papá de Mateo",
      role: "caregiver",
    },
    patients: [
      {
        id: "p-mateo",
        displayName: "Mateo",
        age: 11,
        avatarKey: "mateo",
        routeStatus: "confirmation_needed",
        operationalRisk: "yellow",
        contactPhone: "+51 900 000 002 (ficticio)",
        caregiverName: "Jorge, papá de Mateo",
      },
    ],
    milestones: [],
    alerts: [],
    feelings: [],
    notifications: [],
    serverTime: "2026-08-14T12:00:00.000Z",
  };
}

let db: TestDatabase;

beforeEach(async () => {
  db = await createMigratedDatabase();
  for (const mock of [login, bootstrap, patientLogin, companionView]) mock.mockReset();

  login.mockResolvedValue({
    accessToken: "adult-access",
    refreshToken: "adult-refresh",
    tokenType: "bearer",
    expiresIn: 1800,
  });
  bootstrap.mockResolvedValue(snapshot());
  patientLogin.mockResolvedValue({
    accessToken: "child-access",
    refreshToken: "child-refresh",
    tokenType: "bearer",
    expiresIn: 1800,
  });
  companionView.mockResolvedValue(companion());
});

afterEach(() => {
  db.close();
});

describe("signInAsPatient", () => {
  it("guarda el token marcándolo como sesión infantil", async () => {
    await signInAsPatient(db, "mateo-colibri", "2468");

    expect(await tokenStore.getAccessToken()).toBe("child-access");
    expect(await tokenStore.getSessionKind()).toBe("patient");
  });

  it("no pide la instantánea operativa", async () => {
    await signInAsPatient(db, "mateo-colibri", "2468");
    expect(bootstrap).not.toHaveBeenCalled();
  });

  it("borra del dispositivo lo que dejó la sesión adulta anterior", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");
    expect((await readState(db)).patients).toHaveLength(1);

    await signInAsPatient(db, "mateo-colibri", "2468");

    const state = await readState(db);
    expect(state.patients).toHaveLength(0);
    expect(state.milestones).toHaveLength(0);
    expect(state.alerts).toHaveLength(0);
  });

  it("devuelve únicamente el espacio Compañero", async () => {
    const result = await signInAsPatient(db, "mateo-colibri", "2468");
    expect(Object.keys(result)).toEqual(["companion"]);
  });
});

describe("restauración al abrir la aplicación", () => {
  it("una sesión infantil no intenta la restauración adulta", async () => {
    await signInAsPatient(db, "mateo-colibri", "2468");

    expect(await restoreSession(db)).toBeNull();
    expect(bootstrap).not.toHaveBeenCalled();
  });

  it("una sesión adulta no se confunde con la infantil", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");

    expect(await restorePatientSession()).toBeNull();
    expect(companionView).not.toHaveBeenCalled();
  });

  it("recupera el espacio si la sesión guardada es del menor", async () => {
    await signInAsPatient(db, "mateo-colibri", "2468");

    const restored = await restorePatientSession();
    expect(restored?.companion.greeting).toContain("Kinti");
  });

  it("termina la sesión si el adulto suspendió la cuenta", async () => {
    await signInAsPatient(db, "mateo-colibri", "2468");
    companionView.mockRejectedValue(new ApiError(403, "forbidden", "Cuenta suspendida"));

    expect(await restorePatientSession()).toBeNull();
    expect(await tokenStore.getAccessToken()).toBeNull();
  });

  it("conserva la sesión cuando sólo falta conexión", async () => {
    await signInAsPatient(db, "mateo-colibri", "2468");
    companionView.mockRejectedValue(new NetworkError());

    expect(await restorePatientSession()).toBeNull();
    expect(await tokenStore.getAccessToken()).toBe("child-access");
  });
});

describe("friendlyPatientAuthMessage", () => {
  it("pide ayuda a un adulto en vez de culpar al niño", () => {
    expect(friendlyPatientAuthMessage(new NetworkError())).toContain("adulto");
  });

  it("no distingue alias inexistente de PIN equivocado", () => {
    const message = friendlyPatientAuthMessage(
      new ApiError(401, "invalid_credentials", "No pudimos entrar. Pide ayuda a tu adulto."),
    );
    expect(message).toBe("No pudimos entrar. Pide ayuda a tu adulto.");
  });

  it("explica el bloqueo sin reproche", () => {
    const message = friendlyPatientAuthMessage(new ApiError(423, "account_locked", "x"));
    expect(message).toContain("Descansa");
  });
});
