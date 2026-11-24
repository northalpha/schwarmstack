# Schwarmstack

Upload-Dienst für ein gemeinsames Astrofotografie-Projekt: Viele Teilnehmende fotografieren dasselbe Objekt und laden ihre Dateien hoch, der Betreiber führt sie zu einem Bild zusammen.

## Language

### Personen

**Teilnehmende** (`participant`):
Eine Person, die über die Projektwebsite kommt und eine Submission anlegt. Hat kein Konto und keine dauerhafte Identität im System.
_Avoid_: Nutzer, User, Kunde, Einreicher

**Betreiber** (`operator`):
Eine der wenigen Personen (derzeit drei), die das Projekt verantworten, Schwarmstack betreiben und am Ende alle Dateien weiterverarbeiten. Nur sie haben Zugang zum Admin, jede mit eigenem Konto; alle haben dieselben Rechte.
_Avoid_: Admin (für die Person), Moderator

### Teilnahme

**Aktion** (`Campaign`):
Das eine, einmalige Gemeinschaftsprojekt, für das Schwarmstack läuft: ein Objekt, ein Zeitraum, feste Grenzen.
_Avoid_: Event, Projekt (für den Datensatz), Kampagne

**Gesamtgrenze** (`global_cap`):
Die Obergrenze für die Gesamtgröße aller Master aller Submissions der Aktion.
_Avoid_: Kapazität, Gesamtquote

**Belegung** (`usage`):
Der belegte Platz: die Größe der angenommenen Master plus die angemeldete Größe laufender Uploads (Reservierung). Wird gegen Quote und Gesamtgrenze gerechnet.
_Avoid_: Verbrauch, Auslastung

**Projektwebsite**:
Die externe Website des Projekts, auf der Teilnehmende den Link zum Upload finden. Nicht Teil von Schwarmstack.
_Avoid_: Landingpage, Einstiegsseite

**Community-Seite**:
Die externe Seite der Community zum Projekt, die die Community-Zahlen abruft und anzeigt. Wie die Projektwebsite nicht Teil von Schwarmstack.
_Avoid_: Fanseite, Community-Website

**Submission** (`Submission`):
Alles, was eine teilnehmende Person mit einem Setup zur Aktion beiträgt: ihre Angaben und ihre Master. Bleibt bis zum Ende der Aktion offen und ist nur aus dem Browser erreichbar, in dem sie angelegt wurde. Wer mit einem zweiten Setup beiträgt, legt eine weitere Submission an.
_Avoid_: Abgabe, Upload (als Sammelbegriff), Einreichung, Beitrag

**Submission-ID** (`reference`):
Ein kurzer, lesbarer Code (z. B. `SW-7K3Q`), der eine Submission eindeutig benennt. Teilnehmende sehen ihn nach dem Anlegen und nennen ihn, wenn sie sich beim Betreiber melden.
_Avoid_: Abgabe-Kennung, Kennung, ID (ohne Bezug), Ticketnummer, Token

**Löschung** (`deleted_at`):
Das endgültige Löschen einer ganzen Submission, durch die Teilnehmenden selbst oder in ihrem Auftrag durch einen Betreiber. Master, Foto, Angaben und Einwilligungen verschwinden; es bleiben die Submission-ID, der Zeitpunkt und wer gelöscht hat. Eine gelöschte Submission zählt nicht auf Quote oder Gesamtgrenze und öffnet nicht wieder. Wer die Nutzung im Projekt nicht mehr will, löscht die Submission.
_Avoid_: Rückzug, zurückziehen, Stornierung, Abmeldung

**Ende der Aktion** (`ends_at`):
Der Zeitpunkt, ab dem keine neuen Uploads mehr starten. Begonnene Uploads dürfen noch innerhalb der Nachfrist abschließen; danach ist jede Submission schreibgeschützt.
_Avoid_: Deadline, Schluss

**Nachfrist** (`grace_period`):
Die Zeitspanne nach dem Ende der Aktion (6 Stunden), in der bereits begonnene Uploads noch abgeschlossen werden dürfen.
_Avoid_: Kulanzzeit, Verlängerung

