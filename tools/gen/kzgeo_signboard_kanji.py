"""Shared sign helpers (signboard_kanji, sign_tower_lit): raised kanji / latin glyph reliefs from the Noto
Serif CJK Black outline font, flat or extruded polygons, chamfered timber members, and a to_object that does
NOT re-orient open glyph sheets.

All sign geometry is authored with the face looking +Y.  Seen from the front (camera on +Y) the viewer's right is
-X, so glyph x runs towards -X.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

import genlib

FONT = '/usr/share/fonts/noto-cjk/NotoSerifCJK-Black.ttc'
U = 0.345                                              # font units per em of a full-width kanji at curve size 1
GOLD = dict(tint=(2.5, 2.1, 0.8), wear=0.05)        # bronze library material pushed to gold leaf
_font = None


def font():
    global _font
    if _font is None:
        for f in bpy.data.fonts:
            if f.filepath == FONT:
                _font = f
        _font = _font or bpy.data.fonts.load(FONT)
    return _font


def _glyph_bm(txt, res, ext):
    cu = bpy.data.curves.new('kz_glyph', 'FONT')
    cu.body = txt; cu.font = font(); cu.resolution_u = res; cu.extrude = ext / 2.0 * 1.0
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.size = 1.0
    ob = bpy.data.objects.new('kz_glyph', cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob); bpy.data.curves.remove(cu)
    bm = bmesh.new(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    if ext > 0:
        zmin = min(v.co.z for v in bm.verts)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.9], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        for v in bm.verts:
            v.co.z -= zmin
    return bm


def sheet_layer(mb):
    return mb.bm.faces.layers.int.get('_keep') or mb.bm.faces.layers.int.new('_keep')


def add_text(mb, txt, cx, cz, y, size, mi, ext=0.0, res=2, vertical=False, gap=1.06, max_w=None, max_h=None,
             dissolve=0.14, x_scale=1.0):
    """Glyph relief on a plane facing +Y at (cx, y, cz); `size` is the em height in metres.
    vertical: one glyph per character stacked top to bottom.  max_w/max_h shrink to fit.  Returns (w, h)."""
    lay = sheet_layer(mb)
    lay_old = mb._mark_old()
    chars = list(txt) if vertical else [txt]
    bms = [_glyph_bm(c, res, ext / (size / U) if ext else 0.0) for c in chars]
    # extents (em units)
    ws, hs = [], []
    for bm in bms:
        xs = [v.co.x for v in bm.verts] or [0]; ys = [v.co.y for v in bm.verts] or [0]
        ws.append(max(xs) - min(xs)); hs.append(max(ys) - min(ys))
    tw = (max(ws) if vertical else ws[0]) / U
    th = (len(chars) * gap) if vertical else max(hs[0] / U, 0.8)
    s = size
    if max_w and tw * s * x_scale > max_w:
        s = max_w / (tw * x_scale)
    if max_h and th * s > max_h:
        s = max_h / th
    R = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))        # glyph (x, y, z) -> (-x, z, y)
    n = len(chars)
    for i, bm in enumerate(bms):
        zz = cz + ((n - 1) / 2.0 - i) * gap * s if vertical else cz
        # glyph centre in its own plane
        xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
        gx = (max(xs) + min(xs)) / 2 if xs else 0; gy = (max(ys) + min(ys)) / 2 if (xs and vertical) else 0
        M = Matrix.Translation((cx, y, zz)) @ R @ Matrix.Scale(s / U, 4) @ Matrix.Diagonal((x_scale, 1, 1, 1)) @ Matrix.Translation((-gx, -gy, 0))
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        if ext:
            # extruded glyph: only merge coplanar front-face edges; never touch the side walls (that shears the outline)
            bm.normal_update()
            ed = [e for e in bm.edges if len(e.link_faces) == 2 and all(abs(f.normal.y) > 0.99 for f in e.link_faces)]
            bmesh.ops.dissolve_limit(bm, angle_limit=0.05, verts=[], edges=ed)
        else:
            bmesh.ops.dissolve_limit(bm, angle_limit=dissolve, verts=bm.verts, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        mesh = bpy.data.meshes.new('t'); bm.to_mesh(mesh); bm.free()
        mb.bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    for f in mb._new_faces(lay_old):
        f.material_index = mi
        f[lay] = 1
    return tw * s * x_scale, th * s


def flat_poly(mb, pts, y, mi, ext=0.0):
    """polygon in (x, z) on the plane y facing +Y (viewer coordinates are x -> -x handled by caller); optional
    raised thickness `ext` towards +Y (closed, back omitted).  pts are given counter-clockwise as seen from the front."""
    bm = mb.bm
    lay = sheet_layer(mb)
    vs = [bm.verts.new((x, y, z)) for x, z in pts]
    f = bm.faces.new(vs[::-1] if _area(pts) > 0 else vs)           # seen from +Y, +X is to the left
    f.normal_update()
    if f.normal.y < 0:
        f.normal_flip()
    faces = [f]
    if ext > 0:
        top = [bm.verts.new((v.co.x, y + ext, v.co.z)) for v in vs]
        bm.faces.ensure_lookup_table()
        # move the original face to the top and add skirt quads
        bm.faces.remove(f)
        ft = bm.faces.new(top[::-1] if _area(pts) > 0 else top); ft.normal_update()
        if ft.normal.y < 0:
            ft.normal_flip()
        faces = [ft]
        n = len(vs)
        for i in range(n):
            j = (i + 1) % n
            q = bm.faces.new((vs[i], vs[j], top[j], top[i]))
            q.normal_update()
            faces.append(q)
        # make skirts point outward
        cx = sum(p[0] for p in pts) / n; cz = sum(p[1] for p in pts) / n
        for q in faces[1:]:
            c = q.calc_center_median()
            out = Vector((c.x - cx, 0, c.z - cz))
            if q.normal.dot(out) < 0:
                q.normal_flip()
        bmesh.ops.triangulate(bm, faces=[x for x in faces if len(x.verts) > 4 or x is ft], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    else:
        bmesh.ops.triangulate(bm, faces=[f], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    for g in {fc for v in vs for fc in v.link_faces} | ({fc for v in top for fc in v.link_faces} if ext > 0 else set()):
        g.material_index = mi
        g[lay] = 1
    return faces


def _area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2


def to_object(mb, name):
    """like MeshBuilder.to_object, but glyph / sheet faces keep their authored winding"""
    lay = sheet_layer(mb)
    solid = [f for f in mb.bm.faces if f[lay] == 0]
    bmesh.ops.recalc_face_normals(mb.bm, faces=solid)
    me = bpy.data.meshes.new(name); mb.bm.to_mesh(me); mb.bm.free()
    if '_keep' in me.attributes:
        me.attributes.remove(me.attributes['_keep'])
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for i, (mid, params) in enumerate(mb.slots):
        genlib.matlib.assign(o, mid, slot=i, **params)
    return o


# ------------------------------------------------------------------ timber profile members
def prism_xz(mb, poly, y0, y1, mi):
    """Extrude a polygon given in (x, z) front-view coordinates along Y from y0 to y1 (closed solid)."""
    bm = mb.bm
    a = [bm.verts.new((x, y0, z)) for x, z in poly]
    b = [bm.verts.new((x, y1, z)) for x, z in poly]
    n = len(poly)
    ccw = _area(poly) > 0
    faces = [bm.faces.new(a if ccw else a[::-1]), bm.faces.new(b[::-1] if ccw else b)]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    mb._tag(faces, mi)
    return faces


def chamfered_bar(mb, c, size, mi, ch=0.01, axis='z'):
    """beam of size (sx, sy, sz) with chamfered long edges (octagonal section) along `axis`"""
    sx, sy, sz = size
    cx, cy, cz = c
    pts = lambda a, b: [(-a / 2 + ch, -b / 2), (a / 2 - ch, -b / 2), (a / 2, -b / 2 + ch), (a / 2, b / 2 - ch),
                        (a / 2 - ch, b / 2), (-a / 2 + ch, b / 2), (-a / 2, b / 2 - ch), (-a / 2, -b / 2 + ch)]
    bm = mb.bm
    if axis == 'z':
        ring = lambda z: [bm.verts.new((cx + px, cy + py, z)) for px, py in pts(sx, sy)]
        A, B = ring(cz - sz / 2), ring(cz + sz / 2)
    elif axis == 'x':
        ring = lambda x: [bm.verts.new((x, cy + px, cz + py)) for px, py in pts(sy, sz)]
        A, B = ring(cx - sx / 2), ring(cx + sx / 2)
    else:
        ring = lambda y: [bm.verts.new((cx + px, y, cz + py)) for px, py in pts(sx, sz)]
        A, B = ring(cy - sy / 2), ring(cy + sy / 2)
    faces = [bm.faces.new(A[::-1]), bm.faces.new(B)]
    n = 8
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    mb._tag(faces, mi)
    return faces


# ------------------------------------------------------------------ tiny stroke font for small latin lines
_STROKES = {
    'A': [((0, 0), (.5, 1)), ((.5, 1), (1, 0)), ((.2, .35), (.8, .35))],
    'B': [((0, 0), (0, 1)), ((0, 1), (.85, 1)), ((.85, 1), (.85, .5)), ((.85, .5), (0, .5)), ((.9, .5), (.9, 0)), ((.9, 0), (0, 0))],
    'F': [((0, 0), (0, 1)), ((0, 1), (1, 1)), ((0, .5), (.8, .5))],
    'G': [((1, 1), (0, 1)), ((0, 1), (0, 0)), ((0, 0), (1, 0)), ((1, 0), (1, .5)), ((1, .5), (.5, .5))],
    'H': [((0, 0), (0, 1)), ((1, 0), (1, 1)), ((0, .5), (1, .5))],
    'I': [((.5, 0), (.5, 1))],
    'K': [((0, 0), (0, 1)), ((0, .45), (1, 1)), ((.25, .62), (1, 0))],
    'L': [((0, 1), (0, 0)), ((0, 0), (1, 0))],
    'N': [((0, 0), (0, 1)), ((0, 1), (1, 0)), ((1, 0), (1, 1))],
    'O': [((0, 0), (0, 1)), ((0, 1), (1, 1)), ((1, 1), (1, 0)), ((1, 0), (0, 0))],
    'R': [((0, 0), (0, 1)), ((0, 1), (1, 1)), ((1, 1), (1, .5)), ((1, .5), (0, .5)), ((.3, .5), (1, 0))],
    'S': [((1, 1), (0, 1)), ((0, 1), (0, .5)), ((0, .5), (1, .5)), ((1, .5), (1, 0)), ((1, 0), (0, 0))],
    'T': [((0, 1), (1, 1)), ((.5, 1), (.5, 0))],
    'U': [((0, 1), (0, 0)), ((0, 0), (1, 0)), ((1, 0), (1, 1))],
    'W': [((0, 1), (.25, 0)), ((.25, 0), (.5, .6)), ((.5, .6), (.75, 0)), ((.75, 0), (1, 1))],
    'Y': [((0, 1), (.5, .5)), ((1, 1), (.5, .5)), ((.5, .5), (.5, 0))],
    'Z': [((0, 1), (1, 1)), ((1, 1), (0, 0)), ((0, 0), (1, 0))],
    '-': [((.1, .5), (.9, .5))],
    '1': [((.5, 0), (.5, 1)), ((.5, 1), (.15, .75))],
    '2': [((0, 1), (1, 1)), ((1, 1), (1, .5)), ((1, .5), (0, .5)), ((0, .5), (0, 0)), ((0, 0), (1, 0))],
    '3': [((0, 1), (1, 1)), ((1, 1), (1, 0)), ((1, 0), (0, 0)), ((.2, .5), (1, .5))],
    '4': [((0, 1), (0, .45)), ((0, .45), (1, .45)), ((.8, 1), (.8, 0))],
}


def add_latin(mb, txt, cx, cz, y, height, mi, max_w=None, weight=0.17, spacing=0.34):
    """stroke-built capital letters (2 triangles per stroke) on a plane facing +Y, centred on (cx, cz).
    Reads left to right for a viewer on +Y (so glyph x runs towards -X). Returns the width used."""
    lw = 0.62
    n = len(txt)
    adv = (lw + spacing)
    total = n * adv - spacing
    s = height
    if max_w and total * s > max_w:
        s = max_w / total
    x0 = cx + total * s / 2                                  # the viewer's left edge is +X
    t = weight * s
    lay = sheet_layer(mb)
    for ch in txt:
        for (a, b) in _STROKES.get(ch.upper(), []):
            p0 = Vector((x0 - a[0] * lw * s, cz - s / 2 + a[1] * s)); p1 = Vector((x0 - b[0] * lw * s, cz - s / 2 + b[1] * s))
            d = p1 - p0
            ln = d.length
            if ln < 1e-6:
                continue
            nrm = Vector((-d.y, d.x)) / ln * t / 2
            e = d / ln * t / 2                                 # extend the stroke so joints close
            q = [p0 - e + nrm, p1 + e + nrm, p1 + e - nrm, p0 - e - nrm]
            flat_poly(mb, [(v.x, v.y) for v in q], y, mi)
        x0 -= adv * s
    return total * s


# ------------------------------------------------------------------ mountain crest (vendored from the earlier gen_noren)
_MOUNT_HALF = [(0.0, 0.38), (0.035, 0.405), (0.075, 0.415), (0.095, 0.395), (0.13, 0.345), (0.19, 0.27),
               (0.27, 0.18), (0.37, 0.095), (0.5, 0.0), (0.33, 0.045), (0.22, 0.0), (0.12, 0.07), (0.0, 0.05)]
_MOUNT_HALF_LO = [(0.0, 0.40), (0.09, 0.40), (0.5, 0.0), (0.24, 0.06), (0.0, 0.04)]


def _mountain(lo=False):
    half = _MOUNT_HALF_LO if lo else _MOUNT_HALF
    top = half[:half.index((0.5, 0.0)) + 1] if not lo else half[:3]
    right = top + half[len(top):]
    left = [(-x, y) for x, y in reversed(right) if x > 1e-6]
    out = []
    for p in right + left:
        if not out or abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6:
            out.append(p)
    if abs(out[0][0] - out[-1][0]) < 1e-6 and abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def _wisp(x0, y0, height, amp, width, segs, phase):
    left, right = [], []
    for i in range(segs + 1):
        t = i / segs
        f = lambda tt: math.sin(phase + tt * 2.2 * math.pi) * (0.6 + 0.4 * tt)
        cx = x0 + amp * f(t); cy = y0 + t * height
        wv = width * math.sin(math.pi * min(1.0, t * 1.15)) ** 0.8 if 0 < t < 1 else 0.0
        dx = amp * (f(t + 1e-3) - f(t)); dy = 1e-3 * height
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        left.append((cx + nx * wv / 2, cy + ny * wv / 2)); right.append((cx - nx * wv / 2, cy - ny * wv / 2))
    return left[:1] + left[1:-1] + [left[-1]] + list(reversed(right[1:-1]))


def crest_polys(kind, lod, r):
    """Kazan-yu mountain + three steam wisps as closed polygons (unit width, base y = 0)"""
    polys = [_mountain(lo=lod >= 1)]
    segs = {0: 4, 1: 3}.get(lod, 0)
    if segs:
        for i, x in enumerate((-0.11, 0.0, 0.11)):
            polys.append(_wisp(x, 0.47 + (0.03 if i == 1 else 0.0), 0.42 * (1.08 if i == 1 else 0.92),
                               0.028 + r.uniform(-0.004, 0.004), 0.05, segs, 0.4 + i * 0.3 + r.uniform(-0.2, 0.2)))
    return polys
