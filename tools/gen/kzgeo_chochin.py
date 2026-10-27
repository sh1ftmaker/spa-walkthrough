"""Robust glyph tessellation for printed / raised lettering (used by gen_chochin and gen_lift_drum).

Blender's font fill uses an even-odd rule, and CJK fonts are drawn with overlapping stroke contours, so a
plain text->mesh conversion punches holes wherever two strokes cross (the 'broken 火' problem). Here every
outer contour is filled separately (with only the holes that lie inside it) and the pieces are unioned, so
overlapping strokes stay solid while real counters (口, 日, A, B ...) stay open.
"""
import math

import bpy
from mathutils import Vector
from mathutils.geometry import interpolate_bezier, tessellate_polygon

_cache = {}


def _area(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def _inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def contours(text, font, res=2):
    """sampled contours (lists of (x, y)) of `text` at font size 1, baseline y = 0"""
    key = (text, font, res)
    if key in _cache:
        return _cache[key]
    f = bpy.data.fonts.load(font, check_existing=True)
    cu = bpy.data.curves.new('kz_txt', 'FONT'); cu.body = text; cu.font = f
    o = bpy.data.objects.new('kz_txt', cu); bpy.context.scene.collection.objects.link(o)
    for ob in list(bpy.context.selected_objects):
        ob.select_set(False)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.convert(target='CURVE')
    polys = []
    for sp in o.data.splines:
        pts = []
        if sp.type == 'BEZIER':
            bp = sp.bezier_points
            n = len(bp)
            for i in range(n):
                a, b = bp[i], bp[(i + 1) % n]
                seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, res + 1)
                pts += [(v.x, v.y) for v in seg[:-1]]
        else:
            pts = [(p.co.x, p.co.y) for p in sp.points]
        # drop duplicate consecutive points
        clean = []
        for p in pts:
            if not clean or (abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1])) > 1e-6:
                clean.append(p)
        if len(clean) >= 3 and abs(_area(clean)) > 1e-7:
            polys.append(clean)
    data = o.data
    bpy.data.objects.remove(o)
    try:
        bpy.data.curves.remove(data)
    except Exception:
        pass
    _cache[key] = polys
    return polys


def glyph_tris_raw(text, font, res=2):
    """triangles (2D, font size 1, baseline 0) with overlapping strokes unioned and counters kept"""
    polys = contours(text, font, res)
    if not polys:
        return [], (0, 0, 0, 0)
    big = max(polys, key=lambda p: abs(_area(p)))
    outer_sign = 1 if _area(big) > 0 else -1
    outers = [p for p in polys if (1 if _area(p) > 0 else -1) == outer_sign]
    holes = [p for p in polys if p not in outers]
    tris = []
    for op in outers:
        hs = [h for h in holes if _inside(h[0], op) and abs(_area(h)) < abs(_area(op))]
        loops = [[Vector((x, y, 0)) for x, y in op]] + [[Vector((x, y, 0)) for x, y in h] for h in hs]
        flat = [v for L in loops for v in L]
        for t in tessellate_polygon(loops):
            tris.append([(flat[i].x, flat[i].y) for i in t])
    xs = [p[0] for p in polys for p in p]
    ys = [q[1] for p in polys for q in p]
    return tris, (min(xs), min(ys), max(xs), max(ys))


def glyph_tris(text, font, res=2):
    """same API as before: triangles normalised to height 1, centred at 0; returns (tris, width)"""
    tris, (x0, y0, x1, y1) = glyph_tris_raw(text, font, res)
    if not tris:
        return [], 0.0
    s = 1.0 / max(1e-6, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [[((x - cx) * s, (y - cy) * s) for x, y in t] for t in tris], (x1 - x0) * s


def tracked_line(text, font, cap_h, tracking=0.35, res=2):
    """a horizontal line of letters laid out one by one with wide tracking (e.g. 'K A Z A N - Y U'), centred at
    x = 0 with the cap height `cap_h` and baseline at y = 0. Returns (tris, total_width)."""
    ref, (rx0, ry0, rx1, ry1) = glyph_tris_raw('H', font, res)
    s = cap_h / max(1e-6, ry1)
    out, x = [], 0.0
    adv = []
    for ch in text:
        tr, (x0, y0, x1, y1) = glyph_tris_raw(ch, font, res)
        w = (x1 - x0) if tr else 0.3
        adv.append((tr, x0, w))
    total = sum(w for _, _, w in adv) * s + tracking * cap_h * (len(adv) - 1)
    x = -total / 2
    for tr, x0, w in adv:
        for t in tr:
            out.append([(x + (px - x0) * s, py * s) for px, py in t])
        x += w * s + tracking * cap_h
    return out, total
