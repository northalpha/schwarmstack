- Gesamtgrenze im Befehl (#42): `manage.py campaign` lehnt eine Gesamtgrenze unter der aktuellen
  Belegung ab, wie schon der Admin. Warum: Sonst ließe sich über den Befehl eine Grenze setzen,
  die die laufenden Uploads und angenommenen Master schon überschreiten.
