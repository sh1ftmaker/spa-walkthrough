"""Vanity counter with round backlit mirrors: a stone-topped hinoki counter against the wall, one place per
mirror: a round (or tall oval) mirror on the wall with a glowing washi halo behind its rim, a stone or
ceramic wash bowl with a bronze wall spout, a cluster of amber glass bottles and ceramic jars, folded
towels on the open shelf below, and an upholstered hinoki stool in front.

Identifying features kept at every LOD: stone top on a timber base, a glowing round mirror per place, a
wash bowl per place, a stool per place (LOD3: blocks), bottles to LOD2.

Targets (refs/gen/sheet-ref-ground.png panel 01 right: the mirror counter; dh-changing-treatment.png
"vanity area (mirrors & washbasins)"; scale from the stool seat 0.45-0.5 m and the counter 0.85-0.9 m):
  * counter top 0.86 m, 0.6 m deep, dark stone 70 mm thick with a 30 mm front overhang; timber base with
    one open shelf (towels), apron board with a glow strip, recessed 80 mm toe-kick;
  * place pitch 0.75-1.0 m; mirror r 0.3-0.5 m (row) - concept mirrors are tall rounds ~0.55 x 0.95 m whose
    bottom sits ~0.25 m above the top; halo ~40 mm proud of the rim;
  * vessel bowls 0.38-0.42 m across, 0.12-0.14 m tall, dark stone (or ceramic); 2-4 bottles 0.15-0.22 m;
  * stools: 0.40 x 0.34 m seat at 0.48 m, centre 0.28 m in front of the counter.
  * overall: 4 x 1.06 x 2.0-2.15 m (stools and mirrors included). The proxy (3d/assets.json) is
    4 x 0.6 x 0.9 m: the counter alone. Proposed proxy: w 4, d 1.1, h 2.2 (see report); the sheet
    flags d / h / pivot-y against the old proxy until then.

Parameters: w (2-6), places (2-8), mirror_r (0.3-0.5), mirror ('round' | 'oval'), bowl ('stone' |
'ceramic'), bottles (per place, 0-4), stools (bool).
Seeds: 1 = 4.0 m, 4 places, round mirrors r 0.38, stone bowls, 3 bottles; 2 = 3.0 m, 3 places, tall oval
mirrors (concept), ceramic bowls, 2-4 bottles; 3 = 2.0 m, 2 places, round r 0.32, stone bowls, 4
bottles. Seeds > 3 sample the ranges. Bottle mix / jar placement / stool yaw jitter per seed.

Materials: basalt_dry cooled + honed (top, stone bowls), ceramic white / celadon (ceramic bowls, jars),
lacquer_black, normal 0 (mirror face: obsidian's speckle read as marble; no mirror material in the library -
proposed), washi_backlit (halo: amber tint 1.0/0.66/0.32 at 1.8; glow strips 1.4), lava_glass (amber bottles), lacquer_black (pumps), hinoki wet_oiled (base, stools), hinoki
dark_timber (mirror frames, backsplash), bronze smooth (spouts), terry cream (towels), linen tinted (seats).
Lights: obj['kz_lights']: a point per mirror halo (2700 K) and the apron strip. Lightmap + emissive.
Wall-snapped: the wall plane is the back of the bbox (-d/2), front +Y.
"""
import json
import math

import bpy

import genlib
import kzgeo_common as C
import kzgeo_vanity_counter as K

ASSET = 'vanity_counter'
FEATURES = ['stone-topped counter', 'round glowing mirrors', 'stone wash bowls', 'toiletry bottles', 'stools in front']
PARAMS = dict(w=(2.0, 6.0), places=(2, 8), mirror_r=(0.3, 0.5), mirror=('round', 'oval'), bowl=('stone', 'ceramic'),
              bottles=(0, 4), stools=(True, False))
LIGHT_K = 2700
TOP_Z, TOP_T, DEPTH = 0.86, 0.07, 0.6
# resolution ladder (fall back on resolution only): mirror segs, bowl segs, bottle segs, pillow m, board bevel
QUALITY = {0: [(32, 24, 12, 2, True, False), (28, 20, 10, 1, True, False), (24, 18, 8, 1, True, False), (20, 14, 8, 1, False, False)],
           1: [(20, 12, 6, 1, False, True), (16, 10, 5, 1, False, True), (12, 8, 4, 1, False, True)],
           2: [(12, 8, 4, 0, False, True)], 3: [(6, 4, 0, 0, False, True)]}


