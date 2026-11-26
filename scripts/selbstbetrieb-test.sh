#!/usr/bin/env bash
# Installer-Test für den Selbstbetrieb (ADR 0011, CI-Job „selbstbetrieb“, Ticket #105).
#
#   scripts/selbstbetrieb-test.sh              # Image bauen, setup.sh --lokal zweimal laufen lassen
#   IMAGE=name:tag scripts/selbstbetrieb-test.sh   # ein schon gebautes Image nehmen
#
# Läuft in einer Kopie von deploy/selbst/ in einem Wegwerf-Ordner und fasst das Repo nicht an.
# Prüft: /healthz antwortet mit ok, der Bucket ist eingerichtet, CORS besteht den Preflight wie
# im Browser, und ein zweiter Lauf von setup.sh ändert .env, garage.toml und die Datenbank nicht.
# Braucht Docker und freie Ports 80 und 443. Ein vollständiger Upload-Test gehört nicht dazu.
set -euo pipefail
cd "$(dirname "$0")/.."
wurzel=$PWD

fehler() { echo "Fehler: $*" >&2; exit 1; }
schritt() { echo "==> $*"; }

docker info >/dev/null 2>&1 || fehler "Docker antwortet nicht."

if [[ -z ${IMAGE:-} ]]; then
  IMAGE=schwarmstack-selbstbetrieb-test
  schritt "Image bauen"
  docker build --tag "$IMAGE:test" .
fi
export IMAGE IMAGE_TAG=${IMAGE_TAG:-test}

arbeit=$(mktemp -d)
mkdir -p "$arbeit/deploy"
cp "$wurzel/pyproject.toml" "$arbeit/"
cp -r "$wurzel/deploy/selbst" "$arbeit/deploy/selbst"
rm -rf "$arbeit/deploy/selbst/data" "$arbeit/deploy/selbst/.env"
selbst=$arbeit/deploy/selbst

aufraeumen() {
  status=$?
  if [[ $status -ne 0 && -f $selbst/.env ]]; then
    (cd "$selbst" && docker compose ps -a && docker compose logs --tail 60) >&2 || true
  fi
  (cd "$selbst" && docker compose down --volumes --remove-orphans) >/dev/null 2>&1 || true
  # data/ gehört nach dem Lauf dem Benutzer im Image.
  docker run --rm --user root --entrypoint rm --volume "$arbeit:/arbeit" \
    "$IMAGE:$IMAGE_TAG" -rf /arbeit/deploy/selbst/data >/dev/null 2>&1 || true
  rm -rf "$arbeit"
  exit "$status"
}
trap aufraeumen EXIT

lauf() {
  # Ohne Rückfragen: kein Terminal, alle Angaben haben im Probemodus Standardwerte.
  (cd "$selbst" && ./setup.sh --lokal </dev/null)
}

schritt "Erster Lauf von setup.sh --lokal"
lauf

pruefen() {
  local healthz
  healthz=$(curl -fsS --max-time 10 http://localhost/healthz)
  [[ $healthz == ok ]] || fehler "/healthz antwortet '$healthz' statt 'ok'."

  # Bucket und CORS: setup.sh hat den Preflight schon über den Befehl geprüft. Hier fragt der
  # Test den Speicher noch einmal von außen über Caddy, wie der Browser, mit dem Namen s3.localhost.
  local bucket
  bucket=$(sed -n "s/^S3_BUCKET='\(.*\)'\$/\1/p" "$selbst/.env")
  [[ -n $bucket ]] || fehler "S3_BUCKET fehlt in der .env."
  local methode kopf
  for methode in POST PUT GET DELETE; do
    kopf=$(curl -sS --max-time 10 --include --request OPTIONS \
      --resolve s3.localhost:80:127.0.0.1 \
      --header "Origin: http://localhost" \
      --header "Access-Control-Request-Method: $methode" \
      --header "Access-Control-Request-Headers: content-type" \
      "http://s3.localhost/$bucket/cors-pruefung")
    grep -qi '^HTTP/[0-9.]* 200' <<<"$kopf" || fehler "Preflight $methode: $(head -n1 <<<"$kopf")"
    grep -qi '^access-control-allow-origin: http://localhost' <<<"$kopf" \
      || fehler "Preflight $methode: Access-Control-Allow-Origin fehlt oder passt nicht."
  done
  # Eine fremde Herkunft darf nicht durchkommen (Garage antwortet 403).
  local status
  status=$(curl -sS --max-time 10 --output /dev/null --write-out '%{http_code}' --request OPTIONS \
    --resolve s3.localhost:80:127.0.0.1 \
    --header "Origin: http://fremd.example" \
    --header "Access-Control-Request-Method: PUT" \
    "http://s3.localhost/$bucket/cors-pruefung")
  [[ $status == 403 ]] || fehler "Preflight einer fremden Herkunft: HTTP $status statt 403."

  # Der Bucket existiert und der Schlüssel der App darf ihn lesen.
  (cd "$selbst" && docker compose exec -T app python manage.py shell -c \
    "from storage import get_storage; get_storage().client.head_bucket(Bucket=get_storage().bucket); print('bucket-ok')" \
    </dev/null | tail -n 1) | grep -qx bucket-ok || fehler "Bucket '$bucket' ist nicht erreichbar."
}

schritt "Prüfen: /healthz, Bucket, CORS-Preflight"
pruefen

zustand() {
  # Was ein zweiter Lauf nicht ändern darf: Geheimnisse und Einstellungen, Garage-Einrichtung,
  # und dass Aktion und Betreiber-Konto nicht ein zweites Mal entstehen.
  (cd "$selbst" && sha256sum .env data/garage/garage.toml)
  (cd "$selbst" && docker compose exec -T app python manage.py shell -c \
    "from django.contrib.auth import get_user_model as g; from submissions.models import Campaign; print('konten', g().objects.count(), 'aktionen', Campaign.objects.count())" \
    </dev/null | tail -n 1)
  (cd "$selbst" && docker compose exec -T -e RUST_LOG=warn garage /garage bucket list </dev/null | awk 'NR>1 {print $NF}' | sort)
}

schritt "Zustand nach dem ersten Lauf merken"
vorher=$(zustand)
echo "$vorher"
[[ $vorher == *"konten 1 aktionen 1"* ]] || fehler "Nach dem ersten Lauf: erwartet ein Konto und eine Aktion."

schritt "Zweiter Lauf von setup.sh --lokal"
zweiter=$(lauf)
echo "$zweiter" | tail -n 8
if grep -q "Passwort:" <<<"$zweiter"; then
  fehler "Der zweite Lauf hat ein neues Betreiber-Konto angelegt."
fi

schritt "Zweiter Lauf hat nichts Unnötiges geändert"
nachher=$(zustand)
if [[ $vorher != "$nachher" ]]; then
  diff <(echo "$vorher") <(echo "$nachher") >&2 || true
  fehler "Der zweite Lauf hat Geheimnisse, Einrichtung oder Daten geändert."
fi
pruefen

schritt "Installer-Test bestanden"
