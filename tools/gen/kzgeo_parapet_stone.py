"""kzgeo_parapet_stone: rough basalt block courses with a flat paving cap, along any 2D polyline.

Used by gen_parapet_stone (per metre) and gen_bridge_slab (the bridge parapets). Built on kzgeo_common
(sweep for the cap, convex hulls for the rough-cut blocks). Every block is a closed convex hull of
jittered corner points, so each stone has crisp planar faces and no knife edges.

wall(mb, path, z_base, height, thickness, lod, r, ...) adds the faces to a genlib.MeshBuilder:
  * courses: horizontal bands of height `course`; each band is cut into blocks of length `blen` with a
    seeded running-bond offset. Vertical mortar gap GAP between neighbours.
  * batter: the wall narrows towards the top by `batter` of its half-thickness.
  * cap: a flat coping course, `cap_h` tall, overhanging the wall face by `overhang` (sweep profile).
  * drains (LOD0 only): `drains` openings, 0.14 m wide and 0.09 m high, in the bottom course, each
    capped by a lintel block.
  * LOD2: two full-length bands + a 4-sided cap. LOD3: one trapezoid (8 points), wider at the top so the
    overhang reads in silhouette.
"""
import random

import bmesh
from mathutils import Vector

import kzgeo_common as C

GAP = 0.012          # mortar joint, m
DRAIN_W = 0.14       # drain opening width, m
DRAIN_H = 0.09       # drain opening height, m
CHAMFER = 0.012      # cap top chamfer at LOD0, m


def _path(path):
    """centre polyline -> (length, NT(s)) with NT(s) -> (point, horizontal normal, tangent)."""
    pts = [Vector((p[0], p[1], 0.0)) for p in path]
    segs, L = [], 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        d = b - a
        l = d.length
        segs.append((L, L + l, a, d / l))
        L += l

    def NT(s):
        s = max(0.0, min(L, s))
        for s0, s1, a, t in segs:
            if s <= s1 + 1e-9:
                p = a + t * (s - s0)
                return p, Vector((-t.y, t.x, 0.0)), t
        s0, s1, a, t = segs[-1]
        p = a + t * (s1 - s0)
        return p, Vector((-t.y, t.x, 0.0)), t
    return L, NT


def hull(mb, pts, mi):
    """Convex hull of points (closed solid, planar facets). Interior points are dropped."""
    bm = mb.bm
    vs = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs)
    dead = list({g for g in res['geom_interior'] + res['geom_unused']
                 if isinstance(g, bmesh.types.BMVert) and g.is_valid})
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='VERTS')
    faces = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace) and g.is_valid]
    mb._tag(faces, mi)
    return faces


def _breaks(L, blen, r, lead=None):
    """Block boundaries along [0, L]: running bond with block lengths blen * U(0.8, 1.25)."""
    s = -r.uniform(0.0, blen) if lead is None else lead
    out = []
    while s < L - 1e-6:
        step = blen * r.uniform(0.8, 1.25)
        a, b = s, s + step
        if b > L - 0.5 * blen * 0.8:          # last block takes the remainder (no sliver)
            b = L
        out.append([max(0.0, a), min(L, b), False])
        s = b
    out = [o for o in out if o[1] - o[0] > 0.06]
    out[0][0] = 0.0
    out[-1][1] = L
    return out


def _split_drain(breaks, s_d):
    """Cut block breaks at s_d and s_d + DRAIN_W; the middle piece becomes a lintel (flag True)."""
    for i, (a, b, _) in enumerate(breaks):
        if a < s_d < b and s_d + DRAIN_W < b:
            return breaks[:i] + [[a, s_d, False], [s_d, s_d + DRAIN_W, True], [s_d + DRAIN_W, b, False]] + breaks[i + 1:]
    return breaks


