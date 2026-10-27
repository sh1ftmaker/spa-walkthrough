"""kzgeo_aqueduct: parts for gen_aqueduct (run inside Blender).

  arcade(mb, A, B, ...)       one straight run of an arched hinoki arcade (lookbook 08): a single
                              outline (top edge following the fall, piers + semicircular arches cut out
                              of the bottom) extruded across the run
  spout(mb, ...)              bamboo spout out of the trough side wall, with node bands
  gate(mb, ...)               sluice gate: two uprights, crossbar, sliding board with a handle block,
                              a lever on an iron pivot. Board, handle and lever are marked in the int
                              vertex layer '_gate' (1 = lifts, 2 = lever rotates about kz_gate_pivot)
"""
import math

import bmesh
from mathutils import Vector

import kzgeo_common as C
import kzgeo_boardwalk as K

Z = Vector((0, 0, 1))


def arcade(mb, A, t, n, Ls, z_top0, z_top1, piers, spring, mi, depth, segs, soffits=True, base=0.0, bottoms=False):
    """Arched wall from A along plan tangent t for Ls metres. piers = [(x0, x1), ...] pier extents along
    the run (local x); arches span the gaps between consecutive piers and spring at `spring` (local z).
    The top edge runs from z_top0 to z_top1 (the trough fall). Extruded +-depth/2 along n.
    soffits=False leaves out the faces inside the openings (pier sides and arch soffits: LOD2);
    bottoms=False leaves out the pier undersides (they stand on the sill)."""
    bm = mb.bm
    pts, kinds = [], []            # kinds[k]: type of the edge from pts[k] to pts[k + 1]
    for i, (p0, p1) in enumerate(piers):
        if i:
            q0 = piers[i - 1][1]
            r = (p0 - q0) / 2
            cx = (q0 + p0) / 2
            pts.append((q0, spring)); kinds.append('in')
            for k in range(1, segs):
                a = math.pi - math.pi * k / segs
                pts.append((cx + r * math.cos(a), spring + r * math.sin(a))); kinds.append('in')
            pts.append((p0, spring)); kinds.append('in')
        pts.append((p0, base)); kinds.append('bot')
        pts.append((p1, base)); kinds.append('in' if i < len(piers) - 1 else 'end')
    zt = lambda x: z_top0 + (z_top1 - z_top0) * (x / Ls)
    pts.append((piers[-1][1], zt(piers[-1][1]))); kinds.append('top')
    pts.append((piers[0][0], zt(piers[0][0]))); kinds.append('end')
    # the first point of the loop is (p0, base) of pier 0; rotate so it leads
    i0 = pts.index((piers[0][0], base))
    pts = pts[i0:] + pts[:i0]; kinds = kinds[i0:] + kinds[:i0]

    def P(x, z, y):
        return bm.verts.new(A + t * x + n * y + Z * z)
    F = [P(x, z, depth / 2) for x, z in pts]
    B = [P(x, z, -depth / 2) for x, z in pts]
    faces = [bm.faces.new(F), bm.faces.new(B[::-1])]
    m = len(pts)
    for k in range(m):
        if kinds[k] == 'in' and not soffits:
            continue
        if kinds[k] == 'bot' and not bottoms:
            continue
        k2 = (k + 1) % m
        faces.append(bm.faces.new((F[k], B[k], B[k2], F[k2])))
    for f in faces:
        f.normal_update()
    if faces[0].normal.dot(n) < 0:            # the front outline must face +n: flip the whole consistent shell
        for f in faces:
            f.normal_flip()
    mb._tag(faces, mi)
    return faces


