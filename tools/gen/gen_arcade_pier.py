"""Basalt arcade pier behind the curtain (arcade_pier; replaces the obsidian_monolith stand-in, gallery cases).

Targets (lookbook 19 right half: the shower grotto arcade; sheet-ref-deep #01 behind thunder curtain):
  rough square basalt piers from the floor to the rock roof, splitting the curtain into bays. Against the
  1.65 m bathers in lookbook 19 the bays are ~2.2 m tall to the springing and the piers ~0.5-0.6 bather
  heights wide -> 0.8-1.2 m; the row gives 1.0 x 0.8 x 3.0 m. Built: shaft 0.86-0.92 x 0.66-0.72, foot
  widening to 1.0 x 0.8 over the bottom 0.25 m (splash-worn), the head flaring in x to 1.0 m over the top
  0.5 m (haunch where the bay arches spring, 'flared' seed), corner chamfer 0.06-0.14 m, height 3.0.
  Surface: columnar basalt: noise stretched vertically so the faces break into vertical facets / flutes,
  amplitude 25-45 mm, plus horizontal course joints on the 'coursed' seed. Near-black and wet.

Parameters build(lod, seed, **p)
  w 0.8-1.2 (1.0), d 0.6-1.0 (0.8), h 3.0, chamfer (corner chamfer, m; seeded 0.06-0.14), wetness 0-1 (0.7)
  style  flared | coursed | monolith   (seeds 1, 2, 3 cycle)
Seeds change shape: style (head flare / stacked courses with joints / leaning tapered monolith), chamfer,
taper, lean, noise phase and flute frequency. Each part its own rng stream; drawn before the LOD branch.
Construction: one closed solid lofted through rings of a chamfered-rectangle section (open base: it
stands in the floor). LOD0 28 points x 21 rings, LOD1 16 x 15 (joint / foot / flare rings counted in), LOD2 10 x 7 (flare/foot kept), LOD3 6 x 3.
Materials: basalt_wet tinted near-black (shaft wetness = param, foot/splash zone wetter, head drier).
Animation none. Lighting lightmap. Front +Y.
"""
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'arcade_pier'
FEATURES = ['rough square basalt pier', 'floor to roof', 'chamfered corners / columnar facets']
STYLES = ['flared', 'coursed', 'monolith']
TINT = (0.32, 0.36, 0.46)          # same near-black cooling as the passed stepping stone


def _section(hx, hy, ch, n):
    """chamfered rectangle resampled to n points (n >= 8 keeps the 8 chamfer corners; n == 6 is a hexagon-ish
    stretched section for LOD3), counter-clockwise, with outward normals: [(x, y, nx, ny)]"""
    if n < 8:
        out = []
        for i in range(n):
            a = 2 * math.pi * (i + 0.5) / n
            out.append((hx * math.cos(a) / math.cos(math.pi / n) * 0.92, hy * math.sin(a) / math.cos(math.pi / n) * 0.92,
                        math.cos(a), math.sin(a)))
        return out
    c = min(ch, hx * 0.45, hy * 0.45)
    cor = [(hx, -hy + c), (hx, hy - c), (hx - c, hy), (-hx + c, hy), (-hx, hy - c), (-hx, -hy + c), (-hx + c, -hy), (hx - c, -hy)]
    segs = [(cor[k], cor[(k + 1) % 8]) for k in range(8)]
    lens = [math.dist(a, b) for a, b in segs]
    extra = n - 8                                   # distribute the remaining points over the 4 long faces
    face_idx = [0, 2, 4, 6]
    flen = sum(lens[k] for k in face_idx)
    alloc = {k: 0 for k in range(8)}
    for k in face_idx:
        alloc[k] = int(round(extra * lens[k] / flen))
    while sum(alloc.values()) > extra:
        alloc[max(face_idx, key=lambda k: alloc[k])] -= 1
    while sum(alloc.values()) < extra:
        alloc[max(face_idx, key=lambda k: lens[k] / (alloc[k] + 1))] += 1
    out = []
    for k, (a, b) in enumerate(segs):
        ex, ey = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ey) or 1.0
        nx, ny = ey / L, -ex / L
        m = alloc[k]
        for i in range(m + 1):
            t = i / (m + 1)
            if i == 0:                                  # corner vertex: averaged normal with the previous edge
                pa, pb = segs[k - 1]
                qx, qy = pb[0] - pa[0], pb[1] - pa[1]; ql = math.hypot(qx, qy) or 1.0
                cx, cy = nx + qy / ql, ny - qx / ql
                cl = math.hypot(cx, cy) or 1.0
                out.append((a[0], a[1], cx / cl, cy / cl))
            else:
                out.append((a[0] + ex * t, a[1] + ey * t, nx, ny))
    return out


