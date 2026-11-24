"""PROTOTYP – Wegwerfcode (Issue #49). Nicht Teil der App, nicht weiterpflegen.

Zeigt roh, welche Angaben in den Headern echter Master stecken, damit danach entschieden werden
kann, welche Schlüssel die App übernimmt. Läuft nur lokal: ohne App, ohne S3, ohne Datenbank.

    uv run python scripts/header_prototyp.py PFAD... [--ausgabe ORDNER]

PFAD sind Dateien oder Ordner; Ordner werden rekursiv nach .xisf, .fits, .fit und .fts
durchsucht. Gelesen wird nur der Header, keine Pixeldaten. Ergebnis im Ausgabeordner:
header.html (Übersicht je Schlüssel und Herkunft, Einzelansicht je Datei) und header.json
(alle Rohdaten). Standort, Beobachter und Pfade werden unverändert angezeigt.
"""

import argparse
import html
import json
import struct
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

SUFFIXES = {".xisf", ".fits", ".fit", ".fts"}
FITS_KEYWORD = "FITS-Keyword"
XISF_PROPERTY = "XISF-Property"
IMAGE_ATTRIBUTE = "Bildattribut"
BEISPIELE = 5

_BLOCK = 2880
_CARD = 80
_MAX_HEADER_BLOCKS = 10_000  # Schutz vor endlosem Lesen bei Unsinn ohne END
_TEXT_KEYWORDS = {"COMMENT", "HISTORY", "CONTINUE", ""}


@dataclass
class Eintrag:
    herkunft: str
    schluessel: str
    wert: str | None
    kommentar: str = ""
    hdu: int | None = None  # FITS: Nummer der HDU
    ort: str = ""  # XISF: Element, in dem der Eintrag steht (z. B. Image, Metadata)


@dataclass
class Datei:
    pfad: str
    format: str
    eintraege: list[Eintrag] = field(default_factory=list)
    fehler: str = ""
    erzeuger: str = ""


class _Kaputt(Exception):
    pass


# -- Dateien finden -----------------------------------------------------------


def finde(pfade: list[str]) -> list[Path]:
    gefunden = []
    for pfad in map(Path, pfade):
        if pfad.is_dir():
            gefunden += sorted(p for p in pfad.rglob("*") if p.suffix.lower() in SUFFIXES)
        else:
            gefunden.append(pfad)
    return gefunden


def lies(pfad: Path) -> Datei:
    suffix = pfad.suffix.lower()
    datei = Datei(str(pfad), "XISF" if suffix == ".xisf" else "FITS")
    try:
        if suffix not in SUFFIXES:
            raise _Kaputt(f"Nicht unterstützte Endung {suffix or '(keine)'}.")
        with pfad.open("rb") as f:
            if suffix == ".xisf":
                _xisf(f, datei.eintraege)
            else:
                _fits(f, datei.eintraege)
    except (_Kaputt, OSError) as exc:
        datei.fehler = str(exc)
    datei.erzeuger = _erzeuger(datei.eintraege)
    return datei


def _erzeuger(eintraege: list[Eintrag]) -> str:
    for herkunft, schluessel in (
        (XISF_PROPERTY, "XISF:CreatorApplication"),
        (FITS_KEYWORD, "SWCREATE"),
    ):
        for e in eintraege:
            if (e.herkunft, e.schluessel) == (herkunft, schluessel) and e.wert:
                return e.wert
    return ""


# -- FITS -----------------------------------------------------------------------


def _fits(f, eintraege: list[Eintrag]) -> None:
    hdu = 0
    while True:
        karten = _fits_header(f, erste=hdu == 0)
        if karten is None:
            return  # sauberes Dateiende nach der letzten HDU
        werte = {}
        for text in karten:
            eintrag = _karte(text, hdu)
            eintraege.append(eintrag)
            werte.setdefault(eintrag.schluessel, eintrag.wert)
        f.seek(_datenlaenge(werte), 1)
        hdu += 1


def _fits_header(f, *, erste: bool) -> list[str] | None:
    karten = []
    for _ in range(_MAX_HEADER_BLOCKS):
        block = f.read(_BLOCK)
        if not block and not karten and not erste:
            return None
        if len(block) < _BLOCK:
            raise _Kaputt("Header unvollständig: Datei endet vor END.")
        for i in range(0, _BLOCK, _CARD):
            text = block[i : i + _CARD].decode("ascii", "replace")
            if not karten:
                start = "SIMPLE  =" if erste else "XTENSION="
                if not text.startswith(start):
                    if erste:
                        raise _Kaputt("Keine FITS-Datei: Der Header beginnt nicht mit SIMPLE.")
                    raise _Kaputt("Nach den Daten folgt keine gültige Erweiterung (XTENSION).")
            if text[:8].strip() == "END":
                return karten
            karten.append(text)
    raise _Kaputt("Kein END im Header gefunden.")


