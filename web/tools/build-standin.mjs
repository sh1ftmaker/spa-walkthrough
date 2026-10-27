#!/usr/bin/env node
// Builds the graybox stand-in scene from 3d/layout.json into the asset contract:
//   public/assets/manifests/{low,high}.json, parts/<sha16>.glb, tex/<sha16>.ktx2, data/*.json
// It is a test fixture for the runtime and the contract, not art.
//   node tools/build-standin.mjs [--layout ../3d/layout.json] [--out public/assets] [--exclude-spaces a,b]
// --exclude-spaces: spaces replaced by Blender place models (tools/build-mixed.mjs). Their floors, ceilings, walls,
// lanterns, probes and walk mesh are left out, their footprints are cut out of overlapping slabs and water at the
// same level (except --keep-slabs spaces), and neighbouring walls still treat them as rooms (so portals stay open).
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as G from './lib/geom.mjs';
import * as T from './lib/textures.mjs';
import { buildGLB, writeAddressed } from './lib/pack.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(here, '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []));
const LAYOUT = resolve(args.layout ?? join(WEB, '../3d/layout.json'));
const OUT = resolve(args.out ?? join(WEB, 'public/assets'));
const t0 = Date.now();
const L = JSON.parse(readFileSync(LAYOUT, 'utf8'));
const EXCLUDE = new Set(String(args['exclude-spaces'] ?? '').split(',').map((x) => x.trim()).filter(Boolean));
const report = { layout: LAYOUT, warnings: [], excluded: [...EXCLUDE] };
const warn = (m) => { report.warnings.push(m); console.warn('  warn:', m); };

