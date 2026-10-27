// KZ shader kit comparison demo. Uses the real runtime patch (web/src/materials.js: fog, probes,
// lightmap path) and then kzShade() on top, lit by a fake baked irradiance lightmap (lantern pools).
import * as THREE from 'three';
import { patchMaterial, makeStubEnvironment, KZ } from '../../../../web/src/materials.js';
import { kzShade, KZS, kzCost } from '../kzshader.js';
import { KZM, KZM_DEMO } from '../kzmaterials.js';

const Q = new URLSearchParams(location.search);
const MODE_NAMES = ['plain tiling (today)', 'anti-tiled texture', 'anti-tiled + macro + detail', 'procedural'];
const MODE_SHORT = ['plain', 'anti-tiled', '+macro+detail', 'procedural'];
const WALLS = ['basalt_wet', 'basalt_dry', 'obsidian', 'rimstone', 'ash_clay', 'lava', 'glacier_ice', 'iron', 'bronze', 'hinoki', 'washi', 'paving'];
const FLOORS = ['black_sand', 'paving', 'basalt_wet', 'basalt_dry', 'rimstone', 'obsidian', 'hinoki', 'lacquer_dark', 'tatami', 'lava', 'lava_flow', 'pool_floor'];
const state = {
  scene: Q.get('scene') || 'cave', wall: Q.get('wall') || 'basalt_wet', floor: Q.get('floor') || 'black_sand',
  mode: +(Q.get('mode') ?? 2), tier: Q.get('tier') || 'high', source: Q.get('source') || 'auto',
  cam: Q.get('cam') || null, anim: Q.get('anim') !== '0',
};
if (Q.has('clean')) document.body.classList.add('clean');
const $ = (id) => document.getElementById(id);
const errBox = $('err');
window.addEventListener('error', (e) => { errBox.textContent += (e.message || e) + '\n'; });