def _to_object(mb, name):
    me = bpy.data.meshes.new(name)
    mb.bm.to_mesh(me)
    mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for i, (mid, params) in enumerate(mb.slots):
        genlib.matlib.assign(o, mid, slot=i, **params)
    return o


def _layout(seed, w, places, mirror_r, mirror, bowl, bottles, stools):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'layout')
    pre = {1: (p['w'], 4, 0.38, 'round', 'stone', 3), 2: (3.0, 3, 0.36, 'oval', 'ceramic', None), 3: (2.0, 2, 0.32, 'round', 'stone', 4)}.get(seed)
    if pre is None:
        ww = g.choice([2.0, 2.5, 3.0, 3.5, 4.0])
        pre = (ww, max(2, min(8, round(ww / g.uniform(0.8, 1.0)))), g.uniform(0.3, 0.45), g.choice(['round', 'oval']),
               g.choice(['stone', 'ceramic']), None)
    L = dict(w=min(max(w or pre[0], 2.0), 6.0))
    L['places'] = max(2, min(8, places or pre[1]))
    L['R'] = min(max(mirror_r or pre[2], 0.3), 0.5)
    L['mirror'] = mirror or pre[3]
    L['bowl'] = bowl or pre[4]
    L['stools'] = stools
    L['es'] = 0.04
    pw = (L['w'] - 2 * L['es']) / L['places']
    L['pw'] = pw
    L['R'] = min(L['R'], pw * 0.42)
    gb = C.rng(seed, 'bottles')
    gs = C.rng(seed, 'stools')
    pls = []
    for i in range(L['places']):
        px = -L['w'] / 2 + L['es'] + (i + 0.5) * pw
        nb = bottles if bottles is not None else (pre[5] if pre[5] is not None else gb.randint(2, 4))
        side = 1 if i % 2 == 0 else -1
        items = []
        for k in range(nb):
            kind = 'jar' if (k == nb - 1 and nb >= 3) or gb.random() < 0.2 else 'bottle'
            items.append(dict(kind=kind, x=px + side * (min(0.31, pw * 0.36) + 0.065 * k * (0.9 if kind == 'jar' else 1.0)) + gb.uniform(-0.008, 0.008),
                              y=-0.16 + gb.uniform(-0.03, 0.04) + (0.06 if k % 2 else 0.0),
                              h=(gb.uniform(0.16, 0.21) if kind == 'bottle' else gb.uniform(0.08, 0.1)),
                              r=(gb.uniform(0.027, 0.033) if kind == 'bottle' else gb.uniform(0.034, 0.04))))
        pls.append(dict(x=px, items=items, yaw=gs.uniform(-0.06, 0.06), sdx=gs.uniform(-0.03, 0.03), sdy=gs.uniform(-0.02, 0.03),
                        towels=gs.choice([2, 2, 3])))
    L['pls'] = pls
    return L


def _bottle(mb, x, y, z, r, h, segs, glass, cap, lean=False):
    if lean:
        C.lathe(mb, [(0, 0), (r, 0), (r, h * 0.84), (r * 0.38, h), (0, h)], segs, glass, base=(x, y, z))
        C.lathe(mb, [(0, 0), (r * 0.3, 0), (r * 0.3, 0.04), (0, 0.04)], 4, cap, base=(x, y, z + h))
        return
    C.lathe(mb, [(0, 0), (r, 0), (r * 1.02, h * 0.8), (r * 0.4, h * 0.93), (r * 0.36, h), (0, h)], segs, glass, base=(x, y, z))
    C.lathe(mb, [(0, 0), (r * 0.42, 0), (r * 0.42, 0.022), (r * 0.2, 0.03), (r * 0.2, 0.045), (0, 0.045)], 6, cap, base=(x, y, z + h))
    C.board(mb, (x, y + r * 0.55, z + h + 0.04), (0.008, r * 1.1, 0.008), cap, bevel=0.0)       # pump nozzle


def _jar(mb, x, y, z, r, h, segs, body, lid):
    C.lathe(mb, [(0, 0), (r * 0.8, 0), (r, h * 0.25), (r * 1.02, h * 0.7), (r * 0.82, h * 0.92), (r * 0.82, h), (0, h)], segs, body, base=(x, y, z))
    C.lathe(mb, [(0, 0), (r * 0.88, 0), (r * 0.88, 0.014), (r * 0.5, 0.022), (0, 0.024)], segs, lid, base=(x, y, z + h))


