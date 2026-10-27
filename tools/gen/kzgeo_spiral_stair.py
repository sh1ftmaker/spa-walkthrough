"""Geometry helpers for gen_spiral_stair (polar / helical construction). Bearings follow kzgeo_lift_drum:
radians clockwise from +Y seen from above (x = r sin b, y = r cos b)."""
import math

import bmesh
from mathutils import Vector, noise

import kzgeo_lift_drum as G

polar = G.polar


def hsweep(bm, samples, section, mis, caps=True, disp=None):
    """Sweep a closed section [(dr, dz)] round the axis. samples = [(bearing, rc, zc)];
    section may be a function j -> section. mis: int or list per section edge. disp(v, j, k) -> Vector."""
    rings = []
    for j, (b, rc, zc) in enumerate(samples):
        sec = section(j) if callable(section) else section
        ring = []
        for k, (dr, dz) in enumerate(sec):
            v = polar(rc + dr, b, zc + dz)
            if disp is not None:
                v = disp(v, j, k)
            ring.append(bm.verts.new(v))
        rings.append(ring)
    faces = []
    n = len(rings[0])
    for j in range(len(rings) - 1):
        A, B = rings[j], rings[j + 1]
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = mis[k] if isinstance(mis, (list, tuple)) else mis
            faces.append(f)
    if caps:
        for R in (rings[0], rings[-1]):
            try:
                f = bm.faces.new(R)
                f.material_index = mis[0] if isinstance(mis, (list, tuple)) else mis
                faces.append(f)
            except ValueError:
                pass
    return faces


def polar_block(bm, r0, r1, bears, ztop, zbot, mi, mi_top=None):
    """closed solid between radii r0..r1 over the bearing list; ztop(b), zbot(b) heights (functions or floats)"""
    zt = ztop if callable(ztop) else (lambda b: ztop)
    zb = zbot if callable(zbot) else (lambda b: zbot)
    rings = []
    for b in bears:
        rings.append([bm.verts.new(polar(r0, b, zb(b))), bm.verts.new(polar(r1, b, zb(b))),
                      bm.verts.new(polar(r1, b, zt(b))), bm.verts.new(polar(r0, b, zt(b)))])
    faces = []
    for j in range(len(rings) - 1):
        A, B = rings[j], rings[j + 1]
        for k in range(4):
            k2 = (k + 1) % 4
            f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = (mi_top if (mi_top is not None and k == 2) else mi)
            faces.append(f)
    for R in (rings[0], rings[-1]):
        f = bm.faces.new(R); f.material_index = mi; faces.append(f)
    return faces


def tread_block(bm, r0, r1, b0, b1, hand, z, zb0, zb1, mi, ov=0.0, lip=0.0, ch=0.0, jit=None):
    """One carved tread: closed solid between radii r0, r1; riser at bearing b0, back at b1 (b1 = b0 + hand*dth).
    Nosing overhang `ov` (m), lip depth `lip`, top chamfer `ch`; the underside runs from zb0 (front) to zb1 (back)
    on the pitch line. jit = {'r0': (dz_front, dz_back), 'r1': (...)} warps the top (worn / tilted slabs)."""
    out = []
    for r, key in ((r0, 'r0'), (r1, 'r1')):
        f, bk = (jit or {}).get(key, (0.0, 0.0))
        o = lambda m: b0 - hand * m / r            # bearing `m` metres in front of the riser
        pts = [(b0, zb0)]
        if ov > 0:
            pts += [(b0, z - lip), (o(ov), z - lip + 0.012)]
            if ch:     # rounded nosing: two facets
                pts += [(o(ov), z - ch + f), (o(ov - ch * 0.3), z - ch * 0.3 + f), (o(ov - ch), z + f)]
            else:
                pts += [(o(ov), z + f)]
        else:
            pts += [(b0, z - ch + f), (o(-ch), z + f)] if ch else [(b0, z + f)]
        pts += [(b1, z + bk), (b1, zb1)]
        out.append([bm.verts.new(polar(r, bb, zz)) for bb, zz in pts])
    A, B = out
    n = len(A)
    faces = [bm.faces.new(A[::-1]), bm.faces.new(B)]
    for k in range(n):
        k2 = (k + 1) % n
        faces.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    for fc in faces:
        fc.material_index = mi
    return faces


def rock_disp(amp, freq, seed, keep=()):
    off = Vector((seed * 13.17 % 97, seed * 7.31 % 89, seed * 3.77 % 83))

    def d(v, j, k):
        if k in keep:
            return v
        n1 = noise.noise(v * freq + off)
        n2 = noise.noise(v * freq * 2.7 + off * 1.3) * 0.45
        rad = Vector((v.x, v.y, 0))
        if rad.length > 1e-6:
            rad.normalize()
        # carved look: quantise the low-frequency term a little so faces come out faceted
        q = round(n1 * 3.0) / 3.0 * 0.5 + n1 * 0.5
        return v + rad * amp * (q + n2) + Vector((0, 0, amp * 0.6 * noise.noise(v * freq * 1.6 + off * 0.7)))
    return d


def uv_slabs(obj, slots, seed):
    """offset UV0 per connected stone (tread / slab) so neighbouring stones don't share one continuous texture"""
    import bmesh, random
    rnd = random.Random(seed)
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap')
    slots = set(slots)
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen or f0.material_index not in slots:
            continue
        isl, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen and g.material_index in slots:
                        seen.add(g.index); stack.append(g)
        du, dv = rnd.uniform(0, 7.0), rnd.uniform(0, 7.0)
        for f in isl:
            for l in f.loops:
                a = l[uv].uv
                l[uv].uv = (a.x + du, a.y + dv)
    bm.to_mesh(me); bm.free()
