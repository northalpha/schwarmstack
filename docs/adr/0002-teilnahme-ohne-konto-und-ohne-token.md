# Teilnahme ohne Konto und ohne persönlichen Link

Teilnehmende kommen über einen Link auf der Projektwebsite direkt zum Upload, ohne Konto, ohne E-Mail-Bestätigung und ohne persönlichen Link (Token). Eine Submission ist nur aus dem Browser erreichbar, in dem sie angelegt wurde (signiertes Cookie); dort lassen sich unterbrochene Uploads fortsetzen. Die Hürde zur Teilnahme soll so niedrig wie möglich sein.

## Consequences

- Bis zum Ende der Aktion können Teilnehmende ihre Submission im selben Browser ergänzen, ändern, Master löschen oder sie ganz löschen; danach ist sie schreibgeschützt. Ausgenommen ist der Widerruf der Einwilligung zur Namensnennung: Er geht jederzeit auf der Submission-Seite, solange die Submission nicht gelöscht ist (DSGVO Art. 7 Abs. 3, Ticket #68).
- Ein Browser kann bis zu 3 Submissions halten (für unterschiedliche Setups). Die Quote gilt je Submission, nicht je Person, weil sich eine Person ohne Konto nicht zuverlässig erkennen lässt.
- Dieselbe Person in einem anderen Browser erzeugt eine neue Submission. Der Betreiber kann Submissions im Admin zusammenführen.
- Kein Rückweg von einem anderen Gerät: Wer dort etwas ändern will, wendet sich mit der Submission-ID an den Betreiber. Die Submission-ID wird nach dem Anlegen der Submission angezeigt und steht im Manifest.
- Missbrauch lässt sich nicht an einer Identität festmachen: Schutz nur über Quote je Submission, Gesamtgrenze für alle Submissions, Rate-Limit je IP (gespeichert nur als Hash) und optional ALTCHA.

## Considered Options

- **Persönlicher Link mit Token** (erster Ansatz): verworfen, weil er die Teilnahme verkompliziert und der Rückweg kaum gebraucht wird.
