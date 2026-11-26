"""Datenschutzhinweis, versioniert passend zu `CONSENT_TEXT_VERSION` (Ticket #34)."""

from pathlib import Path

import pytest
from admin_helper import ADMIN
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


def test_hinweis_nennt_standort_und_personendaten_im_dateikopf_der_master(client):
    page = client.get("/datenschutz/").content.decode()
    for keyword in ("SITELAT", "SITELONG", "OBSGEO", "OBSERVER"):
        assert keyword in page
    assert "unverändert" in page  # ADR 0003: Schwarmstack entfernt nichts
    assert "30 Tage" in page  # gelten bis zur Löschfrist, und danach bei den Betreibern (ADR 0008)


def test_fruehere_fassung_bleibt_unveraendert_erreichbar(client, settings):
    assert settings.CONSENT_TEXT_VERSION != "2026-11-25"
    alt = client.get("/datenschutz/2026-11-25/")
    assert alt.status_code == 200
    assert "SITELAT" not in alt.content.decode()
    assert "nicht mehr aktuell" in alt.content.decode()


def test_upload_seite_erklaert_vor_dem_upload_wie_standortdaten_entfernt_werden(
    client, reference, settings
):
    page = client.get(f"/submission/{reference}/").content.decode()
    hinweis = page[page.index('id="header-hinweis"') :]
    for text in ("SITELAT", "SITELONG", "OBSGEO", "OBSERVER", "Siril", "PixInsight", "NINA"):
        assert text in hinweis
    assert "unverändert" in hinweis  # wir ändern die Dateien nicht
    assert f'href="/datenschutz/{settings.CONSENT_TEXT_VERSION}/"' in hinweis


# --- Verantwortliche Stelle und Hoster aus der Umgebung (#101, ADR 0011) ---

GOLDEN = Path(__file__).parent / "golden"
DZVF = {
    "OPERATOR_NAME": "der DZVF",
    "OPERATOR_BEI": "beim DZVF",
    "HOSTER_NAME": "die Hetzner Online GmbH",
    "HOSTER_BEI": "bei der Hetzner Online GmbH",
}


@pytest.mark.parametrize("version", ["2026-11-25", "2026-11-25-2"])
def test_wortlaut_fuer_die_dzvf_bleibt_zeichengenau_wie_vorher(client, settings, version):
    """Ändert sich dieser Text, wechselt die Fassung, und alle müssten neu einwilligen."""
    settings.PRIVACY_CONTACT = "datenschutz@example.org"
    for name, value in DZVF.items():
        setattr(settings, name, value)
    page = client.get(f"/datenschutz/{version}/").content
    assert page == (GOLDEN / f"datenschutz-{version}.html").read_bytes()


def test_andere_betreiber_erscheinen_im_hinweis_und_werden_maskiert(client, settings):
    settings.OPERATOR_NAME = "der Verein <b>Sternfreunde</b>"
    settings.OPERATOR_BEI = "beim Verein Sternfreunde"
    settings.HOSTER_BEI = "bei der Beispiel AG"
    page = client.get("/datenschutz/").content.decode()
    assert "Verantwortlich ist der Verein &lt;b&gt;Sternfreunde&lt;/b&gt;, der" in page
    assert "Projekts beim Verein Sternfreunde." in page
    assert "läuft bei der Beispiel AG (" in page
    assert "DZVF" not in page
    assert "Hetzner" not in page


@pytest.mark.parametrize(
    "name",
    [
        "OPERATOR_NAME",
        "OPERATOR_BEI",
        "OPERATOR_ADDRESS",
        "HOSTER_NAME",
        "HOSTER_BEI",
        "HOSTER_ADDRESS",
    ],
)
def test_fehlt_eine_angabe_erscheint_kein_hinweis_mit_leeren_stellen(client, settings, name):
    setattr(settings, name, "  ")
    for url in ("/datenschutz/", f"/datenschutz/{settings.CONSENT_TEXT_VERSION}/"):
        response = client.get(url)
        assert response.status_code == 503
        assert "noch nicht vollständig" in response.content.decode()
        assert "Verantwortlich ist" not in response.content.decode()


def test_admin_warnt_wenn_angaben_fehlen(operator_client, settings):
    settings.HOSTER_ADDRESS = ""
    page = operator_client.get(ADMIN).content.decode()
    assert "Dem Datenschutzhinweis fehlen Angaben (HOSTER_ADDRESS)" in page


def test_admin_warnt_nicht_wenn_alles_gesetzt_ist(operator_client, settings):
    page = operator_client.get(ADMIN).content.decode()
    assert "Datenschutzhinweis fehlen" not in page


def test_fehlende_angaben_sind_in_produktion_eine_warnung_beim_start(settings, capsys):
    settings.DEBUG = False
    settings.OPERATOR_ADDRESS = ""
    call_command("check")  # Warnung, kein Fehler: der Deploy bricht nicht ab
    assert "submissions.W001" in capsys.readouterr().err
