"""Kanji signboard and wayfinding board (also the gold-leaf lintel board).

Identifying features kept at every LOD: vertical dark lacquer board, gilt raised kanji, timber frame with a gilt
inner border line, and the mount (wall brackets / standing posts with a kasagi cap / lintel hangers).
Proxy (3d/assets.json): 0.6 x 0.2 x 2.4 m, the vertical wall board.  Front faces +Y.

Variants (`variant`, default picked from the seed: 1 wall, 2 standing, 3 level):
  wall      0.6 x 0.2 x 2.4  hinoki frame, lacquer panel, gilt 火山湯 + KAZAN-YU + mountain crest, two iron wall arms
  standing  wayfinding board between two posts on foot sills, kasagi cap, gilt 大浴場 and an arrow (arrow = +/-1)
  level     level board: B1..B4 (or GF / 地上) in gilt latin over the kanji 地下 / 地上, gilt rules
  lintel    horizontal gold-leaf 川霧 KAWAGIRI board (w 1.2-5 m, h 0.5-1.0) with cap board, end kanagu and hangers
            (mount='lintel'; it is wider than the 0.6 m proxy, see the report: proposed proxy 2.4 x 0.2 x 0.7)

Parameters: w (0.4-5 m), h (0.6-2.4 m), text (override the main glyph string), orientation ('vertical' |
'horizontal'), mount ('wall' | 'standing' | 'lintel'), gilt (bool; off = carved, un-gilded dark glyphs),
variant, level ('B1'..'B4' | 'GF'), arrow (-1/1/0).
Text is real raised-glyph geometry here (Noto Serif CJK Black outlines, flat or 4 mm extruded, dissolved); the
asset list note asks for a baked decal per variant, so the glyph layer is the first thing a web build can swap
for a normal/albedo decal: it is every face with the 'gilt' material slot.

No moving parts.
"""
import json
import math

import bpy
from mathutils import Vector

import genlib
import kzgeo_signboard_kanji as K

ASSET = 'signboard_kanji'
FEATURES = ['dark lacquer board', 'gilt raised kanji', 'timber frame with gilt border', 'wall arms / standing posts / lintel hangers']
PARAMS = dict(w=(0.4, 5.0), h=(0.6, 2.4), text='str', orientation=('vertical', 'horizontal'), mount=('wall', 'standing', 'lintel'),
              gilt=(True, False), variant=('wall', 'standing', 'level', 'lintel'), level=('B1', 'B2', 'B3', 'B4', 'GF'))
KINDS = ['wall', 'standing', 'level']


def build(lod, seed, w=None, h=None, text=None, orientation=None, mount=None, gilt=True, variant=None, level=None, arrow=None):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    kind = variant or {'standing': 'standing', 'lintel': 'lintel'}.get(mount) or KINDS[(seed - 1) % 3]
    if orientation == 'horizontal' and kind in ('wall', 'level'):
        kind = 'lintel'
    budget = genlib.budget_of(ASSET) or [400, 160, 50, 12]
    lim = budget[lod]
    for attempt in range(6):
        o = _build_once(lod, seed, kind, w, h, text, gilt, level, arrow, attempt, p)
        if genlib.tris(o) <= lim * 1.05 or attempt == 5:
            break
        bpy.data.meshes.remove(o.data)
    return genlib.finish(o, smooth_angle=50)


