# Wo was im Code liegt

Django-Projekt unter `src/` (`manage.py` dort), Tests unter `tests/` (pytest aus der Repo-Wurzel).

```text
src/
├── schwarmstack/          # Projekt: Settings (alles aus der Umgebung), URLs, /healthz
│   ├── operator_site.py   # Admin-Site der Betreiber, Startseite = Statistik
│   ├── login_limit.py     # gebremste Anmeldung (Fehlversuche je IP-Hash)
│   └── staticfiles.py     # WhiteNoise-Storage
├── submissions/           # Fachmodul: Aktion, Submission, Master, Einwilligung
│   ├── models.py
│   ├── services.py        # Fachverhalten zur Submission: anlegen, Master löschen, Löschung, Widerruf
│   ├── uploads.py         # Upload-Ablauf: Quote, Gesamtgrenze, Zeitfenster, Dubletten, Begleitdatei
│   ├── validation.py      # Prüfung der Master (XISF/FITS-Header), Ablehnungskategorien
│   ├── exposure.py        # Belichtungsangaben: Header-Whitelist lesen, Vorschläge, Herkunft (ADR 0010)
│   ├── access.py          # signiertes Cookie: welche Submissions gehören zu diesem Browser
│   ├── views.py, api.py   # Seiten für Teilnehmende / JSON-API für Uppy
│   ├── public.py          # öffentlich ohne Cookie: /zahlen.json (Community-Zahlen, ADR 0009)
│   ├── admin.py           # Admin: Aktion pflegen, Angaben ändern; ruft services auf
│   ├── statistics.py      # Zahlen für die Statistik und die Community-Zahlen
│   └── management/commands/  # campaign.py: die Aktion anlegen/ändern;
│                             # backfill_exposure.py: Belichtungsangaben für Altbestand lesen
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
