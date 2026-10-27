"""Kawagiri dining pod (kawagiri_pod): timber platform on beams over the river, low tiled roof with a ceiling
trough, water curtains on three sides, red chochin at the corners, floor gutter.

TARGETS (refs/gen/sheet-mod-kawagiri.png panel 1, crop .scratch/op18/m_pod.png at 2x; ~115 px/m, the two
bars agree within 10 %; lookbook 06 / 07 section A-A / 08)
  deck 5.0 x 5.0 m; stone footings 0.4 m tall under a 3 x 3 post grid; stilts + girders put the deck top at
  ~1.2-1.4 m above the water (sheet 1.3); X braces between the stilts (side view);
  room posts at the corners and mid-sides (3 per side); top beam (keta) ~2.6 m above the deck; the ceiling
  trough (the cyan strip of the sheet, 'CEILING TROUGH' of 07 A-A) runs under the keta on the three curtain
  sides; curtains fall from it into a FLOOR GUTTER along the deck edge (07 A-A);
  low hip roof (kawara) with ~0.45 m eaves; the 4.2 m bar spans water -> trough, so the whole pod is ~4.8 m.
  Red chochin (0.4 x 0.55 m) hang at the corners; small andon on the entry rail posts; a low table with
  dark zabuton and a tea set; lookbook 08: a slim timber table-aqueduct on trestles along the table.
  Entry side (open, no curtain) is -Y; the sheet's FRONT view (curtains) is +Y.
  SIZE: the proxy h 3.6 matches the row's h 3.2-4.2 measured deck -> roof; with the stilts the default pod is
  ~4.8 m tall (proposed proxy h 4.9, reported). `h` here is the deck-to-ridge height.

FEATURES kept at every LOD: timber platform on beams and stilts, low tiled roof, ceiling trough, floor gutter,
  red chochin at the corners, the table.  Water curtains are runtime fx (kz_water_curtains), never a mesh.
  LOD1: no bevels, plain deck boards, no tea set; LOD2: deck as one slab, no braces' second diagonal, no
  cushions' pillow shape; LOD3: boxes + roof + chochin.

PARAMETERS  w 4.5-5.5 (5) | d 4.5-5.5 (5) | h 3.2-4.2 (deck to ridge, 3.6) | stilt 0.6-1.4 (0.85) |
  curtain_sides 1-3 (3) | trough True | layout 'long' | 'twin' | 'square' | variant 'standard' | 'chef_table' |
  roof 'hip' | 'irimoya'
SEEDS: seeds 1-3 are 'standard' with layout long / twin / square, h 3.6 / 3.3 / 4.0,
  stilt 0.85 / 1.1 / 0.7 (roof hip on all: irimoya is a parameter but costs ~2000 tris over the LOD0 budget), an extra chochin on the front-mid post on seed 2; seed 4 (and every 4th) is the
  chef_table variant (L-counter with a griddle at the entry side, one long table).
MATERIALS (slots by part): structure hinoki dark_timber; deck + table legs hinoki wet_oiled; table top, gutter
  channel lacquer_dark; trough hinoki walnut; gutter grate iron; footings basalt_wet (wet, in the river); roof
  kawara + lacquer_dark; chochin lantern_paper red + lacquer_black caps; andon lantern_andon; cushions noren
  (indigo); tea set ceramic tenmoku / celadon; griddle iron.
ANIMATION kz_anim sim fx_water_curtain (curtains part on approach): kz_water_curtains = per bay
  {a, b (x, y), z_top, z_bottom}. LIGHTS kz_lights: chochin (2200 K red), andon.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_kawagiri_pod as KK
import kzgeo_roof_tiled as KR

ASSET = 'kawagiri_pod'
FEATURES = ['timber platform on beams over the river', 'low roof with ceiling trough', 'water curtains on three sides',
            'red chochin at the corners', 'floor gutter']
LAYOUTS = ['long', 'twin', 'square']


def params(seed, w=None, d=None, h=None, stilt=None, curtain_sides=None, trough=None, layout=None, variant=None, roof=None):
    variant = variant or ('chef_table' if seed % 4 == 0 else 'standard')
    k = (seed - 1) % 3
    g = C.rng(seed, 'layout')
    P = dict(w=w or 5.0, d=d or 5.0, h=h or [3.6, 3.3, 4.0][k] * (1 if seed <= 4 else g.uniform(0.95, 1.05)),
             stilt=stilt or [0.85, 1.1, 0.7][k], curtain_sides=curtain_sides or 3,
             trough=True if trough is None else trough, variant=variant,
             layout=layout or ('long' if variant == 'chef_table' else C.cycle(seed, LAYOUTS)),
             roof=roof or 'hip', mid_chochin=(k == 1))
    return P


def build(lod, seed, w=None, d=None, h=None, stilt=None, curtain_sides=None, trough=None, layout=None, variant=None,
          roof=None, **_):
    P = params(seed, w, d, h, stilt, curtain_sides, trough, layout, variant, roof)
    W, D = P['w'], P['d']
    mb = genlib.MeshBuilder()
    M = dict(wood=mb.slot('hinoki', variant='dark_timber'), deck=mb.slot('hinoki', variant='wet_oiled'),
             lac=mb.slot('lacquer_dark', wear=0.15), walnut=mb.slot('hinoki', variant='walnut'),
             iron=mb.slot('iron', wear=0.2), stone=mb.slot('basalt_wet', wetness=0.7),
             tile=mb.slot('kawara'), roof_d=mb.slot('lacquer_dark', wear=0.1), bronze=mb.slot('bronze', variant='smooth'),
             paper=mb.slot('lantern_paper', tint=(1.0, 0.05, 0.02), emissive_level=0.5), cap=mb.slot('lacquer_black'),
             andon=mb.slot('lantern_andon', emissive_level=0.9), cushion=mb.slot('noren'),
             tenmoku=mb.slot('ceramic', variant='tenmoku'), celadon=mb.slot('ceramic', variant='celadon'))
    lights = []
    hw, hd = W / 2, D / 2
    # ---------------- vertical layout
    FH = 0.38
    z_b0 = P['stilt']                        # girder underside
    z_b1 = z_b0 + 0.3
    z_d = z_b1 + 0.06                        # deck top
    z_k0 = z_d + P['h'] * 0.66               # keta underside
    z_k1 = z_k0 + 0.28
    gut = 0.3                                # gutter width along curtain edges
    sides = ['+y', '+x', '-x'][:P['curtain_sides']]
    # ---------------- footings + stilts (3 x 3)
    xs = [-hw + 0.2, 0.0, hw - 0.2]
    ys = [-hd + 0.2, 0.0, hd - 0.2]
    rf = C.rng(seed, 'footings')
    for x in xs:
        for y in ys:
            if lod <= 2:
                KK.stone_footing(mb, lod, rf, (x, y, 0), 0.6, 0.6, FH, M['stone'], courses=1, lod2_course=False, npts1=6, npts0=8)
                KK.post(mb, lod, x, y, FH - 0.02, z_b0 + 0.01, 0.28, M['wood'])
            elif abs(x) > 0.1 and abs(y) > 0.1:      # LOD3: corner stilts only (footing + stilt in one box)
                mb.box((x, y, (z_b0 + 0.01) / 2), (0.4, 0.4, z_b0 + 0.01), M['wood'])
    # X braces under the deck on the +-x sides and the +y side (sheet side view)
    if lod <= 2:
        for x in (xs[0], xs[2]):
            for (ya, yb) in ((ys[0], ys[1]), (ys[1], ys[2])):
                KK.brace(mb, lod, (x, ya + 0.15, FH + 0.05), (x, yb - 0.15, z_b0 - 0.05), 0.1, M['wood'])
                if lod <= 1:
                    KK.brace(mb, lod, (x, yb - 0.15, FH + 0.05), (x, ya + 0.15, z_b0 - 0.05), 0.1, M['wood'])
    # ---------------- girders (along y, beam ends project) + perimeter fascia
    for x in (xs if lod <= 2 else []):
        KK.beam_y(mb, lod, -hd - 0.15, hd + 0.15, x, z_b0, z_b0 + 0.22, 0.26, M['wood'])
        if lod == 0:
            for s in (-1, 1):
                mb.box((x, s * (hd + 0.155), z_b0 + 0.11), (0.27, 0.012, 0.23), M['bronze'])
    for y in (ys if lod <= 2 else []):
        KK.beam_x(mb, lod, -hw, hw, y, z_b0 + 0.22, z_b1, 0.2, M['wood'])
    if lod >= 3:                                  # one platform block: girders + deck
        mb.box((0, 0, (z_b0 + z_d) / 2), (W + 0.2, D + 0.2, z_d - z_b0), M['wood'])
    for s in ((-1, 1) if lod <= 1 else ()):
        KK.timber(mb, lod, (0, s * (hd - 0.04), z_b1 - 0.02), (W, 0.08, 0.16), M['wood'], 0.01)
        KK.timber(mb, lod, (s * (hw - 0.04), 0, z_b1 - 0.02), (0.08, D - 0.16, 0.16), M['wood'], 0.01)
    # ---------------- deck boards + floor gutter on the curtain sides
    x0 = -hw + (gut if '-x' in sides else 0.0)
    x1 = hw - (gut if '+x' in sides else 0.0)
    y1 = hd - (gut if '+y' in sides else 0.0)
    y0 = -hd
    if lod >= 3:
        pass
    elif lod <= 1:
        bw_, gap = 0.18, 0.012
        n = int((y1 - y0) / (bw_ + gap))
        pitch = (y1 - y0) / n
        for i in range(n):
            yc = y0 + (i + 0.5) * pitch
            mb.box(((x0 + x1) / 2, yc, z_d - 0.03), (x1 - x0, pitch - gap, 0.06), M['deck'])
    else:
        mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z_d - 0.03), (x1 - x0, y1 - y0, 0.06), M['deck'])
    gut_runs = []
    for sd in sides:
        if sd == '+y':
            a, b, c, L, ax = (-hw, hd - gut / 2), (hw, hd - gut / 2), (0, hd - gut / 2), W, 'x'
        elif sd == '+x':
            a, b, c, L, ax = (hw - gut / 2, -hd), (hw - gut / 2, hd), (hw - gut / 2, 0), D, 'y'
        else:
            a, b, c, L, ax = (-hw + gut / 2, -hd), (-hw + gut / 2, hd), (-hw + gut / 2, 0), D, 'y'
        sz = (L, gut, 0.05) if ax == 'x' else (gut, L, 0.05)
        if lod <= 2:
            mb.box((c[0], c[1], z_d - 0.12), sz, M['lac'])                     # channel floor
        if lod <= 2:                                                            # grate bars along the run
            nb = C.lod_pick(lod, 4, 3, 1)
            for j in range(nb):
                o = -gut / 2 + gut * (j + 0.5) / nb
                if ax == 'x':
                    mb.box((c[0], c[1] + o, z_d - 0.035), (L, 0.025, 0.03), M['iron'])
                else:
                    mb.box((c[0] + o, c[1], z_d - 0.035), (0.025, L, 0.03), M['iron'])
        gut_runs.append(dict(a=[round(a[0], 3), round(a[1], 3)], b=[round(b[0], 3), round(b[1], 3)], z=round(z_d - 0.07, 3)))
    # ---------------- room posts (corners + mid-sides) and keta
    rp = [(x, y) for x in (-hw + 0.13, 0.0, hw - 0.13) for y in (-hd + 0.13, 0.0, hd - 0.13) if not (x == 0 and y == 0)]
    for x, y in rp:
        if lod <= 2 or (x != 0 and y != 0):
            KK.post(mb, lod, x, y, z_d - 0.06, z_k1, 0.24, M['wood'])
    for s in ((-1, 1) if lod <= 2 else ()):
        KK.beam_x(mb, lod, -hw - 0.1, hw + 0.1, s * (hd - 0.13), z_k0, z_k1, 0.22, M['wood'])
        KK.beam_y(mb, lod, -hd + 0.02, hd - 0.02, s * (hw - 0.13), z_k0 + 0.04, z_k1 + 0.04, 0.22, M['wood'])
    # entry-side head rail (nageshi) + low rails either side of the 1.6 m opening
    if lod <= 2:
        for sx in (-1, 1):
            xa, xb = sx * 0.8, sx * (hw - 0.13)
            KK.beam_x(mb, lod, min(xa, xb), max(xa, xb), -hd + 0.13, z_d + 0.5, z_d + 0.58, 0.09, M['deck'])
            KK.post(mb, lod, xa, -hd + 0.13, z_d - 0.03, z_d + 0.62, 0.11, M['wood'])
            if lod <= 1:
                KK.beam_x(mb, lod, min(xa, xb), max(xa, xb), -hd + 0.13, z_d + 0.2, z_d + 0.25, 0.05, M['deck'])
            cen = KK.andon(mb, dict(iron=M['iron'], paper=M['andon']), lod, (xa, -hd + 0.13, z_d + 0.62), size=0.18, height=0.3)
            lights.append(C.light_entry(cen, color_k=2200, watts=10))
    # ---------------- ceiling trough (per bay, under the keta, on the curtain sides) + curtain data
    curtains = []
    z_t1 = z_k0
    z_t0 = z_k0 - 0.2
    for sd in sides:
        if sd == '+y':
            bays = [((-hw + 0.25, hd - 0.13), (-0.12, hd - 0.13)), ((0.12, hd - 0.13), (hw - 0.25, hd - 0.13))]
        elif sd == '+x':
            bays = [((hw - 0.13, -hd + 0.25), (hw - 0.13, -0.12)), ((hw - 0.13, 0.12), (hw - 0.13, hd - 0.25))]
        else:
            bays = [((-hw + 0.13, -hd + 0.25), (-hw + 0.13, -0.12)), ((-hw + 0.13, 0.12), (-hw + 0.13, hd - 0.25))]
        for a, b in bays:
            if P['trough'] and lod >= 3:
                if a == bays[0][0]:              # LOD3: one trough box per side
                    a3, b3 = bays[0][0], bays[1][1]
                    mb.box(((a3[0] + b3[0]) / 2, (a3[1] + b3[1]) / 2, z_t0 + 0.1),
                           (abs(b3[0] - a3[0]) + 0.26, abs(b3[1] - a3[1]) + 0.26, 0.2), M['walnut'])
            elif P['trough']:
                KK.water_trough(mb, lod, [(a[0], a[1], z_t0), (b[0], b[1], z_t0)], 0.26, 0.2, 0.035, M['walnut'])
                if lod <= 1:                    # hangers to the keta
                    for t in (0.2, 0.8):
                        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                        mb.box((p[0], p[1], z_t1 - 0.01), (0.05 if sd != '+y' else 0.3, 0.3 if sd != '+y' else 0.05, 0.03), M['bronze'])
            curtains.append(dict(a=[round(a[0], 3), round(a[1], 3)], b=[round(b[0], 3), round(b[1], 3)],
                                 z_top=round(z_t0 + 0.02, 3), z_bottom=round(z_d - 0.07, 3), side=sd))
    # ---------------- chochin at the corners (iron arms off the corner posts) [+ front-mid on some seeds]
    cho_m = dict(paper=M['paper'], cap=M['cap'], ink=M['cap'], cord=M['iron'])
    spots = [(sx * (hw - 0.13), sy * (hd - 0.13), sx, sy) for sx in (-1, 1) for sy in (-1, 1)]
    if P['mid_chochin']:
        spots.append((0.0, hd - 0.13, 0, 1))
    for x, y, sx, sy in spots:
        ax_ = (sx * 0.3, sy * 0.3) if sx else (0, 0.3)
        za = z_k0 - 0.06
        if lod >= 3 and not sx:
            continue
        if lod <= 2:
            mb.box((x + ax_[0] / 2, y + ax_[1] / 2, za), (abs(ax_[0]) + 0.04, abs(ax_[1]) + 0.04, 0.035), M['iron'])
        cen = KK.chochin(mb, cho_m, lod, (x + ax_[0], y + ax_[1], za), r=0.2, h=0.52, cord=0.1, lod3_caps=False,
                         segs={0: 12, 1: 8, 2: 5, 3: 4}, crest_lod=0, cord_lod=1)
        lights.append(C.light_entry(cen, color_k=1900, watts=25, color=[1.0, 0.25, 0.12]))
    # ---------------- table(s), cushions, tea set, table aqueduct
    gl = C.rng(seed, 'table')
    yc_room = (y0 + y1) / 2 + (0.35 if P['variant'] == 'chef_table' else 0.0)
    if P['layout'] == 'long':
        tables = [(0.0, yc_room, 2.6, 0.95, 3)]
    elif P['layout'] == 'twin':
        tables = [(-1.0, yc_room, 1.35, 0.85, 2), (1.0, yc_room, 1.35, 0.85, 2)]
    else:
        tables = [(0.0, yc_room, 1.5, 1.5, 2)]
    th = 0.36
    for tx, ty, tl, tw, nseat in tables:
        if lod >= 3:
            mb.box((tx, ty, z_d + th / 2), (tl, tw, th), M['lac'])
            continue
        KK.timber(mb, lod, (tx, ty, z_d + th - 0.025), (tl, tw, 0.05), M['lac'], 0.01)
        if lod == 2:
            mb.box((tx, ty, z_d + (th - 0.05) / 2), (tl * 0.8, tw * 0.8, th - 0.05), M['deck'])
        elif lod <= 1:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box((tx + sx * (tl / 2 - 0.1), ty + sy * (tw / 2 - 0.1), z_d + (th - 0.05) / 2), (0.08, 0.08, th - 0.05), M['deck'])
            if lod <= 1:
                mb.box((tx, ty, z_d + th - 0.08), (tl - 0.12, tw - 0.12, 0.05), M['deck'])      # apron frame
        else:
            mb.box((tx, ty, z_d + (th - 0.05) / 2), (tl * 0.8, tw * 0.8, th - 0.05), M['deck'])
        # cushions: both long sides (square table: all four sides)
        seats = []
        for i in range(nseat):
            u = -tl / 2 + (i + 0.5) * tl / nseat
            seats += [(tx + u, ty + tw / 2 + 0.38, 0), (tx + u, ty - tw / 2 - 0.38, math.pi)]
        if P['layout'] == 'square':
            seats += [(tx + tl / 2 + 0.38, ty, -math.pi / 2), (tx - tl / 2 - 0.38, ty, math.pi / 2)]
        if P['variant'] == 'chef_table':
            seats = [s for s in seats if s[1] > ty]
        for sx, sy, yaw in seats:
            if lod <= 2:
                KK.zabuton(mb, lod, (sx, sy, z_d), 0.52, M['cushion'], yaw=gl.uniform(-0.12, 0.12))
            if lod <= 0:                         # tea bowl at each place
                px = sx + (ty - sy) * 0.0
                py = sy + (0.42 if sy < ty else -0.42) * (1 if abs(sy - ty) > 0.2 else 0)
                if abs(sx - tx) > tl / 2:
                    px = sx + (-0.42 if sx > tx else 0.42)
                    py = sy
                KK.bowl(mb, lod, (px, py, z_d + th), 0.06, 0.06, M['tenmoku'])
        if lod <= 1 and tl > 1.2:               # table aqueduct (lookbook 08): slim trough on 3 trestles
            L = tl * 0.62
            zt = z_d + th + 0.14
            KK.water_trough(mb, lod, [(tx - L / 2, ty, zt), (tx + L / 2, ty, zt)], 0.09, 0.06, 0.015, M['walnut'])
            for u in (-L / 2 + 0.06, 0.0, L / 2 - 0.06):
                mb.box((tx + u, ty, z_d + th + 0.07), (0.04, 0.14, 0.14), M['walnut'])
            if lod == 0:
                C.lathe(mb, [(0.05, 0), (0.075, 0.06), (0.06, 0.13), (0.025, 0.15), (0.0, 0.16)], 12, M['celadon'],
                        base=(tx + L / 2 + 0.16, ty + 0.05, z_d + th))            # teapot
    if P['variant'] == 'chef_table' and lod <= 2:
        # L-shaped chef counter by the entry with a griddle; stock pot and bowls
        cx, cy = 0.0, -hd + 0.95
        KK.timber(mb, lod, (cx, cy, z_d + 0.43), (2.2, 0.6, 0.86), M['wood'], 0.012)
        KK.timber(mb, lod, (cx, cy, z_d + 0.88), (2.3, 0.68, 0.05), M['lac'], 0.008)
        mb.box((cx - 0.3, cy, z_d + 0.915), (0.9, 0.45, 0.025), M['iron'])
        if lod <= 1:
            KK.pot(mb, lod, (cx + 0.75, cy, z_d + 0.905), 0.16, 0.24, M['iron'])
            KK.bowl_stack(mb, lod, (cx + 0.35, cy + 0.12, z_d + 0.905), 0.08, 0.07, 4, M['tenmoku'])
    # ---------------- roof (dry run, then lift so its wall plate sits on the keta)
    mats = dict(tile=M['tile'], ridge=M['tile'], wood=M['wood'], wood_d=M['roof_d'], iron=M['iron'])
    budget = genlib.budget_of(ASSET)
    rb = int(budget[lod] * C.lod_pick(lod, 0.34, 0.22, 0.25, 0.2)) if budget else None
    vlay = mb.bm.verts.layers.int.get('_vold') or mb.bm.verts.layers.int.new('_vold')
    for v in mb.bm.verts:
        v[vlay] = 1
    eave = 0.45
    info = KR.roof_into(mb, mats, lod, P['roof'], hw + eave - 0.1, hd + eave - 0.1, z_e=0.0, pitch=12.0, eave=eave, eave_s=eave,
                        up=0.12, tp=0.22, budget=rb)
    if info['notes']:
        print(f'{ASSET} LOD{lod} s{seed} roof resolution fallback: {info["notes"]}')
    rv = [v for v in mb.bm.verts if v[vlay] == 0]
    dz = (z_k1 + 0.04) - info['wall_top']
    if lod >= 3:                                  # LOD3 roof has no soffit/fascia: seat its eave on the posts
        dz = (z_k1 - 0.02) - min(v.co.z for v in rv)
    for v in rv:
        v.co.z += dz
    C.centre_base(mb, centre_x=True, centre_y=True)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=lights, kz_water_curtains=curtains, kz_floor_gutter=gut_runs,
                     kz_anim={'type': 'sim', 'fx': 'fx_water_curtain', 'part_on_approach': True, 'part_radius': 1.6,
                              'curtains': len(curtains)},
                     kz_entry=dict(side='-y', width=1.6), kz_deck_z=round(z_d, 3),
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o