for (const d of ['parts', 'tex', 'data', 'manifests']) rmSync(join(OUT, d), { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

const spaceById = new Map(L.spaces.map((s) => [s.id, s]));
const connById = new Map(L.connections.map((c) => [c.id, c]));
for (const s of L.spaces) s._ring = G.openRing(s.footprint);
for (const id of EXCLUDE) if (!spaceById.has(id)) { console.error(`--exclude-spaces: unknown space ${id}`); process.exit(2); }
// --keep-slabs a,b: stand-in spaces that keep their floor / ceiling where they overlap a replaced space (the place leaves
// that stretch to the stand-in, e.g. the koi junction inside the Mirror corridor footprint)
const KEEP = new Set(String(args['keep-slabs'] ?? '').split(',').map((x) => x.trim()).filter(Boolean));
const excludedRings = (z, tol = 0.6) => {
  const ex = L.spaces.filter((s) => EXCLUDE.has(s.id) && Math.abs(s.floor_z - z) <= tol).map((s) => [s._ring]);
  const keep = L.spaces.filter((s) => KEEP.has(s.id) && Math.abs(s.floor_z - z) <= tol).map((s) => [s._ring]);
  if (!ex.length || !keep.length) return ex;
  try { return G.difference(G.union(...ex), ...keep); } catch (e) { warn(`--keep-slabs: ${e.message}`); return ex; }
};

// ---------------- zones ----------------
const ZONE_NAMES = { ground: 'Ground', b1: 'B1 Thermal', b2: 'B2 River', b3: 'B3 Aqua Cavern', b4: 'B4 Magma', summit: 'Summit', cliff: 'Cliff suites' };
const zoneOfSpace = (s) => s.level;
function zoneOfConn(c) {
  const zs = (c.places ?? []).map((p) => spaceById.get(p)).filter(Boolean);
  const zr = (c.z_top ?? 0) - (c.z_bottom ?? 0);
  if (c.kind === 'helix' || zr > 30 || !zs.length) return `c_${c.id}`;
  zs.sort((a, b) => a.floor_z - b.floor_z);
  return zoneOfSpace(zs[0]);
}
const zones = new Map();
function zone(id) {
  let z = zones.get(id);
  if (!z) {
    const conn = connById.get(id.replace(/^c_/, ''));
    z = { id, name: ZONE_NAMES[id] ?? conn?.note?.split(/[;.]/)[0] ?? id, render: new G.MeshAcc(), walk: new G.MeshAcc(), neighbors: new Set(), preload: new Set(), spaces: [], lanterns: [], wallSegs: [], waterPolys: [], outdoorPolys: [], pts: [] };
    if (conn) z.name = { spiral_stair: 'Carved Spiral Stair', lava_stair: 'Lava Stair', terrace_path: 'Terrace Path', cliff_stair: 'Cliff Stair' }[conn.id] ?? conn.id;
    zones.set(id, z);
  }
  return z;
}
for (const s of L.spaces) { const z = zone(zoneOfSpace(s)); z.spaces.push(s.id); s._zone = z.id; }
for (const c of L.connections) {
  if (!c.walk) continue;
  c._zone = zoneOfConn(c);
  const z = zone(c._zone);
  for (const p of c.places ?? []) { const s = spaceById.get(p); if (s && s._zone !== z.id) { z.neighbors.add(s._zone); zone(s._zone).neighbors.add(z.id); } }
}
for (const p of L.portals) {
  const za = spaceById.get(p.a)?._zone ?? connById.get(p.a)?._zone, zb = spaceById.get(p.b)?._zone ?? connById.get(p.b)?._zone;
  if (za && zb && za !== zb) { zone(za).neighbors.add(zb); zone(zb).neighbors.add(za); }
}
// non-walk links (lift) still make zones neighbours for preloading
for (const c of L.connections) {
  if (c.walk) continue;
  const zs = [...new Set((c.places ?? []).map((p) => spaceById.get(p)?._zone).filter(Boolean))];
  for (const a of zs) for (const b of zs) if (a !== b && !zone(a).neighbors.has(b)) zone(a).preload.add(b);
}

// ---------------- stair patches (walkable treads / landings) ----------------
const patches = []; // {poly, clip, z, thick, zone, conn, kind, noRails}
function addPatch(poly, clip, z, zoneId, conn, kind, opts = {}) {
  const p = { poly, clip, z, thick: opts.thick ?? 0.35, zone: zoneId, conn, kind, noRails: !!opts.noRails, bb: G.bbox(poly[0]) };
  patches.push(p);
  return p;
}
const connEnds = new Map(); // conn id -> [{p:[x,y], z, edge:[[x,y],[x,y]]}]
const stairLanterns = [];

function buildHelix(c) {
  const C = c.center, hw = c.width / 2, r0 = c.r_walk - hw, r1 = c.r_walk + hw;
  const pts = c.path;
  const ang = []; let prev = null;
  for (const [x, y] of pts) {
    let a = Math.atan2(y - C[1], x - C[0]);
    if (prev !== null) { while (a - prev > Math.PI) a -= 2 * Math.PI; while (a - prev < -Math.PI) a += 2 * Math.PI; }
    ang.push(a); prev = a;
  }
  const ext = 0.03 / c.r_walk;
  for (let i = 0; i < pts.length - 1; i++) {
    const a0 = Math.min(ang[i], ang[i + 1]) - ext, a1 = Math.max(ang[i], ang[i + 1]) + ext;
    addPatch(G.annularSector(C, r0, r1, a0, a1), G.annularSector(C, r0 - 0.06, r1 + 0.06, a0, a1), pts[i][2], c._zone, c.id, Math.abs(pts[i][2] - pts[i + 1][2]) < 1e-3 ? 'landing' : 'tread', { noRails: true });
  }
  const n = pts.length - 1, dir = Math.sign(ang[n] - ang[n - 1]) || 1;
  const aEnd = ang[n] + dir * (1.2 / c.r_walk);
  addPatch(G.annularSector(C, r0, r1, Math.min(ang[n], aEnd), Math.max(ang[n], aEnd)), G.annularSector(C, r0 - 0.06, r1 + 0.06, Math.min(ang[n], aEnd), Math.max(ang[n], aEnd)), pts[n][2], c._zone, c.id, 'landing', { noRails: true });

  // walls: solid core and outer shaft wall with doors
  const z = zone(c._zone);
  const placeSpaces = (c.places ?? []).map((p) => spaceById.get(p)).filter(Boolean);
  const topH = Math.max(3.5, ...placeSpaces.filter((s) => Math.abs(s.floor_z - c.z_top) < 0.5 && s.ceiling_z != null).map((s) => s.ceiling_z - s.floor_z));
  const zb = c.z_bottom - 0.4, zt = c.z_top + topH;
  const core = [G.circlePoly(C, r0, 48)[0], G.circlePoly(C, Math.max(0.5, r0 - 0.35), 48)[0].reverse()];
  G.emitPrism(z.render, 'wall:basalt', core, zb, zt);
  G.emitPrism(z.walk, 'walk', core, zb, zt);
  const doors = []; // {a, z0, z1, hwA}
  const hwA = 1.5 / r1;
  for (const s of placeSpaces) {
    if (s.floor_z < c.z_bottom - 0.5 || s.floor_z > c.z_top + 0.5) continue;
    const near = pts.map((p, i) => ({ i, d: Math.abs(p[2] - s.floor_z) })).filter((q) => q.d < 0.09);
    if (!near.length) { warn(`${c.id}: no path point at the floor of ${s.id} (z ${s.floor_z})`); continue; }
    const mid = near[Math.floor(near.length / 2)].i;
    doors.push({ a: ang[mid], z0: s.floor_z, z1: s.floor_z + 2.7, space: s.id });
  }
  for (const p of L.portals) {
    if (p.a !== c.id && p.b !== c.id) continue;
    const s = spaceById.get(p.a === c.id ? p.b : p.a);
    if (!s) continue;
    let a = Math.atan2(p.at[1] - C[1], p.at[0] - C[0]);
    doors.push({ a, z0: s.floor_z, z1: s.floor_z + (p.height ?? 2.7), space: s.id, portal: p.id });
  }
  const N = 128;
  for (let k = 0; k < N; k++) {
    const a0 = (k / N) * 2 * Math.PI, a1 = ((k + 1) / N) * 2 * Math.PI, am = (a0 + a1) / 2;
    let ivals = [[zb, zt]];
    for (const d of doors) {
      let da = Math.abs(((am - d.a) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI);
      if (da > hwA) continue;
      const nx = [];
      for (const [lo, hi] of ivals) {
        if (d.z1 <= lo || d.z0 >= hi) { nx.push([lo, hi]); continue; }
        if (d.z0 > lo) nx.push([lo, d.z0]);
        if (d.z1 < hi) nx.push([d.z1, hi]);
      }
      ivals = nx;
    }
    const sec = G.annularSector(C, r1, r1 + 0.3, a0, a1 + 1e-4, 1);
    for (const [lo, hi] of ivals) { G.emitPrism(z.render, 'wall:basalt', sec, lo, hi); G.emitPrism(z.walk, 'walk', sec, lo, hi); }
  }
  report[`doors_${c.id}`] = doors.map((d) => ({ space: d.space, deg: +((d.a * 180) / Math.PI).toFixed(1), z: d.z0, portal: d.portal }));
  z.pts.push([C[0] - r1, C[1] - r1], [C[0] + r1, C[1] + r1]);
  connEnds.set(c.id, [{ p: [pts[0][0], pts[0][1]], z: pts[0][2] }, { p: [pts[n][0], pts[n][1]], z: pts[n][2] }]);
  // wall lanterns every 60 degrees (same angles on every turn, so the top-down bake dedupes them)
  const step = Math.PI / 3;
  for (let i = 1; i < pts.length; i++) {
    const k0 = Math.floor(ang[i - 1] / step), k1 = Math.floor(ang[i] / step);
    if (k0 === k1) continue;
    const a = Math.max(k0, k1) * step;
    stairLanterns.push({ zone: c._zone, p: [C[0] + (r1 - 0.12) * Math.cos(a), C[1] + (r1 - 0.12) * Math.sin(a)], z: pts[i][2] + 2.2, h: 2.2, I: 3.0, size: 0.24 });
  }
}

// patch along a polyline interval [s0,s1] at height z
function polyPatch(pl, s0, s1, hw, z, zoneId, conn, kind) {
  for (const pc of G.polylinePieces(pl, s0, s1)) {
    addPatch(G.segRect(pc.a, pc.b, hw, 0.02, 0.02), G.segRect(pc.a, pc.b, hw + 0.06, 0.03, 0.03), z, zoneId, conn, kind);
  }
}
function cornerFills(pl, hw, zAt, zoneId, conn) {
  let acc = 0;
  for (let i = 1; i < pl.length - 1; i++) {
    acc += Math.hypot(pl[i][0] - pl[i - 1][0], pl[i][1] - pl[i - 1][1]);
    const z = zAt(acc);
    addPatch(G.circlePoly(pl[i], hw * 1.04, 12), G.circlePoly(pl[i], hw + 0.08, 12), z, zoneId, conn, 'landing');
  }
}
function buildPathStair(c) {
  const pl = c.plan, Ltot = G.polylineLength(pl), n = c.steps, runs = Math.max(1, c.runs ?? 1), nl = c.landings ?? runs - 1;
  const riser = (c.z_top - c.z_bottom) / n, hw = c.width / 2;
  let tread = c.tread ?? 0.29;
  let land = nl > 0 ? (Ltot - n * tread) / nl : 0;
  if (land < 0) { tread = Ltot / n; land = 0; warn(`${c.id}: plan length ${Ltot.toFixed(1)} m too short for ${n} treads; compressed`); }
  const per = Array.from({ length: runs }, (_, r) => Math.floor(n / runs) + (r < n % runs ? 1 : 0));
  const zs = []; // [s0, s1, z]
  let s = 0, z = c.z_top;
  for (let r = 0; r < runs; r++) {
    for (let k = 0; k < per[r]; k++) { z -= riser; zs.push([s, s + tread, z, 'tread']); s += tread; }
    if (r < runs - 1 && land > 0) { zs.push([s, s + land, z, 'landing']); s += land; }
  }
  for (const [a, b, zz, kind] of zs) polyPatch(pl, a, b, hw, zz, c._zone, c.id, kind);
  const zAt = (sv) => { for (const q of zs) if (sv >= q[0] - 1e-6 && sv <= q[1] + 1e-6) return q[2]; return zs[zs.length - 1][2]; };
  cornerFills(pl, hw, zAt, c._zone, c.id);
  for (let sv = 6; sv < Ltot - 3; sv += 12) {
    const q = G.polylineAt(pl, sv);
    stairLanterns.push({ zone: c._zone, p: [q.p[0] - q.dir[1] * (hw + 0.25), q.p[1] + q.dir[0] * (hw + 0.25)], z: zAt(sv) + 1.0, h: 1.0, I: 1.6, size: 0.22 });
  }
  const st = G.polylineAt(pl, 0), en = G.polylineAt(pl, Ltot);
  connEnds.set(c.id, [{ p: pl[0], z: c.z_top, dir: st.dir, hw }, { p: pl[pl.length - 1], z: zs[zs.length - 1][2], dir: en.dir, hw }]);
  zone(c._zone).pts.push(...pl);
}
function buildWalkway(c) {
  const pl = c.plan, Ltot = G.polylineLength(pl), hw = c.width / 2;
  polyPatch(pl, 0, Ltot, hw, c.z, c._zone, c.id, 'landing');
  cornerFills(pl, hw, () => c.z, c._zone, c.id);
  connEnds.set(c.id, [{ p: pl[0], z: c.z }, { p: pl[pl.length - 1], z: c.z }]);
  zone(c._zone).pts.push(...pl);
}
function buildSwitchback(c) {
  const hw = c.flight_width / 2, tread = c.tread ?? 0.29, fl = c.flights;
  fl.forEach((f) => {
    const dir = Math.sign(f.y_end - f.y_start), len = Math.abs(f.y_end - f.y_start), n = f.steps, m = f.mid_landings ?? 0;
    const riser = (f.z_start - f.z_end) / n, land = m > 0 ? (len - n * tread) / m : 0;
    const per = Array.from({ length: m + 1 }, (_, r) => Math.floor(n / (m + 1)) + (r < n % (m + 1) ? 1 : 0));
    let s = 0, z = f.z_start;
    const pl = [[f.x, f.y_start], [f.x, f.y_end]];
    for (let r = 0; r <= m; r++) {
      for (let k = 0; k < per[r]; k++) { z -= riser; polyPatch(pl, s, s + tread, hw, z, c._zone, c.id, 'tread'); s += tread; }
      if (r < m) { polyPatch(pl, s, s + land, hw, z, c._zone, c.id, 'landing'); s += land; }
    }
    if (Math.abs(s - len) > 0.05) warn(`${c.id}: flight at x ${f.x} uses ${s.toFixed(2)} m of ${len.toFixed(2)} m`);
    void dir;
  });
  for (let i = 0; i < fl.length - 1; i++) {
    const f = fl[i], g = fl[i + 1];
    const xs = [f.x - hw, f.x + hw, g.x - hw, g.x + hw], x0 = Math.min(...xs), x1 = Math.max(...xs);
    const south = Math.sign(f.y_end - f.y_start) < 0;
    const edge = south ? Math.min(f.y_end, g.y_start) : Math.max(f.y_end, g.y_start);
    const far = south ? edge - 2.0 : edge + 2.0;
    const polys = [G.rect(Math.min(f.x - hw, f.x + hw), Math.min(far, f.y_end), Math.max(f.x - hw, f.x + hw), Math.max(far, f.y_end)),
      G.rect(Math.min(g.x - hw, g.x + hw), Math.min(far, g.y_start), Math.max(g.x - hw, g.x + hw), Math.max(far, g.y_start)),
      G.rect(x0, Math.min(far, edge), x1, Math.max(far, edge))];
    for (const poly of G.union(...polys)) {
      addPatch(poly, poly, f.z_end, c._zone, c.id, 'landing');
    }
  }
  const f0 = fl[0], fN = fl[fl.length - 1];
  connEnds.set(c.id, [
    { p: [f0.x, f0.y_start], z: f0.z_start, edge: [[f0.x - hw, f0.y_start], [f0.x + hw, f0.y_start]] },
    { p: [fN.x, fN.y_end], z: fN.z_end, edge: [[fN.x - hw, fN.y_end], [fN.x + hw, fN.y_end]] },
  ]);
  zone(c._zone).pts.push(...c.box);
}

for (const c of L.connections) {
  if (!c.walk) continue;
  if (c.kind === 'helix') buildHelix(c);
  else if (c.kind === 'path_stair') buildPathStair(c);
  else if (c.kind === 'walkway') buildWalkway(c);
  else if (c.kind === 'switchback') buildSwitchback(c);
  else warn(`connection ${c.id}: kind ${c.kind} not built by the stand-in`);
}

// approach patches from a portal to the nearest stair end (non-helix)
for (const p of L.portals) {
  const cid = connById.has(p.a) ? p.a : connById.has(p.b) ? p.b : null;
  if (!cid) continue;
  const c = connById.get(cid);
  if (c.kind === 'helix') continue;
  const s = spaceById.get(cid === p.a ? p.b : p.a);
  const ends = connEnds.get(cid);
  if (!s || !ends) continue;
  const end = ends.reduce((b, e) => (Math.abs(e.z - s.floor_z) < Math.abs(b.z - s.floor_z) ? e : b));
  if (Math.abs(end.z - s.floor_z) > 0.5) { warn(`portal ${p.id}: no end of ${cid} at the floor of ${s.id}`); continue; }
  const hw = p.width / 2;
  const pts = [[p.at[0] - hw, p.at[1] - hw], [p.at[0] + hw, p.at[1] - hw], [p.at[0] + hw, p.at[1] + hw], [p.at[0] - hw, p.at[1] + hw]];
  if (end.edge) pts.push(...end.edge); else pts.push([end.p[0] - hw, end.p[1] - hw], [end.p[0] + hw, end.p[1] + hw], [end.p[0] - hw, end.p[1] + hw], [end.p[0] + hw, end.p[1] - hw]);
  const hull = G.convexHull(pts);
  addPatch(hull, hull, s.floor_z, c._zone, cid, 'landing');
}

// ---------------- water ----------------
const waters = [];
for (const w of L.water) {
  let poly = null, z = w.z, bed = null;
  if (w.footprint && (w.kind === 'still' || w.kind === 'sea')) {
    poly = [[G.openRing(w.footprint)]];
    bed = w.kind === 'sea' ? z - 4 : z - 1.2;
  } else if (w.kind === 'flow' && w.centerline) {
    const cl = w.centerline, closed = Math.hypot(cl[0][0] - cl[cl.length - 1][0], cl[0][1] - cl[cl.length - 1][1]) < 5;
    const pts = closed ? [...cl, cl[0]] : cl;
    const width = (i) => (Array.isArray(w.widths) ? w.widths[Math.min(i, w.widths.length - 1)] : w.width ?? 6);
    const parts = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const hw = (width(i) + width(Math.min(i + 1, pts.length - 1))) / 4;
      parts.push(G.segRect(pts[i], pts[i + 1], hw, 0.01, 0.01));
      if (i > 0) parts.push(G.circlePoly(pts[i], width(i) / 2, 16));
    }
    poly = G.union(...parts);
    z = (w.z_start + w.z_end) / 2;
    bed = w.bed_z ?? z - 1.2;
  } else continue;
  const level = w.level ?? null;
  const cut = excludedRings(z, 1.5);
  if (cut.length) {
    try { poly = G.difference(poly, ...cut); } catch (e) { warn(`water ${w.id}: exclusion cut failed (${e.message})`); }
    if (!poly.length) { report.excluded_water = [...(report.excluded_water ?? []), w.id]; continue; }
  }
  waters.push({ id: w.id, kind: w.kind, z, bed, poly, level, src: w, bb: G.multiBBox(poly) });
}

// ---------------- slabs (floors / ceilings) ----------------
const slabGroups = new Map();
for (const s of L.spaces) {
  if (EXCLUDE.has(s.id)) continue;
  const k = `${s._zone}|floor|${s.floor_z}`;
  if (!slabGroups.has(k)) slabGroups.set(k, { zone: s._zone, kind: 'floor', top: s.floor_z, bottom: s.floor_z - 0.3, polys: [], spaces: [] });
  slabGroups.get(k).polys.push([s._ring]); slabGroups.get(k).spaces.push(s);
  if (s.ceiling_z != null) {
    const kc = `${s._zone}|ceiling|${s.ceiling_z}`;
    if (!slabGroups.has(kc)) slabGroups.set(kc, { zone: s._zone, kind: 'ceiling', top: s.ceiling_z + 0.3, bottom: s.ceiling_z, polys: [], spaces: [] });
    slabGroups.get(kc).polys.push([s._ring]); slabGroups.get(kc).spaces.push(s);
  }
}
const slabs = [];
for (const g of slabGroups.values()) {
  const full = G.union(...g.polys);
  const bb = G.multiBBox(full);
  const cuts = [];
  for (const p of patches) {
    if (p.z < g.bottom - 2.4 || p.z > g.top + 0.03) continue;
    if (!G.bboxOverlap(bb, p.bb, 0.2)) continue;
    cuts.push(p.clip);
  }
  const wcuts = [];
  if (g.kind === 'floor') for (const w of waters) {
    if (w.z < g.top - 3 || w.z > g.top + 0.02) continue;
    if (!G.bboxOverlap(bb, w.bb)) continue;
    wcuts.push(w.poly);
    (w.cutFrom ??= []).push({ top: g.top, full, zone: g.zone });
  }
  let mp = full;
  const xcuts = excludedRings(g.kind === 'floor' ? g.top : g.bottom, 0.6);
  try {
    if (cuts.length || wcuts.length || xcuts.length) mp = G.difference(full, ...cuts, ...wcuts, ...xcuts);
  } catch (e) {
    warn(`slab ${g.zone}/${g.kind}/${g.top}: clipping failed (${e.message}); kept uncut`);
  }
  slabs.push({ ...g, full, mp, bb });
}

// ---------------- emit slabs, water, basins ----------------
const indoorMat = (s) => (s.kind === 'cave' || s.kind === 'tunnel' ? 'basalt' : s.kind === 'outdoor' ? 'basalt' : 'plaster');
for (const sl of slabs) {
  const z = zone(sl.zone);
  if (sl.kind === 'floor') {
    G.emitMultiPrism(z.render, 'floor:stone_floor', sl.mp, sl.bottom, sl.top);
    G.emitMultiPrism(z.walk, 'walk', sl.mp, sl.bottom, sl.top);
  } else {
    G.emitMultiPrism(z.render, 'ceiling:rock_ceiling', sl.mp, sl.bottom, sl.top);
  }
  for (const poly of sl.full) z.pts.push(...poly[0]);
  for (const s of sl.spaces) if (s.kind === 'outdoor' && sl.kind === 'floor') z.outdoorPolys.push([s._ring]);
}
const bridges = [];
for (const p of L.portals) {
  if (!/bridge/i.test(p.note ?? '')) continue;
  let best = null;
  for (const w of waters) {
    if (w.kind !== 'flow') continue;
    const cl = w.src.centerline;
    for (let i = 0; i < cl.length; i++) {
      const a = cl[i], b = cl[(i + 1) % cl.length];
      const { d, t } = G.distPointSeg(p.at, a, b);
      if (!best || d < best.d) best = { d, w, a, b, t };
    }
  }
  const s = spaceById.get(p.a);
  if (!best || best.d > 15 || !s) { warn(`bridge ${p.id}: no river nearby`); continue; }
  const q = [best.a[0] + (best.b[0] - best.a[0]) * best.t, best.a[1] + (best.b[1] - best.a[1]) * best.t];
  const dx = best.b[0] - best.a[0], dy = best.b[1] - best.a[1], l = Math.hypot(dx, dy);
  const nx = -dy / l, ny = dx / l, width = best.w.src.width ?? 8, half = width / 2 + 2.5;
  const poly = G.segRect([q[0] - nx * half, q[1] - ny * half], [q[0] + nx * half, q[1] + ny * half], p.width / 2);
  const patch = addPatch(poly, poly, s.floor_z, s._zone, p.id, 'bridge');
  bridges.push(patch);
}
for (const w of waters) {
  const zoneId = w.cutFrom?.[0]?.zone ?? (w.level ? w.level : null);
  if (!zoneId || !zones.has(zoneId)) { warn(`water ${w.id}: no zone (level ${w.level})`); continue; }
  w.zone = zoneId;
  const z = zone(zoneId);
  G.emitMultiPrism(z.render, `water:${w.id}`, w.poly, w.z, w.z, { bottom: false, sides: false });
  G.emitMultiPrism(z.render, 'basin:pool_tile', w.poly, w.bed - 0.2, w.bed, { sides: false });
  G.emitMultiPrism(z.walk, 'walk', w.poly, w.bed - 0.2, w.bed, { sides: false });
  const top = w.cutFrom ? Math.max(...w.cutFrom.map((c) => c.top)) - 0.3 : w.z + 0.25;
  for (const poly of w.poly) for (const ring of poly) {
    const r = G.openRing(ring);
    for (let i = 0; i < r.length; i++) G.emitWallQuad(z.render, 'basin:pool_tile', r[i], r[(i + 1) % r.length], w.bed, Math.max(top, w.z + 0.05));
  }
  const drop = w.cutFrom ? Math.max(...w.cutFrom.map((c) => c.top)) - w.z : 0;
  w.walkOnSurface = drop <= 0.25;
  if (w.walkOnSurface) G.emitMultiPrism(z.walk, 'walk', w.poly, w.z - 0.05, w.z, { bottom: false, sides: false });
  // rails along the hole edge where a floor surrounds deep water
  if (!w.walkOnSurface && w.cutFrom) {
    for (const poly of w.poly) for (const ring of poly) {
      const r = G.openRing(ring);
      const ccw = G.ringArea(r) > 0;
      for (let i = 0; i < r.length; i++) {
        const a = r[i], b = r[(i + 1) % r.length];
        railAlong(z, a, b, ccw ? 1 : -1, (pt) => {
          const c = w.cutFrom.find((cf) => G.pointInMulti(pt, cf.full));
          if (!c) return null;
          if (bridges.some((br) => G.pointInPolygon(pt, br.poly))) return null;
          return c.top;
        }, 'rail:rail');
      }
    }
  }
  z.waterPolys.push(w.poly);
  for (const poly of w.poly) z.pts.push(...poly[0]);
}

// Rail helper: samples the edge a->b; outSign: +1 when the outward side is to the right of a->b.
// zOf(pt) returns the rail base z at a sample (point slightly outside the edge), or null for no rail.
function railAlong(z, a, b, outSign, zOf, key, { inset = 0.04, h = 1.0, t = 0.06, step = 0.1 } = {}) {
  const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy);
  if (l < 1e-3) return;
  const ux = dx / l, uy = dy / l, ox = uy * outSign, oy = -ux * outSign; // outward normal
  const n = Math.max(1, Math.round(l / step));
  let run = null;
  const flush = (k) => {
    if (!run) return;
    const t0 = run.k0 / n, t1 = k / n;
    const p0 = [a[0] + dx * t0, a[1] + dy * t0], p1 = [a[0] + dx * t1, a[1] + dy * t1];
    const ring = [[p0[0] - ox * inset, p0[1] - oy * inset], [p1[0] - ox * inset, p1[1] - oy * inset], [p1[0] - ox * (inset + t), p1[1] - oy * (inset + t)], [p0[0] - ox * (inset + t), p0[1] - oy * (inset + t)]];
    G.emitPrism(z.render, key, [ring], run.z, run.z + h);
    G.emitPrism(z.walk, 'walk', [ring], run.z, run.z + h);
    run = null;
  };
  for (let k = 0; k < n; k++) {
    const tm = (k + 0.5) / n, pt = [a[0] + dx * tm + ox * 0.08, a[1] + dy * tm + oy * 0.08];
    const zz = zOf(pt);
    if (zz == null || (run && Math.abs(run.z - zz) > 1e-3)) flush(k);
    if (zz != null && !run) run = { k0: k, z: zz };
  }
  flush(n);
}

// ---------------- walls ----------------
const portalsOf = new Map();
for (const p of L.portals) for (const id of [p.a, p.b]) { if (!portalsOf.has(id)) portalsOf.set(id, []); portalsOf.get(id).push(p); }
function insideOtherSpace(pt, s, maxDz) {
  for (const t of L.spaces) {
    if (t === s || Math.abs(t.floor_z - s.floor_z) > maxDz) continue;
    if (G.pointInRing(pt, t._ring)) return t;
  }
  return null;
}
const patchGrid = new Map(); const CELL = 4;
const cellKey = (i, j) => `${i},${j}`;
for (const [idx, p] of patches.entries()) {
  for (let i = Math.floor(p.bb.minx / CELL); i <= Math.floor(p.bb.maxx / CELL); i++) for (let j = Math.floor(p.bb.miny / CELL); j <= Math.floor(p.bb.maxy / CELL); j++) {
    const k = cellKey(i, j); if (!patchGrid.has(k)) patchGrid.set(k, []); patchGrid.get(k).push(idx);
  }
}
function patchAt(pt, zz, tol, self = -1) {
  const list = patchGrid.get(cellKey(Math.floor(pt[0] / CELL), Math.floor(pt[1] / CELL))) ?? [];
  for (const i of list) {
    if (i === self) continue;
    const p = patches[i];
    if (Math.abs(p.z - zz) > tol) continue;
    if (pt[0] < p.bb.minx || pt[0] > p.bb.maxx || pt[1] < p.bb.miny || pt[1] > p.bb.maxy) continue;
    if (G.pointInPolygon(pt, p.poly)) return p;
  }
  return null;
}
function floorAt(pt, zz, tol) {
  for (const sl of slabs) {
    if (sl.kind !== 'floor' || Math.abs(sl.top - zz) > tol) continue;
    if (pt[0] < sl.bb.minx || pt[0] > sl.bb.maxx || pt[1] < sl.bb.miny || pt[1] > sl.bb.maxy) continue;
    if (G.pointInMulti(pt, sl.mp)) return sl;
  }
  for (const w of waters) if (w.walkOnSurface && Math.abs(w.z - zz) <= tol && G.pointInMulti(pt, w.poly)) return w;
  return null;
}
const lanterns = [...stairLanterns];
for (const s of L.spaces) {
  if (EXCLUDE.has(s.id)) continue;
  const z = zone(s._zone);
  const r = s._ring, ccw = G.ringArea(r) > 0;
  const indoor = s.ceiling_z != null;
  const H = indoor ? s.ceiling_z - s.floor_z : 1.1;
  const mat = indoor ? indoorMat(s) : 'basalt';
  const ports = portalsOf.get(s.id) ?? [];
  // portal -> nearest edge
  const openings = ports.map((p) => {
    let best = null;
    for (let i = 0; i < r.length; i++) {
      const { d, t } = G.distPointSeg(p.at, r[i], r[(i + 1) % r.length]);
      if (!best || d < best.d) best = { d, i, t };
    }
    if (best.d > 3 && !connById.has(p.a === s.id ? p.b : p.a) && !/bridge/i.test(p.note ?? '')) warn(`portal ${p.id}: ${best.d.toFixed(1)} m from the nearest wall of ${s.id}`);
    return { p, ...best };
  });
  for (let i = 0; i < r.length; i++) {
    const a = r[i], b = r[(i + 1) % r.length];
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy);
    if (l < 0.05) continue;
    const ux = dx / l, uy = dy / l;
    const inx = ccw ? -uy : uy, iny = ccw ? ux : -ux;
    const n = Math.max(1, Math.round(l / 0.1));
    const cols = []; // per sample: null (no wall) or [[z0,z1],...]
    for (let k = 0; k < n; k++) {
      const tm = (k + 0.5) / n, p = [a[0] + dx * tm, a[1] + dy * tm];
      const pin = [p[0] + inx * 0.15, p[1] + iny * 0.15], pout = [p[0] - inx * 0.15, p[1] - iny * 0.15];
      let iv = [[s.floor_z, s.floor_z + H]];
      if (insideOtherSpace(pin, s, 0.6)) iv = [];
      if (!indoor && (insideOtherSpace(pout, s, 0.35) || patchAt(pout, s.floor_z, 0.35))) iv = [];
      for (const o of openings) {
        if (o.d > 3) continue;
        const along = Math.abs((tm - (o.i === i ? o.t : -99)) * l);
        if (o.i !== i || along > o.p.width / 2) continue;
        const top = indoor && o.p.height ? s.floor_z + o.p.height : Infinity;
        const nx = [];
        for (const [lo, hi] of iv) { if (top < hi) nx.push([Math.max(lo, top), hi]); }
        iv = nx;
      }
      cols.push(iv);
    }
    // run-length into pieces
    let k = 0;
    while (k < n) {
      const sig = JSON.stringify(cols[k]);
      let e = k + 1;
      while (e < n && JSON.stringify(cols[e]) === sig) e++;
      if (cols[k].length) {
        const t0 = k / n, t1 = e / n;
        const p0 = [a[0] + dx * t0, a[1] + dy * t0], p1 = [a[0] + dx * t1, a[1] + dy * t1];
        const ring = [p0, p1, [p1[0] + inx * 0.2, p1[1] + iny * 0.2], [p0[0] + inx * 0.2, p0[1] + iny * 0.2]];
        for (const [lo, hi] of cols[k]) {
          G.emitPrism(z.render, `wall:${mat}`, [ring], lo - (lo === s.floor_z ? 0 : 0), hi);
          G.emitPrism(z.walk, 'walk', [ring], lo, hi);
        }
        z.wallSegs.push([p0, p1]);
      }
      k = e;
    }
  }
  // lanterns: beside each portal with a lintel, and one per indoor space
  for (const o of openings) {
    if (!o.p.height || o.d > 3 || o.p.a !== s.id) continue;
    const a = r[o.i], b = r[(o.i + 1) % r.length];
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy), ux = dx / l, uy = dy / l;
    const inx = ccw ? -uy : uy, iny = ccw ? ux : -ux;
    const c = [a[0] + dx * o.t, a[1] + dy * o.t];
    for (const sg of [-1, 1]) {
      const off = o.p.width / 2 + 0.45;
      lanterns.push({ zone: s._zone, p: [c[0] + ux * off * sg + inx * 0.35, c[1] + uy * off * sg + iny * 0.35], z: s.floor_z + Math.min(2.1, o.p.height - 0.2), h: Math.min(2.1, o.p.height - 0.2), I: 3.5, size: 0.28 });
    }
  }
  if (indoor) {
    // ceiling pendant: hangs 0.8 m below the ceiling; intensity scaled with height so the floor gets ~1 unit
    const c = G.interiorPoint(r);
    const hh = Math.max(2.2, H - 0.8);
    lanterns.push({ zone: s._zone, p: c, z: s.floor_z + hh, h: hh, I: 1.1 * hh * hh + 4 + 0.006 * (s.area_m2 ?? 200), size: 0.5, space: s.id });
  }
}
for (const lt of lanterns) {
  const z = zone(lt.zone), q = lt.size / 2;
  const poly = G.rect(lt.p[0] - q, lt.p[1] - q, lt.p[0] + q, lt.p[1] + q);
  G.emitPrism(z.render, 'lantern:lantern', poly, lt.z - lt.size * 0.7, lt.z + lt.size * 0.7);
  z.lanterns.push(lt);
}

