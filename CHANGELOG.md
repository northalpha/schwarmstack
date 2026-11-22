# Changelog

## 0.2.0

- A2: Einstieg über die Projektwebsite. `/start/<slug>/` prüft den Referer (nur der Origin, nie
  gespeichert) gegen `Event.entry_origins` und setzt bei Erfolg ein signiertes Entry-Ticket
  (HttpOnly, SameSite=Lax, 60 min). Ohne passenden Referer erscheint „Bitte starte über die
  Projektseite“, ohne das Verfahren zu erklären. Abgelehnte Versuche werden gezählt (für die
  Statistik). Warum: Wer auf „Upload“ klickt, soll zum Projekt gehören; der Referer ist ein weiches
  Tor, dahinter stehen Rate-Limits, Quote und die Dateiprüfung.
- Teilnahmeformular mit Einwilligungen (Pflicht: Datenschutz gelesen, Nutzung im Projekt), Anlegen
  der Abgabe, persönlicher Link `/a/<token>/` (einmalig angezeigt, nur als Hash gespeichert), ein
  Ticket gilt für genau eine Abgabe.
- Abgabeseite `/abgabe/`: Quotenbalken, Stack-Karten mit Status, Stack-Formular mit
  Belichtungszeilen und Vorbelegung der Ausrüstung aus dem letzten Stack.
- Rate-Limits je gehashter IP: Einstieg 20/Stunde, neue Abgaben 5/Stunde. Die Client-Adresse kommt
  hinter Tailscale und Caddy aus `X-Forwarded-For` (`CLIENT_IP_SKIP`).
- ALTCHA im Teilnahmeformular, wenn das Event es eingeschaltet hat.
- Datenschutz und Impressum (Vorlage mit den Betreiberdaten aus der Umgebung), Hinweis
  „Testsystem“ auf allen Seiten (`TEST_SYSTEM`).
- Der Upload selbst (Uppy, tusd-Hooks) folgt in A3; die Stack-Karten zeigen bis dahin „Das
  Hochladen der Dateien kommt in Kürze“.

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