# ------------------------------------------------------------------ board assembly
def _frame(mb, lod, cx, zc, bw, bh, yf, depth, fw, S, bevel_ch):
    """hinoki frame (4 members), recessed lacquer panel, gilt inner border line. Returns (inner_w, inner_h, y_face)."""
    wood, lac, gold, iron = S['wood'], S['lac'], S['gold'], S['iron']
    pd = depth - 0.02                                       # panel sits 2 cm behind the frame front
    y_face = yf - 0.018
    iw, ih = bw - 2 * fw, bh - 2 * fw
    if lod >= 3:
        return iw, ih, y_face
    if lod == 2:
        mb.box((cx, yf - depth / 2, zc), (bw, depth, bh), lac)
        return iw, ih, yf
    ch = bevel_ch
    if lod == 0:
        K.chamfered_bar(mb, (cx - (bw / 2 - fw / 2), yf - depth / 2, zc), (fw, depth, bh), wood, ch=ch, axis="z")
        K.chamfered_bar(mb, (cx + (bw / 2 - fw / 2), yf - depth / 2, zc), (fw, depth, bh), wood, ch=ch, axis="z")
        mb.box((cx, yf - depth / 2, zc + (bh / 2 - fw / 2)), (iw, depth, fw), wood, bevel=0.0)
        mb.box((cx, yf - depth / 2, zc - (bh / 2 - fw / 2)), (iw, depth, fw), wood, bevel=0.0)
    else:
        _open_box(mb, (cx, yf - depth / 2, zc), (bw, depth, bh), wood)
        y_face = yf + 0.001
        K.flat_poly(mb, [(cx + iw / 2, zc + ih / 2), (cx - iw / 2, zc + ih / 2), (cx - iw / 2, zc - ih / 2), (cx + iw / 2, zc - ih / 2)], y_face, lac)
    if lod == 0:
        mb.box((cx, yf - depth + pd / 2 - 0.0, zc), (iw + 0.004, pd, ih + 0.004), lac)
    if lod <= 1:
        # gilt inner border line (flat strips on the panel face)
        m, t = 0.02, 0.006
        x0, x1 = cx - iw / 2 + m, cx + iw / 2 - m
        z0, z1 = zc - ih / 2 + m, zc + ih / 2 - m
        y = y_face + 0.0015
        for (ax, az, bx, bz) in ((x0, z1, x1, z1 - t), (x0, z0 + t, x1, z0), (x0, z1, x0 + t, z0), (x1 - t, z1, x1, z0)):
            K.flat_poly(mb, [(ax, az), (bx, az), (bx, bz), (ax, bz)], y, gold)
    return iw, ih, y_face


def _crest(mb, cx, cz, size, y, mi, lod, r):
    polys = K.crest_polys('kazan', 0 if lod == 0 else 1, r)
    for poly in polys:
        K.flat_poly(mb, [(cx - px * size, cz + py * size) for px, py in poly], y, mi)


def _arm(mb, x, z, y0, y1, S, lod):
    """iron wall arm with a wall plate"""
    iron = S['iron']
    mb.box((x, (y0 + y1) / 2, z), (0.05, y1 - y0, 0.05), iron)
    if lod == 0:
        mb.box((x, y0 + 0.006, z), (0.09, 0.012, 0.14), iron)


