"""Equipment-Foto im Admin: ansehen, im Auftrag löschen, Widerruf vermerken (Ticket #82)."""

import pytest
from admin_helper import log_messages, submission_url
from django.contrib.admin.models import LogEntry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from photo_files import foto

from submissions.models import Consent, EquipmentPhoto

pytestmark = pytest.mark.django_db


@pytest.fixture
def with_photo(participant, storage_dir):
    upload = SimpleUploadedFile("Garten.jpg", foto("jpeg"), content_type="image/jpeg")
    participant.client.post(
        f"/submission/{participant.reference}/aendern/foto/",
        {"equipment_photo": upload, "consent_equipment_photo": "on"},
    )
    assert EquipmentPhoto.objects.count() == 1
    return participant


def stored_files(storage_dir):
    return [p for p in (storage_dir / "objects").rglob("foto-*") if p.is_file()]


def test_betreiber_sehen_thumbnail_und_foto_in_der_submission(with_photo, operator_client):
    seite = operator_client.get(submission_url(with_photo.submission)).content.decode()
    assert "Equipment-Foto" in seite
    assert submission_url(with_photo.submission, "foto/vorschau/") in seite
    assert submission_url(with_photo.submission, "foto/") in seite
    voll = operator_client.get(submission_url(with_photo.submission, "foto/"))
    klein = operator_client.get(submission_url(with_photo.submission, "foto/vorschau/"))
    assert voll.status_code == klein.status_code == 200
    assert voll["Content-Type"] == "image/jpeg"
    assert voll.content[:2] == klein.content[:2] == b"\xff\xd8"


def test_ohne_anmeldung_kein_zugang_zum_foto(with_photo):
    for suffix in ("foto/", "foto/vorschau/", "foto/loeschen/"):
        antwort = Client().get(submission_url(with_photo.submission, suffix))
        assert antwort.status_code in (302, 404)
        assert antwort.status_code != 200


def test_ohne_foto_zeigt_der_admin_einen_strich_und_404(participant, operator_client):
    assert operator_client.get(submission_url(participant.submission)).status_code == 200
    assert operator_client.get(submission_url(participant.submission, "foto/")).status_code == 404


def test_betreiber_loeschen_das_foto_im_auftrag_und_es_steht_im_protokoll(
    with_photo, operator_client, storage_dir
):
    url = submission_url(with_photo.submission, "foto/loeschen/")
    assert operator_client.get(url).status_code == 200
    assert len(stored_files(storage_dir)) == 2  # Rückfrage löscht noch nichts
    assert operator_client.post(url).status_code == 302
    assert stored_files(storage_dir) == []
    assert not EquipmentPhoto.objects.exists()
    (consent,) = Consent.objects.filter(kind=Consent.Kind.EQUIPMENT_PHOTO)
    assert consent.revoked_at is not None
    assert "Equipment-Foto gelöscht" in " ".join(log_messages(with_photo.submission))


def test_widerruf_der_foto_einwilligung_im_admin_loescht_das_foto(
    with_photo, operator_client, storage_dir
):
    consent = Consent.objects.get(kind=Consent.Kind.EQUIPMENT_PHOTO)
    seite = operator_client.get(submission_url(with_photo.submission)).content.decode()
    url = submission_url(with_photo.submission, f"einwilligung/{consent.pk}/widerrufen/")
    assert url in seite
    assert operator_client.get(url).status_code == 200
    assert operator_client.post(url).status_code == 302
    consent.refresh_from_db()
    assert consent.revoked_at is not None
    assert stored_files(storage_dir) == []
    assert not EquipmentPhoto.objects.exists()
    assert LogEntry.objects.filter(change_message__contains="Widerruf vermerkt: Equipment-Foto")


def test_betreiber_loeschen_die_submission_samt_foto(with_photo, operator_client, storage_dir):
    operator_client.post(submission_url(with_photo.submission, "loeschen/"))
    assert stored_files(storage_dir) == []
    assert not EquipmentPhoto.objects.exists()
