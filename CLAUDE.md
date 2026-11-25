## Navigation

- Wo was im Code liegt: `docs/agents/codebase.md`.
- Prüfen wie in CI: `scripts/pruefen.sh` (mit Garage und Browser; `--schnell` ohne).
- Changelog-Einträge: eine Datei je Änderung in `changelog.d/`, nicht in `CHANGELOG.md`.
- Pull Requests: jede Session legt am Ende einen PR an, wartet auf die CI und mergt nicht selbst: `docs/agents/pull-requests.md`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `northalpha/schwarmstack` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
