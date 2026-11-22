"""ALTCHA (selbst gehostete Proof-of-Work-Prüfung): Aufgabe erzeugen und Lösung prüfen.

Protokoll "PoW v2" (Widget 3.x, Python-Bibliothek altcha 2.x). Die Aufgabe ist mit einem
HMAC signiert (ALTCHA_HMAC_SECRET), läuft nach ALTCHA_EXPIRY_SECONDS ab und gilt nur einmal.
"""

import datetime
import logging

from altcha import Payload, create_challenge, verify_solution
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import UsedChallenge

logger = logging.getLogger(__name__)


def new_challenge() -> dict:
    expires = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        seconds=settings.ALTCHA_EXPIRY_SECONDS
    )
    challenge = create_challenge(
        algorithm=settings.ALTCHA_ALGORITHM,
        cost=settings.ALTCHA_COST,
        expires_at=expires,
        hmac_secret=settings.ALTCHA_HMAC_SECRET,
    )
    return challenge.to_dict()


def verify_payload(payload: str | None) -> bool:
    """True nur bei gültiger, nicht abgelaufener und noch nicht benutzter Lösung."""
    if not payload:
        return False
    try:
        result = verify_solution(payload, settings.ALTCHA_HMAC_SECRET)
        if not result.verified:
            return False
        signature = Payload.from_base64(payload).challenge.signature
    except Exception:  # noqa: BLE001 - jede kaputte Eingabe heißt "nicht verifiziert"
        logger.info("ALTCHA-Payload nicht lesbar", exc_info=True)
        return False
    if not signature:
        return False
    try:
        with transaction.atomic():
            UsedChallenge.objects.create(signature=signature)
    except IntegrityError:
        return False  # schon benutzt
    return True


def purge_old(max_age_hours: int = 24) -> int:
    """Alte Einträge löschen; abgelaufene Aufgaben sind ohnehin nicht mehr gültig."""
    cutoff = timezone.now() - datetime.timedelta(hours=max_age_hours)
    return UsedChallenge.objects.filter(used_at__lt=cutoff).delete()[0]
