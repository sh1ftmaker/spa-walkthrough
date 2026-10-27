#!/usr/bin/env node
// Build a flythrough route along a stair connection from 3d/layout.json.
//   node tools/make-route.mjs <connection id> <z from> <z to> [--layout ../3d/layout.json] > tools/routes/name.json
// Output: { start, points: [[x, y, zEye], ...] } in layout coords (eye = floor + 1.6).
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const [cid, zFromS, zToS] = process.argv.slice(2);
const li = process.argv.indexOf('--layout');
const here = dirname(fileURLToPath(import.meta.url));
const L = JSON.parse(readFileSync(li > 0 ? process.argv[li + 1] : resolve(here, '../../3d/layout.json'), 'utf8'));
const c = L.connections.find((q) => q.id === cid);
if (!c) { console.error(`no connection ${cid}`); process.exit(2); }
const zFrom = Number(zFromS ?? c.z_top), zTo = Number(zToS ?? c.z_bottom), EYE = 1.6;
const down = zTo < zFrom;
const spaces = new Map(L.spaces.map((s) => [s.id, s]));
const at = (z) => (c.places ?? []).map((p) => spaces.get(p)).find((s) => s && Math.abs(s.floor_z - z) < 0.3);
const sFrom = at(zFrom), sTo = at(zTo);
const portal = (s) => s && L.portals.find((p) => (p.a === s.id && p.b === cid) || (p.b === s.id && p.a === cid));
let pts = [];
if (c.kind === 'helix') {
  const inRange = c.path.filter((p) => (down ? p[2] <= zFrom + 1e-3 && p[2] >= zTo - 1e-3 : p[2] >= zFrom - 1e-3 && p[2] <= zTo + 1e-3));
  const seq = down ? inRange : inRange.slice().reverse();
  pts = seq.filter((_, i) => i % 4 === 0 || i === seq.length - 1).map((p) => [p[0], p[1], p[2] + EYE]);
} else if (c.plan) {
  const pl = c.plan; let L2 = 0; const seg = [];
  for (let i = 1; i < pl.length; i++) { const l = Math.hypot(pl[i][0] - pl[i - 1][0], pl[i][1] - pl[i - 1][1]); seg.push(l); L2 += l; }
  const zAt = (s) => c.z_top - (c.z_top - c.z_bottom) * (s / L2);
  for (let s = 0, i = 0, acc = 0; s <= L2; s += 2) {
    while (i < seg.length - 1 && s > acc + seg[i]) { acc += seg[i]; i++; }
    const t = Math.min(1, (s - acc) / seg[i]);
    pts.push([pl[i][0] + (pl[i + 1][0] - pl[i][0]) * t, pl[i][1] + (pl[i + 1][1] - pl[i][1]) * t, zAt(s) + EYE]);
  }
  pts.push([pl[pl.length - 1][0], pl[pl.length - 1][1], c.z_bottom + EYE]);
  if (!down) pts.reverse();
} else { console.error(`connection kind ${c.kind} not supported`); process.exit(2); }
const pa = portal(sFrom), pb = portal(sTo);
if (pa) pts.unshift([pa.at[0], pa.at[1], zFrom + EYE]);
if (pb) pts.push([pb.at[0], pb.at[1], zTo + EYE]);
if (pb && c.center) { const dx = pb.at[0] - c.center[0], dy = pb.at[1] - c.center[1], l = Math.hypot(dx, dy); pts.push([pb.at[0] + (dx / l) * 3, pb.at[1] + (dy / l) * 3, zTo + EYE]); }
const r3 = (v) => Math.round(v * 1000) / 1000;
console.log(JSON.stringify({ start: sFrom?.id ?? null, connection: cid, from_z: zFrom, to_z: zTo, generated_from: 'layout.json', points: pts.map((p) => p.map(r3)) }));
