"""Nennung nur bei Einwilligung zur Veröffentlichung (Ticket #33)."""

import json

import pytest
from files import fits
from uploads_helper import upload

from submissions.models import Master, Submission

pytestmark = pytest.mark.django_db


def sidecar(storage_dir, master):
    return json.loads((storage_dir / "objects" / master.sidecar_key).read_bytes())


def upload_one(client, form):
    client.post("/", form)
    response = upload(client, Submission.objects.get().reference, fits())
    return Master.objects.get(public_id=response.json()["masterId"])


@pytest.fixture
def anonymous_form(valid_form):
    form = dict(valid_form)
    del form["consent_publish_credit"]
    return form


def test_anonym_ohne_nennung_anlegen(client, campaign, anonymous_form):
    del anonymous_form["credit_name"]
    response = client.post("/", anonymous_form)
    assert response.status_code == 302
    assert Submission.objects.get().credit_name == ""


@pytest.mark.parametrize("name", ["", "   "])
def test_mit_haekchen_ist_die_nennung_pflicht(client, campaign, valid_form, name):
    response = client.post("/", dict(valid_form, credit_name=name))
    assert response.status_code == 200
    assert Submission.objects.count() == 0
    assert "Nennung" in response.context["form"].errors["credit_name"][0]


def test_ohne_haekchen_wird_ein_name_verworfen(client, campaign, anonymous_form):
    location = client.post("/", anonymous_form)["Location"]
    assert Submission.objects.get().credit_name == ""
    content = client.get(location).content.decode()
    assert "Ada Sternguck" not in content
    assert "anonym" in content
    assert "speichern wir keinen Namen" in content


def test_ohne_haekchen_erfaehrt_man_dass_der_eingetragene_name_verworfen_wurde(
    client, campaign, anonymous_form
):
    content = client.post("/", anonymous_form, follow=True).content.decode()
    assert "Deinen Namen haben wir nicht gespeichert" in content
    # Nur einmal, nicht bei jedem Besuch der Abgabeseite.
    location = f"/abgabe/{Submission.objects.get().reference}/"
    assert "Deinen Namen haben wir nicht gespeichert" not in client.get(location).content.decode()


def test_ohne_haekchen_und_ohne_name_kein_hinweis_auf_verworfenen_namen(
    client, campaign, anonymous_form
):
    del anonymous_form["credit_name"]
    content = client.post("/", anonymous_form, follow=True).content.decode()
    assert "Deinen Namen haben wir nicht gespeichert" not in content


def test_formular_sagt_dass_ohne_haekchen_kein_name_gespeichert_wird(client, campaign):
    assert "ohne Häkchen speichern wir keinen Namen" in client.get("/").content.decode()


def test_mit_haekchen_steht_die_nennung_auf_der_abgabeseite(client, campaign, valid_form):
    location = client.post("/", valid_form)["Location"]
    assert Submission.objects.get().credit_name == "Ada Sternguck"
    assert "Ada Sternguck" in client.get(location).content.decode()


def test_begleitdatei_mit_einwilligung_enthaelt_die_nennung(
    client, campaign, valid_form, storage_dir
):
    master = upload_one(client, valid_form)
    assert sidecar(storage_dir, master)["credit_name"] == "Ada Sternguck"


def test_begleitdatei_ohne_einwilligung_hat_keine_nennung(
    client, campaign, anonymous_form, storage_dir
):
    master = upload_one(client, anonymous_form)
    assert sidecar(storage_dir, master)["credit_name"] is None


def test_begleitdatei_nach_widerruf_hat_keine_nennung(client, campaign, valid_form, storage_dir):
    """Auch wenn die Nennung noch in der Datenbank stünde: ohne gültige Einwilligung nie."""
    client.post("/", valid_form)
    submission = Submission.objects.get()
    submission.consents.filter(kind="publish_credit").update(revoked_at=submission.created_at)
    response = upload(client, submission.reference, fits())
    master = Master.objects.get(public_id=response.json()["masterId"])
    assert sidecar(storage_dir, master)["credit_name"] is None
