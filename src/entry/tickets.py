"""Entry-Ticket: kurzlebiges, signiertes Cookie, das den Weg über die Projektwebsite belegt."""

from django.conf import settings
from django.core import signing

SALT = "schwarmstack.entry-ticket"


def issue(response, event) -> None:
    value = signing.dumps({"event": event.pk}, salt=SALT)
    response.set_cookie(
        settings.ENTRY_TICKET_COOKIE,
        value,
        max_age=settings.ENTRY_TICKET_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


def valid_for(request, event) -> bool:
    value = request.COOKIES.get(settings.ENTRY_TICKET_COOKIE)
    if not value:
        return False
    try:
        data = signing.loads(value, salt=SALT, max_age=settings.ENTRY_TICKET_MAX_AGE)
    except signing.BadSignature:  # auch SignatureExpired
        return False
    return data.get("event") == event.pk


def clear(response) -> None:
    response.delete_cookie(settings.ENTRY_TICKET_COOKIE, samesite="Lax")
