"""Richtet den S3-Bucket für den direkten Upload aus dem Browser ein (ADR 0005).

- CORS: Der Browser lädt von der eigenen Domain direkt in den Bucket und muss den ETag lesen.
- Lifecycle: Unvollständige Multipart-Uploads werden nach 7 Tagen abgeräumt.
"""

from django.core.management.base import BaseCommand, CommandError

from storage import get_storage
from storage.s3 import S3Storage

ABORT_AFTER_DAYS = 7


def cors_rules(origins: list[str]) -> dict:
    return {
        "CORSRules": [
            {
                "AllowedOrigins": origins,
                "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
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


class Command(BaseCommand):
    help = "Setzt CORS-Freigabe und Lifecycle-Regel im S3-Bucket (STORAGE_BACKEND=s3)."

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
        for origin in opts["origin"]:
            if not origin.startswith(("https://", "http://localhost", "http://127.0.0.1")):
                raise CommandError(f"Herkunft muss HTTPS sein: {origin}")
        client, bucket = storage.client, storage.bucket
        client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors_rules(opts["origin"]))
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket, LifecycleConfiguration=lifecycle_rules()
        )
        self.stdout.write(
            f"Bucket {bucket}: CORS für {', '.join(opts['origin'])}, "
            f"unvollständige Uploads nach {ABORT_AFTER_DAYS} Tagen abräumen."
        )
