"""Backlit cubby wall (yukata, towels, baskets): a wall of open hinoki cubbies whose paper backs glow like a
washi lantern, each holding a stack of folded undyed linen yukata or cream towels, with a row of woven
baskets at the bottom, over a closed base cabinet and a lit toe-kick.

Identifying features kept at every LOD: the grid of open cubbies, the glowing backs, the folded stacks in
every cell, the basket row at the bottom.

Targets (refs/gen/sheet-ref-ground.png panel 01 "changing hall", left; dh-changing-treatment.png
"yukata shelves (amber backlit)"; measured against the bench seat 0.45 m and the door 2.0-2.1 m):
  * bay (cell) width 0.62-0.78 m between 0.06-0.07 m stiles; shelf pitch 0.34-0.40 m; shelves 35 mm with a
    lit strip under the front edge; one stack of 3-4 folded items per cell, ~75 % of the cell width,
    filling ~45-55 % of the cell height; folded fronts are rounded (no knife edge).
  * bottom content row: woven baskets, one per bay (~0.8 x bay width, 0.22-0.26 m tall).
  * closed base cabinet 0.36-0.40 m with panel doors, a recessed 0.08 m toe-kick with a light strip,
    a 0.14 m cornice with a downlight strip.
  * overall: row typical 14 x 0.6 x 3.4 m; proxy (3d/assets.json) 6 x 0.6 x 2.4 m is the default build.
    Range w 2-14 m, h 2.4-3.4 m (dims beyond the proxy fail the proxy check by design: give them their
    own proxy).

Parameters: w, h, d, bay (cell width), contents 'yukata' | 'towels' | 'baskets', backlight (washi back
emissive level, 0.6-1.4, default 1.0), basket_rows (1-2).
Styles (seed cycle): 1 yukata wall (6.0 x 2.4, 0.72 m bays, linen yukata with an indigo obi on each
stack), 2 towel shelf (3.0-3.6 m, 0.58-0.64 m bays, cream terry, 1 or 2 stacks per cell by row),
3 basket row (4.2-4.8 m, two basket rows with towels peeking, towels above). Seeds also change the
cornice (stepped / slab), kumiko on the backs (2 bars / 1 bar + rail), per-cell item counts, offsets.

Materials: hinoki wet_oiled (carcass), hinoki dark_timber (cornice cap, plinth), washi_backlit (cell
backs, emissive = backlight; light strips at 1.4), linen (yukata), terry cream (towels), noren (obi),
tatami (basket weave), bronze smooth (pulls).
Lights: obj['kz_lights'], one area entry per bay at the middle of the glowing backs (2700 K) plus the
toe-kick strip. Lightmap + emissive. No animation. Wall-snapped: back at y = -d/2, front +Y.
"""
import json
import math

import bmesh
import bpy

import genlib
import kzgeo_common as C
import kzgeo_yukata_shelves as K

ASSET = 'yukata_shelves'
FEATURES = ['grid of open hinoki cubbies', 'glowing washi backs', 'folded linen yukata / towels in every cell',
            'basket row at the bottom']
STYLES = ['yukata', 'towels', 'baskets']
PARAMS = dict(w=(2.0, 14.0), h=(2.4, 3.4), bay=(0.55, 0.8), contents=tuple(STYLES), backlight=(0.6, 1.4),
              basket_rows=(1, 2))
LIGHT_K = 2700


def _to_object(mb, name):
    me = bpy.data.meshes.new(name)
    mb.bm.to_mesh(me)
    mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for i, (mid, params) in enumerate(mb.slots):
        genlib.matlib.assign(o, mid, slot=i, **params)
    return o