def _bowl(mb, x, y, z, style, segs, mi, lean=False):
    if lean:
        prof = [(0, 0), (0.12, 0.0), (0.2, 0.115), (0.18, 0.13), (0.12, 0.055), (0, 0.045)] if style == 'stone' else \
               [(0, 0), (0.085, 0.0), (0.205, 0.12), (0.19, 0.12), (0.08, 0.03), (0, 0.026)]
    elif style == 'stone':    # heavy turned stone vessel, thick rounded rim
        prof = [(0, 0), (0.1, 0), (0.17, 0.04), (0.2, 0.105), (0.19, 0.13), (0.17, 0.122), (0.12, 0.055), (0, 0.045)]
    else:                     # ceramic basin on a foot ring, thin flared lip
        prof = [(0, 0.012), (0.07, 0.012), (0.075, 0.0), (0.085, 0.0), (0.09, 0.015), (0.16, 0.05), (0.2, 0.11), (0.205, 0.12),
                (0.196, 0.12), (0.15, 0.055), (0.08, 0.03), (0, 0.026)]
    C.lathe(mb, prof, segs, mi, base=(x, y, z))


def _stool(mb, x, y, yaw, wood, seat, q, lod):
    """square upholstered stool: 4 legs, aprons, side stretchers, cushion (seat top 0.48)"""
    import kzgeo_vanity_counter as KK
    sw, sd = 0.40, 0.34
    lw = 0.036
    bm = mb.bm
    n0 = len(bm.verts)
    if lod <= 1:
        for sx in (-1, 1):
            for sy in (-1, 1):
                lx, ly = sx * (sw / 2 - 0.035), sy * (sd / 2 - 0.035)
                if lod == 0:
                    C.chamfered_bar(mb, (x + lx, y + ly, 0.21), (lw, lw, 0.42), wood, ch=0.005)
                else:
                    KK.box_open(bm, x + lx - lw / 2, x + lx + lw / 2, y + ly - lw / 2, y + ly + lw / 2, 0.0, 0.42, wood, sides='fklr')
        for sy in (-1, 1):       # aprons front/back + side stretchers low
            KK.box_open(bm, x - sw / 2 + 0.03, x + sw / 2 - 0.03, y + sy * (sd / 2 - 0.035) - 0.01, y + sy * (sd / 2 - 0.035) + 0.01, 0.35, 0.42, wood, sides='fkb')
        for sx in (-1, 1):
            KK.box_open(bm, x + sx * (sw / 2 - 0.035) - 0.01, x + sx * (sw / 2 - 0.035) + 0.01, y - sd / 2 + 0.03, y + sd / 2 - 0.03, 0.35, 0.42, wood, sides='lrb')
            KK.box_open(bm, x + sx * (sw / 2 - 0.035) - 0.009, x + sx * (sw / 2 - 0.035) + 0.009, y - sd / 2 + 0.03, y + sd / 2 - 0.03, 0.10, 0.125, wood, sides='lrtb')
        C.board(mb, (x, y, 0.43), (sw, sd, 0.02), wood, bevel=0.004 if lod == 0 else 0.0)
        if lod == 0:
            C.pillow(mb, (x, y, 0.44), sw - 0.01, sd - 0.01, 0.045, seat, rc=0.035, m=q[3], puff=0.01, edge_w=0.008)
        else:
            C.slab(mb, (x, y, 0.4625), sw - 0.01, sd - 0.01, 0.045, seat, rc=0.03, m=1)
    elif lod == 2:
        for sx in (-1, 1):
            for sy in (-1, 1):
                lx, ly = sx * (sw / 2 - 0.035), sy * (sd / 2 - 0.035)
                KK.box_open(bm, x + lx - lw / 2, x + lx + lw / 2, y + ly - lw / 2, y + ly + lw / 2, 0.0, 0.43, wood, sides='fl' if sx < 0 else 'fr')
        KK.box_open(bm, x - sw / 2, x + sw / 2, y - sd / 2, y + sd / 2, 0.43, 0.49, seat, sides='ftlr')
    else:
        KK.box_open(bm, x - sw / 2 + 0.03, x + sw / 2 - 0.03, y - sd / 2, y + sd / 2, 0.0, 0.43, wood, sides='f')
        KK.box_open(bm, x - sw / 2, x + sw / 2, y - sd / 2, y + sd / 2, 0.43, 0.49, seat, sides='ft')
    KK.rot_verts(list(bm.verts)[n0:], x, y, yaw)


