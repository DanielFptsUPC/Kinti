"""Contrato HTTP del piloto.

Los campos viajan en camelCase para coincidir con los tipos TypeScript del
cliente (`src/types/index.ts`). Aquí no hay lógica de dominio: sólo forma,
límites de tamaño y validación de entrada.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.config import get_settings

_MAX_NOTE = get_settings().max_note_length

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=_MAX_NOTE)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

MilestoneType = Literal["consultation", "laboratory", "procedure", "treatment", "follow_up"]
MilestoneStatus = Literal[
    "completed", "upcoming", "unscheduled", "support_needed", "rescheduled", "missed"
]
BarrierCategory = Literal[
    "transport",
    "lodging",
    "financial",
    "schedule",
    "instructions",
    "communication",
    "health_difficulty",
    "other",
]
AlertAction = Literal[
    "guidance",
    "reschedule",
    "social_work_referral",
    "lodging_coordination",
    "transport_coordination",
    "other",
]
AlertStatus = Literal["open", "in_progress", "resolved"]
SocialWorkStatus = Literal["pending", "contacted", "referred", "resolved"]
CapacityState = Literal["underused", "balanced", "high", "overbooked"]
Emotion = Literal["calm", "unsure", "worried", "tired"]
OperationalRisk = Literal["green", "yellow", "red"]
RouteStatus = Literal["on_track", "confirmation_needed", "support_needed"]
#: `patient` es la cuenta del menor. Sólo abre el espacio Compañero: el rol
#: viaja en el perfil para que el cliente sepa qué superficie montar, no para
#: concederle alcance operativo — eso lo decide el servidor en cada ruta.
Role = Literal["caregiver", "care_team", "patient"]


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


# --------------------------------------------------------------------------- identidad


class LoginRequest(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class TokenPair(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(ApiModel):
    refresh_token: str


class UserProfile(ApiModel):
    id: UUID
    email: str
    display_name: str
    role: Role


class MeResponse(ApiModel):
    user: UserProfile
    patient_ids: list[UUID]


# --------------------------------------------------------------------------- dominio


class PatientOut(ApiModel):
    id: UUID
    display_name: str
    age: int
    avatar_key: str
    caregiver_name: str
    contact_phone: str
    #: Derivados por el servidor. El cliente los muestra pero nunca los envía.
    operational_risk: OperationalRisk
    route_status: RouteStatus


class MilestoneOut(ApiModel):
    id: UUID
    patient_id: UUID
    type: MilestoneType
    title: str
    scheduled_at: datetime | None = None
    location: str | None = None
    preparation: str | None = None
    service: str | None = None
    confirmation_deadline: datetime | None = None
    status: MilestoneStatus
    attendance_confirmed: bool
    version: int


class AlertOut(ApiModel):
    id: UUID
    patient_id: UUID
    milestone_id: UUID
    category: BarrierCategory
    note: str | None = None
    status: AlertStatus
    #: Derivado por el servidor a partir del estado y la ventana de respuesta.
    risk: OperationalRisk
    family_contacted: bool
    action_taken: AlertAction | None = None
    internal_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class FeelingOut(ApiModel):
    id: UUID
    patient_id: UUID
    mood: Emotion
    created_at: datetime


class NotificationOut(ApiModel):
    id: UUID
    type: str
    patient_id: UUID | None = None
    title: str
    body: str
    created_at: datetime
    read_at: datetime | None = None


class RouteResponse(ApiModel):
    patient: PatientOut
    milestones: list[MilestoneOut]
    alerts: list[AlertOut]
    next_milestone_id: UUID | None = None


class RiskCounts(ApiModel):
    green: int
    yellow: int
    red: int


class OverviewResponse(ApiModel):
    counts: RiskCounts
    open_alerts: int
    generated_at: datetime


class CareTeamPatientRow(ApiModel):
    patient: PatientOut
    next_milestone: MilestoneOut | None = None
    has_open_barrier: bool
    has_missed: bool
    reason: str


class AlertDetail(ApiModel):
    alert: AlertOut
    milestone: MilestoneOut
    patient: PatientOut


class WorkloadRow(ApiModel):
    professional_id: UUID
    professional_name: str
    assigned_patients: int
    red_patients: int
    yellow_patients: int
    open_alerts: int
    missed_milestones: int
    weighted_load: int


class WorkloadResponse(ApiModel):
    rows: list[WorkloadRow]
    max_difference: int
    generated_at: datetime
    disclaimer: str


class CapacitySlotOut(ApiModel):
    id: UUID
    service: str
    starts_at: datetime
    ends_at: datetime
    available_places: int
    scheduled_patients: int
    occupancy_percent: int
    state: CapacityState


class CapacityResponse(ApiModel):
    slots: list[CapacitySlotOut]
    generated_at: datetime
    disclaimer: str


class SocialWorkQueueRow(ApiModel):
    alert_id: UUID
    patient_id: UUID
    patient_name: str
    category: BarrierCategory
    alert_status: AlertStatus
    coordination_status: SocialWorkStatus
    family_contacted: bool
    created_at: datetime


class SocialWorkQueueResponse(ApiModel):
    rows: list[SocialWorkQueueRow]
    generated_at: datetime


# --------------------------------------------------------------------------- comandos


class ConfirmAttendanceRequest(ApiModel):
    operation_id: UUID | None = None


class ReportBarrierRequest(ApiModel):
    category: BarrierCategory
    note: Note | None = None
    operation_id: UUID | None = None


class RecordFeelingRequest(ApiModel):
    mood: Emotion
    operation_id: UUID | None = None


class ContactFamilyRequest(ApiModel):
    operation_id: UUID | None = None


class ReferSocialWorkRequest(ApiModel):
    internal_note: Note | None = None
    operation_id: UUID | None = None


class ResolveAlertRequest(ApiModel):
    action_taken: AlertAction
    internal_note: Note | None = None
    new_scheduled_at: datetime | None = None
    operation_id: UUID | None = None


class CreateMilestoneRequest(ApiModel):
    type: MilestoneType
    title: Title
    scheduled_at: datetime | None = None
    location: ShortText | None = None
    preparation: Note | None = None
    service: ShortText | None = None
    confirmation_deadline: datetime | None = None
    operation_id: UUID | None = None


class RescheduleMilestoneRequest(ApiModel):
    new_scheduled_at: datetime
    operation_id: UUID | None = None


# --------------------------------------------------------------------------- sync


OperationType = Literal[
    "confirm_attendance",
    "report_barrier",
    "record_feeling",
    "mark_family_contacted",
    "refer_social_work",
    "resolve_alert",
    "create_milestone",
    "reschedule_milestone",
]


class SyncOperation(ApiModel):
    operation_id: UUID
    type: OperationType
    #: Identificador de la entidad objetivo: hito, alerta o paciente según el tipo.
    target_id: UUID
    payload: dict = Field(default_factory=dict)


class SyncOperationsRequest(ApiModel):
    operations: list[SyncOperation]


class SyncOperationResult(ApiModel):
    operation_id: UUID
    status: Literal["applied", "already_applied", "rejected"]
    error_code: str | None = None


class SyncOperationsResponse(ApiModel):
    results: list[SyncOperationResult]


class BootstrapResponse(ApiModel):
    """Instantánea canónica: todo lo que el cliente necesita para su caché."""

    user: UserProfile
    patients: list[PatientOut]
    milestones: list[MilestoneOut]
    alerts: list[AlertOut]
    feelings: list[FeelingOut]
    notifications: list[NotificationOut]
    server_time: datetime


# --------------------------------------------------------------- asistente (Fase 3)


Intent = Literal[
    "institutional_faq",
    "next_milestone_query",
    "attendance_confirmation",
    "report_barrier",
    "request_callback",
    "administrative_document_question",
    "clinical_or_safety_concern",
    "unknown",
]
Confidence = Literal["supported", "insufficient_evidence", "refused"]
Modality = Literal["text", "audio", "image"]

Question = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class StartSessionRequest(ApiModel):
    patient_id: UUID | None = None


class SessionOut(ApiModel):
    id: UUID
    patient_id: UUID | None = None
    status: str
    policy_version: str
    created_at: datetime


class CitationOut(ApiModel):
    """Cita comprensible: título, versión y sección. Sin URLs permanentes."""

    chunk_id: UUID
    document_title: str
    document_version: str
    section: str | None = None
    page: int | None = None


class ProposedActionOut(ApiModel):
    kind: Literal["report_barrier", "confirm_attendance", "request_callback"]
    #: Texto que se muestra para que la persona confirme conscientemente.
    summary: str
    payload: dict = Field(default_factory=dict)


class SendMessageRequest(ApiModel):
    text: Question = ""
    modality: Modality = "text"
    media_id: UUID | None = None
    operation_id: UUID | None = None


class AssistantMessageOut(ApiModel):
    message_id: UUID
    intent: Intent
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    confidence: Confidence
    needs_human: bool
    proposed_action: ProposedActionOut | None = None


class ConfirmActionRequest(ApiModel):
    #: Idempotencia del comando resultante.
    operation_id: UUID | None = None


class MediaUploadIntentRequest(ApiModel):
    modality: Literal["audio", "image"]
    mime_type: Annotated[str, StringConstraints(max_length=120)]
    size_bytes: int
    duration_seconds: float | None = None


class MediaUploadIntentResponse(ApiModel):
    media_id: UUID
    upload_url: str
    expires_in_seconds: int


# ------------------------------------------------------------- conocimiento


class CreateDocumentRequest(ApiModel):
    slug: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
    title: Title
    category: ShortText
    audience: Literal["caregiver", "care_team", "child", "public"] = "caregiver"
    language: Annotated[str, StringConstraints(max_length=8)] = "es"


class DocumentOut(ApiModel):
    id: UUID
    slug: str
    title: str
    category: str
    audience: str
    language: str
    is_active: bool


class CreateVersionRequest(ApiModel):
    version: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)]
    #: Contenido textual del documento sintético. En un despliegue real llegaría
    #: por URL firmada a un bucket privado.
    content: Annotated[str, StringConstraints(max_length=200_000)]
    mime_type: Annotated[str, StringConstraints(max_length=120)] = "text/markdown"


class VersionOut(ApiModel):
    id: UUID
    document_id: UUID
    version: str
    status: str
    checksum: str
    published_at: datetime | None = None
    retired_at: datetime | None = None


class VersionPreviewOut(ApiModel):
    version: VersionOut
    chunk_count: int
    sections: list[str] = Field(default_factory=list)


# ----------------------------------------------------- Kinti Compañero (Fase 4)


DevelopmentBand = Literal["early", "middle", "adolescent"]
SupportRequestType = Literal["want_to_talk", "feeling_scared", "need_help", "want_company"]
AccountStatus = Literal["active", "suspended", "locked"]

Alias = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
Pin = Annotated[str, StringConstraints(min_length=4, max_length=12)]


class PatientLoginRequest(ApiModel):
    """El menor entra con alias y PIN. No se le exige correo ni teléfono."""

    alias: Alias
    pin: Pin


class PatientAccountRequest(ApiModel):
    alias: Alias
    pin: Pin
    #: Consentimiento del apoderado, requerido por el procedimiento institucional.
    consent_confirmed: bool = False


class PatientAccountUpdateRequest(ApiModel):
    status: AccountStatus | None = None
    pin: Pin | None = None
    development_band: DevelopmentBand | None = None
    enabled_categories: dict[str, bool] | None = None


class PatientAccountOut(ApiModel):
    patient_id: UUID
    alias: str
    status: AccountStatus
    development_band: DevelopmentBand
    enabled_categories: dict[str, bool]
    consented_at: datetime | None = None


class CompanionActivityOut(ApiModel):
    key: str
    title: str
    duration_seconds: int


class ImmediatePreparationOut(ApiModel):
    """Preparación inmediata **sin** nombre clínico del procedimiento."""

    when: str
    bring: str | None = None
    company: str | None = None


class CompanionViewOut(ApiModel):
    """Todo lo que el menor puede ver. Lista blanca, no filtrado de la interfaz."""

    greeting: str
    chosen_name: str | None = None
    avatar_key: str | None = None
    comfort_object: str | None = None
    development_band: DevelopmentBand
    activities: list[CompanionActivityOut] = Field(default_factory=list)
    immediate_preparation: ImmediatePreparationOut | None = None


class CompanionPreferencesRequest(ApiModel):
    chosen_name: Annotated[str, StringConstraints(max_length=60)] | None = None
    avatar_key: Annotated[str, StringConstraints(max_length=40)] | None = None
    comfort_object: Annotated[str, StringConstraints(max_length=40)] | None = None


class SupportRequestCreate(ApiModel):
    request_type: SupportRequestType
    operation_id: UUID | None = None


class SupportRequestOut(ApiModel):
    id: UUID
    patient_id: UUID
    request_type: SupportRequestType
    status: Literal["open", "acknowledged", "closed"]
    created_at: datetime
    acknowledged_at: datetime | None = None
