- Lokaler Start im frischen Checkout: Das Datenverzeichnis (`var/` bzw. `DATA_DIR`) wird beim
  Start angelegt. Warum: `migrate` brach sonst mit „unable to open database file“ ab, weil
  SQLite die Datei anlegt, aber nicht das Verzeichnis.
