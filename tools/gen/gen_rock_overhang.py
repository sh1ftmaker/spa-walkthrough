"""Rock overhang and canopy (rock_overhang): a heavy rough basalt shelf overhead with a dripping front edge.
Pieces are laid side by side and overlap into one rock roof (g_east_path, b3_lobby, b3_shore; ~15 pieces).

Targets (no scale sheet shows the overhang; measured on the lookbook, guide 9 rule 2):
  * lookbook 21 (private suite): the cliff roof over the bath terrace. Against the 2.0-2.1 m shoji doors
    the shelf underside is ~2.6-3.0 m above the deck, the visible rock lip ~0.8-1.2 m thick, the shelf
    reaching ~3 m out from the cliff face. Underside rough, near-black, glossy wet rims, facets and
    hanging knobs; the front edge is the thickest part (no knife edge).
  * lookbook 35 (B3 plan): the walkway roofs read as continuous dark rock canopies over the paths, so
    pieces must butt and overlap without a visible seam: each piece runs flush to its x ends.
  * proxy 6 x 3 x 3 m: default w 6, d 3, total h 3.0 = clear height + thickness.

Construction (kzgeo_rock_cluster helpers):
  * shelf = n = round(w / 2) overlapping slab hulls along x (boxy super-ellipsoid points, exponent 3.5,
    so the slab keeps full thickness to its edges), flat-clamped to the ceiling plane z = h; the front half
    droops 0-25 % of the thickness (heavy lip). LOD0 subdivides once, fractal noise, chip planes biased
    downwards (faceted underside).
  * drip edge: 2.4 drips per metre along the front underside, 0.12-0.45 m long tapered knobs whose tops are
    sunk 0.25 m into the lip (no floating), wetter material.
  * support by style: 'cliff' = a battered back wall from the ground to the shelf (cantilever, as in
    lookbook 21); 'pillar' = one rock pier under one end; 'hanging' = shelf only (snap to the cave
    ceiling, zmin at the drip tips).
  * materials: basalt_wet cooled near-black (TINT) on top / sides, cave_rock (wet) on the underside
    (faces n.z < -0.35), drips basalt_wet wetness 1.0 polished.

Parameters (build kwargs):
  w 3-10 m (default 6); d 2-5 m (default 3); thickness 0.6-1.5 m (default seeded 0.8-1.1);
  clear  clear height under the shelf (default 3.0 - thickness, so the piece is 3.0 m tall);
  drip   True / False (default True); style 'cliff' | 'hanging' | 'pillar' (default seed-cycled cliff,
  hanging, pillar, cliff: 4 seeds).
Seeds change: style, piece count jitter, thickness, front droop, underside facets, drip layout and lengths,
pier side. One rng per part; all draws before the LOD branches.

LOD: LOD0 shelf + wall hulls 2 cuts (pier 1) + noise + chips, all drips (9-point cones); LOD1 same hulls 1 cut,
all drips (5-point); LOD2 hulls from 18 points, every second drip as a 4-point cone; LOD3 one boxy hull
per shelf piece / support (8 points each), 2 drips. Budget 3000/1200/360/80.
Animation none. Lighting lightmap. Custom props: kz_clear_h, kz_style.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R

ASSET = 'rock_overhang'
FEATURES = ['heavy rough basalt shelf overhead', 'dripping front edge', 'overlapping pieces into one roof',
            'faceted wet underside']
STYLES = ['cliff', 'hanging', 'pillar', 'cliff']


def _boxy(g, n, rx, ry, rz, p=3.5):
    """n points on a super-ellipsoid (|x|^p + |y|^p + |z|^p = 1) scaled by rx, ry, rz: a slab with full
    thickness out to its edges."""
    out = []
    while len(out) < n:
        v = Vector((g.gauss(0, 1), g.gauss(0, 1), g.gauss(0, 1)))
        s = (abs(v.x) ** p + abs(v.y) ** p + abs(v.z) ** p) ** (1.0 / p)
        if s < 1e-6:
            continue
        v /= s
        k = g.uniform(0.94, 1.0)
        out.append(Vector((v.x * rx * k, v.y * ry * k, v.z * rz * k)))
    return out


def _corners(rx, ry, rz, k=0.92):
    return [Vector((sx * rx * k, sy * ry * k, sz * rz * k)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def build(lod, seed, w=6.0, d=3.0, thickness=None, clear=None, drip=True, style=None):
    style = style or C.cycle(seed, STYLES)
    gl = C.rng(seed, 'layout')
    T = gl.uniform(0.8, 1.1) if thickness is None else max(0.6, min(1.5, float(thickness)))
    droop = gl.uniform(0.0, 0.25)
    pier_side = -1 if gl.random() < 0.5 else 1
    W, D = max(3.0, min(10.0, float(w))), max(2.0, min(5.0, float(d)))
    clr = (3.0 - T) if clear is None else float(clear)
    H = clr + T
    mb = genlib.MeshBuilder()
    m_side = mb.slot('basalt_wet', wetness=0.7, tint=R.TINT)
    m_top = mb.slot('basalt_wet', wetness=0.9, tint=R.TINT, roughness_offset=-0.04)
    m_under = mb.slot('cave_rock', wetness=0.85)
    m_drip = mb.slot('basalt_wet', wetness=1.0, tint=R.TINT, roughness_offset=-0.08)
    under = dict(mi_under=m_under, under_thresh=-0.35)
    n = max(2, int(round(W / 2.0)))
    pitch = W / n
    zc = H - T / 2
    # ---------------------------------------------------------------- shelf pieces
    pieces = []
    for i in range(n):
        g = C.rng(seed, f'shelf{i}')
        cx = -W / 2 + pitch * (i + 0.5) + g.uniform(-0.08, 0.08) * pitch
        rx = pitch / 2 * g.uniform(1.25, 1.4)          # overlap 25-40 % with the neighbours
        ry = D / 2 * g.uniform(0.95, 1.0)
        rz = T / 2 * g.uniform(0.95, 1.1)
        shell = _boxy(g, 48, rx, ry, rz)
        chips = R.draw_chips(g, 6, up_bias=-0.9, depth=(0.04, 0.12))
        off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
        pieces.append((cx, rx, ry, rz, shell, chips, off))
    # end pieces flush with the module ends so neighbouring pieces overlap without a gap
    for i, (cx, rx, ry, rz, shell, chips, off) in enumerate(pieces):
        if lod >= 3:
            local = _corners(rx, ry, rz)
        else:
            local = shell[:C.lod_pick(lod, 48, 48, 18, 0)] + _corners(rx, ry, rz, 0.9)
        pts = []
        for p in local:
            q = Vector((cx + p.x, p.y, zc + p.z))
            q.x = max(-W / 2, min(W / 2, q.x))
            if p.y > 0.3 * ry and p.z < 0:              # heavy front lip: the underside droops to the front
                q.z -= droop * T * (p.y / ry - 0.3) / 0.7
            pts.append(q)
        R.basalt_hull(mb, pts, m_side, m_top, ceiling=H, cuts=C.lod_pick(lod, 2, 1, 0, 0),
                      amp=C.lod_pick(lod, 0.06, 0.04, 0.0, 0.0) * T, freq=2.2, off=off,
                      chips=chips[:C.lod_pick(lod, 6, 6, 3, 0)], top_thresh=0.6, **under)
    # ---------------------------------------------------------------- drips along the front underside
    if drip:
        gd = C.rng(seed, 'drips')
        nd = max(4, int(round(W * 2.4)))
        drips = []
        for k in range(nd):
            x = -W / 2 + W * (k + gd.uniform(0.15, 0.85)) / nd
            y = D / 2 * gd.uniform(0.62, 0.86)
            L = gd.uniform(0.12, 0.45) * (T / 0.95)
            r = gd.uniform(0.05, 0.1) * (0.6 + L)
            drips.append((x, y, L, r, gd.uniform(0, 6.28), gd.uniform(-0.04, 0.04)))
        keep = list(range(nd)) if lod < 2 else (list(range(0, nd, 2)) if lod == 2 else list(range(nd // 4, nd, max(1, nd // 2)))[:2])
        for k in keep:
            x, y, L, r, a0, lean = drips[k]
            yy = y / (D / 2)
            z_under = zc - T / 2 - droop * T * max(0.0, (yy - 0.3) / 0.7)
            z_top = z_under + 0.25 * T                  # sunk into the lip
            z_tip = z_under - L
            nb = C.lod_pick(lod, 5, 4, 3, 3)
            pts = [Vector((x + math.cos(a0 + 2 * math.pi * j / nb) * r, y + math.sin(a0 + 2 * math.pi * j / nb) * r, z_top))
                   for j in range(nb)]
            if lod == 0:
                pts += [Vector((x + lean * L * 0.5 + math.cos(a0 + 1 + 2 * math.pi * j / 3) * r * 0.55,
                                y + math.sin(a0 + 1 + 2 * math.pi * j / 3) * r * 0.55, z_under - 0.45 * L)) for j in range(3)]
            pts.append(Vector((x + lean * L, y, z_tip)))
            R.basalt_hull(mb, pts, m_drip, m_drip, top_thresh=2.0)
    # ---------------------------------------------------------------- support
    if style == 'cliff':
        nw = n
        for i in range(nw):
            g = C.rng(seed, f'wall{i}')
            cx = -W / 2 + pitch * (i + 0.5) + g.uniform(-0.06, 0.06) * pitch
            rx = pitch / 2 * g.uniform(1.2, 1.35)
            wd = g.uniform(0.9, 1.3)
            ry, rz = wd / 2, H / 2
            shell = _boxy(g, 44, rx, ry, rz, p=3.0)
            chips = R.draw_chips(g, 5, up_bias=0.0, depth=(0.04, 0.10))
            off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
            batter = g.uniform(0.08, 0.16)               # the face leans back towards the top
            local = _corners(rx, ry, rz) if lod >= 3 else shell[:C.lod_pick(lod, 44, 44, 16, 0)] + _corners(rx, ry, rz, 0.9)
            pts = []
            for p in local:
                zf = (p.z + rz) / (2 * rz)
                q = Vector((cx + p.x, -D / 2 + ry + p.y - batter * zf * ry, rz + p.z))
                q.x = max(-W / 2, min(W / 2, q.x))
                pts.append(q)
            R.basalt_hull(mb, pts, m_side, m_top, ground=0.0, ceiling=H, cuts=C.lod_pick(lod, 2, 1, 0, 0),
                          amp=C.lod_pick(lod, 0.06, 0.04, 0.0, 0.0) * wd, freq=1.8, off=off,
                          chips=chips[:C.lod_pick(lod, 5, 5, 2, 0)], top_thresh=0.6, **under)
    elif style == 'pillar':
        g = C.rng(seed, 'pier')
        rb = g.uniform(0.55, 0.75)
        px = pier_side * (W / 2 - rb * 1.2)
        py = g.uniform(-0.15, 0.1) * D
        pts = R.column_points(g, 7, 4, rb, rb * 0.78, -0.1, H - T * 0.3, wobble=0.12)
        chips = R.draw_chips(g, 4, up_bias=0.0, depth=(0.04, 0.1))
        off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
        if lod == 2:
            pts = pts[0:7] + pts[21:]
        elif lod >= 3:
            pts = pts[0:7:2] + pts[21:28:2]
        pts = [Vector((px + p.x, py + p.y, p.z)) for p in pts]
        R.basalt_hull(mb, pts, m_side, m_top, ground=0.0, ceiling=H, cuts=C.lod_pick(lod, 1, 0, 0, 0),
                      amp=C.lod_pick(lod, 0.05, 0.03, 0.0, 0.0), freq=2.0, off=off,
                      chips=chips[:C.lod_pick(lod, 4, 4, 2, 0)], top_thresh=0.6)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    C.set_json_props(o, kz_clear_h=round(clr, 3), kz_style=style, kz_thickness=round(T, 3))
    return genlib.finish(o)
