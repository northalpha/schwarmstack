"""Datenschutzhinweis: eine Vorlage je Fassung, passend zu `CONSENT_TEXT_VERSION` (Ticket #34).

Jede Einwilligung speichert die Fassung, die die Person gesehen hat; alte Fassungen bleiben unter
ihrer eigenen Adresse erreichbar.
"""

import re

from django.conf import settings
from django.core import checks
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

# Einstellung -> Schlüssel im Kontext der Vorlagen. Adressen stehen im heutigen Wortlaut nicht;
# sie sind trotzdem Pflicht, damit spätere Fassungen sie nennen können.
_DETAILS = {
    "PRIVACY_CONTACT": "contact",
    "OPERATOR_NAME": "operator_name",
    "OPERATOR_BEI": "operator_bei",
    "OPERATOR_ADDRESS": "operator_address",
    "HOSTER_NAME": "hoster_name",
    "HOSTER_BEI": "hoster_bei",
    "HOSTER_ADDRESS": "hoster_address",
}

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


def missing_details() -> list[str]:
    """Einstellungen, die dem Datenschutzhinweis noch fehlen."""
    return [name for name in _DETAILS if not getattr(settings, name, "").strip()]


def context() -> dict[str, str]:
    """Angaben für die Vorlagen; fehlt eine, ist `missing_details()` nicht leer."""
    return {key: getattr(settings, name, "").strip() for name, key in _DETAILS.items()}


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
                "Kontaktadresse für Widerruf und Löschung.",
                id="submissions.E002",
            )
        )
    missing = [name for name in missing_details() if name != "PRIVACY_CONTACT"]
    if missing and not settings.DEBUG:
        errors.append(
            checks.Warning(
                f"Dem Datenschutzhinweis fehlen Angaben: {', '.join(missing)}. Er erscheint erst, "
                "wenn sie gesetzt sind.",
                hint="Siehe docs/betrieb/deployment.md.",
                id="submissions.W001",
            )
        )
    return errors
