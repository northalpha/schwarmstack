"""Prüft GLOSSARY.md und Änderungen gegen das Glossar.

    uv run python scripts/glossar.py pruefen        # CI: jeder Begriff steht genau einmal
    uv run python scripts/glossar.py diff origin/main [--alle]
        # Review: gemiedene Wörter (_Avoid_) in den hinzugefügten Zeilen seit dem Merge-Base

`diff` meldet nur und endet immer mit 0: Ob ein Treffer ein Verstoß ist, entscheidet das Review.
Wörter mit Zusatz in Klammern („Admin (für die Person)“) sind nur in diesem Sinn gemieden; sie
werden nur gezählt, mit `--alle` einzeln mit ihrem Zusatz gemeldet. Verglichen wird mit Groß- und
Kleinschreibung, also trifft „Check“, nicht `check()`; englische Bezeichner im Code prüft das
Review selbst.
"""

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "GLOSSARY.md"
TERM = re.compile(r"^\*\*(?P<term>[^*]+)\*\*")
AVOID = re.compile(r"^_Avoid_:\s*(?P<words>.+)$")
# Nicht geprüft: das Glossar selbst (nennt die Wörter), mitgelieferter Code, generierte Dateien.
SKIP = re.compile(r"^(GLOSSARY\.md|uv\.lock|.*/vendor/.*|.*/migrations/.*)$")


def terms(text: str) -> list[str]:
    return [m["term"].strip() for line in text.splitlines() if (m := TERM.match(line))]


def avoided(text: str) -> list[tuple[str, str, str]]:
    """(Wort, Zusatz, Begriff) für jedes gemiedene Wort."""
    result, term = [], ""
    for line in text.splitlines():
        if m := TERM.match(line):
            term = m["term"].strip()
        elif m := AVOID.match(line):
            for entry in m["words"].split(","):
                word, _, note = entry.strip().partition("(")
                result.append((word.strip(), note.rstrip(") ").strip(), term))
    return result


def pruefen() -> int:
    doppelt = [t for t, n in Counter(terms(GLOSSARY.read_text())).items() if n > 1]
    for t in doppelt:
        print(f"GLOSSARY.md: Begriff „{t}“ steht mehrfach (nach einem Merge zusammenführen)")
    return 1 if doppelt else 0


def added_lines(base: str):
    out = subprocess.run(  # noqa: S603
        ["git", "diff", "--unified=0", "--no-color", f"{base}...HEAD"],  # noqa: S607
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    path, lineno = "", 0
    for line in out.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("@@"):
            lineno = int(re.search(r"\+(\d+)", line)[1])
        elif line.startswith("+") and path and not SKIP.match(path):
            yield path, lineno, line[1:]
            lineno += 1


def diff(base: str, alle: bool) -> int:
    words = [
        (re.compile(rf"(?<!\w){re.escape(w)}(?!\w)"), w, note, term)
        for w, note, term in avoided(GLOSSARY.read_text())
    ]
    treffer, im_sinn = 0, Counter()
    for path, lineno, text in added_lines(base):
        for rx, w, note, term in words:
            if not rx.search(text):
                continue
            if note and not alle:
                im_sinn[f"„{w}“ ({note})"] += 1
                continue
            treffer += 1
            sinn = f" ({note})" if note else ""
            print(f"{path}:{lineno}: „{w}“{sinn} gemieden, Begriff: {term}")
    print(f"{treffer} Treffer" if treffer else "Keine gemiedenen Wörter in den neuen Zeilen.")
    if im_sinn:
        liste = ", ".join(f"{w} {n}×" for w, n in im_sinn.most_common())
        print(f"Nur in einem Sinn gemieden, Bedeutung prüfen (--alle zeigt die Stellen): {liste}")
    return 0


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["pruefen"]:
            sys.exit(pruefen())
        case ["diff", base]:
            sys.exit(diff(base, alle=False))
        case ["diff", base, "--alle"]:
            sys.exit(diff(base, alle=True))
        case _:
            print(__doc__, file=sys.stderr)
            sys.exit(2)
