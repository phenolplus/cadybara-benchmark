import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import {
  bindCollapsibleQueryText,
  finalizeCollapsibleQueryTexts,
  formatCollapsibleQueryText,
  prepareQueryTextToggle,
} from "./query-text.js";

const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.dataset.bsTheme = savedTheme;

const pathParts = window.location.pathname.split("/").filter(Boolean);
const [experimentId, legacyRunId] = pathParts.slice(1);
const searchParams = new URLSearchParams(window.location.search);
const selectedRunIds = searchParams.getAll("run");
const compactRunIds = searchParams.get("runs");
const runIds = [
  ...selectedRunIds,
  ...(compactRunIds ? compactRunIds.split(",") : []),
  ...(legacyRunId ? [legacyRunId] : []),
].filter(Boolean);

const compareMeta = document.querySelector("#compareMeta");
const compareGrid = document.querySelector("#compareGrid");
const compareStatus = document.querySelector("#compareStatus");
const backLink = document.querySelector("#backLink");

const backgroundColor = savedTheme === "dark" ? 0x15181c : 0xf8f9fb;
const runPalette = [
  { light: 0x356aa6, dark: 0x6ea8fe, swatch: "#356aa6" },
  { light: 0x287a5e, dark: 0x62d6a7, swatch: "#287a5e" },
  { light: 0xb25c2a, dark: 0xffa45c, swatch: "#b25c2a" },
  { light: 0x7a5bb6, dark: 0xc7a6ff, swatch: "#7a5bb6" },
  { light: 0xb44f6f, dark: 0xff8fb1, swatch: "#b44f6f" },
  { light: 0x6f6a22, dark: 0xd9cf54, swatch: "#6f6a22" },
];

if (!experimentId || !runIds.length) {
  showStatus("Missing experiment or run selection in the URL.", true);
} else {
  backLink.href = `/experiment/${encodeURIComponent(experimentId)}`;
  initCompare();
}

async function initCompare() {
  try {
    const uniqueRunIds = Array.from(new Set(runIds));
    const [experiment, ...runs] = await Promise.all([
      fetchJson(`/api/experiments/${encodeURIComponent(experimentId)}`),
      ...uniqueRunIds.map((runId) => fetchJson(`/api/experiments/${encodeURIComponent(experimentId)}/runs/${encodeURIComponent(runId)}`)),
    ]);
    const compareItems = buildCompareItems(runs, experiment);
    compareMeta.textContent = `${experimentId} · ${runs.length} run${runs.length === 1 ? "" : "s"} · ${compareItems.length} quer${compareItems.length === 1 ? "y" : "ies"}`;

    if (!compareItems.length) {
      showStatus("The selected runs have no queries to compare.", true);
      return;
    }

    compareGrid.replaceChildren();
    const blocks = compareItems.map((item) => {
      const { element, host } = createBlockShell(item);
      prepareQueryTextToggle(element.querySelector(".query-text-toggle"), item.query.text);
      compareGrid.append(element);
      return { element, item, host };
    });
    const viewports = await Promise.all(blocks.map(({ item, host }) => createViewport(item, host)));
    blocks.forEach((block, index) => {
      block.viewport = viewports[index];
      block.viewport.block = block.element;
    });
    setupViewportResize(viewports);
    setupSyncedControls(viewports);
    setupBlockInteractions(blocks, compareGrid);
    bindCollapsibleQueryText(compareGrid);
    finalizeCollapsibleQueryTexts(compareGrid);
    autoMinimizeInProgressBlocks(blocks, compareGrid);
    fitAllCameras(viewports);
    animate(viewports);
    showStatus("Drag a block handle to reorder. Drag a model viewport to rotate all models together.");
  } catch (error) {
    showStatus(error.message, true);
  }
}

