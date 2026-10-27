"""Changing booth row with noren doors: a row of hinoki changing booths under one flat plank roof, each
booth closed by a split noren with the Kazan-yu crest, a lit washi transom above the door head and a lit
ceiling inside, a bench and a peg rail inside.

Identifying features kept at every LOD: the row of booths (posts + partitions under one roof), a noren
in every opening with the crest, the lit transoms.

Targets (lookbook/img/31-plan-ground.jpg F3-G4 and refs/gen/dh-changing-treatment.png "changing booths
(indigo noren)"; refs/gen/sheet-ref-ground.png 01 for the noren: indigo cloth, cream ring + mountain crest;
scale from the people 1.6-1.7 m and the plan's 10 m bar):
  * booth 1.2-1.8 m wide (concept ~1.5 m), 1.2-1.6 m deep, door head ~1.95 m, total 2.2-2.6 m;
  * 90 mm chamfered posts at every partition, 45 mm board partitions, a dark 60 mm plank roof overhanging
    the front by 0.12 m over a dark fascia, a 0.18-0.2 m washi transom (ranma) with kumiko bars;
  * noren: 3 panels hung from a rod under the lintel, hem 0.55-0.75 m above the floor (privacy), ripples
    2 per panel, 4-16 mm deep (growing to the hem), 2 cm belly, slits opening at the hem; crest ~0.3 m ring
    + mountain on the centre panel (the noren r2/r3 lessons from GUIDE 4.6).
  * overall: proxy (3d/assets.json) 10 x 1.6 x 2.4 m = row typical; snap ground; host (enterable booths).

Parameters: booths (n), booth_w (1.2-1.8), depth (1.2-1.6), h (2.2-2.6), noren ('indigo' | 'black' |
'vermilion' | 'cream'), hem (0.5-0.8).
Seeds: 1 = 6 booths x ~1.6 m, indigo, hem 0.6; 2 = 4 booths x 1.4 m, 1.4 m deep, 2.3 m tall, black
noren, long hem 0.5, two-bar kumiko; 3 = 3 booths x 1.8 m, indigo, short hem 0.75, 4-bar kumiko and
a bench on the side wall. Seeds > 3 sample the ranges. Pleat phase, hem lift, crest height jitter per
booth from per-part streams.

Materials: hinoki wet_oiled (posts, partitions, lintels, bench), hinoki dark_timber (roof, fascia, back
wall), washi_backlit (transoms 1.2, ceiling panels 1.0), noren (+ variant) for cloth, noren cream (crest;
indigo crest on cream noren), hinoki dark rod.
Animation: vertex sway. Float point attribute '_sway' (0 at the head band, 1 at the hem) on the cloth and
crest; obj['kz_anim'] = {'type': 'vertex_sway', 'attrs': ['_sway'], 'panels': ..., 'booth_x': [...]}.
The cloth is single-sided: render double-sided.
Lights: obj['kz_lights'], one point per booth under the lit ceiling (2700 K). Host data: obj['kz_rooms']
= [x0, x1, y0, y1, z0, z1] per booth interior. Lightmap + emissive.
"""
import json
import math

import bpy

import genlib
import kzgeo_common as C
import kzgeo_changing_booth_row as K

ASSET = 'changing_booth_row'
FEATURES = ['row of hinoki booths', 'lit noren door on every booth', 'crest on the noren', 'lit transoms']
PARAMS = dict(booths=(2, 8), booth_w=(1.2, 1.8), depth=(1.2, 1.6), h=(2.2, 2.6), noren=('indigo', 'black', 'vermilion', 'cream'),
              hem=(0.5, 0.8))
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


