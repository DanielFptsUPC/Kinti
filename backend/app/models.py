"""Registro único de modelos.

Alembic y las utilidades de pruebas importan este módulo para que todas las
tablas queden declaradas sobre el mismo `Base` antes de autogenerar o crear el
esquema.
"""

from app.core.database import Base
from app.modules.alerts.models import BarrierAlert
from app.modules.assistant.models import (
    AiRun,
    ConversationMedia,
    ConversationMessage,
    ConversationSession,
    RetrievalEvidence,
    SafetyEvent,
)
from app.modules.audit.models import AuditEvent
from app.modules.companion.models import (
    CompanionPreferences,
    PatientContentSettings,
    PatientSupportRequest,
    PatientUserLink,
)
from app.modules.feelings.models import FeelingCheckIn
from app.modules.identity.models import User
from app.modules.interventions.models import Intervention
from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
)
from app.modules.milestones.models import AttendanceConfirmation, Milestone
from app.modules.notifications.models import NotificationOutbox
from app.modules.operations.models import AmbulatoryCapacitySlot
from app.modules.patients.models import CaregiverPatientLink, CareTeamAssignment, Patient
from app.modules.sync.models import ProcessedOperation
from app.modules.voice.models import (
    AppointmentHold,
    AppointmentRequest,
    AppointmentSlot,
    CallbackRequest,
    ReferralCase,
    ServiceHour,
    VoiceEvent,
    VoiceSession,
)

__all__ = [
    "AiRun",
    "AmbulatoryCapacitySlot",
    "AttendanceConfirmation",
    "AuditEvent",
    "AppointmentHold",
    "AppointmentRequest",
    "AppointmentSlot",
    "BarrierAlert",
    "Base",
    "CareTeamAssignment",
    "CaregiverPatientLink",
    "CallbackRequest",
    "CompanionPreferences",
    "ConversationMedia",
    "ConversationMessage",
    "ConversationSession",
    "FeelingCheckIn",
    "Intervention",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeDocumentVersion",
    "KnowledgeIngestionJob",
    "Milestone",
    "NotificationOutbox",
    "Patient",
    "PatientContentSettings",
    "PatientSupportRequest",
    "PatientUserLink",
    "ProcessedOperation",
    "ReferralCase",
    "RetrievalEvidence",
    "SafetyEvent",
    "ServiceHour",
    "User",
    "VoiceEvent",
    "VoiceSession",
]
