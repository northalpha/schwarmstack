"""Belichtungsangaben für Master lesen, die vor dem Feature hochgeladen wurden (Ticket #50)."""

from io import StringIO

import pytest
from django.core.management import call_command
from files import DWARF_KEYWORDS as DWARF
from files import UNKNOWN_CREATOR_KEYWORDS, fits

from submissions.models import Master

pytestmark = pytest.mark.django_db

EMPTY = {
    "exposure_per_light": None,
    "exposure_per_light_source": "",
    "light_count": None,
    "light_count_source": "",
    "total_exposure": None,
    "total_exposure_source": "",
    "instrument": "",
    "instrument_source": "",
    "telescope": "",
    "telescope_source": "",
    "creator": "",
}


def legacy(master, **values):
    """Ein Master wie vor dem Feature: ohne Belichtungsangaben (bis auf `values`)."""
    Master.objects.filter(pk=master.pk).update(**{**EMPTY, **values})


def backfill():
    out = StringIO()
    call_command("backfill_exposure", stdout=out)
    return out.getvalue()


def test_altbestand_wird_aus_dem_header_gefuellt(participant):
    master = participant.upload(fits(keywords=DWARF))
    legacy(master)

    output = backfill()

    master.refresh_from_db()
    assert master.total_exposure == 5715
    assert master.total_exposure_source == "header"
    assert master.light_count == 381
    assert master.telescope == "DWARF3"
    assert master.creator == "DWARFLAB"
    assert "1 Master" in output


def test_werte_von_hand_bleiben_unangetastet(participant):
    master = participant.upload(fits(keywords=DWARF))
    legacy(master, telescope="Mein DWARF", telescope_source="manuell")

    backfill()

    master.refresh_from_db()
    assert master.telescope == "Mein DWARF"
    assert master.telescope_source == "manuell"
    assert master.instrument == "DWARF3 TELE"


def test_nur_angenommene_master(participant):
    accepted = participant.upload(fits(keywords=DWARF))
    rejected = participant.upload(fits(keywords=DWARF, bitpix=16), channel="R")
    assert rejected.state == Master.State.REJECTED
    legacy(accepted)

    backfill()

    rejected.refresh_from_db()
    assert rejected.creator == ""


def test_beantwortete_frage_nach_exptime_kommt_nicht_wieder(participant):
    master = participant.upload(fits(keywords=UNKNOWN_CREATOR_KEYWORDS))
    participant.save_exposure(master, exptime_meaning="exposure_per_light")
    participant.save_exposure(master, exposure_per_light="30")

    backfill()

    master.refresh_from_db()
    assert master.exposure_per_light == 30
    assert "<code>EXPTIME</code> =" not in participant.page()
