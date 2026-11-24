- Begriffe nach dem Glossar (#66): Aus der Abgabe wird die Submission, aus der Abgabe-Kennung die
  Submission-ID, aus dem Rückzug die Löschung („Submission löschen“) und aus der Nennung die
  Namensnennung; im Admin heißt es „Angaben ändern“. Felder `deleted_at`/`deleted_by` per
  Migration umbenannt, die Daten bleiben. Seiten liegen jetzt unter `/submission/<ID>/`, alte
  Adressen unter `/abgabe/…` leiten dauerhaft um. Widerrufen lässt sich nur noch die
  Einwilligung zur Namensnennung; wer die Nutzung im Projekt nicht mehr will, löscht die
  Submission. Warum: Oberfläche, Code und Doku sollen dieselben Wörter benutzen wie das Team,
  und ein eigener Widerruf der Nutzung war nur eine zweite Tür zur Löschung.
