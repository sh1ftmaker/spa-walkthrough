"""kzgeo_railing: path sampling and railing parts for gen_railing (run inside Blender).

A railing runs along a 3D polyline (x, y, z): z follows stair treads (rails slope with the path, posts
and balusters stay vertical). Parts:
  Path(pts)                      arc-length sampler: at(s) -> (point, plan tangent, yaw)
  stations(path, ds)             rail stations: ends + corners for straight runs, uniform ds on curves
  vprism(...)                    vertical oriented prism (posts, balusters), optional chamfer / caps
  rail(...)                      a profile swept along the path between s0 and s1 at height dz
  plinth_blocks(...)             rough-cut basalt blocks (convex hulls of jittered corners) along the path
  band(...)                      iron band wrapped round a post (the sheet's corner brackets)
"""
import math

from mathutils import Vector

import kzgeo_common as C
import kzgeo_parapet_stone as P


class Path:
    def __init__(self, pts):
        self.p = [Vector((float(q[0]), float(q[1]), float(q[2]) if len(q) > 2 else 0.0)) for q in pts]
        self.segs, L = [], 0.0
        for a, b in zip(self.p[:-1], self.p[1:]):
            l = (b - a).length
            if l < 1e-6:
                continue
            self.segs.append((L, L + l, a, (b - a) / l))
            L += l
        self.L = L

    def at(self, s):
        s = max(0.0, min(self.L, s))
        for s0, s1, a, d in self.segs:
            if s <= s1 + 1e-9:
                break
        p = a + d * (s - s0)
        t = Vector((d.x, d.y, 0.0))
        t = t.normalized() if t.length > 1e-6 else Vector((1, 0, 0))
        return p, t, math.atan2(t.y, t.x)

    def corners(self, min_deg=12.0):
        out = []
        for (s0, s1, a, d), (_, _, _, d2) in zip(self.segs[:-1], self.segs[1:]):
            if math.degrees(d.angle(d2, 0.0)) > min_deg:
                out.append(s1)
        return out

    def curved(self):
        return any(math.degrees(d.angle(d2, 0.0)) > 0.5 for (_, _, _, d), (_, _, _, d2) in zip(self.segs[:-1], self.segs[1:]))


def stations(path, s0, s1, ds):
    """sample positions between s0 and s1: ends + sharp corners; on curved paths every ~ds metres"""
    ss = {round(s0, 5), round(s1, 5)}
    for c in path.corners():
        if s0 < c < s1:
            ss.add(round(c, 5))
    if path.curved() and ds:
        n = max(1, int(math.ceil((s1 - s0) / ds)))
        for k in range(1, n):
            ss.add(round(s0 + (s1 - s0) * k / n, 5))
    return sorted(ss)


def vprism(mb, xy, yaw, w, d, z0, z1, mi, ch=0.0, cap_top=True, cap_bot=False, sides=None):
    """vertical prism, w along the path tangent, d across it; ch > 0 chamfers the 4 vertical edges.
    sides=3 gives a cheap triangular baluster (LOD1)."""
    c, s = math.cos(yaw), math.sin(yaw)
    if sides == 3:
        loc = [(0.0, d * 0.58), (-w * 0.5, -d * 0.29), (w * 0.5, -d * 0.29)]
    elif ch > 0:
        a, b = w / 2, d / 2
        loc = [(a - ch, -b), (a, -b + ch), (a, b - ch), (a - ch, b), (-a + ch, b), (-a, b - ch), (-a, -b + ch), (-a + ch, -b)]
    else:
        a, b = w / 2, d / 2
        loc = [(a, -b), (a, b), (-a, b), (-a, -b)]
    poly = [(xy[0] + x * c - y * s, xy[1] + x * s + y * c) for x, y in loc]
    fs = mb.poly_prism(poly, z0, z1, mi)
    # poly_prism adds [bottom, top, sides...]: drop the caps nobody sees
    dead = []
    if not cap_bot:
        dead.append(fs[0])
    if not cap_top:
        dead.append(fs[1])
    for f in dead:
        mb.bm.faces.remove(f)
    return [f for f in fs if f.is_valid]


