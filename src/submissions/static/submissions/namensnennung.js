// Den Namen gibt es nur mit dem Häkchen zur Namensnennung (Ticket #33). Ohne Häkchen ist
// das Feld gesperrt und wird nicht mitgeschickt; der Server verwirft einen Namen ohnehin.
(() => {
  const consent = document.querySelector("[name=consent_publish_credit]");
  const name = document.querySelector("[name=credit_name]");
  if (!consent || !name) return;
  const couple = () => {
    name.disabled = !consent.checked;
  };
  consent.addEventListener("change", couple);
  couple();
})();
