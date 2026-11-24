"""Erreichbarkeit für Deploy-Job und externes Monitoring (Ticket #27, ADR 0007)."""

import socket
import time

import pytest
from storage_backends import moto_storage


@pytest.fixture
def s3_settings(settings, moto_endpoint):
    settings.STORAGE_BACKEND = "s3"
    settings.S3_ENDPOINT_URL = moto_endpoint
    settings.S3_REGION = "us-east-1"
    settings.S3_ACCESS_KEY_ID = "test"
    settings.S3_SECRET_ACCESS_KEY = "test"
    settings.S3_ADDRESSING_STYLE = "path"
    return settings


@pytest.mark.django_db
def test_ok_wenn_datenbank_und_speicher_erreichbar(client, settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.django_db
def test_nicht_ok_ohne_details_wenn_s3_speicher_nicht_erreichbar(client, s3_settings):
    s3_settings.S3_BUCKET = "gibt-es-nicht"
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.content == b"nicht ok"


@pytest.mark.django_db
def test_ok_mit_erreichbarem_s3_bucket(client, s3_settings):
    s3_settings.S3_BUCKET = moto_storage(s3_settings.S3_ENDPOINT_URL, "gesund").bucket
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.fixture
def stummer_endpunkt():
    """Nimmt Verbindungen an, antwortet aber nie (wie ein hängender Speicher)."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(8)
        yield f"http://127.0.0.1:{server.getsockname()[1]}"


@pytest.mark.django_db
def test_nicht_ok_ohne_langes_warten_wenn_s3_speicher_nicht_antwortet(
    client, s3_settings, stummer_endpunkt
):
    s3_settings.S3_ENDPOINT_URL = stummer_endpunkt
    s3_settings.S3_BUCKET = "egal"
    start = time.monotonic()
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.content == b"nicht ok"
    # Monitoring und Deploy-Job fragen mit kurzer Zeitgrenze; gunicorn bricht nach 60 s ab.
    assert time.monotonic() - start < 10
