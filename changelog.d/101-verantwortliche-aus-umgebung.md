- Datenschutzhinweis: verantwortliche Stelle und Hoster kommen aus Umgebungsvariablen (#101). Neu:
  `OPERATOR_NAME`, `OPERATOR_BEI`, `OPERATOR_ADDRESS`, `HOSTER_NAME`, `HOSTER_BEI`,
  `HOSTER_ADDRESS` (zusammen mit `PRIVACY_CONTACT`), in `deploy.sh`, `deploy.yml` und
  `docs/betrieb/deployment.md`. Fehlt eine Angabe, warnt der Admin und beim Start (`submissions.W001`),
  und `/datenschutz/` zeigt „noch nicht vollständig“ (503) statt eines Textes mit leeren Stellen.
  Der Wortlaut für die DZVF bleibt zeichengenau gleich (Test gegen `tests/golden/`), die Fassung
  `CONSENT_TEXT_VERSION` ändert sich nicht. Warum: Selbstbetreiber (ADR 0011) brauchen ihre eigenen
  Angaben. Folge für die DZVF: Die sechs Werte vor dem nächsten Deploy als GitHub-Variablen
  setzen (`der DZVF`, `beim DZVF`, `die Hetzner Online GmbH`, `bei der Hetzner Online GmbH` und die
  Anschriften), sonst bricht `deploy.sh` ab. Die Anschriften stehen im heutigen Wortlaut nicht.
