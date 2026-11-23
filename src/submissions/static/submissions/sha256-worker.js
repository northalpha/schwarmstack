// SHA-256 eines Masters im Web Worker mit WebCrypto (ADR 0005).
// WebCrypto hasht nur ganze Puffer, die Datei liegt also kurz vollständig im Speicher. Das ist
// vertretbar, weil ein Master höchstens 500 MB groß ist. Die Dateien werden nacheinander
// gehasht, damit nie mehr als eine gleichzeitig im Speicher liegt.
"use strict";

let queue = Promise.resolve();

async function sha256(blob) {
  if (!self.crypto || !self.crypto.subtle) {
    throw new Error("WebCrypto ist nicht verfügbar (nur über HTTPS oder localhost)");
  }
  const digest = await self.crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

self.onmessage = (event) => {
  const { id, blob } = event.data;
  queue = queue.then(async () => {
    try {
      self.postMessage({ id, sha256: await sha256(blob) });
    } catch (error) {
      self.postMessage({ id, error: String(error.message || error) });
    }
  });
};
