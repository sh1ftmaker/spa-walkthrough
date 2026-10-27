"""Upper cascade terraces (cascade_terrace_upper): the far-tier version of cascade_pool for the chain of teal
pools stepping down the south face beside the Terrace Path (summit -> ground).

One build() = ONE terrace unit (budget is per pool): a lobed teal pool whose wet black lip spills over the
front, sitting on its own terrace step - the outer front face drops `step_h` to the next terrace (crag /
rimstone drapery / ledge), the back sits flush in the slope. `pools=n` builds a chain of n units stepping
down and zig-zagging (for the canonical and for placement previews; the scene places units one by one).

Concepts: lookbook 30 (summit plan A3-C5 'Cascade Terraces +120 -> 0 m': ~6 lobed pools in a chain, each
~10-14 m x 6-8 m at the 20 m grid = 150 px, falls between them), lookbook 01 (hero: lobed teal pools,
dark wet lips with white curtains, each step ~0.8-1.5 m against 1.7 m bathers on the lower terraces;
higher up the drops grow), refs/gen/sheet-ref-ground.png #03 'Terrace Path' (lobed pools stepping down a
steep face, black crag fronts 2-3 m tall with white curtains, the stair path beside them).
Targets: pool 8.5-11 x 5.5-7 m (seeded), water depth 0.8 m, rim 0.83 m, lip band 0.3 m, 3-5 front lobes,
front drop step_h 1.6-2.6 m (seeded), spill dip 45 mm over 1.2-3 m (1-2 spills), so a unit is about
11 x 7 x 3.4 m. Same construction as gen_cascade_pool (layout + outline reused), rows thinned for the
far tier and the outer face extended down the step.

Parameters: w, d (footprint), depth (0.8), step_h 1.2-3.0, lip 'basalt' | 'drape' | 'stepped' (cycles
with the seed: 1 basalt crag front like ref-ground #03, 2 rimstone drapery like lookbook 01, 3 stepped
ledge), spills 1-2, scallops 3-5, pools (chain length, default 1).
Seeds change: front style, footprint/aspect, lobe count/depth, spill count/position, step height.

Materials (slots by part): lip basalt_wet 0.98 polish -0.06; front face basalt_wet 0.6 (or rimstone for
'drape'); back/side face basalt_wet 0.5; bowl sinter (teal under water). water_still is runtime only.
Water: kz_water_level / kz_water_outline and kz_pools (one entry per unit) + kz_spills (lip polylines
for fx_falls_sheet, 'to' = the foot of the step); no water mesh in build(). Animation: shader (spill
sheets, fx side). Lighting: lightmap.
Budget per pool 2000 / 800 / 240 / 60.
"""
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_plunge_basin as P
from kzgeo_falls_lip_rock import smoothstep
import gen_cascade_pool as CP

ASSET = 'cascade_terrace_upper'
FEATURES = ['chain of lobed teal pools stepping down', 'wet black lip with spill', 'dark front step face',
            'pale sinter bowl (teal under water)']
STYLES = ['basalt', 'drape', 'stepped']
PROXY_SHEET = dict(w=11.6, d=7.6, h=3.6)      # proposed (no proxy in assets.json): one unit