def _layout(seed, booths, booth_w, depth, h, noren, hem):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'layout')
    pre = {1: (6, None, 1.6, 2.4, 'indigo', 0.6, 3), 2: (4, 1.4, 1.4, 2.3, 'black', 0.5, 2), 3: (3, 1.8, 1.6, 2.4, 'indigo', 0.75, 4)}.get(seed)
    if pre is None:
        pre = (g.randint(2, 6), g.uniform(1.2, 1.6), g.uniform(1.2, 1.6), g.uniform(2.2, 2.4), g.choice(['indigo', 'indigo', 'black', 'cream']),
               g.uniform(0.5, 0.8), g.choice([2, 3, 4]))
    n = booths or pre[0]
    pw, wt = 0.09, 0.045
    bw = booth_w or pre[1] or min(1.8, (p['w'] - (n + 1) * pw) / n)
    bw = min(max(bw, 1.2), 1.8)
    L = dict(n=n, bw=bw, pw=pw, wt=wt)
    L['D'] = min(max(depth or pre[2], 1.2), 1.6)
    L['H'] = min(max(h or pre[3], 2.2), 2.6)
    L['colour'] = noren or pre[4]
    L['hem'] = min(max(hem or pre[5], 0.5), 0.8)
    L['kumiko'] = pre[6]
    L['W'] = n * bw + (n + 1) * pw
    L['bench'] = 'side' if seed == 3 else 'back'
    L['posts'] = [-L['W'] / 2 + pw / 2 + i * (bw + pw) for i in range(n + 1)]
    gc = C.rng(seed, 'cloth')
    L['cloth'] = [dict(phase=[gc.uniform(0, 2 * math.pi) for _ in range(3)], lift=[gc.uniform(-0.015, 0.015) for _ in range(3)],
                       crest_dz=gc.uniform(-0.02, 0.02)) for _ in range(n)]
    return L


