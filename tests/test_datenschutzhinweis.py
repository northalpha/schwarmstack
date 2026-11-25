"""Datenschutzhinweis, versioniert passend zu `CONSENT_TEXT_VERSION` (Ticket #34)."""

import pytest
from django.core.management import call_command
from django.core.management.base import SystemCheckError

from submissions.models import Consent

pytestmark = pytest.mark.django_db


def test_hinweis_nennt_verantwortlichen_fristen_und_kontakt(client, settings):
    settings.PRIVACY_CONTACT = "datenschutz@example.org"
    response = client.get("/datenschutz/")
    assert response.status_code == 200
    page = response.content.decode()
    assert "DZVF" in page
    assert "Hetzner" in page
    assert "30 Tage" in page  # Löschfrist
    assert "14 Tage" in page  # Sicherungen
    assert "7 Tage" in page  # Logs
    assert "datenschutz@example.org" in page
    assert settings.CONSENT_TEXT_VERSION in page


def test_jede_fassung_hat_eine_eigene_adresse(client, settings):
    response = client.get(f"/datenschutz/{settings.CONSENT_TEXT_VERSION}/")
    assert response.status_code == 200
    assert client.get("/datenschutz/1999-01/").status_code == 404
    assert client.get("/datenschutz/..%2Fbase/").status_code == 404


def test_formular_verlinkt_den_hinweis_in_der_aktuellen_fassung(client, campaign, settings):
    page = client.get("/").content.decode()
    assert f'href="/datenschutz/{settings.CONSENT_TEXT_VERSION}/"' in page


def test_einwilligung_zeigt_auf_die_fassung_die_die_person_gesehen_hat(
    client, campaign, valid_form, settings
):
    client.post("/", valid_form)
    versions = set(Consent.objects.values_list("text_version", flat=True))
    assert versions == {settings.CONSENT_TEXT_VERSION}
    assert client.get(f"/datenschutz/{versions.pop()}/").status_code == 200


def test_ohne_hinweis_fuer_die_fassung_startet_nichts(settings):
    settings.CONSENT_TEXT_VERSION = "2099-01"
    with pytest.raises(SystemCheckError, match="Datenschutzhinweis"):
        call_command("check")


def test_in_produktion_braucht_der_hinweis_einen_kontakt(settings):
    settings.DEBUG = False
    settings.PRIVACY_CONTACT = ""
    with pytest.raises(SystemCheckError, match="PRIVACY_CONTACT"):
        call_command("check")
