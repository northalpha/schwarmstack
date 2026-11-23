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
  const button = root.querySelector("button");
  const channelTemplate = document.getElementById("channel-template");

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
    restrictions: { allowedFileTypes: [".xisf", ".fits", ".fit", ".fts"] },
    locale: {
      strings: {
        youCanOnlyUploadFileTypes: "Nur XISF- oder FITS-Dateien (%{types}).",
        noDuplicates: "Die Datei „%{fileName}“ ist schon ausgewählt.",
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

  uppy.on("file-added", (file) => {
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
    row.append(name, select, progress, status);
    queue.append(row);
    rows.set(file.id, row);
    updateButton();
  });

  uppy.on("restriction-failed", (file, error) => {
    const row = document.createElement("li");
    row.dataset.state = "error";
    row.textContent = `${file ? file.name : "Datei"}: ${error.message}`;
    queue.append(row);
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
      const result = await post(`${base}${masterId}/fertig/`);
      setStatus(file.id, result.stateLabel, result.state);
    } catch (error) {
      setStatus(file.id, error.message, "error");
    }
  });

  uppy.on("upload-error", (file, error) => {
    setStatus(file.id, error.message, "error");
  });

  uppy.on("complete", (result) => {
    if (result.failed.length === 0) window.setTimeout(() => window.location.reload(), 800);
  });

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
    for (const row of rows.values()) row.querySelector("select").disabled = true;
    uppy.upload();
  });
})();