def build(lod, seed, booths=None, booth_w=None, depth=None, h=None, noren=None, hem=None, **_):
    L = _layout(seed, booths, booth_w, depth, h, noren, hem)
    budget = (genlib.budget_of(ASSET) or [6000, 2400, 720, 120])[lod]
    mb = genlib.MeshBuilder()
    bm = mb.bm
    sway = bm.verts.layers.float.new('_sway')
    wood = mb.slot('hinoki', variant='wet_oiled', wear=0.15)
    dark = mb.slot('hinoki', variant='dark_timber')
    ranma = mb.slot('washi_backlit', emissive_level=1.2)
    ceil = mb.slot('washi_backlit', emissive_level=1.0)
    col = L['colour']
    cloth = mb.slot('noren', normal_strength=1.6) if col == 'indigo' else mb.slot('noren', variant=col, normal_strength=1.6)
    band = mb.slot('noren', tint=(0.0085, 0.017, 0.056)) if col == 'indigo' else mb.slot('noren', variant=col, roughness_offset=0.05)
    crest = mb.slot('noren', variant='cream') if col != 'cream' else mb.slot('noren')
    n, bw, pw, wt, D, H = L['n'], L['bw'], L['pw'], L['wt'], L['D'], L['H']
    W = L['W']
    yb, yr = -D / 2, D / 2                          # back face, roof front edge
    yfp = yr - 0.12                                 # post front line
    zr0 = H - 0.06                                  # roof underside
    zf0 = zr0 - 0.12                                # fascia underside
    zl1 = zf0 - 0.19                                # transom bottom = lintel top
    zl0 = zl1 - 0.08                                # lintel underside = door head
    z_top = zl0 - 0.005                             # noren head
    posts = L['posts']
    lights, rooms = [], []

    # ------------------------------------------------------------------ structure
    if lod <= 1:
        c = 0.01 if lod == 0 else 0.0
        for x in posts:
            if lod == 0:
                C.chamfered_bar(mb, (x, yfp - pw / 2, zr0 / 2), (pw, pw, zr0), wood, ch=c)
            else:
                K.box_open(bm, x - pw / 2, x + pw / 2, yfp - pw, yfp, 0.0, zr0, wood, sides='flr')
            # partition board behind the post, to the back wall
            if lod == 0:
                C.board(mb, (x, (yb + 0.03 + yfp - pw) / 2, zr0 / 2), (wt, yfp - pw - yb - 0.03, zr0), wood, bevel=0.004)
            else:
                K.box_open(bm, x - wt / 2, x + wt / 2, yb + 0.03, yfp - pw, 0.0, zr0, wood, sides='lr')
        # back wall, roof slab, fascia
        K.box_open(bm, -W / 2, W / 2, yb, yb + 0.03, 0.0, zr0, dark, sides='f' if lod else 'flr')
        if lod == 0:
            C.board(mb, (0, 0, H - 0.03), (W + 0.12, D, 0.06), dark, bevel=0.008)
            K.ext(bm, K.chamfer_rect(yfp - 0.02, yfp + 0.05, zf0, zr0, 0.0), 'x', -W / 2 - 0.03, W / 2 + 0.03, dark)
        else:
            K.box_open(bm, -W / 2 - 0.06, W / 2 + 0.06, yb, yr, zr0, H, dark, sides='ftblr')
            K.box_open(bm, -W / 2 - 0.03, W / 2 + 0.03, yfp - 0.02, yfp + 0.05, zf0, zr0, dark, sides='fb')
        for i in range(n):
            xa, xb = posts[i] + pw / 2, posts[i + 1] - pw / 2
            xc = (xa + xb) / 2
            # lintel (kamoi), transom paper + kumiko, sill
            K.ext(bm, K.chamfer_rect(yfp - 0.07, yfp - 0.005, zl0, zl1, c * 0.6), 'x', xa, xb, wood, caps=(False, False))
            K.quad(bm, [(xa, yfp - 0.04, zl1), (xb, yfp - 0.04, zl1), (xb, yfp - 0.04, zf0), (xa, yfp - 0.04, zf0)], ranma, (0, 1, 0))
            K.quad(bm, [(xa, yfp - 0.05, zl1), (xb, yfp - 0.05, zl1), (xb, yfp - 0.05, zf0), (xa, yfp - 0.05, zf0)], ranma, (0, -1, 0))
            if lod == 0:
                nk = L['kumiko']
                for k in range(1, nk + 1):
                    xk = xa + (xb - xa) * k / (nk + 1)
                    K.box_open(bm, xk - 0.009, xk + 0.009, yfp - 0.04, yfp - 0.022, zl1, zf0, wood, sides='flr')
                K.box_open(bm, xa, xb, yfp - 0.04, yfp - 0.022, (zl1 + zf0) / 2 - 0.008, (zl1 + zf0) / 2 + 0.008, wood, sides='ftb')
                K.box_open(bm, xa, xb, yfp - 0.09, yfp - 0.005, 0.0, 0.03, wood, sides='ft')       # sill
            # lit ceiling inside, bench, peg rail
            K.quad(bm, [(xa + 0.08, yb + 0.12, zr0 - 0.004), (xb - 0.08, yb + 0.12, zr0 - 0.004), (xb - 0.08, yfp - 0.2, zr0 - 0.004),
                        (xa + 0.08, yfp - 0.2, zr0 - 0.004)], ceil, (0, 0, -1))
            if L['bench'] == 'back':
                bx0, bx1, by0, by1 = xa + 0.06, xb - 0.06, yb + 0.03, yb + 0.37
            else:
                bx0, bx1, by0, by1 = xa + wt / 2 - 0.02, xa + 0.36, yb + 0.15, yfp - 0.45
            if lod == 0:
                C.board(mb, ((bx0 + bx1) / 2, (by0 + by1) / 2, 0.43), (bx1 - bx0, by1 - by0, 0.035), wood, bevel=0.005)
                for t in (0.15, 0.85):
                    if L['bench'] == 'back':
                        xx = bx0 + (bx1 - bx0) * t
                        C.board(mb, (xx, (by0 + by1) / 2, 0.205), (0.04, by1 - by0 - 0.06, 0.41), wood, bevel=0.004)
                    else:
                        yy = by0 + (by1 - by0) * t
                        C.board(mb, ((bx0 + bx1) / 2, yy, 0.205), (bx1 - bx0 - 0.06, 0.04, 0.41), wood, bevel=0.004)
                # peg rail on the right partition with two turned pegs
                xr = xb - wt / 2 + 0.02
                K.box_open(bm, xr - 0.02, xr, yb + 0.25, yfp - 0.35, 1.58, 1.66, wood, sides='lftb')
                for yy in (yb + 0.45, yfp - 0.55):
                    C.stick(mb, (xr - 0.02, yy, 1.62), (xr - 0.11, yy, 1.64), 0.012, 0.01, dark, segs=6)
            else:
                K.box_open(bm, bx0, bx1, by0, by1, 0.0, 0.45, wood, sides='ft')
            rooms.append([round(xa, 3), round(xb, 3), round(yb + 0.03, 3), round(yfp - 0.07, 3), 0.0, round(zr0, 3)])
            lights.append(C.light_entry((xc, (yb + yfp) / 2, zr0 - 0.12), color_k=LIGHT_K, watts=20, kind='point'))
    elif lod == 2:
        for x in posts:
            K.box_open(bm, x - pw / 2, x + pw / 2, yfp - pw, yfp, 0.0, zr0, wood, sides='f')
        for x in (posts[0], posts[-1]):
            K.quad(bm, [(x + (-pw / 2 if x < 0 else pw / 2), yb, 0.0), (x + (-pw / 2 if x < 0 else pw / 2), yfp, 0.0),
                        (x + (-pw / 2 if x < 0 else pw / 2), yfp, zr0), (x + (-pw / 2 if x < 0 else pw / 2), yb, zr0)], wood, (-1 if x < 0 else 1, 0, 0))
        K.box_open(bm, -W / 2 - 0.06, W / 2 + 0.06, yb, yr, zr0, H, dark, sides='ftb')
        K.quad(bm, [(-W / 2, yfp + 0.05, zf0), (W / 2, yfp + 0.05, zf0), (W / 2, yfp + 0.05, zr0), (-W / 2, yfp + 0.05, zr0)], dark, (0, 1, 0))
        for i in range(n):
            xa, xb = posts[i] + pw / 2, posts[i + 1] - pw / 2
            K.quad(bm, [(xa, yfp - 0.005, zl0), (xb, yfp - 0.005, zl0), (xb, yfp - 0.005, zl1), (xa, yfp - 0.005, zl1)], wood, (0, 1, 0))
            K.quad(bm, [(xa, yfp - 0.04, zl1), (xb, yfp - 0.04, zl1), (xb, yfp - 0.04, zf0), (xa, yfp - 0.04, zf0)], ranma, (0, 1, 0))
            K.quad(bm, [(xa, yb + 0.12, zr0 - 0.004), (xb, yb + 0.12, zr0 - 0.004), (xb, yfp - 0.2, zr0 - 0.004), (xa, yfp - 0.2, zr0 - 0.004)], ceil, (0, 0, -1))
        K.quad(bm, [(-W / 2, yb + 0.03, 0.0), (W / 2, yb + 0.03, 0.0), (W / 2, yb + 0.03, zr0), (-W / 2, yb + 0.03, zr0)], dark, (0, 1, 0))
    else:
        K.box_open(bm, -W / 2 - 0.06, W / 2 + 0.06, yb, yr, zf0, H, dark, sides='ft')
        for x in posts:
            K.quad(bm, [(x - pw / 2, yfp, 0.0), (x + pw / 2, yfp, 0.0), (x + pw / 2, yfp, zf0), (x - pw / 2, yfp, zf0)], wood, (0, 1, 0))
        for x in (posts[0], posts[-1]):
            xs = x + (-pw / 2 if x < 0 else pw / 2)
            K.quad(bm, [(xs, yb, 0.0), (xs, yfp, 0.0), (xs, yfp, zf0), (xs, yb, zf0)], wood, (-1 if x < 0 else 1, 0, 0))
        for i in range(n):
            xa, xb = posts[i] + pw / 2, posts[i + 1] - pw / 2
            K.quad(bm, [(xa, yfp - 0.04, zl1), (xb, yfp - 0.04, zl1), (xb, yfp - 0.04, zf0), (xa, yfp - 0.04, zf0)], ranma, (0, 1, 0))

    # ------------------------------------------------------------------ noren (same layout at every LOD)
    for i in range(n):
        xa, xb = posts[i] + pw / 2, posts[i + 1] - pw / 2
        cl = L['cloth'][i]
        y0 = yfp - 0.085
        nw = (xb - xa) - 0.03
        gap = 0.012
        pwid = (nw - 2 * gap) / 3
        x0 = (xa + xb) / 2 - nw / 2
        hem = L['hem']
        if lod <= 1:
            cols, rows, rip = (8, 6, 2) if lod == 0 else (4, 4, 2)
            Ps = []
            for k in range(3):
                pa = x0 + k * (pwid + gap)
                P = K.Pleats(pa, pa + pwid, z_top, hem, rip, 0.004, 0.016, 0.02, cl['phase'][k])
                Ps.append(P)
                K.noren_panel(bm, P, y0, cols, rows, cloth, band, 0.09, sway, hem_lift=cl['lift'][k], flare=0.015, side=k - 1)
            # head band across the slits (sewn double layer) + rod
            K.quad(bm, [(x0, y0 - 0.006, z_top - 0.09), (x0 + nw, y0 - 0.006, z_top - 0.09), (x0 + nw, y0 - 0.006, z_top), (x0, y0 - 0.006, z_top)], band, (0, 1, 0))
            C.tube(mb, [(xa - 0.02, y0 - 0.012, z_top - 0.02), (xb + 0.02, y0 - 0.012, z_top - 0.02)], [0.016, 0.016], dark, sides=8 if lod == 0 else 5)
            # crest on the centre panel: ring + mountain, laid on the pleat field
            P = Ps[1]
            r_out = min(0.15, pwid * 0.38)
            cx = P.x0 + pwid / 2
            cz = z_top - 0.09 - 0.07 - r_out + cl['crest_dz']
            tris = K.ring_tris(cx, cz, r_out * 0.86, r_out, 28 if lod == 0 else 12)
            mt = K.mountain(lo=lod > 0)
            s = r_out * 1.3
            poly = [(cx - x * s, cz - r_out * 0.48 + y * s * 1.1) for x, y in mt]        # x -> -X: reads correctly from +Y
            tris += K.poly_tris(poly)
            K.decal_tris(bm, tris, P, y0, 0.005, crest, sway, sub=1 if lod == 0 else 0)
        elif lod == 2:
            for k in range(3):
                pa = x0 + k * (pwid + gap)
                P = K.Pleats(pa, pa + pwid, z_top, hem, 1, 0.0, 0.0, 0.02, 0.0)
                K.noren_panel(bm, P, y0, 2, 2, cloth, band, 0.09, sway, flare=0.015, side=k - 1)
            P = K.Pleats(x0 + pwid + gap, x0 + 2 * pwid + gap, z_top, hem, 1, 0.0, 0.0, 0.02, 0.0)
            r_out = min(0.15, pwid * 0.38)
            cx = x0 + pwid * 1.5 + gap
            cz = z_top - 0.16 - r_out
            disc = [(cx + r_out * math.cos(2 * math.pi * k / 8), cz + r_out * math.sin(2 * math.pi * k / 8)) for k in range(8)]
            K.decal_tris(bm, K.poly_tris(disc), P, y0, 0.006, crest, sway, sub=0)
        else:
            P = K.Pleats(x0, x0 + nw, z_top, hem, 1, 0.0, 0.0, 0.0, 0.0)
            K.noren_panel(bm, P, y0, 1, 1, cloth, cloth, 0.0, sway)
            r_out = min(0.15, pwid * 0.38)
            cx, cz = (xa + xb) / 2, z_top - 0.16 - r_out
            K.decal_tris(bm, [((cx - r_out, cz - r_out), (cx + r_out, cz - r_out), (cx + r_out, cz + r_out)),
                              ((cx - r_out, cz - r_out), (cx + r_out, cz + r_out), (cx - r_out, cz + r_out))], P, y0, 0.006, crest, sway, sub=0)

    if C.tri_count(bm) > budget * 1.1:
        print(f'[{ASSET}] LOD{lod}: {C.tri_count(bm)} tris over budget {budget}')
    o = _to_object(mb, ASSET)
    C.set_json_props(o, kz_lights=lights, kz_rooms=rooms,
                     kz_anim=dict(type='vertex_sway', attrs=['_sway'], panels=3 * n, booth_x=[round((posts[i] + posts[i + 1]) / 2, 3) for i in range(n)],
                                  head_z=round(z_top, 3), hem_z=round(L['hem'], 3)),
                     kz_params=dict(booths=n, booth_w=round(bw, 3), depth=round(D, 3), h=round(H, 3), noren=col, hem=round(L['hem'], 3),
                                    w=round(W, 3), kumiko=L['kumiko'], bench=L['bench']))
    genlib.finish(o, smooth_angle=40)
    return o
