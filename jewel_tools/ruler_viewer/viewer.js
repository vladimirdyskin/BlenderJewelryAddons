// Pretty Ruler Web viewer: scene, loading, polling, UI. Dimensions are drawn by overlay2d.js.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { DimensionOverlay } from './overlay2d.js';

const VIEWER_VERSION = 2; // keep in sync with the first-line comment of index.html
const POLL_MS = 3000;
const MAX_BACKOFF_MS = 30000;

const $ = (id) => document.getElementById(id);
const stage = $('stage');
const glCanvas = $('gl');
const overlayCanvas = $('overlay');

// ---------- Scene ----------
const renderer = new THREE.WebGLRenderer({ canvas: glCanvas, antialias: true });
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
pmrem.dispose();

const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(5, 10, 7);
scene.add(sun);

const perspCam = new THREE.PerspectiveCamera(40, 1, 0.1, 1e5);
const orthoCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1e5);
let orthoHalfH = 10; // ortho frustum half-height at zoom = 1 (mm)
let camera = perspCam;
camera.position.set(20, 15, 25);

const controls = new OrbitControls(camera, glCanvas);
controls.enableDamping = true;
controls.zoomToCursor = true;
controls.addEventListener('change', markDirty);

const overlay = new DimensionOverlay(overlayCanvas);
const loader = new GLTFLoader();

const state = {
  root: null,
  dims: null,
  sceneHash: null,
  dimensionsHash: null,
  first: true,
  overrides: new Map(), // id -> enabled, user changes in the checkbox list
  dimsVisible: true,
};

let dirty = true;
function markDirty() { dirty = true; }

const _v = new THREE.Vector3();
// Project a world point [x, y, z] to CSS pixels (y down); null if behind the camera or outside the depth range.
function project(p) {
  _v.set(p[0], p[1], p[2]).applyMatrix4(camera.matrixWorldInverse);
  if (camera.isPerspectiveCamera && _v.z >= 0) return null;
  _v.applyMatrix4(camera.projectionMatrix);
  if (_v.z > 1 || _v.z < -1) return null;
  return { x: (_v.x + 1) / 2 * stage.clientWidth, y: (1 - _v.y) / 2 * stage.clientHeight };
}

function updateOrthoFrustum() {
  const aspect = stage.clientWidth / Math.max(1, stage.clientHeight);
  orthoCam.left = -orthoHalfH * aspect;
  orthoCam.right = orthoHalfH * aspect;
  orthoCam.top = orthoHalfH;
  orthoCam.bottom = -orthoHalfH;
  orthoCam.updateProjectionMatrix();
}

function resize() {
  const w = stage.clientWidth, h = stage.clientHeight, dpr = window.devicePixelRatio || 1;
  renderer.setPixelRatio(dpr);
  renderer.setSize(w, h, false);
  perspCam.aspect = w / Math.max(1, h);
  perspCam.updateProjectionMatrix();
  updateOrthoFrustum();
  overlay.resize(w, h, dpr);
  markDirty();
}
window.addEventListener('resize', resize);
resize();

function loop() {
  requestAnimationFrame(loop);
  controls.update();
  if (!dirty) return;
  dirty = false;
  renderer.render(scene, camera);
  overlay.render(project);
}
loop();

// ---------- Camera helpers ----------
function modelSphere() {
  if (!state.root) return null;
  return new THREE.Box3().setFromObject(state.root).getBoundingSphere(new THREE.Sphere());
}

function fit() {
  const s = modelSphere();
  if (!s || s.radius === 0) return;
  const r = s.radius * 1.1;
  const dir = camera.position.clone().sub(controls.target).normalize();
  if (dir.lengthSq() === 0) dir.set(0.6, 0.5, 0.7).normalize();
  const aspect = stage.clientWidth / Math.max(1, stage.clientHeight);
  controls.target.copy(s.center);
  if (camera.isPerspectiveCamera) {
    const fovV = THREE.MathUtils.degToRad(perspCam.fov);
    const fovH = 2 * Math.atan(Math.tan(fovV / 2) * aspect);
    const dist = r / Math.sin(Math.min(fovV, fovH) / 2);
    camera.position.copy(s.center).addScaledVector(dir, dist);
  } else {
    orthoHalfH = r * Math.max(1, 1 / aspect);
    orthoCam.zoom = 1;
    updateOrthoFrustum();
    camera.position.copy(s.center).addScaledVector(dir, r * 4);
  }
  controls.update();
  markDirty();
}

