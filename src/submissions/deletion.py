"""Löschung nach Ablauf der Löschfrist (ADR 0008).

Ein Cron-Job auf dem Host ruft `manage.py delete_after_export` täglich auf. Der Befehl ist
idempotent und tut erst etwas nach dem endgültigen Export: sieben Tage vor Ablauf der
Löschfrist eine Erinnerung an die Betreiber, nach Ablauf die Löschung aller Master,
Begleitdateien und Angaben und eine Meldung danach. Die Sicherungen bleiben stehen.
"""

import enum
import logging
from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from schwarmstack import notices
from schwarmstack.models import LoginAttempt
from storage import BACKUP_PREFIX, get_storage

from .models import Campaign, Submission

WARN_BEFORE = timedelta(days=7)
log = logging.getLogger(__name__)


class Outcome(enum.Enum):
    NOTHING = "nichts zu tun"
    WARNED = "an die Löschung erinnert"
    DELETED = "gelöscht"
    INCOMPLETE = "unvollständig, der nächste Lauf versucht es erneut"


def run() -> Outcome:
    campaign = Campaign.current()
    if campaign is None or not campaign.is_exported or campaign.data_deleted_at is not None:
        return Outcome.NOTHING
    now = timezone.now()
    if now >= campaign.deletes_at:
        return Outcome.DELETED if _delete(campaign) else Outcome.INCOMPLETE
    if now >= campaign.deletes_at - WARN_BEFORE and campaign.deletion_warned_at is None:
        when = timezone.localtime(campaign.deletes_at)
        if notices.send(
            "Löschung in sieben Tagen",
            f"Die Löschfrist läuft am {when:%d.%m.%Y um %H:%M} ab. Danach löscht Schwarmstack "
            "alle Master, Begleitdateien und Angaben; neue Download-Links gibt es dann nicht "
            "mehr. Bitte bis dahin alle Master herunterladen.",
        ):
            # Erst nach dem Versand vermerken: Schlägt er fehl, erinnert der nächste Lauf.
            campaign.deletion_warned_at = now
            campaign.save(update_fields=["deletion_warned_at"])
        return Outcome.WARNED
    return Outcome.NOTHING


def _delete(campaign: Campaign) -> bool:
    """Erst der Speicher, dann die Datenbank; gibt zurück, ob alles gelöscht ist.

    Ein Fehler bei einem Objekt (auch bei einem Equipment-Foto oder seinem Thumbnail) bricht den
    Lauf nicht ab: Alle übrigen Objekte werden trotzdem gelöscht. Blieb etwas liegen, bleiben auch
    die Datenbank und `data_deleted_at` stehen, die Betreiber bekommen eine Meldung, und der
    nächste Lauf fängt von vorn an.
    """
    storage = get_storage()
    deleted = 0
    failed = 0
    for key in list(storage.keys()):
        if key.startswith(BACKUP_PREFIX):
            continue
        try:
            storage.delete(key)
            deleted += 1
        except Exception:
            # Der Schlüssel enthält nur die Submission-ID, nichts aus Dateien der Teilnehmenden.
            log.exception("Objekt %s ließ sich nach Ablauf der Löschfrist nicht löschen", key)
            failed += 1
    if failed:
        notices.send(
            "Löschung unvollständig",
            f"Nach Ablauf der Löschfrist ließen sich {failed} Objekte im Speicher nicht löschen "
            f"({deleted} wurden gelöscht). Die Datenbank bleibt bis dahin stehen; der nächste "
            "tägliche Lauf versucht es erneut. Bitte den Speicher prüfen.",
        )
        return False
    with transaction.atomic():
        Submission.objects.all().delete()  # mit Mastern und Einwilligungen
        # Das Protokoll nennt Submission-IDs und Dateinamen. Was die Aktion betrifft (Export,
        # Links), enthält keine Angaben von Teilnehmenden und bleibt.
        LogEntry.objects.exclude(content_type=ContentType.objects.get_for_model(Campaign)).delete()
        LoginAttempt.objects.all().delete()
        campaign.data_deleted_at = timezone.now()
        campaign.save(update_fields=["data_deleted_at"])
    log.info("Löschfrist abgelaufen: %d Objekte und alle Submissions gelöscht", deleted)
    notices.send(
        "Daten gelöscht",
        "Die Löschfrist ist abgelaufen. Schwarmstack hat alle Master, Begleitdateien und Angaben "
        f"gelöscht ({deleted} Objekte im Speicher); die Sicherungen laufen von selbst aus. "
        "Die Installation kann jetzt abgebaut werden.",
    )
    return True
