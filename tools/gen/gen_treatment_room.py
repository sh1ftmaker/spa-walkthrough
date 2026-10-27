"""Treatment room module (b1_treatment, 6 instances): a small tatami massage room behind glowing shoji.

Targets (measured):
  * refs/gen/sheet-mod-pavilions.png #02 'TREATMENT ROOM MODULE' (crop .scratch/op15/tr_panel.png, 2x: 1 m bar
    83.6 px; the printed labels give 71.5 px/m, labels win): front eave-to-eave 6 m, side 5 m. Front: four posts,
    a centre opening ~2.2 m wide showing the room, one shoji pair (~0.75 m) each side of it, a narrow side bay
    with a bamboo blind (sudare) on the right under the same eave, a lit transom band (ranma) over the openings,
    tiled irimoya roof with upswept eaves and ridge end blocks, floor lanterns on the front corners, a step
    stone at the opening. Inside: tatami floor, a massage bed set across the room (~2.0 x 0.75 x 0.6 m, white
    linen top, folded towel, low headrest), a hanging scroll (~0.5 x 1.1 m) centred above it on the back wall,
    andon lamps on low side tables, a small bonsai in a pot. Side: one shoji window bay with a koshi kick board,
    board walls front and back of it.
  * Sheet height: floor to ridge 5.2 m at the label scale with a ~1 m rock plinth. The row and the proxy cap the
    module at 3.2 m (+5 % check tolerance; row range 3.0-3.6 m), so the walls are compressed: floor 0.25 m, door
    head 2.05 m above the ground (1.80 m clear), eave beam 2.31 m, roof eave ~2.4 m, ridge at H (3.35 default:
    at 3.2 the roof pitch drops to ~9 deg and reads flat). No rock plinth (the place model supplies the ground);
    only a 0.12 m basalt sill under the wall line.
  * Defaults per seed: 6.0 x 5.0 x 3.35 (sheet), 5.2 x 4.6 x 3.35, 4.4 x 4.2 x 3.25.

Parameters:
  w      4-6 m eave to eave             (default per seed 6.0 / 5.2 / 4.4)
  d      4-6 m eave to eave             (default 5.0 / 4.6 / 4.2; the proxy is 5.0, so d > 5.25 needs a new proxy)
  h      3.0-3.6 m ground to ridge top  (default 3.35 / 3.35 / 3.25; proxy 3.2, propose 3.4)
  front  'shoji' (shoji pair each side of the opening) | 'open' (all front bays open, sudare half down)
  props  True / False interior props (bed, scroll, plant, side tables, lamps)
  roof   'irimoya' | 'hip'
Seeds change: overall size (above), front style (seed 2 'open'), roof style (seed 2 'hip'), side bay with the
sudare (right / left / none on the 4.4 m module), bed side table layout, plant kind (bonsai / sasa / moss ball),
scroll position, shoji grid (3 x 5 / 2 x 6 / 4 x 6).

Materials: hinoki dark_timber (posts, beams, walls, sill beam), hinoki wet_oiled (shoji frames, kumiko, bed
frame, tables), washi_backlit (shoji paper, ranma, emissive 1.0), lantern_andon (lamps), tatami (mats),
lacquer_dark (tatami borders, scroll rollers), terry cream (mattress cover, headrest: the library linen renders
grey-speckled on a large flat), linen (folded towel, scroll mount), washi_backlit at 0.15 (interior plaster and the
scroll field: a warm lit wall), kawara (roof tiles via kzgeo_pavilion_engawa.roof), basalt_wet (sill, step stone, lantern
pads), bamboo (sudare), ceramic tenmoku (pot), moss (plant pads), iron (lantern frames).
Lighting: lightmap + emissive; obj['kz_lights'] has an area light per lit shoji field, the interior lamps
and the floor lanterns. Animation: none. Pivot: base centre, +Y is the front (the opening).
"""
import math

from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_pavilion_engawa as kp
import kzgeo_shoji_wall_bay as ks

ASSET = 'treatment_room'
FEATURES = ['tatami room behind glowing shoji', 'massage bed', 'hanging scroll', 'small plant', 'tiled eave']

SIZES = {1: (6.0, 5.0, 3.35), 2: (5.2, 4.6, 3.35), 3: (4.4, 4.2, 3.25)}
GRIDS = [(3, 5), (2, 6), (4, 6)]

