"""Fachverhalten rund um die Submission: anlegen, Master löschen, Angaben ändern, Löschung,
Widerruf.

Admin und Submission-Seite rufen diese Operationen auf; sie selbst kennen keine Anfrage.
"""

import logging
import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from storage import get_storage

from . import exposure, references, validation
from .models import Campaign, Consent, EquipmentPhoto, Master, Submission
from .photos import CleanPhoto
from .uploads import abort_multipart, sidecar

logger = logging.getLogger(__name__)

_ATTEMPTS = 5
# Reservierter, nicht anmeldbarer Benutzer für das Protokoll bei Änderungen durch Teilnehmende.
PARTICIPANT_USERNAME = "teilnehmende"


def create_submission(
    *,
    credit_name,
    setup_description,
    publish_credit,
    photo: CleanPhoto | None = None,
    photo_consent: bool = False,
) -> Submission:
    """Legt eine Submission samt Einwilligungen an und vergibt eine freie Submission-ID.

    Die Namensnennung gibt es nur mit der Einwilligung zur Namensnennung; ohne sie wird ein
    eingegebener Name verworfen und die Submission bleibt anonym. Ein bereinigtes
    Equipment-Foto (`photo`) gibt es nur mit der aktiv erteilten Einwilligung (`photo_consent`),
    sonst `PhotoConsentMissing`; sie wird hier mit angelegt.
    """
    if photo is not None and not photo_consent:
        raise PhotoConsentMissing
    kinds = [Consent.Kind.PROJECT_USE]
    if publish_credit:
        kinds.append(Consent.Kind.PUBLISH_CREDIT)
    else:
        credit_name = ""
    if photo is not None:
        kinds.append(Consent.Kind.EQUIPMENT_PHOTO)
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
                if photo is not None:
                    # Zuletzt: Danach kann in der Transaktion nichts mehr scheitern.
                    _store_photo(submission, photo)
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


# -- Equipment-Foto (Ticket #82, ADR 0005) --------------------------------------


class PhotoConsentMissing(Exception):
    """Zum Hinzufügen fehlt die aktiv erteilte Einwilligung zum Foto."""


class PhotoNotAllowed(Exception):
    """Die Submission ist gelöscht; ein Foto lässt sich nicht mehr hinzufügen."""


def photo_consent(submission: Submission) -> Consent | None:
    """Die gültige (nicht widerrufene) Einwilligung zum Equipment-Foto."""
    return submission.consents.filter(
        kind=Consent.Kind.EQUIPMENT_PHOTO, revoked_at__isnull=True
    ).first()


def photo_consent_needed(submission: Submission) -> bool:
    """Ob beim Hinzufügen oder Ersetzen eine neue Einwilligung nötig ist: wenn keine gültige
    vorliegt oder sich die Fassung des Hinweistextes seitdem geändert hat."""
    consent = photo_consent(submission)
    return consent is None or consent.text_version != settings.CONSENT_TEXT_VERSION


def _new_photo_keys(submission: Submission) -> tuple[str, str]:
    """Objekt-Schlüssel aus Submission-ID und Zufalls-ID, nie aus Eingaben."""
    token = uuid.uuid4().hex
    return f"{submission.reference}/foto-{token}.jpg", f"{submission.reference}/foto-{token}-t.jpg"


def _store_photo(submission: Submission, photo: CleanPhoto) -> list[str]:
    """Legt Foto und Thumbnail im Speicher ab und ersetzt den Datensatz der Submission.

    Gibt die Schlüssel des bisherigen Fotos zurück; deren Dateien löscht erst der Aufrufer, wenn
    alles andere gespeichert ist. Scheitert etwas, bleibt nichts Neues im Speicher liegen.
    """
    storage = get_storage()
    key, thumbnail_key = _new_photo_keys(submission)
    storage.put_bytes(key, photo.photo, "image/jpeg")
    try:
        storage.put_bytes(thumbnail_key, photo.thumbnail, "image/jpeg")
        old = EquipmentPhoto.objects.filter(submission=submission).first()
        old_keys = [old.key, old.thumbnail_key] if old else []
        if old:
            old.delete()
        EquipmentPhoto.objects.create(submission=submission, key=key, thumbnail_key=thumbnail_key)
    except Exception:
        # Aufräumen am Speicher; der eigentliche Fehler wird gleich weitergereicht.
        logger.exception("Equipment-Foto der Submission %s nicht gespeichert", submission.reference)
        _delete_quietly([key, thumbnail_key])
        raise
    return old_keys


def _delete_quietly(keys: list[str]) -> None:
    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            # Aufräumen: Der Fehler, der dazu führte, zählt mehr; der Schlüssel enthält nichts
            # aus der Datei der Teilnehmenden.
            logger.warning("Objekt %s ließ sich nicht löschen", key)


