from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import access, services
from .forms import SubmissionForm
from .models import Campaign, Master, Phase, Submission
from .services import create_submission
from .uploads import release_stale, usage


@require_http_methods(["GET", "POST"])
def entry(request):
    """Einstieg über den Link der Projektwebsite: zur eigenen Abgabe oder zum Formular."""
    existing = access.references(request)
    if request.method == "GET" and existing and Campaign.current() is not None:
        return redirect("submission", existing[0])
    return new_submission(request)


@require_http_methods(["GET", "POST"])
def new_submission(request):
    campaign = Campaign.current()
    if campaign is None:
        return render(request, "submissions/not_ready.html", status=503)

    phase = campaign.phase()
    context = {"campaign": campaign, "before_start": phase is Phase.BEFORE, "own": _own(request)}
    if not phase.accepts_new_submissions:
        return render(request, "submissions/closed.html", context)
    if not access.has_room(request):
        context["max_per_browser"] = access.MAX_PER_BROWSER
        return render(request, "submissions/limit.html", context)

    form = SubmissionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        submission = create_submission(
            credit_name=form.cleaned_data["credit_name"],
            setup_description=form.cleaned_data["setup_description"],
            publish_credit=form.cleaned_data["consent_publish_credit"],
        )
        if form.cleaned_data["credit_name"] and not submission.credit_name:
            messages.info(
                request,
                "Deinen Namen haben wir nicht gespeichert: Ohne Häkchen bei der Veröffentlichung "
                "trägst du anonym bei.",
            )
        response = redirect("submission", submission.reference)
        access.grant(response, request, submission.reference, campaign)
        return response
    return render(request, "submissions/entry.html", {**context, "form": form})


@require_http_methods(["GET"])
def submission(request, reference):
    submission = _own_submission(request, reference)
    campaign = Campaign.current()
    release_stale()
    used = usage(submission.masters.all())
    quota = campaign.quota if campaign else 0
    phase = campaign.phase() if campaign else Phase.CLOSED
    masters = submission.masters.all()
    # Unterbrochene Uploads: im Speicher angelegt, aber nie fertig gemeldet. Fortsetzen geht,
    # solange die Abgabe nicht schreibgeschützt ist.
    resumable = (
        masters.filter(state=Master.State.UPLOADING).exclude(upload_id="")
        if phase in (Phase.OPEN, Phase.GRACE)
        else masters.none()
    )
    show_uploader = not submission.is_withdrawn and (
        phase is Phase.OPEN or (phase is Phase.GRACE and resumable.exists())
    )
    can_add = (
        campaign is not None
        and campaign.phase().accepts_new_submissions
        and access.has_room(request)
    )
    return render(
        request,
        "submissions/submission.html",
        {
            "campaign": campaign,
            "submission": submission,
            "own": _own(request),
            "can_add": can_add,
            "masters": masters.exclude(state=Master.State.ABORTED),
            "deletable_ids": set(
                masters.filter(state__in=services.DELETABLE).values_list("pk", flat=True)
            ),
            "resumable_ids": set(resumable.values_list("pk", flat=True)),
            "phase": phase.name.lower(),
            "show_uploader": show_uploader,
            "may_start": phase is Phase.OPEN,
            "may_change": services.changeable_by_participant(submission),
            "used": used,
            "quota": quota,
            "used_percent": min(100, used * 100 // quota) if quota else 0,
            "max_master_size": campaign.max_master_size if campaign else 0,
            "channels": Master.Channel.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def withdraw(request, reference):
    submission = _changeable_submission(request, reference)
    if request.method == "POST":
        services.withdraw(submission, by=Submission.WithdrawnBy.PARTICIPANT)
        return redirect("submission", submission.reference)
    return _confirm(
        request,
        submission,
        title="Abgabe zurückziehen",
        question=(
            "Alle Master, Angaben und Einwilligungen dieser Abgabe werden endgültig gelöscht. "
            "Es bleibt nur die Abgabe-Kennung. Die Abgabe lässt sich nicht wieder öffnen."
        ),
        button="Ja, zurückziehen",
    )


@require_http_methods(["GET", "POST"])
def delete_master(request, reference, master_id):
    submission = _changeable_submission(request, reference)
    master = get_object_or_404(
        Master, submission=submission, public_id=master_id, state__in=services.DELETABLE
    )
    if request.method == "POST":
        services.delete_master(master)
        messages.info(request, f"Der Master {master.original_name} wurde gelöscht.")
        return redirect("submission", submission.reference)
    return _confirm(
        request,
        submission,
        title="Master löschen",
        question=(
            "Dieser Master wird sofort und endgültig gelöscht."
            + (" Der Upload wird abgebrochen." if master.state == Master.State.UPLOADING else "")
        ),
        details=[f"{master.get_channel_display()} · {master.original_name}"],
        button="Ja, löschen",
    )


def _own_submission(request, reference) -> Submission:
    if not access.may_access(request, reference):
        raise Http404
    return get_object_or_404(Submission, reference=reference)


def _changeable_submission(request, reference) -> Submission:
    """Die eigene Abgabe, solange Teilnehmende sie noch ändern dürfen."""
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        raise PermissionDenied
    return submission


def _confirm(request, submission, *, title, question, button, details=()):
    """Rückfrage vor einer Löschung; Abbrechen führt zurück zur Abgabeseite."""
    return render(
        request,
        "submissions/confirm.html",
        {
            "submission": submission,
            "title": title,
            "question": question,
            "details": details,
            "button": button,
        },
    )


def _own(request) -> list[Submission]:
    refs = access.references(request)
    found = {s.reference: s for s in Submission.objects.filter(reference__in=refs)}
    return [found[r] for r in refs if r in found]
