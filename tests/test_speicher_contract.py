"""Contract Tests: Jeder Adapter verhält sich für Server und Browser gleich (Ticket #12)."""

import io
import json
import re
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest
from storage_backends import (
    DjangoBrowser,
    HttpBrowser,
    garage_available,
    garage_storage,
    moto_storage,
)

from storage import S3Request
from storage.local import LocalStorage, StorageError

MB = 1024 * 1024
FIRST = bytes(range(256)) * (5 * MB // 256 + 1)  # S3 verlangt mind. 5 MB außer im letzten Teil
LAST = b"schluss" * 100

BACKENDS = [
    "lokal",
    "moto",
    pytest.param(
        "garage",
        marks=pytest.mark.skipif(not garage_available(), reason="Garage nicht gestartet"),
    ),
]


@pytest.fixture(params=BACKENDS)
def backend(request, settings, tmp_path, client):
    if request.param == "lokal":
        settings.STORAGE_LOCAL_DIR = tmp_path
        storage = LocalStorage(tmp_path)
        return request.param, storage, DjangoBrowser(client)
    if request.param == "moto":
        endpoint = request.getfixturevalue("moto_endpoint")
        return request.param, moto_storage(endpoint, f"b{uuid.uuid4().hex[:12]}"), HttpBrowser()
    return request.param, garage_storage(), HttpBrowser()


def key():
    return f"SW-TEST/{uuid.uuid4().hex}.fits"


def tag(xml, name):
    return re.search(rf"<{name}>(.*?)</{name}>", xml).group(1)


def create(storage, browser, k):
    reply = browser.send("POST", storage.presign(S3Request("POST", k)))
    assert reply.status == 200, reply.text
    return tag(reply.text, "UploadId")


def put_part(storage, browser, k, upload_id, number, data):
    reply = browser.send("PUT", storage.presign(S3Request("PUT", k, upload_id, number)), data)
    assert reply.status == 200, reply.text
    etag = {name.lower(): value for name, value in reply.headers.items()}["etag"]
    return etag.strip('"')


def complete(storage, browser, k, upload_id, parts):
    xml = (
        "<CompleteMultipartUpload>"
        + "".join(f"<Part><PartNumber>{n}</PartNumber><ETag>{e}</ETag></Part>" for n, e in parts)
        + "</CompleteMultipartUpload>"
    )
    url = storage.presign(S3Request("POST", k, upload_id))
    return browser.send("POST", url, xml.encode(), "application/xml")


def upload(storage, browser, k):
    upload_id = create(storage, browser, k)
    parts = [
        (1, put_part(storage, browser, k, upload_id, 1, FIRST)),
        (2, put_part(storage, browser, k, upload_id, 2, LAST)),
    ]
    reply = complete(storage, browser, k, upload_id, parts)
    assert reply.status == 200, reply.text
    return upload_id


def test_multipart_von_anfang_bis_ende(backend):
    _, storage, browser = backend
    k = key()
    assert storage.size(k) is None
    upload(storage, browser, k)
    assert storage.size(k) == len(FIRST) + len(LAST)


def test_range_request_liest_den_anfang(backend):
    _, storage, browser = backend
    k = key()
    upload(storage, browser, k)
    assert storage.read_head(k, 100) == FIRST[:100]


def test_range_request_groesser_als_die_datei(backend):
    _, storage, _ = backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"a": 1})
    assert json.loads(storage.read_head(k, 10 * MB)) == {"a": 1}


def test_begleitdatei_mit_umlauten(backend):
    _, storage, _ = backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"credit_name": "Jürgen Ö."})
    assert json.loads(storage.read_head(k, MB).decode()) == {"credit_name": "Jürgen Ö."}


def test_bytes_ablegen_und_lesen(backend):
    _, storage, _ = backend
    k = f"SW-TEST/{uuid.uuid4().hex}.jpg"
    daten = bytes(range(256)) * 10
    storage.put_bytes(k, daten, "image/jpeg")
    assert storage.size(k) == len(daten)
    assert storage.read(k) == daten
    storage.delete(k)
    assert storage.size(k) is None


def test_teile_auflisten(backend):
    _, storage, browser = backend
    k = key()
    upload_id = create(storage, browser, k)
    put_part(storage, browser, k, upload_id, 1, FIRST)
    put_part(storage, browser, k, upload_id, 2, LAST)
    reply = browser.send("GET", storage.presign(S3Request("GET", k, upload_id)))
    assert reply.status == 200, reply.text
    assert re.findall(r"<PartNumber>(\d+)</PartNumber>", reply.text) == ["1", "2"]


def test_loeschen(backend):
    _, storage, browser = backend
    k = key()
    upload(storage, browser, k)
    storage.delete(k)
    assert storage.size(k) is None
    storage.delete(k)  # erneutes Löschen ist kein Fehler