def wall(mb, path, z_base, height, thickness, lod, r, mi_block, mi_base, mi_cap,
         course=0.22, blen=0.45, cap_h=0.09, overhang=0.025, batter=0.03, drains=0, wet_base=False):
    """Add one parapet to the bmesh. path: [(x, y), ...] centre line, z_base: bottom z, height: bottom to
    the top of the cap, thickness: wall body thickness (cap adds overhang on each face).
    r: rng stream for the block layout and jitter (one stream per wall). Returns the list of faces."""
    L, NT = _path(path)
    rb = random.Random(r.random())             # block layout stream: same joints at every LOD
    drain_at = [rb.uniform(0.15, max(0.16, L - 0.3)) for _ in range(2)]   # always drawn
    top = z_base + height - cap_h              # wall top: the cap sits above it
    H = top - z_base
    t0 = thickness / 2.0
    hw = t0 + overhang
    faces = []

    def tz(z):                                 # half thickness at height z (batter narrows the top)
        return t0 * (1.0 - batter * (z - z_base) / max(H, 1e-6))

    def block(sA, sB, zA, zB, mi, jit, mids):
        """Closed hull of one block. LOD0 (mids): 3 stations x 2 sides x 2 heights, a 15 mm chamfer on the
        top edges, a bulge on each side face at mid height, and a per-block face offset (each stone
        proud or set back of its neighbours). A convex hull ignores inward points: roughness is outward."""
        sM = 0.5 * (sA + sB)
        off = [r.uniform(-0.010, 0.012), r.uniform(-0.010, 0.012)] if mids else [0.0, 0.0]
        pts = []
        for s in ([sA, sM, sB] if mids else [sA, sB]):
            p, n, _ = NT(s)
            for k, side in enumerate((-1.0, 1.0)):
                for z in (zA, zB):
                    q = p + n * side * (tz(z) + off[k])
                    q.z = z
                    pts.append(q)
                if mids:                                   # top edge chamfer, 15 mm
                    q = p + n * side * (tz(zB) + off[k] - 0.015)
                    q.z = zB - 0.015
                    pts.append(q)
        if mids:
            zM = 0.5 * (zA + zB)
            p, n, _ = NT(sM)
            for k, side in enumerate((-1.0, 1.0)):
                q = p + n * side * (tz(zM) + off[k] + r.uniform(0.002, 0.009))
                q.z = zM + r.uniform(-0.015, 0.015)
                pts.append(q)
        if jit > 0:
            pts = [p + Vector((r.uniform(-jit, jit), r.uniform(-jit, jit), r.uniform(-jit, jit))) for p in pts]
        return hull(mb, pts, mi)

    if lod == 3:
        # one trapezoid: base at the wall face, top widened by the cap overhang
        pts = []
        for s, z, w in ((0.0, z_base, t0), (L, z_base, t0), (0.0, z_base + height, hw), (L, z_base + height, hw)):
            p, n, _ = NT(s)
            for side in (-1.0, 1.0):
                q = p + n * side * w
                q.z = z
                pts.append(q)
        return hull(mb, pts, mi_block)

    if lod == 2:
        bands = [(z_base, z_base + H * 0.5), (z_base + H * 0.5, top)]
    else:
        nC = max(1, round(H / course))
        bands = [(z_base + H * i / nC, z_base + H * (i + 1) / nC) for i in range(nC)]

    for bi, (zb0, zb1) in enumerate(bands):
        zA = zb0 + (GAP / 2 if zb0 > z_base + 1e-6 else 0.0)
        zB = zb1 - (GAP / 2 if zb1 < top - 1e-6 else 0.0)
        mi = mi_base if (bi == 0 and wet_base) else mi_block
        if lod == 2:
            breaks = [[0.0, L, False]]
        else:
            breaks = _breaks(L, blen, rb)                  # drawn for every LOD (same joints)
            if bi == 0:
                for k in range(drains):
                    breaks = _split_drain(breaks, drain_at[k])
            if lod == 1 and len(breaks) >= 4:              # LOD1 budget: merge joint pairs in busy courses
                merged, k = [], 0
                while k < len(breaks):
                    a = breaks[k]
                    if k + 1 < len(breaks):
                        merged.append([a[0], breaks[k + 1][1], False]); k += 2
                    else:
                        merged.append(a); k += 1
                breaks = merged
            if lod in (2, 3):
                breaks = [[0.0, L, False]]
        for a, b, lintel in breaks:
            if lod == 3 or (lintel and lod != 0):
                continue
            sA = a + (GAP / 2 if a > 1e-6 else 0.0)
            sB = b - (GAP / 2 if b < L - 1e-6 else 0.0)
            if lintel:
                faces += block(sA, sB, z_base + DRAIN_H, zB, mi_block, 0.0, False)
                continue
            jit = 0.010 if lod == 0 else 0.0
            faces += block(sA, sB, zA, zB, mi, jit, mids=(lod == 0))

    # cap: a coping course along the path vertices, overhanging both faces
    pts = [Vector((x, y, top)) for x, y in path]
    if lod == 0:
        ch = CHAMFER
        prof = [(-hw, 0.0), (hw, 0.0), (hw, cap_h * 0.45), (hw - ch, cap_h), (-hw + ch, cap_h), (-hw, cap_h * 0.45)]
    else:
        prof = [(-hw, 0.0), (hw, 0.0), (hw, cap_h), (-hw, cap_h)]
    faces += C.sweep(mb, pts, prof, mi_cap)
    return faces
