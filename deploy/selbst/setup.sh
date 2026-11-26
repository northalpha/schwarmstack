#!/usr/bin/env bash
# Richtet Schwarmstack für den Selbstbetrieb ein und startet es (ADR 0011).
#
#   git clone --branch vX.Y.Z <repo> && cd schwarmstack/deploy/selbst && ./setup.sh
#   ./setup.sh --lokal    # Probemodus auf localhost, ohne Zertifikat, nur zum Ausprobieren
#
# Das Skript fragt, was es nicht schon weiß, erzeugt alle Geheimnisse selbst und schreibt die
# .env. Es läuft auch ohne Rückfragen, wenn alle Werte als Umgebungsvariablen gesetzt sind
# (Liste in .env.example), und lässt sich beliebig oft wiederholen: Geheimnisse, Daten, Aktion
# und Betreiber-Konto bleiben, wie sie sind. Ein Versionswechsel ist
# `git fetch --tags && git checkout vX.Y.Z && ./setup.sh`.
#
# Nur für Entwicklung und den Installer-Test der CI:
#   IMAGE_TAG=<tag>  nimmt dieses Image statt der Version aus pyproject.toml (kein Tag nötig)
#   IMAGE=<name>     nimmt ein anderes Image (z. B. ein lokal gebautes)
#   DNS_PRUEFEN=nein überspringt die Prüfung der DNS-Einträge
set -euo pipefail

cd "$(dirname "$0")"
wurzel=$(cd ../.. && pwd)

fehler() { echo "Fehler: $*" >&2; exit 1; }
schritt() { echo "==> $*"; }

lokal=
for arg in "$@"; do
  case "$arg" in
    --lokal) lokal=1 ;;
    -h | --hilfe | --help)
      sed -n '2,/^set -/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) fehler "Unbekannte Option: $arg (erlaubt: --lokal, --hilfe)" ;;
  esac
done

# --- Version ----------------------------------------------------------------------------------
version=$(sed -n '/^version = "/{s/^version = "\(.*\)"$/\1/;p;q}' "$wurzel/pyproject.toml")
[[ -n $version ]] || fehler "Keine Version in pyproject.toml gefunden."
if [[ -z ${IMAGE_TAG:-} ]]; then
  tag=$(git -C "$wurzel" describe --exact-match --tags HEAD 2>/dev/null || true)
  if [[ $tag != "v$version" ]]; then
    fehler "Dieser Stand ist kein Release (Tag ${tag:-keiner}, erwartet v$version). Für den main-Zweig" \
      "gibt es kein veröffentlichtes Image. Erst auf einen Release wechseln:" \
      "git fetch --tags && git checkout vX.Y.Z"
  fi
  IMAGE_TAG=v$version
fi

# --- .env lesen und Werte sammeln -------------------------------------------------------------
# Aus der .env stammt, was ein früherer Lauf schon festgelegt hat; eine gesetzte Umgebungs-
# variable geht vor.
alt() {
  [[ -f .env ]] || return 0
  sed -n "/^$1='/{s/^$1='\\(.*\\)'\$/\\1/;p;q}" .env
}

modus_alt=$(alt MODUS)
modus=betrieb
[[ -z $lokal ]] || modus=lokal
if [[ -n $modus_alt && $modus_alt != "$modus" ]]; then
  fehler "Die vorhandene .env ist für den Modus '$modus_alt' angelegt. Probemodus und echter" \
    "Betrieb lassen sich nicht mischen. Zum Neuanfang .env und data/ entfernen."
fi

