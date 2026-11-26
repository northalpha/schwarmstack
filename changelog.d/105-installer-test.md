- Installer-Test (#105): Der CI-Job „selbstbetrieb“ führt `deploy/selbst/setup.sh --lokal` ohne
  Rückfragen aus und prüft `/healthz`, Bucket, CORS-Preflight und dass ein zweiter Lauf nichts
  ändert. Er läuft bei Änderungen an `deploy/` und bei Tags; der Release-Workflow ruft ihn als
  `selbstbetrieb.yml` vor dem Veröffentlichen auf (ADR 0011). Lokal:
  `scripts/selbstbetrieb-test.sh`.
