#!/usr/bin/env node
// Node half of tools/export/export_gallery.py: .scratch/gallery/dump/ -> web/public/gallery/.
//   node tools/export/gallery_pack.mjs <dump> <out>          (run from web/ so node_modules resolve)
// GLBs: EXT_meshopt_compression + KHR_mesh_quantization through web/tools/lib/pack.mjs (the same writer as the place
// packages), content-addressed under parts/. Library materials become manifest entries of "type": "kz" exactly as
// web/tools/build-mixed.mjs writes them (src/kzlib.js renders them), with the library KTX2 copied to tex/.
// Writes data/index.json (models) and data/materials.json (library), then removes files nothing references.
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, rmSync, statSync } from 'node:fs';
import { join, resolve, basename } from 'node:path';
import { buildGLB, writeAddressed, io, weld, meshopt, MeshoptEncoder } from '../../web/tools/lib/pack.mjs';

const DUMP = resolve(process.argv[2] ?? '');
const OUT = resolve(process.argv[3] ?? '');
const ROOT = resolve(DUMP, '..', '..', '..');
if (!existsSync(join(DUMP, 'meta.json'))) { console.error(`no ${DUMP}/meta.json (run export_gallery.py)`); process.exit(2); }
mkdirSync(join(OUT, 'data'), { recursive: true });
const t0 = Date.now();
const META = JSON.parse(readFileSync(join(DUMP, 'meta.json'), 'utf8'));
const LIB = JSON.parse(readFileSync(join(ROOT, '3d/materials.json'), 'utf8'));
const LIBM = new Map(LIB.materials.map((m) => [m.id, m]));
const warnings = [];
const warn = (m) => { warnings.push(m); console.warn('  warn:', m); };

// ---------------- library materials (same entry layout as web/tools/build-mixed.mjs kzMaterial) ----------------
const textures = {};
const texCache = new Map();
function libTexture(rel, colorSpace) {
  const key = `${rel}|${colorSpace}`;
  if (texCache.has(key)) return texCache.get(key);
  const src = join(ROOT, '3d', rel);
  if (!existsSync(src)) { warn(`library texture missing: ${rel}`); texCache.set(key, null); return null; }
  const uri = writeAddressed(OUT, 'tex', 'ktx2', readFileSync(src));
  const ent = { id: `lib:${basename(rel, '.ktx2')}`, def: { uri, colorSpace, codec: 'uastc', source: rel, bytes: statSync(src).size } };
  texCache.set(key, ent);
  return ent;
}
function kzMaterial(m) {
  const d = LIBM.get(m.id);
  const out = { type: 'kz', id: m.id, params: { ...(d?.params ?? {}), ...(m.params ?? {}) }, lightmap: false, maps: {}, kit: {} };
  if (!d) { warn(`kz_id ${m.id} is not in 3d/materials.json`); return { type: 'standard', id: m.id, color: [0.5, 0.5, 0.5], roughness: 0.8, lightmap: false }; }
  const c = d.constants ?? {}, t = d.three ?? {};
  out.lib = {
    tiling: d.tiling_m_per_repeat ?? null, aspect: d.aspect ?? 1, uv_mode: d.uv_mode ?? 'metric', tech: d.kzTech ?? null,
    porosity: c.Porosity, worn: { color: c.WornColor, rough: c.WornRough }, emissive: d.emissive ? { map_scale: d.emissive.map_scale ?? 1, color: d.emissive.color_linear ?? [1, 1, 1], strength: d.emissive.strength ?? 1, emit_core: d.emissive.emit_core ?? 0 } : null,
    alphaTest: t.alphaTest ?? (c.AlphaFromMask > 0 && !t.transparent ? 0.5 : null), doubleSided: t.side === 'DoubleSide', transparent: !!t.transparent,
    envMapIntensity: t.envMapIntensity ?? 1, roughness: d.stats?.mean_roughness ?? null,
  };
  const add = (slot, rel, cs, into) => { if (!rel) return; const x = libTexture(rel, cs); if (x) { textures[x.id] = x.def; into[slot] = x.id; } };
  if (d.kzTech && d.kzBase) {
    add('base', d.kzBase, 'srgb', out.kit); add('nh', d.kzNh, 'linear', out.kit);
    add('base2', d.kzBase2, 'srgb', out.kit); add('nh2', d.kzNh2, 'linear', out.kit);
    add('noise', d.kzNoise, 'linear', out.kit);
  } else {
    add('base', d.textures?.base, 'srgb', out.maps); add('orm', d.textures?.orm, 'linear', out.maps);
    add('nh', d.textures?.normal_height, 'linear', out.maps);
  }
  if (d.textures?.emissive) add('emis', d.textures.emissive, 'srgb', out.maps);
  return out;
}
// one table for every model: Blender names (<kz_id>~<hash>) are the keys; the same name with other params in another
// asset file gets "@<asset>" so no model ever renders with another one's settings
const materials = { _glowworm: { type: 'sprite', lightmap: false } };
const matSig = new Map();
function matKey(name, m, asset) {
  const sig = JSON.stringify([m.id, m.params]);
  if (!matSig.has(name)) { matSig.set(name, sig); materials[name] = kzMaterial(m); return name; }
  if (matSig.get(name) === sig) return name;
  const k = `${name}@${asset}`;
  if (!matSig.has(k)) { matSig.set(k, sig); materials[k] = kzMaterial(m); }
  return k;
}

