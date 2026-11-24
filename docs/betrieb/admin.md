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

## Deployment

`ADMIN_PATH` steht als Variable im GitHub-Environment und kommt mit jedem Deploy in die `.env`;
ohne ihn bricht der Deploy-Job ab. Die statischen Dateien des Admin liegen im Image und kommen
über WhiteNoise. Siehe [`deployment.md`](deployment.md).
