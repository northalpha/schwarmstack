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
