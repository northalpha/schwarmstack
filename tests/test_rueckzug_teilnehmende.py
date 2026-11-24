"""Rückzug und Master löschen durch Teilnehmende auf der Abgabeseite (Ticket #30)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from files import fits
from uploads_helper import finish, sign, start

from submissions.models import Master, Submission

pytestmark = pytest.mark.django_db


def page_url(participant):
    return f"/abgabe/{participant.reference}/"


def withdraw_url(participant):
    return f"/abgabe/{participant.reference}/zurueckziehen/"


def test_rueckzug_fragt_erst_nach(participant):
    response = participant.client.get(withdraw_url(participant))
    assert response.status_code == 200
    content = response.content.decode()
    assert "endgültig" in content
    assert 'method="post"' in content
    assert not Submission.objects.get(pk=participant.submission.pk).is_withdrawn


def test_rueckzug_loescht_master_und_angaben_und_vermerkt_teilnehmende(participant, storage_dir):
    master = participant.upload(fits())
    response = participant.client.post(withdraw_url(participant))
    assert response.status_code == 302
    assert response["Location"] == f"/abgabe/{participant.reference}/"

    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.is_withdrawn
    assert submission.withdrawn_by == Submission.WithdrawnBy.PARTICIPANT
    assert submission.credit_name == ""
    assert not submission.masters.exists()
    assert not (storage_dir / "objects" / master.key).exists()


def test_zurueckgezogene_abgabe_zeigt_nur_noch_den_rueckzug(participant):
    participant.upload(fits())
    participant.client.post(withdraw_url(participant))
    content = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert participant.reference in content
    assert "Du hast diese Abgabe am" in content
    assert "zurückgezogen" in content
    assert "Ada Sternguck" not in content
    assert "m101_L.fits" not in content
    assert withdraw_url(participant) not in content


def test_abgabeseite_bietet_den_rueckzug_an(participant):
    content = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert f'href="{withdraw_url(participant)}"' in content


@pytest.mark.parametrize("after", [timedelta(minutes=1), timedelta(days=2)])
def test_nach_dem_ende_der_aktion_kein_rueckzug(participant, campaign, after):
    """In der Nachfrist und danach ist die Abgabe nicht mehr änderbar (ADR 0002)."""
    campaign.ends_at = timezone.now() - after
    campaign.save()
    content = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert withdraw_url(participant) not in content
    for method in (participant.client.get, participant.client.post):
        response = method(withdraw_url(participant), follow=True)
        assert response.redirect_chain == [(page_url(participant), 302)]
        assert "nicht mehr ändern" in response.content.decode()
    assert not Submission.objects.get(pk=participant.submission.pk).is_withdrawn


def test_rueckzug_meldet_den_erfolg(participant):
    response = participant.client.post(withdraw_url(participant), follow=True)
    assert "Deine Abgabe wurde zurückgezogen." in response.content.decode()


def test_zweiter_rueckzug_fuehrt_zur_abgabeseite(participant):
    participant.client.post(withdraw_url(participant))
    response = participant.client.post(withdraw_url(participant))
    assert response.status_code == 302
    assert response["Location"] == page_url(participant)


def test_fremde_abgabe_laesst_sich_nicht_zurueckziehen(participant, another):
    stranger = another()
    assert stranger.client.post(withdraw_url(participant)).status_code == 404
    assert not Submission.objects.get(pk=participant.submission.pk).is_withdrawn


# -- Master löschen ------------------------------------------------------------


def delete_url(participant, master):
    return f"/abgabe/{participant.reference}/master/{master.public_id}/loeschen/"


def test_master_loeschen_fragt_erst_nach(participant):
    master = participant.upload(fits())
    page = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert f'href="{delete_url(participant, master)}"' in page
    response = participant.client.get(delete_url(participant, master))
    assert response.status_code == 200
    assert master.original_name in response.content.decode()
    assert Master.objects.filter(pk=master.pk).exists()


def test_master_loeschen_entfernt_datei_und_gibt_belegung_frei(participant, storage_dir):
    master = participant.upload(fits())
    assert participant.used() > 0
    response = participant.client.post(delete_url(participant, master))
    assert response.status_code == 302
    assert response["Location"] == f"/abgabe/{participant.reference}/"
    assert not Master.objects.filter(pk=master.pk).exists()
    assert not (storage_dir / "objects" / master.key).exists()
    assert participant.used() == 0
    page = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert "Noch keine Master." in page


def test_abgelehnter_master_hat_nichts_zu_loeschen(participant):
    master = participant.upload(fits(bitpix=16))
    page = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert delete_url(participant, master) not in page
    assert participant.client.post(delete_url(participant, master)).status_code == 404


def test_nach_dem_ende_der_aktion_kein_master_loeschen(participant, campaign):
    master = participant.upload(fits())
    campaign.ends_at = timezone.now() - timedelta(minutes=1)
    campaign.save()
    page = participant.client.get(f"/abgabe/{participant.reference}/").content.decode()
    assert delete_url(participant, master) not in page
    response = participant.client.post(delete_url(participant, master))
    assert response.status_code == 302
    assert response["Location"] == page_url(participant)
    assert Master.objects.filter(pk=master.pk).exists()


def test_fremden_master_nicht_loeschen(participant, another):
    master = participant.upload(fits())
    stranger = another()
    foreign = f"/abgabe/{stranger.reference}/master/{master.public_id}/loeschen/"
    assert stranger.client.post(foreign).status_code == 404
    assert stranger.client.post(delete_url(participant, master)).status_code == 404
    assert Master.objects.filter(pk=master.pk).exists()


def test_upload_eines_geloeschten_masters_meldet_das_verstaendlich(participant):
    """Der Master wird gelöscht, während ein anderer Tab ihn noch hochlädt."""
    data = fits()
    body = start(participant.client, participant.reference, size=len(data)).json()
    master = Master.objects.get(public_id=body["masterId"])
    participant.client.post(delete_url(participant, master))

    signed = sign(
        participant.client, participant.reference, body["masterId"],
        method="PUT", key=body["key"], uploadId="x", partNumber=1,
    )  # fmt: skip
    assert signed.status_code == 404
    assert signed.json()["error"] == "Dieser Master wurde gelöscht."
    finished = finish(participant.client, participant.reference, body["masterId"])
    assert finished.json()["error"] == "Dieser Master wurde gelöscht."
