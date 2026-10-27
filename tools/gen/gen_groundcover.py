"""Groundcover: moss cushions, fern clumps and low arching grass, in a rock crevice or a timber planter box.

Identifying features kept at every LOD: bright green fern fronds / moss cushions / arching grass blades
springing from a rock crevice or a dark timber planter box.
Concept: refs/gen/sheet-vs-nature-2.png #2 "Moss, fern & low plants" (W 0.8 x D 0.8 x H 0.5 m label;
310 px/m bar): drawn planter 0.71 w x 0.53 d x 0.21 h (w:d 1.34), plants rise to 0.69 m drawn (label 0.5:
built to the label), fern fronds spill 0.05-0.1 m past the box ends, a black basalt rock at the back, moss
cushions and small broadleaf plants at the front.  Lookbook 05 (planter boxes and fern/moss tufts on the
kerb left), 12 / 13 (ferns and moss in lava-tube rock crevices).

Targets (built, proxy 0.8 x 0.8 x 0.5):
  spread 0.64-0.8 m (seeded 0.8-1.0 x proxy w; param range 0.2-1.5)
  planter: W = 0.92 spread, D = 0.68 W (1.35), wall 0.18 m high, 32 mm boards with 6 mm round, corner posts
  fern: 9-14 fronds 0.30-0.42 m long (x frond_length), 50-72 deg rise, drooping tips, saw-tooth pinnae,
        widest 1/3 out; overall h <= 0.5 m
  moss: 4-7 cushions 0.09-0.22 m radius, 0.05-0.12 m high, hugging 1-2 basalt rocks (0.12-0.2 m)
  grass: 4-6 tufts of 9-14 blades 0.22-0.36 m, arching over (Hakone-grass cascade)
Styles: species fern | moss | grass cycle with the seed (1 fern, 2 moss, 3 grass, ...); setting planter |
  ground: seeds 1, 5, 6 planter, 2, 3, 4 ground (so the 6 seeds cover 3 species x 2 settings).
Seeds change: species, setting, spread, frond/blade/cushion count, length, layout, rock size and place.

Materials: fern / grass blades `foliage_fern` (NEW: stand-in `moss` tinted bright green, double-sided sheet:
  the fronds are open strips), cushions `moss` (library tint), rocks `basalt_wet` (cooled tint),
  planter `hinoki dark_timber` boards + `hinoki walnut` posts, soil `black_sand`.
LOD: one layout; LOD1 3-segment fronds / 8-seg cushions / unbevelled boards; LOD2 2-segment strips, no
  pinnae, the box as one open shell; LOD3 the box shell + the 4 longest fronds/blades as single strips, or
  the 2 largest cushions + rock.
Animation: `kz_sway` colour attribute (R weight 0 at the root -> 1 at the frond tip, G phase per frond,
  B 1 on foliage) + vertex group `sway`; cushions, rocks and box 0.  kz_sway_default_indoor = 0.4 (drafts).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_groundcover as P

ASSET = 'groundcover'
FEATURES = ['bright green fern fronds', 'moss cushions', 'rock crevice or timber planter box']
SPECIES = ['fern', 'moss', 'grass']
SETTING_BY_SEED = ['planter', 'ground', 'ground', 'ground', 'planter', 'planter']
ROCK_TINT = (0.32, 0.36, 0.46)


def cushion(pl, c, rx, ry, h, mi, r, segs, rings, rot=0.0):
    """moss cushion: a soft dome (open underside sunk 1 cm into the ground), lobed outline"""
    bm = pl.mb.bm
    off = Vector((r.uniform(0, 50), r.uniform(0, 50), r.uniform(0, 50)))
    ph = r.uniform(0, 6.28)
    c = Vector(c)
    top = bm.verts.new(c + Vector((0, 0, h)))
    pl.tag(top, 0.0)
    rows = []
    for j in range(1, rings + 1):
        f = j / rings
        row = []
        for k in range(segs):
            th = 2 * math.pi * k / segs
            e = 1 + 0.12 * math.cos(3 * th + ph) + 0.08 * noise.noise(Vector((math.cos(th), math.sin(th), 0.5)) * 1.7 + off)
            x, y = math.cos(th) * rx * e * f, math.sin(th) * ry * e * f
            z = h * (1 - f ** 2) ** 0.55 if j < rings else -0.01
            x, y = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
            v = bm.verts.new(c + Vector((x, y, z)))
            pl.tag(v, 0.0)
            row.append(v)
        rows.append(row)
    faces = [bm.faces.new((top, rows[0][k], rows[0][(k + 1) % segs])) for k in range(segs)]
    for A, B in zip(rows[:-1], rows[1:]):
        faces += C.bridge_rings(bm, A, B)
    for f in faces:
        f.material_index = mi
        f.normal_update()
    return faces


def layout(seed, spread, species, setting, density, frond_length):
    g = C.rng(seed, 'layout')
    L = dict(species=species, setting=setting, spread=spread)
    if setting == 'planter':
        W = spread * 0.92
        L['box'] = (W, W * 0.68, 0.18)
        hx, hy, z0 = W / 2 - 0.05, W * 0.34 - 0.05, 0.15
    else:
        hx, hy, z0 = spread * 0.36, spread * 0.36, 0.0
    L['z0'] = z0
    rr = C.rng(seed, 'rocks')
    rocks = []
    n_rock = 1 if setting == 'planter' else rr.choice([1, 2, 2])
    for k in range(n_rock):
        s = rr.uniform(0.12, 0.2) * (1.0 if k == 0 else 0.7) * min(1.0, spread / 0.7) * (0.7 if setting == 'planter' else 1.0)
        rocks.append(dict(c=(rr.uniform(-0.5, 0.5) * hx, -hy * rr.uniform(0.45, 0.75) * (1 if k == 0 else -0.6), z0),   # main rock at the back (-Y)
                          s=(s * rr.uniform(1.0, 1.4), s, s * rr.uniform(0.8, 1.2)), seed=rr.random()))
    L['rocks'] = rocks
    fr = C.rng(seed, 'plants')
    plants = []
    if species == 'fern':
        crowns = [(fr.uniform(-0.15, 0.15) * hx, fr.uniform(-0.1, 0.2) * hy)]
        if fr.random() < 0.6:
            crowns.append((crowns[0][0] + fr.choice([-1, 1]) * hx * 0.6, hy * fr.uniform(0.0, 0.5)))
        n = int(round(fr.randint(11, 16) * density))
        for i in range(n):
            ci = 0 if (i % 3 or len(crowns) == 1) else 1
            a = 2 * math.pi * i / n + fr.uniform(-0.25, 0.25)
            el = math.radians(fr.uniform(42, 75) + (8 if setting == 'ground' else 0))
            ln = fr.uniform(0.34, 0.48) * frond_length * (0.7 if ci else 1.0) * min(1.25, spread / 0.7) * \
                (1.1 if setting == 'ground' else 1.0)
            plants.append(dict(kind='frond', base=(crowns[ci][0], crowns[ci][1], z0), a=a, el=el, len=ln,
                               w=ln * fr.uniform(0.17, 0.21), droop=fr.uniform(1.1, 1.7), ph=fr.random()))
        n_c = 4 if setting == 'planter' else 2          # the planter soil is carpeted with moss (sheet #2)
    elif species == 'grass':
        n_t = fr.randint(4, 6)
        for t in range(n_t):
            cx, cy = fr.uniform(-0.75, 0.75) * hx, fr.uniform(-0.75, 0.75) * hy
            nb = int(round(fr.randint(9, 14) * density))
            for i in range(nb):
                a = 2 * math.pi * i / nb + fr.uniform(-0.3, 0.3)
                ln = fr.uniform(0.22, 0.36) * frond_length
                plants.append(dict(kind='blade', base=(cx + math.cos(a) * 0.015, cy + math.sin(a) * 0.015, z0), a=a,
                                   el=math.radians(fr.uniform(55, 80)), len=ln, w=fr.uniform(0.008, 0.012),
                                   droop=fr.uniform(1.6, 2.4), ph=fr.random()))
        n_c = 3 if setting == 'planter' else 1
    else:  # moss: a few short fern sprigs among the cushions
        n_c = int(round(fr.randint(4, 7) * density))
        for i in range(3):
            a = fr.uniform(0, 2 * math.pi)
            ln = fr.uniform(0.13, 0.18) * frond_length
            plants.append(dict(kind='frond', base=(fr.uniform(-0.5, 0.5) * hx, fr.uniform(-0.5, 0.5) * hy, z0), a=a,
                               el=math.radians(fr.uniform(45, 65)), len=ln, w=ln * 0.17, droop=1.1, ph=fr.random()))
    cr = C.rng(seed, 'cushions')
    cush = []
    for i in range(n_c):
        big = species == 'moss'
        rx = cr.uniform(0.09, 0.22) if big else (cr.uniform(0.1, 0.16) if setting == 'planter' else cr.uniform(0.08, 0.13))
        # moss hugs the rocks: first cushions sit against the first rock
        if setting == 'planter' and species != 'moss':     # a carpet along the box, front row first
            cx = (-0.75 + 1.5 * (i + 0.5) / n_c) * hx + cr.uniform(-0.05, 0.05)
            cy = hy * (0.45 if i % 2 == 0 else -0.2) + cr.uniform(-0.04, 0.04)
        elif rocks and i < 2:
            rc = rocks[0]['c']
            a = cr.uniform(0, 2 * math.pi)
            cx, cy = rc[0] + math.cos(a) * rocks[0]['s'][0] * 0.9, rc[1] + math.sin(a) * rocks[0]['s'][1] * 0.9
        else:
            cx, cy = cr.uniform(-0.8, 0.8) * hx, cr.uniform(-0.8, 0.8) * hy
        if setting == 'planter':      # keep every cushion inside the box walls
            rx = min(rx, hy * 0.9)
            cx = max(-hx + rx * 0.9, min(hx - rx * 0.9, cx)); cy = max(-hy + rx * 0.9, min(hy - rx * 0.9, cy))
        cush.append(dict(c=(cx, cy, z0), rx=rx, ry=rx * cr.uniform(0.7, 1.0), h=rx * cr.uniform(0.45, 0.6),
                         rot=cr.uniform(0, 3.1), seed=cr.random()))
    L['cushions'] = cush
    L['plants'] = plants
    return L


def planter(mb, L, lod, wood, post, soil):
    W, D, H = L['box']
    t = 0.032
    if lod <= 1:
        bev = 0.006 if lod == 0 else 0.0
        for sx in (-1, 1):
            C.board(mb, (0, sx * (D / 2 - t / 2), H / 2), (W - 2 * t, t, H), wood, bevel=bev) if bev else \
                mb.box((0, sx * (D / 2 - t / 2), H / 2), (W - 2 * t, t, H), wood)
            mb.box((sx * (W / 2 - t / 2), 0, H / 2), (t, D - 2 * t, H), wood)      # end boards: posts cover the edges
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (W / 2 - 0.012), sy * (D / 2 - 0.012), H / 2 + 0.006), (0.05, 0.05, H + 0.012), post)
        bm = mb.bm
        sv = [bm.verts.new((x * (W / 2 - t), y * (D / 2 - t), L['z0'])) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        f = bm.faces.new(sv); f.material_index = soil
    else:                             # one open shell: 4 outer walls + soil top (10 tris)
        bm = mb.bm
        q = [(-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2)]
        lo = [bm.verts.new((x, y, 0)) for x, y in q]
        hi = [bm.verts.new((x, y, H)) for x, y in q]
        fs = C.bridge_rings(bm, lo, hi)
        for f in fs:
            f.material_index = wood
        s = [bm.verts.new((x * 0.92, y * 0.9, L['z0'])) for x, y in q]
        f = bm.faces.new(s); f.material_index = soil


def build(lod, seed, species=None, setting=None, spread=None, density=1.0, frond_length=1.0):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    species = species or C.cycle(seed, SPECIES)
    setting = setting or SETTING_BY_SEED[(seed - 1) % len(SETTING_BY_SEED)]
    spread = spread or p['w'] * g.uniform(0.8, 1.0)
    L = layout(seed, spread, species, setting, density, frond_length)

    mb = genlib.MeshBuilder()
    pending = {}
    fern = P.slot(mb, 'foliage_fern', pending)
    grass = P.slot(mb, 'foliage_fern', pending, tint=(1.05, 1.3, 0.42))
    moss = mb.slot('moss')
    rock = mb.slot('basalt_wet', wetness=0.6, tint=ROCK_TINT)
    wood = mb.slot('hinoki', variant='dark_timber')
    post_m = mb.slot('hinoki', variant='walnut')
    soil = mb.slot('black_sand', wetness=0.0, roughness_offset=0.3)
    pl = P.Plant(mb)

    if L['setting'] == 'planter':
        planter(mb, L, lod, wood, post_m, soil)

    # rocks (kept at every LOD; LOD3 keeps the first)
    for k, R in enumerate(L['rocks']):
        if lod == 3 and (k or L['setting'] == 'planter'):     # LOD3: the box (or the main rock) carries the read
            continue
        rr = genlib.rng(R['seed'], 'rock')
        c = (R['c'][0], R['c'][1], R['c'][2] + R['s'][2] * 0.45)
        faces = C.hull_rock(mb, c, R['s'], rock, rr, npts=C.lod_pick(lod, 13, 10, 7, 6), ground=R['c'][2])
        pl.tag_faces(faces, 0.0, 0.0, 0.0)

    # cushions
    cush = L['cushions']
    if lod == 3:
        cush = sorted(cush, key=lambda q: -q['rx'])[:2 if species == 'moss' else 0]
    segs, rings = C.lod_pick(lod, (11, 3), (8, 2), (5, 1), (5, 1))
    if L['setting'] == 'planter' and lod < 2:
        segs, rings = (9, 2) if lod == 0 else (6, 1)
    for q in cush:
        cushion(pl, q['c'], q['rx'], q['ry'], q['h'], moss, genlib.rng(q['seed'], 'c'), segs, rings, q['rot'])

    # fronds / blades
    plants = L['plants']
    if species == 'grass' and lod in (1, 2):          # fewer, wider blades (same tufts)
        k = 2 if lod == 1 else 3
        plants = [dict(q, w=q['w'] * (1.6 if lod == 1 else 1.4)) for i, q in enumerate(plants) if i % k == 0]
    if lod == 3:
        plants = sorted(plants, key=lambda q: -q['len'])[:4 if species != 'moss' else 0]
    # resolution by arithmetic (never presence): best option whose cost fits what the budget leaves
    budget = (genlib.budget_of(ASSET) or [600, 240, 80, 20])[lod]
    left = budget * 1.04 - C.tri_count(mb.bm)
    nf = sum(1 for q in plants if q['kind'] == 'frond'); nb = len(plants) - nf
    f_opts = C.lod_pick(lod, [11, 10, 9, 8, 7], [6, 5, 4], [3, 2, 1], [2, 1])
    b_opts = C.lod_pick(lod, [3, 2, 1], [2, 1], [1], [1])
    cost_f = lambda sg: 2 * sg
    cost_b = lambda sg: 4 * (sg - 1) + 2
    fo = next((o for o in f_opts if nf * cost_f(o) <= left), f_opts[-1])
    left -= nf * cost_f(fo)
    bo = next((o for o in b_opts if nb * cost_b(o) <= left), b_opts[-1])
    if (nf and fo != f_opts[0]) or (nb and bo != b_opts[0]):
        print(f'[{ASSET}] s{seed} L{lod}: frond segs {fo}, blade segs {bo} to fit {budget}')
    for q in plants:
        d = Vector((math.cos(q['a']) * math.cos(q['el']), math.sin(q['a']) * math.cos(q['el']), math.sin(q['el'])))
        if q['kind'] == 'frond':
            pl.fishbone(q['base'], d, q['len'], q['w'] * (1.0 if fo > 4 else 1.25), fern, fo, ph=q['ph'],
                        droop=q['droop'], lean=(0.45 if fo > 4 else 0.25))
        else:
            w = q['w'] * (1.0 if lod < 2 else 2.2)
            pl.blade(q['base'], d, q['len'] * (1.0 if bo > 1 else 0.85), w, grass, bo, ph=q['ph'], droop=q['droop'])

    P.fit_xy(mb, p['w'] * 1.0, p['d'] * 1.0) if spread <= p['w'] else None
    P.fit_h(mb, p['h'] * 1.0)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=60)
    P.post(o, soft_slots=(fern, grass, moss), sharp_slots=(rock,))
    o['kz_sway_default_indoor'] = 0.4
    C.set_json_props(o, kz_params=dict(species=species, setting=setting, spread=round(spread, 3), density=density,
                                       frond_length=frond_length),
                     kz_material_pending=pending)
    return o