def add_photo(submission: Submission, photo: CleanPhoto, *, consent_given: bool) -> bool:
    """Equipment-Foto hinzufügen oder ersetzen; gibt zurück, ob es ein Ersetzen war.

    Ohne gültige Einwilligung zum Foto (oder bei geänderter Fassung des Hinweistextes) braucht
    es die aktiv erteilte (`consent_given`), sonst `PhotoConsentMissing` und nichts wird
    gespeichert. Beim Ersetzen gilt eine gültige Einwilligung weiter. Die Dateien des alten
    Fotos werden gelöscht, sobald das neue gespeichert ist.
    """
    with transaction.atomic():
        submission = Submission.objects.select_for_update().get(pk=submission.pk)
        if submission.is_deleted:
            raise PhotoNotAllowed
        needed = photo_consent_needed(submission)
        if needed and not consent_given:
            raise PhotoConsentMissing
        if needed:
            # Eine Einwilligung zu einer älteren Fassung bleibt als Nachweis stehen.
            submission.consents.filter(
                kind=Consent.Kind.EQUIPMENT_PHOTO, revoked_at__isnull=True
            ).update(revoked_at=timezone.now())
            Consent.objects.create(
                submission=submission,
                kind=Consent.Kind.EQUIPMENT_PHOTO,
                text_version=settings.CONSENT_TEXT_VERSION,
            )
        old_keys = _store_photo(submission, photo)
    _delete_quietly(old_keys)
    log_participant_change(
        submission,
        "Equipment-Foto ersetzt (durch Teilnehmende)"
        if old_keys
        else "Equipment-Foto hinzugefügt (durch Teilnehmende)",
    )
    return bool(old_keys)


def _remove_photo(submission: Submission) -> bool:
    """Löscht Foto und Thumbnail aus dem Speicher und den Datensatz; die Einwilligung bleibt."""
    photo = EquipmentPhoto.objects.filter(submission=submission).first()
    if photo is None:
        return False
    storage = get_storage()
    storage.delete(photo.key)
    storage.delete(photo.thumbnail_key)
    photo.delete()
    return True


def delete_photo(submission: Submission) -> bool:
    """Foto löschen: Foto und Thumbnail sind sofort weg. Das widerruft die Einwilligung zum
    Foto; sie bleibt mit dem Zeitpunkt des Widerrufs als Nachweis stehen. Gibt zurück, ob es ein
    Foto gab."""
    removed = _remove_photo(submission)
    submission.consents.filter(kind=Consent.Kind.EQUIPMENT_PHOTO, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    return removed


def delete_photo_by_participant(submission: Submission) -> bool:
    removed = delete_photo(submission)
    if removed:
        log_participant_change(submission, "Equipment-Foto gelöscht (durch Teilnehmende)")
    return removed


def delete_submission(submission: Submission, *, by: Submission.DeletedBy) -> Submission:
    """Löschung: löscht alle Master, das Equipment-Foto, Angaben und Einwilligungen samt Widerruf.

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
    _remove_photo(submission)
    return submission


# Widerrufen lassen sich die Einwilligungen zur Namensnennung und zum Equipment-Foto. Wer die
# Nutzung im Projekt nicht mehr will, löscht die Submission.
REVOCABLE = (Consent.Kind.PUBLISH_CREDIT, Consent.Kind.EQUIPMENT_PHOTO)


def revoke(consent: Consent) -> bool:
    """Widerruf einer Einwilligung: Sie bekommt einen Zeitpunkt und bleibt stehen. Bei der
    Namensnennung wird sie gelöscht und die Begleitdateien neu geschrieben, beim Equipment-Foto
    werden Foto und Thumbnail sofort gelöscht.

    Gibt zurück, ob sich etwas geändert hat: Ein schon vermerkter Widerruf ändert nichts, und
    ebenso wenig eine Einwilligung, die eine Löschung (etwa in einem anderen Tab) schon entfernt
    hat. Andere Einwilligungen lassen sich nicht widerrufen (`ValueError`).
    """
    if consent.kind not in REVOCABLE:
        raise ValueError(
            f"Die Einwilligung „{consent.get_kind_display()}“ lässt sich nicht widerrufen; "
            "dafür die Submission löschen."
        )
    if consent.kind == Consent.Kind.EQUIPMENT_PHOTO and consent.revoked_at is None:
        # Zuerst die Dateien: Scheitert das Löschen, bleibt der Widerruf offen und lässt sich
        # wiederholen, statt ein Foto ohne Einwilligung stehen zu lassen.
        _remove_photo(consent.submission)
    now = timezone.now()
    # In einem Schritt, damit ein gleichzeitiger Widerruf oder eine Löschung nicht dazwischenkommt.
    if not Consent.objects.filter(pk=consent.pk, revoked_at__isnull=True).update(revoked_at=now):
        return False
    consent.revoked_at = now
    if consent.kind == Consent.Kind.PUBLISH_CREDIT:
        # Ohne gültige Einwilligung wird die Namensnennung dabei verworfen.
        details_changed(consent.submission)
    return True


def consent_revocable_by_participant(submission: Submission) -> Consent | None:
    """Die Einwilligung zur Namensnennung, die Teilnehmende selbst widerrufen dürfen.

    Der Widerruf geht jederzeit, auch in der Nachfrist und nach dem Ende der Aktion
    (DSGVO Art. 7 Abs. 3); nach einer Löschung gibt es nichts mehr zu widerrufen.
    """
    if submission.is_deleted:
        return None
    return submission.consents.filter(
        kind=Consent.Kind.PUBLISH_CREDIT, revoked_at__isnull=True
    ).first()


# -- Belichtungsangaben (ADR 0010) ---------------------------------------------


def exposure_changeable_by_participant(master: Master) -> bool:
    """Teilnehmende ändern Belichtungsangaben, solange sie Master hochladen dürfen; danach
    nur noch die Betreiber im Admin."""
    return exposure_changeable_by_operator(master) and changeable_by_participant(master.submission)


def exposure_changeable_by_operator(master: Master) -> bool:
    """Betreiber ändern Belichtungsangaben angenommener Master, auch nach der Aktion."""
    return master.state == Master.State.ACCEPTED


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
