- Upload-Anzeige: Der Balken steht nach dem Hochladen auf 100 %, und der Bucket gibt
  `x-amz-error-code` frei. Warum: Uppy meldet den letzten Fortschritt nicht immer, der Balken
  blieb knapp darunter stehen; ohne den Header zeigte Uppy S3-Fehler nur ohne Code an.
