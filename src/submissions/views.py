from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from entry import tickets
from entry.views import friendly_refusal

from . import access
from .forms import PREFILL_FIELDS, ExposureFormSet, ParticipationForm, StackForm
from .models import Event, Stack, Submission
from .netutil import client_ip_hash, one_hour_ago
from .quota import used_bytes_submission
from .services import create_submission


@require_http_methods(["GET", "POST"])
@never_cache
def teilnahme(request, slug):
    """Teilnahmeformular. Ohne gültiges Entry-Ticket (Weg über die Projektwebsite) gibt es keins."""
    event = Event.objects.filter(slug=slug).first()
    if event is None or not event.is_open() or not tickets.valid_for(request, event):
        return friendly_refusal(request, event)

    ip_hash = client_ip_hash(request)
    if request.method == "POST":
        recent = Submission.objects.filter(ip_hash=ip_hash, created_at__gte=one_hour_ago()).count()
        if recent >= settings.RATE_SUBMISSIONS_PER_HOUR:
            return render(request, "entry/zu_viele_anfragen.html", status=429)
        form = ParticipationForm(request.POST, altcha_enabled=event.altcha_enabled)
        if form.is_valid():
            submission, token = create_submission(event, form.cleaned_data, form.links, ip_hash)
            link = request.build_absolute_uri(reverse("abgabe_link", args=[token]))
            response = render(
                request,
                "submissions/abgabe_angelegt.html",
                {"submission": submission, "personal_link": link},
            )
            access.set_cookie(response, token)
            tickets.clear(response)  # ein Ticket, eine Abgabe
            return response
    else:
        form = ParticipationForm(altcha_enabled=event.altcha_enabled)
    return render(request, "submissions/teilnahme.html", {"event": event, "form": form})


@require_GET
@never_cache
def abgabe_link(request, token):
    """Persönlicher Abgabe-Link: setzt das Cookie neu (auch ohne Umweg über die Projektseite)."""
    submission = access.find_submission(token)
    if submission is None:
        return render(request, "submissions/link_ungueltig.html", status=403)
    response = redirect("abgabe")
    access.set_cookie(response, token)
    return response


def _initial_from_last_stack(submission):
    last = submission.stacks.order_by("-created_at").first()
    return {name: getattr(last, name) for name in PREFILL_FIELDS} if last else {}


@require_http_methods(["GET", "POST"])
@never_cache
@access.require_submission
def abgabe(request):
    """Abgabeseite: Quote, bisherige Stacks und das Formular für einen neuen Stack."""
    submission = request.submission
    event = submission.event
    can_add = not submission.is_blocked and event.is_open()
    stack_form = formset = None
    if can_add:
        if request.method == "POST":
            stack_form = StackForm(request.POST)
            formset = ExposureFormSet(request.POST, instance=Stack())
            if stack_form.is_valid() and formset.is_valid():
                with transaction.atomic():
                    stack = stack_form.save(commit=False)
                    stack.submission = submission
                    stack.save()
                    formset.instance = stack
                    formset.save()
                return redirect("abgabe")
        else:
            stack_form = StackForm(initial=_initial_from_last_stack(submission))
            formset = ExposureFormSet(instance=Stack())
    used = used_bytes_submission(submission)
    quota = event.quota_bytes_per_submission
    context = {
        "submission": submission,
        "event": event,
        "can_add": can_add,
        "stack_form": stack_form,
        "formset": formset,
        "stacks": submission.stacks.prefetch_related("exposure_lines", "files").order_by(
            "-created_at"
        ),
        "used_bytes": used,
        "quota_bytes": quota,
        "quota_percent": min(100, round(used * 100 / quota)) if quota else 0,
    }
    return render(request, "submissions/abgabe.html", context)
