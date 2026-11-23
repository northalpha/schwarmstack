"""Speicher-Adapter für die Vertragstests: lokale Platte, S3 mit moto, Garage (wenn verfügbar)."""

import os
from dataclasses import dataclass

import boto3
import pytest
import requests

from storage.s3 import S3Storage

GARAGE_ENV = ["S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"]


def garage_available() -> bool:
    return all(os.environ.get(name) for name in GARAGE_ENV)


def garage_storage(**kwargs) -> S3Storage:
    return S3Storage(
        bucket=os.environ["S3_BUCKET"],
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        region=os.environ.get("S3_REGION", "garage"),
        access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        addressing_style=os.environ.get("S3_ADDRESSING_STYLE", "path"),
        **kwargs,
    )


@dataclass
class Reply:
    status: int
    headers: dict
    text: str


class HttpBrowser:
    """Führt signierte S3-Links aus wie der Browser (absolute URLs)."""

    def send(self, method, url, body=b"", content_type=None) -> Reply:
        headers = {"Content-Type": content_type} if content_type else {}
        response = requests.request(method, url, data=body, headers=headers, timeout=30)
        return Reply(response.status_code, dict(response.headers), response.text)


class DjangoBrowser:
    """Führt Links des lokalen Adapters über den Django-Test-Client aus (relative URLs)."""

    def __init__(self, client):
        self.client = client

    def send(self, method, url, body=b"", content_type=None) -> Reply:
        response = self.client.generic(
            method, url, data=body, content_type=content_type or "application/octet-stream"
        )
        return Reply(response.status_code, dict(response.items()), response.content.decode())


@pytest.fixture(scope="session")
def moto_endpoint():
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


def moto_storage(endpoint, bucket="vertrag", **kwargs) -> S3Storage:
    credentials = {"aws_access_key_id": "test", "aws_secret_access_key": "test"}
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1", **credentials)
    s3.create_bucket(Bucket=bucket)
    return S3Storage(
        bucket=bucket,
        endpoint_url=endpoint,
        region="us-east-1",
        access_key_id="test",
        secret_access_key="test",
        addressing_style="path",
        **kwargs,
    )
