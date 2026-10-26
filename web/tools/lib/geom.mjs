// Geometry helpers for the stand-in builder.
// Layout space: x east, y north, z up (metres). three/glTF space: X = x, Y = z, Z = -y.
import * as THREE from 'three';
import pc from 'polygon-clipping';

export const toThree = (x, y, z) => [x, z, -y];

// ---------- 2D polygon helpers (layout xy) ----------
export function ringArea(r) {
  let a = 0;
  for (let i = 0; i < r.length; i++) {
    const [x1, y1] = r[i], [x2, y2] = r[(i + 1) % r.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}
export function openRing(r) {
  if (r.length > 1) {
    const a = r[0], b = r[r.length - 1];
    if (a[0] === b[0] && a[1] === b[1]) return r.slice(0, -1);
  }
  return r;
}
export function closeRing(r) {
  r = openRing(r);
  return [...r, r[0]];
}
export function pointInRing(p, ring) {
  let inside = false;
  const [x, y] = p;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-30) + xi) inside = !inside;
  }
  return inside;
}
export function pointInPolygon(p, poly) {
  // poly: [outer, ...holes]
  if (!pointInRing(p, poly[0])) return false;
  for (let i = 1; i < poly.length; i++) if (pointInRing(p, poly[i])) return false;
  return true;
}
export function pointInMulti(p, mp) {
  for (const poly of mp) if (pointInPolygon(p, poly)) return true;
  return false;
}
export function bbox(points) {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  for (const [x, y] of points) {
    if (x < minx) minx = x; if (y < miny) miny = y;
    if (x > maxx) maxx = x; if (y > maxy) maxy = y;
  }
  return { minx, miny, maxx, maxy };
}
export function multiBBox(mp) {
  const pts = [];
  for (const poly of mp) for (const p of poly[0]) pts.push(p);
  return bbox(pts);
}
export const bboxOverlap = (a, b, m = 0) =>
  a.minx - m <= b.maxx && b.minx - m <= a.maxx && a.miny - m <= b.maxy && b.miny - m <= a.maxy;

export function centroid(ring) {
  ring = openRing(ring);
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i], [x2, y2] = ring[(i + 1) % ring.length];
    const f = x1 * y2 - x2 * y1;
    a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f;
  }
  if (Math.abs(a) < 1e-9) {
    const b = bbox(ring);
    return [(b.minx + b.maxx) / 2, (b.miny + b.maxy) / 2];
  }
  return [cx / (3 * a), cy / (3 * a)];
}
// A point guaranteed inside the polygon (centroid if inside, else nearest interior sample).
export function interiorPoint(ring) {
  const c = centroid(ring);
  if (pointInRing(c, ring)) return c;
  const b = bbox(ring);
  let best = null, bd = Infinity;
  for (let i = 1; i < 30; i++) for (let j = 1; j < 30; j++) {
    const p = [b.minx + (b.maxx - b.minx) * i / 30, b.miny + (b.maxy - b.miny) * j / 30];
    if (!pointInRing(p, ring)) continue;
    const d = Math.hypot(p[0] - c[0], p[1] - c[1]) - 0.3 * distToRing(p, ring);
    if (d < bd) { bd = d; best = p; }
  }
  return best ?? c;
}
export function distPointSeg(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy || 1e-12;
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2;
  t = Math.max(0, Math.min(1, t));
  return { d: Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy), t };
}
export function distToRing(p, ring) {
  let d = Infinity;
  for (let i = 0; i < ring.length; i++) d = Math.min(d, distPointSeg(p, ring[i], ring[(i + 1) % ring.length]).d);
  return d;
}
export const rect = (x0, y0, x1, y1) => [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]];
// oriented rectangle from segment a->b with half width hw
export function segRect(a, b, hw, ext0 = 0, ext1 = 0) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l = Math.hypot(dx, dy) || 1e-9;
  const ux = dx / l, uy = dy / l, nx = -uy * hw, ny = ux * hw;
  const a2 = [a[0] - ux * ext0, a[1] - uy * ext0], b2 = [b[0] + ux * ext1, b[1] + uy * ext1];
  return [[[a2[0] - nx, a2[1] - ny], [b2[0] - nx, b2[1] - ny], [b2[0] + nx, b2[1] + ny], [a2[0] + nx, a2[1] + ny]]];
}
export function circlePoly(c, r, n = 24) {
  const ring = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    ring.push([c[0] + r * Math.cos(a), c[1] + r * Math.sin(a)]);
  }
  return [ring];
}
export function annularSector(c, r0, r1, a0, a1, maxStep = 0.12) {
  if (a1 < a0) [a0, a1] = [a1, a0];
  const n = Math.max(1, Math.ceil((a1 - a0) / maxStep));
  const outer = [], inner = [];
  for (let i = 0; i <= n; i++) {
    const a = a0 + (a1 - a0) * i / n;
    outer.push([c[0] + r1 * Math.cos(a), c[1] + r1 * Math.sin(a)]);
    inner.push([c[0] + r0 * Math.cos(a), c[1] + r0 * Math.sin(a)]);
  }
  return [[...outer, ...inner.reverse()]];
}
export function convexHull(points) {
  const p = points.map((q) => [q[0], q[1]]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [], upper = [];
  for (const q of p) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], q) <= 0) lower.pop(); lower.push(q); }
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], q) <= 0) upper.pop(); upper.push(q); }
  upper.pop(); lower.pop();
  return [lower.concat(upper)];
}

