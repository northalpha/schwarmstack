- Deployment nach Staging, Produktion vorgesehen (#27): Container-Image (gunicorn, statische
  Dateien über WhiteNoise), eine Compose-Datei mit Caddy für beide Umgebungen, Einrichtung des
  Hosts per cloud-init oder SSH (`deploy/host-einrichten.sh`) und Deploy per GitHub Actions:
  jeder grüne Push auf `main` nach Staging, Tags `vX.Y.Z` nach Freigabe in die Produktion,
  Zurückrollen über *Run workflow*. Neuer Endpunkt `/healthz` prüft Datenbank und S3-Speicher.
  Anleitung in `docs/betrieb/deployment.md`. Warum: Der Upload-Weg soll unter echten Bedingungen
  (TLS, Hetzner-S3, Heimleitung, mehrere Browser) laufen, und die Produktion später auf demselben
  Weg ohne Umbau.
