"""Geometry for gen_facade_timber: a lit multi-bay hinoki frontage (also called by cliff_bracket hosts).

Frame: the front wall (post line) is the plane y = 0, the body runs back to y = -body_d, balconies and eaves
project to +y; x is centred on the frontage; z = 0 is the ground (or the bottom of the cliff brackets).
Everything is added to one genlib.MeshBuilder; `facade_into` returns lights, the lit slots and anchor data.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_roof_tiled as KR
import kzgeo_shoji_panel as KSP


def _new_verts(mb, lay):
    return list({v for f in mb._new_faces(lay) for v in f.verts})


def _q(mb, pts, mi):
    bm = mb.bm
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mi
    return f


def _post(mb, c, s, mi, lod, ch=0.02):
    if lod == 0:
        C.chamfered_bar(mb, c, s, mi, ch=ch, axis='z')
    else:
        mb.box(c, s, mi)


def _beam_x(mb, c, s, mi, lod, ch=0.015):
    if lod == 0:
        C.chamfered_bar(mb, c, s, mi, ch=ch, axis='x')
    else:
        mb.box(c, s, mi)


def _strut(mb, a, b, w, d, mi):
    """square timber from a to b (box oriented along a->b)"""
    a, b = Vector(a), Vector(b)
    M = kg.frame((a + b) / 2, b - a, Vector((1, 0, 0)) if abs((b - a).normalized().x) < 0.9 else Vector((0, 0, 1)))
    kg.cbox(mb, M, (w, (b - a).length, d), mi)


def _chochin(mb, c, mats, lod, rad=0.17, h=0.42):
    """simple hanging chochin: turned paper body + black caps + a short cord"""
    x, y, z = c
    segs = 8 if lod == 0 else 6
    prof = [(rad * 0.66, 0.0), (rad * 0.97, h * 0.25), (rad * 0.97, h * 0.75), (rad * 0.66, h)]
    C.lathe(mb, prof, segs, mats['lantern'], base=(x, y, z - h))
    C.lathe(mb, [(rad * 0.66, 0.0), (rad * 0.66, 0.05), (0.0, 0.05)], segs, mats['cap'], base=(x, y, z))
    C.lathe(mb, [(rad * 0.66, -0.05), (rad * 0.66, 0.0), (0.0, 0.0)], segs, mats['cap'], base=(x, y, z - h - 0.0))
    if lod == 0:
        mb.box((x, y, z + 0.15), (0.012, 0.012, 0.2), mats['cap'])
    return (x, y, z - h / 2)


# ------------------------------------------------------------------ infill
def infill(mb, mats, lod, P, x0, x1, z0, z1, kind, rng_k):
    """one bay opening between posts (x0..x1) from the sill z0 to the kamoi z1. Returns lit rects."""
    lit = []
    W = x1 - x0
    if lod == 3:
        mi = mats['paper'] if kind in ('shoji', 'lattice') else mats['glow']
        _q(mb, [(x0, -0.02, z0), (x1, -0.02, z0), (x1, -0.02, z1), (x0, -0.02, z1)], mi)
        lit.append((x0, x1, z0, z1))
        return lit
    if kind == 'glass':
        # glow plane (the lit room) behind clear glass, mullions + a transom bar
        yi = -0.9
        _q(mb, [(x0, yi, z0), (x1, yi, z0), (x1, yi, z1), (x0, yi, z1)], mats['glow'])
        lit.append((x0, x1, z0, z1))
        _q(mb, [(x0, -0.03, z0), (x1, -0.03, z0), (x1, -0.03, z1), (x0, -0.03, z1)], mats['glass'])   # every LOD: no pop
        n = max(2, round(W / P['glass_pitch']))
        for k in range(1, n):
            x = x0 + W * k / n
            if lod <= 1:
                mb.box((x, -0.03, (z0 + z1) / 2), (0.05, 0.07, z1 - z0), mats['frame'])
            else:
                _q(mb, [(x - 0.03, 0.005, z0), (x + 0.03, 0.005, z0), (x + 0.03, 0.005, z1), (x - 0.03, 0.005, z1)], mats['frame'])
        zt = z0 + (z1 - z0) * 0.78
        if lod <= 1:
            mb.box(((x0 + x1) / 2, -0.03, zt), (W, 0.07, 0.05), mats['frame'])
        if lod <= 1:   # sill and head frames
            mb.box(((x0 + x1) / 2, -0.03, z0 + 0.03), (W, 0.09, 0.06), mats['frame'])
        return lit
    if kind == 'lattice' and lod == 2:
        # LOD2 lattice: the lit paper plane behind front-only bar strips (opaque panel slabs would put the bay out)
        _q(mb, [(x0, -0.06, z0), (x1, -0.06, z0), (x1, -0.06, z1), (x0, -0.06, z1)], mats['paper'])
        nb_ = max(6, int(W / 0.12))
        for k in range(1, nb_):
            x = x0 + W * k / nb_
            _q(mb, [(x - 0.011, -0.02, z0), (x + 0.011, -0.02, z0), (x + 0.011, -0.02, z1), (x - 0.011, -0.02, z1)], mats['frame'])
        lit.append((x0, x1, z0, z1))
        return lit
    # shoji / lattice: n sliding panels on two tracks
    n = max(2, round(W / 0.95))
    pw = W / n + 0.02
    plod = {0: 1, 1: 2, 2: 3}[lod] + (1 if P['n_panels'] > 14 and lod <= 1 else 0)
    PP = dict(rng_k)
    for k in range(n):
        xc = x0 + W * (k + 0.5) / n
        xc = max(x0 + pw / 2, min(x1 - pw / 2, xc))
        y = -0.03 if k % 2 == 0 else -0.068
        M = Matrix.Translation((xc, y, z0))
        style = 'shoji' if kind == 'shoji' else 'lattice'
        KSP.panel_into(mb, M, pw, z1 - z0, style, mats, plod, PP)
    if kind == 'lattice':
        yi = -0.16
        _q(mb, [(x0, yi, z0), (x1, yi, z0), (x1, yi, z1), (x0, yi, z1)], mats['paper'])
    lit.append((x0, x1, z0, z1))
    return lit


def ranma(mb, mats, lod, x0, x1, z0, z1, style):
    """transom over the kamoi: lit paper behind slats (LOD0-1), a lit band (LOD2), nothing at LOD3"""
    if lod >= 3 or z1 - z0 < 0.12:
        return None
    _q(mb, [(x0, -0.05, z0), (x1, -0.05, z0), (x1, -0.05, z1), (x0, -0.05, z1)], mats['paper'])
    if lod <= 1:
        # front-only slat strips (the transom is seen from the front, 2 tris per slat)
        W = x1 - x0
        n = max(4, int(W / (0.15 if style == 'tate' else 0.35)))
        bw = 0.02 if style == 'tate' else 0.03
        for k in range(1, n):
            x = x0 + W * k / n
            _q(mb, [(x - bw / 2, -0.02, z0), (x + bw / 2, -0.02, z0), (x + bw / 2, -0.02, z1), (x - bw / 2, -0.02, z1)], mats['frame'])
        if style != 'tate':
            zm = (z0 + z1) / 2
            _q(mb, [(x0, -0.019, zm - 0.011), (x1, -0.019, zm - 0.011), (x1, -0.019, zm + 0.011), (x0, -0.019, zm + 0.011)], mats['frame'])
    return (x0, x1, z0, z1)


# ------------------------------------------------------------------ balcony / engawa
def railing(mb, mats, lod, xs, y_edge, y_back, z_f, h, pitch, sides=True):
    """koran: rail posts at the bay lines, top / mid / bottom rails, vertical balusters ('lattice rail')"""
    wood = mats['rail']
    x0, x1 = xs[0], xs[-1]
    zt = z_f + h
    yr = y_edge - 0.06
    runs = [((x0, yr), (x1, yr))]
    if sides:
        runs += [((x0, y_back), (x0, yr)), ((x1, y_back), (x1, yr))]
    if lod == 3:
        _q(mb, [(x0, yr, z_f), (x1, yr, z_f), (x1, yr, zt), (x0, yr, zt)], wood)
        return
    pts = set()
    for x in xs:
        pts.add((round(x, 4), round(yr, 4)))
    if sides:
        for x in (x0, x1):
            pts.add((round(x, 4), round(y_back + 0.1, 4)))
    for (x, y) in pts:
        _post(mb, (x, y, z_f + (h + 0.06) / 2), (0.1, 0.1, h + 0.06), wood, 1 if lod > 0 else 0, ch=0.012)
    for (ax, ay), (bx, by) in runs:
        L = math.hypot(bx - ax, by - ay)
        along_x = abs(by - ay) < 1e-6
        c = ((ax + bx) / 2, (ay + by) / 2)
        for zz, sz in ((zt - 0.035, (0.1, 0.07)), (z_f + 0.1, (0.07, 0.06)), (z_f + h * 0.55, (0.05, 0.045))):
            if lod >= 2 and zz != zt - 0.035:
                continue
            size = (L, sz[0], sz[1]) if along_x else (sz[0], L, sz[1])
            if lod == 0 and zz == zt - 0.035:
                C.chamfered_bar(mb, (c[0], c[1], zz), size, wood, ch=0.012, axis='x' if along_x else 'y')
            else:
                mb.box((c[0], c[1], zz), size, wood)
        if lod >= 2:
            # lattice as one slab under the top rail
            if along_x:
                _q(mb, [(ax, ay, z_f + 0.04), (bx, by, z_f + 0.04), (bx, by, zt - 0.07), (ax, ay, zt - 0.07)], wood)
            else:
                _q(mb, [(ax, ay, z_f + 0.04), (ax, ay, zt - 0.07), (bx, by, zt - 0.07), (bx, by, z_f + 0.04)][::(1 if ax > 0 else -1)], wood)
            continue
        n = max(2, int(L / pitch))
        for k in range(1, n):
            t = k / n
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            zb, ztp = z_f + 0.13, zt - 0.07
            s = 0.034
            if along_x:
                _q(mb, [(x - s / 2, y + s / 2, zb), (x + s / 2, y + s / 2, zb), (x + s / 2, y + s / 2, ztp), (x - s / 2, y + s / 2, ztp)], wood)
                _q(mb, [(x + s / 2, y + s / 2, zb), (x + s / 2, y - s / 2, zb), (x + s / 2, y - s / 2, ztp), (x + s / 2, y + s / 2, ztp)], wood)
                _q(mb, [(x - s / 2, y - s / 2, zb), (x - s / 2, y + s / 2, zb), (x - s / 2, y + s / 2, ztp), (x - s / 2, y - s / 2, ztp)], wood)
            else:
                sx = 1 if ax > 0 else -1
                xo = x + sx * s / 2
                q = [(xo, y - s / 2, zb), (xo, y + s / 2, zb), (xo, y + s / 2, ztp), (xo, y - s / 2, ztp)]
                _q(mb, q if sx > 0 else q[::-1], wood)
                yf = y + s / 2
                _q(mb, [(x - s / 2, yf, zb), (x + s / 2, yf, zb), (x + s / 2, yf, ztp), (x - s / 2, yf, ztp)], wood)


def deck(mb, mats, lod, x0, x1, y0, y1, z, t=0.09):
    """deck slab (plank grooves on top at LOD0) with a fascia edge beam"""
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z - t / 2), (x1 - x0, y1 - y0, t), mats['deck'])
    if lod == 0:
        n = max(2, int((x1 - x0) / 0.16))
        for k in range(1, n):
            x = x0 + (x1 - x0) * k / n
            _q(mb, [(x - 0.004, y0, z + 0.0015), (x + 0.004, y0, z + 0.0015), (x + 0.004, y1, z + 0.0015), (x - 0.004, y1, z + 0.0015)], mats['gap'])
    if lod <= 2:
        mb.box(((x0 + x1) / 2, y1 - 0.06, z - t - 0.08), (x1 - x0, 0.12, 0.16), mats['frame_d'])


# ------------------------------------------------------------------ main
def facade_into(mb, mats, lod, P, budget=None):
    nb, ns = P['bays'], P['storeys']
    bw, sh = P['bay_w'], P['storey_h']
    W = nb * bw
    xs = [-W / 2 + k * bw for k in range(nb + 1)]
    bd = P['body_d']
    z0 = P['z0']                                     # ground-storey floor
    pw = P['post_w']
    lights, lit_rects = [], []
    floors = [z0 + k * sh for k in range(ns + 1)]   # floor levels; floors[ns] = top plate
    top = floors[-1]
    bal = P['balcony']                               # per storey: depth (0 = none); storey 0 = engawa / deck
    wood, frame_d = mats['struct'], mats['frame_d']

    # ---- mount
    if P['mount'] == 'cliff_bracket':
        yb = -bd
        yf = max(bal[0], 0.3)
        nbk = list(xs) if lod <= 2 else [xs[0], xs[len(xs) // 2], xs[-1]]
        for x in nbk:
            if lod <= 2:
                _strut(mb, (x, yb + 0.15, 0.25), (x, yf - 0.25, z0 - 0.32), 0.2, 0.22, wood)     # diagonal bracket
                mb.box((x, (yb + yf) / 2, z0 - 0.21), (0.2, yf - yb, 0.24), wood)            # floor beam
                if lod <= 1:
                    _strut(mb, (x, yb + 0.12, z0 * 0.45), (x, yb + 0.12 + (yf - yb) * 0.42, z0 - 0.33), 0.14, 0.14, wood)
                    mb.box((x, yb + 0.1, (z0 - 0.1) / 2), (0.24, 0.2, z0 - 0.1), wood)      # wall ledger post
            else:
                _q(mb, [(x - 0.1, yb, 0.0), (x + 0.1, yb, 0.0), (x + 0.1, yf, z0 - 0.3), (x - 0.1, yf, z0 - 0.3)][::-1], wood)
        if lod <= 2:
            mb.box((0, yb + 0.1, 0.3), (W + 0.3, 0.2, 0.3), wood)                       # cliff ledger
    else:
        # floor platform on short posts and soseki stones
        if lod <= 2:
            for x in xs:
                for y in (-bd + 0.15, -0.0) + ((max(bal[0], 0) - 0.15,) if bal[0] > 0.3 else ()):
                    if lod <= 1:
                        mb.box((x, y, 0.06), (0.36, 0.36, 0.12), mats['stone'])
                    mb.box((x, y, (0.12 + z0) / 2), (0.16, 0.16, z0 - 0.12), wood)
        if lod <= 2:
            mb.box((0, -bd / 2, z0 - 0.1), (W + 0.12, bd, 0.2), frame_d)        # floor edge band (body)
    # ---- body: floors, side and back walls (lacquered boards)
    yb = -bd
    for sx in (-1, 1):
        x = sx * (W / 2 + 0.01)
        q = [(x, yb, z0), (x, 0.0, z0), (x, 0.0, top), (x, yb, top)]
        _q(mb, q if sx > 0 else q[::-1], mats['wall'])
    _q(mb, [(W / 2, yb, z0), (-W / 2, yb, z0), (-W / 2, yb, top), (W / 2, yb, top)], mats['wall'])
    if lod <= 2:
        # interior ceiling plane per storey so glass / open bays never show the sky inside
        for k in range(ns):
            zc = floors[k + 1] - 0.26
            _q(mb, [(-W / 2, 0.0, zc), (W / 2, 0.0, zc), (W / 2, yb, zc), (-W / 2, yb, zc)], mats['wall'])
            _q(mb, [(-W / 2, yb, floors[k] + 0.01), (W / 2, yb, floors[k] + 0.01), (W / 2, 0.0, floors[k] + 0.01), (-W / 2, 0.0, floors[k] + 0.01)], mats['deck'])

    # ---- frame: posts, nuki, keta per storey
    for x in xs:
        if lod <= 2:
            _post(mb, (x, 0.0, (z0 + top) / 2), (pw, pw, top - z0), wood, lod)
            if lod <= 1:
                for xx in (x,):
                    mb.box((xx, yb + pw / 2, (z0 + top) / 2), (pw * 0.8, pw * 0.8, top - z0), wood)
    for k in range(ns):
        zf, zt = floors[k], floors[k + 1]
        if lod <= 2:
            _beam_x(mb, (0, 0.0, zt - 0.13), (W + pw, pw + 0.02, 0.26), wood, lod)          # keta / floor beam
        dh = min(P['door_h'], sh - 0.6)
        zk = zf + dh
        if lod <= 1:
            _beam_x(mb, (0, 0.01, zk + 0.06), (W, pw * 0.7, 0.12), frame_d, lod, ch=0.01)     # kamoi / nuki
            mb.box((0, 0.0, zf + 0.03), (W, pw * 0.8, 0.06), frame_d)                       # shikii (sill)
        kind = P['infill'][k]
        for b in range(nb):
            x0b, x1b = xs[b] + pw / 2, xs[b + 1] - pw / 2
            if kind == 'open':
                continue
            lit_rects += infill(mb, mats, lod, P, x0b, x1b, zf + 0.06, zk, kind, P['panel'])
            if lod <= 2:
                rr = ranma(mb, mats, lod, x0b, x1b, zk + 0.12, zt - 0.27, P['ranma'])
                if rr:
                    lit_rects.append(rr)
        if lod == 3:
            _q(mb, [(-W / 2, 0.0, zk), (W / 2, 0.0, zk), (W / 2, 0.0, zt), (-W / 2, 0.0, zt)], frame_d)
            for x in xs:
                _q(mb, [(x - pw / 2, 0.005, zf), (x + pw / 2, 0.005, zf), (x + pw / 2, 0.005, zk), (x - pw / 2, 0.005, zk)], wood)

    # ---- balconies (storey k > 0) / engawa deck (storey 0)
    for k in range(ns):
        d = bal[k]
        if d <= 0:
            continue
        zf = floors[k]
        x0d, x1d = -W / 2 - (0.0 if k else 0.0), W / 2
        deck(mb, mats, lod, x0d, x1d, 0.0, d, zf, t=0.09 if k == 0 else 0.12)
        if lod == 3:
            continue
        if k > 0 or P['mount'] == 'cliff_bracket' or P['rail0']:
            railing(mb, mats, lod, xs, d, 0.0, zf, P['rail_h'], P['baluster'], sides=True)
        if k > 0 and lod <= 1:
            # projecting joists under the balcony + knee braces back to the posts
            for x in xs:
                mb.box((x, d / 2, zf - 0.2), (0.14, d, 0.16), wood)
                _strut(mb, (x, 0.08, zf - 0.85), (x, d * 0.75, zf - 0.24), 0.12, 0.12, wood)
        if k == 0 and P['mount'] != 'cliff_bracket' and lod <= 2 and P['steps']:
            # two stone steps to the engawa in the centre bay
            xc = (xs[nb // 2] + xs[(nb + 1) // 2]) / 2 if nb % 2 == 0 else (xs[nb // 2] + xs[nb // 2 + 1]) / 2
            for i, f in enumerate((0.66, 0.33)):
                zz = zf * f
                mb.box((xc, d + 0.18 + 0.32 * i, zz / 2), (1.4 - 0.2 * i, 0.34, zz), mats['stone'])

    # ---- pent roofs (machiya style) where the next storey has no balcony
    rmats = dict(tile=mats['tile'], ridge=mats['tile'], wood=wood, wood_d=frame_d, iron=mats['iron'])
    for k in range(ns - 1):
        if bal[k + 1] > 0:
            continue
        zt = floors[k + 1] + 0.35
        dep = P['pent'] + max(0.0, bal[k])
        KR.pent_into(mb, rmats, lod, -W / 2 - 0.3, W / 2 + 0.3, 0.0, dep, zt, pitch=20.0, tp=P['tp'])

    # ---- sign board (Kawagiri)
    if P['sign'] and lod <= 2:
        bwid = min(W * 0.4, 3.6)
        bh = bwid * 0.42
        zc = top - 0.3 - bh / 2 - 0.2
        ys = 0.08
        C.board(mb, (0, ys - 0.04, zc), (bwid + 0.16, 0.08, bh + 0.16), frame_d, bevel=0.01 if lod == 0 else 0.0)
        C.board(mb, (0, ys + 0.01, zc), (bwid, 0.02, bh), mats['sign'], bevel=0.0)
        if lod == 0:
            C.text_solid(mb, P['sign'][0], 0.0, zc + bh * 0.12, ys + 0.02, bh * 0.52, mats['gold'], depth=0.012,
                         res=1)
            C.tracked_text(mb, P['sign'][1], 0.0, zc - bh * 0.33, ys + 0.02, bh * 0.1, mats['gold'], depth=0.008,
                           tracking=0.35, res=1)
        else:
            for i, (dx, w_) in enumerate(((-bwid * 0.2, bwid * 0.26), (bwid * 0.18, bwid * 0.3))):
                mb.box((dx, ys + 0.025, zc + bh * 0.1), (w_, 0.01, bh * 0.5), mats['gold'])
        lights.append(C.light_entry((0, ys + 1.5, zc - 0.4), color_k=2400, watts=30))

    # ---- lanterns
    if P['lanterns'] and lod <= 1:
        for k in range(ns):
            if bal[k] <= 0 and k == 0 and ns > 1:
                continue
            zt = floors[k + 1] - 0.3
            yl = (bal[k] if bal[k] > 0 else P['pent']) * 0.85 if k < ns - 1 or bal[k] > 0 else 0.6
            for x in xs[1:-1]:
                c = _chochin(mb, (x, max(0.35, yl), zt), mats, lod)
                lights.append(C.light_entry(c, color_k=1900 if P['lanterns'] == 'red' else 2200, watts=12))

    # ---- top roof (roof_tiled) over the body + the top balcony
    yfr = max(bal[-1], 0.0)
    hd = (bd + yfr) / 2 + P['eave']
    hw = W / 2 + P['eave_s']
    yc = (yfr - bd) / 2
    lay = mb._mark_old()
    roof_budget = None
    if budget:
        roof_budget = max(int(budget * 0.12), int(budget * 0.97) - C.tri_count(mb.bm))
    tmp = genlib.MeshBuilder()
    info0 = KR._roof(tmp, dict(KR.RES[lod], tp=P['tp']), rmats, lod, P['roof'], hw, hd, 0.0, P['pitch'], P['eave'],
                     P['eave_s'], P['up'], P['tp'], P['p'], None, 1.1, 'irimoya')
    tmp.bm.free()
    z_e = top + 0.04 - info0['wall_top']
    info = KR.roof_into(mb, rmats, lod, P['roof'], hw, hd, z_e=z_e, pitch=P['pitch'], eave=P['eave'], eave_s=P['eave_s'],
                        up=P['up'], tp=P['tp'], p=P['p'], budget=roof_budget, r=None)
    vs = _new_verts(mb, lay)
    bmesh.ops.translate(mb.bm, vec=(0, yc, 0), verts=vs)
    if lod <= 2:
        # wall plate / beam closing the gap between the top keta and the soffit
        mb.box((0, -bd / 2, top + 0.02), (W + 0.1, bd, 0.08), wood)
    for x0, x1, za, zb in lit_rects:
        lights.append(C.light_entry(((x0 + x1) / 2, -0.4, (za + zb) / 2), color_k=2300,
                                    watts=round(14 * (x1 - x0) * (zb - za), 1), kind='area', normal=[0, 1, 0],
                                    size=[round(x1 - x0, 3), round(zb - za, 3)]))
    return dict(lights=lights, roof_notes=info['notes'], top=top, floors=floors, W=W)
