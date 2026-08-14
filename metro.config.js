// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require("expo/metro-config");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// `expo-sqlite` en web se apoya en wa-sqlite, que se distribuye como WebAssembly.
// Metro necesita tratar `.wasm` como asset para poder empaquetarlo.
config.resolver.assetExts.push("wasm");

// wa-sqlite usa `SharedArrayBuffer`, que los navegadores sólo habilitan en
// contextos aislados. Estas cabeceras son las que producen ese aislamiento
// durante el desarrollo; en un despliegue real las debe emitir el servidor web.
config.server.enhanceMiddleware = (middleware) => {
  return (req, res, next) => {
    res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
    res.setHeader("Cross-Origin-Embedder-Policy", "credentialless");
    return middleware(req, res, next);
  };
};

module.exports = config;
