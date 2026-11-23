# Einträge für den nächsten Release

Eine Datei je Änderung: `<ticket>-<kurz>.md`, ohne Ticket `<kurz>.md`. Inhalt ist der Eintrag als
Listenpunkt, wie er in `CHANGELOG.md` stehen soll: was sich ändert und warum.

```markdown
- Export für die Betreiber (#33): … Warum: …
```

Beim Release übernimmt `uv run python scripts/changelog.py sammeln <version>` alle Dateien als
neuen Abschnitt in `CHANGELOG.md` und löscht sie. CI prüft mit `scripts/changelog.py pruefen`,
dass unter „Unveröffentlicht“ in `CHANGELOG.md` nichts eingetragen wird.
