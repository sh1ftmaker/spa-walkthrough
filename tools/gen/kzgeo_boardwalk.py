"""kzgeo_boardwalk: timber-structure helpers shared by the op20 generators (boardwalk, deck_slatted,
pier_trestle, aqueduct). Run inside Blender.

  Path                    arc-length sampler over a 3D polyline (from kzgeo_railing)
  run_path(path, length)  default straight run along X, centred on the origin
  stations(path, ds)      sample s-values (ends, corners, every ds on curves)
  frames(path, ss)        (point, tangent, left normal, mitre scale) per station
  beam(...)               a member from a to b with a rect / chamfered / top-chamfered section
  hsweep(...)             a profile (across, up) swept along plan stations with mitred joints
  frustum(...)            a tapered block (footings, stone courses)
  quad(...)               a single quad (LOD3 cards)
  plank_layout(...)       plank / board centres along a path (pitch, gap, ragged jitter)
"""
import math

from mathutils import Vector

import kzgeo_common as C
from kzgeo_railing import Path  # noqa: F401  (re-exported)

Z = Vector((0, 0, 1))


def run_path(path, length):
    if path:
        return Path(path)
    return Path([(-length / 2, 0.0, 0.0), (length / 2, 0.0, 0.0)])


def stations(path, ds=0.3):
    ss = {0.0, round(path.L, 6)}
    for c in path.corners(min_deg=2.0):
        ss.add(round(c, 6))
    if path.curved():
        n = max(1, int(math.ceil(path.L / ds)))
        for k in range(1, n):
            ss.add(round(path.L * k / n, 6))
    return sorted(ss)


def left(t):
    return Vector((-t.y, t.x, 0.0))


def frames(path, ss):
    """per station: point, plan tangent, left normal (mitred, scaled so offsets keep their width)"""
    out = []
    eps = 1e-3
    for s in ss:
        p, t, _ = path.at(s)
        _, t0, _ = path.at(max(0.0, s - eps))
        _, t1, _ = path.at(min(path.L, s + eps))
        n0, n1 = left(t0), left(t1)
        n = (n0 + n1)
        n = n.normalized() if n.length > 1e-6 else left(t)
        sc = 1.0 / max(0.5, n.dot(n0))
        out.append((p, t, n, sc))
    return out


def profile(kind, w, h, ch=0.0):
    """section points (x across, z up), centred, counter-clockwise"""
    a, b = w / 2, h / 2
    ch = min(ch, 0.45 * min(w, h))
    if kind == 'rect' or ch <= 1e-5:
        return [(-a, -b), (a, -b), (a, b), (-a, b)]
    if kind == 'oct':
        return [(-a + ch, -b), (a - ch, -b), (a, -b + ch), (a, b - ch), (a - ch, b), (-a + ch, b), (-a, b - ch), (-a, -b + ch)]
    if kind == 'top':
        return [(-a, -b), (a, -b), (a, b - ch), (a - ch, b), (-a + ch, b), (-a, b - ch)]
    if kind == 'round':          # 2-segment rounds on the top edges, a small chamfer underneath
        c2 = ch * 0.35
        k = ch * (1 - math.cos(math.radians(45)))
        return [(-a + c2, -b), (a - c2, -b), (a, -b + c2), (a, b - ch), (a - k, b - k), (a - ch, b),
                (-a + ch, b), (-a + k, b - k), (-a, b - ch), (-a, -b + c2)]
    raise ValueError(kind)


def _ring(bm, origin, x, u, prof, sx=1.0):
    return [bm.verts.new(origin + x * (px * sx) + u * pz) for px, pz in prof]


def beam(mb, a, b, side, w, h, mi, kind='rect', ch=0.0, caps=(True, True), skip=()):
    """Member from a to b. `side` is the across direction (projected perpendicular to the axis); w is the
    size along side, h the size along the third axis (kept pointing up where possible). skip: indices
    of profile edges to leave open (e.g. the hidden underside of a LOD3 board)."""
    bm = mb.bm
    a, b = Vector(a), Vector(b)
    f = (b - a).normalized()
    s = Vector(side)
    s = (s - f * s.dot(f))
    if s.length < 1e-6:
        s = f.cross(Z) if abs(f.z) < 0.99 else Vector((1, 0, 0))
    s.normalize()
    u = s.cross(f).normalized()
    if u.z < -1e-6:
        u = -u
    prof = profile(kind, w, h, ch)
    A = _ring(bm, a, s, u, prof)
    B = _ring(bm, b, s, u, prof)
    faces = C.bridge_rings(bm, A, B, skip=set(skip))
    if caps[0]:
        faces.append(bm.faces.new(A[::-1]))
    if caps[1]:
        faces.append(bm.faces.new(B))
    _orient_out(faces, (a + b) / 2)
    mb._tag(faces, mi)
    return faces


