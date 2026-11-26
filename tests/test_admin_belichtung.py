"""Belichtungsangaben im Admin ändern, auch nach Ende der Aktion (Ticket #50)."""

import pytest
from admin_helper import ADMIN, change_form_data, submission_url
from files import DWARF_KEYWORDS as DWARF
from files import fits

pytestmark = pytest.mark.django_db


def master_change_url(master):
    return f"{ADMIN}submissions/master/{master.pk}/change/"


def test_betreiber_aendert_wert_der_wird_manuell(operator_client, participant):
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


def test_submission_seite_im_admin_verlinkt_die_belichtungsangaben(operator_client, participant):
    master = participant.upload(fits(keywords=DWARF))
    html = operator_client.get(submission_url(participant.submission)).content.decode()
    assert master_change_url(master) in html


def test_nur_angenommene_master_lassen_sich_aendern(operator_client, participant):
    master = participant.upload(fits(bitpix=16))
    assert operator_client.get(master_change_url(master)).status_code in (302, 403)


def test_betreiber_kann_dezimalkomma_eingeben(operator_client, participant):
    master = participant.upload(fits())
    form = operator_client.get(master_change_url(master))
    response = operator_client.post(
        master_change_url(master), change_form_data(form, exposure_per_light="0,5")
    )
    assert response.status_code == 302, response.content
    master.refresh_from_db()
    assert str(master.exposure_per_light.normalize()) == "0.5"
    assert master.exposure_per_light_source == "manuell"


def test_betreiber_leert_teleskop_und_instrument(operator_client, participant):
    master = participant.upload(fits(keywords=DWARF))
    assert master.telescope and master.instrument
    form = operator_client.get(master_change_url(master))

    response = operator_client.post(
        master_change_url(master), change_form_data(form, telescope="", instrument="")
    )

    assert response.status_code == 302, response.content
    master.refresh_from_db()
    assert (master.telescope, master.instrument) == ("", "")
    assert (master.telescope_source, master.instrument_source) == ("", "")
