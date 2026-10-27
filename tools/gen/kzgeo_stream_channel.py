"""Geometry helpers for gen_stream_channel: path frames, chamfered ashlar blocks, craggy flat-topped boulders,
irregular lip slabs, stepped-runnel treads, UV island jitter. All add faces to a genlib.MeshBuilder bmesh."""
import math
import bmesh
from mathutils import Matrix, Vector, noise

Z = Vector((0, 0, 1))


# ---------------------------------------------------------------- path
class Path:
    """Polyline in XY with z per node. Arc length s is measured in plan. Frame: right = tan x Z (local +x),
    tan (local +y, downstream), Z up."""

    def __init__(self, pts):
        self.p = [Vector(q) for q in pts]
        self.s = [0.0]
        for a, b in zip(self.p[:-1], self.p[1:]):
            self.s.append(self.s[-1] + (Vector((b.x - a.x, b.y - a.y, 0))).length)
        self.L = self.s[-1]
        self.flat = max(q.z for q in self.p) - min(q.z for q in self.p) < 0.01

    def at(self, s):
        s = max(0.0, min(self.L, s))
        for i in range(len(self.s) - 1):
            if s <= self.s[i + 1] + 1e-9:
                t = (s - self.s[i]) / max(self.s[i + 1] - self.s[i], 1e-9)
                p = self.p[i].lerp(self.p[i + 1], t)
                d = self.p[i + 1] - self.p[i]
                # smooth the tangent across nodes (average with the neighbour segment near the joint)
                tan = Vector((d.x, d.y, 0)).normalized()
                if t > 0.7 and i + 2 < len(self.p):
                    d2 = self.p[i + 2] - self.p[i + 1]
                    tan = tan.lerp(Vector((d2.x, d2.y, 0)).normalized(), (t - 0.7) / 0.6).normalized()
                elif t < 0.3 and i > 0:
                    d0 = self.p[i] - self.p[i - 1]
                    tan = tan.lerp(Vector((d0.x, d0.y, 0)).normalized(), (0.3 - t) / 0.6).normalized()
                return p, tan
        d = self.p[-1] - self.p[-2]
        return self.p[-1], Vector((d.x, d.y, 0)).normalized()

    def z(self, s):
        return self.at(s)[0].z

    def right(self, s):
        t = self.at(s)[1]
        return Vector((t.y, -t.x, 0))

    def pt(self, s, u, z):
        p, t = self.at(s)
        return Vector((p.x + t.y * u, p.y - t.x * u, z))

    def M(self, s, u=0.0, z=0.0, yaw=0.0):
        """4x4 frame at (s, u, z): local x = right, y = downstream, z = up (optionally yawed)."""
        p, t = self.at(s)
        o = Vector((p.x + t.y * u, p.y - t.x * u, z))
        if yaw:
            c, si = math.cos(yaw), math.sin(yaw)
            t = Vector((t.x * c - t.y * si, t.x * si + t.y * c, 0))
        x = Vector((t.y, -t.x, 0))
        M = Matrix.Identity(4)
        for i in range(3):
            M[i][0], M[i][1], M[i][2], M[i][3] = x[i], t[i], Z[i], o[i]
        return M

    def yaw(self, s):
        t = self.at(s)[1]
        return math.atan2(t.y, t.x)


def _faces_of(vs):
    return list({f for v in vs for f in v.link_faces})


# ---------------------------------------------------------------- cut stone
def block(mb, M, x0, x1, y0, y1, z0, z1, mi, ch=0.0, ch_end=0.0, bottom=False, caps=(True, True)):
    """Ashlar block in local frame M: x0..x1 across, y0..y1 along, z0..z1 up. `ch` chamfers the two top long
    edges, `ch_end` also chamfers/insets the end faces (so joints between neighbouring blocks read as V grooves).
    Open bottom by default (sits on something). Tris: 10 plain, 18 top chamfer, 38 with end chamfers."""
    bm = mb.bm

    def prof(e):
        if ch > 0:
            return [(x0 + e, z0), (x1 - e, z0), (x1 - e, z1 - ch - e), (x1 - ch - e, z1 - e),
                    (x0 + ch + e, z1 - e), (x0 + e, z1 - ch - e)]
        return [(x0 + e, z0), (x1 - e, z0), (x1 - e, z1 - e), (x0 + e, z1 - e)]

    if ch_end > 0:
        sts = [(y0, ch_end), (y0 + ch_end, 0.0), (y1 - ch_end, 0.0), (y1, ch_end)]
    else:
        sts = [(y0, 0.0), (y1, 0.0)]
    rings = []
    for y, e in sts:
        rings.append([bm.verts.new(M @ Vector((x, y, z))) for x, z in prof(e)])
    n = len(rings[0])
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        for i in range(n):
            if i == 0 and not bottom:
                continue
            j = (i + 1) % n
            faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    if caps[0]:
        faces.append(bm.faces.new(rings[0][::-1]))
    if caps[1]:
        faces.append(bm.faces.new(rings[-1]))
    mb._tag(faces, mi)
    return faces


