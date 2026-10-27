"""Stepping stone (stepping_stone): a dark wet basalt cobble, flat-topped, lumpy outline, set just under the water.

Remade by the gen31 builder. Identifying features kept at every LOD: flat polished top just under the surface,
rough crusty edge with chips, irregular lumpy outline with bites (guests follow the stones by touch).

Construction: one closed polar-grid solid (angular segments x profile rings), no separate shoulder ring.
  * plan outline r(theta): base radius times periodic noise (harmonics 2-7 with random phases, so lobes not
    facets) times 1-2 gaussian bites (8-16 % deep) times an aspect ellipse (0.72-1.35); no straight runs.
  * side profile (monotone, convex, no ledge): bottom ring, lower side, belly (max radius, seeded height and
    batter), upper side, a rounded shoulder (two rings, seeded roundness) running straight into the top.
  * rock surface: 3D noise displacement of 4-9 mm on the sides (more low down), 2-4 shallow chips
    (gaussian dents in theta/z), finer breakup on the shoulder; top is flat with a seeded tilt, slow
    undulation (2-5 mm, less when polish is high) and a shallow dish.
  * materials: basalt_wet only. side (wetness 0.3, rougher), shoulder (wetness 0.55), top (wetness 0.95,
    roughness_offset lowered by polish). basalt_dry / stepping_stone are not used (they render pale).
  * LOD0 54 segments x 9 rings (~970 tris), LOD1 24 x 5 (~240), LOD2 10 x 3 (~60), LOD3 5 x 2 (20, closed disc).
Animation: none. Lighting: lightmap (UV1 from genlib.finish).

Parameters (build kwargs; proxy 0.75 x 0.75 x 0.2 m):
  r          mean outline radius, 0.25-0.36 m (footprint 0.5-0.75 m across the long axis, clamped to proxy)
  thickness  0.15-0.21 m
  polish     0 rough .. 1 polished top (flatness, roughness)
  rough      edge roughness 0..1 (side displacement and chips)
  ovality    aspect of the plan, 0.72-1.35 (seeded)
Seeds change plan lobes, bites, aspect, thickness, belly height, shoulder roundness, tilt and chips.
Proposed proxy: h 0.22 (thickness up to 0.21).
"""
import math
import genlib
from mathutils import Vector, noise

ASSET = 'stepping_stone'
FEATURES = ['flat polished top', 'rough chipped edge', 'lumpy outline with bites']

TINT = (0.32, 0.36, 0.46)     # cools and darkens the library basalt toward near-black blue-grey
SEGS = {0: 54, 1: 24, 2: 10, 3: 5}


def _plan(g, R, aspect, rg):
    harm = [(k, g.uniform(0.0, 2 * math.pi), a * g.uniform(0.6, 1.3))
            for k, a in ((2, 0.085), (3, 0.08), (4, 0.06), (5, 0.04), (7, 0.028), (9, 0.016), (12, 0.008))]
    bites = [(g.uniform(0, 2 * math.pi), g.uniform(0.28, 0.5), g.uniform(0.06, 0.11))
             for _ in range(g.choice([1, 2, 2]))]
    sx, sy = math.sqrt(aspect), 1 / math.sqrt(aspect)

    def rad(th):
        k = 1.0 + sum(a * math.sin(n * th + ph) for n, ph, a in harm)
        for c, w, d in bites:
            dd = math.atan2(math.sin(th - c), math.cos(th - c))
            k -= d * math.exp(-(dd / w) ** 2)
        return R * k
    return rad, sx, sy


