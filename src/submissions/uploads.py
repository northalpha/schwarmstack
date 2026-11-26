"""Upload-Ablauf eines Masters über dem Speicher-Modul (ADR 0005, ADR 0009).

Der Browser führt die S3-Anfragen selbst aus; hier wird nur entschieden, welche Anfrage für
welchen Master signiert wird, und nach dem Upload der Master übernommen.
"""

import logging
import re
from datetime import timedelta
from decimal import ROUND_UP, Decimal
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from storage import S3Request, get_storage

from . import exposure, validation
from .models import Campaign, Master, Phase, Submission

# Endungen der Teilnehmenden -> Endung im Speicher
EXTENSIONS = {".xisf": ".xisf", ".fits": ".fits", ".fit": ".fits", ".fts": ".fits"}
log = logging.getLogger(__name__)

MAX_PARTS = 10_000
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
# Nach dieser Zeit gilt ein nie abgeschlossener Upload als aufgegeben (wie die Lifecycle-Regel).
STALE_AFTER = timedelta(days=7)
# So lange nach der letzten Anfrage läuft ein Upload vielleicht noch (Teile sind mindestens
# 5 MiB groß, über eine langsame Leitung dauert einer ein paar Minuten).
ACTIVE_WITHIN = timedelta(minutes=5)


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


def _usage_sums(prefix: str = "") -> tuple[Sum, Sum]:
    """Die eine Definition der Belegung: angenommene Master mit tatsächlicher Größe,
    laufende Uploads mit angemeldeter. `prefix` führt von einem anderen Modell zu den Mastern."""
    return (
        Sum(f"{prefix}size", filter=Q(**{f"{prefix}state": Master.State.ACCEPTED})),
        Sum(f"{prefix}declared_size", filter=Q(**{f"{prefix}state": Master.State.UPLOADING})),
    )


def usage_parts(masters) -> tuple[int, int]:
    """Belegung getrennt: (angenommen mit tatsächlicher Größe, reserviert mit angemeldeter)."""
    accepted, reserved = _usage_sums()
    totals = masters.aggregate(accepted=accepted, reserved=reserved)
    return totals["accepted"] or 0, totals["reserved"] or 0


def submission_usage():
    """Belegung je Submission als Ausdruck für `Submission.objects.annotate(used=…)`."""
    accepted, reserved = _usage_sums("masters__")
    return Coalesce(accepted, 0) + Coalesce(reserved, 0)


def usage(masters) -> int:
    """Belegung: angenommene Master plus Reservierungen laufender Uploads."""
    return sum(usage_parts(masters))


