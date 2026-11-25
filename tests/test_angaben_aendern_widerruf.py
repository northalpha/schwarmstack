"""Widerruf der Einwilligung zur Namensnennung als Häkchen unter „Angaben ändern“."""

import pytest
from uploads_helper import Participant

from submissions.models import Consent, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture
def anonymous(campaign, valid_form, storage_dir):
    form = {k: v for k, v in valid_form.items() if k != "consent_publish_credit"}
    del form["credit_name"]
    return Participant(form)


def change_url(participant):
    return f"/submission/{participant.reference}/aendern/"


def test_haekchen_steht_unter_dem_namen(participant):
    content = participant.client.get(change_url(participant)).content.decode()
    assert 'name="revoke_credit"' in content
    assert content.index('name="credit_name"') < content.index('name="revoke_credit"')


def test_link_auf_der_submission_seite_entfaellt_solange_aendern_geht(participant):
    page = participant.page()
    assert "namensnennung/widerrufen" not in page


def test_haekchen_widerruft_und_loescht_den_namen(participant):
    response = participant.client.post(
        change_url(participant),
        {"setup_description": "Newton", "credit_name": "", "revoke_credit": "on"},
    )
    assert response.status_code == 302
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.credit_name == ""
    assert not submission.publishes_credit
    assert submission.setup_description == "Newton"
    consent = submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    assert consent.revoked_at is not None


def test_ohne_haekchen_bleibt_der_name_pflicht(participant):
    response = participant.client.post(
        change_url(participant), {"setup_description": "", "credit_name": ""}
    )
    assert response.status_code == 200
    assert Submission.objects.get(pk=participant.submission.pk).publishes_credit


def test_anonym_gibt_es_kein_haekchen(anonymous):
    content = anonymous.client.get(change_url(anonymous)).content.decode()
    assert 'name="revoke_credit"' not in content
