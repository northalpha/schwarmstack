# Sicherheitsprüfungen in CI

Schwarmstack ist ein Hobbyprojekt. Ziel ist ein gesundes Maß an Sicherheit ohne grobe Lücken, kein Audit. Die Prüfungen laufen automatisch und sollen nur dann stören, wenn es sich lohnt.

## Entscheidung

- **Schwelle:** Für das Image (Trivy) wird der PR nur rot bei High/Critical und vorhandenem Fix; alles andere erscheint als Hinweis im Security-Tab von GitHub. `pip-audit` hat keine Schwelle, siehe unten.
- **Abhängigkeiten:** Dependabot prüft wöchentlich `uv.lock`, die GitHub Actions und das Docker-Basisimage, in gruppierten Updates. Sicherheitsupdates kommen sofort. Gemergt wird von Hand. `pip-audit` läuft gegen `uv.lock` in `scripts/pruefen.sh`, damit lokal und in CI dasselbe läuft.
- **Image:** Trivy scannt das gebaute Image im `image`-Job von `ci.yml`. Rot wird er bei High/Critical mit Fix; der Gesamtbericht geht bei Pushes auf `main` in den Security-Tab.
- **Workflows:** `zizmor` läuft neben `actionlint` in `scripts/pruefen.sh` (ab Schweregrad „medium“). Alle Actions sind auf Commit-SHAs gepinnt, mit der Version als Kommentar; Dependabot hält sie aktuell. Jeder Checkout setzt `persist-credentials: false`. Einzige Ausnahme in `.github/zizmor.yml`: `secrets-inherit` in `ci.yml`, weil die Deploy-Geheimnisse sonst zweimal einzeln aufgezählt würden; beide Aufrufer sind eigene Workflows.
- **Code:** CodeQL für Python und die Workflows, bei PRs, bei Pushes auf `main` und wöchentlich.
- **Ausnahmen:** Eine Datei, `sicherheit-ausnahmen.toml`. Jeder Eintrag hat `id`, `grund` und `bis`. `scripts/pruefen.sh` prüft Pflichtfelder und Ablauf (`scripts/ausnahmen.py`); abgelaufene Ausnahmen gelten nicht mehr und lassen die Prüfung scheitern. `pip-audit` und Trivy lesen dieselben IDs.
- **Bewusst weggelassen:** OWASP ZAP. Es braucht eine laufende Instanz mit Testdaten und liefert für den Aufwand vorerst zu wenig; das Review der Anwendung (Teil 3 der Sicherheitsüberprüfung) deckt das Wichtige ab.
- **Header und Deploy-Prüfung (#122):** Eine eigene Middleware (`schwarmstack/security_headers.py`) setzt die Content-Security-Policy, `X-Frame-Options: DENY` und die `Permissions-Policy`, ganz außen, damit auch Fehlerantworten sie tragen. Sie liegt in Django statt in Caddy, weil der E2E-Test gegen `live_server` ohne Caddy läuft und der echte Browser die Policy nur so mitprüft; außerdem gilt sie dann bei beiden Caddyfiles und bei eigenen Proxys im Selbstbetrieb. Die Policy kennt kein `unsafe-inline`; `connect-src` enthält den S3-Ursprung aus den Settings, weil Uppy direkt zu S3 hochlädt. Skripte und Styles liegen deshalb nur als statische Dateien vor. `CSP_REPORT_ONLY=true` stellt die Policy im Notfall auf „nur melden“. `manage.py check --deploy` läuft in `scripts/pruefen.sh` und lässt jede Warnung scheitern; die Ausnahmen (`W004`, `W008`, `W021`) stehen mit Grund in den Settings.

## Consequences

- `pip-audit` kennt keinen Schweregrad und nicht jeden Fund mit Fix: Jede bekannte Schwachstelle in einem gesperrten Paket lässt die Prüfung scheitern. Ist sie nicht behebbar oder nicht erreichbar, steht sie mit Begründung und Ablaufdatum in der Ausnahmedatei.
- Lokal prüft `zizmor` ohne GitHub-Token nur offline; in CI läuft es mit Token vollständig.
- Neue Funde ohne Fix erscheinen nur im Security-Tab und brauchen dort einen Blick der Betreiber.
- Repo-Einstellungen (Secret-Scanning, Push-Protection, Private Vulnerability Reporting, Branch-Schutz) macht der Betreiber von Hand; sie sind nicht Teil dieser Entscheidung.
- Neue Seiten dürfen kein Inline-`<script>` oder `<style>` und kein `style=`-Attribut enthalten; der E2E-Test meldet Verstöße gegen die Policy.
