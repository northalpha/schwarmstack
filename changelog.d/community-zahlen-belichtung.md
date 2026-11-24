- Community-Zahlen mit Belichtung (#50, #53): `GET /zahlen.json` liefert zusätzlich `lights`,
  `exposureSeconds` (ganze Sekunden) und `mastersWithExposure`. Summiert wird über angenommene Master
  ohne Dubletten; Master ohne Angaben fehlen in den Summen und zählen nicht in
  `mastersWithExposure`. Warum: Die Community-Seite soll die aufsummierte Belichtung zeigen.
