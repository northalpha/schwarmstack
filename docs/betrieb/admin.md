# Admin für die Betreiber

Der Admin (Ticket #29) liegt unter `/<ADMIN_PATH>/`, nicht unter `/admin/`. Startseite ist die
Statistik.

## Einstellungen

| Variable | Pflicht | Bedeutung |
| --- | --- | --- |
| `ADMIN_PATH` | in Produktion ja | Pfad des Admin ohne Schrägstriche, z. B. eine zufällige Zeichenfolge. Fehlt er bei `DEBUG=0`, startet die App nicht. Lokal (`DEBUG=1`) ist `betrieb` der Standard. |
| `TRUST_X_FORWARDED_FOR` | nein | Standard bei `DEBUG=0`: an. Die IP für das Rate-Limit kommt dann aus dem letzten Eintrag von `X-Forwarded-For` (Caddy). Nur abschalten, wenn kein Proxy davor steht. |
| `LOGIN_ATTEMPTS_MAX` | nein | Fehlversuche je IP im Zeitfenster, danach Sperre (Standard 5). |
| `LOGIN_ATTEMPTS_WINDOW_SECONDS` | nein | Zeitfenster der Sperre in Sekunden (Standard 900). |

Fehlversuche zählt die Datenbank (SQLite), nicht der Cache: gunicorn läuft mit mehreren Prozessen.
Die IP steht nur als HMAC-Hash darin (ADR 0002).

## Betreiber-Konten

Je Betreiber ein eigenes Konto, alle mit denselben Rechten:

```bash
docker compose run --rm app python manage.py createsuperuser
```

Lokal ohne Docker: `uv run python src/manage.py createsuperuser`.

## Was der Admin kann

- **Aktion**: Ende, Nachfrist, Quote, Gesamtgrenze und Höchstgröße ändern. Objekt und Beginn sind
  ab dem Start gesperrt; die Gesamtgrenze darf nicht unter die aktuelle Belegung sinken. Quote
  und Gesamtgrenze stehen in GiB, die Höchstgröße je Master in MiB, wie bei `manage.py campaign`
  (Komma oder Punkt, z. B. `1,5`). Anlegen und Löschen gehen nur per `manage.py campaign` bzw.
  gar nicht (ADR 0004).
- **Abgaben**: suchen nach Abgabe-Kennung oder Nennung, Nennung und Setup korrigieren (auch nach
  dem Ende der Aktion), einzelne Master löschen, Abgabe zurückziehen, Widerruf vermerken. Eine
  Nennung gibt es nur mit gültiger Einwilligung zur Veröffentlichung: Anonyme Abgaben zeigen
  „anonym“ und bekommen auch nachträglich keinen Namen. Mit Einwilligung lässt sich die Nennung
  nicht leeren; soll die Abgabe anonym werden, den Widerruf der Veröffentlichung vermerken. Er
  löscht die Nennung samt Eintrag in den Begleitdateien.
- **Download zur Kontrolle**: einzelne angenommene Master über einen Link, der
  `UPLOAD_LINK_SECONDS` (Standard 15 Minuten) gilt.
- **Protokoll**: jede Änderung, Löschung, jeder Rückzug, Widerruf und Download mit Betreiber und
  Zeitpunkt.

## Export und Löschfrist

Unter *Aktion → Export* (ADR 0008):

- **Vorläufiger Export**: jederzeit das Manifest (`manifest-vorlaeufig.json`) nach heutigem Stand,
  ohne Download-Links. Stichproben weiter über den Download einzelner Master.
- **Endgültiger Export**: genau einmal, frühestens nach Ende der Aktion plus Nachfrist, mit
  Rückfrage. Danach ist alles eingefroren, auch für Betreiber: keine Korrektur von Nennung und
  Setup, kein Master löschen, keine Änderung an der Aktion. Widerruf und Rückzug bleiben möglich.
- **Links**: Nach dem endgültigen Export stellt jedes Herunterladen von Manifest oder
  Download-Liste neue Links aus, die 7 Tage gelten; jedes Ausstellen steht im Protokoll. Neue
  Links gibt es bis zum Ablauf der Löschfrist.
- **Herunterladen**: `aria2c -i download-liste.txt -d <Ziel>`. Die Liste legt die Dateinamen fest
  (`SW-7K3Q/Ha_3f9c1a2b.xisf`: Abgabe-Kennung als Ordner, Kanal, Anfang der Master-ID; der
  Originalname steht nur im Manifest), und aria2c gleicht nach dem Laden die Prüfsumme ab.
- **Manifest**: je Abgabe Kennung, Nennung (nur bei gültiger Einwilligung zur Veröffentlichung),
  Setup, Anlagezeitpunkt, alle Einwilligungen mit Art, Zeitpunkt, Fassung und Widerruf; je
  angenommenem Master Kanal, Originalname, Größe, Prüfsumme, Dublettenverweis, Zielpfad und (nach
  dem endgültigen Export) Link. Zurückgezogene Abgaben nur mit Kennung und Zeitpunkt. Das Manifest
  ist nach der Löschung der einzige Nachweis der Einwilligungen: aufbewahren.
- **Nachtrag**: Widerruf oder Rückzug nach dem endgültigen Export wirkt sofort, wird an der
  Abgabe vermerkt (`amended_at` im Manifest, Filter „Nachtrag“ in der Liste der Abgaben, Liste
  auf der Export-Seite) und per Betriebsmeldung gemeldet, nur mit der Abgabe-Kennung. Danach
  lokale Kopien und die Credits-Liste anpassen.
- **Löschfrist**: 30 Tage ab dem endgültigen Export; die restlichen Tage stehen auf der Statistik
  und der Export-Seite. Sieben Tage vorher und nach der Löschung kommt eine Betriebsmeldung. Die
  Löschung (`manage.py delete_after_export`, täglich per Cron) entfernt alle Objekte im Bucket
  außer `sicherungen/`, alle Abgaben samt Mastern und Einwilligungen, die Fehlversuche der
  Anmeldung und die Protokolleinträge zu Abgaben. Es bleiben die Aktion mit den Zeitpunkten von
  Export und Löschung, ihre Protokolleinträge und die Betreiber-Konten. Den Abbau der Installation
  macht ihr danach von Hand.

## Deployment

`ADMIN_PATH` steht als Variable im GitHub-Environment und kommt mit jedem Deploy in die `.env`;
ohne ihn bricht der Deploy-Job ab. Die statischen Dateien des Admin liegen im Image und kommen
über WhiteNoise. Siehe [`deployment.md`](deployment.md).