// ---------------- emit patches + rails ----------------
for (const [idx, p] of patches.entries()) {
  const z = zone(p.zone);
  G.emitPrism(z.render, `stair:wood`, p.poly, p.z - p.thick, p.z);
  G.emitPrism(z.walk, 'walk', p.poly, p.z - p.thick, p.z);
  z.pts.push(...p.poly[0]);
  if (p.noRails) continue;
  const ring = G.openRing(p.poly[0]), ccw = G.ringArea(ring) > 0;
  for (let i = 0; i < ring.length; i++) {
    railAlong(z, ring[i], ring[(i + 1) % ring.length], ccw ? 1 : -1, (pt) => {
      if (patchAt(pt, p.z, 0.25, idx) || floorAt(pt, p.z, 0.25)) return null;
      // allow stepping down from a patch onto a lower patch within one riser + a bit
      if (patchAt(pt, p.z - 0.2, 0.06, idx) || patchAt(pt, p.z + 0.2, 0.06, idx)) return null;
      return p.z;
    }, 'rail:rail', { step: 0.12 });
  }
}

// ---------------- connection endpoint diagnostics ----------------
report.endpoints = [];
for (const [cid, ends] of connEnds) {
  for (const e of ends) {
    const hit = L.spaces.filter((s) => G.pointInRing(e.p, s._ring)).sort((a, b) => Math.abs(a.floor_z - e.z) - Math.abs(b.floor_z - e.z))[0];
    const dz = hit ? +(hit.floor_z - e.z).toFixed(3) : null;
    report.endpoints.push({ conn: cid, at: e.p.map((v) => +v.toFixed(2)), z: +e.z.toFixed(3), space: hit?.id ?? null, dz });
    if (!hit) warn(`${cid}: end at (${e.p.map((v) => v.toFixed(1))}) z ${e.z.toFixed(2)} is outside every space`);
    else if (Math.abs(dz) > 0.25) warn(`${cid}: end at (${e.p.map((v) => v.toFixed(1))}) z ${e.z.toFixed(2)} is ${dz} m from the floor of ${hit.id}`);
  }
}
report.portal_drops = [];
for (const p of L.portals) {
  const a = spaceById.get(p.a), b = spaceById.get(p.b);
  if (a && b && Math.abs(a.floor_z - b.floor_z) > 0.25) {
    report.portal_drops.push({ portal: p.id, a: p.a, b: p.b, dz: +(b.floor_z - a.floor_z).toFixed(2) });
    warn(`portal ${p.id}: floors differ by ${(b.floor_z - a.floor_z).toFixed(2)} m (${p.a} ${a.floor_z} / ${p.b} ${b.floor_z}) with no stair`);
  }
}

