"""Geometry for the shoji_panel component (also used by gen_facade_timber for its infill).

`panel_into(mb, M, W, H, style, mats, lod, P)` builds one sliding panel in the local frame M: local x runs along
the panel (centred on 0), local +y is the panel's front, z = 0 is the panel's bottom edge.  Styles:
  shoji   stiles + rails, optional koshi kick board, kumiko grid in front of back-lit washi
  fusuma  solid paper panel in a thin lacquer frame (fuchi) with a recessed round / square hikite pull
  lattice tategoshi: dense vertical bars between the rails with 1-3 horizontal ties, open (no paper)
  glazed  yukimi-shoji: clear glass in the lower part, kumiko + lit washi above a mid rail
LOD0 bevelled frame members, kumiko with front + side faces; LOD1 plain boxes; LOD2 a front + back frame ring and
the same kumiko as front-only strips (grid kept: no pop at the switch); LOD3 a 10-tri slab.
"""
import math

from mathutils import Matrix, Vector

import kzgeo_common as C


def _q(mb, M, pts, mi):
    bm = mb.bm
    f = bm.faces.new([bm.verts.new(M @ Vector(p)) for p in pts])
    f.material_index = mi
    return f


def _box(mb, M, c, s, mi, bevel=0.0):
    """box in frame M (axis aligned in the local frame)"""
    lay = mb._mark_old()
    if bevel > 0:
        C.board(mb, c, s, mi, bevel=bevel, segs=1)
    else:
        mb.box(c, s, mi)
    vs = list({v for f in mb._new_faces(lay) for v in f.verts})
    for v in vs:
        v.co = M @ v.co


def _bar_v(mb, M, x, y0, y1, z0, z1, wd, mi, sides=True, back=False):
    """vertical strip: front face (+ side faces, + back face)"""
    a, b = x - wd / 2, x + wd / 2
    _q(mb, M, [(a, y1, z0), (b, y1, z0), (b, y1, z1), (a, y1, z1)], mi)
    if sides:
        _q(mb, M, [(b, y1, z0), (b, y0, z0), (b, y0, z1), (b, y1, z1)], mi)
        _q(mb, M, [(a, y0, z0), (a, y1, z0), (a, y1, z1), (a, y0, z1)], mi)
    if back:
        _q(mb, M, [(b, y0, z0), (a, y0, z0), (a, y0, z1), (b, y0, z1)], mi)


def _bar_h(mb, M, z, y0, y1, x0, x1, wd, mi, sides=True, back=False):
    a, b = z - wd / 2, z + wd / 2
    _q(mb, M, [(x0, y1, a), (x1, y1, a), (x1, y1, b), (x0, y1, b)], mi)
    if sides:
        _q(mb, M, [(x0, y1, b), (x1, y1, b), (x1, y0, b), (x0, y0, b)], mi)
        _q(mb, M, [(x0, y0, a), (x1, y0, a), (x1, y1, a), (x0, y1, a)], mi)
    if back:
        _q(mb, M, [(x1, y0, a), (x0, y0, a), (x0, y0, b), (x1, y0, b)], mi)


def _ring(mb, M, W, H, T, st, tp, bt, mi):
    """LOD2 frame: front and back picture-frame rings (8 quads), no edge faces (3 cm, invisible at 16 m)"""
    x0, x1 = -W / 2, W / 2
    for y, flip in ((T / 2, False), (-T / 2, True)):
        for pts in (((x0, y, 0), (x1, y, 0), (x1, y, bt), (x0, y, bt)),
                    ((x0, y, H - tp), (x1, y, H - tp), (x1, y, H), (x0, y, H)),
                    ((x0, y, bt), (x0 + st, y, bt), (x0 + st, y, H - tp), (x0, y, H - tp)),
                    ((x1 - st, y, bt), (x1, y, bt), (x1, y, H - tp), (x1 - st, y, H - tp))):
            _q(mb, M, pts[::-1] if flip else pts, mi)


def frame_members(mb, M, W, H, T, st, tp, bt, mi, lod):
    """stiles + top / bottom rails"""
    if lod >= 2:
        _ring(mb, M, W, H, T, st, tp, bt, mi)
        return
    bev = 0.003 if lod == 0 else 0.0
    _box(mb, M, (-W / 2 + st / 2, 0, H / 2), (st, T, H), mi, bev)
    _box(mb, M, (W / 2 - st / 2, 0, H / 2), (st, T, H), mi, bev)
    _box(mb, M, (0, 0, H - tp / 2), (W - 2 * st, T * 0.94, tp), mi, bev)
    _box(mb, M, (0, 0, bt / 2), (W - 2 * st, T * 0.94, bt), mi, bev)


