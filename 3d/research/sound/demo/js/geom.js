// 2D/3D geometry helpers in layout metres (x east, y north, z up).
export const dist2 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
export const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], (a[2] || 0) - (b[2] || 0));

export function pointInPoly(p, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi + 1e-12) + xi) inside = !inside;
  }
  return inside;
}
export function nearestOnSeg(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1]; const L = dx * dx + dy * dy;
  const t = L > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L)) : 0;
  return [a[0] + t * dx, a[1] + t * dy, t];
}
// Nearest point on an open polyline. Returns [x, y, segIndex, t].
export function nearestOnPolyline(p, pts) {
  if (pts.length === 1) return [pts[0][0], pts[0][1], 0, 0];
  let best = null, bd = Infinity;
  for (let i = 0; i < pts.length - 1; i++) {
    const q = nearestOnSeg(p, pts[i], pts[i + 1]); const d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2;
    if (d < bd) { bd = d; best = [q[0], q[1], i, q[2]]; }
  }
  return best;
}
// Nearest point on a closed polygon boundary, or p itself when inside. Returns [x, y, inside].
export function nearestOnPolygon(p, poly) {
  if (pointInPoly(p, poly)) return [p[0], p[1], true];
  const q = nearestOnPolyline(p, [...poly, poly[0]]);
  return [q[0], q[1], false];
}
export function polyArea(poly) { let a = 0; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) a += (poly[j][0] + poly[i][0]) * (poly[j][1] - poly[i][1]); return Math.abs(a / 2); }
export function centroid(poly) { let x = 0, y = 0; for (const p of poly) { x += p[0]; y += p[1]; } return [x / poly.length, y / poly.length]; }
export function polylineLength(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += dist2(pts[i - 1], pts[i]); return L; }
export function pointAlong(pts, u) { // u in [0,1] along the polyline length
  const L = polylineLength(pts); let s = u * L;
  for (let i = 1; i < pts.length; i++) { const d = dist2(pts[i - 1], pts[i]); if (s <= d || i === pts.length - 1) { const t = d > 0 ? Math.min(1, s / d) : 0; return [pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]), pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1])]; } s -= d; }
  return pts[pts.length - 1];
}
export function randomInPoly(poly, R) {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  for (const [x, y] of poly) { minx = Math.min(minx, x); maxx = Math.max(maxx, x); miny = Math.min(miny, y); maxy = Math.max(maxy, y); }
  for (let k = 0; k < 40; k++) { const p = [minx + R() * (maxx - minx), miny + R() * (maxy - miny)]; if (pointInPoly(p, poly)) return p; }
  return centroid(poly);
}
