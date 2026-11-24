# Schwarmstack

Upload-Dienst für ein gemeinsames Astrofotografie-Projekt: Viele Teilnehmende fotografieren dasselbe Objekt und laden ihre Dateien hoch, der Betreiber führt sie zu einem Bild zusammen.

## Language

### Personen

**Teilnehmende** (`participant`):
Eine Person, die über die Projektwebsite kommt und eine Abgabe macht. Hat kein Konto und keine dauerhafte Identität im System.
_Avoid_: Nutzer, User, Kunde, Einreicher

**Betreiber** (`operator`):
Eine der wenigen Personen (derzeit drei), die das Projekt verantworten, Schwarmstack betreiben und am Ende alle Dateien weiterverarbeiten. Nur sie haben Zugang zum Admin, jede mit eigenem Konto; alle haben dieselben Rechte.
_Avoid_: Admin (für die Person), Moderator

### Teilnahme

**Aktion** (`Campaign`):
Das eine, einmalige Gemeinschaftsprojekt, für das Schwarmstack läuft: ein Objekt, ein Zeitraum, feste Grenzen.
_Avoid_: Event, Projekt (für den Datensatz), Kampagne

**Gesamtgrenze** (`global_cap`):
Die Obergrenze für die Gesamtgröße aller Master aller Abgaben der Aktion.
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

**Abgabe** (`Submission`):
Alles, was eine teilnehmende Person mit einem Setup zur Aktion beiträgt: ihre Angaben und ihre Master. Bleibt bis zum Ende der Aktion offen und ist nur aus dem Browser erreichbar, in dem sie angelegt wurde. Wer mit einem zweiten Setup beiträgt, legt eine weitere Abgabe an.
_Avoid_: Upload (als Sammelbegriff), Einreichung, Beitrag

**Abgabe-Kennung** (`reference`):
Ein kurzer, lesbarer Code (z. B. `SW-7K3Q`), der eine Abgabe eindeutig benennt. Teilnehmende sehen ihn nach dem Anlegen und nennen ihn, wenn sie sich beim Betreiber melden.
_Avoid_: ID, Ticketnummer, Token

**Rückzug** (`withdrawn`):
Die Löschung einer ganzen Abgabe, durch die Teilnehmenden selbst oder in ihrem Auftrag durch einen Betreiber. Master, Foto, Angaben und Einwilligungen verschwinden; es bleiben die Abgabe-Kennung, der Zeitpunkt und wer den Rückzug ausgelöst hat. Eine zurückgezogene Abgabe zählt nicht auf Quote oder Gesamtgrenze und öffnet nicht wieder.
_Avoid_: Stornierung, Abmeldung

**Ende der Aktion** (`ends_at`):
Der Zeitpunkt, ab dem keine neuen Uploads mehr starten. Begonnene Uploads dürfen noch innerhalb der Nachfrist abschließen; danach ist jede Abgabe schreibgeschützt.
_Avoid_: Deadline, Schluss

**Nachfrist** (`grace_period`):
Die Zeitspanne nach dem Ende der Aktion (6 Stunden), in der bereits begonnene Uploads noch abgeschlossen werden dürfen.
_Avoid_: Kulanzzeit, Verlängerung

**Master** (`Master`):
Eine hochgeladene, lineare und unbearbeitete integrierte Bilddatei (XISF oder FITS, 32 Bit) für genau einen Kanal: ein Filterkanal bei Mono-Kameras, ein debayertes RGB-Bild bei Farbkameras.
_Avoid_: Stack, Frame, Rohbild, Upload (für die Datei)

**Prüfung** (`validation`):
Die automatische Kontrolle eines Masters nach dem Hochladen auf Format, 32-Bit-Gleitkomma und Form. Ein Master, der sie nicht besteht, wird abgelehnt und gelöscht.
_Avoid_: Validierung, Check

**Kanal** (`channel`):
Der Filter- bzw. Farbkanal, den ein Master abbildet, z. B. L, R, G, B, Hα, OIII, SII, IR oder RGB. Teilnehmende wählen ihn beim Hochladen.
_Avoid_: Filter (für den Kanal des Masters), Band

**Nennung** (`credit_name`):
Der Name, unter dem Teilnehmende im Projekt genannt werden wollen. Gibt es nur zusammen mit der Einwilligung zur Veröffentlichung; ohne sie bleibt die Abgabe anonym und nur über ihre Kennung erkennbar.
_Avoid_: Anzeigename, Credit, Pseudonym