// ---------------- textures ----------------
const TIERS = {
  low: { albedo: 512, waterNormal: 256, lmTexel: 0.5, lmMax: 1024, lmEncoding: 'rgbm', albedoCodec: 'etc1s' },
  high: { albedo: 1024, waterNormal: 512, lmTexel: 0.25, lmMax: 2048, lmEncoding: 'hdr', albedoCodec: 'uastc' },
};
const RGBM = { range: 16, gamma: 2 };
const MATERIALS = {
  stone_floor: { tex: 'stone_floor', roughness: 0.72, color: [1, 1, 1] },
  basalt: { tex: 'basalt', roughness: 0.82, color: [1, 1, 1] },
  rock_ceiling: { tex: 'rock_ceiling', roughness: 0.9, color: [1, 1, 1] },
  plaster: { tex: 'plaster', roughness: 0.85, color: [1, 1, 1] },
  wood: { tex: 'wood', roughness: 0.55, color: [1, 1, 1] },
  pool_tile: { tex: 'pool_tile', roughness: 0.3, color: [1, 1, 1] },
  rail: { roughness: 0.45, metalness: 0.7, color: [0.32, 0.22, 0.14] },
  lantern: { roughness: 0.6, color: [1.0, 0.85, 0.6], emissive: [1.0, 0.62, 0.3], emissiveIntensity: 4, lightmap: false },
};
const texCache = {};
async function tierTextures(tier) {
  const cfg = TIERS[tier], out = {};
  for (const name of Object.keys(T.ALBEDO)) {
    const key = `${name}@${cfg.albedo}@${cfg.albedoCodec}`;
    texCache[key] ??= writeAddressed(OUT, 'tex', 'ktx2', await T.encodeLDR(T.makeAlbedo(name, cfg.albedo), 'srgb', { etc1s: cfg.albedoCodec === 'etc1s' }));
    out[name] = { uri: texCache[key], colorSpace: 'srgb', width: cfg.albedo, height: cfg.albedo, codec: cfg.albedoCodec };
  }
  const wkey = `water_normal@${cfg.waterNormal}`;
  texCache[wkey] ??= writeAddressed(OUT, 'tex', 'ktx2', await T.encodeLDR(T.makeWaterNormal(cfg.waterNormal), 'normal'));
  out.water_normal = { uri: texCache[wkey], colorSpace: 'linear', width: cfg.waterNormal, height: cfg.waterNormal };
  return out;
}