def tread(mb, M, x0, x1, ya, yb, zb, T, mi, nose=0.05, lip_t=0.06, round_=True):
    """Stepped-runnel tread across x0..x1: flat top at T from ya to yb, a rounded nosing projecting `nose`
    beyond the riser face at yb, riser down to zb. Back face, bottom and x-ends are hidden (dropped)."""
    bm = mb.bm
    if nose <= 0:
        prof = [(ya, T), (yb, T), (yb, zb)]
    elif round_:
        r = 0.022
        prof = [(ya, T), (yb + nose - r, T)]
        for k in range(1, 4):
            a = math.pi / 2 * (1 - k / 3.0)
            prof.append((yb + nose - r + r * math.cos(a), T - r + r * math.sin(a)))
        prof += [(yb + nose - 0.006, T - lip_t), (yb, T - lip_t), (yb, zb)]
    else:
        prof = [(ya, T), (yb + nose, T), (yb + nose, T - lip_t), (yb, T - lip_t), (yb, zb)]
    L_ = [bm.verts.new(M @ Vector((x0, y, z))) for y, z in prof]
    R_ = [bm.verts.new(M @ Vector((x1, y, z))) for y, z in prof]
    faces = []
    for i in range(len(prof) - 1):
        faces.append(bm.faces.new((L_[i], L_[i + 1], R_[i + 1], R_[i])))
    mb._tag(faces, mi)
    return faces


# ---------------------------------------------------------------- rocks
def crag_rock(mb, M, rx, ry, z0, ztop, mi, r, nside=7, bands=3, tilt=0.05, crag=0.17, top_inset=0.6, dome=False, lean=(0.0, 0.0)):
    """Dark craggy flat-topped boulder (lookbook 04 bank masses): irregular lumpy footprint, a bulging belly,
    a rounded shoulder and a tilted, flat, lumpy top whose outline differs from the base (so the sides twist
    into irregular facets). Per-vertex noise crags the sides. Open bottom (sits in the bed).
    M: local frame at the rock centre; z0/ztop are local z. Tris = 2*bands*nside + (nside if dome else nside-2)."""
    bm = mb.bm
    H = max(0.03, ztop - z0)
    off = Vector((r.uniform(0, 99), r.uniform(0, 99), r.uniform(0, 99)))
    angs = [2 * math.pi * (i + r.uniform(-0.32, 0.32)) / nside for i in range(nside)]
    # lumpy outline: random radial factors, lightly smoothed so it is boulder-like, not a regular polygon
    raw = [r.uniform(0.72, 1.18) for _ in range(nside)]
    fac = [0.6 * raw[i] + 0.2 * raw[i - 1] + 0.2 * raw[(i + 1) % nside] for i in range(nside)]
    tfac = [f * r.uniform(0.8, 1.15) for f in fac]            # top outline differs from the base
    ringdef = {3: [(0.0, 1.06), (0.36, 1.05), (0.74, 0.9), (1.0, top_inset)],
               2: [(0.0, 1.05), (0.6, 0.97), (1.0, top_inset + 0.04)],
               1: [(0.0, 1.0), (1.0, top_inset + 0.1)]}[bands]
    tx, ty = r.uniform(-tilt, tilt), r.uniform(-tilt, tilt)
    twist = r.uniform(-0.25, 0.25)
    rings = []
    for hf, rs in ringdef:
        ring = []
        for i, a in enumerate(angs):
            a2 = a + twist * hf
            ca, sa = math.cos(a2), math.sin(a2)
            f = fac[i] + (tfac[i] - fac[i]) * hf
            nv = noise.noise(Vector((ca * 2.1, sa * 2.1, hf * 2.5)) + off)
            rad = rs * f * (1.0 + crag * nv)
            x, y = ca * rx * rad, sa * ry * rad
            if hf >= 1.0:
                z = ztop + (tx * x / max(rx, 1e-3) + ty * y / max(ry, 1e-3)) * H * 0.6 \
                    + 0.05 * H * noise.noise(Vector((ca, sa, 0)) * 3 + off)
            elif hf <= 0.0:
                z = z0
            else:
                z = z0 + H * hf + 0.08 * H * noise.noise(Vector((ca, sa, hf)) * 3 + off * 1.3)
            x += lean[0] * hf ** 1.5; y += lean[1] * hf ** 1.5
            ring.append(bm.verts.new(M @ Vector((x, y, z))))
        rings.append(ring)
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        for i in range(nside):
            j = (i + 1) % nside
            faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    top = rings[-1]
    if dome:
        c = sum((v.co for v in top), Vector()) / len(top) + Vector((0, 0, 0.012 + 0.02 * H))
        cv = bm.verts.new(c)
        for i in range(nside):
            faces.append(bm.faces.new((top[i], top[(i + 1) % nside], cv)))
    else:
        faces.append(bm.faces.new(top))
    mb._tag(faces, mi)
    return faces


