- Bucket-Einrichtung beim Deploy (#73): Verweigert der Speicher das Setzen von CORS oder
  Lifecycle mit `AccessDenied`, warnt `s3_bucket_setup` nur und lässt den CORS-Preflight
  entscheiden; passt er, läuft der Deploy weiter. Andere Fehler brechen weiter ab. Warum: Hetzner
  verweigert seit dem 24.11.2026 diese Schreibzugriffe im ganzen Projekt, die Freigaben aus
  früheren Deploys greifen aber weiter. Ohne den Workaround blieb Staging auf einer alten Version.
