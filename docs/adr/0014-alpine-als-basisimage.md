# Alpine als Basisimage, Distroless nur bewertet

Das Image (ADR 0001, 0011) war `python:3.13-slim-trixie`. In #121 meldete Trivy Funde in Systempaketen und in den Bibliotheken von `pip`; behoben wurde das mit `pip uninstall` und `apt-get upgrade`. #127 fragt, ob ein kleineres Basisimage solche Funde gar nicht erst entstehen lässt.

## Entscheidung

- Das Image baut auf `python:3.13-alpine`. Das Entfernen von `pip` bleibt, `apt-get upgrade` wird zu `apk upgrade --no-cache`. Benutzer und Gruppe haben weiter die uid/gid 10001, `/data` gehört ihnen wie bisher.
- **Test im Image:** `scripts/image-pruefen.sh` schickt je ein JPEG, PNG, WebP und HEIC (mit Metadaten) im gebauten Image durch `submissions.photos` (`scripts/image_foto_pruefen.py`). Der `image`-Job in `ci.yml` ruft das Skript auf (und gibt die Imagegröße aus); der Release-Workflow ruft es schon auf, damit gilt der Fototest auch als Gate vor einem Release. Grund: Die Tests laufen auf glibc, das Image auf musl, und der Smoke-Test prüft nur `/healthz`.
- **Installer-Test:** `ci.yml` startet den Job `selbstbetrieb` jetzt auch bei Änderungen am `Dockerfile`, denn der Test baut das Image selbst.
- **Distroless:** nicht umgesetzt, siehe unten.

## Messwerte

Lokal gebaut, `linux/amd64`, gleiche Quellen und `uv.lock`:

| | `python:3.13-slim-trixie` | `python:3.13-alpine` |
| --- | --- | --- |
| Imagegröße (`docker image inspect`) | 380 MB | 277 MB (−27 %) |
| Systempakete (`dpkg -l` / `apk list -I`) | 87 | 29 |
| Equipment-Foto bereinigen, 7 MB JPEG, 6000×4000 | 0,68 s | 0,70 s |
| Equipment-Foto bereinigen, 3,4 MB HEIC | 0,46 s | 0,53 s |
| Speicher-Spitze in dieser Messung (JPEG / HEIC) | 380 / 613 MiB | 373 / 613 MiB |
| JPEG, PNG, WebP, HEIC im Image bereinigt | ja | ja |

Die Speicher-Spitze enthält das Erzeugen des Testbilds im selben Prozess; sie taugt nur zum Vergleich. Unter musl zeigte sich kein spürbarer Nachteil bei großen Fotos.

**CI (Alpine 3.24, mit `apk upgrade`):** Trivy meldet im `image`-Job 0 Funde bei 29 Systempaketen und in allen Python-Paketen. Einen Trivy-Vergleich mit dem alten Debian-Image gibt es nicht; die lokalen Größen oben entstanden ohne `apk upgrade`, weil die Sandbox `dl-cdn.alpinelinux.org` sperrt. Das Gate und die Schwellen (ADR 0012) bleiben unverändert. `linux/arm64`: Für `pillow` und `pillow-heif` gibt es laut `uv.lock` `musllinux`-Wheels für `aarch64`, gebaut wurde nur `amd64`; der Release-Workflow baut beide Plattformen.

## Distroless (bewertet, nicht umgesetzt)

`gcr.io/distroless/python3-debian13` hat keine Shell, kein `pip` und kein `apt`, nutzt glibc wie die Tests und ist für beide Plattformen da. Der Umbau kostet mehr, als er bringt:

- Die venv muss zum festen Python des Images passen; der Build-Schritt braucht dasselbe Python wie das Laufbild.
- Der Benutzer ist `nonroot` (uid 65532); `/data` und alle Bind-Mounts der Compose-Dateien (uid 10001) müssten umgestellt werden, auch bei bestehenden Installationen.
- `scripts/image-pruefen.sh` und der Smoke-Test nutzen `sh` im Container und müssten über einen Hilfscontainer oder `docker export` laufen.
- `docs/betrieb/selbstbetrieb.md` beschreibt Fehlersuche im Container; ohne Shell gäbe es nur `docker debug` oder ein zweites Image.

Alpine liefert den größten Teil des Gewinns (wenige Pakete, keine Debian-Funde) ohne diese Kosten. Distroless lohnt erst, wenn Alpine-Funde dauerhaft stören.

## Consequences

- Die App läuft produktiv auf musl, getestet wird die Python-Ebene weiter auf glibc; der Fototest im Image deckt die native Seite ab. Fällt ein künftiges Wheel für musl aus, schlägt der Build fehl, statt zu kompilieren, denn `uv sync` hat keinen Compiler im Image.
- Fehlersuche im Container geht mit `sh` (busybox), nicht mit `bash`.
- Basisimage-Updates kommen weiter über Dependabot (ADR 0012).

## Considered Options

- **Bei `slim-trixie` bleiben:** hätte funktioniert; verworfen, weil Alpine ein Viertel kleiner ist und weniger Pakete mitbringt, ohne dass der Betrieb komplizierter wird.
- **Distroless:** siehe oben.
