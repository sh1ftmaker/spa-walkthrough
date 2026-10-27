"""Hinoki header tank (header_tank): a big copper-hooped stave tank on a braced timber stand, with copper outlet
spouts, a ladder, a 火山湯 plaque and stone footings (B2 core, gravity feed for the restaurant baths).

Concept: refs/gen/sheet-mod-kawagiri.png panel 6 "Hinoki header tanks" (front + side, labelled 3.0 m wide,
3.5 m tall); lookbook 07 (restaurant plan). Measured on the panel (2x crop .scratch/op16/m_tank.png, 3.5 m
arrow = 415 px -> 118.6 px/m; the 3.0 m arrow gives 135 px/m, the height label is used):
  * ground -> stone footing top 0.6 m; footing ~0.6 m square, rubble basalt, one under each post
  * stand: 4 square posts (~0.2 m), centres +-1.18 m (spacing 2.36 m = 0.95 x tank D), head beams with ~0.25 m
    overhang, X bracing on every face, stand top (beams) at 1.73 m
  * tank: D ~2.5 m (r 1.25; label scale 2.2 m), wall 1.75 m (1.81 -> 3.54 m), ~36 staves, slight barrel
    (bottom 0.97 x top), 3 copper hoops (top hoop double), flat lid with cleats and a turned vent cap
    (cap top 3.8 m)
  * plaque on the front: pale board ~0.45 x 1.0 m with dark 火山湯 and a mountain mark
  * 2 copper spouts: out of the lower wall (z ~2.0 m), horizontal ~0.4 m then bent down 45 deg, mouth ~0.75 m
    beyond the wall; water falls into stone basins (runtime water + place model, not built here)
  * ladder (side view): ~0.55 m wide, rungs ~0.3 m, from the ground to ~0.3 m above the rim
Targets (seed 1): tank r 1.15, wall 1.75, stand 1.75, overall ~3.7 (with spouts) x 2.9 x 3.75 m.
Proxy in assets.json is 2.4 x 1.4 x 1.6 m: far smaller than the row (3 x 3 x 3.5) and the sheet. Built to the
sheet; PROXY_SHEET below is the proposed proxy (used by .scratch/op16/lod_sheet.py for the check).

Parameters build(lod, seed, **p)
  r        tank radius 0.8-1.5 (seed: 1.15 / 0.95 / 1.38)
  h        tank wall height 1.2-2.0 (seed: 1.75 / 1.95 / 1.30)
  stand_h  stand top height 1.2-2.2 (seed: 1.75 / 1.55 / 1.95)
  hoops    3-5 (seed: 3 / 4 / 3);  spouts 1-3 (seed: 2 / 1 / 3);  ladder True/False (seed: on +X / on -X / off)
  lid      'flat' | 'cone' (seed: flat / cone / flat)
Seeds change: tank proportion (squat / tall / wide), stand height and bracing (X / X / X + girt), hoop count,
spout count and positions, ladder side or none, lid form.

Materials (slot by part): staves hinoki wet_oiled; lid hinoki handled; stand hinoki dark_timber;
hoops / spouts bronze smooth tinted copper (1.25, 0.85, 0.72); straps + lugs + cap iron; plaque hinoki natural;
glyphs lacquer_black; footings basalt_wet (wetness 0.4, splashed by the spouts).
LOD: 0 everything (36 grooved staves); 1 plain lathe 20, no lugs/cleats/glyph relief -> blocks; 2 lathe 10,
one hoop band per hoop, no bracing straps, ladder rails + 3 rungs; 3 tank (6 segs) + 1 hoop + posts + spouts.
Water: obj['kz_spouts'] = [{mouth: [x, y, z], dir: [x, y, z], r}] for the runtime water strands.
Lighting: lightmap.  Animation: none.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_cable_station as K

ASSET = 'header_tank'
FEATURES = ['big stave tank', 'copper hoops', 'braced timber stand', 'outlet spouts', 'ladder']
PROXY_SHEET = dict(w=4.2, d=3.45, h=3.95)       # proposed (assets.json 2.4 x 1.4 x 1.6 is too small)
COPPER = (1.25, 0.85, 0.72)

SEEDS = {1: dict(r=1.15, h=1.75, stand_h=1.70, hoops=3, spouts=2, ladder=True, lid='flat', brace='x'),
         2: dict(r=0.95, h=1.85, stand_h=1.45, hoops=4, spouts=1, ladder=True, lid='cone', brace='x'),
         3: dict(r=1.38, h=1.30, stand_h=1.95, hoops=3, spouts=2, ladder=False, lid='flat', brace='xg')}


def params(seed, **p):
    base = SEEDS.get((seed - 1) % 3 + 1)
    g = C.rng(seed, 'tank')
    P = dict(base)
    if seed > 3:
        P['r'] *= g.uniform(0.92, 1.08); P['h'] *= g.uniform(0.9, 1.1)
    for k, v in p.items():
        if k in P and v is not None:
            P[k] = v
    P['r'] = min(1.5, max(0.8, P['r'])); P['h'] = min(2.0, max(1.2, P['h']))
    return P


def build(lod, seed, **p):
    P = params(seed, **p)
    R, H, S = P['r'], P['h'], P['stand_h']
    mb = genlib.MeshBuilder()
    M = dict(stave=mb.slot('hinoki', variant='wet_oiled'), lid=mb.slot('hinoki', variant='handled'),
             stand=mb.slot('hinoki', variant='dark_timber'),
             copper=mb.slot('bronze', variant='smooth', tint=COPPER, wear=0.0),
             iron=mb.slot('iron', wear=0.2), plaque=mb.slot('hinoki', variant='natural', wear=0.2),
             ink=mb.slot('lacquer_black'), stone=mb.slot('basalt_wet', wetness=0.4))
    rr = C.rng(seed, 'rocks')
    segs = C.lod_pick(lod, 36, 20, 10, 6)
    a = max(0.8, R * 0.95 + 0.08)                   # post centre half-spacing
    foot_h = 0.55 if lod <= 2 else S * 0.3
    pw = 0.2

    # ---- footings (one stone block per post; small rubble at LOD0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * a, sy * a
            if lod <= 2:
                if lod <= 1:
                    C.slab(mb, (x, y, foot_h / 2), 0.6, 0.6, foot_h, M['stone'], rc=C.lod_pick(lod, 0.08, 0.06), m=C.lod_pick(lod, 2, 1))
                else:
                    mb.box((x, y, foot_h / 2), (0.6, 0.6, foot_h), M['stone'])
                if lod == 0:
                    for k in range(3):
                        ang = rr.uniform(0, 2 * math.pi)
                        C.hull_rock(mb, (x + 0.33 * math.cos(ang), y + 0.33 * math.sin(ang), 0.06),
                                    (0.13, 0.11, 0.1), M['stone'], rr, npts=10, ground=0.0)
    # ---- stand: posts, head beams, joists, bracing
    zt = S                                          # top of the head beams = tank base
    bh = 0.26                                       # head beam depth
    for sx in (-1, 1):
        for sy in (-1, 1):
            z0 = foot_h if lod <= 2 else 0.0
            if lod <= 2:
                mb.box((sx * a, sy * a, (z0 + zt - bh) / 2), (pw, pw, zt - bh - z0), M['stand'])
            else:
                C.stick(mb, (sx * a, sy * a, 0), (sx * a, sy * a, zt), pw * 0.7, pw * 0.7, M['stand'], segs=3)
    ov = 0.28
    if lod <= 2:
        for sy in (-1, 1):                          # main beams along X, overhanging the posts
            K.box(mb, (0, sy * a, zt - bh / 2), (2 * a + 2 * ov, 0.22, bh), M['stand'], bevel=C.lod_pick(lod, 0.012, 0.0, 0.0))
        nj = C.lod_pick(lod, 5, 4, 0)
        for i in range(nj):                         # joists along Y on the beams
            x = -a + 2 * a * (i + 0.5) / nj if nj > 2 else (-0.5 * a if i == 0 else 0.5 * a)
            mb.box((x, 0, zt + 0.07), (0.14, 2 * a + 0.3, 0.14), M['stand'])
        for sx in (-1, 1):                          # cross beams along Y under the main beams
            mb.box((sx * a, 0, zt - bh - 0.09), (0.18, 2 * a + 0.2, 0.18), M['stand'])
    else:
        mb.box((0, 0, zt - 0.1), (2 * a + 2 * ov, 2 * a + 0.2, 0.2), M['stand'])
    zt_tank = zt + (0.14 if lod <= 2 else 0.0)
    if lod <= 1:
        zb0, zb1 = foot_h + 0.12, zt - bh - 0.2
        for (ax_, ay_, bx_, by_) in ((-a, -a, a, -a), (-a, a, a, a), (-a, -a, -a, a), (a, -a, a, a)):
            for (p, q) in (((ax_, ay_, zb0), (bx_, by_, zb1)), ((bx_, by_, zb0), (ax_, ay_, zb1))):
                K.beam(mb, p, q, 0.16, 0.06, M['stand'])
            if P['brace'] == 'xg':
                K.beam(mb, (ax_, ay_, zb0 + 0.05), (bx_, by_, zb0 + 0.05), 0.14, 0.12, M['stand'])
        if lod == 0:                                # iron joint plates where the braces meet the posts
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for dz in (zb0, zb1):
                        mb.box((sx * (a + pw / 2 + 0.004), sy * a, dz), (0.008, 0.16, 0.22), M['iron'])
                        mb.box((sx * a, sy * (a + pw / 2 + 0.004), dz), (0.16, 0.008, 0.22), M['iron'])
    elif lod == 2:
        for (ax_, ay_, bx_, by_) in ((-a, a, a, a), (-a, -a, a, -a)):
            K.beam(mb, (ax_, ay_, foot_h + 0.1), (bx_, by_, zt - bh - 0.2), 0.16, 0.06, M['stand'])
            K.beam(mb, (bx_, by_, foot_h + 0.1), (ax_, ay_, zt - bh - 0.2), 0.16, 0.06, M['stand'])

    # ---- tank: barrel wall with a chime (lid sunk 0.05 below the rim), base disc
    r0, r1 = R * 0.965, R
    lid_z = H - 0.06
    wall = [(r0, 0.0), (R * 0.995, H * 0.45), (r1, H - 0.05), (r1 + 0.012, H - 0.02), (r1 - 0.05, H), (r1 - 0.05, lid_z)]
    base = (0, 0, zt_tank)
    if lod == 0:
        C.lathe_grooved(mb, wall, segs, 0.006, M['stave'], base=base)
    elif lod <= 2:
        C.lathe(mb, wall, segs, M['stave'], base=base, closed=False)
    else:
        C.lathe(mb, [(r0, 0.0), (r1, H)], segs, M['stave'], base=base, closed=False)
    if lod <= 2:
        C.lathe(mb, [(r0, 0.0), (0, 0.0)], segs, M['stave'], base=base)                # base disc
    zl = zt_tank + (lid_z if lod <= 2 else H)
    if P['lid'] == 'flat' or lod == 3:
        C.lathe(mb, [(0, 0.0), ((r1 - 0.05) if lod <= 2 else r1, 0.0)], segs, M['lid'], base=(0, 0, zl))
        cap_z = zl
    else:
        C.lathe(mb, [((r1 - 0.05), 0.0), (0.18, 0.24), (0, 0.25)], segs, M['lid'], base=(0, 0, zl))
        cap_z = zl + 0.24
    if lod <= 1 and P['lid'] == 'flat':
        for s in (-1, 1):                            # lid battens + rim cleats
            mb.box((s * R * 0.35, 0, zl + 0.03), (0.12, 2 * (r1 - 0.06) * math.sqrt(1 - 0.35 ** 2) * 0.98, 0.06), M['lid'])
        if lod == 0:
            for k in range(8):
                ang = 2 * math.pi * k / 8 + 0.2
                C.board(mb, ((r1 - 0.1) * math.cos(ang), (r1 - 0.1) * math.sin(ang), zl + 0.04), (0.14, 0.09, 0.08),
                        M['lid'], bevel=0.01, rot=(0, 0, ang))
    if lod <= 2:                                    # turned vent cap
        cp = [(0.13, 0.0), (0.13, 0.12), (0.2, 0.14), (0.18, 0.2), (0.06, 0.24), (0, 0.25)] if lod <= 1 else \
            [(0.13, 0.0), (0.2, 0.15), (0, 0.25)]
        C.lathe(mb, cp, C.lod_pick(lod, 16, 10, 6), M['iron'], base=(0, 0, cap_z))
    # hoops: top hoop doubled
    nh = P['hoops']
    hz = [0.14] + [0.14 + (H - 0.42) * (i + 1) / (nh - 1) for i in range(nh - 1)]
    hz[-1] = H - 0.2
    bands = [(z, 0.075) for z in hz]
    bands.append((H - 0.09, 0.05))
    if lod == 3:
        bands = [(H * 0.5, 0.12)]
    for z, bw in bands:
        rz = r0 + (R * 0.995 - r0) * min(1, z / (H * 0.45)) if z < H * 0.45 else R * 0.995 + (r1 - R * 0.995) * (z - H * 0.45) / (H * 0.55 - 0.05)
        ro = rz + 0.004
        hseg = C.lod_pick(lod, 40, 20, 10, 6)
        if lod <= 1:
            C.lathe(mb, [(ro - 0.01, z - bw / 2), (ro + 0.012, z - bw / 2), (ro + 0.012, z + bw / 2), (ro - 0.01, z + bw / 2)],
                    hseg, M['copper'], base=base, closed=False)
        else:
            C.lathe(mb, [(ro + 0.012, z - bw / 2), (ro + 0.012, z + bw / 2)], hseg, M['copper'], base=base, closed=False)
        if lod == 0:                                 # tightening lugs, two per hoop
            for ang in (math.radians(62), math.radians(242)):
                mb.box(((ro + 0.03) * math.cos(ang), (ro + 0.03) * math.sin(ang), zt_tank + z),
                       (0.05, 0.12, bw + 0.04), M['iron'], rot=(0, 0, ang))

    # ---- plaque (+Y): pale board, 火山湯, mountain mark
    pz = zt_tank + H * 0.52
    ph = min(1.05, H * 0.62)
    if lod <= 2:
        K.box(mb, (0, R + 0.002, pz), (0.44, 0.04, ph), M['plaque'], bevel=C.lod_pick(lod, 0.008, 0.0, 0.0))
        yf = R + 0.022
        if lod == 0:
            C.text_solid(mb, '火山湯', 0.0, pz + ph * 0.12, yf, ph * 0.2, M['ink'], depth=0.008, vertical=True, gap=1.12)
            K.prism_xz(mb, [(-0.14, pz - ph * 0.42), (0.14, pz - ph * 0.42), (0.03, pz - ph * 0.27),
                            (0.0, pz - ph * 0.29), (-0.03, pz - ph * 0.26)], yf, yf + 0.008, M['ink'])
        elif lod == 1:
            for k in range(3):
                zc = pz + ph * 0.12 + (1 - k) * ph * 0.225
                mb.box((0, yf + 0.003, zc), (0.17 - 0.02 * k, 0.006, ph * 0.17), M['ink'])
        else:
            mb.box((0, yf + 0.003, pz + ph * 0.12), (0.16, 0.006, ph * 0.62), M['ink'])

    # ---- spouts: copper pipe out of the lower wall, bent down 45 deg, flared mouth
    fwd = math.radians(20) if R > 1.3 else 0.0          # wide tank: both spouts swing towards the front
    spout_dirs = {1: [0.0], 2: [fwd, math.pi - fwd], 3: [fwd, math.pi - fwd, math.radians(270)]}[P['spouts']]
    spouts = []
    pr = 0.075
    zs = zt_tank + 0.32
    for ang in spout_dirs:
        d = Vector((math.cos(ang), math.sin(ang), 0))
        p0 = d * (R - 0.08) + Vector((0, 0, zs))
        pts = [p0, p0 + d * 0.45]
        bend = C.lod_pick(lod, 5, 3, 2, 1)
        rb = 0.25
        for k in range(1, bend + 1):
            th = math.radians(45) * k / bend
            pts.append(pts[1] + d * rb * math.sin(th) - Vector((0, 0, rb * (1 - math.cos(th)))))
        tipdir = (d * math.cos(math.radians(45)) - Vector((0, 0, math.sin(math.radians(45))))).normalized()
        pts.append(pts[-1] + tipdir * 0.22)
        if lod <= 2:
            C.tube(mb, pts, [pr] * len(pts), M['copper'], sides=C.lod_pick(lod, 12, 8, 5), cap0=True, cap1=True)
        else:
            C.tube(mb, [pts[0], pts[-1]], [pr, pr], M['copper'], sides=4)
        if lod <= 1:                                 # wall flange + mouth lip
            C.stick(mb, p0 + d * 0.06, p0 + d * 0.13, pr * 1.6, pr * 1.6, M['copper'], segs=C.lod_pick(lod, 12, 8))
            C.stick(mb, pts[-1] - tipdir * 0.05, pts[-1] + tipdir * 0.01, pr * 1.3, pr * 1.35, M['copper'], segs=C.lod_pick(lod, 12, 8))
        if lod <= 2:                                 # hanger strap from the tank wall
            K.beam(mb, pts[2] + Vector((0, 0, pr)), d * (R + 0.01) + Vector((0, 0, zs + 0.45)), 0.03, 0.012, M['iron'])
        spouts.append(dict(mouth=[round(c, 3) for c in pts[-1]], dir=[round(c, 3) for c in tipdir], r=pr))

    # ---- ladder: two rails + rungs, leaning on the tank (+X side, behind the spout)
    if P['ladder']:
        ls = -1 if P['spouts'] == 1 else 1           # one spout (+X): ladder on the opposite side, centred
        yl = 0.62 * R if P['spouts'] != 1 else 0.0
        xt = math.sqrt(max(0.1, R * R - yl * yl)) + 0.07
        top = Vector((ls * xt, yl, zt_tank + H + 0.25))
        foot = Vector((ls * (a + 0.28 + 0.5), yl, 0.0))
        lw = 0.27
        rail_w = C.lod_pick(lod, 0.07, 0.07, 0.07, 0.09)
        if lod <= 2:
            for s in (-1, 1):
                K.beam(mb, foot + Vector((0, s * lw, 0)), top + Vector((0, s * lw, 0)), 0.05, rail_w, M['stand'], up=(ls, 0, 0))
            L = (top - foot).length
            nr = C.lod_pick(lod, int(L / 0.3), int(L / 0.3), 3)
            for k in range(1, nr + 1):
                q = foot.lerp(top, k / (nr + 1))
                mb.box((q.x, q.y, q.z), (0.04, 2 * lw, 0.04), M['stand'])
        else:
            K.beam(mb, foot, top, 2 * lw, 0.06, M['stand'], up=(ls, 0, 0))

    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=False)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    for sp in spouts:
        sp['mouth'][2] = round(sp['mouth'][2] + dz, 3)
    C.set_json_props(o, kz_spouts=spouts, kz_params={k: v for k, v in P.items()})
    return o
