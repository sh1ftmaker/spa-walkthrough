"""Tansu chest (tansu_chest) for the cliff suites suite_1a..suite_4c: a low dark wood chest of drawers with
iron pulls and a small vase or teapot on top.

Targets (measured before coding)
  * lookbook 21 (private suite, back wall left of the shoji): chest ~1.2-1.4 m wide (vs the 2.0 m door
    behind it), ~0.55-0.6 m to the top, ~0.45 m deep; dark brown wood, two rows of drawers (top row split in
    two or three, lower row wider), small dark iron pulls, a plinth/shadow line at the foot; a dark round vase
    with a bare branch on top. A second, smaller chest on the far wall (h ~0.6, w ~0.8) carries a lamp.
  * lookbook 32 (suite plan): storage along the genkan and the side room, ~1.2 x 0.45 m in plan.
  Built: w 0.8-1.6, d 0.42-0.46, h 0.4-0.9 (row), 2-4 drawer rows, plinth 0.04, top 0.025 with 10 mm
  overhang, fronts 18 mm proud with 8 mm reveals, warabite (bail) pulls 70 mm wide.

Construction (front +Y; pivot at the base centre)
  * carcass: bevelled box + top board, `hinoki` walnut (near-black wood); recessed plinth `lacquer_black`.
    (Row asks lacquer_dark: on the first sheet its mottling read as silver speckle over the whole carcass.)
  * drawer / door fronts: bevelled boards, `hinoki` dark_timber (dark brown grain), proud of the carcass.
  * pulls: iron back plate + a hanging U bail (tube); iron corner plates on the four front corners
    (and kannon-door style iron lock plate on the cabinet door), `iron`.
  * topper: tenmoku vase with a bare branch (bark sticks), or an iron tetsubin teapot, or a small vase.
  LOD1: 1-seg chamfers, coarser tubes and lathe. LOD2: plain boxes, pulls as small iron blocks, topper as
  a 6-sided lathe, corner plates dropped. LOD3: carcass + a dark pull strip + topper block (~30 tris).
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 1.2 x 0.45 x 0.6 m)
  style   drawers | cabinet | kasane      (default cycles with the seed: 1 drawers, 2 cabinet, 3 kasane)
  w       0.8-1.6 m     h 0.4-0.9 m
  drawers number of drawer rows 2-4 (default by style and seed)
  pulls   bail | ring                      (default seeded)
  topper  vase_branch | teapot | vase | none   (default seeded; seeds 1-3 show three different ones)
Seeds change: style (all drawers / sliding-door cabinet beside a drawer stack / two stacked sections with
side carry handles), width, height, drawer rows and splits, pull type, topper and its position.
"""
import math

import bmesh

from mathutils import Vector

import genlib
import kzgeo_bridge_arched as KG
import kzgeo_common as C

ASSET = 'tansu_chest'
FEATURES = ['low dark wood chest', 'drawer fronts', 'iron pulls', 'vase or teapot on top']
STYLES = ['drawers', 'cabinet', 'kasane']
TOPPERS = ['vase_branch', 'teapot', 'vase']


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _quad(mb, x0, x1, z0, z1, y, mi):
    """single-sided front-facing quad (LOD2/3 fronts and pulls)"""
    vs = [mb.bm.verts.new(v) for v in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]
    f = mb.bm.faces.new(vs)
    mb._tag([f], mi)
    return f


def _bail(mb, x, z, yf, mi, lod, kind):
    """warabite pull on the front plane y = yf: back plate + U bail hanging down (or a ring)"""
    if lod >= 2:
        _quad(mb, x - 0.04, x + 0.04, z - 0.018, z + 0.018, yf + 0.004, mi)
        return
    if lod >= 1:
        mb.box((x, yf + 0.004, z), (0.075, 0.008, 0.03), mi)
        if lod == 1:
            mb.box((x, yf + 0.012, z - 0.026), (0.06, 0.008, 0.009), mi)
        return
    if kind == 'ring':
        mb.box((x, yf + 0.002, z + 0.012), (0.045, 0.004, 0.045), mi)
        n = 6
        pts = [Vector((x + 0.026 * math.sin(2 * math.pi * k / n), yf + 0.009, z - 0.004 - 0.026 * math.cos(2 * math.pi * k / n)))
               for k in range(n + 1)]
        C.tube(mb, pts, [0.0045] * len(pts), mi, sides=4, cap0=True, cap1=True)
        return
    mb.box((x, yf + 0.002, z), (0.085, 0.004, 0.034), mi)
    n = 3
    pts = []
    for k in range(n + 1):
        a = math.pi * k / n
        pts.append(Vector((x - 0.032 * math.cos(a), yf + 0.012, z - 0.006 - 0.022 * math.sin(a))))
    pts = [Vector((pts[0].x, yf + 0.004, z + 0.002))] + pts + [Vector((pts[-1].x, yf + 0.004, z + 0.002))]
    C.tube(mb, pts, [0.0045] * len(pts), mi, sides=4, cap0=True, cap1=True)


