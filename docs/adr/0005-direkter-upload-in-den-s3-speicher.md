# Master gehen direkt aus dem Browser in den S3-Speicher

Der Browser lädt Master per S3-Multipart-Upload direkt in den Hetzner-S3-Speicher; Django stellt nur die signierten Links aus, prüft Quote und Gesamtgrenze vorab und prüft den Master nach Abschluss über einen Teilabruf des Headers. Die Master-Daten laufen nie durch den App-Server. Upload-Bibliothek im Browser ist Uppy, als Datei im Repo mitgeliefert. Der Bucket braucht dafür eine CORS-Freigabe für die eigene Domain.

## Consequences

- Die Speicher-Schnittstelle hat zwei Adapter: lokale Platte (Modultests, lokale Entwicklung) und S3 (Staging, Produktion). Das Ausstellen signierter Links wird mit `moto` getestet, der Browser-Ablauf in CI gegen Garage als S3-kompatiblen Container (MinIO ist seit 2025 im Wartungsmodus).
- Der Server kann keine Prüfsumme über den Master bilden. Der Browser berechnet beim Hochladen die SHA-256 in einem Web Worker parallel zum Upload und meldet sie beim Abschluss; der Server speichert sie ungeprüft. Sie dient der Kontrolle nach dem Download und dem Erkennen doppelter Dateien. Berechnet wird sie mit WebCrypto, das nur ganze Puffer hasht: Die Datei liegt dafür kurz vollständig im Speicher des Browsers. Das ist vertretbar, weil ein Master höchstens 500 MB groß ist; der Worker hasht die Dateien nacheinander.
- Unvollständige Multipart-Uploads räumt eine Lifecycle-Regel im Bucket nach 7 Tagen ab.
- Ausnahme Equipment-Foto: Es ist höchstens 10 MB groß und läuft durch den Server, der es neu speichert und dabei alle EXIF- und GPS-Daten entfernt.
- Ein Master ist höchstens 500 MB groß; die Grenze wird beim Start des Uploads geprüft.

## Considered Options

- **tusd als eigener Upload-Server mit Hooks zu Django** (erster Ansatz): verworfen, weil er einen weiteren Dienst samt Hook-Protokoll bedeutet, ohne bei Dateien bis 500 MB einen Vorteil gegenüber S3-Multipart zu bringen.
- **SHA-256 schrittweise in eigenem JavaScript**: verworfen, als feststand, dass Master höchstens 500 MB groß sind. Es hätte große Dateien ohne Speicherspitze gehasht, ist aber eigener Krypto-Code und etwa fünfmal langsamer als WebCrypto.
