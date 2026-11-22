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

## Offen

- Noch keine.
