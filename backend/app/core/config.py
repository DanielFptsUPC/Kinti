from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
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

    # --- Fase 5: Kinti Voz -------------------------------------------------
    # Todos los adaptadores externos permanecen apagados por omisión. Un error
    # de configuración no debe abrir una línea, gastar saldo ni afirmar una
    # cita institucional inexistente.
    telephony_provider: Literal["fake", "twilio"] = "fake"
    # Streaming pertenece a 5B y todavía no tiene una ruta habilitada.
    voice_mode: Literal["turn"] = "turn"
    voice_language: str = "es-PE"
    voice_default_speech_rate: Literal["slow", "normal"] = "slow"
    voice_max_call_seconds: int = Field(default=480, ge=60, le=1800)
    voice_max_reprompts: int = Field(default=2, ge=1, le=5)
    voice_recording_enabled: bool = False
    voice_transcript_retention_enabled: bool = False
    voice_callback_enabled: bool = True

    referral_provider: Literal["fake", "manual"] = "fake"
    scheduling_provider: Literal["fake", "manual"] = "fake"
    stt_provider: Literal["fake"] = "fake"
    tts_provider: Literal["fake"] = "fake"

    # Firma del simulador/webhook fake. En staging se genera como secreto; no
    # autentica a una persona, sólo evita aceptar webhooks fabricados.
    telephony_webhook_secret: str = "kinti-fake-webhook-solo-desarrollo"

    # Twilio usa nombres de entorno propios, sin el prefijo KINTI_. Se admiten
    # ambos nombres para no obligar a copiar credenciales entre convenciones.
    twilio_account_sid: str = Field(
        default="",
        validation_alias=AliasChoices("TWILIO_ACCOUNT_SID", "KINTI_TWILIO_ACCOUNT_SID"),
    )
    twilio_auth_token: str = Field(
        default="",
        validation_alias=AliasChoices("TWILIO_AUTH_TOKEN", "KINTI_TWILIO_AUTH_TOKEN"),
    )
    twilio_phone_number: str = Field(
        default="",
        validation_alias=AliasChoices("TWILIO_PHONE_NUMBER", "KINTI_TWILIO_PHONE_NUMBER"),
    )
    twilio_webhook_base_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TWILIO_WEBHOOK_BASE_URL", "KINTI_TWILIO_WEBHOOK_BASE_URL"
        ),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _validate_voice_safety_gate(self) -> "Settings":
        """Impide activar telefonía real o retención sensible a medias."""
        if self.voice_recording_enabled or self.voice_transcript_retention_enabled:
            raise ValueError(
                "Fase 5A no admite grabación ni retención de transcripciones"
            )
        if self.environment not in {"local", "test"} and (
            self.telephony_webhook_secret
            == "kinti-fake-webhook-solo-desarrollo"
            or len(self.telephony_webhook_secret) < 32
        ):
            raise ValueError(
                "KINTI_TELEPHONY_WEBHOOK_SECRET debe ser aleatorio fuera de local"
            )
        if self.telephony_provider == "twilio":
            missing = [
                name
                for name, value in (
                    ("TWILIO_ACCOUNT_SID", self.twilio_account_sid),
                    ("TWILIO_AUTH_TOKEN", self.twilio_auth_token),
                    ("TWILIO_PHONE_NUMBER", self.twilio_phone_number),
                    ("TWILIO_WEBHOOK_BASE_URL", self.twilio_webhook_base_url),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "KINTI_TELEPHONY_PROVIDER=twilio requiere: " + ", ".join(missing)
                )
            if not self.twilio_webhook_base_url.startswith("https://"):
                raise ValueError("TWILIO_WEBHOOK_BASE_URL debe usar HTTPS")
            # El adaptador y su firma se prueban de forma contractual, pero el
            # runtime actual usa una máquina fake en memoria. Activar un número
            # real antes de disponer de reanudación durable y gateways
            # institucionales haría posible una solicitud no persistida.
            raise ValueError(
                "Twilio permanece bloqueado en Fase 5A hasta conectar workflow "
                "durable y gateways institucionales autorizados"
            )
        return self

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
