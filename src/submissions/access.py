"""Zugang zur eigenen Abgabe über den persönlichen Link (Cookie mit dem Token)."""

import datetime
import functools

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

from .models import Submission
from .tokens import hash_token


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        settings.SUBMISSION_COOKIE,
        token,
        max_age=settings.SUBMISSION_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


def find_submission(token: str | None) -> Submission | None:
    if not token:
        return None
    # Zugriff über den Hash des Tokens; der Klartext wird nie gespeichert
    return Submission.objects.select_related("event").filter(token_hash=hash_token(token)).first()


def touch(submission: Submission) -> None:
    """last_seen_at höchstens einmal pro Minute schreiben (SQLite schont es)."""
    now = timezone.now()
    if not submission.last_seen_at or now - submission.last_seen_at > datetime.timedelta(minutes=1):
        Submission.objects.filter(pk=submission.pk).update(last_seen_at=now)


def require_submission(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        submission = find_submission(request.COOKIES.get(settings.SUBMISSION_COOKIE))
        if submission is None:
            return render(request, "submissions/link_ungueltig.html", status=403)
        touch(submission)
        request.submission = submission
        return view(request, *args, **kwargs)

    return wrapper