def test_erreichbarer_speicher(backend):
    _, storage, _ = backend
    storage.ensure_reachable()  # wirft nicht


def test_abbrechen_ueber_den_browser(backend):
    _, storage, browser = backend
    k = key()
    upload_id = create(storage, browser, k)
    put_part(storage, browser, k, upload_id, 1, FIRST)
    reply = browser.send("DELETE", storage.presign(S3Request("DELETE", k, upload_id)))
    assert reply.status in (200, 204), reply.text
    assert browser.send("GET", storage.presign(S3Request("GET", k, upload_id))).status >= 400
    assert storage.size(k) is None


def test_abbrechen_durch_den_server(backend):
    _, storage, browser = backend
    k = key()
    upload_id = create(storage, browser, k)
    put_part(storage, browser, k, upload_id, 1, FIRST)
    storage.abort_multipart(k, upload_id)
    assert browser.send("GET", storage.presign(S3Request("GET", k, upload_id))).status >= 400


def test_upload_id_gilt_nur_fuer_ihren_schluessel(backend, request):
    # Der Server übernimmt die Upload-ID vom Browser ungeprüft (ADR 0009). Das ist nur
    # tragbar, weil der Speicher sie an den Schlüssel bindet, unter dem sie angelegt wurde.
    name, storage, browser = backend
    if name == "moto":
        reason = "moto prüft beim Teil-Upload nicht, ob Upload-ID und Schlüssel passen"
        request.applymarker(pytest.mark.xfail(reason=reason, strict=True))
    eigen, fremd = key(), key()
    upload_id = create(storage, browser, fremd)
    url = storage.presign(S3Request("PUT", eigen, upload_id, 1))
    assert browser.send("PUT", url, LAST).status >= 400
    listing = browser.send("GET", storage.presign(S3Request("GET", fremd, upload_id)))
    assert re.findall(r"<PartNumber>(\d+)</PartNumber>", listing.text) == []


def test_falscher_etag_beim_abschluss(backend):
    _, storage, browser = backend
    k = key()
    upload_id = create(storage, browser, k)
    put_part(storage, browser, k, upload_id, 1, LAST)
    reply = complete(storage, browser, k, upload_id, [(1, "0" * 32)])
    assert reply.status >= 400
    assert storage.size(k) is None


def test_download_link_liefert_die_datei(backend):
    _, storage, browser = backend
    k = key()
    upload(storage, browser, k)
    reply = browser.send("GET", storage.download_url(k))
    assert reply.status == 200, reply.text
    assert reply.body == FIRST + LAST


def test_download_link_mit_eigener_gueltigkeit_liefert_die_datei(backend):
    """Der Export stellt Links aus, die 7 Tage gelten (Ticket #34)."""
    _, storage, browser = backend
    k = key()
    upload(storage, browser, k)
    reply = browser.send("GET", storage.download_url(k, seconds=7 * 24 * 3600))
    assert reply.status == 200, reply.text
    assert reply.body == FIRST + LAST


def test_schluessel_listet_alle_objekte(backend):
    """Für die Löschung nach Ablauf der Löschfrist (Ticket #34)."""
    _, storage, browser = backend
    prefix = f"SW-{uuid.uuid4().hex[:6].upper()}"
    master = f"{prefix}/{uuid.uuid4().hex}.fits"
    upload(storage, browser, master)
    storage.put_json(f"{prefix}/{uuid.uuid4().hex}.json", {"a": 1})
    storage.put_json(f"{prefix}/x/tief.json", {"b": 2})
    found = sorted(k for k in storage.keys() if k.startswith(prefix + "/"))
    assert len(found) == 3
    assert master in found
    assert f"{prefix}/x/tief.json" in found


# -- Signatur: nur dort, wo der Speicher sie wirklich prüft (lokal und Garage, nicht moto) --

SIGNING = [
    "lokal",
    pytest.param(
        "garage",
        marks=pytest.mark.skipif(not garage_available(), reason="Garage nicht gestartet"),
    ),
]


@pytest.fixture(params=SIGNING)
def signing_backend(request, settings, tmp_path, client):
    if request.param == "lokal":
        settings.STORAGE_LOCAL_DIR = tmp_path
        settings.UPLOAD_LINK_SECONDS = 1
        return LocalStorage(tmp_path), DjangoBrowser(client)
    return garage_storage(link_seconds=1), HttpBrowser()


def test_abgelaufener_link_wird_abgewiesen(signing_backend):
    storage, browser = signing_backend
    url = storage.presign(S3Request("POST", key()))
    time.sleep(2.1)
    # AWS und der lokale Adapter antworten 403, Garage 400 ("Date is too old").
    assert browser.send("POST", url).status in (400, 403)


