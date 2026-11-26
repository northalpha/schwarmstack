# Changelog

## Unveröffentlicht

Neue Einträge stehen bis zum Release je Änderung in [`changelog.d/`](changelog.d/README.md).

## Vorgeschichte (verworfener Ansatz)

Die Versionen 0.0.1 und 0.1.0 gehören zum verworfenen Ansatz A0/A1 (ADR 0011); ihre Tags sind gelöscht, es gibt dazu kein Release. Der erste öffentliche Release ist 0.2.0.

- 0.0.1, A0: Gerüst mit Django 5.2 LTS, Settings aus der Umgebung, `/healthz` und Startseite, damit das Walking Skeleton früh auf Staging läuft.
- 0.1.0, A1: Datenmodell mit Quote und Gesamtgrenze, Tokens nur als HMAC-Hash, Django-Admin mit Zweitfaktor (django-otp), ALTCHA als optionales Modul und `manage.py otp_setup`.