// ---------------- helpers ----------------
const put = (bytes) => writeAddressed(OUT, 'parts', 'glb', bytes);
function readBin(dir, file, attrs) {
  const buf = readFileSync(join(dir, file));
  const out = {};
  for (const [k, a] of Object.entries(attrs)) out[k] = new Float32Array(buf.buffer, buf.byteOffset + a.offset, a.count * a.size).slice();
  return out;
}
function unitFlow(a) {
  for (let i = 0; i < a.length; i += 2) { const l = Math.hypot(a[i], a[i + 1]); if (l > 1e-6) { a[i] /= l; a[i + 1] /= l; } }
  return a;
}
// glowworm points / threads and stars (same COLOR_0 packing as tools/export/pack_place.mjs, contract §15.4)
function spriteMeshes(dir, sp, color) {
  const ms = [];
  if (sp.sprites) {
    const s = new Float32Array(readFileSync(join(dir, sp.sprites.file)).buffer.slice(0));
    const n = sp.sprites.count, pos = new Float32Array(n * 3), col = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
      const r = s.subarray(i * 8, i * 8 + 8);
      pos.set(r.subarray(0, 3), i * 3);
      col.set([Math.min(1, r[5] * (r[7] < 0.75 ? 0.45 : 1)), r[4] % 1, Math.min(1, r[3] / 0.05), Math.min(1, r[6] / 0.4)], i * 4);
    }
    ms.push({ name: 'glowworm_points', attrs: { position: pos, color: col }, mode: 'points', extras: { role: 'glowworm', material: '_glowworm', color } });
  }
  if (sp.threads) {
    const s = new Float32Array(readFileSync(join(dir, sp.threads.file)).buffer.slice(0));
    const n = sp.threads.count, pos = new Float32Array(n * 6), col = new Float32Array(n * 8);
    for (let i = 0; i < n; i++) {
      const r = s.subarray(i * 8, i * 8 + 8);
      pos.set(r.subarray(0, 6), i * 6);
      col.set([r[6], 0, 0, 1, r[6] * 0.3, 0, 0, 1], i * 8);
    }
    ms.push({ name: 'glowworm_threads', attrs: { position: pos, color: col }, mode: 'lines', extras: { role: 'glowworm_threads', material: '_glowworm', color } });
  }
  return ms;
}
function glbJson(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const len = dv.getUint32(12, true);
  return JSON.parse(new TextDecoder().decode(bytes.subarray(20, 20 + len)));
}
function summarizeAnim(a) {
  if (a == null) return null;
  if (typeof a !== 'object') return { type: String(a) };
  const out = { type: a.type ?? (Object.keys(a).join('+') || 'none') };
  for (const k of ['what', 'pose', 'clips', 'note', 'fx', 'mode', 'speed_mps', 'period_s', 'hz']) if (a[k] != null) out[k] = a[k];
  return out;
}
function summarizeLights(L) {
  if (!Array.isArray(L) || !L.length) return null;
  const kinds = {};
  let watts = 0;
  for (const l of L) { const k = l.kind ?? l.type ?? 'point'; kinds[k] = (kinds[k] ?? 0) + 1; watts += Number(l.watts ?? 0) || 0; }
  const pts = L.filter((l) => /point|spot/.test(l.kind ?? l.type ?? 'point') && Array.isArray(l.pos)).map((l) => ({
    kind: l.kind ?? l.type ?? 'point', pos: l.pos, watts: Number(l.watts ?? 0) || null, color: l.color ?? null, kelvin: l.color_k ?? null, radius: l.radius ?? null,
  }));
  return { count: L.length, kinds, watts: Math.round(watts * 10) / 10, points: pts.slice(0, 24) };
}
function summarizeFx(F) {
  if (F == null) return null;
  const arr = Array.isArray(F) ? F : [F];
  const kinds = {};
  for (const f of arr) { const k = typeof f === 'string' ? f : (f.kind ?? f.type ?? f.fx ?? 'fx'); kinds[k] = (kinds[k] ?? 0) + 1; }
  return { count: arr.length, kinds };
}

