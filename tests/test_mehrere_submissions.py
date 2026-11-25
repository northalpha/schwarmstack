"""Mehrere Submissions je Browser und Zeitfenster beim Anlegen (Ticket #10)."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from submissions.models import Submission

pytestmark = pytest.mark.django_db

NEW = "/neu/"


def create(client, data, url=NEW):
    return client.post(url, data)


def test_zweite_submission_im_selben_browser(client, campaign, valid_form):
    first = create(client, valid_form, "/")["Location"]
    second = create(client, dict(valid_form, setup_description="Zweites Setup"))["Location"]
    assert first != second
    assert Submission.objects.count() == 2
    assert client.get(first).status_code == 200
    assert client.get(second).status_code == 200


def test_submission_seite_bietet_wechsel_und_neue_submission(client, campaign, valid_form):
    first = create(client, valid_form, "/")["Location"]
    second = create(client, valid_form)["Location"]
    content = client.get(second).content.decode()
    assert f'href="{first}"' in content
    assert f'href="{NEW}"' in content


def test_hoechstens_drei_submissions_je_browser(client, campaign, valid_form):
    for _ in range(3):
        assert create(client, valid_form).status_code == 302
    response = create(client, valid_form)
    assert Submission.objects.count() == 3
    assert response.status_code == 200
    content = response.content.decode()
    assert "höchstens 3 Submissions" in content
    assert 'name="credit_name"' not in content


def test_bei_drei_submissions_kein_formular_und_kein_link(client, campaign, valid_form):
    for _ in range(3):
        location = create(client, valid_form)["Location"]
    assert 'name="credit_name"' not in client.get(NEW).content.decode()
    assert f'href="{NEW}"' not in client.get(location).content.decode()


def test_grenze_gilt_je_browser(campaign, valid_form):
    a, b = Client(), Client()
    for _ in range(3):
        create(a, valid_form)
    assert create(b, valid_form).status_code == 302


def test_cookie_enthaelt_nur_eigene_submissions(campaign, valid_form):
    a, b = Client(), Client()
    location_a = create(a, valid_form)["Location"]
    create(b, valid_form)
    assert b.get(location_a).status_code == 404


def _shift(campaign, **kwargs):
    for field, value in kwargs.items():
        setattr(campaign, field, value)
    campaign.save()


def test_vor_dem_beginn_hinweis_statt_formular(client, campaign):
    _shift(campaign, starts_at=timezone.now() + timedelta(days=2))
    response = client.get("/")
    content = response.content.decode()
    assert 'name="credit_name"' not in content
    assert "beginnt am" in content


def test_vor_dem_beginn_kein_anlegen(client, campaign, valid_form):
    _shift(campaign, starts_at=timezone.now() + timedelta(days=2))
    create(client, valid_form, "/")
    create(client, valid_form)
    assert Submission.objects.count() == 0


@pytest.mark.parametrize("since", [timedelta(minutes=1), timedelta(days=3)])
def test_nach_dem_ende_keine_neue_submission(client, campaign, valid_form, since):
    _shift(campaign, ends_at=timezone.now() - since)
    response = create(client, valid_form, "/")
    assert Submission.objects.count() == 0
    content = response.content.decode()
    assert 'name="credit_name"' not in content
    assert "beendet" in content


def test_nach_dem_ende_bleibt_submission_sichtbar(client, campaign, valid_form):
    location = create(client, valid_form, "/")["Location"]
    _shift(campaign, ends_at=timezone.now() - timedelta(days=3))
    response = client.get(location)
    assert response.status_code == 200
    assert f'href="{NEW}"' not in response.content.decode()
    assert client.get("/")["Location"] == location


def test_neu_ohne_aktion(client, db):
    assert client.get(NEW).status_code == 503


def test_neu_url_ist_benannt():
    assert reverse("new_submission") == NEW


def test_geloeschte_submissions_belegen_keinen_platz(client, campaign, valid_form):
    locations = [create(client, valid_form)["Location"] for _ in range(3)]
    assert create(client, valid_form).status_code == 200
    assert client.post(f"{locations[0]}loeschen/").status_code == 302
    assert 'name="credit_name"' in client.get(NEW).content.decode()
    assert create(client, valid_form).status_code == 302


def test_einstieg_fuehrt_nicht_zu_einer_geloeschten_submission(client, campaign, valid_form):
    location = create(client, valid_form)["Location"]
    client.post(f"{location}loeschen/")
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="credit_name"' in response.content.decode()
