"""Espacio del paciente — Kinti Compañero.

Tres reglas gobiernan estas tablas, y ninguna es negociable:

- **La cuenta del menor está separada del registro asistencial.** Suspenderla no
  borra al paciente ni sus hitos: la continuidad clínica nunca puede depender de
  que un niño mantenga una sesión activa.
- **El vínculo es uno a uno y lo autoriza un adulto.** Un `patient_id` no es una
  credencial; el servidor lo deriva del token, nunca del cliente.
- **La expresión emocional usa opciones estructuradas.** No se crea un diario de
  texto libre que el producto no pueda proteger adecuadamente.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin

ACCOUNT_STATUSES = ("active", "suspended", "locked")

#: Bandas por desarrollo, no por edad cronológica: dos niños de 8 años pueden
#: necesitar lenguaje distinto.
DEVELOPMENT_BANDS = ("early", "middle", "adolescent")

#: Categorías de contenido que el cuidador habilita o desactiva.
CONTENT_CATEGORIES = (
    "breathing",
    "music",
    "drawing",
    "stories",
    "comfort_object",
    "caregiver_messages",
    "immediate_preparation",
)

#: Lo que el menor puede pedir. Estructurado a propósito: sin texto libre
#: obligatorio y sin nada que se parezca a describir un síntoma.
SUPPORT_REQUEST_TYPES = ("want_to_talk", "feeling_scared", "need_help", "want_company")

SUPPORT_REQUEST_STATUSES = ("open", "acknowledged", "closed")


class PatientUserLink(UuidPkMixin, TimestampMixin, Base):
    """Une una cuenta `patient` con un único registro asistencial.

    Se separa de `patients` porque el paciente existe como entidad clínica
    aunque su cuenta esté suspendida o todavía no se haya creado.
    """

    __tablename__ = "patient_user_links"
    __table_args__ = (
        # Uno a uno en ambas direcciones: ni una cuenta con dos pacientes, ni un
        # paciente con dos cuentas.
        UniqueConstraint("user_id", name="uq_patient_link_user"),
        UniqueConstraint("patient_id", name="uq_patient_link_patient"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")

    #: Quién autorizó el alta y cuándo se registró el consentimiento.
    activated_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Intentos fallidos de PIN. Bloquear la cuenta no afecta la ruta clínica.
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PatientContentSettings(UuidPkMixin, TimestampMixin, Base):
    """Qué puede ver el menor. Lo decide un adulto autorizado, no el producto."""

    __tablename__ = "patient_content_settings"
    __table_args__ = (UniqueConstraint("patient_id", name="uq_content_settings_patient"),)

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    development_band: Mapped[str] = mapped_column(String(24), nullable=False, default="middle")

    #: Mapa categoría → habilitada. Ausente equivale a habilitada por defecto
    #: sólo para las categorías seguras; ver `companion/service.py`.
    enabled_categories: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    #: Preparación inmediata: qué llevar o quién acompaña. Nunca el nombre
    #: clínico del procedimiento.
    show_immediate_preparation: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PatientSupportRequest(UuidPkMixin, Base):
    """«Quiero hablar», «tengo miedo», «necesito ayuda», «quiero compañía».

    Llega al adulto correspondiente. El sistema **no interpreta la causa** ni la
    convierte en una señal clínica.
    """

    __tablename__ = "patient_support_requests"

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requested_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    #: Idempotencia para el outbox del cliente infantil.
    operation_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True, nullable=True)


class CompanionPreferences(UuidPkMixin, TimestampMixin, Base):
    """Nombre elegido, avatar y objeto de confort.

    Vive aparte del cuidador: es el espacio del niño, y su contenido no se mezcla
    con la sesión adulta.
    """

    __tablename__ = "companion_preferences"
    __table_args__ = (UniqueConstraint("patient_id", name="uq_companion_prefs_patient"),)

    patient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chosen_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    avatar_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    comfort_object: Mapped[str | None] = mapped_column(String(40), nullable=True)
