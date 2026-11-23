- Neuaufbau, Abgabe anlegen (#9): Django-Gerüst, die Aktion als genau ein Datensatz
  (`manage.py campaign`), Formular mit Nennung, Setup-Beschreibung und Einwilligungen,
  Abgabe-Kennung (`SW-XXXX`) und Abgabeseite nur über ein signiertes Cookie. Warum: Teilnahme
  ohne Konto und ohne Token (ADR 0002); alles Weitere (Upload, Prüfung, Quote) baut darauf auf.