def _layout(seed, w, h, d, bay, contents, basket_rows):
    p = genlib.proxy(ASSET)
    style = contents or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    if seed <= 3:
        w_s = {'yukata': p['w'], 'towels': g.choice([3.0, 3.6]), 'baskets': g.choice([4.2, 4.8])}[style]
    else:
        w_s = g.choice([2.4, 3.0, 3.6, 4.2, 4.8, 6.0])
    w = min(max(w or w_s, 2.0), 14.0)
    h = min(max(h or p['h'], 2.4), 3.4)
    d = d or p['d']
    bay = bay or {'yukata': g.uniform(0.70, 0.76), 'towels': g.uniform(0.58, 0.64), 'baskets': g.uniform(0.64, 0.7)}[style]
    nb = basket_rows or (2 if style == 'baskets' else 1)
    L = dict(style=style, w=w, h=h, d=d, nb=nb)
    L['es'], L['st'], L['sh'] = 0.055, 0.065, 0.035
    L['tk'], L['base'] = 0.08, g.uniform(0.36, 0.40)
    L['cornice'] = 'stepped' if C.pick(seed, 'cornice', [0, 1]) == 0 else 'slab'
    L['ch'] = 0.15 if L['cornice'] == 'stepped' else 0.12
    L['kumiko'] = C.pick(seed, 'kumiko', ['bars', 'rail'])
    L['yb'], L['yf'] = -d / 2, d / 2 - 0.03
    inner = w - 2 * L['es']
    n = max(1, round((inner + L['st']) / (bay + L['st'])))
    L['nbays'] = n
    L['bw'] = (inner - (n - 1) * L['st']) / n
    L['bays'] = [(-w / 2 + L['es'] + i * (L['bw'] + L['st'])) for i in range(n)]
    z0 = L['tk'] + L['base']
    z1 = h - L['ch']
    pb = 0.32                                            # basket row pitch
    pitch_t = {'yukata': 0.37, 'towels': 0.35, 'baskets': 0.36}[style]
    nc = max(2, round((z1 - z0 - nb * pb) / pitch_t))
    pc = (z1 - z0 - nb * pb) / nc
    rows = []
    z = z0
    for i in range(nb):
        rows.append(('basket', z, pb)); z += pb
    for i in range(nc):
        rows.append(('stack', z, pc)); z += pc
    L['rows'], L['z0'], L['z1'] = rows, z0, z1
    # ---- contents: one stream per concern, independent of LOD
    gi = C.rng(seed, 'items')
    cells = []
    for bi, x0 in enumerate(L['bays']):
        for ri, (kind, zr, pr) in enumerate(rows):
            cx = x0 + L['bw'] / 2
            if kind == 'basket':
                cells.append(dict(kind='basket', bi=bi, ri=ri, cx=cx + gi.uniform(-0.01, 0.01), z=zr, p=pr,
                                  W=L['bw'] * gi.uniform(0.78, 0.84), D=gi.uniform(0.34, 0.38), H=gi.uniform(0.21, 0.25),
                                  peek=(style == 'baskets' or gi.random() < 0.25)))
                continue
            if style == 'yukata':
                n_it = gi.choice([3, 3, 4, 4, 4]) if pr > 0.33 else 3
                stacks = [(cx, L['bw'] * gi.uniform(0.70, 0.76), 0.32, 0.05, n_it, 'yukata')]
            else:
                two = style == 'towels' and (ri % 2 == 1) and L['bw'] > 0.55
                if two:
                    sw = L['bw'] * 0.42
                    stacks = [(cx + s * L['bw'] * 0.24, sw * gi.uniform(0.95, 1.0), 0.26, 0.045, gi.choice([4, 5]), 'towel') for s in (-1, 1)]
                else:
                    stacks = [(cx, L['bw'] * gi.uniform(0.68, 0.76), 0.30, 0.065, gi.choice([3, 3, 4]), 'towel')]
            for sx, sw, sd, st_, n_it, kind2 in stacks:
                items = []
                zz = zr + 0.0
                for k in range(n_it):
                    items.append(dict(x=sx + gi.uniform(-0.012, 0.012), y=gi.uniform(-0.012, 0.008), W=sw * gi.uniform(0.96, 1.02),
                                      D=sd * gi.uniform(0.97, 1.02), t=st_ * gi.uniform(0.92, 1.08), yaw=gi.uniform(-0.035, 0.035), z=zz))
                    zz += items[-1]['t'] + 0.001
                cells.append(dict(kind=kind2, bi=bi, ri=ri, cx=sx, z=zr, p=pr, items=items,
                                  obi=(kind2 == 'yukata'), obi_x=sx + gi.choice([-1, 1]) * sw * gi.uniform(0.18, 0.26)))
    L['cells'] = cells
    return L


