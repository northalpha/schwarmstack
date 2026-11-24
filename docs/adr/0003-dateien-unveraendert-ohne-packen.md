# Dateien werden unverändert gespeichert, ohne Packen und ohne Warteschlange

Hochgeladene Dateien bleiben byte-genau so im S3-Speicher, wie sie ankommen. Es gibt kein Packen (fpack, Archive), keine Auftrags-Warteschlange und keinen Worker; die Prüfung einer Datei läuft synchron, sobald der Upload fertig gemeldet wird. Der Betreiber bearbeitet die Dateien am Ende selbst weiter; Kompression spart bei wenigen Dateien je Submission wenig und erzeugt Formate (`.fz`), die nicht jede Software liest.

## Considered Options

- **Packen je Stack in einem Worker mit DB-Warteschlange** (erster Ansatz): verworfen, weil der Nutzen die Komplexität (Zustandsmaschine, Worker, Wiederholungen) nicht trägt.
