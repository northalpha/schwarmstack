"""Quote, Gesamtgrenze und Zulässigkeit eines neuen Uploads (für den tusd-pre-create-Hook)."""

from django.db.models import Sum

from uploads.models import UploadedFile

from .models import Event, Stack, Submission


def used_bytes_submission(submission: Submission) -> int:
    total = UploadedFile.objects.filter(
        stack__submission=submission, state__in=UploadedFile.COUNTED_STATES
    ).aggregate(total=Sum("size_bytes"))["total"]
    return total or 0


def used_bytes_event(event: Event) -> int:
    total = UploadedFile.objects.filter(
        stack__submission__event=event, state__in=UploadedFile.COUNTED_STATES
    ).aggregate(total=Sum("size_bytes"))["total"]
    return total or 0


def refusal_reason(stack: Stack, size: int, now=None) -> str | None:
    """Kurze deutsche Meldung, warum ein Upload dieser Größe abgelehnt wird, sonst None."""
    submission = stack.submission
    event = submission.event
    if submission.is_blocked:
        return "Diese Abgabe ist gesperrt."
    if not event.is_open(now):
        return "Das Event ist geschlossen."
    if stack.state != Stack.OPEN:
        return "Dieser Stack ist abgeschlossen."
    if size <= 0:
        return "Die Dateigröße ist unbekannt."
    if size > event.max_file_bytes:
        return "Die Datei ist zu groß."
    if used_bytes_submission(submission) + size > event.quota_bytes_per_submission:
        return "Deine Quote ist ausgeschöpft."
    if used_bytes_event(event) + size > event.global_cap_bytes:
        return "Die Gesamtkapazität des Events ist erreicht."
    return None
