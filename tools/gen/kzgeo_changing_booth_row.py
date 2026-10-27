"""Helpers for gen_changing_booth_row: the face / prism helpers of kzgeo_yukata_shelves plus a deterministic pleated
noren panel and a crest decal that follows the same pleat field (no material or object code).

Faces are oriented by an explicit outward hint, so the generator can skip a global normal recalc (which
flips lone quads at random). Section points are (u, v): axis 'x' -> (y, z), 'y' -> (x, z), 'z' -> (x, y).
"""
import math

from mathutils import Vector


def face(bm, vs, mi, out):
    f = bm.faces.new(vs)
    f.material_index = mi
    f.normal_update()
    if f.normal.dot(Vector(out)) < 0:
        f.normal_flip()
    return f


def quad(bm, pts, mi, out):
    return face(bm, [bm.verts.new(p) for p in pts], mi, out)


def _P(axis):
    if axis == 'x':
        return lambda u, v, t: (t, u, v)
    if axis == 'y':
        return lambda u, v, t: (u, t, v)
    return lambda u, v, t: (u, v, t)


def ext(bm, sec, axis, a0, a1, mi, caps=(True, True), skip=(), mi_cap=None, mi_front=None):
    """Extrude a 2D section along an axis between a0 and a1. Side i (sec[i] -> sec[i+1]) is skipped when i
    is in `skip` (hidden against something). mi_front: faces whose normal is mostly +Y get this slot.
    Returns (faces, verts)."""
    P = _P(axis)
    area = sum(sec[i][0] * sec[(i + 1) % len(sec)][1] - sec[(i + 1) % len(sec)][0] * sec[i][1] for i in range(len(sec)))
    sgn = 1.0 if area > 0 else -1.0
    n = len(sec)
    A = [bm.verts.new(P(u, v, a0)) for u, v in sec]
    B = [bm.verts.new(P(u, v, a1)) for u, v in sec]
    faces = []
    for i in range(n):
        if i in skip:
            continue
        j = (i + 1) % n
        du, dv = sec[j][0] - sec[i][0], sec[j][1] - sec[i][1]
        out = P(dv * sgn, -du * sgn, 0.0)
        faces.append(face(bm, [A[i], A[j], B[j], B[i]], mi, out))
    if caps[0]:
        faces.append(face(bm, A[::-1], mi if mi_cap is None else mi_cap, P(0, 0, -1)))
    if caps[1]:
        faces.append(face(bm, B, mi if mi_cap is None else mi_cap, P(0, 0, 1)))
    if mi_front is not None:
        for f in faces:
            if f.normal.y > 0.6:
                f.material_index = mi_front
    return faces, A + B


def box_open(bm, x0, x1, y0, y1, z0, z1, mi, sides='fbtlrk'):
    """axis-aligned box from chosen faces only: f(ront +y) b(ottom) t(op) l(eft -x) r(ight +x) k (back -y)"""
    fs = []
    if 'f' in sides:
        fs.append(quad(bm, [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], mi, (0, 1, 0)))
    if 'k' in sides:
        fs.append(quad(bm, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], mi, (0, -1, 0)))
    if 't' in sides:
        fs.append(quad(bm, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mi, (0, 0, 1)))
    if 'b' in sides:
        fs.append(quad(bm, [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], mi, (0, 0, -1)))
    if 'l' in sides:
        fs.append(quad(bm, [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], mi, (-1, 0, 0)))
    if 'r' in sides:
        fs.append(quad(bm, [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], mi, (1, 0, 0)))
    return fs


def chamfer_rect(u0, u1, v0, v1, c):
    """CCW rectangle with all four corners chamfered by c (c = 0: plain rectangle)"""
    if c <= 0:
        return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    return [(u0 + c, v0), (u1 - c, v0), (u1, v0 + c), (u1, v1 - c), (u1 - c, v1), (u0 + c, v1), (u0, v1 - c), (u0, v0 + c)]


def stadium(yf, yb, z0, t, n, puff=0.0):
    """(y, z) section of a folded cloth item lying on z0, front fold at yf (rounded, radius t/2), back at
    yb (rounded), top puffed by `puff` at mid-depth. n arc segments per end (n >= 1). Never a knife edge:
    the ends are half-circles of the full thickness."""
    r = t / 2
    zc = z0 + r
    pts = []
    for k in range(n + 1):                       # front arc, bottom -> top
        a = -math.pi / 2 + math.pi * k / n
        pts.append((yf - r + r * math.cos(a), zc + r * math.sin(a)))
    pts.append(((yf + yb) / 2, z0 + t + puff))
    for k in range(n + 1):                       # back arc, top -> bottom
        a = math.pi / 2 + math.pi * k / n
        pts.append((yb + r + r * math.cos(a), zc + r * math.sin(a)))
    pts.append(((yf + yb) / 2, z0 - 0.0))
    # drop duplicate neighbours
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6):
            out.append(p)
    return out


