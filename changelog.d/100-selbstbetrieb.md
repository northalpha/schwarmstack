- Selbstbetrieb (#100): `deploy/selbst/` startet App, Caddy und Garage mit einem Skript
  (`./setup.sh`, Probemodus `--lokal`). Es erzeugt alle Geheimnisse, richtet Bucket und CORS ein,
  legt Aktion und Betreiber-Konto an und lässt sich wiederholen, ohne etwas Unnötiges zu ändern.
  Anleitung in `docs/betrieb/selbstbetrieb.md`. Warum: Dritte sollen eine eigene Aktion ohne
  GitHub-Deployment betreiben können (ADR 0011).
