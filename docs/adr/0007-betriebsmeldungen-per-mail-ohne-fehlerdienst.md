# Betriebsmeldungen per Mail, ohne Fehlerdienst eines Drittanbieters

Schwarmstack überwacht sich selbst und meldet dem Betreiber per SMTP-Mail: Gesamtgrenze bei 80 % und 95 %, Serverfehler, fehlende oder fehlgeschlagene Datenbanksicherung, knapper Platz auf dem Host und nicht erreichbarer S3-Speicher. Die Erreichbarkeit von außen prüft das bestehende Monitoring des Betreibers über `/healthz`. Meldungen enthalten keine Angaben von Teilnehmenden: nur Fehlertyp, URL ohne Parameter, Zeitpunkt und Abgabe-Kennung, höchstens eine Mail je Fehlertyp und Stunde; den Stacktrace gibt es nur in den Logs.

## Consequences

- Caddy protokolliert IP-Adressen gekürzt (IPv4 /24, IPv6 /48), Docker-Logs rotieren nach 7 Tagen.
- Djangos eingebaute Fehler-Mails (`AdminEmailHandler`) werden nicht genutzt, weil sie den ganzen Request samt Formularwerten und Cookie enthalten.

## Considered Options

- **Sentry oder ein vergleichbarer Fehlerdienst**: verworfen, weil Daten von Teilnehmenden an einen weiteren Dienstleister gingen und im Datenschutzhinweis stehen müssten.
- **Push über ntfy**: verworfen zugunsten von Mail, die ohne weiteren Dienst auskommt.
