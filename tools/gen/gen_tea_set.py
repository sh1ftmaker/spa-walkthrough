"""Tea set (tea_set): black iron tetsubin with a bail handle, small stoneware cups, a hinoki tray; a sake
variant with tokkuri flasks and choko cups. Placed on suite tables, the moon deck and the wave-grotto
side tables (b3_wave, s_moon, suite_1a..4c).

Targets (no scale sheet shows the set; measured off the lookbook and sized from real objects):
  * lookbook 21 (private suite, crop .scratch/op22/c21.png): kettle on a long low rectangular tray with two
    cups on the left; kettle body w:h ~ 1 : 0.62 (squat, round belly), lid with a knob, a short upturned
    spout, an iron bail handle arching ~0.7 body heights above the lid. Tray ~2x the kettle width, thin rim.
  * lookbook 20 (wave grotto, crop .scratch/op22/c20.png): the same kettle on a round dark saucer on a side
    table, no cups (seed 3 style).
  * lookbook 22 (brand board): the speckled stoneware yunomi on a round coaster (seed 3 cups).
  * Row: kettle r 0.08-0.12 m, cups 1-4, tray on/off, sake flask variant; dims 0.4 x 0.3 x 0.25 m
    (= proxy). Built: kettle R 0.085-0.10 (body diameter 0.17-0.20, body height 1.2 R, lid + knob to
    1.18 Hb, handle crown ~2.4 R (1.2 body widths, lookbook 20/21) above the tray floor, capped so the set stays <= 0.25 m tall);
    yunomi R 0.030-0.034 x H 0.055-0.065; tokkuri R 0.036-0.04 x H 0.13-0.15; choko R 0.024 x H 0.03;
    tray 0.36 x 0.25 x 0.027 with a 9 mm rim wall.

Parts (all present at LOD0): tetsubin body (one closed lathe solid with turned foot, shoulder, lid step,
domed lid and button knob), spout with a rolled lip, two lugs, bail handle with knuckles; cups (closed
solids with inner wall, kzgeo_tableware.cup); tray (rounded-rect loft with rim and floor); saucer
(round iron shiki) and hinoki coasters in the saucer style; tokkuri + choko in the sake style.

Styles (cycle with the seed):  1 'tea'    kettle + 2 cups on the tray (lookbook 21)
                               2 'sake'   2 tokkuri + 3 choko on the tray
                               3 'saucer' kettle on a round iron saucer, 1-2 cups on coasters, no tray
                                          (lookbook 20 / 22)
Seeds change: style, kettle radius and belly height, kettle yaw (spout to the viewer's right, 175-215 deg),
cup count/glaze/height, flask count.

Parameters (build kwargs)
  style     'tea' | 'sake' | 'saucer'   (default: cycles with the seed)
  kettle_r  0.08-0.12 m                 (default seeded 0.085-0.10; >0.105 drops cups to 2 on the tray)
  cups      1-4                         (default seeded per style)
  tray      True | False                (default: True except 'saucer')
  glaze     'celadon' | 'tenmoku' | 'white' (cups; default seeded)

Materials: iron (kettle, saucer), ceramic celadon/tenmoku/white (cups, flasks), hinoki walnut (tray,
coasters). Animation: none. Steam: obj['kz_fx'] = [{'fx': 'fx_steam', 'pos': spout tip}] (tea styles).
Lighting: lightmap.

LOD: LOD1 keeps every part at fewer segments (no handle knuckles, no spout lip); LOD2 keeps kettle, spout,
handle, cups (simplified outer profile), tray; LOD3 kettle + handle + tray (or flasks + tray).
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_tableware as P
import kzgeo_tea_set as T

ASSET = 'tea_set'
FEATURES = ['black iron tetsubin', 'bail handle over the lid', 'small stoneware cups', 'hinoki tray']
STYLES = ['tea', 'sake', 'saucer']


def _cup(mb, x, y, z, R, H, mi, lod, segs):
    if lod >= 2:
        prof = [(0.0, 0.0), (R * 0.85, 0.0), (R, H), (R * 0.75, H * 0.97), (0.0, H * 0.85)]
    else:
        prof = P.cup(R, H, lod=lod)
    C.lathe(mb, prof, segs, mi, base=(x, y, z))


def build(lod, seed, style=None, kettle_r=None, cups=None, tray=None, glaze=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'kettle')
    R = max(0.08, min(0.12, kettle_r)) if kettle_r else g.uniform(0.085, 0.10)
    Hb = R * g.uniform(1.12, 1.28)
    yaw = math.radians(g.uniform(175, 215))       # spout to the viewer's right (lookbook 21), handle broadside
    gc = C.rng(seed, 'cups')
    n_cups = cups or {'tea': gc.choice([2, 2, 3]), 'sake': 3, 'saucer': gc.choice([1, 2])}[style]
    n_cups = max(1, min(4, n_cups))
    if R > 0.105 and style == 'tea':
        n_cups = min(n_cups, 2)
    cR, cH = gc.uniform(0.030, 0.034), gc.uniform(0.055, 0.065)
    glaze = glaze or C.cycle(seed, ['tenmoku', 'celadon', 'celadon', 'white', 'tenmoku'])   # 21 dark cups, 22 celadon
    gf = C.rng(seed, 'flasks')
    n_flasks = gf.choice([1, 2, 2])
    fR, fH = gf.uniform(0.036, 0.040), gf.uniform(0.13, 0.15)
    tray = (style != 'saucer') if tray is None else tray

    mb = genlib.MeshBuilder()
    m_iron = mb.slot('iron')
    m_cup = mb.slot('ceramic', variant=glaze)
    m_flask = mb.slot('ceramic', variant='white')
    m_wood = mb.slot('hinoki', variant='walnut', wear=0.1)

    TW, TD = 0.36, 0.25
    floor = 0.0
    if tray:
        if lod <= 1:
            rings = [(0.006, 0.0), (0.0, 0.006), (0.0, 0.024), (0.0025, 0.027), (0.0085, 0.027), (0.0105, 0.013)]
            if lod == 1:
                rings = [rings[0], rings[2], rings[4], rings[5]]
            T.rr_loft(mb, 0, 0, 0, TW, TD, 0.022, rings, m_wood, m=C.lod_pick(lod, 2, 1))
        elif lod == 2:
            T.rr_loft(mb, 0, 0, 0, TW, TD, 0.022, [(0.0, 0.0), (0.0, 0.027)], m_wood, m=1, cap_bottom=False)
        else:                                        # top + front + back faces only (6 tris)
            bm = mb.bm
            a = [bm.verts.new((x, y, z)) for z in (0.0, 0.022) for x, y in ((TW / 2, TD / 2), (-TW / 2, TD / 2), (-TW / 2, -TD / 2), (TW / 2, -TD / 2))]
            fs = [bm.faces.new((a[4], a[5], a[6], a[7])), bm.faces.new((a[1], a[0], a[4], a[5])[::-1]),
                  bm.faces.new((a[3], a[2], a[6], a[7]))]
            mb._tag(fs, m_wood)
        floor = 0.013 if lod <= 2 else 0.022

    tips = []
    if style in ('tea', 'saucer'):
        kx = -0.065 if tray else -0.07
        kz = floor
        if style == 'saucer':                        # round iron shiki under the kettle
            sR = R * 1.3
            if lod <= 2:
                prof = [(0.0, 0.0), (sR * 0.9, 0.0), (sR, 0.006), (sR * 0.96, 0.011), (sR * 0.8, 0.008), (0.0, 0.008)]
                if lod >= 1:
                    prof = [prof[0], prof[1], prof[3], prof[5]]
                C.lathe(mb, prof, C.lod_pick(lod, 20, 12, 7), m_iron, base=(kx, 0, 0))
            else:
                C.lathe(mb, [(sR, 0.008), (0.0, 0.008)], 5, m_iron, base=(kx, 0, 0), closed=False)
            kz = 0.008
        handle_h = min(2.4 * R, 0.25 - kz - 0.002)     # crown ~1.2 body widths (lookbook 20/21)
        first = T.mark_verts(mb)
        tip = T.kettle(mb, (0, 0, 0), R, Hb, 0.0, m_iron, lod, handle_h=handle_h)
        T.place_new(mb, first, (kx, 0.0, kz), yaw)
        from mathutils import Matrix, Vector
        tips.append(Matrix.Translation((kx, 0, kz)) @ Matrix.Rotation(yaw, 4, 'Z') @ Vector(tip))
        # cups: a 2 x 2 grid right of the kettle (tray), or loose on coasters (saucer)
        if lod <= 2:
            segs = C.lod_pick(lod, 14 if n_cups <= 2 else 10, 8 if n_cups <= 2 else 7, 5 if n_cups <= 2 else 4)
            if tray:
                spots = [(0.115, 0.055), (0.115, -0.055), (0.06, 0.075), (0.06, -0.075)][:n_cups]
                if n_cups == 1:
                    spots = [(0.11, 0.04)]
            else:
                spots = [(0.13, 0.07), (0.17, -0.04)][:n_cups]
            for i, (x, y) in enumerate(spots):
                h = cH * (1.0 - 0.06 * (i % 2))
                cz = floor
                if not tray:                          # hinoki coaster under each loose cup
                    cprof = ([(0.0, 0.0), (cR * 1.45, 0.0), (cR * 1.5, 0.005), (cR * 1.45, 0.008), (0.0, 0.008)]
                             if lod == 0 else [(0.0, 0.0), (cR * 1.5, 0.0), (cR * 1.5, 0.008), (0.0, 0.008)])
                    C.lathe(mb, cprof, C.lod_pick(lod, 14, 8, 6), m_wood, base=(x, y, 0))
                    cz = 0.008
                _cup(mb, x, y, cz, cR, h, m_cup, lod, segs)
    else:                                            # sake: tokkuri flasks + choko cups
        fsegs = C.lod_pick(lod, 14, 9, 5, 4)
        fx = [(-0.10, 0.02), (-0.03, -0.04)][:n_flasks] if n_flasks == 2 else [(-0.07, 0.0)]
        for i, (x, y) in enumerate(fx):
            h = fH * (1.0 - 0.07 * i)
            allv, _ = C.lathe(mb, T.tokkuri_profile(fR, h, lod), fsegs, m_flask, base=(x, y, floor), closed=lod < 3)
            if lod == 3:
                ring = allv[-fsegs:]
                mb._tag([mb.bm.faces.new(ring)], m_flask)
        if lod <= 2:
            segs = C.lod_pick(lod, 12, 8, 4)
            for i, (x, y) in enumerate([(0.07, 0.06), (0.12, -0.02), (0.06, -0.07), (0.13, 0.07)][:n_cups]):
                _cup(mb, x, y, floor, 0.024, 0.030, m_cup, lod, segs)

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    o = genlib.finish(o)
    if tips:
        t = tips[0]
        C.set_json_props(o, kz_fx=[dict(fx='fx_steam', pos=[round(t.x + dx, 4), round(t.y + dy, 4), round(t.z + dz, 4)])])
    C.set_json_props(o, kz_params=dict(style=style, kettle_r=round(R, 3), cups=n_cups, tray=tray, glaze=glaze))
    return o
