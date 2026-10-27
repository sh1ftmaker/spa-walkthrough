"""Fumarole steam vent (fumarole_vent): a low cracked, ash-crusted rock mound with a dark vent mouth.

Targets (no scale sheet shows the vent; lookbook/img/16-steam-grotto.jpg shows steam rising from dark
cracked basalt at the pool edges and lookbook/img/07-restaurant-plan.jpg the steaming rock mounds in the
river; size from the asset row and proxy):
  * 1.6 x 1.6 x 0.6 m (row r 0.6-1.6 m, h 0.3-0.8 m; proxy 1.6 x 1.6 x 0.6): default R = 0.78, h 0.42-0.58.
  * profile: a broad low convex mound with a rounded toe, a raised rim at 0.18-0.30 R around a dark throat
    0.10-0.18 R wide that drops 0.25-0.35 m below the rim (the "dark vent mouth").
  * crust: pale ash-grey crust plates (30-45 mm thick) broken by 5-9 radial cracks and one concentric
    crack, the dark rock core showing in the 25-45 mm gaps; a pale yellow-white sinter deposit ring on
    the lip.
Construction: core = lathe of the profile (basalt_dry, cooled dark), with the throat in a darker
basalt_dry tint; crust = closed plates (top grid following the core + crust thickness with noise, side
walls, bottom sunk into the core) cut into sectors by the radial cracks and split by the concentric crack;
sinter = the core faces between the rim and the throat.
Materials: basalt_dry tint (0.55, 0.55, 0.6) core, (0.25, 0.25, 0.28) throat; ash_clay with the crust tint
(crust param); sinter tint (1.0, 0.92, 0.62) on the lip.

Parameters: r 0.6-0.8 (plan radius, default 0.78; the row's 1.6 m is the diameter); h 0.3-0.8 (default
seeded, clamped to the proxy); cracks 5-9 (default seeded); crust 'ash' | 'ochre' | 'white';
style 'cone' | 'fissure' | 'shield' (seed-cycled): cone = tall rim around a round throat; fissure =
oval mound with a slot-shaped vent (aspect 1.9); shield = broad low dome with a wide shallow mouth.
LODs (1500 / 600 / 180 / 40): same plates at LOD0-2 (fewer grid cells), LOD3 core only with the crust
material on its flanks (the dominant colour).
Animation: sim-driven steam: kz_fx 'fx_steam' with kz_vent (mouth centre, radius, aspect).
Lighting: lightmap.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'fumarole_vent'
FEATURES = ['low rock mound', 'ash crust plates with cracks', 'dark vent mouth', 'sinter lip']
STYLES = ['cone', 'fissure', 'shield']
CRUST = {'ash': (0.62, 0.62, 0.65), 'ochre': (0.9, 0.72, 0.5), 'white': (1.05, 1.04, 1.0)}


def _layout(seed, r, h, cracks, style):
    g = C.rng(seed, 'layout')
    p = genlib.proxy(ASSET)
    R = min(r, p['w'] / 2 * 0.98)
    if style == 'shield':
        H = h or g.uniform(0.32, 0.4)
        rim, throat, drop = g.uniform(0.26, 0.32), g.uniform(0.16, 0.2), g.uniform(0.15, 0.2)
    elif style == 'fissure':
        H = h or g.uniform(0.42, 0.5)
        rim, throat, drop = g.uniform(0.2, 0.25), g.uniform(0.12, 0.15), g.uniform(0.25, 0.32)
    else:
        H = h or g.uniform(0.5, 0.58)
        rim, throat, drop = g.uniform(0.17, 0.22), g.uniform(0.10, 0.13), g.uniform(0.28, 0.35)
    H = min(H, p['h'] * 1.02)
    aspect = 1.9 if style == 'fissure' else g.uniform(0.85, 1.0)      # vent aspect (x stretch)
    mound_y = 0.72 if style == 'fissure' else g.uniform(0.86, 1.0)    # mound depth / width
    gc = C.rng(seed, 'cracks')
    n = int(cracks or gc.randint(5, 9))
    a0 = gc.uniform(0, 2 * math.pi)
    cuts = sorted(a0 + 2 * math.pi * (i + gc.uniform(-0.3, 0.3)) / n for i in range(n))
    split = [gc.uniform(0.5, 0.68) if gc.random() < 0.75 else None for _ in range(n)]
    gaps = [gc.uniform(0.025, 0.045) for _ in range(n)]
    off = Vector((gc.uniform(0, 99), gc.uniform(0, 99), gc.uniform(0, 99)))
    return dict(R=R, H=H, rim=rim * R, throat=throat * R, drop=drop, aspect=aspect, my=mound_y, cuts=cuts,
                split=split, gaps=gaps, off=off, n=n)


def _core_z(L, rr):
    """core surface height at plan radius rr (outer flank, rr >= rim)"""
    R, H, rim = L['R'], L['H'], L['rim']
    if rr <= rim:
        return H
    s = (rr - rim) / (R - rim)
    return H * (1 - s ** 1.7) * (1 - 0.25 * s) * (1 - s) ** 0.35   # convex mound, rounded toe


def _xy(L, rr, a):
    return rr * math.cos(a) * (1.0 if L['aspect'] < 1.5 else 1.0), rr * math.sin(a) * L['my']


def build(lod, seed, r=0.78, h=None, cracks=None, crust=None, style=None):
    style = style or C.cycle(seed, STYLES)
    crust = crust or C.pick(seed, 'crust', list(CRUST))
    r = max(0.3, min(0.8, float(r)))
    L = _layout(seed, r, h, cracks, style)
    R, H, rim, th, drop = L['R'], L['H'], L['rim'], L['throat'], L['drop']
    mb = genlib.MeshBuilder()
    m_core = mb.slot('basalt_dry', tint=(0.55, 0.55, 0.6))
    m_throat = mb.slot('basalt_dry', tint=(0.22, 0.22, 0.25))
    m_crust = mb.slot('ash_clay', tint=CRUST[crust])
    m_sinter = mb.slot('sinter', tint=(1.0, 0.92, 0.62), wetness=0.6)
    bm = mb.bm
    # ---- core: polar lathe, elliptical plan; vent aspect squeezes the throat in y
    segs = C.lod_pick(lod, 24, 12, 8, 6)
    va = L['aspect']
    prof = [(R, 0.0, m_core)]
    nfl = C.lod_pick(lod, 4, 2, 1, 0)
    for k in range(1, nfl + 1):
        rr = R - (R - rim * 1.15) * k / nfl
        prof.append((rr, _core_z(L, rr), m_crust if lod == 3 else m_core))
    prof += [(rim, H, m_crust if lod == 3 else m_sinter)]
    if lod < 3:
        prof += [(rim * 0.82, H - 0.02, m_sinter)]
    if lod < 2:
        prof += [((rim * 0.82 + th) / 2, H - drop * 0.35, m_sinter)]
    prof += [(th, H - drop * 0.6, m_throat)]
    if lod < 3:
        prof += [(th * 0.7, H - drop, m_throat)]
    rings = []
    for rr, z, _m in prof:
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            inner = rr <= rim
            sx = (va if inner else 1.0) * (1.0 if not inner else 1.0)
            sy = L['my'] / (va if inner and va > 1.5 else 1.0) if True else 1.0
            nz = 0.0
            if 0 < z and rr > rim * 1.05 and lod < 2:
                nz = 0.025 * noise.noise(Vector((math.cos(a) * rr * 4, math.sin(a) * rr * 4, 0)) + L['off'])
            ring.append(bm.verts.new((rr * math.cos(a) * sx, rr * math.sin(a) * sy, max(0.0, z + nz) if rr < R else 0.0)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            f.material_index = prof[i + 1][2] if prof[i + 1][2] != m_crust else m_crust
            if prof[i][0] > rim and prof[i + 1][0] >= rim:
                f.material_index = prof[i + 1][2] if lod == 3 else m_core
            if prof[i + 1][0] <= rim:
                f.material_index = prof[i + 1][2]
    ctr = bm.verts.new((0, 0, H - drop - 0.01))
    for k in range(segs):
        f = bm.faces.new((rings[-1][k], rings[-1][(k + 1) % segs], ctr)); f.material_index = m_throat
    # ---- crust plates (LOD0-2)
    if lod < 3:
        na_per = C.lod_pick(lod, 4, 2, 1)
        nr = C.lod_pick(lod, 3, 1, 1)
        T = 0.038
        n = L['n']
        r_in, r_out = rim * 1.22, R * 0.96
        for i in range(n):
            a0, a1 = L['cuts'][i], L['cuts'][(i + 1) % n] + (2 * math.pi if i == n - 1 else 0)
            bands = [(r_in, r_out)]
            if L['split'][i] is not None:
                rs = r_in + (r_out - r_in) * L['split'][i]
                bands = [(r_in, rs - 0.018), (rs + 0.018, r_out)]
            for (q0, q1) in bands:
                na = max(1, int(round(na_per * (a1 - a0) / (2 * math.pi / n))))
                grid_top, grid_bot = [], []
                for jr in range(nr + 1):
                    rr = q0 + (q1 - q0) * jr / nr
                    ga = L['gaps'][i] / 2 / rr
                    rowt, rowb = [], []
                    for ja in range(na + 1):
                        a = a0 + ga + (a1 - a0 - 2 * ga) * ja / na
                        x, y = rr * math.cos(a), rr * math.sin(a) * L['my']
                        edge = jr in (0, nr) or ja in (0, na)
                        zc = _core_z(L, rr)
                        t = (T if lod < 2 else 0.022) * (0.6 if edge and lod < 2 else 1.0) + (0.022 * noise.noise(Vector((x * 9, y * 9, 1)) + L['off']) if lod == 0 else 0)
                        rowt.append(bm.verts.new((x, y, zc + t)))
                        rowb.append(bm.verts.new((x, y, max(0.0, zc - 0.03))) if lod < 2 else None)
                    grid_top.append(rowt); grid_bot.append(rowb)
                fs = []
                for jr in range(nr):
                    for ja in range(na):
                        fs.append(bm.faces.new((grid_top[jr][ja], grid_top[jr][ja + 1], grid_top[jr + 1][ja + 1], grid_top[jr + 1][ja])))
                loop = [(0, ja) for ja in range(na)] + [(jr, na) for jr in range(nr)] + \
                       [(nr, ja) for ja in range(na, 0, -1)] + [(jr, 0) for jr in range(nr, 0, -1)]
                for k in range(len(loop) if lod < 2 else 0):
                    (r1, c1), (r2, c2) = loop[k], loop[(k + 1) % len(loop)]
                    fs.append(bm.faces.new((grid_top[r1][c1], grid_bot[r1][c1], grid_bot[r2][c2], grid_top[r2][c2])))
                for f in fs:
                    f.material_index = m_crust
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_fx='fx_steam',
                     kz_vent=dict(pos=[round(dx, 3), round(dy, 3), round(H - drop * 0.5 + dz, 3)], r=round(th, 3), aspect=round(va, 2)),
                     kz_params=dict(style=style, r=round(R, 3), h=round(H, 3), cracks=L['n'], crust=crust))
    return o
