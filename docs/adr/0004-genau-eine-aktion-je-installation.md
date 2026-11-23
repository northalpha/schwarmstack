# Genau eine Aktion je Installation

Schwarmstack bedient genau eine, einmalige Aktion (ein Objekt, ein Zeitraum). Es gibt kein Event-Modell mit mehreren parallelen Aktionen; Zeitraum, erlaubte Herkunft und Grenzen sind ein einziger Datensatz. Das hält Modell, Admin und Tests klein; eine weitere Aktion bedeutet eine neue Installation.

## Considered Options

- **Mehrere Events mit Slug und je eigenen Einstellungen** (erster Ansatz): verworfen, weil nur ein einmaliges Projekt geplant ist.
