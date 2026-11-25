from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from storage import get_storage

from . import access, privacy, services
from .forms import CreditForm, DetailsForm, PhotoForm, SubmissionForm
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
    """Einstieg über den Link der Projektwebsite: zur eigenen Submission oder zum Formular."""
    existing = _held(request)
    if request.method == "GET" and existing and Campaign.current() is not None:
        return redirect("submission", existing[0].reference)
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
    if not access.has_room(len(_held(request))):
        context["max_per_browser"] = access.MAX_PER_BROWSER
        return render(request, "submissions/limit.html", context)

    form = SubmissionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        submission = create_submission(
            credit_name=form.cleaned_data["credit_name"],
            setup_description=form.cleaned_data["setup_description"],
            publish_credit=form.cleaned_data["consent_publish_credit"],
            photo=form.photo,
            photo_consent=form.cleaned_data["consent_equipment_photo"],
        )
        if form.cleaned_data["credit_name"] and not submission.credit_name:
            messages.info(
                request,
                "Deinen Namen haben wir nicht gespeichert: Ohne Häkchen bei der Namensnennung "
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
    can_add = phase.accepts_new_submissions and access.has_room(len(_held(request)))
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
            "may_revoke": services.consent_revocable_by_participant(submission) is not None,
            "may_grant": services.consent_grantable_by_participant(submission),
            **quota_usage(submission),
            "max_master_size": campaign.max_master_size if campaign else 0,
            "channels": Master.Channel.choices,
            "privacy_version": settings.CONSENT_TEXT_VERSION,
        },
    )


@require_http_methods(["GET", "POST"])
def change_details(request, reference):
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
    initial = {
        "setup_description": submission.setup_description,
        "credit_name": submission.credit_name,
    }
    form = DetailsForm(request.POST or None, initial=initial, submission=submission)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        consent = (
            services.consent_revocable_by_participant(submission)
            if data.get("revoke_credit")
            else None
        )
        if consent is not None:
            # Der Widerruf löscht die Namensnennung; ein eingetragener Name wird nicht gespeichert.
            services.change_details(submission, setup_description=data["setup_description"])
            services.revoke(consent)
            messages.info(request, "Deine Einwilligung zur Namensnennung ist widerrufen.")
        else:
            services.change_details(
                submission,
                setup_description=data["setup_description"],
                credit_name=data.get("credit_name"),
            )
            messages.info(request, "Deine Angaben wurden geändert.")
        return redirect("submission", submission.reference)
    context = {"submission": submission, "form": form}
    if submission.photo is None:
        context["photo_form"] = PhotoForm(submission=submission)
    return render(request, "submissions/details.html", context)


@require_http_methods(["GET", "POST"])
def change_photo(request, reference):
    """Equipment-Foto hinzufügen oder ersetzen, unabhängig von den übrigen Angaben (Ticket #82)."""
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
    form = PhotoForm(request.POST or None, request.FILES or None, submission=submission)
    if request.method == "POST" and form.is_valid():
        try:
            replaced = services.add_photo(
                submission,
                form.photo,
                consent_given=form.cleaned_data.get("consent_equipment_photo", False),
            )
        except services.PhotoNotAllowed:
            return _not_changeable(request, submission)
        except services.PhotoConsentMissing:  # die Fassung des Hinweistextes wechselte eben
            form.add_error("consent_equipment_photo", "Bitte erteile die Einwilligung erneut.")
        else:
            messages.info(
                request,
                "Dein Equipment-Foto wurde ersetzt."
                if replaced
                else "Dein Equipment-Foto wurde gespeichert.",
            )
            return redirect("submission", submission.reference)
    return render(request, "submissions/photo.html", {"submission": submission, "form": form})


@require_http_methods(["GET", "POST"])
def delete_photo(request, reference):
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
    if submission.photo is None:
        return redirect("submission", submission.reference)
    if request.method == "POST":
        services.delete_photo_by_participant(submission)
        messages.info(request, "Dein Equipment-Foto und das Thumbnail sind gelöscht.")
        return redirect("submission", submission.reference)
    return _confirm(
        request,
        submission,
        title="Equipment-Foto löschen",
        question=(
            "Das Foto und das Thumbnail werden sofort und endgültig gelöscht. Damit widerrufst "
            "du deine Einwilligung zur Nutzung des Fotos."
        ),
        button="Ja, löschen",
    )


@require_http_methods(["GET"])
def photo(request, reference):
    """Das bereinigte Foto in voller Größe; es gibt es nur über die App, nie über S3-Links."""
    return _serve_photo(request, reference, thumbnail=False)


