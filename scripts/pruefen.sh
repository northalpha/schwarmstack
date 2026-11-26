#!/usr/bin/env bash
# Alle Prüfungen wie in CI, in derselben Reihenfolge; CI ruft genau dieses Skript auf.
#
#   scripts/pruefen.sh            # alles, mit Garage (S3) und E2E-Test
#   scripts/pruefen.sh --schnell  # ohne Garage: S3- und Browser-Tests werden übersprungen
#   scripts/pruefen.sh -- -k admin   # alles nach "--" geht an pytest
#
# Braucht Docker für Garage und Chromium für Playwright (in CI vorher installiert).
set -euo pipefail
cd "$(dirname "$0")/.."

schnell=
pytest_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --schnell) schnell=1 ;;
    --) shift; pytest_args=("$@"); break ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

schritt() { echo "==> $*"; }

# Cloud-Container setzen noch den alten Namen; uv warnt sonst bei jedem Aufruf.
if [[ -n ${UV_NATIVE_TLS:-} ]]; then
  export UV_SYSTEM_CERTS=$UV_NATIVE_TLS
  unset UV_NATIVE_TLS
fi

schritt ruff check
uv run ruff check .
schritt ruff format --check
uv run ruff format --check .
schritt shellcheck
uv run shellcheck deploy/*.sh deploy/self-hosting/*.sh scripts/*.sh
schritt actionlint
uv run actionlint .github/workflows/*.yml
schritt zizmor
# In GitHub Actions prüft zizmor auch gepinnte Commits gegen GitHub (mit GITHUB_TOKEN), lokal offline.
if [[ -n ${GITHUB_ACTIONS:-} && -n ${GITHUB_TOKEN:-} ]]; then
  uv run zizmor --min-severity medium .github/workflows
else
  uv run zizmor --offline --min-severity medium .github/workflows
fi
schritt Sicherheitsausnahmen
uv run python scripts/ausnahmen.py pruefen
schritt pip-audit
# Bekannte Schwachstellen in den gesperrten Paketen (uv.lock); Ausnahmen aus sicherheit-ausnahmen.toml.
audit_args=()
while IFS= read -r id; do
  [[ -n $id ]] && audit_args+=(--ignore-vuln "$id")
done < <(uv run python scripts/ausnahmen.py ids)
uv export --frozen --no-emit-project --format requirements-txt --quiet \
  | uv run pip-audit --disable-pip --no-deps --progress-spinner off "${audit_args[@]}" -r /dev/stdin
schritt "Django check --deploy"
# Wie in Produktion (DEBUG aus, HSTS an); jede Warnung lässt die Prüfung scheitern. Begründete
# Ausnahmen stehen als SILENCED_SYSTEM_CHECKS in den Settings.
DJANGO_SECRET_KEY="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  ADMIN_PATH=pruefung ALLOWED_HOSTS=example.org HSTS_SECONDS=31536000 \
  PRIVACY_CONTACT=datenschutz@example.org OPERATOR_NAME=DZVF OPERATOR_ADDRESS=Beispielstrasse \
  HOSTER_NAME=Hoster HOSTER_ADDRESS=Hosterweg DATA_DIR="$(mktemp -d)" \
  uv run python src/manage.py check --deploy --fail-level WARNING
schritt Glossar und Changelog
uv run python scripts/glossar.py pruefen
uv run python scripts/changelog.py pruefen
schritt Migrationen vollständig
DEBUG=1 DATA_DIR="$(mktemp -d)" uv run python src/manage.py makemigrations --check --dry-run

if [[ -n $schnell ]]; then
  schritt "pytest (ohne Garage)"
  uv run pytest -q "${pytest_args[@]}"
  exit 0
fi

schritt Garage starten
if ! docker info >/dev/null 2>&1; then
  echo "Docker antwortet nicht. Daemon starten (in der Cloud-Sitzung: dockerd &>/tmp/dockerd.log &)" >&2
  echo "oder ohne Garage prüfen: scripts/pruefen.sh --schnell" >&2
  exit 1
fi
# Cloud-Sitzungen haben ein vorinstalliertes Chromium, das nicht zur Playwright-Version passt.
if [[ -z ${PLAYWRIGHT_CHROMIUM_EXECUTABLE:-} && -x /opt/pw-browsers/chromium ]]; then
  export PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium
fi
trap 'scripts/garage.sh stop || true' EXIT
garage_env=$(scripts/garage.sh start)
while IFS='=' read -r name wert; do
  export "$name=$wert"
done <<<"$garage_env"
schritt "pytest (mit Garage und Browser)"
REQUIRE_GARAGE=1 uv run pytest -q "${pytest_args[@]}"
