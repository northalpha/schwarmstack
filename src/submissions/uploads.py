"""Upload-Ablauf eines Masters über dem Speicher-Modul (ADR 0005).

Der Browser führt die S3-Anfragen selbst aus; hier wird nur entschieden, welche Anfrage für
welchen Master signiert wird, und nach dem Upload der Master übernommen.
"""

import logging
import re
from datetime import timedelta
from pathlib import PurePosixPath

from django.db import transaction
from django.db.models import Q, Sum
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from storage import S3Request, get_storage

from . import validation
from .models import Campaign, Master, Phase, Submission

# Endungen der Teilnehmenden -> Endung im Speicher
EXTENSIONS = {".xisf": ".xisf", ".fits": ".fits", ".fit": ".fits", ".fts": ".fits"}
log = logging.getLogger(__name__)

MAX_PARTS = 10_000
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
# Nach dieser Zeit gilt ein nie abgeschlossener Upload als aufgegeben (wie die Lifecycle-Regel).
STALE_AFTER = timedelta(days=7)


class UploadError(Exception):
    """Anfrage ist ungültig (HTTP 400)."""


class NotFinished(Exception):
    """Der Upload ist im Speicher noch nicht abgeschlossen (HTTP 409)."""


class Conflict(Exception):
    """Der Master ist in einem Zustand, der das nicht erlaubt (HTTP 409)."""


def release_stale() -> None:
    """Aufgegebene Uploads geben ihre Reservierung frei."""
    Master.objects.filter(
        state=Master.State.UPLOADING, created_at__lt=timezone.now() - STALE_AFTER
    ).update(state=Master.State.ABORTED)


def usage_parts(masters) -> tuple[int, int]:
    """Belegung getrennt: (angenommen mit tatsächlicher Größe, reserviert mit angemeldeter)."""
    totals = masters.aggregate(
        accepted=Sum("size", filter=Q(state=Master.State.ACCEPTED)),
        reserved=Sum("declared_size", filter=Q(state=Master.State.UPLOADING)),
    )
    return totals["accepted"] or 0, totals["reserved"] or 0


def usage(masters) -> int:
    """Belegung: angenommene Master plus Reservierungen laufender Uploads."""
    return sum(usage_parts(masters))


def _check_limits(campaign: Campaign, submission: Submission, size: int) -> None:
    if size > campaign.max_master_size:
        raise UploadError(
            f"Ein Master darf höchstens {filesizeformat(campaign.max_master_size)} groß sein."
        )
    free = campaign.quota - usage(submission.masters.all())
    if size > free:
        raise UploadError(
            f"Dieser Master passt nicht mehr in die Quote deiner Abgabe: "
            f"noch {filesizeformat(max(free, 0))} frei."
        )
    if size > campaign.global_cap - usage(Master.objects.all()):
        raise UploadError(
            "Die Gesamtgrenze der Aktion ist erreicht. Bitte melde dich beim Betreiber."
        )


def _require_phase(*, starting: bool) -> None:
    """Zeitfenster der Aktion: neue Uploads nur während der Aktion, begonnene auch in der
    Nachfrist; danach ist jede Abgabe schreibgeschützt."""
    campaign = Campaign.current()
    phase = campaign.phase() if campaign else Phase.CLOSED
    if phase is Phase.BEFORE:
        raise UploadError("Die Aktion hat noch nicht begonnen.")
    if phase is Phase.CLOSED:
        raise UploadError("Die Aktion ist vorbei, deine Abgabe ist schreibgeschützt.")
    if starting and phase is not Phase.OPEN:
        raise UploadError(
            "Die Aktion ist beendet. Neue Uploads sind nicht mehr möglich, "
            "begonnene kannst du in der Nachfrist noch abschließen."
        )


def interrupted(masters):
    """Unterbrochene Uploads, die sich noch fortsetzen oder abbrechen lassen: während der Aktion
    und in der Nachfrist. Danach ist die Abgabe schreibgeschützt."""
    campaign = Campaign.current()
    phase = campaign.phase() if campaign else Phase.CLOSED
    if phase not in (Phase.OPEN, Phase.GRACE):
        return masters.none()
    return masters.filter(state=Master.State.UPLOADING)


def start(submission: Submission, *, channel, filename, size) -> tuple[Master, str]:
    """Legt einen Master an und gibt den signierten Link zum Anlegen des Multipart-Uploads."""
    _require_phase(starting=True)
    if submission.is_withdrawn:
        raise UploadError("Diese Abgabe wurde zurückgezogen.")
    if channel not in Master.Channel.values:
        raise UploadError("Bitte wähle einen gültigen Kanal.")
    if not isinstance(filename, str) or not filename.strip():
        raise UploadError("Dateiname fehlt.")
    suffix = EXTENSIONS.get(PurePosixPath(filename.lower()).suffix)
    if suffix is None:
        raise UploadError("Nur XISF- oder FITS-Dateien (.xisf, .fits, .fit, .fts).")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise UploadError("Ungültige Dateigröße.")

    campaign = Campaign.current()
    if campaign is None:
        raise UploadError("Die Aktion ist nicht eingerichtet.")

    # Prüfen und Reservieren in einer Transaktion: Bei SQLite (transaction_mode IMMEDIATE) sind
    # Schreibtransaktionen serialisiert, gleichzeitige Starts überziehen die Grenzen also nicht.
    with transaction.atomic():
        release_stale()
        _check_limits(campaign, submission, size)
        master = Master(
            submission=submission,
            channel=channel,
            original_name=filename.strip()[:255],
            declared_size=size,
        )
        master.key = f"{submission.reference}/{master.public_id.hex}{suffix}"
        master.save()
    return master, get_storage().presign(S3Request("POST", master.key))


