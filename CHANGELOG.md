# Changelog

## Unveröffentlicht

Neue Einträge stehen bis zum Release je Änderung in [`changelog.d/`](changelog.d/README.md).

## 0.3.0

- Sicherheitsprüfungen in CI (#121): Dependabot (uv, Actions, Docker), `pip-audit` und `zizmor` in `scripts/pruefen.sh`, Trivy über das gebaute Image, CodeQL für Python und die Workflows; alle Actions sind auf Commit-SHAs gepinnt. Beim Image wird nur bei High/Critical mit Fix rot, `pip-audit` meldet jeden bekannten Fund; Ausnahmen stehen mit Grund und Ablaufdatum in `sicherheit-ausnahmen.toml` (ADR 0012). Warum: grobe Lücken in Abhängigkeiten, Image und Workflows sollen auffallen, ohne ein Hobbyprojekt mit Alarmen zu überlasten. Das Image enthält dafür kein `pip` mehr und zieht Sicherheitskorrekturen des Basisimages beim Bauen nach.
- Sicherheits-Header (#122): Alle Antworten tragen eine strenge Content-Security-Policy ohne `unsafe-inline` (Skripte und Styles nur von der eigenen Domain, Uploads nur zum eigenen S3-Host), `X-Frame-Options: DENY` und eine `Permissions-Policy`. `manage.py check --deploy` läuft jetzt in `scripts/pruefen.sh`. Warum: Ein eingeschleustes Skript oder eine eingebettete Seite soll im Browser nichts ausrichten können. Das Inline-Stylesheet der Statistik liegt dafür in einer statischen Datei. `CSP_REPORT_ONLY=true` stellt die Policy im Notfall auf „nur melden“.
- Sicherheitsreview gegen die OWASP Top 10 (#123): Passwörter der Betreiber müssen mindestens 12 Zeichen haben und dürfen nicht häufig oder rein numerisch sein (`AUTH_PASSWORD_VALIDATORS`). Die ungenutzte Abhängigkeit `django-otp` ist entfernt, der Admin hatte nie einen Zweitfaktor (ADR 0013). Neue Regressionstests (`tests/test_sicherheit_review.py`) halten Zugriff über das Cookie, Signaturen für Uploads, Header-Prüfung von XISF/FITS, sichere Voreinstellungen der Settings und Logs ohne Zugangsdaten fest. Warum: Jede Sicherheitsannahme soll auch nach späteren Änderungen gelten.
- Image auf Alpine (#127): Das Release-Image baut auf `python:3.13-alpine` statt `slim-trixie`, rund ein Viertel kleiner und mit weniger Systempaketen. Warum: weniger Angriffsfläche und weniger Funde im Image-Scan (ADR 0014). Die Fotobereinigung (JPEG, PNG, WebP, HEIC) wird jetzt im gebauten Image geprüft, nicht nur in der CI auf glibc.
- Lokaler Adapter: Teile eines Uploads dürfen zusammen die angemeldete Größe nicht überschreiten; `upload_part` bricht größere Teile ab (400) und lässt nichts liegen (#135). Warum: Die Gesamtgrenze der Aktion soll nicht durch zu große Teile umgangen werden. Bei S3 bleibt es bei der Lifecycle-Regel.
- Die `sha-…`-Images von `main` liegen jetzt in `ghcr.io/northalpha/schwarmstack-ci`; `ghcr.io/northalpha/schwarmstack` enthält nur noch Releases (`vX.Y.Z`, `vX.Y`). Beim Deploy wählt `deploy.sh` das Package nach dem Image-Tag (`v…` = Release, sonst `main`-Stand) und schreibt `IMAGE` in die `.env`. Warum: Die Package-Seite zeigte sonst immer das zuletzt gebaute `sha-…` als „Latest“.
- Dependabot (#132): Django kommt in einem eigenen PR statt im Sammel-PR der Python-Abhängigkeiten, Major-Sprünge schlägt Dependabot nicht mehr vor. Warum: Feature-Releases entfernen Deprecations und brauchen Planung; sie sollen nicht zwischen Bumps von Pillow oder boto3 untergehen.
- Das Release-Image `ghcr.io/northalpha/schwarmstack` ist öffentlich, wie das Repo. Warum: Selbstbetreiber (ADR 0011) ziehen es ohne Anmeldung; `docs/betrieb/deployment.md` und ADR 0011 sagten noch „privat“.

## 0.2.0

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
- S3-Adapter und Browser-Durchlauf (#12): Speicher im S3-Bucket (`STORAGE_BACKEND=s3`), gemeinsame
  Vertragstests für lokale Platte, `moto` und Garage, ein Playwright-Durchlauf mit Uppy gegen
  Garage in CI, `manage.py s3_bucket_setup` für CORS und Lifecycle-Regel, Betriebsanleitung in
  `docs/betrieb/s3-speicher.md`. Warum: Staging und Produktion laufen auf S3, und der Weg
  Browser → S3 → Abschluss soll vor jedem Rollout einmal wirklich gelaufen sein.
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
- Deployment nach Staging, Produktion vorgesehen (#27): Container-Image (gunicorn, statische
  Dateien über WhiteNoise), eine Compose-Datei mit Caddy für beide Umgebungen, Einrichtung des
  Hosts per cloud-init oder SSH (`deploy/host-einrichten.sh`) und Deploy per GitHub Actions:
  jeder grüne Push auf `main` nach Staging, Tags `vX.Y.Z` nach Freigabe in die Produktion,
  Zurückrollen über *Run workflow*. Neuer Endpunkt `/healthz` prüft Datenbank und S3-Speicher.
  Anleitung in `docs/betrieb/deployment.md`. Warum: Der Upload-Weg soll unter echten Bedingungen
  (TLS, Hetzner-S3, Heimleitung, mehrere Browser) laufen, und die Produktion später auf demselben
  Weg ohne Umbau.
- Admin für die Betreiber (#29): Djangos Admin unter `/<ADMIN_PATH>/` mit eigenem Konto je
  Betreiber und gebremster Anmeldung (Fehlversuche je IP-Hash in der Datenbank). Startseite ist
  die Statistik: Abgaben, Master je Zustand und Kanal, Belegung gegen die Gesamtgrenze,
  Dubletten, Ablehnungen nach Kategorie und Verlauf je Tag. Die Aktion lässt sich pflegen (Objekt
  und Beginn ab dem Start gesperrt, Gesamtgrenze nicht unter der Belegung). Abgaben suchen,
  filtern und korrigieren; Master löschen, Rückzug und Widerruf als Fachverhalten, einzelne Master
  über einen kurz gültigen Link herunterladen; alles im Protokoll. Die Prüfung liefert jetzt eine
  feste Kategorie je Ablehnung. Warum: Die Betreiber sollen den Stand der Aktion sehen und
  Anfragen von Teilnehmenden ohne Zugang zum Server erledigen können. Betrieb:
  `docs/betrieb/admin.md`.
- Rückzug und Master löschen durch Teilnehmende (#30): Auf der Abgabeseite lassen sich bis zum
  Ende der Aktion einzelne Master löschen und die ganze Abgabe zurückziehen, jeweils nach einer
  Rückfrage. Der Rückzug wird als „durch Teilnehmende“ vermerkt; danach zeigt die Seite nur noch
  Kennung und Zeitpunkt. In der Nachfrist und danach ist beides gesperrt, die Abgabeseite sagt
  dann, warum. Lädt ein anderer Tab einen gerade gelöschten Master noch hoch, meldet der
  Uploader „Dieser Master wurde gelöscht.“ Warum: ADR 0002 verspricht,
  dass Teilnehmende ihre Abgabe im selben Browser selbst ändern und zurückziehen können, ohne
  sich beim Betreiber melden zu müssen.
- Nennung nur mit Einwilligung zur Veröffentlichung (#33): Das Formular verlangt die Nennung nur
  noch, wenn das Häkchen zur Veröffentlichung gesetzt ist; das Feld steht jetzt nach dem Häkchen
  und ist mit JavaScript bis dahin gesperrt. Ohne Häkchen wird ein eingetragener Name verworfen,
  die Abgabeseite sagt das einmal, und Abgabeseite und Admin zeigen „anonym“. Im Admin bekommt
  eine anonyme Abgabe keinen Namen, und mit Einwilligung bleibt die Nennung Pflicht. Begleitdateien
  enthalten die Nennung nur bei gültiger Einwilligung, sonst `null`. Der Widerruf der
  Veröffentlichung löscht die Nennung und schreibt die Begleitdateien der Abgabe neu. Warum: Wer
  anonym beitragen will, soll keinen Namen angeben müssen, und ohne Rechtsgrundlage soll kein Name
  im Speicher liegen.
- Export, Manifest, Löschfrist und Datenschutzhinweis (#34): Im Admin unter *Aktion → Export*
  gibt es jederzeit einen vorläufigen Export (nur Manifest, ohne Links) und nach Ende der Aktion
  plus Nachfrist genau einmal den endgültigen Export. Er friert alle Submissions ein, auch für
  Betreiber (Angaben, Belichtungsangaben, Master), und stellt bis zum Ablauf der Löschfrist auf Wunsch neue, 7 Tage gültige Links aus,
  als Manifest und als Download-Liste für `aria2c` mit Prüfsummen, samt Equipment-Fotos. Widerruf und Löschung danach
  sind Nachträge: im Admin gelistet, im Manifest markiert und per Betriebsmeldung gemeldet. 30 Tage
  nach dem endgültigen Export löscht `manage.py delete_after_export` (täglich per Cron) alle
  Master, Begleitdateien und Angaben, mit Betriebsmeldung sieben Tage vorher und danach. Der
  Datenschutzhinweis steht unter `/datenschutz/`, versioniert passend zu `CONSENT_TEXT_VERSION`
  und vom Formular verlinkt; IP-Hashes der Anmeldung bleiben höchstens eine Stunde. Neu Pflicht im
  GitHub-Environment: `PRIVACY_CONTACT`; für Betriebsmeldungen `OPERATOR_EMAILS` und SMTP. Warum:
  Die Betreiber brauchen am Ende alle Master mit einem festen Stand und dem Nachweis der
  Einwilligungen, und die Daten der Teilnehmenden sollen nicht länger liegen bleiben als nötig
  (ADR 0008).
- Unterbrochene Uploads abbrechen (#39): Jeder unterbrochene Upload hat in der Master-Liste der
  Abgabeseite einen Knopf „Abbrechen“, auch nach dem Neuladen, auch wenn der Upload im Speicher
  nie angelegt wurde, und auch ohne JavaScript. Abbrechen gibt die Reservierung sofort frei, die
  Belegung wird ohne Neuladen aktualisiert. Gab es in den letzten 5 Minuten noch Anfragen, steht
  der Upload als „läuft gerade oder wurde eben unterbrochen“ da, und Abbrechen fragt nach.
  Warum: Bisher ließ sich so ein Upload nur abbrechen, indem man dieselbe Datei noch einmal
  auswählte, und ein nie angelegter blockierte die Quote bis zur Bereinigung nach 7 Tagen.
- Fachregeln an einer Stelle (#42): Gesamtgrenze nicht unter der Belegung, Belegung je Abgabe,
  Rückzug nach Widerruf, Zeitfenster des Uploaders und „Ende nach Beginn“ stehen nur noch in
  `uploads`, `services` und im Modell; Admin, Abgabeseite und `manage.py campaign` fragen dort
  nach. `manage.py campaign` prüft dabei alle Angaben wie der Admin. Warum: Ändert sich eine
  Regel, sollen Admin-Liste, Abgabeseite und Befehl nicht unbemerkt Verschiedenes zeigen.
- Gesamtgrenze im Befehl (#42): `manage.py campaign` lehnt eine Gesamtgrenze unter der aktuellen
  Belegung ab, wie schon der Admin. Warum: Sonst ließe sich über den Befehl eine Grenze setzen,
  die die laufenden Uploads und angenommenen Master schon überschreiten.
- Fassung des Hinweistextes einstellbar beim Deploy (#43): `CONSENT_TEXT_VERSION` steht jetzt in
  `docs/betrieb/deployment.md` und wird als Variable aus dem GitHub-Environment in die `.env`
  übernommen. Warum: Jede Einwilligung speichert diese Fassung; bisher galt auf dem Host immer der
  Standard `2026-11`, auch nach einer Änderung des Hinweistextes.
- Belichtungsangaben je Master (#50): Belichtung pro Light, Anzahl Lights, Gesamtbelichtung,
  Instrument und Teleskop werden beim Abschluss des Uploads aus dem Header gelesen (nur eine
  feste Auswahl von Schlüsseln, nie Standort oder Beobachter). Auf der Abgabeseite können
  Teilnehmende sie bis zum Ende der Aktion ergänzen und korrigieren, danach die Betreiber im
  Admin. Fehlende Werte schlägt der Server vor, statt sie still zu übernehmen. Für schon
  hochgeladene Master liest `manage.py backfill_exposure` die Werte aus dem Header. Warum: Die Betreiber
  brauchen die Belichtung je Kanal für die Weiterverarbeitung, und die Header der Programme sind
  uneinheitlich (z. B. ist `EXPTIME` beim DWARF die Gesamtzeit).
- Glossar: „Fassung des Hinweistextes“ (#57): Der Begriff für `Consent.text_version` steht jetzt
  im Glossar, „Version“ ist unter *Avoid* gelistet, und der Kommentar zu `CONSENT_TEXT_VERSION`
  in den Einstellungen sagt dasselbe wie das Modell. Warum: Ein Fachbegriff, der in Modell,
  Betriebsdoku und Changelog schon „Fassung“ heißt, gehört ins Glossar, damit nicht beide
  Wörter nebeneinander wachsen.
- Hinweis auf Standort- und Personendaten im Dateikopf der Master (#62): Der Datenschutzhinweis
  (neue Fassung `2026-11-25-2`, `CONSENT_TEXT_VERSION` steht jetzt darauf) nennt `SITELAT`,
  `SITELONG`, `OBSGEO-*` und `OBSERVER` und erklärt, dass sie unverändert in den Dateien bleiben,
  mit dem Export zu den Betreibern gehen und nach der Löschfrist nur noch in deren Kopien liegen.
  Die Submission-Seite zeigt vor dem Upload einen kurzen Hinweis, wie man die Keywords vorher
  entfernt. Schwarmstack ändert die Dateien weiterhin nicht (ADR 0003) und erkennt die Keywords
  nicht. Warum: Teilnehmende sollen wissen, was in ihren Dateien steckt, bevor sie hochladen.
  Folge: Wer ein Equipment-Foto ersetzt, bestätigt dessen Einwilligung einmal neu, weil sich die
  Fassung geändert hat.
- Begriffe nach dem Glossar (#66): Aus der Abgabe wird die Submission, aus der Abgabe-Kennung die
  Submission-ID, aus dem Rückzug die Löschung („Submission löschen“) und aus der Nennung die
  Namensnennung; im Admin heißt es „Angaben ändern“. Felder `deleted_at`/`deleted_by` per
  Migration umbenannt, die Daten bleiben. Seiten liegen jetzt unter `/submission/<ID>/`, alte
  Adressen unter `/abgabe/…` leiten dauerhaft um. Widerrufen lässt sich nur noch die
  Einwilligung zur Namensnennung; wer die Nutzung im Projekt nicht mehr will, löscht die
  Submission. Warum: Oberfläche, Code und Doku sollen dieselben Wörter benutzen wie das Team,
  und ein eigener Widerruf der Nutzung war nur eine zweite Tür zur Löschung.
- Angaben ändern durch Teilnehmende (#67): Auf der Submission-Seite lassen sich Setup und
  Namensnennung bis zum Ende der Aktion selbst ändern, wie bisher nur im Admin. Die
  Namensnennung gibt es nur mit gültiger Einwilligung und darf dann nicht leer sein; nach der
  Löschung geht nichts mehr. Die Begleitdateien werden neu geschrieben, und das Protokoll
  nennt „Teilnehmende“ als Urheber (reservierter, nicht anmeldbarer Benutzer). Warum: ADR 0002
  verspricht, dass Teilnehmende ihre Angaben ohne den Betreiber ändern können.
- Widerruf der Namensnennung durch Teilnehmende (#68): Auf der Submission-Seite können
  Teilnehmende ihre Einwilligung zur Namensnennung nach einer Rückfrage selbst widerrufen,
  jederzeit, auch in der Nachfrist und nach dem Ende der Aktion. Die Einwilligung bleibt mit dem
  Zeitpunkt des Widerrufs stehen, die Namensnennung wird gelöscht, die Begleitdateien werden
  neu geschrieben, und die Seite zeigt danach „anonym“. Nach einer Löschung gibt es nichts mehr
  zu widerrufen. Warum: Nach DSGVO Art. 7 Abs. 3 muss der Widerruf so einfach sein wie die
  Erteilung; bisher konnten nur die Betreiber einen Widerruf vermerken.
- Namensnennung nachträglich erlauben (#69): Wer eine Submission anonym angelegt oder die
  Namensnennung widerrufen hat, kann sie auf der Submission-Seite bis zum Ende der Aktion
  (wieder) erlauben, so oft er will. Die Einwilligung wird ausdrücklich erteilt wie beim
  Anlegen: eigenes Häkchen, Verweis auf den Datenschutzhinweis in der aktuellen Fassung, Name
  Pflicht. Dabei entsteht eine neue Einwilligung mit eigenem Zeitpunkt; die widerrufene bleibt
  als Nachweis stehen, und je Zweck gilt höchstens eine, die nicht widerrufen ist. Das Manifest
  und der Admin führen darum zu einer Art mehrere Einwilligungen, nach Zeitpunkt der Erteilung
  geordnet. Nach dem Ende der Aktion und nach einer Löschung geht es nicht mehr; der Widerruf
  bleibt jederzeit möglich. Die Begleitdateien werden danach neu geschrieben. Warum: Wer
  anonym angefangen oder widerrufen hat, soll sich später doch nennen lassen können, ohne die
  Submission zu löschen und neu anzulegen.
- Bucket-Einrichtung beim Deploy (#73): Verweigert der Speicher das Setzen von CORS oder
  Lifecycle mit `AccessDenied`, warnt `s3_bucket_setup` nur und lässt den CORS-Preflight
  entscheiden; passt er, läuft der Deploy weiter. Andere Fehler brechen weiter ab. Warum: Hetzner
  verweigert seit dem 24.11.2026 diese Schreibzugriffe im ganzen Projekt, die Freigaben aus
  früheren Deploys greifen aber weiter. Ohne den Workaround blieb Staging auf einer alten Version.
- Nachtrag nach dem endgültigen Export auf allen Wegen (#78): Ein Widerruf der Einwilligung zur
  Namensnennung auf der Submission-Seite (#68), ein Widerruf im Admin und eine Löschung im Admin
  nach dem endgültigen Export wirken wie sonst und werden als Nachtrag markiert: im Admin
  gelistet, im Manifest als `amended_at` vermerkt und mit einer Betriebsmeldung gemeldet, die nur
  die Submission-ID enthält. Vor dem endgültigen Export gibt es keinen Nachtrag, ebenso wenig
  für einen Widerruf, der nichts ändert (schon widerrufen oder schon gelöscht). Warum: Die
  Betreiber sollen ihre Kopien und die Credits-Liste anpassen, auch wenn die Teilnehmenden selbst
  widerrufen (ADR 0008).
- Equipment-Foto (#82): Teilnehmende können ihrer Submission freiwillig ein Foto ihres Setups
  beilegen, beim Anlegen oder später in „Angaben ändern“ (hinzufügen, ersetzen, löschen) bis zum
  Ende der Aktion. Dafür braucht es ein eigenes, nicht vorangekreuztes Häkchen zur Einwilligung;
  wer das Foto löscht, widerruft sie. Erlaubt sind JPEG, PNG, WebP und HEIC bis 10 MB. Der Server
  dekodiert das Bild und schreibt nur die Pixel neu (JPEG), sodass kein Standort, keine
  Gerätedaten und keine Zeitstempel in der gespeicherten Datei bleiben; das Original und der
  Dateiname werden nie gespeichert. In der Seitenleiste der Submission-Seite steht ein
  Thumbnail unter „Setup“; die Betreiber sehen Foto und Thumbnail im Admin und können das Foto im
  Auftrag löschen. Die Einwilligung gibt es jetzt je Zweck einmal gültig, widerrufene bleiben als
  Nachweis stehen. `CONSENT_TEXT_VERSION` steht auf `2026-11-25`. Warum: Betreiber ordnen das
  Setup mit dem Foto ein, ohne dass Teilnehmende unbemerkt ihre Adresse mitgeben.
  Noch offen: Foto im Export und Manifest und im Datenschutzhinweis (beides #34) sowie das
  Löschen nach der Löschfrist (ADR 0008).
- Equipment-Foto nach der Löschfrist (#85): Foto und Thumbnail verschwinden nach Ablauf der
  Löschfrist mit allen übrigen Objekten aus dem Speicher (ADR 0008). Scheitert das Löschen eines
  Objekts, löscht `delete_after_export` trotzdem alle übrigen, lässt die Datenbank stehen,
  meldet es den Betreibern („Löschung unvollständig“) und versucht es am nächsten Tag erneut.
  Warum: Ein einzelner Speicherfehler ließ bisher alle weiteren Objekte liegen.
- Kanal aus dem Header (#95): Bei Mastern mit einer Ebene liest der Server den Filternamen
  (`FILTER`, `FILT-1`, `INSFLNAM`, in XISF `Instrument:Filter:Name`) und schlägt einen passenden
  Kanal vor, wenn er vom beim Upload gewählten abweicht. Teilnehmende übernehmen den Vorschlag mit
  einem Klick (Herkunft `header`) oder ändern den Kanal von Hand (Herkunft `manuell`); der Header wird nie als Ganzes gespeichert.
  Dualband- und Lichtverschmutzungsfilter sowie `IR-cut` ergeben keinen Vorschlag.
  Warum: Ein beim Upload falsch gewählter Kanal fiel bisher nicht auf, obwohl der Header ihn oft nennt.
- Release-Image-Prüfung (#99): `scripts/image-pruefen.sh` meldet das öffentliche CA-Bündel `cacert.pem` (certifi in pip und botocore) nicht mehr als Schlüsseldatei. Warum: Der Probelauf von `release.yml` brach daran im Schritt „Keine .env und keine Zugangsdaten im Image“ ab, obwohl nichts Geheimes im Image lag.
- Release nach „Merge ist Release“ (#99, ADR 0011): Der Skill `/release <version>` öffnet den PR „Release vX.Y.Z“; nach dem Merge testet `release.yml`, baut das Image für `linux/amd64` und `linux/arm64`, pusht es nach `ghcr.io/northalpha/schwarmstack` (Tags `vX.Y.Z` und `vX.Y`, nie `latest`) mit Prüfsummen und Attestation und setzt erst danach Tag und GitHub Release. Der Image-Job prüft, dass keine `.env` und keine Zugangsdaten im Image liegen. Der Tag `v*` deployt nicht mehr nach Produktion; das geht nur noch über „Run workflow“ mit Image-Tag. Warum: Ein von Hand gesetzter Tag vor dem grünen Lauf könnte ein kaputtes Release erzeugen.
- Selbstbetrieb (#100): `deploy/selbst/` startet App, Caddy und Garage mit einem Skript
  (`./setup.sh`, Probemodus `--lokal`). Es erzeugt alle Geheimnisse, richtet Bucket und CORS ein,
  legt Aktion und Betreiber-Konto an und lässt sich wiederholen, ohne etwas Unnötiges zu ändern.
  Anleitung in `docs/betrieb/selbstbetrieb.md`. Warum: Dritte sollen eine eigene Aktion ohne
  GitHub-Deployment betreiben können (ADR 0011).
- Datenschutzhinweis: verantwortliche Stelle und Hoster kommen aus Umgebungsvariablen (#101). Neu:
  `OPERATOR_NAME`, `OPERATOR_ADDRESS`, `HOSTER_NAME`, `HOSTER_ADDRESS` (neben `PRIVACY_CONTACT`), in `deploy.sh`,
  `deploy.yml` und
  `docs/betrieb/deployment.md`. Fehlt eine Angabe, warnt der Admin und beim Start (`submissions.W001`),
  und `/datenschutz/` zeigt „noch nicht vollständig“ (503) statt eines Textes mit leeren Stellen.
  Der Wortlaut für die DZVF bleibt zeichengenau gleich (Test gegen `tests/golden/`), die Fassung
  `CONSENT_TEXT_VERSION` ändert sich nicht. Warum: Selbstbetreiber (ADR 0011) brauchen ihre eigenen
  Angaben. Folge für die DZVF: Die vier Werte vor dem nächsten Deploy als GitHub-Variablen
  setzen (`DZVF`, `Hetzner Online GmbH` und die Anschriften), sonst bricht `deploy.sh` ab.
  Die Anschriften stehen im heutigen Wortlaut nicht.
- Public-Vorbereitung (#102): `SECURITY.md` (Meldung über „Private vulnerability reporting“, nur der
  letzte Release), `CONTRIBUTING.md` (Issues willkommen, Pull Requests nur nach Absprache),
  `CODE_OF_CONDUCT.md`, Issue-Formulare für Fehler, Wunsch und Frage (keine leeren Issues) und
  `THIRD_PARTY.md` mit den Lizenzhinweisen zum mitgelieferten Uppy-Bundle. Warum: Das Repo soll
  öffentlich werden können (ADR 0011). Geprüft: Kein Workflow gibt Forks Zugriff auf Secrets
  (`pull_request`, kein `pull_request_target`; Secrets nur bei Push und von Hand), `permissions:`
  sind minimal, ein Muster-Scan der Historie (Schlüsselformate, Schlüssel- und Env-Dateien) fand nichts; er muss nach dem Umschreiben der Historie noch einmal laufen.
- README neu (#103): Was Schwarmstack kann, Bilder, Ausprobieren, Hinweise zum Selbstbetrieb,
  Mitmachen; dazu `README.en.md` als Kurzfassung und `scripts/screenshots.py`, das die Bilder in
  `docs/bilder/` mit Demo-Daten reproduzierbar erzeugt. Warum: Das Repo soll öffentlich werden
  können, und die bisherige README war ein reiner Entwickler-Einstieg.
- Installer-Test (#105): Der CI-Job „selbstbetrieb“ führt `deploy/selbst/setup.sh --lokal` ohne
  Rückfragen aus und prüft `/healthz`, Bucket, CORS-Preflight und dass ein zweiter Lauf nichts
  ändert. Er läuft bei Änderungen an `deploy/` und steht als `selbstbetrieb.yml` dem Release-Workflow
  (#99) bereit, der ihn vor dem Veröffentlichen aufruft. Lokal:
  `scripts/selbstbetrieb-test.sh`. Warum: Ein kaputter Installer fällt so in der CI auf, nicht
  erst bei Dritten, die eine eigene Aktion betreiben (ADR 0011).
- Abhängigkeit `altcha` entfernt (#109): Der Code unter `src/` nutzt sie nicht mehr, ein Captcha
  ist vorerst nicht geplant. Damit entfällt auch der ALTCHA-Abschnitt in `THIRD_PARTY.md`.
- Im Admin stehen Quote und Gesamtgrenze der Aktion in GiB, die Höchstgröße je Master in MiB,
  statt in Bytes. Warum: Zahlen wie 2147483648 tippt niemand fehlerfrei, und `manage.py campaign`
  nimmt dieselben Einheiten.
- ADR 0011: Öffentliche Releases („Merge ist Release“) und Selbstbetrieb per Git-Tag und
  `setup.sh`. Warum: Das Repo soll öffentlich werden können; Release, Image, Installer und
  Datenschutz-Angaben für andere Betreiber waren bisher nicht festgelegt.
- Ausrollen prüft `S3_ENDPOINT_URL` vorab: Ohne `https://` bricht das Skript ab, bevor etwas
  auf den Host geht. Warum: boto3 lehnt einen Endpunkt ohne Schema ab, und das fiel bisher erst
  nach dem Neustart über `/healthz` auf.
- Doku, Tests und Beispiele nutzen nur noch `example.com`-Adressen statt echter Domains. Warum:
  Das Repo soll öffentlich werden können, ohne Betriebsdetails der Aktion preiszugeben.
- Ein geändertes Caddyfile greift beim Deploy sofort: Der Caddy-Container startet dann neu.
  Warum: Bisher lief Caddy mit der alten Konfiguration weiter, so verlangte Staging für
  `/zahlen.json` trotz Ausnahme weiter Basic Auth.
- Community-Zahlen mit Belichtung (#50, #53): `GET /zahlen.json` liefert zusätzlich `lights`,
  `exposureSeconds` (ganze Sekunden) und `mastersWithExposure`. Summiert wird über angenommene Master
  ohne Dubletten; Master ohne Angaben fehlen in den Summen und zählen nicht in
  `mastersWithExposure`. Warum: Die Community-Seite soll die aufsummierte Belichtung zeigen.
- Community-Zahlen (#53): `GET /zahlen.json` liefert öffentlich die Zahl der Abgaben, der
  angenommenen Master und ihre Datenmenge in Bytes, mit CORS für die Ursprünge aus
  `COMMUNITY_ORIGINS` und einem kurzen Cache (`COMMUNITY_CACHE_SECONDS`, Standard 10 s). Warum: Die
  Community-Seite soll den Stand der Aktion zeigen, ohne dass die Betreiber Zahlen abschreiben.
- Lokaler Start im frischen Checkout: Das Datenverzeichnis (`var/` bzw. `DATA_DIR`) wird beim
  Start angelegt. Warum: `migrate` brach sonst mit „unable to open database file“ ab, weil
  SQLite die Datei anlegt, aber nicht das Verzeichnis.
- Prüfung: Views, API und Admin dürfen nichts selbst speichern oder löschen (`tests/test_fachregeln_ort.py`). Warum: Fachregeln landeten viermal zuerst in der View und wurden erst im Review nach `services` verschoben.
- Gelöschte Submissions belegen keinen Platz mehr im Browser: Die Grenze von 3 gilt für bestehende Submissions, nicht für alle je angelegten (ADR 0002). Der Einstieg führt nicht mehr auf eine gelöschte Submission, sondern zum Formular. Außerdem kleinere Schrift bei den Links in der Seitenleiste und auf den Seiten „Angaben ändern“ und „Widerruf“. Warum: Wer zum Testen drei Submissions löschte, konnte keine neue mehr anlegen, weil das Cookie auch gelöschte IDs behält.
- Neue Optik für alle Teilnehmenden-Seiten („Nacht“): dunkel mit Sternenfeld und Verlauf aus der Marke, hell bei hellem System. Auf der Submission-Seite stehen ID, Belegung und Angaben in einer Seitenleiste, die Belichtungsangaben sind erstmals gestaltet. Schriften (Inter, Space Grotesk, JetBrains Mono, OFL) liefern wir selbst aus. Warum: Die Seite war funktional, wirkte aber unfertig; Klassen, IDs und Texte bleiben, Tests und Skripte sind unberührt.
- CORS des Buckets bei jedem Deploy: `auf-dem-host.sh` ruft `s3_bucket_setup` mit der Domain
  der Umgebung auf. Der Befehl wandelt Umlaut-Domains in Punycode um und prüft die Freigabe
  danach per CORS-Preflight wie ein Browser; greift sie nicht, bricht der Deploy vor der
  Migration ab. Warum: Mit fehlender oder als Unicode gesetzter Herkunft scheiterte jeder
  Upload im Browser mit „Network error during S3 request“, und das fiel erst beim Hochladen auf.
- Upload-Anzeige: Der Balken steht nach dem Hochladen auf 100 %, und der Bucket gibt
  `x-amz-error-code` frei. Warum: Uppy meldet den letzten Fortschritt nicht immer, der Balken
  blieb knapp darunter stehen; ohne den Header zeigte Uppy S3-Fehler nur ohne Code an.
- Namensnennung widerrufen: Auf der Seite „Angaben ändern“ gibt es jetzt unter dem Namen ein Häkchen zum Widerruf. Der Link auf der Submission-Seite erscheint nur noch, wenn sich Angaben nicht mehr ändern lassen (nach dem Ende der Aktion). Warum: Der Widerruf gehört zu den Angaben zum Namen.

## Vorgeschichte (verworfener Ansatz)

Die Versionen 0.0.1 und 0.1.0 gehören zum verworfenen Ansatz A0/A1 (ADR 0011); ihre Tags sind gelöscht, es gibt dazu kein Release. Der erste öffentliche Release ist 0.2.0.

- 0.0.1, A0: Gerüst mit Django 5.2 LTS, Settings aus der Umgebung, `/healthz` und Startseite, damit das Walking Skeleton früh auf Staging läuft.
- 0.1.0, A1: Datenmodell mit Quote und Gesamtgrenze, Tokens nur als HMAC-Hash, Django-Admin mit Zweitfaktor (django-otp), ALTCHA als optionales Modul und `manage.py otp_setup`.
