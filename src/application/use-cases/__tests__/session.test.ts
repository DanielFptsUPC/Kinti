/**
 * Sesión del piloto.
 *
 * Lo crítico: los tokens sólo viven en SecureStore, y cerrar sesión no puede
 * dejar rastro de la sesión anterior en el dispositivo.
 */

import { friendlyAuthMessage, signIn, signOut } from "@/application/use-cases/session";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import * as tokenStore from "@/infrastructure/auth/tokenStore";
import { readState } from "@/infrastructure/database/cache";
import { enqueue } from "@/infrastructure/database/outbox";
import { createMigratedDatabase, type TestDatabase } from "@/testing/sqliteTestDatabase";
import type { Snapshot } from "@/domain/entities";

// SecureStore y AsyncStorage se simulan globalmente en `jest.setup.js`.
jest.mock("@/infrastructure/api/client", () => {
  const actual = jest.requireActual("@/infrastructure/api/client");
  return {
    ...actual,
    api: {
      login: jest.fn(),
      logout: jest.fn(),
      bootstrap: jest.fn(),
      pushOperations: jest.fn(),
      markNotificationRead: jest.fn(),
    },
  };
});

const login = api.login as jest.Mock;
const logout = api.logout as jest.Mock;
const bootstrap = api.bootstrap as jest.Mock;

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
    serverTime: "2026-08-13T12:00:00.000Z",
  };
}

let db: TestDatabase;

beforeEach(async () => {
  db = await createMigratedDatabase();
  login.mockReset();
  logout.mockReset();
  bootstrap.mockReset();
  login.mockResolvedValue({
    accessToken: "access-token",
    refreshToken: "refresh-token",
    tokenType: "bearer",
    expiresIn: 1800,
  });
  bootstrap.mockResolvedValue(snapshot());
});

afterEach(() => {
  db.close();
});

describe("signIn", () => {
  it("stores tokens in SecureStore", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");

    expect(await tokenStore.getAccessToken()).toBe("access-token");
    expect(await tokenStore.getRefreshToken()).toBe("refresh-token");
  });

  it("initialises the cache from the canonical snapshot", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");

    const state = await readState(db);
    expect(state.patients).toHaveLength(1);
    expect(state.patients[0].displayName).toBe("Mateo");
  });

  it("returns the role and patients the server authorised", async () => {
    const result = await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");

    expect(result.user.role).toBe("caregiver");
    expect(result.patientIds).toEqual(["p-mateo"]);
  });
});

describe("signOut", () => {
  it("removes the tokens", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");
    await signOut(db);

    expect(await tokenStore.getAccessToken()).toBeNull();
    expect(await tokenStore.getRefreshToken()).toBeNull();
  });

  it("wipes every local trace of the session", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");
    await enqueue(db, {
      operationId: "op-1",
      type: "report_barrier",
      targetId: "m-1",
      payload: {},
    });

    await signOut(db);

    const state = await readState(db);
    expect(state.patients).toHaveLength(0);
    const queued = await db.getAllAsync("SELECT operation_id FROM outbox_operations");
    expect(queued).toHaveLength(0);
  });

  it("signs out locally even when the server is unreachable", async () => {
    await signIn(db, "cuidador.mateo@kinti.demo", "Kinti.Demo.2026");
    logout.mockRejectedValue(new NetworkError());

    await signOut(db);

    expect(await tokenStore.getAccessToken()).toBeNull();
  });
});

describe("friendlyAuthMessage", () => {
  it("explains a connection problem without technical detail", () => {
    expect(friendlyAuthMessage(new NetworkError())).toContain("conexión");
  });

  it("does not reveal whether the account exists", () => {
    const message = friendlyAuthMessage(new ApiError(401, "invalid_credentials", "nope"));
    expect(message).toBe("Correo o contraseña incorrectos.");
  });

  it("falls back to a generic message", () => {
    expect(friendlyAuthMessage(new Error("boom"))).toContain("inesperado");
  });
});
