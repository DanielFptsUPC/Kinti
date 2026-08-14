const expoConfig = require("eslint-config-expo/flat");

module.exports = [
  ...expoConfig,
  {
    // `backend/` es Python: lo revisa Ruff, no ESLint.
    ignores: ["dist/*", "node_modules/*", "coverage/*", "backend/*"],
  },
  {
    // Globales de Jest para las pruebas y su archivo de configuración.
    files: ["**/__tests__/**/*.{ts,tsx,js}", "**/*.test.{ts,tsx}", "jest.setup.js"],
    languageOptions: {
      globals: {
        jest: "readonly",
        describe: "readonly",
        it: "readonly",
        test: "readonly",
        expect: "readonly",
        beforeEach: "readonly",
        afterEach: "readonly",
        beforeAll: "readonly",
        afterAll: "readonly",
      },
    },
  },
];
