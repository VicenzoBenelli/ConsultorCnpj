import { ApiError, requestJson } from "./api.js";

const form = document.getElementById("job-form");
const textarea = document.getElementById("cnpjs");
const lineCount = document.getElementById("cnpj-line-count");
const submitButton = document.getElementById("create-job-button");
const feedback = document.getElementById("form-feedback");
const submitButtonLabel = submitButton.textContent;
let isSubmitting = false;

function setFeedback(message) {
  feedback.textContent = message;
  feedback.className = "alert is-error";
  feedback.hidden = false;
}

function clearFeedback() {
  feedback.textContent = "";
  feedback.className = "alert";
  feedback.hidden = true;
}

function updateLineCount() {
  const count = textarea.value.split(/\r?\n/).filter((line) => line.trim()).length;
  lineCount.textContent = `${count} ${count === 1 ? "linha não vazia" : "linhas não vazias"}`;
}

function batchErrorMessage(item) {
  const labels = {
    EMPTY_BATCH: "Informe ao menos um CNPJ.",
    INVALID_FORMAT: "Use 14 dígitos ou a máscara completa do CNPJ.",
    INVALID_CHECK_DIGITS: "Os dígitos verificadores do CNPJ são inválidos.",
    MAX_CNPJS_EXCEEDED: "A quantidade de CNPJs excede o limite permitido.",
  };
  const base = labels[item.code] || item.message || "A lista de CNPJs é inválida.";
  const location = item.position ? ` Posição ${item.position}.` : "";
  const value = item.value ? ` Valor informado: ${item.value}.` : "";
  return `${base}${location}${value}`;
}

function errorMessage(error) {
  if (!(error instanceof ApiError)) {
    return "Ocorreu um erro inesperado. Tente novamente.";
  }
  if (error.status !== 422) {
    return error.kind === "network" ? error.message : "Não foi possível criar a consulta. Tente novamente.";
  }
  const details = error.payload?.detail;
  if (!details || !Array.isArray(details.errors)) {
    return "Informe uma lista de CNPJs válida.";
  }
  return details.errors.map(batchErrorMessage).join(" ");
}

textarea.addEventListener("input", updateLineCount);
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSubmitting) return;

  isSubmitting = true;
  submitButton.disabled = true;
  submitButton.classList.add("is-loading");
  submitButton.setAttribute("aria-busy", "true");
  submitButton.textContent = "Criando consulta...";
  clearFeedback();
  try {
    const response = await requestJson("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cnpjs: textarea.value }),
    });
    if (response.status === 201 && response.data.id) {
      window.location.assign(`/jobs/${encodeURIComponent(response.data.id)}`);
      return;
    }
    throw new ApiError("invalid-response", "A aplicação retornou uma resposta inválida.");
  } catch (error) {
    setFeedback(errorMessage(error));
    isSubmitting = false;
    submitButton.disabled = false;
    submitButton.classList.remove("is-loading");
    submitButton.removeAttribute("aria-busy");
    submitButton.textContent = submitButtonLabel;
  }
});

updateLineCount();
