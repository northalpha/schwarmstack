"""Löschfrist: Equipment-Foto und Thumbnail verschwinden nach Ablauf aus dem Speicher (#85).

Getestet wird an der Naht des Befehls `delete_after_export` (ADR 0008).
"""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from files import fits
from photo_files import foto

from storage import BACKUP_PREFIX, get_storage
from submissions.models import Campaign, EquipmentPhoto

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def recipients(settings):
    settings.OPERATOR_EMAILS = ["betrieb@example.org"]


def exported(campaign, days_ago):
    campaign.starts_at = timezone.now() - timedelta(days=90)
    campaign.ends_at = timezone.now() - timedelta(days=days_ago + 1)
    campaign.exported_at = timezone.now() - timedelta(days=days_ago)
    campaign.save()


def add_photo(participant):
    participant.client.post(
        f"/submission/{participant.reference}/aendern/foto/",
        {
            "equipment_photo": SimpleUploadedFile("setup.jpg", foto("jpeg"), "image/jpeg"),
            "consent_equipment_photo": "on",
        },
    )
    photo = EquipmentPhoto.objects.get(submission=participant.submission)
    return [photo.key, photo.thumbnail_key]


def stored_keys():
    return set(get_storage().keys())


def run():
    call_command("delete_after_export")


@pytest.fixture
def with_photo(campaign, participant, storage_dir):
    participant.upload(fits())
    get_storage().put_json(f"{BACKUP_PREFIX}db-2026-12-01.json", {"sicherung": True})
    return participant, add_photo(participant)


def test_vor_ablauf_bleiben_foto_und_thumbnail_liegen(campaign, with_photo):
    _, photo_keys = with_photo
    exported(campaign, days_ago=10)
    run()
    assert set(photo_keys) <= stored_keys()


def test_nach_ablauf_sind_foto_und_thumbnail_weg_die_sicherung_bleibt(campaign, with_photo):
    _, photo_keys = with_photo
    exported(campaign, days_ago=31)
    run()
    assert not set(photo_keys) & stored_keys()
    assert f"{BACKUP_PREFIX}db-2026-12-01.json" in stored_keys()
    assert Campaign.objects.get().data_deleted_at is not None


def test_submission_ohne_foto_ist_kein_problem_und_wird_wie_sonst_geloescht(campaign, participant):
    participant.upload(fits())
    exported(campaign, days_ago=31)
    run()
    assert EquipmentPhoto.objects.count() == 0
    assert Campaign.objects.get().data_deleted_at is not None


def test_speicherfehler_bei_einem_foto_laesst_die_uebrigen_loeschen_und_den_lauf_wiederholen(
    campaign, with_photo, another, monkeypatch
):
    _, broken_keys = with_photo
    other = another()
    other_keys = add_photo(other)
    from storage.local import LocalStorage

    original = LocalStorage.delete
    failing = {"on": True}

    def delete(self, key):
        if failing["on"] and key == broken_keys[0]:
            raise OSError("Speicher nicht erreichbar")
        return original(self, key)

    monkeypatch.setattr(LocalStorage, "delete", delete)
    exported(campaign, days_ago=31)

    run()  # darf nicht abbrechen
    assert not set(other_keys) & stored_keys()
    assert broken_keys[0] in stored_keys()
    # Solange etwas im Speicher liegt, bleibt die Datenbank stehen und der nächste Lauf versucht es.
    assert Campaign.objects.get().data_deleted_at is None
    assert EquipmentPhoto.objects.filter(key=broken_keys[0]).exists()

    failing["on"] = False
    run()
    assert not set(broken_keys) & stored_keys()
    assert Campaign.objects.get().data_deleted_at is not None
