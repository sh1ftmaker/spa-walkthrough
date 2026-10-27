"""Potted bonsai pine: a small pine in a low glazed pot on a lacquer stand, a glazed pot on the floor, or a
hinoki planter box on the kerb.

Identifying features kept at every LOD: a small S-curved pine with flat cloud pads, in a low pot / box,
(stand style) raised on a dark lacquer table.
Concept: refs/gen/sheet-vs-nature-2.png #1 "Potted bonsai" (W 0.9 x D 0.9 x H 1.2 m label; 307 px/m bar):
drawn h 1.04 (label 1.2: built to the label), canopy 0.81 w; stand 0.60 w x 0.24 h, dark lacquer, 4 square
legs on a floor frame, apron under the top; pot 0.48 w x 0.18 h, dark bronze-black glaze, oval, rolled rim,
small feet; moss mound + exposed nebari roots on the soil; trunk ~0.08 m, a twisting S-curve; 4-5 pads,
the lowest ones widest, crown pad on top.  Lookbook 05 left: a small tree in a hinoki planter box on the
kerb; lookbook 04: small pines on planters by the pools.

Targets (built at default h = proxy 1.08-1.2 m):
  stand style  : stand 0.60 x 0.44 x 0.24 m; oval pot 0.48 x 0.36 x 0.17 m (tenmoku); tree 0.75-0.85 m
  planter_box  : hinoki box 0.62 x 0.62 x 0.36 m (rim cap, corner posts, feet); tree 0.7-0.8 m
  ceramic      : round celadon / tenmoku pot 0.52 dia x 0.30 m on the floor; tree 0.75-0.85 m
  trunk base r 0.04-0.05 m with 4 nebari roots; limbs 0.15-0.32 m; pads R 0.13-0.26, T 0.35-0.45 R;
  canopy w 0.7-0.88 m.
Parameters: h 0.6-1.8, pot_style ceramic | planter_box | stand (cycles 1 stand, 2 planter_box, 3 ceramic,
  4 stand), pads 2-5 (seeds 4, 3, 5, 2 ...), moss_top on/off (off on seed 3 -> black soil).
Seeds change: pot style, pad count / sides / sizes, trunk S-curve phase and lean, height, glaze.

Materials: needles `foliage_pine` (alpha cards), pad cores `moss` darkened, trunk/limbs `bark`, stand
  `lacquer_dark` (top) + `lacquer_black` (legs/frame), pots `ceramic` tenmoku / celadon, box `hinoki`
  wet_oiled, soil `black_sand`, moss top `moss`.
LOD: one layout.  LOD1 no bevels, lathe 14, 7-sided trunk, fewer bigger cards; LOD2 lathe 8, 5-seg lens pads
  + a few cards; LOD3 stand box + 6-seg pot band + 3-sided trunk + one hull blob per pad (<= 80 tris).
Animation: none (indoor potted plant).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_groundcover as P

ASSET = 'bonsai_potted'
FEATURES = ['small S-curved pine with cloud pads', 'low glazed pot or hinoki box', 'dark lacquer stand']
STYLES = ['stand', 'planter_box', 'ceramic']
PADS_BY_SEED = [4, 3, 5, 2, 4, 5]


def base_dims(style, k):
    if style == 'stand':
        return dict(stand=(0.60 * k, 0.44 * k, 0.24 * k), pot=(0.48 * k, 0.36 * k, 0.17 * k))
    if style == 'planter_box':
        return dict(box=(0.62 * k, 0.62 * k, 0.36 * k))
    return dict(pot=(0.52 * k, 0.52 * k, 0.30 * k))


def tree_layout(seed, Ht, pads, k):
    g = C.rng(seed, 'tree')
    S = Ht / 0.8
    phase = g.uniform(0, 2 * math.pi)
    side = g.choice([-1, 1])
    lean = g.uniform(-0.06, 0.06) * S
    A = g.uniform(0.07, 0.11) * S
    trunk = []
    Htr = Ht * 0.80
    for i in range(25):
        t = i / 24
        x = A * math.sin(2 * math.pi * t * 1.1 + phase) * min(1, t * 3) + lean * t
        y = A * 0.4 * math.sin(2 * math.pi * t * 0.8 + phase * 1.3) * t
        trunk.append(Vector((x, y, Htr * t)))
    trunk = [q - Vector((trunk[0].x, trunk[0].y, 0)) for q in trunk]
    pr = C.rng(seed, 'pads')
    P_ = [dict(c=trunk[-1] + Vector((0, 0, 0.02)), R=pr.uniform(0.15, 0.19) * S, path=None, t=1.0, ph=pr.random())]
    order = [(0.38, 1, 0.23), (0.55, -1, 0.2), (0.68, 1, 0.16), (0.5, 0, 0.14)]   # (height t, side, limb length)
    for j in range(pads - 1):
        t, sd, ln = order[j]
        if sd == 0:
            d = Vector((pr.uniform(-0.4, 0.4), -1, 0)).normalized()     # back pad, for depth
        else:
            d = Vector((sd * side, pr.uniform(-0.45, 0.45), 0)).normalized()
        ln = ln * S * pr.uniform(0.9, 1.1)
        p0 = _at(trunk, t)
        rise = pr.uniform(0.04, 0.09) * S
        q = Vector((-d.y, d.x, 0)) * ln * 0.15 * pr.choice([-1, 1])
        path = [p0, p0 + d * ln * 0.45 + q + Vector((0, 0, rise * 0.3)), p0 + d * ln + Vector((0, 0, rise))]
        R = (0.21 - 0.04 * j) * S * pr.uniform(0.9, 1.05) if j < 3 else 0.15 * S      # canopy ~0.8 m: no xy squash
        P_.append(dict(c=path[-1] + Vector((0, 0, 0.01)), R=R, path=path, t=t, ph=pr.random()))
    # fit the canopy (not the pot) into the proxy footprint: scale limb reach and pad size together
    lim = 0.86 * max(0.75, k)
    for _ in range(4):
        ex = [(q['c'].x - q['R'] * 1.5 - 0.04, q['c'].x + q['R'] * 1.5 + 0.04, q['c'].y - q['R'] * 1.3 - 0.04,
               q['c'].y + q['R'] * 1.3 + 0.04) for q in P_]
        wx = max(e[1] for e in ex) - min(e[0] for e in ex); wy = max(e[3] for e in ex) - min(e[2] for e in ex)
        f = min(1.0, lim / wx, lim / wy)
        if f >= 0.995:
            break
        sc = lambda v: Vector((v.x * f, v.y * f, v.z))
        trunk = [sc(v) for v in trunk]
        for q in P_:
            q['c'] = sc(q['c']); q['R'] *= f
            if q['path']:
                q['path'] = [sc(v) for v in q['path']]
    roots = []
    for j in range(4):
        a = 2 * math.pi * (j + g.uniform(-0.2, 0.2)) / 4 + phase
        dd = Vector((math.cos(a), math.sin(a), 0))
        roots.append([dd * 0.02 * S + Vector((0, 0, 0.05 * S)), dd * 0.07 * S + Vector((0, 0, 0.015 * S)),
                      dd * 0.12 * S + Vector((0, 0, -0.005))])
    return dict(trunk=trunk, pads=P_, roots=roots, S=S, r0=g.uniform(0.04, 0.05) * S, off=Vector((phase, phase * 2, 3)))


def _at(path, t):
    f = t * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    return path[i].lerp(path[i + 1], f - i)


def build(lod, seed, h=None, pot_style=None, pads=None, moss_top=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    h = h or p['h'] * g.uniform(0.9, 1.0)
    style = pot_style or C.cycle(seed, STYLES)
    pads = max(2, min(5, int(pads or PADS_BY_SEED[(seed - 1) % len(PADS_BY_SEED)])))
    moss_top = (seed % 3 != 0) if moss_top is None else moss_top
    k = max(0.6, min(1.4, h / 1.2))
    glaze = C.pick(seed, 'glaze', ['tenmoku', 'tenmoku', 'celadon']) if style == 'ceramic' else 'tenmoku'

    mb = genlib.MeshBuilder()
    needles = mb.slot('foliage_pine')
    core = mb.slot('moss', tint=(0.45, 0.55, 0.32))
    bark = mb.slot('bark', tint=(0.55, 0.5, 0.45))
    top_m = mb.slot('lacquer_dark')
    leg_m = mb.slot('lacquer_black')
    pot_m = mb.slot('ceramic', variant=glaze)
    box_m = mb.slot('hinoki', variant='wet_oiled')
    soil_m = mb.slot('black_sand', roughness_offset=0.3)
    moss_m = mb.slot('moss')
    bm = mb.bm
    D = base_dims(style, k)
    z = 0.0

    # ------------------------------------------------ stand (lacquer table: top, apron, legs, floor frame)
    if style == 'stand':
        W, Dp, Hs = D['stand']
        tt = 0.035 * k
        if lod == 3:
            mb.box((0, 0, Hs / 2), (W, Dp, Hs), leg_m)
        else:
            if lod == 0:
                C.board(mb, (0, 0, Hs - tt / 2), (W, Dp, tt), top_m, bevel=0.008)
            else:
                mb.box((0, 0, Hs - tt / 2), (W, Dp, tt), top_m)
            lw = 0.045 * k
            for sx in (-1, 1):
                for sy in (-1, 1):
                    c = (sx * (W / 2 - 0.04 * k), sy * (Dp / 2 - 0.04 * k), (Hs - tt) / 2)
                    if lod == 0:
                        C.chamfered_bar(mb, c, (lw, lw, Hs - tt), leg_m, ch=0.006)
                    else:
                        mb.box(c, (lw, lw, Hs - tt), leg_m)
            if lod < 2:
                ah, fh = 0.045 * k, 0.03 * k
                for sy in (-1, 1):       # apron + floor frame, long sides
                    mb.box((0, sy * (Dp / 2 - 0.04 * k), Hs - tt - ah / 2), (W - 0.1 * k, 0.02 * k, ah), leg_m)
                    mb.box((0, sy * (Dp / 2 - 0.04 * k), fh / 2), (W - 0.04 * k, lw, fh), leg_m)
                for sx in (-1, 1):       # short sides
                    mb.box((sx * (W / 2 - 0.04 * k), 0, Hs - tt - ah / 2), (0.02 * k, Dp - 0.1 * k, ah), leg_m)
                    mb.box((sx * (W / 2 - 0.04 * k), 0, fh / 2), (lw, Dp - 0.04 * k, fh), leg_m)
        z = Hs

    # ------------------------------------------------ pot (oval or round lathe) or hinoki box
    if 'pot' in D:
        PW, PD, PH = D['pot']
        R = PW / 2
        ell = PD / PW
        segs = C.lod_pick(lod, 28, 14, 8, 6)
        if style == 'stand':       # low oval bonsai pot: foot, near-vertical wall, rolled rim
            prof = [(R * 0.86, 0.0), (R * 0.9, PH * 0.12), (R * 0.97, PH * 0.55), (R, PH * 0.88), (R * 1.04, PH * 0.95),
                    (R * 1.03, PH), (R * 0.95, PH), (R * 0.93, PH * 0.86)]
        else:                      # rounder floor pot: bellied, rolled rim
            prof = [(R * 0.7, 0.0), (R * 0.88, PH * 0.2), (R * 0.99, PH * 0.55), (R * 0.96, PH * 0.86), (R * 1.03, PH * 0.94),
                    (R * 1.02, PH), (R * 0.92, PH), (R * 0.9, PH * 0.9)]
        if lod == 1:
            prof = [prof[i] for i in (0, 2, 3, 4, 6, 7)]
        elif lod >= 2:
            prof = [prof[0], prof[3], prof[5], prof[6]] if lod == 2 else [prof[0], prof[5]]
        foot = 0.018 * k if lod < 2 else 0.0
        vs, fs = C.lathe(mb, prof + ([(0.0, prof[-1][1] - 0.012)] if lod < 3 else [(0.0, PH)]), segs, pot_m, base=(0, 0, z + foot))
        for v in vs:
            v.co.y *= ell
        if lod < 2:                # 4 small cloud feet
            for a in (0.6, 2.54, 3.74, 5.68):
                mb.box((math.cos(a) * R * 0.72, math.sin(a) * R * 0.72 * ell, z + foot / 2), (0.05 * k, 0.04 * k, foot), pot_m)
        soil_z = z + foot + PH * 0.86
        top = z + foot + PH
        inner = (R * 0.93, R * 0.93 * ell)
    else:
        BW, BD, BH = D['box']
        t = 0.03 * k
        if lod == 3:
            mb.box((0, 0, BH / 2), (BW, BD, BH), box_m)
        else:
            foot = 0.04 * k
            for sx in (-1, 1):
                if lod == 0:
                    C.board(mb, (0, sx * (BD / 2 - t / 2), foot + (BH - foot) / 2), (BW - 2 * t, t, BH - foot), box_m, bevel=0.004)
                else:
                    mb.box((0, sx * (BD / 2 - t / 2), foot + (BH - foot) / 2), (BW - 2 * t, t, BH - foot), box_m)
                mb.box((sx * (BW / 2 - t / 2), 0, foot + (BH - foot) / 2), (t, BD - 2 * t, BH - foot), box_m)
            if lod < 2:
                cap = 0.022 * k
                for sx in (-1, 1):   # rim cap boards
                    mb.box((0, sx * (BD / 2 - t / 2), BH + cap / 2), (BW + 0.02 * k, t + 0.016 * k, cap), box_m)
                    mb.box((sx * (BW / 2 - t / 2), 0, BH + cap / 2), (t + 0.016 * k, BD - 2 * t, cap), box_m)
                for sx in (-1, 1):   # corner posts doubling as feet
                    for sy in (-1, 1):
                        mb.box((sx * (BW / 2 - 0.02 * k), sy * (BD / 2 - 0.02 * k), BH / 2), (0.05 * k, 0.05 * k, BH), leg_m)
        soil_z = BH - 0.03 * k
        top = BH
        inner = (BW / 2 - t, BD / 2 - t)
    if lod < 3:                    # soil disc / plane
        if 'pot' in D:
            ring = [bm.verts.new((inner[0] * math.cos(2 * math.pi * i / segs), inner[1] * math.sin(2 * math.pi * i / segs), soil_z))
                    for i in range(segs)]
        else:
            ring = [bm.verts.new((x * inner[0], y * inner[1], soil_z)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        f = bm.faces.new(ring); f.material_index = soil_m
    if moss_top and lod < 3:
        from gen_groundcover import cushion
        pl0 = P.Plant(mb)
        cushion(pl0, (0.02, 0.0, soil_z), inner[0] * 0.75, inner[1] * 0.75, 0.035 * k, moss_m, C.rng(seed, 'moss'),
                C.lod_pick(lod, 12, 8, 6), C.lod_pick(lod, 2, 1, 1))

    # ------------------------------------------------ tree
    Ht = h - soil_z
    T = tree_layout(seed, Ht, pads, k)
    base = Vector((0, 0, soil_z))
    trunk = [base + q for q in T['trunk']]
    S = T['S']
    nr = C.lod_pick(lod, 14, 8, 4, 2)
    ts = [i / nr for i in range(nr + 1)]
    pts = [_at(trunk, t) for t in ts]
    rad = [T['r0'] * (1 - 0.6 * t) for t in ts]
    off = T['off']

    def tmod(i, kk, th):
        t = ts[i]
        flare = 1.0 + 0.9 * math.exp(-t / 0.06)
        ridge = 1.0 + (0.08 * math.cos(4 * th + 3 * t) + 0.05 * noise.noise(Vector((math.cos(th), math.sin(th), t * 6)) + off)) if lod == 0 else 1.0
        return flare * ridge
    C.tube(mb, pts, rad, bark, sides=C.lod_pick(lod, 10, 7, 5, 3), cap1=True, mod=tmod)
    if lod == 0:
        for path in T['roots']:
            C.tube(mb, [base + q for q in path], [0.018 * S, 0.012 * S, 0.006], bark, sides=5)
    for P_ in T['pads']:
        if P_['path'] and lod < 3:
            path = [base + q for q in P_['path']]
            r0 = T['r0'] * (1 - 0.6 * P_['t']) * 0.6
            n = C.lod_pick(lod, 4, 3, 1)
            lp = [_at(path, i / n) for i in range(n + 1)]
            C.tube(mb, lp, [r0 * (1 - 0.6 * i / n) for i in range(n + 1)], bark, sides=C.lod_pick(lod, 6, 4, 3), cap1=True)
        elif P_['path'] and lod == 3 and P_['R'] > 0.18 * S:
            path = [base + q for q in P_['path']]
            C.tube(mb, [path[0], path[-1]], [0.02 * S, 0.012 * S], bark, sides=3)

    # pads: cores + needle cards from what the budget leaves
    budget = (genlib.budget_of(ASSET) or [2500, 1000, 300, 80])[lod]
    pads_l = T['pads']
    if lod == 3:
        for j, P_ in enumerate(pads_l):
            c = base + P_['c']
            C.hull_rock(mb, (c.x, c.y, c.z + P_['R'] * 0.22), (P_['R'] * 1.15, P_['R'] * 1.0, P_['R'] * 0.45), core,
                        C.rng(seed, f'l3{j}'), npts=5)
    else:
        segs_p, rings_p = C.lod_pick(lod, (10, 1), (8, 1), (5, 0))
        core_cost = len(pads_l) * 2 * segs_p * (rings_p + 2)
        n_cards = max(0, int((budget * 0.97 - C.tri_count(bm) - core_cost) / 2))
        csz = C.lod_pick(lod, 1.0, 1.4, 1.8)
        areas = [q['R'] ** 2 for q in pads_l]
        for j, P_ in enumerate(pads_l):
            nc = int(n_cards * areas[j] / sum(areas))
            r = C.rng(seed, f'pad{j}')
            C.foliage_pad(mb, base + P_['c'], P_['R'], P_['R'] * r.uniform(0.36, 0.45), core, needles, r, n_cards=nc,
                          segs=segs_p, rings=rings_p, lobes=r.choice([4, 5, 6]), flat=r.uniform(1.0, 1.2),
                          card_w=(0.11 * S * csz, 0.17 * S * csz), card_h=(0.08 * S * csz, 0.12 * S * csz), side_band=0.3)

    kf = P.fit_xy(mb, p['w'] * 0.98, p['d'] * 0.98)
    if kf < 0.97:
        print(f'[{ASSET}] s{seed} L{lod}: footprint squeezed x{kf:.2f} to fit the proxy')
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=50)
    P.post(o, soft_slots=(needles, core, moss_m), sway=False)
    C.set_json_props(o, kz_params=dict(h=round(h, 3), pot_style=style, pads=pads, moss_top=moss_top, glaze=glaze))
    return o
