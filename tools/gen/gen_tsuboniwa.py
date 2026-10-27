"""Courtyard garden (tsuboniwa) with washi light box, op06 first build.  Hero of b1_treatment.

Identifying features kept at every LOD: a sunken court of raked gravel with moss mounds around one niwaki pine
and a stone toro, under a glowing washi ceiling box (the 'false sky').

Concept: refs/gen/sheet-ref-ground.png panel 02 (treatment hall: a sunken moss-and-basalt garden with one
niwaki pine, dark wet rock edges and lanterns beside the engawa), lookbook 05 (mist corridor: dark basalt,
warm toro and andon glow).  3d/spaces/b1_treatment.json: hero at the engawa, dims 9 x 6.5 x 0.6, hall ceiling
3.6-4.0 m (coffered hinoki), "a washi light box over the garden is the only bright ceiling".
No scale sheet: scale from the row (w 6-9, d 5-6.5, sink 0.3-0.6) and the hall (door 2.1 m, ceiling 3.6 m).

Targets (default = proxy footprint 6 x 5, sink 0.45; the space places it at 9 x 6.5):
  basalt retaining wall 0.2 m thick, hinoki coping 0.24 x 0.06 at hall-floor level (z = sink);
  raked gravel bed: ridges 15 cm pitch, 18 mm high, 3 concentric rings round each mound / the toro, straight (or
  wave) lines elsewhere, cut at the rings;  3-6 moss mounds 0.5-1.0 m across x 0.15-0.32 m high; 2-3 basalt
  rocks; one niwaki pine 2.2-2.8 m on the largest mound (S-curved trunk, 5 cloud pads); one hexagonal stone toro
  1.0-1.2 m with a glowing firebox; washi light box 0.55-0.8 x the court, face 3.6 m above the hall floor,
  hinoki frame 0.09 x 0.2 and a kumiko grid at 0.45 m pitch.

Pivot / placement: base centre = court floor (z = 0).  The hall floor (coping top) is at z = sink: place the
asset sink metres below the engawa floor (kz_floor_z).  The light box lives at kz_box_z (sink + ceiling).
Parameters: w (6-9), d (5-6.5), sink (0.3-0.6), rake 'straight' | 'wave', mounds (3-6), box (0.5-0.85, light box
  size / court), ceiling (3.2-4.0 m above the hall floor).
Seeds change: mound count / layout / sizes, which corner holds the pine and the toro, rock placement, rake pattern
  (seed 1 straight, 2 wave, 3 straight ...), pine lean and pads, light box proportion.

Materials: gravel  `ash_clay` tinted pale (1.7, 1.7, 1.8)  STAND-IN for NEW:gravel (proposed: pale grey
                   shirakawa-suna, base #A8A49A, rough 0.9, 5 mm grain normal);
           moss    `moss` tinted (0.45, 0.55, 0.32)  (moss exists in the library);
           walls, rocks, toro  `basalt_wet` (wetness 0.4, cooled tint 0.32, 0.36, 0.46);
           coping, light-box frame, kumiko  `hinoki` variant 'dark_timber';
           light box panel, toro firebox  `washi_backlit` (emissive 1.0 / 0.8);
           pine `bark`, pad cores `moss` darkened, needles `foliage_pine`.
Lighting: lightmap + emissive.  kz_lights: the light box (area, 2600 K, 40 W) and the toro (point, 2200 K, 6 W).
LOD: one layout.  LOD0 ridges with rings 24-seg, 24-seg mounds, pine with ~170 cards, toro 6-sided with posts,
  kumiko.  LOD1 rings 16-seg, wave lines coarser, 14-seg mounds, fewer cards.  LOD2 rings only (2 per feature),
  8-seg mounds, pine card-less, no kumiko.  LOD3 gravel plane, wall frame, 5-seg mounds, trunk + pad cones,
  toro stack, light panel + frame.
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_tsuboniwa as K

ASSET = 'tsuboniwa'
FEATURES = ['sunken court of raked gravel', 'moss mounds', 'one niwaki pine', 'stone toro', 'glowing washi ceiling box']
PROXY_SHEET = dict(w=6.0, d=5.0, h=4.25)       # proposed: the light box and pine stand above the 0.6 m court
STONE_TINT = (0.32, 0.36, 0.46)
RAKES = ['straight', 'wave']


def layout(seed, W, D, sink, n_m):
    g = C.rng(seed, 'layout')
    tw = 0.2
    IW, ID = W - 2 * tw, D - 2 * tw
    sx, sy = g.choice([-1, 1]), g.choice([-1, 1])
    mounds = []
    R0 = min(IW, ID) * g.uniform(0.17, 0.2)
    pine_c = (sx * IW * g.uniform(0.17, 0.25), sy * ID * g.uniform(0.08, 0.16))
    mounds.append(dict(c=pine_c, R=R0, H=g.uniform(0.26, 0.32), asp=g.uniform(0.8, 1.25), pine=True))
    toro_c = (-sx * IW * g.uniform(0.22, 0.3), -sy * ID * g.uniform(0.05, 0.18))
    tries = 0
    while len(mounds) < n_m and tries < 400:
        tries += 1
        R = min(IW, ID) * g.uniform(0.08, 0.13)
        c = (g.uniform(-IW / 2 + R + 0.35, IW / 2 - R - 0.35), g.uniform(-ID / 2 + R + 0.35, ID / 2 - R - 0.35))
        ok = all(math.hypot(c[0] - m['c'][0], c[1] - m['c'][1]) > (R + m['R']) * 1.2 + 0.45 for m in mounds)
        ok = ok and math.hypot(c[0] - toro_c[0], c[1] - toro_c[1]) > R + 0.85
        if ok:
            mounds.append(dict(c=c, R=R, H=g.uniform(0.14, 0.22), asp=g.uniform(0.75, 1.3), pine=False))
    rocks = []
    for m in mounds[:3]:
        a = g.uniform(0, 2 * math.pi)
        s = g.uniform(0.18, 0.3) * (1.4 if m['pine'] else 1.0)
        rocks.append(dict(c=(m['c'][0] + math.cos(a) * m['R'] * 0.95, m['c'][1] + math.sin(a) * m['R'] * 0.95), s=s, seed=g.random()))
    a = g.uniform(0, 2 * math.pi)
    rocks.append(dict(c=(toro_c[0] + math.cos(a) * 0.42, toro_c[1] + math.sin(a) * 0.42), s=0.16, seed=g.random()))
    return dict(tw=tw, IW=IW, ID=ID, mounds=mounds, toro=toro_c, rocks=rocks, pine_h=g.uniform(2.2, 2.7),
                toro_h=g.uniform(1.0, 1.15), pine_seed=g.random())


def build(lod, seed, w=None, d=None, sink=None, rake=None, mounds=None, box=None, ceiling=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    W = max(6.0, min(9.0, w or p['w']))
    D = max(5.0, min(6.5, d or p['d']))
    sink = max(0.3, min(0.6, sink or g.uniform(0.4, 0.5)))
    rake = rake or C.cycle(seed, RAKES)
    n_m = int(mounds or C.pick(seed, 'nm', [4, 5, 3, 6, 4]))
    box = box or g.uniform(0.58, 0.75)
    ceiling = ceiling or 3.6
    lay = layout(seed, W, D, sink, n_m)
    IW, ID, tw = lay['IW'], lay['ID'], lay['tw']

    mb = genlib.MeshBuilder()
    gravel = mb.slot('ash_clay', tint=(1.7, 1.7, 1.8))
    moss = mb.slot('moss', tint=(0.45, 0.55, 0.32))
    stone = mb.slot('basalt_wet', wetness=0.4, tint=STONE_TINT)
    rock_top = mb.slot('basalt_wet', wetness=0.75, tint=STONE_TINT)
    wood = mb.slot('hinoki', variant='dark_timber')
    washi = mb.slot('washi_backlit', emissive_level=1.0)
    paper = mb.slot('washi_backlit', emissive_level=0.8)
    bark = mb.slot('bark', tint=(0.7, 0.62, 0.55))
    core = mb.slot('moss', tint=(0.3, 0.4, 0.22))
    fol = mb.slot('foliage_pine')
    bm = mb.bm

    # ---------------- gravel bed (flat plane, the ridges sit on it)
    q = [bm.verts.new((x, y, 0.0)) for x, y in ((-IW / 2, -ID / 2), (IW / 2, -ID / 2), (IW / 2, ID / 2), (-IW / 2, ID / 2))]
    f = bm.faces.new(q); f.material_index = gravel

    # ---------------- retaining walls + hinoki coping (the hall-floor edge)
    hw = sink - 0.06
    bev = C.lod_pick(lod, 0.012, 0.0, 0.0, 0.0)
    if lod < 3:
        for sxy in (-1, 1):
            C.board(mb, (sxy * (W / 2 - tw / 2), 0, hw / 2), (tw, D, hw), stone, bevel=bev)
            C.board(mb, (0, sxy * (D / 2 - tw / 2), hw / 2), (W - 2 * tw, tw, hw), stone, bevel=bev)
        cw = 0.24
        cb = C.lod_pick(lod, 0.006, 0.0, 0.0, 0.0)
        for sxy in (-1, 1):
            C.board(mb, (sxy * (W / 2 - cw / 2 + 0.03), 0, sink - 0.03), (cw, D + 0.06, 0.06), wood, bevel=cb)
            C.board(mb, (0, sxy * (D / 2 - cw / 2 + 0.03), sink - 0.03), (W - 2 * cw + 0.06, cw, 0.06), wood, bevel=cb)
    else:                          # a frame: inner wall faces + coping top as one ring
        def loop(hx, hy, z):
            return [bm.verts.new((x, y, z)) for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        a0, a1, b1 = loop(IW / 2, ID / 2, 0.0), loop(IW / 2, ID / 2, sink), loop(W / 2 + 0.03, D / 2 + 0.03, sink)
        fs = C.bridge_rings(bm, a0, a1) + C.bridge_rings(bm, a1, b1)
        mb._tag(fs, stone)

    # ---------------- moss mounds, rocks
    feats = []
    for mi_, m in enumerate(lay['mounds']):
        K.mound(mb, (m['c'][0], m['c'][1], 0.0), m['R'], m['H'], moss, C.rng(seed, f'mound{mi_}'), lod, aspect=m['asp'])
        feats.append((m['c'][0], m['c'][1], m['R'] * 1.08 * max(m['asp'], 1 / m['asp']) ** 0.5))
    feats.append((lay['toro'][0], lay['toro'][1], 0.36))
    for ri, rk in enumerate(lay['rocks']):
        if lod == 3:
            continue
        rr = genlib.rng(rk['seed'], 'rock')
        s = rk['s']
        if lod < 2:
            C.crag_rock(mb, C.frame((rk['c'][0], rk['c'][1], 0), (0, 1, 0)), s * 1.1, s * 0.9, -0.02, s * 0.9, stone, rr,
                        nside=C.lod_pick(lod, 8, 6), bands=C.lod_pick(lod, 3, 2))
        else:
            C.hull_rock(mb, (rk['c'][0], rk['c'][1], 0.0), (s * 1.1, s * 0.9, s * 0.9), stone, rr, npts=6, ground=0.0)

    # ---------------- rake
    pitch = 0.15 * max(1.0, IW * ID / 25.8) ** 0.5     # larger courts: coarser pitch keeps the ridge count (budget)
    K.rake(mb, IW, ID, feats, gravel, lod, pattern=rake, period=pitch, n_rings=C.lod_pick(lod, 3, 2, 1, 0),
           ring_segs=C.lod_pick(lod, 24, 12, 8, 8))

    # ---------------- niwaki pine on the largest mound
    pm = lay['mounds'][0]
    K.pine(mb, (pm['c'][0], pm['c'][1], pm['H'] * 0.82), lay['pine_h'], dict(bark=bark, core=core, fol=fol),
           genlib.rng(lay['pine_seed'], 'pine'), lod)

    # ---------------- toro on a flat stone
    tc = lay['toro']
    if lod < 3:
        C.slab(mb, (tc[0], tc[1], 0.0), 0.62, 0.56, 0.06, stone, rc=0.06, m=C.lod_pick(lod, 3, 2, 1))
    light_c = K.toro(mb, (tc[0], tc[1], 0.06 if lod < 3 else 0.0), lay['toro_h'], dict(stone=stone, paper=paper), lod)

    # ---------------- washi ceiling light box
    zb = sink + ceiling
    lights = K.light_box(mb, zb, IW * box, ID * box, dict(wood=wood, washi=washi), lod)
    lights.append(C.light_entry(light_c, color_k=2200, watts=6, note='toro firebox'))

    for v in bm.verts:                 # rocks are sunk into the gravel: nothing below the court floor
        if v.co.z < 0:
            v.co.z = 0.0
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
    bmesh.ops.translate(bm, vec=Vector((-(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, 0)), verts=bm.verts)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=lights, kz_floor_z=round(sink, 3), kz_box_z=round(zb, 3),
                     kz_params=dict(w=W, d=D, sink=round(sink, 3), rake=rake, mounds=len(lay['mounds']), box=round(box, 3),
                                    ceiling=ceiling),
                     kz_material_pending={'gravel': 'stand-in ash_clay tinted 1.7'},
                     kz_place_note='base = court floor; drop by kz_floor_z under the engawa floor; light box at kz_box_z')
    return o
