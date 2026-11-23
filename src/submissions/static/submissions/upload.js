// Upload der Master direkt in den Speicher (ADR 0005), mit Uppy und dem AWS-S3-Plugin.
// Der Server signiert jede einzelne S3-Anfrage; die Daten laufen nie über ihn.
(() => {
  const root = document.getElementById("uploader");
  if (!root || !window.Uppy) return;
  root.hidden = false;

  const base = root.dataset.base;
  const csrf = root.dataset.csrf;
  const input = root.querySelector("input[type=file]");
  const queue = root.querySelector(".queue");
  const button = root.querySelector("button.start");
  const channelTemplate = document.getElementById("channel-template");
  // In der Nachfrist dürfen nur begonnene Uploads fortgesetzt werden.
  const mayStart = root.dataset.mayStart === "1";

  // Unterbrochene Uploads dieser Abgabe (vom Server). Wählen Teilnehmende dieselbe Datei
  // erneut aus, setzt Uppy über die Liste der schon übertragenen Teile fort.
  const resumable = new Map();
  for (const row of document.querySelectorAll("tr.resumable")) {
    resumable.set(`${row.dataset.name}|${row.dataset.size}`, { ...row.dataset });
  }

  // Prüfsumme im Web Worker, parallel zum Upload; gemeldet wird sie mit der Fertig-Meldung.
  const worker = new Worker(root.dataset.shaWorker);
  const waiting = new Map();
  worker.onmessage = (event) => {
    const { id, sha256, error } = event.data;
    const job = waiting.get(id);
    waiting.delete(id);
    if (error) job.reject(new Error(`Prüfsumme: ${error}`));
    else job.resolve(sha256);
  };
  const checksums = new Map(); // Datei-ID -> Promise der SHA-256
  function checksum(file) {
    if (!checksums.has(file.id)) {
      checksums.set(
        file.id,
        new Promise((resolve, reject) => {
          waiting.set(file.id, { resolve, reject });
          worker.postMessage({ id: file.id, blob: file.data });
        }),
      );
    }
    return checksums.get(file.id);
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Fehler ${response.status}`);
    return data;
  }

  const uppy = new Uppy.Uppy({
    autoProceed: false,
    restrictions: {
      allowedFileTypes: [".xisf", ".fits", ".fit", ".fts"],
      maxFileSize: Number(root.dataset.maxSize) || null,
    },
    locale: {
      strings: {
        youCanOnlyUploadFileTypes: "Nur XISF- oder FITS-Dateien (%{types}).",
        noDuplicates: "Die Datei „%{fileName}“ ist schon ausgewählt.",
        exceedsSize: "Größer als die erlaubten %{size}.",
      },
    },
  });
  const pending = new Map(); // vorläufiger Schlüssel -> Datei-ID
  const masters = new Map(); // Objekt-Schlüssel -> Master-ID

  uppy.use(Uppy.AwsS3, {
    shouldUseMultipart: true,
    limit: 2,
    generateObjectKey(file) {
      const key = `neu-${file.id}`;
      pending.set(key, file.id);
      return key;
    },
    async signRequest(request) {
      if (request.method === "POST" && !request.uploadId) {
        const file = uppy.getFile(pending.get(request.key));
        const started = await post(base, {
          channel: file.meta.channel,
          filename: file.name,
          size: file.size,
        });
        masters.set(started.key, started.masterId);
        uppy.setFileMeta(file.id, { masterId: started.masterId });
        return { url: started.url, key: started.key };
      }
      const masterId = masters.get(request.key);
      const signed = await post(`${base}${masterId}/signieren/`, {
        method: request.method,
        key: request.key,
        uploadId: request.uploadId,
        partNumber: request.partNumber,
      });
      return { url: signed.url };
    },
  });

  const rows = new Map();
  let uploadStarted = false;

  function updateButton() {
    const files = uppy.getFiles();
    button.disabled = files.length === 0 || files.some((f) => !f.meta.channel);
  }

  function setStatus(fileId, text, state) {
    const row = rows.get(fileId);
    if (!row) return;
    row.querySelector(".status").textContent = text;
    if (state) row.dataset.state = state;
  }

  function rejectRow(text) {
    const row = document.createElement("li");
    row.dataset.state = "error";
    row.textContent = text;
    queue.append(row);
  }

  uppy.on("file-added", (file) => {
    const match = resumable.get(`${file.name}|${file.size}`);
    if (!match && !mayStart) {
      queueMicrotask(() => uppy.removeFile(file.id));
      rejectRow(
        `${file.name}: Die Aktion ist beendet. Fortsetzen lassen sich nur unterbrochene Uploads.`,
      );
      return;
    }
    const row = document.createElement("li");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = file.name;
    const select = channelTemplate.content.firstElementChild.cloneNode(true);
    select.setAttribute("aria-label", `Kanal für ${file.name}`);
    select.addEventListener("change", () => {
      uppy.setFileMeta(file.id, { channel: select.value });
      setStatus(file.id, select.value ? "bereit" : "Kanal wählen");
      updateButton();
    });
    const progress = document.createElement("progress");
    progress.max = 100;
    progress.value = 0;
    const status = document.createElement("span");
    status.className = "status";
    status.textContent = "Kanal wählen";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "cancel";
    cancel.textContent = "Abbrechen";
    cancel.addEventListener("click", () => cancelFile(file.id));
    const pause = document.createElement("button");
    pause.type = "button";
    pause.className = "pause";
    pause.textContent = "Pause";
    pause.hidden = true;
    pause.addEventListener("click", () => {
      const paused = uppy.pauseResume(file.id);
      pause.textContent = paused ? "Weiter" : "Pause";
      if (paused) setStatus(file.id, "pausiert");
    });
    row.append(name, select, progress, status, pause, cancel);
    queue.append(row);
    rows.set(file.id, row);

    if (match) {
      resumable.delete(`${file.name}|${file.size}`);
      uppy.setFileMeta(file.id, { channel: match.channel, masterId: match.masterId });
      uppy.setFileState(file.id, { s3Multipart: { key: match.key, uploadId: match.uploadId } });
      masters.set(match.key, match.masterId);
      select.value = match.channel;
      select.disabled = true;
      status.textContent = "wird fortgesetzt";
    }
    updateButton();
  });

  // Abbrechen: Uppy bricht den Multipart-Upload im Speicher ab, der Server gibt die
  // Reservierung frei. Vor dem Start wird die Datei nur aus der Liste genommen.
  async function cancelFile(fileId) {
    const file = uppy.getFile(fileId);
    const row = rows.get(fileId);
    const masterId = file && file.meta.masterId;
    if (file) uppy.removeFile(fileId);
    rows.delete(fileId);
    if (!masterId) {
      row.remove();
      updateButton();
      return;
    }
    row.querySelector(".cancel").remove();
    row.dataset.state = "aborted";
    row.querySelector(".status").textContent = "abgebrochen";
    try {
      await post(`${base}${masterId}/abbrechen/`);
    } catch (error) {
      row.querySelector(".status").textContent = error.message;
    }
  }

  uppy.on("restriction-failed", (file, error) => {
    rejectRow(`${file ? file.name : "Datei"}: ${error.message}`);
  });

  uppy.on("upload-progress", (file, progress) => {
    const row = rows.get(file.id);
    if (!row || !progress.bytesTotal) return;
    const percent = Math.floor((progress.bytesUploaded / progress.bytesTotal) * 100);
    row.querySelector("progress").value = percent;
    setStatus(file.id, `${percent} %`);
  });

  uppy.on("upload-success", async (file) => {
    const masterId = uppy.getFile(file.id).meta.masterId;
    try {
      setStatus(file.id, "Prüfsumme wird abgeschlossen …");
      const sha256 = await checksum(file);
      const result = await post(`${base}${masterId}/fertig/`, { sha256 });
      const text = result.reason ? `${result.stateLabel}: ${result.reason}` : result.stateLabel;
      setStatus(file.id, text, result.state);
      rows.get(file.id)?.querySelector(".cancel")?.remove();
      rows.get(file.id)?.querySelector(".pause")?.remove();
    } catch (error) {
      setStatus(file.id, error.message, "error");
    } finally {
      document.dispatchEvent(new Event("schwarmstack:finished"));
    }
  });

  uppy.on("upload-error", (file, error) => {
    setStatus(file.id, error.message, "error");
    const row = rows.get(file.id);
    if (row) row.querySelector(".cancel")?.remove();
    if (row) row.querySelector(".pause")?.remove();
  });

  let finishing = 0;
  uppy.on("upload-success", () => {
    finishing += 1;
  });
  document.addEventListener("schwarmstack:finished", () => {
    finishing -= 1;
    maybeReload();
  });
  let uploadsDone = null;
  uppy.on("complete", (result) => {
    uploadsDone = result;
    maybeReload();
  });
  function maybeReload() {
    // Erst neu laden, wenn alle Fertig-Meldungen durch sind. Kurz stehen lassen, damit
    // Ablehnungsgründe lesbar sind; die Liste zeigt sie danach auch.
    const done = uploadsDone;
    if (uploadStarted && done && finishing === 0 && done.failed.length === 0 && done.successful.length > 0) {
      window.setTimeout(() => window.location.reload(), 1500);
    }
  }

  input.addEventListener("change", () => {
    for (const file of input.files) {
      try {
        uppy.addFile({ name: file.name, type: file.type, data: file, source: "Local" });
      } catch {
        // Ablehnung wird über "restriction-failed" angezeigt.
      }
    }
    input.value = "";
  });

  button.addEventListener("click", () => {
    button.disabled = true;
    input.disabled = true;
    for (const row of rows.values()) {
      row.querySelector("select").disabled = true;
      row.querySelector(".pause").hidden = false;
    }
    uploadStarted = true;
    for (const file of uppy.getFiles()) checksum(file);
    uppy.upload();
  });
})();