// ---------------------------------------------------------------- renderer
const canvas = $('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, stencil: false, preserveDrawingBuffer: true });
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = +(Q.get('exp') ?? 1.0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
const gl = renderer.getContext();
const tq = gl.getExtension('EXT_disjoint_timer_query_webgl2');
function dprFor() { return Q.get('dpr') ? +Q.get('dpr') : Math.min(devicePixelRatio, state.tier === 'low' ? 1.5 : 2); }
const camera = new THREE.PerspectiveCamera(60, 1, 0.05, 300);
let lastSize = '';
function resize() {
  const w = innerWidth, h = innerHeight;
  const key = `${w}x${h}@${dprFor()}`;
  if (key === lastSize) return;
  lastSize = key;
  renderer.setPixelRatio(dprFor()); renderer.setSize(w, h, false);
  camera.aspect = w / h;
  // keep a sensible horizontal field of view in portrait
  camera.fov = w < h ? 72 : 58;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);

const env = makeStubEnvironment(renderer);
KZ.kzFogDensity.value = 0.012;

// ---------------------------------------------------------------- textures / manifest
const loader = new THREE.TextureLoader();
const TEX = new Map();
const pending = new Set();
function tex(path, srgb) {
  const key = path + (srgb ? '|s' : '');
  if (TEX.has(key)) return TEX.get(key);
  let res;
  const p = new Promise((r) => { res = r; });
  const t = loader.load(path, () => { pending.delete(p); res(); }, undefined, () => { pending.delete(p); errBox.textContent += 'missing ' + path + '\n'; res(); });
  pending.add(p);
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = 4;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  TEX.set(key, t);
  return t;
}
const MAN = {};
const manifest = await (await fetch('../../../materials.json')).json();
for (const m of manifest.materials) MAN[m.id] = m;

function cfgFor(id, mode, tier, source) {
  const d = KZM[id] || KZM_DEMO[id];
  const baseId = KZM_DEMO[id] ? 'paving' : id;
  const man = MAN[baseId];
  const p = man.params, k = man.constants || {};
  const settings = {
    tint: p.tint, wetness: p.wetness, wear: p.wear, roughness_offset: p.roughness_offset,
    normal_strength: p.normal_strength, emissive_level: p.emissive_level || 1, ...(d.settings || {}),
  };
  const libSet = man.textures.base.match(/tex\/(.+)_base/)[1];
  const usePlate = !!d.plate && (source === 'plate' || (source === 'auto' && mode >= 1));
  const ratio = (p.scale || man.tiling_m_per_repeat || 1) / (man.tiling_m_per_repeat || p.scale || 1);
  const c = {
    mode, tier, settings, porosity: k.Porosity ?? d.porosity ?? 0.5,
    worn: { color: k.WornColor || [0.05, 0.05, 0.05], rough: k.WornRough ?? 0.45 },
    rot: d.rot ?? 1, gainR: d.gainR ?? 0.7, macro: d.macro, layer: d.layer, proc: d.proc,
    procA: d.procA, procB: d.procB, albedoA: d.albedoA, albedoB: d.albedoB, caustics: d.caustics ?? 0,
    emissive: d.emissive, metal: d.metal ?? 0, rough: d.rough ?? [0.7, 0.2], hybrid: d.tech === 'hybrid' && usePlate,
  };
  for (const key of Object.keys(c)) if (c[key] === undefined) delete c[key];
  if (usePlate) {
    const dir = 'tex/pl/';
    c.maps = { base: tex(`${dir}${d.plate}_base.jpg`, true), nh: tex(`${dir}${d.plate}_nh.png`, false) };
    if (d.plate2 && mode >= 2) c.maps2 = { base: tex(`${dir}${d.plate2}_base.jpg`, true), nh: tex(`${dir}${d.plate2}_nh.png`, false) };
    c.patch = true;
    const m = d.plateM * ratio;
    c.tileM = [m, m]; c.aspect = 1; settings.scale = m;
    c.proj = mode >= 1 ? (d.proj || 'uv') : 'uv';
    if (d.boards) c.boards = d.boards;
    if (d.gain && !(mode === 3 && d.proc && d.tech !== 'hybrid')) settings.tint = settings.tint.map((x) => x * d.gain);
  } else {
    const dir = 'tex/lib/';
    c.maps = { base: tex(`${dir}${libSet}_base.jpg`, true), nh: tex(`${dir}${libSet}_nh.png`, false), orm: tex(`${dir}${libSet}_orm.png`, false) };
    const s = p.scale || man.tiling_m_per_repeat || 1;
    c.tileM = [s, s / (man.aspect || 1)]; c.aspect = man.aspect || 1; settings.scale = s;
    c.proj = mode === 0 ? 'uv' : (d.proj || 'uv');
    c.patch = false;
    if (c.emissive?.fromBase) c.emissive = { ...c.emissive, fromBase: c.emissive.fromBase * 0.6 };
  }
  if (mode === 0) { c.macro = { ...(c.macro || {}), amount: 0 }; }
  if (state.debug) c.debug = state.debug;
  c.noiseTex = tex('tex/kz_noise.png', false);
  return c;
}

function makeMat(id, mode, lm, opts = {}) {
  const m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, metalness: 0, side: opts.side ?? THREE.FrontSide });
  m.lightMap = lm; m.lightMap.channel = 1; m.lightMapIntensity = Math.PI;
  m.envMap = env; m.envMapIntensity = 1;
  patchMaterial(m, {});
  const cfg = cfgFor(id, mode, state.tier, state.source);
  if (opts.kind === 'wall' && cfg.proj === 'floor') cfg.proj = 'biplanar';
  kzShade(m, cfg);
  m.userData.kzId = id; m.userData.kzMode = mode;
  return m;
}