def spout(mb, root, out_dir, length, rad, mi, mi_node, lod, drop=0.35, nodes=2):
    """bamboo spout from root (inside the trough wall) outward along out_dir, dipping by `drop` per metre.
    One straight culm (a single segment), node bands at LOD0, a dark open mouth. Returns the mouth."""
    d = Vector((out_dir.x, out_dir.y, -drop)).normalized()
    tip = root + d * length
    if lod >= 3:
        side = Vector((-d.y, d.x, 0)).normalized() * rad
        K.quad(mb, [root - side, tip - side, tip + side, root + side], mi)
        return tip
    sides = C.lod_pick(lod, 8, 5, 3)
    C.tube(mb, [root, tip], [rad, rad], mi, sides=sides, cap0=lod <= 1, cap1=lod <= 1)
    if lod == 0:
        for k in range(nodes):
            c = root + d * (length * (0.38 + 0.36 * k))
            C.tube(mb, [c - d * 0.008, c + d * 0.008], [rad * 1.12] * 2, mi_node, sides=sides)
        C.tube(mb, [tip, tip + d * 0.0015], [rad * 0.72] * 2, mi_node, sides=sides, cap1=True)   # dark open mouth
    return tip


def gate(mb, c, t, n, inner_w, outer_w, z_floor, z_top, mats, lod, lay, post=0.05, lever=True):
    """Sluice gate across the trough at plan point c (trough centreline), tangent t, normal n."""
    wood, board_m, iron = mats
    zup = z_top + 0.24
    bm = mb.bm
    n0 = len(bm.verts)
    marks = []
    # uprights either side of the trough
    for sg in (-1, 1):
        q = c + n * sg * (outer_w / 2 + post / 2 + 0.005)
        if lod <= 1:
            K.beam(mb, Vector((q.x, q.y, z_top - 0.16)), Vector((q.x, q.y, zup)), t, post, post, wood,
                   caps=(lod == 0, True))
    # crossbar (LOD2 keeps only the board: without uprights a crossbar would float)
    if lod <= 1:
        a = c - n * (outer_w / 2 + post + 0.03); b = c + n * (outer_w / 2 + post + 0.03)
        K.beam(mb, Vector((a.x, a.y, zup + 0.03)), Vector((b.x, b.y, zup + 0.03)), t, 0.06, 0.06, wood,
               caps=(True, True) if lod <= 1 else (False, False))
    # sliding gate board (marked 1)
    nb = len(bm.verts)
    a = c - n * (inner_w / 2 - 0.002); b = c + n * (inner_w / 2 - 0.002)
    zb0, zb1 = z_floor + 0.005, z_top + 0.12
    if lod <= 2:
        K.beam(mb, (a + b) / 2 + Z * zb0, (a + b) / 2 + Z * zb1, n, inner_w - 0.004, 0.025, board_m, caps=(lod <= 1, True))
        if lod == 0:      # handle block on top of the board
            K.beam(mb, (a + b) / 2 + Z * zb1, (a + b) / 2 + Z * (zb1 + 0.05), n, 0.08, 0.04, wood)
    else:
        K.quad(mb, [Vector((a.x, a.y, zb0)), Vector((b.x, b.y, zb0)), Vector((b.x, b.y, zup)), Vector((a.x, a.y, zup))], board_m)
    marks.append((nb, len(bm.verts), 1))
    # lever on an iron pivot (marked 2)
    pivot = c + Z * (zup + 0.09)
    if lever and lod <= 1:
        if lod == 0:
            K.beam(mb, pivot - n * 0.05, pivot + n * 0.05, t, 0.02, 0.02, iron)
        nl = len(bm.verts)
        d = (-t * math.cos(math.radians(20)) + Z * math.sin(math.radians(20)))
        K.beam(mb, pivot + t * 0.10, pivot + d * 0.40, n, 0.035, 0.035, wood)
        if lod == 0:      # link from the lever to the handle
            K.beam(mb, pivot + t * 0.02 + Z * 0.0, (a + b) / 2 + Z * (zb1 + 0.05), n, 0.012, 0.012, iron)
        marks.append((nl, len(bm.verts), 2))
    bm.verts.ensure_lookup_table()
    for v0, v1, val in marks:
        for i in range(v0, v1):
            bm.verts[i][lay] = val
    return pivot
