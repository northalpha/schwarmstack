"""Kanal eines Masters aus dem Header (Ticket #95)."""

import json

import pytest
from files import fits, xisf

from submissions import exposure

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("text", "channel"),
    [
        ("Ha", "Ha"),
        ("H-alpha", "Ha"),
        ("H_Alpha 7nm", "Ha"),
        ("Hα", "Ha"),
        ("H", "Ha"),
        ("OIII", "OIII"),
        ("O3 [3 nm]", "OIII"),
        ("O", "OIII"),
        ("SII", "SII"),
        ("S2", "SII"),
        ("S", "SII"),
        ("L", "L"),
        ("Luminance", "L"),
        ("lum", "L"),
        ("Red", "R"),
        ("r", "R"),
        ("GREEN", "G"),
        ("Blue", "B"),
        ("IR", "IR"),
        ("IR pass", "IR"),
    ],
)
def test_filterbezeichnung_ergibt_den_kanal(text, channel):
    assert exposure.channel_for_filter(text) == channel


@pytest.mark.parametrize(
    "text",
    ["HO", "VIS", "DualBand", "L-eNhance", "L-Extreme", "UV/IR cut", "IR-cut", "", "Rot", "X"],
)
def test_dualband_und_unbekanntes_ergibt_keinen_vorschlag(text):
    assert exposure.channel_for_filter(text) is None


# -- Upload- und Seiten-Seam -------------------------------------------------------


def _mono(filter_value, *, keyword="FILTER"):
    return fits(keywords=[(keyword, filter_value, "")])


def test_header_schlaegt_kanal_vor_und_klick_uebernimmt_ihn_mit_herkunft(participant):
    master = participant.upload(_mono("Ha"), channel="L")

    assert master.channel == "L"
    assert master.channel_source == "manuell"
    assert "Der Header nennt den Kanal Hα" in participant.page()

    response = participant.save_exposure(master, accept="channel")

    assert response.status_code == 200
    master.refresh_from_db()
    assert master.channel == "Ha"
    assert master.channel_source == "header"
    assert "Der Header nennt den Kanal" not in response.json()["html"]


def test_uebernommener_kanal_steht_auch_in_der_begleitdatei(participant, storage_dir):
    master = participant.upload(_mono("OIII"), channel="L")
    participant.save_exposure(master, accept="channel")

    sidecar = next(storage_dir.rglob(f"{master.public_id.hex}.json"))
    assert json.loads(sidecar.read_text())["channel"] == "OIII"


def test_stimmt_der_gewaehlte_kanal_mit_dem_header_ueberein_bleibt_er_manuell(participant):
    master = participant.upload(_mono("H-alpha 7nm"), channel="Ha")

    assert master.channel_source == "manuell"
    assert "Der Header nennt den Kanal" not in participant.page()


def test_kanal_von_hand_aendern_wird_manuell_und_schreibt_die_begleitdatei(
    participant, storage_dir
):
    master = participant.upload(_mono("Ha"), channel="L")

    response = participant.save_exposure(master, channel="SII")

    assert response.status_code == 200
    master.refresh_from_db()
    assert (master.channel, master.channel_source) == ("SII", "manuell")
    sidecar = next(storage_dir.rglob(f"{master.public_id.hex}.json"))
    assert json.loads(sidecar.read_text())["channel"] == "SII"


@pytest.mark.parametrize("value", ["RGB", "Quatsch"])
def test_kanal_von_hand_nur_zwischen_einzelkanaelen(participant, value):
    master = participant.upload(_mono("Ha"), channel="L")

    assert participant.save_exposure(master, channel=value).status_code == 400
    master.refresh_from_db()
    assert master.channel == "L"


def test_rgb_master_wechselt_den_kanal_nicht(participant):
    master = participant.upload(fits(planes=3), channel="RGB", filename="rgb.fits")

    assert participant.save_exposure(master, channel="L").status_code == 400


@pytest.mark.parametrize("value", ["HO", "VIS", "IR-cut", "Sonderfilter"])
def test_ohne_eindeutigen_treffer_kein_vorschlag(participant, value):
    master = participant.upload(_mono(value), channel="L")

    assert master.header_channel == ""
    assert master.channel_source == "manuell"
    assert "Der Header nennt den Kanal" not in participant.page()


def test_bei_drei_ebenen_steht_der_kanal_fest_und_filter_wird_nicht_ausgewertet(participant):
    master = participant.upload(
        fits(planes=3, keywords=[("FILTER", "HO", "")]), channel="RGB", filename="rgb.fits"
    )

    assert master.header_channel == ""
    assert "Der Header nennt den Kanal" not in participant.page()


def test_alias_filt_1_und_insflnam(participant):
    one = participant.upload(_mono("SII", keyword="FILT-1"), channel="L")
    two = participant.upload(_mono("R", keyword="INSFLNAM"), channel="L", filename="b.fits")

    assert one.header_channel == "SII"
    assert two.header_channel == "R"


def test_xisf_property_hat_vorrang_vor_dem_filter_keyword(participant):
    master = participant.upload(
        xisf(
            fits_keywords=[("FILTER", "'L'", "")],
            properties=[("Instrument:Filter:Name", "String", "Ha")],
        ),
        channel="G",
        filename="g.xisf",
    )

    assert master.header_channel == "Ha"
    assert "FILTER</code>: Header widersprüchlich (FITS: L)" in participant.page()


def test_kanal_ohne_vorschlag_laesst_sich_nicht_uebernehmen(participant):
    master = participant.upload(_mono("HO"), channel="L")

    response = participant.save_exposure(master, accept="channel")

    assert response.status_code == 400
    master.refresh_from_db()
    assert master.channel == "L"
