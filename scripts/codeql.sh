#!/usr/bin/env bash
# CodeQL lokal, mit denselben Abfragen wie der CodeQL-Job in CI (Code-Scanning-Suite).
#
#   scripts/codeql.sh            # Funde außerhalb von codeql-ausnahmen.toml lassen die Prüfung scheitern
#
# Lädt beim ersten Lauf das CodeQL-Bündel (ca. 700 MB) in ~/.cache/schwarmstack; danach dauert der
# Lauf etwa 20 Sekunden. Gefunden werden z. B. Regex-Muster mit polynomialer Laufzeit (ReDoS).
set -euo pipefail
cd "$(dirname "$0")/.."

version=2.27.6
cache=${XDG_CACHE_HOME:-$HOME/.cache}/schwarmstack/codeql-$version
if [[ ! -x $cache/codeql/codeql ]]; then
  echo "Lade CodeQL $version nach $cache (einmalig)" >&2
  mkdir -p "$cache"
  curl -fsSL "https://github.com/github/codeql-action/releases/download/codeql-bundle-v$version/codeql-bundle-linux64.tar.gz" \
    | tar xz -C "$cache"
fi

arbeit=$(mktemp -d)
trap 'rm -rf "$arbeit"' EXIT
codeql=$cache/codeql/codeql
"$codeql" database create "$arbeit/db" --language=python --source-root=. -q >/dev/null 2>&1
"$codeql" database analyze "$arbeit/db" codeql/python-queries:codeql-suites/python-code-scanning.qls \
  --format=sarif-latest --output="$arbeit/ergebnis.sarif" -q >/dev/null 2>&1
python3 - "$arbeit/ergebnis.sarif" <<'PY'
import json
import sys
import tomllib
from pathlib import Path

ausnahmen = tomllib.loads(Path("codeql-ausnahmen.toml").read_text()).get("ausnahme", [])
erlaubt = set()
for eintrag in ausnahmen:
    if not eintrag.get("grund", "").strip():
        sys.exit(f"codeql-ausnahmen.toml: {eintrag.get('regel')} ohne Begründung")
    erlaubt.add((eintrag["regel"], eintrag["datei"]))

offen = []
for lauf in json.load(open(sys.argv[1]))["runs"]:
    for fund in lauf["results"]:
        ort = fund["locations"][0]["physicalLocation"]
        datei, zeile = ort["artifactLocation"]["uri"], ort["region"]["startLine"]
        if (fund["ruleId"], datei) not in erlaubt:
            offen.append(f"{datei}:{zeile}: {fund['ruleId']}: {fund['message']['text'].splitlines()[0]}")
for zeile in sorted(offen):
    print(zeile)
print(f"{len(offen)} offene CodeQL-Funde" if offen else "Keine offenen CodeQL-Funde.")
sys.exit(1 if offen else 0)
PY
