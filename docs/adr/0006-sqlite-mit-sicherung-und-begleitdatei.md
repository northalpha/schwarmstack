# SQLite mit täglicher Sicherung und einer Begleitdatei je Master

Die Datenbank ist SQLite. Sie wird täglich per `sqlite3 .backup` in einen eigenen Pfad im S3-Bucket gesichert (14 Tage aufbewahrt). Zusätzlich liegt neben jedem Master eine kleine JSON-Datei mit den Angaben der Abgabe und des Masters, damit die Zuordnung auch ohne Datenbank rekonstruierbar ist: Ohne sie wären die Master im S3 nur namenlose Dateien.

## Considered Options

- **Postgres**: verworfen, für eine einmalige Aktion mit wenigen hundert Abgaben unnötiger Betriebsaufwand.