def build(lod, seed, w=None, h=None, d=None, bay=None, contents=None, backlight=1.0, basket_rows=None, **_):
    L = _layout(seed, w, h, d, bay, contents, basket_rows)
    budget = (genlib.budget_of(ASSET) or [12000, 4800, 1440, 200])[lod]
    mb = genlib.MeshBuilder()
    bm = mb.bm
    wood = mb.slot('hinoki', variant='wet_oiled', wear=0.15)
    wood_in = mb.slot('hinoki', variant='wet_oiled', tint=(0.36, 0.27, 0.19))        # shelf tops / cell sides (shade)
    cap = mb.slot('hinoki', variant='dark_timber')
    paper = mb.slot('washi_backlit', emissive_level=round(float(backlight), 2))
    strip = mb.slot('washi_backlit', emissive_level=1.4)
    yuk = mb.slot('linen')
    towel = mb.slot('terry', variant='cream')
    obi = mb.slot('noren')
    weave = mb.slot('tatami', tint=(0.62, 0.5, 0.34))
    pull = mb.slot('bronze', variant='smooth')
    W, H, D = L['w'], L['h'], L['d']
    yb, yf, es, st, sh, tk = L['yb'], L['yf'], L['es'], L['st'], L['sh'], L['tk']
    z0, z1, bw = L['z0'], L['z1'], L['bw']
    xL, xR = -W / 2 + es, W / 2 - es
    yback = yb + 0.015                       # paper plane (a back board sits behind it)
    rows = L['rows']
    shelf_z = [r[1] for r in rows] + [z1]    # shelf tops (the first is the base-cabinet top)

    # ------------------------------------------------------------------ carcass
    if lod <= 1:
        c = 0.006 if lod == 0 else 0.0
        # end panels (full height to the cornice, chamfered front edges)
        for sx in (-1, 1):
            a, b = sorted((sx * W / 2, sx * (W / 2 - es)))
            K.ext(bm, K.chamfer_rect(a, b, yb, yf, c), 'z', 0.0, H - L['ch'], wood, caps=(False, True))
        # back board (dark) behind the paper
        K.quad(bm, [(xL, yb, 0.0), (xR, yb, 0.0), (xR, yb, z1), (xL, yb, z1)], cap, (0, 1, 0))
        # stiles between bays: from the plinth to the cornice, chamfered, proud of the shelves
        for i in range(L['nbays'] - 1):
            a = L['bays'][i] + bw
            K.ext(bm, K.chamfer_rect(a, a + st, yback, yf, c), 'z', tk, z1, wood, caps=(False, False), skip=(0,))
        # shelves: one per row boundary, full bay width, front edge chamfered, with a lit strip underneath
        for zi, zt in enumerate(shelf_z):
            for x0 in L['bays']:
                sec = [(yback, zt - sh), (yf - 0.012 - c, zt - sh), (yf - 0.012, zt - sh + c), (yf - 0.012, zt), (yback, zt)] if c else \
                      [(yback, zt - sh), (yf - 0.012, zt - sh), (yf - 0.012, zt), (yback, zt)]
                K.ext(bm, sec, 'x', x0, x0 + bw, wood_in, caps=(False, False), mi_front=wood)
                if zi > 0:     # light strip under the shelf front (lights the cell below)
                    K.quad(bm, [(x0 + 0.01, yf - 0.06, zt - sh - 0.002), (x0 + bw - 0.01, yf - 0.06, zt - sh - 0.002),
                                (x0 + bw - 0.01, yf - 0.035, zt - sh - 0.002), (x0 + 0.01, yf - 0.035, zt - sh - 0.002)], strip, (0, 0, -1))
            # cell side faces are the stiles; paper backs per cell
        for x0 in L['bays']:
            for (kind, zr, pr) in rows:
                za, zb = zr, zr + pr - sh
                K.quad(bm, [(x0, yback, za), (x0 + bw, yback, za), (x0 + bw, yback, zb), (x0, yback, zb)], paper, (0, 1, 0))
                if lod == 0:   # kumiko on the paper: two vertical bars (or one bar and a mid rail)
                    bars = [(x0 + bw / 3, 'v'), (x0 + 2 * bw / 3, 'v')] if L['kumiko'] == 'bars' else [(x0 + bw / 2, 'v'), ((za + zb) / 2, 'h')]
                    for pos, o in bars:
                        if o == 'v':
                            K.box_open(bm, pos - 0.008, pos + 0.008, yback, yback + 0.012, za, zb, wood, sides='flr')
                        else:
                            K.box_open(bm, x0, x0 + bw, yback, yback + 0.012, pos - 0.008, pos + 0.008, wood, sides='fbt')
        # cornice: fascia + cap board (stepped: an extra 30 mm step), downlight strip under it
        zc = H - L['ch']
        if L['cornice'] == 'stepped' and lod == 0:
            sec = [(yb, zc), (yf + 0.004, zc), (yf + 0.004, zc + 0.09), (yf + 0.018, zc + 0.09), (yf + 0.018, zc + 0.115),
                   (D / 2, zc + 0.115), (D / 2, H), (yb, H)]
        else:
            sec = [(yb, zc), (yf + 0.004, zc), (yf + 0.004, H - 0.035), (D / 2, H - 0.035), (D / 2, H), (yb, H)]
        K.ext(bm, sec, 'x', -W / 2, W / 2, cap, skip=(len(sec) - 1,))
        # base cabinet: one panel door per bay with a bronze pull, carcass face behind
        zb0, zb1 = tk, z0 - sh
        K.quad(bm, [(xL, yf - 0.008, zb0), (xR, yf - 0.008, zb0), (xR, yf - 0.008, zb1), (xL, yf - 0.008, zb1)], cap, (0, 1, 0))
        for i, x0 in enumerate(L['bays']):
            xa, xb = x0 - st / 2 + 0.006 if i else x0 + 0.004, x0 + bw + st / 2 - 0.006 if i < L['nbays'] - 1 else x0 + bw - 0.004
            if lod == 0:
                C.board(mb, ((xa + xb) / 2, yf + 0.002, (zb0 + zb1) / 2), (xb - xa - 0.006, 0.02, zb1 - zb0 - 0.012), wood, bevel=0.004)
                C.board(mb, ((xa + xb) / 2, yf + 0.016, zb1 - 0.07), (min(0.14, (xb - xa) * 0.3), 0.012, 0.016), pull, bevel=0.003)
            else:
                K.quad(bm, [(xa + 0.003, yf + 0.008, zb0 + 0.006), (xb - 0.003, yf + 0.008, zb0 + 0.006), (xb - 0.003, yf + 0.008, zb1 - 0.006),
                            (xa + 0.003, yf + 0.008, zb1 - 0.006)], wood, (0, 1, 0))
                pw = min(0.14, (xb - xa) * 0.3) / 2
                K.quad(bm, [((xa + xb) / 2 - pw, yf + 0.012, zb1 - 0.078), ((xa + xb) / 2 + pw, yf + 0.012, zb1 - 0.078),
                            ((xa + xb) / 2 + pw, yf + 0.012, zb1 - 0.062), ((xa + xb) / 2 - pw, yf + 0.012, zb1 - 0.062)], pull, (0, 1, 0))
        # toe-kick: recessed dark face + light strip
        K.quad(bm, [(xL, yf - 0.07, 0.0), (xR, yf - 0.07, 0.0), (xR, yf - 0.07, tk), (xL, yf - 0.07, tk)], cap, (0, 1, 0))
        K.quad(bm, [(xL, yf - 0.07, tk), (xR, yf - 0.07, tk), (xR, yf - 0.008, tk), (xL, yf - 0.008, tk)], cap, (0, 0, -1))
        K.quad(bm, [(xL, yf - 0.05, tk - 0.002), (xR, yf - 0.05, tk - 0.002), (xR, yf - 0.025, tk - 0.002), (xL, yf - 0.025, tk - 0.002)], strip, (0, 0, -1))
    elif lod == 2:
        for sx in (-1, 1):
            a, b = sorted((sx * W / 2, sx * (W / 2 - es)))
            K.box_open(bm, a, b, yb, yf, 0.0, H - L['ch'], wood, sides='flr')
        for i in range(L['nbays'] - 1):
            a = L['bays'][i] + bw
            K.quad(bm, [(a, yf, tk), (a + st, yf, tk), (a + st, yf, z1), (a, yf, z1)], wood, (0, 1, 0))
        for zi, zt in enumerate(shelf_z):
            K.quad(bm, [(xL, yf - 0.012, zt - sh), (xR, yf - 0.012, zt - sh), (xR, yf - 0.012, zt), (xL, yf - 0.012, zt)], wood, (0, 1, 0))
            K.quad(bm, [(xL, yback, zt), (xR, yback, zt), (xR, yf - 0.012, zt), (xL, yf - 0.012, zt)], wood_in, (0, 0, 1))
        for (kind, zr, pr) in rows:
            K.quad(bm, [(xL, yback, zr), (xR, yback, zr), (xR, yback, zr + pr - sh), (xL, yback, zr + pr - sh)], paper, (0, 1, 0))
        K.box_open(bm, -W / 2, W / 2, yb, D / 2, H - L['ch'], H, cap, sides='fbt')
        K.quad(bm, [(xL, yf, tk), (xR, yf, tk), (xR, yf, z0 - sh), (xL, yf, z0 - sh)], wood, (0, 1, 0))
        K.quad(bm, [(xL, yf - 0.05, tk), (xR, yf - 0.05, tk), (xR, yf, tk), (xL, yf, tk)], strip, (0, 0.3, -1))
    else:
        K.box_open(bm, -W / 2, W / 2, yb, D / 2, H - L['ch'], H, cap, sides='ft')    # cornice front + top (keeps the depth)
        for sx in (-1, 1):
            a, b = sorted((sx * W / 2, sx * (W / 2 - es)))
            K.quad(bm, [(a, yf, 0), (b, yf, 0), (b, yf, H - L['ch']), (a, yf, H - L['ch'])], wood, (0, 1, 0))
        K.quad(bm, [(xL, yback, z0), (xR, yback, z0), (xR, yback, z1), (xL, yback, z1)], paper, (0, 1, 0))
        for i in range(L['nbays'] - 1):
            a = L['bays'][i] + bw
            K.quad(bm, [(a, yf, z0), (a + st, yf, z0), (a + st, yf, z1), (a, yf, z1)], wood, (0, 1, 0))
        for zt in shelf_z:
            K.quad(bm, [(xL, yf - 0.012, zt - sh), (xR, yf - 0.012, zt - sh), (xR, yf - 0.012, zt), (xL, yf - 0.012, zt)], wood, (0, 1, 0))
        K.quad(bm, [(xL, yf, tk), (xR, yf, tk), (xR, yf, z0 - sh), (xL, yf, z0 - sh)], wood, (0, 1, 0))
        K.quad(bm, [(xL, yf - 0.05, tk), (xR, yf - 0.05, tk), (xR, yf, tk), (xL, yf, tk)], strip, (0, 0.3, -1))

    # ------------------------------------------------------------------ contents (same cells at every LOD)
    left = budget - C.tri_count(bm)
    stacks = [c for c in L['cells'] if c['kind'] != 'basket']
    baskets = [c for c in L['cells'] if c['kind'] == 'basket']
    n_items = sum(len(c['items']) for c in stacks)
    yfront = yf - 0.035                     # folded fronts sit 35 mm behind the shelf nosing
    if lod <= 1:
        # item tier by arithmetic: arc segments per fold end (tris per item = 2P + 2(P-2), P = 2n + 4)
        bcost = 64 if lod == 0 else 34
        extra = sum(14 for c in stacks if c['obi'])
        arcs = [4, 3, 2, 1] if lod == 0 else [2, 1]
        n_arc = arcs[-1]
        for n_ in arcs:
            P = 2 * n_ + 4
            if n_items * (4 * P - 4) + len(baskets) * bcost + extra <= left:
                n_arc = n_
                break
        if n_arc != arcs[0]:
            print(f'[{ASSET}] LOD{lod}: fold arcs reduced to {n_arc} for {n_items} items (budget {budget})')
        for c in stacks:
            mi = yuk if c['kind'] == 'yukata' else towel
            for it in c['items']:
                Dd = it['D']
                sec = K.stadium(yfront + it['y'], yfront + it['y'] - Dd, it['z'], it['t'], n_arc, puff=0.006 if lod == 0 else 0.0)
                fs, vs = K.ext(bm, sec, 'x', it['x'] - it['W'] / 2, it['x'] + it['W'] / 2, mi)
                K.rot_verts(vs, it['x'], yfront - Dd / 2, it['yaw'])
            if c['obi']:
                top = c['items'][-1]
                zt = top['z'] + top['t'] + 0.004
                fs, vs = K.ext(bm, K.chamfer_rect(c['obi_x'] - 0.03, c['obi_x'] + 0.03, zt - 0.006, zt + 0.004, 0.0), 'y',
                               yfront - top['D'] * 0.92, yfront + 0.006, obi, caps=(False, True), skip=(0,))
                K.rot_verts(vs, top['x'], yfront - top['D'] / 2, top['yaw'])
        for c in baskets:
            _basket(bm, c, yfront + 0.01, weave, wood, towel, lod)
    elif lod == 2:
        for c in stacks:
            it0, it1 = c['items'][0], c['items'][-1]
            Wd = max(i['W'] for i in c['items'])
            mi = yuk if c['kind'] == 'yukata' else towel
            ztop = it1['z'] + it1['t']
            K.box_open(bm, c['cx'] - Wd / 2, c['cx'] + Wd / 2, yfront - it0['D'], yfront, it0['z'], ztop, mi, sides='ftlr')
            if c['obi']:
                K.quad(bm, [(c['obi_x'] - 0.03, yfront - it1['D'] * 0.9, ztop + 0.003), (c['obi_x'] + 0.03, yfront - it1['D'] * 0.9, ztop + 0.003),
                            (c['obi_x'] + 0.03, yfront, ztop + 0.003), (c['obi_x'] - 0.03, yfront, ztop + 0.003)], obi, (0, 0, 1))
        for c in baskets:
            K.box_open(bm, c['cx'] - c['W'] / 2, c['cx'] + c['W'] / 2, yfront - c['D'], yfront + 0.01, c['z'], c['z'] + c['H'], weave, sides='ftlr')
    else:
        per_cell = len(stacks) * 2 + len(baskets) * 2
        if per_cell <= budget - C.tri_count(bm):
            for c in stacks + baskets:
                if c['kind'] == 'basket':
                    x0, x1, zt, mi = c['cx'] - c['W'] / 2, c['cx'] + c['W'] / 2, c['z'] + c['H'], weave
                else:
                    Wd = max(i['W'] for i in c['items'])
                    x0, x1, zt, mi = c['cx'] - Wd / 2, c['cx'] + Wd / 2, c['items'][-1]['z'] + c['items'][-1]['t'], (yuk if c['kind'] == 'yukata' else towel)
                K.quad(bm, [(x0, yfront, c['z']), (x1, yfront, c['z']), (x1, yfront, zt), (x0, yfront, zt)], mi, (0, 1, 0))
        else:
            print(f'[{ASSET}] LOD3: contents merged to one strip per row ({per_cell} > budget left)')
            for ri, (kind, zr, pr) in enumerate(L['rows']):
                mi = weave if kind == 'basket' else (yuk if L['style'] == 'yukata' else towel)
                K.quad(bm, [(xL + 0.03, yfront, zr), (xR - 0.03, yfront, zr), (xR - 0.03, yfront, zr + pr * 0.55), (xL + 0.03, yfront, zr + pr * 0.55)], mi, (0, 1, 0))

    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=False)   # back stays at -d/2 at every LOD
    o = _to_object(mb, ASSET)
    lights = [C.light_entry((x0 + bw / 2 + dx, yback + 0.05 + dy, (z0 + z1) / 2), color_k=LIGHT_K, watts=round(12 * (z1 - z0), 1),
                            kind='area', size=[round(bw, 3), round(z1 - z0, 3)], normal=[0, 1, 0]) for x0 in L['bays']]
    lights.append(C.light_entry((dx, yf - 0.04 + dy, tk - 0.003), color_k=LIGHT_K, watts=round(4 * W, 1), kind='strip',
                                p0=[round(xL + dx, 3), round(yf - 0.04 + dy, 3), round(tk - 0.003, 3)],
                                p1=[round(xR + dx, 3), round(yf - 0.04 + dy, 3), round(tk - 0.003, 3)], normal=[0, 0.3, -1]))
    C.set_json_props(o, kz_lights=lights,
                     kz_params=dict(w=round(W, 3), h=round(H, 3), d=round(D, 3), contents=L['style'], bays=L['nbays'],
                                    bay=round(bw, 3), rows=len(L['rows']), basket_rows=L['nb'], backlight=backlight,
                                    cornice=L['cornice'], kumiko=L['kumiko'], items=n_items))
    genlib.finish(o, smooth_angle=50)
    return o