def _orient_out(faces, centre):
    for f in faces:
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - centre) < 0:
            f.normal_flip()


def hsweep(mb, fr, prof, mi, off=0.0, z=0.0, caps=(True, True), skip=()):
    """Sweep prof [(x across, z up)] along station frames `fr` (from frames()), offset `off` to the left
    and lifted by z (+ the path z). Joints are mitred in plan."""
    bm = mb.bm
    rings = []
    for p, t, n, sc in fr:
        o = Vector((p.x, p.y, p.z + z)) + n * (off * sc)
        rings.append([bm.verts.new(o + n * (px * sc) + Z * pz) for px, pz in prof])
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        fs = C.bridge_rings(bm, A, B, skip=set(skip))
        faces += fs
    if caps[0]:
        faces.append(bm.faces.new(rings[0][::-1]))
    if caps[1]:
        faces.append(bm.faces.new(rings[-1]))
    bmesh_recalc(mb, faces)
    mb._tag(faces, mi)
    return faces


def bmesh_recalc(mb, faces):
    import bmesh
    bmesh.ops.recalc_face_normals(mb.bm, faces=faces)


def frustum(mb, c, w0, d0, w1, d1, z0, z1, mi, yaw=0.0, top=True, bottom=False):
    """tapered block: w0 x d0 at z0 -> w1 x d1 at z1, centred on c (x, y), rotated by yaw"""
    bm = mb.bm
    cs, sn = math.cos(yaw), math.sin(yaw)

    def P(x, y, z):
        return bm.verts.new((c[0] + x * cs - y * sn, c[1] + x * sn + y * cs, z))
    A = [P(-w0 / 2, -d0 / 2, z0), P(w0 / 2, -d0 / 2, z0), P(w0 / 2, d0 / 2, z0), P(-w0 / 2, d0 / 2, z0)]
    B = [P(-w1 / 2, -d1 / 2, z1), P(w1 / 2, -d1 / 2, z1), P(w1 / 2, d1 / 2, z1), P(-w1 / 2, d1 / 2, z1)]
    faces = C.bridge_rings(bm, A, B)
    if top:
        faces.append(bm.faces.new(B))
    if bottom:
        faces.append(bm.faces.new(A[::-1]))
    _orient_out(faces, Vector((c[0], c[1], (z0 + z1) / 2)))
    mb._tag(faces, mi)
    return faces


def quad(mb, pts, mi):
    vs = [mb.bm.verts.new(p) for p in pts]
    f = mb.bm.faces.new(vs)
    mb._tag([f], mi)
    return [f]


def plank_layout(L, pitch_fn, r=None, end_gap=None):
    """centres and widths of boards along a run of length L: pitch_fn(r) -> (board width, gap).
    Boards fill the run with a half gap at each end (modules chain without a double gap)."""
    out = []
    s = 0.0
    while True:
        w, g = pitch_fn()
        if s + g / 2 + w > L + 1e-6:
            break
        out.append((s + g / 2 + w / 2, w))
        s += w + g
    if out:                                  # spread the remainder evenly so the ends match
        rem = L - s
        k = len(out)
        out = [(c + rem * (i + 0.5) / k, w) for i, (c, w) in enumerate(out)]
    return out


def fan_tangent(path, s, blend):
    """plan tangent for a board at s: within `blend` of a polyline corner the boards fan from one segment's
    direction to the next (no wedge gaps or overlaps at corners)."""
    p, t, _ = path.at(s)
    for (s0, s1, a, d), (_, _, _, d2) in zip(path.segs[:-1], path.segs[1:]):
        if abs(s - s1) < blend:
            ta = Vector((d.x, d.y, 0)).normalized(); tb = Vector((d2.x, d2.y, 0)).normalized()
            f = (s - s1 + blend) / (2 * blend)
            f = f * f * (3 - 2 * f)
            t = (ta * (1 - f) + tb * f)
            if t.length > 1e-6:
                t.normalize()
            break
    return p, t


def grain_uv(obj, mis):
    """Re-project UV0 (metres) on timber faces so the texture's grain (V) runs along each member: per face,
    V follows the longest edge, U the in-plane perpendicular. genlib.uv0_metric box-projects every side
    face with V = world z, which stands the grain upright on beams, stringers and troughs."""
    import bmesh
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    mis = set(mis)
    for f in bm.faces:
        if f.material_index not in mis or len(f.verts) < 3:
            continue
        n = f.normal
        e = max((ed for ed in f.edges), key=lambda ed: ed.calc_length())
        d = e.verts[1].co - e.verts[0].co
        d = d - n * d.dot(n)
        if d.length < 1e-9:
            continue
        d.normalize()
        b = n.cross(d)
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = (co.dot(b), co.dot(d))
    bm.to_mesh(me); bm.free()
