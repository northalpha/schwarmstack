// Belichtungsangaben je Master (Ticket #50): Die Formulare im aufklappbaren Bereich speichern
// über die JSON-API, der Server schickt den Bereich neu gerendert zurück. Gerechnet wird nur auf
// dem Server. Ohne JavaScript schicken die Formulare normal ab.
(() => {
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    const details = form.closest("details.exposure");
    if (!details) return;
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const csrf = data.csrfmiddlewaretoken;
    delete data.csrfmiddlewaretoken;
    const error = details.querySelector(".error");
    const buttons = form.querySelectorAll("button");
    for (const button of buttons) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(data),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || `Fehler ${response.status}`);
      details.outerHTML = body.html;
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
      for (const button of buttons) button.disabled = false;
    }
  });
})();
