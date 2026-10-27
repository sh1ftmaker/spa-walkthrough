"""Cliff suite room and veranda (suite_module) for suite_1a..suite_4c: one North Cliff suite carved into the
rock, with its private tub niche. Host asset: futon_bed, tansu_chest, table_low, lantern_floor and stone_tub
are placed into it through kz_anchors.

Targets (measured before coding)
  * lookbook 32, suite plan (bar 0-5 m = 190 px, 38 px/m): timber suite box ~7.4 x 8.0 m with the entry
    vestibule (genkan, with storage) at the back-left off the cliff-stair landing, the tatami room in the
    centre (futon + tea table), a side room behind sliding washi screens on the east, a wooden veranda with
    seating across the front (~1.8-2.2 m deep), and the stone onsen in a rock niche in front / beside it.
  * lookbook 32, front elevation (0-20 m = 162 px, 8.1 px/m): suite bays ~12-14 m wide incl. the tub,
    storey ~3.2 m; each suite shows lit shoji at both ends, an open centre onto the futon, a rail along
    the veranda, rock above and between suites, the tub at one side with a falls.
  * lookbook 21 and sheet-ref-cliff-cavern #01: open shoji (2 m doors, kumiko grid, lit) onto tatami with
    dark borders, dark timber posts and head beams, glowing ranma above the kamoi, a tokonoma with a hanging
    scroll, andon floor lanterns, a rock overhang right above the tub niche, wet black basalt round the tub.
  Built: 16 x 12 x 3.2 m (row footprint): room 9.6-11.4 x 7.6-8.4 m, tatami top 0.45 m, ceiling 2.9 m,
  door head (kamoi) 1.95 m above the tatami, veranda 1.8-2.6 m deep at 0.36 m, rail 0.9 m, bath niche
  4.6-5.4 m wide with a 0.5-0.9 m thick rock overhang at the roof line.

Construction (front +Y = veranda / view; back -Y = the cliff; pivot at the base centre)
  * floor: dark timber sub-floor + sill beams; tatami mats in a running bond with dark heri gaps (`tatami`,
    `lacquer_dark`); genkan floor of wet basalt with a lacquer step edge (agari-kamachi).
  * front facade: square posts per bay, sill, kamoi head beam, lit ranma transoms, top beam; per bay two
    shoji (kzgeo_shoji_panel, `washi_backlit`) closed, open (stacked behind a post) or half open.
  * walls: back and left walls dark hinoki with posts; the bath-side wall is lit shoji over the side room;
    tokonoma alcove with raised floor, lacquer edge, toko-bashira post, otoshigake beam and a hanging scroll.
  * veranda: deck boards along X on an edge beam, eave posts per bay, capped rail with mid rails (open at
    the bath end), a low bench; style c wraps the veranda round the left end.
  * roof: ceiling slab + roof slab with a deep eave over the veranda, fascia and exposed rafters.
  * bath niche: wet basalt platform (stone_tub placed on it), the cliff mass behind, a rock cheek on the
    outer side and a craggy rock overhang slab above (`basalt_wet`), edge rocks along the front.
  * lights: andon floor lanterns (C.lantern_head, `lantern_andon`), kz_lights for lanterns, lit shoji and the
    room's ceiling area light (proxy light 120 W 2600 K).
  LOD1: shoji with front-strip kumiko, plain boxes, coarser rocks. LOD2: shoji as lit slabs, single tatami and
  deck slabs, no rafters / bench / edge rocks. LOD3: massing with a lit front band (~120 tris).
Animation: none. Lighting: lightmap + emissive (washi_backlit, lantern_andon).

Parameters (build kwargs; proxy 16 x 12 x 3.2 m)
  style        a | b | c   (columns a, b, c; default cycles with the seed: 1 a, 2 b, 3 c)
  bays         3-5 shoji bays across the front         veranda_depth  1.6-2.8 m
  overhang     rock overhang slab thickness 0.5-0.9 m  bath_w  bath niche width 4.6-5.4 m
Styles: a: tub right, 4 bays, 2.2 m veranda; b: mirrored (tub left), 3 wide bays, 2.6 m veranda, tokonoma on the
other side; c: tub right, 5 narrow bays, 1.8 m veranda wrapping the left end. Seeds > 3 draw these in range.
Seeds change: style/mirror, bay count and open pattern, veranda depth and wrap, bath niche width, room split,
rock shapes, lantern positions.
"""
import math

