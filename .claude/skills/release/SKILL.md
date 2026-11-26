---
name: release
description: "Einen Release vorbereiten: /release <version> öffnet den PR „Release vX.Y.Z“. Merge ist Release (ADR 0011)."
disable-model-invocation: true
---

Bereite den Release `<version>` vor (Form `X.Y.Z`, ohne „v“). Der Skill öffnet nur den PR. Er merged nie selbst und setzt weder Tag noch Release: Das tut `.github/workflows/release.yml` nach dem Merge durch die Betreiber (ADR 0011).

## Ablauf

1. **Version prüfen:** `git fetch origin main --tags`, dann `uv run python scripts/release.py pruefen <version>`. Schlägt es fehl (keine gültige Form, nicht größer als der letzte Release), abbrechen und das den Betreibern sagen.
2. **`main` grün?** Der letzte Lauf von `CI` auf `main` muss grün sein (`test` und `image`; `staging`, `production`, `von-hand` dürfen übersprungen sein). In der Cloud-Sitzung mit den GitHub-MCP-Tools (`get_commit` für den Stand von `main`, `actions_list` und `get_check_run` für die Läufe). Ist er rot oder läuft noch, abbrechen.
3. **Auf `main` aufsetzen:** Branch von `origin/main` anlegen (in einer Session mit vorgegebenem Branch: diesen auf `origin/main` bringen, nicht rebasen). Es darf nichts anderes im Arbeitsbaum liegen.
4. **Changelog sammeln:** `uv run python scripts/changelog.py sammeln <version>`. Ist `changelog.d/` leer, gibt es nichts zu veröffentlichen: abbrechen.
5. **Version setzen:** `uv run python scripts/release.py version <version>`, danach `uv lock`, damit `uv.lock` dieselbe Version trägt.
6. **Prüfen:** `scripts/pruefen.sh` (Cloud: ggf. `dockerd &>/tmp/dockerd.log &`, sonst `--schnell` und im PR sagen, dass es so war).
7. **Committen und pushen:** ein Commit „Release vX.Y.Z“ mit genau diesen Änderungen: `CHANGELOG.md`, gelöschte `changelog.d/*.md`, `pyproject.toml`, `uv.lock`.
8. **PR „Release vX.Y.Z“ gegen `main` anlegen** nach `docs/agents/pull-requests.md` und Skill `pr`. Der Text nennt den Changelog-Abschnitt und sagt: Der Merge löst den Release aus (Tests, Image für `linux/amd64` und `linux/arm64` nach `ghcr.io/northalpha/schwarmstack`, dann Tag und GitHub Release). Danach den PR abonnieren, auf die CI warten und melden. **Nicht mergen.**

## Danach

Nach dem Merge läuft `release.yml` auf `main`. Es ist erst fertig, wenn Tag `vX.Y.Z` und GitHub Release da sind. Schlägt ein Schritt davor fehl, gibt es beides nicht; dann Ursache beheben und den Lauf erneut starten oder einen Folge-PR öffnen. Deployt wird nichts von selbst: Produktion nur über *Run workflow* in `ci.yml` mit dem Image-Tag `vX.Y.Z`.

## Probelauf

`release.yml` hat einen manuellen Auslöser mit `dry_run` (Standard an): Er baut und prüft das Image, pusht aber nichts und setzt weder Tag noch Release. Er geht auch in einem Fork.
