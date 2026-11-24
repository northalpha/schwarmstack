from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import access
from .forms import SubmissionForm
from .models import Campaign, Master, Phase, Submission
from .services import create_submission
from .uploads import interrupted, quota_usage, recently_active, release_stale


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
    if not access.may_access(request, reference):
        raise Http404
    submission = get_object_or_404(Submission, reference=reference)
    campaign = Campaign.current()
    release_stale()
    phase = Campaign.current_phase()
    masters = submission.masters.all()
    # Unterbrochene Uploads: nie fertig gemeldet. Abbrechen lässt sich jeder; fortsetzen nur,
    # wenn der Multipart-Upload im Speicher schon angelegt ist.
    abortable = interrupted(masters)
    resumable = abortable.exclude(upload_id="")
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
            "abortable_ids": set(abortable.values_list("pk", flat=True)),
            "resumable_ids": set(resumable.values_list("pk", flat=True)),
            "active_ids": set(recently_active(abortable).values_list("pk", flat=True)),
            "phase": phase.name.lower(),
            "show_uploader": show_uploader,
            "may_start": phase is Phase.OPEN,
            **quota_usage(submission),
            "max_master_size": campaign.max_master_size if campaign else 0,
            "channels": Master.Channel.choices,
        },
    )


def _own(request) -> list[Submission]:
    refs = access.references(request)
    found = {s.reference: s for s in Submission.objects.filter(reference__in=refs)}
    return [found[r] for r in refs if r in found]
