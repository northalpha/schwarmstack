"""Antworten des lokalen S3-Nachbaus: Abschluss-Body wird linear gelesen, Fehler verraten nichts."""

import time
import uuid

import pytest
from django.test import Client

from storage import S3Request, get_storage

pytestmark = pytest.mark.django_db


def _url(method, key, upload_id=None):
    return get_storage().presign(S3Request(method, key, upload_id))


def test_abschluss_mit_boesem_body_ist_schnell_und_abgelehnt():
    client = Client()
    key = f"SW-TEST/{uuid.uuid4().hex}.fits"
    upload_id = client.post(_url("POST", key)).content.decode().split("<UploadId>")[1].split("<")[0]
    body = "<PartNumber>" + "9a" * 200_000 + "<ETag>" + " " * 200_000
    start = time.monotonic()
    response = client.post(_url("POST", key, upload_id), body, content_type="application/xml")
    assert time.monotonic() - start < 2
    assert response.status_code == 400


def test_fehlermeldung_nennt_keine_internas():
    client = Client()
    key = f"SW-TEST/{uuid.uuid4().hex}.fits"
    response = client.get(_url("GET", key, "gibt-es-nicht"))
    assert response.status_code == 400
    assert response.content.decode() == "Anfrage abgelehnt"


def test_etag_in_anfuehrungszeichen_und_entities_wird_gelesen():
    from storage.local_views import parse_parts

    xml = (
        "<Part><PartNumber> 1 </PartNumber><ETag>&quot;abc&quot;</ETag></Part>"
        '<Part><PartNumber>2</PartNumber><ETag>"def"</ETag></Part>'
        "<Part><PartNumber>3</PartNumber><ETag>&#34;ghi&#34;</ETag></Part>"
    )
    assert parse_parts(xml) == [(1, "abc"), (2, "def"), (3, "ghi")]
