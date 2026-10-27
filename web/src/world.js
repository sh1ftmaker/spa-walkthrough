// World: zone loading/visibility, material binding, water, probes, per-frame fog/probe uniforms.
import * as THREE from 'three';
import { KZ, MaterialLibrary } from './materials.js';
import { createWaterMeshes } from './water.js';
import { spriteMaterial } from './sprites.js';
import { l2t, boundsToXZ } from './coords.js';
import { FOG } from './config.js';

const SINGLE_SIDED = new Set(['floor', 'wall', 'ceiling', 'rock', 'basin', 'stair']);

export class World {
  constructor(renderer, scene, assets, manifest, env, tier = 'low') {
    this.renderer = renderer; this.scene = scene; this.assets = assets; this.m = manifest; this.env = env; this.tier = tier;
    this.mixers = []; this.liveLights = []; this.fxMist = []; this.sprites = [];
    this.zones = new Map(); // id -> {def, state, group, walkGeo, probes}
    for (const z of manifest.zones) this.zones.set(z.id, { def: z, state: 'idle', group: null, promise: null });
    // water ids resolve per zone first (a stand-in remnant and a Blender place may share a layout water id)
    this.waterDefs = new Map((manifest.water ?? []).flatMap((w) => [[`${w.zone}|${w.id}`, w], [w.id, w]]).reverse());
    this.waterObjs = []; // groups
    this.probes = [];
    this.onZoneLoaded = () => {};
    this.ceilings = [];
  }
  async init() {
    const tex = await this.assets.libraryTextures(this.m);
    this.lib = new MaterialLibrary(this.m, tex, this.env, this.tier);
    this.waterNormal = tex[this.m.materials.water?.normalTexture] ?? null;
    if (this.waterNormal) { this.waterNormal.wrapS = this.waterNormal.wrapT = THREE.RepeatWrapping; this.waterNormal.colorSpace = THREE.NoColorSpace; }
  }
  zoneOfSpace(spaceId) { for (const z of this.zones.values()) if (z.def.spaces.includes(spaceId)) return z.def.id; return null; }

  load(id) {
    const z = this.zones.get(id);
    if (!z) return Promise.reject(new Error(`unknown zone ${id}`));
    if (z.promise) return z.promise;
    z.state = 'loading';
    z.promise = this.assets.zone(z.def).then((res) => { this.build(z, res); z.state = 'ready'; this.onZoneLoaded(z); return z; })
      .catch((e) => { z.state = 'failed'; throw e; });
    return z.promise;
  }

