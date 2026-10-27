"""Geometry helpers for gen_table_low (also used by gen_chair_dining for its LOD3 silhouette).

extrude_profile: a concave 2D outline extruded into a closed prism along one axis. One prism gives a
whole table (top + legs) or a whole chair side silhouette in 20-40 triangles, which is what LOD3 needs.
"""
import bmesh
from mathutils import Vector


def _area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))


def extrude_profile(mb, prof, a0, a1, mi, axis='y', edge_mats=None):
    """prof = [(u, z)] closed outline (any winding), extruded along `axis` ('y': u is x; 'x': u is y)
    from a0 to a1. edge_mats = {edge index i (prof[i] -> prof[i+1]): slot} recolours single side faces
    (the seat top of a chair silhouette, say). Returns the faces (closed solid)."""
    if _area2(prof) < 0:
        prof = prof[::-1]
        if edge_mats:
            n = len(prof)
            edge_mats = {(n - 2 - i) % n: m for i, m in edge_mats.items()}
    bm = mb.bm

    def P(u, z, a):
        return Vector((u, a, z)) if axis == 'y' else Vector((a, u, z))
    A = [bm.verts.new(P(u, z, a0)) for u, z in prof]
    B = [bm.verts.new(P(u, z, a1)) for u, z in prof]
    faces = [bm.faces.new(A), bm.faces.new(B[::-1])]
    side = []
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        side.append(bm.faces.new((A[i], B[i], B[j], A[j])))
    faces += side
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    if edge_mats:
        for i, m in edge_mats.items():
            side[i].material_index = m
    return faces
