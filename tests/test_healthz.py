"""Gesundheitsprüfung für Deploy-Job und externes Monitoring (Ticket #27, ADR 0007)."""

import pytest
from storage_backends import moto_endpoint, moto_storage  # noqa: F401  (Fixture)


@pytest.fixture
def s3_settings(settings, moto_endpoint):  # noqa: F811
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
