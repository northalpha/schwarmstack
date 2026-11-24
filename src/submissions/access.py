"""Zugang zur Submission nur aus dem Browser, in dem sie angelegt wurde (ADR 0002).

Das Cookie ist signiert und enthält die Submission-IDs dieses Browsers.
"""

from django.conf import settings
from django.utils import timezone

# Name bleibt trotz Umbenennung (Issue #66): Ein neuer Name sperrte Teilnehmende aus ihren
# bestehenden Submissions aus, denn ohne das Cookie gibt es keinen Zugang.
COOKIE_NAME = "schwarmstack_abgaben"
_SALT = "submissions.access"
# Ein Browser kann höchstens so viele Submissions halten (ADR 0002).
MAX_PER_BROWSER = 3
# Puffer über Ende der Aktion plus Nachfrist hinaus, damit die Submission danach noch ansehbar ist.
_EXTRA = 30 * 86400


def references(request) -> list[str]:
    value = request.get_signed_cookie(COOKIE_NAME, default=None, salt=_SALT)
    if not value:
        return []
    return [r for r in value.split(",") if r]


def grant(response, request, reference: str, campaign) -> None:
    refs = references(request)
    if reference not in refs:
        refs.append(reference)
    until = campaign.closes_at
    max_age = max(int((until - timezone.now()).total_seconds()), 0) + _EXTRA
    response.set_signed_cookie(
        COOKIE_NAME,
        ",".join(refs),
        salt=_SALT,
        max_age=max_age,
        httponly=True,
        secure=settings.SUBMISSION_COOKIE_SECURE,
        samesite="Lax",
    )


def has_room(request) -> bool:
    return len(references(request)) < MAX_PER_BROWSER


def may_access(request, reference: str) -> bool:
    return reference in references(request)
