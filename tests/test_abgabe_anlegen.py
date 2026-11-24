"""Abgabe anlegen über den HTTP-Seam (Ticket #9)."""

import re

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from submissions.models import Consent, Submission
from submissions.references import ALPHABET

pytestmark = pytest.mark.django_db

ENTRY = "/"


def create(client, data):
    return client.post(ENTRY, data)


def test_formular_wird_angezeigt(client, campaign):
    response = client.get(ENTRY)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="credit_name"' in content
    assert 'name="consent_project_use"' in content
    assert 'name="consent_publish_credit"' in content
    assert 'name="setup_description"' in content
    assert "M 101" in content


def test_abgabe_anlegen_zeigt_kennung(client, campaign, valid_form):
    response = create(client, valid_form)
    submission = Submission.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse("submission", args=[submission.reference])

    page = client.get(response["Location"])
    assert page.status_code == 200
    assert submission.reference in page.content.decode()
    assert submission.credit_name == "Ada Sternguck"
    assert submission.setup_description == "RedCat 51, ASI2600MM"


def test_kennung_hat_das_vereinbarte_format(client, campaign, valid_form):
    create(client, valid_form)
    reference = Submission.objects.get().reference
    assert re.fullmatch(r"SW-[" + ALPHABET + "]{4}", reference)
    assert not set("0O1IL") & set(ALPHABET)


def test_kennung_wird_bei_kollision_neu_gezogen(campaign, valid_form, monkeypatch):
    from submissions import references

    draws = iter(["AAAA", "AAAA", "BBBB"])
    monkeypatch.setattr(references, "_draw", lambda: next(draws))
    create(Client(), valid_form)
    create(Client(), valid_form)
    assert sorted(Submission.objects.values_list("reference", flat=True)) == [
        "SW-AAAA",
        "SW-BBBB",
    ]


@pytest.mark.parametrize("missing", ["credit_name", "consent_project_use"])
def test_pflichtangaben_fehlen(client, campaign, valid_form, missing):
    data = dict(valid_form)
    del data[missing]
    response = create(client, data)
    assert response.status_code == 200
    assert Submission.objects.count() == 0
    content = response.content.decode()
    assert "Pflichtangabe" in content or "Bitte" in content
    # übrige Eingaben bleiben erhalten
    if missing != "credit_name":
        assert 'value="Ada Sternguck"' in content
    assert "RedCat 51, ASI2600MM" in content


def test_einwilligungen_werden_einzeln_gespeichert(client, campaign, valid_form):
    create(client, valid_form)
    consents = {c.kind: c for c in Consent.objects.all()}
    assert set(consents) == {"project_use", "publish_credit"}
    for consent in consents.values():
        assert consent.granted_at is not None
        assert consent.text_version


def test_veroeffentlichung_der_nennung_ist_freiwillig(client, campaign, valid_form):
    data = dict(valid_form)
    del data["consent_publish_credit"]
    create(client, data)
    assert Submission.objects.count() == 1
    assert list(Consent.objects.values_list("kind", flat=True)) == ["project_use"]


def test_setup_beschreibung_ist_freiwillig(client, campaign, valid_form):
    data = dict(valid_form, setup_description="")
    create(client, data)
    assert Submission.objects.count() == 1


def test_fremder_browser_bekommt_404(client, campaign, valid_form):
    response = create(client, valid_form)
    other = Client()
    assert other.get(response["Location"]).status_code == 404


def test_manipuliertes_cookie_gibt_404(client, campaign, valid_form):
    response = create(client, valid_form)
    reference = Submission.objects.get().reference
    other = Client()
    other.cookies["schwarmstack_abgaben"] = reference
    assert other.get(response["Location"]).status_code == 404


def test_unbekannte_kennung_gibt_404(client, campaign, valid_form):
    create(client, valid_form)
    assert client.get(reverse("submission", args=["SW-ZZZZ"])).status_code == 404


def test_rueckkehr_fuehrt_zur_abgabeseite(client, campaign, valid_form):
    location = create(client, valid_form)["Location"]
    response = client.get(ENTRY)
    assert response.status_code == 302
    assert response["Location"] == location


@override_settings(SUBMISSION_COOKIE_SECURE=True)
def test_cookie_eigenschaften(client, campaign, valid_form):
    response = create(client, valid_form)
    cookie = response.cookies["schwarmstack_abgaben"]
    assert cookie["httponly"]
    assert cookie["secure"]
    assert cookie["samesite"] == "Lax"
    # gilt mindestens bis Ende der Aktion plus Nachfrist
    assert (
        int(cookie["max-age"])
        >= (campaign.ends_at + campaign.grace_period - campaign.starts_at).total_seconds()
        - 2 * 86400
    )


def test_kein_token_in_der_url(client, campaign, valid_form):
    location = create(client, valid_form)["Location"]
    assert location == f"/abgabe/{Submission.objects.get().reference}/"


def test_ohne_aktion_kein_formular(client, db):
    response = client.get(ENTRY)
    assert response.status_code == 503
    assert 'name="credit_name"' not in response.content.decode()
