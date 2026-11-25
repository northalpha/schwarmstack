- Export, Manifest, Löschfrist und Datenschutzhinweis (#34): Im Admin unter *Aktion → Export*
  gibt es jederzeit einen vorläufigen Export (nur Manifest, ohne Links) und nach Ende der Aktion
  plus Nachfrist genau einmal den endgültigen Export. Er friert alle Submissions ein, auch für
  Betreiber (Angaben, Belichtungsangaben, Master), und stellt bis zum Ablauf der Löschfrist auf Wunsch neue, 7 Tage gültige Links aus,
  als Manifest und als Download-Liste für `aria2c` mit Prüfsummen. Widerruf und Löschung danach
  sind Nachträge: im Admin gelistet, im Manifest markiert und per Betriebsmeldung gemeldet. 30 Tage
  nach dem endgültigen Export löscht `manage.py delete_after_export` (täglich per Cron) alle
  Master, Begleitdateien und Angaben, mit Betriebsmeldung sieben Tage vorher und danach. Der
  Datenschutzhinweis steht unter `/datenschutz/`, versioniert passend zu `CONSENT_TEXT_VERSION`
  und vom Formular verlinkt; IP-Hashes der Anmeldung bleiben höchstens eine Stunde. Neu Pflicht im
  GitHub-Environment: `PRIVACY_CONTACT`; für Betriebsmeldungen `OPERATOR_EMAILS` und SMTP. Warum:
  Die Betreiber brauchen am Ende alle Master mit einem festen Stand und dem Nachweis der
  Einwilligungen, und die Daten der Teilnehmenden sollen nicht länger liegen bleiben als nötig
  (ADR 0008).