// ---------------------------------------------------------------- noise for geometry
function h2(x, y) { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); }
function vn(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = h2(xi, yi), b = h2(xi + 1, yi), c = h2(xi, yi + 1), d = h2(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x, y, o = 4) { let s = 0, a = 0.5, t = 0; for (let i = 0; i < o; i++) { s += a * vn(x, y); t += a; a *= 0.5; x *= 2.03; y *= 2.03; } return s / t; }

// grid: fn(u01, v01) -> [x, y, z, uvx, uvy]
function grid(segX, segY, fn) {
  const nx = segX + 1, ny = segY + 1;
  const pos = new Float32Array(nx * ny * 3), uv = new Float32Array(nx * ny * 2), uv1 = new Float32Array(nx * ny * 2);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const k = j * nx + i;
    const r = fn(i / segX, j / segY);
    pos.set([r[0], r[1], r[2]], k * 3); uv.set([r[3], r[4]], k * 2);
    uv1.set([(i + 0.5) / nx, (j + 0.5) / ny], k * 2);
  }
  const idx = [];
  for (let j = 0; j < segY; j++) for (let i = 0; i < segX; i++) {
    const a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;
    idx.push(a, b, d, a, d, c);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setAttribute('uv1', new THREE.BufferAttribute(uv1, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  g.userData.grid = [nx, ny];
  return g;
}
// fake bake: irradiance per vertex (= texel) from lanterns, written to a half-float lightmap
function bake(g, lights, amb, opts = {}) {
  const [nx, ny] = g.userData.grid;
  const P = g.attributes.position.array, N = g.attributes.normal.array;
  const data = new Uint16Array(nx * ny * 4);
  const flip = opts.flip ? -1 : 1;
  for (let k = 0; k < nx * ny; k++) {
    const px = P[k * 3], py = P[k * 3 + 1], pz = P[k * 3 + 2];
    const nX = N[k * 3] * flip, nY = N[k * 3 + 1] * flip, nZ = N[k * 3 + 2] * flip;
    let r = amb[0], gg = amb[1], b = amb[2];
    // soft sky/bounce: a little more from below-facing floors' bounce on walls
    const s = 0.6 + 0.4 * Math.max(0, nY);
    r *= s; gg *= s; b *= s;
    for (const L of lights) {
      const dx = L.p[0] - px, dy = L.p[1] - py, dz = L.p[2] - pz;
      const d2 = dx * dx + dy * dy + dz * dz, d = Math.sqrt(d2);
      const cos = Math.max(0, (dx * nX + dy * nY + dz * nZ) / d);
      const w = L.I * (0.15 + 0.85 * cos) * cos / (d2 + 0.4);
      r += w * L.c[0]; gg += w * L.c[1]; b += w * L.c[2];
    }
    if (opts.contact) { const c = 0.55 + 0.45 * Math.min(1, Math.max(0, (py - opts.contact) / 1.2)); r *= c; gg *= c; b *= c; }
    data[k * 4] = THREE.DataUtils.toHalfFloat(r); data[k * 4 + 1] = THREE.DataUtils.toHalfFloat(gg);
    data[k * 4 + 2] = THREE.DataUtils.toHalfFloat(b); data[k * 4 + 3] = THREE.DataUtils.toHalfFloat(1);
  }
  const t = new THREE.DataTexture(data, nx, ny, THREE.RGBAFormat, THREE.HalfFloatType);
  t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearFilter; t.colorSpace = THREE.LinearSRGBColorSpace;
  t.needsUpdate = true;
  return t;
}
const WARM = [1.0, 0.6, 0.3];
function lanternMesh(p, scale = 1) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(0.16 * scale, 16, 10), new THREE.MeshBasicMaterial({ color: new THREE.Color(14, 7, 2.6) }));
  m.position.set(...p);
  return m;
}

// ---------------------------------------------------------------- scenes
let scene = null;
let surfaces = []; // {mesh, kind: 'wall'|'floor'|'ceil', lm, modeOverride}
let labelAnchors = [];
const CAMS = {
  cave: { wide: [[0, 1.6, 9], [0, 4.2, -6]], floor: [[-6, 1.6, 6], [6, 0, -4]], close: [[3, 1.6, -2.2], [3.5, 1.4, -6]], left: [[8, 1.6, 4], [-12, 3, -6]] },
  corridor: { down: [[0, 1.6, -1], [0, 1.45, -30]], wall: [[0.6, 1.6, -10], [-2, 1.5, -16]], floor: [[0, 1.6, -4], [0, 0, -12]] },
  swatch: { front: [[0, 1.35, 1.2], [0, 1.25, -2.2]], low: [[0, 1.0, 0.2], [0, 0.4, -1.6]], near: [[-0.9, 1.4, -0.9], [-0.9, 1.3, -2.2]] },
};
function buildScene() {
  if (scene) scene.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose?.(); } });
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0.006, 0.005, 0.004);
  surfaces = []; labelAnchors = [];
  const S = state.scene;
  if (S === 'cave') {
    // 40 x 20 m concave cave wall with big bulges and ledges
    const wall = grid(200, 100, (u, v) => {
      const x = -20 + 40 * u, y = 20 * v;
      const big = (fbm(x * 0.08 + 3, y * 0.08, 4) - 0.5) * 4.0;
      const mid = (fbm(x * 0.35, y * 0.35 + 7, 3) - 0.5) * 0.9;
      const ledge = Math.max(0, Math.sin(y * 0.9 + fbm(x * 0.1, 1, 2) * 4)) * 0.25;
      const z = -6 - 0.012 * x * x + big + mid + ledge - (y > 12 ? (y - 12) * (y - 12) * 0.05 : 0);
      return [x, y, z, x, y];
    });
    const floor = grid(160, 80, (u, v) => {
      const x = -20 + 40 * u, z = 16 - 24 * v;
      const y = (fbm(x * 0.15, z * 0.15, 3) - 0.5) * 0.25 + (fbm(x * 0.8, z * 0.8, 2) - 0.5) * 0.04;
      return [x, y, z, x, -z];
    });
    const L = [];
    for (const x of [-15, -7, 1, 9, 16]) L.push({ p: [x, 1.0, -4.2 - 0.012 * x * x], c: WARM, I: 22 });
    for (const x of [-10, 4, 13]) L.push({ p: [x, 0.8, 4], c: WARM, I: 12 });
    L.push({ p: [-3, 7, -3], c: [0.3, 0.7, 0.8], I: 25 });
    const amb = [0.25, 0.22, 0.19];
    add(wall, 'wall', bake(wall, L, amb, { contact: 0 }));
    add(floor, 'floor', bake(floor, L, amb));
    for (const l of L) scene.add(lanternMesh(l.p, l.c === WARM ? 1 : 0.01));
  } else if (S === 'corridor') {
    const len = 60, W = 2.0, H = 3.6;
    const L = [];
    for (let z = -3; z > -len; z -= 6) L.push({ p: [(L.length % 2 ? 1 : -1) * (W - 0.35), 0.9, z], c: WARM, I: 9 });
    const amb = [0.12, 0.1, 0.09];
    const wallL = grid(300, 24, (u, v) => {
      const z = -len * u, y = H * v; const d = (fbm(z * 0.6, y * 0.6, 3) - 0.5) * 0.35 + (fbm(z * 2.2, y * 2.2, 2) - 0.5) * 0.06;
      return [-W - d, y, z, -z, y];
    });
    const wallR = grid(300, 24, (u, v) => {
      const z = -len * (1 - u), y = H * v; const d = (fbm(z * 0.6 + 9, y * 0.6, 3) - 0.5) * 0.35 + (fbm(z * 2.2 + 9, y * 2.2, 2) - 0.5) * 0.06;
      return [W + d, y, z, -z, y];
    });
    const floor = grid(24, 300, (u, v) => { const x = -W + 2 * W * u, z = -len * v; return [x, (fbm(x, z, 2) - 0.5) * 0.02, z, x, -z]; });
    const ceil = grid(24, 300, (u, v) => { const x = W - 2 * W * u, z = -len * v; return [x, H + (fbm(x * 0.7, z * 0.7, 3) - 0.5) * 0.4, z, x, -z]; });
    add(wallL, 'wall', bake(wallL, L, amb, { contact: 0 }));
    add(wallR, 'wall', bake(wallR, L, amb, { contact: 0 }));
    add(floor, 'floor', bake(floor, L, amb));
    add(ceil, 'ceil', bake(ceil, L, amb));
    for (const l of L) scene.add(lanternMesh(l.p));
  } else {
    // swatch wall: the wall material in the 4 modes side by side
    const L = [{ p: [-2.0, 3.0, 0.2], c: WARM, I: 10 }, { p: [2.0, 3.0, 0.2], c: WARM, I: 10 }, { p: [0, 0.6, -0.4], c: WARM, I: 3 }];
    const amb = [0.05, 0.045, 0.04];
    for (let i = 0; i < 4; i++) {
      const x0 = -3.0 + i * 1.5;
      const g = grid(60, 100, (u, v) => {
        const x = x0 + 1.42 * u, y = 2.5 * v;
        const z = -2.2 + (fbm(x * 0.9, y * 0.9, 3) - 0.5) * 0.12;
        return [x, y, z, x + 10, y];
      });
      add(g, 'wall', bake(g, L, amb, { contact: 0 }), i);
      labelAnchors.push({ p: new THREE.Vector3(x0 + 0.71, 2.62, -2.2), text: MODE_SHORT[i] });
    }
    const floor = grid(60, 40, (u, v) => { const x = -3.2 + 6.4 * u, z = 1.6 - 4 * v; return [x, 0, z, x, -z]; });
    add(floor, 'floor', bake(floor, L, amb));
    for (const l of L.slice(0, 2)) scene.add(lanternMesh(l.p, 0.7));
  }
  assignMaterials();
  setCam(state.cam && CAMS[S][state.cam] ? state.cam : Object.keys(CAMS[S])[0]);
  fillCamSelect();
  probeTex = null;
  probeReady = bakeProbe();
}
let probeReady = null;
function add(g, kind, lm, modeOverride = null) {
  const mesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial());
  mesh.userData = { kind, lm, modeOverride };
  scene.add(mesh);
  surfaces.push(mesh);
}
// scene probe: a cubemap of the lit scene (lanterns included), PMREM-filtered and box-projected, as the
// runtime's baked probes are. Rendered once per scene build.
const PROBES = {
  cave: { pos: [0, 2.0, 3], min: [-20, -0.5, -10], max: [20, 20, 16] },
  corridor: { pos: [0, 1.6, -12], min: [-2.3, -0.1, -60], max: [2.3, 3.8, 0.5] },
  swatch: { pos: [0, 1.5, 0], min: [-3.3, 0, -2.4], max: [3.3, 3.2, 1.7] },
};
let probeTex = null;
const pmrem = new THREE.PMREMGenerator(renderer);
async function bakeProbe() {
  const P = PROBES[state.scene];
  while (pending.size) await Promise.all([...pending]);
  await renderer.compileAsync(scene, camera);
  const rt = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType });
  const cc = new THREE.CubeCamera(0.05, 200, rt);
  cc.position.set(...P.pos);
  scene.add(cc);
  KZ.kzFogOn.value = 0;
  cc.update(renderer, scene);
  KZ.kzFogOn.value = 1;
  scene.remove(cc);
  probeTex?.dispose();
  probeTex = pmrem.fromCubemap(rt.texture).texture;
  rt.dispose();
  KZ.kzProbeAMin.value.set(...P.min); KZ.kzProbeAMax.value.set(...P.max); KZ.kzProbeACenter.value.set(...P.pos);
  KZ.kzProbeBMin.value.set(...P.min); KZ.kzProbeBMax.value.set(...P.max); KZ.kzProbeBCenter.value.set(...P.pos);
  KZ.kzEnvB.value = probeTex; KZ.kzProbeBlend.value = 0; KZ.kzProbeIntensity.value = 1;
  for (const m of surfaces) m.material.envMap = probeTex;
}
function assignMaterials() {
  for (const m of surfaces) {
    const { kind, lm, modeOverride } = m.userData;
    m.material.dispose();
    const id = kind === 'wall' ? state.wall : kind === 'floor' ? state.floor : 'basalt_dry';
    m.material = makeMat(id, modeOverride ?? state.mode, lm, { kind });
    if (probeTex) m.material.envMap = probeTex;
  }
}
let camYaw = 0, camPitch = 0;
function setCam(name) {
  state.cam = name;
  const c = CAMS[state.scene][name];
  camera.position.set(...c[0]);
  camera.lookAt(new THREE.Vector3(...c[1]));
  const e = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
  camYaw = e.y; camPitch = e.x;
}

