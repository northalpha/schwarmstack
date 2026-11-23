# Schwarmstack

Upload-Dienst für ein gemeinsames Astrofotografie-Projekt: Viele Teilnehmende fotografieren dasselbe Objekt und laden ihre Dateien hoch, der Betreiber führt sie zu einem Bild zusammen.

## Language

### Personen

**Teilnehmende** (`participant`):
Eine Person, die über die Projektwebsite kommt und eine Abgabe macht. Hat kein Konto und keine dauerhafte Identität im System.
_Avoid_: Nutzer, User, Kunde, Einreicher

**Betreiber** (`operator`):
Die Person, die das Projekt verantwortet, Schwarmstack betreibt und am Ende alle Dateien weiterverarbeitet. Einzige Person mit Zugang zum Admin.
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
Alles, was eine teilnehmende Person in einem Durchgang zum Projekt beiträgt: ihre Angaben und ihre Dateien. Nur aus dem Browser erreichbar, in dem sie angelegt wurde.
_Avoid_: Upload (als Sammelbegriff), Einreichung, Beitrag

**Abgabe-Kennung** (`reference`):
Ein kurzer, lesbarer Code (z. B. `SW-7K3Q`), der eine Abgabe eindeutig benennt. Teilnehmende sehen ihn nach dem Anlegen und nennen ihn, wenn sie sich beim Betreiber melden.
_Avoid_: ID, Ticketnummer, Token

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
Der Name, unter dem Teilnehmende im Projekt genannt werden wollen.
_Avoid_: Anzeigename, Credit, Pseudonym

**Einwilligung** (`Consent`):
Eine einzelne, ausdrücklich erteilte Zustimmung der Teilnehmenden, z. B. zur Nutzung im Projekt oder zur Veröffentlichung der Nennung.
_Avoid_: Zustimmung, Opt-in

**Equipment-Foto**:
Ein optionales Foto der Ausrüstung, das Teilnehmende ihrer Abgabe beilegen können. Kein Master.
_Avoid_: Setup-Bild

**Quote** (`quota`):
Die Obergrenze für die Gesamtgröße aller Master einer Abgabe.
_Avoid_: Kontingent, Limit (ohne Bezug)

### Auswertung

**Export**:
Die Übergabe aller Master an den Betreiber am Ende der Aktion: ein Manifest und je Master ein zeitlich begrenzter Download-Link. Vor dem Ende der Aktion plus Nachfrist ist ein Export nur vorläufig; erst der endgültige Export startet die Löschfristen.
_Avoid_: Download (für den Gesamtvorgang), Archiv, Paket

**Manifest**:
Die Liste aller Abgaben und ihrer Master mit Angaben und Prüfsummen, die zum Export gehört. Einzige Quelle für die öffentliche Nennung; Schwarmstack selbst zeigt nichts öffentlich an.
_Avoid_: Index, Übersicht

**Prüfsumme** (`sha256`):
Die SHA-256 eines Masters, vom Browser der Teilnehmenden beim Hochladen berechnet und gemeldet. Nicht vom Server bestätigt.
_Avoid_: Hash (ohne Bezug), ETag

**Dublette** (`duplicate_of`):
Ein Master, dessen Prüfsumme schon in einer anderen Abgabe vorkommt. Wird angenommen und markiert; in derselben Abgabe wird dieselbe Datei abgelehnt.
_Avoid_: Kopie, doppelter Upload
