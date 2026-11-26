- Kanal aus dem Header (#95): Bei Mastern mit einer Ebene liest der Server den Filternamen
  (`FILTER`, `FILT-1`, `INSFLNAM`, in XISF `Instrument:Filter:Name`) und schlägt einen passenden
  Kanal vor, wenn er vom beim Upload gewählten abweicht. Teilnehmende übernehmen den Vorschlag mit
  einem Klick (Herkunft `header`, sonst `manuell`); der Header wird nie als Ganzes gespeichert.
  Dualband- und Lichtverschmutzungsfilter sowie `IR-cut` ergeben keinen Vorschlag.