def build(lod, seed, w=1.0, d=0.8, h=3.0, chamfer=None, wetness=0.7, style=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'shape')
    ch = chamfer if chamfer is not None else g.uniform(0.06, 0.14)
    shaft = g.uniform(0.86, 0.92)
    taper = g.uniform(0.0, 0.04) if style != 'monolith' else g.uniform(0.06, 0.1)
    lean = (g.uniform(-0.03, 0.03), g.uniform(-0.02, 0.02)) if style == 'monolith' else (0.0, 0.0)
    fl = g.uniform(1.6, 2.6)                       # flute frequency across the faces
    amp = g.uniform(0.025, 0.045)
    courses = sorted(g.uniform(0.45, 0.75) * k for k in (1, 2, 3, 4)) if style == 'coursed' else []
    cz = [c * h / 3.0 * 1.0 for c in courses]
    off = Vector((g.uniform(0, 80), g.uniform(0, 80), g.uniform(0, 80)))

    n, nz = C.lod_pick(lod, (28, 21), (16, 15), (10, 7), (6, 3))
    hx0, hy0 = w / 2, d / 2

    def width(z):
        """(sx, sy) section scale at height z: foot widening, shaft taper, flared head"""
        t = z / h
        s = shaft * (1 - taper * t)
        sx = sy = s
        if z < 0.25:                                # splash-worn foot
            f = (1 - z / 0.25) ** 1.5
            sx = sy = s + (1.0 - s) * f
        if style == 'flared' and z > h - 0.5:       # haunch: flare in x where the bay arches spring
            f = ((z - (h - 0.5)) / 0.5) ** 1.6
            sx = s + (1.0 - s) * f
        return sx, sy

    n_extra = 0
    if lod <= 1:
        n_extra = (3 if lod == 0 else 1) * sum(1 for c in cz if 0.3 < c < h - 0.3) + (2 if style == 'flared' else 0) + 2
    nz = max(4, nz - n_extra) if lod <= 1 else nz                        # hold the ring total (budget) whatever the extras
    zs = [h * k / (nz - 1) for k in range(nz)]
    if lod <= 1:
        for c in cz:                                 # course joints: a pinched pair of rings
            if 0.3 < c < h - 0.3:
                zs += [c - 0.02, c, c + 0.02] if lod == 0 else [c]
        if style == 'flared':
            zs += [h - 0.5, h - 0.25]
        zs += [0.12, 0.25]
    zs = sorted(set(round(z, 4) for z in zs))
    sec = _section(hx0, hy0, ch, n)
    bm = genlib.MeshBuilder()
    mb = bm
    body = mb.slot('basalt_wet', wetness=round(wetness, 3), tint=TINT)
    foot = mb.slot('basalt_wet', wetness=round(min(1.0, wetness + 0.25), 3), tint=TINT, roughness_offset=-0.05)
    head = mb.slot('basalt_wet', wetness=round(max(0.0, wetness - 0.3), 3), tint=TINT, roughness_offset=0.08)
    B = mb.bm
    rings = []
    for z in zs:
        sx, sy = width(z)
        joint = any(abs(z - c) < 1e-3 for c in cz)
        ring = []
        for (x, y, nx, ny) in sec:
            px, py = x * sx, y * sy
            if lod <= 2:
                # columnar facets: noise stretched in z, sampled along the perimeter
                q = Vector((px * fl, py * fl, z * 0.35)) + off
                dd = amp * noise.noise(q) + 0.4 * amp * noise.noise(q * 2.3)
                if lod == 2:
                    dd *= 0.5
                if joint:
                    dd -= 0.03
                if z < 1e-4:
                    dd = max(dd, 0.0)
                L = math.hypot(nx, ny) or 1.0
                px += nx / L * dd; py += ny / L * dd
            px = max(-w / 2, min(w / 2, px)); py = max(-d / 2, min(d / 2, py))
            ring.append(B.verts.new((px + lean[0] * z / h, py + lean[1] * z / h, z)))
        rings.append(ring)
    faces = []
    for k, (A, Bb) in enumerate(zip(rings[:-1], rings[1:])):
        fs = C.bridge_rings(B, A, Bb)
        zm = (zs[k] + zs[k + 1]) / 2
        mb._tag(fs, foot if zm < 0.3 else (head if zm > h - 0.4 else body))
        faces += fs
    top = B.faces.new(rings[-1]); mb._tag([top], head); faces.append(top)
    bmesh.ops.recalc_face_normals(B, faces=faces)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=28)
    C.set_json_props(o, kz_params=dict(style=style, w=w, d=d, h=h, chamfer=round(ch, 3), wetness=wetness))
    return o
