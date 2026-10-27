#!/usr/bin/env node
// Node half of tools/export/export_place.py: turns <bake>/dump/ into the place package <bake>/pkg/.
//   node tools/export/pack_place.mjs 3d/bake/<space>/<tier>
// GLBs: EXT_meshopt_compression + KHR_mesh_quantization (web/tools/lib/pack.mjs), content-addressed names.
// KTX2: lightmap RGBM in UASTC LDR (low) or UASTC HDR (high); probes UASTC HDR equirect (both tiers).
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildGLB, writeAddressed, io, weld, meshopt, MeshoptEncoder } from '../../web/tools/lib/pack.mjs';
import * as T from '../../web/tools/lib/textures.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const BAKE = resolve(process.argv[2] ?? '');
const DUMP = join(BAKE, 'dump');
const PKG = join(BAKE, 'pkg');
if (!existsSync(join(DUMP, 'place.json'))) { console.error(`no ${DUMP}/place.json (run export_place.py)`); process.exit(2); }
rmSync(PKG, { recursive: true, force: true });
mkdirSync(join(PKG, 'files'), { recursive: true });
const P = JSON.parse(readFileSync(join(DUMP, 'place.json'), 'utf8'));
const RGBM = { range: 16, gamma: 2 };
const MAX_PART_TRIS = 120000; // ~2 MB per GLB after meshopt
const t0 = Date.now();

function readBin(file, attrs) {
  const buf = readFileSync(join(DUMP, file));
  const out = {};
  for (const [k, a] of Object.entries(attrs)) out[k] = new Float32Array(buf.buffer, buf.byteOffset + a.offset, a.count * a.size).slice();
  return out;
}
const put = (ext, bytes) => writeAddressed(PKG, 'files', ext, bytes).replace(/^files\//, '');
const role = (r) => r ?? 'prop';

// ---- unit vectors for the flow attribute (quantized to normalized shorts) ----
function unitFlow(a) {
  for (let i = 0; i < a.length; i += 2) { const l = Math.hypot(a[i], a[i + 1]); if (l > 1e-6) { a[i] /= l; a[i + 1] /= l; } }
  return a;
}

// ---------------- render parts (+ water) ----------------
const meshes = P.parts.map((p) => {
  const a = readBin(p.file, p.attrs);
  return {
    name: p.name, tris: p.tris, material: { name: p.extras.material },
    attrs: { position: a.position, normal: a.normal, uv0: a.uv0, uv1: a.uv1 },
    custom: a.flow ? { _KZ_FLOW: { type: 'VEC2', array: unitFlow(a.flow) } } : undefined,
    extras: { ...p.extras, role: role(p.extras.role) },
  };
});
const waterMeshes = P.water.map((w) => {
  const a = readBin(w.file, w.attrs);
  return { name: `water_${w.id}`, tris: a.position.length / 9, material: { name: 'water' }, attrs: { position: a.position, normal: a.normal }, extras: { role: 'water', material: 'water', water: w.id } };
});
const chunks = [];
let cur = [], curTris = 0;
for (const m of [...waterMeshes, ...meshes]) {
  if (cur.length && curTris + m.tris > MAX_PART_TRIS) { chunks.push(cur); cur = []; curTris = 0; }
  cur.push(m); curTris += m.tris;
}
if (cur.length) chunks.push(cur);
const parts = [];
for (const c of chunks) {
  const glb = await buildGLB(c, { generator: 'kazanyu-export' });
  parts.push({ uri: put('glb', glb), bytes: glb.byteLength, tris: c.reduce((s, m) => s + m.tris, 0), kind: 'static' });
}

// ---------------- glowworm sprites / threads ----------------
if (P.sprites.sprites || P.sprites.threads) {
  const ms = [];
  if (P.sprites.sprites) {
    const s = new Float32Array(readFileSync(join(DUMP, P.sprites.sprites.file)).buffer.slice(0));
    const n = P.sprites.sprites.count, pos = new Float32Array(n * 3), col = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
      const r = s.subarray(i * 8, i * 8 + 8);
      pos.set(r.subarray(0, 3), i * 3);
      // COLOR_0 = (bright, phase, size / 0.05 m, hz / 0.4 Hz); kind 0.5 (thread bead) is dimmed into bright
      col.set([Math.min(1, r[5] * (r[7] < 0.75 ? 0.45 : 1)), r[4] % 1, Math.min(1, r[3] / 0.05), Math.min(1, r[6] / 0.4)], i * 4);
    }
    ms.push({ name: 'glowworm_points', attrs: { position: pos, color: col }, mode: 'points', extras: { role: 'glowworm', material: '_glowworm', color: P.glow_color } });
  }
  if (P.sprites.threads) {
    const s = new Float32Array(readFileSync(join(DUMP, P.sprites.threads.file)).buffer.slice(0));
    const n = P.sprites.threads.count, pos = new Float32Array(n * 6), col = new Float32Array(n * 8);
    for (let i = 0; i < n; i++) {
      const r = s.subarray(i * 8, i * 8 + 8);
      pos.set(r.subarray(0, 6), i * 6);
      col.set([r[6], 0, 0, 1, r[6] * 0.3, 0, 0, 1], i * 8);
    }
    ms.push({ name: 'glowworm_threads', attrs: { position: pos, color: col }, mode: 'lines', extras: { role: 'glowworm_threads', material: '_glowworm', color: P.glow_color } });
  }
  const glb = await buildGLB(ms, { generator: 'kazanyu-export' });
  parts.push({ uri: put('glb', glb), bytes: glb.byteLength, tris: 0, points: P.sprites.sprites?.count ?? 0, lines: P.sprites.threads?.count ?? 0, kind: 'sprites' });
}

