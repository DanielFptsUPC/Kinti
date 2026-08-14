/**
 * Dobles de los módulos nativos que las pruebas no pueden cargar.
 *
 * SQLite NO se simula: las pruebas usan `node:sqlite` a través de
 * `src/testing/sqliteTestDatabase.ts`, para ejercitar el esquema real.
 *
 * Los nombres llevan el prefijo `mock` porque es el único que Jest permite
 * referenciar dentro de una factoría de `jest.mock`.
 */

// AsyncStorage: mock oficial del paquete, con almacenamiento en memoria.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// SecureStore: mapa en memoria. Es donde viven los tokens, así que las pruebas
// necesitan poder comprobar que se guardan y se borran de verdad.
const mockSecureStore = new Map();

jest.mock("expo-secure-store", () => ({
  setItemAsync: jest.fn(async (key, value) => {
    mockSecureStore.set(key, value);
  }),
  getItemAsync: jest.fn(async (key) =>
    mockSecureStore.has(key) ? mockSecureStore.get(key) : null,
  ),
  deleteItemAsync: jest.fn(async (key) => {
    mockSecureStore.delete(key);
  }),
}));

// UUID determinista: los identificadores de operación deben ser distintos entre
// sí, pero reproducibles dentro de una prueba.
const mockUuidState = { counter: 0 };

jest.mock("expo-crypto", () => ({
  randomUUID: jest.fn(() => `uuid-${(mockUuidState.counter += 1)}`),
}));

beforeEach(() => {
  mockSecureStore.clear();
  mockUuidState.counter = 0;
});