// ---------------------------------------------------------------- UI
function fillSelect(sel, items, cur) { sel.innerHTML = items.map((x) => `<option ${x === cur ? 'selected' : ''}>${x}</option>`).join(''); }
fillSelect($('wall'), WALLS, state.wall); fillSelect($('floor'), FLOORS, state.floor);
$('scene').value = state.scene; $('source').value = state.source; $('anim').checked = state.anim;
function fillCamSelect() { fillSelect($('cam'), Object.keys(CAMS[state.scene]), state.cam); }
$('modes').innerHTML = MODE_SHORT.map((n, i) => `<button data-m="${i}">${i}: ${n}</button>`).join('');
$('tiers').innerHTML = ['low', 'high'].map((t) => `<button data-t="${t}">${t}</button>`).join('');
function syncButtons() {
  for (const b of $('modes').children) b.classList.toggle('on', +b.dataset.m === state.mode);
  for (const b of $('tiers').children) b.classList.toggle('on', b.dataset.t === state.tier);
}
$('modes').onclick = (e) => { if (e.target.dataset.m != null) { state.mode = +e.target.dataset.m; assignMaterials(); syncButtons(); } };
$('tiers').onclick = (e) => { if (e.target.dataset.t) { state.tier = e.target.dataset.t; resize(); assignMaterials(); syncButtons(); } };
$('scene').onchange = (e) => { state.scene = e.target.value; state.cam = null; buildScene(); };
$('wall').onchange = (e) => { state.wall = e.target.value; assignMaterials(); };
$('floor').onchange = (e) => { state.floor = e.target.value; assignMaterials(); };
$('source').onchange = (e) => { state.source = e.target.value; assignMaterials(); };
$('cam').onchange = (e) => setCam(e.target.value);
$('anim').onchange = (e) => { state.anim = e.target.checked; };
$('hide').onclick = () => document.body.classList.add('clean');
syncButtons();