// ---------------- animated objects ----------------
for (const a of P.anims) {
  let glb, tris = 0;
  if (a.kind === 'glb') {
    const doc = await io.read(join(DUMP, a.file));
    for (const n of doc.getRoot().listNodes()) if (n.getMesh()) n.setExtras({ kz: { role: 'anim', anim: a.anim, clips: a.clips } });
    await doc.transform(weld(), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
    glb = await io.writeBinary(doc);
    for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) tris += (p.getIndices()?.getCount() ?? 0) / 3;
  } else {
    const ms = a.prims.map((p, i) => {
      const d = readBin(p.file, p.attrs);
      tris += d.position.length / 9;
      return { name: `${a.name}_${i}`, material: { name: p.material }, attrs: { position: d.position, normal: d.normal, uv0: d.uv0 }, extras: { role: 'anim', material: p.material, anim: a.anim } };
    });
    glb = await buildGLB(ms, { generator: 'kazanyu-export' });
  }
  parts.push({ uri: put('glb', glb), bytes: glb.byteLength, tris, kind: 'anim', name: a.name, clips: a.clips ?? [], note: a.note });
}

// ---------------- walk ----------------
let walk = null;
if (P.walk) {
  const a = readBin(P.walk.file, P.walk.attrs);
  const glb = await buildGLB([{ name: `${P.space}_walk`, attrs: { position: a.position }, extras: { role: 'walk', space: P.space } }], { generator: 'kazanyu-export' });
  walk = { uri: put('glb', glb), bytes: glb.byteLength, tris: a.position.length / 9 };
}

