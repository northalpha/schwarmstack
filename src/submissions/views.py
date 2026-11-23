from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import access
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
    used = usage(submission.masters.all())
    quota = campaign.quota if campaign else 0
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
            "masters": submission.masters.exclude(state=Master.State.ABORTED),
            "used": used,
            "quota": quota,
            "used_percent": min(100, used * 100 // quota) if quota else 0,
            "max_master_size": campaign.max_master_size if campaign else 0,
            "channels": Master.Channel.choices,
        },
    )


def _own(request) -> list[Submission]:
    refs = access.references(request)
    found = {s.reference: s for s in Submission.objects.filter(reference__in=refs)}
    return [found[r] for r in refs if r in found]
