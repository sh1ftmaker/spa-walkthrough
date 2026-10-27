"""Cable lift station (cable_station), bottom ('base') and top ('top'): a bronze-and-timber hall on a stone plinth with
an open cabin bay (loading pit) between two raised boarding platforms, glazed screens on the platform sides,
an enclosed machine room behind, a bronze bull wheel in its housing at the rear, eave lanterns and a tiled roof.

Concept: refs/gen/sheet-vs-lift-cable.png panel 3 "Cable lift stations (bottom / top), W 5 x D 6 x H 5 m" (front
and side of each); lookbook 30 / 31 (plans: top station E4 on the summit, bottom station on the ground terrace),
lookbook 11 (caldera crown: timber-and-glass buildings with deep tiled eaves). Measured on panel 3 (2x crop
.scratch/op16/m_station.png, 1 m bar = 83 px; the bar gives 5.4 x 3.7 m for a 5 x 5 m label, so ratios + labels):
  * front: gable end with a curved (irimoya) roof the full 5 m width, ridge along the depth; 4 posts across the
    front (bay posts ~+-0.9 m, corner posts ~+-2.2 m), a cabin hanging in the centre bay; side platforms with
    bronze fret railings on a stone plinth ~0.8-1.1 m tall; hanging lanterns on bracket arms at the corner posts
    under the eave and smaller lanterns on the bay posts
  * side: open hall at the front (~1/3 of the depth), enclosed timber room behind with a double door and a lit
    panel, plaster / board upper wall; a spoked bull wheel (~1.2-1.5 m) at the rear upper corner with the cables
    leaving it; steps down at one end; a bronze pipe on the wall
Scale conflict (GUIDE 9): the sheet draws the cabin at half its own panel-4 size. With the real cabin (4.7 m from
lamp to grip) hanging in the bay, the cable sits at 4.55 m above the pit, so the eave must be at ~5.1 m and the
ridge ~6.7 m: the station is built 7.0 m tall (row range h 5-7) and the bull wheel projects behind the rear wall.
PROXY_SHEET is the proposed proxy (assets.json 5 x 6 x 5).

Layout (seed 1): plinth 5.0 x 6.0 x 1.1 m; loading pit 2.1 m wide open to the front (floor 0.12 m); platforms
1.1 m up with hinoki decking; posts 0.22 m (dark timber, bronze shoes); hall y -0.4 .. +2.9, machine room
y -2.9 .. -0.4 with doors on both side walls; glazed bronze screens above the platform railings; roof eave outline
5.9 x 7.1 m, eave 5.15 m; twin cables (x +-0.20, z 4.55) from the front edge to the bull wheel
(R 0.75, axis X, centre y -3.84, rim 0.6 m behind the rear eave); the cable port is obj['kz_cable_port'] for cable_line endpoints.

Parameters build(lod, seed, **p)
  style   'base' | 'top' (cycles with the seed: base, top, base)
  w 5-8 (5.0 / 5.3 / 5.6)   d 6-8 (6.0 / 6.4 / 6.6)   glazed bays per side 1-3 (2 / 3 / 1)
  roof    irimoya | gable | hip via roof_tiled (irimoya / gable / hip)   wheel_r 0.6-1.0 (0.75 / 0.85 / 0.7)
Seeds change: style (top adds a tension counterweight under the bull wheel, steps on both sides, an extra
platform lantern pair), footprint, glazed bay count, roof type, wheel size and spoke count (8 / 6 / 8).

Materials (slots by part): plinth basalt_dry tint (0.55, 0.55, 0.6); pit floor basalt_wet 0.5; deck hinoki handled;
posts + beams hinoki dark_timber; cladding hinoki wet_oiled; doors lacquer_dark; frame bronze (wear 0.2, normal
0.03: shoes, railings, glazing, wheel housing); polish bronze smooth (rails' top bar, wheel rim, lantern caps);
glass glass_clear (row's lava_glass is not used for clear screens, GUIDE 7); lit panels washi_backlit 0.6;
lanterns lantern_andon; roof: kawara, hinoki dark_timber, lacquer_dark, iron (roof_tiled).
Animation (rigid): the bull wheel turns: vertex group 'bull_wheel', obj['kz_anim'] = rotate about
[1, 0, 0] through kz_anim.pivot, speed tied to the cable. Lights: kz_lights (eave + post lanterns, lit panels).
Lighting: lightmap + emissive.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_cable_station as K
import kzgeo_roof_tiled as KR

ASSET = 'cable_station'
FEATURES = ['bronze-and-timber station', 'glazed cabin bay', 'bull-wheel housing', 'eave lanterns', 'tiled roof']
PROXY_SHEET = dict(w=6.6, d=8.8, h=7.2)        # proposed (assets.json 5 x 6 x 5): see the docstring
STYLES = ['base', 'top']
GAUGE = 0.40

SEEDS = {1: dict(style='base', w=5.0, d=6.0, glazed=2, roof='irimoya', wheel_r=0.75, spokes=8),
         2: dict(style='top', w=5.3, d=6.4, glazed=3, roof='gable', wheel_r=0.85, spokes=6),
         3: dict(style='base', w=5.6, d=6.6, glazed=1, roof='hip', wheel_r=0.70, spokes=8)}
ROOF_BUDGET = (4600, 1850, 420, 70)


def params(seed, **p):
    P = dict(SEEDS[(seed - 1) % 3 + 1])
    if seed > 3:
        g = C.rng(seed, 'station')
        P['w'] = min(8.0, P['w'] * g.uniform(0.95, 1.1)); P['d'] = min(8.0, P['d'] * g.uniform(0.95, 1.1))
    for k, v in p.items():
        if v is not None and k in P:
            P[k] = v
    return P


def build(lod, seed, **p):
    P = params(seed, **p)
    W, D = P['w'], P['d']
    top = P['style'] == 'top'
    mb = genlib.MeshBuilder()
    M = dict(stone=mb.slot('basalt_dry', tint=(0.55, 0.55, 0.6)), pit=mb.slot('basalt_wet', wetness=0.5),
             deck=mb.slot('hinoki', variant='handled'), post=mb.slot('hinoki', variant='dark_timber'),
             clad=mb.slot('hinoki', variant='wet_oiled'), door=mb.slot('lacquer_dark', wear=0.1),
             frame=mb.slot('bronze', wear=0.2, normal_strength=0.03),
             polish=mb.slot('bronze', variant='smooth', wear=0.6, roughness_offset=-0.1),
             glass=mb.slot('glass_clear'), lit=mb.slot('washi_backlit', emissive_level=0.6),
             paper=mb.slot('lantern_andon', emissive_level=1.0),
             tile=mb.slot('kawara'), roofwood=mb.slot('hinoki', variant='dark_timber'),
             roofd=mb.slot('lacquer_dark', wear=0.1), iron=mb.slot('iron', wear=0.2))
    lights = []
    hw, hd = W / 2, D / 2                       # plinth half extents
    zp = 1.1                                    # platform level
    bay = max(1.42, W * 0.28)                   # pit half width (the 2.4-2.6 m cabin hangs in it)
    yf, ym, yr = hd - 0.1, -0.4, -hd + 0.1     # post rows: front, room front wall, rear
    xo, xb = hw - 0.15, bay + 0.12              # outer / bay post x
    zc = 4.60                                   # cable centre (cabin lamp 0.07 m above the pit floor)
    z_e = 5.15                                  # roof eave tile edge
    zs = zp + 0.06                              # deck top

    # ------------------------------------------------------------------ plinth, pit, steps
    step_x0 = bay                               # steps take the platform's full width at the front
    ys0 = hd - 1.2                              # steps start (y) on the platform front
    sides = (1, -1) if top else (1,)
    bev = C.lod_pick(lod, 0.03, 0.0, 0.0, 0.0)
    if lod <= 2:
        for sx in (-1, 1):                      # platform blocks (left / right of the pit)
            x0, x1 = bay, hw
            if sx in sides:
                K.box(mb, (sx * (x0 + x1) / 2, (ym + ys0) / 2, zp / 2), (x1 - x0, ys0 - ym, zp), M['stone'], bevel=bev)
                for k in range(3):              # three steps down to the ground, towards +Y
                    zt = zp * (3 - k) / 4
                    y0 = ys0 + 0.3 * k
                    K.box(mb, (sx * (step_x0 + hw) / 2, (y0 + hd) / 2, zt / 2), (hw - step_x0, hd - y0, zt), M['stone'], bevel=bev * 0.5)
            else:
                K.box(mb, (sx * (x0 + x1) / 2, (ym + hd) / 2, zp / 2), (x1 - x0, hd - ym, zp), M['stone'], bevel=bev)
        K.box(mb, (0, (ym - hd) / 2, zp / 2), (W, hd + ym, zp), M['stone'], bevel=bev)     # under the machine room
        mb.box((0, (ym + hd) / 2, 0.03), (2 * bay, hd - ym, 0.06), M['pit'])              # pit floor
        if lod == 0:                            # coping course on the plinth edges
            for sx in (-1, 1):
                K.box(mb, (sx * (hw + 0.02), 0, zp - 0.08), (0.08, D + 0.04, 0.16), M['stone'], bevel=0.015)
    else:
        mb.box((0, 0, zp / 2), (W, D, zp), M['stone'])

    # ------------------------------------------------------------------ deck boards on the platforms
    if lod <= 1:
        nb = C.lod_pick(lod, 7, 1)
        for sx in (-1, 1):
            x0, x1 = bay + 0.02, hw - 0.02
            ye = ys0 if sx in sides else hd - 0.02
            for i in range(nb):
                bw = (x1 - x0) / nb
                x = x0 + bw * (i + 0.5)
                if sx in sides and x > step_x0:
                    ye_i = ys0
                else:
                    ye_i = hd - 0.02
                K.box(mb, (sx * x, (ym + ye_i) / 2, zp + 0.03), (bw - 0.012, ye_i - ym, 0.06), M['deck'],
                      bevel=C.lod_pick(lod, 0.006, 0.0))

    # ------------------------------------------------------------------ roof (built along X, rotated so the ridge runs along Y)
    eave_x, eave_y = 0.5, 0.6                   # overhang beyond the outer posts (sides) / the end rows (front, back)
    pre = set(mb.bm.verts)
    rmats = dict(tile=M['tile'], ridge=M['tile'], wood=M['roofwood'], wood_d=M['roofd'], iron=M['iron'])
    info = KR.roof_into(mb, rmats, lod, P['roof'], (yf - yr) / 2 + eave_y, xo + eave_x, z_e=z_e, pitch=27.0,
                        eave=eave_x + 0.0, eave_s=eave_y, up=0.2, tp=0.27, p=1.25,
                        budget=ROOF_BUDGET[lod], r=C.rng(seed, 'roof'))
    rv = [v for v in mb.bm.verts if v not in pre]
    K.rot_verts_z(rv, math.pi / 2)
    for v in rv:
        v.co.y += (yf + yr) / 2
    wall_top = info['wall_top']

    # ------------------------------------------------------------------ posts and beams
    pw = 0.22
    rows = [yf, ym, yr]
    posts = []
    for y in rows:
        for x in (-xo, -xb, xb, xo):
            if y == yr and abs(x) == xb and lod >= 2:
                continue
            posts.append((x, y))
    for x, y in posts:
        z0 = zp if abs(x) > bay or y <= ym else 0.06
        if lod <= 2:
            K.box(mb, (x, y, (z0 + wall_top) / 2), (pw, pw, wall_top - z0), M['post'], bevel=C.lod_pick(lod, 0.012, 0.0, 0.0))
        if lod == 0:                            # bronze shoe + capital band
            mb.box((x, y, z0 + 0.09), (pw + 0.04, pw + 0.04, 0.18), M['frame'])
            mb.box((x, y, wall_top - 0.42), (pw + 0.03, pw + 0.03, 0.06), M['polish'])
    if lod == 3:
        for x, y in ((-xo, yf), (xo, yf), (-xb, yf), (xb, yf)):
            mb.box((x, y, (zp + wall_top) / 2), (pw, pw, wall_top - zp), M['post'])
    bh = 0.26
    if lod <= 2:
        for y in rows:                          # head beams across X
            K.box(mb, (0, y, wall_top - bh / 2), (2 * xo + 0.3, 0.2, bh), M['post'], bevel=C.lod_pick(lod, 0.01, 0.0, 0.0))
        for x in (-xo, xo):                     # side plates along Y
            K.box(mb, (x, (yf + yr) / 2, wall_top - bh / 2), (0.2, yf - yr + 0.3, bh), M['post'], bevel=C.lod_pick(lod, 0.01, 0.0, 0.0))
        for x in (-xb, xb):
            K.box(mb, (x, (yf + ym) / 2, wall_top - bh / 2), (0.18, yf - ym, bh), M['post'])
        if lod <= 1:                            # nuki tie beams at door-head height between the outer posts
            for x in (-xo, xo):
                K.box(mb, (x, (yf + ym) / 2, zp + 2.35), (0.16, yf - ym, 0.16), M['post'])
            for sx in (-1, 1):
                K.box(mb, (sx * (xo + xb) / 2, yf, zp + 2.35), (xo - xb, 0.16, 0.16), M['post'])

    # ------------------------------------------------------------------ machine room: cladding, doors, lit panels
    t = 0.08
    if lod <= 2:
        # side walls (x = +-xo) between ym and yr, with a double door; rear wall; front wall (facing the hall)
        for sx in (-1, 1):
            x = sx * xo
            L = ym - yr
            dw = 1.2
            yc = (ym + yr) / 2
            for y0, y1 in ((yr, yc - dw / 2), (yc + dw / 2, ym)):
                K.box(mb, (x, (y0 + y1) / 2, (zp + wall_top - bh) / 2), (t, y1 - y0 - pw, wall_top - bh - zp), M['clad'])
            K.box(mb, (x, yc, (zp + 2.15 + wall_top - bh) / 2), (t, dw, wall_top - bh - zp - 2.15), M['clad'])
            # double door (lacquer leaves, lit glazing in the upper half, bronze handles)
            K.box(mb, (x + sx * 0.0, yc, zp + 1.075), (t * 0.8, dw - 0.04, 2.15), M['door'])
            if lod <= 1:
                for sy in (-1, 1):
                    K.box(mb, (x + sx * t * 0.45, yc + sy * dw / 4, zp + 1.55), (0.02, dw / 2 - 0.2, 0.8), M['lit'])
                    if lod == 0:
                        for k in range(1, 3):   # kumiko bars over the lit pane
                            K.box(mb, (x + sx * t * 0.6, yc + sy * dw / 4, zp + 1.15 + 0.8 * k / 3), (0.015, dw / 2 - 0.2, 0.02), M['frame'])
                        K.box(mb, (x + sx * t * 0.6, yc + sy * dw / 4, zp + 1.55), (0.015, 0.02, 0.8), M['frame'])
                        K.beam(mb, (x + sx * 0.06, yc + sy * 0.06, zp + 0.85), (x + sx * 0.06, yc + sy * 0.06, zp + 1.25), 0.025, 0.025, M['polish'])
                lights.append(C.light_entry((x + sx * 0.3, yc, zp + 1.6), color_k=2400, watts=20, kind='area_panel'))
            if lod == 0:                        # wainscot rail + vertical battens on the cladding
                for y0, y1 in ((yr, yc - dw / 2), (yc + dw / 2, ym)):
                    K.box(mb, (x + sx * t * 0.6, (y0 + y1) / 2, zp + 1.0), (0.03, y1 - y0 - pw, 0.07), M['post'])
                    nbat = max(1, int((y1 - y0) / 0.45))
                    for k in range(1, nbat):
                        yy = y0 + (y1 - y0) * k / nbat
                        K.box(mb, (x + sx * t * 0.6, yy, (zp + wall_top - bh) / 2), (0.025, 0.04, wall_top - bh - zp), M['post'])
        K.box(mb, (0, yr, (zp + wall_top - bh) / 2), (2 * xo - pw, t, wall_top - bh - zp), M['clad'])
        # room front wall facing the hall: boarded, a lit window band, opening for the cables at the top
        K.box(mb, (0, ym, (zp + 3.6) / 2), (2 * xo - pw, t, 3.6 - zp), M['clad'])
        for sx in (-1, 1):
            K.box(mb, (sx * (xo + 0.5) / 2, ym, (3.6 + wall_top - bh) / 2), (xo - 0.5 - pw / 2, t, wall_top - bh - 3.6), M['clad'])
        K.box(mb, (0, ym + t * 0.6, zp + 1.7), (1.6, 0.03, 0.9), M['lit'])
        lights.append(C.light_entry((0, ym + 0.4, zp + 1.7), color_k=2400, watts=25, kind='area_panel'))
        if lod <= 1:
            for k in range(1, 4):
                K.box(mb, (-0.8 + 1.6 * k / 4, ym + t * 0.6 + 0.02, zp + 1.7), (0.03, 0.03, 0.9), M['post'])
    else:
        mb.box((0, (ym + yr) / 2, (zp + wall_top) / 2), (2 * xo, ym - yr, wall_top - zp), M['clad'])

    # ------------------------------------------------------------------ hall: railings + glazed screens on the platform sides
    rm = dict(frame=M['frame'], polish=M['polish'])
    rh = 1.0
    if lod <= 2:
        for sx in (-1, 1):
            # outer side railing (x = +-xo .. along Y from ym to the front / the steps)
            yend = ys0 if sx in sides else yf
            K.railing(mb, (sx * (xo - 0.02), ym + pw / 2), (sx * (xo - 0.02), yend), zs, rh, rm, lod, post_sp=0.95 if lod <= 1 else 1.8)
            # front railing (y = yf) from the bay post to the steps / the corner
            if sx not in sides:
                K.railing(mb, (sx * (xb + pw / 2), yf), (sx * xo, yf), zs, rh, rm, lod, post_sp=0.9 if lod <= 1 else 1.8)
            # glazed screen above the outer railing: n bays of bronze-framed glass between the beams
            n = P['glazed']
            zg0, zg1 = zs + rh + 0.12, wall_top - bh - 0.04
            ya, yb = ym + pw / 2, yf - pw / 2
            xg = sx * (xo + 0.0)
            K.box(mb, (xg, (ya + yb) / 2, zg0 - 0.04), (0.07, yb - ya, 0.08), M['frame'])          # sill
            for k in range(n):
                y0 = ya + (yb - ya) * k / n; y1 = ya + (yb - ya) * (k + 1) / n
                K.pane(mb, (xg, (y0 + y1) / 2, (zg0 + zg1) / 2), (0.012, y1 - y0 - 0.04, zg1 - zg0), M['glass'])
                if k and lod <= 1:
                    K.box(mb, (xg, y0, (zg0 + zg1) / 2), (0.06, 0.06, zg1 - zg0), M['frame'])
                if lod == 0:                    # transom bar + small corner brackets per bay
                    K.box(mb, (xg, (y0 + y1) / 2, zg1 - 0.35), (0.05, y1 - y0, 0.04), M['frame'])
                    for yy, s in ((y0 + 0.12, 1), (y1 - 0.12, -1)):
                        K.beam(mb, (xg, yy - s * 0.1, zg1 - 0.35), (xg, yy + s * 0.02, zg1 - 0.2), 0.03, 0.03, M['polish'])
        # bronze fret (ranma) under the front lintel either side of the cable gap
        if lod <= 1:
            for sx in (-1, 1):
                x0, x1 = 0.55, xb - pw / 2
                z0, z1 = wall_top - bh - 0.45, wall_top - bh
                K.box(mb, (sx * (x0 + x1) / 2, yf, z0), (x1 - x0, 0.06, 0.04), M['frame'])
                if lod == 0:
                    for k in range(5):
                        x = x0 + (x1 - x0) * (k + 0.5) / 5
                        K.box(mb, (sx * x, yf, (z0 + z1) / 2), (0.025, 0.04, z1 - z0), M['frame'])
                    K.beam(mb, (sx * x0, yf, z0), (sx * x1, yf, z1), 0.025, 0.04, M['polish'])

    # ------------------------------------------------------------------ lanterns: eave lanterns on the corner posts, smaller ones on the bay posts
    lm = dict(frame=M['frame'], paper=M['paper'])
    if lod <= 2:
        for sx in (-1, 1):
            c = K.hanging_lantern(mb, (sx * (xo + pw / 2), yf, wall_top - 0.55), (sx, 0.0), lm, lod,
                                  size=0.24, height=0.42, arm=0.32, drop=0.1)
            lights.append(C.light_entry(c, color_k=2200, watts=25))
            c = K.hanging_lantern(mb, (sx * xb, yf + pw / 2, zp + 1.9), (0.0, 1.0), lm, lod,
                                  size=0.16, height=0.3, arm=0.18, drop=0.05)
            lights.append(C.light_entry(c, color_k=2200, watts=12))
            if top:                             # top station: wall lantern beside each room door
                c = K.hanging_lantern(mb, (sx * (xo + t / 2), ym - 0.35, zp + 2.35), (sx, 0.0), lm, lod,
                                      size=0.16, height=0.3, arm=0.2, drop=0.05)
                lights.append(C.light_entry(c, color_k=2200, watts=12))
    else:
        for sx in (-1, 1):
            q = Vector((sx * (xo + 0.45), yf, wall_top - 1.1))
            C.lantern_head(mb, tuple(q), dict(iron=M['frame'], paper=M['paper']), 2, size=0.24, height=0.42)
            lights.append(C.light_entry(q + Vector((0, 0, 0.21)), color_k=2200, watts=25))

    # ------------------------------------------------------------------ cables through the hall to the bull wheel, the wheel and its housing
    R = P['wheel_r']
    yw = yr - eave_y - 0.45 * R                 # wheel centre: projects behind the rear eave, as on the sheet's side view
    zw = zc - R + 0.02
    if lod <= 2:
        for sx in (-1, 1):
            x = sx * GAUGE / 2
            pts = [Vector((x, yf + eave_y - 0.05, zc)), Vector((x, yw, zc))]
            K.cable(mb, pts, 0.028, M['iron'], sides=C.lod_pick(lod, 6, 4, 3))
        if lod <= 1:                            # support sheaves hung from the room front wall
            for sx in (-1, 1):
                x = sx * GAUGE / 2
                K.wheel(mb, (x, ym + 0.2, zc - 0.028 - 0.14), (1, 0, 0), 0.14, dict(rim=M['polish'], spoke=M['frame'], hub=M['iron']),
                        lod, spokes=0, rim_w=0.05, rim_t=0.06, hub_r=0.04, segs=C.lod_pick(lod, 12, 8))
                K.beam(mb, (x, ym + 0.2, zc - 0.16), (x, ym + 0.2, wall_top - bh), 0.05, 0.05, M['frame'])
    pre = set(mb.bm.verts)
    wm = dict(rim=M['polish'], spoke=M['frame'], hub=M['iron'])
    if lod <= 2:
        K.wheel(mb, (0, yw, zw), (1, 0, 0), R, wm, lod, spokes=P['spokes'] if lod <= 1 else 4, rim_w=0.1, rim_t=0.12,
                hub_r=0.12, segs=C.lod_pick(lod, 40, 20, 12))
    else:
        mb.cylinder((0, yw, zw), R, 0.12, M['polish'], segs=6, rot=(0, math.pi / 2, 0))
    wheel_set = [v for v in mb.bm.verts if v not in pre]
    if lod <= 2:
        # housing: a bronze hood over the top third of the wheel, two raking supports from the plinth to the axle
        hood = K.axis_frame((0, yw, zw), (1, 0, 0))
        if lod <= 1:
            K.torus(mb, hood, R + 0.12, [(-0.02, -0.16), (0.02, -0.16), (0.02, 0.16), (-0.02, 0.16)],
                    C.lod_pick(lod, 14, 8), M['frame'], a0=math.radians(-30), a1=math.radians(110))
        for sx in (-1, 1):
            K.beam(mb, (sx * 0.32, yr - 0.05, zp), (sx * 0.2, yw, zw), 0.12, 0.12, M['frame'])
            K.beam(mb, (sx * 0.32, yr - 0.1, wall_top - bh), (sx * 0.2, yw, zw), 0.1, 0.1, M['frame'])
        C.stick(mb, (-0.24, yw, zw), (0.24, yw, zw), 0.05, 0.05, M['iron'], segs=C.lod_pick(lod, 8, 6, 4))
        if top:                                 # tension counterweight hanging under the wheel
            K.beam(mb, (0, yw, zw - 0.1), (0, yw, zp + 1.3), 0.04, 0.04, M['iron'])
            K.box(mb, (0, yw, zp + 0.95), (0.55, 0.4, 0.7), M['iron'], bevel=C.lod_pick(lod, 0.02, 0.0, 0.0))
            K.box(mb, (0, yw, zp / 2 + 0.3), (1.0, 0.8, zp + 0.6 - 0.0), M['stone'])     # pier the weight sits over
    # ------------------------------------------------------------------ finish
    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=True)
    mb.bm.verts.index_update()
    idx = sorted(v.index for v in wheel_set if v.is_valid)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    # vertex group for the turning bull wheel (indices survive to_object in creation order)
    wc = Vector((0, yw + dy, zw + dz))
    g = o.vertex_groups.new(name='bull_wheel'); g.add(idx, 1.0, 'REPLACE')
    for L in lights:
        L['pos'][1] = round(L['pos'][1] + dy, 4); L['pos'][2] = round(L['pos'][2] + dz, 4)
    port = [[round(s * GAUGE / 2, 3), round(yf + eave_y - 0.05 + dy, 3), round(zc + dz, 3)] for s in (-1, 1)]
    C.set_json_props(o, kz_lights=lights,
                     kz_anim=dict(type='rigid', parts=dict(bull_wheel=dict(group='bull_wheel', kind='rotate',
                                                                          axis=[1, 0, 0], pivot=[0, round(wc.y, 3), round(wc.z, 3)],
                                                                          rpm_from='cable speed / (2 pi r)', r=R))),
                     kz_cable_port=port, kz_cabin_stop=[0, round((yf + ym) / 2 + dy, 3), round(zc + dz, 3)],
                     kz_glow_slots=[M['paper'], M['lit']],
                     kz_params={k: v for k, v in P.items()})
    return o