@require_http_methods(["GET"])
def photo_thumbnail(request, reference):
    return _serve_photo(request, reference, thumbnail=True)


def _serve_photo(request, reference, *, thumbnail):
    submission = _own_submission(request, reference)
    stored = submission.photo
    if stored is None:
        raise Http404
    key = stored.thumbnail_key if thumbnail else stored.key
    response = HttpResponse(get_storage().read(key), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET", "POST"])
def delete_submission(request, reference):
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
    if request.method == "POST":
        services.delete_submission(submission, by=Submission.DeletedBy.PARTICIPANT)
        messages.info(request, "Deine Submission wurde gelöscht.")
        return redirect("submission", submission.reference)
    return _confirm(
        request,
        submission,
        title="Submission löschen",
        question=(
            "Alle Master, Angaben und Einwilligungen dieser Submission werden endgültig "
            "gelöscht. Es bleibt nur die Submission-ID. Die Submission lässt sich nicht wieder "
            "öffnen."
        ),
        button="Ja, löschen",
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


@require_http_methods(["GET", "POST"])
def revoke_credit(request, reference):
    """Widerruf der Einwilligung zur Namensnennung, jederzeit (Ticket #68)."""
    submission = _own_submission(request, reference)
    consent = services.consent_revocable_by_participant(submission)
    if consent is None:
        return redirect("submission", submission.reference)
    if request.method == "POST":
        services.revoke(consent)
        messages.info(request, "Deine Einwilligung zur Namensnennung ist widerrufen.")
        return redirect("submission", submission.reference)
    return _confirm(
        request,
        submission,
        title="Namensnennung widerrufen",
        question=(
            "Deine Namensnennung wird gelöscht, die Submission ist danach anonym. Deine Master "
            "bleiben im Projekt."
        ),
        details=[f"Namensnennung: {submission.credit_name}"],
        button="Ja, widerrufen",
    )


@require_http_methods(["GET", "POST"])
def grant_credit(request, reference):
    """Namensnennung erlauben, erstmals oder nach einem Widerruf, bis zum Ende der Aktion
    (Ticket #69)."""
    submission = _own_submission(request, reference)
    if not services.changeable_by_participant(submission):
        return _not_changeable(request, submission)
    if submission.publishes_credit:
        return redirect("submission", submission.reference)
    form = CreditForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.grant_credit(submission, form.cleaned_data["credit_name"])
        except services.CreditNotAllowed:
            return _not_changeable(request, submission)
        messages.info(request, "Deine Einwilligung zur Namensnennung ist erteilt.")
        return redirect("submission", submission.reference)
    return render(
        request,
        "submissions/credit.html",
        {
            "submission": submission,
            "form": form,
            "privacy_version": settings.CONSENT_TEXT_VERSION,
        },
    )


def _own_submission(request, reference) -> Submission:
    if not access.may_access(request, reference):
        raise Http404
    return get_object_or_404(Submission, reference=reference)


def _not_changeable(request, submission):
    """Zurück zur Submission-Seite, wenn Teilnehmende nichts mehr ändern dürfen; sie erklärt die
    Löschung selbst, das Ende der Aktion sagt die Meldung."""
    if not submission.is_deleted:
        messages.info(
            request, "Die Aktion ist beendet. Deine Submission kannst du nicht mehr ändern."
        )
    return redirect("submission", submission.reference)


def _confirm(request, submission, *, title, question, button, details=()):
    """Rückfrage vor dem Löschen oder dem Widerruf; Abbrechen führt zurück zur Submission-Seite."""
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


def _held(request) -> list[Submission]:
    """Die Submissions dieses Browsers, die es noch gibt; gelöschte zählen nicht (ADR 0002)."""
    return [s for s in _own(request) if not s.is_deleted]


def legacy_redirect(request, rest):
    """Alte Adressen unter `abgabe/` (vor Issue #66) führen dauerhaft auf `submission/`,
    damit Lesezeichen und Links in Mails weiter funktionieren."""
    prefix = request.path.removesuffix("abgabe/" + rest)
    if rest.endswith("/zurueckziehen/"):
        rest = rest.removesuffix("zurueckziehen/") + "loeschen/"
    target = f"{prefix}submission/{rest}"
    if request.META.get("QUERY_STRING"):
        target += "?" + request.META["QUERY_STRING"]
    return HttpResponsePermanentRedirect(target)
