"""JSON-Endpunkte für den Upload im Browser. Alle an die Abgabe aus dem Cookie gebunden."""

import functools
import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import access, exposure, services, uploads
from .models import Master, Submission


def _submission(request, reference) -> Submission:
    if not access.may_access(request, reference):
        raise Http404
    return get_object_or_404(Submission, reference=reference)


def _with_master(view):
    """Übergibt den Master der eigenen Abgabe. Fehlt er, wurde er gelöscht, etwa in einem
    anderen Tab, während dieser noch hochlädt; das soll der Uploader verständlich anzeigen."""

    @functools.wraps(view)
    def wrapper(request, reference, master_id):
        submission = _submission(request, reference)
        master = Master.objects.filter(public_id=master_id, submission=submission).first()
        if master is None:
            return JsonResponse({"error": "Dieser Master wurde gelöscht."}, status=404)
        return view(request, master)

    return wrapper


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
@_with_master
def sign(request, master):
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
@_with_master
def abort(request, master):
    # Ohne JavaScript schickt der Browser das Formular; dann zurück zur Abgabeseite.
    from_form = request.content_type == "application/x-www-form-urlencoded"
    try:
        master = uploads.abort(master)
    except (uploads.UploadError, uploads.Conflict) as exc:
        if from_form:
            messages.error(request, str(exc))
            return redirect("submission", master.submission.reference)
        return _error(exc, 409 if isinstance(exc, uploads.Conflict) else 400)
    if from_form:
        messages.info(request, f"Upload von {master.original_name} abgebrochen.")
        return redirect("submission", master.submission.reference)
    return JsonResponse({**master_json(master), "usage": _usage_json(master.submission)})


def _usage_json(submission: Submission) -> dict:
    """Neue Belegung, damit die Abgabeseite sie ohne Neuladen anzeigen kann."""
    usage = uploads.quota_usage(submission)
    label = render_to_string("submissions/_usage_label.html", usage).strip()
    return {"label": label, "percent": usage["percent"]}


@require_POST
@_with_master
def finish(request, master):
    try:
        master = uploads.finish(master, sha256=_json(request).get("sha256"))
    except uploads.UploadError as exc:
        return _error(exc, 400)
    except uploads.NotFinished as exc:
        return _error(exc, 409)
    return JsonResponse(master_json(master))


def render_exposure(request, master: Master, *, editable: bool) -> str:
    """Der aufklappbare Bereich „Belichtungsangaben“ einer Master-Zeile, aufgeklappt."""
    return render_to_string(
        "submissions/_exposure.html",
        {"m": master, "submission": master.submission, "editable": editable, "open": True},
        request=request,
    )


@require_POST
@_with_master
def change_exposure(request, master):
    """Belichtungsangaben ändern: JSON aus dem Browser, ohne JavaScript ein Formular."""
    from_form = request.content_type != "application/json"
    back = redirect(
        f"{reverse('submission', args=[master.submission.reference])}#belichtung-{master.public_id}"
    )
    if not services.exposure_changeable_by_participant(master):
        error = "Die Aktion ist beendet. Belichtungsangaben ändert jetzt nur noch der Betreiber."
        if from_form:
            messages.error(request, error)
            return back
        return JsonResponse({"error": error}, status=403)
    try:
        data = request.POST.dict() if from_form else _json(request)
        services.change_exposure(master, data)
    except (uploads.UploadError, exposure.InvalidInput) as exc:
        if from_form:
            messages.error(request, str(exc))
            return back
        return _error(exc, 400)
    if from_form:
        messages.info(request, f"Belichtungsangaben zu {master.original_name} gespeichert.")
        return back
    return JsonResponse({"html": render_exposure(request, master, editable=True)})
