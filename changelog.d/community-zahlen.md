- Community-Zahlen (#53): `GET /zahlen.json` liefert öffentlich die Zahl der Abgaben, der
  angenommenen Master und ihre Datenmenge in Bytes, mit CORS für die Ursprünge aus
  `COMMUNITY_ORIGINS` und einem kurzen Cache (`COMMUNITY_CACHE_SECONDS`, Standard 10 s). Warum: Die
  Community-Seite soll den Stand der Aktion zeigen, ohne dass die Betreiber Zahlen abschreiben.