  build(z, { parts, walk, lightmaps }) {
    const g = new THREE.Group();
    g.name = `zone_${z.def.id}`;
    const lmById = new Map();
    (z.def.lightmaps ?? []).forEach((info, i) => {
      const t = lightmaps[i];
      t.colorSpace = THREE.NoColorSpace;
      t.channel = info.uv ?? 1;
      t.flipY = false;
      lmById.set(info.id, { tex: t, info });
    });
    for (const gl of parts) {
      gl.scene.updateMatrixWorld(true);
      const meshes = [];
      gl.scene.traverse((o) => { if (o.isMesh || o.isPoints || o.isLine) meshes.push(o); });
      for (const mesh of meshes) {
        const kz = mesh.userData.kz ?? mesh.parent?.userData?.kz ?? {};
        mesh.userData.kz = kz;
        if (kz.role === 'glowworm' || kz.role === 'glowworm_threads') {
          mesh.material = spriteMaterial(kz.color, kz.role === 'glowworm_threads');
          mesh.frustumCulled = false; mesh.renderOrder = 12;
          mesh.matrixAutoUpdate = false;
          this.sprites.push(mesh);
          continue;
        }
        if (kz.role === 'water' || kz.material === 'water') {
          const info = this.waterDefs.get(`${z.def.id}|${kz.water}`) ?? this.waterDefs.get(kz.water);
          if (!info) { console.warn(`[kz] water mesh ${mesh.name} has no manifest water entry "${kz.water}"`); continue; }
          const geo = worldGeometry(mesh, true);
          const w = createWaterMeshes(geo, info, this.waterNormal, this.env);
          w.userData.zone = z.def.id;
          g.add(w);
          this.waterObjs.push(w);
          mesh.removeFromParent();
          continue;
        }
        const lm = kz.lightmap ? lmById.get(kz.lightmap) : null;
        if (kz.lightmap && !lm) console.warn(`[kz] ${mesh.name}: lightmap ${kz.lightmap} not in zone ${z.def.id}`);
        try {
          const mname = kz.material && this.m.materials[kz.material] ? kz.material : mesh.material.name;
          const isKz = this.m.materials[mname]?.type === 'kz';
          const side = isKz ? (SINGLE_SIDED.has(kz.role) ? THREE.FrontSide : THREE.DoubleSide) : mesh.material.side;
          mesh.material = this.lib.get(mname, { lightMap: lm?.tex ?? null, lightMapInfo: lm?.info ?? null, side, flow: !!mesh.geometry.attributes._kz_flow });
        } catch (e) {
          console.error(`[kz] ${mesh.name}: ${e.message}`);
        }
        if (!mesh.isSkinnedMesh) mesh.matrixAutoUpdate = false;
        if (kz.role === 'ceiling') this.ceilings.push(mesh);
      }
      if (gl.animations?.length) {
        const mixer = new THREE.AnimationMixer(gl.scene);
        const clip = gl.animations.find((c) => /idle|loop|float|soak/i.test(c.name)) ?? gl.animations[0];
        mixer.clipAction(clip).play();
        mixer.setTime(Math.random() * clip.duration);
        this.mixers.push({ mixer, zone: z.def.id, clips: gl.animations.map((c) => c.name) });
      }
      g.add(gl.scene);
    }
    // walk mesh: world-space positions
    const wg = [];
    walk.scene.updateMatrixWorld(true);
    walk.scene.traverse((o) => { if (o.isMesh) wg.push(worldGeometry(o, false)); });
    z.walkGeos = wg;
    z.group = g;
    g.visible = false;
    g.traverse((o) => { o.frustumCulled = true; });
    this.scene.add(g);
    // live lights (kz_runtime) and mist emitters, in three space
    for (const l of z.def.lights ?? []) this.liveLights.push({ ...l, zone: z.def.id, p: l2t(l.pos), c: new THREE.Color().setRGB(...l.color, THREE.LinearSRGBColorSpace) });
    for (const f of z.def.fx ?? []) {
      if (!/mist|steam|fog/i.test(f.kind)) continue;
      const r = Number(f.params?.radius ?? (f.kind === 'mist' ? 6 : 1.5)), q = l2t(f.pos);
      this.fxMist.push({ zone: z.def.id, x0: q.x - r, z0: q.z - r, x1: q.x + r, z1: q.z + r, y: q.y, mist: Number(f.params?.density ?? (f.kind === 'mist' ? 1 : 0.5)) });
    }
    // probes (layout -> three)
    for (const p of z.def.probes ?? []) {
      const a = l2t(p.box_min), b = l2t(p.box_max);
      this.probes.push({
        id: p.id, space: p.space, zone: z.def.id, intensity: p.intensity ?? 1, mean: p.mean ?? null,
        center: l2t(p.center), min: new THREE.Vector3(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.min(a.z, b.z)), max: new THREE.Vector3(Math.max(a.x, b.x), Math.max(a.y, b.y), Math.max(a.z, b.z)),
        tex: this.env, // stub until the real cubemap (p.cubemap) has loaded
      });
      if (p.cubemap) {
        const probe = this.probes[this.probes.length - 1];
        this.assets.texture(p.cubemap).then((cube) => {
          this.pmrem ??= new THREE.PMREMGenerator(this.renderer);
          // roughness-prefiltered (GGX) at load time; equirect probes (Blender places) are 1024 x 512 -> 256 px cube faces
          probe.tex = (p.projection === 'equirect' ? this.pmrem.fromEquirectangular(cube) : this.pmrem.fromCubemap(cube)).texture;
          cube.dispose();
        }).catch((e) => console.error(`[kz] probe ${p.id}: ${e.message}`));
      }
    }
    // compile now so the first visible frame does not hitch
    this.renderer.compile(g, new THREE.PerspectiveCamera());
  }

