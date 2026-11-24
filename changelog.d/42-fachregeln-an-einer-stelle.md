- Fachregeln an einer Stelle (#42): Gesamtgrenze nicht unter der Belegung, Belegung je Abgabe,
  Rückzug nach Widerruf, Zeitfenster des Uploaders und „Ende nach Beginn“ stehen nur noch in
  `uploads`, `services` und im Modell; Admin, Abgabeseite und `manage.py campaign` fragen dort
  nach. `manage.py campaign` prüft dabei alle Angaben wie der Admin. Warum: Ändert sich eine
  Regel, sollen Admin-Liste, Abgabeseite und Befehl nicht unbemerkt Verschiedenes zeigen.