def kumiko(mb, M, x0, x1, z0, z1, cols, rows, yf, yb, wd, mi, lod):
    """kumiko grid over x0..x1, z0..z1: front + sides at LOD0-1, front-only strips at LOD2"""
    sides = lod <= 1
    for k in range(1, cols):
        _bar_v(mb, M, x0 + (x1 - x0) * k / cols, yb, yf, z0, z1, wd, mi, sides)
    for k in range(1, rows):
        _bar_h(mb, M, z0 + (z1 - z0) * k / rows, yb, yf, x0, x1, wd, mi, sides)


def paper(mb, M, x0, x1, z0, z1, y, mi, both=True):
    _q(mb, M, [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], mi)
    if both:
        _q(mb, M, [(x1, y - 0.001, z0), (x0, y - 0.001, z0), (x0, y - 0.001, z1), (x1, y - 0.001, z1)], mi)


def hikite(mb, M, x, z, y, mi, lod, shape='round', r=0.03):
    """recessed pull: a shallow turned cup (LOD0-1) or a flat disc (LOD2), on the face plane y (front)"""
    segs = 12 if lod == 0 else 8
    lay = mb._mark_old()
    if shape == 'round':
        C.lathe(mb, [(r, 0.0), (r, 0.003), (r * 0.72, 0.003), (r * 0.72, -0.002), (0.0, -0.002)], segs, mi)
    else:
        mb.box((0, 0, 0.0005), (2 * r * 0.85, 2 * r * 1.3, 0.004), mi)
    vs = list({v for f in mb._new_faces(lay) for v in f.verts})
    R = M @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    for v in vs:
        v.co = R @ v.co


