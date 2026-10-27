// Gallery model viewer: one GLB at a time on a studio stage, library materials through the walkthrough's own
// MaterialLibrary / kzlib (so a model looks exactly as it does in the walkaround), glowworm / star sprites, lava flow,
// skinned figures with the shared clip set. Lit live (no lightmaps): warm lantern key + teal fill like the LOD sheet rig.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { KZ, MaterialLibrary, makeStubEnvironment, patchMaterial } from '../materials.js';
import { spriteMaterial, SPRITES } from '../sprites.js';

export const ENVS = {
  studio: { label: 'Studio', key: 2.6, fill: 0.9, rim: 0.8, env: 0.55, room: false, bg: 0x0f0d0c, exposure: 0 },
  lantern: { label: 'Lantern', key: 0.9, fill: 0.25, rim: 0.2, env: 1.0, room: false, bg: 0x070605, exposure: 0.3 },
  neutral: { label: 'Neutral', key: 1.4, fill: 0.5, rim: 0.4, env: 0.9, room: true, bg: 0x2a2724, exposure: 0 },
};

export class Viewer {
  constructor(canvas, { base, materialsDoc, onStats } = {}) {
    this.canvas = canvas;
    this.base = base; // URL of gallery/ (data paths are relative to it)
    this.onStats = onStats ?? (() => {});
    // default power preference: an explicit 'high-performance' is refused by some dual-GPU setups (it logged a
    // context error before the walkthrough-style retry); single-context pages get the discrete GPU anyway
    const r = new THREE.WebGLRenderer({ canvas, antialias: false, stencil: false });
    this.renderer = r;
    try { const gl = r.getContext(), ext = gl.getExtension('WEBGL_debug_renderer_info'); this.gpu = ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : ''; } catch { this.gpu = ''; }
    r.toneMapping = THREE.AgXToneMapping;
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.info.autoReset = false;
    this.ktx2 = new KTX2Loader().setTranscoderPath(new URL('libs/basis/', document.baseURI).href).detectSupport(r);
    this.gltf = new GLTFLoader().setKTX2Loader(this.ktx2).setMeshoptDecoder(MeshoptDecoder);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.02, 2000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.08;
    this.controls.autoRotateSpeed = 1.2;
    this.controls.addEventListener('start', () => { this.userTouched = true; });
    const target = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(r, target);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.composer.addPass(new OutputPass());

    // environment: the walkthrough's stub probe (warm floor, dark vault, lantern band) or a neutral room
    this.stubEnv = makeStubEnvironment(r);
    const pm = new THREE.PMREMGenerator(r);
    this.roomEnv = pm.fromScene(new RoomEnvironment(), 0.04).texture; pm.dispose();
    KZ.kzEnvB.value = this.stubEnv;
    KZ.kzFogOn.value = 0;
    KZ.kzWaterCount.value = 0;

    // lights: fixed set (no recompiles when toggled) - key, fill, rim + a pool of 4 points for the asset's own lamps
    this.key = new THREE.DirectionalLight(new THREE.Color().setRGB(1.0, 0.72, 0.42, THREE.LinearSRGBColorSpace), 2.6);
    this.fill = new THREE.DirectionalLight(new THREE.Color().setRGB(0.35, 0.8, 0.85, THREE.LinearSRGBColorSpace), 0.9);
    this.rim = new THREE.DirectionalLight(new THREE.Color().setRGB(1.0, 0.85, 0.7, THREE.LinearSRGBColorSpace), 0.8);
    this.lightRig = new THREE.Group();
    for (const l of [this.key, this.fill, this.rim]) { this.lightRig.add(l); this.lightRig.add(l.target); }
    this.scene.add(this.lightRig);
    this.pool = Array.from({ length: 4 }, () => { const l = new THREE.PointLight(0xffffff, 0, 0, 2); this.scene.add(l); return l; });

    // stage: dark floor disc, metre grid, 1.7 m figure silhouette
    this.stage = new THREE.Group();
    this.floorMat = patchMaterial(new THREE.MeshStandardMaterial({ color: 0x1a1613, roughness: 0.92, metalness: 0 }));
    this.floor = new THREE.Mesh(new THREE.CircleGeometry(1, 96), this.floorMat);
    this.floor.rotation.x = -Math.PI / 2; this.floor.position.y = -0.002;
    this.stage.add(this.floor);
    this.gridGroup = new THREE.Group(); this.stage.add(this.gridGroup);
    this.silhouette = makeSilhouette(); this.stage.add(this.silhouette);
    this.scene.add(this.stage);

    this.lib = null;
    this.materialsDoc = materialsDoc;
    this.texCache = new Map(); // id -> Promise<Texture>
    this.texReady = {}; // id -> Texture (MaterialLibrary.textures)
    this.glbCache = new Map(); // uri -> Promise<gltf>
    this.model = null; this.modelRoot = new THREE.Group(); this.scene.add(this.modelRoot);
    this.mixer = null; this.action = null; this.clips = null;
    this.opts = { wire: false, rotate: false, grid: true, figure: true, lamps: false, env: 'studio' };
    this.lastT = performance.now();
    this.t = 0;
    this.frameStats = { tris: 0, calls: 0, points: 0, lines: 0, fps: 0 };
    this._fpsN = 0; this._fpsT = 0;
    this.running = false;
    this.setEnv('studio');
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(canvas.parentElement ?? canvas);
    this.resize();
  }

