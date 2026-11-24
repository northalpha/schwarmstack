#!/usr/bin/env bash
# Teil des Deploys, der als `deploy` auf dem Host läuft; ausrollen.sh kopiert das Skript per SSH.
#
#   auf-dem-host.sh <image-tag> <domain> <registry-benutzer>   (Registry-Token auf stdin)
#
# Schlagen Bucket-Einrichtung oder Migration fehl, bleiben die alten Dateien und die alte
# Version laufen.
set -euo pipefail

IMAGE_TAG=${1:?Image-Tag fehlt}
DOMAIN=${2:?Domain fehlt}
REGISTRY_USER=${3:?Registry-Benutzer fehlt}
IFS= read -r REGISTRY_TOKEN
# Danach liest nichts mehr von stdin (docker compose run würde sonst darauf warten).
exec </dev/null
IMAGE=ghcr.io/northalpha/schwarmstack:$IMAGE_TAG
DATEIEN=(compose.yaml Caddyfile .env)

cd /opt/schwarmstack

echo "Image $IMAGE holen"
docker login ghcr.io --username "$REGISTRY_USER" --password-stdin <<<"$REGISTRY_TOKEN" >/dev/null
# Kein dauerhafter Zugang zur Registry auf dem Host, auch nicht bei einem Fehler beim Holen.
trap 'docker logout ghcr.io >/dev/null' EXIT
docker pull --quiet "$IMAGE"
docker logout ghcr.io >/dev/null
trap - EXIT

echo "Neue Konfiguration übernehmen"
mkdir -p vorher
for datei in "${DATEIEN[@]}"; do
  if [[ -f $datei ]]; then cp -p "$datei" vorher/; fi
  mv "neu/$datei" "$datei"
done
rm -f neu/auf-dem-host.sh

zuruecklegen() {
  for datei in "${DATEIEN[@]}"; do
    if [[ -f vorher/$datei ]]; then cp -p "vorher/$datei" "$datei"; fi
  done
}

# CORS für genau diese Domain (der Befehl wandelt Umlaut-Domains in Punycode um) und danach ein
# CORS-Preflight wie im Browser: Ohne passende Freigabe scheitert jeder Upload im Browser.
echo "Bucket einrichten und CORS prüfen"
if ! docker compose run --rm --no-deps app \
  python manage.py s3_bucket_setup --origin "https://$DOMAIN"; then
  zuruecklegen
  echo "::error::Bucket-Einrichtung oder CORS-Prüfung fehlgeschlagen, die bisherige Version" \
    "läuft weiter." >&2
  exit 1
fi

echo "Migrieren"
if ! docker compose run --rm --no-deps app python manage.py migrate --noinput; then
  zuruecklegen
  echo "::error::Migration fehlgeschlagen, die bisherige Version läuft weiter." >&2
  exit 1
fi

echo "Starten"
docker compose up --detach --remove-orphans

echo "Auf https://$DOMAIN/healthz warten"
ende=$((SECONDS + 60))
while ((SECONDS < ende)); do
  if curl -fsS --max-time 5 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/healthz" \
    >/dev/null 2>&1; then
    echo "$IMAGE läuft."
    docker image prune --force >/dev/null
    exit 0
  fi
  sleep 2
done
echo "::error::/healthz hat nach 60 s nicht mit ok geantwortet." >&2
docker compose ps
docker compose logs --tail 50 app
exit 1
