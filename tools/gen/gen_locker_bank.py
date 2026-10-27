"""Locker bank with crest doors: a run of tall hinoki locker doors in 1-3 tiers, each door with a small bronze
Kazan-yu crest roundel and a basalt-token lock, grouped in modules by dark lacquer stiles, under a dark
cornice, on a basalt plinth lit from a recessed strip.

Identifying features kept at every LOD: the grid of tall hinoki doors (seams visible), a crest on each
door (LOD3: one per module and tier), the lock tokens (to LOD2), the lit plinth.

Targets (refs/gen/sheet-ref-ground.png panel 01, right half: the locker wall between the noren; and
dh-changing-treatment.png "lockers"; scale from the bench seat 0.45 m and noren 2.0 m door heads):
  * doors 0.42-0.56 m wide (row 0.4-0.6), 2 tiers in the concept (upper ~0.95 m, lower ~0.75 m),
    22 mm flush plank doors with 4 mm seams, vertical grain;
  * crest: bronze roundel ~70 mm across at ~85 % of the door height (mountain relief in a raised ring);
    lock: a ~35 x 50 mm basalt token with a bronze keyhole on the latch side at mid-height of the door;
  * cornice 0.10-0.12 m, plinth 0.10-0.12 m set back 40 mm with a light strip under the carcass;
  * overall: row typical 6 x 0.6 x 2.0 m = proxy (3d/assets.json). Range w 1-24 m, h 1.8-2.4 m.

Parameters: w, h, d, door_w (0.4-0.6), tiers (1-3), plinth_light (bool), module (doors per module 2-5).
Seeds: 1 = 6.0 m, 2 tiers, 0.48 m doors, 4-door modules; 2 = 3.6 m, 3 tiers of 0.42 m doors (small
lockers), stepped cornice; 3 = 4.8 m, 1 tier of tall 0.56 m doors. Seeds > 3 sample the ranges. Door
hinge side alternates in pairs; crest height and token height jitter a few cm per seed.

Materials: hinoki wet_oiled (doors, carcass), hinoki dark_timber (module stiles, cornice: lacquer_dark's
mottle read as speckled granite at this size), lacquer_dark (back plane behind the seams), lacquer_black (crest
relief), basalt_dry
cooled tint (plinth), bronze smooth (crest roundels, keyholes), basalt_dry (tokens), washi_backlit (plinth
light strip). Lights: obj['kz_lights'] strip along the plinth. Lightmap. No animation. Wall-snapped:
back at y = -d/2, front +Y.
"""
import json
import math

import bpy

import genlib
import kzgeo_common as C
import kzgeo_locker_bank as K

ASSET = 'locker_bank'
FEATURES = ['tall hinoki locker doors in tiers', 'small crest on each door', 'basalt-token lock', 'lit plinth']
PARAMS = dict(w=(1.0, 24.0), h=(1.8, 2.4), door_w=(0.4, 0.6), tiers=(1, 3), plinth_light=(True, False), module=(2, 5))
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


