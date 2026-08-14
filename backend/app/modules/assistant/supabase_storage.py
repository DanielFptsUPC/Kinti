"""Almacenamiento privado sobre Supabase Storage.

Implementa el puerto `MediaStorage` contra la API REST de Storage. Los buckets
son **privados**: el contenido sólo se sirve mediante URLs firmadas de corta
duración, nunca por una ruta pública permanente.

La `service_role` key vive sólo aquí, en el backend. El cliente móvil jamás la
recibe: pide una URL firmada y sube contra ella.
"""

import hashlib
from urllib.parse import quote

import httpx

from app.modules.assistant.ports import MediaRef

#: Un archivo de conocimiento o un audio breve no justifican esperas largas.
DEFAULT_TIMEOUT = 30.0


class SupabaseStorageError(RuntimeError):
    """Fallo de Storage con el detalle ya saneado."""


class SupabaseMediaStorage:
    def __init__(self, *, url: str, service_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._base = url.rstrip("/") + "/storage/v1"
        self._key = service_key
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"apikey": self._key, "Authorization": f"Bearer {self._key}"}

    def _object_path(self, bucket: str, path: str) -> str:
        # Se codifica cada segmento por separado: la ruta puede llevar barras.
        safe = "/".join(quote(part, safe="") for part in path.split("/"))
        return f"{quote(bucket, safe='')}/{safe}"

    async def put(
        self, bucket: str, path: str, content: bytes, mime_type: str
    ) -> MediaRef:
        url = f"{self._base}/object/{self._object_path(bucket, path)}"
        headers = {
            **self._headers,
            "Content-Type": mime_type,
            # Permite reprocesar una versión sin tener que borrar antes.
            "x-upsert": "true",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, content=content, headers=headers)

        if response.status_code >= 400:
            raise SupabaseStorageError(
                f"No se pudo guardar el archivo (HTTP {response.status_code})"
            )

        return MediaRef(
            bucket=bucket,
            path=path,
            mime_type=mime_type,
            size_bytes=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
        )

    async def get(self, ref: MediaRef) -> bytes:
        url = f"{self._base}/object/{self._object_path(ref.bucket, ref.path)}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=self._headers)

        if response.status_code >= 400:
            raise SupabaseStorageError(
                f"No se pudo leer el archivo (HTTP {response.status_code})"
            )
        return response.content

    async def signed_url(self, ref: MediaRef, expires_in_seconds: int) -> str:
        """URL temporal. Nunca se expone una ruta pública permanente."""
        url = f"{self._base}/object/sign/{self._object_path(ref.bucket, ref.path)}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url, json={"expiresIn": expires_in_seconds}, headers=self._headers
            )

        if response.status_code >= 400:
            raise SupabaseStorageError(
                f"No se pudo firmar la URL (HTTP {response.status_code})"
            )

        signed = response.json().get("signedURL") or response.json().get("signedUrl", "")
        # La API devuelve una ruta relativa; se compone con el host del proyecto.
        return self._base.replace("/storage/v1", "") + "/storage/v1" + signed

    async def delete(self, ref: MediaRef) -> None:
        url = f"{self._base}/object/{self._object_path(ref.bucket, ref.path)}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.delete(url, headers=self._headers)

        # 404 se acepta: borrar algo que ya no está es el estado deseado.
        if response.status_code >= 400 and response.status_code != 404:
            raise SupabaseStorageError(
                f"No se pudo borrar el archivo (HTTP {response.status_code})"
            )