function createBlockShell(item) {
  const { query, run, color } = item;
  const queryId = query.query_id || query.id || "";
  const blockId = `${run.id || ""}:${queryId}`;
  const titleText = `${run.id || ""} · ${queryId}`;

  const block = document.createElement("article");
  block.className = "compare-block";
  block.dataset.blockId = blockId;
  block.style.setProperty("--run-color", color.swatch);

  const header = document.createElement("header");
  header.className = "compare-block-header";

  const dragHandle = document.createElement("button");
  dragHandle.type = "button";
  dragHandle.className = "compare-block-drag";
  dragHandle.draggable = true;
  dragHandle.setAttribute("aria-label", "Drag to reorder");
  dragHandle.innerHTML = '<span class="compare-block-drag-icon" aria-hidden="true"></span>';

  const title = document.createElement("div");
  title.className = "compare-block-title";
  title.textContent = titleText;

  const minimizeButton = document.createElement("button");
  minimizeButton.type = "button";
  minimizeButton.className = "compare-block-minimize";
  minimizeButton.setAttribute("aria-label", "Minimize block");
  minimizeButton.setAttribute("aria-expanded", "true");
  minimizeButton.innerHTML = '<span class="compare-block-minimize-icon" aria-hidden="true">−</span>';

  header.append(dragHandle, title, minimizeButton);

  const host = document.createElement("div");
  const isEmpty = isDnfQuery(query);
  host.className = `compare-viewport${isEmpty ? " is-empty" : ""}`;

  const stage = document.createElement("div");
  stage.className = "compare-viewport-stage";
  host.append(stage);

  if (isEmpty) {
    const label = document.createElement("div");
    label.className = "compare-viewport-label";
    label.textContent = "DNF";
    host.append(label);
  }

  block.append(
    header,
    host,
    metaFromHtml(`
    <div class="compare-meta">
      <div>
        <div class="label">Run</div>
        <div class="value run-value fw-semibold"><span class="run-swatch" aria-hidden="true"></span>${escapeHtml(run.id || "")}</div>
      </div>
      <div>
        <div class="label">Query</div>
        <div class="value fw-semibold">${escapeHtml(queryId)}</div>
      </div>
      <div>
        <div class="label">Model</div>
        <div class="value">${escapeHtml(query.model || "(default)")}</div>
      </div>
      <div class="compare-meta-field compare-meta-prompt">
        <div class="label">Prompt</div>
        <div class="value compare-prompt-value">${formatCollapsibleQueryText(query.text, escapeHtml)}</div>
      </div>
      ${formatQueryImagesBlock(query.images)}
      ${formatClientLatencyBlock(query)}
      ${formatMetricsBlock(query.metrics)}
      ${query.status === "failed" ? `<div class="error">${escapeHtml(formatError(query.error))}</div>` : ""}
    </div>
  `),
  );
  return { element: block, host: stage };
}

function buildCompareItems(runs, experiment) {
  const experimentQueries = experiment?.queries || [];
  return runs.flatMap((run, runIndex) => {
    const runQueriesById = new Map(
      (run.queries || []).map((query) => [queryId(query), query]),
    );
    const queries = experimentQueries.length
      ? experimentQueries.map((experimentQuery) => {
          const runQuery = runQueriesById.get(experimentQuery.id);
          if (runQuery) return runQuery;
          return {
            query_id: experimentQuery.id,
            text: experimentQuery.text,
            model: experimentQuery.model,
            images: experimentQuery.images || [],
            status: "pending",
            error: {},
            response_metadata: {},
            metrics: {},
          };
        })
      : run.queries || [];
    return queries.map((query) => ({
      query,
      run,
      runIndex,
      color: runColor(runIndex),
    }));
  });
}

function queryId(query) {
  return query.query_id || query.id || "";
}

function isInProgressQuery(query) {
  return query.status === "pending" || query.status === "running";
}

function isDnfQuery(query) {
  return query.status !== "completed";
}

async function createViewport(item, host) {
  const { query, run, color } = item;
  const queryId = query.query_id || query.id || "";
  const isDnf = isDnfQuery(query);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(backgroundColor);

  scene.add(new THREE.AmbientLight(0xffffff, 0.65));
  const keyLight = new THREE.DirectionalLight(0xffffff, 0.85);
  keyLight.position.set(2, 3, 4);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.35);
  fillLight.position.set(-3, -1, -2);
  scene.add(fillLight);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  camera.up.set(0, 0, 1);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  host.replaceChildren(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enabled = !isDnf;

  let mesh = null;
  let maxDim = 0.001;

  if (query.status === "completed" && query.has_stl) {
    const geometry = await loadStl(
      `/api/experiments/${encodeURIComponent(experimentId)}/runs/${encodeURIComponent(run.id)}/queries/${encodeURIComponent(queryId)}/stl`,
    );
    geometry.computeVertexNormals();
    geometry.center();
    geometry.computeBoundingBox();
    const size = new THREE.Vector3();
    geometry.boundingBox.getSize(size);
    maxDim = Math.max(size.x, size.y, size.z, 0.001);

    const material = new THREE.MeshStandardMaterial({
      color: savedTheme === "dark" ? color.dark : color.light,
      metalness: 0.12,
      roughness: 0.58,
    });
    mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);
  }

  return { scene, camera, renderer, controls, mesh, maxDim, host, block: null, isDnf };
}

function setupBlockInteractions(blocks, grid) {
  blocks.forEach(({ element }) => {
    setupDragReorder(element, grid);
    setupMinimize(element, grid);
  });
}

function autoMinimizeInProgressBlocks(blocks, grid) {
  blocks.forEach(({ element, item }) => {
    if (isInProgressQuery(item.query)) {
      setBlockExpanded(element, grid, false);
    }
  });
}

