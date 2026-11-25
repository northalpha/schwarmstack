"""Löschung und Master löschen durch Teilnehmende auf der Submission-Seite (Ticket #30)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from files import fits
from uploads_helper import finish, sign, start

from submissions import services
from submissions.models import Consent, Master, Submission

pytestmark = pytest.mark.django_db


def page_url(participant):
    return f"/submission/{participant.reference}/"


def delete_submission_url(participant):
    return f"/submission/{participant.reference}/loeschen/"


def test_loeschung_fragt_erst_nach(participant):
    response = participant.client.get(delete_submission_url(participant))
    assert response.status_code == 200
    content = response.content.decode()
    assert "endgültig" in content
    assert 'method="post"' in content
    assert not Submission.objects.get(pk=participant.submission.pk).is_deleted


def test_loeschung_loescht_master_und_angaben_und_vermerkt_teilnehmende(participant, storage_dir):
    master = participant.upload(fits())
    response = participant.client.post(delete_submission_url(participant))
    assert response.status_code == 302
    assert response["Location"] == f"/submission/{participant.reference}/"

    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.is_deleted
    assert submission.deleted_by == Submission.DeletedBy.PARTICIPANT
    assert submission.credit_name == ""
    assert not submission.masters.exists()
    assert not (storage_dir / "objects" / master.key).exists()


def test_geloeschte_submission_zeigt_nur_noch_die_loeschung(participant):
    participant.upload(fits())
    participant.client.post(delete_submission_url(participant))
    content = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert participant.reference in content
    assert "Du hast diese Submission am" in content
    assert "gelöscht" in content
    assert "Ada Sternguck" not in content
    assert "m101_L.fits" not in content
    assert delete_submission_url(participant) not in content


def test_submission_seite_bietet_die_loeschung_an(participant):
    content = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert f'href="{delete_submission_url(participant)}"' in content


@pytest.mark.parametrize("after", [timedelta(minutes=1), timedelta(days=2)])
def test_nach_dem_ende_der_aktion_keine_loeschung(participant, campaign, after):
    """In der Nachfrist und danach ist die Submission nicht mehr änderbar (ADR 0002)."""
    campaign.ends_at = timezone.now() - after
    campaign.save()
    content = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert delete_submission_url(participant) not in content
    for method in (participant.client.get, participant.client.post):
        response = method(delete_submission_url(participant), follow=True)
        assert response.redirect_chain == [(page_url(participant), 302)]
        assert "nicht mehr ändern" in response.content.decode()
    assert not Submission.objects.get(pk=participant.submission.pk).is_deleted


def test_loeschung_meldet_den_erfolg(participant):
    response = participant.client.post(delete_submission_url(participant), follow=True)
    assert "Deine Submission wurde gelöscht." in response.content.decode()


def test_zweite_loeschung_fuehrt_zur_submission_seite(participant):
    participant.client.post(delete_submission_url(participant))
    response = participant.client.post(delete_submission_url(participant))
    assert response.status_code == 302
    assert response["Location"] == page_url(participant)


def test_fremde_submission_laesst_sich_nicht_loeschen(participant, another):
    stranger = another()
    assert stranger.client.post(delete_submission_url(participant)).status_code == 404
    assert not Submission.objects.get(pk=participant.submission.pk).is_deleted


# -- Master löschen ------------------------------------------------------------


def delete_url(participant, master):
    return f"/submission/{participant.reference}/master/{master.public_id}/loeschen/"


def test_master_loeschen_fragt_erst_nach(participant):
    master = participant.upload(fits())
    page = participant.client.get(f"/submission/{participant.reference}/").content.decode()
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
    assert response["Location"] == f"/submission/{participant.reference}/"
    assert not Master.objects.filter(pk=master.pk).exists()
    assert not (storage_dir / "objects" / master.key).exists()
    assert participant.used() == 0
    page = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert "Noch keine Master." in page


def test_abgelehnter_master_hat_nichts_zu_loeschen(participant):
    master = participant.upload(fits(bitpix=16))
    page = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert delete_url(participant, master) not in page
    assert participant.client.post(delete_url(participant, master)).status_code == 404


def test_nach_dem_ende_der_aktion_kein_master_loeschen(participant, campaign):
    master = participant.upload(fits())
    campaign.ends_at = timezone.now() - timedelta(minutes=1)
    campaign.save()
    page = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert delete_url(participant, master) not in page
    response = participant.client.post(delete_url(participant, master))
    assert response.status_code == 302
    assert response["Location"] == page_url(participant)
    assert Master.objects.filter(pk=master.pk).exists()


def test_fremden_master_nicht_loeschen(participant, another):
    master = participant.upload(fits())
    stranger = another()
    foreign = f"/submission/{stranger.reference}/master/{master.public_id}/loeschen/"
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


# -- Alte Adressen (Issue #66) --------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("abgabe/{ref}/", "submission/{ref}/"),
        ("abgabe/{ref}/zurueckziehen/", "submission/{ref}/loeschen/"),
        ("abgabe/{ref}/master/", "submission/{ref}/master/"),
    ],
)
def test_alte_abgabe_adressen_leiten_dauerhaft_um(participant, old, new):
    ref = participant.reference
    response = participant.client.get("/" + old.format(ref=ref) + "?x=1")
    assert response.status_code == 301
    assert response["Location"] == "/" + new.format(ref=ref) + "?x=1"


def test_loeschung_loescht_auch_widerrufene_einwilligungen(participant):
    """Ein Widerruf bleibt nur bis zur Löschung stehen; danach gibt es in der Datenbank keinen
    Nachweis mehr (Glossar: Widerruf; Nachweis ist allein das Manifest, ADR 0008)."""
    submission = participant.submission
    consent = submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    assert services.revoke(consent)
    assert submission.consents.filter(revoked_at__isnull=False).exists()

    services.delete_submission(submission, by=Submission.DeletedBy.OPERATOR)

    assert not Consent.objects.filter(submission=submission).exists()
