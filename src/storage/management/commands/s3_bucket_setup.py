"""Richtet den S3-Bucket für den direkten Upload aus dem Browser ein (ADR 0005).

- CORS: Der Browser lädt von der eigenen Domain direkt in den Bucket und muss den ETag lesen;
  x-amz-error-code braucht Uppy, um S3-Fehler mit Code statt als Netzwerkfehler zu melden.
- Lifecycle: Unvollständige Multipart-Uploads werden nach 7 Tagen abgeräumt.

Läuft bei jedem Deploy (deploy/auf-dem-host.sh). Danach fragt der Befehl den Bucket wie ein
Browser per CORS-Preflight; lehnt der Speicher die Herkunft ab, bricht er mit Fehler ab.
"""

import urllib.error
import urllib.request
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError

from storage import S3Request, get_storage
from storage.s3 import S3Storage

ABORT_AFTER_DAYS = 7
# Was Uppy beim Multipart-Upload direkt an den Bucket schickt.
BROWSER_METHODS = ("POST", "PUT", "GET", "DELETE")


def normalize_origin(origin: str) -> str:
    """Herkunft so, wie der Browser sie im `Origin`-Header schickt: Punycode, ohne Pfad.

    S3 vergleicht die Herkunft zeichengenau; `https://bücher.example` passt nie, weil der
    Browser `https://xn--bcher-kva.example` schickt.
    """
    parts = urlsplit(origin.strip())
    if not parts.scheme or not parts.hostname:
        raise CommandError(f"Keine gültige Herkunft: {origin}")
    if parts.path not in ("", "/") or parts.query or parts.fragment or parts.username:
        raise CommandError(f"Herkunft nur mit Schema und Host, ohne Pfad: {origin}")
    try:
        host = parts.hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise CommandError(f"Host lässt sich nicht in Punycode umwandeln: {origin}") from exc
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme.lower()}://{host}{port}"


def cors_rules(origins: list[str]) -> dict:
    return {
        "CORSRules": [
            {
                "AllowedOrigins": origins,
                "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag", "x-amz-error-code"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }


def lifecycle_rules() -> dict:
    return {
        "Rules": [
            {
                "ID": "unvollstaendige-uploads-abraeumen",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": ABORT_AFTER_DAYS},
            }
        ]
    }


def preflight_problems(storage: S3Storage, origin: str) -> list[str]:
    """Fragt den Bucket per CORS-Preflight wie der Browser; leer, wenn alles erlaubt ist."""
    url = storage.presign(S3Request(method="POST", key="cors-pruefung"))
    if not url.startswith(("https://", "http://")):
        return [f"signierter Link ist kein HTTP(S): {url}"]
    problems = []
    for method in BROWSER_METHODS:
        request = urllib.request.Request(  # noqa: S310  # Schema oben geprüft
            url,
            method="OPTIONS",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                allowed = response.headers.get("Access-Control-Allow-Origin")
        except urllib.error.HTTPError as exc:
            problems.append(f"{method}: Speicher antwortet {exc.code}")
            continue
        except OSError as exc:
            problems.append(f"{method}: Speicher nicht erreichbar ({exc})")
            continue
        if allowed not in (origin, "*"):
            problems.append(f"{method}: Access-Control-Allow-Origin ist {allowed!r}")
    return problems


class Command(BaseCommand):
    help = (
        "Setzt CORS-Freigabe und Lifecycle-Regel im S3-Bucket (STORAGE_BACKEND=s3) "
        "und prüft die Freigabe per CORS-Preflight."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--origin",
            action="append",
            required=True,
            help="Erlaubte Herkunft, z. B. https://upload.dzvf.de (mehrfach möglich)",
        )

    def handle(self, *args, **opts):
        storage = get_storage()
        if not isinstance(storage, S3Storage):
            raise CommandError("Nur mit STORAGE_BACKEND=s3 sinnvoll.")
        origins = []
        for given in opts["origin"]:
            origin = normalize_origin(given)
            if not origin.startswith(("https://", "http://localhost", "http://127.0.0.1")):
                raise CommandError(f"Herkunft muss HTTPS sein: {given}")
            if origin not in origins:
                origins.append(origin)
        client, bucket = storage.client, storage.bucket
        client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors_rules(origins))
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket, LifecycleConfiguration=lifecycle_rules()
        )
        self.stdout.write(
            f"Bucket {bucket}: CORS für {', '.join(origins)}, "
            f"unvollständige Uploads nach {ABORT_AFTER_DAYS} Tagen abräumen."
        )
        failed = {origin: p for origin in origins if (p := preflight_problems(storage, origin))}
        if failed:
            details = "; ".join(f"{o}: {', '.join(p)}" for o, p in failed.items())
            raise CommandError(
                f"CORS-Freigabe greift nicht, Uploads aus dem Browser würden scheitern. {details}"
            )
        self.stdout.write("CORS-Preflight für alle Herkünfte erfolgreich.")
