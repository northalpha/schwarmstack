from django.conf import settings
from django.db import IntegrityError, transaction

from . import references
from .models import Consent, Submission

_ATTEMPTS = 5


def create_submission(*, credit_name, setup_description, publish_credit) -> Submission:
    """Legt eine Abgabe samt Einwilligungen an und vergibt eine freie Abgabe-Kennung."""
    kinds = [Consent.Kind.PROJECT_USE]
    if publish_credit:
        kinds.append(Consent.Kind.PUBLISH_CREDIT)
    for _ in range(_ATTEMPTS):
        reference = references.new_reference(
            lambda r: Submission.objects.filter(reference=r).exists()
        )
        try:
            with transaction.atomic():
                submission = Submission.objects.create(
                    reference=reference,
                    credit_name=credit_name,
                    setup_description=setup_description,
                )
                Consent.objects.bulk_create(
                    Consent(
                        submission=submission,
                        kind=kind,
                        text_version=settings.CONSENT_TEXT_VERSION,
                    )
                    for kind in kinds
                )
            return submission
        except IntegrityError:  # gleichzeitig dieselbe Kennung gezogen
            continue
    raise RuntimeError("Abgabe konnte nicht angelegt werden")