def unit(mb, seed, lod, slots, w=None, d=None, depth=None, step_h=None, lip=None, spills=None, scallops=None,
         origin=(0.0, 0.0, 0.0)):
    g = C.rng(seed, 'terrace')
    w = w if w is not None else g.uniform(8.5, 11.0)
    d = d if d is not None else g.uniform(5.5, 7.0)
    sh = step_h if step_h is not None else g.uniform(1.6, 2.6)
    style = lip or C.cycle(seed, STYLES)
    L = CP.layout(seed, w=w, d=d, depth=depth, lip=style, spills=spills, spill_w=None, deck=False, scallops=scallops)
    L['spills'] = [(th, max(1.2, wsp * 1.4)) for th, wsp in L['spills']]
    f = CP.outline_fn(L)
    rz = L['rz']
    ox, oy, oz = origin

    def front(th):
        return smoothstep(-0.1, 0.5, math.sin(th))

    def zfoot(th):
        return -sh * front(th)

    def rw(th):
        return 0.30 + 0.06 * (1 - front(th))

    def spill_w8(th):
        v = 0.0
        for ths, wsp in L['spills']:
            x, y = f(ths)
            hw = wsp / 2 / math.hypot(x, y)
            v = max(v, 1 - smoothstep(hw * 0.75, hw * 1.15, abs(CP.adiff(th, ths))))
        return v

    def zrim(th, drop=0.0):
        return rz - L['dip'] * spill_w8(th) - drop
    # rows: outer foot (down the step) -> face -> lip -> inner wall -> bed -> pole
    face = lambda k: (lambda t: zfoot(t) + (0.0 - zfoot(t)) * k)
    rows_all = {
        0: [(1, -0.35, zfoot, 'foot'), (1, -0.22, face(0.35), 'out'), (1, -0.1, face(0.7), 'out'), (1, 0.0, 0.0, 'out'),
            (1, 0.02, 0.5 * rz, 'out'), (1, 0.04, lambda t: zrim(t, 0.05), 'lip'), (1, 0.1, zrim, 'lip'),
            (1, lambda t: rw(t) - 0.04, zrim, 'lip'), (1, lambda t: rw(t) + 0.04, rz - 0.15, 'in'),
            (1, lambda t: rw(t) + 0.16, 0.25 * rz, 'in'), (1, lambda t: rw(t) + 0.5, 0.04, 'bed'), (0.5, 0.0, 0.01, 'bed'),
            (0, 0, 0.0, 'bed')],
        1: [(1, -0.35, zfoot, 'foot'), (1, -0.15, face(0.55), 'out'), (1, 0.0, 0.0, 'out'), (1, 0.04, lambda t: zrim(t, 0.05), 'lip'),
            (1, lambda t: rw(t), zrim, 'lip'), (1, lambda t: rw(t) + 0.14, 0.3 * rz, 'in'), (0.55, 0.0, 0.02, 'bed'), (0, 0, 0.0, 'bed')],
        2: [(1, -0.3, zfoot, 'foot'), (1, 0.0, 0.2 * rz, 'out'), (1, 0.06, zrim, 'lip'), (1, lambda t: rw(t), zrim, 'lip'),
            (1, lambda t: rw(t) + 0.15, 0.3 * rz, 'in'), (0, 0, 0.0, 'bed')],
        3: [(1, -0.3, zfoot, 'foot'), (1, 0.05, zrim, 'lip'), (1, lambda t: rw(t) + 0.15, 0.4 * rz, 'in'), (0, 0, 0.0, 'bed')],
    }
    rows = rows_all[lod]
    N = C.lod_pick(lod, 72, 52, 20, 8)
    m_lip, m_front, m_side, m_bowl = slots['lip'], slots['front_' + style], slots['side'], slots['bowl']
    nfl = max(8, int(2 * math.pi * (L['a'] + L['b']) / 2 / 0.45))

    def disp(th, j, tag, p):
        if tag not in ('out', 'foot'):
            return Vector()
        fr = front(th)
        ux, uy = math.cos(th), math.sin(th)
        zf = max(0.0, min(1.0, (p.z + sh) / (sh + rz)))
        if style == 'drape':
            fl = (0.5 + 0.5 * math.cos(nfl * th)) ** 2 if lod <= 1 else 0.5
            o = fr * (0.06 + 0.3 * (1 - zf) ** 1.5) * (0.55 + 0.45 * fl)
        elif style == 'stepped':
            o = fr * 0.45 * (1 - smoothstep(0.42, 0.55, zf))
            o += 0.06 * noise.noise(p * 1.2 + L['off']) * (lod <= 1)
        else:
            o = fr * (0.16 * noise.noise(p * 0.9 + L['off']) * (lod <= 2) + 0.12 * (1 - zf))
        o += 0.05 * (1 - fr) * noise.noise(p * 1.3 + L['off']) * (lod <= 1)
        return Vector((ux * o, uy * o, 0.0))

    def mi_fn(j, t0, t1, th):
        if t0 == 'lip' and t1 == 'lip':
            return m_lip
        if t0 in ('out', 'foot'):
            if t1 == 'lip' and t0 == 'out':
                return m_lip
            return m_front if front(th) > 0.45 else m_side
        return m_bowl
    lay = mb._mark_old()
    P.polar_basin(mb, f, N, rows, mi_fn, disp=disp, phase=math.pi / N)
    new = mb._new_faces(lay)
    vs = list({v for fc in new for v in fc.verts})
    for v in vs:
        v.co += Vector(origin)
    lvl = rz - L['dip'] + 0.015
    ol = []
    for k in range(40):
        th = 2 * math.pi * k / 40
        x, y = f(th); R = math.hypot(x, y); r_ = R - rw(th) + 0.01
        ol.append((x / R * r_ + ox, y / R * r_ + oy))
    sp = []
    for ths, wsp in L['spills']:
        x, y = f(ths); hw = wsp / 2 / math.hypot(x, y)
        lipl = []
        for k in range(7):
            th = ths - hw * 0.8 + 1.6 * hw * k / 6
            x, y = f(th); R = math.hypot(x, y)
            lipl.append([x / R * (R + 0.02) + ox, y / R * (R + 0.02) + oy, zrim(th) + 0.012 + oz])
        sp.append(dict(lip=lipl, width=round(wsp, 3), to=oz - sh, fx='fx_falls_sheet'))
    return dict(level=lvl + oz, outline=ol, spills=sp, w=2 * L['a'], d=2 * L['b'], step_h=sh, style=style,
                scallops=L['nsc'], b=L['b'])