// ---------------- models ----------------
const assets = [];
const ids = Object.keys(META.assets).sort();
let totalGlb = 0;
for (const id of ids) {
  const meta = META.assets[id];
  const dir = join(DUMP, id);
  const rec = existsSync(join(dir, 'asset.json')) ? JSON.parse(readFileSync(join(dir, 'asset.json'), 'utf8')) : { variants: [], materials: {}, errors: ['no dump'] };
  const variants = [];
  const usedMats = new Set();
  for (const v of rec.variants) {
    let glb, tris = 0, draws = 0, bbox = v.bbox ?? null, points = 0, lines = 0;
    if (v.kind === 'skinned') {
      const doc = await io.read(join(dir, v.file));
      for (const m of doc.getRoot().listMaterials()) {
        const src = rec.materials[m.getName()];
        if (src) { const k = matKey(m.getName(), src, id); m.setName(k); usedMats.add(k); } else warn(`${id}: skinned material ${m.getName()} not in the dump`);
      }
      for (const n of doc.getRoot().listNodes()) if (n.getMesh()) n.setExtras({ kz: { role: 'anim', anim: { type: 'skinned' } } });
      await doc.transform(weld(), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
      glb = await io.writeBinary(doc);
      for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) { tris += (p.getIndices()?.getCount() ?? 0) / 3; draws++; }
      let mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) {
        const a = p.getAttribute('POSITION'); const lo = a.getMinNormalized([]), hi = a.getMaxNormalized([]);
        for (let i = 0; i < 3; i++) { mn[i] = Math.min(mn[i], lo[i]); mx[i] = Math.max(mx[i], hi[i]); }
      }
      bbox = { w: +(mx[0] - mn[0]).toFixed(4), d: +(mx[2] - mn[2]).toFixed(4), h: +(mx[1] - mn[1]).toFixed(4), zmin: +mn[1].toFixed(4), min: mn, max: mx, note: 'bind pose' };
    } else {
      const ms = v.prims.map((p, i) => {
        const a = readBin(dir, p.file, p.attrs);
        const src = rec.materials[p.material];
        const key = src ? matKey(p.material, src, id) : p.material;
        if (!src) warn(`${id} LOD${v.lod} s${v.seed}: material ${p.material} has no kz_id`);
        usedMats.add(key);
        tris += p.tris; draws++;
        return {
          name: `${id}_${i}`, material: { name: key }, attrs: { position: a.position, normal: a.normal, uv0: a.uv0 },
          custom: a.flow ? { _KZ_FLOW: { type: 'VEC2', array: unitFlow(a.flow) } } : undefined,
          extras: { role: 'prop', material: key },
        };
      });
      if (v.sprites) {
        const sm = spriteMeshes(dir, v.sprites, v.glow_color);
        ms.push(...sm); draws += sm.length;
        points = v.sprites.sprites?.count ?? 0; lines = v.sprites.threads?.count ?? 0;
      }
      glb = await buildGLB(ms, { generator: 'kazanyu-gallery' });
    }
    const uri = put(glb);
    totalGlb += glb.byteLength;
    variants.push({ lod: v.lod, seed: v.seed, uri, bytes: glb.byteLength, tris, draws, bbox, points, lines, kind: v.kind, ...(v.sprites?.sprites?.stars ? { stars: v.sprites.sprites.stars } : {}) });
  }
  for (const e of rec.errors ?? []) warn(`${id}: ${e}`);
  const v0 = variants.find((v) => v.lod === 0 && v.seed === 1);
  const libIds = [...new Set([...usedMats].map((k) => materials[k]?.id).filter(Boolean))].sort();
  assets.push({
    ...meta, materials_used: [...usedMats].sort(), library_ids: libIds,
    variants, tris_lod0: v0?.tris ?? 0, bytes: variants.reduce((s, v) => s + v.bytes, 0),
    kz_anim: summarizeAnim(rec.kz_anim), kz_lights: summarizeLights(rec.kz_lights), kz_fx: summarizeFx(rec.kz_fx),
    features_list: Array.isArray(rec.kz_features) ? rec.kz_features : [],
    skinned: !!rec.skinned, errors: rec.errors ?? [],
  });
  process.stdout.write(`\r[pack] ${assets.length}/${ids.length} ${id}                 `);
}
process.stdout.write('\n');

