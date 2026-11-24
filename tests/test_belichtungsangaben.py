"""Belichtungsangaben je Master: aus dem Header, berechnet oder von Hand (Ticket #50)."""

import pytest
from files import fits, xisf

pytestmark = pytest.mark.django_db

DWARF = [
    ("ORIGIN", "DWARFLAB", "Organization or institution"),
    ("EXPTIME", 5715.0, "[s] Exposure Time"),
    ("STACKCNT", 381, "Number of stacked frames"),
    ("INSTRUME", "DWARF3 TELE", ""),
    ("TELESCOP", "DWARF3", ""),
]


def test_dwarf_master_speichert_werte_aus_dem_header(participant):
    master = participant.upload(fits(keywords=DWARF))

    assert master.total_exposure == 5715
    assert master.total_exposure_source == "header"
    assert master.light_count == 381
    assert master.light_count_source == "header"
    assert master.instrument == "DWARF3 TELE"
    assert master.instrument_source == "header"
    assert master.telescope == "DWARF3"
    assert master.telescope_source == "header"
    assert master.creator == "DWARFLAB"
    assert master.exposure_per_light is None
    assert master.exposure_per_light_source == ""


def page(participant):
    return participant.client.get(f"/abgabe/{participant.reference}/").content.decode()


def save(participant, master, **data):
    import json

    return participant.client.post(
        f"/abgabe/{participant.reference}/master/{master.public_id}/belichtung/",
        json.dumps(data),
        content_type="application/json",
    )


def test_dwarf_pro_light_wird_vorgeschlagen_und_erst_per_klick_gespeichert(participant):
    master = participant.upload(fits(keywords=DWARF))

    assert "15 s, berechnet aus 5715 s / 381." in page(participant)
    master.refresh_from_db()
    assert master.exposure_per_light is None

    response = save(participant, master, accept="exposure_per_light")
    assert response.status_code == 200
    master.refresh_from_db()
    assert master.exposure_per_light == 15
    assert master.exposure_per_light_source == "berechnet"
    assert "Übernehmen" not in response.json()["html"]


UNBEKANNT = [
    ("SWCREATE", "Sternenzaehler 2.1", ""),
    ("EXPTIME", 300.0, ""),
    ("STACKCNT", 20, ""),
]


def test_unbekannter_erzeuger_nichts_berechnet_formular_fragt_nach_exptime(participant):
    master = participant.upload(fits(keywords=UNBEKANNT))

    assert master.creator == "Sternenzaehler 2.1"
    assert master.light_count == 20
    assert master.exposure_per_light is None
    assert master.total_exposure is None
    html = page(participant)
    assert "<code>EXPTIME</code> = 300 s ist" in html
    assert "berechnet aus" not in html

    response = save(participant, master, exptime_meaning="exposure_per_light")
    assert response.status_code == 200
    master.refresh_from_db()
    assert master.exposure_per_light == 300
    assert master.exposure_per_light_source == "header"
    assert master.total_exposure is None
    html = response.json()["html"]
    assert "6000 s, berechnet aus 300 s × 20." in html
    assert "<code>EXPTIME</code>" not in html


def test_nicht_glatte_division_gibt_hinweis_statt_vorschlag(participant):
    keywords = [("ORIGIN", "DWARFLAB", ""), ("EXPTIME", 5700.0, ""), ("STACKCNT", 381, "")]
    master = participant.upload(fits(keywords=keywords))

    assert master.total_exposure == 5700
    html = page(participant)
    assert "Gemischte Belichtungszeiten? Bitte von Hand eintragen." in html
    assert "berechnet aus" not in html


def test_unter_einer_sekunde_wird_auf_zehntel_geprueft(participant):
    keywords = [("ORIGIN", "DWARFLAB", ""), ("EXPTIME", 50.0, ""), ("STACKCNT", 100, "")]
    participant.upload(fits(keywords=keywords))

    assert "0,5 s, berechnet aus 50 s / 100." in page(participant)


