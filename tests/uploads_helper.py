"""Spielt im Test den Browser (Uppy mit dem AWS-S3-Plugin) gegen den HTTP-Seam."""

import hashlib
import json
import re
from xml.sax.saxutils import escape

from django.test import Client

from submissions.models import Master, Submission

PART_SIZE = 1024


def new_submission(form):
    """Legt im Browser eine Submission an; gibt Client (mit Cookie) und Submission zurück."""
    from django.test import Client

    from submissions.models import Submission

    client = Client()
    before = set(Submission.objects.values_list("pk", flat=True))
    client.post("/", form)
    return client, Submission.objects.exclude(pk__in=before).get()


def start(client, reference, *, channel="L", filename="m101_L.fits", size):
    return client.post(
        f"/submission/{reference}/master/",
        json.dumps({"channel": channel, "filename": filename, "size": size}),
        content_type="application/json",
    )


def sign(client, reference, master_id, **request):
    return client.post(
        f"/submission/{reference}/master/{master_id}/signieren/",
        json.dumps(request),
        content_type="application/json",
    )


DUMMY_SHA256 = "0" * 64


def finish(client, reference, master_id, sha256=DUMMY_SHA256):
    body = {} if sha256 is None else {"sha256": sha256}
    return client.post(
        f"/submission/{reference}/master/{master_id}/fertig/",
        json.dumps(body),
        content_type="application/json",
    )


def _tag(xml, name):
    return re.search(rf"<{name}>(.*?)</{name}>", xml).group(1)


def send_parts(client, reference, master_id, key, upload_id, data, part_size=PART_SIZE, first=1):
    parts = []
    for number, offset in enumerate(range(0, len(data), part_size), start=first):
        url = sign(
            client, reference, master_id,
            method="PUT", key=key, uploadId=upload_id, partNumber=number,
        ).json()["url"]  # fmt: skip
        response = client.put(
            url, data[offset : offset + part_size], content_type="application/octet-stream"
        )
        assert response.status_code == 200, response.content
        parts.append((number, response["ETag"]))
    return parts


def complete(client, reference, master_id, key, upload_id, parts):
    url = sign(client, reference, master_id, method="POST", key=key, uploadId=upload_id).json()[
        "url"
    ]
    body = (
        "<CompleteMultipartUpload>"
        + "".join(
            f"<Part><PartNumber>{n}</PartNumber><ETag>{escape(e)}</ETag></Part>" for n, e in parts
        )
        + "</CompleteMultipartUpload>"
    )
    response = client.post(url, body, content_type="application/xml")
    assert response.status_code == 200, response.content
    return response


def create(client, url):
    response = client.post(url, b"", content_type="application/octet-stream")
    assert response.status_code == 200, response.content
    return _tag(response.content.decode(), "UploadId")


def upload(client, reference, data, *, channel="L", filename="m101_L.fits", part_size=PART_SIZE):
    """Kompletter Ablauf wie im Browser; gibt die Antwort der Fertig-Meldung zurück."""
    started = start(client, reference, channel=channel, filename=filename, size=len(data))
    assert started.status_code == 201, started.content
    body = started.json()
    upload_id = create(client, body["url"])
    parts = send_parts(client, reference, body["masterId"], body["key"], upload_id, data, part_size)
    complete(client, reference, body["masterId"], body["key"], upload_id, parts)
    return finish(client, reference, body["masterId"], hashlib.sha256(data).hexdigest())


class Participant:
    """Eine teilnehmende Person mit eigenem Browser und einer Submission."""

    def __init__(self, form):
        self.client = Client()
        before = set(Submission.objects.values_list("pk", flat=True))
        self.client.post("/", form)
        self.submission = Submission.objects.exclude(pk__in=before).get()

    @property
    def reference(self):
        return self.submission.reference

    def upload(self, data, **kwargs):
        response = upload(self.client, self.reference, data, **kwargs)
        return Master.objects.get(public_id=response.json()["masterId"])

    def used(self):
        return self.client.get(f"/submission/{self.reference}/").context["used"]
