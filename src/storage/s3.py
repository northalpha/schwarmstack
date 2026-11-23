"""Speicher im S3-kompatiblen Bucket (Hetzner in Produktion, Garage in CI).

Der Server spricht S3 nur für Größe, Teilabruf, Löschen, Begleitdateien und kurz gültige
Download-Links für Betreiber; die Master selbst
lädt der Browser mit signierten Links direkt hoch (ADR 0005).
"""

import json

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from . import S3Request

# S3-Anfrage des Browsers -> boto3-Operation
_OPERATIONS = {
    ("POST", False): "create_multipart_upload",
    ("PUT", True): "upload_part",
    ("GET", True): "list_parts",
    ("POST", True): "complete_multipart_upload",
    ("DELETE", True): "abort_multipart_upload",
}


class S3Storage:
    def __init__(
        self,
        *,
        bucket,
        endpoint_url=None,
        region=None,
        access_key_id=None,
        secret_access_key=None,
        addressing_style="virtual",
        link_seconds=900,
    ):
        self.bucket = bucket
        self.link_seconds = link_seconds
        verbindung = dict(
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
        )
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": addressing_style},
            # Nur dort Prüfsummen, wo S3 sie verlangt (Garage und Hetzner kennen nicht alle).
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        )
        self.client = boto3.client("s3", **verbindung, config=config)
        # Für /healthz: ein hängender Speicher soll schnell als nicht erreichbar gelten.
        self._erreichbarkeit = boto3.client(
            "s3",
            **verbindung,
            config=config.merge(
                Config(connect_timeout=2, read_timeout=3, retries={"total_max_attempts": 1})
            ),
        )

    def presign(self, request: S3Request) -> str:
        operation = _OPERATIONS.get((request.method, request.upload_id is not None))
        if operation is None or (operation == "upload_part") != (request.part_number is not None):
            raise ValueError(f"Nicht signierbar: {request}")
        params = {"Bucket": self.bucket, "Key": request.key}
        if request.upload_id is not None:
            params["UploadId"] = request.upload_id
        if request.part_number is not None:
            params["PartNumber"] = request.part_number
        return self.client.generate_presigned_url(
            operation, Params=params, ExpiresIn=self.link_seconds
        )

    def size(self, key: str) -> int | None:
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def read_head(self, key: str, length: int) -> bytes:
        response = self.client.get_object(
            Bucket=self.bucket, Key=key, Range=f"bytes=0-{length - 1}"
        )
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def put_json(self, key: str, data: dict) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode(),
            ContentType="application/json",
        )

    def abort_multipart(self, key: str, upload_id: str) -> None:
        self.client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)

    def ensure_reachable(self) -> None:
        self._erreichbarkeit.head_bucket(Bucket=self.bucket)

    def download_url(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.link_seconds
        )
