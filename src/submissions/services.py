"""Fachverhalten rund um die Submission: anlegen, Master löschen, Angaben ändern, Löschung,
Widerruf, Nachtrag.

Admin und Submission-Seite rufen diese Operationen auf; sie selbst kennen keine Anfrage.
"""

from pathlib import PurePosixPath

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from schwarmstack import notices
from storage import get_storage

from . import exposure, references, validation
from .models import Campaign, Consent, Master, Submission
from .uploads import abort_multipart, sidecar

_ATTEMPTS = 5
# Reservierter, nicht anmeldbarer Benutzer für das Protokoll bei Änderungen durch Teilnehmende.
PARTICIPANT_USERNAME = "teilnehmende"


def create_submission(*, credit_name, setup_description, publish_credit) -> Submission:
    """Legt eine Submission samt Einwilligungen an und vergibt eine freie Submission-ID.

    Die Namensnennung gibt es nur mit der Einwilligung zur Namensnennung; ohne sie wird ein
    eingegebener Name verworfen und die Submission bleibt anonym.
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
        except IntegrityError:  # gleichzeitig dieselbe Submission-ID gezogen
            continue
    raise RuntimeError("Submission konnte nicht angelegt werden")


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


def details_changed(submission: Submission) -> None:
    """Nach einer Änderung von Namensnennung oder Setup (im Admin oder durch einen Widerruf) die
    Begleitdateien neu schreiben, damit die Zuordnung ohne Datenbank stimmt (ADR 0006).

    Ohne gültige Einwilligung zur Namensnennung bleibt die Submission anonym: Eine nachträglich
    eingetragene Namensnennung wird verworfen.
    """
    if submission.credit_name and not submission.publishes_credit:
        submission.credit_name = ""
        submission.save(update_fields=["credit_name"])
    storage = get_storage()
    for master in submission.masters.filter(state=Master.State.ACCEPTED):
        storage.put_json(master.sidecar_key, sidecar(master))


def correctable_by_operator() -> bool:
    """Ob Betreiber Angaben und Belichtungsangaben ändern und Master löschen dürfen: bis zum
    endgültigen Export.

    Danach müssen Manifest und Speicher übereinstimmen; nur Widerruf und Löschung bleiben
    möglich, als Nachtrag (ADR 0008).
    """
    campaign = Campaign.current()
    return campaign is None or not campaign.is_exported


def _amendment(submission: Submission, what: str) -> None:
    """Nach dem endgültigen Export ist ein Widerruf oder eine Löschung ein Nachtrag: Er wird an
    der Submission vermerkt und den Betreibern gemeldet, damit sie ihre Kopien anpassen."""
    if correctable_by_operator():
        return
    submission.amended_at = timezone.now()
    submission.save(update_fields=["amended_at"])
    notices.send(
        f"Nachtrag zum Export: {submission.reference}",
        f"{what} für die Submission {submission.reference} nach dem endgültigen Export.\n\n"
        "Bitte lokale Kopien und die Credits-Liste anpassen; die Submission steht im Admin "
        "unter Export → Nachträge.",
    )


def changeable_by_participant(submission: Submission) -> bool:
    """Ob Teilnehmende selbst Master löschen, die Submission löschen oder ihre Angaben ändern
    dürfen: nur bis zum Ende der Aktion und nicht mehr nach einer Löschung (ADR 0002)."""
    phase = Campaign.current_phase()
    return phase.allows_changes_by_participants and not submission.is_deleted


def change_details(submission: Submission, *, setup_description, credit_name=None) -> bool:
    """Angaben ändern durch Teilnehmende: Setup und Namensnennung speichern, die Begleitdateien
    neu schreiben und im Protokoll vermerken.

    Ohne gültige Einwilligung zur Namensnennung bleibt die Namensnennung leer. Ohne Änderung
    wird nichts gespeichert und nichts vermerkt; gibt zurück, ob sich etwas geändert hat.
    """
    changed = []
    if setup_description != submission.setup_description:
        submission.setup_description = setup_description
        changed.append("setup_description")
    if credit_name is not None and credit_name != submission.credit_name:
        submission.credit_name = credit_name
        changed.append("credit_name")
    if changed:
        submission.save(update_fields=changed)
        details_changed(submission)
        log_participant_change(submission, "Angaben geändert (durch Teilnehmende)")
    return bool(changed)


def log_participant_change(submission: Submission, message: str) -> None:
    """Protokolleintrag für eine Änderung durch Teilnehmende. Das Protokoll (`LogEntry`)
    verlangt einen Benutzer; Teilnehmende haben kein Konto, deshalb steht ein reservierter,
    gesperrter Benutzer „teilnehmende“ dafür, ohne Passwort und nicht anmeldbar."""
    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        **{user_model.USERNAME_FIELD: PARTICIPANT_USERNAME}, defaults={"is_active": False}
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    LogEntry.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(Submission),
        object_id=str(submission.pk),
        object_repr=str(submission),
        action_flag=CHANGE,
        change_message=message,
    )


def delete_submission(submission: Submission, *, by: Submission.DeletedBy) -> Submission:
    """Löschung: löscht alle Master, Angaben und Einwilligungen samt Widerruf.

    Es bleiben die Submission-ID, der Zeitpunkt und wer gelöscht hat. Eine gelöschte
    Submission zählt nicht mehr auf Quote oder Gesamtgrenze und öffnet nicht wieder. Wer die
    Nutzung im Projekt nicht mehr will, löscht die Submission; die Löschung ist der Nachweis.
    """
    with transaction.atomic():
        submission = Submission.objects.select_for_update().get(pk=submission.pk)
        if submission.is_deleted:
            return submission
        # Zuerst als gelöscht markieren: Ab hier startet kein neuer Upload mehr.
        submission.deleted_at = timezone.now()
        submission.deleted_by = by
        submission.credit_name = ""
        submission.setup_description = ""
        submission.save()
        submission.consents.all().delete()
    for master in submission.masters.all():
        if master.state in DELETABLE:
            delete_master(master)
    submission.masters.all().delete()
    _amendment(submission, "Löschung")
    return submission


# Widerrufen lässt sich nur die Einwilligung zur Namensnennung. Wer die Nutzung im Projekt
# nicht mehr will, löscht die Submission.
REVOCABLE = (Consent.Kind.PUBLISH_CREDIT,)


def revoke(consent: Consent) -> bool:
    """Widerruf der Einwilligung zur Namensnennung: Sie bekommt einen Zeitpunkt und bleibt
    stehen; die Namensnennung wird gelöscht und die Begleitdateien neu geschrieben.

    Gibt zurück, ob sich etwas geändert hat: Ein schon vermerkter Widerruf ändert nichts, und
    ebenso wenig eine Einwilligung, die eine Löschung (etwa in einem anderen Tab) schon entfernt
    hat. Andere Einwilligungen lassen sich nicht widerrufen (`ValueError`).
    """
    if consent.kind not in REVOCABLE:
        raise ValueError(
            f"Die Einwilligung „{consent.get_kind_display()}“ lässt sich nicht widerrufen; "
            "dafür die Submission löschen."
        )
    now = timezone.now()
    # In einem Schritt, damit ein gleichzeitiger Widerruf oder eine Löschung nicht dazwischenkommt.
    if not Consent.objects.filter(pk=consent.pk, revoked_at__isnull=True).update(revoked_at=now):
        return False
    consent.revoked_at = now
    # Ohne gültige Einwilligung wird die Namensnennung dabei verworfen.
    details_changed(consent.submission)
    _amendment(consent.submission, "Widerruf der Namensnennung")
    return True


def consent_revocable_by_participant(submission: Submission) -> Consent | None:
    """Die Einwilligung zur Namensnennung, die Teilnehmende selbst widerrufen dürfen.

    Der Widerruf geht jederzeit, auch in der Nachfrist und nach dem Ende der Aktion
    (DSGVO Art. 7 Abs. 3); nach einer Löschung gibt es nichts mehr zu widerrufen.
    """
    if submission.is_deleted:
        return None
    return submission.consents.filter(kind__in=REVOCABLE, revoked_at__isnull=True).first()


# -- Belichtungsangaben (ADR 0010) ---------------------------------------------


def exposure_changeable_by_participant(master: Master) -> bool:
    """Teilnehmende ändern Belichtungsangaben, solange sie Master hochladen dürfen; danach
    nur noch die Betreiber im Admin."""
    return exposure_changeable_by_operator(master) and changeable_by_participant(master.submission)


def exposure_visible_to_operator(master: Master) -> bool:
    """Belichtungsangaben gibt es nur für angenommene Master."""
    return master.state == Master.State.ACCEPTED


def exposure_changeable_by_operator(master: Master) -> bool:
    """Betreiber ändern Belichtungsangaben angenommener Master, auch nach der Aktion, aber
    nicht mehr nach dem endgültigen Export."""
    return exposure_visible_to_operator(master) and correctable_by_operator()


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
    Belichtungsangaben neu. Werte mit der Herkunft `manuell` bleiben unangetastet."""
    head = get_storage().read_head(master.key, validation.HEAD_BYTES)
    suffix = PurePosixPath(master.key).suffix
    changed = exposure.apply_header(master, exposure.read(head, suffix), keep_manual=True)
    master.save(update_fields=changed)
