"""Prüfsumme und Dubletten (Ticket #14)."""

import hashlib
import json

import pytest
from django.test import Client
from files import fits, xisf
from uploads_helper import complete, create, finish, send_parts, start, upload

from submissions.models import Master, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture
def storage_dir(settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


def sha(data):
    return hashlib.sha256(data).hexdigest()


def uploaded_until_finish(client, reference, data, **kwargs):
    body = start(client, reference, size=len(data), **kwargs).json()
    upload_id = create(client, body["url"])
    parts = send_parts(client, reference, body["masterId"], body["key"], upload_id, data)
    complete(client, reference, body["masterId"], body["key"], upload_id, parts)
    return body["masterId"]


def test_pruefsumme_wird_gespeichert(client, reference):
    data = fits()
    upload(client, reference, data)
    assert Master.objects.get().sha256 == sha(data)


def test_pruefsumme_steht_in_der_begleitdatei(client, reference, storage_dir):
    data = fits()
    upload(client, reference, data)
    master = Master.objects.get()
    sidecar = json.loads((storage_dir / "objects" / master.sidecar_key).read_text())
    assert sidecar["sha256"] == sha(data)
    assert sidecar["duplicate_of"] is None


def test_pruefsumme_wird_ungeprueft_uebernommen(client, reference):
    """Der Server kann die Prüfsumme nicht bilden (ADR 0005) und vergleicht nicht."""
    data = fits()
    master_id = uploaded_until_finish(client, reference, data)
    response = finish(client, reference, master_id, "a" * 64)
    assert response.json()["state"] == "accepted"
    assert Master.objects.get().sha256 == "a" * 64


def test_grossbuchstaben_werden_normalisiert(client, reference):
    data = fits()
    master_id = uploaded_until_finish(client, reference, data)
    finish(client, reference, master_id, sha(data).upper())
    assert Master.objects.get().sha256 == sha(data)


@pytest.mark.parametrize(
    "value", [None, "", "abc", "g" * 64, "a" * 63, "a" * 65, 123, ["a" * 64], " " + "a" * 63]
)
def test_ungueltige_pruefsumme(client, reference, value):
    data = fits()
    master_id = uploaded_until_finish(client, reference, data)
    response = finish(client, reference, master_id, value)
    assert response.status_code == 400
    assert "Prüfsumme" in response.json()["error"]
    master = Master.objects.get()
    assert master.state == Master.State.UPLOADING  # Fertig-Meldung kann wiederholt werden
    assert finish(client, reference, master_id, sha(data)).json()["state"] == "accepted"


def test_ohne_json_ungueltig(client, reference):
    master_id = uploaded_until_finish(client, reference, fits())
    response = client.post(f"/submission/{reference}/master/{master_id}/fertig/")
    assert response.status_code == 400


def test_dieselbe_datei_in_derselben_submission_wird_abgelehnt(client, reference, storage_dir):
    data = fits()
    upload(client, reference, data, filename="erste.fits")
    response = upload(client, reference, data, filename="zweite.fits")
    body = response.json()
    assert body["state"] == "rejected"
    assert "schon" in body["reason"]

    first, second = Master.objects.order_by("created_at")
    assert first.state == Master.State.ACCEPTED
    assert second.state == Master.State.REJECTED
    assert second.get_rejection_category_display() == "Dublette in derselben Submission"
    assert (storage_dir / "objects" / first.key).exists()
    assert not (storage_dir / "objects" / second.key).exists()


def test_abgelehnte_datei_zaehlt_nicht_als_vorhanden(client, reference):
    bad = fits(bitpix=16)
    upload(client, reference, bad)
    assert upload(client, reference, bad).json()["reason"].startswith("Kein 32-Bit")


def test_dieselbe_datei_in_anderer_submission_ist_eine_dublette(
    client, reference, valid_form, storage_dir
):
    data = xisf()
    upload(client, reference, data, filename="a.xisf")
    other = Client()
    other.post("/", valid_form)
    other_ref = Submission.objects.exclude(reference=reference).get().reference

    response = upload(other, other_ref, data, filename="b.xisf")
    assert response.json()["state"] == "accepted"
    original = Master.objects.get(submission__reference=reference)
    duplicate = Master.objects.get(submission__reference=other_ref)
    assert duplicate.duplicate_of == original
    sidecar = json.loads((storage_dir / "objects" / duplicate.sidecar_key).read_text())
    assert sidecar["duplicate_of"] == {
        "reference": reference,
        "master_id": original.public_id.hex,
    }


def test_dublette_wird_teilnehmenden_nicht_angezeigt(client, reference, valid_form):
    data = fits()
    upload(client, reference, data)
    other = Client()
    other.post("/", valid_form)
    other_ref = Submission.objects.exclude(reference=reference).get().reference
    response = upload(other, other_ref, data)
    assert reference not in json.dumps(response.json())
    assert reference not in other.get(f"/submission/{other_ref}/").content.decode()


def test_dublette_verweist_auf_den_ersten_master(client, campaign, valid_form, storage_dir):
    data = fits()
    references = []
    for _ in range(3):
        c = Client()
        c.post("/", valid_form)
        ref = Submission.objects.order_by("-created_at").first().reference
        references.append(ref)
        upload(c, ref, data)
    first, second, third = Master.objects.order_by("created_at")
    assert second.duplicate_of == first
    assert third.duplicate_of == first


def test_uploader_nutzt_web_worker(client, reference):
    content = client.get(f"/submission/{reference}/").content.decode()
    assert "data-sha-worker=" in content
    assert "sha256-worker.js" in content