  update(dt) {
    for (const m of this.mixers) if (this.zones.get(m.zone)?.group?.visible) m.mixer.update(dt);
  }
  // nearest runtime lights of the visible zones -> the fixed light pool (constant light count: no recompiles)
  assignLights(pool, camPos, camDir) {
    if (camDir) (this._fwd ??= new THREE.Vector3()).copy(camDir);
    if (!pool.length) return;
    const vis = new Set(this.visibleIds ?? []);
    // rank by what the camera can notice: intensity over distance (not squared: lamps that rake a far wall matter for
    // its wet-rock highlights), lights in front of the camera first, runtime lights first
    const fwd = this._fwd ?? (this._fwd = new THREE.Vector3());
    const c = this.liveLights.filter((l) => vis.has(l.zone)).map((l) => {
      const dx = l.p.x - camPos.x, dy = l.p.y - camPos.y, dz = l.p.z - camPos.z, d = Math.hypot(dx, dy, dz) + 1e-3;
      const front = (dx * fwd.x + dy * fwd.y + dz * fwd.z) / d > -0.2 ? 1 : 0.25;
      return { l, d: -(l.intensity / (1 + d)) * front * (l.baked ? 1 : 4) };
    }).sort((a, b) => a.d - b.d);
    pool.forEach((pl, i) => {
      const e = c[i]?.l;
      if (!e) { pl.intensity = 0; return; }
      pl.position.copy(e.p); pl.color.copy(e.c); pl.intensity = e.intensity; pl.distance = e.distance ?? 0;
    });
  }

  walkParts() {
    const out = [];
    for (const z of this.zones.values()) if (z.state === 'ready') for (const geometry of z.walkGeos) out.push({ zone: z.def.id, geometry });
    return out;
  }
  loadedIds() { return [...this.zones.values()].filter((z) => z.state === 'ready').map((z) => z.def.id); }

  setVisible(ids) {
    const set = new Set(ids);
    for (const z of this.zones.values()) if (z.group) z.group.visible = set.has(z.def.id);
    this.visibleIds = [...set].filter((id) => this.zones.get(id)?.state === 'ready');
  }
  neighborsReady(id) {
    const z = this.zones.get(id);
    return !z || z.def.neighbors.every((n) => this.zones.get(n)?.state === 'ready');
  }

