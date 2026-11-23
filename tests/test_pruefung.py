"""Prüfung der Master nach dem Upload (Ticket #13)."""

import hashlib

import pytest
from files import fits, xisf
from uploads_helper import complete, create, finish, send_parts, sign, start, upload

from submissions.models import Master, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture
def storage_dir(settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


@pytest.fixture
def reference(client, campaign, valid_form, storage_dir):
    client.post("/", valid_form)
    return Submission.objects.get().reference


def objects(storage_dir):
    root = storage_dir / "objects"
    return sorted(p.name for p in root.rglob("*") if p.is_file()) if root.exists() else []


GUELTIG = [
    ("FITS mono", "L", "m.fits", fits()),
    ("FITS mono NAXIS3=1", "Ha", "m.fit", fits(planes=1)),
    ("FITS RGB", "RGB", "m.fts", fits(planes=3)),
    ("XISF mono", "OIII", "m.xisf", xisf()),
    ("XISF RGB", "RGB", "m.xisf", xisf(channels=3)),
]


@pytest.mark.parametrize(
    ("name", "channel", "filename", "data"), GUELTIG, ids=[g[0] for g in GUELTIG]
)
def test_gueltige_master_werden_angenommen(
    client, reference, storage_dir, name, channel, filename, data
):
    response = upload(client, reference, data, channel=channel, filename=filename, part_size=4096)
    assert response.json()["state"] == "accepted", response.json()
    assert Master.objects.get().state == Master.State.ACCEPTED
    assert len(objects(storage_dir)) == 2  # Master und Begleitdatei


ABGELEHNT = [
    ("FITS 16 Bit", "L", "m.fits", fits(bitpix=16), "32-Bit-Gleitkomma"),
    ("FITS 64 Bit", "L", "m.fits", fits(bitpix=-64), "32-Bit-Gleitkomma"),
    ("FITS 32 Bit Ganzzahl", "L", "m.fits", fits(bitpix=32), "32-Bit-Gleitkomma"),
    ("FITS RGB mit einer Ebene", "RGB", "m.fits", fits(), "Kanal RGB"),
    ("FITS RGB mit NAXIS3=1", "RGB", "m.fits", fits(planes=1), "Kanal RGB"),
    ("FITS mono mit drei Ebenen", "L", "m.fits", fits(planes=3), "eine Ebene"),
    ("FITS SIMPLE = F", "L", "m.fits", fits(simple="F"), "FITS"),
    ("FITS ohne END", "L", "m.fits", fits(end=False), "Header"),
    ("FITS zu kurz", "L", "m.fits", fits(width=40, height=40, truncate=3000), "kürzer"),
    ("FITS mit XISF-Endung", "L", "m.xisf", fits(), "XISF"),
    ("XISF UInt16", "L", "m.xisf", xisf(sample="UInt16"), "32-Bit-Gleitkomma"),
    ("XISF Float64", "L", "m.xisf", xisf(sample="Float64"), "32-Bit-Gleitkomma"),
    ("XISF RGB mit einer Ebene", "RGB", "m.xisf", xisf(), "Kanal RGB"),
    ("XISF mono mit drei Ebenen", "B", "m.xisf", xisf(channels=3), "eine Ebene"),
    ("XISF zu kurz", "L", "m.xisf", xisf(width=40, height=40, truncate=100), "kürzer"),
    ("XISF falsche Signatur", "L", "m.xisf", xisf(signature=b"XISF0200"), "XISF"),
    ("XISF mit FITS-Endung", "L", "m.fits", xisf(), "FITS"),
    ("XISF ohne Image", "L", "m.xisf", xisf(xml="<xisf/>"), "Header"),
    ("XISF kaputtes XML", "L", "m.xisf", xisf(xml="<xisf><Image"), "Header"),
    (
        "XISF mit Entitäten",
        "L",
        "m.xisf",
        xisf(xml='<!DOCTYPE x [<!ENTITY a "aaaa">]><xisf>&a;</xisf>'),
        "Header",
    ),
    ("Zufallsdaten", "L", "m.fits", bytes(range(256)) * 20, "FITS"),
]


@pytest.mark.parametrize(
    ("name", "channel", "filename", "data", "reason"), ABGELEHNT, ids=[a[0] for a in ABGELEHNT]
)
def test_ungueltige_master_werden_abgelehnt_und_geloescht(
    client, reference, storage_dir, name, channel, filename, data, reason
):
    response = upload(client, reference, data, channel=channel, filename=filename, part_size=4096)
    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "rejected"
    assert reason in body["reason"], body["reason"]

    master = Master.objects.get()
    assert master.state == Master.State.REJECTED
    assert reason in master.rejection_reason
    assert objects(storage_dir) == []  # gelöscht, keine Begleitdatei


def test_groesse_weicht_von_der_angemeldeten_ab(client, reference, storage_dir):
    data = fits()
    body = start(client, reference, size=len(data) + 1).json()
    upload_id = create(client, body["url"])
    parts = send_parts(client, reference, body["masterId"], body["key"], upload_id, data, 4096)
    complete(client, reference, body["masterId"], body["key"], upload_id, parts)
    response = finish(client, reference, body["masterId"], hashlib.sha256(data).hexdigest()).json()
    assert response["state"] == "rejected"
    assert "Größe" in response["reason"]
    assert objects(storage_dir) == []


def test_grund_steht_auf_der_abgabeseite(client, reference):
    upload(client, reference, fits(bitpix=16), filename="m101_16bit.fits", part_size=4096)
    content = client.get(f"/abgabe/{reference}/").content.decode()
    assert "m101_16bit.fits" in content
    assert "abgelehnt" in content
    assert "32-Bit-Gleitkomma" in content


def test_abgelehnter_master_kann_nicht_mehr_signiert_werden(client, reference):
    data = fits(bitpix=16)
    body = start(client, reference, size=len(data)).json()
    upload_id = create(client, body["url"])
    parts = send_parts(client, reference, body["masterId"], body["key"], upload_id, data, 4096)
    complete(client, reference, body["masterId"], body["key"], upload_id, parts)
    finish(client, reference, body["masterId"])
    response = sign(
        client, reference, body["masterId"], method="GET", key=body["key"], uploadId=upload_id
    )
    assert response.status_code == 400


def test_erneute_fertig_meldung_aendert_nichts(client, reference):
    data = fits(bitpix=16)
    body = start(client, reference, size=len(data)).json()
    upload_id = create(client, body["url"])
    parts = send_parts(client, reference, body["masterId"], body["key"], upload_id, data, 4096)
    complete(client, reference, body["masterId"], body["key"], upload_id, parts)
    first = finish(client, reference, body["masterId"]).json()
    second = finish(client, reference, body["masterId"]).json()
    assert first["state"] == second["state"] == "rejected"
    assert first["reason"] == second["reason"]
