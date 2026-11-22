"""Kleine Hilfen zum Anlegen von Testdaten."""

from submissions.models import Event, Stack, Submission
from submissions.tokens import hash_token
from uploads.models import UploadedFile

GIB = 1024**3


def make_event(**kwargs) -> Event:
    defaults = {"slug": "demo", "title": "Demo"}
    return Event.objects.create(**{**defaults, **kwargs})


def make_submission(event: Event | None = None, **kwargs) -> Submission:
    event = event or make_event()
    n = Submission.objects.count()
    defaults = {"display_name": f"Person {n}", "token_hash": hash_token(f"token-{n}")}
    return Submission.objects.create(event=event, **{**defaults, **kwargs})


def make_stack(submission: Submission | None = None, **kwargs) -> Stack:
    submission = submission or make_submission()
    defaults = {"object_name": "M31", "telescope": "Refraktor", "camera": "Kamera"}
    return Stack.objects.create(submission=submission, **{**defaults, **kwargs})


def make_file(stack: Stack, size: int, state: str = UploadedFile.VALID, name: str = "a.fits"):
    return UploadedFile.objects.create(
        stack=stack, filename=name, size_bytes=size, state=state, format="fits"
    )
