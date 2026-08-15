/**
 * Exporta el esquema OpenAPI del backend a `src/infrastructure/api/openapi.json`.
 *
 * Existe como script de Node porque `npm run` usa cmd.exe en Windows y sh en
 * Unix, y la ruta del intérprete del entorno virtual difiere entre ambos. Un
 * comando en línea funcionaba en uno y fallaba en el otro dejando el archivo
 * vacío — que es peor que fallar, porque la prueba de contrato pasa a comparar
 * contra nada.
 */

import { spawnSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = join(root, "backend");
const output = join(root, "src", "infrastructure", "api", "openapi.json");

const candidates =
  process.platform === "win32"
    ? [join(backend, ".venv", "Scripts", "python.exe")]
    : [join(backend, ".venv", "bin", "python")];

const python = candidates.find(existsSync);
if (!python) {
  console.error(
    `No se encontró el intérprete del entorno virtual.\n` +
      `Buscado en:\n  ${candidates.join("\n  ")}\n` +
      `Crea el entorno con: cd backend && python -m venv .venv`,
  );
  process.exit(1);
}

const result = spawnSync(python, ["-X", "utf8", "-m", "app.openapi_export"], {
  cwd: backend,
  encoding: "utf-8",
  env: {
    ...process.env,
    PYTHONIOENCODING: "utf-8",
    PYTHONUTF8: "1",
  },
  maxBuffer: 32 * 1024 * 1024,
});

if (result.status !== 0) {
  console.error(result.stderr || "El backend no pudo exportar el esquema");
  process.exit(result.status ?? 1);
}

// Se valida antes de escribir: un JSON truncado dejaría la prueba de contrato
// comparando contra un objeto vacío y pasando por accidente.
let parsed;
try {
  parsed = JSON.parse(result.stdout);
} catch {
  console.error("La salida no es JSON válido; no se sobrescribe el contrato.");
  process.exit(1);
}

if (!parsed.paths || Object.keys(parsed.paths).length === 0) {
  console.error("El esquema no declara rutas; no se sobrescribe el contrato.");
  process.exit(1);
}

writeFileSync(output, `${JSON.stringify(parsed, null, 2)}\n`, "utf-8");
console.log(
  `Contrato actualizado: ${Object.keys(parsed.paths).length} rutas, ` +
    `${Object.keys(parsed.components?.schemas ?? {}).length} esquemas`,
);