fehlend=()
# frage NAME "Beschreibung" [Standardwert]: setzt die Variable aus Umgebung, .env, Eingabe
# oder Standardwert; ohne Terminal und ohne Standardwert landet sie in der Liste der fehlenden.
frage() {
  local name=$1 text=$2 standard=${3-}
  if [[ -n ${!name+x} ]]; then return; fi
  local bisher
  bisher=$(alt "$name")
  if [[ -n $bisher ]]; then printf -v "$name" '%s' "$bisher"; return; fi
  if [[ -n $lokal && -n $standard ]]; then printf -v "$name" '%s' "$standard"; return; fi
  if [[ -t 0 ]]; then
    local antwort
    read -r -p "$text${standard:+ [$standard]}: " antwort
    antwort=${antwort:-$standard}
    if [[ -n $antwort ]]; then printf -v "$name" '%s' "$antwort"; return; fi
  elif [[ -n $standard ]]; then
    printf -v "$name" '%s' "$standard"
    return
  fi
  fehlend+=("$name ($text)")
}

if [[ -n $lokal ]]; then
  DOMAIN=localhost
  PUBLIC_ORIGIN=http://localhost
  SCHEMA=http://
  S3_ENDPOINT_URL=http://s3.localhost
  SUBMISSION_COOKIE_SECURE=0
else
  frage DOMAIN "Domain der Teilnahmeseite, z. B. upload.example.org"
  [[ -z ${DOMAIN:-} ]] || PUBLIC_ORIGIN=https://$DOMAIN
  SCHEMA=
  [[ -z ${DOMAIN:-} ]] || S3_ENDPOINT_URL=https://s3.$DOMAIN
fi
# Standardwerte gibt es nur im Probemodus; im echten Betrieb müssen die Angaben stimmen.
probe=${lokal:+Probe (nur zum Ausprobieren)}
probe_adresse=${lokal:+Musterstraße 1, 12345 Musterstadt}
probe_mail=${lokal:+probe@example.com}
frage OPERATOR_EMAILS "Mailadressen der Betreiber für Betriebsmeldungen (mit Komma getrennt)" "$probe_mail"
frage OPERATOR_NAME "Verantwortliche Stelle (Name)" "$probe"
frage OPERATOR_ADDRESS "Verantwortliche Stelle (Anschrift)" "$probe_adresse"
frage HOSTER_NAME "Hoster (Name)" "$probe"
frage HOSTER_ADDRESS "Hoster (Anschrift)" "$probe_adresse"
frage PRIVACY_CONTACT "Kontakt für Datenschutzanfragen (Mailadresse)" "$probe_mail"

