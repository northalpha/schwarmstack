- Im Admin stehen Quote und Gesamtgrenze der Aktion in GiB, die Höchstgröße je Master in MiB,
  statt in Bytes. Warum: Zahlen wie 2147483648 tippt niemand fehlerfrei, und `manage.py campaign`
  nimmt dieselben Einheiten.