  // per-frame: nearest waters for mist, nearest two probes for reflections
  updateUniforms(camPos, t) {
    KZ.kzTime.value = t;
    const ws = [];
    for (const w of this.waterObjs) {
      if (!w.parent?.visible) continue;
      const info = w.userData.kzWater;
      const [x0, z0, x1, z1] = boundsToXZ(info.bounds);
      const y = info.z;
      const dx = Math.max(x0 - camPos.x, 0, camPos.x - x1), dz = Math.max(z0 - camPos.z, 0, camPos.z - z1);
      const d = Math.hypot(dx, dz, Math.max(0, Math.abs(camPos.y - y) - 3));
      if (d < 120) ws.push({ d, x0, z0, x1, z1, y, mist: info.mist ?? 1 });
    }
    for (const f of this.fxMist) {
      if (!this.zones.get(f.zone)?.group?.visible) continue;
      const dx = Math.max(f.x0 - camPos.x, 0, camPos.x - f.x1), dz = Math.max(f.z0 - camPos.z, 0, camPos.z - f.z1);
      const d = Math.hypot(dx, dz, Math.max(0, Math.abs(camPos.y - f.y) - 3));
      if (d < 120) ws.push({ d, ...f, mist: -Math.abs(f.mist) }); // negative: patch (see FOG_PARS)
    }
    ws.sort((a, b) => a.d - b.d);
    const n = Math.min(ws.length, FOG.maxWaters);
    for (let i = 0; i < n; i++) {
      KZ.kzWaterRect.value[i].set(ws[i].x0, ws[i].z0, ws[i].x1, ws[i].z1);
      KZ.kzWaterY.value[i] = ws[i].y; KZ.kzWaterMist.value[i] = ws[i].mist;
    }
    KZ.kzWaterCount.value = n;
    // probes
    const box = (p) => {
      const dx = Math.max(p.min.x - camPos.x, 0, camPos.x - p.max.x), dy = Math.max(p.min.y - camPos.y, 0, camPos.y - p.max.y), dz = Math.max(p.min.z - camPos.z, 0, camPos.z - p.max.z);
      return Math.hypot(dx, dy, dz);
    };
    let A = null, B = null, dA = Infinity, dB = Infinity;
    for (const p of this.probes) {
      let d = box(p);
      if (d === 0) d = -1 / ((p.max.x - p.min.x) * (p.max.z - p.min.z) + 1); // inside: prefer the smallest box
      if (d < dA) { B = A; dB = dA; A = p; dA = d; } else if (d < dB) { B = p; dB = d; }
    }
    if (A) {
      const ua = Math.max(0, dA), ub = Math.max(0, dB);
      KZ.kzProbeAMin.value.copy(A.min); KZ.kzProbeAMax.value.copy(A.max); KZ.kzProbeACenter.value.copy(A.center);
      const Bp = B ?? A;
      KZ.kzProbeBMin.value.copy(Bp.min); KZ.kzProbeBMax.value.copy(Bp.max); KZ.kzProbeBCenter.value.copy(Bp.center);
      KZ.kzEnvB.value = Bp.tex;
      KZ.kzProbeBlend.value = B ? (ua + ub > 0 ? ua / (ua + ub) : 0) : 0;
      KZ.kzProbeIntensity.value = A.intensity;
      // haze and mist are lit by the room: baked probes carry their mean radiance; stand-in probes keep the defaults
      const mean = A.mean ? A.mean.map((c, i) => (B?.mean ? c + (B.mean[i] - c) * KZ.kzProbeBlend.value : c)) : null;
      const k = Math.min(1, 0.05 * (this.dtFog ?? 0.016) * 60);
      for (const [u, def, gain] of [[KZ.kzFogColor, FOG.color, FOG.hazeFromProbe], [KZ.kzMistColor, FOG.mistColor, FOG.mistFromProbe]]) {
        // mist: the probe's luminance in a cool neutral (steam reads grey-blue against the black water, not brown)
        const lum = mean ? 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2] : 0;
        const tr = !mean ? def : u === KZ.kzMistColor ? FOG.mistTint.map((c) => c * lum * gain) : mean.map((c) => c * gain);
        u.value.r += (tr[0] - u.value.r) * k; u.value.g += (tr[1] - u.value.g) * k; u.value.b += (tr[2] - u.value.b) * k;
      }
      this.probeA = A.id; this.probeB = B?.id ?? null;
      if (A.tex !== this.envA) {
        // swap the primary probe on every library material (same PMREM size -> no recompile)
        this.envA = A.tex;
        for (const m of this.lib.cache.values()) if (m.envMap) m.envMap = A.tex;
        for (const w of this.waterObjs) w.userData.uniforms.envMap.value = A.tex;
      }
    }
  }
}

// Dequantize (KHR_mesh_quantization / meshopt) into float32 world-space geometry.
function worldGeometry(mesh, withNormals) {
  const src = mesh.geometry, g = new THREE.BufferGeometry();
  const p = src.attributes.position, arr = new Float32Array(p.count * 3);
  for (let i = 0; i < p.count; i++) { arr[i * 3] = p.getX(i); arr[i * 3 + 1] = p.getY(i); arr[i * 3 + 2] = p.getZ(i); }
  g.setAttribute('position', new THREE.BufferAttribute(arr, 3));
  if (src.index) g.setIndex(new THREE.BufferAttribute(Uint32Array.from(src.index.array), 1));
  g.applyMatrix4(mesh.matrixWorld);
  if (withNormals) g.computeVertexNormals();
  return g;
}