def _build_once(lod, seed, kind, w, h, text, gilt, level, arrow, attempt, p):
    r = genlib.rng(seed, ASSET + kind)
    lod3 = lod == 3
    lod = min(lod, 2)
    mb = genlib.MeshBuilder()
    S = dict(
        wood=mb.slot('hinoki', variant='stained', wear=0.1),
        lac=mb.slot('lacquer_black'),
        gold=mb.slot('gold_leaf') if gilt else mb.slot('lacquer_dark', wear=0.5, tint=(0.8, 0.8, 0.8)),
        iron=mb.slot('bronze', wear=0.35))
    gold, lac, wood, iron = S['gold'], S['lac'], S['wood'], S['iron']
    ext = 0.007 if (lod == 0 and attempt == 0) else 0.0      # 7 mm relief on the wall and level boards (extruded sides cost 2.5x; standing and lintel stay flat)
    gres = 2 if lod == 0 else 1
    dis = 0.12 if lod == 0 else 0.35
    D = 0.2
    y_front = D / 2
    info = {}

    if kind in ('wall', 'level'):
        bw = (w or p['w']) * (r.uniform(0.84, 1.0) if kind == 'wall' else r.uniform(0.74, 0.86))
        bh = (h or p['h']) * (r.uniform(0.9, 1.0) if kind == 'wall' else r.uniform(0.64, 0.74))
        fw = 0.065
        depth = 0.1
        zc = bh / 2
        iw, ih, yf = _frame(mb, lod, 0.0, zc, bw, bh, y_front, depth, fw, S, 0.011)
        # wall arms
        if lod <= 2:
            for zz in (zc + bh * 0.4, zc - bh * 0.4):
                _arm(mb, 0, zz, -y_front, y_front - depth, S, lod if lod < 2 else 2)
        if kind == 'wall':
            txt = text or '火山湯'
            n = len(txt)
            top = zc + ih / 2 - 0.1
            gp = 1.2
            s = min(iw * 0.80, (ih * 0.66) / (n * gp))
            zk = top - n * gp * s / 2
            if lod <= 2:
                if lod == 2:
                    for i in range(n):                      # three separate glyph blocks with dark gaps
                        zz = zk + ((n - 1) / 2 - i) * gp * s
                        ww_ = s * (0.42, 0.34, 0.46)[i % 3]
                        K.flat_poly(mb, [(ww_, zz + s * 0.4), (-ww_, zz + s * 0.4), (-ww_, zz - s * 0.4), (ww_, zz - s * 0.4)], yf + 0.002, gold)
                else:
                    K.add_text(mb, txt, 0, zk, yf, s, gold, ext=ext, res=1 if ext else gres, vertical=True, dissolve=1.2 if ext else dis, max_w=iw * 0.82, gap=gp)
            zl = zk - n * gp * s / 2 - 0.1 * iw
            if lod <= 1:
                (K.add_latin(mb, 'KAZAN-YU', 0, zl, yf + 0.0015, iw * 0.085, gold, max_w=iw * 0.72) if not ext else _blocks(mb, 0, zl, yf + 0.0015, iw * 0.6, iw * 0.06, 1, gold, r)) if lod == 0 else _blocks(mb, 0, zl, yf + 0.0015, iw * 0.7, iw * 0.07, 1, gold, r)
                _crest(mb, 0, zl - iw * 0.10 - 0.42 * iw, iw * 0.46, yf + 0.0015, gold, 1, r)
            elif lod == 2:
                K.flat_poly(mb, [(-iw * 0.34, zl + 0.02), (iw * 0.34, zl + 0.02), (iw * 0.34, zl - 0.02), (-iw * 0.34, zl - 0.02)], yf + 0.002, gold)
        else:                                                    # level board
            lv = level or 'B1'
            if lv == 'GF':
                big, kan = 'GF', '地上'
            else:
                big, kan = lv, '地下'
            s1 = min(iw * 0.74, ih * 0.2)
            z1 = zc + ih / 2 - iw * 0.45
            if lod <= 1:
                K.add_text(mb, big, 0, z1, yf, s1, gold, ext=ext, res=1 if ext else gres, dissolve=1.2 if ext else dis, max_w=iw * 0.74)
                for dz in (-s1 * 0.78, -s1 * 0.78 - 0.03):
                    zz = z1 + dz
                    K.flat_poly(mb, [(-iw * 0.38, zz + 0.006), (iw * 0.38, zz + 0.006), (iw * 0.38, zz - 0.006), (-iw * 0.38, zz - 0.006)], yf + 0.0015, gold)
                zk = z1 - s1 * 0.78 - 0.1 - len(kan) * 1.06 * min(iw * 0.62, 0.3) / 2
                K.add_text(mb, kan, 0, zk, yf, min(iw * 0.62, 0.3), gold, ext=ext, res=1 if ext else gres, vertical=True, dissolve=1.2 if ext else dis, max_w=iw * 0.7)
            elif lod == 2:
                K.flat_poly(mb, [(-iw * 0.34, z1 + s1 * 0.4), (iw * 0.34, z1 + s1 * 0.4), (iw * 0.34, z1 - s1 * 0.4), (-iw * 0.34, z1 - s1 * 0.4)], yf + 0.002, gold)
                K.flat_poly(mb, [(-iw * 0.2, zc - ih * 0.05), (iw * 0.2, zc - ih * 0.05), (iw * 0.2, zc - ih * 0.3), (-iw * 0.2, zc - ih * 0.3)], yf + 0.002, gold)
        info = dict(kind=kind, w=bw, h=bh)

    elif kind == 'standing':
        bw = (w or p['w']) * r.uniform(0.62, 0.68)
        H = (h or p['h']) * r.uniform(0.9, 1.0)
        fw = 0.036
        post = 0.062
        px = bw / 2 + post * 0.1
        cap_h = 0.05
        bh = H * r.uniform(0.66, 0.74)
        zb = H - cap_h - 0.12 - bh / 2                 # board centre
        depth = 0.07
        yf_b = 0.02 + depth                            # board front sits 2 cm ahead of the posts' centre line
        # posts (hinoki) and foot sills
        for sx in (-1, 1):
            if lod == 0:
                mb.box((sx * px, -0.01, (H - cap_h) / 2), (post, post, H - cap_h), wood, bevel=0.0)
                mb.box((sx * px, 0.0, 0.045), (post * 1.55, D * 0.98, 0.09), wood)
            elif lod == 1:
                mb.box((sx * px, -0.01, (H - cap_h) / 2), (post, post, H - cap_h), wood)
                mb.box((sx * px, 0.0, 0.045), (post * 1.55, D * 0.98, 0.09), wood)
            else:
                mb.box((sx * px, 0.0, (H - cap_h) / 2), (post * 1.3, D * 0.9, H - cap_h), wood)
        if lod == 0:
            mb.box((0, -0.01, zb - bh / 2 - 0.06), (bw - post, 0.035, 0.05), wood)
            mb.box((0, -0.01, H * 0.3), (2 * px - post, 0.035, 0.045), wood)                 # second crossbar low on the posts
        # board
        iw, ih, yf = _frame(mb, lod, 0.0, zb, bw, bh, yf_b, depth, fw, S, 0.011)
        # cap (kasagi): flat board with a sloped top
        ov = 0.035
        cw = 2 * px + post + 2 * ov
        cz0 = H - cap_h
        pts = [(-cw / 2, cz0), (cw / 2, cz0), (cw / 2 - 0.01, cz0 + cap_h * 0.55), (cw / 2 - 0.04, H), (-cw / 2 + 0.04, H), (-cw / 2 + 0.01, cz0 + cap_h * 0.55)]
        # section across Y: slope front-to-back; build as a prism along X for the cap
        sec = [(D * 0.5, cz0), (-D * 0.5, cz0), (-D * 0.5 + 0.005, cz0 + cap_h * 0.5), (-D * 0.15, H), (D * 0.15, H), (D * 0.5 - 0.005, cz0 + cap_h * 0.5)]
        if lod <= 1:
            _prism_x(mb, sec, -cw / 2, cw / 2, wood)
        else:
            mb.box((0, 0, H - cap_h / 2), (cw, D * 0.8, cap_h), wood)
        txt = text or '大浴場'
        n = len(txt)
        s = min(iw * 0.82, (ih * 0.62) / (n * 1.06))
        zk = zb + ih / 2 - 0.08 - n * 1.06 * s / 2
        if lod <= 1:
            if lod == 0:
                K.add_text(mb, txt, 0, zk, yf, s, gold, ext=ext, res=2 if attempt == 0 else 1, vertical=True, dissolve=0.3, max_w=iw * 0.84)
            else:
                for i in range(n):
                    zz = zk + ((n - 1) / 2 - i) * 1.06 * s
                    K.flat_poly(mb, [(iw * 0.3, zz + s * 0.42), (-iw * 0.3, zz + s * 0.42), (-iw * 0.3, zz - s * 0.42), (iw * 0.3, zz - s * 0.42)], yf + 0.002, gold)
            a = arrow if arrow is not None else r.choice((-1, 1))
            za = zb - ih / 2 + 0.17
            aw = iw * 0.62
            pts = [(-a * aw / 2, za + 0.012), (a * aw * 0.12, za + 0.012), (a * aw * 0.12, za + 0.05), (a * aw / 2, za),
                   (a * aw * 0.12, za - 0.05), (a * aw * 0.12, za - 0.012), (-a * aw / 2, za - 0.012)]
            K.flat_poly(mb, pts, yf + 0.002, gold, ext=0.0)
            K.add_latin(mb, 'BATH', 0, zk - n * 1.06 * s / 2 - 0.07, yf + 0.0015, iw * 0.09, gold, max_w=iw * 0.5) if lod == 0 else _blocks(mb, 0, zk - n * 1.06 * s / 2 - 0.07, yf + 0.0015, iw * 0.5, iw * 0.07, 1, gold, r)
        elif lod == 2:
            K.flat_poly(mb, [(-iw * 0.3, zk + n * s / 2), (iw * 0.3, zk + n * s / 2), (iw * 0.3, zk - n * s / 2), (-iw * 0.3, zk - n * s / 2)], yf + 0.002, gold)
        info = dict(kind=kind, w=2 * px + post * 1.55, h=H)

    else:                                                       # lintel board
        bw = min(5.0, max(0.4, w or 2.4))
        bh = min(1.2, max(0.4, h or 0.62))
        depth = 0.09
        fw = 0.05
        # board centre at half height (lowest edge on z=0)
        capH = 0.06
        zc = bh / 2
        iw, ih, yf = _frame(mb, lod, 0.0, zc, bw, bh, y_front, depth, fw, S, 0.012)
        txt = text or '川霧'
        n = len(txt)
        if lod <= 1:
            s = min(ih * 0.68, iw / (n * 1.5))
            for i, ch in enumerate(txt):
                K.add_text(mb, ch, ((n - 1) / 2 - i) * -1.18 * s * -1.0, zc + ih * 0.1, yf, s, gold, res=gres, dissolve=dis)
            # spaced latin line, gilt rule on each side
            K.add_latin(mb, 'KAWAGIRI', 0, zc - ih * 0.36, yf + 0.0015, ih * 0.13, gold, max_w=min(iw * 0.34, 1.2)) if lod == 0 else _blocks(mb, 0, zc - ih * 0.36, yf + 0.0015, min(iw * 0.34, 1.2), ih * 0.1, 1, gold, r)
            for sx in (-1, 1):
                zz = zc - ih * 0.36
                x0, x1 = sx * iw * 0.20, sx * iw * 0.40
                K.flat_poly(mb, [(x0, zz + 0.006), (x1, zz + 0.006), (x1, zz - 0.006), (x0, zz - 0.006)], yf + 0.0015, gold)
        elif lod == 2:
            for sx in (-1, 1):
                K.flat_poly(mb, [(sx * iw * 0.04 + iw * 0.2, zc + ih * 0.3), (sx * iw * 0.04 - iw * 0.0, zc + ih * 0.3), (sx * iw * 0.04 - iw * 0.0, zc - ih * 0.1), (sx * iw * 0.04 + iw * 0.2, zc - ih * 0.1)], yf + 0.002, gold) if sx > 0 else \
                    K.flat_poly(mb, [(-iw * 0.04 - iw * 0.2, zc + ih * 0.3), (-iw * 0.04, zc + ih * 0.3), (-iw * 0.04, zc - ih * 0.1), (-iw * 0.04 - iw * 0.2, zc - ih * 0.1)], yf + 0.002, gold)
        # cap board and end kanagu
        capw = bw + 0.1
        if lod == 0:
            sec = [(y_front + 0.04, bh), (-y_front * 0.4, bh), (-y_front * 0.4, bh + capH * 1.2), (y_front * 0.2, bh + capH * 1.2)] if lod == 2 else \
                  [(y_front + 0.05, bh + 0.012), (y_front + 0.04, bh), (-y_front * 0.5, bh), (-y_front * 0.5, bh + capH * 0.8), (0.0, bh + capH), (y_front + 0.03, bh + capH * 1.5)]
            _prism_x(mb, sec, -capw / 2, capw / 2, wood)
        if lod == 0:
            for sx in (-1, 1):
                for zz in (fw * 0.5, bh - fw * 0.5):
                    if lod == 0 and zz < bh / 2:
                        continue
                    mb.box((sx * (bw / 2 - fw * 0.5), yf + 0.004, zz), (fw * 0.85, 0.012, fw * 0.85), gold)
        info = dict(kind=kind, w=bw, h=bh + capH * 1.5)

    if lod3:
        mb.bm.clear()
        _lod3(mb, kind, info, S)
    o = K.to_object(mb, ASSET)
    o['kz_params'] = json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items()})
    o['kz_text_slot'] = gold
    return o