def _topper(mb, kind, x, y, z, lod, mats, r):
    seg = C.lod_pick(lod, 12, 8, 8, 4)
    if kind in ('vase_branch', 'vase'):
        s = 1.0 if kind == 'vase_branch' else 0.7
        prof = [(0.0, 0.0), (0.045 * s, 0.0), (0.075 * s, 0.07 * s), (0.08 * s, 0.11 * s), (0.06 * s, 0.17 * s),
                (0.028 * s, 0.22 * s), (0.026 * s, 0.25 * s), (0.034 * s, 0.27 * s), (0.0, 0.265 * s)]
        if lod >= 2:
            prof = [(0.0, 0.0), (0.06 * s, 0.0), (0.08 * s, 0.11 * s), (0.03 * s, 0.22 * s), (0.03 * s, 0.27 * s), (0.0, 0.27 * s)]
        C.lathe(mb, prof, seg, mats['vase'], base=(x, y, z))
        if kind == 'vase_branch' and lod <= 1:
            base = Vector((x, y, z + 0.25))
            for b in range(C.lod_pick(lod, 3, 2)):
                a = r.uniform(0, 2 * math.pi)
                tilt = r.uniform(0.25, 0.55)
                L = r.uniform(0.22, 0.36)
                tip = base + Vector((math.sin(tilt) * math.cos(a), math.sin(tilt) * math.sin(a) * 0.5, math.cos(tilt))) * L
                C.stick(mb, base, tip, 0.006, 0.002, mats['branch'], segs=C.lod_pick(lod, 5, 4))
                if lod == 0:
                    mid = base.lerp(tip, 0.6)
                    tw = mid + Vector((r.uniform(-0.12, 0.12), r.uniform(-0.04, 0.04), r.uniform(0.06, 0.14)))
                    C.stick(mb, mid, tw, 0.003, 0.0015, mats['branch'], segs=4)
    else:   # tetsubin teapot (iron) on a walnut coaster
        if lod <= 1:
            C.board(mb, (x, y, z + 0.006), (0.2, 0.2, 0.012), mats['tray'], bevel=0.003 if lod == 0 else 0.0)
            z += 0.012
        prof = [(0.0, 0.0), (0.07, 0.0), (0.09, 0.04), (0.088, 0.075), (0.06, 0.105), (0.035, 0.112), (0.034, 0.118),
                (0.012, 0.125), (0.01, 0.135), (0.0, 0.14)]
        if lod >= 2:
            prof = [(0.0, 0.0), (0.08, 0.0), (0.09, 0.05), (0.05, 0.11), (0.0, 0.13)]
        C.lathe(mb, prof, seg, mats['pot'], base=(x, y, z))
        if lod <= 1:
            C.stick(mb, (x + 0.07, y, z + 0.05), (x + 0.15, y, z + 0.1), 0.014, 0.007, mats['pot'], segs=C.lod_pick(lod, 6, 4))
            n = C.lod_pick(lod, 7, 4)
            pts = [Vector((x + 0.06 * math.cos(math.pi * k / n), y, z + 0.11 + 0.07 * math.sin(math.pi * k / n))) for k in range(n + 1)]
            C.tube(mb, pts, [0.005] * len(pts), mats['pot'], sides=C.lod_pick(lod, 6, 4), cap0=True, cap1=True)


