"""Flat-bottomed river boat (boat): the B2 underground-river transport boat at the boat landing.

Identifying features kept at every LOD: long shallow plank hull, low rail, lantern on a pole at the stern.

Targets (measured before coding)
  * refs/gen/sheet-mod-kawagiri.png panel 5 (crop .scratch/op21/m_boat.png, 2x): SIDE 8.0 m bar = 435 px
    (54 px/m); FRONT 2.4 m bar = 183 px (76 px/m; the front and side are not drawn to one scale, so the
    labels win). Hull: long, shallow, flat bottom with a gentle rocker, raked ends, 5 strakes; hull depth at
    midships ~1.05-1.1 m (front view 160/152), gunwale rising ~0.2 m at the ends; beam 2.2-2.4 m at the
    gunwale (label 2.4 includes the rope fenders), bottom ~1.6 m; pointed stem at the bow seen in the front
    view. Low rail: 8-10 short posts (~0.2 m) with a top rail along most of the length. A tall pole near one
    end carries a round paper lantern (~0.35 x 0.45 m) on an L-arm, lantern top ~2.4 m above the keel
    (label); the other end has a tall post / sculling oar and a wicker basket. Lookbook 23 and
    refs/gen/dh-core-boat.png show the same boats lit at the landing.
  * Row: l 7-8 m, beam 1.8-2.4 m, freeboard, thwarts, pole lantern on/off, lit|unlit; proxy 1.8 x 8.0 x 1.2.
    The proxy height holds the hull only; with the lantern pole (an identifying feature) the boat is
    ~2.4 m tall, and the concept beam is ~2.2 m: proposed proxy w 2.3, h 2.5 (report).
  Built: L 7.3-8.0, gunwale beam 1.85-2.2 (+ rub rails), bottom 0.62-0.70 of the beam, hull depth
  0.78-0.95 m + 0.15-0.25 m sheer at the ends, rail 0.18-0.24 m, pole lantern top 2.25-2.45 m.

Construction
  * hull: one closed lofted shell (kzgeo_boat.hull_shell), 4 cm walls, 5 strakes with 8 mm V-seams at LOD0,
    rounded chine, flat bottom with rocker; `hinoki` dark_timber outside, a rougher dark_timber inside / gunwale top.
    'transom' style: square raked stern with a transom board and iron corner straps; 'double' style:
    double-ended, pointed at both ends with a second stem post.
  * rub rails (wale) along both gunwales, stem post(s) with iron bands, low rail = posts + top rail
    (`hinoki` wet_oiled), 3-5 thwarts, floor boards, wicker basket (`bamboo`), mooring bitt with rope coil
    (`rope`), a long punting pole (sao) laid along the rail.
  * pole lantern (stern): `lacquer_dark` pole lashed with rope, iron L-arm, a round ribbed chochin in
    `lantern_paper` with `lacquer_dark` caps. lit=True: emissive 0.9 + obj['kz_lights'] at the lantern
    centre (2200 K, 20 W); unlit: emissive 0.05, no light entry.
LOD1: hull 16 stations without seams, posts as boxes, same counts. LOD2: hull 7 stations, top rails + 3
posts per side (no wales, basket, bitt or sao), pole + lantern (8-sided), thwarts. LOD3: 5-station hull with a sunk deck, pole, lantern box.
Animation: rigid (bob and roll; follows the boat route): obj['kz_anim']. Water: obj['kz_waterline'].
Lighting: probe (moving) + emissive.

Parameters (build kwargs)
  style      transom | double          (cycles with the seed)
  l          7-8 m        beam 1.8-2.4 m (gunwale)      freeboard 0.45-0.7 m (gunwale above the waterline)
  thwarts    3-5          lantern True/False (pole lantern on/off)     lit True/False
Seeds change: stern style (transom vs double-ended + second stem), length, beam, bottom width, depth,
sheer, rocker, thwart count and spacing, rail post count, basket side, pole position.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_boat as KB
import kzgeo_common as C

ASSET = 'boat'
FEATURES = ['long shallow plank hull', 'low rail', 'lantern on a pole at the stern']
STYLES = ['transom', 'double']
DRAFT = 0.28


def build(lod, seed, style=None, l=None, beam=None, freeboard=None, thwarts=None, lantern=True, lit=True):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'hull')
    L = max(7.0, min(8.0, l)) if l else g.uniform(7.3, 8.0)
    B = max(1.8, min(2.4, beam)) if beam else g.uniform(1.85, 2.2)
    bot = g.uniform(0.62, 0.70)
    D = (DRAFT + max(0.45, min(0.7, freeboard))) if freeboard else g.uniform(0.78, 0.95)
    sheer_b, sheer_s = g.uniform(0.18, 0.25), g.uniform(0.12, 0.2)
    rock_b, rock_s = g.uniform(0.40, 0.55), g.uniform(0.22, 0.32)
    u0b, u0s = g.uniform(0.25, 0.4), g.uniform(0.45, 0.6)
    e_s = 0.42 if style == 'transom' else 0.06
    if style == 'double':
        rock_s, sheer_s, u0s = rock_b * 0.9, sheer_b * 0.9, u0b
    gt = C.rng(seed, 'thwarts')
    n_th = int(max(3, min(5, thwarts))) if thwarts else gt.randint(3, 5)
    th_u = [-0.55 + 1.05 * (i + 0.5) / n_th + gt.uniform(-0.04, 0.04) for i in range(n_th)]
    gr = C.rng(seed, 'rail')
    n_post = gr.randint(7, 10)
    rail_h = gr.uniform(0.18, 0.24)
    rail_u = (gr.uniform(-0.78, -0.68), gr.uniform(0.62, 0.72))
    gp = C.rng(seed, 'props')
    basket_side = gp.choice([-1, 1])
    pole_u = gp.uniform(-0.86, -0.8) if style == 'transom' else gp.uniform(-0.78, -0.72)
    pole_x = gp.uniform(-0.15, 0.15)
    pole_top = gp.uniform(2.25, 2.45)
    sao_side = -basket_side

    HG, HB = B / 2, B / 2 * bot
    T_WALL = 0.04

    def shape(u):
        """hb, hg, zb, zg at u in [-1 stern, 1 bow]"""
        if u >= 0:
            t = max(0.0, (u - u0b) / (1 - u0b))
            hg = HG * (1 - (1 - 0.05) * t ** 1.9)
            hb = HB * (1 - (1 - 0.02) * t ** 1.25)
            zb = rock_b * t ** 2.2
            zg = D + sheer_b * t ** 2
        else:
            t = max(0.0, (-u - u0s) / (1 - u0s))
            e = e_s
            hg = HG * (1 - (1 - e) * t ** 1.9)
            hb = HB * (1 - (1 - (e * 0.8 if e > 0.1 else 0.02)) * t ** 1.25)
            zb = rock_s * t ** 2.2
            zg = D + sheer_s * t ** 2
        return hb, hg, zb, zg

    def y_of(u):
        return u * L / 2

    mb = genlib.MeshBuilder()
    m_hull = mb.slot('hinoki', variant='dark_timber', wear=0.45)
    m_in = mb.slot('hinoki', variant='dark_timber', wear=0.25, roughness_offset=0.15)
    m_trim = mb.slot('hinoki', variant='wet_oiled')
    m_lac = mb.slot('lacquer_dark')
    m_iron = mb.slot('iron')
    m_paper = mb.slot('lantern_paper', emissive_level=0.9 if lit else 0.05)
    m_rope = mb.slot('rope')
    m_bask = mb.slot('bamboo', tint=(0.55, 0.45, 0.35))
    lights = []

    # ---------------------------------------------------------------- LOD3: 5-station hull with a sunk deck
    if lod == 3:
        sts = []
        for u in (-1.0, -0.6, 0.0, 0.6, 1.0):
            hb, hg, zb, zg = shape(u)
            di = max(hg - 0.08, 0.02)
            sts.append((y_of(u), [(-hg, zg), (-hb, zb), (hb, zb), (hg, zg), (di, zg - 0.35), (-di, zg - 0.35)]))
        KB.hull_shell(mb, sts, m_hull)
        hb, hg, zb, zg = shape(pole_u)
        C.lathe(mb, [(0.05, zb + 0.05), (0.04, pole_top)], 4, m_lac, base=(pole_x, y_of(pole_u), 0))
        mb.box((pole_x, y_of(pole_u) + 0.42, pole_top - 0.42), (0.34, 0.34, 0.46), m_paper)
        return _finish(mb, style, L, B, D, n_th, lantern, lit, lights, pole_x, pole_u, pole_top, y_of)

    # ---------------------------------------------------------------- hull shell
    N = C.lod_pick(lod, 24, 16, 7)
    n_side = C.lod_pick(lod, 6, 4, 2)
    seams = (0.2, 0.4, 0.6, 0.8) if lod == 0 else ()
    sts = []
    for i in range(N):
        s = -1 + 2 * i / (N - 1)
        u = math.copysign(abs(s) ** 0.8, s)
        hb, hg, zb, zg = shape(u)
        sts.append((y_of(u), KB.section(hb, hg, zb, zg, T_WALL, n_side, seams, 0.008)))
    KB.hull_shell(mb, sts, m_hull, mi_in=m_in)

    # ---------------------------------------------------------------- rub rails (wales) along the gunwale
    us = [math.copysign(abs(-1 + 2 * i / (N // 2 - 1)) ** 0.8, -1 + 2 * i / (N // 2 - 1)) for i in range(N // 2)]
    us = [max(-0.985, min(0.985, u)) for u in us]
    wale = [(-0.0, 0.0), (0.035, 0.0), (0.045, 0.025), (0.035, 0.055), (0.0, 0.055)] if lod <= 1 else \
        [(0.0, 0.0), (0.04, 0.0), (0.04, 0.05), (0.0, 0.05)]
    for sx in (-1, 1):
        pts = []
        for u in us:
            hb, hg, zb, zg = shape(u)
            pts.append(Vector((sx * (hg - 0.004), y_of(u), zg - 0.075)))
        prof = [(x * sx, z) for x, z in wale]
        if sx < 0:
            prof = prof[::-1]
        if lod <= 1:
            C.sweep(mb, pts, prof, m_trim)

    # ---------------------------------------------------------------- low rail: posts + top rail
    post_n = n_post if lod <= 1 else 3
    for sx in (-1, 1):
        tops = []
        for k in range(post_n):
            u = rail_u[0] + (rail_u[1] - rail_u[0]) * k / (post_n - 1)
            hb, hg, zb, zg = shape(u)
            x = sx * (hg - T_WALL / 2)
            c = (x, y_of(u), zg + rail_h / 2 - 0.01)
            if lod == 0:
                C.chamfered_bar(mb, c, (0.06, 0.06, rail_h + 0.02), m_trim, ch=0.008, axis='z')
                C.board(mb, (x, y_of(u), zg + rail_h * 0.25), (0.066, 0.066, 0.025), m_iron, bevel=0.0)
            else:
                mb.box(c, (0.06, 0.06, rail_h + 0.02), m_trim)
        nr = C.lod_pick(lod, 12, 7, 4)
        for k in range(nr):
            u = rail_u[0] + (rail_u[1] - rail_u[0]) * k / (nr - 1)
            hb, hg, zb, zg = shape(u)
            tops.append(Vector((sx * (hg - T_WALL / 2), y_of(u), zg + rail_h)))
        prof = [(-0.04, 0.0), (0.04, 0.0), (0.04, 0.035), (-0.04, 0.035)] if lod else \
            [(-0.035, 0.0), (0.035, 0.0), (0.042, 0.012), (0.042, 0.03), (0.03, 0.042), (-0.03, 0.042), (-0.042, 0.03), (-0.042, 0.012)]
        C.sweep(mb, tops, prof, m_trim)

    # ---------------------------------------------------------------- stem post(s) with iron bands
    def stem(end):
        hb, hg, zb, zg = shape(end * 0.999)
        hb2, hg2, zb2, zg2 = shape(end * 0.9)
        y0 = y_of(end) + end * 0.02
        top = Vector((0, y0 + end * 0.06, zg + 0.22))
        bot = Vector((0, y_of(end * 0.93), zb2 - 0.0))
        sec = [(-0.045, -0.05), (0.045, -0.05), (0.045, 0.05), (-0.045, 0.05)]
        C.sweep(mb, [bot, Vector((0, y0, (zb + zg) / 2)), top], sec, m_trim, up=Vector((1, 0, 0)))
        if lod <= 1:
            for f in (0.55, 0.85):
                p = Vector((0, y0, zb + (zg - zb) * f))
                C.board(mb, (p.x, p.y - end * 0.0, p.z), (0.1, 0.11, 0.03), m_iron, bevel=0.0)
    stem(1)
    if style == 'double':
        stem(-1)
    else:   # transom board + iron corner straps
        hb, hg, zb, zg = shape(-1)
        y0 = y_of(-1) - 0.02
        if lod <= 1:
            C.board(mb, (0, y0, (zb + zg) / 2 + 0.02), (2 * hg + 0.05, 0.04, zg - zb + 0.08), m_trim,
                    bevel=C.lod_pick(lod, 0.008, 0.0))
            for sx in (-1, 1):
                C.board(mb, (sx * (hg + 0.01), y0 + 0.03, (zb + zg) / 2), (0.03, 0.12, zg - zb - 0.05), m_iron, bevel=0.0)
        else:
            mb.box((0, y0, (zb + zg) / 2 + 0.02), (2 * hg + 0.05, 0.04, zg - zb + 0.08), m_trim)

    # ---------------------------------------------------------------- thwarts and floor boards
    for u in th_u:
        hb, hg, zb, zg = shape(u)
        z = zg - 0.16
        w = 2 * (hg - T_WALL) - 0.01 - 0.06 * (1 - (z - zb) / (zg - zb))
        C.board(mb, (0, y_of(u), z), (w, 0.26, 0.045), m_in, bevel=C.lod_pick(lod, 0.008, 0.0, 0.0))
    if lod <= 1:
        for k, fx in enumerate((-0.42, 0.0, 0.42)):
            hb, hg, zb, zg = shape(0)
            C.board(mb, (fx * HB, 0, T_WALL + 0.012), (0.2, L * 0.55, 0.024), m_in, bevel=C.lod_pick(lod, 0.004, 0.0))

    # ---------------------------------------------------------------- basket, bitt + rope, punting pole
    if lod <= 1:
        ub = 0.62
        hb, hg, zb, zg = shape(ub)
        bx = basket_side * max(0.0, hb - 0.3)
        C.board(mb, (bx, y_of(ub), zb + T_WALL + 0.16), (0.42, 0.36, 0.3), m_bask, bevel=C.lod_pick(lod, 0.015, 0.0))
        C.board(mb, (bx, y_of(ub), zb + T_WALL + 0.315), (0.44, 0.38, 0.03), m_bask, bevel=0.0)
        ut = 0.82
        hb, hg, zb, zg = shape(ut)
        C.lathe(mb, [(0.06, zb + 0.05), (0.06, zg + 0.14), (0.07, zg + 0.16), (0.0, zg + 0.2)],
                C.lod_pick(lod, 10, 6), m_trim, base=(0, y_of(ut), 0))
        C.rope_turns(mb, (0, y_of(ut), zg + 0.04), (0, 0, 1), 0.06, C.lod_pick(lod, 4, 2), m_rope,
                     cord=0.014, pitch=0.024, N=C.lod_pick(lod, 8, 6))
        # punting pole (sao) resting on the thwarts, its tip over the bow
        hb, hg, zb, zg = shape(th_u[0])
        p0 = Vector((sao_side * (hg - 0.3), y_of(th_u[0] - 0.08), zg - 0.16 + 0.05))
        hb, hg, zb, zg = shape(0.9)
        p1 = Vector((sao_side * 0.12, y_of(1.0) + 0.25, zg + 0.08))
        C.tube(mb, [p0, p1], [0.028, 0.024], m_lac, sides=C.lod_pick(lod, 8, 5), cap0=True, cap1=True)

    # ---------------------------------------------------------------- stern pole lantern
    if lantern:
        hb, hg, zb, zg = shape(pole_u)
        py = y_of(pole_u)
        segs = C.lod_pick(lod, 10, 6, 4)
        C.stick(mb, (pole_x, py, zb + T_WALL), (pole_x, py, pole_top), 0.05, 0.04, m_lac, segs=segs)
        if lod <= 1:   # lashed to the aft thwart height with rope
            C.rope_turns(mb, (pole_x, py, zg - 0.05), (0, 0, 1), 0.048, C.lod_pick(lod, 4, 2), m_rope,
                         cord=0.012, pitch=0.022, N=segs)
        arm_l = 0.5
        az = pole_top - 0.06
        C.stick(mb, (pole_x, py - 0.03, az), (pole_x, py + arm_l, az), 0.018, 0.016, m_iron, segs=C.lod_pick(lod, 6, 4, 4))
        if lod <= 1:   # diagonal brace
            C.stick(mb, (pole_x, py + 0.02, az - 0.3), (pole_x, py + arm_l * 0.6, az), 0.012, 0.012, m_iron, segs=4)
        lc = Vector((pole_x, py + arm_l - 0.08, az - 0.07 - 0.25))
        _chochin(mb, lc, 0.17, 0.42, lod, m_paper, m_lac, m_rope, az)
        if lit:
            lights.append(C.light_entry(lc, color_k=2200, watts=20))

    return _finish(mb, style, L, B, D, n_th, lantern, lit, lights, pole_x, pole_u, pole_top, y_of)


def _chochin(mb, c, r, h, lod, m_paper, m_cap, m_cord, hang_z):
    """round ribbed paper lantern centred at c, hanging from hang_z: lacquer caps top and bottom."""
    segs = C.lod_pick(lod, 12, 8, 6)
    nrib = C.lod_pick(lod, 6, 4, 2)
    z0, z1 = c.z - h / 2, c.z + h / 2
    prof = []
    for i in range(nrib * 2 + 1):
        t = i / (nrib * 2)
        z = z0 + 0.03 + (h - 0.06) * t
        rr = r * (0.62 + 0.38 * math.sin(math.pi * t) ** 0.7)
        if lod == 0 and i % 2 == 1:
            rr -= 0.006
        prof.append((rr, z))
    C.lathe(mb, prof, segs, m_paper, base=(c.x, c.y, 0))
    for zc, s in ((z0, 1), (z1, -1)):
        cr = r * 0.62 + 0.008
        prof = [(cr * 0.7, zc), (cr, zc + s * 0.012), (cr, zc + s * 0.04), (cr * 0.7, zc + s * 0.045)] if lod <= 1 else \
            [(cr, zc), (cr, zc + s * 0.045)]
        C.lathe(mb, prof[::s], segs, m_cap, base=(c.x, c.y, 0))
    if lod <= 1:
        C.rope_cord(mb, (c.x, c.y, z1 + 0.04), (c.x, c.y, hang_z), 0.006, m_cord, sides=C.lod_pick(lod, 6, 4),
                    twist=lod == 0, seg_len=0.04)
    else:
        C.stick(mb, (c.x, c.y, z1 + 0.04), (c.x, c.y, hang_z), 0.008, 0.008, m_cord, segs=3)


def _uv_grain_along_hull(o, slots):
    """genlib's box UV0 puts the hinoki grain vertical on X-facing faces; for the hull planks, wales and
    rails the grain must run along the boat (Y), and across the transom: swap the axes on those faces."""
    me = o.data
    uv = me.uv_layers['UVMap'].data
    for p in me.polygons:
        if p.material_index not in slots:
            continue
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                uv[li].uv = (co.z * (1 if n.x > 0 else -1), co.y)
            elif ax == 1:
                uv[li].uv = (co.z * (1 if n.y < 0 else -1), co.x)


def _finish(mb, style, L, B, D, n_th, lantern, lit, lights, pole_x, pole_u, pole_top, y_of):
    wood_slots = {i for i, (mid, prm) in enumerate(mb.slots) if mid == 'hinoki'}
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    _uv_grain_along_hull(o, wood_slots)
    for e in lights:
        p = e['pos']
        e['pos'] = [round(p[0] + dx, 3), round(p[1] + dy, 3), round(p[2] + dz, 3)]
    props = dict(kz_waterline=DRAFT + dz,
                 kz_anim=dict(type='rigid', what='bob and roll; follows the boat route', bob_amp_m=0.03,
                              bob_period_s=4.5, roll_deg=2.5, roll_period_s=6.0, pitch_deg=1.0,
                              follows='b2 boat route (layout)'),
                 kz_params=dict(style=style, l=round(L, 3), beam=round(B, 3), depth=round(D, 3),
                                freeboard=round(D - DRAFT, 3), thwarts=n_th, lantern=lantern, lit=lit))
    if lights:
        props['kz_lights'] = lights
    C.set_json_props(o, **props)
    return o
