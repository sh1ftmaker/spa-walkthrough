"""Reception and robe counter: a long hinoki board-and-stile counter under a basalt slab top, floating on
foot blocks over a lit plinth gap, with folded towels (or robes), a key-tag tray, a bell and a small andon.

Identifying features kept at every LOD: long hinoki body, stone (or hinoki) top, glowing plinth gap, folded towel
stacks on top.  Proxy (3d/assets.json): 7 x 1 x 1.05 m (w and d include the slab overhang).  Front faces +Y
(customer side); the staff side is -Y.

Variants (default from the seed: 1 arrival, 2 robe, 3 arrival with a centre bay):
  arrival  towel stacks, key-tag tray, bell, andon, gilt 受付 plaque on the middle stile
  robe     folded indigo-and-cream robe stacks, numbered key-tag rack, gilt 浴衣 plaque
Parameters: w (3-8 m; default <= the 7 m proxy), h (1.0-1.1 m), d (0.8-1.0 m), top ('stone' | 'hinoki'),
bays (panel count; default from w), rhythm ('even' | 'wide_centre' | 'pairs'), plinth_light (bool),
variant ('arrival' | 'robe').

Light data: obj['kz_lights'] = JSON list of low point lights in the plinth gap (one per bay, amber, the spill
on the floor) plus the andon lamp; the glowing plinth strip and the andon are 'lantern_andon' (emissive) faces.
No moving parts.
"""
import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import genlib
import kzgeo_signboard_kanji as K
import kzgeo_bridge_arched as B

ASSET = 'reception_counter'
FEATURES = ['long hinoki board counter', 'stone slab top', 'lit plinth gap on foot blocks', 'folded towel stacks']
PARAMS = dict(w=(3, 8), h=(1.0, 1.1), d=(0.8, 1.0), top=('stone', 'hinoki'), bays='int', rhythm=('even', 'wide_centre', 'pairs'),
              plinth_light=(True, False), variant=('arrival', 'robe'))
CREAM = (40.0, 15.5, 6.0)            # linear tint that turns the indigo noren albedo cream


def build(lod, seed, w=None, h=None, d=None, top=None, bays=None, rhythm=None, plinth_light=True, variant=None):
    p = genlib.proxy(ASSET)
    budget = genlib.budget_of(ASSET) or [3000, 1200, 360, 60]
    for attempt in range(4):
        o = _build_once(lod, seed, w, h, d, top, bays, rhythm, plinth_light, variant, attempt, p)
        if genlib.tris(o) <= budget[lod] * 1.05 or attempt == 3:
            break
        bpy.data.meshes.remove(o.data)
    return genlib.finish(o, smooth_angle=45)


def hex_board(mb, cx, cy, z0, z1, bw, t, c, mi, caps=True):
    """vertical board with the two front vertical edges chamfered (hexagonal section)"""
    bm = mb.bm
    sec = [(-bw / 2, -t / 2), (bw / 2, -t / 2), (bw / 2, t / 2 - c), (bw / 2 - c, t / 2), (-bw / 2 + c, t / 2), (-bw / 2, t / 2 - c)]
    a = [bm.verts.new((cx + x, cy + y, z0)) for x, y in sec]
    b = [bm.verts.new((cx + x, cy + y, z1)) for x, y in sec]
    faces = []
    n = len(sec)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    if caps:
        faces.append(bm.faces.new(a[::-1]))
        faces.append(bm.faces.new(b))
    mb._tag(faces, mi)
    return faces


def _stack(mb, cx, cy, z0, sx, sy, layers, lh, mi, r, tilt=0.06, bevel=0.0, mi2=None):
    mi2 = mi if mi2 is None else mi2
    z = z0
    for k in range(layers):
        jx, jy = r.uniform(-0.012, 0.012), r.uniform(-0.01, 0.01)
        mb.box((cx + jx + (0.01 if k % 2 else -0.01), cy + jy, z + lh / 2), (sx * r.uniform(0.94, 1.0), sy * r.uniform(0.96, 1.0), lh * 0.98), mi if k % 2 == 0 else mi2,
               rot=(0, 0, r.uniform(-tilt, tilt)))
        mb.box((cx + jx + sx / 2 * (1 if k % 2 else -1) * 0.97, cy + jy, z + lh / 2), (0.012, sy * 0.96, lh * 0.9), mi2 if k % 2 == 0 else mi)    # fold edge
        z += lh
    return z


