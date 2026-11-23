# Master gehen direkt aus dem Browser in den S3-Speicher

Der Browser lädt Master per S3-Multipart-Upload direkt in den Hetzner-S3-Speicher; Django stellt nur die signierten Links aus, prüft Quote und Gesamtgrenze vorab und prüft den Master nach Abschluss über einen Teilabruf des Headers. Die Master-Daten laufen nie durch den App-Server. Upload-Bibliothek im Browser ist Uppy, als Datei im Repo mitgeliefert. Der Bucket braucht dafür eine CORS-Freigabe für die eigene Domain.

## Consequences

- Die Speicher-Schnittstelle hat zwei Adapter: lokale Platte (Modultests, lokale Entwicklung) und S3 (Staging, Produktion). Das Ausstellen signierter Links wird mit `moto` getestet, der Browser-Ablauf in CI gegen Garage als S3-kompatiblen Container (MinIO ist seit 2025 im Wartungsmodus).
- Der Server kann keine Prüfsumme über den Master bilden. Der Browser berechnet beim Hochladen die SHA-256 (gestreamt) und meldet sie beim Abschluss; der Server speichert sie ungeprüft. Sie dient der Kontrolle nach dem Download und dem Erkennen doppelter Dateien.
- Unvollständige Multipart-Uploads räumt eine Lifecycle-Regel im Bucket nach 7 Tagen ab.
- Ausnahme Equipment-Foto: Es ist höchstens 10 MB groß und läuft durch den Server, der es neu speichert und dabei alle EXIF- und GPS-Daten entfernt.

## Considered Options

- **tusd als eigener Upload-Server mit Hooks zu Django** (erster Ansatz): verworfen, weil er einen weiteren Dienst samt Hook-Protokoll bedeutet, ohne bei Dateien bis 2 GB einen Vorteil gegenüber S3-Multipart zu bringen.
