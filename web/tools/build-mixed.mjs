#!/usr/bin/env node
// Mixed manifests: Blender place models where a place package exists, the graybox stand-in everywhere else.
//   node tools/build-mixed.mjs [--places auto|g_arrival,b1_mirror] [--bake ../3d/bake] [--pkg b1_mirror=<dir with low/ high/>]
//                              [--out public/assets] [--layout ../3d/layout.json]
// Place packages come from tools/export (bake_place.py -> export_place.py -> pack_place.mjs): <bake>/<space>/<tier>/pkg/.
// Steps: stand-in with --exclude-spaces, copy the package files (already content-addressed), add one zone per place
// ("p_<space>", neighbours = its level zone + that zone's neighbours, and back), library materials (kz_id + kz_params)
// with the library KTX2 they need, water, probes, lights, fx, places / spaces data, then a portal seam check on the
// walk meshes. Without any package it is exactly the stand-in (source "standin").
import { readFileSync, writeFileSync, existsSync, readdirSync, copyFileSync, mkdirSync } from 'node:fs';
import { join, resolve, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { io, writeAddressed } from './lib/pack.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(here, '..');
const ROOT = resolve(WEB, '..');
const argv = process.argv.slice(2);
const opt = {};
const pkgOverride = {};
for (let i = 0; i < argv.length; i++) {
  if (!argv[i].startsWith('--')) continue;
  const k = argv[i].slice(2), v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  if (k === 'pkg') { const [s, d] = String(v).split('='); pkgOverride[s] = resolve(d); } else opt[k] = v;
}
const OUT = resolve(opt.out ?? join(WEB, 'public/assets'));
const BAKE = resolve(opt.bake ?? join(ROOT, '3d/bake'));
const LAYOUT = resolve(opt.layout ?? join(ROOT, '3d/layout.json'));
const L = JSON.parse(readFileSync(LAYOUT, 'utf8'));
const LIB = JSON.parse(readFileSync(join(ROOT, '3d/materials.json'), 'utf8'));
const LIBM = new Map(LIB.materials.map((m) => [m.id, m]));
const TIERS = ['low', 'high'];
const report = { generated: new Date().toISOString(), places: {}, warnings: [], seams: [] };
const warn = (m) => { report.warnings.push(m); console.warn('  warn:', m); };

// ---------------- which places ----------------
const pkgDir = (space, tier) => {
  const base = pkgOverride[space] ?? join(BAKE, space);
  return join(base, tier, 'pkg');
};
let places = [];
if (!opt.places || opt.places === 'auto') {
  const cand = new Set(Object.keys(pkgOverride));
  if (existsSync(BAKE)) for (const d of readdirSync(BAKE)) cand.add(d);
  places = [...cand].filter((s) => TIERS.some((t) => existsSync(join(pkgDir(s, t), 'place.json'))));
} else places = String(opt.places).split(',').map((s) => s.trim()).filter(Boolean);
places = places.filter((s) => {
  if (!L.spaces.some((x) => x.id === s)) { warn(`place package ${s}: no such space in the layout, skipped`); return false; }
  return true;
});
console.log(`mixed build: ${places.length ? places.join(', ') : 'no place packages (stand-in only)'}`);

// ---------------- 1. stand-in without the replaced spaces ----------------
// stand-in spaces under a place's kz_standin walk patches keep their slabs there
const keepSlabs = new Set();
for (const space of places) {
  const dir = TIERS.map((t) => pkgDir(space, t)).find((d) => existsSync(join(d, 'place.json')));
  for (const w of JSON.parse(readFileSync(join(dir, 'place.json'), 'utf8')).standin_walk ?? []) {
    const c = [(w.bounds[0] + w.bounds[2]) / 2, (w.bounds[1] + w.bounds[3]) / 2];
    const fz = L.spaces.find((x) => x.id === space).floor_z;
    for (const s of L.spaces) if (!places.includes(s.id) && Math.abs(s.floor_z - fz) < 1 && pointIn(c, s.footprint)) keepSlabs.add(s.id);
  }
}
if (keepSlabs.size) console.log(`keep stand-in slabs under kz_standin walk patches: ${[...keepSlabs].join(', ')}`);
execFileSync('node', [join(here, 'build-standin.mjs'), '--layout', LAYOUT, '--out', OUT, ...(places.length ? ['--exclude-spaces', places.join(',')] : []),
  ...(keepSlabs.size ? ['--keep-slabs', [...keepSlabs].join(',')] : [])], { stdio: 'inherit' });
if (!places.length) process.exit(0);

// ---------------- helpers ----------------
const spaceFile = (id) => { const f = join(ROOT, '3d/spaces', `${id}.json`); return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : {}; };
const layoutSpace = (id) => L.spaces.find((s) => s.id === id);
const texCache = new Map();
function libTexture(rel, colorSpace) {
  // rel: 'materials/tex/x.ktx2' (relative to 3d/)
  const key = `${rel}|${colorSpace}`;
  if (texCache.has(key)) return texCache.get(key);
  const src = join(ROOT, '3d', rel);
  if (!existsSync(src)) { warn(`library texture missing: ${rel}`); texCache.set(key, null); return null; }
  const uri = writeAddressed(OUT, 'tex', 'ktx2', readFileSync(src));
  const id = `lib:${basename(rel, '.ktx2')}`;
  const ent = { id, def: { uri, colorSpace, codec: 'uastc', source: rel } };
  texCache.set(key, ent);
  return ent;
}
function kzMaterial(name, m, textures) {
  const d = LIBM.get(m.id);
  const out = { type: 'kz', id: m.id, params: { ...(d?.params ?? {}), ...(m.params ?? {}) }, lightmap: true, maps: {}, kit: {} };
  if (d) {
    const c = d.constants ?? {}, t = d.three ?? {};
    out.lib = {
      tiling: d.tiling_m_per_repeat ?? null, aspect: d.aspect ?? 1, uv_mode: d.uv_mode ?? 'metric', tech: d.kzTech ?? null,
      porosity: c.Porosity, worn: { color: c.WornColor, rough: c.WornRough }, emissive: d.emissive ? { map_scale: d.emissive.map_scale ?? 1, color: d.emissive.color_linear ?? [1, 1, 1], strength: d.emissive.strength ?? 1, emit_core: d.emissive.emit_core ?? 0 } : null,
      alphaTest: t.alphaTest ?? (c.AlphaFromMask > 0 && !t.transparent ? 0.5 : null), doubleSided: t.side === 'DoubleSide', transparent: !!t.transparent,
      envMapIntensity: t.envMapIntensity ?? 1, roughness: d.stats?.mean_roughness ?? null,
    };
  }
  if (!d) { warn(`material ${name}: kz_id ${m.id} is not in 3d/materials.json`); out.type = 'standard'; out.color = [0.5, 0.5, 0.5]; out.roughness = 0.8; return out; }
  const add = (slot, rel, cs, into) => { if (!rel) return; const t = libTexture(rel, cs); if (t) { textures[t.id] = t.def; into[slot] = t.id; } };
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
const SCATTER = [0.006, 0.03, 0.028];
function probeLum(P) {
  const ms = P.probes.map((p) => p.mean).filter(Boolean);
  if (!ms.length) return 0.05;
  return ms.reduce((s, m) => s + 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2], 0) / ms.length;
}
function copyPkgFile(dir, f, sub) {
  const src = join(dir, 'files', f);
  const dstRel = `${sub}/${f}`;
  mkdirSync(join(OUT, sub), { recursive: true });
  if (!existsSync(join(OUT, dstRel))) copyFileSync(src, join(OUT, dstRel));
  return dstRel;
}

// ---------------- 2. per tier ----------------
let placesDoc = JSON.parse(readFileSync(join(OUT, 'data/places.json'), 'utf8'));
const lowManifest = JSON.parse(readFileSync(join(OUT, 'manifests/low.json'), 'utf8'));
const spacesDoc = JSON.parse(readFileSync(join(OUT, lowManifest.spaces), 'utf8'));
for (const tier of TIERS) {
  const mf = join(OUT, `manifests/${tier}.json`);
  const M = JSON.parse(readFileSync(mf, 'utf8'));
  const zoneById = new Map(M.zones.map((z) => [z.id, z]));
  const added = [];
  for (const space of places) {
    let dir = pkgDir(space, tier);
    if (!existsSync(join(dir, 'place.json'))) {
      const other = TIERS.find((t) => existsSync(join(pkgDir(space, t), 'place.json')));
      warn(`${space}: no ${tier} package, using ${other}`);
      dir = pkgDir(space, other);
    }
    const P = JSON.parse(readFileSync(join(dir, 'place.json'), 'utf8'));
    const ls = layoutSpace(space), sf = spaceFile(space);
    const baseZone = M.zones.find((z) => z.spaces.includes(space)) ?? zoneById.get(ls.level);
    const zid = `p_${space}`;
    baseZone.spaces = baseZone.spaces.filter((s) => s !== space);
    const xs = ls.footprint.map((p) => p[0]), ys = ls.footprint.map((p) => p[1]);
    const glb = (p) => ({ uri: copyPkgFile(dir, p.uri, 'parts'), bytes: p.bytes, tris: p.tris, ...(p.kind !== 'static' ? { kind: p.kind } : {}), ...(p.clips?.length ? { clips: p.clips } : {}) });
    const z = {
      id: zid, name: ls.name.replace(/^\d\d\s/, ''), source: 'blender', base: baseZone.id,
      neighbors: [], preload: [], spaces: [space],
      bounds: [Math.min(...xs) - 1, Math.min(...ys) - 1, Math.max(...xs) + 1, Math.max(...ys) + 1],
      parts: P.parts.map(glb),
      walk: P.walk ? { uri: copyPkgFile(dir, P.walk.uri, 'parts'), bytes: P.walk.bytes, tris: P.walk.tris } : null,
      lightmaps: (P.lightmaps ?? (P.lightmap ? [P.lightmap] : [])).map((l) => ({ ...l, uri: copyPkgFile(dir, l.uri, 'tex') })),
      probes: P.probes.map((p) => ({ ...p, cubemap: copyPkgFile(dir, p.cubemap, 'tex') })),
      lights: P.lights, fx: P.fx, placements: [],
    };
    if (!z.walk) warn(`${space}: package has no walk mesh`);
    // water
    for (const w of P.water) {
      const sw = (sf.water ?? []).find((x) => x.id === w.id || x.layout_ref === w.id);
      const lw = L.water.find((x) => x.id === w.id || x.id === sw?.layout_ref);
      const temp = sw?.temp ?? lw?.temp;
      // a stand-in remnant of the same layout water (cut at the place footprint) keeps its entry: ids resolve per zone
      M.water.push({
        id: w.id, kind: w.kind, zone: zid, z: +w.z.toFixed(3), bed_z: +(w.bed_z ?? sw?.bed_z ?? (w.z - (sw?.depth ?? 1.2))).toFixed(3),
        bounds: w.bounds.map((v) => +v.toFixed(2)),
        // a planar reflection re-renders the scene: only for large waters (>= 80 m2 of bounds) or the Mirror
        planar: !!w.planar && ((w.bounds[2] - w.bounds[0]) * (w.bounds[3] - w.bounds[1]) >= 80 || w.id === 'w_mirror'),
        // a place that authors its own mist emitters (kz_fx mist) keeps only a thin layer over the whole water
        mist: P.fx.some((f) => /mist/.test(f.kind)) ? 0 : temp != null && (Array.isArray(temp) ? Math.max(...temp) : temp) >= 30 ? 1 : 0.35,
        absorption: w.absorption, flow: w.flow ?? 0,
        // in-scatter follows the room's light (the probe mean), so a dark pool stays black
        // the Obsidian Mirror (water_still variant mirror): a black, dead-still, strongly reflecting surface
        ...(/~mirror$/.test(w.material ?? '') || w.id === 'w_mirror' ? { f0: 0.12, normal_strength: 0.025, reflect_gain: 1.25, absorption: [1.6, 1.1, 0.9], scatter_override: [0, 0, 0] } : {}),
        scatter: SCATTER.map((c) => +(c * Math.min(1, probeLum(P) / 0.05)).toFixed(5)),
        // (the Mirror's override zeroes it below: a black salt pool, no teal glow)
      });
    }
    // materials
    for (const [name, m] of Object.entries(P.materials)) M.materials[name] = kzMaterial(name, m, M.textures);
    M.materials._glowworm = { type: 'sprite', lightmap: false };
    added.push({ z, baseZone });
    // places / spaces (once)
    if (tier === 'low') {
      const pl = placesDoc.places.find((p) => p.id === space);
      // the concept camera is the pose the place was designed around (entry poses could face a post at point-blank range)
      const cam = sf.cameras?.concept ?? P.cameras?.concept ?? sf.cameras?.entry ?? P.cameras?.entry;
      if (pl) {
        pl.zone = zid;
        if (cam) {
          pl.pos = cam.pos.map((v) => +v.toFixed(3));
          pl.yaw_deg = +((((Math.atan2(cam.target[0] - cam.pos[0], cam.target[1] - cam.pos[1]) * 180) / Math.PI) + 360) % 360).toFixed(1);
          pl.pitch_deg = +((Math.atan2(cam.target[2] - cam.pos[2], Math.hypot(cam.target[0] - cam.pos[0], cam.target[1] - cam.pos[1])) * 180) / Math.PI).toFixed(1);
          pl.source = 'place-camera-concept';
        }
      }
      const sp = spacesDoc.spaces.find((s) => s.id === space);
      if (sp) sp.zone = zid;
      report.places[space] = { package: dir, generated: P.generated, tris: P.stats?.tris, bytes: P.stats?.bytes, lightmaps: (P.lightmaps ?? []).map((l) => `${l.id} ${l.width}^2 ${l.encoding} ${l.texel_m ? (l.texel_m * 100).toFixed(1) + ' cm' : ''}`), probes: P.probes.length };
    }
  }
  // neighbours: a place zone sees its base zone and the zones it has portals to (stand-in level zones, stair zones,
  // other places), and every one of those lists it back. (Base zone + all of the base zone's neighbours put all three
  // places in view on the spiral stair: 192 draws / 673k tris on Low.)
  const zoneOfId = (id) => added.find((a) => a.z.spaces.includes(id))?.z ?? M.zones.find((z) => z.spaces.includes(id)) ?? zoneById.get(`c_${id}`);
  for (const { z, baseZone } of added) {
    const nb = new Set([baseZone.id]);
    for (const p of L.portals) {
      if (p.a !== z.spaces[0] && p.b !== z.spaces[0]) continue;
      const oz = zoneOfId(p.a === z.spaces[0] ? p.b : p.a);
      if (oz && oz.id !== z.id) nb.add(oz.id);
    }
    z.neighbors = [...nb].sort();
    z.preload = [...new Set(baseZone.preload ?? [])].sort();
  }
  for (const { z } of added) {
    for (const n of z.neighbors) {
      const nz = zoneById.get(n) ?? added.find((a) => a.z.id === n)?.z;
      if (nz && !nz.neighbors.includes(z.id)) nz.neighbors.push(z.id);
    }
  }
  for (const w of M.water) if (w.scatter_override) { w.scatter = w.scatter_override; delete w.scatter_override; }
  M.zones.push(...added.map((a) => a.z));
  if (places.includes('g_arrival')) M.start = { place: 'g_arrival' };
  M.source = 'mixed';
  M.places_blender = places;
  M.generated = new Date().toISOString();
  if (tier === 'low') {
    const uri = writeAddressed(OUT, 'data', 'json', Buffer.from(JSON.stringify(spacesDoc)));
    lowManifest.spaces = uri;
  }
  M.spaces = lowManifest.spaces;
  writeFileSync(mf, JSON.stringify(M, null, 1));
  const tris = M.zones.reduce((s, z) => s + z.parts.reduce((a, p) => a + (p.tris ?? 0), 0), 0);
  console.log(`manifest ${tier}: ${M.zones.length} zones (${added.length} Blender), ${Object.keys(M.textures).length} textures, ${tris} tris total`);
  report[tier] = { zones: M.zones.length, textures: Object.keys(M.textures).length, tris };
}
writeFileSync(join(OUT, 'data/places.json'), JSON.stringify(placesDoc, null, 1));


// ---------------- 3. portal seams (walk meshes, Low manifest) ----------------
const M = JSON.parse(readFileSync(join(OUT, 'manifests/low.json'), 'utf8'));
const walkCache = new Map();
async function walkTris(uri) {
  if (walkCache.has(uri)) return walkCache.get(uri);
  const doc = await io.read(join(OUT, uri));
  const out = [];
  for (const node of doc.getRoot().listNodes()) {
    const mesh = node.getMesh(); if (!mesh) continue;
    const mtx = node.getWorldMatrix();
    for (const prim of mesh.listPrimitives()) {
      const pa = prim.getAttribute('POSITION'), idx = prim.getIndices();
      const n = idx ? idx.getCount() : pa.getCount();
      const v = [], e = [0, 0, 0];
      for (let i = 0; i < n; i++) {
        pa.getElement(idx ? idx.getScalar(i) : i, e);
        const x = mtx[0] * e[0] + mtx[4] * e[1] + mtx[8] * e[2] + mtx[12], y = mtx[1] * e[0] + mtx[5] * e[1] + mtx[9] * e[2] + mtx[13], zz = mtx[2] * e[0] + mtx[6] * e[1] + mtx[10] * e[2] + mtx[14];
        v.push([x, -zz, y]); // three -> layout
        if (v.length === 3) { out.push(v.splice(0)); }
      }
    }
  }
  walkCache.set(uri, out);
  return out;
}
// highest walk surface at (x, y) between zLo and zHi (vertical ray)
function floorAt(tris, x, y, zLo, zHi) {
  let best = null;
  for (const [a, b, c] of tris) {
    if (x < Math.min(a[0], b[0], c[0]) || x > Math.max(a[0], b[0], c[0]) || y < Math.min(a[1], b[1], c[1]) || y > Math.max(a[1], b[1], c[1])) continue;
    const d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]);
    if (Math.abs(d) < 1e-12) continue;
    const l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d, l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d, l3 = 1 - l1 - l2;
    if (l1 < -1e-6 || l2 < -1e-6 || l3 < -1e-6) continue;
    const z = l1 * a[2] + l2 * b[2] + l3 * c[2];
    // walkable only (normal z > 0.5)
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    if (Math.abs(nz) / Math.hypot(nx, ny, nz) < 0.5) continue;
    if (z < zLo || z > zHi) continue;
    if (best == null || z > best) best = z;
  }
  return best;
}
const zoneOfSpaceM = (id) => M.zones.find((z) => z.spaces.includes(id));
for (const space of places) {
  const ls = layoutSpace(space);
  const pz = M.zones.find((z) => z.id === `p_${space}`);
  if (!pz?.walk) continue;
  const mine = await walkTris(pz.walk.uri);
  for (const p of L.portals.filter((q) => q.a === space || q.b === space)) {
    const other = p.a === space ? p.b : p.a;
    const os = layoutSpace(other);
    const oz = os ? zoneOfSpaceM(other) : M.zones.find((z) => z.id === `c_${other}`) ?? M.zones.find((z) => z.id.endsWith(other));
    const theirs = oz?.walk ? await walkTris(oz.walk.uri) : [];
    // direction from the portal into this space: toward the footprint centroid
    const cx = ls.footprint.reduce((s, q) => s + q[0], 0) / ls.footprint.length, cy = ls.footprint.reduce((s, q) => s + q[1], 0) / ls.footprint.length;
    let dx = cx - p.at[0], dy = cy - p.at[1]; const dl = Math.hypot(dx, dy) || 1; dx /= dl; dy /= dl;
    const z0 = ls.floor_z;
    const res = { space, portal: p.id, other, other_zone: oz?.id ?? null, at: p.at, lines: [] };
    // walk across the portal on three lines; every sample (except within 5 cm of the portal line itself) needs a
    // walkable floor from either walk mesh within 0.2 m of the floor height (gaps < 0.1 m cannot catch a 0.3 m capsule)
    let ok = true;
    for (const off of [-0.3, 0, 0.3]) {
      const tx = -dy * off * p.width, ty = dx * off * p.width;
      const line = [];
      for (let d = -0.65; d <= 0.651; d += 0.1) {
        const x = p.at[0] + dx * d + tx, y = p.at[1] + dy * d + ty;
        const a = floorAt(mine, x, y, z0 - 0.5, z0 + 0.5), b = floorAt(theirs, x, y, z0 - 0.5, z0 + 0.5);
        const f = a ?? b;
        line.push([r3(d), r3(a), r3(b)]);
        if (f == null || Math.abs(f - z0) > 0.2) ok = false;
      }
      res.lines.push({ off, samples: line });
    }
    res.ok = ok;
    if (!ok) warn(`seam ${p.id} (${space} | ${other}): gap or step in the walk meshes across the portal`);
    report.seams.push(res);
  }
}
function pointIn(p, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi + 1e-30) + xi) inside = !inside;
  }
  return inside;
}
function r3(v) { return v == null ? null : Math.round(v * 1000) / 1000; }
writeFileSync(join(OUT, 'mixed-report.json'), JSON.stringify(report, null, 1));
console.log(`mixed: ${places.length} places, ${report.seams.filter((s) => s.ok).length}/${report.seams.length} portal seams ok, ${report.warnings.length} warnings`);
