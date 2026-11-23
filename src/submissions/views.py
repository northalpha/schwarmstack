from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import access
from .forms import SubmissionForm
from .models import Campaign, Submission
from .services import create_submission


@require_http_methods(["GET", "POST"])
def entry(request):
    campaign = Campaign.current()
    if campaign is None:
        return render(request, "submissions/not_ready.html", status=503)

    existing = access.references(request)
    if request.method == "GET" and existing:
        return redirect("submission", existing[0])

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
    return render(request, "submissions/entry.html", {"campaign": campaign, "form": form})


@require_http_methods(["GET"])
def submission(request, reference):
    if not access.may_access(request, reference):
        raise Http404
    submission = get_object_or_404(Submission, reference=reference)
    return render(
        request,
        "submissions/submission.html",
        {"campaign": Campaign.current(), "submission": submission},
    )
