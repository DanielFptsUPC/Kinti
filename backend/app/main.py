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