def _build_once(lod, seed, w, h, d, top, bays, rhythm, plinth_light, variant, attempt, p):
    r = genlib.rng(seed, ASSET)
    top = top or ('hinoki' if seed % 3 == 0 else 'stone')
    var = variant or ('robe' if seed % 3 == 2 else 'arrival')
    W = w if w is not None else {1: 6.95 * r.uniform(0.98, 1.0), 2: 5.2 * r.uniform(0.97, 1.0), 0: 4.4 * r.uniform(0.97, 1.0)}[seed % 3]
    W = min(W, p['w'] * 1.05) if w is None else W
    Hh = h if h is not None else 1.05 * r.uniform(0.97, 1.0)          # counter surface height (props stand on it)
    D = d if d is not None else p['d'] * (r.uniform(0.9, 1.0) if var == 'robe' else r.uniform(0.96, 1.0))
    rhythm = rhythm or ['even', 'wide_centre', 'pairs'][(seed - 1) % 3]
    nb = bays or max(3, round(W / 1.2))
    if rhythm == 'wide_centre' and nb % 2 == 0:
        nb += 1
    if rhythm == 'pairs' and nb % 2:
        nb += 1
    mb = genlib.MeshBuilder()
    lod3 = lod == 3
    lod = min(lod, 2) if not lod3 else 2
    wood = mb.slot('hinoki', wear=round(r.uniform(0.05, 0.2), 2))
    wood_d = mb.slot('hinoki', variant='dark_timber', wear=0.05)
    dark = mb.slot('lacquer_black')
    stone = mb.slot('obsidian', wetness=0.4) if top == 'stone' else mb.slot('hinoki', variant='dark_timber', wear=0.1)
    glow = mb.slot('washi_backlit', emissive_level=1.2, tint=(1.0, 0.5, 0.15))
    iron = mb.slot('iron', wear=0.4)
    bronze = mb.slot('bronze', wear=0.2)
    cloth = mb.slot('noren', variant='cream', wear=0.0, normal_strength=0.7)
    ink = mb.slot('lacquer_black')
    wood3 = mb.slot('hinoki', variant='wet_oiled', wear=round(r.uniform(0.05, 0.2), 2))
    wood2 = mb.slot('hinoki', variant='natural', wear=round(r.uniform(0.05, 0.2), 2))
    cloth2 = mb.slot('linen', wear=0.0)
    indigo = mb.slot('noren', wear=0.1, normal_strength=0.6)
    gold = mb.slot('gold_leaf')

    # ------------------------------------------------ vertical layout
    slab_t = 0.09
    z_top = Hh
    z_body1 = z_top - slab_t
    foot_h = 0.115
    z_body0 = foot_h
    rail_h = 0.075
    yb = D / 2 - 0.07                       # front plane of the body (stiles)
    yk = -D / 2 + 0.05                       # back plane
    bd = yb - yk                             # body depth
    stile = 0.08
    # ------------------------------------------------ bay layout (x, viewer-symmetric)
    inner = W - 0.14                         # body width: 7 cm overhang each end
    ws = {'even': [1.0] * nb, 'wide_centre': [(1.7 if i == nb // 2 else 1.0) for i in range(nb)],
          'pairs': [(1.25 if i % 4 in (1, 2) else 0.85) for i in range(nb)]}[rhythm]
    tot = sum(ws)
    xs = [-inner / 2]
    for k in ws:
        xs.append(xs[-1] + inner * k / tot)
    xs[-1] = inner / 2
    centers = [(xs[i] + xs[i + 1]) / 2 for i in range(nb)]

    # ------------------------------------------------ body core (dark, closes the gaps) and the plinth gap
    core_h = z_body1 - z_body0
    if lod == 2:
        mb.box((0, (yb + yk) / 2, z_body0 + core_h / 2), (inner, bd - 0.09, core_h), wood)       # recessed panel plane
    else:
        mb.box((0, (yb + yk) / 2, z_body0 + core_h / 2), (inner - 0.02, bd - 0.09, core_h), dark)
    # toe-kick: a dark board set back from the stiles with the amber light hidden behind it (only a 3 cm line shows)
    mb.box((0, (yb + yk) / 2, foot_h / 2), (inner - 0.04, bd - 0.2, foot_h - 0.005), dark)
    mb.box((0, yb - 0.065, 0.065 + (foot_h - 0.065) / 2), (inner - 0.1, 0.02, foot_h - 0.065), dark)
    if plinth_light:
        if lod == 2:
            mb.box((0, yb - 0.12, 0.02), (inner - 0.1, 0.02, 0.04), glow)
        else:
            mb.box((0, yb - 0.07, 0.03), (inner - 0.12, 0.012, 0.058), glow)             # one continuous 6 cm slot, flush under the toe-kick board
    # ------------------------------------------------ foot blocks + stiles (front and back)
    for i, x in enumerate(xs):
        end = i in (0, nb)
        sw = stile * (1.25 if end else 1.0)
        xx = x + (0.0 if not end else (sw / 2 - stile / 2) * (1 if i == 0 else -1))
        for yy, side in ((yb - stile / 2, 1), (yk + stile / 2, -1)):
            zf = z_body1 - z_body0
            if lod == 0:
                K.chamfered_bar(mb, (xx, yy, z_body0 + zf / 2), (sw, stile, zf), wood, ch=0.014, axis='z')
                mb.box((xx, yy, foot_h / 2), (sw * 1.12, stile * 1.18, foot_h), wood_d)
                # iron strap on the foot and a small plate at the stile head (front only)
                if side > 0:
                    mb.box((xx, yy + stile * 0.62, foot_h * 0.5), (sw * 0.7, 0.008, foot_h * 0.8), iron)
                    # strap plate 0.12 x 0.25 with four bolt heads
                    zs_ = z_body1 - 0.16
                    mb.box((xx, yy + stile * 0.52, zs_), (0.12, 0.008, 0.25), iron)
                    for bx_ in (-0.04, 0.04):
                        for bz_ in (-0.09, 0.09):
                            K.flat_poly(mb, [(xx + bx_ + 0.008, zs_ + bz_ + 0.008), (xx + bx_ - 0.008, zs_ + bz_ + 0.008), (xx + bx_ - 0.008, zs_ + bz_ - 0.008), (xx + bx_ + 0.008, zs_ + bz_ - 0.008)], yy + stile * 0.52 + 0.0045, bronze)
            elif lod == 1:
                mb.box((xx, yy, z_body0 + zf / 2), (sw, stile, zf), wood)
                mb.box((xx, yy, foot_h / 2), (sw * 1.12, stile * 1.18, foot_h), wood_d)
            elif side > 0:
                mb.box((xx, yy, z_body0 + zf / 2), (sw, stile, zf), wood)
    # ------------------------------------------------ rails (top/bottom of the panels) front and back
    if lod == 2:
        mb.box((0, yb - stile * 0.35, z_body1 - rail_h / 2), (inner, stile * 0.7, rail_h), wood)
    if lod <= 1:
        for yy, sgn in ((yb - stile * 0.35, 1), (yk + stile * 0.35, -1)):
            for z in (z_body1 - rail_h / 2, z_body0 + rail_h * 0.5):
                if lod == 0:
                    K.chamfered_bar(mb, (0, yy, z), (inner, stile * 0.7, rail_h), wood, ch=0.012, axis='x')
                else:
                    mb.box((0, yy, z), (inner, stile * 0.7, rail_h), wood)
    if lod == 0:
        mb.box((0, yb - 0.005, 0.12), (inner, 0.03, 0.07), wood_d)                       # continuous 7 cm base rail
        for i in range(nb):
            mb.box((centers[i], yb - 0.012, (z_body0 + z_body1) / 2), (xs[i + 1] - xs[i] - stile, 0.024, 0.04), wood)   # mid rail per bay
    # ------------------------------------------------ boards in each bay (front) and a plain back
    zb0, zb1 = z_body0 + rail_h, z_body1 - rail_h
    bcount = 0
    for i in range(nb):
        x0, x1 = xs[i] + stile * 0.5, xs[i + 1] - stile * 0.5
        span = x1 - x0
        if lod == 0:
            nbd = max(3, round(span / 0.125))
            bw = span / nbd
            for k in range(nbd):
                xc = x0 + bw * (k + 0.5)
                hex_board(mb, xc, yb - 0.043, zb0, zb1, bw - 0.0025, 0.026, 0.0035, [wood, wood2, wood3][(k * 7 + i * 3 + (k * k) % 5) % 3], caps=False)
            nbk = max(2, round(span / 0.3))
            bwk = span / nbk
            for k in range(nbk):
                hex_board(mb, x0 + bwk * (k + 0.5), yk + 0.034, zb0, zb1, bwk - 0.003, 0.026, 0.003, wood2, caps=False)
        elif lod == 1:
            nbd = max(2, round(span / 0.3))
            bw = span / nbd
            for k in range(nbd):
                mb.box((x0 + bw * (k + 0.5), yb - 0.043, (zb0 + zb1) / 2), (bw - 0.006, 0.026, zb1 - zb0), wood)
            mb.box((centers[i], yk + 0.034, (zb0 + zb1) / 2), (span, 0.026, zb1 - zb0), wood)
        else:
            mb.box((centers[i], yb - 0.043, (zb0 + zb1) / 2), (span, 0.026, zb1 - zb0), wood)
    # gilt plaque on the middle stile / bay
    plaque = '受付' if var == 'arrival' else '浴衣'
    cb = nb // 2
    xp = centers[cb] if nb % 2 else xs[cb]
    if lod <= 1:
        pzh = 0.4
        pw_ = 0.12
        mb.box((xp, yb + 0.004, (zb0 + zb1) / 2), (pw_, 0.014, pzh), wood, bevel=0.003 if lod == 0 else 0.0)
        K.add_text(mb, plaque, xp, (zb0 + zb1) / 2, yb + 0.0115, 0.1, ink, res=1, vertical=True, dissolve=0.4, gap=1.2, max_w=pw_ * 0.84)
    # ------------------------------------------------ stone (or hinoki) top: jointed slabs, chamfered irregular edges
    ns = max(2, round(W / 1.75))
    sj = [0.0] + sorted(r.uniform(0.18, 0.82) * 0 + (k + r.uniform(-0.22, 0.22)) / ns for k in range(1, ns)) + [1.0]
    zc = z_top - slab_t / 2
    for k in range(ns):
        xa, xb = -W / 2 + W * sj[k] + (0.003 if k else 0), -W / 2 + W * sj[k + 1] - (0.003 if k < ns - 1 else 0)
        t_k = slab_t * r.uniform(0.94, 1.04)
        M = Matrix.Translation(((xa + xb) / 2, 0, z_top - t_k / 2))
        if lod == 0:
            B.cbox(mb, M, (xb - xa, D, t_k), stone, bevel=0.02, segs=1, jitter=0.002, r=r)
        elif lod == 1:
            mb.box(((xa + xb) / 2, 0, z_top - t_k / 2), (xb - xa, D, t_k), stone, bevel=0.02)
        else:
            mb.box(((xa + xb) / 2, 0, z_top - t_k / 2), (xb - xa, D, t_k), stone)
    # ------------------------------------------------ things on the counter
    zt = z_top + 0.0
    nst = 3 if var == 'arrival' else 4
    if W < 4.5:
        nst = 2
    # towel / robe stacks sit over bays chosen from the seed
    pick = sorted(r.sample(range(nb), min(nb, nst)))
    ys = D * 0.16
    for k, bi in enumerate(pick):
        cx = centers[bi] + r.uniform(-0.08, 0.08)
        cy = r.uniform(-0.08, 0.1)
        if var == 'arrival' or k % 2 == 0:
            layers = r.randint(3, 4) if lod == 0 else 3
            lh = 0.04 if lod == 0 else 0.1
            sx_, sy_ = (0.30, 0.17) if lod < 2 else (0.3, 0.17)
            if lod == 2:
                mb.box((cx, cy, zt + 0.09), (0.3, 0.17, 0.18), cloth)
                continue
            if lod == 1:
                mb.box((cx, cy, zt + 0.09), (0.3, 0.17, 0.18), cloth)
                continue
            _stack(mb, cx, cy, zt, sx_, sy_, layers, lh, cloth, r, mi2=cloth2)
            if k == 0:
                # three rolled towels lying beside the stack
                for q in range(3):
                    mb.cylinder((cx - 0.3, cy + (q - 1) * 0.075, zt + 0.035), 0.035, 0.26, cloth if q != 1 else cloth2, segs=8, rot=(0, math.pi / 2, r.uniform(-0.08, 0.08)))
            if k == 0 and var == 'arrival':
                # a second, smaller stack of face towels beside it
                _stack(mb, cx + 0.34, cy + 0.02, zt, 0.2, 0.2, r.randint(3, 4), 0.035, cloth, r, mi2=cloth2)
        else:
            layers = r.randint(4, 5) if lod == 0 else 2
            if lod == 2:
                mb.box((cx, cy, zt + 0.1), (0.4, 0.28, 0.2), indigo)
                continue
            if lod == 1:
                mb.box((cx, cy, zt + 0.1), (0.4, 0.28, 0.2), indigo)
                mb.box((cx, cy, zt + 0.205), (0.4, 0.28, 0.02), cloth)
                continue
            z = zt
            for q in range(layers):
                lh = 0.04
                mb.box((cx + r.uniform(-0.01, 0.01), cy, z + lh / 2), (0.4, 0.28, lh * 0.98), indigo, rot=(0, 0, r.uniform(-0.04, 0.04)), bevel=0.006 if q == layers - 1 else 0.0)
                z += lh
                if q % 2 == 1:
                    mb.box((cx, cy + 0.0, z + 0.003), (0.06, 0.285, 0.006), cloth)      # obi band
    if lod == 0:
        # key-tag tray (open hinoki box) with standing tags, a bell, a small andon
        xt = centers[(pick[-1] + 1) % nb] if len(pick) else 0.0
        xt = r.choice([centers[0] + 0.1, centers[-1] - 0.1]) if r.random() < 0.5 else xt
        ty = -0.1
        mb.box((xt, ty, zt + 0.01), (0.34, 0.2, 0.02), wood_d)
        for sx_, sy_, szx, szy in ((0, 0.1, 0.34, 0.016), (0, -0.1, 0.34, 0.016), (0.17, 0, 0.016, 0.2), (-0.17, 0, 0.016, 0.2)):
            mb.box((xt + sx_, ty + sy_, zt + 0.04), (szx, szy, 0.04), wood_d)
        for q in range(7 if var == 'robe' else 5):
            mb.box((xt - 0.13 + q * 0.043, ty + r.uniform(-0.02, 0.02), zt + 0.065), (0.03, 0.006, 0.075), wood, rot=(r.uniform(-0.2, 0.2), 0, r.uniform(-0.05, 0.05)))
        xbl = centers[min(nb - 1, (pick[0] + 2) % nb)] if var == 'arrival' else centers[-1] - 0.3
        B.lathe(mb, (xbl, 0.12, zt), [(0.0, 0.0), (0.045, 0.0), (0.04, 0.012), (0.034, 0.05), (0.02, 0.07), (0.0, 0.075)], bronze, segs=8)
        # small andon lamp (box lantern with four posts)
        xa_ = centers[0] + 0.28 if var == 'arrival' else centers[-1] - 0.75
        mb.box((xa_, -0.05, zt + 0.1), (0.15, 0.15, 0.17), glow)
        for sx_ in (-1, 1):
            for sy_ in (-1, 1):
                mb.box((xa_ + sx_ * 0.075, -0.05 + sy_ * 0.075, zt + 0.1), (0.014, 0.014, 0.18), wood_d)
        mb.box((xa_, -0.05, zt + 0.195), (0.19, 0.19, 0.016), dark)
        mb.box((xa_, -0.05, zt + 0.005), (0.18, 0.18, 0.01), wood_d)
    elif lod == 1:
        xa_ = centers[0] + 0.28 if var == 'arrival' else centers[-1] - 0.75
        mb.box((xa_, -0.05, zt + 0.1), (0.15, 0.15, 0.2), glow)
    if lod3:
        mb.bm.clear()
        _lod3(mb, W, D, z_top, glow, wood, stone, cloth, foot_h, slab_t, pick, centers)
    o = K.to_object(mb, ASSET)
    nl = max(3, int(inner / 0.8))
    strip = [dict(pos=[0, yb + 0.12, 0.04], len=inner - 0.2, color=[1.0, 0.55, 0.2], energy=120.0, note='continuous plinth spill (area strip)')]
    lights = strip + [dict(pos=[-inner / 2 + inner * (i + 0.5) / nl, yb + 0.1, 0.05], color=[1.0, 0.55, 0.2], energy=5.0, size=0.4, note='plinth spill, overlapping') for i in range(nl)]
    o['kz_lights'] = json.dumps(lights)
    o['kz_params'] = json.dumps(dict(variant=var, w=round(W, 3), h=round(Hh, 3), d=round(D, 3), top=top, bays=nb, rhythm=rhythm, plinth_light=plinth_light))
    return o


def _lod3(mb, W, D, H, glow, wood, stone, cloth, foot_h, slab_t, pick, centers):
    """60-triangle silhouette: slab top, recessed body, three stile blocks that step the front, glow quad, one towel stack"""
    mb.box((0, 0, H - slab_t / 2), (W, D, slab_t), stone)                                             # 12
    bh = H - slab_t - foot_h
    mb.box((0, -0.04, foot_h + bh / 2), (W - 0.14, D - 0.2, bh), wood)                                # 12
    for x in (-(W - 0.3) / 2, 0.0, (W - 0.3) / 2):
        mb.box((x, D / 2 - 0.15, foot_h + bh / 2), (0.16, 0.1, bh), wood)                             # 3 x 12
    K.flat_poly(mb, [((W - 0.3) / 2, 0.0), (-(W - 0.3) / 2, 0.0), (-(W - 0.3) / 2, foot_h * 0.8), ((W - 0.3) / 2, foot_h * 0.8)], D / 2 - 0.12, glow)   # 2
