"""Hilfen für Release-Skill und Release-Workflow (ADR 0011).

    uv run python scripts/release.py pruefen 0.2.0     # Version gültig, größer als der letzte Tag
    uv run python scripts/release.py version 0.2.0     # `version` in pyproject.toml setzen
    uv run python scripts/release.py erkennen          # CI: ist der Commit ein Release-Commit?
    uv run python scripts/release.py text 0.2.0        # CI: Abschnitt „## 0.2.0“ aus CHANGELOG.md

`erkennen` schreibt `release`, `version` und `tags` nach $GITHUB_OUTPUT (sonst auf stdout).
Die Tags kommen aus `git tag`; der Checkout braucht sie (`fetch-depth: 0` oder `fetch-tags`).
"""

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
# Stand vor dem ersten Release v0.2.0: Die alten Tags sind gelöscht, 0.1.0 ist kein Release.
AUSGANG = (0, 1, 0)


class ReleaseFehler(Exception):
    pass


def parse(version: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        raise ReleaseFehler(f"Version „{version}“ muss die Form X.Y.Z haben (ohne „v“).")
    return int(m[1]), int(m[2]), int(m[3])


def letzte_version(tags: list[str]) -> tuple[int, int, int]:
    """Höchste Version unter den Tags `vX.Y.Z`; ohne Tag der Ausgangsstand."""
    versionen = [parse(t[1:]) for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    return max(versionen, default=AUSGANG)


def ist_release(version: str, tags: list[str]) -> bool:
    return parse(version) > letzte_version(tags)


def pruefe_version(version: str, tags: list[str]) -> None:
    if not ist_release(version, tags):
        letzte = ".".join(map(str, letzte_version(tags)))
        raise ReleaseFehler(f"Version {version} ist nicht größer als der letzte Release {letzte}.")


def image_tags(version: str) -> list[str]:
    x, y, z = parse(version)
    return [f"v{x}.{y}.{z}", f"v{x}.{y}"]


def setze_version(pyproject: Path, version: str) -> None:
    parse(version)
    text = pyproject.read_text()
    neu, n = re.subn(r'^version = "[^"]*"$', f'version = "{version}"', text, count=1, flags=re.M)
    if n != 1:
        raise ReleaseFehler('pyproject.toml: Zeile `version = "…"` nicht gefunden.')
    pyproject.write_text(neu)


def release_text(changelog: str, version: str) -> str:
    m = re.search(rf"^## {re.escape(version)}\n(.*?)(?=^## |\Z)", changelog, re.M | re.S)
    if not m or not m[1].strip():
        raise ReleaseFehler(f"CHANGELOG.md hat keinen Abschnitt „## {version}“ mit Einträgen.")
    return m[1].strip("\n") + "\n"


def git_tags() -> list[str]:
    out = subprocess.run(  # noqa: S603
        ["git", "tag", "--list"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return out.stdout.split()


def projekt_version() -> str:
    return tomllib.loads(PYPROJECT.read_text())["project"]["version"]


def ausgeben(werte: dict[str, str]) -> None:
    zeilen = "".join(f"{k}={v}\n" for k, v in werte.items())
    ziel = os.environ.get("GITHUB_OUTPUT")
    if ziel:
        with open(ziel, "a") as f:
            f.write(zeilen)
    print(zeilen, end="")


def main(argv: list[str]) -> int:
    try:
        match argv:
            case ["pruefen", version]:
                pruefe_version(version, git_tags())
            case ["version", version]:
                setze_version(PYPROJECT, version)
            case ["erkennen"]:
                version = projekt_version()
                ist = ist_release(version, git_tags())
                if ist:  # fehlt der Abschnitt, scheitert der Lauf hier, nicht erst nach dem Image
                    release_text(CHANGELOG.read_text(), version)
                ausgeben(
                    {
                        "release": str(ist).lower(),
                        "version": version,
                        "tags": " ".join(image_tags(version)),
                    }
                )
            case ["text", version]:
                print(release_text(CHANGELOG.read_text(), version), end="")
            case _:
                print(__doc__, file=sys.stderr)
                return 2
    except ReleaseFehler as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