def _karte(text: str, hdu: int) -> Eintrag:
    schluessel = text[:8].strip()
    if schluessel in _TEXT_KEYWORDS or text[8:10] != "= ":
        return Eintrag(FITS_KEYWORD, schluessel, None, text[8:].rstrip(), hdu=hdu)
    wert, kommentar = _wert_und_kommentar(text[10:])
    return Eintrag(FITS_KEYWORD, schluessel, wert, kommentar, hdu=hdu)


def _wert_und_kommentar(rest: str) -> tuple[str, str]:
    rest = rest.strip()
    if rest.startswith("'"):
        i, wert = 1, []
        while i < len(rest):
            if rest[i] == "'":
                if rest[i + 1 : i + 2] == "'":
                    wert.append("'")
                    i += 2
                    continue
                break
            wert.append(rest[i])
            i += 1
        _, _, kommentar = rest[i + 1 :].partition("/")
        return "".join(wert).rstrip(), kommentar.strip()
    wert, _, kommentar = rest.partition("/")
    return wert.strip(), kommentar.strip()


def _datenlaenge(werte: dict[str, str | None]) -> int:
    def zahl(schluessel, standard):
        try:
            return int(werte.get(schluessel) or standard)
        except ValueError as exc:
            raise _Kaputt(f"{schluessel} ist keine ganze Zahl.") from exc

    naxis = zahl("NAXIS", 0)
    if naxis == 0:
        return 0
    pixel = 1
    for i in range(1, naxis + 1):
        pixel *= zahl(f"NAXIS{i}", 0)
    laenge = abs(zahl("BITPIX", 8)) // 8 * zahl("GCOUNT", 1) * (zahl("PCOUNT", 0) + pixel)
    return -(-laenge // _BLOCK) * _BLOCK


# -- XISF -----------------------------------------------------------------------


def _xisf(f, eintraege: list[Eintrag]) -> None:
    kopf = f.read(16)
    if not kopf.startswith(b"XISF0100"):
        raise _Kaputt("Keine XISF-Datei: Die Signatur XISF0100 fehlt.")
    if len(kopf) < 16:
        raise _Kaputt("Header unvollständig.")
    (laenge,) = struct.unpack("<I", kopf[8:12])
    xml = f.read(laenge)
    if len(xml) < laenge:
        raise _Kaputt("Header unvollständig: Datei ist kürzer als der XML-Header.")
    try:
        wurzel = fromstring(xml)
    except (ParseError, DefusedXmlException, ValueError) as exc:
        raise _Kaputt(f"XML-Header nicht lesbar: {exc}") from exc
    _xisf_element(wurzel, "", eintraege)


def _tag(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _xisf_element(element, ort: str, eintraege: list[Eintrag]) -> None:
    for kind in element:
        tag = _tag(kind)
        hier = f"{ort}/{tag}" if ort else tag
        if tag == "Image":
            for name, wert in kind.attrib.items():
                eintraege.append(Eintrag(IMAGE_ATTRIBUTE, name, wert, ort=hier))
        elif tag == "FITSKeyword":
            eintraege.append(
                Eintrag(
                    FITS_KEYWORD,
                    kind.get("name", ""),
                    kind.get("value"),
                    kind.get("comment", ""),
                    ort=ort,
                )
            )
            continue
        elif tag == "Property":
            wert = kind.get("value", kind.text)
            typ = kind.get("type", "")
            eintraege.append(
                Eintrag(
                    XISF_PROPERTY, kind.get("id", ""), wert, f"Typ {typ}" if typ else "", ort=ort
                )
            )
            continue
        _xisf_element(kind, hier, eintraege)


# -- Übersicht ------------------------------------------------------------------


def uebersicht(dateien: list[Datei]) -> list[dict]:
    zeilen = defaultdict(lambda: {"dateien": set(), "werte": []})
    for datei in dateien:
        for e in datei.eintraege:
            zeile = zeilen[(e.herkunft, e.schluessel)]
            zeile["dateien"].add(datei.pfad)
            if e.wert is not None and e.wert not in zeile["werte"]:
                zeile["werte"].append(e.wert)
            elif e.wert is None and e.kommentar and e.kommentar not in zeile["werte"]:
                zeile["werte"].append(e.kommentar)
    return [
        {
            "herkunft": herkunft,
            "schluessel": schluessel,
            "dateien": len(z["dateien"]),
            "verschiedene_werte": len(z["werte"]),
            "beispiele": z["werte"][:BEISPIELE],
        }
        for (herkunft, schluessel), z in sorted(
            zeilen.items(), key=lambda item: (-len(item[1]["dateien"]), item[0])
        )
    ]


# -- Ausgabe ----------------------------------------------------------------------


_STIL = """
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; margin: 1rem; }
table { border-collapse: collapse; margin: .5rem 0 1.5rem; font-size: .9rem; }
th, td { border: 1px solid #8884; padding: .2rem .5rem; text-align: left; vertical-align: top; }
th { background: #8882; }
.fehler { color: #c00; font-weight: bold; }
code { white-space: pre-wrap; }
details { margin: .5rem 0; }
"""


def _e(text) -> str:
    return html.escape("" if text is None else str(text))


def _tabelle_uebersicht(zeilen: list[dict]) -> str:
    kopf = "<tr><th>Herkunft</th><th>Schlüssel</th><th>Dateien</th><th>Werte</th>"
    kopf += "<th>Beispielwerte</th></tr>"
    reihen = "".join(
        f"<tr><td>{_e(z['herkunft'])}</td><td><code>{_e(z['schluessel'])}</code></td>"
        f"<td>{z['dateien']}</td><td>{z['verschiedene_werte']}</td>"
        f"<td>{'<br>'.join(f'<code>{_e(b)}</code>' for b in z['beispiele'])}</td></tr>"
        for z in zeilen
    )
    return f"<table>{kopf}{reihen}</table>"


def _tabelle_datei(datei: Datei) -> str:
    kopf = "<tr><th>Herkunft</th><th>HDU/Ort</th><th>Schlüssel</th><th>Wert</th>"
    kopf += "<th>Kommentar</th></tr>"
    reihen = "".join(
        f"<tr><td>{_e(e.herkunft)}</td><td>{_e(e.hdu if e.hdu is not None else e.ort)}</td>"
        f"<td><code>{_e(e.schluessel)}</code></td><td><code>{_e(e.wert)}</code></td>"
        f"<td>{_e(e.kommentar)}</td></tr>"
        for e in datei.eintraege
    )
    return f"<table>{kopf}{reihen}</table>"


def als_html(dateien: list[Datei]) -> str:
    teile = [
        "<!doctype html><html lang='de'><head><meta charset='utf-8'>",
        "<title>Header-Prototyp</title>",
        f"<style>{_STIL}</style></head><body>",
        "<h1>Header-Inhalt der Master</h1>",
        "<p>Prototyp (Issue #49): alle Einträge roh, getrennt nach Herkunft.</p>",
        f"<h2>Übersicht: alle {len(dateien)} Dateien</h2>",
        _tabelle_uebersicht(uebersicht(dateien)),
        "<h2>Übersicht je Erzeugerprogramm</h2>",
    ]
    gruppen = defaultdict(list)
    for datei in dateien:
        gruppen[datei.erzeuger or "(unbekannt)"].append(datei)
    for erzeuger, gruppe in sorted(gruppen.items()):
        teile.append(f"<details><summary>{_e(erzeuger)} – {len(gruppe)} Dateien</summary>")
        teile.append(_tabelle_uebersicht(uebersicht(gruppe)))
        teile.append("</details>")
    teile.append("<h2>Einzelansicht je Datei</h2>")
    for datei in dateien:
        teile.append(
            f"<details><summary><code>{_e(datei.pfad)}</code> – {_e(datei.format)}, "
            f"{len(datei.eintraege)} Einträge, Erzeuger {_e(datei.erzeuger or '(unbekannt)')}"
            "</summary>"
        )
        if datei.fehler:
            teile.append(f"<p class='fehler'>Fehler: {_e(datei.fehler)}</p>")
        teile.append(_tabelle_datei(datei))
        teile.append("</details>")
    teile.append("</body></html>")
    return "\n".join(teile)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Prototyp: Header von XISF/FITS anzeigen.")
    parser.add_argument("pfade", nargs="+", help="Dateien oder Ordner")
    parser.add_argument("--ausgabe", default=".", help="Ordner für header.html und header.json")
    args = parser.parse_args(argv)

    dateien = [lies(p) for p in finde(args.pfade)]
    ausgabe = Path(args.ausgabe)
    ausgabe.mkdir(parents=True, exist_ok=True)
    daten = {"dateien": [asdict(d) for d in dateien], "uebersicht": uebersicht(dateien)}
    (ausgabe / "header.json").write_text(
        json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ausgabe / "header.html").write_text(als_html(dateien), encoding="utf-8")
    fehler = sum(1 for d in dateien if d.fehler)
    print(f"{len(dateien)} Dateien gelesen, {fehler} mit Fehler → {ausgabe}", file=sys.stderr)


if __name__ == "__main__":
    main()
