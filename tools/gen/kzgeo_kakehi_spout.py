"""Geometry helpers for gen_kakehi_spout: bamboo tubes with nodes, a cut half-pipe scoop, rope bands.

All helpers write into a genlib.MeshBuilder bmesh and tag faces with a material slot index.
"""
import math
import bmesh
from mathutils import Vector

from kzgeo_bridge_arched import frame


def ring(bm, M, radius, N, rot=0.0, ell=1.0):
    """N verts on a circle (local x, z plane of frame M), angle 0 = +x, counter-clockwise seen from +fwd."""
    out = []
    for k in range(N):
        a = rot + 2 * math.pi * k / N
        out.append(bm.verts.new(M @ Vector((radius * math.cos(a) * ell, 0, radius * math.sin(a)))))
    return out


def bridge_rings(bm, A, B, skip=None):
    """quad strip between two rings of equal length; skip = set of k whose quad is omitted"""
    fs = []
    n = len(A)
    for k in range(n):
        if skip and k in skip:
            continue
        k2 = (k + 1) % n
        fs.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    return fs


def bamboo_tube(mb, stations, mi, N=8, cap0=True, cap1=True, tag_extra=None):
    """Closed bamboo tube. stations = list of (centre Vector, forward Vector, up Vector, radius).
    Returns (faces, rings)."""
    bm = mb.bm
    rings = []
    for c, f, u, r in stations:
        M = frame(c, f, u)
        rings.append(ring(bm, M, r, N))
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        faces += bridge_rings(bm, a, b)
    if cap0:
        faces.append(bm.faces.new(rings[0][::-1]))
    if cap1:
        faces.append(bm.faces.new(rings[-1]))
    mb._tag(faces, mi)
    return faces, rings


def band(mb, c, axis, radius, width, mi, N=7, bulge=0.006, up=None):
    """Rope lashing band around a tube: 3 rings, middle one proud (a wrapped, knotted look)."""
    bm = mb.bm
    axis = Vector(axis).normalized()
    up = Vector(up) if up is not None else Vector((0, 0, 1))
    rs = [(-width / 2, radius + 0.0015), (0, radius + bulge), (width / 2, radius + 0.0015)]
    rr = []
    for off, r in rs:
        M = frame(Vector(c) + axis * off, axis, up)
        rr.append(ring(bm, M, r, N, rot=off * 40))        # twist between rings reads as a spiral wrap
    faces = []
    for a, b in zip(rr[:-1], rr[1:]):
        faces += bridge_rings(bm, a, b)
    mb._tag(faces, mi)
    return faces


def knot(mb, c, size, mi, up=None):
    """little rope knot: a squashed tetra-ish blob (6 tris)"""
    bm = mb.bm
    c = Vector(c)
    pts = [c + Vector(v) * size for v in ((0, 0, 1), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0), (0, 0, -1))]
    vs = [bm.verts.new(p) for p in pts]
    fs = []
    for a, b in ((1, 2), (2, 3), (3, 4), (4, 1)):
        fs.append(bm.faces.new((vs[0], vs[a], vs[b])))
        fs.append(bm.faces.new((vs[5], vs[b], vs[a])))
    mb._tag(fs, mi)
    return fs


def turns(mb, c, axis, radius, n, mi, cord=0.006, pitch=0.011, N=5, up=None):
    """n tight rope turns round a tube (6 mm cord): crest rings at radius+cord with a slight twist per ring, thin end rings."""
    bm = mb.bm
    axis = Vector(axis).normalized()
    up = Vector(up) if up is not None else Vector((0, 0, 1))
    half = (n - 1) * pitch / 2
    offs = [-half - pitch * 0.7] + [-half + i * pitch for i in range(n)] + [half + pitch * 0.7]
    rr = []
    for i, off in enumerate(offs):
        rad = radius + (0.002 if i in (0, len(offs) - 1) else cord)
        rr.append(ring(bm, frame(Vector(c) + axis * off, axis, up), rad, N, rot=i * 0.9))
    faces = []
    for a, b in zip(rr[:-1], rr[1:]):
        faces += bridge_rings(bm, a, b)
    mb._tag(faces, mi)
    return faces
