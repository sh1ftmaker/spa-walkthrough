"""Rock surround for gen_lantern_niche (op01): one closed craggy basalt block with a niche cut into its front.

niche_rock() builds N-vertex rings that share their angles, so they bridge into one closed solid:
  R0 outer outline at the back face, R1 outer outline at the front edge, R2 a craggy mid ring on the front
  face (LOD0 only), R3 the niche lip, R4 the niche back. Caps: R0 (wall side) and R4 (niche back wall).
The niche floor is the flat bottom run of the opening (p_bot 10), so the lantern stands level on it.
"""
import math

import bmesh
from mathutils import Vector, noise

import kzgeo_common as C
import kzgeo_lantern_floor as L


def outline(r, W, H, p=3.2, amp=0.07, bites=1):
    """seeded lumpy outline in the x-z plane: theta -> (x, z), half-sizes W/2, H/2"""
    ph = [r.uniform(0, 2 * math.pi) for _ in range(5)]
    am = [amp * a for a in (0.9, 0.6, 0.45, 0.3, 0.2)]
    bite_at = [r.uniform(0, 2 * math.pi) for _ in range(bites)]
    bite_d = [r.uniform(0.06, 0.11) for _ in range(bites)]

    def f(th):
        k = L.shape_r('sq', th, p)
        n = 1.0 + sum(a * math.sin((i + 2) * th + ph[i]) for i, a in enumerate(am))
        for b, d in zip(bite_at, bite_d):
            dd = math.atan2(math.sin(th - b), math.cos(th - b))
            n -= d * math.exp(-(dd / 0.28) ** 2)
        return (W / 2 * k * n * math.cos(th), H / 2 * k * n * math.sin(th))
    return f


def opening(ow, oh, cz, p_top=4.0, p_bot=10.0):
    def f(th):
        p = p_top if math.sin(th) > 0 else p_bot
        k = L.shape_r('sq', th, p)
        return (ow / 2 * k * math.cos(th), cz + oh / 2 * k * math.sin(th))
    return f


def niche_rock(mb, f_out, f_open, D, depth, mi_face, mi_in, seed, N=16, mid=True, crag=0.018, back_cap=True):
    bm = mb.bm
    off = Vector(((seed * 13.7) % 50, (seed * 5.3) % 40, (seed * 2.9) % 30))

    def nz(x, y, z, s=7.0):
        return noise.noise(Vector((x, y, z)) * s + off)
    yf, yb = D / 2, -D / 2
    rings = []
    ths = [math.pi / 4 + 2 * math.pi * k / N for k in range(N)]       # N in 4, 8, 16: corners at 45 deg, flat sill run
    # R0 back outline, R1 front edge (pulled in 6 % and back 2 cm: a rounded shoulder)
    R0 = [bm.verts.new((x, yb, z)) for x, z in (f_out(t) for t in ths)]
    R1 = []
    for t in ths:
        x, z = f_out(t)
        R1.append(bm.verts.new((x * 0.96 + crag * nz(x, yf, z), yf - 0.02 - abs(crag * nz(x, 0, z, 4.0)), z * 0.96)))
    rings += [R0, R1]
    if mid:
        R2 = []
        for t in ths:
            xo, zo = f_out(t); xi, zi = f_open(t)
            x, z = (xo + xi) / 2, (zo + zi) / 2
            R2.append(bm.verts.new((x + crag * 0.6 * nz(x, 1, z), yf - crag * 0.8 + crag * 0.8 * nz(x, 2, z, 5.0), z + crag * 0.6 * nz(x, 3, z))))
        rings.append(R2)
    R3 = [bm.verts.new((x, yf - 0.006 - 0.008 * abs(nz(x, 4, z)), z)) for x, z in (f_open(t) for t in ths)]
    R4 = []
    cz = (f_open(math.pi / 2)[1] + f_open(1.5 * math.pi)[1]) / 2
    for t in ths:
        x, z = f_open(t)
        sill = math.sin(t) < -0.5            # niche floor stays level for the lantern
        R4.append(bm.verts.new((x * 0.86, yf - depth, z if sill else cz + (z - cz) * 0.9)))
    rings += [R3, R4]
    side = C.bridge_rings(bm, R0, R1)
    front = []
    for A, B in zip(rings[1:-2], rings[2:-1]):
        front += C.bridge_rings(bm, A, B)
    tun = C.bridge_rings(bm, R3, R4)
    caps = ([bm.faces.new(R0[::-1])] if back_cap else []) + [bm.faces.new(R4)]   # the back sits on the cave wall
    allf = side + front + tun + caps
    bmesh.ops.recalc_face_normals(bm, faces=allf)
    mb._tag(side + front, mi_face)
    mb._tag(tun + caps, mi_in)
    return allf