// fake bake: top-down irradiance per zone (stand-in only)
function zoneBounds(z) {
  const b = G.bbox(z.pts.length ? z.pts : [[0, 0], [1, 1]]);
  return { minx: Math.floor(b.minx - 1), miny: Math.floor(b.miny - 1), maxx: Math.ceil(b.maxx + 1), maxy: Math.ceil(b.maxy + 1) };
}
function bakeZone(z, b, texel, maxRes) {
  const seen = new Set();
  z.uniqueLanterns = z.lanterns.filter((l) => { const k = `${l.p[0].toFixed(1)},${l.p[1].toFixed(1)}`; if (seen.has(k)) return false; seen.add(k); return true; });
  const pow2 = (v) => 2 ** Math.ceil(Math.log2(Math.max(4, v)));
  const W = Math.min(maxRes, pow2((b.maxx - b.minx) / texel)), H = Math.min(maxRes, pow2((b.maxy - b.miny) / texel));
  const sx = (b.maxx - b.minx) / W, sy = (b.maxy - b.miny) / H;
  // distance to walls (chamfer transform)
  const D = new Float32Array(W * H).fill(1e9);
  for (const [p0, p1] of z.wallSegs) {
    const l = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]), n = Math.max(1, Math.ceil(l / (Math.min(sx, sy) * 0.5)));
    for (let k = 0; k <= n; k++) {
      const x = p0[0] + (p1[0] - p0[0]) * k / n, y = p0[1] + (p1[1] - p0[1]) * k / n;
      const i = Math.floor((x - b.minx) / sx), j = Math.floor((b.maxy - y) / sy);
      if (i >= 0 && j >= 0 && i < W && j < H) D[j * W + i] = 0;
    }
  }
  const d1 = Math.min(sx, sy), d2 = d1 * Math.SQRT2;
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
    let v = D[j * W + i];
    if (i > 0) v = Math.min(v, D[j * W + i - 1] + d1);
    if (j > 0) { v = Math.min(v, D[(j - 1) * W + i] + d1); if (i > 0) v = Math.min(v, D[(j - 1) * W + i - 1] + d2); if (i < W - 1) v = Math.min(v, D[(j - 1) * W + i + 1] + d2); }
    D[j * W + i] = v;
  }
  for (let j = H - 1; j >= 0; j--) for (let i = W - 1; i >= 0; i--) {
    let v = D[j * W + i];
    if (i < W - 1) v = Math.min(v, D[j * W + i + 1] + d1);
    if (j < H - 1) { v = Math.min(v, D[(j + 1) * W + i] + d1); if (i < W - 1) v = Math.min(v, D[(j + 1) * W + i + 1] + d2); if (i > 0) v = Math.min(v, D[(j + 1) * W + i - 1] + d2); }
    D[j * W + i] = v;
  }
  const E = new Float32Array(W * H * 3);
  const warm = [1.0, 0.7, 0.42], teal = [0.05, 0.2, 0.18];
  for (let j = 0; j < H; j++) {
    const y = b.maxy - (j + 0.5) * sy;
    for (let i = 0; i < W; i++) {
      const x = b.minx + (i + 0.5) * sx;
      const pt = [x, y];
      const outdoor = z.outdoorPolys.some((p) => G.pointInPolygon(pt, p));
      let r = outdoor ? 0.32 : 0.025, g = outdoor ? 0.34 : 0.022, bl = outdoor ? 0.42 : 0.02;
      for (const lt of z.uniqueLanterns) {
        const dx = x - lt.p[0], dy = y - lt.p[1], h = Math.max(1.2, lt.h), d2 = dx * dx + dy * dy + h * h;
        if (d2 > 1600) continue;
        const e = (lt.I * h) / (d2 * Math.sqrt(d2));
        r += e * warm[0]; g += e * warm[1]; bl += e * warm[2];
      }
      if (z.waterPolys.some((mp) => G.pointInMulti(pt, mp))) { r += teal[0]; g += teal[1]; bl += teal[2]; }
      const d = D[j * W + i], s = Math.min(1, d / 1.2), ao = 0.45 + 0.55 * s * s * (3 - 2 * s);
      E[(j * W + i) * 3] = r * ao; E[(j * W + i) * 3 + 1] = g * ao; E[(j * W + i) * 3 + 2] = bl * ao;
    }
  }
  return { W, H, E };
}

