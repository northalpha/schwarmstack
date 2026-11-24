- Ein geändertes Caddyfile greift beim Deploy sofort: Der Caddy-Container startet dann neu.
  Warum: Bisher lief Caddy mit der alten Konfiguration weiter, so verlangte Staging für
  `/zahlen.json` trotz Ausnahme weiter Basic Auth.