def _basket(bm, c, yfr, weave, rim, cloth, lod):
    """woven basket: tapered chamfered-rect body, rolled rim band, inner floor high with folded cloth"""
    Wd, Dd, Hh = c['W'], c['D'], c['H']
    cx, cy, z = c['cx'], yfr - Dd / 2, c['z']
    ch = 0.03 if lod == 0 else 0.0

    def loop(w_, d_, zz, chf):
        return [(cx + u, cy + v, zz) for u, v in K.chamfer_rect(-w_ / 2, w_ / 2, -d_ / 2, d_ / 2, chf)]
    if lod == 0:
        loops = [loop(Wd * 0.9, Dd * 0.9, z, ch * 0.8), loop(Wd, Dd, z + Hh - 0.025, ch), loop(Wd + 0.008, Dd + 0.008, z + Hh - 0.022, ch),
                 loop(Wd + 0.008, Dd + 0.008, z + Hh, ch), loop(Wd - 0.02, Dd - 0.02, z + Hh, ch * 0.7),
                 loop(Wd - 0.03, Dd - 0.03, z + Hh - 0.05, ch * 0.6)]
        mis = [weave, weave, rim, rim, weave, cloth]
        K.loft(bm, loops, weave, mis=mis)
        if c['peek']:                 # a folded towel peeking over the rim
            sec = K.stadium(cy + Dd * 0.3, cy - Dd * 0.3, z + Hh - 0.05, 0.07, 3, puff=0.006)
            K.ext(bm, sec, 'x', cx - Wd * 0.36, cx + Wd * 0.36, cloth)
    else:
        loops = [loop(Wd * 0.9, Dd * 0.9, z, 0.0), loop(Wd, Dd, z + Hh, 0.0), loop(Wd - 0.03, Dd - 0.03, z + Hh - 0.05, 0.0)]
        K.loft(bm, loops, weave, mis=[weave, weave, cloth])