**Unterbrochener Upload** (`interrupted`):
Ein Upload, der begonnen, aber nie fertig gemeldet wurde, etwa weil der Browser geschlossen wurde. Er belegt seine angemeldete Größe, bis er fortgesetzt, abgebrochen oder nach 7 Tagen freigegeben wird. Abbrechen geht bis zum Ende der Nachfrist; fortsetzen nur, wenn der Multipart-Upload im Speicher schon angelegt ist. Gab es in den letzten Minuten noch Anfragen, läuft er vielleicht in einem anderen Fenster weiter.
_Avoid_: hängender Upload, abgebrochener Upload (das ist der Zustand danach)

**Master** (`Master`):
Eine hochgeladene, lineare und unbearbeitete integrierte Bilddatei (XISF oder FITS, 32 Bit) für genau einen Kanal: ein Filterkanal bei Mono-Kameras, ein debayertes RGB-Bild bei Farbkameras.
_Avoid_: Stack, Frame, Rohbild, Upload (für die Datei)

**Prüfung** (`validation`):
Die automatische Kontrolle eines Masters nach dem Hochladen auf Format, 32-Bit-Gleitkomma und Form. Ein Master, der sie nicht besteht, wird abgelehnt und gelöscht.
_Avoid_: Validierung, Check

**Kanal** (`channel`):
Der Filter- bzw. Farbkanal, den ein Master abbildet, z. B. L, R, G, B, Hα, OIII, SII, IR oder RGB. Teilnehmende wählen ihn beim Hochladen.
_Avoid_: Filter (für den Kanal des Masters), Band

**Namensnennung** (`credit_name`):
Der Name, unter dem Teilnehmende im Projekt genannt werden wollen. Gibt es nur zusammen mit der Einwilligung zur Namensnennung; ohne sie bleibt die Submission anonym und nur über ihre Submission-ID erkennbar. Teilnehmende können sie bis zum Ende der Aktion selbst ändern und nachträglich erlauben.
_Avoid_: Nennung, Anzeigename, Credit, Pseudonym, Bildnachweis

**Einwilligung** (`Consent`):
Eine einzelne, ausdrücklich erteilte Erlaubnis der Teilnehmenden, z. B. zur Nutzung im Projekt oder zur Namensnennung. Je Zweck gilt höchstens eine; nach einem Widerruf kann bis zum Ende der Aktion eine neue erteilt werden, die widerrufene bleibt als Nachweis stehen.
_Avoid_: Zustimmung, Opt-in

**Widerruf** (`revoked_at`):
Die Rücknahme der Einwilligung zur Namensnennung. Geht jederzeit, auch nach dem Ende der Aktion. Die Einwilligung bleibt mit dem Zeitpunkt des Widerrufs stehen, damit nachweisbar ist, was wann galt; die Namensnennung wird gelöscht und die Submission anonym.
_Avoid_: Kündigung, Opt-out

**Datenschutzhinweis**:
Der Text in Schwarmstack, der erklärt, wer was wie lange verarbeitet; Verantwortlicher ist DZVF. Er ist versioniert, und jede Einwilligung hält fest, auf welche Version sie sich bezieht.
_Avoid_: Datenschutzerklärung, Privacy Policy

**Equipment-Foto**:
Ein optionales Foto der Ausrüstung, das Teilnehmende ihrer Submission beilegen können. Kein Master.
_Avoid_: Setup-Bild

**Quote** (`quota`):
Die Obergrenze für die Gesamtgröße aller Master einer Submission.
_Avoid_: Kontingent, Limit (ohne Bezug)

### Auswertung

**Admin**:
Die Oberfläche nur für Betreiber, mit eigenem Konto je Betreiber: Statistik, Aktion pflegen, Submissions und Master ansehen und im Auftrag der Teilnehmenden ändern. Jeder Eingriff steht im Protokoll.
_Avoid_: Backend, Dashboard

