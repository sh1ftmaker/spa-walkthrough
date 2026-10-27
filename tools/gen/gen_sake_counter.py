"""Sake counter (sake_counter) for the Tsukimi moon deck (s_moon): a short hinoki counter with a stone hearth
built into one bay, an iron kettle steaming on a trivet over a spring-heated ember bed, sake flasks and
cups on the top.

Targets
  * lookbook 30 (summit plan) shows the moon deck only at plan scale (H2, ~2 px per 0.3 m): no detail
    of the counter can be measured there, so the build follows the row and real bar-counter sizes.
  * Row: w 2-3 m, h 0.9 m, d 0.8 (proxy 3 x 0.8 x 1.0). Built: counter top 0.90 m (hinoki slab 60 mm,
    rounded 8 mm edges, 0.12 m front overhang for knees), body depth 0.68 m, a 0.08 m recessed plinth
    (set back 0.05 m), hearth bay 0.66-0.74 m wide in basalt: 3 courses of hewn blocks with 12 mm
    chamfers, a 70 mm stone coping flush with the top, and a 0.16 m deep pit (opening ~0.42 x 0.54).
    Kettle (tetsubin, kzgeo_tea_set): R 0.12, body 0.14 m, standing on an iron gotoku so the spout tip
    clears the coping; the handle crown is capped at 1.04 m (inside the 1.0 m proxy + 5 %).
  * Sake: tokkuri R 0.04 x H 0.14 (white / tenmoku), choko cups R 0.024 x H 0.03, on the hinoki top.

Parts (all at LOD0): top slab(s), front boards with chamfered joints (or frame-and-panel), back panel
(staff side), recessed plinth, hearth blocks, stone coping with pit, ember bed (lava, emissive), gotoku,
kettle (lid, knob, spout, lugs, bail handle), flasks, cups.

Styles / seeds (cycle):  1 hearth at the viewer's right end, w 3.0, vertical boards, 4 flasks
                         2 hearth in the centre, w 2.5, wide boards, 3 flasks
                         3 hearth at the viewer's left end, w 2.1, frame-and-panel front, 2 flasks
Seeds also change: board width, block course heights and joints, flask/cup layout.

Parameters (build kwargs)
  w        2.0-3.0 m         (default by style)
  h        0.85-0.95 m       (default 0.90)
  hearth   'right' | 'centre' | 'left' | None (no hearth)
  front    'boards' | 'panels'
  flasks   0-6               (default by style; cups = flasks)

Materials: hinoki wet_oiled (top), hinoki dark_timber (front, back, plinth), basalt_dry (hearth blocks,
coping), lava emissive_level 0.55 (ember bed), iron (kettle, gotoku), ceramic white / tenmoku (flasks),
ceramic celadon (cups). Animation: none. Steam: obj['kz_fx'] fx_steam at the spout tip and over the pit.
Lighting: lightmap; obj['kz_lights'] = one warm point light in the pit (ember glow).

LOD: LOD1 every part at fewer segments, boards kept, blocks unbevelled, one ember slab; LOD2 counter as
boxes (top, body, plinth), hearth block + coping ring, kettle + handle, flasks (low lathes), no cups;
LOD3 one two-material box + kettle with handle.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_sake_counter as K
import kzgeo_tableware as P
import kzgeo_tea_set as T

ASSET = 'sake_counter'
FEATURES = ['short hinoki counter', 'stone hearth with glowing pit', 'steaming iron kettle', 'sake flasks']
STYLES = [dict(w=3.0, hearth='right', front='boards', bw=0.14, flasks=4),
          dict(w=2.5, hearth='centre', front='boards', bw=0.20, flasks=3),
          dict(w=2.1, hearth='left', front='panels', bw=0.0, flasks=2)]


def build(lod, seed, w=None, h=None, hearth='style', front=None, flasks=None):
    st = C.cycle(seed, STYLES)
    W = max(2.0, min(3.0, w or st['w']))
    H = max(0.85, min(0.95, h or 0.90))
    hearth = st['hearth'] if hearth == 'style' else hearth
    front = front or st['front']
    nf = st['flasks'] if flasks is None else max(0, min(6, flasks))
    D = 0.80
    OV = 0.12                                   # front overhang of the top
    TT = 0.06                                   # top thickness
    yb, yf = -D / 2, D / 2 - OV                 # body back / front faces
    PL, PS = 0.08, 0.05                         # plinth height / setback
    gh = C.rng(seed, 'hearth')
    Wh = gh.uniform(0.66, 0.74)
    courses = [gh.uniform(0.9, 1.1) for _ in range(3)]
    joints = [gh.uniform(0.35, 0.65) for _ in range(3)]
    gb = C.rng(seed, 'boards')
    bw = st['bw'] * gb.uniform(0.92, 1.08) if st['bw'] else 0.0
    gf = C.rng(seed, 'flasks')
    flask_glaze = [gf.choice(['white', 'white', 'tenmoku']) for _ in range(6)]

    mb = genlib.MeshBuilder()
    m_top = mb.slot('hinoki', variant='wet_oiled')
    m_body = mb.slot('hinoki', variant='dark_timber')
    m_stone = mb.slot('basalt_dry')
    m_ember = mb.slot('lava', emissive_level=0.55)
    m_iron = mb.slot('iron')
    m_white = mb.slot('ceramic', variant='white')
    m_dark = mb.slot('ceramic', variant='tenmoku')
    m_cup = mb.slot('ceramic', variant='celadon')

    # hearth bay position (viewer on +Y sees +X on the left: 'right' = -X end)
    if hearth:
        hx = {'right': -W / 2 + Wh / 2, 'left': W / 2 - Wh / 2, 'centre': 0.0}[hearth]
        hx0, hx1 = hx - Wh / 2, hx + Wh / 2
        spans = [(a, b) for a, b in ((-W / 2, hx0), (hx1, W / 2)) if b - a > 0.05]
    else:
        spans = [(-W / 2, W / 2)]

    # ------------------------------------------------------------------ LOD3: one box + kettle
    if lod == 3:
        K.box_faces(mb, -W / 2, W / 2, -D / 2, D / 2, 0, H, m_body, skip=('bottom',))
    else:
        for a, b in spans:
            # top slab
            if lod == 0:
                C.board(mb, ((a + b) / 2, 0, H - TT / 2), (b - a, D, TT), m_top, bevel=0.008, segs=2)
            else:
                K.box_faces(mb, a, b, -D / 2, D / 2, H - TT, H, m_top, skip=('bottom',) if lod == 2 else ())
            # body core (back panel and ends), plinth
            ends = ()
            K.box_faces(mb, a, b, yb, yf - (0.02 if lod <= 1 else 0.0), PL, H - TT, m_body, skip=('top', 'bottom') + ends)
            K.box_faces(mb, a + PS, b - PS, yb + PS, yf - PS, 0, PL, m_body, skip=('top', 'bottom'))
            if lod <= 1:
                if front == 'boards':
                    n = max(2, round((b - a) / bw))
                    for i in range(n):
                        x0 = a + (b - a) * i / n
                        x1 = a + (b - a) * (i + 1) / n
                        K.front_board(mb, x0 + 0.0015, x1 - 0.0015, yf - 0.03, yf, PL, H - TT,
                                      0.006 if lod == 0 else 0.0001, m_body)
                else:                           # frame and panel: stiles, rails, recessed panels
                    n = max(1, round((b - a) / 0.6))
                    sw = 0.07
                    for i in range(n + 1):
                        x = a + (b - a) * i / n
                        x = min(max(x, a + sw / 2), b - sw / 2)
                        K.box_faces(mb, x - sw / 2, x + sw / 2, yf - 0.02, yf, PL, H - TT, m_body, skip=('top', 'bottom', 'back'))
                    for z in (PL + 0.035, H - TT - 0.035):
                        K.box_faces(mb, a, b, yf - 0.02, yf, z - 0.035, z + 0.035, m_body, skip=('back',))
                    for i in range(n):              # panels sit 12 mm back (the body core face) with a 6 mm bead
                        x0 = a + (b - a) * i / n + sw / 2
                        x1 = a + (b - a) * (i + 1) / n - sw / 2
                        if lod == 0:
                            C.chamfered_bar(mb, ((x0 + x1) / 2, yf - 0.026, (H - TT + PL) / 2),
                                            (x1 - x0 - 0.02, 0.012, H - TT - PL - 0.16), m_body, ch=0.004, axis='z')

    # ------------------------------------------------------------------ hearth
    tips = []
    pit_z = H - 0.16
    if hearth:
        Dh = D - OV                                   # hearth body depth (flush with the boards)
        yc = (yb + yf) / 2
        if lod <= 1:
            # three courses of hewn blocks, staggered joints, faces 0-8 mm proud
            zc = PL * 0.0
            tot = sum(courses)
            z = 0.0
            hb = H - 0.07
            for ci in range(3):
                ch_ = hb * courses[ci] / tot
                j = hx0 + Wh * (joints[ci] if ci != 1 else 1 - joints[ci])
                for (a, b) in ((hx0, j), (j, hx1)):
                    pro = gh.uniform(0.0, 0.008)
                    if lod == 0:
                        C.board(mb, ((a + b) / 2, yc + pro / 2, z + ch_ / 2), (b - a - 0.006, Dh + pro, ch_ - 0.006),
                                m_stone, bevel=0.012, segs=1)
                    else:
                        K.box_faces(mb, a + 0.003, b - 0.003, yc - Dh / 2, yc + Dh / 2, z + 0.003, z + ch_ - 0.003, m_stone)
                z += ch_
            # coping with the pit
            m = C.lod_pick(lod, 2, 1)
            rings = [(0.0, -0.07), (0.0, -0.008), (0.006, 0.0), (0.124, 0.0), (0.13, -0.008), (0.13, -0.16)]
            if lod == 1:
                rings = [rings[0], rings[1], rings[3], rings[5]]
            T.rr_loft(mb, hx, 0, H, Wh, D, 0.03, rings, m_stone, m=m)
            # ember bed: low lumps of glowing crust on the pit floor
            if lod == 0:
                ge = C.rng(seed, 'embers')
                for k in range(6):
                    ex = hx + ge.uniform(-0.12, 0.12); ey = ge.uniform(-0.15, 0.15)
                    C.hull_rock(mb, (ex, ey, pit_z), (ge.uniform(0.05, 0.08), ge.uniform(0.04, 0.07), 0.03), m_ember, ge,
                                npts=8, ground=pit_z)
            else:
                K.box_faces(mb, hx - 0.15, hx + 0.15, -0.2, 0.2, pit_z, pit_z + 0.015, m_ember, skip=('bottom',))
            K.gotoku(mb, hx, 0, pit_z, pit_z + 0.05, 0.085, m_iron, lod)
        elif lod == 2:
            K.box_faces(mb, hx0, hx1, yc - Dh / 2, yc + Dh / 2, 0, H - 0.07, m_stone, skip=('bottom', 'top'))
            T.rr_loft(mb, hx, 0, H, Wh, D, 0.03, [(0.0, -0.07), (0.0, 0.0), (0.13, 0.0), (0.13, -0.16)], m_stone, m=0,
                      cap_bottom=False)
            K.box_faces(mb, hx - 0.15, hx + 0.15, -0.2, 0.2, pit_z, pit_z + 0.015, m_ember, skip=('bottom',))
        else:                                       # LOD3: stone front quad over the body box
            bm = mb.bm
            vs = [bm.verts.new(p) for p in ((hx0, D / 2 + 0.002, 0), (hx1, D / 2 + 0.002, 0), (hx1, D / 2 + 0.002, H),
                                            (hx0, D / 2 + 0.002, H))]
            mb._tag([bm.faces.new(vs)], m_stone)
        # kettle on the gotoku
        R, Hb = 0.12, 0.14
        base = pit_z + 0.05
        first = T.mark_verts(mb)
        tip = T.kettle(mb, (0, 0, 0), R, Hb, 0.0, m_iron, lod, handle_h=min(2.4 * R, 1.04 - base))
        yaw = math.radians(C.rng(seed, 'kettle').uniform(190, 215))
        T.place_new(mb, first, (hx, 0.0, base), yaw)
        from mathutils import Matrix
        tips.append(Matrix.Translation((hx, 0, base)) @ Matrix.Rotation(yaw, 4, 'Z') @ Vector(tip))

    # ------------------------------------------------------------------ flasks and cups on the top
    if lod <= 2 and nf:
        a, b = max(spans, key=lambda s: s[1] - s[0])
        L = b - a
        fsegs = C.lod_pick(lod, 10, 7, 5)
        for i in range(nf):
            x = a + L * (0.15 + 0.5 * (i + 0.5) / nf) if hearth != 'left' else b - L * (0.15 + 0.5 * (i + 0.5) / nf)
            x += gf.uniform(-0.03, 0.03)
            y = gf.uniform(-0.02, 0.12)
            fh = 0.14 * gf.uniform(0.92, 1.05)
            mi = m_white if flask_glaze[i] == 'white' else m_dark
            allv, _ = C.lathe(mb, T.tokkuri_profile(0.04, fh, max(1, lod + 1) if lod < 2 else 3), fsegs, mi, base=(x, y, H),
                              closed=lod < 2)
            if lod == 2:
                ring = allv[-fsegs:]
                mb._tag([mb.bm.faces.new(ring)], mi)
            if lod <= 1:
                cx = x + gf.choice([-1, 1]) * 0.09
                C.lathe(mb, P.cup(0.024, 0.03, lod=2 if lod else 1), C.lod_pick(lod, 8, 6), m_cup,
                        base=(cx, y + 0.1 + gf.uniform(-0.02, 0.02), H))

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    o = genlib.finish(o, smooth_angle=40)
    fx, lights = [], []
    for t in tips:
        fx.append(dict(fx='fx_steam', pos=[round(t.x + dx, 4), round(t.y + dy, 4), round(t.z + dz, 4)]))
    if hearth:
        fx.append(dict(fx='fx_steam', pos=[round(hx + dx, 4), round(dy, 4), round(H + dz, 4)], scale=0.6))
        lights.append(C.light_entry((hx + dx, dy, pit_z + 0.06 + dz), color_k=1900, watts=15))
    C.set_json_props(o, kz_fx=fx, kz_lights=lights,
                     kz_params=dict(w=round(W, 3), h=round(H, 3), hearth=hearth, front=front, flasks=nf))
    return o
