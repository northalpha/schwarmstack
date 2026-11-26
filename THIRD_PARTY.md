# Drittsoftware

Schwarmstack steht unter der [MIT-Lizenz](LICENSE). Diese Datei nennt fremden Code, der **im Repo selbst** liegt. Python-Abhängigkeiten (siehe `pyproject.toml` und `uv.lock`) werden beim Bau des Images installiert und bringen ihre Lizenzdateien in ihren Paketen mit.

## Uppy (mitgeliefert)

- Datei: `src/submissions/static/submissions/vendor/uppy/uppy.min.js`, Version 6.0.7 (npm-Paket `uppy`), unverändert (ADR 0005).
- Lizenz: MIT, Copyright (c) 2018 Transloadit. Der Text liegt neben der Datei: `src/submissions/static/submissions/vendor/uppy/LICENSE`.
- Das Bündel enthält weiteren Code. Die Hinweise dazu stehen am Ende von `uppy.min.js` („Bundled license information“) und bleiben dort unverändert erhalten:

  | Bestandteil         | Lizenz       | Copyright                  |
  | ------------------- | ------------ | -------------------------- |
  | classnames          | MIT          | 2018 Jed Watson            |
  | compressorjs 1.3.0  | MIT          | 2018-present Chen Fengyuan |
  | cropperjs 1.6.2     | MIT          | 2015-present Chen Fengyuan |
  | tus-js-client (mit regenerator-runtime) | MIT | 2014-present Facebook, Inc. (regenerator-runtime) |
  | polyglot.js (Teil)  | nur Verweis auf die LICENSE im Projekt `airbnb/polyglot.js` | – |

  Die Tabelle gibt nur wieder, was das Bündel selbst nennt; die Kurzhinweise dort ersetzen nicht den vollen Lizenztext der jeweiligen Pakete, der in deren npm-Paketen steht. Das Bündel setzt weitere npm-Pakete zusammen; deren Lizenzen stehen in den jeweiligen Paketen und im Paket `uppy`.
