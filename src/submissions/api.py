"""JSON-Endpunkte für den Upload im Browser. Alle an die Abgabe aus dem Cookie gebunden."""

import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from . import access, uploads
from .models import Master, Submission


def _submission(request, reference) -> Submission:
    if not access.may_access(request, reference):
        raise Http404
    return get_object_or_404(Submission, reference=reference)


def _master(request, reference, master_id) -> Master:
    return get_object_or_404(
        Master, public_id=master_id, submission=_submission(request, reference)
    )


def _json(request) -> dict:
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise uploads.UploadError("Ungültige Anfrage.") from exc
    if not isinstance(data, dict):
        raise uploads.UploadError("Ungültige Anfrage.")
    return data


def _error(exc: Exception, status: int) -> JsonResponse:
    return JsonResponse({"error": str(exc)}, status=status)


def master_json(master: Master) -> dict:
    return {
        "masterId": str(master.public_id),
        "state": master.state,
        "stateLabel": master.get_state_display(),
        "channel": master.channel,
        "name": master.original_name,
        "size": master.size,
        "reason": master.rejection_reason,
    }


@require_POST
def start(request, reference):
    submission = _submission(request, reference)
    try:
        data = _json(request)
        master, url = uploads.start(
            submission,
            channel=data.get("channel"),
            filename=data.get("filename"),
            size=data.get("size"),
        )
    except uploads.UploadError as exc:
        return _error(exc, 400)
    return JsonResponse(
        {"masterId": str(master.public_id), "key": master.key, "url": url}, status=201
    )


@require_POST
def sign(request, reference, master_id):
    master = _master(request, reference, master_id)
    try:
        data = _json(request)
        url = uploads.sign(
            master,
            method=data.get("method"),
            key=data.get("key"),
            upload_id=data.get("uploadId"),
            part_number=data.get("partNumber"),
        )
    except uploads.UploadError as exc:
        return _error(exc, 400)
    return JsonResponse({"url": url})


@require_POST
def abort(request, reference, master_id):
    master = _master(request, reference, master_id)
    try:
        master = uploads.abort(master)
    except uploads.Conflict as exc:
        return _error(exc, 409)
    return JsonResponse(master_json(master))


@require_POST
def finish(request, reference, master_id):
    master = _master(request, reference, master_id)
    try:
        master = uploads.finish(master, sha256=_json(request).get("sha256"))
    except uploads.UploadError as exc:
        return _error(exc, 400)
    except uploads.NotFinished as exc:
        return _error(exc, 409)
    return JsonResponse(master_json(master))