def quota_usage(submission: Submission) -> dict:
    """Belegung der Submission gegen ihre Quote, für die Anzeige."""
    campaign = Campaign.current()
    used = usage(submission.masters.all())
    quota = campaign.quota if campaign else 0
    return {"used": used, "quota": quota, "percent": min(100, used * 100 // quota) if quota else 0}


def check_global_cap(global_cap: int) -> None:
    """Die Gesamtgrenze darf nicht unter die aktuelle Belegung sinken (sonst ValidationError).

    Aufgegebene Uploads geben vorher ihre Reservierung frei, damit sie nicht mitzählen.
    """
    release_stale()
    used = usage(Master.objects.all())
    if global_cap < used:
        gib = (Decimal(used) / 1024**3).quantize(Decimal("0.000001"), ROUND_UP)
        raise ValidationError(
            f"Die Gesamtgrenze darf nicht unter der aktuellen Belegung liegen "
            f"({filesizeformat(used)}, aufgerundet {gib} GiB).",
            code="below_usage",
        )


def _check_limits(campaign: Campaign, submission: Submission, size: int) -> None:
    if size > campaign.max_master_size:
        raise UploadError(
            f"Ein Master darf höchstens {filesizeformat(campaign.max_master_size)} groß sein."
        )
    free = campaign.quota - usage(submission.masters.all())
    if size > free:
        raise UploadError(
            f"Dieser Master passt nicht mehr in die Quote deiner Submission: "
            f"noch {filesizeformat(max(free, 0))} frei."
        )
    if size > campaign.global_cap - usage(Master.objects.all()):
        raise UploadError(
            "Die Gesamtgrenze der Aktion ist erreicht. Bitte melde dich beim Betreiber."
        )


def _phase_refusal(*, starting: bool) -> str | None:
    """Zeitfenster der Aktion: neue Uploads nur während der Aktion, begonnene auch in der
    Nachfrist; danach ist jede Submission schreibgeschützt. Gibt den Grund einer Ablehnung
    zurück."""
    phase = Campaign.current_phase()
    if phase is Phase.BEFORE:
        return "Die Aktion hat noch nicht begonnen."
    if phase is Phase.CLOSED:
        return "Die Aktion ist vorbei, deine Submission ist schreibgeschützt."
    if starting and phase is not Phase.OPEN:
        return (
            "Die Aktion ist beendet. Neue Uploads sind nicht mehr möglich, "
            "begonnene kannst du in der Nachfrist noch abschließen."
        )
    return None


def _require_phase(*, starting: bool) -> None:
    if reason := _phase_refusal(starting=starting):
        raise UploadError(reason)


def may_start(submission: Submission) -> bool:
    """Ob die Submission jetzt einen neuen Upload beginnen darf."""
    return not submission.is_deleted and _phase_refusal(starting=True) is None


def interrupted(masters):
    """Unterbrochene Uploads, die sich noch fortsetzen oder abbrechen lassen: während der Aktion
    und in der Nachfrist. Danach ist die Submission schreibgeschützt."""
    if _phase_refusal(starting=False):
        return masters.none()
    return masters.filter(state=Master.State.UPLOADING)


def resumable(masters):
    """Unterbrochene Uploads, die sich fortsetzen lassen: Der Multipart-Upload im Speicher ist
    schon angelegt. Abbrechen lässt sich jeder unterbrochene (`interrupted`)."""
    return interrupted(masters).exclude(upload_id="")


def shows_uploader(submission: Submission) -> bool:
    """Ob die Submission-Seite den Uploader zeigt: zum Beginnen neuer Uploads oder, in der
    Nachfrist, zum Fortsetzen begonnener."""
    if submission.is_deleted:
        return False
    return may_start(submission) or resumable(submission.masters.all()).exists()


def recently_active(masters):
    """Uploads, die vielleicht gerade noch laufen, etwa in einem anderen Fenster."""
    return masters.filter(
        state=Master.State.UPLOADING, last_activity_at__gte=timezone.now() - ACTIVE_WITHIN
    )


def start(submission: Submission, *, channel, filename, size) -> tuple[Master, str]:
    """Legt einen Master an und gibt den signierten Link zum Anlegen des Multipart-Uploads."""
    _require_phase(starting=True)
    if submission.is_deleted:
        raise UploadError("Diese Submission wurde gelöscht.")
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
            channel_source=exposure.Source.MANUAL,
            original_name=filename.strip()[:255],
            declared_size=size,
            last_activity_at=timezone.now(),
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
    abort_multipart(master)
    master.state = Master.State.ABORTED
    master.save(update_fields=["state"])
    return master


def abort_multipart(master: Master) -> None:
    """Bricht den Multipart-Upload eines Masters im Speicher ab, wenn er eine Upload-ID hat.

    Scheitert das, wird es nur protokolliert: Aufräumen nach bestem Bemühen.
    """
    if not master.upload_id:
        return
    try:
        get_storage().abort_multipart(master.key, master.upload_id)
    except Exception:  # noqa: BLE001
        # Schon abgeräumt (vom Browser oder durch Abschluss) oder nie angelegt; die
        # Lifecycle-Regel räumt Reste ohnehin ab. Der Aufrufer macht trotzdem weiter.
        log.info("Multipart-Upload war schon weg: %s", master.public_id)


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

    master.upload_id = upload_id
    master.last_activity_at = timezone.now()
    master.save(update_fields=["upload_id", "last_activity_at"])
    return get_storage().presign(
        S3Request(method, key, upload_id, part_number, max_size=master.declared_size)
    )


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
    head = b""
    suffix = PurePosixPath(master.key).suffix
    if size != master.declared_size:
        result = validation.rejected(
            validation.Category.SIZE, "Die Größe weicht von der angemeldeten ab."
        )
    else:
        head = storage.read_head(master.key, validation.HEAD_BYTES)
        result = validation.check(
            head,
            suffix=suffix,
            channel=master.channel,
            channel_label=master.get_channel_display(),
            size=size,
        )
    if result.ok:
        result = _check_duplicates(master)

    exposure_fields = []
    if result.ok:
        master.state = Master.State.ACCEPTED
        # Belichtungsangaben aus demselben Range Request; sie stehen nicht in der Begleitdatei.
        exposure_fields = exposure.apply_header(master, exposure.read(head, suffix))
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
            *exposure_fields,
        ]
    )
    return master


def _check_duplicates(master: Master) -> validation.Result:
    """Dieselbe Datei in derselben Submission: ablehnen, in einer anderen: annehmen, markieren."""
    accepted = Master.objects.filter(sha256=master.sha256, state=Master.State.ACCEPTED).exclude(
        pk=master.pk
    )
    if accepted.filter(submission=master.submission).exists():
        return validation.rejected(
            validation.Category.DUPLICATE, "Diese Datei ist in deiner Submission schon vorhanden."
        )
    master.duplicate_of = accepted.order_by("created_at").first()
    return validation.ACCEPTED


def sidecar(master: Master) -> dict:
    """Angaben neben dem Master, damit die Zuordnung ohne Datenbank rekonstruierbar ist.

    Die Namensnennung steht nur bei gültiger Einwilligung zur Namensnennung darin.
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