def build(lod, seed, w=None, places=None, mirror_r=None, mirror=None, bowl=None, bottles=None, stools=True, **_):
    L = _layout(seed, w, places, mirror_r, mirror, bowl, bottles, stools)
    budget = (genlib.budget_of(ASSET) or [5000, 2000, 600, 100])[lod]
    ladder = QUALITY[lod]
    for qi, q in enumerate(ladder):
        mb = _build(lod, L, q)
        if C.tri_count(mb.bm) <= budget * 1.05 or qi == len(ladder) - 1:
            break
        mb.bm.free()
    if qi:
        print(f'[{ASSET}] LOD{lod}: resolution stepped down to {q} for {L["places"]} places (budget {budget})')
    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=True)
    o = _to_object(mb, ASSET)
    lights = []
    for pl in L['pls']:
        lights.append(C.light_entry((pl['x'] + dx, -DEPTH / 2 + 0.08 + dy, L['mz']), color_k=LIGHT_K, watts=15, kind='point'))
    lights.append(C.light_entry((dx, DEPTH / 2 - 0.06 + dy, 0.715), color_k=LIGHT_K, watts=round(4 * L['w'], 1), kind='strip',
                                p0=[round(-L['w'] / 2 + 0.05 + dx, 3), round(DEPTH / 2 - 0.06 + dy, 3), 0.715],
                                p1=[round(L['w'] / 2 - 0.05 + dx, 3), round(DEPTH / 2 - 0.06 + dy, 3), 0.715], normal=[0, 0, -1]))
    C.set_json_props(o, kz_lights=lights,
                     kz_params=dict(w=round(L['w'], 3), places=L['places'], mirror_r=round(L['R'], 3), mirror=L['mirror'], bowl=L['bowl'],
                                    bottles=[len(p['items']) for p in L['pls']], stools=L['stools'], wall_y=round(-DEPTH / 2 + dy, 3)))
    genlib.finish(o, smooth_angle=40)
    return o


