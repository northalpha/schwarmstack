#!/usr/bin/env bash
# Startet Garage als S3-kompatiblen Speicher für Tests und lokale Entwicklung (ADR 0005).
# Nur für Test- und Entwicklungsdaten: feste Zugangsdaten, keine Persistenz.
#
#   scripts/garage.sh start   # startet und richtet ein, gibt die Umgebungsvariablen aus
#   scripts/garage.sh stop
set -euo pipefail

NAME=schwarmstack-garage
IMAGE=dxflrs/garage:v2.5.0
PORT=${GARAGE_PORT:-3900}
BUCKET=schwarmstack-test
# Feste Testschlüssel, nur für den lokalen Container.
KEY_ID=GK0123456789abcdef01234567
SECRET=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

garage() { docker exec -e RUST_LOG=warn "$NAME" /garage "$@"; }

start() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  config=$(mktemp)
  cat > "$config" <<TOML
metadata_dir = "/var/lib/garage/meta"
data_dir = "/var/lib/garage/data"
db_engine = "sqlite"
replication_factor = 1
rpc_bind_addr = "0.0.0.0:3901"
rpc_public_addr = "127.0.0.1:3901"
rpc_secret = "$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"

[s3_api]
s3_region = "garage"
api_bind_addr = "0.0.0.0:3900"
root_domain = ".s3.garage.localhost"
TOML
  chmod 644 "$config"
  docker run -d --name "$NAME" -p "127.0.0.1:$PORT:3900" \
    -v "$config:/etc/garage.toml:ro" "$IMAGE" >/dev/null

  for _ in $(seq 1 50); do
    garage status >/dev/null 2>&1 && break
    sleep 0.2
  done
  node=$(garage node id -q | cut -d@ -f1)
  garage layout assign -z dc1 -c 1G "$node" >/dev/null
  garage layout apply --version 1 >/dev/null
  garage key import --yes -n test "$KEY_ID" "$SECRET" >/dev/null
  garage bucket create "$BUCKET" >/dev/null
  garage bucket allow --read --write --owner "$BUCKET" --key "$KEY_ID" >/dev/null

  # CORS wie im Betrieb: Der Browser lädt direkt in den Bucket und muss den ETag lesen.
  S3_ENDPOINT_URL="http://127.0.0.1:$PORT" uv run --quiet python - <<PY
import boto3
s3 = boto3.client("s3", endpoint_url="http://127.0.0.1:$PORT", region_name="garage",
                  aws_access_key_id="$KEY_ID", aws_secret_access_key="$SECRET")
s3.put_bucket_cors(Bucket="$BUCKET", CORSConfiguration={"CORSRules": [{
    "AllowedOrigins": ["*"], "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 3600}]})
PY

  cat <<ENV
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://127.0.0.1:$PORT
S3_BUCKET=$BUCKET
S3_REGION=garage
S3_ACCESS_KEY_ID=$KEY_ID
S3_SECRET_ACCESS_KEY=$SECRET
S3_ADDRESSING_STYLE=path
ENV
}

case "${1:-}" in
  start) start ;;
  stop) docker rm -f "$NAME" >/dev/null ;;
  *) echo "Aufruf: $0 start|stop" >&2; exit 2 ;;
esac
