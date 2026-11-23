# Changelog

## Unveröffentlicht

Neue Einträge stehen bis zum Release je Änderung in [`changelog.d/`](changelog.d/README.md).

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