function applyView(v) {
  const cam = v.perspective ? perspCam : orthoCam;
  cam.up.fromArray(v.up || [0, 1, 0]);
  cam.position.fromArray(v.position);
  controls.target.fromArray(v.target);
  // Blender fits fovDeg / orthoScale to the larger viewport side; three.js uses the vertical one.
  const aspect = stage.clientWidth / Math.max(1, stage.clientHeight);
  const toVertical = aspect >= 1 ? 1 / aspect : 1;
  if (v.perspective) {
    if (typeof v.fovDeg === 'number') {
      const half = Math.tan(THREE.MathUtils.degToRad(v.fovDeg) / 2) * toVertical;
      perspCam.fov = THREE.MathUtils.radToDeg(2 * Math.atan(half));
      perspCam.updateProjectionMatrix();
    }
  } else {
    if (typeof v.orthoScale === 'number') orthoHalfH = v.orthoScale / 2 * toVertical;
    orthoCam.zoom = 1;
    updateOrthoFrustum();
  }
  setCamera(cam);
}

function setCamera(cam) {
  camera = cam;
  controls.object = cam;
  controls.update();
  $('btn-proj').textContent = cam.isPerspectiveCamera ? 'Persp' : 'Ortho';
  markDirty();
}

// Switch projection keeping the orbit target and the apparent size of the model.
function toggleProjection() {
  const from = camera;
  const to = from.isPerspectiveCamera ? orthoCam : perspCam;
  const dir = from.position.clone().sub(controls.target);
  const dist = dir.length();
  dir.normalize();
  to.up.copy(from.up);
  const halfFov = THREE.MathUtils.degToRad(perspCam.fov) / 2;
  if (to.isPerspectiveCamera) {
    const h = orthoHalfH / from.zoom;
    to.position.copy(controls.target).addScaledVector(dir, h / Math.tan(halfFov));
  } else {
    orthoHalfH = dist * Math.tan(halfFov);
    to.zoom = 1;
    updateOrthoFrustum();
    to.position.copy(from.position);
  }
  setCamera(to);
}

// ---------- Loading ----------
async function fetchJson(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

function forceOpaque(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      m.transparent = false;
      m.opacity = 1;
      m.depthWrite = true;
      if ('transmission' in m) m.transmission = 0;
      // Glossy BSDF exports without PBR data -> glTF defaults (metallic 1, roughness 1) look matte; make it metal.
      if (m.isMeshStandardMaterial && !m.roughnessMap && m.metalness >= 0.99 && m.roughness >= 0.99) m.roughness = 0.25;
      m.needsUpdate = true;
    }
  });
}

function disposeTree(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.geometry.dispose();
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      for (const v of Object.values(m)) if (v && v.isTexture) v.dispose();
      m.dispose();
    }
  });
}

async function loadScene(hash) {
  const gltf = await loader.loadAsync(`scene.glb?v=${encodeURIComponent(hash)}`);
  forceOpaque(gltf.scene);
  if (state.root) { scene.remove(state.root); disposeTree(state.root); }
  state.root = gltf.scene;
  scene.add(state.root);
  state.sceneHash = hash;
  markDirty();
}

async function loadDimensions(hash) {
  const data = await fetchJson(`dimensions.json?v=${encodeURIComponent(hash)}`);
  if (data.version !== 1) toast(`dimensions.json version ${data.version} (expected 1)`, 4000);
  state.dims = data;
  state.dimensionsHash = hash;
  overlay.setData(data);
  for (const [id, on] of state.overrides) overlay.setEnabled(id, on);
  buildDimList();
  $('btn-home').disabled = !data.view;
  markDirty();
}

