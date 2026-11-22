from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Consent, Event, SocialLink, Submission
from .tokens import hash_token, new_token

CONSENT_FIELDS = (
    Consent.PRIVACY_READ,
    Consent.PROJECT_USE,
    Consent.PUBLISH_NAME_LINKS,
    Consent.PUBLISH_EQUIPMENT_PHOTO,
    Consent.STATUS_MAILS,
)


@transaction.atomic
def create_submission(event: Event, cleaned: dict, links: list[str], ip_hash: str):
    """Legt Abgabe, Links und Einwilligungen an. Gibt (Abgabe, Klartext-Token) zurück.

    Der Token wird nur hier und einmalig angezeigt; gespeichert wird nur sein Hash.
    """
    token = new_token()
    submission = Submission.objects.create(
        event=event,
        display_name=cleaned["display_name"],
        email=cleaned.get("email", ""),
        region=cleaned.get("region", ""),
        bortle=cleaned.get("bortle"),
        token_hash=hash_token(token),
        ip_hash=ip_hash,
    )
    for url in links:
        SocialLink.objects.create(submission=submission, url=url)
    now = timezone.now()
    for kind in CONSENT_FIELDS:
        granted = bool(cleaned.get(kind))
        Consent.objects.create(
            submission=submission,
            kind=kind,
            granted=granted,
            granted_at=now if granted else None,
            text_version=settings.CONSENT_TEXT_VERSION,
        )
    return submission, token
