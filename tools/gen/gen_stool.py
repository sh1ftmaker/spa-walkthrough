"""Stool (vanity, bar, bath) (stool).

Identifying features kept at every LOD: vanity stool with cushion; timber bar stool with red cushion and
footrest; low hinoki bath stool.

Construction (round 3)
  * bar and vanity: dark stained hinoki (variant dark_timber) seat, legs, apron and footrest. Round seat (16
    segments at LOD0, two-step 12 mm edge), a domed fabric cushion 40-50 mm with a 15 mm bevelled edge, a
    6 mm welt and a stitched seam ring. Four 8-sided legs with a 30 mm bead at mid height and a 12 mm tenon
    into an under-seat apron (30 mm deep). Bar also has a round footrest ring (0.30-0.34 m, 25 mm section,
    0.22 m up) with two tie stretchers.
  * cushion colour is seeded from red, indigo and cream for every style. Noren is the cloth.
  * bath: low hinoki drum (tapered lathe) with a shallow dished top, no legs.
  * LOD3 is a seat disc, four square-section legs and a footring stub (about 110 tris). LOD2 keeps the
    cushion and the footring. LOD1 and LOD0 keep the full set.
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 0.42 x 0.42 x 0.75 m):
  h       height 0.25-0.75 m   (default 0.72 bar, 0.52 vanity, 0.27 bath)
  w       seat width 0.36-0.45 m (default seeded)
  style   vanity | bar | bath  (default bar)
  cushion red | indigo | cream (default: seeded)
Seeds change leg splay, seat thickness, seat diameter, cushion colour and dome height.
"""
import math
import genlib
import kzgeo_stool as K

ASSET = 'stool'
FEATURES = ['vanity stool with cushion', 'timber bar stool with red cushion and footrest', 'low hinoki bath stool']
SEG_SEAT = {0: 16, 1: 12, 2: 8, 3: 8}
SEG_LEG = {0: 8, 1: 6, 2: 4, 3: 4}
SEG_RING = {0: 16, 1: 8, 2: 8, 3: 8}
CUSHION = {'red': (0.7, 0.02, 0.02), 'indigo': (0.07, 0.09, 0.2), 'cream': (0.62, 0.55, 0.42)}


def _ring_band(mb, rc, zc, half_w, half_h, segs, mi):
    """round section approximated by a square-section band, open at the ends"""
    prof = [(rc - half_w, zc - half_h), (rc + half_w, zc - half_h), (rc + half_w, zc + half_h), (rc - half_w, zc + half_h)]
    K.revolve(mb, prof, segs, mi, closed=False)