def test_abgelaufener_download_link_wird_abgewiesen(signing_backend):
    storage, browser = signing_backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"a": 1})
    url = storage.download_url(k)
    time.sleep(2.1)
    assert browser.send("GET", url).status in (400, 403)


def test_download_link_mit_eigener_gueltigkeit_laeuft_ab(signing_backend):
    storage, browser = signing_backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"a": 1})
    url = storage.download_url(k, seconds=1)
    time.sleep(2.1)
    assert browser.send("GET", url).status in (400, 403)


def test_download_link_gilt_nur_fuer_get(signing_backend):
    storage, browser = signing_backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"a": 1})
    assert browser.send("DELETE", storage.download_url(k)).status in (400, 403)
    assert storage.size(k) is not None


def test_link_mit_fremdem_schluessel_wird_abgewiesen(signing_backend):
    storage, browser = signing_backend
    url = storage.presign(S3Request("POST", "SW-TEST/eigen.fits"))
    scheme, netloc, path, query, fragment = urlsplit(url)
    if isinstance(storage, LocalStorage):
        forged = url[:-5] + ("AAAA/" if not url.endswith("AAAA/") else "BBBB/")
    else:
        forged = urlunsplit((scheme, netloc, path.replace("eigen", "fremd"), query, fragment))
    assert browser.send("POST", forged).status == 403


def test_s3_adapter_verweigert_unbekannte_anfragen(moto_endpoint):
    storage = moto_storage(moto_endpoint, f"b{uuid.uuid4().hex[:12]}")
    with pytest.raises(ValueError):
        storage.presign(S3Request("DELETE", key()))  # Objekt löschen: nie für den Browser
    with pytest.raises(ValueError):
        storage.presign(S3Request("PUT", key()))  # einfacher PUT ohne Multipart
    with pytest.raises(ValueError):
        storage.presign(S3Request("PUT", key(), "u"))  # Teil ohne Nummer


# -- Teilgröße ist durch die angemeldete Größe begrenzt (#135) --------------------------------


@pytest.fixture
def lokal(tmp_path, client, settings):
    settings.STORAGE_LOCAL_DIR = tmp_path
    storage, browser, k = LocalStorage(tmp_path), DjangoBrowser(client), key()
    return storage, browser, k, create(storage, browser, k)


def test_lokal_teil_ueber_angemeldete_groesse_wird_abgelehnt(lokal):
    storage, browser, k, upload_id = lokal
    url = storage.presign(S3Request("PUT", k, upload_id, 1, max_size=10))
    assert browser.send("PUT", url, b"x" * 11).status == 400
    assert storage.list_parts(k, upload_id) == []


def test_lokal_teile_zusammen_nicht_ueber_angemeldete_groesse(lokal):
    storage, browser, k, upload_id = lokal
    first = storage.presign(S3Request("PUT", k, upload_id, 1, max_size=10))
    second = storage.presign(S3Request("PUT", k, upload_id, 2, max_size=10))
    assert browser.send("PUT", first, b"x" * 6).status == 200
    assert browser.send("PUT", second, b"x" * 5).status == 400
    assert browser.send("PUT", second, b"x" * 4).status == 200
    assert [n for n, _, _ in storage.list_parts(k, upload_id)] == [1, 2]


def test_lokal_teil_ersetzen_zaehlt_nur_einmal(lokal):
    storage, browser, k, upload_id = lokal
    url = storage.presign(S3Request("PUT", k, upload_id, 1, max_size=10))
    assert browser.send("PUT", url, b"x" * 10).status == 200
    assert browser.send("PUT", url, b"y" * 10).status == 200  # Wiederholung desselben Teils
    assert storage.list_parts(k, upload_id)[0][2] == 10


def test_lokal_upload_part_begrenzt_den_datenstrom(tmp_path):
    storage = LocalStorage(tmp_path)
    k = key()
    upload_id = storage.create_multipart(k)
    stream = io.BytesIO(b"x" * (3 * MB))
    with pytest.raises(StorageError):
        storage.upload_part(k, upload_id, 1, stream, max_size=10)
    assert stream.tell() == 11  # nur ein Byte über die Grenze gelesen
    assert storage.list_parts(k, upload_id) == []


def test_max_size_im_link_stoert_keinen_adapter(backend):
    """S3 ignoriert die angemeldete Größe im Link; ein passender Teil geht überall durch."""
    _, storage, browser = backend
    k = key()
    upload_id = create(storage, browser, k)
    url = storage.presign(S3Request("PUT", k, upload_id, 1, max_size=len(LAST)))
    assert browser.send("PUT", url, LAST).status == 200
