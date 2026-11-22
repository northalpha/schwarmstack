# Schwarmstack

> Viele Teleskope, ein Stack.

Upload-Service für ein Astrofotografie-Community-Projekt (FITS/XISF). Ausgerollt per Ansible
(Repo `home-ansible`), ohne Docker auf den Servern.

## Entwicklung

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
DEBUG=1 DATA_DIR=./var uv run python src/manage.py runserver
```

Settings kommen aus der Umgebung. Pflicht außerhalb von `DEBUG`: `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`.
Weitere: `CSRF_TRUSTED_ORIGINS`, `DATA_DIR`, `HSTS_SECONDS` (nur Produktion), `LOG_LEVEL`.

## Admin und Zweitfaktor

Der Admin liegt unter `/<ADMIN_PATH>/` (Umgebungsvariable, Standard `admin`) und verlangt Passwort
**und** Einmalcode. Ersteinrichtung auf dem Server:

```bash
sudo schwarmstack-manage createsuperuser
sudo schwarmstack-manage otp_setup <benutzer>     # QR-Code für die Authenticator-App und 8 Wiederherstellungscodes
```

Gerät verloren: `otp_setup <benutzer> --reset`. Ohne Gerät kommt niemand in den Admin.

## ALTCHA (optional)

Selbst gehostete Proof-of-Work-Prüfung statt CAPTCHA, ohne Drittanbieter. Pro Event im Admin
(`ALTCHA im Teilnahmeformular`), Standard aus; nur einschalten, wenn Missbrauch auftritt. Formulare
nutzen `AltchaFormMixin` und binden `altcha_gate/widget.html` ein. Widget aktualisieren: siehe
`src/altcha_gate/static/altcha_gate/README.txt`.

## Release

Ein Tag `vX.Y.Z` löst `release.yml` aus. Das Release enthält `schwarmstack-X.Y.Z.tar.gz` und
`schwarmstack-X.Y.Z.tar.gz.sha256`. Die Prüfsumme gehört in `schwarmstack_release_sha256` der Ansible-Rolle.