def _blocks(mb, cx, cz, y, width, height, n, mi, r):
    """stand-in for a small latin text line: n raised letter blocks of seeded widths (a baked decal replaces it)"""
    if n <= 1:
        K.flat_poly(mb, [(cx - width / 2, cz + height / 2), (cx + width / 2, cz + height / 2), (cx + width / 2, cz - height / 2), (cx - width / 2, cz - height / 2)], y, mi)
        return
    ws = [r.uniform(0.7, 1.1) for _ in range(n)]
    gap = 0.35
    tot = sum(ws) + gap * (n - 1)
    x = cx + width / 2
    for wv in ws:
        ww = wv / tot * width
        K.flat_poly(mb, [(x, cz + height / 2), (x - ww, cz + height / 2), (x - ww, cz - height / 2), (x, cz - height / 2)], y, mi)
        x -= ww + gap / tot * width


def _open_box(mb, c, size, mi):
    """closed box minus its bottom face"""
    f = mb.box(c, size, mi)
    bot = [q for q in f if q.is_valid and q.normal.z < -0.9]
    import bmesh
    bmesh.ops.delete(mb.bm, geom=bot, context='FACES_ONLY')


def _bars(mb, xc, zc, wid, hgt, n, y, mi):
    """n separate gilt bars stacked in a column (the three glyphs at distance), dark gaps between"""
    for i in range(n):
        z = zc + ((n - 1) / 2 - i) * hgt * 1.1
        K.flat_poly(mb, [(xc + wid / 2, z + hgt / 2), (xc - wid / 2, z + hgt / 2), (xc - wid / 2, z - hgt / 2), (xc + wid / 2, z - hgt / 2)], y, mi)


