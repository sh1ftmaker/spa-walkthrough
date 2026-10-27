"""Geometry helpers for gen_boat: a lofted plank hull shell with real wall thickness.

hull_shell() builds one closed solid: per station (along Y) a U-shaped section running from the port
gunwale down the flared side, round the chine, across the flat bottom and up to the starboard gunwale,
then back along the inside (offset by the wall thickness). Strake seams are V-grooves made by three
outer points per seam (the middle one pushed in). The two end stations are capped (transom / stem face).
"""
import math

import bmesh
from mathutils import Vector


def section(hb, hg, zb, zg, t, n_side, seams, groove, flare_bulge=0.06, chine_r=0.06):
    """outer + inner (x, z) loop of one hull section. hb / hg = half width at the bottom / gunwale,
    zb / zg = bottom / gunwale height, t = wall thickness, n_side = points per side between chine and
    gunwale (excluding seams), seams = strake seam heights as fractions 0..1 of the side, groove = depth."""
    cr = min(chine_r, 0.45 * max(hb, 0.02), 0.45 * (zg - zb))

    def side_pt(s):                      # s = 0 at the chine top, 1 at the gunwale
        x = hb + (hg - hb) * s + flare_bulge * math.sin(math.pi * s) * (hg - hb) / max(hg, 1e-3)
        z = zb + cr + (zg - zb - cr) * s
        return x, z

    def side_normal(s, e=1e-3):
        x0, z0 = side_pt(max(0.0, s - e)); x1, z1 = side_pt(min(1.0, s + e))
        dx, dz = x1 - x0, z1 - z0
        L = math.hypot(dx, dz) or 1.0
        return dz / L, -dx / L           # outward normal of the port side mirrored to +x

    # outer, starboard half from gunwale (s=1) down to the bottom centre
    ss = set(i / n_side for i in range(n_side + 1))
    for f in seams:
        for d in (-0.02, 0.0, 0.02):
            ss.add(f + d)
    ss = sorted(ss, reverse=True)
    half = []
    for s in ss:
        x, z = side_pt(s)
        if any(abs(s - f) < 1e-6 for f in seams):
            nx, nz = side_normal(s)
            x -= nx * groove; z -= nz * groove
        half.append((x, z))
    # chine round + bottom
    half.append((hb - cr * 0.3, zb + cr * 0.3))
    half.append((max(hb - cr, hb * 0.5), zb))
    half.append((0.0, zb))
    outer = [(-x, z) for x, z in half[:-1]] + [(0.0, zb)] + [(x, z) for x, z in reversed(half[:-1])]
    # outer runs port gunwale -> bottom centre -> starboard gunwale.  Inner: fewer points, offset by t.
    xi_g = max(hg - t, 0.012)
    xi_b = max(hb - t - cr * 0.3, 0.008)
    zi_b = zb + t
    xm, zm = side_pt(0.5)
    inner_half = [(xi_g, zg), (max(xm - t, 0.01), zm), (max(hb - t, 0.01), zb + cr + t * 0.3), (xi_b, zi_b)]
    inner = [(x, z) for x, z in inner_half] + [(0.0, zi_b)] + [(-x, z) for x, z in reversed(inner_half)]
    # inner runs starboard gunwale -> port gunwale, so outer + inner is one closed loop
    return outer + inner


def hull_shell(mb, stations, mi_out, mi_in=None, mi_cap=None):
    """stations = [(y, loop)] with equal loop lengths; returns (faces, rings)."""
    bm = mb.bm
    rings = [[bm.verts.new((x, y, z)) for x, z in loop] for y, loop in stations]
    n = len(rings[0])
    faces = []
    n_out = None
    for A, B in zip(rings[:-1], rings[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    caps = [bm.faces.new(rings[0]), bm.faces.new(rings[-1][::-1])]
    faces += caps
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.material_index = mi_out
    if mi_in is not None:
        for f in faces:
            if f in caps:
                continue
            # inner faces point towards the hull centreline / upwards
            c = f.calc_center_median()
            if f.normal.z > 0.5 or (f.normal.x * c.x < -1e-4 and abs(f.normal.x) > 0.3):
                f.material_index = mi_in
    if mi_cap is not None:
        for f in caps:
            f.material_index = mi_cap
    return faces, rings


def catenary(p0, p1, sag, n):
    p0, p1 = Vector(p0), Vector(p1)
    return [p0.lerp(p1, i / (n - 1)) - Vector((0, 0, sag * math.sin(math.pi * i / (n - 1)))) for i in range(n)]
