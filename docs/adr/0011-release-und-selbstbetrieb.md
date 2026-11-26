# Öffentliche Releases per „Merge ist Release“ und Selbstbetrieb per Git-Tag

> Begriffe heute: „Selbstbetrieb“ heißt jetzt **Self-Hosting**, „Probemodus“ **Demo-Modus**, `deploy/selbst/` liegt unter `deploy/self-hosting/`, der Job „selbstbetrieb“ heißt `installer`. Der Text unten ist unverändert (siehe `GLOSSARY.md`, Abschnitt „Betrieb“).

Das Repo soll öffentlich werden können. Schwarmstack ist für die Aktion der DZVF gebaut; wer eine eigene Aktion betreiben will, soll es mit einem Compose-Aufruf starten können, ohne GitHub-Deployment. Das ist kein Produktversprechen: Es gibt keine Support-Zusage, Issues sind willkommen, Pull Requests nur nach Absprache im Issue. Diese Entscheidung ergänzt ADR 0001 (Deployment der Betreiber) und ersetzt dort nur den Satz, das Image sei privat.

## Release

- **Versionen:** SemVer, solange die Hauptversion 0 ist, können Minor-Versionen noch etwas brechen. Der Changelog sagt es dann. Der erste öffentliche Release ist `v0.2.0`. Die alten Abschnitte 0.0.1 und 0.1.0 im `CHANGELOG.md` beschreiben den verworfenen Ansatz A0/A1 und stehen künftig unter „Vorgeschichte (verworfener Ansatz)“. Die alten Tags sind gelöscht.
- **Merge ist Release:** Der Skill `/release <version>` prüft, dass `main` grün ist, sammelt den Changelog (`scripts/changelog.py sammeln`), setzt die Version in `pyproject.toml` und öffnet einen PR „Release vX.Y.Z“ im üblichen Ablauf (`docs/agents/pull-requests.md`). Die Betreiber reviewen und mergen; das ist die Freigabe. Ein Workflow auf `main` erkennt den Release-Commit, führt Tests und den Installer-Test aus, baut und veröffentlicht das Image und legt **erst danach** Tag und GitHub Release an. Schlägt ein Schritt fehl, gibt es weder Tag noch Release.
- **Image:** öffentlich auf `ghcr.io/northalpha/schwarmstack`, für `linux/amd64` und `linux/arm64`, mit den Tags `vX.Y.Z` und `vX.Y`, nie `latest`. Dazu kommen eine Prüfsummen-Datei am Release und die Build-Bestätigung (Attestation) von GitHub. Das Image war bis zur Veröffentlichung des Repos privat; seit dem 2026-11-26 ist es öffentlich.
- **Release und Deploy sind getrennt:** Ein vom Workflow gesetzter Tag stößt keinen Produktions-Deploy an. Die Betreiber deployen nach Staging bei jedem Push auf `main` wie bisher und nach Produktion bewusst über „Run workflow“ mit dem Image-Tag, weiter mit Freigabe im Environment `production`. Der bisherige Auslöser „Tag `v*` deployt nach Produktion“ in `ci.yml` entfällt.

## Selbstbetrieb

