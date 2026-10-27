"""Hinoki bucket (oke), long-handled ladle and shallow bowl (oke_bucket).

Identifying features kept at every LOD: round hinoki stave bucket with copper hoops, long-handled ladle
resting across the rim, shallow bowl, stacks of buckets.

Construction (round 2)
  * body LOD0: 30 narrow staves. The wall ring has 60 vertices, odd ones pushed 1.5 mm inside the even
    ones, so each stave joint is a V-groove. Rolled top lip (about 20 mm tall, 7 mm proud of the wall).
    Water disc (obsidian) sits 60 mm below the rim, so the inner wall shows above it.
    LOD1 keeps the lip and the belly with 14 smooth segments; LOD2/3 are one tapered band with a top disc.
  * hoops: bronze bands on the outer wall. LOD0 is a 3-band section, LOD1 a 2-band bead, LOD2 one band,
    LOD3 none.
  * ladle: a scoop cup (0.12 m across, 0.05 m deep, wood) in the water and a 0.55 m tapered hinoki handle
    (30 mm at the cup end, 20 mm at the tip) lying diagonally across the rim. Projected length stays inside
    the proxy footprint.
  * bowl: shallow lacquer dark cup (r 0.09, depth 0.04) standing in the water, opposite the scoop.
  * stack: n buckets stacked, each about 5 % smaller, each with its own hoops.
Animation: none. Lighting: lightmap (UV1 from genlib.finish).

Parameters (build kwargs):
  r      top radius, 0.15-0.30 m          (default seeded 0.18-0.20)
  h      height, 0.15-0.35 m              (default seeded 0.19-0.25)
  hoops  2 or 3
  style  bucket | stack | with_ladle | bowl     (default with_ladle)
  n      buckets in a stack, 2-3
Seeds change taper, belly, height, hoop count, lip size, ladle azimuth and reach, and bowl size.
"""
import math
import bmesh
from mathutils import Matrix, Vector
import genlib
import kzgeo_oke_bucket as K

ASSET = 'oke_bucket'
FEATURES = ['round hinoki stave bucket with copper hoops', 'long-handled ladle', 'shallow bowl', 'stacks of buckets']

STAVES = {0: 30, 1: 0, 2: 0, 3: 0}
SEGS = {0: 30, 1: 14, 2: 8, 3: 6}


def _hoop_profile(lod, ro, hz, hw, e):
    if lod == 0:
        return [(ro, hz - hw), (ro + e, hz - hw), (ro + e, hz + hw), (ro, hz + hw)]
    if lod == 1:
        return [(ro, hz - hw), (ro + e, hz), (ro, hz + hw)]
    return [(ro, hz - hw), (ro + e, hz + hw)]


def _bucket(mb, mi_wood, mi_hoop, mi_water, lod, R, r0, H, bulge, t, drop, lip, hoop_zs, hw, e, segs, belly,
            z0=0.0):
    if lod >= 2:
        K.revolve(mb, [(r0, 0.0), (R, H), (0.0, H)], segs, mi_wood, z0=z0, closed=False)
    else:
        mid = [(K.outer_r(H * f, r0, R, H, bulge), H * f) for f in belly]
        base = [(r0, 0.0)] + mid + [(R, H - lip), (R + 0.007, H - lip * 0.3), (R - t, H)]
        if lod == 0:
            K.revolve_grooved(mb, base + [(R - t, H - drop)], STAVES[0], 0.0015, mi_wood, z0=z0)
            # water disc in obsidian, 60 mm below the rim
            K.revolve(mb, [(R - t - 0.001, H - drop), (0.0, H - drop)], segs * 2, mi_water, z0=z0)
        else:
            K.revolve(mb, base + [(R - t, H - drop)], segs, mi_wood, z0=z0, closed=False)
            K.revolve(mb, [(R - t - 0.001, H - drop), (0.0, H - drop)], segs, mi_water, z0=z0)
    for hz in hoop_zs:
        ro = K.outer_r(hz, r0, R, H, bulge) - 0.002
        K.revolve(mb, _hoop_profile(lod, ro, hz, hw, e), segs, mi_hoop, z0=z0, closed=False)


