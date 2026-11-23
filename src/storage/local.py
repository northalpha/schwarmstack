"""Speicher auf der lokalen Platte, der sich für den Browser wie S3 verhält.

Signierte Links zeigen auf einen app-eigenen Endpunkt (nur aktiv, wenn dieser Adapter
konfiguriert ist), der die nötigen S3-Antworten für Uppy nachbildet.
"""

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.urls import reverse

from . import S3Request

_SALT = "storage.local"
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(/[A-Za-z0-9][A-Za-z0-9_.-]*)*$")


class StorageError(Exception):
    pass


def sign_token(request: S3Request) -> str:
    payload = {"m": request.method, "k": request.key}
    if request.upload_id is not None:
        payload["u"] = request.upload_id
    if request.part_number is not None:
        payload["p"] = request.part_number
    return signing.dumps(payload, salt=_SALT, compress=True)


def read_token(token: str) -> S3Request:
    """Prüft Signatur und Ablauf; wirft signing.BadSignature."""
    payload = signing.loads(token, salt=_SALT, max_age=settings.UPLOAD_LINK_SECONDS)
    return S3Request(payload["m"], payload["k"], payload.get("u"), payload.get("p"))


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root)

    # -- Pfade -------------------------------------------------------------

    def _object(self, key: str) -> Path:
        if not _KEY.match(key) or ".." in key:
            raise StorageError(f"Ungültiger Schlüssel: {key!r}")
        return self.root / "objects" / key

    def _upload_dir(self, upload_id: str) -> Path:
        try:
            uuid.UUID(hex=upload_id)
        except (ValueError, TypeError) as exc:
            raise StorageError("Unbekannter Upload") from exc
        return self.root / "multipart" / upload_id

    def _checked_upload(self, key: str, upload_id: str) -> Path:
        directory = self._upload_dir(upload_id)
        meta = directory / "key"
        if not meta.exists() or meta.read_text() != key:
            raise StorageError("Unbekannter Upload")
        return directory

    # -- Schnittstelle für den Server --------------------------------------

    def presign(self, request: S3Request) -> str:
        return reverse("local_s3", args=[sign_token(request)])

    def size(self, key: str) -> int | None:
        path = self._object(key)
        return path.stat().st_size if path.exists() else None

    def read_head(self, key: str, length: int) -> bytes:
        with self._object(key).open("rb") as handle:
            return handle.read(length)

    def delete(self, key: str) -> None:
        self._object(key).unlink(missing_ok=True)

    def put_json(self, key: str, data: dict) -> None:
        path = self._object(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def abort_multipart(self, key: str, upload_id: str) -> None:
        shutil.rmtree(self._checked_upload(key, upload_id), ignore_errors=True)

    def ensure_reachable(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not os.access(self.root, os.W_OK):
            raise StorageError(f"Nicht beschreibbar: {self.root}")

    def download_url(self, key: str) -> str:
        self._object(key)  # Schlüssel prüfen
        return reverse("local_s3", args=[sign_token(S3Request("GET", key))])

    def open(self, key: str):
        """Öffnet ein Objekt zum Lesen (für den lokalen Download-Endpunkt)."""
        path = self._object(key)
        if not path.is_file():
            raise StorageError("Objekt nicht gefunden")
        return path.open("rb")

    # -- S3-Operationen für den Browser (über den lokalen Endpunkt) ---------

    def create_multipart(self, key: str) -> str:
        self._object(key)  # Schlüssel prüfen
        upload_id = uuid.uuid4().hex
        directory = self._upload_dir(upload_id)
        directory.mkdir(parents=True)
        (directory / "key").write_text(key)
        return upload_id

    def upload_part(self, key: str, upload_id: str, part_number: int, stream) -> str:
        """Schreibt einen Teil als Datenstrom; gibt den ETag (MD5) zurück."""
        directory = self._checked_upload(key, upload_id)
        digest = hashlib.md5(usedforsecurity=False)
        with (directory / f"part-{part_number:05d}").open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                out.write(chunk)
        return digest.hexdigest()

    def list_parts(self, key: str, upload_id: str) -> list[tuple[int, str, int]]:
        directory = self._checked_upload(key, upload_id)
        parts = []
        for path in sorted(directory.glob("part-*")):
            data = path.read_bytes()
            etag = hashlib.md5(data, usedforsecurity=False).hexdigest()
            parts.append((int(path.name[5:]), etag, len(data)))
        return parts

    def complete_multipart(self, key: str, upload_id: str, parts: list[tuple[int, str]]) -> str:
        directory = self._checked_upload(key, upload_id)
        known = {number: etag for number, etag, _ in self.list_parts(key, upload_id)}
        numbers = [number for number, _ in parts]
        if not parts or numbers != sorted(set(numbers)):
            raise StorageError("Teile fehlen oder sind nicht aufsteigend")
        for number, etag in parts:
            if known.get(number) != etag:
                raise StorageError(f"Teil {number} passt nicht")
        target = self._object(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.md5(usedforsecurity=False)
        with target.open("wb") as out:
            for number, _ in parts:
                data = (directory / f"part-{number:05d}").read_bytes()
                digest.update(data)
                out.write(data)
        shutil.rmtree(directory)
        return f"{digest.hexdigest()}-{len(parts)}"
