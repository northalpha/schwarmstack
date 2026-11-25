# Mitmachen

Schwarmstack ist ein Hobbyprojekt für eine Aktion der DZVF-Community. Es gibt **keine Support-Zusage** und keinen festen Zeitplan.

## Issues sind willkommen

Fehler, Wünsche und Fragen gern als [Issue](../../issues/new/choose). Die Formulare fragen, was wir zum Nachvollziehen brauchen. Sicherheitslücken meldest du **nicht** als Issue, sondern wie in [`SECURITY.md`](SECURITY.md) beschrieben.

## Pull Requests nur nach Absprache

Bitte öffne einen Pull Request erst, **nachdem du die Änderung in einem Issue abgesprochen hast** und die Betreiber zugestimmt haben. Pull Requests ohne vorherige Absprache schließen wir meist ohne Review, auch wenn sie gut gemeint sind: Das Projekt hat einen klaren Zuschnitt (siehe [`docs/adr/`](docs/adr/)), und jede Änderung kostet Review-Zeit.

Wenn ihr euch einig seid:

- Halte dich an [`CODING_STANDARDS.md`](CODING_STANDARDS.md) und die Begriffe in [`GLOSSARY.md`](GLOSSARY.md).
- Prüfe lokal mit `scripts/pruefen.sh` (ohne Docker: `--schnell`), die CI macht dasselbe.
- Lege einen Eintrag in `changelog.d/` an (siehe [`changelog.d/README.md`](changelog.d/README.md)), nicht in `CHANGELOG.md`.
- Mit dem Pull Request stimmst du zu, dass dein Beitrag unter der [MIT-Lizenz](LICENSE) des Projekts steht.

## Verhalten

Es gilt der [Verhaltenskodex](CODE_OF_CONDUCT.md).
