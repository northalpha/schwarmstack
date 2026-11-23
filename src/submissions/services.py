"""Fachverhalten rund um die Abgabe: anlegen, Master löschen, Rückzug, Widerruf.

Admin und Abgabeseite rufen diese Operationen auf; sie selbst kennen keine Anfrage.
"""

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from storage import get_storage

from . import references
from .models import Consent, Master, Submission
from .uploads import sidecar

_ATTEMPTS = 5
log = logging.getLogger(__name__)


def create_submission(*, credit_name, setup_description, publish_credit) -> Submission:
    """Legt eine Abgabe samt Einwilligungen an und vergibt eine freie Abgabe-Kennung."""
    kinds = [Consent.Kind.PROJECT_USE]
    if publish_credit:
        kinds.append(Consent.Kind.PUBLISH_CREDIT)
    for _ in range(_ATTEMPTS):
        reference = references.new_reference(
            lambda r: Submission.objects.filter(reference=r).exists()
        )
        try:
            with transaction.atomic():
                submission = Submission.objects.create(
                    reference=reference,
                    credit_name=credit_name,
                    setup_description=setup_description,
                )
                Consent.objects.bulk_create(
                    Consent(
                        submission=submission,
                        kind=kind,
                        text_version=settings.CONSENT_TEXT_VERSION,
                    )
                    for kind in kinds
                )
            return submission
        except IntegrityError:  # gleichzeitig dieselbe Kennung gezogen
            continue
    raise RuntimeError("Abgabe konnte nicht angelegt werden")


# Nur diese Master lassen sich löschen; abgelehnte und abgebrochene haben keine Datei mehr.
DELETABLE = (Master.State.ACCEPTED, Master.State.UPLOADING)


def delete_master(master: Master) -> None:
    """Löscht einen Master: Datei und Begleitdatei sofort aus dem Speicher, dann den Datensatz.

    Ein Master im Upload wird über das Speicher-Modul abgebrochen. Zeigen andere Master als
    Dublette auf ihn, wird der früheste von ihnen zum Original.
    """
    storage = get_storage()
    if master.state == Master.State.UPLOADING and master.upload_id:
        try:
            storage.abort_multipart(master.key, master.upload_id)
        except Exception:  # noqa: BLE001
            # Schon abgeräumt oder abgeschlossen; das Objekt wird unten ohnehin gelöscht.
            log.info("Multipart-Upload war schon weg: %s", master.public_id)
    storage.delete(master.key)
    storage.delete(master.sidecar_key)

    with transaction.atomic():
        duplicates = list(master.duplicates.order_by("created_at"))
        if duplicates:
            new_original, *rest = duplicates
            new_original.duplicate_of = None
            new_original.save(update_fields=["duplicate_of"])
            for duplicate in rest:
                duplicate.duplicate_of = new_original
                duplicate.save(update_fields=["duplicate_of"])
        master.delete()
    for duplicate in duplicates:
        if duplicate.state == Master.State.ACCEPTED:
            storage.put_json(duplicate.sidecar_key, sidecar(duplicate))


def withdraw(submission: Submission, *, by: str) -> Submission:
    """Rückzug: löscht alle Master, Angaben und Einwilligungen samt Widerruf.

    Es bleiben die Abgabe-Kennung, der Zeitpunkt und wer den Rückzug ausgelöst hat. Eine
    zurückgezogene Abgabe zählt nicht mehr auf Quote oder Gesamtgrenze und öffnet nicht wieder.
    """
    if submission.is_withdrawn:
        return submission
    for master in submission.masters.all():
        if master.state in DELETABLE:
            delete_master(master)
    with transaction.atomic():
        submission.masters.all().delete()
        submission.consents.all().delete()
        submission.credit_name = ""
        submission.setup_description = ""
        submission.withdrawn_at = timezone.now()
        submission.withdrawn_by = by
        submission.save()
    return submission


def revoke(consent: Consent, *, by: str) -> Consent:
    """Widerruf einer Einwilligung: Sie bekommt einen Zeitpunkt und bleibt stehen.

    Der Widerruf der Nutzung im Projekt löst den Rückzug der ganzen Abgabe aus.
    """
    if consent.revoked_at is None:
        consent.revoked_at = timezone.now()
        consent.save(update_fields=["revoked_at"])
    if consent.kind == Consent.Kind.PROJECT_USE:
        withdraw(consent.submission, by=by)
    return consent