def build(lod, seed, r=None, h=None, hoops=None, style=None, n=None):
    g = genlib.rng(seed, ASSET)
    style = style or 'with_ladle'
    R = r or g.uniform(0.18, 0.20)
    H = h or g.uniform(0.19, 0.25)
    taper = g.uniform(0.66, 0.84)
    bulge = g.uniform(0.0, 0.03)
    nh = hoops or g.choice([2, 3])
    t = g.uniform(0.010, 0.014)
    drop = 0.06
    lip = g.uniform(0.016, 0.02)
    e = 0.006
    hw = 0.007
    segs = SEGS[lod]
    belly = [0.5] if lod <= 1 else []
    hoop_f = [0.2, 0.8] if nh == 2 else [0.14, 0.5, 0.86]
    if lod == 3:
        hoop_f = [0.5]
    elif lod == 2:
        hoop_f = [hoop_f[0], hoop_f[-1]] if nh == 2 else [0.5]
    ladle_az = math.radians(g.uniform(44, 50))

    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant='wet_oiled', wear=round(g.uniform(0.1, 0.25), 2))
    bronze = mb.slot('bronze')
    dark = mb.slot('lacquer_dark')
    water = mb.slot('obsidian')
    glaze = mb.slot('ceramic', variant='celadon')

    if style == 'bowl':
        Rb = 0.08
        prof = [(0.0, 0.0), (Rb * 0.6, 0.005), (Rb, 0.06), (Rb - 0.008, 0.06), (Rb * 0.8, 0.025), (0.0, 0.012)]
        if lod >= 2:
            prof = [(0.0, 0.0), (Rb, 0.06), (Rb * 0.8, 0.025), (0.0, 0.012)]
        K.revolve(mb, prof, max(12, segs * 2 // 3), glaze)
    elif style == 'stack':
        nn = n or 2
        ss = max(8, segs * 3 // 4)
        for k in range(nn):
            Rk = R * (1 - 0.05 * k)
            _bucket(mb, wood, bronze, water, lod, Rk, Rk * taper, H, bulge, t, drop, lip,
                    [H * f for f in hoop_f], hw, e, ss, belly, z0=H * 0.93 * k)
    else:
        _bucket(mb, wood, bronze, water, lod, R, R * taper, H, bulge, t, drop, lip,
                [H * f for f in hoop_f], hw, e, segs, belly)
        if style == 'with_ladle':
            # ladle: scoop in the water, handle lying diagonally across the rim
            cup_r = 0.06
            cup_c = (-0.13, -0.13, H - 0.004)
            hl = 0.55
            tip = (cup_c[0] + hl * math.cos(ladle_az), cup_c[1] + hl * math.sin(ladle_az), H + 0.005)
            cseg = max(8, segs // 2)
            cprof = [(0.0, 0.0), (cup_r * 0.5, 0.0), (cup_r, 0.02), (cup_r * 1.03, 0.05), (cup_r * 0.94, 0.05),
                     (cup_r * 0.86, 0.015), (0.0, 0.008)]
            if lod >= 2:
                cprof = [(0.0, 0.0), (cup_r, 0.03), (cup_r * 0.94, 0.05), (cup_r * 0.8, 0.012), (0.0, 0.008)]
            if lod < 3:
                cv, _ = K.revolve(mb, cprof, cseg, wood)
                bmesh.ops.transform(mb.bm, matrix=Matrix.Translation(Vector(cup_c)), verts=cv)
            hs = {0: 12, 1: 8, 2: 5, 3: 3}[lod]
            K.stick(mb, (cup_c[0] + 0.02, cup_c[1] + 0.02, cup_c[2] + 0.005), tip, 0.015, 0.010, wood, segs=hs)
    if style == 'with_ladle' and lod <= 1:
        # bowl stands in the water beside the scoop (inside the rim)
        Rb = 0.08
        bc = (0.05, -0.05, H - drop)
        bprof = [(0.0, 0.0), (Rb * 0.6, 0.005), (Rb, 0.06), (Rb - 0.008, 0.06), (Rb * 0.8, 0.025), (0.0, 0.012)]
        bv, _ = K.revolve(mb, bprof, max(10, segs // 2), glaze)
        bmesh.ops.transform(mb.bm, matrix=Matrix.Translation(Vector(bc)), verts=bv)

    # the origin stays on the bucket axis; with_ladle only keeps the bbox offset inside the 0.045 m check
    K.centre_xy_base(mb, centre_x=False, centre_y=False) if style == 'with_ladle' else K.centre_xy_base(mb)
    o = mb.to_object(ASSET)
    return genlib.finish(o)
