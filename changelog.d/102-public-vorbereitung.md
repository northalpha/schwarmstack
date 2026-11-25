- Public-Vorbereitung (#102): `SECURITY.md` (Meldung über „Private vulnerability reporting“, nur der
  letzte Release), `CONTRIBUTING.md` (Issues willkommen, Pull Requests nur nach Absprache),
  `CODE_OF_CONDUCT.md`, Issue-Formulare für Fehler, Wunsch und Frage (keine leeren Issues) und
  `THIRD_PARTY.md` mit den Lizenzhinweisen zum mitgelieferten Uppy-Bundle. Warum: Das Repo soll
  öffentlich werden können (ADR 0011). Geprüft: Kein Workflow gibt Forks Zugriff auf Secrets
  (`pull_request`, kein `pull_request_target`; Secrets nur bei Push und von Hand), `permissions:`
  sind minimal, ein Muster-Scan der Historie (Schlüsselformate, Schlüssel- und Env-Dateien) fand nichts; er muss nach dem Umschreiben der Historie noch einmal laufen.
