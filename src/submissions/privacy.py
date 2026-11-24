"""Datenschutzhinweis: eine Vorlage je Fassung, passend zu `CONSENT_TEXT_VERSION` (Ticket #34).

Jede Einwilligung speichert die Fassung, die die Person gesehen hat; alte Fassungen bleiben unter
ihrer eigenen Adresse erreichbar.
"""

import re

from django.conf import settings
from django.core import checks
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def template_name(version: str) -> str | None:
    """Vorlage für diese Fassung, oder None, wenn es sie nicht gibt."""
    if not _VERSION.match(version) or ".." in version:
        return None
    name = f"submissions/datenschutz/{version}.html"
    try:
        get_template(name)
    except TemplateDoesNotExist:
        return None
    return name


@checks.register()
def check_privacy_notice(app_configs, **kwargs):
    errors = []
    if template_name(settings.CONSENT_TEXT_VERSION) is None:
        errors.append(
            checks.Error(
                "Kein Datenschutzhinweis für "
                f"CONSENT_TEXT_VERSION={settings.CONSENT_TEXT_VERSION!r}",
                hint="Vorlage submissions/datenschutz/<Fassung>.html anlegen.",
                id="submissions.E001",
            )
        )
    if not settings.DEBUG and not settings.PRIVACY_CONTACT:
        errors.append(
            checks.Error(
                "PRIVACY_CONTACT ist nicht gesetzt; der Datenschutzhinweis braucht eine "
                "Kontaktadresse für Widerruf und Rückzug.",
                id="submissions.E002",
            )
        )
    return errors