function setupDragReorder(block, grid) {
  const handle = block.querySelector(".compare-block-drag");
  if (!handle) return;

  let draggedBlock = null;

  handle.addEventListener("dragstart", (event) => {
    draggedBlock = block;
    block.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", block.dataset.blockId || "");
  });

  handle.addEventListener("dragend", () => {
    block.classList.remove("is-dragging");
    grid.querySelectorAll(".compare-block.is-drop-target").forEach((node) => {
      node.classList.remove("is-drop-target");
    });
    draggedBlock = null;
  });

  grid.addEventListener("dragover", (event) => {
    if (!draggedBlock) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";

    grid.querySelectorAll(".compare-block.is-drop-target").forEach((node) => {
      node.classList.remove("is-drop-target");
    });

    const target = getDropTargetBlock(event.clientX, event.clientY, draggedBlock);
    if (target) {
      target.classList.add("is-drop-target");
      insertBlockRelativeToTarget(draggedBlock, target, event.clientY);
    }
  });

  grid.addEventListener("drop", (event) => {
    event.preventDefault();
    if (!draggedBlock) return;

    const target = getDropTargetBlock(event.clientX, event.clientY, draggedBlock);
    if (target) {
      insertBlockRelativeToTarget(draggedBlock, target, event.clientY);
    } else if (draggedBlock.classList.contains("is-minimized")) {
      getOrCreateMinimizedStack(grid).appendChild(draggedBlock);
    } else {
      const stack = grid.querySelector(".compare-minimized-stack");
      if (stack) {
        stack.before(draggedBlock);
      } else {
        grid.appendChild(draggedBlock);
      }
    }

    grid.querySelectorAll(".compare-block.is-drop-target").forEach((node) => {
      node.classList.remove("is-drop-target");
    });
  });
}

function getDropTargetBlock(clientX, clientY, draggedBlock) {
  const element = document.elementFromPoint(clientX, clientY);
  const stack = element?.closest(".compare-minimized-stack");
  const block = element?.closest(".compare-block");
  const draggedMinimized = draggedBlock.classList.contains("is-minimized");

  if (block && block !== draggedBlock && compareGrid.contains(block)) {
    const targetMinimized = block.classList.contains("is-minimized");
    if (draggedMinimized === targetMinimized) {
      return block;
    }
  }

  if (draggedMinimized && stack && compareGrid.contains(stack)) {
    return stack.lastElementChild && stack.lastElementChild !== draggedBlock
      ? stack.lastElementChild
      : null;
  }

  return null;
}

function insertBlockRelativeToTarget(draggedBlock, targetBlock, clientY) {
  const rect = targetBlock.getBoundingClientRect();
  const midpoint = rect.top + rect.height / 2;
  const pointerBelowMidpoint = clientY >= midpoint;

  if (pointerBelowMidpoint) {
    if (targetBlock.nextElementSibling !== draggedBlock) {
      targetBlock.after(draggedBlock);
    }
  } else if (targetBlock.previousElementSibling !== draggedBlock) {
    targetBlock.before(draggedBlock);
  }
}

function setupMinimize(block, grid) {
  const minimizeButton = block.querySelector(".compare-block-minimize");
  const title = block.querySelector(".compare-block-title");
  if (!minimizeButton) return;

  minimizeButton.addEventListener("click", () => {
    setBlockExpanded(block, grid, block.classList.contains("is-minimized"));
  });

  title?.addEventListener("click", () => {
    if (!block.classList.contains("is-minimized")) return;
    setBlockExpanded(block, grid, true);
  });
}

function setBlockExpanded(block, grid, expanded) {
  const minimizeButton = block.querySelector(".compare-block-minimize");
  const icon = minimizeButton?.querySelector(".compare-block-minimize-icon");
  block.classList.toggle("is-minimized", !expanded);
  if (minimizeButton) {
    minimizeButton.setAttribute("aria-expanded", String(expanded));
    minimizeButton.setAttribute("aria-label", expanded ? "Minimize block" : "Expand block");
  }
  if (icon) {
    icon.textContent = expanded ? "−" : "+";
  }
  if (expanded) {
    restoreExpandedBlock(block, grid);
  } else {
    getOrCreateMinimizedStack(grid).appendChild(block);
  }
}

function getOrCreateMinimizedStack(grid) {
  let stack = grid.querySelector(".compare-minimized-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "compare-minimized-stack";
    stack.setAttribute("aria-label", "Minimized blocks");
    grid.appendChild(stack);
  }
  return stack;
}

function restoreExpandedBlock(block, grid) {
  const stack = grid.querySelector(".compare-minimized-stack");
  if (stack) {
    stack.before(block);
    removeMinimizedStackIfEmpty(grid);
  } else {
    grid.appendChild(block);
  }
}

