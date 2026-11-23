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

**Projektwebsite**:
Die externe Website des Projekts, auf der Teilnehmende den Link zum Upload finden. Nicht Teil von Schwarmstack.
_Avoid_: Landingpage, Einstiegsseite

**Abgabe** (`Submission`):
Alles, was eine teilnehmende Person mit einem Setup zur Aktion beiträgt: ihre Angaben und ihre Master. Bleibt bis zum Ende der Aktion offen und ist nur aus dem Browser erreichbar, in dem sie angelegt wurde. Wer mit einem zweiten Setup beiträgt, legt eine weitere Abgabe an.
_Avoid_: Upload (als Sammelbegriff), Einreichung, Beitrag

**Abgabe-Kennung** (`reference`):
Ein kurzer, lesbarer Code (z. B. `SW-7K3Q`), der eine Abgabe eindeutig benennt. Teilnehmende sehen ihn nach dem Anlegen und nennen ihn, wenn sie sich beim Betreiber melden.
_Avoid_: ID, Ticketnummer, Token

**Rückzug** (`withdrawn`):
Die Löschung einer ganzen Abgabe durch die Teilnehmenden selbst oder auf ihre Bitte durch einen Betreiber. Master, Foto und Angaben verschwinden; nur die Abgabe-Kennung bleibt als zurückgezogen sichtbar.
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

**Widerruf** (`revoked_at`):
Die nachträgliche Rücknahme einer Einwilligung auf Bitte der Teilnehmenden. Die Einwilligung bleibt mit dem Zeitpunkt des Widerrufs erhalten, damit nachweisbar ist, was wann galt. Der Widerruf der Nutzung im Projekt führt zum Rückzug der Abgabe.
_Avoid_: Löschung (der Einwilligung), Opt-out

**Nennung** (`credit_name`):
Der Name, unter dem Teilnehmende im Projekt genannt werden wollen. Gibt es nur zusammen mit der Einwilligung zur Veröffentlichung; ohne sie bleibt die Abgabe anonym und nur über ihre Kennung erkennbar.
_Avoid_: Anzeigename, Credit, Pseudonym

**Einwilligung** (`Consent`):
Eine einzelne, ausdrücklich erteilte Zustimmung der Teilnehmenden, z. B. zur Nutzung im Projekt oder zur Veröffentlichung der Nennung.
_Avoid_: Zustimmung, Opt-in

**Equipment-Foto**:
Ein optionales Foto der Ausrüstung, das Teilnehmende ihrer Abgabe beilegen können. Kein Master.
_Avoid_: Setup-Bild

**Belegung** (`usage`):
Die Größe aller angenommenen Master plus der Reservierungen laufender Uploads, gemessen an der Quote einer Abgabe oder an der Gesamtgrenze der Aktion.
_Avoid_: Verbrauch, Füllstand, Auslastung

**Quote** (`quota`):
Die Obergrenze für die Gesamtgröße aller Master einer Abgabe.
_Avoid_: Kontingent, Limit (ohne Bezug)

### Auswertung

**Admin**:
Der geschützte Bereich, in dem Betreiber die Aktion pflegen, Abgaben ansehen und im Auftrag von Teilnehmenden korrigieren. Jede Änderung darin ist mit Betreiber und Zeitpunkt nachvollziehbar.
_Avoid_: Backend, Dashboard, Verwaltung

**Statistik**:
Die Kennzahlen zur laufenden Aktion, die nur Betreiber im Admin sehen: Abgaben, Master je Zustand und Kanal, Belegung, Dubletten, Ablehnungsgründe und der Verlauf je Tag. Zählt Abgaben, nie Personen.
_Avoid_: Reporting, Analytics, Auswertung (für die Zahlen)

**Export**:
Die Übergabe aller Master an den Betreiber: ein Manifest und je Master ein zeitlich begrenzter Download-Link. Ein **vorläufiger Export** ist jederzeit möglich, enthält aber nur das Manifest ohne Links. Den **endgültigen Export** gibt es genau einmal, frühestens nach Ende der Aktion plus Nachfrist; er friert alle Abgaben ein, auch für Betreiber, und startet die Löschfrist.
_Avoid_: Download (für den Gesamtvorgang), Archiv, Paket

**Manifest**:
Die Liste aller Abgaben und ihrer Master mit Angaben, Einwilligungen und Prüfsummen, die zum Export gehört. Einzige Quelle für die öffentliche Nennung, denn Schwarmstack selbst zeigt nichts öffentlich an; nach Ablauf der Löschfrist auch der einzige Nachweis der Einwilligungen.
_Avoid_: Index, Übersicht

**Löschfrist**:
Die Zeitspanne nach dem endgültigen Export (30 Tage), nach der Schwarmstack alle Master, Begleitdateien, Equipment-Fotos und Angaben löscht. Danach wird die Installation abgebaut; die Sicherungen laufen nach weiteren 14 Tagen aus.
_Avoid_: Aufbewahrungsfrist, Retention, Löschfristen (Mehrzahl)

**Prüfsumme** (`sha256`):
Die SHA-256 eines Masters, vom Browser der Teilnehmenden beim Hochladen berechnet und gemeldet. Nicht vom Server bestätigt.
_Avoid_: Hash (ohne Bezug), ETag

**Dublette** (`duplicate_of`):
Ein Master, dessen Prüfsumme schon in einer anderen Abgabe vorkommt. Wird angenommen und markiert; in derselben Abgabe wird dieselbe Datei abgelehnt.
_Avoid_: Kopie, doppelter Upload
