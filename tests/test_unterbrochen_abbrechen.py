"""Unterbrochene Uploads auf der Abgabeseite abbrechen (Ticket #39)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from uploads_helper import start

pytestmark = pytest.mark.django_db


def page(client, reference):
    return client.get(f"/abgabe/{reference}/").content.decode()


def abort_url(reference, master_id):
    return f"/abgabe/{reference}/master/{master_id}/abbrechen/"


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