def rail(mb, path, s0, s1, dz, prof, mi, ds, caps=True, offset=0.0):
    """sweep `prof` [(x, z)] along the path from s0 to s1, dz above the path (z follows treads).
    offset shifts the rail sideways (+ = to the left of the travel direction)."""
    pts = []
    for s in stations(path, s0, s1, ds):
        p, t, _ = path.at(s)
        n = Vector((-t.y, t.x, 0.0))
        pts.append(p + Vector((0, 0, dz)) + n * offset)
    if len(pts) < 2:
        return []
    return C.sweep(mb, pts, prof, mi, caps=caps)


def rect_prof(w, h, ch=0.0):
    a, b = w / 2, h / 2
    if ch <= 0:
        return [(a, -b), (a, b), (-a, b), (-a, -b)]
    return [(a, -b + ch), (a, b - ch), (a - ch, b), (-a + ch, b), (-a, b - ch), (-a, -b + ch), (-a + ch, -b), (a - ch, -b)]


def round_prof(r, n, ell=1.0):
    return [(r * math.cos(2 * math.pi * k / n + math.pi / n), r * ell * math.sin(2 * math.pi * k / n + math.pi / n)) for k in range(n)]


def cap_rail_prof(w, h, lod):
    """the spiral-stair rail: wide, flat-bellied, strongly rounded top (mushroom section), centred at z 0"""
    a = w / 2
    if lod == 0:
        pts = [(a * 0.62, -h / 2), (a * 0.98, -h * 0.30), (a, h * 0.02), (a * 0.88, h * 0.30), (a * 0.55, h * 0.47),
               (0.0, h / 2)]
    elif lod == 1:
        pts = [(a * 0.7, -h / 2), (a, -h * 0.1), (a * 0.7, h * 0.4), (0.0, h / 2)]
    else:
        pts = [(a * 0.8, -h / 2), (a * 0.8, h * 0.3)]
    right = [(x, z) for x, z in pts if x > 0]
    left = [(-x, z) for x, z in reversed(right)]
    top = [(x, z) for x, z in pts if x == 0]
    return right + top + left if top else right + left


def plinth_blocks(mb, path, s0, s1, h, d, mi, r, blen, lod, gap=0.012):
    """rough-cut basalt blocks along the path; each is a convex hull of jittered corners (planar facets, no
    knife edges). LOD0 adds a bulge point on each long face; LOD2+ makes one block per run."""
    L = s1 - s0
    if lod >= 2:
        n = 1
    else:
        n = max(1, int(round(L / blen)))
    edges = [s0 + L * k / n for k in range(n + 1)]
    for k in range(n):
        a, b = edges[k] + (gap / 2 if k else 0), edges[k + 1] - (gap / 2 if k < n - 1 else 0)
        dh = r.uniform(-0.012, 0.012) if lod < 2 else 0.0
        dd = r.uniform(-0.01, 0.012) if lod < 2 else 0.0
        jit = 0.008 if lod == 0 else (0.004 if lod == 1 else 0.0)
        pts = []
        for s in (a, b):
            p, t, _ = path.at(s)
            nrm = Vector((-t.y, t.x, 0.0))
            for side in (-1, 1):
                for zz in (0.0, h + dh):
                    inset = 0.018 if zz > 0 else 0.0          # top arris knocked back: chamfered look
                    q = p + nrm * side * (d / 2 + dd - inset) + Vector((0, 0, zz))
                    q += Vector((r.uniform(-jit, jit), r.uniform(-jit, jit), r.uniform(-jit, jit) if zz > 0 else 0.0))
                    pts.append(q)
                if lod == 0:                      # shoulder points: top arris chamfer reads as hand-cut
                    q = p + nrm * side * (d / 2 + dd) + Vector((0, 0, h + dh - 0.022))
                    pts.append(q)
        if lod == 0:
            for frac in (0.3, 0.7):
                s = a + (b - a) * frac
                p, t, _ = path.at(s)
                nrm = Vector((-t.y, t.x, 0.0))
                for side in (-1, 1):
                    pts.append(p + nrm * side * (d / 2 + dd + r.uniform(0.004, 0.014)) + Vector((0, 0, h * r.uniform(0.35, 0.65))))
        P.hull(mb, pts, mi)


def band(mb, xy, yaw, w, d, z, hgt, mi, t=0.007):
    """iron band (bracket plate) wrapped round a post at height z"""
    return vprism(mb, xy, yaw, w + 2 * t, d + 2 * t, z - hgt / 2, z + hgt / 2, mi, cap_top=True, cap_bot=True)
