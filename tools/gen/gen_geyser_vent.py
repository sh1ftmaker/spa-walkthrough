"""Geyser vent mound and seat ring (b3_geyser): the low cracked black rock mound the fx_geyser_jet leaves
from, standing in a round teal pool, with smaller vents round it and a low sinter seat ring.

Concepts: refs/gen/sheet-mod-water.png #1 (geyser pool, label 8 m pool; the mound cluster spans ~0.35 of the
pool width -> ~2.8 m, rocks clustered round a central throat, low: ~0.12 of the pool width tall above the
water), lookbook/img/14-geyser-plaza.jpg (bathers ~1.7 m tall: mound rocks stand 0.4-0.9 m out of the water,
5-7 smaller jets round the main one, black wet faceted rock, teal underlit water). The carved seat blocks of
the sheet are a separate asset (seat_block_carved); the pool basin is pool_shell.

Targets (default build): overall 3.9 x 3.9 x 0.95-1.0 m (proxy 4 x 4 x 1.0; row dims 4.4 x 4.4 x 0.6).
  base z = 0 is the pool floor; water level kz_water_level = 0.30 m (shallow sitting pool round the mound) (row: shallow geyser pool)
  mound: footprint r 1.15-1.45 m (the row's 1.5-2.2 m counts the seat ring: overall r <= 1.98 m),
         H 0.93-1.0 (0.63-0.7 m out of the water), crater throat r 0.12-0.18 m with a pale sinter collar,
         4-6 radial cracks (V grooves 0.05-0.09 m deep), horizontal basalt strata facets
  rocks: 5-10 faceted basalt chunks 0.22-0.55 m (2-3 size classes) seated 35 % into the mound flanks
  vents: 1-7 small dark basalt cones (concave flanks) r 0.26-0.34 m with a pale sinter collar, tops 0.07-0.11 m above the water, each with a throat (kz_jets entries)
  seat ring: rimstone ring, inner r = mound r + 0.22, width 0.36-0.44 m, top 0.16 m under water, scalloped
         outer edge; style 'arcs' breaks it into 3-4 arcs with capped ends
Parameters: pool_r 4-8 (recorded for pool_shell, default 5), mound_r 1.15-1.45, vents 1-7, rocks 3-10,
  water (level, default 0.3), style 'ring' | 'arcs' | 'crown'.
Styles (C.cycle): ring (full ring, 3 vents), arcs (broken ring, 5 vents, offset crater), crown (full ring, 7
  vents, taller rock crown round the throat). Seeds also change mound radius / height, outline lobes,
  crack count and angles, rock count / sizes / layout, vent angles.
Materials (slots by part): m_flank basalt_wet 0.6, m_top basalt_wet 0.95 (spray-wet upper mound and rock
  tops), m_collar sinter (crater throat, vent collars); vent cones m_flank, m_ring rimstone (seat ring).
Custom props: kz_water_level, kz_water_outline (pool circle, pool_r), kz_pool_r, kz_jets (JSON [x, y, z,
  height, role]), kz_lights (main teal 7500 K 600 W in the throat + small vent uplights), kz_anim.
LODs from one layout: LOD1 halves the angular resolution, same rocks / vents; LOD2 keeps the 3 largest rocks,
  vents as 6-sided cones, ring 24 segments; LOD3 = 6-sided mound with crater, 3-sided vent cones, 8-sided ring.
Pivot: mound axis at (0, 0), z = 0 pool floor. No animation in the mesh (jets are fx_geyser_jet).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'geyser_vent'
CORE = 0.66          # the smooth core mound is 62 % of H; the rock crown carries the top
FEATURES = ['low cracked black rock mound with a central throat', 'smaller vents round it',
            'round teal pool (data) with a low sinter seat ring']
STYLES = ['ring', 'arcs', 'crown']


def _layout(seed, pool_r=None, mound_r=None, vents=None, rocks=None, water=None, style=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'mound')
    L = dict(style=style)
    L['R'] = mound_r or g.uniform(1.15, 1.45)
    L['H'] = g.uniform(0.93, 1.0)
    L['cr'] = g.uniform(0.12, 0.18)
    L['coff'] = (g.uniform(-0.12, 0.12), g.uniform(-0.12, 0.12)) if style != 'arcs' else (0.22, -0.1)
    L['outline'] = C.stone_outline(g, 1.0, aspect=g.uniform(0.9, 1.12), bites=g.choice([0, 1]),
                                   harmonics=((2, 0.05), (3, 0.07), (5, 0.05), (7, 0.03)))
    gc = C.rng(seed, 'cracks')
    nc = gc.randint(4, 6)
    L['cracks'] = [(2 * math.pi * (i + gc.uniform(-0.3, 0.3)) / nc, gc.uniform(0.05, 0.09), gc.uniform(0.05, 0.09))
                   for i in range(nc)]
    L['noff'] = Vector((g.uniform(0, 50), g.uniform(0, 50), g.uniform(0, 50)))
    L['water'] = water if water is not None else 0.30
    L['pool_r'] = pool_r or 5.0
    # rocks round the throat / flanks
    gr = C.rng(seed, 'rocks')
    nr = rocks if rocks is not None else gr.randint(6, 9) + (2 if style == 'crown' else 0)
    rl = []
    for i in range(nr):
        a = 2 * math.pi * (i + gr.uniform(-0.25, 0.25)) / max(nr, 1)
        crown = i % 2 == 0 if style == 'crown' else i % 3 == 0
        rho = (gr.uniform(0.22, 0.42) if crown else gr.uniform(0.45, 0.85)) * L['R']
        s = (gr.choice([0.4, 0.48, 0.55]) if crown else gr.choice([0.22, 0.32, 0.32, 0.45])) * gr.uniform(0.85, 1.1)
        lift = gr.uniform(0.9, 1.0) if crown else gr.uniform(0.55, 0.85)
        rl.append(dict(a=a, rho=rho, s=s, sz=(s, s * gr.uniform(0.75, 1.0), s * gr.uniform(0.7, 0.95)),
                       rot=gr.uniform(0, math.pi), rs=gr.randint(0, 10 ** 6), crown=crown, lift=lift))
    rl.sort(key=lambda d: -d['s'])
    L['rocks'] = rl
    # small vents
    gv = C.rng(seed, 'vents')
    nv = vents if vents is not None else {'ring': 3, 'arcs': 5, 'crown': 7}[style]
    ph = gv.uniform(0, 2 * math.pi)
    vl = []
    for i in range(nv):
        a = ph + 2 * math.pi * (i + gv.uniform(-0.2, 0.2)) / max(nv, 1)
        vl.append(dict(a=a, rho=L['R'] + gv.uniform(0.0, 0.14), rb=gv.uniform(0.26, 0.34), h=gv.uniform(0.16, 0.30),
                       ra=gv.uniform(0.05, 0.08)))
    L['vents'] = vl
    # seat ring
    gs = C.rng(seed, 'ring')
    L['ri'] = L['R'] + 0.22
    L['rw'] = min(gs.uniform(0.36, 0.44), 1.97 - L['ri'] - 0.05)
    L['rtop'] = L['water'] - 0.16
    L['scal'] = gs.randint(9, 13)
    L['sph'] = gs.uniform(0, 2 * math.pi)
    na = gs.choice([3, 4])
    if style == 'arcs':
        gaps = []
        a0 = gs.uniform(0, 2 * math.pi)
        for i in range(na):
            c = a0 + 2 * math.pi * i / na
            gaps.append((c + 0.22, c + 2 * math.pi / na - 0.22))
        L['arcs'] = gaps
    else:
        L['arcs'] = None
    return L


def _mound_r(L, th, zf):
    """radius of the mound surface at angle th and height fraction zf (outer flank)"""
    x, y = L['outline'](th)
    base = math.hypot(x, y)
    # profile: wide foot, convex flank, narrowing to the crater collar
    top_r = (L['cr'] + 0.09) / L['R']
    prof = base * (1 - zf ** 1.15) + top_r * zf ** 1.15
    prof *= 1 - 0.08 * math.sin(math.pi * zf)
    cut = 0.0
    for ca, w, dep in L['cracks']:
        d = math.atan2(math.sin(th - ca), math.cos(th - ca))
        cut += dep * math.exp(-(d / w) ** 2) * math.sin(math.pi * min(1.0, zf * 1.15))
    p = Vector((math.cos(th) * 1.3, math.sin(th) * 1.3, zf * 2.5)) + L['noff']
    facet = 0.05 * noise.noise(p) + 0.025 * noise.noise(p * 2.7)
    return max(0.08, L['R'] * prof - cut + facet * L['R'] * 0.6)


def _mound_h(L, rho_frac):
    """approx. mound height at a radius fraction (for seating rocks)"""
    return L['H'] * CORE * max(0.0, 1 - rho_frac) ** (1 / 1.15)


def build(lod, seed, pool_r=None, mound_r=None, vents=None, rocks=None, water=None, style=None):
    L = _layout(seed, pool_r, mound_r, vents, rocks, water, style)
    mb = genlib.MeshBuilder()
    m_flank = mb.slot('basalt_wet', wetness=0.6)
    m_top = mb.slot('basalt_wet', wetness=0.95, roughness_offset=-0.04)
    m_collar = mb.slot('sinter')
    m_ring = mb.slot('rimstone')
    bm = mb.bm
    R, H = L['R'], L['H']
    Hc = H * CORE
    cx, cy = L['coff']

    # ------------------------------------------------ mound: polar grid, outer flank -> collar -> throat
    N = C.lod_pick(lod, 56, 28, 12, 6)
    zfs = C.lod_pick(lod, (0.0, 0.12, 0.26, 0.42, 0.58, 0.72, 0.84, 0.93, 1.0),
                     (0.0, 0.2, 0.45, 0.7, 0.88, 1.0), (0.0, 0.4, 0.8, 1.0), (0.0, 0.55, 1.0))
    cr = L['cr']
    inner = C.lod_pick(lod, ((cr * 0.92, 0.985), (cr * 0.75, 0.93), (cr * 0.55, 0.82)),
                       ((cr * 0.85, 0.97), (cr * 0.55, 0.84)), ((cr * 0.6, 0.86),), ((cr * 0.5, 0.88),))
    rows = []
    for j, zf in enumerate(zfs):
        row = []
        for i in range(N):
            th = 2 * math.pi * i / N
            rr = _mound_r(L, th, zf)
            # the top rings are pulled to the crater centre so the throat sits off axis
            k = zf ** 2
            z = Hc * zf
            if 0 < zf < 1:
                p = Vector((math.cos(th), math.sin(th), zf * 3)) * 2.0 + L['noff']
                z += 0.035 * Hc * noise.noise(p)
            row.append(bm.verts.new((math.cos(th) * rr + cx * k, math.sin(th) * rr + cy * k, z)))
        rows.append(row)
    for rr_, zf in inner:
        row = []
        for i in range(N):
            th = 2 * math.pi * i / N
            row.append(bm.verts.new((cx + math.cos(th) * rr_, cy + math.sin(th) * rr_, Hc * zf)))
        rows.append(row)
    pole = bm.verts.new((cx, cy, Hc * (inner[-1][1] - 0.08)))
    n_outer = len(zfs)
    for j in range(len(rows) - 1):
        zmid = (j + 0.5) / (n_outer - 1) if j < n_outer - 1 else 1.0
        mi = m_flank if zmid < 0.55 else (m_top if j < n_outer - 1 else m_collar)
        for f in C.bridge_rings(bm, rows[j], rows[j + 1]):
            f.material_index = mi
    for i in range(N):
        f = bm.faces.new((rows[-1][i], rows[-1][(i + 1) % N], pole)); f.material_index = m_collar

    # ------------------------------------------------ rocks seated into the flanks
    keep = C.lod_pick(lod, len(L['rocks']), len(L['rocks']), 3, 0)
    npts = C.lod_pick(lod, 16, 10, 7, 6)
    for rk in L['rocks'][:keep]:
        a, rho = rk['a'], rk['rho']
        x, y = math.cos(a) * rho, math.sin(a) * rho
        hz = _mound_h(L, rho / R)
        s = rk['sz']
        top_t = H * rk['lift'] if rk['crown'] else hz + s[2] * rk['lift'] * 1.4
        zc = max(s[2] * 0.25, min(top_t, H) - s[2])
        rr = genlib.rng(rk['rs'], 'rock')
        mi = m_top if zc + s[2] > L['water'] + 0.1 else m_flank
        C.hull_rock(mb, (x, y, zc), s, mi, rr, npts=npts, ground=0.0, rot=rk['rot'], rmin=0.7,
                    flat_top=min(zc + s[2], H, 0.995))

    # ------------------------------------------------ small vents (sinter cones with a throat)
    vs_ = C.lod_pick(lod, 20, 12, 6, 3)
    for v in L['vents']:
        x, y = math.cos(v['a']) * v['rho'], math.sin(v['a']) * v['rho']
        base_z = 0.0
        hh = L['water'] + 0.02 + v['h'] * 0.3
        rb, ra = v['rb'], v['ra']
        if lod < 3:
            # dark basalt cone (concave flank) carrying a thin pale sinter collar round the throat
            body = [(rb, base_z), (rb * 0.62, hh * 0.3), (ra * 2.0, hh * 0.7), (ra * 1.7, hh * 0.9)]
            collar = [(ra * 1.7, hh * 0.9), (ra * 1.3, hh), (ra, hh * 0.93), (ra * 0.6, hh * 0.7), (0, hh * 0.62)]
            if lod == 2:
                body = [(rb, base_z), (ra * 1.7, hh * 0.9)]
                collar = [(ra * 1.7, hh * 0.9), (ra, hh), (0, hh * 0.75)]
            C.lathe(mb, body, vs_, m_flank, base=(x, y, 0), phase=v['a'])
            C.lathe(mb, collar, vs_, m_collar, base=(x, y, 0), phase=v['a'])
        else:
            b = [bm.verts.new((x + rb * math.cos(v['a'] + 2 * math.pi * k / 3), y + rb * math.sin(v['a'] + 2 * math.pi * k / 3), 0)) for k in range(3)]
            t = bm.verts.new((x, y, hh))
            for k in range(3):
                f = bm.faces.new((b[k], b[(k + 1) % 3], t)); f.material_index = m_flank

    # ------------------------------------------------ seat ring (rimstone, scalloped outer edge)
    ri, rw, top = L['ri'], L['rw'], L['rtop']
    prof = C.lod_pick(lod,
                      [(0.0, 0.0), (-0.02, 0.55), (0.03, 0.9), (0.1, 1.0), (0.5, 1.02), (0.9, 0.98), (0.98, 0.86), (1.04, 0.45), (1.08, 0.0)],
                      [(0.0, 0.0), (0.0, 0.8), (0.1, 1.0), (0.9, 1.0), (1.02, 0.6), (1.08, 0.0)],
                      [(0.0, 0.0), (0.05, 1.0), (0.95, 1.0), (1.08, 0.0)],
                      [(0.0, 0.0), (0.5, 1.0), (1.08, 0.0)])
    NA = C.lod_pick(lod, 120, 60, 24, 8)

    def ring_pt(th, u, zf):
        sc = 0.035 * (abs(math.sin(L['scal'] * th / 2 + L['sph'])) ** 0.6 - 0.5) * u
        r_ = ri + rw * u + sc
        return (math.cos(th) * r_, math.sin(th) * r_, top * zf)

    spans = [(0.0, 2 * math.pi, True)] if not L['arcs'] else [(a0, a1, False) for a0, a1 in L['arcs']]
    for a0, a1, cyc in spans:
        n = NA if cyc else max(3, int(NA * (a1 - a0) / (2 * math.pi)) + 1)
        ths = [a0 + (a1 - a0) * i / (n if cyc else n - 1) for i in range(n)]
        rws = [[bm.verts.new(ring_pt(th, u, zf)) for u, zf in prof] for th in ths]
        m = len(prof)
        for i in range(n if cyc else n - 1):
            A, B = rws[i], rws[(i + 1) % n]
            for k in range(m - 1):
                f = bm.faces.new((A[k], B[k], B[k + 1], A[k + 1])); f.material_index = m_ring
        if not cyc:
            for rw_, flip in ((rws[0], True), (rws[-1], False)):
                f = bm.faces.new(rw_[::-1] if flip else rw_); f.material_index = m_ring

    # ------------------------------------------------ object + data
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=40)
    pr = L['pool_r']
    C.water_props(o, L['water'], outline_xy=[(pr * math.cos(2 * math.pi * k / 48), pr * math.sin(2 * math.pi * k / 48)) for k in range(48)])
    jets = [[round(cx, 3), round(cy, 3), round(H * 0.8, 3), 8.0, 'main']]
    lights = [C.light_entry((cx, cy, L['water'] - 0.1), color_k=7500, watts=600, role='throat uplight', color=(0.35, 0.95, 0.85))]
    for v in L['vents']:
        x, y = math.cos(v['a']) * v['rho'], math.sin(v['a']) * v['rho']
        jets.append([round(x, 3), round(y, 3), round(L['rtop'] + v['h'], 3), 3.0, 'small'])
        lights.append(C.light_entry((x, y, L['water'] - 0.12), color_k=7500, watts=60, role='vent uplight', color=(0.35, 0.95, 0.85)))
    C.set_json_props(o, kz_jets=jets, kz_lights=lights, kz_pool_r=pr, kz_style=L['style'],
                     kz_anim=dict(type='sim-driven', fx='fx_geyser_jet', sources='kz_jets'),
                     kz_params=dict(mound_r=round(R, 3), H=round(H, 3), vents=len(L['vents']), rocks=len(L['rocks']),
                                    seat_ring=[round(ri, 3), round(ri + rw, 3), round(top, 3)]))
    return o