def build(lod, seed, r=None, thickness=None, polish=None, rough=None, ovality=None):
    g = genlib.rng(seed, ASSET)
    R = r if r is not None else g.uniform(0.25, 0.36)
    t = thickness if thickness is not None else g.uniform(0.15, 0.21)
    pol = polish if polish is not None else g.uniform(0.4, 1.0)
    rg = rough if rough is not None else g.uniform(0.5, 1.0)
    aspect = ovality if ovality is not None else g.uniform(0.72, 1.35)
    rot = g.uniform(0, math.pi)
    rad, sx, sy = _plan(g, R, aspect, rg)
    off = Vector((g.uniform(0, 50), g.uniform(0, 50), g.uniform(0, 50)))
    belly_z = g.uniform(0.28, 0.5)            # height fraction of the widest point
    batter = g.uniform(-0.04, 0.07)           # bottom ring inset relative to belly
    sh_r = g.uniform(0.07, 0.15)              # shoulder roundness (fraction of R)
    tilt = (g.uniform(-1, 1) * 0.012, g.uniform(-1, 1) * 0.012)
    dish = (g.uniform(-0.1, 0.1), g.uniform(-0.1, 0.1), g.uniform(0.001, 0.004))
    chips = [(g.uniform(0, 2 * math.pi), g.uniform(0.25, 0.5), g.uniform(0.2, 0.8), g.uniform(0.006, 0.013))
             for _ in range(g.choice([2, 3, 4]))]   # theta, width, z fraction, depth (m)
    ph = g.uniform(0, 6.28)

    # plan sampled (all LODs share it); clamp so the long axis fits 0.75 m
    def plan_pt(th):
        k = rad(th)
        x, y = k * math.cos(th) * sx, k * math.sin(th) * sy
        c, s = math.cos(rot), math.sin(rot)
        return x * c - y * s, x * s + y * c
    N = SEGS[lod]
    ext = max(max(abs(plan_pt(2 * math.pi * i / 96)[k]) for i in range(96)) for k in (0, 1))
    clamp = min(1.0, 0.355 / ext)
    full = [plan_pt(2 * math.pi * i / 96) for i in range(96)]
    cx = (max(p[0] for p in full) + min(p[0] for p in full)) / 2 * clamp
    cy = (max(p[1] for p in full) + min(p[1] for p in full)) / 2 * clamp

    def top_z(x, y):
        z = t - tilt[0] * x / 0.3 - tilt[1] * y / 0.3
        z += (0.003 * (1.2 - pol)) * noise.noise(Vector((x, y, 0)) * 7 + off) + 0.0012 * (1.2 - pol) * noise.noise(Vector((x, y, 0)) * 19 + off)
        d2 = (x - dish[0]) ** 2 + (y - dish[1]) ** 2
        z -= dish[2] * math.exp(-d2 / 0.03)
        return z

    # profile rings: (radial scale, height fraction, surface roughness weight, slot)
    rings = {
        0: [(0.0, 0.0), (0.88 + batter, 0.0), (0.96 + batter * 0.5, 0.2), (1.0, belly_z), (0.985, 0.62),
            (0.97, 0.80), None, None],
        1: [(0.88 + batter, 0.0), (1.0, belly_z), (0.97, 0.78), None, None],
        2: [(0.9 + batter, 0.0), (1.0, belly_z), None],
        3: [(0.95, 0.0), None],
    }[lod]
    mb = genlib.MeshBuilder()
    m_side = mb.slot('basalt_wet', wetness=0.35, roughness_offset=0.12, tint=TINT)
    m_sh = mb.slot('basalt_wet', wetness=0.5, tint=TINT)
    m_top = mb.slot('basalt_wet', wetness=0.95, tint=TINT, roughness_offset=round(-0.05 + 0.2 * (1 - pol), 3))
    bm = mb.bm
    detail = {0: 1.0, 1: 0.4, 2: 0.0, 3: 0.0}[lod]

    def side_pt(th, sc, zf):
        x, y = plan_pt(th)
        x, y = x * clamp - cx, y * clamp - cy
        z = zf * t
        p = Vector((x, y, z)) * 5.0 + off
        n = noise.noise(p) * 0.010 + noise.noise(p * 2.3 + Vector((3, 1, 2))) * 0.006
        amp = detail * rg * n * (1.3 - 0.8 * zf)
        for c, w, zc, d in chips:
            dd = math.atan2(math.sin(th - c), math.cos(th - c))
            amp -= detail * rg * d * math.exp(-(dd / w) ** 2 - ((zf - zc) / 0.2) ** 2)
        L = math.hypot(x, y) or 1
        k = sc + amp / L
        return x * k, y * k, z

    verts = []
    prof = []
    for ri, spec in enumerate(rings):
        if spec is not None and spec[0] == 0.0:
            continue
        prof.append(spec)
    # top rings: edge (rounded shoulder end) then inner
    ring_vs = []
    for spec in prof:
        row = []
        for i in range(N):
            th = 2 * math.pi * i / N
            if spec is not None:
                x, y, z = side_pt(th, spec[0], spec[1])
            row.append(None if spec is None else (x, y, z))
        ring_vs.append(row)
    # build the top rings explicitly: shoulder (0.9, ~0.93t then rounding in), edge, inner
    top_specs = [(0.945, 0.915), (0.90, 0.972), (0.80, 1.0), (0.5, 1.0)] if lod == 0 else \
                [(0.92, 0.97), (0.6, 1.0)] if lod == 1 else [(0.9, 1.0)] if lod == 2 else [(0.92, 1.0)]
    rows = [r_ for r_ in ring_vs if r_[0] is not None]
    for sc_, zf in top_specs:
        row = []
        for i in range(N):
            th = 2 * math.pi * i / N
            x, y, z = side_pt(th, sc_, zf)
            z = z + (top_z(x, y) - t) * min(1.0, max(0.0, (zf - 0.88) / 0.12)) if lod < 3 else t
            row.append((x, y, z))
        rows.append(row)
    if lod == 0:
        pass
    V = [[bm.verts.new(p) for p in row] for row in rows]
    cb = bm.verts.new((0, 0, 0))
    ct = bm.verts.new((0, 0, top_z(0, 0)))
    nrow = len(V)
    sh0 = len(rows) - len(top_specs)           # first top-spec row index
    for k in range(N):
        k2 = (k + 1) % N
        bm.faces.new((cb, V[0][k2], V[0][k])).material_index = m_side
    for j in range(nrow - 1):
        if j < sh0:
            mi = m_side
        elif j < sh0 + 1:
            mi = m_sh
        else:
            mi = m_top
        if lod >= 2:
            mi = m_side if j < sh0 else m_top
        for k in range(N):
            k2 = (k + 1) % N
            bm.faces.new((V[j][k], V[j][k2], V[j + 1][k2], V[j + 1][k])).material_index = mi
    for k in range(N):
        k2 = (k + 1) % N
        bm.faces.new((ct, V[-1][k], V[-1][k2])).material_index = m_top
    o = mb.to_object(ASSET)
    genlib.finish(o)
    _cyl_uv(o, R)
    return o


def _cyl_uv(obj, R):
    """Replace UV0 on the sides by a continuous cylindrical metric unwrap (seam at the back, -Y), so the library
    texture has no vertical seam where box projection flips axis. Top faces keep the planar XY mapping."""
    import bmesh
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap')
    TAU = 2 * math.pi
    for f in bm.faces:
        if f.normal.z > 0.75:
            continue
        us = []
        for l in f.loops:
            a = (math.atan2(l.vert.co.y, l.vert.co.x) + math.pi / 2) % TAU      # 0 at the back
            us.append(a)
        if max(us) - min(us) > math.pi:
            us = [a + TAU if a < math.pi else a for a in us]
        for l, a in zip(f.loops, us):
            l[uv].uv = (a * R, l.vert.co.z)
    bm.to_mesh(me); bm.free()
