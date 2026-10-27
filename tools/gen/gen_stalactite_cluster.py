"""Stalactite cluster (stalactite_cluster): a hanging cluster of tapering, amber-tipped rock spikes from a
lumpy ceiling plate. Ceiling-snapped: the plate top is the attach plane (z = h), the longest tip is z = 0.

Targets (measured on refs/gen/sheet-mod-nature.png, panel 8 "Stalactite cluster - 3 m", 56 px/m from both
the 1 m bar (688-744 px) and the 3 m arrow (750-918 px), they agree):
  * overall height 3.0 m from the plate top to the longest tip; plate 0.25-0.35 m thick, lumpy, with
    many short stubs on its underside.
  * spikes spread over ~2.7 m of the plate in the front view and ~2.0 m in the side view; ~15-20 spikes
    visible: one long central spike (2.7 m below the plate) fused with 1-2 shorter satellites, a ring of
    0.4-1.6 m spikes around it, getting shorter towards the edge.
  * root widths: the long spike ~0.35-0.45 m at the plate (with a flare), short ones 0.10-0.18 m;
    taper is concave (fast near the root, needle tip), drip ridges along the length.
  * colour: dark glossy rock on the upper half, translucent amber / honey on the lower 30-50 % of each
    spike (the "amber tips"); lookbook 20 (wave grotto) and 14 (geyser plaza) agree: dark root, glowing
    amber tips, slender needles.
  Build size: proxy 2.0 x 2.0 x 3.0 (the row's dims); the sheet plate is drawn wider (it is cropped by the
  panel) so I kept the plate inside the proxy and the spike spread inside the plate.

Construction:
  * plate: convex hull of 30 seeded half-ellipsoid points clamped to the ceiling plane (kzgeo_rock_cluster
    basalt_hull, ceiling=h), 1 subdivision cut + fractal noise at LOD0 for a lumpy underside. cave_rock.
  * spikes (kzgeo_stalactite_cluster.spike): stacked 7-sided rings with per-angle facet factors (planar
    vertical facets), a concave power taper, a root flare that blends into the plate, sinusoidal drip
    ridges and a slight seeded bend; pointed apex. Upper part basalt_wet (near-black tint), lower
    tip_frac (0.30-0.50) sinter tinted amber; the material boundary is a ring kept at every LOD.
  * stubs: 8-14 short spikes 0.08-0.30 m on the plate underside (LOD0-1 only, small parts).
Materials: cave_rock (plate), basalt_wet tint (0.32, 0.36, 0.46) wetness 0.85 (spike upper), sinter with a
tip tint (spike tips). All tints <= 1.

Parameters (build kwargs):
  w        plate width 0.8-3 m (default 2.0); plate depth = w * aspect (0.75-1.0, seeded).
  length   longest spike below the plate, 0.5-5 m (default by style; clamped so h <= proxy h).
  count    spike count 5-25 (default by style: 16 / 20 / 12); stubs extra.
  taper    taper exponent 1.0-2.0 (default seeded 1.25-1.6; higher = needle-like).
  tip      tip tint 'amber' | 'honey' | 'rust' (default seeded).
  style    'chandelier' | 'curtain' | 'forest' (default seed-cycled):
           chandelier = one dominant central spike with fused satellites, a descending ring around it;
           curtain = spikes along a slightly curved line (drapery edge), a hump of long ones;
           forest = many mid-length spikes of mixed length all over the plate, no dominant one.
Seeds change shape: style, count, spread, lengths, taper, bend and facets (5 variants: seeds 1-5; seeds
4 and 5 repeat chandelier / curtain with different counts and lengths).

LODs (budget 3000 / 1200 / 360 / 80): same spikes, same places, same slots.
  LOD0 7 sides (9 on the dominant spike), 4-9 rings by length + stubs; LOD1 5 sides, half the rings + stubs;
  LOD2 4 sides, 2-3 rings (root, amber split, apex), no stubs; LOD3 the plate as an 8-point hull and the
  longest spikes as 3-sided cones split at the amber ring (fits 80).
Animation: none. Lighting: lightmap (UV1). Custom props: kz_snap 'ceiling', kz_attach_z (plate top),
kz_tips (tip points, for glowworm threads / drips), kz_params.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R
import kzgeo_stalactite_cluster as S

ASSET = 'stalactite_cluster'
FEATURES = ['ceiling plate', 'hanging tapering rock spikes', 'amber tips', 'long central spike']
STYLES = ['chandelier', 'curtain', 'forest']
COUNT = {'chandelier': 16, 'curtain': 20, 'forest': 12}
LEN = {'chandelier': 2.68, 'curtain': 2.1, 'forest': 1.55}
TIPS = {'amber': (1.0, 0.5, 0.2), 'honey': (1.0, 0.66, 0.34), 'rust': (0.86, 0.4, 0.18)}
BUDGET = [3000, 1200, 360, 80]


def _layout(seed, w, length, count, taper, style):
    g = C.rng(seed, 'layout')
    aspect = g.uniform(0.75, 1.0)
    thick = g.uniform(0.25, 0.34)
    p = genlib.proxy(ASSET)
    Lmax = min(length if length else LEN[style] * g.uniform(0.92, 1.0), p['h'] * 1.03 - thick)
    rx, ry = w / 2, w * aspect / 2
    n = int(count if count else COUNT[style] + (seed - 1) // 3 * g.choice([-3, 3]))
    n = max(5, min(25, n))
    tap = taper if taper else g.uniform(1.25, 1.6)
    spikes = []
    if style == 'curtain':
        arc = g.uniform(-0.25, 0.25)
        hump_c, hump_w = g.uniform(-0.25, 0.25), g.uniform(0.25, 0.45)
    for i in range(n):
        s = C.rng(seed, f'spike{i}')
        for _try in range(30):
            if style == 'chandelier':
                if i == 0:
                    x, y = s.uniform(-0.05, 0.05) * rx, s.uniform(-0.05, 0.05) * ry
                elif i <= 2:                       # fused satellites hugging the main spike
                    a = s.uniform(0, 2 * math.pi); d = s.uniform(0.11, 0.16)
                    x, y = math.cos(a) * d, math.sin(a) * d
                else:
                    a = s.uniform(0, 2 * math.pi); q = math.sqrt(s.uniform(0.06, 1.0)) * 0.68
                    x, y = math.cos(a) * q * rx, math.sin(a) * q * ry
            elif style == 'curtain':
                tx = s.uniform(-1, 1)
                x = tx * rx * 0.72
                y = (arc * (tx * tx - 0.4) + s.uniform(-0.09, 0.09)) * ry
            else:
                a = s.uniform(0, 2 * math.pi); q = math.sqrt(s.uniform(0.0, 1.0)) * 0.66
                x, y = math.cos(a) * q * rx, math.sin(a) * q * ry
            q = math.hypot(x / rx, y / ry)
            # length by style
            if style == 'chandelier':
                if i == 0:
                    L = Lmax
                elif i <= 2:
                    L = Lmax * s.uniform(0.45, 0.72)
                else:
                    L = Lmax * max(0.12, (0.62 - 0.55 * q / 0.68)) * s.uniform(0.7, 1.25)
            elif style == 'curtain':
                hump = math.exp(-((x / rx - hump_c) / hump_w) ** 2)
                L = Lmax * max(0.14, 0.25 + 0.75 * hump * s.uniform(0.55, 1.0) if i else 1.0)
                if i == 0:
                    x = hump_c * rx * 0.72; y = arc * (hump_c ** 2 - 0.4) * ry
            else:
                L = Lmax * (1.0 if i < 2 else s.uniform(0.2, 0.85))
            L = min(L, Lmax)
            r0 = (0.055 + 0.085 * L) * s.uniform(0.85, 1.15)
            if style == 'chandelier' and i == 0:
                r0 = 0.20 * max(0.6, Lmax / 2.6)
            ok = all(math.hypot(x - o['x'], y - o['y']) > 0.55 * (r0 + o['r0']) or (style == 'chandelier' and i <= 2)
                     for o in spikes)
            if ok:
                break
        spikes.append(dict(
            x=x, y=y, L=L, r0=r0, taper=tap * s.uniform(0.92, 1.08),
            tip=s.uniform(0.30, 0.50), facets=S.facet_factors(s, 9, 0.84, 1.12),
            ripple=(s.uniform(0.05, 0.11), s.uniform(1.6, 3.4) * max(1.0, L), s.uniform(0, 1)),
            bend=(s.uniform(-0.04, 0.04), s.uniform(-0.04, 0.04)), phase=s.uniform(0, 2 * math.pi),
            flare=s.uniform(1.35, 1.7), main=(i == 0)))
    gs = C.rng(seed, 'stubs')
    stubs = []
    for i in range(int(8 + 6 * min(1.0, w / 2.0))):
        a = gs.uniform(0, 2 * math.pi); q = math.sqrt(gs.uniform(0.02, 1.0)) * 0.85
        L = gs.uniform(0.08, 0.30)
        stubs.append(dict(x=math.cos(a) * q * rx, y=math.sin(a) * q * ry, q=q, L=L, r0=0.035 + 0.12 * L,
                          phase=gs.uniform(0, 6.3), facets=S.facet_factors(gs, 5, 0.85, 1.1)))
    gp = C.rng(seed, 'plate')
    plate = dict(pts=R.draw_points(gp, 30, rx, ry, thick, rmin=0.82), off=Vector((gp.uniform(0, 99), gp.uniform(0, 99), gp.uniform(0, 99))),
                 chips=R.draw_chips(gp, 4, up_bias=-0.8, depth=(0.04, 0.10)))
    env = []
    for k in range(8):
        a = 2 * math.pi * k / 8 + gp.uniform(-0.2, 0.2)
        env.append(Vector((math.cos(a) * rx * gp.uniform(0.92, 1.0), math.sin(a) * ry * gp.uniform(0.92, 1.0), -thick * gp.uniform(0.15, 0.35))))
    plate['env'] = env
    return dict(aspect=aspect, thick=thick, Lmax=Lmax, rx=rx, ry=ry, spikes=spikes, stubs=stubs, plate=plate, taper=tap)


def _res(lod, sp, Lmax):
    """(sides, stations) for one spike at one LOD"""
    if lod == 0:
        n = max(4, min(9, int(round(3 + 2.2 * sp['L']))))
        return (9 if sp['main'] else 7), S.stations_for(n, 1 - sp['tip'], 0.9)
    if lod == 1:
        n = max(3, min(5, int(round(2 + 1.1 * sp['L']))))
        return (6 if sp['main'] else 5), S.stations_for(n, 1 - sp['tip'], 0.9)
    if lod == 2:
        return 4, ([0.0, 0.45 * (1 - sp['tip']), 1 - sp['tip']] if sp['L'] > 0.5 * Lmax else [0.0, 1 - sp['tip']])
    return 3, [0.0, 1 - sp['tip']]


def build(lod, seed, w=2.0, length=None, count=None, taper=None, tip=None, style=None):
    style = style or C.cycle(seed, STYLES)
    tip = tip or C.pick(seed, 'tip', list(TIPS))
    w = max(0.8, min(3.0, float(w)))
    L = _layout(seed, w, length, count, taper, style)
    H = L['thick'] + L['Lmax']
    mb = genlib.MeshBuilder()
    m_plate = mb.slot('cave_rock', wetness=0.7)
    m_rock = mb.slot('basalt_wet', wetness=0.85, tint=R.TINT, roughness_offset=-0.05)
    m_tip = mb.slot('sinter', wetness=0.9, tint=TIPS[tip], roughness_offset=-0.1)
    # plate
    P = L['plate']
    if lod < 3:
        n_pts = C.lod_pick(lod, 30, 24, 14)
        pts = [Vector((p.x, p.y, H - abs(p.z))) for p in P['pts'][:n_pts]] + [Vector((p.x, p.y, H + p.z)) for p in P['env']]
        pts += [Vector((p.x * 0.9, p.y * 0.9, H)) for p in P['env'][::2]]
    else:
        pts = [Vector((p.x, p.y, H + p.z)) for p in P['env'][::2]] + [Vector((p.x * 0.8, p.y * 0.8, H)) for p in P['env'][1::2]] \
            + [Vector((0, 0, H - L['thick']))]
    R.basalt_hull(mb, pts, m_plate, m_plate, ceiling=H, cuts=C.lod_pick(lod, 1, 0, 0, 0),
                  amp=C.lod_pick(lod, 0.035, 0.0, 0.0, 0.0), freq=3.0, off=P['off'],
                  chips=P['chips'][:C.lod_pick(lod, 4, 2, 0, 0)])
    # spikes: LOD3 keeps the longest ones that fit the budget
    order = sorted(range(len(L['spikes'])), key=lambda i: -L['spikes'][i]['L'])
    keep = set(order)
    if lod == 3:
        per = S.cost(3, 2)
        plate_tris = 14
        keep = set(order[:max(1, (BUDGET[3] - plate_tris) // per)])
    tips = []
    for i, sp in enumerate(L['spikes']):
        if i not in keep:
            continue
        sides, st = _res(lod, sp, L['Lmax'])
        split = 1 - sp['tip']
        fac = [sp['facets'][k % len(sp['facets'])] for k in range(sides)] if lod < 3 else None
        S.spike(mb, (sp['x'], sp['y'], H - 0.03), (0, 0, -1), sp['L'] + L['thick'] - 0.03, sp['r0'], sides, st,
                lambda t, split=split: m_rock if t < split else m_tip,
                taper=sp['taper'], flare=sp['flare'] if lod < 2 else 1.0, flare_len=0.10,
                ripple=sp['ripple'] if lod < 2 else (0, 0, 0), bend=sp['bend'], facets=fac, phase=sp['phase'])
        tips.append([round(sp['x'] + sp['bend'][0] * 0, 3), round(sp['y'], 3), round(H - L['thick'] - sp['L'], 3)])
    # stubs (LOD0-1): root inside the plate underside
    if lod < 2:
        for sb in L['stubs']:
            z0 = H - L['thick'] * 0.7 * math.sqrt(max(0.0, 1 - sb['q'] ** 2))
            S.spike(mb, (sb['x'], sb['y'], z0 + 0.02), (0, 0, -1), sb['L'] + 0.02, sb['r0'], C.lod_pick(lod, 5, 4),
                    [0.0, 0.5] if lod == 0 else [0.0], m_plate, taper=1.2, flare=1.3, facets=sb['facets'][:C.lod_pick(lod, 5, 4)],
                    phase=sb['phase'])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_snap='ceiling', kz_attach_z=round(H + dz, 3),
                     kz_tips=[[t[0] + dx, t[1] + dy, t[2] + dz] for t in tips],
                     kz_params=dict(style=style, w=round(w, 3), d=round(2 * L['ry'], 3), length=round(L['Lmax'], 3),
                                    count=len(L['spikes']), taper=round(L['taper'], 3), tip=tip))
    return o
