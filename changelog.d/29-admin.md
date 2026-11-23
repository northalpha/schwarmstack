- Admin für die Betreiber (#29): Djangos Admin unter `/<ADMIN_PATH>/` mit eigenem Konto je
  Betreiber und gebremster Anmeldung (Fehlversuche je IP-Hash in der Datenbank). Startseite ist
  die Statistik: Abgaben, Master je Zustand und Kanal, Belegung gegen die Gesamtgrenze,
  Dubletten, Ablehnungen nach Kategorie und Verlauf je Tag. Die Aktion lässt sich pflegen (Objekt
  und Beginn ab dem Start gesperrt, Gesamtgrenze nicht unter der Belegung). Abgaben suchen,
  filtern und korrigieren; Master löschen, Rückzug und Widerruf als Fachverhalten, einzelne Master
  über einen kurz gültigen Link herunterladen; alles im Protokoll. Die Prüfung liefert jetzt eine
  feste Kategorie je Ablehnung. Warum: Die Betreiber sollen den Stand der Aktion sehen und
  Anfragen von Teilnehmenden ohne Zugang zum Server erledigen können. Betrieb:
  `docs/betrieb/admin.md`.
