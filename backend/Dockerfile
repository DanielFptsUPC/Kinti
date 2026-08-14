# Imagen del backend de Kinti.
#
# Multi-stage para que la imagen final no arrastre compiladores: `asyncpg` y
# `argon2-cffi` necesitan construir extensiones nativas, pero sólo al instalar.

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.12-slim

# Usuario sin privilegios: el proceso no necesita root para escuchar en 8000.
RUN useradd --create-home --uid 10001 kinti

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# CA raíz de Supabase. Es un certificado público, no un secreto, y hace falta
# para verificar TLS: tanto la conexión directa como el pooler están firmados
# por esta CA y no por una pública. Sin él, cualquier consulta a la base falla.
COPY supabase-ca.crt ./

# El arranque aplica las migraciones antes de servir; ver el comentario del
# script. Se copia con permiso de ejecución explícito porque el modo del archivo
# en Windows no se conserva al construir.
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

USER kinti

# El puerto lo fija la plataforma (Render, Cloud Run y Fly usan $PORT).
ENV PORT=8000
EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
