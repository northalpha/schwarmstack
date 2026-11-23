# Teilnahme ohne Konto und ohne persönlichen Link

Teilnehmende kommen über einen Link auf der Projektwebsite direkt zum Upload, ohne Konto, ohne E-Mail-Bestätigung und ohne persönlichen Link (Token). Eine Abgabe ist nur aus dem Browser erreichbar, in dem sie angelegt wurde (signiertes Cookie); dort lassen sich unterbrochene Uploads fortsetzen. Die Hürde zur Teilnahme soll so niedrig wie möglich sein.

## Consequences

- Kein Rückweg von einem anderen Gerät und keine nachträgliche Änderung durch die Teilnehmenden; Korrekturen laufen über den Betreiber.
- Missbrauch lässt sich nicht an einer Identität festmachen: Schutz nur über Quote je Abgabe, Gesamtgrenze für alle Abgaben, Rate-Limit je IP (gespeichert nur als Hash) und optional ALTCHA.

## Considered Options

- **Persönlicher Link mit Token** (erster Ansatz): verworfen, weil er die Teilnahme verkompliziert und der Rückweg kaum gebraucht wird.