def build(lod=0, seed=1, w=None, d=None, depth=None, step_h=None, lip=None, spills=None, scallops=None, pools=1):
    mb = genlib.MeshBuilder()
    slots = dict(lip=mb.slot('basalt_wet', wetness=0.98, roughness_offset=-0.06),
                 front_basalt=mb.slot('basalt_wet', wetness=0.6), front_stepped=mb.slot('basalt_wet', wetness=0.6),
                 front_drape=mb.slot('rimstone'), side=mb.slot('basalt_wet', wetness=0.5),
                 bowl=mb.slot('sinter', wetness=0.6))
    units = []
    origin = [0.0, 0.0, 0.0]
    gc = C.rng(seed, 'chain')
    for k in range(pools):
        s_k = seed if k == 0 else seed * 37 + k
        u = unit(mb, s_k, lod, slots, w if k == 0 else None, d if k == 0 else None, depth, step_h if k == 0 else None,
                 lip if lip else (None if k == 0 else C.cycle(seed, STYLES)), spills, scallops, origin=tuple(origin))
        units.append(u)
        # next unit: down the step, forward (+Y), zig-zag sideways
        origin = [origin[0] + gc.uniform(1.5, 3.0) * (1 if k % 2 == 0 else -1), origin[1] + u['b'] * 1.7,
                  origin[2] - u['step_h']]
    bmesh.ops.recalc_face_normals(mb.bm, faces=mb.bm.faces[:])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    pl = []
    for u in units:
        pl.append(dict(level=round(u['level'] + dz, 4), outline=[[round(x + dx, 3), round(y + dy, 3)] for x, y in u['outline']]))
        for s in u['spills']:
            s['lip'] = [[round(p[0] + dx, 3), round(p[1] + dy, 3), round(p[2] + dz, 3)] for p in s['lip']]
            s['to'] = round(s['to'] + dz, 3)
    u0 = units[0]
    C.water_props(o, level_z=pl[0]['level'], outline_xy=pl[0]['outline'], kz_pools=pl,
                  kz_spills=[s for u in units for s in u['spills']])
    C.set_json_props(o, kz_anim=dict(type='shader', what='spill sheets over each lip (fx_falls_sheet)'),
                     kz_params=dict(pools=pools, w=round(u0['w'], 3), d=round(u0['d'], 3), step_h=round(u0['step_h'], 3),
                                    lip=u0['style'], scallops=u0['scallops'], spills=len(u0['spills'])))
    return o
