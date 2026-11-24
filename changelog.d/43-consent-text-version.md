- Fassung des Hinweistextes einstellbar beim Deploy (#43): `CONSENT_TEXT_VERSION` steht jetzt in
  `docs/betrieb/deployment.md` und wird als Variable aus dem GitHub-Environment in die `.env`
  übernommen. Warum: Jede Einwilligung speichert diese Fassung; bisher galt auf dem Host immer der
  Standard `2026-11`, auch nach einer Änderung des Hinweistextes.