**Statistik**:
Der Stand der Aktion für die Betreiber, Startseite des Admin: Submissions, Master je Zustand und Kanal, Belegung, Dubletten, Ablehnungen nach Kategorie und der Verlauf je Tag. Zählt Submissions, nie Personen; nicht öffentlich. Öffentlich sind nur die Community-Zahlen.
_Avoid_: Auswertung (für die Seite), Reporting

**Community-Zahlen**:
Die wenigen Summen zur Aktion, die Schwarmstack öffentlich als JSON ausgibt, damit die Community-Seite sie anzeigen kann: Submissions, angenommene Master und ihre Datenmenge, dazu die aufsummierten Lights und die Gesamtbelichtung. Nur aggregierte Summen, nie Namen, Submission-IDs oder einzelne Submissions.
_Avoid_: öffentliche Statistik, Live-Zahlen

**Export**:
Die Übergabe aller Master an den Betreiber: ein Manifest und je Master ein zeitlich begrenzter Download-Link. Ein **vorläufiger Export** ist jederzeit möglich, enthält aber nur das Manifest ohne Links. Den **endgültigen Export** gibt es genau einmal, frühestens nach Ende der Aktion plus Nachfrist; er friert alle Submissions ein, auch für Betreiber, und startet die Löschfrist.
_Avoid_: Download (für den Gesamtvorgang), Archiv, Paket

**Manifest**:
Die Liste aller Submissions und ihrer Master mit Angaben, Einwilligungen und Prüfsummen, die zum Export gehört. Einzige Quelle für die öffentliche Namensnennung, denn Schwarmstack selbst zeigt nichts öffentlich an außer den Community-Zahlen, reinen Summen ohne Namen, Submission-IDs oder einzelne Submissions; nach Ablauf der Löschfrist auch der einzige Nachweis der Einwilligungen.
_Avoid_: Index, Übersicht

**Löschfrist**:
Die Zeitspanne nach dem endgültigen Export (30 Tage), nach der Schwarmstack alle Master, Begleitdateien, Equipment-Fotos und Angaben löscht. Danach wird die Installation abgebaut; die Sicherungen laufen nach weiteren 14 Tagen aus.
_Avoid_: Aufbewahrungsfrist, Retention, Löschfristen (Mehrzahl)

**Nachtrag**:
Ein Widerruf oder eine Löschung, die nach dem endgültigen Export eingeht. Der Nachtrag wirkt in Schwarmstack sofort und wird den Betreibern als Änderung am bereits übergebenen Export gemeldet, damit sie ihre Kopien anpassen.
_Avoid_: Korrektur, Änderung (ohne Bezug)

**Prüfsumme** (`sha256`):
Die SHA-256 eines Masters, vom Browser der Teilnehmenden beim Hochladen berechnet und gemeldet. Nicht vom Server bestätigt.
_Avoid_: Hash (ohne Bezug), ETag

**Belichtungsangaben** (`exposure`):
Die technischen Aufnahmeangaben eines Masters: Belichtung pro Light, Anzahl Lights, Gesamtbelichtung, Instrument und Teleskop. Werden beim Abschluss des Uploads aus einer festen Auswahl von Header-Schlüsseln gelesen und können von den Teilnehmenden bis zum Ende der Aktion ergänzt werden. Jeder Wert trägt seine Herkunft: aus dem Header, berechnet oder von Hand. Standort- und Personendaten gehören nie dazu.
_Avoid_: Metadaten, Aufnahmedaten, Header (für die Werte)

**Erzeuger** (`creator`):
Das Programm oder Gerät, das einen Master geschrieben hat, aus `ORIGIN`, `SWCREATE` oder `XISF:CreatorApplication`. Bestimmt, wie `EXPTIME` zu deuten ist (Gesamtzeit oder pro Light).
_Avoid_: Software, Hersteller

**Dublette** (`duplicate_of`):
Ein Master, dessen Prüfsumme schon in einer anderen Submission vorkommt. Wird angenommen und markiert; in derselben Submission wird dieselbe Datei abgelehnt.
_Avoid_: Kopie, doppelter Upload
