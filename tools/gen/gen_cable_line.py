"""Cable line and pylons (cable_line): twin thin cables hanging in catenaries between the two cable-lift stations,
carried over tapered bronze lattice pylons with sheave trains, on stepped stone plinths.

Concept: refs/gen/sheet-vs-lift-cable.png panel 5 "Cable line & pylons, 120 m run" (full run front + pylon detail
front / side); lookbook 30 / 31 (summit and ground plans: the line leaves the top station at E4 and runs down
over the cliff). Measured on panel 5 (2x crop .scratch/op16/m_line.png; the "1 m" bars there are not usable for
a 120 m run, so ratios only):
  * full run: 3 pylons evenly spaced between stations on rock pedestals; pylon (tower + head) ~0.82 of the total,
    stone plinth ~0.18; the cables sag visibly (~2-3 % of the span)
  * pylon detail: tower base full width ~0.30 x tower height across the cable direction... along the cable,
    ~0.20 x height in the other direction, top ~0.08 x height; 4 bronze legs, X bracing in 5-7 storeys with a
    girt at each storey; a cap beam, a crossarm and per cable a rocker with a train of 3-4 support sheaves
    (front view shows 4 + 4 wheels, side view two stacks: twin cables side by side)
  * stepped plinth: grey stone block on a wider footing slab
Row: pylon h 8-25 m, 2-4 pylons, 120 m run, tri budget per pylon 1500/600/180/40, cable as lines.

Orientation: the cable runs along Y (as cable_cabin and cable_station: the cabin travels along its own Y, the
station's bay opens to +Y). Twin cables at x = +-GAUGE/2 (0.40 m, the cabin's grip gauge).

Two build parts:
  part='pylon' (default; the LOD sheet and the budget check): one pylon with 2.5 m cable stubs over its sheaves.
    Seeds change: height (12 / 14.5 / 10 m), bracing style (X / K / zig-zag), storey count, base spread, sheave
    count (4 / 3 / 3 per train), plinth tiers.
  part='line': the whole run. Params: a, b = cable attach points (x, y, z) at the two stations (default
    (0, -60, 14) and (0, 60, 14): stations on rock pedestals, as on the sheet); pylons = count (2-4, default 3)
    or a list of y positions; ground = z of the ground under the pylons (float or list per pylon, default 0);
    sag = mid-span sag as a fraction of the span (default 0.025); hump = cable rise over each pylon above the
    chord (default 0.6 m). Pylon heights follow (cable height - ground), clamped to 8-25 m.
    obj['kz_cables'] = [[x, y, z] ...] x 2 polylines (runtime line rendering + cabin travel path);
    obj['kz_pylons'] = [[x, y, ground_z, height] ...].
  Cables are 4-sided tubes (r 28 mm, a ~56 mm track rope) at LOD0, 3-sided at LOD1-3 with fewer points (the runtime may draw kz_cables
  as lines instead and hide the cable faces: slot `cable` is listed in obj['kz_line_slots']).

Materials (slots by part): legs / lattice / head bronze (smooth, wear 0.45: warm polished bronze, as the sheet); sheaves bronze smooth
(polished rims) ; bolts + plates iron; cables iron (roughness -0.1); plinth basalt_dry tinted (0.55, 0.55, 0.6)
(dry grey stone block, the sheet's veined granite plinth).
LOD: 0 all faces braced, 3-4 sheaves per train; 1 bracing on the two wide faces + girts on the narrow ones,
2 sheaves; 2 one X per wide face, rockers without sheaves; 3 tapered prism + plinth + head bar.
Lighting: vertex.  Animation: none (the cables are static; the cabin animates along kz_cables).
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_cable_station as K

ASSET = 'cable_line'
FEATURES = ['twin thin cables in a catenary', 'lattice bronze pylons', 'sheave trains', 'stone plinths']
PROXY_SHEET = dict(w=4.0, d=5.3, h=15.0)       # proposed for the default part='pylon' module (assets.json has none)
GAUGE = 0.40
CABLE_R = 0.028
STYLES = ['x', 'k', 'n']

SEEDS = {1: dict(h=12.0, style='x', storeys=6, spread=1.0, sheaves=4, tiers=2),
         2: dict(h=14.5, style='k', storeys=7, spread=0.85, sheaves=3, tiers=2),
         3: dict(h=10.0, style='n', storeys=5, spread=1.12, sheaves=3, tiers=1)}


def pylon_params(seed, h=None, style=None):
    P = dict(SEEDS[(seed - 1) % 3 + 1])
    if seed > 3:
        g = C.rng(seed, 'pylon')
        P['h'] *= g.uniform(0.9, 1.1); P['spread'] *= g.uniform(0.92, 1.08)
    if h is not None:
        P['h'] = float(h)
    if style:
        P['style'] = style
    P['h'] = min(25.0, max(8.0, P['h']))
    P['storeys'] = max(4, min(10, round(P['storeys'] * (P['h'] / SEEDS[(seed - 1) % 3 + 1]['h']) ** 0.5)))
    return P


def pylon(mb, M, base, P, lod):
    """one pylon standing on `base` (x, y, ground z). Returns the cable support points [(x, y, z)] x 2."""
    bx, by, bz = base
    Ht = P['h']
    ph = min(2.0, max(0.8, 0.1 * Ht))                        # plinth height
    tower = Ht - ph
    hw0 = 0.15 * tower * P['spread']                          # tower base half-width along the cable (Y)
    hx0 = 0.10 * tower * P['spread']                          # across (X)
    hw1, hx1 = max(0.42, 0.04 * tower), max(0.38, 0.035 * tower)
    z0, z1 = bz + ph, bz + Ht - 0.55                          # leg feet / leg tops (head on top)
    # ---- plinth
    fw, fx = hw0 + 0.5, hx0 + 0.5
    if lod <= 1:
        if P['tiers'] == 2:
            K.box(mb, (bx, by, bz + 0.15), (2 * fx + 0.5, 2 * fw + 0.5, 0.3), M['stone'], bevel=C.lod_pick(lod, 0.04, 0.0, 0.0))
            K.box(mb, (bx, by, bz + 0.3 + (ph - 0.3) / 2), (2 * fx, 2 * fw, ph - 0.3), M['stone'], bevel=C.lod_pick(lod, 0.05, 0.0, 0.0))
        else:
            K.box(mb, (bx, by, bz + ph / 2), (2 * fx + 0.2, 2 * fw + 0.2, ph), M['stone'], bevel=C.lod_pick(lod, 0.05, 0.0, 0.0))
        if lod == 0:                                          # cap stone + leg shoes
            K.box(mb, (bx, by, bz + ph + 0.04), (2 * fx - 0.25, 2 * fw - 0.25, 0.08), M['stone'], bevel=0.02)
    else:
        fs = mb.box((bx, by, bz + ph / 2), (2 * fx, 2 * fw, ph), M['stone'])
        if lod == 3:
            for f in fs:
                f.normal_update()
            bmesh.ops.delete(mb.bm, geom=[f for f in fs if f.normal.z < -0.9], context='FACES_ONLY')
    if lod == 3:                                              # tapered 4-sided prism + head bar
        bm = mb.bm
        lo = [bm.verts.new((bx + sx * hx0, by + sy * hw0, z0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        hi = [bm.verts.new((bx + sx * hx1, by + sy * hw1, z1)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        mb._tag(C.bridge_rings(bm, lo, hi), M['leg'])
        top = bz + Ht
        mb.box((bx, by, top - 0.25), (GAUGE + 0.5, 2 * hw1 + 1.2, 0.5), M['leg'])
        return [(bx + s * GAUGE / 2, by, top) for s in (-1, 1)]
    # ---- legs
    lw = max(0.12, 0.016 * Ht)
    feet = [Vector((bx + sx * hx0, by + sy * hw0, z0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    tops = [Vector((bx + sx * hx1, by + sy * hw1, z1)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for a, b in zip(feet, tops):
        K.beam(mb, a, b, lw, lw, M['leg'])
    # ---- bracing per face: 0 (-Y face, wide... across X), 1 (+X), 2 (+Y), 3 (-X)
    n = P['storeys'] if lod == 0 else (max(3, P['storeys'] // 2) if lod == 1 else 1)
    bw = lw * 0.55
    for f in range(4):
        a0, b0 = feet[f], feet[(f + 1) % 4]
        a1, b1 = tops[f], tops[(f + 1) % 4]
        along_cable = abs((b0 - a0).y) > abs((b0 - a0).x)     # faces whose plane contains the cable direction
        if lod <= 1:
            # geometric storeys (taller at the bottom), as on the sheet
            K.lattice_face(mb, a0, a1, b0, b1, bw, bw, M['leg'], n, style=P['style'])
        elif lod == 1:
            for i in range(1, n + 1):
                s = i / n
                K.beam(mb, a0.lerp(a1, s), b0.lerp(b1, s), bw, bw, M['leg'], caps=False)
        elif along_cable:                                     # LOD2: one X per wide face
            K.beam(mb, a0, b1, bw, bw, M['leg'], caps=False); K.beam(mb, b0, a1, bw, bw, M['leg'], caps=False)
    # ---- head: cap beam, crossarm (X), per cable a rocker beam along Y with a sheave train
    zc = bz + Ht                                              # cable centre over the sheaves
    sr = 0.2 if Ht < 15 else 0.24
    zw = zc - CABLE_R - sr                                    # sheave centres
    zr = zw - 0.06                                            # rocker beam
    K.box(mb, (bx, by, z1 + 0.06), (2 * hx1 + 0.3, 2 * hw1 + 0.3, 0.14), M['leg'], bevel=C.lod_pick(lod, 0.015, 0.0, 0.0))
    K.beam(mb, (bx - GAUGE / 2 - 0.25, by, z1 + 0.2), (bx + GAUGE / 2 + 0.25, by, z1 + 0.2), 0.22, 0.16, M['leg'])
    ns = C.lod_pick(lod, P['sheaves'], 2, 0)
    Lr = max(1.6, 0.16 * Ht)                                  # rocker length along the cable
    for s in (-1, 1):
        x = bx + s * GAUGE / 2
        if lod <= 1:
            K.beam(mb, (x, by, z1 + 0.25), (x, by, zr - 0.04), 0.14, 0.14, M['leg'])             # hanger post
        if lod == 0:
            for sp in (-1, 1):                                # rocker side plates
                K.box(mb, (x + sp * 0.06, by, zr), (0.03, Lr, 0.18), M['leg'])
        elif lod == 1:
            K.box(mb, (x, by, zr), (0.15, Lr, 0.16), M['leg'])
        else:
            K.box(mb, (x, by, (z1 + 0.25 + zr) / 2), (0.14, Lr, zr - z1 - 0.1), M['leg'])
        for k in range(ns):
            y = by - Lr / 2 + 0.22 + (Lr - 0.44) * k / max(1, ns - 1)
            if lod == 0:
                K.wheel(mb, (x, y, zw), (1, 0, 0), sr, dict(rim=M['sheave'], spoke=M['leg'], hub=M['iron']), lod,
                        spokes=0, rim_w=0.06, rim_t=0.07, hub_r=0.05, segs=8, groove=False, hub_segs=4)
            else:
                mb.cylinder((x, y, zw), sr, 0.07, M['sheave'], segs=6, rot=(0, math.pi / 2, 0))
        if lod == 0:                                          # pivot pin through the rocker
            C.stick(mb, (x - 0.1, by, zr), (x + 0.1, by, zr), 0.05, 0.05, M['iron'], segs=6)
    return [(bx + s * GAUGE / 2, by, zc) for s in (-1, 1)]


def cable_pts(lod):
    return C.lod_pick(lod, 1.5, 3.0, 6.0, 15.0)


def build(lod, seed, part='pylon', a=None, b=None, pylons=None, ground=None, sag=None, hump=None, h=None, style=None,
          stub=2.5, **_):
    mb = genlib.MeshBuilder()
    M = dict(leg=mb.slot('bronze', variant='smooth', wear=0.45), sheave=mb.slot('bronze', variant='smooth', wear=0.6),
             iron=mb.slot('iron', wear=0.2), cable=mb.slot('iron', roughness_offset=-0.1),
             stone=mb.slot('basalt_dry', tint=(0.55, 0.55, 0.6)))
    sides = 4 if lod == 0 else 3
    cables = [[], []]
    pyl = []
    if part == 'pylon':
        P = pylon_params(seed, h, style)
        sup = pylon(mb, M, (0, 0, 0), P, lod)
        for i, (sx, sy, sz) in enumerate(sup):
            pts = [Vector((sx, -stub, sz - 0.12)), Vector((sx, -stub * 0.5, sz - 0.03)), Vector((sx, 0, sz)),
                   Vector((sx, stub * 0.5, sz - 0.03)), Vector((sx, stub, sz - 0.12))]
            if lod >= 1:
                pts = [pts[0], pts[2], pts[4]] if lod <= 2 else [pts[0], pts[4]]
            if lod <= 1:
                K.cable(mb, pts, CABLE_R, M['cable'], sides=sides)
            else:
                C.tube(mb, pts, [CABLE_R] * len(pts), M['cable'], sides=3)
            cables[i] = pts
        pyl.append([0, 0, 0, P['h']])
        C.centre_base(mb, centre_x=False, centre_y=False)
    else:
        A = Vector(a or (0, -60, 14.0)); B = Vector(b or (0, 60, 14.0))
        sagf = 0.025 if sag is None else sag
        hump = 0.6 if hump is None else hump
        if isinstance(pylons, (list, tuple)):
            ts = [(float(y) - A.y) / (B.y - A.y) for y in pylons]
        else:
            n = 3 if pylons is None else max(2, min(4, int(pylons)))
            ts = [(i + 1) / (n + 1) for i in range(n)]
        gz = ground if isinstance(ground, (list, tuple)) else [float(ground or 0.0)] * len(ts)
        sups = [[(A.x + s * GAUGE / 2, A.y, A.z) for s in (-1, 1)]]
        for k, t in enumerate(ts):
            c = A.lerp(B, t)
            zc = c.z + hump
            P = pylon_params(seed + k, None, style)
            P['h'] = min(25.0, max(8.0, zc - gz[k]))
            P['storeys'] = max(4, min(10, round(4 + P['h'] / 3.5)))
            sups.append(pylon(mb, M, (c.x, c.y, gz[k]), P, lod))
            pyl.append([round(c.x, 3), round(c.y, 3), round(gz[k], 3), round(P['h'], 3)])
        sups.append([(B.x + s * GAUGE / 2, B.y, B.z) for s in (-1, 1)])
        for i in range(2):
            pts = []
            for s0, s1 in zip(sups[:-1], sups[1:]):
                p0, p1 = Vector(s0[i]), Vector(s1[i])
                L = (p1 - p0).length
                seg = K.catenary(p0, p1, sagf * L, max(2, round(L / cable_pts(lod))))
                pts += seg if not pts else seg[1:]
            K.cable(mb, pts, CABLE_R, M['cable'], sides=sides)
            cables[i] = pts
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_cables=[[[round(c, 3) for c in p] for p in cab] for cab in cables], kz_pylons=pyl,
                     kz_line_slots=[M['cable']], kz_params=dict(part=part, gauge=GAUGE, cable_r=CABLE_R))
    return o
