// Pretty Ruler Web viewer: scene, loading, polling, UI. Dimensions are drawn by overlay2d.js.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { DimensionOverlay } from './overlay2d.js';

const VIEWER_VERSION = 6; // keep in sync with the first-line comment of index.html
const POLL_MS = 3000;
const MAX_BACKOFF_MS = 30000;
const PREFS_KEY = 'prettyRuler.material';
const CAVITY_RADIUS_PX = 1.5; // sample offset in CSS px (scaled by DPR via the buffer size)
const CAVITY_RIDGE = 1.0, CAVITY_VALLEY = 1.0; // Blender workbench curvature factors

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

// ---------- Material prefs (persisted) ----------
const prefs = { clay: true, color: '#7a2e2e', cavityClay: true, cavityBlender: false };
try { Object.assign(prefs, JSON.parse(localStorage.getItem(PREFS_KEY)) || {}); } catch { /* ignore */ }
function savePrefs() { try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch { /* ignore */ } }
function cavityOn() { return prefs.clay ? prefs.cavityClay : prefs.cavityBlender; }

// Shared matte clay material (Blender sculpt-mode look); originals are kept in mesh.userData.originalMaterial.
const clayMat = new THREE.MeshStandardMaterial({ color: prefs.color, roughness: 0.85, metalness: 0, envMapIntensity: 0.6, side: THREE.DoubleSide });