def lip_slab(mb, M, x0, x1, y_back, y_front, zb, zt, mi, r, notches=2, jag=0.02, npts=6, bottom=True):
    """Irregular weir lip stone: straight back edge at y_back, a ragged front edge around y_front with `notches`
    shallow spill notches, extruded zb..zt (bottom kept: the lip overhangs and its underside is seen)."""
    bm = mb.bm
    front = []
    nn = set(r.sample(range(1, npts - 1), min(notches, max(0, npts - 2))))
    for i in range(npts):
        x = x0 + (x1 - x0) * i / (npts - 1) + (r.uniform(-0.3, 0.3) * (x1 - x0) / (npts - 1) if 0 < i < npts - 1 else 0)
        y = y_front + r.uniform(-jag, jag) - (0.035 if i in nn else 0.0)
        front.append((x, y))
    poly = [(x0, y_back), (x1, y_back)] + front[::-1]
    # ensure CCW (viewed from +z)
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    if a < 0:
        poly = poly[::-1]
    bot = [bm.verts.new(M @ Vector((x, y, zb))) for x, y in poly]
    top = [bm.verts.new(M @ Vector((x, y, zt + r.uniform(-0.004, 0.004)))) for x, y in poly]
    faces = [bm.faces.new(top)]
    if bottom:
        faces.append(bm.faces.new(bot[::-1]))
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((bot[i], bot[j], top[j], top[i])))
    mb._tag(faces, mi)
    return faces


def grid_strip(mb, P, s0, s1, u0, u1, zfn, mi, ns=4, nu=2):
    """Bed surface between u0..u1 from s0..s1, z = zfn(s, u)."""
    bm = mb.bm
    rows = []
    for i in range(ns + 1):
        s = s0 + (s1 - s0) * i / ns
        rows.append([bm.verts.new(P.pt(s, u0 + (u1 - u0) * j / nu, zfn(s, u0 + (u1 - u0) * j / nu))) for j in range(nu + 1)])
    faces = []
    for A, B in zip(rows[:-1], rows[1:]):
        for j in range(nu):
            faces.append(bm.faces.new((A[j], B[j], B[j + 1], A[j + 1])))
    for f in faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    mb._tag(faces, mi)
    return faces


# ---------------------------------------------------------------- UVs
def uv_island_jitter(obj, r, slots=None, span=2.0, rotate=True):
    """Offset (and rotate by 90 deg steps) UV0 per connected island so neighbouring stones do not share the
    same texture patch (reviewers: 'each stone should differ')."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap')
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen or (slots is not None and f0.material_index not in slots):
            continue
        isl, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index); stack.append(g)
        du, dv = r.uniform(0, span), r.uniform(0, span)
        rot = r.randrange(4) if rotate else 0
        for f in isl:
            for l in f.loops:
                u_, v_ = l[uv].uv
                for _ in range(rot):
                    u_, v_ = -v_, u_
                l[uv].uv = (u_ + du, v_ + dv)
    bm.to_mesh(me); bm.free()
