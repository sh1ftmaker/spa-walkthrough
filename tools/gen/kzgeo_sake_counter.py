"""Geometry for gen_sake_counter: front boards with chamfered faces, open-ended boxes, hearth blocks."""
import bmesh

import kzgeo_common as C


def front_board(mb, x0, x1, y_back, y_front, z0, z1, ch, mi):
    """vertical board between x0..x1 whose two front vertical edges are chamfered by `ch` (hexagonal
    section), no end caps (top hides under the slab, bottom on the plinth): 12 tris"""
    bm = mb.bm
    sec = [(x0, y_back), (x1, y_back), (x1, y_front - ch), (x1 - ch, y_front), (x0 + ch, y_front), (x0, y_front - ch)]
    a = [bm.verts.new((x, y, z0)) for x, y in sec]
    b = [bm.verts.new((x, y, z1)) for x, y in sec]
    n = len(sec)
    fs = [bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i])) for i in range(1, n)]   # skip the hidden back face
    mb._tag(fs, mi)
    return fs


def box_faces(mb, x0, x1, y0, y1, z0, z1, mi, skip=()):
    """axis box with chosen faces left out ('bottom', 'top', 'front', 'back', 'left', 'right')"""
    bm = mb.bm
    v = {}
    for i, x in enumerate((x0, x1)):
        for j, y in enumerate((y0, y1)):
            for k, z in enumerate((z0, z1)):
                v[(i, j, k)] = bm.verts.new((x, y, z))
    quads = dict(bottom=((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)), top=((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
                 back=((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)), front=((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
                 right=((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)), left=((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)))
    fs = [bm.faces.new([v[q] for q in quad]) for name, quad in quads.items() if name not in skip]
    mb._tag(fs, mi)
    return fs


def gotoku(mb, cx, cy, z0, z1, r, mi, lod):
    """iron trivet: a ring at z1 on three splayed legs standing on z0"""
    import math
    n = C.lod_pick(lod, 14, 8, 0)
    if n:
        pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z1) for k in range(n)]
        pts.append(pts[0])
        C.tube(mb, pts, [0.007] * len(pts), mi, sides=C.lod_pick(lod, 5, 4))
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            C.stick(mb, (cx + r * 1.15 * math.cos(a), cy + r * 1.15 * math.sin(a), z0),
                    (cx + r * math.cos(a), cy + r * math.sin(a), z1 + 0.004), 0.007, 0.006, mi, segs=C.lod_pick(lod, 5, 4))
