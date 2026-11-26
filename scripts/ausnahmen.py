"""Ausnahmen für Sicherheitsfunde (pip-audit, Trivy) aus `sicherheit-ausnahmen.toml`.

Jeder Eintrag braucht `id` (z. B. CVE oder GHSA), `grund` und `bis` (Ablaufdatum). Abgelaufene
Einträge lassen die Prüfung scheitern und gelten nicht mehr, der Fund erscheint dann wieder.

    uv run python scripts/ausnahmen.py pruefen   # Pflichtfelder, Doppelte, Ablauf
    uv run python scripts/ausnahmen.py ids       # aktive IDs, eine je Zeile (für die Scanner)
"""

import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATEI = ROOT / "sicherheit-ausnahmen.toml"


def laden(text: str) -> list[dict]:
    return tomllib.loads(text).get("ausnahme", [])


def _name(eintrag: dict, nr: int) -> str:
    return f"Ausnahme {nr} ({eintrag.get('id') or 'ohne id'})"


def _abgelaufen(eintrag: dict, heute: date) -> bool:
    bis = eintrag.get("bis")
    return isinstance(bis, date) and bis < heute


def pruefen(eintraege: list[dict], heute: date) -> list[str]:
    fehler = []
    gesehen = set()
    for nr, e in enumerate(eintraege, 1):
        name = _name(e, nr)
        for feld in ("id", "grund"):
            if not str(e.get(feld, "")).strip():
                fehler.append(f"{name}: {feld} fehlt")
        if "bis" not in e:
            fehler.append(f"{name}: bis fehlt (Ablaufdatum, z. B. 2027-03-01)")
        elif not isinstance(e["bis"], date):
            fehler.append(f"{name}: bis muss ein Datum sein, nicht {e['bis']!r}")
        elif _abgelaufen(e, heute):
            fehler.append(f"{name}: abgelaufen am {e['bis']}; beheben oder begründet verlängern")
        kennung = str(e.get("id", "")).strip()
        if kennung and kennung in gesehen:
            fehler.append(f"{name}: id doppelt")
        gesehen.add(kennung)
    return fehler


def aktive_ids(eintraege: list[dict], heute: date) -> list[str]:
    return [
        e["id"]
        for e in eintraege
        if str(e.get("id", "")).strip()
        and isinstance(e.get("bis"), date)
        and not _abgelaufen(e, heute)
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("pruefen", "ids"):
        print(__doc__)
        return 2
    eintraege = laden(DATEI.read_text())
    if argv[0] == "ids":
        print("\n".join(aktive_ids(eintraege, date.today())))
        return 0
    fehler = pruefen(eintraege, date.today())
    for f in fehler:
        print(f"{DATEI.name}: {f}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
