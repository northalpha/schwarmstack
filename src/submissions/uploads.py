"""Upload-Ablauf eines Masters über dem Speicher-Modul (ADR 0005).

Der Browser führt die S3-Anfragen selbst aus; hier wird nur entschieden, welche Anfrage für
welchen Master signiert wird, und nach dem Upload der Master übernommen.
"""

from pathlib import PurePosixPath

from django.utils import timezone

from storage import S3Request, get_storage

from .models import Master, Submission

# Endungen der Teilnehmenden -> Endung im Speicher
EXTENSIONS = {".xisf": ".xisf", ".fits": ".fits", ".fit": ".fits", ".fts": ".fits"}
MAX_PARTS = 10_000


class UploadError(Exception):
    """Anfrage ist ungültig (HTTP 400)."""


class NotFinished(Exception):
    """Der Upload ist im Speicher noch nicht abgeschlossen (HTTP 409)."""


def start(submission: Submission, *, channel, filename, size) -> tuple[Master, str]:
    """Legt einen Master an und gibt den signierten Link zum Anlegen des Multipart-Uploads."""
    if channel not in Master.Channel.values:
        raise UploadError("Bitte wähle einen gültigen Kanal.")
    if not isinstance(filename, str) or not filename.strip():
        raise UploadError("Dateiname fehlt.")
    suffix = EXTENSIONS.get(PurePosixPath(filename.lower()).suffix)
    if suffix is None:
        raise UploadError("Nur XISF- oder FITS-Dateien (.xisf, .fits, .fit, .fts).")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise UploadError("Ungültige Dateigröße.")

    master = Master(
        submission=submission,
        channel=channel,
        original_name=filename.strip()[:255],
        declared_size=size,
    )
    master.key = f"{submission.reference}/{master.public_id.hex}{suffix}"
    master.save()
    return master, get_storage().presign(S3Request("POST", master.key))


def sign(master: Master, *, method, key, upload_id=None, part_number=None) -> str:
    """Signiert eine S3-Anfrage des Browsers, wenn sie zu diesem Master passt."""
    if master.state != Master.State.UPLOADING:
        raise UploadError("Dieser Master ist schon abgeschlossen.")
    if key != master.key:
        raise UploadError("Schlüssel passt nicht zum Master.")
    if not isinstance(upload_id, str) or not upload_id:
        raise UploadError("Upload-ID fehlt.")
    if master.upload_id and upload_id != master.upload_id:
        raise UploadError("Upload-ID passt nicht zum Master.")

    if method == "PUT":
        if (
            isinstance(part_number, bool)
            or not isinstance(part_number, int)
            or not 1 <= part_number <= MAX_PARTS
        ):
            raise UploadError("Ungültige Teilnummer.")
    elif method in {"GET", "POST", "DELETE"}:
        part_number = None
    else:
        raise UploadError("Anfrage wird nicht signiert.")

    if not master.upload_id:
        master.upload_id = upload_id
        master.save(update_fields=["upload_id"])
    return get_storage().presign(S3Request(method, key, upload_id, part_number))


def finish(master: Master) -> Master:
    """Übernimmt einen fertig hochgeladenen Master und schreibt die Begleitdatei."""
    if master.state == Master.State.ACCEPTED:
        return master
    storage = get_storage()
    size = storage.size(master.key)
    if size is None:
        raise NotFinished("Der Upload ist noch nicht abgeschlossen.")

    master.size = size
    master.completed_at = timezone.now()
    master.state = Master.State.ACCEPTED
    storage.put_json(master.sidecar_key, sidecar(master))
    master.save(update_fields=["size", "completed_at", "state"])
    return master


def sidecar(master: Master) -> dict:
    """Angaben neben dem Master, damit die Zuordnung ohne Datenbank rekonstruierbar ist."""
    return {
        "reference": master.submission.reference,
        "credit_name": master.submission.credit_name,
        "channel": master.channel,
        "original_name": master.original_name,
        "size": master.size,
        "completed_at": master.completed_at.isoformat(),
        "master_id": master.public_id.hex,
    }
