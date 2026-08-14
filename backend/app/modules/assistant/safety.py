"""Política de seguridad del asistente.

Todo lo que hay aquí es **determinístico a propósito**. Si la seguridad clínica
dependiera de que un modelo se comporte, sería probabilística: un clasificador
con 0,95 de acierto falla una de cada veinte veces, y aquí ese fallo significa
responder a una consulta sobre dosis o interpretar un hemograma.

Estas reglas corren **antes** que el modelo y pueden cortocircuitarlo. El modelo
nunca puede desactivarlas, ni siquiera si el usuario o un documento se lo pide.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

SafetyCategory = Literal[
    "clinical_advice",
    "medication_or_dose",
    "result_interpretation",
    "emergency",
    "prompt_injection",
    "none",
]

SafetyAction = Literal["allow", "refuse_and_transfer", "strip_and_continue"]

#: Versión del prompt de sistema y de estas políticas. Se registra en cada `ai_run`
#: para que una respuesta pasada siga siendo explicable.
POLICY_VERSION = "2026-08-13.1"


def _normalize(text: str) -> str:
    """Minúsculas y sin tildes.

    Las familias escriben «dosis» y «dósis», «hemograma» y «emograma». Comparar
    sobre texto normalizado evita que una tilde omitida sortee una regla de
    seguridad.
    """
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


# Patrones por categoría. Deliberadamente amplios: un falso positivo deriva a una
# persona (molesto pero seguro); un falso negativo deja que la IA opine sobre
# tratamiento (inaceptable).
#
# Los patrones anclan al **inicio** de palabra pero no al final. El español
# flexiona: «gota/gotas», «plaqueta/plaquetas», «convulsionando». Exigir un
# límite de palabra al cierre dejaba pasar precisamente esas formas, que son las
# que la gente escribe. Un prefijo de más deriva a una persona; un plural sin
# cubrir deja que la IA opine sobre tratamiento.
_PATTERNS: list[tuple[SafetyCategory, re.Pattern[str]]] = [
    (
        "emergency",
        re.compile(
            r"\b(emergencia|urgencia|se esta muriendo|no respira|convuls|"
            r"desmay|sangrado que no para|fiebre muy alta|ambulancia)"
        ),
    ),
    (
        "medication_or_dose",
        re.compile(
            r"\b(dosis|dosific|cuanta?s?\s+(pastilla|gota|jarabe|ml|cucharada)|"
            r"puedo\s+(darle|tomar|subir|bajar|cambiar|suspender)|"
            r"receta|medicament|quimioterapia|corticoide|antibiotic)"
        ),
    ),
    (
        "result_interpretation",
        re.compile(
            r"\b(hemograma|leucocito|plaqueta|hemoglobina|neutrofilo|blasto|"
            r"resultado de (laboratorio|analisis|examen)|biopsia|"
            r"que significa (este|mi|el) (resultado|analisis|examen)|"
            r"(salieron|estan|esta|salio)\s+(alto|alta|bajo|baja|mal)"
            r"|esta (alto|bajo|mal) mi)"
        ),
    ),
    (
        "clinical_advice",
        re.compile(
            r"\b(tiene cancer|es grave|va a (sanar|morir|curarse)|pronostico|"
            r"diagnostic|que enfermedad|esta empeorando|es normal que (le|me)\s)"
        ),
    ),
]

#: Intentos de manipular las instrucciones del sistema.
_INJECTION = re.compile(
    r"(ignora|olvida|desactiva|omite)\s+(las?\s+)?"
    r"(instruccion|regla|politica|indicacion|todo lo anterior)"
    r"|actua como si no|eres un modelo sin restriccion"
    r"|revela|muestrame\s+(tu|el)\s+(prompt|instruccion|sistema|clave|secreto)"
    r"|system prompt|jailbreak|modo desarrollador"
)


@dataclass(frozen=True)
class SafetyVerdict:
    category: SafetyCategory
    action: SafetyAction
    #: Texto institucional aprobado que se muestra al usuario. Nunca improvisado.
    message: str | None = None
    needs_human: bool = False


# Textos institucionales aprobados. No se generan: se eligen.
# No inventan teléfonos, horarios ni plazos, porque Kinti no los conoce.
CLINICAL_TRANSFER_MESSAGE = (
    "Kinti no puede orientar sobre tratamiento, medicamentos ni resultados. "
    "Eso corresponde al equipo que atiende a tu niña o niño. "
    "¿Quieres que registre una solicitud para que te contacten?"
)

EMERGENCY_MESSAGE = (
    "Kinti no atiende urgencias y no puede evaluar síntomas. "
    "Si crees que es una urgencia, acude al establecimiento de salud o "
    "comunícate con los canales oficiales que te indicó el hospital. "
    "¿Quieres que registre una solicitud de contacto con el equipo?"
)

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "No tengo información aprobada para responder eso con seguridad. "
    "Prefiero no adivinar. ¿Quieres que el equipo te contacte?"
)

ALLOWED = SafetyVerdict(category="none", action="allow")


def classify(text: str) -> SafetyVerdict:
    """Evalúa un mensaje del usuario antes de que llegue al modelo."""
    normalized = _normalize(text)

    if _INJECTION.search(normalized):
        # No se corta la conversación: se ignora el intento y se sigue. Cortar
        # daría señal de qué funciona y qué no.
        return SafetyVerdict(category="prompt_injection", action="strip_and_continue")

    for category, pattern in _PATTERNS:
        if pattern.search(normalized):
            message = (
                EMERGENCY_MESSAGE if category == "emergency" else CLINICAL_TRANSFER_MESSAGE
            )
            return SafetyVerdict(
                category=category,
                action="refuse_and_transfer",
                message=message,
                needs_human=True,
            )

    return ALLOWED


def classify_image(category: str) -> SafetyVerdict:
    """Evalúa una imagen ya clasificada por tipo.

    Un documento administrativo puede explicarse; una receta, un resultado o una
    lesión se derivan sin interpretación alguna.
    """
    from app.modules.assistant.ports import CLINICAL_IMAGE_CATEGORIES

    if category in CLINICAL_IMAGE_CATEGORIES:
        return SafetyVerdict(
            category="result_interpretation",
            action="refuse_and_transfer",
            message=CLINICAL_TRANSFER_MESSAGE,
            needs_human=True,
        )
    return ALLOWED


def sanitize_document_text(text: str) -> str:
    """Neutraliza instrucciones incrustadas en un documento recuperado.

    Todo documento es contenido **no confiable**: puede haber sido redactado por
    alguien que quiere alterar el comportamiento del asistente. Las instrucciones
    que aparezcan dentro nunca deben modificar el prompt del sistema.
    """
    return _INJECTION.sub("[contenido omitido]", text)


def validate_response(
    intent: str, has_citations: bool, confidence: str
) -> SafetyVerdict:
    """Última puerta: valida la salida del modelo antes de mostrarla.

    Una respuesta informativa sin citas válidas no se muestra, por convincente
    que parezca. Es exactamente el caso en que un modelo alucina con seguridad.
    """
    if intent == "clinical_or_safety_concern":
        return SafetyVerdict(
            category="clinical_advice",
            action="refuse_and_transfer",
            message=CLINICAL_TRANSFER_MESSAGE,
            needs_human=True,
        )

    if intent == "institutional_faq" and confidence == "supported" and not has_citations:
        return SafetyVerdict(
            category="none",
            action="refuse_and_transfer",
            message=INSUFFICIENT_EVIDENCE_MESSAGE,
            needs_human=False,
        )

    return ALLOWED