if [[ ${#fehlend[@]} -gt 0 ]]; then
  echo "Fehler: Es fehlen Angaben. Als Umgebungsvariablen setzen oder im Terminal beantworten:" >&2
  printf '  %s\n' "${fehlend[@]}" >&2
  exit 1
fi

# --- Prüfungen vor dem Start --------------------------------------------------------------------
for name in DOMAIN OPERATOR_EMAILS OPERATOR_NAME OPERATOR_ADDRESS HOSTER_NAME HOSTER_ADDRESS \
  PRIVACY_CONTACT; do
  if [[ ${!name} == *"'"* || ${!name} == *$'\n'* ]]; then
    fehler "$name darf weder ' noch einen Zeilenumbruch enthalten."
  fi
done
if [[ ! $DOMAIN =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]]; then
  fehler "DOMAIN ist keine Domain ohne Schema und Pfad: '$DOMAIN'"
fi

if [[ -z $lokal && ${DNS_PRUEFEN:-ja} != nein ]]; then
  schritt "DNS prüfen"
  eigene=" $(hostname -I 2>/dev/null || true) "
  erste=${eigene# }
  erste=${erste%% *}
  problem=0
  for name in "$DOMAIN" "s3.$DOMAIN"; do
    adressen=$(getent ahosts "$name" 2>/dev/null | awk '{print $1}' | sort -u || true)
    if [[ -z $adressen ]]; then
      echo "  Es fehlt ein DNS-Eintrag: $name (A, ggf. AAAA) auf ${erste:-die Adresse dieses Servers}" >&2
      problem=1
      continue
    fi
    passt=0
    while read -r adresse; do
      [[ $eigene == *" $adresse "* ]] && passt=1
    done <<<"$adressen"
    if [[ $passt -eq 0 ]]; then
      echo "  $name zeigt auf $(echo "$adressen" | tr '\n' ' ')und nicht auf diesen Server" \
        "(${eigene# }). DNS-Eintrag ändern." >&2
      problem=1
    fi
  done
  if [[ $problem -ne 0 ]]; then
    fehler "Ohne beide DNS-Einträge bekommt Caddy kein Zertifikat. Danach ./setup.sh erneut" \
      "starten. Steht der Server hinter NAT oder einem Load Balancer: DNS_PRUEFEN=nein setzen."
  fi
fi

for programm in docker curl; do
  command -v "$programm" >/dev/null || fehler "$programm fehlt. Siehe docs/betrieb/selbstbetrieb.md."
done
docker compose version >/dev/null 2>&1 || fehler "Docker Compose (Plugin) fehlt."
docker info >/dev/null 2>&1 || fehler "Docker antwortet nicht. Läuft der Dienst, und darf dieser Benutzer ihn nutzen?"

# --- Geheimnisse -------------------------------------------------------------------------------
zufall() { od -An -tx1 -N"$1" /dev/urandom | tr -d ' \n'; }
geheimnis() {
  local name=$1 laenge=$2 vorsatz=${3-}
  if [[ -n ${!name+x} ]]; then return; fi
  local bisher
  bisher=$(alt "$name")
  if [[ -n $bisher ]]; then printf -v "$name" '%s' "$bisher"; else printf -v "$name" '%s' "$vorsatz$(zufall "$laenge")"; fi
}
geheimnis DJANGO_SECRET_KEY 32
geheimnis ADMIN_PATH 12
geheimnis GARAGE_RPC_SECRET 32
# Garage verlangt für Schlüssel-IDs "GK" und 24 Hexzeichen.
geheimnis S3_ACCESS_KEY_ID 12 GK
geheimnis S3_SECRET_ACCESS_KEY 32
S3_BUCKET=${S3_BUCKET:-$(alt S3_BUCKET)}
S3_BUCKET=${S3_BUCKET:-schwarmstack}

# --- Dateien schreiben --------------------------------------------------------------------------
umask 077
mkdir -p data/app data/garage/meta data/garage/data

ersetzen() { # ersetzen ZIEL TEMP: nur austauschen, wenn sich etwas ändert
  if [[ -f $1 ]] && cmp -s "$1" "$2"; then rm -f "$2"; else mv "$2" "$1"; fi
}

temp=$(mktemp -p data)
cat >"$temp" <<TOML
metadata_dir = "/var/lib/garage/meta"
data_dir = "/var/lib/garage/data"
db_engine = "sqlite"
replication_factor = 1
rpc_bind_addr = "0.0.0.0:3901"
rpc_public_addr = "127.0.0.1:3901"
rpc_secret = "$GARAGE_RPC_SECRET"

[s3_api]
s3_region = "garage"
api_bind_addr = "0.0.0.0:3900"
TOML
# Garage läuft im Container als root und muss die Datei lesen können.
chmod 644 "$temp"
ersetzen data/garage/garage.toml "$temp"

zeile() {
  # Compose liest Werte in einfachen Anführungszeichen wörtlich; ein ' würde die .env zerstören.
  if [[ $2 == *"'"* || $2 == *$'\n'* ]]; then
    rm -f "$temp"
    fehler "$1 darf weder ' noch einen Zeilenumbruch enthalten."
  fi
  printf "%s='%s'\n" "$1" "$2"
}
temp=$(mktemp -p data)
{
  zeile MODUS "$modus"
  zeile IMAGE_TAG "$IMAGE_TAG"
  [[ -z ${IMAGE:-} ]] || zeile IMAGE "$IMAGE"
  zeile DOMAIN "$DOMAIN"
  zeile PUBLIC_ORIGIN "$PUBLIC_ORIGIN"
  zeile SCHEMA "$SCHEMA"
  zeile OPERATOR_EMAILS "$OPERATOR_EMAILS"
  zeile OPERATOR_NAME "$OPERATOR_NAME"
  zeile OPERATOR_ADDRESS "$OPERATOR_ADDRESS"
  zeile HOSTER_NAME "$HOSTER_NAME"
  zeile HOSTER_ADDRESS "$HOSTER_ADDRESS"
  zeile PRIVACY_CONTACT "$PRIVACY_CONTACT"
  zeile DJANGO_SECRET_KEY "$DJANGO_SECRET_KEY"
  zeile ADMIN_PATH "$ADMIN_PATH"
  zeile GARAGE_RPC_SECRET "$GARAGE_RPC_SECRET"
  zeile STORAGE_BACKEND s3
  zeile S3_ENDPOINT_URL "$S3_ENDPOINT_URL"
  zeile S3_BUCKET "$S3_BUCKET"
  zeile S3_REGION garage
  zeile S3_ACCESS_KEY_ID "$S3_ACCESS_KEY_ID"
  zeile S3_SECRET_ACCESS_KEY "$S3_SECRET_ACCESS_KEY"
  zeile S3_ADDRESSING_STYLE path
  [[ -z ${SUBMISSION_COOKIE_SECURE:-} ]] || zeile SUBMISSION_COOKIE_SECURE "$SUBMISSION_COOKIE_SECURE"
  # Mail für Betriebsmeldungen: nur, was gesetzt ist (oder früher gesetzt war).
  for name in EMAIL_HOST EMAIL_PORT EMAIL_HOST_USER EMAIL_HOST_PASSWORD EMAIL_USE_TLS \
    DEFAULT_FROM_EMAIL; do
    wert=${!name-$(alt "$name")}
    [[ -z $wert ]] || zeile "$name" "$wert"
  done
} >"$temp"
ersetzen .env "$temp"

# --- Start -------------------------------------------------------------------------------------
dc() { docker compose "$@"; }
garage() { dc exec -T -e RUST_LOG=warn garage /garage "$@" </dev/null; }

schritt "Speicher (Garage) starten"
dc up --detach garage
for _ in $(seq 1 50); do
  garage status >/dev/null 2>&1 && break
  sleep 0.5
done
garage status >/dev/null 2>&1 || { dc logs --tail 30 garage >&2; fehler "Garage startet nicht."; }

schritt "Garage und Bucket einrichten"
if garage status | grep -q "NO ROLE ASSIGNED"; then
  knoten=$(garage node id -q | cut -d@ -f1)
  # Die Kapazität ist bei einem Knoten nur ein Gewicht, keine Grenze.
  garage layout assign -z dc1 -c 1G "$knoten" >/dev/null
  garage layout apply --version 1 >/dev/null
fi
if ! garage key info "$S3_ACCESS_KEY_ID" >/dev/null 2>&1; then
  garage key import --yes -n schwarmstack "$S3_ACCESS_KEY_ID" "$S3_SECRET_ACCESS_KEY" >/dev/null
fi
garage bucket info "$S3_BUCKET" >/dev/null 2>&1 || garage bucket create "$S3_BUCKET" >/dev/null
garage bucket allow --read --write --owner "$S3_BUCKET" --key "$S3_ACCESS_KEY_ID" >/dev/null

schritt "Datenbank vorbereiten"
# Der Datenordner gehört dem Benutzer im Image, nicht dem, der setup.sh aufruft.
dc run --rm --no-deps --user root --entrypoint chown app -R 10001:10001 /data
dc run --rm --no-deps app python manage.py migrate --noinput >/dev/null

schritt "Alles starten"
dc up --detach --remove-orphans

if [[ -n $lokal ]]; then
  healthz=http://localhost/healthz
else
  healthz=https://$DOMAIN/healthz
fi
schritt "Auf $healthz warten (beim ersten Start holt Caddy erst die Zertifikate)"
bereit=
for _ in $(seq 1 60); do
  if [[ $(curl -fsS --max-time 5 "$healthz" 2>/dev/null || true) == ok ]]; then bereit=1; break; fi
  sleep 2
done
if [[ -z $bereit ]]; then
  dc ps >&2
  dc logs --tail 40 app caddy garage >&2
  fehler "$healthz antwortet nach 120 s nicht mit ok."
fi

schritt "CORS im Bucket einrichten und wie im Browser prüfen"
dc exec -T app python manage.py s3_bucket_setup --origin "$PUBLIC_ORIGIN" </dev/null

# --- Betreiber-Konto und Aktion ----------------------------------------------------------------
manage() { dc exec -T app python manage.py "$@" </dev/null; }
# Django 5 schreibt beim Start der Shell eine Zeile zu automatisch importierten Objekten davor.
django() { manage shell -c "$1" | tail -n 1; }

neues_passwort=
if [[ $(django "from django.contrib.auth import get_user_model as g; print(g().objects.filter(is_superuser=True).exists())") != True ]]; then
  schritt "Betreiber-Konto anlegen"
  frage ADMIN_USER "Benutzername des ersten Betreibers" betreiber
  frage ADMIN_EMAIL "Mailadresse des ersten Betreibers" "${OPERATOR_EMAILS%%,*}"
  if [[ ${#fehlend[@]} -gt 0 ]]; then fehler "Es fehlen Angaben: ${fehlend[*]}"; fi
  neues_passwort=$(zufall 12)
  dc exec -T -e DJANGO_SUPERUSER_PASSWORD="$neues_passwort" app \
    python manage.py createsuperuser --noinput --username "$ADMIN_USER" --email "$ADMIN_EMAIL" </dev/null >/dev/null
fi

if [[ $(django "from submissions.models import Campaign; print(Campaign.current() is not None)") != True ]]; then
  schritt "Aktion anlegen"
  jetzt=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
  in30=$(date -u -d "+30 days" +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null || date -u -v+30d +%Y-%m-%dT%H:%M:%S+00:00)
  fehlend=()
  frage AKTION_OBJEKT "Objekt der Aktion, z. B. M 101" "M 101"
  frage AKTION_START "Beginn (ISO 8601 mit Zeitzone)" "$jetzt"
  frage AKTION_ENDE "Ende (ISO 8601 mit Zeitzone)" "$in30"
  frage AKTION_QUOTE_GIB "Quote je Submission in GiB" 5
  frage AKTION_GESAMTGRENZE_GIB "Gesamtgrenze aller Master in GiB" 100
  if [[ ${#fehlend[@]} -gt 0 ]]; then
    printf 'Fehler: Es fehlen Angaben: %s\n' "${fehlend[*]}" >&2
    exit 1
  fi
  manage campaign --object "$AKTION_OBJEKT" --starts-at "$AKTION_START" --ends-at "$AKTION_ENDE" \
    --quota-gib "$AKTION_QUOTE_GIB" --global-cap-gib "$AKTION_GESAMTGRENZE_GIB"
fi

# --- Ergebnis ----------------------------------------------------------------------------------
echo
echo "Schwarmstack $IMAGE_TAG läuft."
echo "  Teilnahmeseite: $PUBLIC_ORIGIN/"
echo "  Admin:          $PUBLIC_ORIGIN/$ADMIN_PATH/"
echo "  Speicher:       $S3_ENDPOINT_URL (Bucket $S3_BUCKET)"
if [[ -n $neues_passwort ]]; then
  echo
  echo "Erstes Betreiber-Konto: $ADMIN_USER, Passwort: $neues_passwort"
  echo "Das Passwort steht nur hier. Ändern:"
  echo "  docker compose exec app python manage.py changepassword $ADMIN_USER"
fi
if [[ -n $lokal ]]; then
  echo
  echo "PROBEMODUS: nur zum Ausprobieren, nicht für Teilnehmerdaten (kein Zertifikat, Probe-Angaben)."
fi
