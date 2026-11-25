- Equipment-Foto nach der Löschfrist (#85): Foto und Thumbnail verschwinden nach Ablauf der
  Löschfrist mit allen übrigen Objekten aus dem Speicher (ADR 0008). Scheitert das Löschen eines
  Objekts, löscht `delete_after_export` trotzdem alle übrigen, lässt die Datenbank stehen,
  meldet es den Betreibern („Löschung unvollständig“) und versucht es am nächsten Tag erneut.
  Warum: Ein einzelner Speicherfehler ließ bisher alle weiteren Objekte liegen.
