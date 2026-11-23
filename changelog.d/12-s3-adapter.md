- S3-Adapter und Browser-Durchlauf (#12): Speicher im S3-Bucket (`STORAGE_BACKEND=s3`), gemeinsame
  Vertragstests für lokale Platte, `moto` und Garage, ein Playwright-Durchlauf mit Uppy gegen
  Garage in CI, `manage.py s3_bucket_setup` für CORS und Lifecycle-Regel, Betriebsanleitung in
  `docs/betrieb/s3-speicher.md`. Warum: Staging und Produktion laufen auf S3, und der Weg
  Browser → S3 → Abschluss soll vor jedem Rollout einmal wirklich gelaufen sein.
