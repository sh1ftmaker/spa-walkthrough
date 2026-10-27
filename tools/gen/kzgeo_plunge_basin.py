"""kzgeo_plunge_basin: polar-grid basin helpers (used by gen_plunge_basin and gen_cascade_pool).

A basin is N angular columns x a list of rows from the outer base, over the rim, down the inner wall to
the bed and a centre pole. Each row point is  outline(theta) * s  - radial_unit(theta) * off(theta),  so
rim widths can be given in metres (off) on any outline; z may be a function of theta (rim dips, lumps).
Open along the outer base (it sits in the ground).
"""
import math

from mathutils import Vector


def _val(v, th):
    return v(th) if callable(v) else v


def polar_basin(mb, outline, N, rows, mi_fn, disp=None, phase=0.0):
    """rows: [(s, off, z, tag)] outer base -> centre; the last row may have s == 0 (pole, single vert).
    off, z may be callables of theta. disp(th, j, tag, p) -> displacement Vector (optional).
    mi_fn(j, tag0, tag1, th) -> slot of the band between row j and j+1. Returns (grid, faces)."""
    bm = mb.bm
    G = []
    ths = [phase + 2 * math.pi * i / N for i in range(N)]
    for j, (s, off, z, tag) in enumerate(rows):
        if s == 0 and j == len(rows) - 1:
            G.append([bm.verts.new((0.0, 0.0, _val(z, 0.0)))])
            continue
        row = []
        for th in ths:
            x, y = outline(th)
            L = math.hypot(x, y) or 1.0
            ux, uy = x / L, y / L
            o = _val(off, th)
            p = Vector((x * s - ux * o, y * s - uy * o, _val(z, th)))
            if disp:
                p += disp(th, j, tag, p)
            row.append(bm.verts.new(p))
        G.append(row)
    faces = []
    for j in range(len(G) - 1):
        A, B = G[j], G[j + 1]
        t0, t1 = rows[j][3], rows[j + 1][3]
        for i in range(N):
            th = ths[i] + math.pi / N
            if len(B) == 1:
                f = bm.faces.new((A[i], A[(i + 1) % N], B[0]))
            else:
                f = bm.faces.new((A[i], A[(i + 1) % N], B[(i + 1) % N], B[i]))
            f.material_index = mi_fn(j, t0, t1, th)
            faces.append(f)
    return G, faces


def sector_slab(mb, outline, th0, th1, off0, off1, z0, z1, n, mi, mi_side=None):
    """closed annular-sector prism following the outline: radial offsets off0 (outer) .. off1 (inner, m),
    angular span th0..th1 with n segments, from z0 to z1. Used for seat steps inside a basin."""
    bm = mb.bm
    mi_side = mi if mi_side is None else mi_side

    def P(th, off, z):
        x, y = outline(th)
        L = math.hypot(x, y) or 1.0
        return Vector((x - x / L * off, y - y / L * off, z))
    ths = [th0 + (th1 - th0) * k / n for k in range(n + 1)]
    ob = [bm.verts.new(P(t, off0, z0)) for t in ths]
    ot = [bm.verts.new(P(t, off0, z1)) for t in ths]
    it = [bm.verts.new(P(t, off1, z1)) for t in ths]
    ib = [bm.verts.new(P(t, off1, z0)) for t in ths]
    faces = []
    for k in range(n):
        for (a, b), m in (((ob, ot), mi_side), ((ot, it), mi), ((it, ib), mi_side), ((ib, ob), mi_side)):
            f = bm.faces.new((a[k], a[k + 1], b[k + 1], b[k])); f.material_index = m; faces.append(f)
    for k, m in ((0, mi_side), (n, mi_side)):
        f = bm.faces.new((ob[k], ot[k], it[k], ib[k])); f.material_index = m; faces.append(f)
    return faces
