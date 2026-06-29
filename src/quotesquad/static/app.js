const sampleButton = document.querySelector("[data-sample]");
const textArea = document.querySelector("#quote_text");
const submitButton = document.querySelector("[data-submit]");

if (sampleButton instanceof HTMLButtonElement && textArea instanceof HTMLTextAreaElement) {
  sampleButton.addEventListener("click", () => {
    textArea.value = [
      "Westside Auto Repair",
      "2026-06-29",
      "ZIP 90210",
      "Front brake rotor replacement labor 3.5 hours $525.00",
      "Front brake rotors pair $340.00",
      "Engine flush service $189.00",
      "Shop supplies fee $64.00",
      "Total $1118.00",
    ].join("\n");
  });
}

if (submitButton instanceof HTMLButtonElement) {
  submitButton.form?.addEventListener("submit", () => {
    submitButton.disabled = true;
    submitButton.textContent = "Auditing";
  });
}