RES = {
    0: dict(roof=dict(rings=5, n_long=12, n_short=8, up_rows=3, ribs=True, rib_segs=2, rib_prof=2, discs=True,
                      disc_n=8, rafters=False, fascia=True, fascia_n=6, soffit=True, ridge_prof='full', teeth=0),
            bars=True, mats=True, bevel=0.006, props=2, lantern=0, sudare=14),
    1: dict(roof=dict(rings=3, n_long=8, n_short=5, up_rows=2, ribs=False, rib_segs=0, rib_prof=0, discs=False,
                      disc_n=0, rafters=False, fascia=True, fascia_n=4, soffit=True, ridge_prof='box', teeth=0.5),
            bars=True, mats=True, bevel=0.0, props=1, lantern=1, sudare=7),
    2: dict(roof=dict(rings=2, n_long=4, n_short=3, up_rows=1, ribs=False, rib_segs=0, rib_prof=0, discs=False,
                      disc_n=0, rafters=False, fascia=True, fascia_n=2, soffit=False, ridge_prof='box', teeth=0),
            bars=False, mats=False, bevel=0.0, props=0, lantern=2, sudare=0),
    3: dict(roof=dict(rings=1, n_long=1, n_short=1, up_rows=1, ribs=False, rib_segs=0, rib_prof=0, discs=False,
                      disc_n=0, rafters=False, fascia=False, fascia_n=1, soffit=False, ridge_prof='tri', teeth=0),
            bars=False, mats=False, bevel=0.0, props=-1, lantern=3, sudare=0),
}


def params(seed, w=None, d=None, h=None, front=None, props=True, roof=None):
    s = ((seed - 1) % 3) + 1
    W0, D0, H0 = SIZES[s]
    g = C.rng(seed, 'size')
    if seed > 3:
        W0, D0 = g.uniform(4.4, 6.0), g.uniform(4.2, 5.0)
    P = dict(W=float(w or W0), D=float(d or D0), H=float(h or H0))
    P['front'] = front or C.cycle(seed, ['shoji', 'open', 'shoji'])
    P['roof'] = roof or C.cycle(seed, ['irimoya', 'hip', 'irimoya'])
    P['props'] = bool(props)
    gl = C.rng(seed, 'layout')
    P['annex'] = (1 if P['W'] >= 5.0 else 0) * C.cycle(seed, [1, -1, 1])
    P['grid'] = C.cycle(seed, GRIDS)
    P['plant'] = C.cycle(seed, ['bonsai', 'sasa', 'moss'])
    P['tables'] = C.cycle(seed, [2, 1, 2])
    P['scroll_dx'] = gl.uniform(-0.15, 0.15)
    P['up'] = gl.uniform(0.14, 0.22)
    P['ov'] = gl.uniform(0.48, 0.55)
    P['ovs'] = gl.uniform(0.45, 0.52)
    P['shoji_open'] = gl.uniform(0.15, 0.35)
    return P


def _bed(mb, x, y, z, mats, lod, r):
    """massage bed, long axis along x: hinoki frame with legs and apron, linen mattress, headrest, towel"""
    wood, cloth = mats['wood'], mats['cloth']
    L, Wb, Hb = 1.95, 0.75, 0.62
    bev = 0.006 if lod == 0 else 0.0
    if lod <= 1:
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((x + sx * (L / 2 - 0.07), y + sy * (Wb / 2 - 0.06), z + (Hb - 0.12) / 2),
                       (0.07, 0.07, Hb - 0.12), wood, bevel=bev)
        C.board(mb, (x, y, z + Hb - 0.19), (L - 0.06, Wb - 0.06, 0.1), wood, bevel=bev) if lod == 0 else \
            mb.box((x, y, z + Hb - 0.19), (L - 0.06, Wb - 0.06, 0.1), wood)
        mb.box((x, y, z + 0.14), (L - 0.14, 0.04, 0.04), wood)                    # stretcher
        if lod == 0:
            C.pillow(mb, (x, y, z + Hb - 0.14), L, Wb, 0.09, cloth, rc=0.06, m=2, puff=0.02)
            C.pillow(mb, (x - L / 2 + 0.22, y, z + Hb - 0.02), 0.3, 0.42, 0.06, cloth, rc=0.04, m=2, puff=0.015)
            C.pillow(mb, (x + L / 2 - 0.3, y + 0.02, z + Hb - 0.035), 0.36, 0.5, 0.05, mats['towel'], rc=0.03, m=2,
                     puff=0.01, yaw=0.05)
        else:
            mb.box((x, y, z + Hb - 0.09), (L, Wb, 0.1), cloth)
            mb.box((x - L / 2 + 0.22, y, z + Hb + 0.0), (0.3, 0.42, 0.06), cloth)
    else:
        mb.box((x, y, z + (Hb - 0.12) / 2), (L - 0.14, Wb - 0.14, Hb - 0.12), wood)
        mb.box((x, y, z + Hb - 0.07), (L, Wb, 0.14), cloth)


