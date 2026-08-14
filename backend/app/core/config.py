from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del piloto. Todo se lee de entorno con el prefijo `KINTI_`."""

    model_config = SettingsConfigDict(
        env_prefix="KINTI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"

    database_url: str = "postgresql+asyncpg://kinti:kinti@localhost:5433/kinti"

    jwt_secret: str = "cambia-este-secreto-solo-para-desarrollo-local"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # Reglas de dominio configurables (paridad con src/logic/risk.ts).
    barrier_response_window_hours: int = 48
    missed_tolerance_hours: int = 6

    # `NoDecode` es imprescindible: sin él, pydantic-settings intenta parsear el
    # valor como JSON antes de que corra el validador, y una lista separada por
    # comas —que es como se documenta— revienta el arranque.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8081", "http://localhost:19006"]
    )

    seed_password: str = "Kinti.Demo.2026"

    # Límites de entrada: notas cortas, sin cargas clínicas extensas.
    max_note_length: int = 500
    max_sync_batch: int = 50

    # --- Fase 3: IA conversacional y RAG ---------------------------------
    #: `fake` por defecto a propósito: un despliegue mal configurado no debe
    #: empezar a gastar dinero ni a enviar datos a un tercero por omisión.
    ai_provider: str = "fake"
    ai_model_id: str = ""
    ai_region: str = ""
    ai_timeout_seconds: int = 30
    ai_max_output_tokens: int = 1024

    embedding_provider: str = "fake"
    embedding_model_id: str = ""
    embedding_dimension: int = 768

    rag_top_k: int = 5

    storage_provider: str = "local"
    supabase_url: str = ""
    supabase_service_key: str = ""

    #: Conexión directa para Alembic y administración. Vacío = usa `database_url`.
    #: Alembic toma locks de DDL y necesita una conexión estable sin pooler; el
    #: runtime necesita pool. Separarlas también permite dar al rol de aplicación
    #: menos privilegios que al de migración.
    migration_database_url: str = ""

    # Pool de conexiones. Los valores se ajustan al límite real del plan.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    #: Exige TLS verificado. Sólo se desactiva para PostgreSQL local en desarrollo.
    require_tls: bool = False

    #: Certificado raíz del servidor de base de datos.
    #:
    #: Supabase firma su conexión directa con una CA propia que no está en los
    #: almacenes públicos, así que verificar contra ellos falla con
    #: «self-signed certificate in certificate chain». La solución correcta es
    #: confiar en **esa** CA, no desactivar la verificación: descargar el
    #: certificado desde Settings › Database › SSL Configuration y apuntarlo aquí.
    db_ssl_root_cert: str = ""

    # Límites de medios conversacionales.
    max_audio_seconds: int = 120
    max_media_bytes: int = 10 * 1024 * 1024
    media_retention_hours: int = 24

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    @property
    def runtime_database_url(self) -> str:
        """URL del runtime, con TLS comprobado.

        `sslmode=disable` se rechaza al arrancar en lugar de degradar en
        silencio: una conexión sin cifrar a una base administrada expone
        credenciales y contenido en tránsito, y es el tipo de fallo que nadie
        nota hasta que alguien lo aprovecha.
        """
        url = self.database_url
        if "sslmode=disable" in url.replace(" ", "").lower():
            raise ValueError(
                "sslmode=disable está prohibido: la conexión debe usar TLS verificado"
            )
        return url

    @property
    def migration_url(self) -> str:
        """URL para Alembic. Cae a la de runtime si no se configuró una directa."""
        return self.migration_database_url or self.runtime_database_url

    @property
    def asyncpg_connect_args(self) -> dict:
        """Argumentos del driver.

        Con `require_tls`, asyncpg exige un certificado **válido y verificado**.
        No se acepta `ssl=True` a secas, que cifra pero no comprueba la identidad
        del servidor y deja la puerta abierta a un intermediario.

        Si se indica `db_ssl_root_cert`, se confía en esa CA además de las
        públicas. Es lo que hace falta con Supabase, cuya conexión directa está
        firmada por una CA propia.
        """
        if not self.require_tls:
            return {}

        import ssl
        from pathlib import Path

        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        if self.db_ssl_root_cert:
            path = Path(self.db_ssl_root_cert)
            if not path.is_file():
                raise ValueError(
                    f"KINTI_DB_SSL_ROOT_CERT apunta a un archivo que no existe: {path}"
                )
            context.load_verify_locations(cafile=str(path))

            # Python 3.13+ activa `VERIFY_X509_STRICT` por defecto, que exige la
            # extensión `keyUsage` en los certificados de CA. La raíz que publica
            # Supabase es de 2021 y no la trae, así que la verificación fallaría
            # con «CA cert does not include key usage extension».
            #
            # Se relaja **sólo** ese requisito de forma del certificado. Lo que
            # importa se mantiene intacto: la cadena se sigue validando contra
            # esta CA concreta y el nombre del servidor se sigue comprobando. No
            # es equivalente a desactivar la verificación.
            context.verify_flags &= ~ssl.VERIFY_X509_STRICT

        return {"ssl": context}


@lru_cache
def get_settings() -> Settings:
    return Settings()
