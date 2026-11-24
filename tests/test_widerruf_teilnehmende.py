"""Widerruf der Namensnennung durch Teilnehmende auf der Submission-Seite (Ticket #68)."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone
from files import fits
from uploads_helper import Participant

from submissions.models import Consent, Phase, Submission

pytestmark = pytest.mark.django_db


def revoke_url(participant):
    return f"/submission/{participant.reference}/namensnennung/widerrufen/"


def credit_consent(participant):
    return Consent.objects.get(submission=participant.submission, kind=Consent.Kind.PUBLISH_CREDIT)


def test_widerruf_fragt_erst_nach(participant):
    assert f'href="{revoke_url(participant)}"' in participant.page()
    response = participant.client.get(revoke_url(participant))
    assert response.status_code == 200
    content = response.content.decode()
    assert "anonym" in content
    assert 'method="post"' in content
    assert credit_consent(participant).revoked_at is None


def test_widerruf_macht_die_submission_anonym_und_die_einwilligung_bleibt_stehen(participant):
    response = participant.client.post(revoke_url(participant), follow=True)
    assert response.redirect_chain == [(f"/submission/{participant.reference}/", 302)]
    content = response.content.decode()
    assert "Ada Sternguck" not in content
    assert "anonym" in content

    assert credit_consent(participant).revoked_at is not None
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.credit_name == ""
    assert not submission.is_deleted


@pytest.mark.parametrize(
    "starts, ends, phase",
    [
        (timedelta(days=1), timedelta(days=30), Phase.BEFORE),
        (-timedelta(days=1), timedelta(days=30), Phase.OPEN),
        (-timedelta(days=2), -timedelta(minutes=1), Phase.GRACE),
        (-timedelta(days=30), -timedelta(days=5), Phase.CLOSED),
    ],
    ids=["vor-beginn", "laufend", "nachfrist", "schreibgeschuetzt"],
)
def test_widerruf_geht_in_jeder_phase_der_aktion(participant, campaign, starts, ends, phase):
    """Jederzeit, auch wenn die Submission sonst schreibgeschützt ist (DSGVO Art. 7 Abs. 3)."""
    now = timezone.now()
    campaign.starts_at = now + starts
    campaign.ends_at = now + ends
    campaign.save()
    assert campaign.phase() is phase

    assert f'href="{revoke_url(participant)}"' in participant.page()
    assert participant.client.get(revoke_url(participant)).status_code == 200
    participant.client.post(revoke_url(participant))
    assert credit_consent(participant).revoked_at is not None
    assert "Ada Sternguck" not in participant.page()


def test_nach_der_loeschung_kein_widerruf(participant):
    participant.client.post(f"/submission/{participant.reference}/loeschen/")
    assert revoke_url(participant) not in participant.page()
    for method in (participant.client.get, participant.client.post):
        response = method(revoke_url(participant))
        assert response.status_code == 302
        assert response["Location"] == f"/submission/{participant.reference}/"
    assert not Consent.objects.filter(submission=participant.submission).exists()


def test_widerruf_schreibt_die_begleitdateien_ohne_namensnennung(participant, storage_dir):
    master = participant.upload(fits())
    sidecar = storage_dir / "objects" / master.sidecar_key
    assert json.loads(sidecar.read_bytes())["credit_name"] == "Ada Sternguck"
    participant.client.post(revoke_url(participant))
    assert json.loads(sidecar.read_bytes())["credit_name"] is None


def test_nach_dem_widerruf_kein_zweiter_widerruf(participant):
    participant.client.post(revoke_url(participant))
    revoked_at = credit_consent(participant).revoked_at
    assert revoke_url(participant) not in participant.page()
    response = participant.client.post(revoke_url(participant))
    assert response.status_code == 302
    assert credit_consent(participant).revoked_at == revoked_at


def test_anonyme_submission_hat_nichts_zu_widerrufen(campaign, valid_form, storage_dir):
    form = dict(valid_form)
    del form["consent_publish_credit"]
    anonymous = Participant(form)
    assert revoke_url(anonymous) not in anonymous.page()
    assert anonymous.client.get(revoke_url(anonymous)).status_code == 302


def test_fremde_namensnennung_laesst_sich_nicht_widerrufen(participant, another):
    stranger = another()
    assert stranger.client.post(revoke_url(participant)).status_code == 404
    assert credit_consent(participant).revoked_at is None
