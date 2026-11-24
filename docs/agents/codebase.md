# Wo was im Code liegt

Django-Projekt unter `src/` (`manage.py` dort), Tests unter `tests/` (pytest aus der Repo-Wurzel).

```text
src/
├── schwarmstack/          # Projekt: Settings (alles aus der Umgebung), URLs, /healthz
│   ├── operator_site.py   # Admin-Site der Betreiber, Startseite = Statistik
│   ├── login_limit.py     # gebremste Anmeldung (Fehlversuche je IP-Hash)
│   └── staticfiles.py     # WhiteNoise-Storage
├── submissions/           # Fachmodul: Aktion, Abgabe, Master, Einwilligung
│   ├── models.py
│   ├── services.py        # Fachverhalten zur Abgabe: anlegen, Master löschen, Rückzug, Widerruf
│   ├── uploads.py         # Upload-Ablauf: Quote, Gesamtgrenze, Zeitfenster, Dubletten, Begleitdatei
│   ├── validation.py      # Prüfung der Master (XISF/FITS-Header), Ablehnungskategorien
│   ├── access.py          # signiertes Cookie: welche Abgaben gehören zu diesem Browser
│   ├── views.py, api.py   # Seiten für Teilnehmende / JSON-API für Uppy
│   ├── admin.py           # Admin: Aktion pflegen, Abgaben korrigieren; ruft services auf
│   ├── statistics.py      # Zahlen für die Statistik
│   └── management/commands/campaign.py   # die Aktion anlegen/ändern
└── storage/               # Speicher-Modul: Protokoll in __init__.py, Adapter local.py und s3.py;
                           # local_views.py bildet für Uppy S3 nach (nur lokaler Speicher)
tests/
├── conftest.py, settings_test.py
├── storage_backends.py    # Adapter-Fixtures: lokal, moto, Garage (Garage nur mit scripts/garage.sh)
├── uploads_helper.py      # Upload-Schritte wie der Browser (start, sign, send_parts, finish)
├── admin_helper.py        # Betreiber-Fixtures, Admin-URLs, Formulardaten
├── files.py               # erzeugt XISF/FITS-Testdateien
└── e2e/                   # E2E-Test im echten Browser gegen Garage
deploy/                    # Compose, Caddy, Skripte für Host und Deploy (docs/betrieb/deployment.md)
scripts/                   # pruefen.sh (alle Prüfungen wie CI), garage.sh, glossar.py, changelog.py;
                           # header_prototyp.py: Wegwerf-Prototyp, zeigt Header roh (Issue #49)
```

Prüfen wie in CI: `scripts/pruefen.sh` (braucht Docker für Garage; ohne: `--schnell`).
In einer Cloud-Sitzung läuft der Docker-Daemon nicht von selbst: `dockerd &>/tmp/dockerd.log &`.
