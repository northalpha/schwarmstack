# Sicherheit

## Eine Schwachstelle melden

Bitte **kein öffentliches Issue** für Sicherheitslücken. Nutze stattdessen die private Meldung von GitHub:

1. Öffne den Reiter **Security** dieses Repos.
2. Wähle **Report a vulnerability** („Private vulnerability reporting“).
3. Beschreibe, was du gefunden hast, wie man es nachstellt und welche Version betroffen ist.

Die Meldung sehen nur die Betreiber. Fehlt der Knopf, ist die Funktion in den Repo-Einstellungen noch nicht eingeschaltet; öffne dann ein Issue **ohne Einzelheiten** („Ich möchte eine Sicherheitslücke melden“), und die Betreiber antworten dort, wie ihr vertraulich weiterschreibt.

Schwarmstack ist ein Hobbyprojekt. Wir lesen Meldungen, so schnell wir können, und versprechen keine Antwortzeit.

## Unterstützte Versionen

Sicherheitskorrekturen gibt es nur für den **letzten Release** (siehe [Releases](../../releases)). Wer eine ältere Version betreibt, aktualisiert zuerst.

## Was dazugehört

Schwachstellen in Schwarmstack selbst: Zugriff auf Daten anderer Teilnehmender, Umgehen der Quote oder des Zugangs zum Admin, Schwächen beim Upload, Offenlegen von Zugangsdaten. Nicht dazu gehören Fehler in der Einrichtung eines einzelnen Betreibers (Server, Domain, S3-Speicher) und Lücken in Drittsoftware ohne Bezug zu Schwarmstack; melde diese bei den jeweiligen Projekten.

## Automatische Prüfungen

Abhängigkeiten, Docker-Image und Workflows werden in CI automatisch auf bekannte Schwachstellen geprüft (Dependabot, `pip-audit`, Trivy, CodeQL, `zizmor`; siehe [ADR 0012](docs/adr/0012-sicherheitspruefungen-in-ci.md)). Funde ohne Fix und alles unterhalb von High erscheinen im Security-Tab, ohne den Build zu stoppen. Das ersetzt keine Meldung: Wenn du etwas findest, melde es wie oben beschrieben.