def abort(master: Master) -> Master:
    """Bricht einen laufenden Upload ab und gibt die Reservierung frei."""
    _require_phase(starting=False)
    if master.state == Master.State.ABORTED:
        return master
    if master.state != Master.State.UPLOADING:
        raise Conflict("Dieser Master ist schon abgeschlossen.")
    if master.upload_id:
        try:
            get_storage().abort_multipart(master.key, master.upload_id)
        except Exception:  # noqa: BLE001
            # Schon abgeräumt (z. B. vom Browser) oder nie angelegt; die Lifecycle-Regel
            # räumt Reste ohnehin ab. Die Reservierung wird trotzdem freigegeben.
            log.info("Multipart-Upload war schon weg: %s", master.public_id)
    master.state = Master.State.ABORTED
    master.save(update_fields=["state"])
    return master


def sign(master: Master, *, method, key, upload_id=None, part_number=None) -> str:
    """Signiert eine S3-Anfrage des Browsers, wenn sie zu diesem Master passt."""
    _require_phase(starting=False)
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


def finish(master: Master, *, sha256) -> Master:
    """Prüft einen fertig hochgeladenen Master und nimmt ihn an oder lehnt ihn ab.

    Angenommen: Begleitdatei wird geschrieben. Abgelehnt: Datei wird gelöscht, Grund gespeichert.
    Die Prüfsumme kommt vom Browser und wird ungeprüft übernommen.
    """
    if not isinstance(sha256, str) or not _SHA256.match(sha256):
        raise UploadError("Ungültige Prüfsumme (erwartet: SHA-256 als 64 Hex-Zeichen).")
    _require_phase(starting=False)
    if master.state != Master.State.UPLOADING:
        return master
    storage = get_storage()
    size = storage.size(master.key)
    if size is None:
        raise NotFinished("Der Upload ist noch nicht abgeschlossen.")

    master.size = size
    master.completed_at = timezone.now()
    master.sha256 = sha256.lower()
    if size != master.declared_size:
        result = validation.rejected(
            validation.Category.SIZE, "Die Größe weicht von der angemeldeten ab."
        )
    else:
        result = validation.check(
            storage.read_head(master.key, validation.HEAD_BYTES),
            suffix=PurePosixPath(master.key).suffix,
            channel=master.channel,
            channel_label=master.get_channel_display(),
            size=size,
        )
    if result.ok:
        result = _check_duplicates(master)

    if result.ok:
        master.state = Master.State.ACCEPTED
        storage.put_json(master.sidecar_key, sidecar(master))
    else:
        master.state = Master.State.REJECTED
        master.rejection_reason = result.reason
        master.rejection_category = result.category
        storage.delete(master.key)
    master.save(
        update_fields=[
            "size",
            "completed_at",
            "state",
            "rejection_reason",
            "rejection_category",
            "sha256",
            "duplicate_of",
        ]
    )
    return master


def _check_duplicates(master: Master) -> validation.Result:
    """Dieselbe Datei in derselben Abgabe: ablehnen. In einer anderen: annehmen und markieren."""
    accepted = Master.objects.filter(sha256=master.sha256, state=Master.State.ACCEPTED).exclude(
        pk=master.pk
    )
    if accepted.filter(submission=master.submission).exists():
        return validation.rejected(
            validation.Category.DUPLICATE, "Diese Datei ist in deiner Abgabe schon vorhanden."
        )
    master.duplicate_of = accepted.order_by("created_at").first()
    return validation.ACCEPTED


def sidecar(master: Master) -> dict:
    """Angaben neben dem Master, damit die Zuordnung ohne Datenbank rekonstruierbar ist.

    Die Nennung steht nur bei gültiger Einwilligung zur Veröffentlichung darin.
    """
    submission = master.submission
    return {
        "reference": submission.reference,
        "credit_name": (submission.credit_name or None) if submission.publishes_credit else None,
        "channel": master.channel,
        "original_name": master.original_name,
        "size": master.size,
        "completed_at": master.completed_at.isoformat(),
        "master_id": master.public_id.hex,
        "sha256": master.sha256,
        "duplicate_of": (
            {
                "reference": master.duplicate_of.submission.reference,
                "master_id": master.duplicate_of.public_id.hex,
            }
            if master.duplicate_of
            else None
        ),
    }
