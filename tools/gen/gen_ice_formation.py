"""Glacier ice wall and frost (ice_formation): translucent blue ice rising from the pool in crystalline
masses with fluted columns and icicle fringes; a frost-patch variant on basalt.

Targets (lookbook/img/17-glacier-plunge.jpg left third: the ice wall from the pool to the vault, the
bather ~1.65 m on the right gives ~0.27 m per 100 px at the pool, so the visible wall is ~7-9 m tall and
6+ m wide; refs/gen/mat-glacier-ice.png: big planar crystal facets 0.5-1.5 m, fringes of icicles under
every overhang, a frozen cascade foaming into the pool on the left):
  * proxy 6 x 4 x 8 m (row: w 3-22, h 2.8-11, d 0.4-2.4). Default wall 6.0 x 2.4 x 7.6 m, cascade
    5.2 x 2.8 x 8.0 m, frost patch 3.2 x 1.1 x 2.8 m.
  * crystalline masses: convex hulls with planar chip faces, 1.0-2.6 m across, stacked in 3 tiers, the
    crown overhanging the front by 0.3-0.6 m.
  * fluted columns 0.3-0.55 m radius, 8 flutes, 2.5-6.5 m tall, standing in front of the masses.
  * icicles 0.6-2.4 m under the crown; dark wet basalt boulders at the foot; frost on rock tops.
Construction: masses = kzgeo_rock_cluster.basalt_hull (no noise: crisp crystal facets + 5-7 chip planes);
columns and icicles = kzgeo_stalactite_cluster.spike (flute_fn on columns; up / down); foot rocks =
basalt_hull with frost patches through the moss channel (frost slot on top faces, coverage = frost).
Materials: glacier_ice (masses: deep tint (0.78, 0.92, 1.0), emissive_level = translucency; columns and
icicles: clear, roughness -0.15; frost: tint (1.25, 1.25, 1.25) roughness +0.35), basalt_wet near-black.

Parameters: w (3-22 m, default by style; x scales), h (2.8-11 m, default by style; z scales), d
(0.4-2.4, y scales), columns (count, default by style), translucency 0.4-1.2 (default 0.9), frost 0-0.6
(coverage, default 0.35), style 'wall' | 'cascade' | 'frost' (seed-cycled; the row's three variants):
  wall    = three tiers of crystalline masses, 5-7 fluted columns in front, icicles under the crown;
  cascade = a wide crown ledge with a dense curtain of long fused hanging columns (some reaching the
            pool), an ice splash mound at the foot, masses at both flanks;
  frost   = a basalt rock face and boulders with frost patches, a thin ice crust over the top, short icicles.
Seeds change style; within a style the tiers, sizes, counts and lean are seeded.

LODs (15000 / 6000 / 1800 / 200): one layout per seed; LODs use fewer hull points, sides and rings;
LOD3 keeps every mass (8-point hulls), the 6 biggest columns / icicles as 3-sided cones, the 2 biggest rocks.
Animation: shader (subsurface glow, wet sheen) -> kz_anim. Lighting: lightmap + emissive backlight:
kz_lights point 400 W 12000 K behind the ice (proxy light).
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R
import kzgeo_stalactite_cluster as S

ASSET = 'ice_formation'
FEATURES = ['translucent blue crystalline ice masses', 'fluted ice columns', 'icicle fringe', 'frost on basalt']
STYLES = ['wall', 'cascade', 'frost']
DIMS = {'wall': (6.0, 2.4, 7.6), 'cascade': (5.2, 2.8, 8.0), 'frost': (3.2, 1.1, 2.8)}


def _mass(g, cx, cy, z0, rx, ry, top, ground, npts=44):
    """one crystalline mass: shell points + a broad top; all draws made here"""
    sh = R.draw_points(g, npts, rx, ry, (top - z0) / 2, rmin=0.82)
    zc = (top + z0) / 2
    return dict(kind='mass', pts=[Vector((cx + p.x, cy + p.y, zc + p.z)) for p in sh],
                env=[Vector((cx + rx * math.cos(a) * 0.8, cy + ry * math.sin(a) * 0.8, z)) for a, z in
                     ((g.uniform(0, 6.3), top), (g.uniform(0, 6.3), top * 0.98 + z0 * 0.02), (g.uniform(0, 6.3), z0),
                      (g.uniform(0, 6.3), z0), (g.uniform(0, 6.3), (top + z0) / 2), (g.uniform(0, 6.3), (top + z0) / 2))],
                chips=R.draw_chips(g, 7, up_bias=0.2, depth=(0.05, 0.14)), ground=ground, size=rx * ry * (top - z0))


def _layout(seed, style, w, d, h, columns):
    W0, D0, H0 = DIMS[style]
    g = C.rng(seed, 'layout')
    W, D, Hh = (w or W0 * g.uniform(0.93, 1.0)), (d or D0), (h or H0 * g.uniform(0.94, 1.0))
    p = genlib.proxy(ASSET)
    W, D, Hh = min(W, p['w']), min(D, p['d']), min(Hh, p['h'])
    sx, sz = W / W0, Hh / H0
    el = []
    if style in ('wall', 'cascade'):
        gm = C.rng(seed, 'masses')
        # tier 1 (ground), tier 2, crown
        n1 = 4 if style == 'wall' else 2
        xs1 = [(-1 + 2 * (i + 0.5) / n1) * W0 * 0.38 for i in range(n1)] if style == 'wall' else [-W0 * 0.34, W0 * 0.34]
        for x in xs1:
            el.append(_mass(gm, x * sx + gm.uniform(-0.2, 0.2), gm.uniform(-0.3, 0.0) * D0, 0.0,
                            gm.uniform(0.8, 1.1) * sx * (1.0 if style == 'wall' else 0.95), gm.uniform(0.6, 0.85) * D0 / 2.4,
                            gm.uniform(1.8, 3.2) * sz, True))
        t1_top = min(max(q.z for q in m['env']) for m in el)
        if style == 'cascade':      # backing curtain mass behind the hanging columns (no hole in the fall)
            el.append(_mass(gm, gm.uniform(-0.15, 0.15), -0.32 * D0, 0.0, W0 * 0.26 * sx, D0 * 0.22, 0.6 * Hh, True))
        n2 = 3 if style == 'wall' else 2
        t2_tops = []
        for i in range(n2):
            x = ((-1 + 2 * (i + 0.5) / n2) * W0 * 0.32) if style == 'wall' else (-1 + 2 * i) * W0 * 0.36
            z0 = min(gm.uniform(1.6, 2.4) * sz, 0.8 * t1_top)
            top2 = z0 + gm.uniform(2.2, 3.2) * sz
            t2_tops.append(top2)
            el.append(_mass(gm, x * sx + gm.uniform(-0.2, 0.2), gm.uniform(-0.45, -0.15) * D0, z0,
                            gm.uniform(0.9, 1.2) * sx, gm.uniform(0.55, 0.8) * D0 / 2.4, top2, False))
        crown_n = 2 if style == 'wall' else 3
        crown_z0 = min(gm.uniform(0.62, 0.68) * Hh, min(t2_tops) - 0.6 * sz)
        for i in range(crown_n):
            x = (-1 + 2 * (i + 0.5) / crown_n) * W0 * (0.28 if style == 'wall' else 0.33)
            el.append(_mass(gm, x * sx, gm.uniform(-0.05, 0.12) * D0, crown_z0,
                            gm.uniform(1.25, 1.5) * sx * (0.85 if style == 'cascade' else 1.0), gm.uniform(0.75, 0.95) * D0 / 2.4,
                            Hh * gm.uniform(0.97, 1.0) if i == 0 else Hh * gm.uniform(0.86, 0.96), False))
        gc = C.rng(seed, 'columns')
        if style == 'wall':
            nc = columns or gc.randint(5, 7)
            for i in range(nc):
                x = (-1 + 2 * (i + 0.5) / nc) * W0 * 0.42 + gc.uniform(-0.15, 0.15)
                el.append(dict(kind='column', x=x * sx, y=D0 * gc.uniform(0.12, 0.28), L=gc.uniform(2.5, 6.0) * sz,
                               r0=gc.uniform(0.3, 0.5) * sx ** 0.5, up=True, flutes=8, depth=gc.uniform(0.10, 0.16),
                               phase=gc.uniform(0, 6.3), taper=gc.uniform(0.35, 0.55), bend=(gc.uniform(-0.03, 0.03), gc.uniform(-0.04, 0.0))))
            n_ic = 12
        else:
            nc = columns or gc.randint(9, 12)
            for i in range(nc):
                x = (-1 + 2 * (i + 0.5) / nc) * W0 * 0.30 + gc.uniform(-0.1, 0.1)
                reach = gc.random() < 0.35
                L = crown_z0 + 0.3 if reach else gc.uniform(0.35, 0.8) * crown_z0
                el.append(dict(kind='column', x=x * sx, y=D0 * gc.uniform(0.0, 0.2), L=L, top=crown_z0 + 0.4 * sz,
                               r0=gc.uniform(0.28, 0.45) * sx ** 0.5, up=False, flutes=7, depth=gc.uniform(0.12, 0.2),
                               phase=gc.uniform(0, 6.3), taper=0.5 if reach else gc.uniform(0.9, 1.3),
                               bend=(gc.uniform(-0.02, 0.02), gc.uniform(0.0, 0.04))))
            gs = C.rng(seed, 'splash')
            el.append(_mass(gs, gs.uniform(-0.2, 0.2), D0 * 0.15, 0.0, W0 * 0.32 * sx, D0 * 0.28, gs.uniform(0.9, 1.3) * sz, True))
            n_ic = 8
        gi = C.rng(seed, 'icicles')
        for i in range(n_ic):
            x = gi.uniform(-0.42, 0.42) * W0 * sx
            el.append(dict(kind='icicle', x=x, y=gi.uniform(0.1, 0.4) * D0, z=crown_z0 + 0.35 * sz,
                           L=gi.uniform(0.6, 2.4) * sz, r0=gi.uniform(0.08, 0.16), phase=gi.uniform(0, 6.3),
                           ripple=(gi.uniform(0.05, 0.1), gi.uniform(2, 4), gi.uniform(0, 1))))
        gr = C.rng(seed, 'rocks')
        for i in range(3):
            x = (-0.45 + 0.45 * i) * W0 * sx + gr.uniform(-0.3, 0.3)
            el.append(dict(kind='rock', c=(x, D0 * 0.42, 0.0), size=(gr.uniform(0.4, 0.7), gr.uniform(0.35, 0.55), gr.uniform(0.3, 0.55)),
                           g_seed=(seed, f'rock{i}')))
    else:   # frost patch on basalt
        gr = C.rng(seed, 'rocks')
        el.append(dict(kind='rock', c=(0.0, -D0 * 0.12, 0.0), size=(W0 * 0.42 * sx, D0 * 0.38, Hh * 0.97), g_seed=(seed, 'face'), face=True))
        for i in range(3):
            x = (-0.32 + 0.32 * i) * W0 * sx + gr.uniform(-0.15, 0.15)
            el.append(dict(kind='rock', c=(x, D0 * 0.22, 0.0), size=(gr.uniform(0.35, 0.55), gr.uniform(0.22, 0.3), gr.uniform(0.35, 0.8)),
                           g_seed=(seed, f'rock{i}')))
        gm = C.rng(seed, 'crust')
        el.append(_mass(gm, gm.uniform(-0.2, 0.2), -D0 * 0.1, Hh * 0.72, W0 * 0.36 * sx, D0 * 0.34, Hh, False, npts=20))
        gi = C.rng(seed, 'icicles')
        for i in range(9):
            el.append(dict(kind='icicle', x=gi.uniform(-0.35, 0.35) * W0 * sx, y=D0 * gi.uniform(0.05, 0.18),
                           z=Hh * gi.uniform(0.74, 0.8), L=gi.uniform(0.25, 0.9) * sz, r0=gi.uniform(0.04, 0.08),
                           phase=gi.uniform(0, 6.3), ripple=(gi.uniform(0.05, 0.1), gi.uniform(3, 6), gi.uniform(0, 1))))
    return dict(W=W, D=D, H=Hh, el=el)


def build(lod, seed, w=None, d=None, h=None, columns=None, translucency=0.9, frost=0.35, style=None):
    style = style or C.cycle(seed, STYLES)
    tr = max(0.4, min(1.2, float(translucency)))
    frost = max(0.0, min(0.6, float(frost)))
    L = _layout(seed, style, w, d, h, columns)
    mb = genlib.MeshBuilder()
    m_ice = mb.slot('glacier_ice', tint=(0.78, 0.92, 1.0), emissive_level=round(tr, 3))
    m_top = mb.slot('glacier_ice', tint=(0.9, 0.97, 1.0), emissive_level=round(tr, 3), roughness_offset=0.1)
    m_clear = mb.slot('glacier_ice', roughness_offset=-0.15, emissive_level=round(min(1.2, tr * 1.05), 3))
    m_frost = mb.slot('glacier_ice', tint=(1.25, 1.25, 1.25), roughness_offset=0.35, emissive_level=0.3)
    m_rock = mb.slot('basalt_wet', wetness=0.85, tint=R.TINT, roughness_offset=-0.05)
    els = L['el']
    big = sorted([e for e in els if e['kind'] in ('column', 'icicle')], key=lambda e: -e['L'] * e['r0'])
    keep_spk = {id(e) for e in big[:6]} if lod == 3 else {id(e) for e in big}
    if lod == 2:
        keep_spk = {id(e) for e in big if e['kind'] == 'column' or e['L'] > 0.9}
    rocks = sorted([e for e in els if e['kind'] == 'rock'], key=lambda e: -e['size'][0] * e['size'][2])
    keep_rock = {id(e) for e in (rocks[:2] if lod == 3 else rocks)}
    for e in els:
        k = e['kind']
        if k == 'mass':
            n = C.lod_pick(lod, len(e['pts']), 22, 9, 2)
            pts = e['pts'][:n] + e['env']
            R.basalt_hull(mb, pts, m_ice, m_top, ground=0.0 if e['ground'] else None,
                          chips=e['chips'][:C.lod_pick(lod, 7, 5, 2, 0)], cuts=0, amp=0.0)
        elif k == 'column':
            if id(e) not in keep_spk:
                continue
            sides = C.lod_pick(lod, 24, 12, 6, 3)
            st = S.stations_for(C.lod_pick(lod, 8, 4, 2, 1), None, 1.0)
            fl = S.flute_fn(e['flutes'], e['depth'], e['phase']) if lod < 2 else None
            if e['up']:
                S.spike(mb, (e['x'], e['y'], 0.0), (0, 0, 1), e['L'], e['r0'], sides, st, m_clear, taper=e['taper'],
                        flare=1.25 if lod < 2 else 1.0, flare_len=0.08, facets=fl, bend=e['bend'], phase=e['phase'])
            else:
                S.spike(mb, (e['x'], e['y'], e['top']), (0, 0, -1), e['L'] + (e['top'] - (e['top'] - 0.4)) , e['r0'], sides, st, m_clear,
                        taper=e['taper'], flare=1.3 if lod < 2 else 1.0, flare_len=0.1, facets=fl, bend=e['bend'],
                        phase=e['phase'], ripple=(0.06, 3.0, e['phase']) if lod < 2 else (0, 0, 0))
        elif k == 'icicle':
            if id(e) not in keep_spk:
                continue
            S.spike(mb, (e['x'], e['y'], e['z']), (0, 0, -1), e['L'] + 0.35, e['r0'], C.lod_pick(lod, 10, 6, 4, 3),
                    S.stations_for(C.lod_pick(lod, 6, 3, 2, 1), None, 0.9), m_clear, taper=1.4, flare=1.4 if lod < 2 else 1.0,
                    flare_len=0.12, ripple=e['ripple'] if lod < 2 else (0, 0, 0), phase=e['phase'])
        elif k == 'rock':
            if id(e) not in keep_rock:
                continue
            g = C.rng(*e['g_seed'])
            sx, sy, sz = e['size']
            if e.get('face'):
                shell = R.draw_points(g, 40, sx, sy, sz, rmin=0.85)
                pts = [Vector((e['c'][0] + p.x, e['c'][1] + p.y, abs(p.z))) for p in shell]
                pts += [Vector((e['c'][0] + sx * a * 0.9, e['c'][1] + sy * b * 0.6, sz * 0.97)) for a, b in ((-1, -1), (1, -1), (-0.3, 1), (0.4, 1))]
            else:
                shell = R.draw_points(g, 24, sx, sy, sz, rmin=0.8)
                pts = [Vector((e['c'][0] + p.x, e['c'][1] + p.y, abs(p.z))) for p in shell]
            off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
            n = C.lod_pick(lod, len(pts), max(12, len(pts) * 2 // 3), 10, 6)
            R.basalt_hull(mb, pts[:n] if not e.get('face') else pts[:n - 4] + pts[-4:], m_rock, m_rock, ground=0.0,
                          cuts=C.lod_pick(lod, 2 if e.get('face') else 1, 1 if e.get('face') else 0, 0, 0),
                          amp=C.lod_pick(lod, 0.04, 0.03, 0, 0) * max(1.0, sz / 1.5), freq=2.0, off=off, top_thresh=0.45,
                          mi_moss=m_frost if lod < 3 else None, moss=frost)
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=40)
    C.set_json_props(o, kz_lights=[C.light_entry((dx, -L['D'] * 0.3 + dy, L['H'] * 0.45), color_k=12000, watts=400, role='backlight')],
                     kz_anim=dict(type='shader', subsurface_glow=round(tr, 2), wet_sheen=0.6),
                     kz_params=dict(style=style, w=round(L['W'], 2), d=round(L['D'], 2), h=round(L['H'], 2),
                                    translucency=tr, frost=frost))
    return o
