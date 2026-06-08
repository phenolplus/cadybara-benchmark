import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

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
    const runs = await Promise.all(
      uniqueRunIds.map((runId) => fetchJson(`/api/experiments/${encodeURIComponent(experimentId)}/runs/${encodeURIComponent(runId)}`)),
    );
    const compareItems = runs.flatMap((run, runIndex) =>
      (run.queries || []).map((query) => ({
        query,
        run,
        runIndex,
        color: runColor(runIndex),
      })),
    );
    compareMeta.textContent = `${experimentId} · ${runs.length} run${runs.length === 1 ? "" : "s"} · ${compareItems.length} quer${compareItems.length === 1 ? "y" : "ies"}`;

    if (!compareItems.length) {
      showStatus("The selected runs have no queries to compare.", true);
      return;
    }

    compareGrid.replaceChildren();
    const blocks = compareItems.map((item) => {
      const { element, host } = createBlockShell(item);
      compareGrid.append(element);
      return { item, host };
    });
    const viewports = await Promise.all(blocks.map(({ item, host }, index) => createViewport(item, host, index)));
    setupViewportResize(viewports);
    setupSyncedControls(viewports);
    fitAllCameras(viewports);
    animate(viewports);
    showStatus("Drag any viewport to rotate all models together.");
  } catch (error) {
    showStatus(error.message, true);
  }
}

function createBlockShell(item) {
  const { query, run, color } = item;
  const queryId = query.query_id || query.id || "";
  const block = document.createElement("article");
  block.className = "compare-block";
  block.style.setProperty("--run-color", color.swatch);
  const host = document.createElement("div");
  const isEmpty = query.status !== "completed";
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
    host,
    metaFromHtml(`
    <div class="compare-meta">
      <div>
        <div class="label">Run</div>
        <div class="value run-value fw-semibold"><span class="run-swatch" aria-hidden="true"></span>${escapeHtml(run.id || "")}</div>
      </div>
      <div>
        <div class="label">Query</div>
        <div class="value fw-semibold">${escapeHtml(queryId)}${query.sublabel ? ` · ${escapeHtml(query.sublabel)}` : ""}</div>
      </div>
      <div>
        <div class="label">Model</div>
        <div class="value">${escapeHtml(query.model || "(default)")}</div>
      </div>
      <div>
        <div class="label">Prompt</div>
        <div class="value">${escapeHtml(query.text || "")}</div>
      </div>
      ${formatClientLatencyBlock(query)}
      ${formatMetricsBlock(query.metrics)}
      ${query.status === "failed" ? `<div class="error">${escapeHtml(formatError(query.error))}</div>` : ""}
    </div>
  `),
  );
  return { element: block, host: stage };
}

async function createViewport(item, host, index) {
  const { query, run, color } = item;
  const queryId = query.query_id || query.id || "";
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

  return { index, scene, camera, renderer, controls, mesh, maxDim, host };
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
    viewport.controls.addEventListener("change", () => {
      if (syncing) return;
      syncing = true;
      syncCameras(viewports, viewport.index);
      syncing = false;
    });
  });
}

function syncCameras(viewports, sourceIndex) {
  const source = viewports[sourceIndex];
  viewports.forEach((viewport) => {
    if (viewport.index === sourceIndex) return;
    viewport.camera.position.copy(source.camera.position);
    viewport.camera.quaternion.copy(source.camera.quaternion);
    viewport.controls.target.copy(source.controls.target);
    viewport.controls.update();
  });
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
