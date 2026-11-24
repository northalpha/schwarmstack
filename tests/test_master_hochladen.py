"""Erster Master von Anfang bis Ende über den lokalen Speicher (Ticket #11)."""

import json

import pytest
from django.test import Client
from uploads_helper import create, finish, send_parts, sign, start, upload

from submissions.models import Master, Submission

pytestmark = pytest.mark.django_db

from files import fits, xisf  # noqa: E402

DATA = fits(width=16, height=12)


@pytest.fixture
def storage_dir(settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


def stored(storage_dir, key):
    return (storage_dir / "objects" / key).read_bytes()


def test_master_hochladen_und_annehmen(client, reference, storage_dir):
    data = xisf()
    response = upload(client, reference, data, channel="Ha", filename="M101 Ha.xisf")
    assert response.status_code == 200
    assert response.json()["state"] == "accepted"

    master = Master.objects.get()
    assert master.state == Master.State.ACCEPTED
    assert master.channel == "Ha"
    assert master.original_name == "M101 Ha.xisf"
    assert master.size == len(data)
    assert stored(storage_dir, master.key) == data


def test_datei_kommt_byte_genau_an_bei_vielen_teilen(client, reference, storage_dir):
    upload(client, reference, DATA, part_size=500)
    assert stored(storage_dir, Master.objects.get().key) == DATA


def test_objekt_schluessel_ohne_dateinamen(client, reference):
    upload(client, reference, DATA, filename="../../etc/passwd.fits")
    master = Master.objects.get()
    assert master.key.startswith(f"{reference}/")
    assert master.key.endswith(".fits")
    assert "passwd" not in master.key
    assert ".." not in master.key


@pytest.mark.parametrize(
    ("filename", "suffix"),
    [("a.xisf", ".xisf"), ("a.FITS", ".fits"), ("a.fit", ".fits"), ("a.fts", ".fits")],
)
def test_endung_im_schluessel(client, reference, filename, suffix):
    upload(client, reference, xisf() if suffix == ".xisf" else DATA, filename=filename)
    assert Master.objects.get().key.endswith(suffix)


def test_begleitdatei(client, reference, storage_dir, campaign):
    upload(client, reference, fits(planes=3), channel="RGB", filename="farbe.fits")
    master = Master.objects.get()
    sidecar_key = master.key.rsplit(".", 1)[0] + ".json"
    sidecar = json.loads(stored(storage_dir, sidecar_key))
    assert sidecar["reference"] == reference
    assert sidecar["credit_name"] == "Ada Sternguck"
    assert sidecar["channel"] == "RGB"
    assert sidecar["original_name"] == "farbe.fits"
    assert sidecar["size"] == len(fits(planes=3))
    assert sidecar["completed_at"]


@pytest.mark.parametrize("channel", ["", "X", "rgb", None])
def test_ohne_gueltigen_kanal_kein_upload(client, reference, channel):
    response = start(client, reference, channel=channel, size=10)
    assert response.status_code == 400
    assert "Kanal" in response.json()["error"]
    assert Master.objects.count() == 0


@pytest.mark.parametrize("filename", ["bild.tif", "bild.fits.zip", "bild", "bild.xisf.exe"])
def test_falsche_endung_kein_upload(client, reference, filename):
    response = start(client, reference, filename=filename, size=10)
    assert response.status_code == 400
    assert Master.objects.count() == 0


@pytest.mark.parametrize("size", [0, -1, "zehn", None])
def test_ungueltige_groesse(client, reference, size):
    response = start(client, reference, size=size)
    assert response.status_code == 400


def test_ungueltiges_json(client, reference):
    response = client.post(f"/abgabe/{reference}/master/", "kein json", content_type="text/plain")
    assert response.status_code == 400


def test_alle_kanaele_aus_dem_glossar(client, reference):
    for channel in ["L", "R", "G", "B", "Ha", "OIII", "SII", "IR", "RGB"]:
        assert start(client, reference, channel=channel, size=10).status_code == 201


def test_fremde_abgabe_gibt_404(client, reference, valid_form):
    other = Client()
    other.post("/", valid_form)
    assert start(other, reference, size=10).status_code == 404


def test_fremder_master_gibt_404(client, reference, valid_form):
    master_id = start(client, reference, size=len(DATA)).json()["masterId"]
    other = Client()
    other.post("/", valid_form)
    other_ref = Submission.objects.exclude(reference=reference).get().reference
    # eigener Cookie, aber fremder Master unter eigener Abgabe
    assert sign(other, other_ref, master_id, method="GET", key="x", uploadId="u").status_code == 404
    assert finish(other, other_ref, master_id).status_code == 404
    # fremde Abgabe direkt
    assert finish(other, reference, master_id).status_code == 404


def test_signieren_nur_fuer_den_eigenen_schluessel(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    upload_id = create(client, body["url"])
    response = sign(
        client, reference, body["masterId"],
        method="PUT", key=f"{reference}/anderer.fits", uploadId=upload_id, partNumber=1,
    )  # fmt: skip
    assert response.status_code == 400


def test_signieren_nur_fuer_die_eigene_upload_id(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    upload_id = create(client, body["url"])
    send_parts(client, reference, body["masterId"], body["key"], upload_id, DATA[:8])
    response = sign(
        client, reference, body["masterId"],
        method="PUT", key=body["key"], uploadId="fremd", partNumber=2,
    )  # fmt: skip
    assert response.status_code == 400


@pytest.mark.parametrize(
    "request_",
    [
        {"method": "DELETE"},  # Objekt löschen ist nicht erlaubt
        {"method": "PUT"},  # einfacher PUT ohne Multipart
        {"method": "PUT", "uploadId": "u", "partNumber": 0},
        {"method": "PUT", "uploadId": "u", "partNumber": 10001},
        {"method": "PATCH", "uploadId": "u"},
    ],
)
def test_unzulaessige_anfragen_werden_nicht_signiert(client, reference, request_):
    body = start(client, reference, size=len(DATA)).json()
    response = sign(client, reference, body["masterId"], key=body["key"], **request_)
    assert response.status_code == 400


def test_manipulierter_link_wird_abgewiesen(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    upload_id = create(client, body["url"])
    url = sign(
        client, reference, body["masterId"],
        method="PUT", key=body["key"], uploadId=upload_id, partNumber=1,
    ).json()["url"]  # fmt: skip
    tampered = url[:-3] + ("AAA/" if not url.endswith("AAA/") else "BBB/")
    response = client.put(tampered, b"x", content_type="application/octet-stream")
    assert response.status_code == 403


def test_link_passt_nur_zur_signierten_methode(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    upload_id = create(client, body["url"])
    url = sign(
        client, reference, body["masterId"], method="GET", key=body["key"], uploadId=upload_id
    ).json()["url"]
    assert client.delete(url).status_code == 403


def test_teile_auflisten(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    upload_id = create(client, body["url"])
    send_parts(client, reference, body["masterId"], body["key"], upload_id, DATA[:16], 8)
    url = sign(
        client, reference, body["masterId"], method="GET", key=body["key"], uploadId=upload_id
    ).json()["url"]
    xml = client.get(url).content.decode()
    assert xml.count("<Part>") == 2
    assert "<PartNumber>1</PartNumber>" in xml


def test_fertig_ohne_abgeschlossenen_upload(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    response = finish(client, reference, body["masterId"])
    assert response.status_code == 409
    assert Master.objects.get().state == Master.State.UPLOADING


def test_complete_mit_falschem_etag_schlaegt_fehl(client, reference):
    body = start(client, reference, size=len(DATA)).json()
    upload_id = create(client, body["url"])
    send_parts(client, reference, body["masterId"], body["key"], upload_id, DATA[:8])
    url = sign(
        client, reference, body["masterId"], method="POST", key=body["key"], uploadId=upload_id
    ).json()["url"]
    xml = (
        "<CompleteMultipartUpload><Part><PartNumber>1</PartNumber>"
        '<ETag>"falsch"</ETag></Part></CompleteMultipartUpload>'
    )
    assert client.post(url, xml, content_type="application/xml").status_code == 400


def test_abgabeseite_listet_master(client, reference):
    upload(client, reference, DATA, channel="OIII", filename="m101_oiii.fits")
    start(client, reference, channel="SII", filename="m101_sii.fits", size=10)
    content = client.get(f"/abgabe/{reference}/").content.decode()
    assert "m101_oiii.fits" in content
    assert "OIII" in content
    assert "angenommen" in content
    assert "m101_sii.fits" in content
    assert "unterbrochen" in content  # nie fertig gemeldet (Ticket #39)


def test_abgabeseite_bindet_uppy_ohne_externe_quellen(client, reference):
    content = client.get(f"/abgabe/{reference}/").content.decode()
    assert "uppy.min.js" in content
    assert "<script>" not in content  # kein Inline-JS
    assert "https://" not in content and "http://" not in content


def test_endpunkte_verlangen_csrf(reference, campaign, valid_form, storage_dir):
    client = Client(enforce_csrf_checks=True)
    page = client.get("/")
    token = page.cookies["csrftoken"].value
    client.post("/", dict(valid_form, csrfmiddlewaretoken=token))
    ref = Submission.objects.exclude(reference=reference).get().reference
    assert start(client, ref, size=10).status_code == 403


def test_grosse_teile_gehen_nicht_ueber_den_arbeitsspeicher(client, reference, storage_dir):
    """Teile über Djangos Grenze für Request-Bodies (2,5 MB) werden als Datenstrom geschrieben."""
    data = fits(width=1024, height=768)  # 3 MB
    response = upload(client, reference, data, part_size=len(data))
    assert response.json()["state"] == "accepted"
    assert stored(storage_dir, Master.objects.get().key) == data
