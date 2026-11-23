#!/usr/bin/env bash
# Richtet einen frischen Ubuntu-26.04-Server für Schwarmstack ein (ADR 0001, Ticket #27).
#
# Zwei Wege, eine Quelle:
#   - cloud-init: beim Anlegen in der Hetzner Console den ganzen Inhalt dieser Datei unter
#     "Cloud config" einfügen. cloud-init führt Skripte, die mit #! beginnen, einmal als root aus.
#   - Fallback per SSH als root: ssh root@<host> 'bash -s' < deploy/host-einrichten.sh
#
# Das Skript darf beliebig oft laufen. Es übernimmt die SSH-Schlüssel, die in der Hetzner Console
# für root hinterlegt wurden (Betreiber und Deploy-Job), für den Benutzer `deploy` und sperrt
# danach root und Passwörter für SSH.
set -euo pipefail

DEPLOY_USER=deploy
APP_DIR=/opt/schwarmstack
APP_UID=10001 # Benutzer der App im Image (Dockerfile)

export DEBIAN_FRONTEND=noninteractive

if [[ $(id -u) -ne 0 ]]; then
  echo "Bitte als root ausführen." >&2
  exit 1
fi
if [[ ! -s /root/.ssh/authorized_keys ]]; then
  echo "Keine SSH-Schlüssel in /root/.ssh/authorized_keys; beim Anlegen in der Hetzner Console" \
    "die Schlüssel von Betreiber und Deploy-Job auswählen." >&2
  exit 1
fi

# -- Docker und Compose-Plugin aus dem offiziellen Docker-apt-Repo ---------------------------
apt-get update -q
apt-get install -yq ca-certificates curl unattended-upgrades
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
# shellcheck source=/dev/null
codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $codename
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update -q
apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
  docker-compose-plugin
systemctl enable --now docker

# -- Logs: Container schreiben ins Journal, das 7 Tage aufbewahrt wird (ADR 0007) -------------
install -d /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/schwarmstack.conf <<'EOF'
[Journal]
MaxRetentionSec=7day
EOF
systemctl restart systemd-journald

# -- Benutzer deploy, nur mit SSH-Schlüssel ----------------------------------------------------
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi
usermod --append --groups docker "$DEPLOY_USER"
install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
install -m 0600 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /root/.ssh/authorized_keys \
  "/home/$DEPLOY_USER/.ssh/authorized_keys"

# -- Verzeichnis der App: Compose-Datei, Caddyfile und .env kommen bei jedem Deploy -----------
install -d -m 0750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$APP_DIR"
install -d -m 0750 -o "$APP_UID" -g "$APP_UID" "$APP_DIR/data"

# -- SSH: kein root, keine Passwörter ----------------------------------------------------------
# Die Datei sortiert vor 50-cloud-init.conf; bei sshd gilt der erste gesetzte Wert.
cat > /etc/ssh/sshd_config.d/10-schwarmstack.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowUsers $DEPLOY_USER
EOF
sshd -t
systemctl reload ssh

# -- Sicherheitsupdates selbst einspielen, bei Bedarf nachts neu starten ----------------------
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat > /etc/apt/apt.conf.d/52schwarmstack-upgrades <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
systemctl enable --now unattended-upgrades

echo "Host eingerichtet. Anmelden nur noch als $DEPLOY_USER."
