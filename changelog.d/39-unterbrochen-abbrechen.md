- Unterbrochene Uploads abbrechen (#39): Jeder unterbrochene Upload hat in der Master-Liste der
  Abgabeseite einen Knopf „Abbrechen“, auch nach dem Neuladen, auch wenn der Upload im Speicher
  nie angelegt wurde, und auch ohne JavaScript. Abbrechen gibt die Reservierung sofort frei, die
  Belegung wird ohne Neuladen aktualisiert. Gab es in den letzten 5 Minuten noch Anfragen, steht
  der Upload als „läuft gerade oder wurde eben unterbrochen“ da, und Abbrechen fragt nach.
  Warum: Bisher ließ sich so ein Upload nur abbrechen, indem man dieselbe Datei noch einmal
  auswählte, und ein nie angelegter blockierte die Quote bis zur Bereinigung nach 7 Tagen.
