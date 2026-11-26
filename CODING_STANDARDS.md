# Coding Standards

Für das Review: Regeln, die ein Urteil brauchen. Alles Mechanische prüft `scripts/pruefen.sh`
(ruff, CodeQL, shellcheck, actionlint, zizmor, pip-audit, Sicherheitsausnahmen, doppelte Glossar-Begriffe, Changelog-Ort, Migrationen, Schreibzugriffe in Views); was dort
grün ist, wird im Review nicht wiederholt.

## Sprache des Fachgebiets

- Fachbegriffe stehen in [`GLOSSARY.md`](GLOSSARY.md). Prosa, Oberfläche, Docstrings, Kommentare,
  Testnamen und Commit-Nachrichten verwenden den deutschen Begriff, Code-Bezeichner den Namen in
  Klammern dahinter (Submission → `Submission`, Löschung → `deleted_at`).
- Wörter unter `_Avoid_` meiden. Hilfe für das Review:
  `uv run python scripts/glossar.py diff <fixed-point>` listet sie in den hinzugefügten Zeilen.
  Jeder Treffer ist zu beurteilen, kein Treffer ist automatisch ein Verstoß (z. B. ein
  GitHub-„Token“ in `deploy/` ist keine Submission-ID). Wörter mit Zusatz („Admin (für die
  Person)“) zählt das Skript nur; die Stellen zeigt `--alle`.
- Englische Bezeichner deckt das Skript nicht ab: Ein Bezeichner, der einen gemiedenen Begriff
  übersetzt (`Storage.check()` neben „Check“ für die Prüfung), ist ebenso ein Treffer.
- Ein neuer Fachbegriff, der im Glossar fehlt, gehört ins Glossar oder ist ein Hinweis, dass
  das Wort nicht passt.
- Das Glossar gilt für die Domäne, nicht für Technikvokabular. Begriffe der Softwaretechnik, die
  ein Team auch im deutschen Gespräch englisch benutzt, bleiben englisch und werden nicht
  übersetzt. Gibt es ein gebräuchliches deutsches Wort, bleibt es deutsch (Prüfsumme, Endpunkt,
  Sicherung, signierte Links, Grundgerüst, Begleitdatei). Zu meiden sind Zwangsübersetzungen wie:

  | Begriff         | statt                         |
  | --------------- | ----------------------------- |
  | Seam            | Naht                          |
  | Smoke Test      | Rauchtest                     |
  | Contract Test   | Vertragstest                  |
  | E2E-Test        | Browser-Durchlauf             |
  | Range Request   | Teilabruf                     |
  | Deploy          | Ausrollen                     |
  | Rollback        | Zurückrollen                  |
  | Self-Hosting    | Selbstbetrieb                 |
  | Demo-Modus      | Probemodus                    |

## Wo Fachverhalten liegt

- Regeln zur Submission (anlegen, Master löschen, Löschung, Widerruf) liegen in
  `src/submissions/services.py`, Regeln zum Upload (Quote, Gesamtgrenze, Zeitfenster,
  Dubletten) in `src/submissions/uploads.py`. Views, API und Admin rufen sie auf und entscheiden
  selbst nichts Fachliches; eine Regel, die in einer View oder im Admin neu entsteht, ist ein
  Befund. Schreibzugriffe dort fängt `tests/test_fachregeln_ort.py`; im Review bleiben
  Bedingungen („darf das jetzt?“), die dort stehen, obwohl sie Fachverhalten sind.
- Zugriff auf Dateien nur über `storage.get_storage()` und das `Storage`-Protokoll in
  `src/storage/__init__.py`. Eine neue Methode bekommt jeder Adapter (`local.py`, `s3.py`) und
  einen Fall in `tests/test_speicher_contract.py`, der für alle Adapter läuft.
- Breites `except Exception` nur beim Aufräumen am Speicher, mit einem Kommentar, warum der
  Fehler egal ist, und einem Log-Eintrag.

## Entscheidungen und Doku

- Widerspricht eine Änderung einem ADR in `docs/adr/`, wird das ADR im selben Branch angepasst
  oder die Abweichung im PR begründet. Stillschweigend abweichen ist ein Befund.
- Jede Änderung mit Wirkung für Teilnehmende oder Betreiber hat einen Eintrag in `changelog.d/`
  mit dem *Warum* (siehe [`changelog.d/README.md`](changelog.d/README.md)).
- Neue Einstellungen aus der Umgebung stehen in `docs/betrieb/deployment.md` und, wenn der
  Deploy sie braucht, in `deploy/deploy.sh` und `.github/workflows/deploy.yml`.

## Tests

- Testgetrieben, ein Modul je Thema, Modul-Docstring mit Ticket (`"""… (Ticket #15)."""`).
  Testnamen beschreiben auf Deutsch das Verhalten (`test_widerruf_der_namensnennung_bleibt_als_vermerk`).
- Was gegen S3 läuft, läuft für alle Adapter (lokal, moto, Garage) über die Fixtures aus
  `tests/storage_backends.py`, nicht nur gegen einen.
- Fixtures, die mehrere Module brauchen, kommen nach `tests/conftest.py`. Das Importieren von
  Fixtures aus Hilfsmodulen (mit `# noqa: F811`) gibt es schon; es ist kein Befund, soll aber
  nicht weiter wachsen.