// ---------------- shared figure clips ----------------
let figureClips = null;
const fcDir = join(DUMP, '_figure_clips');
if (existsSync(join(fcDir, 'clips.glb'))) {
  const info = JSON.parse(readFileSync(join(fcDir, 'clips.json'), 'utf8'));
  const doc = await io.read(join(fcDir, 'clips.glb'));
  await doc.transform(meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
  const glb = await io.writeBinary(doc);
  const names = doc.getRoot().listAnimations().map((a) => a.getName());
  figureClips = {
    uri: put(glb), bytes: glb.byteLength, ref_height: info.rig?.height ?? 1.65,
    clips: names.map((n) => ({ name: n, group: info.clips[n]?.group ?? null, duration_s: info.clips[n]?.duration_s ?? null, speed_mps: info.clips[n]?.speed_mps ?? 0, props_bone: info.clips[n]?.props_bone ?? null })),
  };
  totalGlb += glb.byteLength;
}

// ---------------- materials index (library + previews) ----------------
const usedBy = {};
for (const a of assets) for (const id of a.library_ids) (usedBy[id] ??= []).push(a.id);
const lin2srgb = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);
const hex = (rgb) => '#' + rgb.map((c) => Math.round(Math.max(0, Math.min(1, lin2srgb(c))) * 255).toString(16).padStart(2, '0')).join('');
const libList = [];
for (const d of LIB.materials) {
  const previews = META.materials[d.id] ?? {};
  const base = d.params ?? {};
  const albedo = d.stats?.mean_albedo_linear ?? null;
  const swatch = (p) => {
    const t = p.tint ?? [1, 1, 1];
    return { tint_hex: hex(t), albedo_hex: albedo ? hex(albedo.map((x, i) => x * t[i])) : null };
  };
  const key = `lib:${d.id}`;
  materials[key] = kzMaterial({ id: d.id, params: base });
  const variants = Object.entries(d.variants ?? {}).map(([vn, vp]) => {
    const vk = `lib:${d.id}~${vn}`;
    materials[vk] = kzMaterial({ id: d.id, params: { ...base, ...vp } });
    return { name: vn, key: vk, params: vp, ...swatch({ ...base, ...vp }), preview: previews[vn] ?? null };
  });
  // previews of variants the library does not list (e.g. hinoki__wear0.7) are kept as extra shots
  const extra = Object.entries(previews).filter(([k]) => k && !(d.variants ?? {})[k]).map(([k, v]) => ({ name: k, preview: v }));
  libList.push({
    id: d.id, name: d.name, category: d.category, tech: d.kzTech ?? d.kz?.tech ?? null, key, params: base, ...swatch(base),
    mean_albedo_linear: albedo, mean_roughness: d.stats?.mean_roughness ?? null, tiling_m: d.tiling_m_per_repeat ?? null,
    emissive: d.emissive ? { color_linear: d.emissive.color_linear, strength: d.emissive.strength } : null,
    transparent: !!d.transparent, water: !!d.water, preview: previews[''] ?? null, variants, extra_previews: extra,
    concept: d.concept ?? [], reference: d.reference ?? null, source: d.texture_source?.origin ?? null, licence: d.texture_source?.licence ?? null,
    used_by: (usedBy[d.id] ?? []).sort(),
  });
}

