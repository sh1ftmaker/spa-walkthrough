"""Small closed-solid / single-face helpers shared by gen_yukata_shelves (no material or object code).

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
