from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import access, privacy, services
from .forms import SubmissionForm
from .models import Campaign, Master, Phase, Submission
from .services import create_submission
from .uploads import (
    interrupted,
    may_start,
    quota_usage,
    recently_active,
    release_stale,
    resumable,
    shows_uploader,
)


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
    context["privacy_version"] = settings.CONSENT_TEXT_VERSION
    return render(request, "submissions/entry.html", {**context, "form": form})


@require_http_methods(["GET"])
def privacy_notice(request, version=None):
    """Datenschutzhinweis in der aktuellen oder einer früheren Fassung."""
    current = settings.CONSENT_TEXT_VERSION
    version = version or current
    name = privacy.template_name(version)
    if name is None:
        raise Http404
    return render(
        request,
        name,
        {"version": version, "current": current, "contact": settings.PRIVACY_CONTACT},
    )


@require_http_methods(["GET"])
def submission(request, reference):
    submission = _own_submission(request, reference)
    campaign = Campaign.current()
    release_stale()
    phase = Campaign.current_phase()
    masters = submission.masters.all()
    abortable = interrupted(masters)
    can_add = phase.accepts_new_submissions and access.has_room(request)
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
            "deletable_ids": set(
                masters.filter(state__in=services.DELETABLE).values_list("pk", flat=True)
            ),
            "resumable_ids": set(resumable(masters).values_list("pk", flat=True)),
            "active_ids": set(recently_active(abortable).values_list("pk", flat=True)),
            "phase": phase.name.lower(),
            "show_uploader": shows_uploader(submission),
            "may_start": may_start(submission),
            "may_change": services.changeable_by_participant(submission),
            **quota_usage(submission),
            "max_master_size": campaign.max_master_size if campaign else 0,
            "channels": Master.Channel.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def withdraw(request, reference):
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
    if request.method == "POST":
        services.withdraw(submission, by=Submission.WithdrawnBy.PARTICIPANT)
        messages.info(request, "Deine Abgabe wurde zurückgezogen.")
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
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
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


def _not_changeable(request, submission):
    """Zurück zur Abgabeseite, wenn Teilnehmende nichts mehr ändern dürfen; sie erklärt den
    Rückzug selbst, das Ende der Aktion sagt die Meldung."""
    if not submission.is_withdrawn:
        messages.info(request, "Die Aktion ist beendet. Deine Abgabe kannst du nicht mehr ändern.")
    return redirect("submission", submission.reference)


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
