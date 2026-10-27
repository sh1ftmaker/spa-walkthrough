"""kzgeo_falls_lip_rock: station-profile rock helpers (used by gen_falls_lip_rock and gen_spill_lip).

A rock body is a list of X stations, each a profile in the YZ plane ordered counter-clockwise when seen
from +X (front-bottom -> up the front face -> back over the top -> down the back), open along the bottom
(it sits in the ground). `grid` bridges the stations into quads, `fan_cap` closes an end station with a
domed fan (robust on concave, overhanging profiles where a single n-gon would triangulate badly).
"""
import math

from mathutils import Vector, noise


def smoothstep(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def prof_normals(pts):
    """outward 2D normals (ny, nz) of a CCW open profile [(y, z)] by central differences"""
    out = []
    n = len(pts)
    for i in range(n):
        a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
        dy, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dy, dz) or 1.0
        out.append((dz / L, -dy / L))
    return out


def craggy(p, off, freq):
    """fractured-basalt displacement in [-1, 1]: a low octave plus a ridged (abs) octave that makes edges"""
    q = Vector(p) * freq + off
    a = noise.noise(q)
    b = 1.0 - 2.0 * abs(noise.noise(q * 2.3 + Vector((5.1, 2.7, 9.3))))
    c = noise.noise(q * 5.1 + Vector((1.3, 7.7, 3.1)))
    return 0.55 * a + 0.3 * b + 0.15 * c


def grid(mb, P, mi_fn):
    """P[i][j]: Vector at station i, profile point j. Quads between neighbouring stations; mi_fn(i, j, centre)
    returns the slot of face (i, j). Returns (verts grid, faces)."""
    bm = mb.bm
    V = [[bm.verts.new(p) for p in row] for row in P]
    faces = []
    for i in range(len(V) - 1):
        for j in range(len(V[i]) - 1):
            q = (V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1])
            f = bm.faces.new(q)
            c = sum((v.co for v in q), Vector()) / 4
            f.material_index = mi_fn(i, j, c)
            faces.append(f)
    return V, faces


def fan_cap(mb, ring, centre, mi):
    """close an open-bottom station profile with a fan to `centre` (plus the bottom edge back to ring[0])"""
    bm = mb.bm
    c = bm.verts.new(centre)
    faces = []
    for a, b in zip(ring[:-1], ring[1:]):
        f = bm.faces.new((a, b, c)); f.material_index = mi; faces.append(f)
    f = bm.faces.new((ring[-1], ring[0], c)); f.material_index = mi; faces.append(f)
    return faces


def stations(keys, n, weights=None):
    """distribute about n stations over the sorted key x positions; every key is kept (notch walls stay crisp).
    weights[k] scales the density of segment k."""
    keys = sorted(set(round(k, 5) for k in keys))
    segs = list(zip(keys[:-1], keys[1:]))
    weights = weights or [1.0] * len(segs)
    tot = sum((b - a) * w for (a, b), w in zip(segs, weights)) or 1.0
    xs = [keys[0]]
    extra = max(0, n - len(keys))
    for (a, b), w in zip(segs, weights):
        k = int(round(extra * (b - a) * w / tot))
        for s in range(1, k + 1):
            xs.append(a + (b - a) * s / (k + 1))
        xs.append(b)
    return xs