import bmesh

import genlib
import kzgeo_bridge_arched as KG
import kzgeo_common as C
import kzgeo_suite_module as K

ASSET = 'suite_module'
FEATURES = ['timber facade with open shoji', 'tatami room', 'veranda with rail', 'tokonoma',
            'rock overhang above the tub niche']
STYLES = ['a', 'b', 'c']
X0, X1, Y0, Y1, HTOP = -8.0, 8.0, -6.0, 6.0, 3.2


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def params(seed, style=None, bays=None, veranda_depth=None, overhang=None, bath_w=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    base = {'a': dict(side=1, bays=4, vd=2.2, wrap=False, toko='right'),
            'b': dict(side=-1, bays=3, vd=2.6, wrap=False, toko='left'),
            'c': dict(side=1, bays=5, vd=1.8, wrap=True, toko='right')}[style]
    P = dict(style=style, **base)
    if seed > 3:
        P['bays'] = g.choice([3, 4, 5])
        P['vd'] = g.uniform(1.8, 2.6)
    else:
        g.random(); g.random()
    P['bays'] = int(_clamp(bays, 3, 5)) if bays else P['bays']
    P['vd'] = _clamp(veranda_depth, 1.6, 2.8) if veranda_depth else P['vd']
    P['ovh_t'] = _clamp(overhang, 0.5, 0.9) if overhang else g.uniform(0.55, 0.85)
    P['bath_w'] = _clamp(bath_w, 4.6, 5.4) if bath_w else g.uniform(4.6, 5.4)
    P['genkan_w'] = g.uniform(2.4, 2.8)
    P['open'] = C.pick(seed, 'open', ['mid', 'all_but_ends', 'alternate'])
    if seed == 1:
        P['open'] = 'mid'
    return P


def build(lod, seed, style=None, bays=None, veranda_depth=None, overhang=None, bath_w=None):
    P = params(seed, style, bays, veranda_depth, overhang, bath_w)
    r_rock = C.rng(seed, 'rocks')
    r_misc = C.rng(seed, 'misc')

    mb = genlib.MeshBuilder()
    m_wood = mb.slot('hinoki', variant='dark_timber')            # structure, posts, beams, walls
    m_deck = mb.slot('hinoki', variant='wet_oiled', wetness=0.3)  # veranda deck, rail top
    m_ceil = mb.slot('hinoki', variant='stained')                  # ceiling boards
    m_tat = mb.slot('tatami')
    m_lac = mb.slot('lacquer_dark')                                # heri gaps, toko edge, step edge, sub floor
    m_rock = mb.slot('basalt_wet', wetness=0.45)
    m_wet = mb.slot('basalt_wet', wetness=0.9, roughness_offset=-0.05)
    m_washi = mb.slot('washi_backlit', emissive_level=0.85)
    m_scroll = mb.slot('washi')
    m_iron = mb.slot('iron')
    m_andon = mb.slot('lantern_andon', emissive_level=0.9)
    shoji_mats = dict(wood=m_wood, paper=m_washi, washi=m_scroll, lacquer=m_lac, glass=m_washi, metal=m_iron)
    SP = dict(style='shoji', T=0.032, stile=0.03, top=0.04, bot=0.058, kw=0.0085, kd=0.016, mid=0.028,
              koshi=0.22, cols=4, rows=6)

    ZT = 0.45                 # tatami top
    ZC = ZT + 2.45            # ceiling
    ZK = ZT + 1.95            # kamoi (door head)
    ZV = 0.36                 # veranda deck top
    bw = P['bath_w']
    rx1 = X1 - bw             # room / bath boundary
    rx0 = X0 + (1.5 if P['wrap'] else 0.0)
    yv1 = Y1 - 0.15           # veranda front edge
    ry1 = yv1 - P['vd']       # facade line
    gk = P['genkan_w']
    lights = []
    anchors = {}

    if lod == 3:
        f = mb.box(((rx0 + rx1) / 2, (Y0 + ry1) / 2, ZC / 2), (rx1 - rx0, ry1 - Y0, ZC), m_wood)
        for q in f:
            c = q.calc_center_median()
            if c.y > ry1 - 1e-3:
                q.material_index = m_washi                         # lit shoji front
        mb.box(((rx0 + rx1) / 2 - (0.75 if P['wrap'] else 0), (Y0 + yv1) / 2, (ZC + HTOP) / 2),
               (rx1 - rx0 + (1.5 if P['wrap'] else 0), yv1 - Y0, HTOP - ZC), m_wood)
        xd0 = X0 if P['wrap'] else rx0
        mb.box(((xd0 + rx1) / 2, (ry1 + yv1) / 2, ZV / 2), (rx1 - xd0, yv1 - ry1, ZV), m_deck)
        mb.box(((xd0 + rx1 - 1.0) / 2, yv1 - 0.05, ZV + 0.47), (rx1 - 1.0 - xd0, 0.1, 0.94), m_wood)
        mb.box(((rx1 + X1) / 2, (Y0 + 2.0 + yv1) / 2, 0.15), (bw - 0.4, yv1 - Y0 - 2.0, 0.3), m_wet)
        K.rock_mass(mb, (rx1 + X1) / 2, Y0 + 1.1, bw / 2 * 0.85, 1.0, 0.0, HTOP, m_rock, r_rock, 3)
        K.rock_slab(mb, (rx1 + X1) / 2 + 0.1, -1.4, bw / 2 * 0.85, 4.4, HTOP, P['ovh_t'], m_rock, r_rock, 3)
        return _finish(mb, P, lod, lights, anchors)

    # ------------------------------------------------------------------ floor
    mb.box(((rx0 + rx1) / 2, (Y0 + ry1) / 2, (ZT - 0.06) / 2), (rx1 - rx0, ry1 - Y0, ZT - 0.06), m_lac)    # sub-floor
    bev = C.lod_pick(lod, 0.008, 0.0, 0.0)
    # sill beam along the facade
    C.board(mb, ((rx0 + rx1) / 2, ry1, ZT - 0.03), (rx1 - rx0 + 0.15, 0.16, 0.14), m_wood, bevel=bev, segs=1)
    # genkan (back-left): wet stone floor and the lacquer step edge
    gx1 = rx0 + gk
    gy1 = Y0 + 2.4
    mb.box(((rx0 + gx1) / 2, (Y0 + gy1) / 2, 0.06), (gk, 2.4, 0.12), m_wet)
    mb.box(((rx0 + gx1) / 2, gy1 - 0.0, (0.12 + ZT) / 2), (gk, 0.1, ZT - 0.12), m_lac)
    # tatami: front field (full width) and the back field right of the genkan, in front of the tokonoma
    toko_d = 0.85
    K.tatami_floor(mb, rx0 + 0.06, rx1 - 0.06, gy1 + 0.05, ry1 - 0.08, ZT, m_tat, m_lac, lod)
    K.tatami_floor(mb, gx1 + 0.06, rx1 - 0.06, Y0 + toko_d, gy1 + 0.05, ZT, m_tat, m_lac, lod)
    # back strip: tokonoma + itadoko (board floor) side alcove
    tk_w = 1.9
    if P['toko'] == 'right':
        tk0 = rx1 - 0.12 - tk_w
        ita = (gx1, tk0)
    else:
        tk0 = gx1 + 0.06
        ita = (tk0 + tk_w, rx1 - 0.12)
    C.board(mb, (tk0 + tk_w / 2, Y0 + toko_d / 2 + 0.06, ZT + 0.06), (tk_w, toko_d - 0.1, 0.12), m_ceil, bevel=bev * 0.5, segs=1)
    C.board(mb, (tk0 + tk_w / 2, Y0 + toko_d - 0.02, ZT + 0.06), (tk_w + 0.02, 0.06, 0.13), m_lac, bevel=bev * 0.5, segs=1)  # toko-gamachi
    mb.box(((ita[0] + ita[1]) / 2, Y0 + toko_d / 2 + 0.06, ZT - 0.02), (ita[1] - ita[0], toko_d - 0.1, 0.05), m_ceil)
    anchors['tansu_chest'] = [round((ita[0] + ita[1]) / 2, 3), round(Y0 + 0.4, 3), ZT, 0.0]

    # ------------------------------------------------------------------ walls (back, left, bath side)
    wt = 0.12
    mb.box(((rx0 + rx1) / 2, Y0 + wt / 2, ZC / 2), (rx1 - rx0, wt, ZC), m_wood)                        # back wall
    mb.box((rx0 + wt / 2, (Y0 + ry1) / 2, ZC / 2), (wt, ry1 - Y0, ZC), m_wood)                         # left wall
    # posts proud of the walls, and a nageshi rail at the kamoi height
    npost = max(3, round((rx1 - rx0) / 1.82))
    for k in range(npost + 1):
        x = rx0 + (rx1 - rx0) * k / npost
        x = _clamp(x, rx0 + 0.07, rx1 - 0.07)
        mb.box((x, Y0 + wt + 0.04, (ZT + ZC) / 2), (0.13, 0.08, ZC - ZT), m_wood)
    mb.box(((rx0 + rx1) / 2, Y0 + wt + 0.05, ZK + 0.05), (rx1 - rx0, 0.1, 0.1), m_wood)
    for k in range(1, max(2, round((ry1 - Y0) / 1.82))):
        y = Y0 + (ry1 - Y0) * k / max(2, round((ry1 - Y0) / 1.82))
        mb.box((rx0 + wt + 0.04, y, (ZT + ZC) / 2), (0.08, 0.13, ZC - ZT), m_wood)
    mb.box((rx0 + wt + 0.05, (Y0 + ry1) / 2, ZK + 0.05), (0.1, ry1 - Y0, 0.1), m_wood)
    # tokonoma: toko-bashira post, otoshigake beam, hanging scroll on the back wall
    tb_x = tk0 if P['toko'] == 'right' else tk0 + tk_w
    if lod <= 1:
        C.chamfered_bar(mb, (tb_x, Y0 + toko_d - 0.06, (ZT + ZC) / 2), (0.12, 0.12, ZC - ZT), m_wood, ch=0.012, axis='z')
    else:
        mb.box((tb_x, Y0 + toko_d - 0.06, (ZT + ZC) / 2), (0.12, 0.12, ZC - ZT), m_wood)
    mb.box((tk0 + tk_w / 2, Y0 + toko_d - 0.06, ZK + 0.25), (tk_w, 0.08, 0.14), m_wood)          # otoshigake
    scx = tk0 + tk_w / 2
    mb.box((scx, Y0 + wt + 0.006, ZT + 1.25), (0.5, 0.008, 1.3), m_scroll)                      # kakejiku
    if lod <= 1:
        for zz in (ZT + 0.6, ZT + 1.9):
            K.C.stick(mb, (scx - 0.29, Y0 + wt + 0.02, zz), (scx + 0.29, Y0 + wt + 0.02, zz), 0.012, 0.012, m_lac, segs=6)
    # bath-side wall: timber behind the genkan line, lit shoji onto the side room in front
    mb.box((rx1 - wt / 2, (Y0 + gy1) / 2, ZC / 2), (wt, gy1 - Y0, ZC), m_wood)
    nside = max(2, round((ry1 - gy1) / 1.9))
    for k in range(nside + 1):
        y = gy1 + (ry1 - gy1) * k / nside
        mb.box((rx1 - 0.07, y, (ZT + ZC) / 2), (0.14, 0.14, ZC - ZT), m_wood)
    mb.box((rx1 - 0.07, (gy1 + ry1) / 2, ZK + 0.06), (0.12, ry1 - gy1, 0.12), m_wood)
    mb.box((rx1 - 0.07, (gy1 + ry1) / 2, ZT - 0.03), (0.14, ry1 - gy1, 0.12), m_wood)
    for k in range(nside):
        ya, yb = gy1 + (ry1 - gy1) * k / nside + 0.07, gy1 + (ry1 - gy1) * (k + 1) / nside - 0.07
        # shoji built facing +Y, rotated onto the x = rx1 plane (facing -X, into the room)
        lay = mb._mark_old()
        lit = K.shoji_bay(mb, ya, yb, ZT, ZK, 0.0, shoji_mats, lod, SP, state='closed')
        vs = list({v for f in mb._new_faces(lay) for v in f.verts})
        for v in vs:
            x, y = v.co.x, v.co.y
            v.co.x, v.co.y = rx1 - 0.07 + y, x
        for a, b, za, zb, _ in lit:
            lights.append(C.light_entry((rx1 + 0.3, (a + b) / 2, (za + zb) / 2), color_k=2400, kind='area',
                                        watts=round(14 * (b - a) * (zb - za), 1), normal=[-1, 0, 0], size=[round(b - a, 3), round(zb - za, 3)]))
    # genkan partition (closed shoji on its tatami side) and the entry door in the back wall
    lay = mb._mark_old()
    K.shoji_bay(mb, Y0 + wt + 0.05, gy1 - 0.06, ZT, ZK, 0.0, shoji_mats, lod, SP, state='closed')
    for v in {v for f in mb._new_faces(lay) for v in f.verts}:
        x, y = v.co.x, v.co.y
        v.co.x, v.co.y = gx1 + y, x
    mb.box((gx1, Y0 + 1.2, ZK + 0.06), (0.12, 2.4, 0.12), m_wood)
    door = dict(SP, style='lattice', nbars=14, bar_w=0.022, ties=2, kick=0.3)
    from mathutils import Matrix
    KS = K.KS
    KS.panel_into(mb, Matrix.Translation((rx0 + gk / 2, Y0 + wt + 0.03, 0.12)), 0.95, 1.95, 'lattice',
                  shoji_mats, {0: 0, 1: 2, 2: 3}[lod], door)
    anchors['futon_bed'] = [round((gx1 + rx1) / 2 - 0.3, 3), round((gy1 + ry1) / 2 - 0.2, 3), ZT, 0.0]
    anchors['table_low'] = [round((gx1 + rx1) / 2 + 1.9, 3), round(ry1 - 1.3, 3), ZT, 0.0]

    # ------------------------------------------------------------------ front facade
    nb = P['bays']
    xs = [rx0 + (rx1 - rx0) * k / nb for k in range(nb + 1)]
    for k, x in enumerate(xs):
        xp = _clamp(x, rx0 + 0.08, rx1 - 0.08)
        if lod == 0:
            C.chamfered_bar(mb, (xp, ry1, (ZT + ZC) / 2), (0.15, 0.15, ZC - ZT), m_wood, ch=0.012, axis='z')
        else:
            mb.box((xp, ry1, (ZT + ZC) / 2), (0.15, 0.15, ZC - ZT), m_wood)
    C.board(mb, ((rx0 + rx1) / 2, ry1, ZK + 0.06), (rx1 - rx0, 0.14, 0.12), m_wood, bevel=bev * 0.5, segs=1)     # kamoi
    C.board(mb, ((rx0 + rx1) / 2, ry1, ZC - 0.08), (rx1 - rx0 + 0.1, 0.16, 0.16), m_wood, bevel=bev * 0.5, segs=1)  # head beam
    if P['open'] == 'mid':
        states = ['closed'] + ['open'] * (nb - 2) + ['closed']
    elif P['open'] == 'all_but_ends':
        states = ['half'] + ['open'] * (nb - 2) + ['closed']
    else:
        states = ['open' if k % 2 == 0 else 'closed' for k in range(nb)]
    for k in range(nb):
        a, b = xs[k] + 0.075, xs[k + 1] - 0.075
        lit = K.shoji_bay(mb, a, b, ZT, ZK, ry1, shoji_mats, lod, SP, state=states[k], flip=(k >= nb / 2))
        for a2, b2, za, zb, cy in lit:
            lights.append(C.light_entry(((a2 + b2) / 2, cy + 0.3, (za + zb) / 2), color_k=2400, kind='area',
                                        watts=round(14 * (b2 - a2) * (zb - za), 1), normal=[0, 1, 0],
                                        size=[round(b2 - a2, 3), round(zb - za, 3)]))
        # ranma transom: lit washi behind a simple kumiko
        z0r, z1r = ZK + 0.12, ZC - 0.16
        if lod <= 1:
            KS.panel_into(mb, Matrix.Translation(((a + b) / 2, ry1, z0r)), b - a, z1r - z0r, 'shoji', shoji_mats,
                          {0: 0, 1: 2}[lod], dict(SP, koshi=0.0, cols=max(4, round((b - a) / 0.3)), rows=2))
        else:
            KS.panel_into(mb, Matrix.Translation(((a + b) / 2, ry1, z0r)), b - a, z1r - z0r, 'shoji', shoji_mats, 3, SP)
    # ceiling, roof slab, eave, fascia, rafters
    xr0 = X0 if P['wrap'] else rx0
    mb.box(((rx0 + rx1) / 2, (Y0 + ry1) / 2, ZC + 0.03), (rx1 - rx0, ry1 - Y0, 0.06), m_ceil)
    mb.box(((xr0 + rx1) / 2, (Y0 + yv1) / 2, (ZC + 0.06 + HTOP - 0.02) / 2 + 0.01), (rx1 - xr0 + 0.1, yv1 - Y0, HTOP - ZC - 0.06), m_wood)
    C.board(mb, ((xr0 + rx1) / 2, yv1 - 0.06, HTOP - 0.15), (rx1 - xr0 + 0.14, 0.12, 0.3), m_wood, bevel=bev, segs=1)
    if lod == 0:
        nr = int((rx1 - xr0) / 0.45)
        for k in range(nr + 1):
            x = xr0 + 0.05 + (rx1 - xr0 - 0.1) * k / nr
            mb.box((x, (ry1 + yv1) / 2, ZC + 0.02), (0.06, yv1 - ry1 - 0.1, 0.08), m_wood)

    # ------------------------------------------------------------------ veranda
    xd0 = X0 if P['wrap'] else rx0
    K.deck(mb, xd0, rx1 + 0.4, ry1 + 0.08, yv1, ZV, m_deck, lod)
    mb.box(((xd0 + rx1 + 0.4) / 2, yv1 - 0.08, ZV - 0.12), (rx1 + 0.4 - xd0, 0.16, 0.18), m_wood)    # edge beam
    mb.box(((xd0 + rx1 + 0.4) / 2, (ry1 + yv1) / 2 - 0.1, (ZV - 0.035) / 2), (rx1 + 0.4 - xd0 - 0.3, yv1 - ry1 - 0.4, ZV - 0.035), m_lac)
    if P['wrap']:
        K.deck(mb, X0, rx0, Y0 + 2.6, ry1 + 0.08, ZV, m_deck, lod)
        mb.box(((X0 + rx0) / 2, (Y0 + 2.6 + ry1) / 2, (ZV - 0.035) / 2), (rx0 - X0 - 0.2, ry1 - Y0 - 2.6, ZV - 0.035), m_lac)
    # eave posts at the bay lines
    for x in xs:
        xp = _clamp(x, xd0 + 0.08, rx1 - 0.08)
        mb.box((xp, yv1 - 0.12, (ZV + ZC) / 2), (0.14, 0.14, ZC - ZV), m_wood)
    # rail: front edge (open for 1.1 m at the bath end) and the left end
    rpts = [(xd0 + 0.06, (Y0 + 2.7) if P['wrap'] else ry1 + 0.12), (xd0 + 0.06, yv1 - 0.05), (rx1 - 1.1, yv1 - 0.05)]
    K.rail(mb, rpts, ZV, m_wood, m_deck, lod, h=0.88, post_pitch=1.8)
    # bench on the veranda (seating), and lanterns
    if lod <= 1:
        bx = xd0 + 1.4
        C.board(mb, (bx, yv1 - 0.6, ZV + 0.4), (1.6, 0.42, 0.05), m_deck, bevel=bev, segs=1)
        for sx in (-1, 1):
            mb.box((bx + sx * 0.65, yv1 - 0.6, ZV + 0.19), (0.08, 0.36, 0.38), m_wood)
    lan = [(xd0 + 0.35, ry1 + 0.35, ZV), (rx1 - 0.35, yv1 - 0.4, ZV), (rx0 + 0.4, gy1 + 0.4, ZT),
           (rx1 + 0.6, Y0 + 2.4, 0.3)]
    for (x, y, z) in lan:
        ctr = C.lantern_head(mb, (x, y, z), dict(iron=m_iron, paper=m_andon), min(lod, 2), size=0.26, height=0.5, roof='hip')
        lights.append(C.light_entry(ctr, color_k=2200, watts=25))
    lights.append(C.light_entry(((rx0 + rx1) / 2, (Y0 + ry1) / 2, ZC - 0.1), color_k=2600, watts=120, kind='area',
                                normal=[0, 0, -1], size=[round((rx1 - rx0) * 0.5, 2), round((ry1 - Y0) * 0.5, 2)]))

    # ------------------------------------------------------------------ bath niche
    bx0 = rx1 + 0.05
    bcx = (bx0 + X1) / 2
    C.slab(mb, (bcx - 0.15, (Y0 + 2.0 + yv1) / 2 + 0.05, 0.15), bw - 0.6, yv1 - Y0 - 2.2, 0.3, m_wet, rc=0.5,
           m=C.lod_pick(lod, 3, 2, 1))
    anchors['stone_tub'] = [round(bcx - 0.2, 3), round((Y0 + 2.0 + yv1) / 2 + 0.6, 3), 0.3, 0.0]
    # cliff behind, cheek on the outer side, overhang slab above
    K.rock_mass(mb, bcx, Y0 + 1.15, bw / 2 * 0.86, 1.1, 0.0, HTOP, m_rock, r_rock, lod, inset=0.9)
    K.rock_mass(mb, X1 - 0.55, -0.3, 0.5, 3.0, 0.0, HTOP - 0.25, m_rock, r_rock, lod)
    K.rock_mass(mb, X1 - 0.5, 3.6, 0.45, 1.6, 0.0, 1.6, m_rock, r_rock, lod)
    K.rock_slab(mb, bcx + 0.1, -2.2, bw / 2 * 0.92, 4.6, HTOP, P['ovh_t'] * 1.3, m_rock, r_rock, lod)      # ledge out of the cliff
    K.rock_slab(mb, bcx + 0.6, 1.4, bw / 2 * 0.62, 1.9, HTOP, P['ovh_t'], m_rock, r_rock, lod)            # its lip over the tub
    if lod <= 1:
        n = C.lod_pick(lod, 7, 5)
        for k in range(n):
            x = bx0 + 0.4 + (bw - 1.2) * (k + r_misc.uniform(-0.2, 0.2)) / (n - 1)
            C.hull_rock(mb, (x, yv1 - 0.35 + r_misc.uniform(-0.1, 0.1), 0.25), (r_misc.uniform(0.22, 0.34),
                        r_misc.uniform(0.2, 0.3), r_misc.uniform(0.14, 0.22)), m_wet, r_misc, npts=C.lod_pick(lod, 12, 8), ground=0.2)
    return _finish(mb, P, lod, lights, anchors)


def _finish(mb, P, lod, lights, anchors):
    bm = mb.bm
    for v in bm.verts:                      # rocks stay inside the module footprint and the storey height
        v.co.x = _clamp(v.co.x, X0, X1)
        v.co.y = _clamp(v.co.y, Y0, Y1)
        v.co.z = _clamp(v.co.z, 0.0, HTOP)
    mirror = P['side'] < 0
    if mirror:
        for v in bm.verts:
            v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        for L in lights:
            L['pos'][0] = -L['pos'][0]
            if 'normal' in L:
                L['normal'][0] = -L['normal'][0]
        for k in anchors:
            anchors[k][0] = -anchors[k][0]
    dx, dy, dz = C.centre_base(mb)
    for L in lights:
        L['pos'] = [round(L['pos'][0] + dx, 3), round(L['pos'][1] + dy, 3), round(L['pos'][2] + dz, 3)]
    for k in anchors:
        a = anchors[k]
        anchors[k] = [round(a[0] + dx, 3), round(a[1] + dy, 3), round(a[2] + dz, 3), a[3]]
    o = genlib.finish(mb.to_object(ASSET))
    if lod <= 1:
        KG.uv_grain(o, [0, 1])               # hinoki dark_timber + deck: grain along posts, beams and boards
    C.set_json_props(o, kz_lights=lights if lod <= 2 else [L for L in lights if L.get('watts', 0) >= 100],
                     kz_anchors=anchors, kz_light_mode='lightmap+emissive', kz_anim=dict(type='none'),
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o
