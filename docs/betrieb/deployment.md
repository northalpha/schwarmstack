# Deployment: vom leeren Hetzner-Konto bis zur laufenden Instanz

Schwarmstack läuft als Container-Image mit Docker Compose (App mit gunicorn, Caddy für TLS) auf einer eigenen Hetzner-VM und wird per GitHub Actions ausgerollt (ADR 0001). Diese Anleitung führt durch **Staging** (`upload.northalpha.de`); die **Produktion** (`upload.dzvf.de`) wird später genauso aufgesetzt, mit dem Environment `production` statt `staging`.

| Was | Wo |
|---|---|
| Image | `Dockerfile`, gebaut nach `ghcr.io/northalpha/schwarmstack` (privat) |
| Compose-Datei, Caddyfile | `deploy/compose.yaml`, `deploy/Caddyfile` (für beide Umgebungen gleich) |
| Einrichtung des Hosts | `deploy/host-einrichten.sh` (cloud-init oder per SSH) |
| Deploy | `.github/workflows/ci.yml` → `ausrollen.yml` → `deploy/ausrollen.sh` → `deploy/auf-dem-host.sh` |

## Wann was ausgerollt wird

- **Push auf `main`:** Tests → Image `sha-<commit>` bauen, im Container `/healthz` prüfen, pushen → nach **Staging**.
- **Tag `vX.Y.Z`:** dasselbe mit Image `vX.Y.Z` → nach **Produktion**, erst nach Freigabe im Environment `production`. Fehlen dort Pflichtwerte, bricht der Job mit einer Liste ab, bevor er den Host anfasst.
- **Von Hand** (Actions → CI → *Run workflow*): Umgebung und Image-Tag wählen; so wird auch zurückgerollt.

Ein Deploy schreibt die `.env` aus dem GitHub-Environment, kopiert sie mit `compose.yaml` und `Caddyfile` nach `/opt/schwarmstack`, holt das Image mit dem kurzlebigen `GITHUB_TOKEN` (danach `docker logout`), führt `migrate` aus und startet mit `docker compose up -d`. Schlägt die Migration fehl, bleiben die alten Dateien und die alte Version laufen und der Job wird rot; schon angewendete Migrationen derselben Version bleiben allerdings stehen. Danach wartet er bis zu 60 s auf `/healthz` über Caddy; antwortet es nicht mit `ok`, ist der Job rot. Während des Neustarts ist die Seite einige Sekunden nicht erreichbar.

Images werden nie als `latest` getaggt; welcher Stand läuft, steht in `/opt/schwarmstack/.env` (`IMAGE_TAG`) und im Deploy-Verlauf des Environments.

## 1. Schlüssel für den Deploy-Job

Für jede Umgebung ein eigenes Schlüsselpaar, ohne Passphrase:

```bash
ssh-keygen -t ed25519 -N '' -C schwarmstack-staging-deploy -f schwarmstack-staging-deploy
```

Den öffentlichen Teil (`.pub`) in der Hetzner Console unter *Security → SSH Keys* hinterlegen, ebenso den eigenen Schlüssel des Betreibers. Den privaten Teil später als Secret `SSH_PRIVATE_KEY` eintragen und lokal löschen.

## 2. Firewall und Server

In der Hetzner Console:

1. **Firewall** anlegen, eingehend nur TCP 22, 80 und 443 (UDP 443 zusätzlich erlaubt HTTP/3, ist aber nicht nötig).
2. **Server** anlegen: Ubuntu 26.04, kleinster Typ reicht für Staging, Firewall von eben, beide SSH-Schlüssel aus Schritt 1 auswählen.
3. Unter **Cloud config** den ganzen Inhalt von [`deploy/host-einrichten.sh`](../../deploy/host-einrichten.sh) einfügen.

cloud-init richtet den Server beim ersten Start ein: Docker und Compose-Plugin aus dem offiziellen Docker-Repo, Benutzer `deploy` (Gruppe `docker`) mit den ausgewählten SSH-Schlüsseln, `/opt/schwarmstack`, SSH nur per Schlüssel und nur für `deploy`, automatische Sicherheitsupdates mit Neustart um 04:00 bei Bedarf, Logs 7 Tage im Journal. Das dauert einige Minuten.

**Fallback**, falls cloud-init nicht gegriffen hat (z. B. Feld vergessen): dasselbe Skript als root ausführen. Es darf beliebig oft laufen.

```bash
ssh root@<ip> 'bash -s' < deploy/host-einrichten.sh
```

Danach geht root per SSH nicht mehr; angemeldet wird sich nur noch als `deploy`.

## 3. Host-Schlüssel festhalten

Den Host-Schlüssel des Servers für das Secret `SSH_KNOWN_HOSTS` holen:

```bash
ssh-keyscan -t ed25519 <ip>
```

Mit dem Fingerabdruck vergleichen, den der Server selbst meldet (beim ersten `ssh deploy@<ip>` bestätigen oder dort `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`). Die Zeile aus `ssh-keyscan` ist der Wert des Secrets.

## 4. DNS

`A` (und, falls vorhanden, `AAAA`) für `upload.northalpha.de` auf die IP des Servers. Caddy holt das Zertifikat beim ersten Start und erneuert es selbst; ohne DNS-Eintrag scheitert der erste Deploy an `/healthz`.

## 5. Bucket

