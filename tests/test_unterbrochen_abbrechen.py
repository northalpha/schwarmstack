"""Unterbrochene Uploads auf der Submission-Seite abbrechen (Ticket #39)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from files import fits
from uploads_helper import start, upload

pytestmark = pytest.mark.django_db


def page(client, reference):
    return client.get(f"/submission/{reference}/").content.decode()


def abort_url(reference, master_id):
    return f"/submission/{reference}/master/{master_id}/abbrechen/"


def test_unterbrochener_upload_ohne_upload_id_hat_bedienelement_zum_abbrechen(client, reference):
    master_id = start(client, reference, size=10).json()["masterId"]
    assert f'data-abort-url="{abort_url(reference, master_id)}"' in page(client, reference)


def test_nach_der_nachfrist_kein_bedienelement_zum_abbrechen(client, reference, campaign):
    start(client, reference, size=10)
    campaign.ends_at = timezone.now() - timedelta(days=1)
    campaign.save()
    content = page(client, reference)
    assert "data-abort-url=" not in content
    assert "unterbrochen" not in content


def test_abbrechen_meldet_die_neue_belegung(client, reference, campaign):
    campaign.quota = 1000
    campaign.save()
    start(client, reference, size=100)
    master_id = start(client, reference, size=400).json()["masterId"]
    usage = client.post(abort_url(reference, master_id)).json()["usage"]
    assert usage == {"label": "Belegt: 100\xa0Bytes von 1000\xa0Bytes", "percent": 10}


def abort_form(client, reference, master_id):
    """Wie das Formular im Browser ohne JavaScript."""
    return client.post(
        abort_url(reference, master_id),
        "csrfmiddlewaretoken=egal",
        content_type="application/x-www-form-urlencoded",
        follow=True,
    )


def test_abbrechen_ohne_javascript_fuehrt_zurueck_zur_submission_seite(client, reference):
    master_id = start(client, reference, size=10).json()["masterId"]
    response = abort_form(client, reference, master_id)
    assert response.redirect_chain == [(f"/submission/{reference}/", 302)]
    content = response.content.decode()
    assert "Upload von m101_L.fits abgebrochen" in content
    assert "unterbrochen" not in content


def test_bedienelement_zum_abbrechen_geht_ohne_javascript(client, reference):
    master_id = start(client, reference, size=10).json()["masterId"]
    content = page(client, reference)
    assert f'<form method="post" action="{abort_url(reference, master_id)}"' in content


def test_abbrechen_ohne_javascript_zeigt_den_grund_einer_ablehnung(client, reference):
    # Seite veraltet: Der Master ist inzwischen fertig.
    master_id = upload(client, reference, fits()).json()["masterId"]
    response = abort_form(client, reference, master_id)
    assert response.redirect_chain == [(f"/submission/{reference}/", 302)]
    assert "Dieser Master ist schon abgeschlossen." in response.content.decode()


def test_upload_mit_frischer_aktivitaet_laeuft_vielleicht_noch(client, reference):
    start(client, reference, size=10)
    content = page(client, reference)
    assert "läuft gerade oder wurde eben unterbrochen" in content
    assert "data-confirm=" in content  # Abbrechen fragt nach


def test_upload_ohne_aktivitaet_seit_minuten_ist_unterbrochen(client, reference):
    start(client, reference, size=10)
    later = timezone.now() + timedelta(minutes=6)
    with mock.patch("django.utils.timezone.now", return_value=later):
        content = page(client, reference)
    assert "läuft gerade" not in content
    assert "unterbrochen" in content
    assert "data-confirm=" not in content


def test_master_im_upload_wird_abgebrochen_nicht_geloescht(client, reference):
    # Abbrechen geht auch in der Nachfrist, Löschen nicht (Ticket #30); eins genügt.
    master_id = start(client, reference, size=10).json()["masterId"]
    content = page(client, reference)
    assert f'data-abort-url="{abort_url(reference, master_id)}"' in content
    assert f"/master/{master_id}/loeschen/" not in content
