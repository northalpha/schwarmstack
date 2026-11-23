"""Speicher für Master und Begleitdateien (ADR 0005).

Eine kleine Schnittstelle mit zwei Adaptern: lokale Platte (Tests, lokale Entwicklung) und S3.
Der Browser lädt Master per Multipart-Upload direkt in den Speicher; der Server stellt nur
signierte Links für einzelne S3-Anfragen aus und liest danach Größe und Header.
"""

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class S3Request:
    """Eine S3-Anfrage, die der Browser mit einem signierten Link ausführt."""

    method: str
    key: str
    upload_id: str | None = None
    part_number: int | None = None


class Storage(Protocol):
    def presign(self, request: S3Request) -> str: ...
    def size(self, key: str) -> int | None: ...
    def read_head(self, key: str, length: int) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def put_json(self, key: str, data: dict) -> None: ...
    def abort_multipart(self, key: str, upload_id: str) -> None: ...
    def ensure_reachable(self) -> None:
        """Wirft eine Ausnahme, wenn der Speicher nicht erreichbar ist."""
        ...


def get_storage() -> Storage:
    backend = settings.STORAGE_BACKEND
    if backend == "local":
        from .local import LocalStorage

        return LocalStorage(settings.STORAGE_LOCAL_DIR)
    if backend == "s3":
        from .s3 import S3Storage

        return S3Storage(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            region=settings.S3_REGION,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            addressing_style=settings.S3_ADDRESSING_STYLE,
            link_seconds=settings.UPLOAD_LINK_SECONDS,
        )
    raise ImproperlyConfigured(f"Unbekannter Speicher: {backend!r}")
