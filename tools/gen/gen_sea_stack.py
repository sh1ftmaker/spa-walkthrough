"""Basalt sea stack (sea_stack): a tall jagged column of dark wet basalt rising from the surf. Far-tier
landmark (b3_wave grotto mouth, g_east, g_east_path, g_north_ledge), 3 near instances + far copies.

Targets (refs/gen/sheet-mod-nature.png, panel "Basalt sea stack - 9 m": the 9 m arrow is 246 px -> 27 px/m;
lookbook 20 (stacks framed in the grotto mouth), 01 and 32 (stacks off the cliffs):
  * h 9 m to the main spire tip; a second, lower spire / shoulder left of the main one at ~7.5 m (0.8 h);
    a stepped lower block on the right at ~4.5 m (0.5 h).
  * the solid body is ~5.2 m wide at mid height (140 px) and ~3.6 m deep (side view); the rubble apron at the
    waterline spreads to ~9 m wide on the sheet. The proxy is 5 x 5 x 9: I keep the default inside it
    (body 4.1 m, apron to ~5 m) and propose a wider proxy in the report.
  * side view: one slender spire leaning ~4-6 deg, the top narrowing to ~0.8 m.
  * surface: vertical columnar jointing (organ-pipe facets), jagged broken tops at different heights,
    near-black wet basalt with glossy rims, blocks and rubble at the foot.

Construction (kzgeo_rock_cluster helpers): a heavy faceted plinth (two broad hulls, 30-42 % of h) carries
11 interpenetrating basalt columns placed on a
jittered sunflower pattern in the footprint ellipse. Each column is the convex hull of 6-gon rings
(per-angle factors shared up the rings, so vertical fracture faces run the full height) with a jagged
3-point crown. Column heights come from a height field of the spires (each spire a gaussian peak), so
the columns near a spire are tall and the outer ones step down: the silhouette is a jagged cluster that
tapers to the spire tips. LOD0 subdivides each column once and adds fractal noise (knobs, dents) and
chip planes (erosion). A rubble apron of 10 faceted blocks sits around the foot.
Lean: the whole stack shares one seeded lean (place(tilt)).

Parameters (build kwargs):
  h        4-30 m (default 9).            base_w  body width (default 4.1 x (h / 9) ** 0.7).
  spires   1-3 (default seed-cycled 2, 1, 3, 2, 1).
  erosion  0-1 (default seeded 0.35-0.75): noise amplitude, chip depth and count, column wobble.
  depth    depth / width of the body (default seeded 0.62-0.8).
Seeds change: spire count and positions, column layout, heights, lean direction and amount (2-6 deg),
erosion, depth ratio, rubble layout. One rng stream per concern; all draws happen before LOD branches.

LOD: LOD0 all 11 columns 5 rings, 2 cuts + noise + lateral chips, 10 rubble blocks; LOD1 same columns no cut
(noise on the hull verts), same rubble; LOD2 the same columns with 2 rings (base + top) + crown, 5 largest
rubble blocks; LOD3 one hull per spire group (that group's column base and crown points) on the two
6-point plinth hulls: 1-3 jagged spires on a heavy foot. Body columns have blunt broken tops (taper 0.8-0.9),
only the spire columns narrow to a point. Budget 4000/1600/480/100.
Materials: basalt_wet cooled near-black (TINT): splash band (z < 1.6 m, wetness 1.0), body (0.55),
ledge tops (0.85). basalt_dry is not used: every concept view shows the stack wet and glossy, and the
library dry basalt renders pale tan (guide 7). Animation none. Lighting lightmap near / vertex far.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R

ASSET = 'sea_stack'
FEATURES = ['tall jagged basalt column', 'columnar jointing facets', '1-3 spires', 'rubble at the waterline']
N_COL = 11
SPIRE_CYCLE = [2, 1, 3, 2, 1]
SPIRE_SLOTS = [(0.12, 0.02, 1.0), (-0.26, 0.08, 0.80), (0.30, -0.10, 0.55)]   # x/w, y/d, height fraction


def build(lod, seed, h=9.0, base_w=None, spires=None, erosion=None, depth=None):
    H = max(4.0, min(30.0, float(h)))
    W = base_w if base_w is not None else 4.1 * (H / 9.0) ** 0.7
    gl = C.rng(seed, 'layout')
    ns = spires if spires is not None else C.cycle(seed, SPIRE_CYCLE)
    ns = max(1, min(3, int(ns)))
    er = gl.uniform(0.35, 0.75) if erosion is None else max(0.0, min(1.0, float(erosion)))
    dr = gl.uniform(0.62, 0.8) if depth is None else float(depth)
    D = W * dr
    lean_a = gl.uniform(0, 2 * math.pi)
    lean = math.tan(math.radians(gl.uniform(2.0, 6.0)))
    tilt = (lean * math.cos(lean_a), lean * math.sin(lean_a) * 0.5)
    flip = -1 if gl.random() < 0.5 else 1                     # mirror the spire layout left/right
    # spires: the main one is always there; the others from the slot list, jittered
    sp = []
    for k, (sx, sy, sh) in enumerate(SPIRE_SLOTS):
        jx, jy, jh = gl.uniform(-0.06, 0.06), gl.uniform(-0.06, 0.06), gl.uniform(0.94, 1.04)
        if k < ns:
            sp.append((flip * (sx + jx) * W, (sy + jy) * D, (sh * jh if k else 1.0) * H))
    # columns: jittered sunflower in the footprint ellipse (drawn whatever the spire count)
    cols = []
    for i in range(N_COL):
        rr = math.sqrt((i + 0.5) / N_COL) * 0.78
        a = i * 2.39996 + gl.uniform(-0.25, 0.25)
        x = math.cos(a) * rr * W / 2 + gl.uniform(-0.05, 0.05) * W
        y = math.sin(a) * rr * D / 2 + gl.uniform(-0.05, 0.05) * D
        rc = W * gl.uniform(0.17, 0.23)
        hj = gl.uniform(0.86, 1.06)
        cols.append([x, y, rc, hj])
    sig = 0.40 * W
    for c in cols:
        best, grp = 0.0, 0
        for k, (sx, sy, sh) in enumerate(sp):
            v = sh * math.exp(-((c[0] - sx) ** 2 + ((c[1] - sy) / 0.8) ** 2) / (sig * sig))
            if v > best:
                best, grp = v, k
        c[3] = max(0.30 * H, best * c[3])
        c.append(grp)
    # the column nearest each spire carries the spire tip exactly
    for k, (sx, sy, sh) in enumerate(sp):
        j = min(range(N_COL), key=lambda i: (cols[i][0] - sx) ** 2 + (cols[i][1] - sy) ** 2)
        cols[j][0], cols[j][1] = sx, sy
        cols[j][3] = sh
        cols[j][4] = k
        cols[j][2] *= 0.9
    mb = genlib.MeshBuilder()
    m_splash = mb.slot('basalt_wet', wetness=1.0, tint=R.TINT, roughness_offset=-0.06)
    m_body = mb.slot('basalt_wet', wetness=0.55, tint=R.TINT)
    m_top = mb.slot('basalt_wet', wetness=0.85, tint=R.TINT, roughness_offset=-0.04)
    splash_z = 1.6 * min(1.0, H / 9.0) + 0.4 * (H > 9.0)
    lod3_groups = {}
    for i, (x, y, rc, hc, grp) in enumerate(cols):
        g = C.rng(seed, f'col{i}')
        tall = hc / H
        is_tip = any(abs(x - sx) < 1e-6 and abs(y - sy) < 1e-6 for sx, sy, _ in sp)
        # blunt broken tops on the body columns, only the spire columns narrow to a point (the first build
        # tapered every column and read as a bundle of quartz crystals)
        taper = (0.62 - 0.30 * tall) if is_tip else (0.92 - 0.12 * tall)
        pts = R.column_points(g, 6, 5, rc, rc * taper, -0.2, hc, wobble=0.06 + 0.10 * er)
        chips = R.draw_chips(g, 5, up_bias=0.0, depth=(0.03 + 0.04 * er, 0.08 + 0.12 * er))
        chips = [(Vector((d.x, d.y, d.z * 0.25)).normalized(), f) for d, f in chips]   # lateral: keep the tips
        off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
        if lod >= 3:
            ring0 = pts[0:6]
            lod3_groups.setdefault(grp, []).extend(R.place([ring0[0], ring0[2], ring0[4], pts[-3]], (x, y, 0.0), 0.0, tilt))
            continue
        if lod == 2:
            pts = pts[0:6] + pts[24:30] + pts[30:]                 # base ring + top ring + crown
        pw = R.place(pts, (x, y, 0.0), 0.0, tilt)
        R.basalt_hull(mb, pw, m_body, m_top, ground=0.0,
                      cuts=C.lod_pick(lod, 2, 0, 0, 0),
                      amp=C.lod_pick(lod, 1.0, 0.6, 0.0, 0.0) * (0.03 + 0.06 * er) * rc, freq=1.6 / rc, off=off,
                      chips=chips[:C.lod_pick(lod, 5, 5, 2, 0)], top_thresh=0.55)
    # plinth: two broad faceted masses that carry the columns (the concept body is widest over its lower
    # 40 %, a stepped heavy foot, not a bundle of free-standing pencils)
    for k in range(2):
        g = C.rng(seed, f'plinth{k}')
        px = (-0.18 if k == 0 else 0.2) * W * flip
        rx, ry, rz = W * g.uniform(0.36, 0.42), D * g.uniform(0.40, 0.46), H * g.uniform(0.30, 0.42) * (1.0 if k == 0 else 0.8)
        shell = R.draw_points(g, 40, rx, ry, rz, rmin=0.85)
        env = [Vector((math.cos(a) * rx, math.sin(a) * ry * 0.95, 0.0)) for a in (0.3, 1.9, 3.4, 4.9)]
        env += [Vector((math.cos(a) * rx * 0.55, math.sin(a) * ry * 0.55, rz * 0.95)) for a in (1.0, 3.6)]
        chips = R.draw_chips(g, 4, up_bias=0.8, depth=(0.05, 0.12 + 0.08 * er))
        off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
        local = shell[:C.lod_pick(lod, 40, 40, 14, 0)] + env
        pw = R.place(local, (px, 0.0, 0.0), g.uniform(-0.3, 0.3), tilt)
        R.basalt_hull(mb, pw, m_body, m_top, ground=0.0, cuts=C.lod_pick(lod, 1, 1, 0, 0),
                      amp=C.lod_pick(lod, 1.0, 0.6, 0.0, 0.0) * (0.04 + 0.05 * er) * rx, freq=1.2 / rx, off=off,
                      chips=chips[:C.lod_pick(lod, 4, 4, 2, 0)], top_thresh=0.55)
    if lod >= 3:
        for grp, local in sorted(lod3_groups.items()):
            # LOD3: per spire group, the hull of its columns' base corners and crown tips
            R.basalt_hull(mb, local, m_body, m_top, ground=0.0, top_thresh=0.55)
    # rubble apron: faceted blocks round the foot, sunk ~35 %
    gr = C.rng(seed, 'rubble')
    blocks = []
    for k in range(10):
        a = 2 * math.pi * (k + gr.uniform(-0.35, 0.35)) / 10
        rad = gr.uniform(0.88, 1.02)
        sz = W * gr.uniform(0.06, 0.14)
        blocks.append((sz, (math.cos(a) * W / 2 * rad, math.sin(a) * D / 2 * rad, sz * 0.25),
                       (sz * gr.uniform(1.0, 1.5), sz * gr.uniform(0.8, 1.1), sz * gr.uniform(0.7, 1.0)), gr.uniform(0, 6.3),
                       C.rng(seed, f'rubble{k}')))
    blocks.sort(key=lambda b: -b[0])
    keep = C.lod_pick(lod, 10, 10, 5, 0)
    for sz, c, size, rot, g in blocks[:keep]:
        C.hull_rock(mb, c, size, m_body, g, npts=C.lod_pick(lod, 14, 10, 6, 6), ground=0.0, rot=rot, rmin=0.8)
    # slots by height: splash band below splash_z, ledge tops wetter, rest body
    for f in mb.bm.faces:
        cz = f.calc_center_median().z
        if f.material_index == m_body and cz < splash_z:
            f.material_index = m_splash
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    C.set_json_props(o, kz_spires=ns, kz_far_lighting='vertex')
    return genlib.finish(o)