def test_standort_und_beobachter_landen_nirgends_in_der_datenbank(participant):
    from io import StringIO

    from django.core.management import call_command

    secret = [
        ("SITELAT", "52 31 12.345", ""),
        ("SITELONG", "13 24 36.789", ""),
        ("OBSGEO-B", 52.52012345, ""),
        ("OBSGEO-L", 13.41012345, ""),
        ("OBSGEO-H", 34.5678, ""),
        ("OBSERVER", "Hedwig Geheimnis", ""),
    ]
    participant.upload(fits(keywords=[*DWARF, *secret]))
    participant.upload(
        xisf(
            fits_keywords=[
                (k, f"'{v}'" if isinstance(v, str) else str(v), c) for k, v, c in secret
            ],
            properties=[("Observation:Location:Latitude", "Float64", "52.52012345")],
        ),
        channel="Ha",
        filename="ha.xisf",
    )

    dump = StringIO()
    call_command("dumpdata", stdout=dump)
    for value in ("52 31 12", "13 24 36", "52.5201", "13.4101", "34.5678", "Geheimnis"):
        assert value not in dump.getvalue()


def test_xisf_property_hat_vorrang_und_widerspruch_wird_angezeigt(participant):
    master = participant.upload(
        xisf(
            fits_keywords=[
                ("EXPTIME", "600.", ""),
                ("INSTRUME", "'ZWO ASI2600MM Pro'", ""),
                ("ORIGIN", "'DWARFLAB'", ""),
            ],
            properties=[
                ("Instrument:ExposureTime", "Float32", "300"),
                ("Instrument:Camera:Name", "String", "ZWO ASI2600MM Pro"),
            ],
        ),
        filename="l.xisf",
    )

    assert master.total_exposure == 300
    assert master.instrument == "ZWO ASI2600MM Pro"
    html = page(participant)
    assert "<code>EXPTIME</code>: Header widersprüchlich (FITS: 600.)" in html
    assert "INSTRUME</code>: Header" not in html


def test_erzeuger_aus_xisf_creator_application(participant):
    master = participant.upload(
        xisf(metadata=[("XISF:CreatorApplication", "String", "PixInsight 1.8.9-2")]),
        filename="l.xisf",
    )
    assert master.creator == "PixInsight 1.8.9-2"
    assert "Erzeuger: PixInsight 1.8.9-2" in page(participant)


def test_header_werte_werden_auf_100_zeichen_gekuerzt(participant):
    master = participant.upload(fits(keywords=[("TELESCOP", "T" * 68, "")]))
    long_xisf = participant.upload(
        xisf(properties=[("Instrument:Telescope:Name", "String", "R" * 150)]),
        filename="l.xisf",
        channel="R",
    )
    assert master.telescope == "T" * 68
    assert long_xisf.telescope == "R" * 100


def test_korrektur_von_hand_wird_manuell(participant):
    master = participant.upload(fits(keywords=DWARF))

    response = save(
        participant,
        master,
        exposure_per_light="",
        light_count="381",
        total_exposure="5715",
        instrument="DWARF 3",
        telescope="DWARF3",
    )
    assert response.status_code == 200
    master.refresh_from_db()
    assert master.instrument == "DWARF 3"
    assert master.instrument_source == "manuell"
    # Unverändert gelassene Werte behalten ihre Herkunft.
    assert master.total_exposure_source == "header"
    assert master.telescope_source == "header"


def test_zwei_zahlen_von_hand_ergeben_vorschlag_fuer_die_dritte(participant):
    master = participant.upload(fits())

    response = save(participant, master, exposure_per_light="0,5", light_count="120")
    assert "60 s, berechnet aus 0,5 s × 120." in response.json()["html"]

    save(participant, master, accept="total_exposure")
    master.refresh_from_db()
    assert master.total_exposure == 60
    assert master.total_exposure_source == "berechnet"


