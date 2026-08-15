"""El contrato congelado debe corresponder exactamente al backend actual."""

import json
from pathlib import Path

from app.main import app

CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "infrastructure"
    / "api"
    / "openapi.json"
)


def test_versioned_openapi_is_fresh_and_utf8() -> None:
    stored = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert stored == app.openapi(), (
        "OpenAPI desactualizado; ejecute `npm.cmd run api:contract` desde la raíz"
    )
