"""Cliff shrub clump: a low rounded evergreen shrub clinging to a basalt ledge.

Identifying features kept at every LOD: a low, rounded, lumpy foliage dome sitting on (or spilling off) dark
wet rock.
Concept: refs/gen/sheet-vs-nature-2.png #6 "Cliff shrub clump" (W 1.2 x D 1.2 x H 0.8 m label; 290 px/m bar):
drawn 0.91 w x 0.86 h; a broad dome of leafy rosettes (~0.9 w x 0.45 h) sits on a craggy black basalt mound
~0.45 m high, exposed roots run down the rock faces, moss in the rock seams.  Lookbook 32 / 01 / 30 (shrubs
dotted along the cliff ledges, mostly seen at 10-40 m: the dome-on-rock silhouette is what reads).

Targets (proxy 1.2 x 1.2 x 0.8): spread 0.9-1.15 m (seeded 0.75-0.95 x proxy w; param 0.5-2 m), h <= 0.8 m.
  style 'rock'  : 3-4 faceted basalt rocks, main rock 0.38-0.48 m high; foliage dome 2-3 lumps, R 0.28-0.42,
                  T 0.55-0.7 R (rounded), dome base sunk 0.05 m into the rock top; 4 roots down the rock.
  style 'ledge' : 3-5 lumps on the ground, the clump lower and wider (h 0.45-0.65), 1-2 small rocks at the foot,
                  one lump spilling forward / down (the cliff-edge overhang), 3 short stems.
Styles cycle with the seed: 1 rock, 2 ledge, 3 rock, 4 ledge.  colour green | olive | dark (seeded).
Seeds change: style, spread, lump count / sizes / layout, rock count and shape, colour.
Parameters: spread 0.5-2 m, density 0.5-1.5 (card density), colour, style.

Materials: leaf cards `foliage_pine` (alpha, double-sided; tinted per colour), dome core `moss` darkened,
  rocks `basalt_wet` (cooled), roots `bark`, seam moss `moss`.
LOD: one layout.  LOD0 cores 9 seg + ~230 cards; LOD1 7 seg + ~70 larger cards; LOD2 6-seg lens cores + a few
  big cards, rocks 7-pt hulls, no roots; LOD3 one merged dome lens + the main rock.
Animation: `kz_sway` colour attribute (R 0 at the rock -> 0.6-1 over the dome, G phase per lump, B 1 on
  foliage) + vertex group `sway`.  kz_sway_default_indoor = 0.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_groundcover as P
from gen_groundcover import cushion

ASSET = 'shrub_clump'
FEATURES = ['low rounded foliage dome', 'clinging to dark basalt ledge']
STYLES = ['rock', 'ledge']
COLOURS = {'green': ((1.0, 1.0, 1.0), (0.45, 0.55, 0.32)),
           'olive': ((1.15, 1.05, 0.7), (0.5, 0.52, 0.3)),
           'dark': ((0.72, 0.85, 0.75), (0.34, 0.44, 0.3))}
ROCK_TINT = (0.32, 0.36, 0.46)


def layout(seed, spread, style):
    g = C.rng(seed, 'layout')
    k = spread / 1.0
    L = dict(style=style, spread=spread)
    rr = C.rng(seed, 'rocks')
    rocks, lumps, roots = [], [], []
    if style == 'rock':
        H = rr.uniform(0.38, 0.48) * min(1.2, k)
        RX, RY = 0.46 * k, 0.4 * k
        rocks.append(dict(c=(0, 0, 0), s=(RX, RY, H), npts=14, seed=rr.random()))
        for j in range(rr.randint(2, 3)):
            a = rr.uniform(0, 2 * math.pi)
            s = rr.uniform(0.16, 0.24) * k
            rocks.append(dict(c=(math.cos(a) * 0.32 * k, math.sin(a) * 0.28 * k, 0), s=(s * 1.2, s, s * rr.uniform(0.9, 1.4)),
                              npts=11, seed=rr.random()))
        # the dome core sinks into the rock top (its flat underside hidden in the rock); foliage hangs over
        # the upper half of the rock faces like sheet #6
        zc = H * 0.66
        lr = C.rng(seed, 'lumps')
        n = lr.randint(2, 3)
        for j in range(n):
            a = 2 * math.pi * j / n + lr.uniform(-0.4, 0.4)
            R = lr.uniform(0.27, 0.34) * k * (1.0 if j == 0 else 0.8)
            off = 0.0 if j == 0 else lr.uniform(0.16, 0.24) * k
            lumps.append(dict(c=(math.cos(a) * off, math.sin(a) * off, zc - (0.05 if j else 0)),
                              R=R, T=(H - zc) + R * lr.uniform(0.55, 0.75), flat=lr.uniform(1.0, 1.2), ph=lr.random(),
                              seed=lr.random()))

        def on_rock(a, z):                       # a point on the main rock's shell (hull radius ~0.82-1.0)
            q = max(0.0, 1 - ((z - H / 2) / (0.55 * H)) ** 2) ** 0.5
            return Vector((math.cos(a) * RX * q * 0.97, math.sin(a) * RY * q * 0.97, z))
        for j in range(4):
            a = 2 * math.pi * (j + 0.3) / 4 + rr.uniform(-0.3, 0.3)
            roots.append([on_rock(a, H * 0.78), on_rock(a + 0.08, H * 0.45), on_rock(a + 0.15, H * 0.25),
                          on_rock(a + 0.2, H * 0.08) + Vector((math.cos(a + 0.2), math.sin(a + 0.2), 0)) * 0.06 * k])
    else:
        lr = C.rng(seed, 'lumps')
        n = lr.randint(3, 5)
        for j in range(n):
            a = 2 * math.pi * j / n + lr.uniform(-0.35, 0.35)
            off = 0.0 if j == 0 else lr.uniform(0.22, 0.34) * k
            R = lr.uniform(0.26, 0.36) * k * (1.1 if j == 0 else 0.9)
            lumps.append(dict(c=(math.cos(a) * off, math.sin(a) * off, 0.0), R=R, T=R * lr.uniform(0.85, 1.15),
                              flat=lr.uniform(1.0, 1.25), ph=lr.random(), seed=lr.random()))
        # the overhang: one lump spilling forward over the ledge edge, hanging lower
        lumps.append(dict(c=(lr.uniform(-0.1, 0.1) * k, 0.42 * k, -0.02), R=0.22 * k, T=0.18 * k, flat=1.4, ph=lr.random(),
                          seed=lr.random()))
        for j in range(rr.randint(1, 2)):
            s = rr.uniform(0.13, 0.2) * k
            rocks.append(dict(c=(rr.uniform(-0.35, 0.35) * k, rr.uniform(0.3, 0.45) * k, 0), s=(s * 1.3, s, s * 0.8),
                              npts=11, seed=rr.random()))
        for j in range(3):
            a = rr.uniform(0, 2 * math.pi)
            d = Vector((math.cos(a), math.sin(a), 0))
            roots.append([d * 0.02, d * 0.12 * k + Vector((0, 0, 0.12)), d * 0.2 * k + Vector((0, 0, 0.25))])
    L.update(rocks=rocks, lumps=lumps, roots=roots)
    return L


def build(lod, seed, style=None, spread=None, density=1.0, colour=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    style = style or C.cycle(seed, STYLES)
    spread = spread or p['w'] * g.uniform(0.75, 0.95)
    colour = colour or C.pick(seed, 'colour', list(COLOURS))
    L = layout(seed, spread, style)
    budget = (genlib.budget_of(ASSET) or [800, 320, 100, 30])[lod]

    mb = genlib.MeshBuilder()
    ct, cc = COLOURS[colour]
    card = mb.slot('foliage_pine', tint=ct)
    core = mb.slot('moss', tint=cc)
    rock = mb.slot('basalt_wet', wetness=0.55, tint=ROCK_TINT)
    bark = mb.slot('bark', tint=(0.6, 0.55, 0.5))
    moss = mb.slot('moss')
    pl = P.Plant(mb)

    rocks = L['rocks'] if lod < 3 else L['rocks'][:1]
    for R in rocks:
        rr = genlib.rng(R['seed'], 'rock')
        npts = C.lod_pick(lod, R['npts'], 10, 6, 6)
        c = (R['c'][0], R['c'][1], R['s'][2] * 0.5)
        faces = C.hull_rock(mb, c, (R['s'][0], R['s'][1], R['s'][2] * 0.55), rock, rr, npts=npts, ground=0.0,
                            flat_top=R['s'][2])
        pl.tag_faces(faces, 0.0, 0.0, 0.0)
    if lod == 0 and style == 'rock':        # moss in the seams at the rock foot
        for j, R in enumerate(L['rocks'][1:3]):
            cushion(pl, (R['c'][0] * 0.75, R['c'][1] * 0.75, 0.0), 0.12, 0.09, 0.07, moss, genlib.rng(seed, f'm{j}'), 7, 1)

    if lod < 2:
        for j, path in enumerate(L['roots']):
            n = len(path) - 1
            pl.tube(path, [0.035 - 0.025 * i / n for i in range(n + 1)], bark, C.lod_pick(lod, 5, 3), sway=lambda t: 0.0)

    lumps = L['lumps']
    if lod == 3:                              # one merged dome over the clump
        xs = [q['c'][0] for q in lumps]; ys = [q['c'][1] for q in lumps]
        Rm = max(max(abs(q['c'][0]) + q['R'], abs(q['c'][1]) + q['R']) for q in lumps)
        q0 = lumps[0]
        lumps = [dict(q0, c=(sum(xs) / len(xs), sum(ys) / len(ys), q0['c'][2]), R=Rm * 0.85,
                      T=(max(q['T'] + q['c'][2] for q in L['lumps']) - q0['c'][2]) * 1.1)]
    if lod == 2:                              # the 3 biggest lumps, a little larger, carry the dome
        lumps = [dict(q, R=q['R'] * 1.15) for q in sorted(lumps, key=lambda q: -q['R'])[:3]]
    segs, rings = C.lod_pick(lod, (9, 1), (7, 1), (5, 0), (6, 0))
    core_cost = len(lumps) * 2 * segs * (rings + 2)
    n_cards = max(0, int((budget * 0.98 - C.tri_count(mb.bm) - core_cost) / 2 * density)) if lod < 3 else 0
    areas = [q['R'] ** 2 * q['flat'] for q in lumps]
    csz = C.lod_pick(lod, 1.0, 1.4, 1.5, 1.0)
    for j, q in enumerate(lumps):
        nc = int(n_cards * areas[j] / sum(areas))
        r = genlib.rng(q['seed'], 'pad')
        z0 = q['c'][2]
        core_f, card_f = C.foliage_pad(mb, q['c'], q['R'], q['T'], core, card, r, n_cards=nc, segs=segs, rings=rings,
                                       lobes=r.choice([4, 5, 6]), flat=q['flat'],
                                       card_w=(0.18 * csz, 0.28 * csz), card_h=(0.14 * csz, 0.22 * csz), side_band=(0.12 if style == 'rock' else 0.3))
        sw = lambda v, z0=z0, T=q['T']: 0.55 + 0.45 * max(0.0, min(1.0, (v.co.z - z0) / max(T, 1e-3)))
        pl.tag_faces(core_f, sw, q['ph'], 1.0)
        pl.tag_faces(card_f, sw, q['ph'], 1.0)

    for v in mb.bm.verts:
        v.co.z = max(v.co.z, 0.0)
    P.fit_xy(mb, p['w'] * 0.98, p['d'] * 0.98)
    P.fit_h(mb, p['h'] * 0.99)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=60)
    P.post(o, soft_slots=(card, core, moss), sharp_slots=(rock,))
    o['kz_sway_default_indoor'] = 0
    C.set_json_props(o, kz_params=dict(style=style, spread=round(spread, 3), density=density, colour=colour))
    return o
