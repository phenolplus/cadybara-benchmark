const app = document.querySelector("#app");
const alerts = document.querySelector("#alerts");
const themeSwitch = document.querySelector("#themeSwitch");

const state = {
  experiments: [],
  current: null,
  published: [],
};

const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.dataset.bsTheme = savedTheme;
themeSwitch.checked = savedTheme === "dark";

themeSwitch.addEventListener("change", () => {
  const theme = themeSwitch.checked ? "dark" : "light";
  document.documentElement.dataset.bsTheme = theme;
  localStorage.setItem("theme", theme);
});

document.addEventListener("click", (event) => {
  const modalTrigger = event.target.closest("[data-bs-toggle='modal']");
  if (modalTrigger) {
    const target = document.querySelector(modalTrigger.dataset.bsTarget);
    if (target && !window.bootstrap) {
      event.preventDefault();
      showModal(target);
      return;
    }
  }

  const dismiss = event.target.closest("[data-bs-dismiss='modal']");
  if (dismiss && !window.bootstrap) {
    event.preventDefault();
    hideModal(dismiss.closest(".modal"));
    return;
  }

  const link = event.target.closest("[data-link]");
  if (!link) return;
  event.preventDefault();
  navigate(link.getAttribute("href"));
});

window.addEventListener("popstate", route);

function navigate(path) {
  history.pushState({}, "", path);
  route();
}

async function route() {
  resetModalState();
  const path = window.location.pathname;
  if (path === "/" || path === "/experiments") {
    await renderExperiments();
    return;
  }
  if (path.startsWith("/experiment/")) {
    await renderExperiment(path.split("/").pop());
    return;
  }
  if (path === "/published") {
    await renderPublished();
    return;
  }
  navigate("/experiments");
}

async function renderExperiments() {
  state.experiments = await api("/api/experiments");
  app.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="h3 mb-1">Experiments</h1>
        <p class="text-body-secondary mb-0">Organize query datasets, runs, results, and publication status.</p>
      </div>
      <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#experimentModal">New experiment</button>
    </div>
    <section class="panel overflow-hidden">
      ${state.experiments.length ? experimentsTable(state.experiments) : `<div class="empty-state">No experiments yet.</div>`}
    </section>
    ${experimentModal()}
  `;
  bindExperimentForm();
}

async function renderExperiment(id) {
  state.current = await api(`/api/experiments/${id}`);
  const experiment = state.current;
  app.innerHTML = `
    <div class="page-header">
      <div>
        <div class="text-body-secondary small mb-1">${escapeHtml(experiment.id)} · ${escapeHtml(experiment.type || "")}</div>
        <h1 class="h3 mb-1">${escapeHtml(experiment.name)}</h1>
        <p class="text-body-secondary mb-0">${escapeHtml(experiment.description || "No description")}</p>
      </div>
      <div class="toolbar">
        <button class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#queryModal">Add query</button>
        <button class="btn btn-outline-primary" id="publishExperiment">Publish completed</button>
        <button class="btn btn-primary" id="runExperiment">Run experiment</button>
      </div>
    </div>
    <div class="metric-grid mb-3">
      ${metric("Status", experiment.status || "draft")}
      ${metric("Queries", experiment.queries.length)}
      ${metric("Runs", experiment.runs.length)}
      ${metric("Results", experiment.results.length)}
    </div>
    <div class="row g-3">
      <div class="col-xl-7">
        <section class="panel overflow-hidden">
          <div class="p-3 border-bottom"><h2 class="h5 mb-0">Queries</h2></div>
          ${experiment.queries.length ? queriesTable(experiment.queries) : `<div class="empty-state m-3">No queries configured.</div>`}
        </section>
      </div>
      <div class="col-xl-5">
        <section class="panel">
          <div class="p-3 border-bottom"><h2 class="h5 mb-0">Setup</h2></div>
          <div class="p-3"><pre class="code-box mb-0">${escapeHtml(JSON.stringify(experiment.setup || {}, null, 2))}</pre></div>
        </section>
      </div>
      <div class="col-12">
        ${experiment.runs.length ? `
          <div class="run-compare-toolbar">
            <button class="btn btn-outline-primary" id="compareSelectedRuns" disabled>Compare runs</button>
          </div>
        ` : ""}
        <section class="panel overflow-hidden">
          <div class="p-3 border-bottom"><h2 class="h5 mb-0">Runs</h2></div>
          ${experiment.runs.length ? runsTable(experiment.runs, experiment.id) : `<div class="empty-state m-3">No runs recorded.</div>`}
        </section>
      </div>
    </div>
    ${queryModal(experiment.id)}
  `;
  bindExperimentActions(experiment.id);
  bindQueryForm(experiment.id);
  bindRunsTable();
}

async function renderPublished() {
  state.published = await api("/api/published");
  app.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="h3 mb-1">Published Runs</h1>
        <p class="text-body-secondary mb-0">Stable JSON exports under published/runs.</p>
      </div>
    </div>
    <section class="panel overflow-hidden">
      ${state.published.length ? publishedTable(state.published) : `<div class="empty-state">No published runs yet.</div>`}
    </section>
  `;
}

