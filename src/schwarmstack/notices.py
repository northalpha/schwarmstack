"""Betriebsmeldungen per Mail an die Betreiber (ADR 0007).

Meldungen enthalten keine Angaben von Teilnehmenden, höchstens die Submission-ID.
"""

import logging
import smtplib

from django.conf import settings
from django.core.mail import send_mail

log = logging.getLogger(__name__)


def send(subject: str, body: str) -> bool:
    """Schickt eine Betriebsmeldung an `OPERATOR_EMAILS`; gibt zurück, ob sie rausging.

    Ein Fehler beim Versand bricht den Vorgang, den die Meldung beschreibt, nicht ab: Er steht
    im Log, und der Aufrufer entscheidet, ob er es später noch einmal versucht.
    """
    recipients = settings.OPERATOR_EMAILS
    if not recipients:
        log.warning("Betriebsmeldung ohne Empfänger (OPERATOR_EMAILS leer): %s", subject)
        return False
    try:
        send_mail(f"[Schwarmstack] {subject}", body, None, recipients)
    except (smtplib.SMTPException, OSError):
        log.exception("Betriebsmeldung nicht verschickt: %s", subject)
        return False
    return True
