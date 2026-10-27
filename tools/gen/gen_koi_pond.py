"""Koi pond well (koi_pond): a deeper round well sunk under the b1_junction_w corridor water, ringed by low rim
stones that break the surface, with an underwater glow. Fish are the separate koi_fish asset.

Concept: refs/gen/sheet-mod-water.png #4 (label: diameter 6 m; section shows a ring of dark craggy flat-topped
basalt blocks 0.4-0.7 m across standing ~0.2-0.35 m above the water, a stone-lined well wall, rounded cobbles
on the floor, bright teal water lit from below), lookbook/img/33-plan-b1-thermal.jpg (G3-4: a round pond
~6 m across set into the corridor water east of the mirror pool, rim stones round it, koi).
Measured targets (sheet panel 4 section, 1 m bar = 102 px): rim stones 0.35-0.55 m radius, 0.15-0.30 m above
water, water ~1.0-1.2 m deep in the section, overall 6.0 m.
Built: well water radius r 1.8-3.0 (default 2.25-2.45 by seed so the stones land inside 6 m), well depth
0.8-1.5 below the corridor bed (default 0.95-1.25), corridor water 0.22 m over the corridor bed, rim stones
tops 0.10-0.40 m above water with real gaps between some (the corridor water flows over the lip), a 0.6 m
apron of corridor bed round the lip, 5-8 rounded cobbles on the floor (the only smooth stones: the concept's
river cobbles under water), caustics glow decal on the floor.

Proxy 6 x 6 x 0.3 counts only what stands above the corridor bed; the well itself goes 0.8-1.5 m below it,
so the built height is ~1.3-1.6 m (bed at z = 0). Proposed proxy: h 1.6 with "embed": 1.25 (well below grade).

Parameters (build(lod, seed, ...)):
  r          1.8-3.0   well water radius at the lip
  depth      0.8-1.5   well depth below the corridor bed (kz_grade_z)
  water      0.15-0.3  corridor water depth over its bed (water level = grade + water)
  stones     rim stone count (default seeded 13-19 for r 2.3)
  light      True/False underwater light (kz_lights entry; the decal stays)
  feature    'plain' | 'basking' | 'ledge' (default C.cycle(seed)): a big flat basking stone reaching over the
             water, or a submerged sitting ledge ring 0.4 m below the lip
Seeds change: r, depth, outline wobble and aspect, stone count, size mix, spacing and gaps, which stones
lean in, cobble layout, the feature above.
Custom props: kz_water_level, kz_water_outline (the well lip; the corridor water continues over it),
kz_grade_z (corridor bed), kz_grade_outline, kz_lights, kz_fish_volume {centre, r, z0, z1} for koi_fish
swimming, kz_params. Pivot: well centre, well floor z = 0.
Materials: wall + apron basalt_wet, rim stones basalt_wet (wetter tops), floor stepping_stone, cobbles
stepping_stone (worn), glow caustics_decal. water_still is the runtime surface (not built).
LODs (same layout): LOD1 coarser loops, 6-sided stones, cobbles as boxes-free low hulls; LOD2 stones become a
lumpy rim band following the stone heights (gaps kept as dips), cobbles dropped; LOD3 one section ring.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_pool_shell as K

ASSET = 'koi_pond'
FEATURES = ['deep round well under the corridor water', 'low rim stones breaking the surface', 'underwater glow']
FEATS = ['plain', 'basking', 'ledge']
TINT = (0.62, 0.62, 0.68)


def build(lod, seed, r=None, depth=None, water=None, stones=None, light=True, feature=None):
    feature = feature or C.cycle(seed, FEATS)
    g = C.rng(seed, 'layout')
    R = r if r is not None else g.uniform(2.25, 2.45)
    Dw = depth if depth is not None else g.uniform(0.95, 1.25)
    wd = water if water is not None else 0.22
    aspect = g.uniform(1.0, 1.1)
    wob = g.uniform(0.02, 0.05)
    grade = Dw
    zw = grade + wd
    W0 = K.fp_round(R, aspect=aspect, r=C.rng(seed, 'outline'), wob=wob, n=160)
    per = K.perimeter(W0)
    Pf = K.resample(W0, 240)
    cf = K.cumlen(Pf)
    rr = C.rng(seed, 'stones')
    target_n = stones or rr.randint(13, 19)
    mean_gap = per / target_n
    sizes = [(3, 0.26, 0.34), (4, 0.36, 0.46), (2, 0.48, 0.56)]
    avg = 0.40
    ov = 1 - mean_gap / (2 * avg)
    rocks = K.rock_layout(Pf, cf, rr, sizes, (-0.12, 0.08), grade - 0.18,
                          lambda r_, q: zw + 0.1 + (r_ - 0.26) * 0.6 + q.uniform(0.0, 0.12),
                          overlap=(ov - 0.18, ov + 0.12))
    basking = None
    if feature == 'basking':
        rb = C.rng(seed, 'basking')
        basking = dict(s=rb.uniform(0, cf[-1]), u=-0.05, rx=0.75, ry=0.95, z0=grade - 0.18, ztop=zw + 0.1, salt=99, rot=0.0)
        rocks = [k for k in rocks if abs(K.sdist(cf, k['s'], basking['s'])) > 0.9] + [basking]
        rocks.sort(key=lambda k: -(k['rx'] * k['ry'] * (k['ztop'] - k['z0'])))
    rc = C.rng(seed, 'cobbles')
    cobbles = []
    for i in range(rc.randint(5, 8)):
        a = rc.uniform(0, 2 * math.pi); d = math.sqrt(rc.uniform(0.05, 0.75)) * (R - 0.45)
        s = rc.uniform(0.18, 0.32)
        cobbles.append(((d * math.cos(a), d * math.sin(a)), (s * 2, s * rc.uniform(1.4, 1.9), s * rc.uniform(0.8, 1.1)), rc.uniform(0, 3.14), i))
    cobbles.sort(key=lambda c: -c[1][0] * c[1][1])

    mb = genlib.MeshBuilder()
    m_wall = mb.slot('basalt_wet', wetness=0.9, tint=TINT)
    m_apron = mb.slot('stepping_stone', wear=0.25, tint=TINT)
    m_rock = mb.slot('basalt_wet', wetness=0.8, tint=TINT)
    m_bed = mb.slot('stepping_stone', wear=0.2, tint=(0.75, 0.78, 0.8))
    m_cob = mb.slot('stepping_stone', wear=0.5, tint=(0.7, 0.74, 0.72))
    m_glow = mb.slot('caustics_decal', emissive_level=0.8)

    N = C.lod_pick(lod, 84, 40, 20, 10)
    P = K.resample(W0, N)
    nrm = K.normals(P)
    cum = K.cumlen(P)
    sc = cum[-1] / cf[-1]
    rk = [dict(k, s=k['s'] * sc) for k in rocks]
    shelf = feature == 'ledge'
    # wall profile: lip -> bowl, (u from the lip outline, z)
    if lod == 0:
        wall = [(0.0, grade), (-0.04, grade - 0.06), (-0.1, grade - 0.35 * Dw)]
        if shelf:
            wall += [(-0.12, grade - 0.42), (-0.42, grade - 0.44), (-0.45, grade - 0.52)]
        wall += [(-0.18 - 0.3 * shelf, 0.35 * Dw), (-0.3 - 0.3 * shelf, 0.08), (-0.5 - 0.3 * shelf, 0.0)]
    elif lod == 1:
        wall = [(0.0, grade), (-0.08, grade - 0.3 * Dw)]
        if shelf:
            wall += [(-0.12, grade - 0.42), (-0.43, grade - 0.46)]
        wall += [(-0.22 - 0.3 * shelf, 0.25 * Dw), (-0.5 - 0.3 * shelf, 0.0)]
    elif lod == 2:
        wall = [(0.0, grade)] + ([(-0.12, grade - 0.42), (-0.43, grade - 0.46)] if shelf else []) + [(-0.5 - 0.3 * shelf, 0.0)]
    else:
        wall = [(-0.05, zw - 0.12), (-0.5 - 0.3 * shelf, 0.0)]
    if lod <= 2:
        rings = [(0.6, grade)] + wall
        K.shell(mb, P, rings, [m_apron] + [m_wall] * (len(wall) - 1), bed_mi=m_bed, nrm=nrm)
    else:
        env = K.rock_envelope(P, cum, rk, zw - 0.05)
        rings = [(0.6, grade), (0.15, env)] + wall
        K.shell(mb, P, rings, [m_rock, m_rock, m_wall], bed_mi=m_bed, nrm=nrm)
    if lod <= 2:
        gl = K.loop_verts(mb, K.offset(P, -0.55 - 0.3 * shelf, nrm), 0.01)
        K.fill(mb, gl, m_glow)
    # rim stones
    if lod <= 1:
        K.build_rocks(mb, P, cum, rk, m_rock, seed, lod, nside=(8, 6), bands=(3, 2), crag=0.12)
    elif lod == 2:
        env = K.rock_envelope(P, cum, rk, zw - 0.05)
        K.shell(mb, P, [(-0.2, grade - 0.1), (-0.08, env), (0.22, env), (0.5, grade)], [m_rock] * 3, nrm=nrm)
    # floor cobbles: the few smooth stones (river cobbles under water)
    if lod <= 1:
        for (x, y), size, rot, i in cobbles:
            q = C.rng(seed, 'cob%d' % i)
            if lod == 0:
                C.rounded_rock(mb, (x, y, size[2] * 0.38), size, m_cob, q, cuts=1, round_r=size[2] * 0.45, amp=0.015, rot_z=rot, clamp_z=0.0)
            else:
                C.hull_rock(mb, (x, y, 0.0), (size[0] / 2, size[1] / 2, size[2] * 0.8), m_cob, q, npts=8, ground=0.0, rot=rot)

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    lights = [C.light_entry((dx, dy, 0.35 + dz), color_k=6000, watts=20, kind='point', underwater=True)] if light else []
    Wout = K.resample(W0, 64)
    sh = [(x + dx, y + dy) for x, y in Wout]
    C.water_props(o, zw + dz, outline_xy=sh, kz_grade_z=round(grade + dz, 4),
                  kz_grade_outline=[[round(x + dx, 3), round(y + dy, 3)] for x, y in K.offset(Wout, 0.6)])
    C.set_json_props(o, kz_lights=lights, kz_fish_volume=dict(centre=[round(dx, 3), round(dy, 3)], r=round(R - 0.35, 3),
                                                               z0=round(0.2 + dz, 3), z1=round(zw - 0.12 + dz, 3)),
                     kz_params=dict(r=round(R, 3), depth=round(Dw, 3), water=wd, stones=len(rocks), feature=feature))
    return o
