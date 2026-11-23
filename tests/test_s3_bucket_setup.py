"""Einrichtung des S3-Buckets per Befehl (Ticket #12)."""

import uuid

import pytest
from django.core.management import CommandError, call_command
from storage_backends import moto_endpoint, moto_storage  # noqa: F401


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
