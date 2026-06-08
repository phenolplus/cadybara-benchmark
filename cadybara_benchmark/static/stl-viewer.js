import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.dataset.bsTheme = savedTheme;

const pathParts = window.location.pathname.split("/").filter(Boolean);
const [experimentId, runId, queryId] = pathParts.slice(1);

const meta = document.querySelector("#viewerMeta");
const title = document.querySelector("#viewerTitle");
const text = document.querySelector("#viewerText");
const status = document.querySelector("#viewerStatus");
const backLink = document.querySelector("#backLink");
const canvasHost = document.querySelector("#viewerCanvas");

if (!experimentId || !runId || !queryId) {
  showError("Missing experiment, run, or query id in the URL.");
} else {
  backLink.href = `/experiment/${encodeURIComponent(experimentId)}`;
  initViewer();
}

async function initViewer() {
  try {
    const query = await fetchJson(
      `/api/experiments/${encodeURIComponent(experimentId)}/runs/${encodeURIComponent(runId)}/queries/${encodeURIComponent(queryId)}`,
    );
    meta.textContent = `${experimentId} · ${runId} · ${query.query_id || queryId}`;
    title.textContent = query.sublabel || query.query_id || queryId;
    text.textContent = query.text || "";
    if (!query.has_stl) {
      showError("This query has no STL artifact to display.");
      return;
    }
    await renderStl(
      `/api/experiments/${encodeURIComponent(experimentId)}/runs/${encodeURIComponent(runId)}/queries/${encodeURIComponent(queryId)}/stl`,
    );
    status.textContent = "Drag to rotate · scroll to zoom";
  } catch (error) {
    showError(error.message);
  }
}

async function renderStl(url) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(savedTheme === "dark" ? 0x15181c : 0xf8f9fb);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  camera.up.set(0, 0, 1);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  canvasHost.replaceChildren(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  scene.add(new THREE.AmbientLight(0xffffff, 0.65));
  const keyLight = new THREE.DirectionalLight(0xffffff, 0.85);
  keyLight.position.set(2, 3, 4);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.35);
  fillLight.position.set(-3, -1, -2);
  scene.add(fillLight);

  const geometry = await loadStl(url);
  geometry.computeVertexNormals();
  geometry.center();
  geometry.computeBoundingBox();

  const material = new THREE.MeshStandardMaterial({
    color: savedTheme === "dark" ? 0x6ea8fe : 0x356aa6,
    metalness: 0.12,
    roughness: 0.58,
  });
  const mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);

  const resize = () => {
    const width = canvasHost.clientWidth;
    const height = canvasHost.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };

  resize();
  fitCameraToObject(camera, controls, mesh);

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(canvasHost);

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
}

function loadStl(url) {
  return new Promise((resolve, reject) => {
    new STLLoader().load(url, resolve, undefined, () => reject(new Error("Failed to load STL file.")));
  });
}

function fitCameraToObject(camera, controls, object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 0.001);

  const fitOffset = 1.35;
  const fovRadians = (camera.fov * Math.PI) / 180;
  const fitHeightDistance = maxDim / (2 * Math.tan(fovRadians / 2));
  const fitWidthDistance = fitHeightDistance / Math.max(camera.aspect, 0.001);
  const distance = fitOffset * Math.max(fitHeightDistance, fitWidthDistance);

  const direction = new THREE.Vector3(1, -0.85, 0.45).normalize();
  camera.position.copy(center).add(direction.multiplyScalar(distance));
  camera.near = distance / 200;
  camera.far = distance * 200;
  camera.updateProjectionMatrix();

  controls.target.copy(center);
  controls.update();
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText || "Request failed.");
  }
  return response.json();
}

function showError(message) {
  status.textContent = message;
  status.classList.add("text-danger");
}
