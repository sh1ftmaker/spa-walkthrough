"""Rock-ringed plunge basin: a small round pool where a fall lands, ringed with black boulders, lit from below.

Identifying features kept at every LOD: a round dark basin of churning water; a ring of black wet
boulders on its kerb (taller pair either side of the landing point at the back, where the fall
arrives); the glow from below (caustics decal on the bed + an underwater uplight in kz_lights).

Concepts: lookbook 32 (suite plan: the private stone onsen and the overflow plunge below, ~3-4 m across
against the 0-5 m bar, boulders 0.3-0.6 m around a teal lit pool; elevation: small lit pools at the foot
of each fall), 19 (the Thunder plunge, far larger: r up to 12 m), 31 (ground plan: plunge pools at the
road falls). Targets: outer 4.0 x 4.0 m (proxy), kerb top 0.38 m, water 0.33 m deep at default (0.05 m
freeboard), 14-17 boulders 0.55-0.95 m long, 0.17-0.28 m high, top 0.60-0.64 m; kerb 0.40 m wide.
Proxy 4 x 4 x 0.6 (3d/assets.json): fits within the 5 % tolerance (boulders kept as large as it allows). The pool is meant to be set into grade: the bed is z = 0,
grade is the kerb foot (kz_grade_z = 0 for a free-standing kerb; sink by `depth` for a dug-in pool).

Parameters:
  r       1.5-12   outer radius incl. boulders (default 1.72-2.0, seeded)
  depth   0.25-1.5 water depth (default 0.33)
  ring    6-40     boulder count (default 10-14 at r 2, scales with the perimeter)
  steps   bool     two seat steps on the front (+Y) side (seed 1, 3 on; seed 2 off)
Seeds change: r, plan aspect 0.85-1.15 and lobes, boulder count, sizes and spacing, seat steps on/off.

Construction: one polar-grid shell (outer batter -> rounded kerb top -> inner wall -> dished bed -> pole),
noise-displaced; hull boulders seated 35 % into the kerb; annular-sector seat steps; a caustics_decal
disc 12 mm over the bed. LOD3 keeps the ring as lumps in the kerb (no separate boulders).
Materials (slots by part): kerb top basalt_wet 0.95, kerb side 0.55, inner wall + bed 0.85, boulders
basalt_wet 0.7, steps basalt_wet 0.9, glow caustics_decal. Water: kz_water_level / kz_water_outline only.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_plunge_basin as P

ASSET = 'plunge_basin'
FEATURES = ['round basin of churning water', 'ring of black wet boulders on the kerb', 'glow from below']


def layout(seed, r=None, depth=None, ring=None, steps=None):
    g = C.rng(seed, 'dims')
    L = {}
    L['r'] = r if r is not None else g.uniform(1.72, 2.0)
    L['depth'] = depth if depth is not None else 0.33
    L['rim_z'] = L['depth'] + 0.05
    L['rw'] = 0.32 + 0.04 * L['r']
    L['Rb'] = L['r'] - 0.18 * min(L['r'], 3.0) / 2
    go = C.rng(seed, 'outline')
    L['outline'] = C.stone_outline(go, L['Rb'], aspect=go.uniform(0.85, 1.15),
                                   harmonics=((2, 0.03), (3, 0.04), (5, 0.025), (7, 0.012)), bites=0, rot=0.0)
    L['steps'] = steps if steps is not None else (seed % 3 != 2)
    gn = C.rng(seed, 'noise')
    L['off'] = Vector((gn.uniform(0, 90), gn.uniform(0, 90), gn.uniform(0, 90)))
    # boulders
    gb = C.rng(seed, 'ring')
    sc = max(0.8, min(2.5, L['r'] / 2.0))
    n = ring if ring is not None else int(round(gb.randint(14, 17) * L['r'] / 2.0))
    n = max(6, n)
    gap = (math.radians(90), 0.42) if L['steps'] else None
    B = []
    land = math.radians(270)
    for k in range(n):
        th = 2 * math.pi * (k + gb.uniform(-0.22, 0.22)) / n + math.radians(gb.uniform(0, 10))
        d_land = abs(math.atan2(math.sin(th - land), math.cos(th - land)))
        sx = gb.uniform(0.28, 0.40) * sc
        sy = gb.uniform(0.22, 0.30) * sc
        sz = gb.uniform(0.15, 0.2) * sc
        if d_land < 0.6:
            sx *= 1.15; sz = min(0.22 * sc, sz * 1.2)
        if gap and abs(math.atan2(math.sin(th - gap[0]), math.cos(th - gap[0]))) < gap[1]:
            continue                                         # the seat-step side stays open
        B.append(dict(th=th, sx=sx, sy=sy, sz=sz, rot=th + math.pi / 2 + gb.uniform(-0.3, 0.3), roff=gb.uniform(0.3, 0.6)))
    L['boulders'] = B
    return L


def rim_xy(L, th, off):
    x, y = L['outline'](th)
    R = math.hypot(x, y)
    return x / R * (R - off), y / R * (R - off)


def build(lod=0, seed=1, r=None, depth=None, ring=None, steps=None):
    L = layout(seed, r, depth, ring, steps)
    mb = genlib.MeshBuilder()
    m_top = mb.slot('basalt_wet', wetness=0.95, roughness_offset=-0.04)
    m_side = mb.slot('basalt_wet', wetness=0.55)
    m_in = mb.slot('basalt_wet', wetness=0.85)
    m_bould = mb.slot('basalt_wet', wetness=0.7)
    m_step = mb.slot('basalt_wet', wetness=0.9)
    m_glow = mb.slot('caustics_decal')
    rz, rw, dp = L['rim_z'], L['rw'], L['depth']
    B = L['boulders']

    def lumps(th):
        if lod < 3:
            return 0.0
        z = 0.0
        for b in B:
            d = abs(math.atan2(math.sin(th - b['th']), math.cos(th - b['th'])))
            z = max(z, b['sz'] * 1.1 * max(0.0, 1 - d / (0.9 * 2 * math.pi / max(len(B), 1))))
        return z
    zt = lambda th: rz + lumps(th)
    rows_all = {
        0: [(1, 0.0, 0.0, 'out'), (1, 0.03, 0.4 * rz, 'out'), (1, 0.07, 0.78 * rz, 'out'), (1, 0.13, rz - 0.015, 'top'),
            (1, 0.2, zt, 'top'), (1, rw - 0.07, zt, 'top'), (1, rw - 0.01, lambda t: zt(t) - 0.03, 'top'),
            (1, rw + 0.03, rz - 0.12, 'in'), (1, rw + 0.08, 0.55 * dp, 'in'), (1, rw + 0.17, 0.2 * dp, 'in'),
            (1, rw + 0.38, 0.06, 'bed'), (0.62, 0.0, 0.035, 'bed'), (0.32, 0.0, 0.01, 'bed'), (0, 0, 0.0, 'bed')],
        1: [(1, 0.0, 0.0, 'out'), (1, 0.06, 0.65 * rz, 'out'), (1, 0.15, rz - 0.01, 'top'), (1, rw - 0.07, zt, 'top'),
            (1, rw + 0.02, rz - 0.1, 'in'), (1, rw + 0.12, 0.35 * dp, 'in'), (1, rw + 0.38, 0.06, 'bed'),
            (0.5, 0.0, 0.02, 'bed'), (0, 0, 0.0, 'bed')],
        2: [(1, 0.0, 0.0, 'out'), (1, 0.12, rz - 0.01, 'top'), (1, rw - 0.04, zt, 'top'), (1, rw + 0.1, 0.3 * dp, 'in'),
            (0.55, 0.0, 0.02, 'bed'), (0, 0, 0.0, 'bed')],
        3: [(1, 0.0, 0.0, 'out'), (1, 0.12, zt, 'top'), (1, rw, zt, 'top'), (1, rw + 0.15, 0.2 * dp, 'in'), (0, 0, 0.0, 'bed')],
    }
    rows = rows_all[lod]
    N = C.lod_pick(lod, 64, 30, 16, 8)
    amp = C.lod_pick(lod, 0.03, 0.025, 0.0, 0.0)

    def disp(th, j, tag, p):
        if amp == 0 or tag == 'bed' or p.z < 0.01:
            return Vector()
        n = noise.noise(p * 3.0 + L['off']) + 0.4 * noise.noise(p * 7.0 + L['off'])
        x, y = math.cos(th), math.sin(th)
        sgn = 1 if tag == 'out' else -1
        return Vector((x * sgn * amp * n, y * sgn * amp * n, 0.3 * amp * n * (tag == 'top')))

    def mi_fn(j, t0, t1, th):
        if t0 == 'top' and t1 == 'top':
            return m_top
        if t0 == 'out':
            return m_side
        return m_in
    P.polar_basin(mb, L['outline'], N, rows, mi_fn, disp=disp)

    # glow decal on the bed (the "lit from below" read)
    Nd = C.lod_pick(lod, 24, 16, 10, 6)
    bm = mb.bm
    cen = bm.verts.new((0, 0, 0.012))
    ring = []
    for i in range(Nd):
        th = 2 * math.pi * i / Nd
        x, y = L['outline'](th)
        ring.append(bm.verts.new((x * 0.42, y * 0.42, 0.03 * 0.42 + 0.012)))
    for i in range(Nd):
        f = bm.faces.new((cen, ring[i], ring[(i + 1) % Nd])); f.material_index = m_glow

    # boulders on the kerb (LOD0-2: all of them, fewer facets; LOD3: kerb lumps)
    if lod < 3:
        npts = C.lod_pick(lod, 14, 10, 6)
        for b in B:
            x, y = rim_xy(L, b['th'], rw * b['roff'])
            g = C.rng(seed, f"b{round(b['th'], 4)}")
            C.hull_rock(mb, (x, y, rz + 0.2 * b['sz']), (b['sx'], b['sy'], b['sz']), m_bould, g, npts=npts,
                        ground=rz - 0.06, rot=b['rot'], rmin=0.8)
    # seat steps on the front
    if L['steps'] and lod < 3:
        n = C.lod_pick(lod, 6, 3, 2)
        a0, a1 = math.radians(90) - 0.5, math.radians(90) + 0.5
        P.sector_slab(mb, L['outline'], a0, a1, rw - 0.02, rw + 0.42, 0.0, 0.62 * dp, n, m_step)
        P.sector_slab(mb, L['outline'], a0 + 0.08, a1 - 0.08, rw + 0.40, rw + 0.80, 0.0, 0.3 * dp, n, m_step)

    import bmesh
    bmesh.ops.recalc_face_normals(mb.bm, faces=mb.bm.faces[:])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    ol = []
    for k in range(32):
        th = 2 * math.pi * k / 32
        x, y = rim_xy(L, th, rw - 0.02)
        ol.append((x + dx, y + dy))
    lx, ly = rim_xy(L, math.radians(270), rw + 0.6)
    C.water_props(o, level_z=dp + dz, outline_xy=ol, kz_fall_landing=[round(lx + dx, 3), round(ly + dy, 3)],
                  kz_water_fx='fx_water_surface churn')
    C.set_json_props(o, kz_lights=[C.light_entry((dx, dy, 0.08 + dz), color_k=6500, watts=40, kind='point',
                                                 color=[0.35, 0.95, 0.9], role='underwater uplight')],
                     kz_params=dict(r=round(L['r'], 3), depth=dp, ring=len(B), steps=bool(L['steps'])))
    return o