def _build(lod, L, q):
    mseg, bseg, tseg, pm, bev, lean = q
    mb = genlib.MeshBuilder()
    bm = mb.bm
    wood = mb.slot('hinoki', variant='wet_oiled', wear=0.12)
    dark = mb.slot('hinoki', variant='dark_timber')
    stone = mb.slot('basalt_dry', tint=(0.45, 0.45, 0.5), roughness_offset=-0.3)
    bowl_m = stone if L['bowl'] == 'stone' else mb.slot('ceramic', variant='white')
    mirror = mb.slot('lacquer_black', normal_strength=0.0, roughness_offset=-0.06)   # clean black gloss: obsidian's speckle read as marble
    halo = mb.slot('washi_backlit', tint=(1.0, 0.66, 0.32), emissive_level=1.8)
    strip = mb.slot('washi_backlit', emissive_level=1.4)
    glass = mb.slot('lava_glass')
    cap = mb.slot('lacquer_black')
    jar = mb.slot('ceramic', variant='celadon')
    brz = mb.slot('bronze', variant='smooth')
    towel = mb.slot('terry', variant='cream')
    seat = mb.slot('linen', tint=(0.74, 0.64, 0.5))
    W, es = L['w'], L['es']
    yb, yf = -DEPTH / 2, DEPTH / 2
    ztop = TOP_Z
    zt0 = ztop - TOP_T
    yc = yf - 0.03                                  # carcass front
    tk = 0.08
    R = L['R']
    rx, rz = (R, R) if L['mirror'] == 'round' else (R * 0.82, R * 1.38)
    mz = ztop + 0.24 + rz
    L['mz'] = mz
    # ------------------------------------------------------------------ counter
    if lod <= 1:
        if bev:
            C.board(mb, (0, (yb + yf) / 2, ztop - TOP_T / 2), (W, DEPTH, TOP_T), stone, bevel=0.006, segs=2)
        else:
            K.box_open(bm, -W / 2, W / 2, yb, yf, zt0, ztop, stone, sides='ftblr')
        # backsplash board on the wall
        K.box_open(bm, -W / 2, W / 2, yb, yb + 0.02, ztop, ztop + 0.12, dark, sides='ftlr')
        # end panels, place dividers, back, shelf, bottom deck, apron, toe-kick
        for sx in (-1, 1):
            a, b = sorted((sx * W / 2, sx * (W / 2 - es)))
            K.box_open(bm, a, b, yb, yc, 0.0, zt0, wood, sides='flr')
        K.quad(bm, [(-W / 2 + es, yb + 0.01, tk), (W / 2 - es, yb + 0.01, tk), (W / 2 - es, yb + 0.01, zt0), (-W / 2 + es, yb + 0.01, zt0)], dark, (0, 1, 0))
        for i in range(1, L['places']):
            x = -W / 2 + es + i * L['pw']
            K.box_open(bm, x - 0.015, x + 0.015, yb + 0.01, yc - 0.01, tk, zt0, wood, sides='flr')
        for zz, th in ((tk + 0.025, 0.025), (0.40, 0.025)):
            K.ext(bm, [(yb + 0.01, zz - th), (yc - 0.01, zz - th), (yc - 0.01, zz), (yb + 0.01, zz)], 'x', -W / 2 + es, W / 2 - es, wood, caps=(False, False), skip=(3,))
        K.box_open(bm, -W / 2 + es, W / 2 - es, yc - 0.04, yc, 0.72, zt0, wood, sides='fb')        # apron
        K.quad(bm, [(-W / 2 + es, yc - 0.035, 0.718), (W / 2 - es, yc - 0.035, 0.718), (W / 2 - es, yc - 0.012, 0.718), (-W / 2 + es, yc - 0.012, 0.718)], strip, (0, 0, -1))
        K.quad(bm, [(-W / 2 + es, yc - 0.06, 0.0), (W / 2 - es, yc - 0.06, 0.0), (W / 2 - es, yc - 0.06, tk - 0.025), (-W / 2 + es, yc - 0.06, tk - 0.025)], dark, (0, 1, 0))
        K.quad(bm, [(-W / 2 + es, yc - 0.06, tk - 0.025), (W / 2 - es, yc - 0.06, tk - 0.025), (W / 2 - es, yc - 0.01, tk - 0.025), (-W / 2 + es, yc - 0.01, tk - 0.025)], dark, (0, 0, -1))
    elif lod == 2:
        K.box_open(bm, -W / 2, W / 2, yb, yf, zt0, ztop, stone, sides='ftlr')
        K.box_open(bm, -W / 2, W / 2, yb, yb + 0.02, ztop, ztop + 0.12, dark, sides='ft')
        K.box_open(bm, -W / 2, W / 2, yb, yc, tk, zt0, wood, sides='lr')
        K.quad(bm, [(-W / 2, yc, 0.72), (W / 2, yc, 0.72), (W / 2, yc, zt0), (-W / 2, yc, zt0)], wood, (0, 1, 0))
        K.quad(bm, [(-W / 2 + es, yc - 0.3, tk), (W / 2 - es, yc - 0.3, tk), (W / 2 - es, yc - 0.3, 0.72), (-W / 2 + es, yc - 0.3, 0.72)], dark, (0, 1, 0))
        K.quad(bm, [(-W / 2 + es, yc - 0.3, 0.40), (W / 2 - es, yc - 0.3, 0.40), (W / 2 - es, yc, 0.40), (-W / 2 + es, yc, 0.40)], wood, (0, 0, 1))
        K.quad(bm, [(-W / 2, yc, 0.0), (W / 2, yc, 0.0), (W / 2, yc, tk), (-W / 2, yc, tk)], dark, (0, 1, 0))
        K.quad(bm, [(-W / 2, yc - 0.04, 0.718), (W / 2, yc - 0.04, 0.718), (W / 2, yc, 0.718), (-W / 2, yc, 0.718)], strip, (0, 0, -1))
    else:
        K.box_open(bm, -W / 2, W / 2, yb, yf, zt0, ztop, stone, sides='ft')
        K.quad(bm, [(-W / 2, yc, 0.0), (W / 2, yc, 0.0), (W / 2, yc, zt0), (-W / 2, yc, zt0)], wood, (0, 1, 0))
    # ------------------------------------------------------------------ places
    for pi, pl in enumerate(L['pls']):
        px = pl['x']
        ym = yb + 0.004
        if lod <= 1:
            K.annulus_y(bm, px, mz, rz * 0.9, rz + 0.045, ym, mseg, halo, ell=rx / rz)
            # mirror disc on a 25 mm dark frame (sides + bezel), obsidian face
            el_o, el_i = K.ellipse(px, mz, rx, rz, mseg), K.ellipse(px, mz, rx - 0.012, rz - 0.012, mseg)
            K.ext(bm, el_o, 'y', ym + 0.008, ym + 0.032, dark, caps=(False, False))
            if not lean:         # 12 mm bezel round the glass
                fr = [bm.verts.new((u, ym + 0.032, v)) for u, v in el_o]
                fi = [bm.verts.new((u, ym + 0.032, v)) for u, v in el_i]
                for k in range(mseg):
                    k2 = (k + 1) % mseg
                    K.face(bm, [fi[k], fr[k], fr[k2], fi[k2]], dark, (0, 1, 0))
                K.face(bm, [bm.verts.new((u, ym + 0.031, v)) for u, v in el_i], mirror, (0, 1, 0))
            else:
                K.face(bm, [bm.verts.new((u, ym + 0.032, v)) for u, v in el_o], mirror, (0, 1, 0))
            # bowl + bronze spout from the wall
            _bowl(mb, px, -0.02, ztop, L['bowl'], bseg, bowl_m, lean)
            sp = [(px, yb + 0.01, ztop + 0.2), (px, -0.06, ztop + 0.2), (px, -0.035, ztop + 0.175)]
            C.tube(mb, sp, [0.012, 0.012, 0.01], brz, sides=8 if lod == 0 else 5, cap1=True)
            K.ext(bm, K.ellipse(px, ztop + 0.2, 0.03, 0.03, 10 if lod == 0 else 6), 'y', yb + 0.02, yb + 0.032, brz, caps=(False, True))
            # bottles and jars
            for it in pl['items']:
                if it['kind'] == 'bottle':
                    _bottle(mb, it['x'], it['y'], ztop, it['r'], it['h'], tseg, glass, cap, lean)
                else:
                    _jar(mb, it['x'], it['y'], ztop, it['r'], it['h'], tseg, jar, wood)
            # towels on the open shelf
            tw = min(0.34, L['pw'] * 0.42)
            for k in range(pl['towels']):
                sec = K.stadium(yc - 0.05, yc - 0.33, 0.40 + k * 0.058, 0.056, 3 if lod == 0 else 1, puff=0.005 if lod == 0 else 0.0)
                K.ext(bm, sec, 'x', px - tw / 2 + 0.006 * k, px + tw / 2 + 0.006 * k, towel)
        elif lod == 2:
            K.annulus_y(bm, px, mz, rz * 0.9, rz + 0.045, ym, mseg, halo, ell=rx / rz)
            K.face(bm, [bm.verts.new((u, ym + 0.03, v)) for u, v in K.ellipse(px, mz, rx, rz, mseg)], mirror, (0, 1, 0))
            C.lathe(mb, [(0.12, 0), (0.2, 0.12), (0.17, 0.12), (0, 0.06)], bseg, bowl_m, base=(px, -0.02, ztop))
            if pl['items']:
                xs = [it['x'] for it in pl['items']]
                hmax = max(it['h'] for it in pl['items'])
                K.box_open(bm, min(xs) - 0.03, max(xs) + 0.03, -0.2, -0.14, ztop, ztop + hmax, glass, sides='ftlr')
            K.box_open(bm, px - 0.16, px + 0.16, yc - 0.33, yc - 0.05, 0.40, 0.40 + 0.058 * pl['towels'], towel, sides='ft')
        else:
            K.face(bm, [bm.verts.new((u, ym + 0.01, v)) for u, v in K.ellipse(px, mz, rx + 0.045, rz + 0.045, mseg)], halo, (0, 1, 0))
            K.face(bm, [bm.verts.new((u, ym + 0.03, v)) for u, v in K.ellipse(px, mz, rx, rz, mseg)], mirror, (0, 1, 0))
            K.quad(bm, [(px - 0.19, 0.18, ztop), (px + 0.19, 0.18, ztop), (px + 0.19, 0.18, ztop + 0.12), (px - 0.19, 0.18, ztop + 0.12)], bowl_m, (0, 1, 0))
        if L['stools']:
            _stool(mb, px + pl['sdx'], yf + 0.28 + pl['sdy'], pl['yaw'], wood, seat, q, lod)
    return mb
