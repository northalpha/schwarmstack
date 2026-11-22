from django.db import transaction
from django.utils import timezone

from submissions.models import Stack

from .models import PackJob


@transaction.atomic
def enqueue_pack(stack: Stack) -> PackJob:
    """Stack zur Verarbeitung vormerken (abschließen oder neu packen).

    Es gibt höchstens einen Packauftrag je Stack.
    """
    stack.state = Stack.QUEUED
    stack.closed_at = stack.closed_at or timezone.now()
    stack.error_message = ""
    stack.save(update_fields=["state", "closed_at", "error_message"])
    job, _ = PackJob.objects.update_or_create(
        stack=stack,
        kind=PackJob.PACK,
        defaults={"state": PackJob.QUEUED, "attempts": 0, "locked_at": None, "locked_by": ""},
    )
    return job
