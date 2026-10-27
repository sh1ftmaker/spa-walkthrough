"""kzgeo_stalactite_cluster: tapered spike helper shared by stalactite_cluster, icicle_cluster and
ice_formation (op08).

spike() builds one closed tapering spike (stalactite, icicle, fluted ice column) as stacked rings along
an axis, ending in an apex vertex (a real point, the concept spikes are pointed) and a capped root ring.
Every random value is passed in by the caller (drawn once per seed before any LOD branch); the LOD only
chooses `sides` and the station list, so all LODs of one seed share the same envelope.

    faces = spike(mb, root=(x, y, z), axis=(0, 0, -1), L=2.4, r0=0.22, sides=7,
                  stations=[0, .15, .3, .5, .62, .8, .92], mi=lambda t: rock if t < .62 else amber,
                  taper=1.35, flare=1.6, facets=[...per angle...], ripple=(0.10, 3.0, 0.2), bend=(0.05, 0))

Cost: sides * (2 * (len(stations) - 1) + 1) + (sides - 2) triangles (cost()).
"""
import math

from mathutils import Vector


def basis(axis):
    a = Vector(axis).normalized()
    ref = Vector((1, 0, 0)) if abs(a.x) < 0.9 else Vector((0, 1, 0))
    u = a.cross(ref).normalized()
    v = a.cross(u).normalized()
    return a, u, v


def cost(sides, n_stations, cap=True):
    return sides * (2 * (n_stations - 1) + 1) + ((sides - 2) if cap else 0)


def radius_at(t, r0, taper=1.4, flare=1.0, flare_len=0.12, ripple=(0.0, 0.0, 0.0), tip_r=0.0):
    """radius profile: power taper to the apex, a root flare that blends into the plate, ripples (drip
    ridges) of relative amplitude ripple[0], ripple[1] per length, phase ripple[2]. Never zero before t=1."""
    base = r0 * max(0.0, 1.0 - t) ** taper
    fl = 1.0 + (flare - 1.0) * math.exp(-t / max(1e-3, flare_len))
    rp = 1.0 + ripple[0] * math.sin(2 * math.pi * (t * ripple[1] + ripple[2])) * (1.0 - t)
    return max(tip_r, base * fl * rp)


def spike(mb, root, axis, L, r0, sides, stations, mi, taper=1.4, flare=1.0, flare_len=0.12, ripple=(0, 0, 0),
          bend=(0.0, 0.0), facets=None, twist=0.0, ell=1.0, phase=0.0, tip_r=0.0, cap_root=True, apex=True):
    """Closed tapering spike. stations: increasing t values in [0, 1) (0 = root); the apex sits at t = 1.
    mi: slot index or callable t_mid -> slot index (per ring segment; the apex fan uses t = 1).
    facets: per-angle radial factors (len == sides) or a callable(theta) -> factor, applied to every ring
    (vertical facets / flutes). bend: tip offset in the (u, v) plane as a fraction of L (quadratic)."""
    bm = mb.bm
    a, u, v = basis(axis)
    root = Vector(root)
    rings = []

    def centre(t):
        return root + a * (L * t) + (u * bend[0] + v * bend[1]) * (L * t * t)

    def fac(k, th):
        if facets is None:
            return 1.0
        if callable(facets):
            return facets(th)
        return facets[k % len(facets)]

    for t in stations:
        c = centre(t)
        r = radius_at(t, r0, taper, flare, flare_len, ripple, tip_r)
        ring = []
        for k in range(sides):
            th = phase + 2 * math.pi * k / sides + twist * t
            f = fac(k, th)
            ring.append(bm.verts.new(c + (u * math.cos(th) * ell + v * math.sin(th)) * r * f))
        rings.append(ring)
    faces = []
    mif = mi if callable(mi) else (lambda t: mi)
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        m = mif(0.5 * (stations[i] + stations[i + 1]))
        for k in range(sides):
            k2 = (k + 1) % sides
            f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = m
            faces.append(f)
    last = rings[-1]
    if apex:
        tip = bm.verts.new(centre(1.0))
        m = mif(1.0)
        for k in range(sides):
            f = bm.faces.new((last[k], last[(k + 1) % sides], tip))
            f.material_index = m
            faces.append(f)
    else:
        f = bm.faces.new(last)
        f.material_index = mif(1.0)
        faces.append(f)
    if cap_root:
        f = bm.faces.new(rings[0][::-1])
        f.material_index = mif(0.0)
        faces.append(f)
    return faces


def stations_for(n, split=None, bias=1.0):
    """n stations in [0, 1) (root at 0), spaced by t = (i / n) ** bias, with `split` inserted (material
    boundary kept at the same t at every LOD)."""
    st = [(i / n) ** bias for i in range(n)]
    if split is not None and 0 < split < 1:
        st = [t for t in st if abs(t - split) > 0.5 / n] + [split]
        st.sort()
    return st


def facet_factors(g, sides, lo=0.82, hi=1.12):
    """per-angle radial factors (planar-ish vertical facets for rock spikes)"""
    return [g.uniform(lo, hi) for _ in range(sides)]


def flute_fn(n_flutes, depth, phase=0.0):
    """callable(theta) for fluted ice columns: n_flutes rounded grooves of relative depth"""
    def f(th):
        return 1.0 - depth * (0.5 + 0.5 * math.cos(n_flutes * (th - phase)))
    return f
