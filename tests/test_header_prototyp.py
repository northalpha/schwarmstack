"""Rauchtest für den Prototyp scripts/header_prototyp.py (Ticket #49)."""

import importlib.util
import json
from pathlib import Path

import files

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "header_prototyp.py"


def _prototyp():
    spec = importlib.util.spec_from_file_location("header_prototyp", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ordner(tmp_path):
    ordner = tmp_path / "master"
    (ordner / "nacht2").mkdir(parents=True)
    (ordner / "L.fits").write_bytes(
        files.fits(
            keywords=[
                ("EXPTIME", 300.0, "Belichtung in s"),
                ("SWCREATE", "N.I.N.A. 3.1", ""),
                ("OBJECT", "M 101", "Ziel's Name"),
                ("HISTORY", None, "Kalibriert mit Darks"),
                ("COMMENT", None, "frei"),
            ],
            extension=[("EXTNAME", "MASKE", "")],
        )
    )
    (ordner / "nacht2" / "R.fit").write_bytes(
        files.fits(keywords=[("EXPTIME", 120.0, ""), ("SWCREATE", "N.I.N.A. 3.1", "")])
    )
    (ordner / "nacht2" / "RGB.xisf").write_bytes(
        files.xisf(
            channels=3,
            fits_keywords=[("EXPTIME", "300.", "Belichtung")],
            properties=[("Instrument:ExposureTime", "Float32", "300")],
            metadata=[("XISF:CreatorApplication", "String", "PixInsight 1.9")],
        )
    )
    (ordner / "kaputt.fts").write_bytes(b"kein Header")
    (ordner / "abgeschnitten.fits").write_bytes(
        files.fits(keywords=[("EXPTIME", 60.0, "")], truncate=100)
    )
    (ordner / "notizen.txt").write_text("wird ignoriert")
    return ordner


def test_ordner_ergibt_html_und_json(tmp_path):
    ordner = _ordner(tmp_path)
    ausgabe = tmp_path / "ausgabe"

    _prototyp().main([str(ordner), "--ausgabe", str(ausgabe)])

    daten = json.loads((ausgabe / "header.json").read_text())
    by_name = {Path(d["pfad"]).name: d for d in daten["dateien"]}
    assert sorted(by_name) == ["L.fits", "R.fit", "RGB.xisf", "abgeschnitten.fits", "kaputt.fts"]

    assert by_name["kaputt.fts"]["fehler"]
    assert by_name["abgeschnitten.fits"]["fehler"]
    assert by_name["abgeschnitten.fits"]["eintraege"], "gelesener Header bleibt sichtbar"
    assert by_name["L.fits"]["erzeuger"] == "N.I.N.A. 3.1"
    assert by_name["RGB.xisf"]["erzeuger"] == "PixInsight 1.9"

    def eintrag(name, schluessel):
        return [e for e in by_name[name]["eintraege"] if e["schluessel"] == schluessel]

    (exptime,) = eintrag("L.fits", "EXPTIME")
    assert (exptime["herkunft"], exptime["wert"], exptime["kommentar"]) == (
        "FITS-Keyword",
        "300.0",
        "Belichtung in s",
    )
    assert eintrag("L.fits", "OBJECT")[0]["kommentar"] == "Ziel's Name"
    assert eintrag("L.fits", "HISTORY")[0]["kommentar"] == "Kalibriert mit Darks"
    assert eintrag("L.fits", "EXTNAME")[0]["hdu"] == 1

    xisf = by_name["RGB.xisf"]["eintraege"]
    herkunft = {(e["herkunft"], e["schluessel"]): e["wert"] for e in xisf}
    assert herkunft[("FITS-Keyword", "EXPTIME")] == "300."
    assert herkunft[("XISF-Property", "Instrument:ExposureTime")] == "300"
    assert herkunft[("Bildattribut", "geometry")] == "4:3:3"

    html = (ausgabe / "header.html").read_text()
    assert "Instrument:ExposureTime" in html
    assert "kaputt.fts" in html
    assert "PixInsight 1.9" in html

    uebersicht = {(z["herkunft"], z["schluessel"]): z for z in daten["uebersicht"]}
    exptime = uebersicht[("FITS-Keyword", "EXPTIME")]
    assert (exptime["dateien"], exptime["verschiedene_werte"]) == (4, 4)
