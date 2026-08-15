"""Política oral determinista y versionada de Kinti Voz."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo

from app.modules.voice.ports import (
    AppointmentSlot,
    ReferralResult,
    ReferralStatus,
    ServiceHour,
    TurnInput,
)

VOICE_POLICY_VERSION = "kinti-voice-es-PE@1"

WELCOME_PROMPT = (
    "Hola, soy Kinti, un asistente automático. Puedo ayudarle con la referencia "
    "y la cita de su niño. No necesita usar internet ni escribir. Puede pedir "
    "al Equipo asistencial en cualquier momento. ¿Su niño ya se atiende en el "
    "instituto?"
)
INTENT_PROMPT = (
    "Puedo informar un horario, revisar una referencia o ayudar con una cita. "
    "¿Qué necesita hacer?"
)
VERIFY_IDENTITY_PROMPT = (
    "Para proteger sus datos, diga el nombre de su niño y otro dato que ya "
    "registró con el instituto. ¿Cuáles son?"
)
FIND_REFERRAL_PROMPT = "¿En qué hospital atendieron a su niño?"
HUMAN_HANDOFF_MESSAGE = (
    "He pedido apoyo al Equipo asistencial. Revisarán el caso y devolverán la "
    "llamada."
)
CLINICAL_HANDOFF_MESSAGE = (
    "No puedo evaluar síntomas, resultados ni medicamentos. He pedido que una "
    "persona del Equipo asistencial le ayude. Si necesita atención inmediata, "
    "use el canal de emergencia indicado por su institución."
)


class AccessibilityCommand(StrEnum):
    REPEAT = "repeat"
    SLOW_DOWN = "slow_down"
    DID_NOT_UNDERSTAND = "did_not_understand"
    BACK = "back"
    HUMAN = "human"


_WEEKDAYS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
_WEEKDAYS_PLURAL = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábados",
    "domingos",
)
_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_UNITS = {
    0: "cero",
    1: "uno",
    2: "dos",
    3: "tres",
    4: "cuatro",
    5: "cinco",
    6: "seis",
    7: "siete",
    8: "ocho",
    9: "nueve",
    10: "diez",
    11: "once",
    12: "doce",
    13: "trece",
    14: "catorce",
    15: "quince",
    16: "dieciséis",
    17: "diecisiete",
    18: "dieciocho",
    19: "diecinueve",
    20: "veinte",
    21: "veintiuno",
    22: "veintidós",
    23: "veintitrés",
    24: "veinticuatro",
    25: "veinticinco",
    26: "veintiséis",
    27: "veintisiete",
    28: "veintiocho",
    29: "veintinueve",
    30: "treinta",
    31: "treinta y uno",
}

_CLINICAL_TERMS = (
    "fiebre",
    "sangrado",
    "vomito",
    "dolor",
    "dosis",
    "medicamento",
    "resultado",
    "hemograma",
    "desmayo",
    "convulsion",
    "respira",
    "emergencia",
    "urgencia",
)


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold().strip())
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks)


def accessibility_command(turn: TurnInput) -> AccessibilityCommand | None:
    value = normalize(turn.value)
    if turn.modality == "dtmf":
        return {
            "0": AccessibilityCommand.HUMAN,
            "8": AccessibilityCommand.SLOW_DOWN,
            "9": AccessibilityCommand.REPEAT,
            "*": AccessibilityCommand.BACK,
        }.get(value)

    if any(phrase in value for phrase in ("persona", "humano", "alguien", "operador")):
        return AccessibilityCommand.HUMAN
    if "mas despacio" in value or "hable lento" in value:
        return AccessibilityCommand.SLOW_DOWN
    if any(phrase in value for phrase in ("repita", "repetir", "otra vez")):
        return AccessibilityCommand.REPEAT
    if any(phrase in value for phrase in ("no entendi", "no comprendi", "no se")):
        return AccessibilityCommand.DID_NOT_UNDERSTAND
    if any(phrase in value for phrase in ("volver", "atras", "regresar")):
        return AccessibilityCommand.BACK
    return None


def is_clinical_or_safety_question(text: str) -> bool:
    value = normalize(text)
    return any(term in value for term in _CLINICAL_TERMS)


def parse_yes_no(turn: TurnInput) -> bool | None:
    value = normalize(turn.value)
    if turn.modality == "dtmf":
        if value == "1":
            return True
        if value == "2":
            return False
        return None
    if value in {"si", "claro", "correcto", "confirmo", "continuar", "de acuerdo"}:
        return True
    if value in {"no", "cancelar", "rechazo", "cambiar"}:
        return False
    return None


def parse_intent(turn: TurnInput) -> Literal["referral", "hours", "appointment"] | None:
    value = normalize(turn.value)
    if turn.modality == "dtmf":
        return {"1": "referral", "2": "hours", "3": "appointment"}.get(value)
    if "horario" in value or "a que hora" in value:
        return "hours"
    if "referencia" in value:
        return "referral"
    if "cita" in value or "turno" in value:
        return "appointment"
    return None


def parse_option_number(turn: TurnInput, option_count: int) -> int | None:
    if option_count == 1 and parse_yes_no(turn) is True:
        return 1
    value = normalize(turn.value)
    candidates = {
        "1": 1,
        "uno": 1,
        "opcion uno": 1,
        "primera": 1,
        "la primera": 1,
        "2": 2,
        "dos": 2,
        "opcion dos": 2,
        "segunda": 2,
        "la segunda": 2,
    }
    selected = candidates.get(value)
    if selected is None or selected > option_count:
        return None
    return selected


def parse_support_needs(text: str) -> tuple[str, ...]:
    value = normalize(text)
    needs: list[str] = []
    if "alojamiento" in value or "albergue" in value or "donde qued" in value:
        needs.append("lodging")
    if "transporte" in value or "pasaje" in value or "viaje" in value:
        needs.append("transport")
    return tuple(needs)


def referral_message(result: ReferralResult) -> str:
    if result.status == ReferralStatus.RECEIVED:
        return "La referencia llegó y todavía está siendo revisada."
    if result.status == ReferralStatus.IN_REVIEW:
        return "La referencia está en revisión. Aún no puedo ofrecer una cita."
    if result.status == ReferralStatus.OBSERVED:
        if result.missing_requirement_codes:
            return "Falta completar un requisito. Una persona le explicará cuál."
        return "La referencia está observada. Una persona revisará qué falta."
    if result.status == ReferralStatus.APPROVED:
        return "La referencia fue aprobada. Ahora buscaré alternativas de cita."
    return "No pude encontrar la referencia con seguridad. Una persona la revisará."


def speak_date_es_pe(value: datetime) -> str:
    local = value
    if value.tzinfo is not None:
        local = value.astimezone(ZoneInfo("America/Lima"))
    day = _UNITS[local.day]
    year = _speak_year(local.year)
    return (
        f"{_WEEKDAYS[local.weekday()]} {day} de {_MONTHS[local.month - 1]} "
        f"de {year}, a las {speak_time_es_pe(local.time())}"
    )


def speak_time_es_pe(value: time) -> str:
    hour = value.hour
    if hour == 0:
        spoken_hour, period = "doce", "de la noche"
    elif hour < 12:
        spoken_hour, period = _hour_word(hour), "de la mañana"
    elif hour == 12:
        spoken_hour, period = "doce", "del mediodía"
    elif hour < 19:
        spoken_hour, period = _hour_word(hour - 12), "de la tarde"
    else:
        spoken_hour, period = _hour_word(hour - 12), "de la noche"
    minute = "" if value.minute == 0 else f" y {_number_under_100(value.minute)}"
    return f"{spoken_hour}{minute} {period}"


def format_option(number: int, slot: AppointmentSlot) -> str:
    label = "uno" if number == 1 else "dos"
    phrase = f"Opción {label}. {speak_date_es_pe(slot.starts_at)}."
    if slot.related_activity:
        phrase += f" Puede realizar {slot.related_activity} ese mismo día."
    return phrase


def format_service_hours(hours: list[ServiceHour]) -> str:
    if not hours:
        return "No encontré un horario publicado y vigente."
    first = hours[0]
    return (
        f"{first.service} atiende los {_WEEKDAYS_PLURAL[first.weekday]}, de "
        f"{speak_time_es_pe(first.opens_at)} a {speak_time_es_pe(first.closes_at)}, "
        f"en {first.spoken_location}."
    )


def teach_back_matches(text: str, starts_at: datetime) -> bool:
    value = normalize(text)
    day_word = normalize(_UNITS[starts_at.day])
    month = normalize(_MONTHS[starts_at.month - 1])
    numeric_day = str(starts_at.day)
    return (day_word in value or numeric_day in value) and month in value


def assert_accessible_prompt(prompt: str) -> None:
    """Falla pronto si un cambio introduce más de una pregunta por turno."""
    if prompt.count("?") > 1:
        raise ValueError("La política oral permite una sola pregunta por turno")


def _hour_word(hour: int) -> str:
    if hour == 1:
        return "una"
    return _UNITS[hour]


def _speak_year(year: int) -> str:
    if 2000 <= year <= 2099:
        remainder = year - 2000
        return "dos mil" if remainder == 0 else f"dos mil {_number_under_100(remainder)}"
    return str(year)


def _number_under_100(value: int) -> str:
    if value in _UNITS:
        return _UNITS[value]
    tens, units = divmod(value, 10)
    tens_word = {
        4: "cuarenta",
        5: "cincuenta",
        6: "sesenta",
        7: "setenta",
        8: "ochenta",
        9: "noventa",
    }[tens]
    return tens_word if units == 0 else f"{tens_word} y {_UNITS[units]}"
