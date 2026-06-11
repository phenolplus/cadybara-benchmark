const app = document.querySelector("#app");
const alerts = document.querySelector("#alerts");
const themeSwitch = document.querySelector("#themeSwitch");

const state = {
  experiments: [],
  current: null,
  published: [],
  pendingRunId: null,
};

const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.dataset.bsTheme = savedTheme;
if (themeSwitch) {
  themeSwitch.checked = savedTheme === "dark";
}

themeSwitch?.addEventListener("change", () => {
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
  renderExperimentPage(experiment);
}

function renderExperimentPage(experiment, options = {}) {
  const expandedRunIds = options.expandedRunIds ?? getExpandedRunIds();
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
        <label class="d-flex align-items-center gap-2 mb-0 small text-body-secondary" for="runConcurrency">
          <span>Concurrency</span>
          <input class="form-control form-control-sm" id="runConcurrency" type="number" min="1" step="1" value="1" style="width: 5rem;">
        </label>
        <button class="btn btn-primary" id="runExperiment">Run experiment</button>
      </div>
    </div>
    <div class="metric-grid mb-3">
      ${metric("Status", experiment.status || "draft")}
      ${metric("Queries", experiment.queries.length)}
      ${metric("Runs", experiment.runs.length)}
      ${metric("Results", experiment.results.length)}
    </div>
    ${experiment.runs.length ? `
      <div class="run-compare-toolbar">
        <button class="btn btn-outline-primary" id="compareSelectedRuns" disabled>Compare runs</button>
      </div>
    ` : ""}
    <section class="panel runs-panel mb-3">
      <div class="p-3 border-bottom"><h2 class="h5 mb-0">Runs</h2></div>
      ${experiment.runs.length ? runsTable(experiment.runs, experiment.id) : `<div class="empty-state m-3">No runs recorded.</div>`}
    </section>
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
    </div>
    ${queryModal(experiment.id)}
  `;
  bindExperimentActions(experiment.id);
  bindQueryForm(experiment.id);
  bindRunsTable();
  restoreExpandedRunIds(expandedRunIds);
}

function getExpandedRunIds() {
  return Array.from(document.querySelectorAll('.run-row[aria-expanded="true"]')).map((row) => row.dataset.runId);
}

function restoreExpandedRunIds(runIds) {
  runIds.forEach((runId) => {
    const row = document.querySelector(`.run-row[data-run-id="${runId}"]`);
    const detail = document.querySelector(`.run-detail-row[data-run-id="${runId}"]`);
    if (!row || !detail) return;
    row.setAttribute("aria-expanded", "true");
    row.classList.add("expanded");
    detail.classList.remove("d-none");
  });
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
        <thead><tr><th>ID</th><th>Model</th><th>Category</th><th>Image</th><th>Text</th></tr></thead>
        <tbody>
          ${queries.map((query) => `
            <tr>
              <td class="fw-semibold">${escapeHtml(query.id)}</td>
              <td class="small">${escapeHtml(query.model || "(default)")}</td>
              <td>${escapeHtml(query.category || "")}</td>
              <td>${formatQueryImages(query.images)}</td>
              <td class="query-text">${escapeHtml(query.text || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function shouldShowResume(run) {
  if (run.status !== "stopped") return false;
  if (run.can_resume === true) return true;
  return (run.queries || []).some((query) =>
    query.status === "cancelled" || query.status === "pending" || query.status === "running",
  );
}

function shouldShowRetry(run) {
  if (run.status !== "completed_with_errors") return false;
  if (run.can_retry === true) return true;
  return (run.queries || []).some((query) => query.status === "failed");
}

function runActionButton(label, action, runId, className) {
  return `<button type="button" class="btn btn-sm ${className}" data-run-action="${escapeAttr(action)}" data-run-id="${escapeAttr(runId)}">${escapeHtml(label)}</button>`;
}

function runsTable(runs, experimentId) {
  return `
    <div class="table-responsive runs-table-wrap">
      <table class="table runs-table">
        <thead><tr><th></th><th class="run-select-cell">Select</th><th>ID</th><th>Status</th><th>Queries</th><th>Time</th><th>Started</th><th class="run-actions-col">Actions</th></tr></thead>
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
      <td class="text-body-secondary small">${formatRunTime(run)}</td>
      <td class="text-body-secondary small">${escapeHtml(run.started_at || "")}</td>
      <td class="run-actions-cell">
        <div class="run-actions">
          ${run.status === "running" ? runActionButton("Stop", "stop", runId, "btn-outline-danger") : ""}
          ${shouldShowRetry(run) ? runActionButton("Retry", "retry", runId, "btn-outline-warning") : ""}
          ${shouldShowResume(run) ? runActionButton("Resume", "resume", runId, "btn-outline-success") : ""}
          <a class="btn btn-sm btn-outline-secondary" href="/compare/${escapeAttr(experimentId)}/${escapeAttr(runId)}">Compare</a>
          ${runActionButton("Publish", "publish", runId, "btn-outline-primary")}
        </div>
      </td>
    </tr>
    <tr class="run-detail-row d-none" id="run-detail-${escapeAttr(runId)}" data-run-id="${escapeAttr(runId)}">
      <td colspan="8">
        ${shouldShowResume(run) ? `
          <div class="run-detail-toolbar">
            ${runActionButton("Resume cancelled queries", "resume", runId, "btn-outline-success")}
          </div>
        ` : ""}
        ${queries.length ? runQueriesTable(queries, experimentId, runId) : `<div class="text-body-secondary small py-2">No query results.</div>`}
      </td>
    </tr>
  `;
}

function runQueriesTable(queries, experimentId, runId) {
  return `
    <table class="table table-sm mb-0 run-queries-table">
      <thead><tr><th>Query</th><th>Model</th><th>Status</th><th>Metrics</th><th>Text</th><th></th></tr></thead>
      <tbody>
        ${queries.map((query) => {
          const queryId = query.query_id || query.id || "";
          const viewUrl = `/view/${encodeURIComponent(experimentId)}/${encodeURIComponent(runId)}/${encodeURIComponent(queryId)}`;
          return `
          <tr>
            <td class="fw-semibold">${escapeHtml(queryId)}</td>
            <td class="small">${escapeHtml(query.model || "")}</td>
            <td>${statusBadge(query.status)}</td>
            <td class="metrics-cell query-metrics-cell">${formatQueryMetrics(query)}</td>
            <td class="query-text">
              ${formatQueryImages(query.images)}
              ${query.images?.length ? `<div class="mt-2">${escapeHtml(query.text || "")}</div>` : escapeHtml(query.text || "")}
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
    const action = event.target.closest("[data-run-action]");
    if (action) {
      event.stopPropagation();
      const runId = action.dataset.runId;
      if (action.dataset.runAction === "stop") stopRun(runId);
      if (action.dataset.runAction === "retry") retryRun(runId);
      if (action.dataset.runAction === "resume") resumeRun(runId);
      if (action.dataset.runAction === "publish") publishRun(runId);
      return;
    }
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

async function toggleRunRow(runId) {
  const row = document.querySelector(`.run-row[data-run-id="${runId}"]`);
  const detail = document.querySelector(`.run-detail-row[data-run-id="${runId}"]`);
  if (!row || !detail) return;

  const expanded = row.getAttribute("aria-expanded") === "true";
  if (expanded) {
    row.setAttribute("aria-expanded", "false");
    row.classList.remove("expanded");
    detail.classList.add("d-none");
    return;
  }

  if (state.current?.id) {
    const experimentId = state.current.id;
    const expandedRunIds = getExpandedRunIds();
    if (!expandedRunIds.includes(runId)) {
      expandedRunIds.push(runId);
    }
    row.setAttribute("aria-busy", "true");
    row.classList.add("run-row-loading");
    try {
      state.current = await api(`/api/experiments/${experimentId}`);
      renderExperimentPage(state.current, { expandedRunIds });
    } catch (error) {
      row.removeAttribute("aria-busy");
      row.classList.remove("run-row-loading");
      if (error.message) showAlert(error.message, "danger");
    }
    return;
  }

  row.setAttribute("aria-expanded", "true");
  row.classList.add("expanded");
  detail.classList.remove("d-none");
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
              <div class="col-12">
                <label class="form-label">Category</label>
                <input class="form-control" name="category">
              </div>
              <div class="col-12">
                <label class="form-label">Model</label>
                <input class="form-control" name="model" placeholder="Leave blank for experiment default">
              </div>
              <div class="col-12">
                <label class="form-label">Reference image</label>
                <input class="form-control" type="file" name="image" accept="image/jpeg,image/png,image/webp,image/gif">
                <div class="form-text">Optional. Provide an image prompt, query text, or both.</div>
              </div>
              <div class="col-12">
                <label class="form-label">Query text</label>
                <textarea class="form-control" name="text" rows="5"></textarea>
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
    const formData = new FormData(event.target);
    const payload = blankToNull({
      text: formData.get("text") || "",
      model: formData.get("model"),
      category: formData.get("category"),
    });
    const imageFile = formData.get("image");
    if (imageFile && imageFile.size > 0) {
      payload.images = [await readImagePayload(imageFile)];
    }
    if (!String(payload.text || "").trim() && !payload.images?.length) {
      showAlert("Add query text, a reference image, or both.", "danger");
      return;
    }
    await api(`/api/experiments/${experimentId}/queries`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showAlert("Query added.", "success");
    await renderExperiment(experimentId);
  });
}

function parseRunConcurrency() {
  const input = document.querySelector("#runConcurrency");
  const value = Number.parseInt(input?.value ?? "1", 10);
  if (!Number.isFinite(value) || value < 1) {
    showAlert("Concurrency must be a whole number of at least 1.", "danger");
    return null;
  }
  return value;
}

function bindExperimentActions(experimentId) {
  document.querySelector("#runExperiment").addEventListener("click", async () => {
    const concurrency = parseRunConcurrency();
    if (concurrency === null) return;
    if (!confirm(`Run this experiment against the Cadybara API with concurrency ${concurrency}?`)) return;

    addOptimisticRun(experimentId);
    showAlert("Run started.", "info");

    try {
      await runExperimentWithProgress(experimentId, concurrency);
    } catch (error) {
      state.pendingRunId = null;
      if (error.message) showAlert(error.message, "danger");
      await renderExperiment(experimentId);
    }
  });
  document.querySelector("#publishExperiment").addEventListener("click", async () => {
    const result = await api(`/api/experiments/${experimentId}/publish`, { method: "POST" });
    showAlert(`Published ${result.count} run(s).`, "success");
    await renderExperiment(experimentId);
  });
}

function addOptimisticRun(experimentId) {
  if (!state.current || state.current.id !== experimentId) return;

  const runId = nextOptimisticRunId(state.current.runs || []);
  state.pendingRunId = runId;
  const startedAt = new Date().toISOString();
  const setup = state.current.setup || {};
  const defaultModel = setup.model || "default";
  const queries = (state.current.queries || []).map((query) => ({
    query_id: query.id,
    text: query.text,
    model: query.model || defaultModel,
    images: query.images || [],
    status: "pending",
    error: {},
    artifact_dir: "",
    response_metadata: {},
    score: null,
    metrics: {},
  }));

  state.current = {
    ...state.current,
    status: "running",
    runs: [
      ...(state.current.runs || []),
      {
        id: runId,
        experiment_id: experimentId,
        status: "running",
        started_at: startedAt,
        finished_at: "",
        parameters: {},
        queries,
        query_count: queries.length,
        completed_count: 0,
        failed_count: 0,
        total_client_latency_ms: null,
        eta_ms: null,
        summary: { completed: 0, failed: 0 },
      },
    ],
  };

  renderExperimentPage(state.current);
}

function nextOptimisticRunId(runs) {
  const highest = runs.reduce((max, run) => {
    const match = /^RUN(\d+)$/.exec(run.id || "");
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  return `RUN${String(highest + 1).padStart(3, "0")}`;
}

async function runExperimentWithProgress(experimentId, concurrency) {
  const response = await fetch(`/api/experiments/${experimentId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ concurrency }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseSseChunk(chunk);
      if (!event) continue;
      if (event.event === "finished") {
        result = event.payload;
        if (result?.stopped) {
          showAlert(`Run ${result.run_id} stopped.`, "info");
        }
        continue;
      }
      if (event.event === "error") {
        throw new Error(event.payload.message || "Run failed.");
      }
      await handleRunProgressEvent(experimentId, event);
    }
  }

  if (!result) {
    throw new Error("Run finished without a summary.");
  }
  state.pendingRunId = null;
  await renderExperiment(experimentId);
  if (!result.stopped) {
    showAlert(`Run finished: ${result.completed} completed, ${result.failed} failed.`, "success");
  }
  return result;
}

function parseSseChunk(chunk) {
  const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
  if (!dataLine) return null;
  return JSON.parse(dataLine.slice(6));
}

async function handleRunProgressEvent(experimentId, event) {
  if (!state.current || state.current.id !== experimentId) return;

  const { event: name, payload } = event;
  if (name === "run_started") {
    reconcileOptimisticRunId(payload.run_id);
    state.current.status = "running";
    renderExperimentPage(state.current);
    return;
  }

  const runId = payload.run_id;
  if (name === "started") {
    updateQueryStatus(runId, payload.query_id, "running");
    renderExperimentPage(state.current);
    return;
  }

  if (name === "completed" || name === "failed") {
    await refreshRunInState(experimentId, runId);
    renderExperimentPage(state.current);
  }
}

function reconcileOptimisticRunId(runId) {
  if (!state.pendingRunId) {
    state.pendingRunId = runId;
    return;
  }
  if (state.pendingRunId === runId) return;
  const run = state.current?.runs?.find((item) => item.id === state.pendingRunId);
  if (run) run.id = runId;
  state.pendingRunId = runId;
}

function updateQueryStatus(runId, queryId, status) {
  const run = state.current?.runs?.find((item) => item.id === runId);
  if (!run) return;
  const query = (run.queries || []).find((item) => (item.query_id || item.id) === queryId);
  if (!query) return;
  query.status = status;
  Object.assign(run, enrichRun(run));
}

async function refreshRunInState(experimentId, runId) {
  const run = await api(`/api/experiments/${experimentId}/runs/${runId}`);
  const runs = state.current?.runs || [];
  const index = runs.findIndex((item) => item.id === runId);
  const enriched = enrichRun(run);
  if (index >= 0) {
    runs[index] = enriched;
  } else {
    runs.push(enriched);
  }
  state.current.runs = runs;
  const completed = runs.filter((item) => item.status === "completed" || item.status === "completed_with_errors").length;
  const running = runs.some((item) => item.status === "running");
  const stopped = runs.some((item) => item.status === "stopped");
  if (running) {
    state.current.status = "running";
  } else if (stopped) {
    state.current.status = "stopped";
  } else if (completed === runs.length && runs.length > 0) {
    state.current.status = runs.every((item) => item.status === "completed") ? "completed" : "completed_with_errors";
  }
}

function enrichRun(run) {
  const queries = run.queries || [];
  const completedCount = queries.filter((query) => query.status === "completed").length;
  const failedCount = queries.filter((query) => query.status === "failed").length;
  return {
    ...run,
    query_count: queries.length,
    completed_count: completedCount,
    failed_count: failedCount,
    total_client_latency_ms: getRunTotalTimeMs(run),
    eta_ms: run.status === "running" ? getRunEtaMs(run) : null,
  };
}

function markRunAsRunning(runId) {
  if (!state.current) return;
  const run = state.current.runs?.find((item) => item.id === runId);
  if (!run) return;
  run.status = "running";
  run.finished_at = "";
  run.can_retry = false;
  run.can_resume = false;
  for (const query of run.queries || []) {
    if (query.status === "failed") {
      query.status = "pending";
      query.error = {};
    }
  }
  Object.assign(run, enrichRun(run));
  state.current.status = "running";
  state.pendingRunId = runId;
  renderExperimentPage(state.current);
}

async function stopRun(runId) {
  const experimentId = state.current.id;
  if (!confirm(`Stop run ${runId}?`)) return;
  await api(`/api/experiments/${experimentId}/runs/${encodeURIComponent(runId)}/stop`, {
    method: "POST",
  });
  state.pendingRunId = null;
  showAlert(`Run ${runId} stopped.`, "info");
  await renderExperiment(experimentId);
}

async function retryRun(runId) {
  const experimentId = state.current.id;
  const concurrency = parseRunConcurrency();
  if (concurrency === null) return;
  if (!confirm(`Retry failed queries in run ${runId} with concurrency ${concurrency}?`)) return;

  markRunAsRunning(runId);
  showAlert(`Run ${runId} retry started.`, "info");

  try {
    await retryRunWithProgress(experimentId, runId, concurrency);
  } catch (error) {
    state.pendingRunId = null;
    if (error.message) showAlert(error.message, "danger");
    await renderExperiment(experimentId);
  }
}

async function retryRunWithProgress(experimentId, runId, concurrency) {
  const response = await fetch(
    `/api/experiments/${experimentId}/runs/${encodeURIComponent(runId)}/retry`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ concurrency }),
    },
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseSseChunk(chunk);
      if (!event) continue;
      if (event.event === "finished") {
        result = event.payload;
        if (result?.stopped) {
          showAlert(`Run ${result.run_id} stopped.`, "info");
        }
        continue;
      }
      if (event.event === "error") {
        throw new Error(event.payload.message || "Retry failed.");
      }
      await handleRunProgressEvent(experimentId, event);
    }
  }

  if (!result) {
    throw new Error("Retry finished without a summary.");
  }
  state.pendingRunId = null;
  await renderExperiment(experimentId);
  if (!result.stopped) {
    showAlert(`Run retried: ${result.completed} completed, ${result.failed} failed.`, "success");
  }
  return result;
}

async function resumeRun(runId) {
  const experimentId = state.current.id;
  const concurrency = parseRunConcurrency();
  if (concurrency === null) return;
  if (!confirm(`Resume run ${runId} for cancelled queries with concurrency ${concurrency}?`)) return;

  markRunAsRunning(runId);
  showAlert(`Run ${runId} resumed.`, "info");

  try {
    await resumeRunWithProgress(experimentId, runId, concurrency);
  } catch (error) {
    state.pendingRunId = null;
    if (error.message) showAlert(error.message, "danger");
    await renderExperiment(experimentId);
  }
}

async function resumeRunWithProgress(experimentId, runId, concurrency) {
  const response = await fetch(
    `/api/experiments/${experimentId}/runs/${encodeURIComponent(runId)}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ concurrency }),
    },
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseSseChunk(chunk);
      if (!event) continue;
      if (event.event === "finished") {
        result = event.payload;
        if (result?.stopped) {
          showAlert(`Run ${result.run_id} stopped.`, "info");
        }
        continue;
      }
      if (event.event === "error") {
        throw new Error(event.payload.message || "Resume failed.");
      }
      await handleRunProgressEvent(experimentId, event);
    }
  }

  if (!result) {
    throw new Error("Resume finished without a summary.");
  }
  state.pendingRunId = null;
  await renderExperiment(experimentId);
  if (!result.stopped) {
    showAlert(`Run resumed: ${result.completed} completed, ${result.failed} failed.`, "success");
  }
  return result;
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
    pending: "secondary",
    running: "primary",
    completed: "success",
    completed_with_errors: "warning",
    stopped: "warning",
    cancelled: "secondary",
    failed: "danger",
  };
  return `<span class="badge text-bg-${colors[status] || "secondary"}">${escapeHtml(status || "")}</span>`;
}

function blankToNull(data) {
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value === "" ? null : value]));
}