def build(lod, seed, h=None, w=None, style=None, cushion=None):
    g = genlib.rng(seed, ASSET)
    style = style or 'bar'
    seg = SEG_SEAT[lod]
    leg_seg = SEG_LEG[lod]
    mb = genlib.MeshBuilder()
    if style == 'bath':
        wood = mb.slot('hinoki', variant='wet_oiled', wear=round(g.uniform(0.1, 0.25), 2))
    else:
        wood = mb.slot('hinoki', variant='stained', wear=0.1)
    dark = mb.slot('lacquer_dark')

    if style == 'bath':
        H = h or 0.27
        R = (w / 2) if w else g.uniform(0.15, 0.17)
        prof = [(0.0, 0.0), (R * 0.92, 0.0), (R * 0.97, H * 0.5), (R, H), (R * 0.93, H), (R * 0.6, H - 0.012),
                (0.0, H - 0.02)]
        if lod >= 2:
            prof = [(0.0, 0.0), (R * 0.95, 0.0), (R, H), (0.0, H)]
        K.revolve(mb, prof, max(8, seg), wood)
        K.centre_xy_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    H = h or (0.72 if style == 'bar' else 0.52)
    R = (w / 2) if w else g.uniform(0.36, 0.45) / 2
    cu = cushion or g.choice(['red', 'indigo', 'cream'])
    fab = mb.slot('noren', tint=CUSHION.get(cu, CUSHION['red']))
    splay = g.uniform(0.10, 0.20)
    seat_t = g.uniform(0.035, 0.05)
    leg_top = H - seat_t - 0.01
    foot_r = R * (0.72 + splay)
    top_r = R * 0.62
    dome = g.uniform(0.040, 0.050)
    ring_d = g.uniform(0.30, 0.34) if style == 'bar' else 0.0
    rr = ring_d / 2
    zf = 0.22

    # LOD3: seat disc, four square-section legs, footring stub
    if lod == 3:
        for k in range(4):
            a = math.radians(45 + 90 * k)
            top = (top_r * math.cos(a), top_r * math.sin(a), leg_top)
            bot = (foot_r * math.cos(a), foot_r * math.sin(a), 0.0)
            K.stick(mb, bot, top, 0.022, 0.017, wood, segs=4)
        K.revolve(mb, [(0.0, H - seat_t), (R, H - seat_t), (R, H), (0.0, H)], seg, wood)
        if style == 'bar':
            _ring_band(mb, rr, zf, 0.012, 0.012, SEG_RING[3], wood)
        K.centre_xy_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    # legs: 8-sided, 30 mm bead at mid height, 12 mm tenon into the apron
    for k in range(4):
        a = math.radians(45 + 90 * k + g.uniform(-3, 3))
        top = (top_r * math.cos(a), top_r * math.sin(a), leg_top)
        bot = (foot_r * math.cos(a), foot_r * math.sin(a), 0.0)
        K.stick(mb, bot, top, 0.024, 0.019, wood, segs=leg_seg)
        if lod <= 1:
            mid = [(bot[i] + top[i]) / 2 for i in range(3)]
            K.stick(mb, (mid[0], mid[1], mid[2] - 0.015), (mid[0], mid[1], mid[2] + 0.015), 0.017, 0.017, wood,
                    segs=leg_seg)
        K.stick(mb, top, (top[0], top[1], top[2] + 0.012), 0.012, 0.012, wood, segs=max(4, leg_seg))

    # under-seat apron, 30 mm deep, joins the legs
    if lod <= 1:
        _ring_band(mb, R * 0.9, H - seat_t - 0.015, 0.006, 0.015, seg, wood)

    # seat: round disc with a two-step edge
    if lod >= 2:
        sprof = [(0.0, H - seat_t), (R, H - seat_t), (R, H), (0.0, H)]
    else:
        sprof = [(0.0, H - seat_t), (R - 0.012, H - seat_t), (R, H - seat_t + 0.012), (R, H - 0.012),
                 (R - 0.012, H), (0.0, H)]
    K.revolve(mb, sprof, seg, wood)

    # cushion: 15 mm bevelled edge rising into a 40-50 mm dome; 6 mm welt and seam ring
    cr = R * 0.9
    if lod >= 2:
        cprof = [(0.0, H), (cr, H), (cr * 0.7, H + dome), (0.0, H + dome)]
    else:
        cprof = [(0.0, H), (cr - 0.015, H), (cr, H + 0.015), (cr - 0.008, H + dome * 0.75), (cr * 0.6, H + dome),
                 (0.0, H + dome)]
        K.revolve(mb, [(cr - 0.003, H + 0.012), (cr + 0.003, H + 0.012), (cr + 0.003, H + 0.018),
                       (cr - 0.003, H + 0.018)], seg, dark, closed=False)
        K.revolve(mb, [(cr - 0.002, H + 0.014), (cr + 0.002, H + 0.014), (cr + 0.002, H + 0.017),
                       (cr - 0.002, H + 0.017)], seg, dark, closed=False)
    K.revolve(mb, cprof, seg, fab)

    # footrest: round ring at 0.22 m with two tie stretchers (bar only)
    if style == 'bar':
        ring_seg = SEG_RING[lod]
        _ring_band(mb, rr, zf, 0.0125, 0.0125, ring_seg, wood)
        if lod <= 1:
            K.stick(mb, (-rr, 0.0, zf), (rr, 0.0, zf), 0.008, 0.008, wood, segs=6)
            K.stick(mb, (0.0, -rr, zf), (0.0, rr, zf), 0.008, 0.008, wood, segs=6)

    K.centre_xy_base(mb)
    o = mb.to_object(ASSET)
    return genlib.finish(o)
