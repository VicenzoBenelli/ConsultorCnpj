import { ApiError, requestJson } from "./api.js";

const page = document.getElementById("job-page");
const jobId = page?.dataset.jobId;
const statusElement = document.getElementById("job-status");
const progressText = document.getElementById("job-progress-text");
const progressElement = document.getElementById("job-progress");
const statusHint = document.getElementById("job-status-hint");
const successCount = document.getElementById("success-count");
const notFoundCount = document.getElementById("not-found-count");
const failedCount = document.getElementById("failed-count");
const alertElement = document.getElementById("job-alert");
const tableBody = document.getElementById("results-table-body");
const downloadLink = document.getElementById("download-link");

const JOB_LABELS = { PENDING: "Aguardando processamento", RUNNING: "Em processamento", COMPLETED: "Processamento concluído" };
const ITEM_LABELS = { PENDING: "Aguardando", PROCESSING: "Processando", SUCCESS: "Concluído", NOT_FOUND: "Não encontrado", FAILED: "Falhou" };
const POLLING_INTERVAL_MS = 3000;

let timerId = null;
let isRefreshing = false;
let isCompleted = false;
let consecutiveFailures = 0;

function setAlert(message, severity = "warning") {
  alertElement.textContent = message;
  alertElement.className = `alert is-${severity}`;
  alertElement.hidden = false;
}

function clearAlert() {
  alertElement.textContent = "";
  alertElement.className = "alert";
  alertElement.hidden = true;
}

function displayValue(value) {
  return value || "—";
}

function renderStatus(job) {
  statusElement.textContent = JOB_LABELS[job.status] || job.status;
  statusElement.className = `status-badge status-badge--${job.status.toLowerCase()}`;
  const hints = {
    PENDING: "A consulta está aguardando processamento. Esta página será atualizada automaticamente.",
    RUNNING: "A consulta está sendo processada. Esta página será atualizada automaticamente.",
    COMPLETED: "O processamento foi concluído. Revise os resultados e baixe a planilha quando desejar.",
  };
  statusHint.textContent = hints[job.status] || "A página será atualizada automaticamente.";
  const total = Number(job.total) || 0;
  const processed = Math.min(Number(job.processed) || 0, total);
  progressText.textContent = `Processados: ${processed} de ${total}`;
  progressElement.max = total || 1;
  progressElement.value = processed;
  successCount.textContent = String(job.success ?? 0);
  notFoundCount.textContent = String(job.not_found ?? 0);
  failedCount.textContent = String(job.failed ?? 0);

  if (job.status === "COMPLETED") {
    isCompleted = true;
    downloadLink.href = `/api/jobs/${encodeURIComponent(jobId)}/export.xlsx`;
    downloadLink.classList.remove("is-disabled");
    downloadLink.removeAttribute("aria-disabled");
    downloadLink.removeAttribute("tabindex");
    stopPolling();
  }
}

function renderResults(results) {
  tableBody.replaceChildren();
  if (!results.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.className = "empty-state";
    cell.colSpan = 5;
    cell.textContent = "Os resultados aparecerão aqui conforme o processamento avançar.";
    row.append(cell);
    tableBody.append(row);
    return;
  }

  for (const item of results) {
    const row = document.createElement("tr");
    const values = [item.cnpj, ITEM_LABELS[item.status] || item.status, item.razao_social, item.telefone, item.email];
    for (const [index, value] of values.entries()) {
      const cell = document.createElement("td");
      if (index === 1) {
        const badge = document.createElement("span");
        badge.className = `status-badge status-badge--${item.status.toLowerCase()}`;
        badge.textContent = displayValue(value);
        cell.append(badge);
      } else {
        cell.textContent = displayValue(value);
      }
      row.append(cell);
    }
    tableBody.append(row);
  }
}

function stopPolling() {
  if (timerId !== null) {
    window.clearTimeout(timerId);
    timerId = null;
  }
}

function scheduleNext() {
  stopPolling();
  if (!document.hidden && !isCompleted) {
    timerId = window.setTimeout(refresh, POLLING_INTERVAL_MS);
  }
}

async function refresh() {
  if (!jobId || isRefreshing || isCompleted || document.hidden) return;

  isRefreshing = true;
  try {
    const [jobResponse, resultsResponse] = await Promise.all([
      requestJson(`/api/jobs/${encodeURIComponent(jobId)}`),
      requestJson(`/api/jobs/${encodeURIComponent(jobId)}/results`),
    ]);
    consecutiveFailures = 0;
    clearAlert();
    renderStatus(jobResponse.data);
    renderResults(resultsResponse.data.results || []);
    page.classList.remove("is-loading");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      isCompleted = true;
      stopPolling();
      statusElement.textContent = "Job não encontrado";
      setAlert("O Job não foi encontrado.", "error");
      return;
    }
    consecutiveFailures += 1;
    const message = consecutiveFailures >= 3
      ? "Não foi possível atualizar o Job. Continuaremos tentando."
      : "Atualização temporariamente indisponível. Tentaremos novamente.";
    setAlert(message, "warning");
    page.classList.remove("is-loading");
  } finally {
    isRefreshing = false;
    if (!isCompleted) scheduleNext();
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopPolling();
  } else if (!isCompleted) {
    void refresh();
  }
});

void refresh();