// ---------- Cavity: Blender workbench "Screen" cavity (curvature from neighbouring view-space normals) ----------
// Normals+coverage go to normalRT (alpha 0 = background), then one full-screen pass multiplies the linear color
// buffer by (1 + curvature) and applies tone mapping / sRGB itself, so the background stays exactly as rendered.
const normalMat = new THREE.MeshNormalMaterial({ side: THREE.DoubleSide });
const normalRT = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 }));
const renderPass = new RenderPass(scene, camera);
const cavityPass = new ShaderPass({
  uniforms: {
    tDiffuse: { value: null },
    tNormal: { value: null }, // set below: ShaderPass clones uniforms and drops render-target textures
    texel: { value: new THREE.Vector2() },
    ridge: { value: 0.5 / (CAVITY_RIDGE * CAVITY_RIDGE) },
    valley: { value: 0.7 / (CAVITY_VALLEY * CAVITY_VALLEY) },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse, tNormal;
    uniform vec2 texel;
    uniform float ridge, valley;
    varying vec2 vUv;
    float softClamp(float c, float k) { return c < 0.5 / k ? c * (1.0 - c * k) : 0.25 / k; }
    void main() {
      gl_FragColor = texture2D(tDiffuse, vUv);
      vec4 c = texture2D(tNormal, vUv);
      if (c.a < 0.5) {
        // Background: no cavity and no tone mapping (same as the direct render path).
        #include <colorspace_fragment>
        return;
      }
      vec4 u = texture2D(tNormal, vUv + vec2(0.0, texel.y));
      vec4 d = texture2D(tNormal, vUv - vec2(0.0, texel.y));
      vec4 r = texture2D(tNormal, vUv + vec2(texel.x, 0.0));
      vec4 l = texture2D(tNormal, vUv - vec2(texel.x, 0.0));
      if (min(min(u.a, d.a), min(r.a, l.a)) > 0.5) {
        float diff = 2.0 * ((u.g - d.g) + (r.r - l.r)); // normal divergence: >0 ridge, <0 valley
        float curv = diff < 0.0 ? -2.0 * softClamp(-diff, valley) : 2.0 * softClamp(diff, ridge);
        gl_FragColor.rgb *= 1.0 + curv;
      }
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
});
cavityPass.uniforms.tNormal.value = normalRT.texture;
composer.addPass(renderPass);
composer.addPass(cavityPass);
renderer.setClearColor(0x000000, 0); // used by the normal pass only (scene.background covers the color pass)

function render() {
  if (!cavityOn()) { renderer.render(scene, camera); return; }
  const bg = scene.background;
  scene.background = null;
  scene.overrideMaterial = normalMat;
  renderer.setRenderTarget(normalRT);
  renderer.render(scene, camera);
  renderer.setRenderTarget(null);
  scene.overrideMaterial = null;
  scene.background = bg;
  renderPass.camera = camera;
  composer.render();
}

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
  composer.setPixelRatio(dpr);
  composer.setSize(w, h);
  normalRT.setSize(Math.round(w * dpr), Math.round(h * dpr));
  cavityPass.uniforms.texel.value.set(CAVITY_RADIUS_PX / Math.max(1, w), CAVITY_RADIUS_PX / Math.max(1, h));
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
  render();
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
  // Keep world up: OrbitControls orbits around camera.up, and Blender's turntable
  // view has no roll, so position + target alone reproduce it.
  cam.up.set(0, 1, 0);
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

// Swap every mesh between the shared clay material and its original GLB material(s).
function applyMaterials() {
  if (!state.root) return;
  state.root.traverse((o) => {
    if (!o.isMesh) return;
    if (!o.userData.originalMaterial) o.userData.originalMaterial = o.material;
    o.material = prefs.clay ? clayMat : o.userData.originalMaterial;
  });
  markDirty();
}

function disposeTree(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.geometry.dispose();
    const mat = o.userData.originalMaterial || o.material;
    const mats = Array.isArray(mat) ? mat : [mat];
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
  applyMaterials();
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

// ---------- Material popover ----------
function setClay(on) { prefs.clay = on; savePrefs(); applyMaterials(); updateMatUI(); }
function setColor(hex) { prefs.color = hex; clayMat.color.set(hex); savePrefs(); updateMatUI(); markDirty(); }
function toggleCavity() {
  if (prefs.clay) prefs.cavityClay = !prefs.cavityClay; else prefs.cavityBlender = !prefs.cavityBlender;
  savePrefs();
  updateMatUI();
  markDirty();
}
function updateMatUI() {
  $('btn-mat').classList.toggle('active', !$('matpop').hidden);
  $('btn-clay').classList.toggle('active', prefs.clay);
  $('btn-orig').classList.toggle('active', !prefs.clay);
  for (const b of document.querySelectorAll('.sw')) b.classList.toggle('active', b.dataset.color === prefs.color);
  $('mat-color').value = prefs.color;
  $('cb-cavity').checked = cavityOn();
}
function toggleMatPopover(show = $('matpop').hidden) { $('matpop').hidden = !show; updateMatUI(); }

$('project').textContent = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop() || '') || 'Pretty Ruler';
$('btn-fit').addEventListener('click', fit);
$('btn-home').addEventListener('click', () => state.dims?.view && applyView(state.dims.view));
$('btn-dims').addEventListener('click', toggleDims);
$('btn-proj').addEventListener('click', toggleProjection);
$('btn-theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme !== 'dark'));
$('btn-panel').addEventListener('click', () => { $('panel').hidden = !$('panel').hidden; });
$('btn-reload').addEventListener('click', () => location.reload());
$('btn-mat').addEventListener('click', () => toggleMatPopover());
$('btn-clay').addEventListener('click', () => setClay(true));
$('btn-orig').addEventListener('click', () => setClay(false));
for (const b of document.querySelectorAll('.sw')) b.addEventListener('click', () => setColor(b.dataset.color));
$('mat-color').addEventListener('input', (e) => setColor(e.target.value));
$('cb-cavity').addEventListener('change', toggleCavity);
document.addEventListener('pointerdown', (e) => {
  if (!$('matpop').hidden && !e.target.closest('#matpop, #btn-mat')) toggleMatPopover(false);
});

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.metaKey || e.ctrlKey || e.altKey) return;
  switch (e.key.toLowerCase()) {
    case 'f': fit(); break;
    case 'h': if (state.dims?.view) applyView(state.dims.view); break;
    case 'd': toggleDims(); break;
    case 'o': toggleProjection(); break;
    case 'm': setClay(!prefs.clay); break;
    case 'c': toggleCavity(); break;
  }
});

setTheme(true);
updateMatUI();
poll();