def _layout(seed, w, h, d, door_w, tiers, module):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'layout')
    preset = {1: (p['w'], 2, 0.48, 4), 2: (3.6, 3, 0.42, 4), 3: (4.8, 1, 0.56, 3)}.get(seed)
    if preset is None:
        preset = (g.choice([2.4, 3.6, 4.8, 6.0]), g.choice([1, 2, 2, 3]), g.uniform(0.42, 0.56), g.choice([3, 4, 5]))
    w = min(max(w or preset[0], 1.0), 24.0)
    h = min(max(h or p['h'], 1.8), 2.4)
    d = d or p['d']
    tiers = tiers or preset[1]
    door_w = door_w or preset[2]
    module = module or preset[3]
    L = dict(w=w, h=h, d=d, tiers=tiers)
    L['es'], L['ms'] = 0.045, 0.05                       # end panels, module stiles
    L['pl'] = g.uniform(0.10, 0.12)                       # plinth
    L['cornice'] = 'stepped' if seed % 2 == 0 else 'slab'
    L['ch'] = 0.12 if L['cornice'] == 'stepped' else 0.10
    L['yb'], L['yf'] = -d / 2, d / 2 - 0.025
    inner = w - 2 * L['es']
    # columns grouped in modules: solve column count for the target door width
    gap = 0.004
    best = None
    for M in range(1, 40):
        n = max(1, round((inner - (M - 1) * L['ms']) / door_w))
        per = n / M
        if abs(per - module) <= 1 or M == 1:
            dw = (inner - (M - 1) * L['ms']) / n
            score = abs(dw - door_w) + 0.05 * abs(per - module)
            if n % M == 0 and (best is None or score < best[0]):
                best = (score, M, n, dw)
    _, M, n, dw = best
    L['M'], L['ncols'], L['dw'] = M, n, dw
    per = n // M
    cols = []
    x = -w / 2 + L['es']
    for m in range(M):
        for k in range(per):
            cols.append((m, x, x + dw))
            x += dw
        x += L['ms']
    L['cols'] = cols
    L['mods'] = [(cols[m * per][1], cols[m * per + per - 1][2]) for m in range(M)]
    z0, z1 = L['pl'], h - L['ch']
    if tiers == 1:
        tz = [z0, z1]
    elif tiers == 2:
        zs = z0 + (z1 - z0) * 0.44
        tz = [z0, zs, z1]
    else:
        tz = [z0 + (z1 - z0) * k / 3 for k in range(4)]
    L['tz'] = tz
    L['gap'] = gap
    gc = C.rng(seed, 'crest')
    L['crest_f'] = gc.uniform(0.80, 0.88)                 # crest centre height as a fraction of the door
    L['tok_f'] = gc.uniform(0.48, 0.56)
    return L