def panel_into(mb, M, W, H, style, mats, lod, P):
    """One panel. mats: wood, paper (lit washi), washi (fusuma face), lacquer, glass, metal.
    P: style parameters (see gen_shoji_panel.params). Returns list of paper rects (x0, x1, z0, z1) for kz_lights."""
    T = P['T']
    st, tp, bt = P['stile'], P['top'], P['bot']
    wood = mats['wood']
    lit = []
    if lod == 3:
        face = {'shoji': mats['paper'], 'glazed': mats['paper'], 'fusuma': mats['washi'], 'lattice': wood}[style]
        x0, x1 = -W / 2, W / 2
        _q(mb, M, [(x0, T / 2, 0), (x1, T / 2, 0), (x1, T / 2, H), (x0, T / 2, H)], face)
        _q(mb, M, [(x1, -T / 2, 0), (x0, -T / 2, 0), (x0, -T / 2, H), (x1, -T / 2, H)], face)
        _q(mb, M, [(x0, -T / 2, H), (x0, T / 2, H), (x1, T / 2, H), (x1, -T / 2, H)], wood)
        _q(mb, M, [(x1, -T / 2, 0), (x1, T / 2, 0), (x1, T / 2, H), (x1, -T / 2, H)], wood)
        _q(mb, M, [(x0, T / 2, 0), (x0, -T / 2, 0), (x0, -T / 2, H), (x0, T / 2, H)], wood)
        if style in ('shoji', 'glazed'):
            lit.append((x0, x1, 0, H))
        return lit
    fm = mats['lacquer'] if style == 'fusuma' else wood
    frame_members(mb, M, W, H, T, st, tp, bt, fm, lod)
    xa, xb = -W / 2 + st, W / 2 - st
    za, zb = bt, H - tp
    kw, kd = P['kw'], P['kd']
    yf, yb = T * 0.32, T * 0.32 - kd                  # kumiko front / back
    yp = yb - 0.001                                   # paper just behind the kumiko
    if style == 'shoji':
        if P['koshi'] > 0:
            kz = za + P['koshi']
            if lod <= 1:
                _box(mb, M, (0, -T * 0.05, (za + kz) / 2), (xb - xa, T * 0.4, kz - za), wood, 0.002 if lod == 0 else 0)
                _box(mb, M, (0, 0, kz + P['mid'] / 2), (xb - xa, T * 0.9, P['mid']), wood, 0.003 if lod == 0 else 0)
            else:
                _q(mb, M, [(xa, T / 2, za), (xb, T / 2, za), (xb, T / 2, kz + P['mid']), (xa, T / 2, kz + P['mid'])], wood)
                _q(mb, M, [(xb, -T / 2, za), (xa, -T / 2, za), (xa, -T / 2, kz + P['mid']), (xb, -T / 2, kz + P['mid'])], wood)
            za = kz + P['mid']
        paper(mb, M, xa, xb, za, zb, yp, mats['paper'])
        kumiko(mb, M, xa, xb, za, zb, P['cols'], P['rows'], yf, yb, kw, wood, lod)
        lit.append((xa, xb, za, zb))
    elif style == 'glazed':
        zg = za + (zb - za) * P['glass']
        if lod <= 1:
            _box(mb, M, (0, 0, zg + P['mid'] / 2), (xb - xa, T * 0.9, P['mid']), wood, 0.003 if lod == 0 else 0)
        else:
            _q(mb, M, [(xa, T / 2, zg), (xb, T / 2, zg), (xb, T / 2, zg + P['mid']), (xa, T / 2, zg + P['mid'])], wood)
            _q(mb, M, [(xb, -T / 2, zg), (xa, -T / 2, zg), (xa, -T / 2, zg + P['mid']), (xb, -T / 2, zg + P['mid'])], wood)
        paper(mb, M, xa, xb, za, zg, 0.0, mats['glass'])
        if P['muntin'] and lod <= 2:
            _bar_v(mb, M, 0.0, -0.006, 0.006, za, zg, 0.012, wood, lod <= 1, back=True)
        z2 = zg + P['mid']
        paper(mb, M, xa, xb, z2, zb, yp, mats['paper'])
        kumiko(mb, M, xa, xb, z2, zb, P['cols'], P['rows'], yf, yb, kw, wood, lod)
        lit.append((xa, xb, z2, zb))
    elif style == 'fusuma':
        # the face sits 2 mm behind the frame front on both sides; seams of the paper read through the frame
        paper(mb, M, xa, xb, za, zb, T / 2 - 0.002, mats['washi'], both=False)
        _q(mb, M, [(xb, -T / 2 + 0.002, za), (xa, -T / 2 + 0.002, za), (xa, -T / 2 + 0.002, zb), (xb, -T / 2 + 0.002, zb)], mats['washi'])
        if lod <= 2:
            hx = P['pull_side'] * (W / 2 - st - 0.07)
            hikite(mb, M, hx, P['pull_z'], T / 2 - 0.002, mats['metal'], lod, P['pull'])
            if lod <= 1:
                R = M @ Matrix.Rotation(math.pi, 4, 'Z')
                hikite(mb, R, -hx, P["pull_z"], T / 2 - 0.002, mats["metal"], lod, P["pull"])
    elif style == 'lattice':
        if P['kick'] > 0:
            kz = za + P['kick']
            if lod <= 1:
                _box(mb, M, (0, 0, (za + kz) / 2), (xb - xa, T * 0.5, kz - za), wood, 0.002 if lod == 0 else 0)
            else:
                _q(mb, M, [(xa, T / 4, za), (xb, T / 4, za), (xb, T / 4, kz), (xa, T / 4, kz)], wood)
                _q(mb, M, [(xb, -T / 4, za), (xa, -T / 4, za), (xa, -T / 4, kz), (xb, -T / 4, kz)], wood)
            za = kz
        n = P['nbars']
        pitch = (xb - xa) / n
        bw = P['bar_w']
        for k in range(n):
            x = xa + pitch * (k + 0.5)
            if lod <= 1:
                _bar_v(mb, M, x, -T * 0.3, T * 0.3, za, zb, bw, wood, sides=lod == 0, back=True)
            else:
                _bar_v(mb, M, x, -T * 0.3, T * 0.3, za, zb, bw, wood, sides=False)
        for k in range(1, P['ties'] + 1):
            z = za + (zb - za) * k / (P['ties'] + 1)
            if lod <= 1:
                _bar_h(mb, M, z, -T * 0.42, T * 0.42, xa, xb, 0.022, wood, sides=True, back=True)
            else:
                _bar_h(mb, M, z, -T * 0.42, T * 0.42, xa, xb, 0.022, wood, sides=False)
    return lit
