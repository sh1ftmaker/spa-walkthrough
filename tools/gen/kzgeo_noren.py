"""2D crest + lettering shapes for gen_noren (Kazan-yu mark: mountain + three steam wisps, KAZAN-YU, 火山湯).

All shapes are lists of 2D triangles or closed polygons in 'crest units' (crest width = 1, base of the
mountain at y = 0, y up). The glyph outlines come from Blender's font curves (same approach as
gen_chochin.glyph_polys, copied here so the two generators don't depend on each other).
"""
import math

import bpy

FONT_CAPS = '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc'
FONT_JP = '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc'

_MOUNT_HALF = [(0.0, 0.38), (0.035, 0.405), (0.075, 0.415), (0.095, 0.395), (0.13, 0.345), (0.19, 0.27),
               (0.27, 0.18), (0.37, 0.095), (0.5, 0.0), (0.33, 0.045), (0.22, 0.0), (0.12, 0.07), (0.0, 0.05)]
_MOUNT_HALF_LO = [(0.0, 0.385), (0.06, 0.41), (0.5, 0.0), (0.24, 0.06), (0.0, 0.02)]   # peak, crater rim, notched snow line


def mountain(lo=False):
    half = _MOUNT_HALF_LO if lo else _MOUNT_HALF
    left = [(-x, y) for x, y in reversed(half) if x > 1e-6]
    poly = half + left
    out = []
    for p in poly:
        if not out or abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6:
            out.append(p)
    return out


def wisp(x0, y0, height, amp, width, segs, phase):
    """tapered S-curve stroke as a closed outline (pointed both ends)"""
    left, right = [], []
    f = lambda t: x0 + amp * math.sin(phase + t * 2.2 * math.pi) * (0.6 + 0.4 * t)
    for i in range(segs + 1):
        t = i / segs
        cx, cy = f(t), y0 + t * height
        wv = width * math.sin(math.pi * min(1.0, t * 1.15)) ** 0.8 if 0 < t < 1 else 0.0
        dx, dy = f(min(1, t + 1e-3)) - f(max(0, t - 1e-3)), 2e-3 * height
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        left.append((cx + nx * wv / 2, cy + ny * wv / 2))
        right.append((cx - nx * wv / 2, cy - ny * wv / 2))
    return left + list(reversed(right[1:-1]))


def mark_polys(kind, lod, r):
    """closed polygons of the mark (mountain + wisps, or onsen bowl + wisps)"""
    polys = []
    segs = {0: 4, 1: 2}.get(lod, 0)           # LOD1: thin 4-vertex wisps
    if kind in ('kazan', 'kazan_full'):
        polys.append(mountain(lo=lod >= 1) if lod <= 1 else [(-0.5, 0.0), (0.5, 0.0), (0.05, 0.4), (-0.05, 0.4)])   # LOD2: 4-vertex peak
        base_y, wh, xs = 0.47, 0.42, (-0.11, 0.0, 0.11)
    else:
        n = {0: 10, 1: 6}.get(lod, 4)
        outer, inner = [], []
        for i in range(n + 1):
            a = math.pi - 0.3 + (math.pi + 0.6) * i / n
            outer.append((0.34 * math.cos(a), 0.22 + 0.21 * math.sin(a)))
            inner.append((0.265 * math.cos(a), 0.235 + 0.145 * math.sin(a)))
        polys.append(outer + list(reversed(inner)))
        base_y, wh, xs = 0.32, 0.5, (-0.13, 0.0, 0.13)
    if segs:
        for i, x in enumerate(xs):
            polys.append(wisp(x, base_y + (0.03 if i == 1 else 0.0), wh * (1.08 if i == 1 else 0.92),
                              0.028 + r.uniform(-0.004, 0.004), 0.05, segs, 0.4 + i * 0.3 + r.uniform(-0.2, 0.2)))
    return polys


_glyph_cache = {}


def glyph_tris(text, font, res=0):
    """triangles (2D) of a glyph string; glyph box height 1, centred at 0. Returns (tris, width, height)."""
    key = (text, font, res)
    if key in _glyph_cache:
        return _glyph_cache[key]
    f = bpy.data.fonts.load(font, check_existing=True)
    cu = bpy.data.curves.new('kz_glyph', 'FONT'); cu.body = text; cu.font = f
    cu.resolution_u = max(1, res); cu.fill_mode = 'BOTH'
    o = bpy.data.objects.new('kz_glyph', cu); bpy.context.scene.collection.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get(); me = o.evaluated_get(dg).to_mesh()
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    # flat glyph: drop near-collinear outline points, then re-triangulate (halves the triangle count)
    bmesh.ops.dissolve_limit(bm, angle_limit=0.35, verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    tris = [[(v.co.x, v.co.y) for v in f.verts] for f in bm.faces]
    bm.free()
    o.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(o); bpy.data.curves.remove(cu)
    xs = [p[0] for t in tris for p in t]; ys = [p[1] for t in tris for p in t]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    s = 1.0 / max(1e-6, max(ys) - min(ys))
    out = [[((x - cx) * s, (y - cy) * s) for x, y in t] for t in tris]
    res_ = (out, (max(xs) - min(xs)) * s, 1.0)
    _glyph_cache[key] = res_
    return res_


def lettering_tris(lod):
    """KAZAN-YU (spaced caps) over 火山湯, in crest units below the mountain (y < 0).
    LOD0: real glyphs. LOD1+: two cream bars standing in for the two lines."""
    out = []
    caps_h, caps_y = 0.085, -0.12         # spaced caps line
    jp_h, jp_y = 0.19, -0.33              # 火山湯 line
    if lod == 0:
        text = 'KAZAN-YU'
        pitch = 0.115
        x0 = -pitch * (len(text) - 1) / 2
        for i, ch in enumerate(text):
            if ch == '-':                 # glyphs are normalised to unit height: draw the dash as a short bar
                xc, bw, bh = x0 + i * pitch, 0.03, 0.012
                out.append([(xc - bw, caps_y - bh), (xc + bw, caps_y - bh), (xc + bw, caps_y + bh)])
                out.append([(xc - bw, caps_y - bh), (xc + bw, caps_y + bh), (xc - bw, caps_y + bh)])
                continue
            tris, gw, _ = glyph_tris(ch, FONT_CAPS)
            sc = caps_h
            for t in tris:
                out.append([(x0 + i * pitch + x * sc, caps_y + y * sc) for x, y in t])
        jpitch = 0.24
        for i, ch in enumerate('火山湯'):
            tris, gw, _ = glyph_tris(ch, FONT_JP)
            for t in tris:
                out.append([((i - 1) * jpitch + x * jp_h, jp_y + y * jp_h) for x, y in t])
    else:
        for (w, y, hh) in ((0.78, caps_y, caps_h * 0.7), (0.56, jp_y, jp_h * 0.75)):
            a, b = (-w / 2, y - hh / 2), (w / 2, y + hh / 2)
            out.append([(a[0], a[1]), (b[0], a[1]), (b[0], b[1])])
            out.append([(a[0], a[1]), (b[0], b[1]), (a[0], b[1])])
    return out
