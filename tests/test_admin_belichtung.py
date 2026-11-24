"""Belichtungsangaben im Admin korrigieren, auch nach Ende der Aktion (Ticket #50)."""

import pytest
from admin_helper import ADMIN, change_form_data, submission_url
from files import fits
from test_belichtungsangaben import DWARF

pytestmark = pytest.mark.django_db


def master_change_url(master):
    return f"{ADMIN}submissions/master/{master.pk}/change/"


def test_betreiber_korrigiert_wert_der_wird_manuell(operator_client, participant):
    master = participant.upload(fits(keywords=DWARF))
    form = operator_client.get(master_change_url(master))
    assert form.status_code == 200

    response = operator_client.post(
        master_change_url(master), change_form_data(form, telescope="DWARF 3 (korrigiert)")
    )
    assert response.status_code == 302, response.content
    master.refresh_from_db()
    assert master.telescope == "DWARF 3 (korrigiert)"
    assert master.telescope_source == "manuell"
    assert master.total_exposure_source == "header"
    assert master.channel == "L"


def test_abgabe_seite_im_admin_verlinkt_die_belichtungsangaben(operator_client, participant):
    master = participant.upload(fits(keywords=DWARF))
    html = operator_client.get(submission_url(participant.submission)).content.decode()
    assert master_change_url(master) in html


def test_nur_angenommene_master_lassen_sich_aendern(operator_client, participant):
    master = participant.upload(fits(bitpix=16))
    assert operator_client.get(master_change_url(master)).status_code in (302, 403)