def loft(bm, loops, mi, cap0=True, cap1=True, mis=None):
    """quad bands between closed loops of equal length (list of 3D point lists); caps the ends.
    mis: optional slot per band. Orientation: outward for loops listed bottom -> top with CCW points
    (seen from +Z) when the radius grows or stays, inward bands (going down inside) face the axis."""
    rings = [[bm.verts.new(p) for p in L] for L in loops]
    faces = []
    n = len(loops[0])
    for bi, (A, B) in enumerate(zip(rings[:-1], rings[1:])):
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = mi if mis is None else mis[bi]
            faces.append(f)
    if cap0:
        f = bm.faces.new(rings[0][::-1]); f.material_index = mi if mis is None else mis[0]; faces.append(f)
    if cap1:
        f = bm.faces.new(rings[-1]); f.material_index = mi if mis is None else mis[-1]; faces.append(f)
    return faces


def rot_verts(vs, cx, cy, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    for v in vs:
        x, y = v.co.x - cx, v.co.y - cy
        v.co.x, v.co.y = cx + c * x - s * y, cy + s * x + c * y


# ------------------------------------------------------------------ noren cloth with an analytic pleat field
class Pleats:
    """y-displacement of a hanging panel: ridge / valley ripples whose depth grows from a0 under the head
    band to a1 at the hem, plus a forward belly over the lower part. Deterministic, so a decal can follow."""

    def __init__(self, x0, x1, z_top, z_hem, ripples, a0, a1, belly, phase):
        self.x0, self.x1, self.zt, self.zh = x0, x1, z_top, z_hem
        self.lam = (x1 - x0) / ripples
        self.a0, self.a1, self.belly, self.phase = a0, a1, belly, phase

    def s(self, z):
        return min(1.0, max(0.0, (self.zt - z) / max(1e-6, self.zt - self.zh)))

    def dy(self, x, z):
        s = self.s(z)
        A = self.a0 + (self.a1 - self.a0) * s ** 1.4
        rip = math.sin(2 * math.pi * (x - self.x0) / self.lam + self.phase)
        bel = self.belly * math.sin(math.pi * min(1.0, max(0.0, (s - 0.35) / 0.65))) ** 1.2
        return A * rip + bel


def noren_panel(bm, P, y0, cols, rows, mi, mi_band, band_h, sway, hem_lift=0.0, flare=0.0, side=0):
    """grid panel facing +Y following Pleats P; the top band_h gets mi_band; '_sway' (0 top .. 1 hem).
    flare: the outer hem corner swings out sideways by this much (slit opening), side = -1 / +1 / 0."""
    zt, zh = P.zt, P.zh
    zs = ([zt, zt - band_h] if band_h > 0 else [zt]) + [zt - band_h - (zt - band_h - zh) * (k / rows) ** 0.9 for k in range(1, rows + 1)]
    grid = []
    for ci in range(cols + 1):
        u = ci / cols
        x = P.x0 + (P.x1 - P.x0) * u
        col = []
        for zi, z in enumerate(zs):
            s = P.s(z)
            zz = z + (hem_lift * u if zi == len(zs) - 1 else 0.0)
            xo = flare * s ** 2 * (u if side < 0 else (1 - u) if side > 0 else 0.0) * side   # slit edges part at the hem
            v = bm.verts.new((x + xo, y0 + P.dy(x, z), zz))
            v[sway] = s ** 1.3
            col.append(v)
        grid.append(col)
    fs = []
    for ci in range(cols):
        for zi in range(len(zs) - 1):
            fs.append(face(bm, [grid[ci][zi], grid[ci][zi + 1], grid[ci + 1][zi + 1], grid[ci + 1][zi]],
                           mi_band if (zi == 0 and band_h > 0) else mi, (0, 1, 0)))
    return fs


def decal_tris(bm, tris2d, P, y0, off, mi, sway, sub=2):
    """2D triangles (x, z) laid on the pleat field, `off` in front of the cloth; each triangle is split
    `sub` times (4^sub pieces) so it bends with the pleats instead of cutting through them."""
    out = []

    def split(t, n):
        if n == 0:
            return [t]
        a, b, c = t
        ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        bc = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        ca = ((c[0] + a[0]) / 2, (c[1] + a[1]) / 2)
        r = []
        for tt in ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)):
            r += split(tt, n - 1)
        return r
    for t in tris2d:
        for a, b, c in split(t, sub):
            vs = []
            for x, z in (a, b, c):
                v = bm.verts.new((x, y0 + P.dy(x, z) + off, z))
                v[sway] = P.s(z) ** 1.3
                vs.append(v)
            out.append(face(bm, vs, mi, (0, 1, 0)))
    return out


def ring_tris(cx, cz, r_in, r_out, n):
    """annulus as 2D triangles"""
    t = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0 = (cx + r_in * math.cos(a0), cz + r_in * math.sin(a0)); p1 = (cx + r_out * math.cos(a0), cz + r_out * math.sin(a0))
        p2 = (cx + r_out * math.cos(a1), cz + r_out * math.sin(a1)); p3 = (cx + r_in * math.cos(a1), cz + r_in * math.sin(a1))
        t += [(p0, p1, p2), (p0, p2, p3)]
    return t


def poly_tris(poly):
    """2D polygon -> triangles (ear clipping via mathutils)"""
    from mathutils import Vector as V
    from mathutils.geometry import tessellate_polygon
    idx = tessellate_polygon([[V((x, y, 0)) for x, y in poly]])
    return [(poly[i], poly[j], poly[k]) for i, j, k in idx]


def mountain(lo=False):
    import kzgeo_noren
    return kzgeo_noren.mountain(lo=lo)
