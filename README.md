<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/schwarmstack-logo-dark-bg.svg">
  <img alt="Schwarmstack – Viele Teleskope, ein Stack." src="brand/schwarmstack-logo.svg" width="480">
</picture>

# Schwarmstack

Upload-Dienst für ein gemeinsames Astrofotografie-Projekt der [DZVF-Community](https://community.dzvf.de): Teilnehmende laden ihre Master (XISF/FITS, 32 Bit) hoch, der Betreiber führt sie zu einem Bild zusammen.

**Stand:** Neuaufbau. Der erste Ansatz (A0/A1) wurde verworfen; Code entsteht neu, Ticket für Ticket und testgetrieben.

## Wo was steht

- [`GLOSSARY.md`](GLOSSARY.md): die gemeinsame Sprache (Aktion, Abgabe, Master, Kanal, Export …)
- [`docs/adr/`](docs/adr/): Entscheidungen, die schwer umkehrbar sind (Deployment, Upload-Weg, Datenbank …)
- [`docs/agents/`](docs/agents/): Hinweise für Coding-Agenten (Issue-Tracker, Labels, Domain-Docs)

## Lokal starten

```bash
uv sync
cd src
DEBUG=1 uv run python manage.py migrate
DEBUG=1 uv run python manage.py campaign --object "M 101" \
  --starts-at 2026-01-01T00:00+01:00 --ends-at 2027-12-31T23:59+01:00 \
  --quota-gib 2 --global-cap-gib 400
DEBUG=1 uv run python manage.py runserver
```

Tests: `uv run pytest` im Repo-Wurzelverzeichnis.
