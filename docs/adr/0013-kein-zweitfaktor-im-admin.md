# Kein Zweitfaktor im Admin

Beim Review der Anwendung (#123) zeigte sich: `django-otp` stand in `pyproject.toml`, war aber weder in `INSTALLED_APPS` noch in der Middleware oder in `operator_site.py` eingebunden. Der Admin hatte nie einen Zweitfaktor; nur eine Zeile zu 0.1.0 im Changelog (verworfener Ansatz A1) erwähnte ihn.

## Entscheidung

- Der Admin der Betreiber bekommt **keinen** Zweitfaktor. Die tote Abhängigkeit `django-otp` ist entfernt.
- Der Schutz besteht aus: nur Konten per `createsuperuser`, geheimer `ADMIN_PATH`, Login-Bremse je IP (`login_limit.py`, ADR 0002) und Passwort-Regeln (`AUTH_PASSWORD_VALIDATORS`, mindestens 12 Zeichen, keine häufigen oder rein numerischen Passwörter).
- Der Kreis der Betreiber ist klein, die Daten sind nach der Aktion kurzlebig (ADR 0008). Ein Zweitfaktor wäre mehr Betrieb (Einrichtung, verlorene Geräte) für ein Hobbyprojekt (ADR 0012).

## Consequences

- Wer das Passwort eines Betreiber-Kontos kennt, kommt in den Admin. Betreiber wählen darum lange, einmalige Passwörter.
- Soll das später doch kommen, ist es eine neue Entscheidung mit eigenem ADR.
