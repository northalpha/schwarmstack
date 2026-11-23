"""Vertragstests: Jeder Speicher-Adapter verhält sich für Server und Browser gleich (Ticket #12)."""

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
    moto_endpoint,  # noqa: F401  (Fixture)
    moto_storage,
)

from storage import S3Request
from storage.local import LocalStorage

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


def test_teilabruf_liest_den_anfang(backend):
    _, storage, browser = backend
    k = key()
    upload(storage, browser, k)
    assert storage.read_head(k, 100) == FIRST[:100]


def test_teilabruf_groesser_als_die_datei(backend):
    _, storage, _ = backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"a": 1})
    assert json.loads(storage.read_head(k, 10 * MB)) == {"a": 1}


def test_begleitdatei_mit_umlauten(backend):
    _, storage, _ = backend
    k = key().replace(".fits", ".json")
    storage.put_json(k, {"credit_name": "Jürgen Ö."})
    assert json.loads(storage.read_head(k, MB).decode()) == {"credit_name": "Jürgen Ö."}


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


def test_falscher_etag_beim_abschluss(backend):
    _, storage, browser = backend
    k = key()
    upload_id = create(storage, browser, k)
    put_part(storage, browser, k, upload_id, 1, LAST)
    reply = complete(storage, browser, k, upload_id, [(1, "0" * 32)])
    assert reply.status >= 400
    assert storage.size(k) is None


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


def test_link_mit_fremdem_schluessel_wird_abgewiesen(signing_backend):
    storage, browser = signing_backend
    url = storage.presign(S3Request("POST", "SW-TEST/eigen.fits"))
    scheme, netloc, path, query, fragment = urlsplit(url)
    if isinstance(storage, LocalStorage):
        forged = url[:-5] + ("AAAA/" if not url.endswith("AAAA/") else "BBBB/")
    else:
        forged = urlunsplit((scheme, netloc, path.replace("eigen", "fremd"), query, fragment))
    assert browser.send("POST", forged).status == 403


def test_s3_adapter_verweigert_unbekannte_anfragen(moto_endpoint):  # noqa: F811
    storage = moto_storage(moto_endpoint, f"b{uuid.uuid4().hex[:12]}")
    with pytest.raises(ValueError):
        storage.presign(S3Request("DELETE", key()))  # Objekt löschen: nie für den Browser
    with pytest.raises(ValueError):
        storage.presign(S3Request("PUT", key()))  # einfacher PUT ohne Multipart
    with pytest.raises(ValueError):
        storage.presign(S3Request("PUT", key(), "u"))  # Teil ohne Nummer
