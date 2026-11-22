// Registriert den Rechen-Worker (PBKDF2) aus eigener Quelle; das Widget lädt ihn nicht von außen.
const workerUrl = new URL("altcha-pbkdf2-worker.js", import.meta.url).href;
for (const algorithm of ["PBKDF2/SHA-256", "PBKDF2/SHA-384", "PBKDF2/SHA-512"]) {
  globalThis.$altcha.algorithms.set(algorithm, () => new Worker(workerUrl));
}
