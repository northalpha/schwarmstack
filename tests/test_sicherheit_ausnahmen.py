"""scripts/ausnahmen.py: Ausnahmen für Sicherheitsfunde brauchen Grund und Ablaufdatum (#121)."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ausnahmen.py"


def _ausnahmen():
    spec = importlib.util.spec_from_file_location("ausnahmen", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ausnahmen = _ausnahmen()
HEUTE = date(2026, 11, 26)

GUT = """
[[ausnahme]]
id = "CVE-2026-0001"
grund = "Nur im Dev-Werkzeug, nicht im Image."
bis = 2027-03-01
"""


def test_gueltige_ausnahme_ist_aktiv():
    eintraege = ausnahmen.laden(GUT)
    assert ausnahmen.pruefen(eintraege, HEUTE) == []
    assert ausnahmen.aktive_ids(eintraege, HEUTE) == ["CVE-2026-0001"]


def test_leere_datei_ist_in_ordnung():
    assert ausnahmen.pruefen(ausnahmen.laden(""), HEUTE) == []


def test_abgelaufene_ausnahme_ist_fehler_und_nicht_aktiv():
    eintraege = ausnahmen.laden(GUT.replace("2027-03-01", "2026-11-25"))
    assert any("abgelaufen" in f for f in ausnahmen.pruefen(eintraege, HEUTE))
    assert ausnahmen.aktive_ids(eintraege, HEUTE) == []


def test_ablauf_am_heutigen_tag_gilt_noch():
    eintraege = ausnahmen.laden(GUT.replace("2027-03-01", "2026-11-26"))
    assert ausnahmen.pruefen(eintraege, HEUTE) == []


@pytest.mark.parametrize("fehlt", ["id", "grund", "bis"])
def test_pflichtfelder(fehlt):
    zeilen = [z for z in GUT.splitlines() if not z.startswith(fehlt + " ")]
    fehler = ausnahmen.pruefen(ausnahmen.laden("\n".join(zeilen)), HEUTE)
    assert any(fehlt in f for f in fehler)


def test_leere_begruendung_zaehlt_nicht():
    eintraege = ausnahmen.laden(GUT.replace("Nur im Dev-Werkzeug, nicht im Image.", "  "))
    assert any("grund" in f for f in ausnahmen.pruefen(eintraege, HEUTE))


def test_ablaufdatum_muss_ein_datum_sein():
    eintraege = ausnahmen.laden(GUT.replace("2027-03-01", '"bald"'))
    assert any("bis" in f for f in ausnahmen.pruefen(eintraege, HEUTE))


def test_doppelte_id_ist_fehler():
    eintraege = ausnahmen.laden(GUT + GUT)
    assert any("doppelt" in f for f in ausnahmen.pruefen(eintraege, HEUTE))


def test_die_datei_im_repo_ist_gueltig():
    text = (ROOT / "sicherheit-ausnahmen.toml").read_text()
    assert ausnahmen.pruefen(ausnahmen.laden(text), date.today()) == []