function experimentsTable(experiments) {
  return `
    <div class="table-responsive">
      <table class="table table-hover align-middle">
        <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Queries</th><th>Runs</th><th>Updated</th></tr></thead>
        <tbody>
          ${experiments.map((experiment) => `
            <tr role="button" onclick="navigate('/experiment/${escapeAttr(experiment.id)}')">
              <td class="fw-semibold">${escapeHtml(experiment.id)}</td>
              <td>${escapeHtml(experiment.name)}</td>
              <td>${statusBadge(experiment.status)}</td>
              <td>${experiment.query_count}</td>
              <td>${experiment.run_count}</td>
              <td class="text-body-secondary small">${escapeHtml(experiment.updated_at || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function queriesTable(queries) {
  return `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>ID</th><th>Sublabel</th><th>Model</th><th>Category</th><th>Text</th></tr></thead>
        <tbody>
          ${queries.map((query) => `
            <tr>
              <td class="fw-semibold">${escapeHtml(query.id)}</td>
              <td>${escapeHtml(query.sublabel || "")}</td>
              <td class="small">${escapeHtml(query.model || "(default)")}</td>
              <td>${escapeHtml(query.category || "")}</td>
              <td class="query-text">${escapeHtml(query.text || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function runsTable(runs, experimentId) {
  return `
    <div class="table-responsive">
      <table class="table runs-table">
        <thead><tr><th></th><th class="run-select-cell">Select</th><th>ID</th><th>Status</th><th>Queries</th><th>Avg score</th><th>Avg client latency</th><th>Started</th><th></th></tr></thead>
        <tbody>
          ${runs.map((run) => runRows(run, experimentId)).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function runRows(run, experimentId) {
  const queries = run.queries || [];
  const runId = run.id;
  return `
    <tr class="run-row" data-run-id="${escapeAttr(runId)}" role="button" tabindex="0" aria-expanded="false" aria-controls="run-detail-${escapeAttr(runId)}">
      <td class="run-toggle-cell"><span class="run-toggle" aria-hidden="true">▸</span></td>
      <td class="run-select-cell">
        <input class="form-check-input run-select" type="checkbox" value="${escapeAttr(runId)}" aria-label="Select run ${escapeAttr(runId)}">
      </td>
      <td class="fw-semibold">${escapeHtml(runId)}</td>
      <td>${statusBadge(run.status)}</td>
      <td>${run.completed_count ?? 0}/${run.query_count ?? 0}</td>
      <td>${run.average_score !== null && run.average_score !== undefined ? run.average_score : ""}</td>
      <td class="text-body-secondary small">${formatClientLatency(run.average_client_latency_ms)}</td>
      <td class="text-body-secondary small">${escapeHtml(run.started_at || "")}</td>
      <td class="text-nowrap">
        <a class="btn btn-sm btn-outline-secondary" href="/compare/${escapeAttr(experimentId)}/${escapeAttr(runId)}">Compare</a>
        <button class="btn btn-sm btn-outline-primary" onclick="publishRun('${escapeAttr(runId)}')">Publish</button>
      </td>
    </tr>
    <tr class="run-detail-row d-none" id="run-detail-${escapeAttr(runId)}" data-run-id="${escapeAttr(runId)}">
      <td colspan="9">
        ${queries.length ? runQueriesTable(queries, experimentId, runId) : `<div class="text-body-secondary small py-2">No query results.</div>`}
      </td>
    </tr>
  `;
}

function runQueriesTable(queries, experimentId, runId) {
  return `
    <table class="table table-sm mb-0 run-queries-table">
      <thead><tr><th>Query</th><th>Sublabel</th><th>Model</th><th>Status</th><th>Score</th><th>Client latency</th><th>Metrics</th><th>Text</th><th></th></tr></thead>
      <tbody>
        ${queries.map((query) => {
          const queryId = query.query_id || query.id || "";
          const viewUrl = `/view/${encodeURIComponent(experimentId)}/${encodeURIComponent(runId)}/${encodeURIComponent(queryId)}`;
          return `
          <tr>
            <td class="fw-semibold">${escapeHtml(queryId)}</td>
            <td>${escapeHtml(query.sublabel || "")}</td>
            <td class="small">${escapeHtml(query.model || "")}</td>
            <td>${statusBadge(query.status)}</td>
            <td>${query.score !== null && query.score !== undefined ? query.score : ""}</td>
            <td class="text-body-secondary small">${formatClientLatency(getClientLatencyMs(query))}</td>
            <td class="metrics-cell">${formatMetrics(query.metrics)}</td>
            <td class="query-text">
              ${escapeHtml(query.text || "")}
              ${query.status === "failed" && query.error ? `<div class="text-danger small mt-1">${escapeHtml(formatError(query.error))}</div>` : ""}
            </td>
            <td class="text-nowrap">
              ${query.status === "completed" ? `<a class="btn btn-sm btn-outline-secondary" href="${escapeAttr(viewUrl)}">View</a>` : ""}
            </td>
          </tr>
        `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function bindRunsTable() {
  const table = document.querySelector(".runs-table");
  if (!table) return;
  const compareButton = document.querySelector("#compareSelectedRuns");

  table.addEventListener("click", (event) => {
    if (event.target.closest("button, a, input")) return;
    const row = event.target.closest(".run-row");
    if (!row) return;
    toggleRunRow(row.dataset.runId);
  });

  table.addEventListener("change", (event) => {
    if (!event.target.matches(".run-select")) return;
    updateCompareRunsButton();
  });

  table.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (event.target.closest("button, a, input")) return;
    const row = event.target.closest(".run-row");
    if (!row) return;
    event.preventDefault();
    toggleRunRow(row.dataset.runId);
  });

  compareButton?.addEventListener("click", () => {
    const selectedRunIds = selectedRunIdsForCompare();
    if (!selectedRunIds.length) return;

    const params = new URLSearchParams();
    selectedRunIds.forEach((runId) => params.append("run", runId));
    window.location.href = `/compare/${encodeURIComponent(state.current.id)}?${params.toString()}`;
  });

  updateCompareRunsButton();
}

function selectedRunIdsForCompare() {
  return Array.from(document.querySelectorAll(".run-select:checked")).map((input) => input.value);
}

function updateCompareRunsButton() {
  const compareButton = document.querySelector("#compareSelectedRuns");
  if (!compareButton) return;

  const count = selectedRunIdsForCompare().length;
  compareButton.disabled = count === 0;
  compareButton.textContent = count ? `Compare ${count} run${count === 1 ? "" : "s"}` : "Compare runs";
}

function toggleRunRow(runId) {
  const row = document.querySelector(`.run-row[data-run-id="${runId}"]`);
  const detail = document.querySelector(`.run-detail-row[data-run-id="${runId}"]`);
  if (!row || !detail) return;

  const expanded = row.getAttribute("aria-expanded") === "true";
  row.setAttribute("aria-expanded", expanded ? "false" : "true");
  row.classList.toggle("expanded", !expanded);
  detail.classList.toggle("d-none", expanded);
}

function publishedTable(items) {
  return `
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Run</th><th>Experiment</th><th>Queries</th><th>Published</th><th>File</th></tr></thead>
        <tbody>
          ${items.map((item) => `
            <tr>
              <td class="fw-semibold">${escapeHtml(item.run_id || "")}</td>
              <td>${escapeHtml(item.experiment || item.experiment_id || "")}</td>
              <td>${Array.isArray(item.queries) ? item.queries.length : 0}</td>
              <td class="text-body-secondary small">${escapeHtml(item.published_at || "")}</td>
              <td class="small">${escapeHtml(item.file_path || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function experimentModal() {
  return `
    <div class="modal fade" id="experimentModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog">
        <form class="modal-content" id="experimentForm">
          <div class="modal-header">
            <h2 class="modal-title h5">New experiment</h2>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <label class="form-label">Name</label>
            <input class="form-control mb-3" name="name" required>
            <label class="form-label">Description</label>
            <textarea class="form-control mb-3" name="description" rows="3"></textarea>
            <label class="form-label">Type</label>
            <input class="form-control" name="type" value="query_comparison">
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

function queryModal(experimentId) {
  return `
    <div class="modal fade" id="queryModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-lg">
        <form class="modal-content" id="queryForm">
          <div class="modal-header">
            <h2 class="modal-title h5">Add query to ${escapeHtml(experimentId)}</h2>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-md-6">
                <label class="form-label">Sublabel</label>
                <input class="form-control" name="sublabel">
              </div>
              <div class="col-md-6">
                <label class="form-label">Category</label>
                <input class="form-control" name="category">
              </div>
              <div class="col-12">
                <label class="form-label">Model</label>
                <input class="form-control" name="model" placeholder="Leave blank for experiment default">
              </div>
              <div class="col-12">
                <label class="form-label">Query text</label>
                <textarea class="form-control" name="text" rows="5" required></textarea>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary">Add query</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

function bindExperimentForm() {
  document.querySelector("#experimentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    const experiment = await api("/api/experiments", {
      method: "POST",
      body: JSON.stringify(data),
    });
    showAlert(`Created ${experiment.id}.`, "success");
    navigate(`/experiment/${experiment.id}`);
  });
}

function bindQueryForm(experimentId) {
  document.querySelector("#queryForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    await api(`/api/experiments/${experimentId}/queries`, {
      method: "POST",
      body: JSON.stringify(blankToNull(data)),
    });
    showAlert("Query added.", "success");
    await renderExperiment(experimentId);
  });
}

function bindExperimentActions(experimentId) {
  document.querySelector("#runExperiment").addEventListener("click", async () => {
    if (!confirm("Run this experiment against the Cadybara API now?")) return;
    const result = await api(`/api/experiments/${experimentId}/run`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    showAlert(`Run finished: ${result.completed} completed, ${result.failed} failed.`, "success");
    await renderExperiment(experimentId);
  });
  document.querySelector("#publishExperiment").addEventListener("click", async () => {
    const result = await api(`/api/experiments/${experimentId}/publish`, { method: "POST" });
    showAlert(`Published ${result.count} run(s).`, "success");
    await renderExperiment(experimentId);
  });
}

async function publishRun(runId) {
  const experimentId = state.current.id;
  const result = await api(`/api/experiments/${experimentId}/publish?run_id=${encodeURIComponent(runId)}`, {
    method: "POST",
  });
  showAlert(`Published ${result.count} run(s).`, "success");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload.detail || response.statusText;
    showAlert(message, "danger");
    throw new Error(message);
  }
  return response.json();
}

function metric(label, value) {
  return `<div class="metric"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(String(value))}</div></div>`;
}

function statusBadge(status) {
  const colors = {
    draft: "secondary",
    running: "primary",
    completed: "success",
    completed_with_errors: "warning",
    failed: "danger",
  };
  return `<span class="badge text-bg-${colors[status] || "secondary"}">${escapeHtml(status || "")}</span>`;
}

function blankToNull(data) {
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value === "" ? null : value]));
}

function formatError(error) {
  if (typeof error === "string") return error;
  if (error && typeof error.message === "string") return error.message;
  return JSON.stringify(error);
}

function getClientLatencyMs(query) {
  if (typeof query.client_latency_ms === "number") return query.client_latency_ms;
  const meta = query.response_metadata;
  if (meta && typeof meta.latency_ms === "number") return meta.latency_ms;
  const error = query.error;
  if (error && typeof error.latency_ms === "number") return error.latency_ms;
  return null;
}

function formatClientLatency(latencyMs) {
  if (latencyMs === null || latencyMs === undefined) return "—";
  return `${latencyMs} ms`;
}

function formatMetrics(metrics) {
  if (!metrics || typeof metrics !== "object" || !Object.keys(metrics).length) return "";
  return `
    <dl class="metrics-list">
      ${Object.entries(metrics).map(([key, value]) => `
        <div>
          <dt>${escapeHtml(formatMetricLabel(key))}</dt>
          <dd>${escapeHtml(formatMetricValue(value))}</dd>
        </div>
      `).join("")}
    </dl>
  `;
}

function formatMetricLabel(key) {
  return String(key).replaceAll("_", " ");
}

function formatMetricValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function showAlert(message, type = "info") {
  const alert = document.createElement("div");
  alert.className = `alert alert-${type} alert-dismissible shadow-sm`;
  alert.innerHTML = `
    ${escapeHtml(message)}
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;
  alerts.append(alert);
  setTimeout(() => {
    if (window.bootstrap) {
      bootstrap.Alert.getOrCreateInstance(alert).close();
    } else {
      alert.remove();
    }
  }, 5000);
}

function showModal(modal) {
  modal.classList.add("show");
  modal.style.display = "block";
  modal.removeAttribute("aria-hidden");
  modal.setAttribute("aria-modal", "true");
  document.body.classList.add("modal-open");
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop fade show";
  backdrop.dataset.localBackdrop = "true";
  document.body.append(backdrop);
}

function hideModal(modal) {
  if (!modal) return;
  modal.classList.remove("show");
  modal.style.display = "none";
  modal.setAttribute("aria-hidden", "true");
  modal.removeAttribute("aria-modal");
  document.body.classList.remove("modal-open");
  document.querySelectorAll("[data-local-backdrop='true']").forEach((backdrop) => backdrop.remove());
}

function resetModalState() {
  document.querySelectorAll(".modal.show").forEach((modal) => {
    if (window.bootstrap) {
      bootstrap.Modal.getInstance(modal)?.dispose();
    }
    modal.classList.remove("show");
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
    modal.removeAttribute("aria-modal");
  });
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => backdrop.remove());
  document.body.classList.remove("modal-open");
  document.body.style.removeProperty("overflow");
  document.body.style.removeProperty("padding-right");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

route().catch((error) => showAlert(error.message, "danger"));
