"""kzgeo_bridge_slab: the basalt slab deck of gen_bridge_slab.

The deck is a row of thick basalt flags laid end to end along X (the span), each a bevelled box across the
full deck width (Y). Joints between flags are 20 mm. The walking surface (top faces) is paving, the flag
sides and soffit basalt_dry. LOD0 rounds the flag edges (2 segments) and roughens the top with a few mm
of noise; LOD1 chamfers; LOD2 and LOD3 use plain boxes.
Parapets are not in this file: gen_bridge_slab calls kzgeo_parapet_stone.wall() on both deck edges.
"""
import bmesh
from mathutils import Vector, noise

import kzgeo_common as C

JOINT = 0.02          # mortar/joint gap between flags, m


def flags(mb, span, w, T, lod, r, mi_dry, mi_top, n, z0=0.0):
    """Lay n flags from x = -span/2 to span/2 across the full width w. Returns all faces."""
    faces = []
    cuts = [-span / 2.0]
    # uneven flag lengths: each flag takes a seeded share of the span, with a 0.6 m minimum
    shares = [r.uniform(0.7, 1.3) for _ in range(n)]
    tot = sum(shares)
    for sh in shares[:-1]:
        cuts.append(cuts[-1] + span * sh / tot)
    cuts.append(span / 2.0)
    bev, segs = {0: (0.022, 2), 1: (0.012, 1)}.get(lod, (0.0, 1))
    for i in range(n):
        x0, x1 = cuts[i], cuts[i + 1]
        if i > 0:
            x0 += JOINT / 2
        if i < n - 1:
            x1 -= JOINT / 2
        size = (x1 - x0, w, T)
        centre = ((x0 + x1) / 2, 0.0, z0 + T / 2)
        fs = C.board(mb, centre, size, mi_dry, bevel=bev, segs=segs)
        # top faces are the walking surface: paving
        for f in fs:
            f.normal_update()
            if f.normal.z > 0.9:
                f.material_index = mi_top
        if lod == 0:                              # roughen the top a few mm
            tops = {v for f in fs for v in f.verts if v.co.z > z0 + T - 1e-4}
            off = Vector((r.uniform(0, 60), r.uniform(0, 60), r.uniform(0, 60)))
            for v in tops:
                v.co.z += 0.004 * noise.noise(v.co * 3.0 + off)
        faces += fs
    return faces


def sill_layout(span, w, h, L, r):
    """Bank-seat sills: one per end, (x0, x1) along the span, full deck width + a seeded 0-0.05 m
    shoulder each side (kept small: proxy d). Rough corner jitter drawn here (same at every LOD)."""
    out = []
    for side in (-1.0, 1.0):
        xo = side * span / 2
        xi = side * (span / 2 - L)
        sh = r.uniform(0.0, 0.05)
        jit = [(r.uniform(-0.03, 0.03), r.uniform(-0.03, 0.03), r.uniform(-0.02, 0.0)) for _ in range(16)]
        out.append(dict(x0=min(xo, xi), x1=max(xo, xi), hw=w / 2 + sh, h=h, jit=jit))
    return out


def sills(mb, layout, lod, mi):
    """Closed convex blocks. LOD0/1: 16-point hull (rough planar facets, top kept flat for the bearing);
    LOD2/3: plain 8-corner block."""
    import kzgeo_parapet_stone as P
    faces = []
    for s in layout:
        x0, x1, hw, h = s['x0'], s['x1'], s['hw'], s['h']
        if lod >= 2:
            pts = [Vector((x, y, z)) for x in (x0, x1) for y in (-hw, hw) for z in (0.0, h)]
        else:
            pts = []
            k = 0
            for x in (x0, x1):
                for y in (-hw, hw):
                    for z in (0.0, h):
                        jx, jy, jz = s['jit'][k]; k += 1
                        pts.append(Vector((x + (jx if lod == 0 else 0), y + (jy if lod == 0 else 0), z if z == 0.0 else h)))
                    # mid-height bulge on the outer faces (rough split stone)
                    jx, jy, jz = s['jit'][k]; k += 1
                    pts.append(Vector((x + 0.02 * (1 if x > (x0 + x1) / 2 else -1) + jx * 0.5,
                                       y + 0.025 * (1 if y > 0 else -1), h * 0.5 + jz * 2)))
            # chamfer on the top edges, 2 cm
            pts += [Vector((x0 + 0.02, y, h + 0.0)) for y in (-hw + 0.02, hw - 0.02)]
        faces += P.hull(mb, pts, mi)
    return faces
