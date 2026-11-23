# Changelog

## Unveröffentlicht

- Neuaufbau, Abgabe anlegen (#9): Django-Gerüst, die Aktion als genau ein Datensatz
  (`manage.py campaign`), Formular mit Nennung, Setup-Beschreibung und Einwilligungen,
  Abgabe-Kennung (`SW-XXXX`) und Abgabeseite nur über ein signiertes Cookie. Warum: Teilnahme
  ohne Konto und ohne Token (ADR 0002); alles Weitere (Upload, Prüfung, Quote) baut darauf auf.
- Mehrere Abgaben je Browser und Zeitfenster (#10): bis zu 3 Abgaben je Browser mit Wechsel
  zwischen ihnen; eine zentrale Regel für das Zeitfenster (vor Beginn, laufend, Nachfrist,
  schreibgeschützt). Vor dem Beginn und nach dem Ende der Aktion keine neue Abgabe. Warum: eine
  Abgabe je Setup (ADR 0002), und alle späteren Prüfungen fragen dieselbe Regel.
- Erster Master von Anfang bis Ende (#11): Speicher-Modul mit Adapter für die lokale Platte,
  der sich für den Browser wie S3 verhält; Upload mit Uppy 6.0.7 (mitgeliefert) per
  Multipart, Kanalwahl je Master, Master-Liste auf der Abgabeseite und Begleitdatei je Master.
  Warum: der erste durchgehende Weg, auf dem S3-Adapter, Prüfung und Quote aufsetzen.
- Prüfung der Master (#13): Nach dem Upload wird der Header gelesen (XISF über `defusedxml`,
  FITS über die Header-Karten). Angenommen werden nur 32-Bit-Gleitkomma mit einer Ebene, bei
  RGB mit drei; abweichende Größe, zu kurze Dateien und falsche Formate werden abgelehnt, die
  Datei gelöscht und der Grund angezeigt. Warum: Der Betreiber soll am Ende nur brauchbare
  Master bekommen, und Teilnehmende sollen sofort wissen, was sie anders exportieren müssen.
- Prüfsumme und Dubletten (#14): Der Browser berechnet die SHA-256 mit WebCrypto in einem Web
  Worker parallel zum Upload und meldet sie mit der Fertig-Meldung;
  der Server übernimmt sie ungeprüft. Dieselbe Datei in derselben Abgabe wird abgelehnt, in
  einer anderen angenommen und als Dublette des ersten Masters markiert. Prüfsumme und Dublette
  stehen in der Begleitdatei. Warum: Kontrolle nach dem Download und Erkennen doppelter Dateien.
- S3-Adapter und Browser-Durchlauf (#12): Speicher im S3-Bucket (`STORAGE_BACKEND=s3`), gemeinsame
  Vertragstests für lokale Platte, `moto` und Garage, ein Playwright-Durchlauf mit Uppy gegen
  Garage in CI, `manage.py s3_bucket_setup` für CORS und Lifecycle-Regel, Betriebsanleitung in
  `docs/betrieb/s3-speicher.md`. Warum: Staging und Produktion laufen auf S3, und der Weg
  Browser → S3 → Abschluss soll vor jedem Rollout einmal wirklich gelaufen sein.
- Quote, Gesamtgrenze und Abbrechen (#15): Vor dem Start prüft der Server Höchstgröße je Master
  (500 MiB, Einstellung der Aktion), Quote der Abgabe und Gesamtgrenze und reserviert die Größe
  in derselben Transaktion. Uploads lassen sich abbrechen; nach 7 Tagen nicht abgeschlossene
  geben ihre Reservierung frei. Die Abgabeseite zeigt die Belegung. Warum: Der Bucket soll nicht
  über das Budget wachsen, und niemand soll erst nach langem Hochladen scheitern.
- Unterbrochenen Upload fortsetzen und Nachfrist (#16): Unterbrochene Uploads stehen auf der
  Abgabeseite; wird dieselbe Datei erneut gewählt, setzt der Uploader über die Liste der schon
  übertragenen Teile fort, ohne neuen Master und ohne doppelte Reservierung. Uploads lassen sich
  pausieren. Nach dem Ende der Aktion startet kein neuer Upload, begonnene dürfen in der
  Nachfrist abschließen; danach sind alle Upload-Endpunkte gesperrt und die Abgabe nur noch
  ansehbar. Warum: Große Dateien über Heimleitungen brechen ab, und das Ende muss für alle gleich
  gelten.

## 0.1.0

- A1: Datenmodell (Event, Abgabe, Links, Einwilligungen, Stack, Belichtung, Datei, Auftrag),
  Quote und Gesamtgrenze, Tokens nur als HMAC-Hash, Django-Admin unter `/<ADMIN_PATH>/` mit
  Zweitfaktor (django-otp, TOTP plus Wiederherstellungscodes). Warum: Ohne Zweitfaktor wäre der
  Admin das schwächste Glied; die Quote muss vor den Uploads (A3) feststehen und testbar sein.
- ALTCHA als optionales Modul (`Event.altcha_enabled`, Standard aus): Aufgabe unter
  `/altcha/challenge/`, Prüfung mit Einmalverwendung und Ablauf, Formular-Baustein, Widget 3.7.0
  mitgeliefert (kein CDN). Das Widget kommt mit dem Teilnahmeformular in A2 in die Seite.
- `manage.py otp_setup <benutzer>`: richtet TOTP im Terminal ein (QR-Code, Codes).

## 0.0.1

- A0: Gerüst mit Django 5.2 LTS, Settings aus der Umgebung, `/healthz` (prüft die Datenbank)
  und Startseite. Warum: Das Walking Skeleton soll früh auf Staging laufen, damit Rollout,
  Proxy und Freigabe getestet sind, bevor Funktionen dazukommen.
