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

USER kinti

# El puerto lo fija la plataforma (Render, Cloud Run y Fly usan $PORT).
ENV PORT=8000
EXPOSE 8000

# `--proxy-headers` es necesario detrás del balanceador de la plataforma: sin
# ello, las URLs que genere FastAPI usarían el host interno del contenedor.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
