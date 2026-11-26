- Installer-Test (#105): Der CI-Job „selbstbetrieb“ führt `deploy/selbst/setup.sh --lokal` ohne
  Rückfragen aus und prüft `/healthz`, Bucket, CORS-Preflight und dass ein zweiter Lauf nichts
  ändert. Er läuft bei Änderungen an `deploy/` und bei Tags und steht als `selbstbetrieb.yml` für
  den Release-Workflow (#99) bereit, der ihn vor dem Veröffentlichen aufrufen soll. Lokal:
  `scripts/selbstbetrieb-test.sh`. Warum: Ein kaputter Installer fällt so in der CI auf, nicht
  erst bei Dritten, die eine eigene Aktion betreiben (ADR 0011).
