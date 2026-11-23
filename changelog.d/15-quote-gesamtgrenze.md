- Quote, Gesamtgrenze und Abbrechen (#15): Vor dem Start prüft der Server Höchstgröße je Master
  (500 MiB, Einstellung der Aktion), Quote der Abgabe und Gesamtgrenze und reserviert die Größe
  in derselben Transaktion. Uploads lassen sich abbrechen; nach 7 Tagen nicht abgeschlossene
  geben ihre Reservierung frei. Die Abgabeseite zeigt die Belegung. Warum: Der Bucket soll nicht
  über das Budget wachsen, und niemand soll erst nach langem Hochladen scheitern.