function formatQueryImages(images) {
  if (!images?.length) {
    return `<span class="text-body-secondary small">—</span>`;
  }
  return `
    <div class="query-images">
      ${images.map((image) => `
        <img class="query-image-thumb" src="${escapeAttr(image.url)}" alt="Reference image" loading="lazy">
      `).join("")}
    </div>
  `;
}

async function readImagePayload(file) {
  const data = await fileToBase64(file);
  return {
    media_type: file.type || inferImageMediaType(file.name),
    data,
  };
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const commaIndex = result.indexOf(",");
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
    };
    reader.onerror = () => reject(reader.error || new Error("Failed to read image file."));
    reader.readAsDataURL(file);
  });
}

function inferImageMediaType(filename) {
  const extension = String(filename || "").split(".").pop()?.toLowerCase();
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  if (extension === "gif") return "image/gif";
  return "image/jpeg";
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
  return formatDurationMs(latencyMs);
}

function isFinishedQuery(query) {
  const status = query.status;
  return status === "completed" || status === "failed" || status === "cancelled";
}

function getRunTotalTimeMs(run) {
  if (run.status === "running") return null;
  const values = (run.queries || []).map(getClientLatencyMs).filter((value) => value !== null);
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0);
}

function getRunEtaMs(run) {
  const queries = run.queries || [];
  const latencies = queries
    .filter(isFinishedQuery)
    .map(getClientLatencyMs)
    .filter((value) => value !== null);
  const remaining = queries.filter(
    (query) => query.status === "pending" || query.status === "running",
  ).length;
  if (!latencies.length || !remaining) return null;
  const average = latencies.reduce((total, value) => total + value, 0) / latencies.length;
  return Math.round(average * remaining);
}

function formatRunTime(run) {
  if (run.status === "running") {
    const eta = run.eta_ms ?? getRunEtaMs(run);
    return eta !== null ? `ETA: ${formatDurationMs(eta)}` : "ETA: —";
  }
  const total = run.total_client_latency_ms ?? getRunTotalTimeMs(run);
  return formatDurationMs(total);
}

function formatDurationMs(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) {
    const seconds = ms / 1000;
    return Number.isInteger(seconds) ? `${seconds} s` : `${seconds.toFixed(1)} s`;
  }
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  if (minutes < 60) {
    return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins ? `${hours}h ${mins}m` : `${hours}h`;
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

function formatQueryMetrics(query) {
  const entries = [
    ["client latency", formatClientLatency(getClientLatencyMs(query))],
    ...Object.entries(query.metrics || {}).map(([key, value]) => [
      formatMetricLabel(key),
      formatMetricValue(value),
    ]),
  ];

  return `
    <dl class="metrics-list">
      ${entries.map(([key, value]) => `
        <div>
          <dt>${escapeHtml(key)}</dt>
          <dd>${escapeHtml(value)}</dd>
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
