"""Lokaler Endpunkt, der für Uppy die nötigen S3-Antworten nachbildet (nur lokaler Speicher)."""

import re
from xml.sax.saxutils import escape

from django.core import signing
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from . import get_storage
from .local import StorageError, read_token

_PART = re.compile(r"<PartNumber>\s*(\d+)\s*</PartNumber>\s*<ETag>(.*?)</ETag>", re.S)
_QUOTES = re.compile(r'^(?:"|&quot;|&#34;)+|(?:"|&quot;|&#34;)+$')


def _xml(body: str) -> HttpResponse:
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>' + body, content_type="application/xml"
    )


@csrf_exempt  # Die Signatur im Link ist die Berechtigung, wie bei S3.
def local_s3(request, token):
    try:
        signed = read_token(token)
    except signing.BadSignature:
        return HttpResponseForbidden("Link ungültig oder abgelaufen")
    if signed.method != request.method:
        return HttpResponseForbidden("Link gilt nicht für diese Methode")

    storage = get_storage()
    key, upload_id = signed.key, signed.upload_id
    try:
        if request.method == "POST" and upload_id is None:
            new_id = storage.create_multipart(key)
            return _xml(
                "<InitiateMultipartUploadResult><Bucket>lokal</Bucket>"
                f"<Key>{escape(key)}</Key><UploadId>{new_id}</UploadId>"
                "</InitiateMultipartUploadResult>"
            )
        if request.method == "PUT" and signed.part_number is not None:
            etag = storage.upload_part(key, upload_id, signed.part_number, request)
            response = HttpResponse(status=200)
            response["ETag"] = f'"{etag}"'
            return response
        if request.method == "GET":
            parts = "".join(
                f"<Part><PartNumber>{n}</PartNumber><ETag>&quot;{e}&quot;</ETag>"
                f"<Size>{s}</Size></Part>"
                for n, e, s in storage.list_parts(key, upload_id)
            )
            return _xml(
                f"<ListPartsResult><UploadId>{upload_id}</UploadId>{parts}</ListPartsResult>"
            )
        if request.method == "POST":
            body = request.body.decode("utf-8", "replace")
            parts = [(int(n), _QUOTES.sub("", e.strip())) for n, e in _PART.findall(body)]
            etag = storage.complete_multipart(key, upload_id, parts)
            return _xml(
                "<CompleteMultipartUploadResult>"
                f"<Location>/{escape(key)}</Location><Bucket>lokal</Bucket>"
                f"<Key>{escape(key)}</Key><ETag>&quot;{etag}&quot;</ETag>"
                "</CompleteMultipartUploadResult>"
            )
        if request.method == "DELETE" and upload_id is not None:
            storage.abort_multipart(key, upload_id)
            return HttpResponse(status=204)
    except StorageError as exc:
        return HttpResponseBadRequest(str(exc))
    return HttpResponseBadRequest("Nicht unterstützt")
