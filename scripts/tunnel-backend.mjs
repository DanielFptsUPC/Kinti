/**
 * Expone el backend por un túnel público temporal.
 *
 * Para cuando el celular no puede alcanzar el PC por la red local: red
 * corporativa con aislamiento de clientes, celular en datos móviles, o firewall
 * que no se puede abrir.
 *
 * ngrok gratuito permite **un solo agente simultáneo**, y Expo ya levanta uno
 * cuando corre con `--tunnel`. Por eso este script primero busca ese agente y le
 * añade un túnel más, en lugar de intentar arrancar otro — que fallaría con
 * «failed to start tunnel · remote gone away».
 *
 * ADVERTENCIA: mientras corre, tu backend queda accesible desde internet en una
 * URL aleatoria. Los datos son sintéticos, pero el endpoint de login es real.
 * Cierra el túnel (Ctrl+C) cuando termines.
 *
 *   node scripts/tunnel-backend.mjs
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PORT = Number(process.env.KINTI_BACKEND_PORT ?? 8000);
const TUNNEL_NAME = "kinti-backend";
//: Puertos donde el agente de ngrok suele exponer su API local.
const AGENT_PORTS = [4040, 4041, 4042];

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const envLocal = join(root, ".env.local");

async function backendIsUp() {
  try {
    const r = await fetch(`http://127.0.0.1:${PORT}/health`, {
      signal: AbortSignal.timeout(4000),
    });
    return r.ok;
  } catch {
    return false;
  }
}

/** Busca un agente ngrok ya corriendo (el que levanta `expo start --tunnel`). */
async function findAgent() {
  for (const port of AGENT_PORTS) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/api/tunnels`, {
        signal: AbortSignal.timeout(2000),
      });
      if (r.ok) return { port, tunnels: (await r.json()).tunnels ?? [] };
    } catch {
      // Puerto sin agente; se prueba el siguiente.
    }
  }
  return null;
}

async function addTunnel(agentPort) {
  const r = await fetch(`http://127.0.0.1:${agentPort}/api/tunnels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: TUNNEL_NAME, addr: String(PORT), proto: "http" }),
  });
  if (!r.ok) {
    throw new Error(`El agente rechazó el túnel (HTTP ${r.status}): ${await r.text()}`);
  }
  return (await r.json()).public_url;
}

async function removeTunnel(agentPort) {
  try {
    await fetch(`http://127.0.0.1:${agentPort}/api/tunnels/${TUNNEL_NAME}`, {
      method: "DELETE",
    });
  } catch {
    // El agente pudo haberse cerrado antes; no hay nada que limpiar.
  }
}

function writeApiUrl(url) {
  let contents = existsSync(envLocal) ? readFileSync(envLocal, "utf-8") : "";
  if (!contents.includes("EXPO_PUBLIC_DATA_MODE")) {
    contents += "EXPO_PUBLIC_DATA_MODE=remote\n";
  }
  contents = contents.includes("EXPO_PUBLIC_API_URL")
    ? contents.replace(/EXPO_PUBLIC_API_URL=.*/g, `EXPO_PUBLIC_API_URL=${url}`)
    : `${contents.trimEnd()}\nEXPO_PUBLIC_API_URL=${url}\n`;
  writeFileSync(envLocal, contents, "utf-8");
}

// ---------------------------------------------------------------------------

if (!(await backendIsUp())) {
  console.error(
    `El backend no responde en http://127.0.0.1:${PORT}/health\n\n` +
      `Levántalo primero, en otra terminal:\n` +
      `  cd backend\n` +
      `  .venv\\Scripts\\python.exe -m uvicorn app.main:app --port ${PORT}`,
  );
  process.exit(1);
}

const agent = await findAgent();

if (!agent) {
  console.error(
    `No encontré un agente de ngrok corriendo.\n\n` +
      `Arranca primero Expo con túnel, en otra terminal:\n` +
      `  npx expo start --tunnel --clear\n\n` +
      `Espera a que diga "Tunnel ready" y vuelve a ejecutar este script.\n` +
      `Se reutiliza ese agente porque el plan gratuito sólo permite uno.`,
  );
  process.exit(1);
}

const existing = agent.tunnels.find((t) => t.name === TUNNEL_NAME);
if (existing) {
  await removeTunnel(agent.port);
}

let url;
try {
  url = await addTunnel(agent.port);
} catch (error) {
  console.error(`No se pudo abrir el túnel: ${error.message}`);
  process.exit(1);
}

writeApiUrl(url);

console.log(`
  Agente ngrok reutilizado (API local en 127.0.0.1:${agent.port})

  Backend público:  ${url}
  Comprueba:        ${url}/health

  Ya actualicé .env.local con esa URL.

  AHORA, en la terminal de Expo: Ctrl+C y vuelve a arrancarlo con

      npx expo start --tunnel --clear

  El --clear es obligatorio: la URL anterior quedó incrustada en el bundle.

  Deja esta ventana abierta. Ctrl+C cierra el túnel del backend.
`);

const shutdown = async () => {
  console.log("\nCerrando el túnel del backend…");
  await removeTunnel(agent.port);
  process.exit(0);
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

// Mantiene el proceso vivo mientras el túnel deba seguir abierto.
setInterval(() => {}, 1 << 30);