// ---------------- write zone GLBs ----------------
const zoneOut = [];
for (const z of zones.values()) {
  const b = zoneBounds(z);
  z.bounds = b;
  const meshes = [];
  for (const [key, g] of z.render.groups) {
    const [role, mat] = key.split(':');
    const isWater = role === 'water';
    const lm = !isWater && MATERIALS[mat]?.lightmap !== false;
    const attrs = G.finishGroup(g.pos, { tile: 2, lmBounds: lm ? b : null });
    const m = MATERIALS[mat] ?? { color: [0.2, 0.5, 0.55] };
    meshes.push({
      name: `${z.id}_${role}_${mat}`,
      material: { name: isWater ? `water_${mat}` : mat, color: m.color, roughness: m.roughness, metalness: m.metalness, emissive: m.emissive },
      attrs: isWater ? { position: attrs.position, normal: attrs.normal } : { position: attrs.position, normal: attrs.normal, uv0: attrs.uv0, uv1: attrs.uv1 ?? undefined },
      extras: { role, material: isWater ? 'water' : mat, ...(lm ? { lightmap: `lm_${z.id}` } : {}), ...(isWater ? { water: mat } : {}) },
    });
  }
  const glb = await buildGLB(meshes);
  const partUri = writeAddressed(OUT, 'parts', 'glb', glb);
  const wpos = z.walk.group('walk').pos;
  const wglb = await buildGLB([{ name: `${z.id}_walk`, attrs: { position: new Float32Array(wpos) }, extras: { role: 'walk', zone: z.id } }]);
  const walkUri = writeAddressed(OUT, 'parts', 'glb', wglb);
  zoneOut.push({ z, partUri, glbBytes: glb.byteLength, renderTris: z.render.triCount, walkUri, walkBytes: wglb.byteLength, walkTris: wpos.length / 9 });
  console.log(`zone ${z.id}: ${z.render.triCount} tris render, ${wpos.length / 9} walk, glb ${(glb.byteLength / 1024).toFixed(0)} KB`);
}