**Einwilligung** (`Consent`):
Eine einzelne, ausdrücklich erteilte Zustimmung der Teilnehmenden, z. B. zur Nutzung im Projekt oder zur Veröffentlichung der Nennung.
_Avoid_: Zustimmung, Opt-in

**Widerruf** (`revoked_at`):
Die Rücknahme einer Einwilligung. Die Einwilligung bleibt mit dem Zeitpunkt des Widerrufs stehen, damit nachweisbar ist, was wann galt. Der Widerruf der Nutzung im Projekt löst den Rückzug der Abgabe aus.
_Avoid_: Kündigung, Opt-out

**Datenschutzhinweis**:
Der Text in Schwarmstack, der erklärt, wer was wie lange verarbeitet; Verantwortlicher ist DZVF. Er ist versioniert, und jede Einwilligung hält fest, auf welche Version sie sich bezieht.
_Avoid_: Datenschutzerklärung, Privacy Policy

**Equipment-Foto**:
Ein optionales Foto der Ausrüstung, das Teilnehmende ihrer Abgabe beilegen können. Kein Master.
_Avoid_: Setup-Bild

**Quote** (`quota`):
Die Obergrenze für die Gesamtgröße aller Master einer Abgabe.
_Avoid_: Kontingent, Limit (ohne Bezug)

### Auswertung

**Admin**:
Die Oberfläche nur für Betreiber, mit eigenem Konto je Betreiber: Statistik, Aktion pflegen, Abgaben und Master ansehen und im Auftrag der Teilnehmenden korrigieren. Jeder Eingriff steht im Protokoll.
_Avoid_: Backend, Dashboard

**Statistik**:
Der Stand der Aktion für die Betreiber, Startseite des Admin: Abgaben, Master je Zustand und Kanal, Belegung, Dubletten, Ablehnungen nach Kategorie und der Verlauf je Tag. Zählt Abgaben, nie Personen; nicht öffentlich. Öffentlich sind nur die Community-Zahlen.
_Avoid_: Auswertung (für die Seite), Reporting

**Community-Zahlen**:
Die wenigen Summen zur Aktion, die Schwarmstack öffentlich als JSON ausgibt, damit die Community-Seite sie anzeigen kann: Abgaben, angenommene Master und ihre Datenmenge. Nur aggregierte Summen, nie Namen, Kennungen oder einzelne Abgaben.
_Avoid_: öffentliche Statistik, Live-Zahlen

**Export**:
Die Übergabe aller Master an den Betreiber: ein Manifest und je Master ein zeitlich begrenzter Download-Link. Ein **vorläufiger Export** ist jederzeit möglich, enthält aber nur das Manifest ohne Links. Den **endgültigen Export** gibt es genau einmal, frühestens nach Ende der Aktion plus Nachfrist; er friert alle Abgaben ein, auch für Betreiber, und startet die Löschfrist.
_Avoid_: Download (für den Gesamtvorgang), Archiv, Paket

**Manifest**:
Die Liste aller Abgaben und ihrer Master mit Angaben, Einwilligungen und Prüfsummen, die zum Export gehört. Einzige Quelle für die öffentliche Nennung, denn Schwarmstack selbst zeigt nichts öffentlich an außer den Community-Zahlen, reinen Summen ohne Namen, Kennungen oder einzelne Abgaben; nach Ablauf der Löschfrist auch der einzige Nachweis der Einwilligungen.
_Avoid_: Index, Übersicht

**Löschfrist**:
Die Zeitspanne nach dem endgültigen Export (30 Tage), nach der Schwarmstack alle Master, Begleitdateien, Equipment-Fotos und Angaben löscht. Danach wird die Installation abgebaut; die Sicherungen laufen nach weiteren 14 Tagen aus.
_Avoid_: Aufbewahrungsfrist, Retention, Löschfristen (Mehrzahl)

**Nachtrag**:
Ein Widerruf oder Rückzug, der nach dem endgültigen Export eingeht. Er wirkt in Schwarmstack sofort und wird den Betreibern als Änderung am bereits übergebenen Export gemeldet, damit sie ihre Kopien anpassen.
_Avoid_: Korrektur, Änderung (ohne Bezug)

**Prüfsumme** (`sha256`):
Die SHA-256 eines Masters, vom Browser der Teilnehmenden beim Hochladen berechnet und gemeldet. Nicht vom Server bestätigt.
_Avoid_: Hash (ohne Bezug), ETag

**Dublette** (`duplicate_of`):
Ein Master, dessen Prüfsumme schon in einer anderen Abgabe vorkommt. Wird angenommen und markiert; in derselben Abgabe wird dieselbe Datei abgelehnt.
_Avoid_: Kopie, doppelter Upload
