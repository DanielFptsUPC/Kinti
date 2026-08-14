"""Vuelca el esquema OpenAPI a stdout.

Es la fuente del contrato que verifica la prueba de paridad del cliente:

    python -m app.openapi_export > ../src/infrastructure/api/openapi.json

No requiere levantar el servidor ni tener PostgreSQL disponible.
"""

import json

from app.main import app


def main() -> None:
    print(json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
