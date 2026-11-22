from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from submissions.models import Event
from submissions.netutil import client_ip_hash, one_hour_ago

from . import tickets
from .models import EntryAttempt
from .origin import origin_allowed


def friendly_refusal(request, event: Event | None, status: int = 403):
    """Freundliche Seite, die das Verfahren nicht erklärt."""
    url = event.entry_page_url if event else ""
    return render(
        request, "entry/bitte_ueber_projektseite.html", {"entry_page_url": url}, status=status
    )


@require_GET
@never_cache
def start(request, slug):
    """Einstieg: nur mit passendem Referer (Origin der Projektwebsite) gibt es ein Entry-Ticket."""
    ip_hash = client_ip_hash(request)
    recent = EntryAttempt.objects.filter(ip_hash=ip_hash, created_at__gte=one_hour_ago()).count()
    if recent >= settings.RATE_ENTRY_PER_HOUR:
        return render(request, "entry/zu_viele_anfragen.html", status=429)

    event = Event.objects.filter(slug=slug).first()
    allowed = bool(
        event
        and event.is_open()
        and origin_allowed(request.META.get("HTTP_REFERER", ""), event.entry_origins)
    )
    EntryAttempt.objects.create(event=event, accepted=allowed, ip_hash=ip_hash)
    if not allowed:
        return friendly_refusal(request, event)

    response = redirect("teilnahme", slug=event.slug)
    tickets.issue(response, event)
    return response
