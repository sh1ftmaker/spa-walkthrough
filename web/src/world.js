// World: zone loading/visibility, material binding, water, probes, per-frame fog/probe uniforms.
import * as THREE from 'three';
import { KZ, MaterialLibrary } from './materials.js';
import { createWaterMeshes } from './water.js';
import { l2t, boundsToXZ } from './coords.js';
import { FOG } from './config.js';

export class World {
  constructor(renderer, scene, assets, manifest, env) {
    this.renderer = renderer; this.scene = scene; this.assets = assets; this.m = manifest; this.env = env;
    this.zones = new Map(); // id -> {def, state, group, walkGeo, probes}
    for (const z of manifest.zones) this.zones.set(z.id, { def: z, state: 'idle', group: null, promise: null });
    this.waterDefs = new Map((manifest.water ?? []).map((w) => [w.id, w]));
    this.waterObjs = []; // groups
    this.probes = [];
    this.onZoneLoaded = () => {};
    this.ceilings = [];
  }
  async init() {
    const tex = await this.assets.libraryTextures(this.m);
    this.lib = new MaterialLibrary(this.m, tex, this.env);
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
      gl.scene.traverse((o) => { if (o.isMesh) meshes.push(o); });
      for (const mesh of meshes) {
        const kz = mesh.userData.kz ?? mesh.parent?.userData?.kz ?? {};
        mesh.userData.kz = kz;
        if (kz.role === 'water' || kz.material === 'water') {
          const info = this.waterDefs.get(kz.water);
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
          mesh.material = this.lib.get(kz.material ?? mesh.material.name, { lightMap: lm?.tex ?? null, lightMapInfo: lm?.info ?? null, side: mesh.material.side });
        } catch (e) {
          console.error(`[kz] ${mesh.name}: ${e.message}`);
        }
        mesh.matrixAutoUpdate = false;
        if (kz.role === 'ceiling') this.ceilings.push(mesh);
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
    // probes (layout -> three)
    for (const p of z.def.probes ?? []) {
      const a = l2t(p.box_min), b = l2t(p.box_max);
      this.probes.push({
        id: p.id, space: p.space, zone: z.def.id, intensity: p.intensity ?? 1,
        center: l2t(p.center), min: new THREE.Vector3(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.min(a.z, b.z)), max: new THREE.Vector3(Math.max(a.x, b.x), Math.max(a.y, b.y), Math.max(a.z, b.z)),
        tex: this.env, // stub until the real cubemap (p.cubemap) has loaded
      });
      if (p.cubemap) {
        const probe = this.probes[this.probes.length - 1];
        this.assets.texture(p.cubemap).then((cube) => {
          this.pmrem ??= new THREE.PMREMGenerator(this.renderer);
          probe.tex = this.pmrem.fromCubemap(cube).texture; // roughness-prefiltered (GGX) at load time
          cube.dispose();
        }).catch((e) => console.error(`[kz] probe ${p.id}: ${e.message}`));
      }
    }
    // compile now so the first visible frame does not hitch
    this.renderer.compile(g, new THREE.PerspectiveCamera());
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