In der Hetzner Console unter *Object Storage* einen eigenen Bucket für Staging und eigene S3-Zugangsdaten anlegen. CORS und Lifecycle-Regel setzt jeder Deploy selbst (`s3_bucket_setup --origin https://$DOMAIN` in `auf-dem-host.sh`, Details in [`s3-speicher.md`](s3-speicher.md)); von Hand ist nichts einzurichten. Eine Umlaut-Domain wird dabei in Punycode umgewandelt. Greift die CORS-Freigabe danach nicht, bricht der Deploy vor der Migration ab, und die bisherige Version läuft weiter.

## 6. GitHub-Environment

Im Repo unter *Settings → Environments* das Environment `staging` anlegen (für die Produktion `production`, dort zusätzlich *Required reviewers* und als *Deployment branches and tags* nur `v*.*.*`). Alles, was ein Deploy braucht, steht nur hier; auf dem Host wird nichts von Hand gepflegt.

**Variables**

| Name | Staging (Beispiel) | Pflicht |
|---|---|---|
| `DEPLOY_HOST` | IP oder Name des Servers | ja |
| `DOMAIN` | `upload.northalpha.de` | ja |
| `ADMIN_PATH` | zufällige Zeichenfolge, z. B. `openssl rand -hex 12` ([`admin.md`](admin.md)) | ja |
| `S3_ENDPOINT_URL` | `https://fsn1.your-objectstorage.com` | ja |
| `S3_BUCKET` | `schwarmstack-staging` | ja |
| `S3_REGION` | `fsn1` | ja |
| `S3_ADDRESSING_STYLE` | `virtual` (Standard) | nein |
| `UPLOAD_LINK_SECONDS` | `900` (Standard) | nein |
| `HSTS_SECONDS` | `0` (Standard); in Produktion z. B. `31536000` | nein |
| `LOG_LEVEL` | `INFO` (Standard) | nein |
| `LOGIN_ATTEMPTS_MAX`, `LOGIN_ATTEMPTS_WINDOW_SECONDS` | `5`, `900` (Standard) | nein |

**Secrets**

| Name | Inhalt | Pflicht |
|---|---|---|
| `SSH_PRIVATE_KEY` | privater Schlüssel aus Schritt 1 | ja |
| `SSH_KNOWN_HOSTS` | Zeile aus Schritt 3 | ja |
| `DJANGO_SECRET_KEY` | zufällig, z. B. `openssl rand -base64 48` | ja |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | S3-Zugangsdaten aus Schritt 5 | ja |
| `BASIC_AUTH_USER`, `BASIC_AUTH_HASH` | nur Staging: Benutzername und bcrypt-Hash | nein, nur gemeinsam |

Den Hash für Basic Auth erzeugt Caddy (fragt das Passwort ab):

```bash
docker run --rm -it caddy:2.10.2 caddy hash-password
```

Sind beide gesetzt, verlangt Caddy für alle Seiten außer `/healthz` Benutzername und Passwort. Die Uploads gehen direkt zum S3-Speicher und sind davon nicht betroffen. Kein Wert darf `'` oder einen Zeilenumbruch enthalten.

## 7. Erster Deploy

Ein Push auf `main` (oder *Run workflow* mit einem vorhandenen `sha-…`-Tag) rollt aus. Der Deploy-Job ist grün, wenn `https://upload.northalpha.de/healthz` mit `ok` antwortet. `/healthz` prüft Datenbank und S3-Speicher, verlangt kein Passwort und gibt keine Details preis; die Gründe stehen im Log. Dieselbe Adresse nutzt das externe Monitoring (ADR 0007).

## 8. Aktion anlegen

Einmalig von Hand, mit kleiner Gesamtgrenze für Staging. Der Deploy selbst fasst außer Migrationen keine Daten an.

```bash
ssh deploy@<ip>
```

```bash
cd /opt/schwarmstack && docker compose run --rm app python manage.py campaign --object "M 101" \
  --starts-at 2026-12-01T00:00+01:00 --ends-at 2027-03-31T23:59+02:00 \
  --quota-gib 2 --global-cap-gib 20
```

Betreiber-Konten für den Admin unter `https://upload.northalpha.de/<ADMIN_PATH>/` legt dasselbe Muster an, je Betreiber einmal:

```bash
cd /opt/schwarmstack && docker compose run --rm app python manage.py createsuperuser
```

## Zurückrollen

Actions → CI → *Run workflow*: Umgebung und den früheren Image-Tag (`sha-…` oder `vX.Y.Z`) eintragen. Für die Produktion unter *Use workflow from* einen Tag `vX.Y.Z` wählen, sonst lässt das Environment den Job nicht zu (nur `v*.*.*` erlaubt). Die Tags stehen im Deploy-Verlauf des Environments und unter *Packages* im Repo. Migrationen werden dabei nicht zurückgedreht: Ein älteres Image läuft nur, wenn es mit dem neueren Datenbankschema zurechtkommt.

## Auf dem Host nachsehen

```bash
cd /opt/schwarmstack && docker compose ps && docker compose logs --tail 100 app
```

Logs von App und Caddy liegen im Journal des Hosts und werden nach 7 Tagen gelöscht; Caddy protokolliert IP-Adressen gekürzt (IPv4 /24, IPv6 /48, ADR 0007). Die SQLite-Datenbank liegt unter `/opt/schwarmstack/data` (Sicherung nach S3 folgt mit ADR 0006).
