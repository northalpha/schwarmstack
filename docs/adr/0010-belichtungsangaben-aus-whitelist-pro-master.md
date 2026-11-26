# Belichtungsangaben aus einer Whitelist, pro Master, mit Herkunft je Wert

Beim Abschluss eines Uploads liest der Server aus demselben Range Request wie die Prüfung (1 MiB) die Belichtungsangaben eines Masters: Belichtung pro Light, Anzahl Lights, Gesamtbelichtung, Instrument und Teleskop, dazu den Erzeuger. Gelesen wird nur eine feste Whitelist (`EXPTIME`, `STACKCNT`, `LIVETIME`, `INSTRUME`, `TELESCOP`, `ORIGIN`, `SWCREATE`, `XISF:CreatorApplication` und die XISF-Entsprechungen `Instrument:ExposureTime`, `Instrument:Camera:Name`, `Instrument:Telescope:Name`). Dazu kommt der Filtername (`FILTER`, ersatzweise `FILT-1` oder `INSFLNAM`, in XISF `Instrument:Filter:Name`), aus dem `exposure.channel_for_filter` bei einem Master mit einer Ebene einen Kanal vorschlägt (#95); die Teilnehmenden übernehmen ihn, die Herkunft steht in `Master.channel_source`. Der Header wird nie als Ganzes gespeichert; Standort und Beobachter (`SITELAT`, `SITELONG`, `OBSGEO-*`, `OBSERVER`) werden gar nicht erst gelesen. Gespeichert wird pro Master, und jeder Wert trägt seine Herkunft: `header`, `berechnet` oder `manuell`.

## Consequences

- Summen pro Submission oder für die Community-Zahlen werden aus den Mastern berechnet, nicht gespeichert.
- Was `EXPTIME` bedeutet (Gesamtzeit oder pro Light), legt eine kleine Tabelle je Erzeuger im Code fest (`exposure.EXPTIME_MEANING`). Bei einem unbekannten Erzeuger wird nichts gerechnet; die Teilnehmenden wählen die Bedeutung. `LIVETIME` ist, wenn vorhanden, die Gesamtbelichtung.
- Berechnete Werte sind nur Vorschläge; erst ein Klick speichert sie als `berechnet`. Rechnet der Server nicht glatt, zeigt er einen Hinweis statt eines Vorschlags. Gerechnet wird nur auf dem Server, nicht im Browser.
- In XISF hat die XISF-Property Vorrang vor dem eingebetteten FITS-Keyword; ein Widerspruch wird gespeichert und angezeigt.
- Die Werte gehören in Manifest und Export, die aus der Datenbank lesen, nicht in die Begleitdatei: Die Begleitdatei soll die Zuordnung rekonstruierbar machen (ADR 0006), nicht die Angaben duplizieren. Manifest und Export entstehen erst mit #34; `exposure.manifest_values` liefert ihnen die Werte samt Herkunft.
- Teilnehmende ändern die Werte bis zum Ende der Aktion, danach nur die Betreiber im Admin. Die Löschung löscht sie mit den Mastern, Herkunft und Erzeuger eingeschlossen.
- Bewusste Folge aus ADR 0003: Die Dateien bleiben byte-genau. Die vollständigen Header mit Standortdaten liegen also weiter in den Master-Dateien im S3-Speicher; Schwarmstack liest sie nur nicht. Ein Hinweis im Datenschutzhinweis und vor dem Upload (#62) macht das sichtbar; die Dateien ändert Schwarmstack nicht.

## Considered Options

- **Ganzen Header speichern**: verworfen; er enthält Standort- und Personendaten, die Schwarmstack nicht braucht.
- **Parser im Browser**: verworfen; der Server hat den Header beim Abschluss ohnehin, und eine Stelle für die Regeln reicht.
- **Werte pro Submission**: verworfen; Master einer Submission haben je Kanal eigene Belichtungen.
- **Berechnete Werte still übernehmen**: verworfen; gemischte Belichtungszeiten oder eine falsche Deutung von `EXPTIME` würden unbemerkt falsche Zahlen erzeugen.
