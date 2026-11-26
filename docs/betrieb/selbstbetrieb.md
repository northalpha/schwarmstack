# Selbst betreiben

Wer eine eigene Aktion betreiben will, startet Schwarmstack mit einem Skript und Docker Compose, ohne GitHub-Deployment (ADR 0011). Das ist kein Produktversprechen: keine Support-Zusage, Issues sind willkommen. Die Betreiber-Einrichtung der DZVF (Hetzner, GitHub Actions) steht in [`deployment.md`](deployment.md) und ist davon unabhängig.

Kein Rechtsrat: Wer Schwarmstack betreibt, ist selbst für Datenschutzhinweis, Einwilligungen und Löschfristen verantwortlich. Die Angaben zur verantwortlichen Stelle gehören dir.

## Voraussetzungen

- Ein Server mit Linux, öffentlicher IP und den offenen Ports 80 und 443 (TCP, für HTTP/3 auch UDP 443).
- Docker mit dem Compose-Plugin, `git` und `curl`.
- **Zwei DNS-Einträge** (A, ggf. AAAA) auf den Server: die Domain der Teilnahmeseite, etwa `upload.example.org`, und `s3.upload.example.org` für den Speicher. Der Browser lädt direkt zu Garage hoch, darum braucht der Speicher eine eigene Adresse. Caddy holt für beide Namen ein Zertifikat.
- Platz auf der Platte für die Master der Aktion; Garage legt sie unter `deploy/selbst/data/garage/` ab.

## Einrichten

Immer von einem Release-Tag aus, nie von `main` (dafür gibt es kein veröffentlichtes Image):

```bash
git clone --branch vX.Y.Z https://github.com/northalpha/schwarmstack.git
```

```bash
cd schwarmstack/deploy/selbst && ./setup.sh
```

`setup.sh` fragt Domain, Betreiber-Adressen, die Angaben zur verantwortlichen Stelle und zum Hoster, dann Objekt, Zeitraum und Grenzen der Aktion und prüft, ob beide DNS-Einträge auf diesen Server zeigen (und nennt den fehlenden). Es erzeugt alle Geheimnisse selbst, schreibt `.env`, startet App, Caddy, Garage und eine Aufgaben-Schleife, richtet Garage samt Bucket und CORS ein (und prüft CORS wie ein Browser), legt die Aktion und das erste Betreiber-Konto an und nennt am Ende die Adressen. Das Passwort des Kontos steht nur dort; ändern:

```bash
docker compose exec app python manage.py changepassword betreiber
```

Weitere Konten: [`admin.md`](admin.md).

### Ohne Rückfragen

Alle Fragen lassen sich über Umgebungsvariablen beantworten, siehe [`.env.example`](../../deploy/selbst/.env.example):

```bash
DOMAIN=upload.example.org OPERATOR_EMAILS=betrieb@example.org \
OPERATOR_NAME='Beispielverein e. V.' OPERATOR_ADDRESS='Musterstraße 1, 12345 Musterstadt' \
HOSTER_NAME='Beispiel-Hosting GmbH' HOSTER_ADDRESS='Hosterweg 2, 54321 Hosterstadt' \
PRIVACY_CONTACT=datenschutz@example.org \
AKTION_OBJEKT='M 101' AKTION_START=2026-12-01T00:00:00+01:00 AKTION_ENDE=2027-01-01T00:00:00+01:00 \
AKTION_QUOTE_GIB=5 AKTION_GESAMTGRENZE_GIB=100 \
./setup.sh
```

Fehlt eine Angabe und gibt es kein Terminal, bricht das Skript ab und nennt die fehlenden Variablen.

### Probemodus

```bash
./setup.sh --lokal
```

startet alles auf `localhost` ohne Zertifikat und mit Probe-Angaben (Ports 80 und 443 müssen frei sein). **Nur zum Ausprobieren, nicht für Teilnehmerdaten.** Probemodus und echter Betrieb lassen sich nicht in derselben `.env` mischen.

## Wiederholen und Versionswechsel

`./setup.sh` darf beliebig oft laufen. Geheimnisse, Daten, Aktion und Betreiber-Konto bleiben; geändert wird nur, was sich geändert hat. Ein Versionswechsel ist:

```bash
git fetch --tags && git checkout vX.Y.Z && cd deploy/selbst && ./setup.sh
```

Das Skript liest die Version aus `pyproject.toml` der ausgecheckten Version und setzt sie als Image-Tag. Steht der Checkout nicht auf dem passenden Tag, bricht es ab. Der Changelog sagt, was eine neue Version ändert; solange die Hauptversion 0 ist, können Minor-Versionen noch etwas brechen. Automatische Updates gibt es nicht.

## Eigene Daten

Alles Eigene liegt unter `deploy/selbst/` und steht in `.gitignore`; ein Versionswechsel fasst es nicht an:

| Pfad | Inhalt |
|---|---|
| `.env` | Einstellungen und Geheimnisse (nur für den Besitzer lesbar) |
| `data/app/db.sqlite3` | die Datenbank (SQLite, ADR 0006) |
| `data/garage/` | Garage: Konfiguration, Metadaten und die Master selbst |

Die Zertifikate von Caddy liegen in einem Docker-Volume (`schwarmstack_caddy_data`).

## Sichern

Es gibt keine Backup-Skripte, nur diese Befehle (im Ordner `deploy/selbst/`). SQLite sichern, ohne die App anzuhalten (ADR 0006):

```bash
docker compose exec app python -c "import sqlite3; s = sqlite3.connect('/data/db.sqlite3'); d = sqlite3.connect('/data/db-sicherung.sqlite3'); s.backup(d)"
```

Die Sicherung liegt danach in `data/app/db-sicherung.sqlite3` und gehört vom Server weg kopiert. Die Master liegen in `data/garage/data/`; konsistent sichern lässt sich dieser Ordner bei angehaltenem Garage:

```bash
docker compose stop garage && tar -czf garage-sicherung.tar.gz data/garage && docker compose start garage
```

Die `.env` gehört ebenfalls in die Sicherung, ohne sie sind die Zugangsdaten zum Speicher weg.

## Was läuft

| Dienst | Aufgabe |
|---|---|
| `app` | Schwarmstack (gunicorn) |
| `aufgaben` | täglich die Löschung nach Ablauf der Löschfrist (`delete_after_export`, ADR 0008), stündlich `forget_login_attempts` |
| `garage` | S3-kompatibler Speicher (ADR 0005), nur über Caddy unter `s3.<domain>` erreichbar |
| `caddy` | TLS und Weiterleitung für beide Namen |

Logs: `docker compose logs app`. Die Compose-Datei der Betreiber (`deploy/compose.yaml`) und ihr Caddyfile bleiben unverändert; Einstellungen, die beide betreffen, müssen in beiden Dateien nachgezogen werden.