def build(lod, seed, w=None, h=None, d=None, door_w=None, tiers=None, plinth_light=True, module=None, **_):
    L = _layout(seed, w, h, d, door_w, tiers, module)
    budget = (genlib.budget_of(ASSET) or [4000, 1600, 480, 60])[lod]
    mb = genlib.MeshBuilder()
    bm = mb.bm
    wood = mb.slot('hinoki', variant='wet_oiled', wear=0.12)
    lac = mb.slot('hinoki', variant='dark_timber')        # cornice, module stiles (lacquer_dark's mottle read as speckled granite here)
    seam = mb.slot('lacquer_dark')                        # dark back plane seen through the door seams
    ink = mb.slot('lacquer_black')                        # crest relief on the bronze plate
    plinth = mb.slot('basalt_dry', tint=(0.5, 0.5, 0.55))
    token = mb.slot('basalt_dry', tint=(0.42, 0.42, 0.46), roughness_offset=-0.25)
    brz = mb.slot('bronze', variant='smooth')
    glow = mb.slot('washi_backlit', emissive_level=1.4) if plinth_light else lac
    W, H, D = L['w'], L['h'], L['d']
    yb, yf, es, ms, pl, ch = L['yb'], L['yf'], L['es'], L['ms'], L['pl'], L['ch']
    tz, gap = L['tz'], L['gap']
    xL, xR = -W / 2 + es, W / 2 - es
    z1 = H - ch
    doors = []                                            # (col index, x0, x1, za, zb)
    for ci, (m, x0, x1) in enumerate(L['cols']):
        for ti in range(len(tz) - 1):
            doors.append((ci, x0 + gap / 2, x1 - gap / 2, tz[ti] + gap / 2, tz[ti + 1] - gap / 2))
    yd = yf                                               # door back plane

    def crest_pos(dr):
        ci, x0, x1, za, zb = dr
        return ((x0 + x1) / 2, za + (zb - za) * L['crest_f'] if L['tiers'] < 3 else za + (zb - za) * 0.74)

    def token_pos(dr):
        ci, x0, x1, za, zb = dr
        latch = 1 if ci % 2 == 0 else -1                  # hinges alternate: latch sides of neighbours face each other
        return ((x1 - 0.05) if latch > 0 else (x0 + 0.05), za + (zb - za) * L['tok_f'] if L['tiers'] < 3 else za + (zb - za) * 0.45)

    # ------------------------------------------------------------------ carcass
    if lod <= 1:
        c = 0.005 if lod == 0 else 0.0
        for sx in (-1, 1):                                # end panels, plinth to cornice
            a, b = sorted((sx * W / 2, sx * (W / 2 - es)))
            K.ext(bm, K.chamfer_rect(a, b, yb, yf + 0.024, c), 'z', pl - 0.01, z1, wood, caps=(True, False))
        K.quad(bm, [(xL, yd - 0.004, pl), (xR, yd - 0.004, pl), (xR, yd - 0.004, z1), (xL, yd - 0.004, z1)], seam, (0, 1, 0))   # dark seams
        for m in range(L['M'] - 1):                       # module stiles, lacquer, proud
            a = L['mods'][m][1]
            K.ext(bm, K.chamfer_rect(a, a + ms, yb, yf + 0.03, c), 'z', pl - 0.01, z1, lac, caps=(True, False), skip=(0,))
        # tier rails between tiers (thin lacquer line behind the seams)
        # cornice
        zc = z1
        if L['cornice'] == 'stepped' and lod == 0:
            sec = [(yb, zc), (yf + 0.03, zc), (yf + 0.03, zc + 0.07), (D / 2, zc + 0.07), (D / 2, H), (yb, H)]
        else:
            sec = [(yb, zc), (D / 2, zc), (D / 2, H), (yb, H)]
        K.ext(bm, sec, 'x', -W / 2, W / 2, lac, skip=(len(sec) - 1,))
        if L['cornice'] == 'stepped' and lod == 0:        # hinoki cap board on the stepped cornice
            K.ext(bm, [(yb, H - 0.02), (D / 2 + 0.012, H - 0.02), (D / 2 + 0.012, H), (yb, H)], 'x', -W / 2 - 0.012, W / 2 + 0.012, wood, skip=(3,))
        # plinth: basalt block set back 40 mm, light strip under the carcass
        yp = yf - 0.04
        K.ext(bm, [(yb, 0.0), (yp, 0.0), (yp, pl - 0.01), (yb, pl - 0.01)], 'x', -W / 2 + 0.01, W / 2 - 0.01, plinth, skip=(3, 0))
        K.quad(bm, [(xL - es, yp, pl - 0.01), (xR + es, yp, pl - 0.01), (xR + es, yf + 0.024, pl - 0.01), (xL - es, yf + 0.024, pl - 0.01)], lac, (0, 0, -1))
        if plinth_light:
            K.quad(bm, [(xL, yp + 0.012, pl - 0.012), (xR, yp + 0.012, pl - 0.012), (xR, yp + 0.035, pl - 0.012), (xL, yp + 0.035, pl - 0.012)], glow, (0, 0, -1))
    elif lod == 2:
        for sx in (-1, 1):
            a, b = sorted((sx * W / 2, sx * (W / 2 - es)))
            K.box_open(bm, a, b, yb, yf + 0.024, pl - 0.01, z1, wood, sides='flr')
        K.quad(bm, [(xL, yd - 0.004, pl), (xR, yd - 0.004, pl), (xR, yd - 0.004, z1), (xL, yd - 0.004, z1)], lac, (0, 1, 0))
        for m in range(L['M'] - 1):
            a = L['mods'][m][1]
            K.quad(bm, [(a, yf + 0.03, pl), (a + ms, yf + 0.03, pl), (a + ms, yf + 0.03, z1), (a, yf + 0.03, z1)], lac, (0, 1, 0))
        K.box_open(bm, -W / 2, W / 2, yb, D / 2, z1, H, lac, sides='fbt')
        K.box_open(bm, -W / 2 + 0.01, W / 2 - 0.01, yb, yf - 0.04, 0.0, pl - 0.01, plinth, sides='flr')
        K.quad(bm, [(xL, yf - 0.04, pl - 0.01), (xR, yf - 0.04, pl - 0.01), (xR, yf + 0.024, pl - 0.01), (xL, yf + 0.024, pl - 0.01)], glow, (0, 0.3, -1))
    else:
        K.box_open(bm, -W / 2, W / 2, yb, D / 2, z1, H, lac, sides='ft')      # cornice front + top (keeps the depth)
        K.quad(bm, [(-W / 2, yf + 0.02, pl), (W / 2, yf + 0.02, pl), (W / 2, yf + 0.02, z1), (-W / 2, yf + 0.02, z1)], wood, (0, 1, 0))
        K.quad(bm, [(-W / 2, yf - 0.04, 0), (W / 2, yf - 0.04, 0), (W / 2, yf - 0.04, pl), (-W / 2, yf - 0.04, pl)], plinth, (0, 1, 0))
        K.quad(bm, [(-W / 2, yf - 0.04, pl - 0.01), (W / 2, yf - 0.04, pl - 0.01), (W / 2, yf + 0.02, pl - 0.01), (-W / 2, yf + 0.02, pl - 0.01)], glow, (0, 0.3, -1))

    # ------------------------------------------------------------------ doors, crests, tokens
    left = budget - C.tri_count(bm)
    mtn_hi = [(x, y) for x, y in K.mountain(lo=False)]
    mtn_lo = [(x, y) for x, y in K.mountain(lo=True)]
    if lod <= 1:
        # tiers of detail per door (tris): (door bevel, roundel sides, mountain, token rounded)
        peak4 = [(-0.5, 0.0), (0.5, 0.0), (0.05, 0.4), (-0.05, 0.4)]
        tiers_ = [(True, 16, mtn_hi, 2), (True, 12, mtn_lo, 1), (True, 10, peak4, 0), (False, 10, peak4, 0), (False, 8, None, 0)] if lod == 0 else \
                 [(False, 10, mtn_lo, 0), (False, 8, peak4, 0), (False, 6, None, 0)]

        def cost(t):   # ext of n points with one cap = 3n - 2 tris
            bev, n, mt, tr = t
            return (44 if bev else 6) + (3 * n - 2) + ((3 * len(mt) - 2) if mt else 0) + (3 * 4 * (tr + 1) - 2) + 2
        tier = tiers_[-1]
        for t in tiers_:
            if cost(t) * len(doors) <= left:
                tier = t
                break
        if tier is not tiers_[0]:
            print(f'[{ASSET}] LOD{lod}: door detail reduced to {tier[:2]} for {len(doors)} doors (budget {budget})')
        bev, nseg, mt, tr = tier
        for dr in doors:
            ci, x0, x1, za, zb = dr
            if bev:
                C.board(mb, ((x0 + x1) / 2, yd + 0.011, (za + zb) / 2), (x1 - x0, 0.022, zb - za), wood, bevel=0.003)
            else:
                K.box_open(bm, x0, x1, yd, yd + 0.022, za, zb, wood, sides='flr')
            yfr = yd + 0.022
            cx, cz = crest_pos(dr)
            rr = 0.035 if L['dw'] > 0.44 else 0.03
            circ = [(cx + rr * math.cos(2 * math.pi * k / nseg), cz + rr * math.sin(2 * math.pi * k / nseg)) for k in range(nseg)]
            K.ext(bm, circ, 'y', yfr - 0.001, yfr + 0.004, brz, caps=(False, True))
            if mt:
                s = rr * 1.05
                poly = [(cx - x * s, cz - rr * 0.36 + y * s * 1.05) for x, y in mt]      # read from the front: x -> -X
                K.ext(bm, poly[::-1], 'y', yfr + 0.004, yfr + 0.0065, ink, caps=(False, True))
            tx, tz_ = token_pos(dr)
            if tr:
                poly = [(tx + u, tz_ + v) for u, v in C.rounded_rect(0.034, 0.05, 0.008, tr)]
            else:
                poly = [(tx - 0.017, tz_ - 0.025), (tx + 0.017, tz_ - 0.025), (tx + 0.017, tz_ + 0.025), (tx - 0.017, tz_ + 0.025)]
            K.ext(bm, poly, 'y', yfr - 0.001, yfr + 0.009, token, caps=(False, True))
            K.quad(bm, [(tx - 0.003, yfr + 0.0095, tz_ - 0.012), (tx + 0.003, yfr + 0.0095, tz_ - 0.012), (tx + 0.003, yfr + 0.0095, tz_ + 0.006),
                        (tx - 0.003, yfr + 0.0095, tz_ + 0.006)], brz, (0, 1, 0))
    elif lod == 2:
        for dr in doors:
            ci, x0, x1, za, zb = dr
            K.quad(bm, [(x0, yd + 0.02, za), (x1, yd + 0.02, za), (x1, yd + 0.02, zb), (x0, yd + 0.02, zb)], wood, (0, 1, 0))
            cx, cz = crest_pos(dr)
            r_ = 0.04
            K.quad(bm, [(cx - r_, yd + 0.024, cz - r_), (cx + r_, yd + 0.024, cz - r_), (cx + r_, yd + 0.024, cz + r_), (cx - r_, yd + 0.024, cz + r_)], brz, (0, 1, 0))
            tx, tz_ = token_pos(dr)
            K.quad(bm, [(tx - 0.018, yd + 0.024, tz_ - 0.026), (tx + 0.018, yd + 0.024, tz_ - 0.026), (tx + 0.018, yd + 0.024, tz_ + 0.026),
                        (tx - 0.018, yd + 0.024, tz_ + 0.026)], token, (0, 1, 0))
    else:
        # seams (one dark line per column boundary and per tier boundary), module stiles, crests per module x tier
        yl = yf + 0.025
        quads = []
        for ci in range(1, L['ncols']):
            x = L['cols'][ci][1]
            if L['cols'][ci][0] != L['cols'][ci - 1][0]:
                quads.append(((x - ms - 0.002, pl), (x + 0.002, z1), lac))
            else:
                quads.append(((x - 0.006, pl), (x + 0.006, z1), lac))
        for tzz in tz[1:-1]:
            quads.append(((-W / 2, tzz - 0.006), (W / 2, tzz + 0.006), lac))
        for (a, b) in L['mods']:
            for ti in range(len(tz) - 1):
                za, zb = tz[ti], tz[ti + 1]
                cz = za + (zb - za) * (L['crest_f'] if L['tiers'] < 3 else 0.74)
                quads.append((((a + b) / 2 - 0.05, cz - 0.05), ((a + b) / 2 + 0.05, cz + 0.05), brz))
        room = (budget - C.tri_count(bm)) // 2
        if len(quads) > room:
            print(f'[{ASSET}] LOD3: {len(quads)} detail quads > room {room}; keeping module stiles, tier lines and crests')
            quads = [q for q in quads if q[2] == brz or (q[1][0] - q[0][0]) > 0.02 or (q[1][1] - q[0][1]) < 0.02][:room]
        for (x0, za), (x1, zb), mi in quads:
            K.quad(bm, [(x0, yl, za), (x1, yl, za), (x1, yl, zb), (x0, yl, zb)], mi, (0, 1, 0))

    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=False)   # back stays at -d/2 at every LOD
    o = _to_object(mb, ASSET)
    lights = []
    if plinth_light:
        y_ = yf - 0.02 + dy
        lights.append(C.light_entry((dx, y_, pl - 0.015), color_k=LIGHT_K, watts=round(5 * W, 1), kind='strip',
                                    p0=[round(xL + dx, 3), round(y_, 3), round(pl - 0.015, 3)], p1=[round(xR + dx, 3), round(y_, 3), round(pl - 0.015, 3)],
                                    normal=[0, 0.3, -1]))
    C.set_json_props(o, kz_lights=lights,
                     kz_params=dict(w=round(W, 3), h=round(H, 3), d=round(D, 3), tiers=L['tiers'], door_w=round(L['dw'], 3),
                                    cols=L['ncols'], modules=L['M'], doors=len(doors), plinth_light=plinth_light, cornice=L['cornice']),
                     kz_instances=dict(door=[[round((x0 + x1) / 2 + dx, 3), round(yd + dy, 3), round(za, 3), round(x1 - x0, 3), round(zb - za, 3)]
                                             for _, x0, x1, za, zb in doors]))
    genlib.finish(o, smooth_angle=40)
    return o