function removeMinimizedStackIfEmpty(grid) {
  const stack = grid.querySelector(".compare-minimized-stack");
  if (stack && !stack.children.length) {
    stack.remove();
  }
}

function runColor(index) {
  return runPalette[index % runPalette.length];
}

function resizeViewport(viewport) {
  const width = viewport.host.clientWidth;
  const height = viewport.host.clientHeight;
  if (!width || !height) return;
  viewport.renderer.setSize(width, height, false);
  viewport.camera.aspect = width / height;
  viewport.camera.updateProjectionMatrix();
}

function setupViewportResize(viewports) {
  viewports.forEach(resizeViewport);
  const resizeObserver = new ResizeObserver(() => {
    viewports.forEach(resizeViewport);
  });
  viewports.forEach((viewport) => resizeObserver.observe(viewport.host));
}

function setupSyncedControls(viewports) {
  let syncing = false;

  viewports.forEach((viewport) => {
    if (viewport.isDnf) return;
    viewport.controls.addEventListener("change", () => {
      if (syncing) return;
      syncing = true;
      syncCameras(viewports, viewport);
      syncing = false;
    });
  });
}

function syncCameras(viewports, source) {
  viewports.forEach((viewport) => {
    if (viewport === source) return;
    viewport.camera.position.copy(source.camera.position);
    viewport.camera.quaternion.copy(source.camera.quaternion);
    viewport.controls.target.copy(source.controls.target);
    viewport.controls.update();
  });
}

function isViewportMinimized(viewport) {
  return Boolean(viewport.block?.classList.contains("is-minimized"));
}

function fitAllCameras(viewports) {
  const maxDim = Math.max(...viewports.map((viewport) => viewport.maxDim), 0.001);
  const fitOffset = 1.35;
  const fovRadians = (45 * Math.PI) / 180;
  const fitHeightDistance = maxDim / (2 * Math.tan(fovRadians / 2));
  const fitWidthDistance = fitHeightDistance;
  const distance = fitOffset * Math.max(fitHeightDistance, fitWidthDistance);
  const direction = new THREE.Vector3(1, -0.85, 0.45).normalize();
  const center = new THREE.Vector3(0, 0, 0);

  viewports.forEach((viewport) => {
    viewport.camera.aspect = viewport.host.clientWidth / Math.max(viewport.host.clientHeight, 1);
    viewport.camera.position.copy(center).add(direction.clone().multiplyScalar(distance));
    viewport.camera.near = distance / 200;
    viewport.camera.far = distance * 200;
    viewport.camera.updateProjectionMatrix();
    viewport.controls.target.copy(center);
    viewport.controls.update();
  });
}

function animate(viewports) {
  function frame() {
    requestAnimationFrame(frame);
    viewports.forEach((viewport) => {
      if (isViewportMinimized(viewport)) return;
      viewport.controls.update();
      viewport.renderer.render(viewport.scene, viewport.camera);
    });
  }
  frame();
}

function loadStl(url) {
  return new Promise((resolve, reject) => {
    new STLLoader().load(url, resolve, undefined, () => reject(new Error("Failed to load STL file.")));
  });
}

function metaFromHtml(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText || "Request failed.");
  }
  return response.json();
}

function formatError(error) {
  if (typeof error === "string") return error;
  if (error && typeof error.message === "string") return error.message;
  return JSON.stringify(error);
}

function formatQueryImagesBlock(images) {
  if (!images?.length) return "";
  return `
    <div>
      <div class="label">Reference image</div>
      <div class="value compare-query-images">
        ${images.map((image) => `
          <img class="query-image-thumb" src="${escapeAttr(image.url)}" alt="Reference image" loading="lazy">
        `).join("")}
      </div>
    </div>
  `;
}

function formatClientLatencyBlock(query) {
  const latencyMs = getClientLatencyMs(query);
  if (latencyMs === null) return "";
  return `
    <div>
      <div class="label">Client latency</div>
      <div class="value">${escapeHtml(formatClientLatency(latencyMs))}</div>
    </div>
  `;
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
  return `${latencyMs} ms`;
}

function formatMetricsBlock(metrics) {
  if (!metrics || typeof metrics !== "object" || !Object.keys(metrics).length) return "";
  return `
    <div>
      <div class="label">Metrics</div>
      <dl class="metrics-list">
        ${Object.entries(metrics).map(([key, value]) => `
          <div>
            <dt>${escapeHtml(formatMetricLabel(key))}</dt>
            <dd>${escapeHtml(formatMetricValue(value))}</dd>
          </div>
        `).join("")}
      </dl>
    </div>
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

function showStatus(message, isError = false) {
  compareStatus.textContent = message;
  compareStatus.classList.toggle("text-danger", isError);
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