def test_drei_zahlen_die_nicht_passen_werden_gespeichert_mit_hinweis(participant):
    master = participant.upload(fits())

    response = save(
        participant, master, exposure_per_light="15", light_count="10", total_exposure="200"
    )
    assert response.status_code == 200
    master.refresh_from_db()
    assert master.total_exposure == 200
    assert "Die Zahlen passen nicht zusammen" in response.json()["html"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("light_count", "0"),
        ("light_count", "2,5"),
        ("exposure_per_light", "-3"),
        ("total_exposure", "viel"),
        ("instrument", "x" * 101),
    ],
)
def test_ungueltige_eingabe_wird_abgelehnt(participant, field, value):
    master = participant.upload(fits())
    response = save(participant, master, **{field: value})
    assert response.status_code == 400
    assert response.json()["error"]


def test_nach_ende_der_aktion_lehnt_die_api_aenderungen_ab(participant, campaign):
    from datetime import timedelta

    from django.utils import timezone

    master = participant.upload(fits(keywords=DWARF))
    campaign.ends_at = timezone.now() - timedelta(minutes=1)
    campaign.save()

    response = save(participant, master, instrument="anders")
    assert response.status_code == 403
    master.refresh_from_db()
    assert master.instrument == "DWARF3 TELE"
    html = page(participant)
    assert "DWARF3 TELE" in html
    assert 'name="instrument"' not in html


def test_ohne_javascript_speichert_das_formular_und_fuehrt_zurueck(participant):
    master = participant.upload(fits())
    response = participant.client.post(
        f"/abgabe/{participant.reference}/master/{master.public_id}/belichtung/",
        {"telescope": "RedCat 51"},
    )
    assert response.status_code == 302
    assert response["Location"].endswith(f"#belichtung-{master.public_id}")
    master.refresh_from_db()
    assert master.telescope == "RedCat 51"


def test_fremde_abgabe_kann_nichts_aendern(participant, another):
    master = participant.upload(fits())
    other = another()
    response = other.client.post(
        f"/abgabe/{participant.reference}/master/{master.public_id}/belichtung/",
        '{"telescope": "x"}',
        content_type="application/json",
    )
    assert response.status_code == 404


def test_nach_rueckzug_sind_alle_werte_leer(participant):
    from submissions.models import Master

    participant.upload(fits(keywords=DWARF))
    participant.client.post(f"/abgabe/{participant.reference}/zurueckziehen/")

    assert not Master.objects.filter(submission=participant.submission).exists()
    assert not Master.objects.exclude(creator="").exists()


def test_dublette_liest_ihre_werte_selbst(participant, another):
    data = fits(keywords=DWARF)
    original = participant.upload(data)
    participant.client.post(
        f"/abgabe/{participant.reference}/master/{original.public_id}/belichtung/",
        '{"telescope": "von Hand"}',
        content_type="application/json",
    )
    duplicate = another().upload(data)

    assert duplicate.duplicate_of == original
    assert duplicate.telescope == "DWARF3"
    assert duplicate.telescope_source == "header"


def test_belichtungsangaben_im_manifest_nicht_in_der_begleitdatei(participant, storage_dir):
    import json

    from submissions import exposure

    master = participant.upload(fits(keywords=DWARF))
    sidecar = json.loads((storage_dir / "objects" / master.sidecar_key).read_text())
    assert not {"total_exposure", "light_count", "instrument", "creator"} & set(sidecar)
    assert "5715" not in json.dumps(sidecar)

    entry = exposure.manifest_values(master)
    assert entry["total_exposure"] == {"value": "5715", "source": "header"}
    assert entry["light_count"] == {"value": 381, "source": "header"}
    assert entry["exposure_per_light"] == {"value": None, "source": ""}
    assert entry["creator"] == "DWARFLAB"
