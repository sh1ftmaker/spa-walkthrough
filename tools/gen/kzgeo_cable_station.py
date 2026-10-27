"""Geometry helpers shared by the cable-lift family (gen_cable_station, gen_cable_cabin, gen_cable_line) and
gen_header_tank: oriented beams, closed torus rings (wheels, hoops), spoked sheaves, lattice faces, bronze
railings with fret infill, hanging lanterns, extruded XZ profiles, glass panes.

Every helper adds faces to a genlib.MeshBuilder (`mb`) and tags them with a material slot index.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import kzgeo_common as C
import kzgeo_lift_drum as G


# ------------------------------------------------------------------------------------------- frames
def axis_frame(origin, axis):
    """4x4 matrix with local +Z = axis (normalised), +X perpendicular (prefers world +Z or +X)."""
    z = Vector(axis).normalized()
    ref = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((1, 0, 0))
    x = ref.cross(z).normalized()
    y = z.cross(x)
    M = Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
    M.translation = Vector(origin)
    return M


def rot_verts_z(verts, ang, about=(0, 0, 0)):
    c = Vector(about)
    R = Matrix.Rotation(ang, 3, 'Z')
    for v in verts:
        v.co = R @ (v.co - c) + c


def new_verts_since(mb, lay):
    """verts of faces created after mb._mark_old() returned `lay`"""
    return list({v for f in mb._new_faces(lay) for v in f.verts})


# ------------------------------------------------------------------------------------------- bars and boxes
def beam(mb, a, b, w, d, mi, up=(0, 0, 1), caps=True):
    """box from a to b (world), cross-section w (sideways) x d (up); caps=False drops the two end faces
    (lattice members whose ends are buried in a leg: 8 tris instead of 12)"""
    fs = G.strut(mb.bm, a, b, w, d, mi, up)
    if not caps and fs:
        t = (Vector(b) - Vector(a)).normalized()
        for f in fs:
            f.normal_update()
        ends = [f for f in fs if abs(f.normal.dot(t)) > 0.9]
        bmesh.ops.delete(mb.bm, geom=ends, context='FACES_ONLY')
        fs = [f for f in fs if f.is_valid]
    return fs


def box(mb, c, size, mi, bevel=0.0, segs=1):
    if bevel > 0:
        return C.board(mb, c, size, mi, bevel=bevel, segs=segs)
    return mb.box(c, size, mi)


def prism_xz(mb, pts_xz, y0, y1, mi):
    """closed prism: polygon in the XZ plane (convex or simple), extruded from y0 to y1"""
    bm = mb.bm
    a = sum(pts_xz[i][0] * pts_xz[(i + 1) % len(pts_xz)][1] - pts_xz[(i + 1) % len(pts_xz)][0] * pts_xz[i][1]
            for i in range(len(pts_xz)))
    if a < 0:
        pts_xz = pts_xz[::-1]
    A = [bm.verts.new((x, y0, z)) for x, z in pts_xz]
    B = [bm.verts.new((x, y1, z)) for x, z in pts_xz]
    fs = [bm.faces.new(A), bm.faces.new(B[::-1])]
    n = len(pts_xz)
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((A[i], B[i], B[j], A[j])))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def pane(mb, c, size, mi):
    """closed thin glass slab (library glass absorbs by volume, so panes are solids)"""
    return mb.box(c, size, mi)


# ------------------------------------------------------------------------------------------- rings and wheels
def torus(mb, M, R, sec, segs, mi, a0=0.0, a1=None):
    """closed ring: section `sec` = [(dr, dz)] (closed loop, counter-clockwise) swept round local Z of frame M
    at radius R. Full ring when a1 is None, else an arc a0..a1 with end caps."""
    bm = mb.bm
    full = a1 is None
    n = segs if full else segs + 1
    rings = []
    for k in range(n):
        a = a0 + (2 * math.pi if full else (a1 - a0)) * k / segs
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new(M @ Vector(((R + dr) * ca, (R + dr) * sa, dz))) for dr, dz in sec])
    fs = []
    m = len(sec)
    for k in range(segs if full else segs):
        A, B = rings[k], rings[(k + 1) % n]
        for j in range(m):
            j2 = (j + 1) % m
            fs.append(bm.faces.new((A[j], B[j], B[j2], A[j2])))
    if not full:
        fs.append(bm.faces.new(rings[0][::-1]))
        fs.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def rect_sec(w, h, groove=0.0):
    """ring section, radial width w (inwards from R), axial height h; optional V groove on the outside"""
    if groove > 0:
        return [(-w, -h / 2), (0, -h / 2), (-groove, 0), (0, h / 2), (-w, h / 2)]
    return [(-w, -h / 2), (0, -h / 2), (0, h / 2), (-w, h / 2)]


def wheel(mb, centre, axis, R, mats, lod, spokes=6, rim_w=0.08, rim_t=0.10, hub_r=None, groove=True,
          segs=None, hub_segs=None):
    """spoked sheave / bull wheel: grooved rim ring, hub cylinder along the axis, flat spokes.
    mats = dict(rim, spoke, hub). Returns the frame."""
    M = axis_frame(centre, axis)
    segs = segs or C.lod_pick(lod, 32, 16, 10, 6)
    g = rim_w * 0.35 if (groove and lod <= 1) else 0.0
    torus(mb, M, R, rect_sec(rim_w, rim_t, g), segs, mats['rim'])
    hub_r = hub_r or max(0.04, R * 0.14)
    ax = Vector(axis).normalized()
    c = Vector(centre)
    C.stick(mb, c - ax * rim_t * 0.9, c + ax * rim_t * 0.9, hub_r, hub_r, mats['hub'], segs=hub_segs or C.lod_pick(lod, 8, 6, 6, 4))
    if lod <= 2 and spokes:
        for k in range(spokes):
            a = 2 * math.pi * k / spokes + 0.3
            p0 = M @ Vector((hub_r * 0.8 * math.cos(a), hub_r * 0.8 * math.sin(a), 0))
            p1 = M @ Vector(((R - rim_w * 0.9) * math.cos(a), (R - rim_w * 0.9) * math.sin(a), 0))
            beam(mb, p0, p1, rim_t * 0.45, max(0.02, R * 0.07), mats['spoke'], up=tuple(ax))
    return M


# ------------------------------------------------------------------------------------------- lattice
def lattice_face(mb, a0, a1, b0, b1, w, d, mi, panels, style='x'):
    """braced lattice between two legs: a0 -> a1 (leg A bottom -> top), b0 -> b1 (leg B). `panels` storeys.
    style 'x': X bracing per panel plus a horizontal girt; 'k': K / chevron; 'n': single diagonals zig-zag."""
    a0, a1, b0, b1 = map(Vector, (a0, a1, b0, b1))
    t = [i / panels for i in range(panels + 1)]
    A = [a0.lerp(a1, s) for s in t]
    B = [b0.lerp(b1, s) for s in t]
    for i in range(1, panels + 1):
        beam(mb, A[i], B[i], w, d, mi, caps=False)          # girt
    for i in range(panels):
        if style == 'x':
            beam(mb, A[i], B[i + 1], w * 0.8, d * 0.8, mi, caps=False)
            beam(mb, B[i], A[i + 1], w * 0.8, d * 0.8, mi, caps=False)
        elif style == 'k':
            m = (A[i + 1] + B[i + 1]) / 2
            beam(mb, A[i], m, w * 0.8, d * 0.8, mi, caps=False)
            beam(mb, B[i], m, w * 0.8, d * 0.8, mi, caps=False)
        else:
            if i % 2:
                beam(mb, A[i], B[i + 1], w * 0.8, d * 0.8, mi, caps=False)
            else:
                beam(mb, B[i], A[i + 1], w * 0.8, d * 0.8, mi, caps=False)


# ------------------------------------------------------------------------------------------- railing
def railing(mb, p0, p1, z0, h, mats, lod, post_sp=0.9, fret=True):
    """bronze railing on the line p0 -> p1 (xy) standing on z0: posts with ball caps, top + mid + bottom rails,
    a fret infill (vertical + horizontal bars, a key motif per bay at LOD0). mats = dict(frame, polish)."""
    p0 = Vector((p0[0], p0[1], z0)); p1 = Vector((p1[0], p1[1], z0))
    L = (p1 - p0).length
    n = max(1, round(L / post_sp))
    up = Vector((0, 0, 1))
    pw = 0.05
    for k in range(n + 1):
        q = p0.lerp(p1, k / n)
        mb.box((q.x, q.y, z0 + h / 2), (pw, pw, h), mats['frame'])
        if lod <= 1:
            mb.cylinder((q.x, q.y, z0 + h + 0.03), 0.032, 0.05, mats['polish'], segs=C.lod_pick(lod, 8, 6))
    beam(mb, p0 + up * (h - 0.015), p1 + up * (h - 0.015), 0.06, 0.035, mats['polish'])
    if lod <= 2:
        beam(mb, p0 + up * 0.08, p1 + up * 0.08, 0.035, 0.03, mats['frame'])
    if lod <= 1:
        beam(mb, p0 + up * (h - 0.16), p1 + up * (h - 0.16), 0.03, 0.025, mats['frame'])
    if fret and lod == 0:
        t = (p1 - p0).normalized()
        for k in range(n):
            q0 = p0.lerp(p1, k / n); q1 = p0.lerp(p1, (k + 1) / n)
            bl = (q1 - q0).length
            m = (q0 + q1) / 2
            # key fret: two verticals + a mid horizontal + a short hook, 18 mm bars
            for s in (-0.28, 0.28):
                c = m + t * s * bl
                beam(mb, c + up * 0.1, c + up * (h - 0.17), 0.018, 0.018, mats['frame'])
            zf = 0.1 + (h - 0.27) * 0.55
            beam(mb, m - t * 0.28 * bl + up * zf, m + t * 0.28 * bl + up * zf, 0.018, 0.018, mats['frame'])
            beam(mb, m - t * 0.12 * bl + up * (zf - 0.14), m + t * 0.12 * bl + up * (zf - 0.14), 0.018, 0.018, mats['frame'])
            beam(mb, m + up * (zf - 0.14), m + up * zf, 0.018, 0.018, mats['frame'])


# ------------------------------------------------------------------------------------------- lanterns
def hanging_lantern(mb, anchor, out, mats, lod, size=0.22, height=0.38, arm=0.35, drop=0.12):
    """bronze bracket arm from `anchor` (on a post / eave) reaching `arm` along `out` (xy unit), a short hanger
    and a slim lantern (paper box, frame bars, hip cap). mats = dict(frame, paper). Returns the light centre."""
    a = Vector(anchor)
    o = Vector((out[0], out[1], 0)).normalized()
    tip = a + o * arm
    beam(mb, a, tip, 0.04, 0.05, mats['frame'])
    if lod <= 1:
        beam(mb, a - Vector((0, 0, 0.18)), a + o * (arm * 0.6), 0.03, 0.03, mats['frame'])   # knee strut
    top = tip - Vector((0, 0, drop))
    if lod <= 2:
        beam(mb, tip, top + Vector((0, 0, 0.1)), 0.015, 0.015, mats['frame'], up=(1, 0, 0))
    base = top - Vector((0, 0, height + 0.08))
    return C.lantern_head(mb, tuple(base), dict(iron=mats['frame'], paper=mats['paper']), lod, size=size,
                          height=height, roof='hip', frame_w=0.022, ball=False)


# ------------------------------------------------------------------------------------------- cables
def catenary(p0, p1, sag, n):
    """points of a parabola-approximated catenary from p0 to p1 with mid-span sag (m below the chord)"""
    p0, p1 = Vector(p0), Vector(p1)
    return [p0.lerp(p1, i / n) - Vector((0, 0, 4 * sag * (i / n) * (1 - i / n))) for i in range(n + 1)]


def cable(mb, pts, rad, mi, sides=4):
    return C.tube(mb, pts, [rad] * len(pts), mi, sides=sides, cap0=True, cap1=True)
