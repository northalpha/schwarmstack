# Löschfrist und Abbau nach dem endgültigen Export

Es gibt genau einen endgültigen Export, frühestens nach Ende der Aktion plus Nachfrist, ausgelöst von einem Betreiber im Admin. Er friert alle Abgaben ein, auch für Betreiber, und startet eine Löschfrist von 30 Tagen. Danach löscht Schwarmstack automatisch alle Master, Begleitdateien und Angaben samt Datenbank; anschließend wird die Installation von Hand abgebaut. Die Sicherungen der Datenbank laufen nach weiteren 14 Tagen von selbst aus (ADR 0006). Schwarmstack ist ein Übergabepunkt, kein Archiv: Die Daten sollen nicht länger liegen bleiben, als die Betreiber zum Herunterladen brauchen.

## Consequences

- Der einzige dauerhafte Nachweis der Einwilligungen ist das Manifest, das bei DZVF bleibt: je Abgabe Art, Zeitpunkt, Textversion und gegebenenfalls Widerruf jeder Einwilligung. Die Datenbank wird trotzdem gelöscht.
- Ein vorläufiger Export enthält nur das Manifest, keine Download-Links. So entstehen vor dem endgültigen Export keine Massenkopien außerhalb des Systems, die bei Rückzug oder Widerruf nachgezogen werden müssten.
- Die Download-Links gelten 7 Tage (Grenze vorsignierter S3-Links). Betreiber können sie bis zum Ablauf der Löschfrist neu ausstellen; jedes Ausstellen steht im Protokoll.
- Widerruf und Rückzug bleiben nach dem endgültigen Export möglich und wirken in Schwarmstack sofort. Sie erscheinen als Nachtrag zum Export, und die Betreiber bekommen eine Betriebsmeldung (ADR 0007), damit sie ihre Kopien anpassen. Nach dem Abbau erledigen die Betreiber solche Anfragen von Hand über die Kontaktadresse im Datenschutzhinweis.
- „Datenbank löschen“ heißt: Abgaben samt Mastern und Einwilligungen, Fehlversuche der Anmeldung und das Protokoll zu den Abgaben. Bis zum Abbau bleiben die Aktion mit den Zeitpunkten von Export und Löschung (damit der Befehl idempotent ist), ihre Protokolleinträge und die Betreiber-Konten; keins davon enthält Angaben von Teilnehmenden. Die Datei selbst verschwindet mit dem Abbau.
- Die Löschung läuft über einen Management-Befehl, den ein Cron-Job auf dem Host täglich aufruft; er tut erst nach Ablauf der Löschfrist etwas. Sieben Tage vorher und nach der Löschung geht eine Betriebsmeldung an die Betreiber. Das ist bewusst kein Worker im Sinne von ADR 0003: ein einzelner, idempotenter Befehl ohne Warteschlange.

## Considered Options

- **Löschung von Hand im Admin**: verworfen, weil eine Frist, die an Handarbeit hängt, in der Praxis überzogen wird.
- **Datenbank als Einwilligungsnachweis aufbewahren**: verworfen; dafür müsste Schwarmstack oder eine Kopie der Datenbank auf unbestimmte Zeit weiterleben. Das Manifest trägt denselben Nachweis.
- **Vorläufiger Export mit Download-Links**: verworfen, siehe oben.