async function applyManifest(m) {
  if (typeof m.viewerVersion === 'number' && m.viewerVersion > VIEWER_VERSION) $('reload').hidden = false;
  const tasks = [];
  if (m.sceneHash !== state.sceneHash) tasks.push(loadScene(m.sceneHash));
  if (m.dimensionsHash !== state.dimensionsHash) tasks.push(loadDimensions(m.dimensionsHash));
  if (!tasks.length) return;
  const results = await Promise.allSettled(tasks);
  const wasFirst = state.first;
  if (state.first && state.root) {
    state.first = false;
    if (state.dims && state.dims.view) applyView(state.dims.view); else fit();
  }
  const failed = results.find((r) => r.status === 'rejected');
  if (failed) throw failed.reason;
  const t = timeNow();
  $('updated').textContent = `Updated ${t}`;
  if (!wasFirst) toast(`Updated ${t}`);
}

// ---------- Polling ----------
let pollTimer = null;
let backoff = POLL_MS;

async function poll() {
  pollTimer = null;
  try {
    await applyManifest(await fetchJson('manifest.json'));
    backoff = POLL_MS;
    setOnline(true);
  } catch (e) {
    console.warn('[viewer] update failed:', e);
    backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    setOnline(false);
  }
  schedulePoll(backoff);
}

function schedulePoll(ms) {
  clearTimeout(pollTimer);
  pollTimer = document.hidden ? null : setTimeout(poll, ms);
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) { clearTimeout(pollTimer); pollTimer = null; }
  else schedulePoll(0);
});

function setOnline(on) {
  $('dot').classList.toggle('online', on);
  $('dot').title = on ? 'Live' : 'Offline';
}

// ---------- UI ----------
function timeNow() {
  return new Date().toLocaleTimeString('en-GB', { hour12: false });
}

let toastTimer = null;
function toast(msg, ms = 2000) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), ms);
}

function buildDimList() {
  const list = $('dims');
  list.textContent = '';
  for (const d of state.dims.dimensions || []) {
    const on = state.overrides.has(d.id) ? state.overrides.get(d.id) : !!d.enabled;
    const label = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = on;
    cb.addEventListener('change', () => {
      state.overrides.set(d.id, cb.checked);
      overlay.setEnabled(d.id, cb.checked);
      markDirty();
    });
    const text = document.createElement('span');
    const name = d.label ?? `#${d.id}`;
    text.textContent = d.type === 'angle' ? `∠ ${name}` : name;
    if (d.linked) {
      const c = state.dims.style?.linkColor || [1, 0.6, 0.1, 1];
      text.style.color = `rgba(${c.slice(0, 3).map((v) => Math.round(v * 255)).join(',')},${c[3] ?? 1})`;
      text.title = 'Linked';
    }
    const type = document.createElement('span');
    type.className = 'type';
    type.textContent = d.type;
    label.append(cb, text, type);
    list.append(label);
  }
  if (!list.children.length) list.textContent = 'No dimensions';
}

function toggleDims() {
  state.dimsVisible = !state.dimsVisible;
  overlay.setVisible(state.dimsVisible);
  $('btn-dims').classList.toggle('active', state.dimsVisible);
  markDirty();
}

function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  scene.background = new THREE.Color(dark ? 0x1b1b1b : 0xf2f2f2);
  $('btn-theme').textContent = dark ? 'Light' : 'Dark';
  markDirty();
}

$('project').textContent = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop() || '') || 'Pretty Ruler';
$('btn-fit').addEventListener('click', fit);
$('btn-home').addEventListener('click', () => state.dims?.view && applyView(state.dims.view));
$('btn-dims').addEventListener('click', toggleDims);
$('btn-proj').addEventListener('click', toggleProjection);
$('btn-theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme !== 'dark'));
$('btn-panel').addEventListener('click', () => { $('panel').hidden = !$('panel').hidden; });
$('btn-reload').addEventListener('click', () => location.reload());

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.metaKey || e.ctrlKey || e.altKey) return;
  switch (e.key.toLowerCase()) {
    case 'f': fit(); break;
    case 'h': if (state.dims?.view) applyView(state.dims.view); break;
    case 'd': toggleDims(); break;
    case 'o': toggleProjection(); break;
  }
});

setTheme(false);
poll();
