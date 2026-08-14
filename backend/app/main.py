from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.time import utcnow

settings = get_settings()

app = FastAPI(
    title="Kinti API",
    version="2.0.0",
    description=(
        "API del piloto conectado de Kinti (Fase 2). Datos exclusivamente sintéticos. "
        "El semáforo representa riesgo operativo de interrupción de la ruta, no gravedad "
        "clínica. No diagnostica, no prescribe y no realiza triaje."
    ),
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)


@app.get("/health", tags=["infraestructura"])
async def health() -> dict[str, str]:
    return {"status": "ok", "time": utcnow().isoformat()}


@app.get("/health/db", tags=["infraestructura"])
async def health_db() -> dict[str, object]:
    """Diagnóstico de la conexión a la base.

    Existe porque un 500 opaco en un despliegue remoto es imposible de resolver
    sin acceso a los logs: este endpoint convierte el fallo en un diagnóstico
    accionable.

    Nunca devuelve la contraseña, el usuario ni la cadena completa. Sólo el host,
    el tipo de error y una pista de qué revisar.
    """
    from sqlalchemy import text

    from app.core.database import engine

    url = engine.url
    info: dict[str, object] = {
        "host": url.host,
        "database": url.database,
        "requireTls": settings.require_tls,
        "sslRootCert": settings.db_ssl_root_cert or "(vacío)",
        "usesPooler": bool(url.host and "pooler.supabase.com" in url.host),
    }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {**info, "status": "ok"}
    except Exception as exc:  # se clasifica, no se propaga
        name = type(exc).__name__
        message = str(exc)

        if "CERTIFICATE_VERIFY_FAILED" in message or "SSLCert" in name:
            hint = (
                "El certificado no se verifica. Supabase firma con su propia CA, "
                "también en el pooler: revisa KINTI_DB_SSL_ROOT_CERT."
            )
        elif "Network is unreachable" in message or "unreachable" in message:
            hint = (
                "Host inalcanzable. La conexión directa de Supabase es sólo IPv6; "
                "usa el Session pooler, que tiene IPv4."
            )
        elif "password authentication" in message.lower():
            hint = (
                "Credenciales rechazadas. Con el pooler el usuario lleva punto: "
                "postgres.<project_ref>."
            )
        elif "prepared statement" in message.lower():
            hint = "Estás en Transaction pooler. Cambia a Session pooler."
        elif "Tenant or user not found" in message or "ENOTFOUND" in message:
            hint = "Región del pooler incorrecta, o usuario sin el sufijo del project_ref."
        else:
            hint = "Revisa los logs del servicio."

        return {**info, "status": "error", "error": name, "hint": hint}
