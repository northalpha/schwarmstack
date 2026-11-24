"""Angaben ändern durch Teilnehmende auf der Submission-Seite (Ticket #67)."""

import json
from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.utils import timezone
from files import fits

from submissions import services
from submissions.models import Consent, Submission

pytestmark = pytest.mark.django_db


def change_url(participant):
    return f"/submission/{participant.reference}/aendern/"


def current(participant):
    return Submission.objects.get(pk=participant.submission.pk)


def test_seite_zeigt_formular_mit_den_aktuellen_angaben(participant):
    response = participant.client.get(change_url(participant))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Angaben ändern" in content
    assert "Ada Sternguck" in content
    assert "RedCat 51, ASI2600MM" in content


def test_submission_seite_bietet_angaben_aendern_an(participant):
    content = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert f'href="{change_url(participant)}"' in content


def test_teilnehmende_aendern_setup_und_namensnennung(participant):
    response = participant.client.post(
        change_url(participant),
        {"credit_name": "Ada S.", "setup_description": "Newton 200/800"},
    )
    assert response.status_code == 302
    assert response["Location"] == f"/submission/{participant.reference}/"
    submission = current(participant)
    assert submission.credit_name == "Ada S."
    assert submission.setup_description == "Newton 200/800"


def test_aenderung_schreibt_begleitdateien_neu(participant, storage_dir):
    master = participant.upload(fits())
    participant.client.post(
        change_url(participant), {"credit_name": "Ada S.", "setup_description": "Newton 200/800"}
    )
    sidecar = json.loads((storage_dir / "objects" / master.sidecar_key).read_text())
    assert sidecar["credit_name"] == "Ada S."


def test_namensnennung_darf_mit_einwilligung_nicht_leer_sein(participant):
    response = participant.client.post(
        change_url(participant), {"credit_name": " ", "setup_description": "Neu"}
    )
    assert response.status_code == 200
    assert "Namensnennung" in response.content.decode()
    submission = current(participant)
    assert submission.credit_name == "Ada Sternguck"
    assert submission.setup_description == "RedCat 51, ASI2600MM"


def test_ohne_einwilligung_laesst_sich_keine_namensnennung_aendern(participant):
    Consent.objects.filter(submission=participant.submission, kind="publish_credit").update(
        revoked_at=timezone.now()
    )
    services.details_changed(participant.submission)
    content = participant.client.get(change_url(participant)).content.decode()
    assert 'name="credit_name"' not in content
    participant.client.post(
        change_url(participant), {"credit_name": "Ada S.", "setup_description": "Neu"}
    )
    submission = current(participant)
    assert submission.credit_name == ""
    assert submission.setup_description == "Neu"


@pytest.mark.parametrize("after", [timedelta(minutes=1), timedelta(days=2)])
def test_nach_dem_ende_der_aktion_nichts_mehr_aendern(participant, campaign, after):
    campaign.ends_at = timezone.now() - after
    campaign.save()
    content = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert change_url(participant) not in content
    for method in (participant.client.get, participant.client.post):
        response = method(change_url(participant))
        assert response.status_code == 302
    participant.client.post(
        change_url(participant), {"credit_name": "Ada S.", "setup_description": "Neu"}
    )
    assert current(participant).setup_description == "RedCat 51, ASI2600MM"


def test_nach_der_loeschung_nichts_mehr_aendern(participant):
    participant.client.post(f"/submission/{participant.reference}/loeschen/")
    content = participant.client.get(f"/submission/{participant.reference}/").content.decode()
    assert change_url(participant) not in content
    response = participant.client.post(
        change_url(participant), {"credit_name": "Ada S.", "setup_description": "Neu"}
    )
    assert response.status_code == 302
    submission = current(participant)
    assert submission.credit_name == ""
    assert submission.setup_description == ""


def test_fremde_submission_ist_nicht_erreichbar(participant, another):
    other = another()
    assert other.client.get(change_url(participant)).status_code == 404


def test_protokoll_nennt_teilnehmende(participant):
    participant.client.post(
        change_url(participant), {"credit_name": "Ada S.", "setup_description": "Neu"}
    )
    entry = LogEntry.objects.get()
    assert entry.object_id == str(participant.submission.pk)
    assert "Angaben geändert" in entry.get_change_message()
    assert "Teilnehmende" in entry.get_change_message()
    assert not entry.user.is_active
    assert not entry.user.has_usable_password()


def test_unveraenderte_angaben_stehen_nicht_im_protokoll(participant):
    participant.client.post(
        change_url(participant),
        {"credit_name": "Ada Sternguck", "setup_description": "RedCat 51, ASI2600MM"},
    )
    assert not LogEntry.objects.exists()