// ---------------- write ----------------
const index = {
  contract: 1, generated: new Date().toISOString(), count: assets.length,
  categories: [...new Set(assets.map((a) => a.category))].sort(),
  coords: 'three (Y up); asset pivot at the base centre, front = -Z (Blender +Y)',
  materials_index: 'data/materials.json', figure_clips: figureClips, places: META.places,
  assets,
};
const matsDoc = { contract: 1, generated: index.generated, categories: LIB.categories?.map((c) => ({ id: c.id, label: c.label })) ?? [], sheet: META.material_sheet, library: libList, materials, textures };
writeFileSync(join(OUT, 'data/index.json'), JSON.stringify(index));
writeFileSync(join(OUT, 'data/materials.json'), JSON.stringify(matsDoc));

// ---------------- prune unreferenced content-addressed files ----------------
const refs = new Set();
const walk = (x) => {
  if (typeof x === 'string') { if (/^(parts|tex|img)\/[0-9a-f]{16}\.(glb|ktx2|jpg)$/.test(x)) refs.add(x); return; }
  if (Array.isArray(x)) x.forEach(walk); else if (x && typeof x === 'object') Object.values(x).forEach(walk);
};
walk(index); walk(matsDoc);
let pruned = 0, bytes = 0, files = 0;
for (const sub of ['parts', 'tex', 'img']) {
  const d = join(OUT, sub);
  if (!existsSync(d)) continue;
  for (const f of readdirSync(d)) {
    const rel = `${sub}/${f}`;
    if (!refs.has(rel)) { rmSync(join(d, f)); pruned++; } else { bytes += statSync(join(d, f)).size; files++; }
  }
}
const missing = [...refs].filter((r) => !existsSync(join(OUT, r)));
if (missing.length) { console.error(`[pack] ${missing.length} referenced files missing, e.g. ${missing.slice(0, 5).join(', ')}`); process.exit(3); }
const report = { generated: index.generated, assets: assets.length, variants: assets.reduce((s, a) => s + a.variants.length, 0), glb_bytes: totalGlb, files, bytes, pruned, warnings, seconds: (Date.now() - t0) / 1000 };
writeFileSync(join(DUMP, 'pack-report.json'), JSON.stringify(report, null, 1));
console.log(`[pack] ${report.assets} models, ${report.variants} GLBs (${(totalGlb / 1048576).toFixed(1)} MB), ${Object.keys(textures).length} library textures, ${files} files ${(bytes / 1048576).toFixed(1)} MB, pruned ${pruned}, ${warnings.length} warnings, ${report.seconds.toFixed(1)} s`);