// ---------------- data files ----------------
const isAttraction = (s) => /^\d\d\s/.test(s.name);
const MAIN_KINDS = new Set(['hall', 'cave', 'deck', 'outdoor', 'tunnel']);
// Viewpoint per space: the interior point nearest the centroid that is on dry floor (not over water, not on a
// stair hole), at least 1.5 m from walls; heading toward the space centroid (or along the long axis).
function viewpoint(s) {
  const ring = s._ring, b = G.bbox(ring), c = G.centroid(ring);
  const wet = waters.filter((w) => Math.abs(w.z - s.floor_z) < 3 && G.bboxOverlap(w.bb, b));
  const floorSl = slabs.find((sl) => sl.kind === 'floor' && sl.top === s.floor_z && sl.spaces.includes(s));
  let best = null, bd = Infinity;
  const n = 40;
  for (let i = 0; i <= n; i++) for (let j = 0; j <= n; j++) {
    const p = [b.minx + (b.maxx - b.minx) * i / n, b.miny + (b.maxy - b.miny) * j / n];
    if (!G.pointInRing(p, ring) || G.distToRing(p, ring) < 1.5) continue;
    if (wet.some((w) => G.pointInMulti(p, w.poly))) continue;
    if (floorSl && !G.pointInMulti(p, floorSl.mp)) continue;
    const d = Math.hypot(p[0] - c[0], p[1] - c[1]);
    if (d < bd) { bd = d; best = p; }
  }
  const p = best ?? G.interiorPoint(ring);
  let heading;
  if (Math.hypot(c[0] - p[0], c[1] - p[1]) > 2) heading = (Math.atan2(c[0] - p[0], c[1] - p[1]) * 180) / Math.PI;
  else heading = (b.maxx - b.minx) >= (b.maxy - b.miny) ? 90 : 0;
  return { p, heading: (heading + 360) % 360 };
}
const places = L.spaces.map((s) => {
  const vp = viewpoint(s);
  const c = vp.p;
  const yaw = +vp.heading.toFixed(1);
  return {
    id: s.id, name: s.name, level: s.level, zone: s._zone, kind: isAttraction(s) ? 'attraction' : 'place',
    number: isAttraction(s) ? Number(s.name.slice(0, 2)) : null,
    pos: [+c[0].toFixed(3), +c[1].toFixed(3), +(s.floor_z + 1.6).toFixed(3)],
    yaw_deg: yaw, pitch_deg: 0,
    label: isAttraction(s) || MAIN_KINDS.has(s.kind) ? { text: isAttraction(s) ? s.name.slice(3) : s.name, pos: (() => { const q = G.interiorPoint(s._ring); return [+q[0].toFixed(3), +q[1].toFixed(3), +(s.floor_z + 2.6).toFixed(3)]; })() } : null,
    source: 'layout-centroid',
  };
});
const placesUri = 'data/places.json';
mkdirSync(join(OUT, 'data'), { recursive: true });
writeFileSync(join(OUT, placesUri), JSON.stringify({ contract: 1, coords: 'layout', places }, null, 1));
const spacesUri = writeAddressed(OUT, 'data', 'json', Buffer.from(JSON.stringify({
  coords: 'layout',
  spaces: L.spaces.map((s) => ({ id: s.id, name: s.name, level: s.level, zone: s._zone, kind: s.kind, floor_z: s.floor_z, ceiling_z: s.ceiling_z, footprint: s._ring })),
})));
const waterOut = waters.filter((w) => w.zone).map((w) => ({
  id: w.id, kind: w.kind, zone: w.zone, z: +w.z.toFixed(3), bed_z: +w.bed.toFixed(3),
  bounds: [+w.bb.minx.toFixed(2), +w.bb.miny.toFixed(2), +w.bb.maxx.toFixed(2), +w.bb.maxy.toFixed(2)],
  planar: ['w_mirror', 'w_caldera', 'w_river', 'w_glacier', 'w_sea'].includes(w.id),
  mist: w.src.temp != null && (Array.isArray(w.src.temp) ? Math.max(...w.src.temp) : w.src.temp) >= 30 ? 1 : 0.35,
  absorption: w.id === 'w_glacier' ? [0.9, 0.25, 0.18] : [0.75, 0.16, 0.12],
  flow: w.kind === 'flow' ? 0.35 : 0.0,
}));