// ---------------- lightmap ----------------
function readF32(file) {
  const j = JSON.parse(readFileSync(join(DUMP, '..', file + '.json'), 'utf8'));
  const b = readFileSync(join(DUMP, '..', file));
  return { ...j, data: new Float32Array(b.buffer, b.byteOffset, j.width * j.height * 3) };
}
const lightmaps = [];
for (const L of P.lightmaps ?? (P.lightmap ? [P.lightmap] : [])) {
  const f = readF32(L.file);
  const W = f.width, H = f.height;
  // rows bottom-first (Blender) -> top-first (glTF v = 0 is the top row; KTX2 is not flipped)
  const E = new Float32Array(W * H * 3);
  for (let y = 0; y < H; y++) E.set(f.data.subarray((H - 1 - y) * W * 3, (H - y) * W * 3), y * W * 3);
  let bytes, encoding;
  // UASTC HDR (the WASM encoder takes at most ~12 Mpix, so bake_place caps the atlas at 2048)
  if (P.tier === 'high') { bytes = await T.encodeHDR(T.writeHDR(W, H, E)); encoding = 'hdr'; }
  else {
    const img = new Uint8Array(W * H * 4);
    for (let i = 0; i < W * H; i++) img.set(T.rgbmEncode([E[i * 3], E[i * 3 + 1], E[i * 3 + 2]], RGBM.range, RGBM.gamma), i * 4);
    bytes = await T.encodeLDR({ data: img, width: W, height: H }, 'linear');
    encoding = 'rgbm';
  }
  lightmaps.push({ id: L.id, uri: put('ktx2', bytes), bytes: bytes.byteLength, encoding, ...(encoding === 'rgbm' ? RGBM : {}), intensity: Math.PI, width: W, height: H, uv: 1, texel_m: L.texel_m });
}
const lightmap = lightmaps[0] ?? null;

// ---------------- probes (equirect, rows bottom-first = three equirectUv with flipY false) ----------------
const probes = [];
for (const p of P.probes) {
  const f = readF32(p.file);
  const bytes = await T.encodeHDR(T.writeHDR(f.width, f.height, f.data));
  probes.push({ id: p.id, space: P.space, center: p.center, box_min: p.box_min, box_max: p.box_max, cubemap: put('ktx2', bytes), projection: 'equirect', bytes: bytes.byteLength, intensity: 1.0, mean: p.mean });
}

// ---------------- lights: every place light. kz_runtime ones light everything live; the baked ones are already in the
// lightmap, so on lightmapped surfaces the runtime uses them for specular only (and fully on unbaked meshes: figures).
// Watts -> three render units: point / spot I = W / 4pi, area (one-sided panel, as a point) I = W / 2pi.
// Baked area lights are left out: as pool points they made hard, over-bright highlights on wet floors (their soft
// reflections come through the probes, which now show lamps); runtime lights always stay.
const lights = P.lights.filter((l) => l.runtime || l.type !== 'area').map((l) => {
  const I = l.watts / ((l.type === 'area' ? 2 : 4) * Math.PI);
  return {
    name: l.name, type: l.type === 'spot' ? 'spot' : 'point', baked: !l.runtime, pos: l.pos, dir: l.dir, color: l.color,
    intensity: +I.toFixed(4), distance: +Math.max(4, Math.sqrt(I / 0.002)).toFixed(2), spot_deg: l.spot_deg,
  };
});
const pkg = {
  contract: 1, space: P.space, tier: P.tier, generated: new Date().toISOString(), bake_generated: P.generated, source: P.source,
  parts, walk, lightmap, lightmaps, probes, lights,
  water: P.water.map((w) => ({ id: w.id, kind: w.kind, z: w.z, bed_z: w.bed_z, bounds: w.bounds, planar: w.planar, absorption: w.absorption, flow: w.flow, material: w.material })),
  materials: P.materials, fx: P.fx, cameras: P.cameras, standin_walk: P.standin_walk ?? [], all_lights: P.lights.length,
  stats: { tris: parts.reduce((s, p) => s + p.tris, 0), bytes: parts.reduce((s, p) => s + p.bytes, 0) + (walk?.bytes ?? 0) + lightmaps.reduce((s, l) => s + l.bytes, 0) + probes.reduce((s, p) => s + p.bytes, 0), seconds: (Date.now() - t0) / 1000 },
};
writeFileSync(join(PKG, 'place.json'), JSON.stringify(pkg, null, 1));
console.log(`[pack] ${P.space}/${P.tier}: ${parts.length} GLBs (${pkg.stats.tris} tris), walk ${walk?.tris ?? 0} tris, lightmaps ${lightmaps.map((l) => `${l.width}^2 ${l.encoding}`).join(' + ') || 'none'}, ${probes.length} probes, ${lights.filter((l) => !l.baked).length} runtime + ${lights.filter((l) => l.baked).length} baked lights, ${(pkg.stats.bytes / 1048576).toFixed(2)} MB, ${pkg.stats.seconds.toFixed(1)} s -> ${PKG}`);
