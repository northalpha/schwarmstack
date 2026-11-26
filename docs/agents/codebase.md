# Wo was im Code liegt

Django-Projekt unter `src/` (`manage.py` dort), Tests unter `tests/` (pytest aus der Repo-Wurzel).

```text
src/
├── schwarmstack/          # Projekt: Settings (alles aus der Umgebung), URLs, /healthz
│   ├── operator_site.py   # Admin-Site der Betreiber, Startseite = Statistik
│   ├── login_limit.py     # gebremste Anmeldung (Fehlversuche je IP-Hash, höchstens 1 Stunde)
│   ├── notices.py         # Betriebsmeldungen per Mail an die Betreiber (ADR 0007)
│   └── staticfiles.py     # WhiteNoise-Storage
├── submissions/           # Fachmodul: Aktion, Submission, Master, Einwilligung
│   ├── models.py
│   ├── services.py        # Fachverhalten zur Submission (Details im Modul-Docstring)
│   ├── export.py          # Export: Manifest, Download-Liste (aria2c), endgültiger Export
│   ├── deletion.py        # Löschung nach Ablauf der Löschfrist (manage.py delete_after_export)
│   ├── privacy.py         # Datenschutzhinweis je Fassung (templates/submissions/datenschutz/)
│   ├── uploads.py         # Upload-Ablauf und seine Regeln (Details im Modul-Docstring)
│   ├── photos.py          # Equipment-Foto bereinigen: dekodieren, nur Pixel neu schreiben (#82)
│   ├── validation.py      # Prüfung der Master (XISF/FITS-Header), Ablehnungskategorien
│   ├── exposure.py        # Belichtungsangaben (ADR 0010)
│   ├── access.py          # signiertes Cookie: welche Submissions gehören zu diesem Browser
│   ├── views.py, api.py   # Seiten für Teilnehmende / JSON-API für Uppy
│   ├── public.py          # öffentlich ohne Cookie: /zahlen.json (Community-Zahlen, ADR 0009)
│   ├── admin.py           # Admin: Aktion pflegen, Angaben ändern; ruft services auf
│   ├── statistics.py      # Zahlen für die Statistik und die Community-Zahlen
│   └── management/commands/  # campaign.py: die Aktion anlegen/ändern;
│                             # backfill_exposure.py: Belichtungsangaben für Altbestand lesen
│                             # delete_after_export.py: Löschung nach Ablauf der Löschfrist
└── storage/               # Speicher-Modul: Protokoll in __init__.py, Adapter local.py und s3.py;
                           # local_views.py bildet für Uppy S3 nach (nur lokaler Speicher)
tests/
├── conftest.py, settings_test.py
├── storage_backends.py    # Adapter-Fixtures: lokal, moto, Garage (Garage nur mit scripts/garage.sh)
├── uploads_helper.py      # Upload-Schritte wie der Browser (start, sign, send_parts, finish)
├── admin_helper.py        # Betreiber-Fixtures, Admin-URLs, Formulardaten
├── files.py               # erzeugt XISF/FITS-Testdateien
├── photo_files.py         # erzeugt Equipment-Fotos mit allen Metadaten je Format
└── e2e/                   # E2E-Test im echten Browser gegen Garage
deploy/                    # Compose, Caddy, Skripte für Host und Deploy (docs/betrieb/deployment.md)
└── selbst/                # Selbstbetrieb: compose.yaml (App, Caddy, Garage), setup.sh (docs/betrieb/selbstbetrieb.md)
scripts/                   # pruefen.sh (alle Prüfungen wie CI), ausnahmen.py (liest `sicherheit-ausnahmen.toml` im Repo-Root: Ausnahmen für Sicherheitsfunde, ADR 0012; `.github/`: Workflows, dependabot.yml, zizmor.yml), selbstbetrieb-test.sh (Installer-Test), garage.sh, glossar.py, changelog.py;
                           # release.py + image-pruefen.sh: Release-Hilfen (Skill /release, release.yml);
                           # header_prototyp.py: Wegwerf-Prototyp, zeigt Header roh (Issue #49)
```

Prüfen wie in CI: `scripts/pruefen.sh` (braucht Docker für Garage; ohne: `--schnell`).
In einer Cloud-Sitzung läuft der Docker-Daemon nicht von selbst: `dockerd &>/tmp/dockerd.log &`.
