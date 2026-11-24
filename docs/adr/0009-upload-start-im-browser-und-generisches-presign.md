# Der Browser legt den Multipart-Upload an, der Server signiert jede S3-Anfrage einzeln

Beim Start eines Uploads prüft der Server Zeitfenster, Kanal, Endung, Höchstgröße, Quote und Gesamtgrenze, reserviert die Größe und legt den Master mit seinem Objekt-Schlüssel an. Den Multipart-Upload legt er nicht selbst an: Er gibt nur einen signierten Link für CreateMultipartUpload zurück, und der Browser führt ihn aus. Danach signiert der Server jede weitere S3-Anfrage des Browsers (Teil hochladen, Teile auflisten, abschließen, abbrechen) einzeln, wenn sie zum Schlüssel und zur Upload-ID des Masters passt. Die Speicher-Schnittstelle hat dafür ein generisches `presign` für eine S3-Anfrage statt eigener Operationen je Schritt.

Grund ist das AWS-S3-Plugin von Uppy: Es reicht jede S3-Anfrage an einen einzigen Hook `signRequest` und führt sie dann selbst aus, auch das Fortsetzen über die Liste der Teile. Ein generisches `presign` bildet diesen Hook eins zu eins ab. Der Server spricht während des Uploads nie mit dem Speicher, bleibt aus dem Datenweg (ADR 0005) und hat einen Endpunkt für alle Anfragen statt fünf.

## Consequences

- Der Server vertraut der Upload-ID des Browsers. Er kennt sie nicht aus dem Speicher, sondern übernimmt sie aus der ersten Anfrage, die er signieren soll, und signiert danach nur noch Anfragen mit genau dieser ID. Das ist tragbar, weil der Speicher eine Upload-ID an den Schlüssel bindet, unter dem sie angelegt wurde, und der Server nur den eigenen, von ihm gebildeten Schlüssel des Masters signiert. Eine falsche oder erfundene Upload-ID trifft also nur den eigenen Master: Seine Anfragen scheitern im Speicher, der Upload wird nie fertig. Abbrechen gibt die Reservierung trotzdem frei, sonst nach 7 Tagen die Bereinigung aufgegebener Uploads.
- Ob die Upload-ID an den Schlüssel gebunden ist, prüfen die Contract Tests für die lokale Platte und Garage. `moto` bildet das nicht nach; der Test ist dort als bekannte Abweichung markiert.
- Der signierte Link zum Anlegen gilt bis zu seinem Ablauf und lässt sich mehrfach ausführen. Weitere Multipart-Uploads unter demselben Schlüssel bekommen keine Signaturen und bleiben leer; die Lifecycle-Regel räumt sie ab.
- Beim Abschluss prüft der Server nur das fertige Objekt unter dem Schlüssel (Größe, Header), nicht die Upload-ID oder die Teile. Wie viel ein veränderter Browser vor dem Abschluss in Teilen hochladen kann, regelt der Budgetschutz beim Signieren der Teile, nicht dieser Ablauf.
- Ist die Upload-ID nie beim Server angekommen (Browser nach CreateMultipartUpload geschlossen), lässt sich der Upload nicht fortsetzen und nicht im Speicher abbrechen. Der Master wird abgebrochen oder nach 7 Tagen freigegeben, den leeren Multipart-Upload räumt die Lifecycle-Regel ab.
- Der lokale Adapter bildet die S3-Antworten für Uppy über einen app-eigenen Endpunkt nach, damit derselbe Ablauf ohne S3 läuft.
- Die Speicher-Schnittstelle hat neben `presign` nur die Operationen, die der Server selbst ausführt: Größe, Range Request, Löschen, Begleitdatei, Multipart abbrechen, Erreichbarkeit und Download-Link.

## Considered Options

- **Server legt den Multipart-Upload an und schließt ihn ab, mit eigenen Speicher-Operationen je Schritt** (so in der ursprünglichen Spec beschrieben): verworfen. Uppy hätte fünf eigene Hooks gebraucht, die jeweils einen Endpunkt und eine S3-Anfrage vom Server aus bedeuten. Die Upload-ID wäre geprüft, aber eine falsche ID schadet ohnehin nur dem eigenen Master. Ein Abschluss über den Server würde die Teile vor dem Zusammensetzen sehen; das wird interessant, falls der Budgetschutz beim Signieren nicht ausreicht.
