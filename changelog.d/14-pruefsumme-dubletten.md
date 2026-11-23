- Prüfsumme und Dubletten (#14): Der Browser berechnet die SHA-256 mit WebCrypto in einem Web
  Worker parallel zum Upload und meldet sie mit der Fertig-Meldung;
  der Server übernimmt sie ungeprüft. Dieselbe Datei in derselben Abgabe wird abgelehnt, in
  einer anderen angenommen und als Dublette des ersten Masters markiert. Prüfsumme und Dublette
  stehen in der Begleitdatei. Warum: Kontrolle nach dem Download und Erkennen doppelter Dateien.
