"""Icicle cluster (icicle_cluster): long clear tapering icicles hanging in a curtain from a frozen ice lip.
Edge-snapped (the row says 'ground'; see report): the lip top is the attach line (z = h), the longest tip
is z = 0, the curtain faces +Y.

Targets (lookbook/img/17-glacier-plunge.jpg, top-left curtain and centre-top fringe; refs/gen/mat-glacier-ice.png
centre; no scale sheet exists, scale from the bather in 17 (~1.65 m) and the asset row):
  * row dims 0.8 x 0.5 x 0.8 m; lip 0.10-0.16 m thick, 0.25-0.4 m deep, the width of the curtain.
  * icicles: clear pale blue, slender (root 0.025-0.06 m radius, length:root-diameter 8-20), needle tips,
    in curtains with mixed lengths: a few long ones (0.6-0.7 m) among many 0.1-0.4 m; roots fuse into the
    lip with a flare; faint ring ridges (growth rings) along the length; some lean a few degrees.
  * two rows (front denser), drips at the tips (fx_drips, runtime).
Construction: lip = convex hull of a rounded bar of seeded points (crystalline facets), glacier_ice; each
icicle = kzgeo_stalactite_cluster.spike, 10-12 sides at LOD0 with ripples (growth rings) and a root flare,
smoothed shading (finish at 65 deg) so they read as smooth clear ice, not faceted rock.
Materials: glacier_ice only: lip (clarity-driven roughness, slightly whiter tint), icicles (clearer:
roughness_offset -0.1 to -0.25 with clarity, emissive_level 0.7-1.0).

Parameters: w 0.5-2 m (default 0.8); length (longest icicle) 0.3-4 m (default 0.66, clamped to the proxy
h); count 5-40 (default by style); taper 1.0-2.0; clarity 0-1 (default 0.7).
Styles (seed-cycled, 4 variants): 'curtain' (dense even curtain, random lengths), 'fringe' (short even
fringe with 3-4 long ones), 'columnar' (few thick long fused icicles), 'stepped' (lengths grow towards one
end, a V-shaped hem). Seeds change style, count, lengths, lean, lip shape.

LODs (budget 2000 / 800 / 240 / 50): same icicles in the same places.
  Resolution comes from LADDER by arithmetic (fallback on sides / rings, never on count; printed):
  LOD0 up to 12/10 sides x 8/5 rings (dense styles step down to 8/7 x 6/4); LOD1 6/5 sides x 3-4 rings;
  LOD2 4/3 sides x 1-2 rings, every icicle kept; LOD3 lip as a box hull + the 9 longest icicles as cones.
Animation: sim-driven drips: kz_fx = fx_drips with kz_drip_points (tip positions + rate weight).
Lighting: lightmap + emissive (glacier_ice emission). kz_snap 'edge', kz_attach_z.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R
import kzgeo_stalactite_cluster as S

ASSET = 'icicle_cluster'
FEATURES = ['frozen lip', 'curtain of long tapering clear icicles', 'needle tips']
STYLES = ['curtain', 'fringe', 'columnar', 'stepped']
COUNT = {'curtain': 22, 'fringe': 26, 'columnar': 9, 'stepped': 16}
BUDGET = [2000, 800, 240, 50]
# per LOD: (sides long, sides short, rings long, rings short), richest first
LADDER = [[(12, 10, 8, 5), (10, 8, 7, 4), (8, 7, 6, 4), (7, 6, 5, 3), (6, 5, 4, 3), (5, 4, 3, 2)],
          [(6, 6, 4, 3), (6, 5, 3, 2), (5, 4, 3, 2), (4, 4, 2, 2), (4, 3, 2, 1)],
          [(4, 4, 2, 2), (4, 3, 2, 1), (4, 3, 1, 1), (3, 3, 1, 1)],
          [(3, 3, 1, 1)]]


def _layout(seed, w, length, count, taper, style):
    g = C.rng(seed, 'layout')
    p = genlib.proxy(ASSET)
    lip_t = g.uniform(0.10, 0.15)
    lip_d = min(p['d'] * 0.95, g.uniform(0.28, 0.42))
    Lmax = min(length or g.uniform(0.6, 0.66), p['h'] * 1.03 - lip_t)
    n = max(5, min(40, int(count or COUNT[style] + g.randint(-2, 2))))
    tap = taper or g.uniform(1.15, 1.5)
    side = g.choice([-1, 1])
    ic = []
    for i in range(n):
        s = C.rng(seed, f'icicle{i}')
        u = (i + 0.5) / n * 2 - 1 + s.uniform(-0.4, 0.4) / n
        x = u * (w / 2 - 0.06)
        row = 0 if (i % 3) else 1                     # every third icicle in the back row
        y = (0.06 if row == 0 else -0.05) * lip_d / 0.35 + s.uniform(-0.03, 0.03)
        if style == 'curtain':
            L = Lmax * s.uniform(0.25, 1.0) ** 1.3
        elif style == 'fringe':
            L = Lmax * (s.uniform(0.75, 1.0) if i % max(1, n // 4) == n // 8 else s.uniform(0.12, 0.3))
        elif style == 'columnar':
            L = Lmax * s.uniform(0.55, 1.0)
        else:
            L = Lmax * (0.18 + 0.82 * ((u * side + 1) / 2) ** 1.4) * s.uniform(0.75, 1.0)
        r0 = (0.016 + 0.05 * L) * s.uniform(0.8, 1.2) * (1.7 if style == 'columnar' else 1.0)
        ic.append(dict(x=x, y=y, L=max(0.06, L), r0=r0, taper=tap * s.uniform(0.9, 1.1),
                       ripple=(s.uniform(0.06, 0.12), s.uniform(4, 8), s.uniform(0, 1)),
                       bend=(s.uniform(-0.03, 0.03), s.uniform(-0.05, 0.02)), phase=s.uniform(0, 6.3),
                       flare=s.uniform(1.3, 1.8), ell=s.uniform(0.85, 1.0)))
    ic[max(range(n), key=lambda i: ic[i]['L'])]['L'] = Lmax       # one icicle always reaches Lmax
    gl = C.rng(seed, 'lip')
    pts = [Vector((sx * w / 2, 0.0, 0.0)) for sx in (-1, 1)]
    for _ in range(38):
        xx = gl.uniform(-1, 1)
        a = gl.uniform(0, 2 * math.pi)
        k = (1 - xx ** 4) ** 0.25 * gl.uniform(0.85, 1.0)
        pts.append(Vector((xx * w / 2, math.cos(a) * lip_d / 2 * k, math.sin(a) * lip_t / 2 * k)))
    return dict(lip_t=lip_t, lip_d=lip_d, Lmax=Lmax, icicles=ic, lip_pts=pts, taper=tap)


def build(lod, seed, w=0.8, length=None, count=None, taper=None, clarity=0.7, style=None):
    style = style or C.cycle(seed, STYLES)
    w = max(0.5, min(2.0, float(w)))
    clarity = max(0.0, min(1.0, float(clarity)))
    L = _layout(seed, w, length, count, taper, style)
    H = L['lip_t'] + L['Lmax']
    zc = H - L['lip_t'] / 2
    mb = genlib.MeshBuilder()
    m_lip = mb.slot('glacier_ice', tint=(0.9, 0.95, 1.0), roughness_offset=round(0.1 - 0.15 * clarity, 3))
    m_ice = mb.slot('glacier_ice', roughness_offset=round(-0.25 * clarity, 3), emissive_level=round(0.7 + 0.3 * clarity, 3))
    n_pts = C.lod_pick(lod, 40, 26, 14, 8)
    pts = [Vector((p.x, p.y, zc + p.z)) for p in L['lip_pts'][:n_pts]]
    if lod == 3:
        pts = [Vector((sx * w / 2, sy * L['lip_d'] / 2, zc + sz * L['lip_t'] / 2)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    R.basalt_hull(mb, pts, m_lip, m_lip)
    order = sorted(range(len(L['icicles'])), key=lambda i: -L['icicles'][i]['L'])
    keep = set(order)
    if lod == 3:
        keep = set(order[:max(1, (BUDGET[3] - 12) // S.cost(3, 1))])
    # resolution by arithmetic (fall back on sides / rings, never on icicle count; printed)
    big_of = {i: L['icicles'][i]['L'] > 0.5 * L['Lmax'] for i in keep}
    lip_cost = 2 * n_pts
    ladder = LADDER[lod]
    for step, (sb, ss, nb, ns) in enumerate(ladder):
        tot = lip_cost + sum(S.cost(sb if big_of[i] else ss, nb if big_of[i] else ns) for i in keep)
        if tot <= BUDGET[lod] * 1.05:
            break
    if step:
        print(f'{ASSET} s{seed} LOD{lod}: resolution step {step} {ladder[step]} for {len(keep)} icicles ({tot} tris)')
    drips = []
    for i, ic in enumerate(L['icicles']):
        if i not in keep:
            continue
        big = big_of[i]
        sides, n = (sb, nb) if big else (ss, ns)
        st = S.stations_for(n, None, 0.85)
        Ltot = ic['L'] + L['lip_t'] / 2
        S.spike(mb, (ic['x'], ic['y'], zc), (0, 0, -1), Ltot, ic['r0'], sides, st, m_ice, taper=ic['taper'],
                flare=ic['flare'] if lod < 2 else 1.0, flare_len=0.12 * L['lip_t'] / Ltot * 6,
                ripple=ic['ripple'] if lod < 2 else (0, 0, 0), bend=ic['bend'], ell=ic['ell'], phase=ic['phase'])
        drips.append([ic['x'] + ic['bend'][0] * Ltot, ic['y'] + ic['bend'][1] * Ltot, zc - Ltot, round(ic['L'] / L['Lmax'], 2)])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=65)
    C.set_json_props(o, kz_snap='edge', kz_attach_z=round(H + dz, 3), kz_fx='fx_drips',
                     kz_drip_points=[[round(d[0] + dx, 3), round(d[1] + dy, 3), round(d[2] + dz, 3), d[3]] for d in drips],
                     kz_params=dict(style=style, w=round(w, 3), length=round(L['Lmax'], 3), count=len(L['icicles']),
                                    taper=round(L['taper'], 3), clarity=clarity))
    return o
