"""Adaptadores de telefonía por turnos de Kinti Voz.

La máquina de estados sólo produce :class:`TurnOutput`. Este módulo traduce
esa salida a TwiML y valida que una petición realmente proceda del proveedor.
No almacena audio, transcripciones ni números telefónicos.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring


class InvalidTelephonySignature(ValueError):
    """La petición no tiene una firma válida del proveedor configurado."""


FormValue = str | Sequence[str]


class RenderableTurn(Protocol):
    """Mínimo contrato estructural necesario para producir TwiML."""

    prompt: str
    expects_input: bool
    speech_rate: str


def twilio_request_signature(
    *, url: str, form: Mapping[str, FormValue], auth_token: str
) -> str:
    """Calcula la firma de una petición `application/x-www-form-urlencoded`.

    Twilio concatena la URL pública exacta con cada nombre de parámetro y su
    valor, ordenados por nombre, y firma el resultado con HMAC-SHA1. Admitimos
    valores repetidos para no perder campos al convertir ``FormData``.
    """
    if not auth_token:
        raise ValueError("TWILIO_AUTH_TOKEN no está configurado")

    payload = [url]
    for name in sorted(form):
        raw_value = form[name]
        values = [raw_value] if isinstance(raw_value, str) else list(raw_value)
        for value in values:
            payload.extend((name, value))

    digest = hmac.new(
        auth_token.encode("utf-8"),
        "".join(payload).encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def fake_webhook_signature(*, body: bytes, secret: str) -> str:
    """Firma HMAC-SHA256 del proveedor fake para pruebas de integración."""
    if not secret:
        raise ValueError("KINTI_TELEPHONY_WEBHOOK_SECRET no está configurado")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def validate_fake_webhook(*, body: bytes, signature: str | None, secret: str) -> None:
    expected = fake_webhook_signature(body=body, secret=secret)
    if not signature or not hmac.compare_digest(expected, signature):
        raise InvalidTelephonySignature("firma fake inválida")


@dataclass(frozen=True)
class TwilioTurnTelephonyGateway:
    """Valida webhooks Twilio y representa un turno como TwiML ``Gather``.

    ``webhook_base_url`` es una URL canónica configurada por despliegue. No se
    deriva de ``Host`` ni de cabeceras proxy controlables por un cliente.
    """

    auth_token: str
    webhook_base_url: str
    language: str = "es-PE"
    turn_path: str = "/api/v1/voice/turn"

    def __post_init__(self) -> None:
        parsed = urlsplit(self.webhook_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("TWILIO_WEBHOOK_BASE_URL debe ser una URL HTTPS pública")
        if parsed.username or parsed.password:
            raise ValueError("TWILIO_WEBHOOK_BASE_URL no debe contener credenciales")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError(
                "TWILIO_WEBHOOK_BASE_URL debe contener sólo esquema y host públicos"
            )
        if not self.auth_token:
            raise ValueError("TWILIO_AUTH_TOKEN no está configurado")

    def canonical_url(self, path: str, query: str = "") -> str:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("la ruta del webhook debe ser absoluta")
        base = self.webhook_base_url.rstrip("/")
        url = f"{base}{path}"
        return f"{url}?{query}" if query else url

    def validate(
        self,
        *,
        path: str,
        query: str,
        form: Mapping[str, FormValue],
        signature: str | None,
    ) -> None:
        if not signature:
            raise InvalidTelephonySignature("firma Twilio inválida")
        url = self.canonical_url(path, query)

        # El despliegue instala el SDK oficial. El fallback mantiene ejecutable
        # el dominio puro y sus pruebas en un entorno mínimo, pero la puerta de
        # telefonía real siempre usa RequestValidator para aceptar también
        # parámetros nuevos o repetidos que Twilio agregue en el futuro.
        try:
            from twilio.request_validator import RequestValidator
        except ImportError:  # pragma: no cover - sólo entornos de dominio mínimo
            expected = twilio_request_signature(
                url=url,
                form=form,
                auth_token=self.auth_token,
            )
            valid = hmac.compare_digest(expected, signature)
        else:
            valid = RequestValidator(self.auth_token).validate(url, form, signature)
        if not valid:
            raise InvalidTelephonySignature("firma Twilio inválida")

    def render(self, output: RenderableTurn) -> str:
        """Genera TwiML sin ``Record`` ni ``Media Streams``.

        La entrada por voz y DTMF llega al mismo endpoint y, si Twilio no
        detecta nada, igualmente envía el turno para que la política accesible
        decida si repregunta o deriva a una persona.
        """
        response = Element("Response")
        if output.expects_input:
            gather = SubElement(
                response,
                "Gather",
                {
                    "action": self.canonical_url(self.turn_path),
                    "actionOnEmptyResult": "true",
                    "input": "speech dtmf",
                    "language": self.language,
                    "method": "POST",
                    # Un valor numérico tolera pausas intermedias; ``auto``
                    # corta en la primera pausa y perjudica a quien habla lento.
                    "speechTimeout": "5",
                    "timeout": "8",
                },
            )
            say = SubElement(gather, "Say", {"language": self._say_language})
            say.text = output.prompt
            if output.speech_rate == "slow":
                SubElement(gather, "Pause", {"length": "1"})
        else:
            say = SubElement(response, "Say", {"language": self._say_language})
            say.text = output.prompt
            SubElement(response, "Hangup")

        return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(
            response, encoding="unicode", short_empty_elements=True
        )

    @property
    def _say_language(self) -> str:
        # Gather acepta es-PE. Las voces básicas de <Say> no lo ofrecen en
        # todos los proyectos Twilio; es-MX es el fallback español portable.
        return "es-MX" if self.language == "es-PE" else self.language
