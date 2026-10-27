"""Cascade terrace pool: one stepped, scalloped teal pool whose wet black stone lip spills into the next.

Identifying features kept at every LOD: the scalloped (lobed) front edge; the wet black polished stone
lip running round the rim with a lower spill section where the water leaves; the pale sinter bowl that
reads teal under the water; the outer front face (rimstone drapery, black crag or a stepped ledge).

Concepts: lookbook 01 (hero: lobed teal pools stepping down the slope, black wet lips with curtains
over them, each step ~0.8-1.2 m against the 1.7 m bathers), 31 (ground plan B5: pools ~6-10 m across
in a chain), 30 (summit cascade terraces, same generator), refs/gen/sheet-ref-ground.png 03 (terrace
path: lobed pools, white curtains over dark lips), refs/gen/sheet-mod-water.png #2 Rimstone Terrace
(8 m W x 6 m D; round lobed pools, cream fluted rimstone drapery under the lip; the lip itself reads
as a thin dark band at the brim, 0.25-0.3 m at the 1 m bar).
Targets: 8.0 x 6.0 m footprint (proxy), rim 0.83 m (= depth 0.8 + 0.03), lip band 0.28 m wide at the
front, spill dip 45 mm over 0.8-2.2 m, water 15 mm over the spill lip, 3-5 front scallops with
9-12 % lobes, drapery flutes every ~0.36 m bulging 0.04 -> 0.2 m towards the foot.
Proxy 8 x 6 x 0.8 (3d/assets.json): fits at depth 0.8 (depth 1.2 makes it 1.23 m tall: a parameter).

Parameters:
  w, d         footprint (default 7.2-7.8 x 5.2-5.8, seeded)
  depth        0.8-1.2 water depth (rim_z = depth + 0.03)
  lip          'drape' | 'basalt' | 'stepped'  outer front face (cycles with the seed: 1 drape, 2 basalt,
               3 stepped, 4 drape)
  spills       1-2, spill_w 0.8-2.2 m
  deck         bool: a 0.75 m flat basalt deck ledge round the back half (seeds 2, 4)
  scallops     3-5 lobes on the front
Seeds change: lip style, scallop count and depth, aspect, spill count / width / position, deck ledge.

Construction: one polar-grid shell (outer face -> rounded lip -> inner wall -> sinter bed -> pole), the
front outer rows displaced into flutes / crag / a step; the rim dips at each spill. No boulders: the
proxy height leaves no room and the concept's flanking rocks belong to the terrace setting.
Materials (slots by part): lip = basalt_wet 0.98 polish -0.06; deck = basalt_wet 0.8; outer front =
rimstone (drape) or basalt_wet 0.6; outer back/sides = basalt_wet 0.55; bowl (wall + bed) = sinter.
Water: kz_water_level / kz_water_outline; kz_spills (lip polylines for fx_falls_sheet); none in mesh.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_plunge_basin as P
from kzgeo_falls_lip_rock import smoothstep

ASSET = 'cascade_pool'
FEATURES = ['scalloped lobed front edge', 'wet black stone lip with a spill section', 'pale sinter bowl (teal under water)',
            'outer front face: rimstone drapery / crag / step']
LIPS = ['drape', 'basalt', 'stepped', 'drape']


def adiff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def layout(seed, w=None, d=None, depth=None, lip=None, spills=None, spill_w=None, deck=None, scallops=None):
    g = C.rng(seed, 'dims')
    L = {}
    L['a'] = (w if w is not None else g.uniform(7.2, 7.8)) / 2
    L['b'] = (d if d is not None else g.uniform(5.2, 5.8)) / 2
    L['depth'] = depth if depth is not None else 0.8
    L['rz'] = L['depth'] + 0.03
    L['lip'] = lip or C.cycle(seed, LIPS)
    L['deck'] = deck if deck is not None else (seed % 2 == 0)
    gs = C.rng(seed, 'scallop')
    L['nsc'] = scallops if scallops is not None else gs.randint(3, 5)
    L['A'] = gs.uniform(0.09, 0.12)
    L['ph'] = [(k, gs.uniform(0, 6.28), gs.uniform(0.015, 0.03)) for k in (2, 3, 5)]
    gp = C.rng(seed, 'spill')
    ns = spills if spills is not None else gp.choice([1, 1, 2])
    L['spills'] = []
    for k in range(ns):
        wsp = spill_w if spill_w is not None else gp.uniform(0.8, 2.2)
        th = math.pi / 2 + (gp.uniform(-0.5, 0.5) if ns == 1 else (-0.55 + 1.1 * k) + gp.uniform(-0.12, 0.12))
        L['spills'].append((th, wsp))
    gn = C.rng(seed, 'noise')
    L['off'] = Vector((gn.uniform(0, 90), gn.uniform(0, 90), gn.uniform(0, 90)))
    L['dip'] = 0.045
    return L


def outline_fn(L):
    a, b, n, A = L['a'], L['b'], L['nsc'], L['A']

    def f(th):
        c, s = math.cos(th), math.sin(th)
        R = 1.0 / math.sqrt((c / a) ** 2 + (s / b) ** 2)
        wf = max(0.0, s) ** 0.5
        lobe = abs(math.sin(n * th)) ** 0.7
        k = 1 + A * wf * (lobe - 0.55) + sum(amp * math.sin(m * th + ph) for m, ph, amp in L['ph']) * (1 - wf)
        R *= k
        return R * c, R * s
    return f


def build(lod=0, seed=1, w=None, d=None, depth=None, lip=None, spills=None, spill_w=None, deck=None, scallops=None):
    L = layout(seed, w, d, depth, lip, spills, spill_w, deck, scallops)
    f = outline_fn(L)
    mb = genlib.MeshBuilder()
    m_lip = mb.slot('basalt_wet', wetness=0.98, roughness_offset=-0.06)
    m_deck = mb.slot('basalt_wet', wetness=0.8)
    m_front = mb.slot('rimstone') if L['lip'] == 'drape' else mb.slot('basalt_wet', wetness=0.6)
    m_side = mb.slot('basalt_wet', wetness=0.55)
    m_bowl = mb.slot('sinter', wetness=0.6)
    rz, dp = L['rz'], L['depth']

    def front(th):
        return smoothstep(0.05, 0.45, math.sin(th))

    def rw(th):
        base = 0.28 + 0.07 * (1 - front(th))
        if L['deck']:
            base += 0.45 * smoothstep(0.0, 0.5, -math.sin(th))
        return base

    def spill_w8(th):
        v = 0.0
        for ths, wsp in L['spills']:
            x, y = f(ths)
            hw = wsp / 2 / math.hypot(x, y)
            v = max(v, 1 - smoothstep(hw * 0.75, hw * 1.15, abs(adiff(th, ths))))
        return v

    def zrim(th, drop=0.0):
        return rz - L['dip'] * spill_w8(th) - drop + 0.006 * noise.noise(Vector((math.cos(th) * 3, math.sin(th) * 3, 1.0)) + L['off'])
    rows_all = {
        0: [(1, 0.0, 0.0, 'out'), (1, 0.0, 0.2 * rz, 'out'), (1, 0.01, 0.42 * rz, 'out'), (1, 0.02, 0.62 * rz, 'out'),
            (1, 0.03, 0.8 * rz, 'out'), (1, 0.04, lambda t: zrim(t, 0.05), 'lip'), (1, 0.09, zrim, 'lip'),
            (1, lambda t: rw(t) - 0.08, zrim, 'lip'), (1, lambda t: rw(t) - 0.02, lambda t: zrim(t, 0.03), 'lip'),
            (1, lambda t: rw(t) + 0.02, rz - 0.13, 'in'), (1, lambda t: rw(t) + 0.06, 0.55 * rz, 'in'),
            (1, lambda t: rw(t) + 0.15, 0.2 * rz, 'in'), (1, lambda t: rw(t) + 0.45, 0.04, 'bed'),
            (0.6, 0.0, 0.02, 'bed'), (0.3, 0.0, 0.005, 'bed'), (0, 0, 0.0, 'bed')],
        1: [(1, 0.0, 0.0, 'out'), (1, 0.01, 0.3 * rz, 'out'), (1, 0.02, 0.62 * rz, 'out'), (1, 0.04, lambda t: zrim(t, 0.05), 'lip'),
            (1, 0.1, zrim, 'lip'), (1, lambda t: rw(t) - 0.04, zrim, 'lip'), (1, lambda t: rw(t) + 0.04, rz - 0.15, 'in'),
            (1, lambda t: rw(t) + 0.14, 0.25 * rz, 'in'), (1, lambda t: rw(t) + 0.45, 0.04, 'bed'), (0.5, 0.0, 0.01, 'bed'),
            (0, 0, 0.0, 'bed')],
        2: [(1, 0.0, 0.0, 'out'), (1, 0.02, 0.55 * rz, 'out'), (1, 0.06, zrim, 'lip'), (1, lambda t: rw(t), zrim, 'lip'),
            (1, lambda t: rw(t) + 0.12, 0.3 * rz, 'in'), (0.6, 0.0, 0.02, 'bed'), (0, 0, 0.0, 'bed')],
        3: [(1, 0.0, 0.0, 'out'), (1, 0.06, zrim, 'lip'), (1, lambda t: rw(t), zrim, 'lip'), (1, lambda t: rw(t) + 0.15, 0.2 * rz, 'in'),
            (0, 0, 0.0, 'bed')],
    }
    rows = rows_all[lod]
    N = C.lod_pick(lod, 180, 96, 36, 14)
    nfl = max(8, int(2 * math.pi * (L['a'] + L['b']) / 2 / 0.36))
    flute_on = lod <= 1

    def disp(th, j, tag, p):
        if tag != 'out':
            return Vector()
        fr = front(th)
        ux, uy = math.cos(th), math.sin(th)
        zf = p.z / rz
        if L['lip'] == 'drape':
            fl = (0.5 + 0.5 * math.cos(nfl * th)) ** 2 if flute_on else 0.5
            o = fr * (0.04 + 0.16 * (1 - zf) ** 1.5) * (0.55 + 0.45 * fl)
            o += 0.015 * noise.noise(p * 4 + L['off']) * (lod == 0)
        elif L['lip'] == 'stepped':
            o = fr * 0.28 * (1 - smoothstep(0.38, 0.5, zf))
            o += 0.03 * noise.noise(p * 2.5 + L['off']) * (lod <= 1)
        else:
            o = 0.06 * fr * noise.noise(p * 1.8 + L['off']) * (lod <= 1) + 0.05 * fr * (1 - zf)
        o += 0.02 * (1 - fr) * noise.noise(p * 2 + L['off']) * (lod <= 1)
        return Vector((ux * o, uy * o, 0.0))

    def mi_fn(j, t0, t1, th):
        if t0 == 'lip' and t1 == 'lip':
            return m_deck if (L['deck'] and math.sin(th) < -0.25) else m_lip
        if t0 == 'out':
            if t1 == 'lip' and lod < 2:
                return m_lip
            return m_front if front(th) > 0.5 else m_side
        return m_bowl
    P.polar_basin(mb, f, N, rows, mi_fn, disp=disp, phase=math.pi / N)
    import bmesh
    bmesh.ops.recalc_face_normals(mb.bm, faces=mb.bm.faces[:])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    lvl = rz - L['dip'] + 0.015
    ol = []
    for k in range(48):
        th = 2 * math.pi * k / 48
        x, y = f(th); R = math.hypot(x, y); r_ = R - rw(th) + 0.01
        ol.append((x / R * r_ + dx, y / R * r_ + dy))
    sp = []
    for ths, wsp in L['spills']:
        x, y = f(ths); hw = wsp / 2 / math.hypot(x, y)
        lipl = []
        for k in range(7):
            th = ths - hw * 0.8 + 1.6 * hw * k / 6
            x, y = f(th); R = math.hypot(x, y)
            lipl.append([round(x / R * (R + 0.02) + dx, 3), round(y / R * (R + 0.02) + dy, 3), round(zrim(th) + 0.012 + dz, 3)])
        sp.append(dict(lip=lipl, width=round(wsp, 3), to=0.0, fx='fx_falls_sheet'))
    C.water_props(o, level_z=lvl + dz, outline_xy=ol, kz_spills=sp)
    C.set_json_props(o, kz_params=dict(w=round(2 * L['a'], 3), d=round(2 * L['b'], 3), depth=dp, lip=L['lip'],
                                       spills=len(L['spills']), deck=bool(L['deck']), scallops=L['nsc']))
    return o
