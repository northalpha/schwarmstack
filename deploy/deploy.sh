#!/usr/bin/env bash
# Deploy eines Images auf einen Host (ADR 0001). Läuft im Deploy-Job von GitHub Actions; alle
# Werte kommen als Umgebungsvariablen aus dem GitHub-Environment (docs/betrieb/deployment.md).
#
#   1. prüft, ob alle Pflichtwerte gesetzt sind, und bricht sonst mit klarer Meldung ab
#   2. schreibt die .env und kopiert sie mit compose.yaml und Caddyfile auf den Host
#   3. führt dort auf-dem-host.sh aus (Image holen, migrieren, starten, /healthz)
set -euo pipefail

cd "$(dirname "$0")"

PFLICHT=(
  DEPLOY_HOST SSH_PRIVATE_KEY SSH_KNOWN_HOSTS IMAGE_TAG REGISTRY_USER REGISTRY_TOKEN
  DOMAIN ADMIN_PATH DJANGO_SECRET_KEY S3_ENDPOINT_URL S3_BUCKET S3_REGION S3_ACCESS_KEY_ID
  S3_SECRET_ACCESS_KEY PRIVACY_CONTACT
  OPERATOR_NAME OPERATOR_ADDRESS HOSTER_NAME HOSTER_ADDRESS
)
# Werden nur in die .env geschrieben, wenn sie gesetzt sind.
OPTIONAL=(
  S3_ADDRESSING_STYLE UPLOAD_LINK_SECONDS HSTS_SECONDS LOG_LEVEL
  LOGIN_ATTEMPTS_MAX LOGIN_ATTEMPTS_WINDOW_SECONDS CONSENT_TEXT_VERSION
  COMMUNITY_ORIGINS COMMUNITY_CACHE_SECONDS
  OPERATOR_EMAILS EMAIL_HOST EMAIL_PORT EMAIL_HOST_USER EMAIL_HOST_PASSWORD EMAIL_USE_TLS
  DEFAULT_FROM_EMAIL
)

fehlend=()
for name in "${PFLICHT[@]}"; do
  [[ -n ${!name:-} ]] || fehlend+=("$name")
done
if [[ ${#fehlend[@]} -gt 0 ]]; then
  echo "::error::Im GitHub-Environment fehlen Pflichtwerte: ${fehlend[*]}" \
    "(Liste in docs/betrieb/deployment.md). Es gab keinen Deploy." >&2
  exit 1
fi
# boto3 nimmt einen Endpunkt ohne Schema nicht an; die App startete dann, aber /healthz schlug fehl.
if [[ ! $S3_ENDPOINT_URL =~ ^https?:// ]]; then
  echo "::error::S3_ENDPOINT_URL muss mit https:// beginnen (etwa" \
    "https://fsn1.your-objectstorage.com), ist aber '$S3_ENDPOINT_URL'. Es gab keinen Deploy." >&2
  exit 1
fi
if [[ -n ${BASIC_AUTH_USER:-} && -z ${BASIC_AUTH_HASH:-} ]] \
  || [[ -z ${BASIC_AUTH_USER:-} && -n ${BASIC_AUTH_HASH:-} ]]; then
  echo "::error::BASIC_AUTH_USER und BASIC_AUTH_HASH nur gemeinsam setzen." >&2
  exit 1
fi

arbeit=$(mktemp -d)
trap 'rm -rf "$arbeit"' EXIT
umask 077

# Compose liest Werte in einfachen Anführungszeichen wörtlich, auch das `$` im Passwort-Hash.
zeile() {
  local name=$1 wert=$2
  if [[ $wert == *"'"* || $wert == *$'\n'* ]]; then
    echo "::error::$name darf weder ' noch einen Zeilenumbruch enthalten." >&2
    exit 1
  fi
  printf "%s='%s'\n" "$name" "$wert"
}

{
  zeile IMAGE_TAG "$IMAGE_TAG"
  zeile DOMAIN "$DOMAIN"
  zeile ADMIN_PATH "$ADMIN_PATH"
  for name in PRIVACY_CONTACT OPERATOR_NAME OPERATOR_ADDRESS HOSTER_NAME HOSTER_ADDRESS; do
    zeile "$name" "${!name}"
  done
  zeile DJANGO_SECRET_KEY "$DJANGO_SECRET_KEY"
  zeile STORAGE_BACKEND s3
  for name in S3_ENDPOINT_URL S3_BUCKET S3_REGION S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
    zeile "$name" "${!name}"
  done
  for name in "${OPTIONAL[@]}"; do
    [[ -z ${!name:-} ]] || zeile "$name" "${!name}"
  done
  if [[ -n ${BASIC_AUTH_USER:-} ]]; then
    zeile BASIC_AUTH an
    zeile BASIC_AUTH_USER "$BASIC_AUTH_USER"
    zeile BASIC_AUTH_HASH "$BASIC_AUTH_HASH"
  else
    zeile BASIC_AUTH aus
  fi
} > "$arbeit/.env"

printf '%s\n' "$SSH_PRIVATE_KEY" > "$arbeit/schluessel"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$arbeit/known_hosts"
ssh_optionen=(
  -i "$arbeit/schluessel" -o IdentitiesOnly=yes
  -o UserKnownHostsFile="$arbeit/known_hosts" -o StrictHostKeyChecking=yes
  -o BatchMode=yes -o ConnectTimeout=20
)
ziel="deploy@$DEPLOY_HOST"

# Neue Dateien zuerst daneben ablegen; auf-dem-host.sh tauscht sie erst nach der Migration ein.
ssh "${ssh_optionen[@]}" "$ziel" 'mkdir -p /opt/schwarmstack/neu' </dev/null
scp -q "${ssh_optionen[@]}" compose.yaml Caddyfile auf-dem-host.sh "$arbeit/.env" \
  "$ziel:/opt/schwarmstack/neu/"

# Der Token geht über stdin, nie über die Kommandozeile des Hosts.
# shellcheck disable=SC2029  # Werte werden hier mit %q für die Gegenseite maskiert.
printf '%s\n' "$REGISTRY_TOKEN" | ssh "${ssh_optionen[@]}" "$ziel" \
  "bash /opt/schwarmstack/neu/auf-dem-host.sh $(printf '%q ' "$IMAGE_TAG" "$DOMAIN" "$REGISTRY_USER")"
