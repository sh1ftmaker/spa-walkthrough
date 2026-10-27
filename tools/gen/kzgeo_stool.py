"""Geometry helpers for gen_stool (copied from kzgeo_oke_bucket): revolve, stick, centring.

All helpers add faces to a genlib.MeshBuilder bmesh and tag them with a material slot index.
"""
import math
import bmesh
from mathutils import Matrix, Vector


def revolve(mb, prof, segs, mi, z0=0.0, phase=0.0, closed=True):
    """Surface of revolution about local Z. prof = [(r, z)] bottom to top; r == 0 is a pole.
    closed=False leaves open bands (hoops) without end caps."""
    bm = mb.bm
    rings, allv = [], []
    for r, z in prof:
        if r <= 1e-6:
            v = bm.verts.new((0.0, 0.0, z + z0)); rings.append([v]); allv.append(v)
        else:
            vs = [bm.verts.new((r * math.cos(phase + 2 * math.pi * k / segs),
                                r * math.sin(phase + 2 * math.pi * k / segs), z + z0)) for k in range(segs)]
            rings.append(vs); allv += vs
    faces = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(segs):
            k2 = (k + 1) % segs
            if len(A) == 1:
                cand = (A[0], B[k], B[k2])
            elif len(B) == 1:
                cand = (A[k], A[k2], B[0])
            else:
                cand = (A[k], A[k2], B[k2], B[k])
            try:
                faces.append(bm.faces.new(cand))
            except ValueError:
                pass
    if closed:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                try:
                    faces.append(bm.faces.new(ring[::-1] if ring is rings[0] else ring))
                except ValueError:
                    pass
    mb._tag(faces, mi)
    return allv, faces


def stick(mb, a, b, r1, r2, mi, segs=8):
    """Tapered cylinder from point a to point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    res = bmesh.ops.create_cone(mb.bm, cap_ends=True, cap_tris=False, segments=segs,
                                radius1=r1, radius2=r2, depth=d.length)
    vs = res['verts']
    q = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    bmesh.ops.transform(mb.bm, matrix=Matrix.Translation((a + b) / 2) @ q, verts=vs)
    faces = list({f for v in vs for f in v.link_faces})
    mb._tag(faces, mi)
    return faces


def centre_xy_base(mb, centre_x=True, centre_y=True):
    """Shift the whole mesh so its bbox sits on z=0 and (optionally) is centred on x/y."""
    vs = mb.bm.verts
    xs = [v.co.x for v in vs]; ys = [v.co.y for v in vs]; zs = [v.co.z for v in vs]
    dx = -(max(xs) + min(xs)) / 2 if centre_x else 0.0
    dy = -(max(ys) + min(ys)) / 2 if centre_y else 0.0
    dz = -min(zs)
    for v in vs:
        v.co.x += dx; v.co.y += dy; v.co.z += dz


def outer_r(z, r0, R, H, bulge):
    """outer wall radius at height z for a tapered bucket with a seeded belly"""
    t = max(0.0, min(1.0, z / H))
    return r0 + (R - r0) * t + bulge * math.sin(math.pi * t)
