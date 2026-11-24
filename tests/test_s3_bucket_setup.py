"""Einrichtung des S3-Buckets per Befehl (Ticket #12)."""

import uuid

import pytest
from django.core.management import CommandError, call_command
from storage_backends import moto_endpoint, moto_storage  # noqa: F401

from storage.management.commands import s3_bucket_setup
from storage.management.commands.s3_bucket_setup import normalize_origin


@pytest.fixture
def s3(settings, moto_endpoint):  # noqa: F811
    bucket = f"b{uuid.uuid4().hex[:12]}"
    storage = moto_storage(moto_endpoint, bucket)
    settings.STORAGE_BACKEND = "s3"
    settings.S3_BUCKET = bucket
    settings.S3_ENDPOINT_URL = moto_endpoint
    settings.S3_REGION = "us-east-1"
    settings.S3_ACCESS_KEY_ID = "test"
    settings.S3_SECRET_ACCESS_KEY = "test"
    settings.S3_ADDRESSING_STYLE = "path"
    return storage


def test_setzt_cors_und_lifecycle(s3):
    call_command("s3_bucket_setup", "--origin", "https://upload.dzvf.de")
    cors = s3.client.get_bucket_cors(Bucket=s3.bucket)["CORSRules"][0]
    assert cors["AllowedOrigins"] == ["https://upload.dzvf.de"]
    assert "ETag" in cors["ExposeHeaders"]
    assert set(cors["AllowedMethods"]) == {"GET", "PUT", "POST", "DELETE"}
    rule = s3.client.get_bucket_lifecycle_configuration(Bucket=s3.bucket)["Rules"][0]
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7


def test_nur_https(s3):
    with pytest.raises(CommandError):
        call_command("s3_bucket_setup", "--origin", "http://upload.dzvf.de")


def test_nur_mit_s3(settings):
    settings.STORAGE_BACKEND = "local"
    with pytest.raises(CommandError):
        call_command("s3_bucket_setup", "--origin", "https://upload.dzvf.de")


def test_umlautdomain_als_punycode(s3):
    call_command("s3_bucket_setup", "--origin", "https://Upload.Klöpping.de/")
    cors = s3.client.get_bucket_cors(Bucket=s3.bucket)["CORSRules"][0]
    assert cors["AllowedOrigins"] == ["https://upload.xn--klpping-b1a.de"]


def test_gleiche_herkunft_nur_einmal(s3):
    call_command(
        "s3_bucket_setup",
        "--origin",
        "https://upload.klöpping.de",
        "--origin",
        "https://upload.xn--klpping-b1a.de",
    )
    cors = s3.client.get_bucket_cors(Bucket=s3.bucket)["CORSRules"][0]
    assert cors["AllowedOrigins"] == ["https://upload.xn--klpping-b1a.de"]


@pytest.mark.parametrize(
    "origin, erwartet",
    [
        ("https://upload.dzvf.de", "https://upload.dzvf.de"),
        ("HTTPS://upload.dzvf.de/", "https://upload.dzvf.de"),
        ("http://localhost:8000", "http://localhost:8000"),
        ("https://bücher.example", "https://xn--bcher-kva.example"),
    ],
)
def test_herkunft_normalisieren(origin, erwartet):
    assert normalize_origin(origin) == erwartet


@pytest.mark.parametrize("origin", ["upload.dzvf.de", "https://upload.dzvf.de/abgabe/"])
def test_herkunft_ohne_schema_oder_mit_pfad_abgelehnt(origin):
    with pytest.raises(CommandError):
        normalize_origin(origin)


def test_preflight_scheitert_wenn_freigabe_nicht_greift(s3, monkeypatch):
    # Der Speicher nimmt die Regel an, gibt aber eine andere Herkunft frei.
    original = s3_bucket_setup.cors_rules
    monkeypatch.setattr(
        s3_bucket_setup, "cors_rules", lambda origins: original(["https://anders.example"])
    )
    with pytest.raises(CommandError, match="CORS-Freigabe greift nicht"):
        call_command("s3_bucket_setup", "--origin", "https://upload.dzvf.de")
