# Offene Fragen und Abweichungen

## Entscheidungen des Besitzers (Startgespräch)

- Repo `northalpha/schwarmstack` ist **privat**: Die Ansible-Rolle braucht zum Laden des Releases
  einen Token (Vault) oder eine Artefakt-Kopie.
- Staging-Freigabe über **Funnel**, verwaltet über die Rolle (`schwarmstack_tailscale_funnel: true`).
- Die Tailnet-Policy liegt in `home-ansible`; das `funnel`-nodeAttr wird dort gepflegt.
- Die Staging-VM ist bereits im Tailnet. Impressum/Datenschutz: Platzhalter mit Testsystem-Hinweis.
- Projektwebsite: vorerst nur die Demo-Projektseite.
- Den Staging-Lauf führt der Besitzer selbst aus; der Agent hat keinen Netzzugang zur VM.
  Die Prüfungen aus Abschnitt 0b laufen als Skript beim Besitzer.

## Abweichungen vom Plan

- **PackJob nicht 1:1 zu Stack:** Prüfaufträge gelten je Datei, Packaufträge je Stack. Das Modell hat
  `uploaded_file` (nur bei `validate`) und je eine Eindeutigkeit für Stack+pack und Datei+validate.
- **ALTCHA:** Die Python-Bibliothek `altcha` 2.x (PoW v2) passt zum Widget 3.x. Serverseitig mit Tests
  geprüft (Aufgabe, Lösung, Ablauf, Wiederverwendung, Manipulation). **Im Browser nicht getestet**, weil
  die Arbeitsumgebung keinen Browser und kein Node hat: erster Test auf Staging mit `altcha_enabled`
  in einem Event. Widget und Worker laden nur vom eigenen Server (`external`-Build mit eigenem Worker).

- **Referer als weiches Tor** (Plan 5.1): im README „Einbindung“ ehrlich festgehalten.
- **Client-Adresse:** Für die Rate-Limits braucht die App die echte Adresse. Hinter Tailscale (Serve/Funnel)
  und Caddy wird sie aus `X-Forwarded-For` gelesen (`CLIENT_IP_SKIP=1`: der letzte Eintrag ist Caddy, davor
  steht, was Tailscale gesetzt hat). **Nicht gegen echtes Tailscale getestet** (nur mit den Headern nachgestellt);
  fällt der Wert aus, gilt `REMOTE_ADDR` (alle teilen sich dann ein Limit, unsicher wird nichts).
- **Teilnahme ohne eigene Abgabe-Seite für Mails:** Der persönliche Link wird nur angezeigt; das Mailen
  (Status-Mails) folgt mit A7.

## Offen

- ALTCHA im Browser prüfen (siehe oben), sobald das Teilnahmeformular steht (A2).
