ALTCHA-Widget 3.7.0 (MIT, siehe LICENSE-altcha.txt), unverändert aus dem npm-Paket "altcha":
  altcha.min.js              <- dist/external/altcha.min.js
  altcha.css                 <- dist/external/altcha.css
  altcha-pbkdf2-worker.js    <- dist/workers/pbkdf2.js
  altcha-de.js               <- dist/i18n/de.js
Aktualisieren: neue Version von https://www.npmjs.com/package/altcha laden (npm pack altcha),
die vier Dateien ersetzen, Version hier und in CHANGELOG.md nachtragen. Der Server-Teil ist die
Python-Bibliothek altcha (uv.lock); Widget 3.x spricht das "PoW v2"-Protokoll von altcha 2.x.
