"""Geometry helpers for gen_geothermal_gauge: lathes about the +Y axis (dial parts face the viewer), elbow
pipe polylines, annulus bands on the dial face and a hand wheel."""
import math

import bmesh
from mathutils import Matrix, Vector

import kzgeo_common as C

RX = Matrix.Rotation(-math.pi / 2, 4, 'X')        # local +Z (lathe axis) -> world +Y


def lathe_y(mb, prof, segs, mi, centre, closed=True, phase=0.0):
    """C.lathe about +Y through centre (x, y, z): prof [(r, t)], t measured along +Y from centre."""
    vs, fs = C.lathe(mb, prof, segs, mi, base=(0, 0, 0), phase=phase, closed=closed)
    bmesh.ops.transform(mb.bm, matrix=Matrix.Translation(centre) @ RX, verts=vs)
    bmesh.ops.recalc_face_normals(mb.bm, faces=fs)
    return vs, fs


def dial_xz(cx, cz, rad, theta):
    """theta measured clockwise from 12 o'clock as the viewer (on +Y) sees it: screen right = world -X"""
    return cx - rad * math.sin(theta), cz + rad * math.cos(theta)


def annulus_band(mb, cx, cz, y, r0, r1, th0, th1, n, mi, depth=0.002):
    """closed thin band (a ring sector) on the plane y facing +Y"""
    bm = mb.bm
    A, B, Af, Bf = [], [], [], []
    for k in range(n + 1):
        th = th0 + (th1 - th0) * k / n
        for lst, lstf, rr in ((A, Af, r0), (B, Bf, r1)):
            x, z = dial_xz(cx, cz, rr, th)
            lst.append(bm.verts.new((x, y, z)))
            lstf.append(bm.verts.new((x, y + depth, z)))
    fs = []
    for k in range(n):
        fs.append(bm.faces.new((Af[k], Bf[k], Bf[k + 1], Af[k + 1])))
        fs.append(bm.faces.new((A[k + 1], B[k + 1], B[k], A[k])))
        fs.append(bm.faces.new((A[k], Af[k], Af[k + 1], A[k + 1])))
        fs.append(bm.faces.new((B[k + 1], Bf[k + 1], Bf[k], B[k])))
    fs.append(bm.faces.new((A[0], B[0], Bf[0], Af[0])))
    fs.append(bm.faces.new((Af[-1], Bf[-1], B[-1], A[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def elbow_path(pts, radius, n):
    """polyline through corner points with each inner corner rounded by an arc of `radius` (n segments)"""
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d0, d1 = (b - a).normalized(), (c - b).normalized()
        rr = min(radius, (b - a).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b - d0 * rr, b + d1 * rr
        for k in range(n + 1):
            t = k / n
            q = p0.lerp(b, t).lerp(b.lerp(p1, t), t)       # quadratic bezier: close to an arc
            out.append(q)
    out.append(pts[-1])
    return out


def hand_wheel(mb, centre, R, mi, lod, spokes=4):
    """valve hand wheel facing +Y: rim (closed tube loop), spokes, hub"""
    cx, cy, cz = centre
    n = C.lod_pick(lod, 12, 8, 6)
    pts = [Vector((cx + R * math.cos(2 * math.pi * k / n), cy, cz + R * math.sin(2 * math.pi * k / n))) for k in range(n)]
    rings, _ = C.tube(mb, pts + [pts[0]], [0.009] * (n + 1), mi, sides=C.lod_pick(lod, 5, 4, 4))
    if lod <= 1:
        for s in range(spokes):
            a = 2 * math.pi * s / spokes + math.pi / 4
            C.stick(mb, (cx, cy, cz), (cx + R * math.cos(a), cy, cz + R * math.sin(a)), 0.006, 0.006, mi, segs=4)
    lathe_y(mb, [(0.0, -0.02), (0.018, -0.02), (0.018, 0.015), (0.0, 0.02)], C.lod_pick(lod, 8, 6, 4), mi, (cx, cy, cz))