def _lod3(mb, kind, info, S):
    """12-triangle silhouette: dark board front + 3 separate gilt bars (standing: posts as quads, lintel: 2 wide blocks)"""
    w, h = info['w'], info['h']
    if kind == 'standing':
        bh = h * 0.62
        zb0, zb1 = h * 0.95 - bh - 0.08, h * 0.95 - 0.08
        bw3 = w * 0.7
        for sx in (-1, 1):
            K.flat_poly(mb, [(sx * w * 0.42 + 0.03, 0), (sx * w * 0.42 - 0.03, 0), (sx * w * 0.42 - 0.03, h), (sx * w * 0.42 + 0.03, h)], 0.0, S['wood'])
        K.flat_poly(mb, [(bw3 / 2, zb1), (-bw3 / 2, zb1), (-bw3 / 2, zb0), (bw3 / 2, zb0)], 0.0, S['lac'])
        _bars(mb, 0, (zb0 + zb1) / 2 + bh * 0.1, bw3 * 0.55, bh * 0.2, 3, 0.002, S['gold'])
        return
    if kind == 'lintel':
        K.flat_poly(mb, [(w / 2, 0), (-w / 2, 0), (-w / 2, h), (w / 2, h)], 0.0, S['lac'])
        for sx in (-1, 1):
            K.flat_poly(mb, [(sx * w * 0.2 + w * 0.12, h * 0.25), (sx * w * 0.2 - w * 0.12, h * 0.25), (sx * w * 0.2 - w * 0.12, h * 0.75), (sx * w * 0.2 + w * 0.12, h * 0.75)], 0.002, S['gold'])
        K.flat_poly(mb, [(w / 2, h), (-w / 2, h), (-w / 2, h * 0.9), (w / 2, h * 0.9)], 0.004, S['wood'])
        return
    K.flat_poly(mb, [(w / 2, 0), (-w / 2, 0), (-w / 2, h), (w / 2, h)], 0.0, S['lac'])
    _bars(mb, 0, h * 0.62, w * 0.6, h * 0.17, 3, 0.002, S['gold'])
    # left side wall and top so the board reads as a slab from an angle
    for sx in (1,):
        v = [mb.bm.verts.new((sx * w / 2, -0.1, 0)), mb.bm.verts.new((sx * w / 2, 0.1, 0)), mb.bm.verts.new((sx * w / 2, 0.1, h)), mb.bm.verts.new((sx * w / 2, -0.1, h))]
        f = mb.bm.faces.new(v); f.material_index = S['wood']; f[K.sheet_layer(mb)] = 1


def _prism_x(mb, sec_yz, x0, x1, mi):
    """extrude a polygon given in (y, z) between x0 and x1"""
    bm = mb.bm
    a = [bm.verts.new((x0, y, z)) for y, z in sec_yz]
    b = [bm.verts.new((x1, y, z)) for y, z in sec_yz]
    n = len(sec_yz)
    faces = [bm.faces.new(a), bm.faces.new(b[::-1])]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], b[i], b[j], a[j])))
    mb._tag(faces, mi)
