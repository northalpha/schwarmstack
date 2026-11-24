"""Abgaben und Master im Admin: Master löschen, Rückzug, Widerruf, Download (Ticket #29)."""

import json
from datetime import timedelta

import pytest
from admin_helper import (
    ADMIN,
    change_form_data,
    log_messages,
    master_url,
    operator,  # noqa: F401
    operator_client,  # noqa: F401
    submission_url,
)
from django.test import Client
from django.utils import timezone
from files import fits, xisf
from storage_backends import DjangoBrowser
from uploads_helper import create, start, upload

from submissions.models import Consent, Master, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture
def storage_dir(settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


class Participant:
    """Eine teilnehmende Person mit eigenem Browser und einer Abgabe."""

    def __init__(self, form):
        self.client = Client()
        before = set(Submission.objects.values_list("pk", flat=True))
        self.client.post("/", form)
        self.submission = Submission.objects.exclude(pk__in=before).get()

    @property
    def reference(self):
        return self.submission.reference

    def upload(self, data, **kwargs):
        response = upload(self.client, self.reference, data, **kwargs)
        return Master.objects.get(public_id=response.json()["masterId"])

    def used(self):
        return self.client.get(f"/abgabe/{self.reference}/").context["used"]


@pytest.fixture
def participant(campaign, valid_form, storage_dir):
    return Participant(valid_form)


@pytest.fixture
def another(campaign, valid_form, storage_dir):
    return lambda: Participant(valid_form)


def stored(storage_dir, key):
    return (storage_dir / "objects" / key).exists()


def sidecar(storage_dir, master):
    return json.loads((storage_dir / "objects" / master.sidecar_key).read_text())


# -- Master löschen ------------------------------------------------------------


def test_master_loeschen_fragt_erst_nach(operator_client, participant, storage_dir):  # noqa: F811
    master = participant.upload(fits())
    response = operator_client.get(master_url(master, "loeschen"))
    assert response.status_code == 200
    assert master.original_name in response.content.decode()
    assert Master.objects.filter(pk=master.pk).exists()


def test_master_loeschen_entfernt_datei_und_gibt_belegung_frei(
    operator_client,  # noqa: F811
    participant,
    storage_dir,
):
    master = participant.upload(fits())
    assert participant.used() > 0
    response = operator_client.post(master_url(master, "loeschen"))
    assert response.status_code == 302
    assert not Master.objects.filter(pk=master.pk).exists()
    assert not stored(storage_dir, master.key)
    assert not stored(storage_dir, master.sidecar_key)
    assert participant.used() == 0
    assert any(master.original_name in m and "gelöscht" in m for m in log_messages())


def test_master_im_upload_wird_beim_loeschen_abgebrochen(
    operator_client,  # noqa: F811
    participant,
    storage_dir,
):
    data = fits()
    body = start(participant.client, participant.reference, size=len(data)).json()
    upload_id = create(participant.client, body["url"])
    master = Master.objects.get(public_id=body["masterId"])
    master.upload_id = upload_id
    master.save()
    assert (storage_dir / "multipart" / upload_id).exists()

    operator_client.post(master_url(master, "loeschen"))
    assert not (storage_dir / "multipart" / upload_id).exists()
    assert not Master.objects.filter(pk=master.pk).exists()
    assert participant.used() == 0


def test_abgelehnter_master_wird_nicht_geloescht(operator_client, participant):  # noqa: F811
    master = participant.upload(fits(bitpix=16))
    assert operator_client.post(master_url(master, "loeschen")).status_code == 404
    assert Master.objects.filter(pk=master.pk).exists()


def test_frueheste_dublette_wird_zum_original(
    operator_client,  # noqa: F811
    another,
    storage_dir,
):
    data = xisf()
    first, second, third = (another().upload(data, filename="m.xisf") for _ in range(3))
    assert second.duplicate_of == first and third.duplicate_of == first

    operator_client.post(master_url(first, "loeschen"))
    second.refresh_from_db()
    third.refresh_from_db()
    assert second.duplicate_of is None
    assert third.duplicate_of == second
    assert sidecar(storage_dir, second)["duplicate_of"] is None
    assert sidecar(storage_dir, third)["duplicate_of"] == {
        "reference": second.submission.reference,
        "master_id": second.public_id.hex,
    }


# -- Rückzug -------------------------------------------------------------------


def test_rueckzug_fragt_erst_nach(operator_client, participant):  # noqa: F811
    response = operator_client.get(submission_url(participant.submission, "zurueckziehen/"))
    assert response.status_code == 200
    assert participant.reference in response.content.decode()
    participant.submission.refresh_from_db()
    assert not participant.submission.is_withdrawn


def test_rueckzug_loescht_master_und_angaben_und_laesst_die_kennung(
    operator_client,  # noqa: F811
    participant,
    storage_dir,
):
    accepted = participant.upload(fits(), filename="a.fits")
    rejected = participant.upload(fits(bitpix=16), filename="b.fits")
    response = operator_client.post(submission_url(participant.submission, "zurueckziehen/"))
    assert response.status_code == 302

    submission = Submission.objects.get(reference=participant.reference)
    assert submission.is_withdrawn
    assert submission.withdrawn_by == Submission.WithdrawnBy.OPERATOR
    assert submission.credit_name == ""
    assert submission.setup_description == ""
    assert not submission.consents.exists()
    assert not submission.masters.exists()
    assert not stored(storage_dir, accepted.key)
    assert not stored(storage_dir, accepted.sidecar_key)
    assert not Master.objects.filter(pk=rejected.pk).exists()
    assert any("zurückgezogen" in m for m in log_messages(submission))


def test_rueckzug_ordnet_dubletten_neu_zu(operator_client, another, storage_dir):  # noqa: F811
    data = fits()
    owner, other = another(), another()
    original = owner.upload(data)
    duplicate = other.upload(data)
    operator_client.post(submission_url(owner.submission, "zurueckziehen/"))
    duplicate.refresh_from_db()
    assert duplicate.duplicate_of is None
    assert sidecar(storage_dir, duplicate)["duplicate_of"] is None
    assert not Master.objects.filter(pk=original.pk).exists()


def test_zurueckgezogene_abgabe_laesst_sich_nicht_wieder_oeffnen(
    operator_client,  # noqa: F811
    participant,
):
    operator_client.post(submission_url(participant.submission, "zurueckziehen/"))
    response = start(participant.client, participant.reference, size=1000)
    assert response.status_code == 400
    assert "zurückgezogen" in response.json()["error"]
    assert (
        "zurückgezogen"
        in participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    )
    # Ein zweiter Rückzug ändert nichts und bricht nicht ab.
    assert (
        operator_client.post(submission_url(participant.submission, "zurueckziehen/")).status_code
        == 302
    )


# -- Widerruf ------------------------------------------------------------------


def revoke_url(consent):
    return submission_url(consent.submission, f"einwilligung/{consent.pk}/widerrufen/")


def test_widerruf_der_nennung_bleibt_als_vermerk(operator_client, participant):  # noqa: F811
    """Der Widerruf der Veröffentlichung löscht die Nennung (Ticket #33)."""
    consent = participant.submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    assert operator_client.get(revoke_url(consent)).status_code == 200
    consent.refresh_from_db()
    assert consent.revoked_at is None

    assert operator_client.post(revoke_url(consent)).status_code == 302
    consent.refresh_from_db()
    assert consent.revoked_at is not None
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert not submission.is_withdrawn
    assert submission.credit_name == ""
    assert any("Widerruf" in m for m in log_messages(submission))

    # Ein zweiter Widerruf ändert nichts und steht nicht doppelt im Protokoll.
    operator_client.post(revoke_url(consent))
    assert sum("Widerruf" in m for m in log_messages(submission)) == 1


def test_widerruf_der_nennung_schreibt_die_begleitdateien_neu(
    operator_client,  # noqa: F811
    participant,
    storage_dir,
):
    """Ticket #33: Danach steht in keiner Begleitdatei der Abgabe mehr ein Name."""
    first = participant.upload(fits(), filename="a.fits")
    second = participant.upload(xisf(), filename="b.xisf")
    assert sidecar(storage_dir, first)["credit_name"] == "Ada Sternguck"
    consent = participant.submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    operator_client.post(revoke_url(consent))
    assert sidecar(storage_dir, first)["credit_name"] is None
    assert sidecar(storage_dir, second)["credit_name"] is None


def test_widerruf_der_nutzung_im_projekt_zieht_die_abgabe_zurueck(
    operator_client,  # noqa: F811
    participant,
    storage_dir,
):
    master = participant.upload(fits())
    consent = participant.submission.consents.get(kind=Consent.Kind.PROJECT_USE)
    operator_client.post(revoke_url(consent))
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.is_withdrawn
    assert submission.withdrawn_by == Submission.WithdrawnBy.OPERATOR
    assert not stored(storage_dir, master.key)


# -- Download zur Kontrolle ----------------------------------------------------


def test_angenommener_master_laesst_sich_herunterladen(
    operator_client,  # noqa: F811
    participant,
):
    data = fits(width=8)
    master = participant.upload(data)
    response = operator_client.get(master_url(master, "download"))
    assert response.status_code == 302
    reply = DjangoBrowser(Client()).send("GET", response["Location"])
    assert reply.status == 200
    assert reply.body == data
    assert any("heruntergeladen" in m for m in log_messages(master.submission))


def test_nur_angenommene_master_lassen_sich_herunterladen(
    operator_client,  # noqa: F811
    participant,
):
    master = participant.upload(fits(bitpix=16))
    assert operator_client.get(master_url(master, "download")).status_code == 404


def test_ohne_anmeldung_kein_download(participant):
    master = participant.upload(fits())
    response = Client().get(master_url(master, "download"))
    assert response.status_code == 302
    assert response["Location"].startswith(f"{ADMIN}login/")


# -- Liste, Suche, Filter, Korrektur ---------------------------------------------

LIST = f"{ADMIN}submissions/submission/"


def listed(client, query=""):
    response = client.get(LIST + query)
    assert response.status_code == 200
    return {s.reference for s in response.context["cl"].result_list}


def test_liste_zeigt_die_angaben_einer_abgabe(operator_client, participant):  # noqa: F811
    participant.upload(fits(), channel="Ha", filename="h.fits")
    participant.upload(xisf(), channel="OIII", filename="o.xisf")
    content = operator_client.get(LIST).content.decode()
    for text in [participant.reference, "Ada Sternguck", "RedCat 51", "Hα", "OIII", "KB"]:
        assert text in content, text


def test_suche_nach_kennung_und_nennung(operator_client, another, valid_form):  # noqa: F811
    ada = another()
    valid_form["credit_name"] = "Bruno Nebel"
    bruno = Participant(valid_form)
    assert listed(operator_client, f"?q={ada.reference}") == {ada.reference}
    assert listed(operator_client, f"?q={ada.reference.lower()}") == {ada.reference}
    assert listed(operator_client, "?q=nebel") == {bruno.reference}


def test_filter(operator_client, another):  # noqa: F811
    data = fits()
    plain, duplicate, rejected, withdrawn = (another() for _ in range(4))
    plain.upload(data, channel="R")
    duplicate.upload(data, channel="G")
    rejected.upload(fits(bitpix=16))
    operator_client.post(submission_url(withdrawn.submission, "zurueckziehen/"))

    assert listed(operator_client, "?kanal=R") == {plain.reference}
    assert listed(operator_client, "?dubletten=ja") == {duplicate.reference}
    assert listed(operator_client, "?ablehnungen=ja") == {rejected.reference}
    assert listed(operator_client, "?zurueckgezogen=ja") == {withdrawn.reference}
    assert withdrawn.reference not in listed(operator_client, "?zurueckgezogen=nein")


def test_nennung_und_setup_auch_nach_dem_ende_korrigieren(
    operator_client,  # noqa: F811
    participant,
    campaign,
):
    participant.upload(fits())
    campaign.starts_at = timezone.now() - timedelta(days=60)
    campaign.ends_at = timezone.now() - timedelta(days=30)
    campaign.save()
    url = submission_url(participant.submission)
    data = change_form_data(
        operator_client.get(url), credit_name="Ada S.", setup_description="RedCat 61"
    )
    response = operator_client.post(url, data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.credit_name == "Ada S."
    assert submission.setup_description == "RedCat 61"
    assert submission.masters.count() == 1
    assert submission.consents.count() == 2


def test_korrigierte_nennung_steht_in_der_begleitdatei(
    operator_client,  # noqa: F811
    participant,
    storage_dir,
):
    master = participant.upload(fits())
    url = submission_url(participant.submission)
    operator_client.post(url, change_form_data(operator_client.get(url), credit_name="Ada S."))
    assert sidecar(storage_dir, master)["credit_name"] == "Ada S."


def test_anonyme_abgabe_heisst_im_admin_anonym(operator_client, valid_form, campaign):  # noqa: F811
    """Ticket #33."""
    del valid_form["consent_publish_credit"]
    anonymous = Participant(valid_form)
    row = next(
        line
        for line in operator_client.get(LIST).content.decode().splitlines()
        if anonymous.reference in line
    )
    assert "anonym" in row
    assert "anonym" in operator_client.get(submission_url(anonymous.submission)).content.decode()


def test_anonyme_abgabe_bekommt_im_admin_keine_nennung(
    operator_client,  # noqa: F811
    valid_form,
    campaign,
):
    """Ticket #33: Ohne Einwilligung keine Nennung, auch nicht nachträglich durch Betreiber."""
    del valid_form["consent_publish_credit"]
    anonymous = Participant(valid_form)
    url = submission_url(anonymous.submission)
    data = change_form_data(operator_client.get(url), credit_name="Ada", setup_description="Neu")
    assert operator_client.post(url, data).status_code == 302
    submission = Submission.objects.get(pk=anonymous.submission.pk)
    assert submission.credit_name == ""
    assert submission.setup_description == "Neu"


def test_einwilligungen_lassen_sich_nicht_erteilen(operator_client, valid_form, campaign):  # noqa: F811
    del valid_form["consent_publish_credit"]
    anonymous = Participant(valid_form)
    url = submission_url(anonymous.submission)
    response = operator_client.get(url)
    data = change_form_data(
        response,
        **{"consents-TOTAL_FORMS": "2", "consents-1-kind": "publish_credit"},
    )
    operator_client.post(url, data)
    assert anonymous.submission.consents.count() == 1


def test_zurueckgezogene_abgabe_ist_nicht_mehr_aenderbar(
    operator_client,  # noqa: F811
    participant,
):
    operator_client.post(submission_url(participant.submission, "zurueckziehen/"))
    url = submission_url(participant.submission)
    operator_client.post(url, change_form_data(operator_client.get(url), credit_name="Neu"))
    assert Submission.objects.get(pk=participant.submission.pk).credit_name == ""


def test_abgaben_lassen_sich_weder_anlegen_noch_loeschen(
    operator_client,  # noqa: F811
    participant,
):
    assert operator_client.get(f"{LIST}add/").status_code == 403
    assert operator_client.get(submission_url(participant.submission, "delete/")).status_code == 403
