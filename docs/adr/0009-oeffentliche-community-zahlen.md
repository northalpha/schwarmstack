# Öffentliche Community-Zahlen ohne Zugang

Schwarmstack gibt unter `GET /zahlen.json` die Community-Zahlen aus: Abgaben, angenommene Master und ihre Datenmenge in Bytes, als flaches JSON ohne Versionspräfix. Der Endpunkt ist öffentlich, ohne Token und ohne Cookie, damit die Community-Seite (extern wie die Projektwebsite) die Zahlen direkt im Browser abrufen kann. Öffentlich sind nur aggregierte Summen, nie Namen, Kennungen oder einzelne Abgaben; die Statistik bleibt eine reine Betreiber-Sicht.

## Consequences

- Neue Felder kommen nur additiv dazu (etwa Werte aus den Headern, #50); bestehende Schlüssel ändern sich nicht.
- Die Zahlen rechnet eine eigene, rein lesende Funktion; der öffentliche Pfad schreibt nie (kein Aufräumen liegengebliebener Uploads wie in der Statistik).
- Ein Cache im Prozess (`LocMemCache`, Standard 10 s, `COMMUNITY_CACHE_SECONDS`) begrenzt die Last; Gunicorn-Worker können kurz voneinander abweichen. Ein Rate-Limit macht Caddy, nicht die App.
- CORS setzt die Ansicht von Hand für die Ursprünge aus `COMMUNITY_ORIGINS`; `*` ist nur zum Testen auf Staging gedacht. Basic Auth auf Staging lässt `/zahlen.json` wie `/healthz` durch.
- Der Endpunkt antwortet immer mit 200, auch vor Beginn und nach Ende der Aktion; er verschwindet erst mit dem Abbau der Installation (ADR 0008).

## Considered Options

- **Zahlen von Hand auf die Community-Seite übertragen**: verworfen, weil die Betreiber das während der Aktion täglich tun müssten.
- **`django-cors-headers`**: verworfen; für einen einzigen Endpunkt reichen zwei Header, eine weitere Abhängigkeit lohnt nicht.
- **Endpunkt in `api.py`**: verworfen, dort ist alles an die Abgabe aus dem Cookie gebunden.