def build(lod, seed, w=None, d=None, h=None, front=None, props=True, roof=None, **_):
    P = params(seed, w, d, h, front, props, roof)
    R = RES[lod]
    W, D, H = P['W'], P['D'], P['H']
    r = C.rng(seed, 'roofnoise')
    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant='dark_timber')
    wood_s = mb.slot('hinoki', variant='wet_oiled')
    paper = mb.slot('washi_backlit', emissive_level=1.0)
    lamp = mb.slot('lantern_andon', emissive_level=1.0)
    tatami = mb.slot('tatami')
    heri = mb.slot('lacquer_dark')
    cloth = mb.slot('linen')
    towel = mb.slot('terry', variant='cream')
    plaster = mb.slot('washi_backlit', emissive_level=0.15)
    tile = mb.slot('kawara')
    stone = mb.slot('basalt_wet', wetness=0.45)
    bamboo = mb.slot('bamboo')
    pot = mb.slot('ceramic', variant='tenmoku')
    leaf = mb.slot('moss', tint=(0.45, 0.55, 0.32))
    iron = mb.slot('iron')
    lights = []

    ov, ovs = P['ov'], P['ovs']
    xw, yw = W / 2 - ovs, D / 2 - ov                # wall line half extents
    zf = 0.25                                       # floor top
    zk = 2.05                                       # door head (kamoi underside)
    zr = 2.19                                       # ranma top / beam underside
    z_bt = 2.31                                     # eave beam top
    pw = 0.15
    t = 0.09                                        # wall thickness

    # ---------------------------------------------------------------- roof
    hd = D / 2
    p_exp = 1.35
    rz = H - 0.32 if R['roof']['ridge_prof'] != 'tri' else H - 0.18
    f = (ov / hd) ** p_exp
    need = z_bt + 0.16
    z_e = (need - f * rz) / (1 - f)
    hd = D / 2 - 0.12                               # eave-end discs and fascia stand ~0.12 m proud
    f = ((ov - 0.12) / hd) ** p_exp
    z_e = (need - f * rz) / (1 - f)
    S = kp.RoofShape(W / 2, hd, z_e, rz - z_e, p=p_exp, up=P['up'] if lod < 3 else P['up'] * 0.6, style=P['roof'],
                     dg=hd * 0.5)
    if lod <= 2:
        S.hw = W / 2 - 0.1
        RR = dict(R['roof'], tp=0.26, thick=0.1)
        kp.roof(mb, S, RR, dict(tile=tile, ridge=tile, wood=wood, wood_d=heri), r, wall=dict(ov=ov - 0.12, ovs=ovs - 0.1, z_beam=z_bt))
    else:
        # LOD3: hip shell with a thick eave band (18 tris), same kawara slot and eave / ridge heights
        bm = mb.bm
        hw_, rx = W / 2 - 0.05, W / 2 - 0.05 - hd * 0.8
        e = [bm.verts.new((sx * hw_, sy * hd, z_e)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        eb = [bm.verts.new((v.co.x, v.co.y, z_e - 0.12)) for v in e]
        rg = [bm.verts.new((-rx, 0, H)), bm.verts.new((rx, 0, H))]
        fs = [bm.faces.new((e[3], e[2], rg[1], rg[0])), bm.faces.new((e[1], e[0], rg[0], rg[1])),
              bm.faces.new((e[0], e[3], rg[0])), bm.faces.new((e[2], e[1], rg[1])), bm.faces.new(eb[::-1])]
        fs += C.bridge_rings(bm, eb, e)
        mb._tag(fs, tile)

    # ---------------------------------------------------------------- sill, floor, posts, beams
    if lod <= 2:
        mb.box((0, 0, 0.06), (2 * xw + 0.16, 2 * yw + 0.16, 0.12), stone)
        mb.box((0, 0, (0.12 + zf) / 2), (2 * xw, 2 * yw, zf - 0.12), wood)
    else:
        mb.box((0, 0, zf / 2), (2 * xw + 0.1, 2 * yw + 0.1, zf), stone)
    # front bay layout (x): [annex][shoji][opening][shoji] or mirrored annex
    ax = P['annex']
    aw = 0.9 if ax else 0.0
    x0, x1 = -xw, xw
    if ax > 0:
        x1 = xw - aw
    elif ax < 0:
        x0 = -xw + aw
    Wm = x1 - x0
    xc = (x0 + x1) / 2
    sh_w = 0.24 * Wm
    op0, op1 = x0 + sh_w, x1 - sh_w
    front_posts = sorted({-xw, xw, x0, x1, op0, op1})
    if lod <= 2:
        for x in front_posts:
            xx = max(-xw + pw / 2, min(xw - pw / 2, x))
            mb.box((xx, yw - pw / 2, (zf + z_bt) / 2), (pw, pw, z_bt - zf), wood, bevel=R['bevel'])
        for x in (-xw + pw / 2, xw - pw / 2):
            mb.box((x, -yw + pw / 2, (zf + z_bt) / 2), (pw, pw, z_bt - zf), wood, bevel=R['bevel'])
        for sx in (-1, 1):
            mb.box((sx * (xw - pw / 2), 0.0, (zf + z_bt) / 2), (pw, pw, z_bt - zf), wood, bevel=R['bevel'])
        # eave beams (keta) all round, kamoi over the front openings
        for sy in (-1, 1):
            mb.box((0, sy * (yw - 0.08), z_bt - 0.07), (2 * xw + 0.3, 0.16, 0.14), wood)
        for sx in (-1, 1):
            mb.box((sx * (xw - 0.08), 0, z_bt - 0.07), (0.16, 2 * yw, 0.14), wood)
        mb.box((0, yw - 0.06, zk + 0.04), (2 * xw, 0.1, 0.08), wood)
        if lod <= 1:
            mb.box((0, yw - 0.06, zf + 0.03), (2 * xw, 0.1, 0.06), wood)      # threshold (shikii)
    if lod == 3:
        mb.box((0, 0, (zf + z_e) / 2), (2 * xw, 2 * yw, z_e - zf), wood)
    # ceiling board under the beams
    if lod <= 1:
        mb.box((0, 0, z_bt - 0.16), (2 * xw - 0.1, 2 * yw - 0.1, 0.03), wood_s if lod <= 1 else wood)

    # ---------------------------------------------------------------- front: shoji, opening, ranma, annex sudare
    Mf = kg.frame((0, yw - 0.05, 0), (0, 1, 0))
    cols, rows = P['grid']
    mats = dict(wood=wood_s, paper=paper)
    if lod == 3:
        ks.quad(mb, Mf, [(x0, 0.08, zf), (x1, 0.08, zf), (x1, 0.08, z_bt - 0.1), (x0, 0.08, z_bt - 0.1)], paper)
    else:
        if P['front'] == 'shoji':
            for a, b in ((x0 + pw / 2, op0 - pw / 2), (op1 + pw / 2, x1 - pw / 2)):
                if lod <= 1:
                    ks.shoji_run(mb, Mf, a, b, zf + 0.06, zk, 0.0, mats, lod, 2, r, cols=max(1, cols - 1), rows=rows,
                                 koshi=0.25, bars_lod=1 if R['bars'] else -1)
                else:
                    ks.quad(mb, Mf, [(a, 0.0, zf + 0.06), (b, 0.0, zf + 0.06), (b, 0.0, zk), (a, 0.0, zk)], paper)
                    ks.lattice_long(mb, Mf, a, b, zf + 0.06, zk, 0.012, wood_s, 2, 3)
                lights.append(C.light_entry(((a + b) / 2, yw - 0.3, (zf + zk) / 2), color_k=2700, watts=25, kind='area',
                                            size=[round(b - a, 2), round(zk - zf, 2)], dir=[0, 1, 0]))
        else:
            # open front: shoji slid back behind the posts (paper edge shows), sudare half down in the side bays
            for a, b in ((x0 + pw / 2, op0 - pw / 2), (op1 + pw / 2, x1 - pw / 2)):
                zs = zk - (zk - zf) * 0.42
                mb.box(((a + b) / 2, yw + 0.02, (zs + zk) / 2), (b - a, 0.012, zk - zs), bamboo)
                if R['sudare']:
                    mb.cylinder(((a + b) / 2, yw + 0.025, zs), 0.025, b - a + 0.02, bamboo, segs=6, rot=(0, math.pi / 2, 0))
                    for u in (a + 0.15, b - 0.15):
                        mb.box((u, yw + 0.03, (zs + zk) / 2), (0.012, 0.012, zk - zs + 0.02), heri)   # binding cords
        # ranma band over the front: lit washi with vertical bars
        ra, rb = -xw + pw / 2, xw - pw / 2
        ks.quad(mb, Mf, [(ra, -0.02, zk + 0.08), (rb, -0.02, zk + 0.08), (rb, -0.02, zr), (ra, -0.02, zr)], paper)
        if R['bars']:
            nr = int((rb - ra) / 0.3)
            for k in range(1, nr):
                ks.bar(mb, Mf, (ra + (rb - ra) * k / nr, 0.0, (zk + 0.08 + zr) / 2), (0.025, 0.03, zr - zk - 0.08), wood)
        # annex bay: bamboo blind (sudare) in a frame
        if ax:
            a, b = (x1 + pw / 2, xw - pw) if ax > 0 else (-xw + pw, x0 - pw / 2)
            ks.quad(mb, Mf, [(a, -0.03, zf + 0.06), (b, -0.03, zf + 0.06), (b, -0.03, zk), (a, -0.03, zk)], wood)
            if R['sudare']:
                n = R['sudare']
                for k in range(n):
                    u = a + (b - a) * (k + 0.5) / n
                    ks.bar(mb, Mf, (u, 0.0, (zf + 0.1 + zk) / 2), (0.022, 0.025, zk - zf - 0.12), bamboo)
            else:
                ks.quad(mb, Mf, [(a, 0.0, zf + 0.06), (b, 0.0, zf + 0.06), (b, 0.0, zk), (a, 0.0, zk)], bamboo)
            mb.box(((a + b) / 2, yw - 0.12, (zf + zk) / 2), (b - a + 0.04, 0.04, zk - zf), wood)   # back of the annex
        # front wall boards above the ranma
        mb.box((0, yw - 0.05, (zr + z_bt - 0.14) / 2), (2 * xw, 0.05, z_bt - 0.14 - zr), wood)

    # ---------------------------------------------------------------- side walls: shoji window, boards
    for sx in (-1, 1):
        Ms = kg.frame((sx * (xw - 0.05), 0, 0), (sx, 0, 0))
        # u runs along -y for +x (frame x = fwd x up); window centred on the wall
        u0, u1 = -0.7, 0.7
        zw0, zw1 = zf + 0.55, zk
        if lod <= 1:
            ks.shoji_run(mb, Ms, u0, u1, zw0, zw1, 0.0, mats, lod, 2, r, cols=cols - 1 if cols > 2 else 2, rows=rows - 1,
                         bars_lod=1 if R['bars'] else -1)
        elif lod == 2:
            ks.quad(mb, Ms, [(u0, 0.0, zw0), (u1, 0.0, zw0), (u1, 0.0, zw1), (u0, 0.0, zw1)], paper)
        lights.append(C.light_entry((sx * (xw + 0.2), 0, (zw0 + zw1) / 2), color_k=2700, watts=15, kind='area',
                                    size=[1.4, round(zw1 - zw0, 2)], dir=[sx, 0, 0]))
        if lod <= 2:
            for ua, ub in ((-yw + pw, u0), (u1, yw - pw)):
                mb.box((sx * (xw - 0.06), (ua + ub) / 2, (zf + z_bt - 0.14) / 2), (t * 0.6, ub - ua, z_bt - 0.14 - zf), wood)
            mb.box((sx * (xw - 0.06), 0, (zf + zw0) / 2), (t * 0.6, u1 - u0, zw0 - zf), wood)      # koshi under window
            mb.box((sx * (xw - 0.06), 0, (zw1 + z_bt - 0.14) / 2), (t * 0.6, u1 - u0, z_bt - 0.14 - zw1), wood)
        elif lod == 2:
            mb.box((sx * (xw - 0.05), 0, (zf + z_bt) / 2), (0.1, 2 * yw, z_bt - zf), wood)
    # back wall: board outside, plaster inside
    if lod <= 2:
        mb.box((0, -yw + 0.04, (zf + z_bt) / 2), (2 * xw, 0.06, z_bt - zf), wood)
        ks.quad(mb, kg.frame((0, -yw + 0.075, 0), (0, 1, 0)),
                [(-xw + 0.1, 0.0, zf), (xw - 0.1, 0.0, zf), (xw - 0.1, 0.0, z_bt - 0.18), (-xw + 0.1, 0.0, z_bt - 0.18)],
                plaster)

    # ---------------------------------------------------------------- tatami floor
    if lod <= 2:
        rx0, rx1 = -xw + 0.1, xw - 0.1
        ry0, ry1 = -yw + 0.08, yw - 0.1
        if R['mats']:
            nx = max(2, round((rx1 - rx0) / 1.8))
            ny = max(2, round((ry1 - ry0) / 0.9))
            mx, my = (rx1 - rx0) / nx, (ry1 - ry0) / ny
            for i in range(nx):
                for j in range(ny):
                    cx = rx0 + mx * (i + 0.5) + (mx / 2 if (j % 2 and i == nx - 1) else 0) * 0
                    cy = ry0 + my * (j + 0.5)
                    mb.box((cx, cy, zf + 0.025), (mx - 0.012, my - 0.012, 0.05), tatami)
                    if lod == 0:
                        for sy in (-1, 1):                  # heri borders on the long edges
                            mb.box((cx, cy + sy * (my / 2 - 0.02), zf + 0.051), (mx - 0.02, 0.03, 0.004), heri)
        else:
            mb.box((0, (ry0 + ry1) / 2, zf + 0.025), (rx1 - rx0, ry1 - ry0, 0.05), tatami)
    zt = zf + 0.05

    # ---------------------------------------------------------------- interior props
    if P['props'] and R['props'] >= 0:
        gp = C.rng(seed, 'props')
        by = -yw + 0.08 + 0.75 / 2 + 0.55
        bx = (op0 + op1) / 2                       # bed and scroll centred in the front opening
        _bed(mb, bx, by, zt, dict(wood=wood_s, cloth=towel, towel=cloth), lod, gp)   # linen renders grey-speckled: cover in cream terry, linen towel
        # hanging scroll on the back wall
        sx_ = bx + P['scroll_dx']
        sw_, sh_ = 0.52, 1.1
        sz0 = zt + 0.95
        yb = -yw + 0.08
        if lod <= 1:
            ks.quad(mb, kg.frame((0, yb + 0.004, 0), (0, 1, 0)),
                    [(sx_ - sw_ / 2, 0, sz0), (sx_ + sw_ / 2, 0, sz0), (sx_ + sw_ / 2, 0, sz0 + sh_), (sx_ - sw_ / 2, 0, sz0 + sh_)],
                    cloth)
            ks.quad(mb, kg.frame((0, yb + 0.007, 0), (0, 1, 0)),
                    [(sx_ - sw_ / 2 + 0.07, 0, sz0 + 0.2), (sx_ + sw_ / 2 - 0.07, 0, sz0 + 0.2),
                     (sx_ + sw_ / 2 - 0.07, 0, sz0 + sh_ - 0.25), (sx_ - sw_ / 2 + 0.07, 0, sz0 + sh_ - 0.25)], plaster)
            for zz in (sz0 - 0.01, sz0 + sh_ + 0.01):
                mb.cylinder((sx_, yb + 0.02, zz), 0.014, sw_ + 0.08, heri, segs=6, rot=(0, math.pi / 2, 0))
            C.stick(mb, (sx_ - 0.15, yb + 0.02, sz0 + sh_ + 0.02), (sx_, yb + 0.012, sz0 + sh_ + 0.25), 0.003, 0.003, heri, segs=3)
            C.stick(mb, (sx_ + 0.15, yb + 0.02, sz0 + sh_ + 0.02), (sx_, yb + 0.012, sz0 + sh_ + 0.25), 0.003, 0.003, heri, segs=3)
        else:
            ks.quad(mb, kg.frame((0, yb + 0.004, 0), (0, 1, 0)),
                    [(sx_ - sw_ / 2, 0, sz0), (sx_ + sw_ / 2, 0, sz0), (sx_ + sw_ / 2, 0, sz0 + sh_), (sx_ - sw_ / 2, 0, sz0 + sh_)],
                    cloth)
        # side tables with andon lamps, plant
        tabs = [-1, 1] if P['tables'] == 2 else [-1]
        for k, side in enumerate(tabs):
            tx = bx + side * (1.95 / 2 + 0.38)
            ty = by - 0.1
            if lod <= 1:
                mb.box((tx, ty, zt + 0.17), (0.4, 0.36, 0.04), wood_s, bevel=R['bevel'])
                for ex in (-1, 1):
                    mb.box((tx + ex * 0.16, ty, zt + 0.075), (0.04, 0.32, 0.15), wood_s)
            else:
                mb.box((tx, ty, zt + 0.095), (0.4, 0.36, 0.19), wood_s)
            top = zt + 0.19
            if side < 0:
                c = C.lantern_head(mb, (tx, ty, top), dict(iron=iron, paper=lamp), min(2, R['lantern']), size=0.17,
                                   height=0.3)
                lights.append(C.light_entry(c, color_k=2300, watts=20))
            else:
                if lod <= 1:
                    ks.plant(mb, (tx, ty, top), dict(pot=pot, trunk=wood_s, leaf=leaf, bamboo=bamboo), lod, gp,
                             P['plant'], scale=1.6)
                else:
                    mb.cylinder((tx, ty, top + 0.06), 0.11, 0.12, pot, segs=6)
                    mb.ico((tx, ty, top + 0.25), 0.15, leaf, subdiv=0)
        if P['tables'] == 1:
            px, py = bx + (1.95 / 2 + 0.45), by + 0.35
            if lod <= 1:
                ks.plant(mb, (px, py, zt), dict(pot=pot, trunk=wood_s, leaf=leaf, bamboo=bamboo), lod, gp, P['plant'],
                         scale=2.2)
            else:
                mb.cylinder((px, py, zt + 0.08), 0.14, 0.16, pot, segs=6)
                mb.ico((px, py, zt + 0.35), 0.2, leaf, subdiv=0)

    # ---------------------------------------------------------------- step stone, floor lanterns
    sy_ = yw + 0.24
    if lod <= 2:
        g = C.rng(seed, 'step')
        f0 = C.stone_outline(g, 0.36, aspect=1.6, bites=1)
        if lod <= 1:
            lay = mb._mark_old()
            C.cobble(mb, f0, C.lod_pick(lod, 24, 12), 0.18, stone, stone, r=g)
            vs = {v for f_ in mb._new_faces(lay) for v in f_.verts}
            for v in vs:
                v.co.x += (op0 + op1) / 2
                v.co.y += sy_
        else:
            mb.box(((op0 + op1) / 2, sy_, 0.09), (0.8, 0.5, 0.18), stone)
    for sx in (-1, 1):
        lx, ly = sx * (xw + 0.1), yw + 0.22
        if R['lantern'] <= 2:
            if R['lantern'] <= 1:
                mb.box((lx, ly, 0.04), (0.3, 0.3, 0.08), stone)
            c = C.lantern_head(mb, (lx, ly, 0.08), dict(iron=iron, paper=lamp), R['lantern'], size=0.22, height=0.42)
        else:
            c = Vector((lx, ly, 0.25))
        lights.append(C.light_entry(c, color_k=2200, watts=20))

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    for L in lights:
        L['pos'] = [round(L['pos'][0] + dx, 4), round(L['pos'][1] + dy, 4), round(L['pos'][2] + dz, 4)]
    C.set_json_props(o, kz_lights=lights, kz_params=dict(w=W, d=D, h=H, front=P['front'], roof=P['roof'],
                                                         props=P['props']))
    return genlib.finish(o)