- **Weg:** `git clone --branch vX.Y.Z`, dann `deploy/selbst/setup.sh`. Es gibt kein Release-Paket. Das Compose startet das fertige Image und baut nichts aus dem Quellcode, die übrigen Dateien im Repo stören nicht.
- **Dienste:** `app`, `caddy` und `garage` (S3-kompatibler Speicher, ADR 0005) in einer Compose-Datei. Der Browser lädt direkt zu Garage hoch, darum bekommt Garage eine eigene Adresse `s3.<domain>` mit Zertifikat von Caddy. `setup.sh` prüft vor dem Start, dass beide Namen auf den Server zeigen, und nennt den fehlenden Eintrag. Die Compose-Datei der Betreiber (`deploy/compose.yaml`, externes S3) bleibt unverändert.
- **`setup.sh`:** fragt Domain, Betreiber-Adressen und Angaben zur verantwortlichen Stelle ab, erzeugt alle Geheimnisse selbst, schreibt `.env`, startet Compose, richtet Bucket und CORS ein, legt Aktion und Admin an und nennt die Adressen. Es läuft auch ohne Rückfragen (Umgebungsvariablen) und ist wiederholbar. Ein Versionswechsel ist `git fetch --tags && git checkout vX.Y.Z && ./setup.sh`. Das Skript liest die Version aus `pyproject.toml` der ausgecheckten Version und setzt sie als Image-Tag. Steht der Checkout nicht auf einem Tag, bricht es mit einer klaren Meldung ab, denn für `main` gibt es kein veröffentlichtes Image.
- **Eigene Daten:** `.env` und `data/` liegen unter `deploy/selbst/` und sind in `.gitignore`. Ein Versionswechsel fasst sie nicht an.
- **Probemodus:** `./setup.sh --lokal` startet alles auf `localhost` ohne echtes Zertifikat, mit deutlichem Hinweis „nur zum Ausprobieren, nicht für Teilnehmerdaten“. Die CI nutzt denselben Modus.
- **Datenschutz:** Der Hinweistext nennt die verantwortliche Stelle und den Hoster über `OPERATOR_NAME`, `OPERATOR_ADDRESS`, `HOSTER_NAME`, `HOSTER_ADDRESS` und das vorhandene `PRIVACY_CONTACT`. Die Namen stehen ohne Artikel; die Artikel stehen fest im Text, damit der Wortlaut der DZVF gleich bleibt. Fehlt eine Angabe, warnt der Admin, `/datenschutz/` zeigt keinen Text mit leeren Stellen (503), und `deploy.sh` bricht ab. Der Wortlaut für die DZVF darf sich dadurch nicht ändern, sonst wechselt die Fassung des Hinweistextes (`CONSENT_TEXT_VERSION`); ein Test vergleicht ihn. Die Doku sagt deutlich, dass das keine Rechtsberatung ist und jeder Betreiber selbst verantwortlich bleibt.
- **Vorerst nicht:** Backup- und Update-Skripte. Die Doku nennt die Befehle (SQLite-Sicherung nach ADR 0006, Garage-Daten, Versionswechsel).

## CI

- Der Job „selbstbetrieb“ führt `setup.sh --lokal` ohne Rückfragen auf dem Runner aus und prüft `/healthz` und die Einrichtung des Buckets samt CORS. Er läuft bei Änderungen an `deploy/` und `setup.sh` und bei jedem Release, **vor** dem Veröffentlichen. Ein vollständiger Upload-Test folgt später.

## Consequences

- Der Release-Ablauf hat genau einen menschlichen Schritt, den Merge. Wer lieber selbst taggt, kann das später ergänzen.
- Das öffentliche Image darf keine Zugangsdaten enthalten. Das gilt schon heute, denn `.env` entsteht erst zur Laufzeit; der Image-Job prüft es künftig mit.
- Selbstbetreiber bekommen keine Rückfallmöglichkeit, wenn `ghcr.io` ausfällt. Ein Bau aus dem Quellcode (`docker build`) bleibt möglich, ist aber nicht der dokumentierte Weg.
- Zwei Compose-Dateien müssen synchron bleiben, was Caddy-Einstellungen und Umgebungsvariablen betrifft. Der Installer-Test fängt Abweichungen in der Selbstbetriebs-Datei ab, nicht in der der Betreiber.

## Considered Options

- **Release-Paket (`tar.gz` mit Compose, Caddyfile und Installer):** verworfen; ein Checkout des Tags enthält dasselbe, und die Version steht damit in einem Ort.
- **Image bei jedem Selbstbetreiber bauen (`build: .`):** verworfen als Standard; es dauert auf kleinen Servern Minuten, und getestet wird das veröffentlichte Image.
- **Tag von Hand setzen:** verworfen als Standard; ein Tag vor dem grünen Release-Lauf könnte ein kaputtes Release erzeugen.
- **Release-Vorbereitung als eigener Workflow mit Knopfdruck:** verworfen; der Skill nutzt den bestehenden PR-Ablauf und braucht keine neuen Rechte für Workflows.
- **Alles unter einer Domain (Garage unter `/s3/`):** verworfen; Caddy müsste den Pfad abschneiden, und das bricht die S3-Signatur.
- **Web-Assistent zur Einrichtung:** verworfen; viel Aufwand für wenige Installationen. Ein Skript genügt.
- **Automatische Updates (Watchtower o. Ä.):** verworfen; ein stilles Update auf einem Dienst mit Daten von Teilnehmenden ist unerwünscht.