def build(lod, seed, style=None, w=None, h=None, drawers=None, pulls=None, topper=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'dims')
    W = _clamp(w, 0.8, 1.6) if w else {'drawers': g.uniform(1.1, 1.3), 'cabinet': g.uniform(1.0, 1.25),
                                       'kasane': g.uniform(0.8, 1.0)}[style]
    H = _clamp(h, 0.4, 0.9) if h else {'drawers': g.uniform(0.52, 0.6), 'cabinet': g.uniform(0.45, 0.55),
                                       'kasane': g.uniform(0.58, 0.62)}[style]
    D = g.uniform(0.42, 0.46)
    gr = C.rng(seed, 'rows')
    rows = int(_clamp(drawers, 2, 4)) if drawers else {'drawers': gr.choice([2, 3]), 'cabinet': gr.choice([2, 3]),
                                                       'kasane': gr.choice([3, 4])}[style]
    top_split = gr.choice([2, 3]) if W > 1.0 else 2
    pull_kind = pulls or C.pick(seed, 'pull', ['bail', 'bail', 'ring'])
    gt = C.rng(seed, 'topper')
    tkind = topper or (TOPPERS[(seed - 1) % 3] if seed <= 3 else gt.choice(TOPPERS + ['none']))
    tx = gt.uniform(0.18, 0.32) * W * gt.choice([-1, 1])
    r_branch = C.rng(seed, 'branch')

    mb = genlib.MeshBuilder()
    m_body = mb.slot('hinoki', variant='walnut')          # lacquer_dark read speckled silver at chest scale (sheet r0)
    m_front = mb.slot('hinoki', variant='dark_timber')
    m_plinth = mb.slot('lacquer_black')
    m_iron = mb.slot('iron')
    mats = dict(vase=mb.slot('ceramic', variant='tenmoku', roughness_offset=0.25), branch=mb.slot('bark'), pot=m_iron,
                tray=m_front)

    PL, TT, OV = 0.04, 0.025, 0.01                  # plinth h, top thickness, top overhang
    zb0, zb1 = PL, H - TT                          # carcass between plinth and top
    yf = D / 2 - OV                                # carcass front plane
    if style == 'kasane':
        zsplit = PL + (zb1 - PL) * 0.52

    if lod == 3:
        f = mb.box((0, -OV / 2, H / 2), (W, D - OV, H), m_body)
        bot = [q for q in f if q.normal.z < -0.5 or sum(v.co.z for v in q.verts) / 4 < 1e-4]
        bmesh.ops.delete(mb.bm, geom=bot[:1], context='FACES_ONLY')      # sits on the floor: no bottom face
        y0 = yf + 0.004 + 0.002
        vs = [mb.bm.verts.new(v) for v in ((-W * 0.3, y0, zb1 - 0.12), (W * 0.3, y0, zb1 - 0.12), (W * 0.3, y0, zb1 - 0.09), (-W * 0.3, y0, zb1 - 0.09))]
        mb._tag([mb.bm.faces.new(vs)], m_iron)                           # one dark pull strip (single-sided)
        if tkind != 'none':
            th = 0.22 if tkind != 'teapot' else 0.13
            C.lathe(mb, [(0.07, 0.0), (0.07, th * 0.6), (0.03, th)], 4, mats['pot' if tkind == 'teapot' else 'vase'],
                    base=(tx, -0.02, H), phase=math.pi / 4)
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    bev = C.lod_pick(lod, 0.006, 0.004, 0.0)
    segs = C.lod_pick(lod, 2, 1, 1)
    # plinth (recessed), carcass, top
    mb.box((0, -OV / 2, PL / 2), (W - 0.04, D - OV - 0.04, PL), m_plinth)
    if style == 'kasane':
        for z0, z1 in ((zb0, zsplit), (zsplit, zb1)):
            C.board(mb, (0, -OV / 2, (z0 + z1) / 2), (W - 0.004, D - OV, z1 - z0 - 0.004), m_body, bevel=bev, segs=1)
    else:
        C.board(mb, (0, -OV / 2, (zb0 + zb1) / 2), (W, D - OV, zb1 - zb0), m_body, bevel=bev, segs=1)
    C.board(mb, (0, 0, H - TT / 2), (W + 2 * OV, D, TT), m_body, bevel=bev, segs=1)

    # front layout: list of (x0, x1, z0, z1, kind)
    FR, GAP = 0.03, 0.008                          # face frame margin, reveal
    cells = []
    if style == 'cabinet':
        xd = -W / 2 + FR + (W - 2 * FR) * gr.uniform(0.55, 0.62)     # doors left, drawer stack right
        nd = rows + 1
        for k in range(nd):
            z0 = zb0 + FR + (zb1 - zb0 - 2 * FR) * k / nd
            z1 = zb0 + FR + (zb1 - zb0 - 2 * FR) * (k + 1) / nd
            cells.append((xd + GAP, W / 2 - FR, z0, z1, 'drawer'))
        xm = (-W / 2 + FR + xd) / 2
        cells.append((-W / 2 + FR, xm + 0.01, zb0 + FR, zb1 - FR, 'door'))
        cells.append((xm - 0.01, xd, zb0 + FR, zb1 - FR, 'door_back'))
    else:
        bands = [(zb0, zsplit), (zsplit, zb1)] if style == 'kasane' else [(zb0, zb1)]
        nrow_band = [rows // 2, rows - rows // 2] if style == 'kasane' else [rows]
        for (z0b, z1b), nr in zip(bands, nrow_band):
            hs = [1.0] * nr
            hs[-1] = 0.75 if nr > 1 else 1.0         # shallower top row
            tot = sum(hs)
            z = z0b + FR
            for k, hk in enumerate(hs):
                dz = (z1b - z0b - 2 * FR) * hk / tot
                top_row = (k == nr - 1) and (z1b == zb1)
                n_split = top_split if top_row else 1
                for j in range(n_split):
                    x0 = -W / 2 + FR + (W - 2 * FR) * j / n_split
                    x1 = -W / 2 + FR + (W - 2 * FR) * (j + 1) / n_split
                    cells.append((x0, x1, z, z + dz, 'drawer'))
                z += dz

    pz = []
    for x0, x1, z0, z1, kind in cells:
        cw, ch = x1 - x0 - GAP, z1 - z0 - GAP
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        proud = 0.018 if kind != 'door_back' else 0.008
        if lod == 2:
            proud = 0.004
            _quad(mb, cx - cw / 2, cx + cw / 2, cz - ch / 2, cz + ch / 2, yf + proud, m_front)
        else:
            C.board(mb, (cx, yf + proud / 2 - 0.002, cz), (cw, proud + 0.004, ch), m_front, bevel=C.lod_pick(lod, 0.004, 0.0, 0.0), segs=1)
        yff = yf + proud - 0.002
        if kind == 'drawer':
            npull = 2 if cw > 0.62 else 1
            for p in range(npull):
                px = cx if npull == 1 else cx + (p - 0.5) * cw * 0.5
                pz.append((px, cz + min(0.0, ch * 0.08), yff))
        elif kind == 'door':
            # iron lock plate and a recessed finger pull on the front sliding door
            if lod <= 1:
                C.board(mb, (x1 - 0.06, yff + 0.002, cz + 0.02), (0.07, 0.004, 0.12), m_iron, bevel=0.0015 if lod == 0 else 0.0)
            pz.append((x1 - 0.06, cz - 0.08, yff))
    for px, pzz, yff in pz:
        _bail(mb, px, pzz, yff, m_iron, lod, pull_kind)

    # iron corner plates (L-shaped, front + side) at the carcass corners, and kasane carry handles
    if lod == 0:
        t = 0.004
        for sx in (-1, 1):
            for zc in (zb0 + 0.04, H - TT - 0.04):
                mb.box((sx * (W / 2 - 0.03), yf + t / 2, zc), (0.06, t, 0.08), m_iron)
                mb.box((sx * (W / 2 + t / 2), yf - 0.03, zc), (t, 0.06, 0.08), m_iron)
        if style == 'kasane':
            for sx in (-1, 1):
                for zc in (zsplit - 0.09, zb1 - 0.09):
                    mb.box((sx * (W / 2 + 0.002), -OV / 2, zc + 0.02), (0.004, 0.1, 0.05), m_iron)
                    n = 4
                    pts = [Vector((sx * (W / 2 + 0.006 + 0.012 * math.sin(math.pi * k / n)), -OV / 2 - 0.04 * math.cos(math.pi * k / n),
                                   zc + 0.01 - 0.03 * math.sin(math.pi * k / n))) for k in range(n + 1)]
                    C.tube(mb, pts, [0.006] * len(pts), m_iron, sides=5, cap0=True, cap1=True)
    if tkind != 'none':
        _topper(mb, tkind, tx, -0.02, H, lod, mats, r_branch)

    C.centre_base(mb)
    o = genlib.finish(mb.to_object(ASSET))
    KG.uv_grain(o, [m_body, m_front])          # grain along each board (drawer fronts horizontal)
    C.set_json_props(o, kz_params=dict(style=style, w=round(W, 3), h=round(H, 3), d=round(D, 3), rows=rows,
                                       pulls=pull_kind, topper=tkind), kz_anim=dict(type='none'))
    return o
