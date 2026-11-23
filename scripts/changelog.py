"""Changelog aus Einzeldateien, damit parallele Branches nicht in CHANGELOG.md kollidieren.

Jede Änderung bekommt eine eigene Datei `changelog.d/<ticket>-<kurz>.md` (ohne Ticket:
`changelog.d/<kurz>.md`) mit ihrem Eintrag als Markdown-Liste („- …“). CHANGELOG.md enthält nur
Veröffentlichtes.

    uv run python scripts/changelog.py pruefen          # CI: Einträge stehen in changelog.d/
    uv run python scripts/changelog.py sammeln 0.2.0    # beim Release: als „## 0.2.0“ einfügen
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
FRAGMENTS = ROOT / "changelog.d"
UNRELEASED = "## Unveröffentlicht"


def fragments() -> list[Path]:
    def key(p: Path):
        m = re.match(r"(\d+)-", p.name)
        return (0, int(m[1]), p.name) if m else (1, 0, p.name)

    return sorted((p for p in FRAGMENTS.glob("*.md") if p.name != "README.md"), key=key)


def unreleased_body(text: str) -> str:
    start = text.index(UNRELEASED) + len(UNRELEASED)
    end = text.find("\n## ", start)
    return text[start : end if end != -1 else len(text)]


def pruefen() -> int:
    fehler = []
    if re.search(r"^- ", unreleased_body(CHANGELOG.read_text()), re.M):
        fehler.append(
            f"CHANGELOG.md: Einträge unter „{UNRELEASED}“ gehören nach "
            "changelog.d/<ticket>-<kurz>.md"
        )
    for p in fragments():
        if not p.read_text().startswith("- "):
            fehler.append(f"{p.relative_to(ROOT)}: muss mit „- “ beginnen (ein Listeneintrag)")
    for f in fehler:
        print(f)
    return 1 if fehler else 0


def sammeln(version: str) -> int:
    files = fragments()
    if not files:
        print("changelog.d/ ist leer, nichts zu sammeln.")
        return 1
    entries = "".join(p.read_text().rstrip("\n") + "\n" for p in files)
    text = CHANGELOG.read_text()
    body = unreleased_body(text)
    pos = text.index(UNRELEASED) + len(UNRELEASED) + len(body)
    text = text[:pos].rstrip("\n") + f"\n\n## {version}\n\n{entries}\n" + text[pos:].lstrip("\n")
    CHANGELOG.write_text(text)
    for p in files:
        p.unlink()
    print(f"{len(files)} Einträge als „## {version}“ in CHANGELOG.md übernommen.")
    return 0


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["pruefen"]:
            sys.exit(pruefen())
        case ["sammeln", version]:
            sys.exit(sammeln(version))
        case _:
            print(__doc__, file=sys.stderr)
            sys.exit(2)
