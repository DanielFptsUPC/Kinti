#!/bin/sh
#
# Arranque del contenedor: migrar y después servir.
#
# Hasta la Fase 4 la migración era un paso manual, y eso ya falló una vez: el
# código desplegado quedó por delante del esquema y toda ruta nueva devolvía 500
# o 404 sin explicación evidente. Aplicarla aquí elimina esa clase de desfase —
# el contenedor no puede servir una versión cuyo esquema no esté aplicado.
#
# Que un fallo de migración impida arrancar es intencionado: la plataforma
# mantiene viva la versión anterior si la nueva no supera el health check, así
# que romper el arranque es más seguro que servir con el esquema equivocado.
set -e

# Vertex AI se autentica con una service account de GCP, y su credencial es un
# archivo JSON, no una variable de una línea. Render no tiene un mecanismo de
# "montar secreto como archivo" como Fly o Cloud Run: el JSON completo se pega
# como valor de una variable de entorno (`GOOGLE_APPLICATION_CREDENTIALS_JSON`)
# y aquí se materializa a un archivo antes de arrancar. `/tmp` porque `/app`
# pertenece a root y el proceso corre como `kinti` sin permiso de escritura ahí.
#
# Con KINTI_AI_PROVIDER=fake (el valor por defecto) esta variable simplemente
# no existe y el bloque no hace nada — no cambia el arranque de hoy.
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS_JSON:-}" ]; then
  echo "[kinti] escribiendo credencial de Vertex AI..."
  echo "${GOOGLE_APPLICATION_CREDENTIALS_JSON}" > /tmp/gcp-credentials.json
  export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-credentials.json
fi

echo "[kinti] aplicando migraciones..."
alembic upgrade head

echo "[kinti] iniciando API en el puerto ${PORT}"
# `--proxy-headers` es necesario detrás del balanceador de la plataforma: sin
# ello, las URLs que genere FastAPI usarían el host interno del contenedor.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
