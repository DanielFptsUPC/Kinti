/**
 * `expo-secure-store` no tiene implementación en navegador: llamarlo ahí lanza
 * `getValueWithKeyAsync is not a function` en cuanto la app intenta restaurar
 * la sesión (`store.ts::hydrate` → `restorePatientSession`/`restoreSession`).
 * Ocurrió en vivo probando el modo web; estas pruebas fijan que no vuelva a
 * pasar.
 *
 * `store` se decide una sola vez al cargar el módulo (`Platform.OS === "web"
 * ? webStore : SecureStore`), así que cada prueba necesita su propio import
 * fresco tras fijar la plataforma — de ahí `resetModules` en cada caso.
 */

/**
 * El entorno de pruebas de `jest-expo` no trae un DOM: no hay `localStorage`
 * real. Se sustituye por un mapa en memoria, igual que `jest.setup.js` hace
 * con SecureStore — sólo así se puede comprobar que la rama web persiste algo
 * de verdad, en vez de fallar en silencio por un `globalThis.localStorage`
 * ausente.
 */
const memoryLocalStorage = new Map<string, string>();
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: {
    getItem: (key: string) => memoryLocalStorage.get(key) ?? null,
    setItem: (key: string, value: string) => memoryLocalStorage.set(key, value),
    removeItem: (key: string) => memoryLocalStorage.delete(key),
    clear: () => memoryLocalStorage.clear(),
  },
});

function withPlatform(os: "web" | "ios") {
  jest.resetModules();
  // Un doble mínimo, no `requireActual`: `tokenStore.ts` sólo lee `Platform.OS`,
  // y cargar el `react-native` real fuera del preset de `jest-expo` arrastra
  // TurboModules nativos (`DevMenu`, listas virtualizadas) que no existen en
  // este entorno de pruebas.
  jest.doMock("react-native", () => ({ Platform: { OS: os } }));
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("@/infrastructure/auth/tokenStore") as typeof import("@/infrastructure/auth/tokenStore");
}

afterEach(() => {
  jest.dontMock("react-native");
  jest.resetModules();
  memoryLocalStorage.clear();
});

describe("en iOS y Android", () => {
  it("usa SecureStore, no localStorage", async () => {
    const tokenStore = withPlatform("ios");

    await tokenStore.saveTokens({ accessToken: "a", refreshToken: "r" });

    expect(await tokenStore.getAccessToken()).toBe("a");
    // El doble global de SecureStore vive en `jest.setup.js`; si esta prueba
    // pasa usando la plataforma "ios", pasó por SecureStore y no por
    // `localStorage`, que en este entorno de pruebas ni siquiera contendría
    // el valor si el módulo estuviera tomando la rama equivocada.
    expect(globalThis.localStorage.getItem("kinti.accessToken")).toBeNull();
  });
});

describe("en web", () => {
  it("usa localStorage en vez de SecureStore, sin lanzar", async () => {
    const tokenStore = withPlatform("web");

    await expect(
      tokenStore.saveTokens({ accessToken: "a-web", refreshToken: "r-web" }, "patient"),
    ).resolves.toBeUndefined();

    expect(await tokenStore.getAccessToken()).toBe("a-web");
    expect(await tokenStore.getRefreshToken()).toBe("r-web");
    expect(await tokenStore.getSessionKind()).toBe("patient");
    expect(globalThis.localStorage.getItem("kinti.accessToken")).toBe("a-web");
  });

  it("borra la sesión guardada al cerrarla", async () => {
    const tokenStore = withPlatform("web");
    await tokenStore.saveTokens({ accessToken: "a-web", refreshToken: "r-web" });

    await tokenStore.clearTokens();

    expect(await tokenStore.hasSession()).toBe(false);
    expect(globalThis.localStorage.getItem("kinti.accessToken")).toBeNull();
  });

  it("restaurar la sesión no lanza `getValueWithKeyAsync is not a function`", async () => {
    // Reproduce exactamente el camino que falló: `hasSession` es lo primero
    // que llama `restorePatientSession`/`restoreSession` al arrancar la app.
    const tokenStore = withPlatform("web");
    await expect(tokenStore.hasSession()).resolves.toBe(false);
  });
});
