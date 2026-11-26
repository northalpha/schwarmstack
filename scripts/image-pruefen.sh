#!/usr/bin/env bash
# Prüft ein gebautes Image: keine .env, keine Schlüssel und keine Zugangsdaten darin (ADR 0011),
# und Equipment-Fotos (JPEG, PNG, WebP, HEIC) lassen sich darin bereinigen (ADR 0014).
#
#   scripts/image-pruefen.sh ghcr.io/northalpha/schwarmstack:v0.2.0
set -euo pipefail

image=${1:?Aufruf: scripts/image-pruefen.sh <image>}

# Das Image enthält nur Python und die App; Funde außerhalb von Systempfaden sind Fehler.
# `cacert.pem` ist das öffentliche CA-Bündel von certifi (pip, botocore), kein privater Schlüssel.
fund=$(docker run --rm --entrypoint sh "$image" -c '
  find / -xdev \( -path /proc -o -path /sys -o -path /usr/share -o -path /etc/ssl \) -prune -o \
    -type f ! -name cacert.pem \( -name ".env" -o -name ".env.*" -o -name "*.pem" -o -name "*.key" \
               -o -name "id_rsa*" -o -name "id_ed25519*" -o -name "credentials" \
               -o -name ".netrc" -o -name "*.sqlite3" \) -print 2>/dev/null
  grep -rIlE "ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY" \
    /app/src /app/static /data 2>/dev/null || true
')
if [[ -n $fund ]]; then
  echo "Im Image liegen Dateien, die dort nicht hingehören:" >&2
  echo "$fund" >&2
  exit 1
fi

# Auch die Umgebung des Images darf nichts Geheimes vorbelegen.
geheim='^[A-Z_]*(SECRET|PASSWORD|TOKEN|ACCESS_KEY)[A-Z_]*='
namen=$(docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$image" \
  | { grep -iE "$geheim" || true; } | cut -d= -f1)
if [[ -n $namen ]]; then
  echo "Das Image setzt Geheimnisse in seiner Umgebung:" >&2
  echo "$namen" >&2
  exit 1
fi
echo "Image enthält keine .env und keine Zugangsdaten."

# Pillow und pillow-heif laufen im Image auf einer anderen libc als die Tests (Alpine/musl);
# darum geht je ein Foto jedes Formats durch `submissions.photos` im Image selbst.
docker run --rm --interactive --entrypoint python "$image" - < "$(dirname "$0")/image_foto_pruefen.py"
