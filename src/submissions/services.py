"""Fachverhalten rund um die Abgabe: anlegen, Master löschen, Rückzug, Widerruf.

Admin und Abgabeseite rufen diese Operationen auf; sie selbst kennen keine Anfrage.
"""

from pathlib import PurePosixPath

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from storage import get_storage

from . import exposure, references, validation
from .models import Campaign, Consent, Master, Submission
from .uploads import abort_multipart, sidecar

_ATTEMPTS = 5


def create_submission(*, credit_name, setup_description, publish_credit) -> Submission:
    """Legt eine Abgabe samt Einwilligungen an und vergibt eine freie Abgabe-Kennung.

    Die Nennung gibt es nur mit der Einwilligung zur Veröffentlichung; ohne sie wird ein
    eingegebener Name verworfen und die Abgabe bleibt anonym.
    """
    kinds = [Consent.Kind.PROJECT_USE]
    if publish_credit:
        kinds.append(Consent.Kind.PUBLISH_CREDIT)
    else:
        credit_name = ""
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
    if master.state == Master.State.UPLOADING:
        abort_multipart(master)
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


def details_corrected(submission: Submission) -> None:
    """Nach einer Änderung von Nennung oder Setup (im Admin oder durch einen Widerruf) die
    Begleitdateien neu schreiben, damit die Zuordnung ohne Datenbank stimmt (ADR 0006).

    Ohne gültige Einwilligung zur Veröffentlichung bleibt die Abgabe anonym: Eine nachträglich
    eingetragene Nennung wird verworfen.
    """
    if submission.credit_name and not submission.publishes_credit:
        submission.credit_name = ""
        submission.save(update_fields=["credit_name"])
    storage = get_storage()
    for master in submission.masters.filter(state=Master.State.ACCEPTED):
        storage.put_json(master.sidecar_key, sidecar(master))


def changeable_by_participant(submission: Submission) -> bool:
    """Ob Teilnehmende selbst Master löschen oder die Abgabe zurückziehen dürfen: nur bis zum
    Ende der Aktion und nicht mehr nach einem Rückzug (ADR 0002)."""
    phase = Campaign.current_phase()
    return phase.allows_changes_by_participants and not submission.is_withdrawn


def withdraw(submission: Submission, *, by: Submission.WithdrawnBy) -> Submission:
    """Rückzug: löscht alle Master, Angaben und Einwilligungen samt Widerruf.

    Es bleiben die Abgabe-Kennung, der Zeitpunkt und wer den Rückzug ausgelöst hat. Eine
    zurückgezogene Abgabe zählt nicht mehr auf Quote oder Gesamtgrenze und öffnet nicht wieder.
    """
    with transaction.atomic():
        submission = Submission.objects.select_for_update().get(pk=submission.pk)
        if submission.is_withdrawn:
            return submission
        # Zuerst als zurückgezogen markieren: Ab hier startet kein neuer Upload mehr.
        submission.withdrawn_at = timezone.now()
        submission.withdrawn_by = by
        submission.credit_name = ""
        submission.setup_description = ""
        submission.save()
        submission.consents.all().delete()
    for master in submission.masters.all():
        if master.state in DELETABLE:
            delete_master(master)
    submission.masters.all().delete()
    return submission


def revocation_withdraws(consent: Consent) -> bool:
    """Ob der Widerruf dieser Einwilligung die ganze Abgabe zurückzieht: nur bei der Nutzung
    im Projekt, ohne sie kann die Abgabe nicht bleiben."""
    return consent.kind == Consent.Kind.PROJECT_USE


def revoke(consent: Consent, *, by: Submission.WithdrawnBy) -> bool:
    """Widerruf einer Einwilligung: Sie bekommt einen Zeitpunkt und bleibt stehen.

    Der Widerruf der Nutzung im Projekt löst den Rückzug der ganzen Abgabe aus. Der Widerruf
    der Veröffentlichung löscht die Nennung und schreibt die Begleitdateien neu. Gibt zurück,
    ob sich etwas geändert hat (ein schon vermerkter Widerruf ändert nichts).
    """
    if consent.revoked_at is not None:
        return False
    consent.revoked_at = timezone.now()
    consent.save(update_fields=["revoked_at"])
    if revocation_withdraws(consent):
        withdraw(consent.submission, by=by)
    elif consent.kind == Consent.Kind.PUBLISH_CREDIT:
        # Ohne gültige Einwilligung wird die Nennung dabei verworfen.
        details_corrected(consent.submission)
    return True


# -- Belichtungsangaben (ADR 0010) ---------------------------------------------


def exposure_changeable_by_participant(master: Master) -> bool:
    """Teilnehmende ändern Belichtungsangaben, solange sie Master hochladen dürfen; danach
    nur noch die Betreiber im Admin."""
    return master.state == Master.State.ACCEPTED and changeable_by_participant(master.submission)


def change_exposure(master: Master, data: dict) -> None:
    """Eine Änderung der Belichtungsangaben: einen Vorschlag übernehmen (`accept`), die
    Bedeutung von EXPTIME festlegen (`exptime_meaning`) oder Werte von Hand ändern.

    Ungültige Eingaben werfen `exposure.InvalidInput`.
    """
    if "accept" in data:
        changed = exposure.accept(master, data["accept"])
    elif "exptime_meaning" in data:
        changed = exposure.choose_exptime_meaning(master, data["exptime_meaning"])
    else:
        changed = exposure.set_by_hand(master, data)
    if changed:
        master.save(update_fields=changed)


def backfill_exposure(master: Master) -> None:
    """Liest den Header eines angenommenen Masters erneut per Range Request und trägt die
    Belichtungsangaben nach. Werte mit der Herkunft `manuell` bleiben unangetastet."""
    head = get_storage().read_head(master.key, validation.HEAD_BYTES)
    suffix = PurePosixPath(master.key).suffix
    changed = exposure.apply_header(master, exposure.read(head, suffix), keep_manual=True)
    master.save(update_fields=changed)