// ---------------- manifests ----------------
for (const tier of Object.keys(TIERS)) {
  const cfg = TIERS[tier];
  const tex = await tierTextures(tier);
  const textures = {}, materials = {};
  for (const [k, v] of Object.entries(tex)) textures[k] = v;
  for (const [k, m] of Object.entries(MATERIALS)) {
    materials[k] = { type: 'standard', baseColorTexture: m.tex ?? null, color: m.color, roughness: m.roughness, metalness: m.metalness ?? 0, emissive: m.emissive ?? null, emissiveIntensity: m.emissiveIntensity ?? 0, lightmap: m.lightmap !== false };
  }
  materials.water = { type: 'water', normalTexture: 'water_normal' };
  const zonesM = [];
  for (const zo of zoneOut) {
    const z = zo.z, b = z.bounds;
    const { W, H, E } = bakeZone(z, b, cfg.lmTexel, cfg.lmMax);
    let uri, encoding;
    if (cfg.lmEncoding === 'hdr') {
      uri = writeAddressed(OUT, 'tex', 'ktx2', await T.encodeHDR(T.writeHDR(W, H, E)));
      encoding = 'hdr';
    } else {
      const img = new Uint8Array(W * H * 4);
      for (let i = 0; i < W * H; i++) { const q = T.rgbmEncode([E[i * 3], E[i * 3 + 1], E[i * 3 + 2]], RGBM.range, RGBM.gamma); img.set(q, i * 4); }
      uri = writeAddressed(OUT, 'tex', 'ktx2', await T.encodeLDR({ data: img, width: W, height: H }, 'linear'));
      encoding = 'rgbm';
    }
    const probes = z.spaces.filter((sid) => !EXCLUDE.has(sid)).map((sid) => {
      const s = spaceById.get(sid), bb = G.bbox(s._ring), c = G.interiorPoint(s._ring);
      const top = s.ceiling_z ?? s.floor_z + 8;
      return { id: `probe_${sid}`, space: sid, center: [+c[0].toFixed(2), +c[1].toFixed(2), +(s.floor_z + 1.6).toFixed(2)], box_min: [bb.minx, bb.miny, s.floor_z - 0.3], box_max: [bb.maxx, bb.maxy, top], cubemap: null, intensity: s.ceiling_z == null ? 1.0 : 0.6 };
    });
    zonesM.push({
      id: z.id, name: z.name, neighbors: [...z.neighbors].sort(), preload: [...z.preload].filter((p) => !z.neighbors.has(p)).sort(), spaces: z.spaces,
      bounds: [b.minx, b.miny, b.maxx, b.maxy],
      parts: [{ uri: zo.partUri, bytes: zo.glbBytes, tris: zo.renderTris }],
      walk: { uri: zo.walkUri, bytes: zo.walkBytes, tris: zo.walkTris },
      lightmaps: [{ id: `lm_${z.id}`, uri, encoding, ...(encoding === 'rgbm' ? RGBM : {}), intensity: Math.PI, width: W, height: H, uv: 1 }],
      probes,
      placements: [],
    });
  }
  const manifest = {
    contract: 1, tier, source: 'standin', generated: new Date().toISOString(), layout_sha: null,
    coords: { gltf: 'three Y-up (X=x, Y=z, Z=-y)', json: 'layout z-up (x east, y north, z up, metres)' },
    color: { toneMapping: 'AgX', exposureStops: 0, lightMapIntensity: Math.PI },
    start: { place: 'g_gate' },
    textures, materials, zones: zonesM, water: waterOut,
    places: placesUri, spaces: spacesUri,
    budget: tier === 'low' ? { drawCalls: 150, triangles: 500000, textureMB: 250 } : null,
  };
  mkdirSync(join(OUT, 'manifests'), { recursive: true });
  writeFileSync(join(OUT, `manifests/${tier}.json`), JSON.stringify(manifest, null, 1));
  console.log(`manifest ${tier}: ${zonesM.length} zones`);
}
report.zones = zoneOut.map((zo) => ({ id: zo.z.id, neighbors: [...zo.z.neighbors], renderTris: zo.renderTris, walkTris: zo.walkTris, glbKB: +(zo.glbBytes / 1024).toFixed(1) }));
report.seconds = (Date.now() - t0) / 1000;
writeFileSync(join(OUT, 'standin-report.json'), JSON.stringify(report, null, 1));
console.log(`stand-in built in ${report.seconds.toFixed(1)} s, ${report.warnings.length} warnings -> ${OUT}`);
