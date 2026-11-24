- Belichtungsangaben je Master (#50): Belichtung pro Light, Anzahl Lights, Gesamtbelichtung,
  Instrument und Teleskop werden beim Abschluss des Uploads aus dem Header gelesen (nur eine
  feste Auswahl von Schlüsseln, nie Standort oder Beobachter). Auf der Abgabeseite können
  Teilnehmende sie bis zum Ende der Aktion ergänzen und korrigieren, danach die Betreiber im
  Admin. Fehlende Werte schlägt der Server vor, statt sie still zu übernehmen. Für schon
  hochgeladene Master trägt `manage.py backfill_exposure` die Werte nach. Warum: Die Betreiber
  brauchen die Belichtung je Kanal für die Weiterverarbeitung, und die Header der Programme sind
  uneinheitlich (z. B. ist `EXPTIME` beim DWARF die Gesamtzeit).