  ensureLib(materialsDoc) {
    if (this.lib) return this.lib;
    this.materialsDoc = materialsDoc;
    this.lib = new MaterialLibrary({ materials: materialsDoc.materials }, this.texReady, this.stubEnv, 'high');
    return this.lib;
  }
  url(rel) { return new URL(rel, this.base).href; }
  async fetchBuf(rel) {
    const res = await fetch(this.url(rel));
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${rel}`);
    return res.arrayBuffer();
  }
  texture(id) {
    let p = this.texCache.get(id);
    if (!p) {
      const def = this.materialsDoc.textures[id];
      if (!def) return Promise.reject(new Error(`texture ${id} not in materials.json`));
      p = this.fetchBuf(def.uri).then((buf) => new Promise((res, rej) => this.ktx2.parse(buf, res, rej))).then((t) => { t.name = id; this.texReady[id] = t; return t; });
      this.texCache.set(id, p);
    }
    return p;
  }
  // every library texture the given material keys need, loaded before the materials are built
  async texturesFor(keys) {
    const ids = new Set();
    for (const k of keys) {
      const d = this.materialsDoc.materials[k];
      if (!d) continue;
      for (const m of [d.kit, d.maps]) for (const v of Object.values(m ?? {})) if (v) ids.add(v);
    }
    await Promise.all([...ids].map((id) => this.texture(id)));
  }
  glb(uri) {
    let p = this.glbCache.get(uri);
    if (!p) {
      p = this.fetchBuf(uri).then((buf) => new Promise((res, rej) => this.gltf.parse(buf, this.url(uri), res, rej)));
      p.catch(() => this.glbCache.delete(uri));
      this.glbCache.set(uri, p);
    }
    return p;
  }

  setEnv(name) {
    const e = ENVS[name] ?? ENVS.studio;
    this.opts.env = name;
    this.key.intensity = e.key; this.fill.intensity = e.fill; this.rim.intensity = e.rim;
    KZ.kzProbeIntensity.value = e.env;
    const env = e.room ? this.roomEnv : this.stubEnv;
    if (this.lib) for (const m of this.lib.cache.values()) if (m.envMap) m.envMap = env;
    if (this.floorMat) { this.floorMat.envMap = env; }
    KZ.kzEnvB.value = env;
    this.envTex = env;
    this.scene.background = new THREE.Color(e.bg);
    this.renderer.toneMappingExposure = 2 ** e.exposure;
  }

  /**
   * Show one variant. asset: index entry; v: variant entry. Returns load stats.
   */
  async show(asset, v, { keepCamera = false } = {}) {
    const t0 = performance.now();
    const token = (this.token = (this.token ?? 0) + 1);
    const gl = await this.glb(v.uri);
    // material keys used by this GLB
    const keys = new Set();
    gl.scene.traverse((o) => { if (o.isMesh) { const kz = o.userData.kz ?? {}; keys.add(kz.material && this.materialsDoc.materials[kz.material] ? kz.material : o.material?.name); } });
    await this.texturesFor(keys);
    if (token !== this.token) return null; // a newer request won
    this.clearModel();
    const root = gl.scene; // cached GLB scenes are reused: materials are reassigned, never disposed
    const errors = [];
    let points = 0, lines = 0, skinned = false;
    root.traverse((o) => {
      if (!(o.isMesh || o.isPoints || o.isLine)) return;
      const kz = o.userData.kz ?? o.parent?.userData?.kz ?? {};
      o.userData.kz = kz;
      if (kz.role === 'glowworm' || kz.role === 'glowworm_threads') {
        o.material = spriteMaterial(kz.color, kz.role === 'glowworm_threads');
        o.frustumCulled = false; o.renderOrder = 12;
        if (o.isPoints) points += o.geometry.attributes.position.count; else lines += o.geometry.attributes.position.count / 2;
        return;
      }
      if (o.isSkinnedMesh) skinned = true;
      const name = kz.material && this.materialsDoc.materials[kz.material] ? kz.material : (o.userData.kzMat ?? o.material?.name);
      o.userData.kzMat = name;
      try {
        o.material = this.lib.get(name, { side: THREE.DoubleSide, flow: !!o.geometry.attributes._kz_flow });
        if (o.material.envMap) o.material.envMap = this.envTex;
      } catch (e) { errors.push(`${o.name}: ${e.message}`); }
    });
    // placement: ceiling pieces hang 3.2 m above the stage floor, the rest stand on it
    // (lava_crack carries snap 'ceiling' in assets.json but is modelled lying flat: it stays on the floor)
    const ceiling = asset.snap === 'ceiling' && asset.id !== 'lava_crack';
    root.position.set(0, ceiling ? 3.2 - (v.bbox?.max?.[1] ?? 0) : 0, 0);
    this.modelRoot.add(root);
    this.model = { asset, v, root, ceiling };
    this.applyWire();
    // bounds (sprites included)
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root, true);
    if (box.isEmpty()) box.set(new THREE.Vector3(-0.5, 0, -0.5), new THREE.Vector3(0.5, 1, 0.5));
    this.box = box;
    this.layoutStage(box, ceiling);
    if (!keepCamera) this.frame(box, ceiling);
    // asset lamps (kz_lights point / spot) -> the fixed point pool
    this.lamps = (asset.kz_lights?.points ?? []).map((l) => ({
      pos: new THREE.Vector3(l.pos[0], l.pos[2], -l.pos[1]).add(root.position),
      color: l.color ? new THREE.Color().setRGB(...l.color, THREE.LinearSRGBColorSpace) : kelvin(l.kelvin ?? 2200),
      intensity: (l.watts ?? 15) / (4 * Math.PI), distance: l.radius ? l.radius * 3 : 0,
    })).sort((a, b) => b.intensity - a.intensity);
    this.applyLamps();
    // figures: shared clips, retargeted to this rig
    this.mixer = null; this.action = null;
    if (skinned && this.clipSet) this.bindClips(root);
    this.renderer.compile(this.scene, this.camera);
    await this.frames(2);
    return { ms: performance.now() - t0, points, lines, errors, skinned };
  }

  // library material on a 1 m sphere (UV0 in metres, like the generators' metric UVs) on a small plinth
  async showMaterial(key) {
    const token = (this.token = (this.token ?? 0) + 1);
    await this.texturesFor([key]);
    if (token !== this.token) return null;
    this.clearModel();
    const r = 0.5;
    const geo = new THREE.SphereGeometry(r, 96, 64);
    const uv = geo.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 2 * Math.PI * r, (1 - uv.getY(i)) * Math.PI * r);
    const root = new THREE.Group();
    const s = new THREE.Mesh(geo, this.lib.get(key, { side: THREE.FrontSide }));
    s.material.envMap = this.envTex;
    s.position.y = r + 0.12;
    const plinthGeo = new THREE.CylinderGeometry(0.42, 0.46, 0.12, 64);
    const plinth = new THREE.Mesh(plinthGeo, this.floorMat);
    plinth.position.y = 0.06;
    root.add(s, plinth);
    this.modelRoot.add(root);
    this.model = { asset: { id: key }, v: null, root, ceiling: false };
    this.applyWire();
    const box = new THREE.Box3().setFromObject(root);
    this.box = box;
    this.layoutStage(box, false);
    this.silhouette.visible = false;
    this.frame(box, false);
    this.lamps = []; this.applyLamps();
    await this.frames(2);
    return { ok: true };
  }

  clearModel() {
    if (this.mixer) { this.mixer.stopAllAction(); this.mixer.uncacheRoot(this.mixer.getRoot()); }
    this.mixer = null; this.action = null;
    this.modelRoot.clear();
    this.model = null;
  }

  layoutStage(box, ceiling) {
    const size = box.getSize(new THREE.Vector3());
    const ext = Math.max(size.x, size.z, 2);
    const R = Math.ceil(ext * 0.75 + 2);
    this.floor.scale.setScalar(R * 1.15);
    this.gridGroup.clear();
    const n = Math.min(2 * R, 160);
    const grid = new THREE.GridHelper(n, n, 0x6fc7bd, 0x3a332c);
    grid.material.transparent = true; grid.material.opacity = 0.55; grid.material.depthWrite = false;
    grid.position.y = 0.001;
    this.gridGroup.add(grid);
    this.gridGroup.visible = this.opts.grid;
    // silhouette next to the model, on the floor
    // left of the model, away from the default camera; behind small props so it never blocks them
    const small = Math.max(size.x, size.z, size.y) < 1.5;
    this.silhouette.position.set(box.min.x - 0.55, 0, ceiling ? 0 : small ? box.max.z + 0.9 : (box.min.z + box.max.z) / 2);
    this.silhouette.visible = this.opts.figure;
    // light rig scaled to the model
    const c = box.getCenter(new THREE.Vector3()), r = Math.max(size.length() / 2, 0.5);
    this.key.position.set(c.x - r * 1.6, c.y + r * 2.2, c.z - r * 2.4); this.key.target.position.copy(c);
    this.fill.position.set(c.x + r * 2.4, c.y + r * 1.0, c.z + r * 1.2); this.fill.target.position.copy(c);
    this.rim.position.set(c.x + r * 0.5, c.y + r * 1.5, c.z + r * 3); this.rim.target.position.copy(c);
  }

  frame(box, ceiling) {
    const c = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const r = Math.max(size.length() / 2, 0.3);
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const fit = Math.min(fov, 2 * Math.atan(Math.tan(fov / 2) * this.camera.aspect));
    const d = (r / Math.sin(fit / 2)) * 1.02;
    const ext = Math.max(size.x, size.z);
    if (ceiling && ext > 6) {
      // a big ceiling (glowworm field): stand under it at eye height and look up across it
      this.camera.position.set(c.x + ext * 0.12, 1.4, c.z - ext * 0.32);
      c.set(c.x, box.max.y - size.y * 0.5, c.z + ext * 0.08);
      this.camera.near = 0.05; this.camera.far = ext * 6 + 50;
    } else {
      const dir = ceiling ? new THREE.Vector3(0.6, -0.45, -1).normalize() // hanging pieces: seen from below
        : new THREE.Vector3(0.62, 0.42, -1).normalize(); // front is -Z (Blender +Y), seen from front-right, a little above
      this.camera.position.copy(c).addScaledVector(dir, d);
      if (ceiling) this.camera.position.y = Math.max(0.3, this.camera.position.y);
      this.camera.near = Math.max(0.01, d / 400); this.camera.far = d * 30 + 50;
    }
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(c);
    this.controls.minDistance = r * 0.05; this.controls.maxDistance = d * 6;
    this.controls.update();
    this.home = { pos: this.camera.position.clone(), target: c.clone() };
  }
  resetView() { if (this.home) { this.camera.position.copy(this.home.pos); this.controls.target.copy(this.home.target); this.controls.update(); } }

  setOpt(k, v) {
    this.opts[k] = v;
    if (k === 'wire') this.applyWire();
    if (k === 'rotate') this.controls.autoRotate = v;
    if (k === 'grid') this.gridGroup.visible = v;
    if (k === 'figure') this.silhouette.visible = v;
    if (k === 'lamps') this.applyLamps();
    if (k === 'env') this.setEnv(v);
  }
  applyWire() {
    if (!this.model) return;
    const on = this.opts.wire;
    this.model.root.traverse((o) => {
      if (!o.isMesh || !o.material || o.material.isShaderMaterial) return;
      o.material.wireframe = on;
    });
    // shared library materials: everything not in the current model goes back to solid
    if (this.lib) for (const m of this.lib.cache.values()) m.wireframe = on && this.isUsed(m);
  }
  isUsed(m) {
    let used = false;
    this.model?.root.traverse((o) => { if (o.material === m) used = true; });
    return used;
  }
  applyLamps() {
    const on = this.opts.lamps;
    this.pool.forEach((pl, i) => {
      const l = on ? this.lamps?.[i] : null;
      if (!l) { pl.intensity = 0; return; }
      pl.position.copy(l.pos); pl.color.copy(l.color); pl.intensity = l.intensity; pl.distance = l.distance;
    });
  }

  // ---------- figure clips ----------
  async loadClips(uri, refHeight) {
    if (this.clipSet) return this.clipSet;
    const gl = await this.glb(uri);
    const rest = {};
    gl.scene.traverse((o) => { if (o.name) rest[o.name] = { p: o.position.clone(), q: o.quaternion.clone() }; });
    this.clipSet = { clips: gl.animations, rest, refHeight };
    return this.clipSet;
  }
  // clips were baked on the reference rig (guest_figure seed 1, 1.65 m): keep this rig's own bone offsets and scale the
  // animated offset from the reference rest (pelvis bob / seat drop) by the pelvis height ratio
  bindClips(root) {
    const rest = {};
    root.traverse((o) => { if (o.isBone) rest[o.name] = o.position.clone(); });
    const ref = this.clipSet.rest;
    const s = rest.pelvis && ref.pelvis ? Math.max(0.3, Math.min(3, rest.pelvis.length() / Math.max(ref.pelvis.p.length(), 1e-4))) : 1;
    const key = `rt|${Object.keys(rest).length}|${s.toFixed(4)}|${rest.pelvis?.toArray().map((x) => x.toFixed(4)).join(',')}`;
    root.userData.clipCache ??= {};
    let clips = root.userData.clipCache[key];
    if (!clips) {
      clips = this.clipSet.clips.map((c) => {
        const tracks = c.tracks.map((t) => {
          const [node, prop] = t.name.split('.');
          if (prop !== 'position' || !rest[node] || !ref[node]) return t;
          const out = t.clone();
          const v = out.values, fr = rest[node], rr = ref[node].p;
          for (let i = 0; i < v.length; i += 3) {
            v[i] = fr.x + (v[i] - rr.x) * s; v[i + 1] = fr.y + (v[i + 1] - rr.y) * s; v[i + 2] = fr.z + (v[i + 2] - rr.z) * s;
          }
          return out;
        }).filter((t) => rest[t.name.split('.')[0]]);
        return new THREE.AnimationClip(c.name, c.duration, tracks);
      });
      root.userData.clipCache[key] = clips;
    }
    this.figureClips = clips;
    this.mixer = new THREE.AnimationMixer(root);
    this.playClip(this.clipName ?? 'idle_shift');
  }
  playClip(name) {
    this.clipName = name;
    if (!this.mixer || !this.figureClips) return;
    const c = this.figureClips.find((x) => x.name === name) ?? this.figureClips[0];
    if (!c) return;
    const a = this.mixer.clipAction(c);
    if (this.action && this.action !== a) { a.reset().play(); this.action.crossFadeTo(a, 0.25, false); }
    else a.reset().play();
    this.action = a;
  }

  // ---------- loop ----------
  resize() {
    const el = this.canvas.parentElement ?? this.canvas;
    const w = Math.max(1, el.clientWidth), h = Math.max(1, el.clientHeight);
    const dpr = Math.min(devicePixelRatio || 1, 2);
    this.renderer.setPixelRatio(dpr); this.renderer.setSize(w, h, false);
    this.composer.setPixelRatio(dpr); this.composer.setSize(w, h);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    SPRITES.kzPxScale.value = (h * dpr) / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2));
  }
  start() {
    if (this.running) return;
    this.running = true;
    this.lastT = performance.now();
    const loop = () => {
      if (!this.running) return;
      this.raf = requestAnimationFrame(loop);
      this.renderFrame();
    };
    loop();
  }
  stop() { this.running = false; cancelAnimationFrame(this.raf); }
  renderFrame() {
    const now = performance.now();
    const dt = Math.min((now - this.lastT) / 1000, 0.1);
    this.lastT = now;
    this.t += dt;
    KZ.kzTime.value = this.t;
    this.controls.update(dt);
    this.mixer?.update(dt);
    this.renderer.info.reset();
    this.composer.render(dt);
    const info = this.renderer.info.render;
    // the output pass is one full-screen triangle
    this.frameStats.calls = Math.max(0, info.calls - 1);
    this.frameStats.tris = Math.max(0, info.triangles - 1);
    this.frameStats.points = info.points; this.frameStats.lines = info.lines;
    this._fpsN++; this._fpsT += dt;
    if (this._fpsT > 0.5) { this.frameStats.fps = this._fpsN / this._fpsT; this._fpsN = 0; this._fpsT = 0; }
    this.onStats(this.frameStats);
    for (const w of this.frameWaiters ?? []) w.n--;
    const done = (this.frameWaiters ?? []).filter((w) => w.n <= 0);
    this.frameWaiters = (this.frameWaiters ?? []).filter((w) => w.n > 0);
    done.forEach((w) => w.r());
  }
  frames(n = 1) {
    if (!this.running) { for (let i = 0; i < n; i++) this.renderFrame(); return Promise.resolve(); }
    return new Promise((r) => (this.frameWaiters ??= []).push({ n, r }));
  }
  // model-only stats: geometry triangles (what the GLB holds) and one frame of the model alone, nothing culled
  // (rendered triangles count double-sided transparent materials twice: three draws them in two passes)
  modelStats() {
    let geoTris = 0, meshes = 0;
    const culled = [];
    this.model?.root.traverse((o) => {
      if (o.isMesh) { const g = o.geometry; geoTris += (g.index ? g.index.count : g.attributes.position.count) / 3; meshes++; }
      if (o.frustumCulled) { culled.push(o); o.frustumCulled = false; }
    });
    const vis = this.stage.visible;
    this.stage.visible = false;
    this.renderFrame();
    const s = { ...this.frameStats, geoTris, meshes };
    this.stage.visible = vis;
    for (const o of culled) o.frustumCulled = true;
    return s;
  }
}

function makeSilhouette() {
  // 1.7 m person: legs, torso, arms, head as flat dark shapes (reads as a scale figure from every side)
  const g = new THREE.Group();
  const m = new THREE.MeshBasicMaterial({ color: 0x8a7a68, transparent: true, opacity: 0.42, depthWrite: false });
  const add = (geo, x, y, z = 0) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); g.add(o); return o; };
  add(new THREE.CapsuleGeometry(0.075, 0.68, 4, 12), -0.1, 0.42);
  add(new THREE.CapsuleGeometry(0.075, 0.68, 4, 12), 0.1, 0.42);
  add(new THREE.CapsuleGeometry(0.19, 0.38, 4, 16), 0, 1.12).scale.set(1, 1, 0.6);
  add(new THREE.CapsuleGeometry(0.05, 0.55, 4, 10), -0.27, 1.07).rotation.z = 0.08;
  add(new THREE.CapsuleGeometry(0.05, 0.55, 4, 10), 0.27, 1.07).rotation.z = -0.08;
  add(new THREE.SphereGeometry(0.11, 20, 14), 0, 1.585);
  const tick = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.008), new THREE.MeshBasicMaterial({ color: 0xe8a25c, transparent: true, opacity: 0.8 }));
  tick.position.set(0.3, 1.7, 0); g.add(tick);
  g.name = 'scale_figure_1.7m';
  return g;
}

function kelvin(k) {
  // Tanner Helland approximation, linear-ish
  const t = k / 100;
  const r = t <= 66 ? 255 : 329.7 * (t - 60) ** -0.1332;
  const g = t <= 66 ? 99.47 * Math.log(t) - 161.1 : 288.1 * (t - 60) ** -0.0755;
  const b = t >= 66 ? 255 : t <= 19 ? 0 : 138.5 * Math.log(t - 10) - 305;
  const c = (x) => Math.max(0, Math.min(255, x)) / 255;
  return new THREE.Color().setRGB(c(r), c(g), c(b), THREE.SRGBColorSpace);
}
