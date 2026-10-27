"""Geometry helpers for gen_wall_trickle (also imported by gen_stream_channel): hull rocks, noise, ribbons, lofts."""
import math
import bmesh
from mathutils import Vector, noise


def n3(p, off):
    return noise.noise(Vector(p) + off)


def hull_rock(mb, c, size, mi, rnd, npts=10, ground=None, rot=0.0, flat_top=None, rmin=0.74):
    """Convex-hull boulder: random points on an ellipsoid shell -> facets. ground = z floor (verts clamped, flat base
    face removed); flat_top = z ceiling (clamped, gives a flat stepping surface)."""
    bm = mb.bm
    pts = []
    for _ in range(npts):
        v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(rmin, 1.0)
        v = Vector((v.x * size[0], v.y * size[1], v.z * size[2]))
        x = v.x * math.cos(rot) - v.y * math.sin(rot)
        y = v.x * math.sin(rot) + v.y * math.cos(rot)
        p = Vector((c[0] + x, c[1] + y, c[2] + v.z))
        if ground is not None:
            p.z = max(p.z, ground)
        if flat_top is not None:
            p.z = min(p.z, flat_top)
        pts.append(bm.verts.new(p))
    res = bmesh.ops.convex_hull(bm, input=pts)
    dead = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid})
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='VERTS')
    faces = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace) and g.is_valid]
    if ground is not None:
        dead = [f for f in faces if f.normal.z < -0.95 and all(v.co.z < ground + 0.002 for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    for f in faces:
        f.material_index = mi
    return faces


def grid(bm, rows, mi_list, flip=False, close_u=False, mb=None):
    """quad grid from a list of rows (each a list of BMVerts of equal length)"""
    fs = []
    for a, b in zip(rows[:-1], rows[1:]):
        n = len(a)
        for k in range(n if close_u else n - 1):
            k2 = (k + 1) % n
            q = (a[k], a[k2], b[k2], b[k])
            fs.append(bm.faces.new(q[::-1] if flip else q))
    return fs


def ribbon(mb, pts, widths, mi, normal=Vector((0, 1, 0))):
    """Flat strip along a polyline pts (Vectors) with per-point width; faces toward `normal`."""
    bm = mb.bm
    rows = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(normal)
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        rows.append([bm.verts.new(p - side * widths[i] / 2), bm.verts.new(p + side * widths[i] / 2)])
    fs = grid(bm, rows, None)
    # orient toward the viewer
    for f in fs:
        if f.normal.dot(normal) < 0:
            f.normal_flip()
    mb._tag(fs, mi)
    return fs
