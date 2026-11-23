# Eigenständiges Deployment per CI/CD, ohne Ansible-Abhängigkeit

Schwarmstack wird als Container-Image gebaut und per CI/CD ausgerollt (Staging und Produktion). Das Repo enthält alles, was es zum Bauen und Deployen braucht; es hängt nicht von `home-ansible` oder einem anderen privaten Repo ab. Die erste Fassung ging davon aus, dass eine Ansible-Rolle in einem Nachbar-Repo das Release holt und installiert; das koppelte Projekt und Betrieb unnötig.

- Zwei Umgebungen: **Produktion** unter `upload.dzvf.de` (Hetzner-Host, Hetzner-S3-Bucket) und **Staging** unter `upload.northalpha.de` (eigene kleine Hetzner-VM des Betreibers, eigener Bucket). Staging hängt damit nicht von DNS-Einträgen bei DZVF ab. Lokale Entwicklung läuft ohne Server, mit lokaler Platte.
- Beide laufen mit Docker Compose aus demselben Image: App (gunicorn) und Caddy (TLS). SQLite liegt auf einem Volume.
- GitHub Actions baut das Image nach GHCR. Jeder Push auf `main` rollt nach Staging aus, ein Tag `vX.Y.Z` nach Produktion, mit manueller Freigabe. Ausgerollt wird per SSH (`docker compose pull && docker compose up -d`). Secrets liegen als GitHub-Environment-Secrets.

## Considered Options

- **Ansible-Rolle in `home-ansible`, Release als Tarball** (erster Ansatz): verworfen wegen der Kopplung an ein privates Repo und weil Staging dann nur über den Betreiber testbar war.