// polygon-clipping wrappers (accept Polygon or MultiPolygon, always return MultiPolygon)
export const union = (...g) => (g.length ? pc.union(...g) : []);
export const difference = (a, ...b) => (b.length ? pc.difference(a, ...b) : pc.union(a));
export const intersection = (a, b) => pc.intersection(a, b);

// polyline helpers
export function polylineLength(pl) {
  let L = 0;
  for (let i = 1; i < pl.length; i++) L += Math.hypot(pl[i][0] - pl[i - 1][0], pl[i][1] - pl[i - 1][1]);
  return L;
}
export function polylineAt(pl, s) {
  let acc = 0;
  for (let i = 1; i < pl.length; i++) {
    const a = pl[i - 1], b = pl[i];
    const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (s <= acc + l || i === pl.length - 1) {
      const t = l > 0 ? Math.max(0, Math.min(1, (s - acc) / l)) : 0;
      return { p: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], seg: i - 1, dir: [(b[0] - a[0]) / (l || 1), (b[1] - a[1]) / (l || 1)] };
    }
    acc += l;
  }
  return { p: pl[pl.length - 1], seg: pl.length - 2, dir: [1, 0] };
}
// split [s0,s1] into per-segment pieces: [{a,b}] (2D points)
export function polylinePieces(pl, s0, s1) {
  const out = [];
  let acc = 0;
  for (let i = 1; i < pl.length; i++) {
    const a = pl[i - 1], b = pl[i];
    const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const lo = Math.max(s0, acc), hi = Math.min(s1, acc + l);
    if (hi > lo + 1e-6 && l > 0) {
      const ta = (lo - acc) / l, tb = (hi - acc) / l;
      out.push({ a: [a[0] + (b[0] - a[0]) * ta, a[1] + (b[1] - a[1]) * ta], b: [a[0] + (b[0] - a[0]) * tb, a[1] + (b[1] - a[1]) * tb], seg: i - 1 });
    }
    acc += l;
  }
  return out;
}

// ---------- mesh accumulation (three space) ----------
export class MeshAcc {
  constructor() { this.groups = new Map(); }
  group(key) {
    let g = this.groups.get(key);
    if (!g) { g = { pos: [] }; this.groups.set(key, g); }
    return g;
  }
  // a, b, c: three-space [x,y,z]
  tri(key, a, b, c) { this.group(key).pos.push(...a, ...b, ...c); }
  quad(key, a, b, c, d) { this.tri(key, a, b, c); this.tri(key, a, c, d); }
  get triCount() { let n = 0; for (const g of this.groups.values()) n += g.pos.length / 9; return n; }
}