// look / move
let drag = null;
canvas.addEventListener('pointerdown', (e) => { drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointerup', () => { drag = null; });
canvas.addEventListener('pointermove', (e) => {
  if (!drag) return;
  camYaw -= (e.clientX - drag[0]) * 0.004; camPitch -= (e.clientY - drag[1]) * 0.004;
  camPitch = Math.max(-1.4, Math.min(1.4, camPitch)); drag = [e.clientX, e.clientY];
  camera.quaternion.setFromEuler(new THREE.Euler(camPitch, camYaw, 0, 'YXZ'));
});
const keys = new Set();
addEventListener('keydown', (e) => keys.add(e.key.toLowerCase()));
addEventListener('keyup', (e) => keys.delete(e.key.toLowerCase()));
canvas.addEventListener('wheel', (e) => { const f = new THREE.Vector3(); camera.getWorldDirection(f); f.y = 0; f.normalize(); camera.position.addScaledVector(f, -e.deltaY * 0.004); }, { passive: true });

// ---------------------------------------------------------------- loop + timing
let last = performance.now(), fpsAcc = [], gpuMs = NaN, query = null, frameNo = 0;
const clock0 = performance.now();
function renderFrame() {
  if (tq && !query) { query = gl.createQuery(); gl.beginQuery(tq.TIME_ELAPSED_EXT, query); renderer.render(scene, camera); gl.endQuery(tq.TIME_ELAPSED_EXT); }
  else renderer.render(scene, camera);
  if (query) {
    const avail = gl.getQueryParameter(query, gl.QUERY_RESULT_AVAILABLE);
    const disjoint = gl.getParameter(tq.GPU_DISJOINT_EXT);
    if (avail) { if (!disjoint) gpuMs = gl.getQueryParameter(query, gl.QUERY_RESULT) / 1e6; gl.deleteQuery(query); query = null; }
  }
  frameNo++;
}
function updateLabels() {
  const box = $('labels');
  if (!labelAnchors.length) { box.innerHTML = ''; return; }
  if (box.children.length !== labelAnchors.length) box.innerHTML = labelAnchors.map(() => '<div></div>').join('');
  labelAnchors.forEach((a, i) => {
    const v = a.p.clone().project(camera);
    const el = box.children[i];
    el.textContent = a.text;
    el.style.left = ((v.x * 0.5 + 0.5) * innerWidth) + 'px';
    el.style.top = ((-v.y * 0.5 + 0.5) * innerHeight) + 'px';
    el.style.display = v.z < 1 ? '' : 'none';
  });
}
let manualTime = null;
function tick(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (manualTime == null && state.anim) KZS.time.value = (now - clock0) / 1000;
  KZ.kzTime.value = KZS.time.value;
  const f = new THREE.Vector3(); camera.getWorldDirection(f);
  const r = new THREE.Vector3().crossVectors(f, camera.up).normalize();
  const sp = (keys.has('shift') ? 4 : 1.5) * dt;
  if (keys.has('w')) camera.position.addScaledVector(f, sp);
  if (keys.has('s')) camera.position.addScaledVector(f, -sp);
  if (keys.has('a')) camera.position.addScaledVector(r, -sp);
  if (keys.has('d')) camera.position.addScaledVector(r, sp);
  if (!benching) renderFrame();
  updateLabels();
  fpsAcc.push(dt); if (fpsAcc.length > 60) fpsAcc.shift();
  if (frameNo % 15 === 0) {
    const avg = fpsAcc.reduce((a, b) => a + b, 0) / fpsAcc.length;
    const w = surfaces.find((s) => s.userData.kind === 'wall');
    const cost = w ? kzCost(w.material.userData.kz.cfg) : { taps: 0 };
    $('stats').textContent = `${(1 / avg).toFixed(0)} fps  frame ${(avg * 1000).toFixed(1)} ms\nGPU ${isNaN(gpuMs) ? 'n/a' : gpuMs.toFixed(2) + ' ms'}  ${renderer.domElement.width}×${renderer.domElement.height}\nwall: ${MODE_NAMES[state.mode]}, ${state.tier}, ~${cost.taps} taps/px`;
  }
  requestAnimationFrame(tick);
}
let benching = false;

// ---------------------------------------------------------------- automation API (renders / benchmarks)
async function settle() {
  if (probeReady) await probeReady;
  while (pending.size) await Promise.all([...pending]);
  await renderer.compileAsync(scene, camera);
  renderFrame();
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
}
window.KZDEMO = {
  state, MODE_NAMES,
  async set(o = {}) {
    const rebuild = o.scene && o.scene !== state.scene;
    Object.assign(state, o);
    if (o.caption != null) $('caption').textContent = o.caption;
    if (o.exp != null) renderer.toneMappingExposure = o.exp;
    if (o.time != null) { manualTime = o.time; KZS.time.value = o.time; }
    resize();
    if (rebuild) buildScene(); else assignMaterials();
    if (o.cam) setCam(o.cam);
    if (o.pos) { camera.position.set(...o.pos); camera.lookAt(new THREE.Vector3(...o.look)); }
    syncButtons();
    await settle();
    return { w: renderer.domElement.width, h: renderer.domElement.height, err: errBox.textContent };
  },
  pose(pos, look, time) { camera.position.set(...pos); camera.lookAt(new THREE.Vector3(...look)); if (time != null) { manualTime = time; KZS.time.value = time; } renderFrame(); },
  // GPU frame cost. EXT_disjoint_timer_query_webgl2 is not exposed by this Chrome, so: render n frames
  // back-to-back, each followed by a 1-pixel readPixels (full GPU sync), wall-clock / n; best of 3 runs.
  async bench(frames = 40) {
    benching = true;
    const px = new Uint8Array(4);
    const runs = [];
    for (let r = 0; r < 4; r++) {
      await new Promise((res) => requestAnimationFrame(res));
      const t0 = performance.now();
      for (let i = 0; i < frames; i++) { renderer.render(scene, camera); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); }
      runs.push((performance.now() - t0) / frames);
    }
    benching = false;
    runs.shift();
    runs.sort((a, b) => a - b);
    return { median: runs[0], runs, w: renderer.domElement.width, h: renderer.domElement.height, timer: !!tq };
  },
  programs() { return renderer.info.programs.length; },
};

resize();
buildScene();
await settle();
requestAnimationFrame(tick);
window.KZDEMO.ready = true;
