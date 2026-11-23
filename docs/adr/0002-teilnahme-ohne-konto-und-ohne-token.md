# Teilnahme ohne Konto und ohne persönlichen Link

Teilnehmende kommen über einen Link auf der Projektwebsite direkt zum Upload, ohne Konto, ohne E-Mail-Bestätigung und ohne persönlichen Link (Token). Eine Abgabe ist nur aus dem Browser erreichbar, in dem sie angelegt wurde (signiertes Cookie); dort lassen sich unterbrochene Uploads fortsetzen. Die Hürde zur Teilnahme soll so niedrig wie möglich sein.

## Consequences

- Bis zum Ende der Aktion können Teilnehmende ihre Abgabe im selben Browser ergänzen, ändern, Master löschen oder sie ganz zurückziehen; danach ist sie schreibgeschützt.
- Ein Browser kann bis zu 3 Abgaben halten (für unterschiedliche Setups). Die Quote gilt je Abgabe, nicht je Person, weil sich eine Person ohne Konto nicht zuverlässig erkennen lässt.
- Dieselbe Person in einem anderen Browser erzeugt eine neue Abgabe. Der Betreiber kann Abgaben im Admin zusammenführen.
- Kein Rückweg von einem anderen Gerät: Wer dort etwas ändern will, wendet sich mit der Abgabe-Kennung an den Betreiber. Die Kennung wird nach dem Anlegen der Abgabe angezeigt und steht im Manifest.
- Missbrauch lässt sich nicht an einer Identität festmachen: Schutz nur über Quote je Abgabe, Gesamtgrenze für alle Abgaben, Rate-Limit je IP (gespeichert nur als Hash) und optional ALTCHA.

## Considered Options

- **Persönlicher Link mit Token** (erster Ansatz): verworfen, weil er die Teilnahme verkompliziert und der Rückweg kaum gebraucht wird.