// Triangulate a polygon ([outer, ...holes], layout xy) and emit the face at height z.
export function emitFlat(acc, key, poly, z, up = true) {
  let outer = openRing(poly[0]);
  if (outer.length < 3) return;
  if (ringArea(outer) < 0) outer = outer.slice().reverse();
  const holes = poly.slice(1).map(openRing).filter((h) => h.length >= 3).map((h) => (ringArea(h) > 0 ? h.slice().reverse() : h));
  const contour = outer.map(([x, y]) => new THREE.Vector2(x, y));
  const hv = holes.map((h) => h.map(([x, y]) => new THREE.Vector2(x, y)));
  const faces = THREE.ShapeUtils.triangulateShape(contour, hv);
  const all = [...outer, ...holes.flat()];
  for (const [i, j, k] of faces) {
    const A = toThree(all[i][0], all[i][1], z), B = toThree(all[j][0], all[j][1], z), C = toThree(all[k][0], all[k][1], z);
    // decide winding by actual normal (three Y)
    const n = (B[2] - A[2]) * (C[0] - A[0]) - (B[0] - A[0]) * (C[2] - A[2]);
    const isUp = n > 0;
    if (isUp === up) acc.tri(key, A, B, C); else acc.tri(key, A, C, B);
  }
}
// vertical quad between 2D points a,b from z0 to z1 (normal to the right of a->b if CCW)
export function emitWallQuad(acc, key, a, b, z0, z1) {
  if (z1 - z0 < 1e-4) return;
  acc.quad(key, toThree(a[0], a[1], z0), toThree(b[0], b[1], z0), toThree(b[0], b[1], z1), toThree(a[0], a[1], z1));
}
export function emitPrism(acc, key, poly, z0, z1, { top = true, bottom = true, sides = true } = {}) {
  if (top) emitFlat(acc, key, poly, z1, true);
  if (bottom) emitFlat(acc, key, poly, z0, false);
  if (sides) for (const r of poly) {
    let ring = openRing(r);
    for (let i = 0; i < ring.length; i++) emitWallQuad(acc, key, ring[i], ring[(i + 1) % ring.length], z0, z1);
  }
}
export function emitMultiPrism(acc, key, mp, z0, z1, opts) {
  for (const poly of mp) emitPrism(acc, key, poly, z0, z1, opts);
}

// Build final attribute arrays for a group: flat normals, uv0 box-mapped (tile metres), uv1 top-down in bounds
export function finishGroup(pos, { tile = 2, lmBounds = null } = {}) {
  const n = pos.length / 3;
  const normal = new Float32Array(n * 3), uv0 = new Float32Array(n * 2), uv1 = lmBounds ? new Float32Array(n * 2) : null;
  for (let t = 0; t < n; t += 3) {
    const ax = pos[t * 3], ay = pos[t * 3 + 1], az = pos[t * 3 + 2];
    const bx = pos[t * 3 + 3], by = pos[t * 3 + 4], bz = pos[t * 3 + 5];
    const cx = pos[t * 3 + 6], cy = pos[t * 3 + 7], cz = pos[t * 3 + 8];
    let nx = (by - ay) * (cz - az) - (bz - az) * (cy - ay);
    let ny = (bz - az) * (cx - ax) - (bx - ax) * (cz - az);
    let nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
    const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
    const anx = Math.abs(nx), any = Math.abs(ny), anz = Math.abs(nz);
    for (let k = 0; k < 3; k++) {
      const v = t + k, x = pos[v * 3], y = pos[v * 3 + 1], z = pos[v * 3 + 2];
      normal[v * 3] = nx; normal[v * 3 + 1] = ny; normal[v * 3 + 2] = nz;
      let u, w;
      if (any >= anx && any >= anz) { u = x; w = z; } else if (anx >= anz) { u = z; w = y; } else { u = x; w = y; }
      uv0[v * 2] = u / tile; uv0[v * 2 + 1] = w / tile;
      if (uv1) {
        // layout (x, y) = (X, -Z)
        const lx = x, ly = -z;
        uv1[v * 2] = (lx - lmBounds.minx) / (lmBounds.maxx - lmBounds.minx);
        uv1[v * 2 + 1] = 1 - (ly - lmBounds.miny) / (lmBounds.maxy - lmBounds.miny);
      }
    }
  }
  return { position: new Float32Array(pos), normal, uv0, uv1 };
}
