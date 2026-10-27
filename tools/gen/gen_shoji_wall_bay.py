"""Shoji wall bay set in rock (b1 mirror corridor, changing rooms, suites).

Identifying features kept at every LOD: glowing washi shoji in a timber frame (thick posts with cap blocks, kamoi,
projecting head canopy), set deep into a rough basalt surround of stacked rounded boulders on a full-width basalt
base with a stone ledge that carries potted plants and lanterns.

Construction (one mesh, library materials):
  * base          - full-width carved basalt footing (default 'low' layout: 0.9-1.0 m tall), boulders on its face,
                    topped by a flat dressed-stone ledge (~0.3 m deep) in front of the shoji.
  * rock surround - 12-20 rounded basalt boulders (0.3-0.6 m) stacked up the jambs and over the head, the crown
                    boulders overhanging the canopy by 0.15-0.25 m; a low-res lofted backing band behind them so the
                    wall never shows through; matte (dry, rough) basalt, a wetter setting only on crown boulders.
  * timber frame  - set ~0.3 m back from the rock face: 0.18-0.2 m chamfered posts with ~0.22 m cap blocks, 0.2 m
                    kamoi beam, threshold rail, optional lit ranma, and a 0.35 m hisashi head canopy (board, front
                    fascia, battens) on two short brackets.
  * shoji         - 2-4 sliding panels on two tracks: stiles, rails, koshi kick board (0.25-0.3 m, default on),
                    kumiko 4 x 7 / 4 x 8 per panel, lit paper.
  * ledge         - two andon lanterns and potted shrubs (ceramic pots, bark trunks, foliage_pine needle cards),
                    0.5-0.8 m; seeded taller (~1 m) shrub on the floor against one jamb.

Parameters (defaults = proxy 3.0 x 1.0 x 3.0 m in 3d/assets.json):
  w       1.8-6 m   overall width (base); the rock surround above sits 0.1-0.15 m in from each side
  h       1.5-3 m   overall height
  d       0.8-1.2 m depth from the wall plane (y = -d/2) to the front of the rock (y = +d/2)
  panels  2-4       shoji panel count (default seeded from the opening width)
  rock    0.4-0.85 m rock surround thickness at the jambs (default seeded 0.5-0.65 at w = 3 m)
  plants  True/False ledge plants
  ranma   None/True/False transom (default seeded; only where the opening is tall enough)
  layout  'low' | 'window' | 'tall'  (default cycles with the seed, 'low' for seed 1: 0.9-1.0 m base / ~0.55 m
          base with a transom / near-floor sill)
Seeded shape variation: layout, boulder sizes and stacking, crown overhang and lumpiness, jamb asymmetry, panel
count, kumiko grid, ranma style, canopy pitch, lantern/plant arrangement and plant kind (pine pads / rounded bush),
tall floor shrub side, timber tint.

Materials: basalt_dry (rough 0.35, wetter on the crown), hinoki (dark_timber variant for the frame, lighter for
kumiko and ledge-free parts), lantern_andon (lit paper: washi_backlit still renders without emission here, see the
report), iron (lantern frames), ceramic (pots, seeded glaze), bark + foliage_pine (shrubs), paving (stone ledge).
Lighting: lightmap + emissive.  obj['kz_lights'] = JSON list: the shoji glow as an area light
{type:'area', pos, normal, size:[w, h], color, watts} and one point light per lantern {type:'point', pos, color, radius}.
Animation (shader, soft flicker): obj['kz_flicker'] = JSON list of the emissive paper slot indices.
"""
import json
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_shoji_wall_bay as ks
from gen_torii_basalt import Rock, rounded_rock

ASSET = 'shoji_wall_bay'
FEATURES = ['glowing washi shoji', 'timber frame (posts, kamoi, head canopy)', 'rough basalt boulder surround',
            'stone ledge with potted plants and lanterns']

RES = {
    0: dict(nu=24, prof=[(0.0, 0.0), (0.08, 0.16), (0.3, 0.24), (0.7, 0.22), (0.93, 0.05), (1.0, -1.0)],
            boulders=16, base_cuts=3, base_boulders=5, post='oct', bev=0.008, kumiko='panel', ranma=True, plants=0),
    1: dict(nu=14, prof=[(0.0, 0.0), (0.15, 0.22), (0.7, 0.24), (1.0, -1.0)],
            boulders=12, base_cuts=0, base_boulders=3, post='box', bev=0.0, kumiko='long', ranma=True, plants=1),
    2: dict(nu=10, prof=[(0.0, 0.05), (0.3, 0.38), (1.0, -1.0)],
            boulders=0, base_cuts=0, base_boulders=0, post='box', bev=0.0, kumiko='min', ranma=False, plants=2),
    3: dict(nu=6, prof=[(0.0, 0.05), (0.35, 0.38), (1.0, -1.0)],
            boulders=0, base_cuts=-1, base_boulders=0, post='none', bev=0.0, kumiko='none', ranma=False, plants=3),
}


def _variant(mid, name, **over):
    v = dict(genlib.matlib.manifest()[mid].get('variants', {}).get(name, {}))
    v.update(over)
    if 'tint' in v:
        v['tint'] = tuple(v['tint'])
    return v


def _params(seed, w, h, d, panels, rock, plants, ranma, layout=None):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    w = float(w or p['w'])
    h = float(h or p['h'])
    d = float(d or p['d'])
    P = dict(w=w, h=h, d=d)
    P['layout'] = layout or ['low', 'window', 'tall'][(int(seed) - 1) % 3]
    P['inset'] = min(0.15, r.uniform(0.1, 0.15) * w / 3.0)          # surround inset from the base sides
    # jambs ~0.35-0.46 x the opening each (sheet 05 measures ~0.45; total / opening ~1.8-2.0), seeded L/R ratio
    ratio = r.uniform(0.36, 0.46)
    wi = w - 2 * P['inset']
    t = rock if rock is not None else wi * ratio / (1 + 2 * ratio)
    t = min(t, (wi - 0.9) / 2)
    P['rock'] = round(t, 3)
    lr = r.uniform(0.8, 1.25)                           # left / right jamb width ratio
    P['tL'], P['tR'] = 2 * t * lr / (1 + lr), 2 * t / (1 + lr)
    P['t_top'] = max(0.3, min(0.7, r.uniform(0.42, 0.62) * (0.6 + 0.4 * h / 3.0)))
    P['rock_scale'] = r.uniform(0.8, 1.25)              # block size factor: changes the rock count (+-30 %)
    P['crown_var'] = r.uniform(0.12, 0.25)              # crown height variation
    P['moss'] = r.random() < 0.6
    if P['layout'] == 'low':
        P['z_pl'] = max(0.45, min(0.8, h * r.uniform(0.23, 0.25)))
    elif P['layout'] == 'tall':
        P['z_pl'] = max(0.18, min(0.3, h * r.uniform(0.07, 0.09)))
    else:
        P['z_pl'] = max(0.3, min(0.6, h * r.uniform(0.17, 0.2)))
    ow = w - 2 * P['inset'] - P['tL'] - P['tR']
    P['panels'] = int(panels) if panels else max(2, min(4, int(round(ow / r.uniform(0.48, 0.58)))))
    P['cols'] = 4
    P['rows'] = r.choice([7, 8]) if P['layout'] != 'low' else 7
    P['koshi'] = True
    P['ranma'] = (P['layout'] != 'low' and r.random() < 0.7) if ranma is None else bool(ranma)
    P['ranma_style'] = r.choice(['tate', 'yoko'])
    P['plants'] = True if plants is None else bool(plants)
    P['shrub_kind'] = [r.choice(['pine', 'bush']), r.choice(['pine', 'bush'])]
    P['shrub_h'] = [r.uniform(0.4, 0.6), r.uniform(0.4, 0.6)]
    P['tall_side'] = r.choice([-1, 1])
    P['swap'] = r.random() < 0.35                      # True: lanterns at both ends, two shrubs inboard
    P['tall_h'] = r.uniform(1.0, 1.15)
    P['canopy_pitch'] = math.tan(math.radians(r.uniform(5, 8)))
    P['canopy'] = r.uniform(0.35, 0.45)
    P['lump'] = r.uniform(0.05, 0.08)
    P['crown_over'] = r.uniform(0.15, 0.3)
    P['wood_tint'] = (round(r.uniform(0.27, 0.32), 3), round(r.uniform(0.18, 0.21), 3), round(r.uniform(0.11, 0.13), 3))
    P['wet'] = round(r.uniform(0.0, 0.12), 2)
    P['glaze'] = 'tenmoku'
    return P, r


def _u_paths(P, R, r, xo, zb, ox0, ox1, oz1):
    """inner (opening) and outer (lumpy outline) polylines of the backing band, sampled pairwise"""
    h = P['h']
    I = [Vector((ox0, zb)), Vector((ox0, oz1)), Vector((ox1, oz1)), Vector((ox1, zb))]
    O = [Vector((-xo, zb)), Vector((-xo + 0.15 * P['tL'], h - 0.08)), Vector((xo - 0.15 * P['tR'], h - 0.08)), Vector((xo, zb))]
    L = [(I[k + 1] - I[k]).length + (O[k + 1] - O[k]).length for k in range(3)]
    cnt = [max(1, round(R['nu'] * x / sum(L))) for x in L]
    Pi, Po = [], []
    for k in range(3):
        for i in range(cnt[k] + (1 if k == 2 else 0)):
            t = i / cnt[k]
            Pi.append(I[k].lerp(I[k + 1], t)); Po.append(O[k].lerp(O[k + 1], t))
    off = r.uniform(0, 100)
    out = []
    S = len(Po)
    for i, (pi, po) in enumerate(zip(Pi, Po)):
        s = i / (S - 1)
        q = po.copy()
        for c in (O[1], O[2]):
            dist = (po - c).length
            rc = 0.6 * P['rock'] + 0.2
            if dist < rc:
                q = q.lerp(pi, 0.3 * (1 - dist / rc) ** 1.5)
        m = 0.5 + 0.5 * noise.noise(Vector((s * 8.0 + off, 0.3, 0.7)))
        if R['boulders'] == 0:
            # low LODs carry the rock read in the outline: alternating notches / bulges
            k_ = 0.03 + (0.22 if i % 2 else 0.0) * (0.6 + 0.8 * m) if 0 < i < S - 1 else 0.03
            q = q.lerp(pi, k_)
        else:
            q = q.lerp(pi, 0.04 + 0.1 * m)
        out.append(q)
    return [(p.x, p.y) for p in Pi], [(p.x, p.y) for p in out]


def build(lod, seed, w=None, h=None, d=None, panels=None, rock=None, plants=None, ranma=None, layout=None, **_):
    P, r = _params(seed, w, h, d, panels, rock, plants, ranma, layout)
    R = RES[lod]
    W, H, D = P['w'], P['h'], P['d']
    yb, yf = -D / 2, D / 2
    mb = genlib.MeshBuilder()
    stone = mb.slot('basalt_dry', wetness=P['wet'])
    rocks = mb.slot('basalt_dry', wetness=min(1, P['wet'] + 0.08)) if lod <= 1 else stone          # fractured blocks
    rocks_w = mb.slot('basalt_wet') if lod <= 1 else stone                                          # crown drip
    ledge = mb.slot('basalt_dry', wetness=0.0, roughness_offset=-0.1) if lod <= 2 else stone       # dressed course
    wood = mb.slot('hinoki', **_variant('hinoki', 'stained', wear=0.3))                             # frame (aged)
    wood_l = mb.slot('hinoki', wear=0.2)                                                            # kumiko / shoji / cap
    paper = mb.slot('washi_backlit', emissive_level=round(r.uniform(0.95, 1.1), 2), scale=0.4)   # lit shoji paper
    lpaper = mb.slot('lantern_andon', emissive_level=1.0, tint=(1.0, 0.8, 0.55)) if lod <= 2 else paper
    iron = mb.slot('iron', wear=0.25) if lod <= 2 else wood
    pot = mb.slot('ceramic', **_variant('ceramic', P['glaze'])) if lod <= 2 else stone
    bark = mb.slot('bark') if lod <= 1 else wood
    leaf = mb.slot('moss' if 'moss' in genlib.matlib.manifest() else 'foliage_pine') if lod <= 2 else wood   # solid foliage blobs
    rk = Rock(r, cell=0.4, stretch=(1.0, 1.0, 1.2), amp=0.05, crack=0.05, glassy=0.0, width=0.3, fbm=0.12)
    M = kg.frame(Vector((0, 0, 0)), Vector((0, 1, 0)))
    lights = []

    # ---------------------------------------------------------------- plan
    xo = W / 2 - P['inset']                            # surround outer half width (base is the full W)
    ox0, ox1 = -xo + P['tL'], xo - P['tR']             # opening (outer face of the posts)
    oz1 = H - P['t_top']                               # opening top (top of the kamoi)
    z_pl = P['z_pl']                                   # base top
    z_s = z_pl + 0.08                                  # ledge top (dressed stone slab)
    y_fr = yf - 0.36                                   # frame front face, ~0.3 m behind the rock face
    pw = 0.19 if W >= 2.4 else 0.16
    y_post = y_fr - pw / 2
    y_sh = y_post - 0.02                               # shoji front track

    sub = 1 if lod == 0 else 0

    def frock(c, size, mi, zlim, fac=None):
        """angular fractured basalt block (planar cuts, sharp edges), clamped into the bay; hidden back faces dropped"""
        fs, vs = kg.rock(mb, c, size, mi, r, subdiv=sub, rough=0.12, facets=fac or (6 if sub else 3),
                         zmin=zlim[0], zmax=zlim[1])
        kg.clamp_verts(vs, xlim=(-W / 2, W / 2), ylim=(yb, yf))
        dead = [f for f in fs if f.is_valid and all(v.co.y <= yb + 0.005 for v in f.verts)]
        if dead:
            bmesh.ops.delete(mb.bm, geom=dead, context='FACES_ONLY')
        return [f for f in fs if f.is_valid]

    # ---------------------------------------------------------------- base + ledge
    if R['base_cuts'] >= 0:
        if R['base_cuts'] > 0:
            rounded_rock(mb, (0, (yb + yf - 0.2) / 2, z_pl / 2), (W, D - 0.2, z_pl), stone, rk, R['base_cuts'] + 1,
                         1.0, 1.0, round_r=0.05, batter=0.02)
            # a course of mixed fractured blocks across the base face
            x = -W / 2
            while x < W / 2 - 0.1:
                bw = min(W / 2 - x, r.uniform(0.45, 0.95) * P['rock_scale'])
                bh = z_pl * r.uniform(0.7, 1.0)
                frock((x + bw / 2, yf - 0.17, bh * 0.47), (bw * 1.1, 0.36, bh), rocks if r.random() < 0.7 else rocks_w,
                      (0.0, z_pl - 0.04))
                if lod == 0 and r.random() < 0.4:      # small fill stone in the joint
                    frock((x + bw, yf - 0.1, r.uniform(0.15, z_pl - 0.2)), (0.22, 0.2, 0.2), rocks, (0.0, z_pl), fac=3)
                x += bw * r.uniform(0.85, 1.0)
        else:
            mb.box((0, (yb + yf) / 2, z_pl / 2), (W, D, z_pl), stone)
        # dressed sill course 0.25-0.3 m deep with a timber cap that catches the lantern glow
        lw = ox1 - ox0 + 0.34
        ld = r.uniform(0.25, 0.3)
        y0l = y_fr - 0.06
        mb.box(((ox0 + ox1) / 2, y0l + (ld + 0.06) / 2, z_s - 0.07), (lw, ld + 0.06, 0.1), ledge,
               bevel=0.012 if lod == 0 else 0.0)
        mb.box(((ox0 + ox1) / 2, y0l + (ld + 0.06) / 2, z_s - 0.01), (lw - 0.04, ld + 0.04, 0.03), wood_l)
    else:
        ks.quad(mb, M, [(-W / 2, yf, 0), (W / 2, yf, 0), (W / 2, yf, z_s), (-W / 2, yf, z_s)], stone)
        ks.quad(mb, M, [(-W / 2, yf, z_s), (W / 2, yf, z_s), (W / 2, y_fr, z_s), (-W / 2, y_fr, z_s)], ledge)

    # ---------------------------------------------------------------- rock surround: backing band + fractured blocks
    zb = z_pl - 0.04
    Pi, Po = _u_paths(P, R, r, xo, zb, ox0 - 0.02, ox1 + 0.02, oz1 + 0.02)
    prof = [(a, y_fr - 0.02 + (yf - 0.1 - (y_fr - 0.02)) * t if t >= 0 else yb) for a, t in
            [(a, (y - 0.0) / 0.38 if y >= 0 else -1) for a, y in R['prof']]]
    ks.rock_band(mb, Pi, Po, prof, stone, rk if lod <= 1 else None, r, k_amp=0.8, k_crack=0.6,
                 lump=P['lump'] if lod <= 2 else 0.0, lump_f=1.8, y_lim=(yb, yf), x_lim=(-xo, xo), z_lim=(0.0, H))
    moss_mi = mb.slot('moss') if (lod == 0 and P['moss'] and 'moss' in genlib.matlib.manifest()) else None
    if R['boulders']:
        rs = P['rock_scale']
        for side, x_in, t_j in ((-1, ox0, P['tL']), (1, ox1, P['tR'])):
            z = zb
            while z < oz1 - 0.1:
                widen = 1.0 + 0.15 * (1 - (z - zb) / max(0.1, oz1 - zb))      # jambs widen toward the base
                band = t_j * widen
                hz = min(oz1 + 0.1 - z, r.uniform(0.3, 0.75) * rs)
                if r.random() < 0.55 or band < 0.45:
                    # one block spanning the jamb
                    w_ = band * r.uniform(0.95, 1.15)
                    xc = x_in + side * w_ / 2 - side * 0.02
                    frock((xc, yf - 0.24, z + hz * 0.5), (w_, r.uniform(0.42, 0.55), hz * 1.1),
                          rocks_w if r.random() < 0.2 else rocks, (zb - 0.05, H))
                else:
                    # two smaller blocks side by side
                    f_ = r.uniform(0.4, 0.6)
                    for a_, b_ in ((0.0, f_), (f_, 1.0)):
                        w_ = band * (b_ - a_) * 1.12
                        xc = x_in + side * band * (a_ + b_) / 2
                        frock((xc, yf - 0.22, z + hz * 0.5 + r.uniform(-0.05, 0.05)), (w_, r.uniform(0.38, 0.5), hz * 1.05),
                              rocks, (zb - 0.05, H))
                if lod == 0 and r.random() < 0.45:      # fill stone in the joint
                    frock((x_in + side * band * r.uniform(0.3, 0.8), yf - 0.08, z + hz), (0.22, 0.18, 0.2), rocks, (0, H), fac=3)
                if moss_mi is not None and r.random() < 0.3:
                    fs_, vs_ = mb.ico((x_in + side * band * 0.75, yf - 0.12, z + hz), 0.09, moss_mi, subdiv=sub, scale=(1.4, 0.7, 0.55))
                z += hz * r.uniform(0.8, 0.95)
        # crown: irregular row of mixed blocks overhanging the canopy
        x = -xo + 0.05
        while x < xo - 0.05:
            w_ = min(xo + 0.1 - x, r.uniform(0.4, 0.9) * rs)
            ht = P['t_top'] * r.uniform(0.75, 1.0) + r.uniform(-1, 1) * P['crown_var']
            ht = max(0.25, min(ht, H - oz1 + 0.05))
            dep = (yf - y_fr) + P['crown_over'] + r.uniform(0.0, 0.1)
            zc = min(H - ht / 2, oz1 + ht / 2 - 0.02)
            frock((x + w_ / 2, yf - dep / 2, zc), (w_ * 1.12, dep, ht), rocks_w if r.random() < 0.3 else rocks,
                  (oz1 - 0.03, H))
            if lod == 0 and r.random() < 0.5:        # fill stone low in the crown joint, never above the block
                frock((x + w_, yf - 0.1, oz1 + min(ht, 0.4) * r.uniform(0.25, 0.5)), (0.24, 0.2, 0.22), rocks, (oz1, zc + ht / 2), fac=3)
            if moss_mi is not None and r.random() < 0.35:
                mb.ico((x + w_ * 0.5, yf - dep * 0.5, min(H - 0.03, zc + ht * 0.45)), 0.12, moss_mi, subdiv=sub, scale=(1.5, 1.0, 0.45))
            x += w_ * r.uniform(0.82, 0.95)
    for v in mb.bm.verts:
        v.co.x = min(max(v.co.x, -W / 2), W / 2)
        v.co.y = min(max(v.co.y, yb), yf)
        v.co.z = min(max(v.co.z, 0.0), H)

    # ---------------------------------------------------------------- timber frame + canopy
    kam_h = 0.2
    z_kam = oz1 - kam_h                                # kamoi bottom
    rh = min(0.34, (z_kam - z_s) * 0.17)
    z_k = z_kam - rh - 0.07 if (P['ranma'] and R['ranma'] and z_kam - z_s > 1.5) else z_kam   # shoji top
    sw0, sw1 = ox0 + pw, ox1 - pw
    mats = dict(wood=wood_l, paper=paper)
    if lod <= 2:
        if lod <= 1:
            mb.box(((sw0 + sw1) / 2, y_sh - 0.02, z_s + 0.008), (sw1 - sw0, 0.09, 0.016), wood)       # shiki
        z_pt = oz1 + 0.18                              # posts run 0.18 m past the kamoi, capped
        for x in (ox0 + pw / 2, ox1 - pw / 2):
            if R['post'] == 'oct':
                kg.post_oct(mb, x, y_post, z_s, z_pt, pw, wood, chamfer=0.16)
            else:
                mb.box((x, y_post, (z_s + z_pt) / 2), (pw, pw, z_pt - z_s), wood)
            if lod <= 1:
                mb.box((x, y_post + 0.01, z_pt + 0.1), (0.23, 0.23, 0.2), wood, bevel=R['bev'])        # cap block
        mb.box(((ox0 + ox1) / 2, y_post, z_kam + kam_h / 2), (ox1 - ox0 - 0.02, pw * 0.9, kam_h), wood, bevel=R['bev'])
        if z_k < z_kam:
            mb.box(((sw0 + sw1) / 2, y_post, z_k + 0.035), (sw1 - sw0, 0.1, 0.07), wood)
            ks.ranma(mb, M, sw0, sw1, z_k + 0.07, z_kam, y_sh, mats, lod, P['ranma_style'], r)
        # hisashi: thin (0.05 m) board sloping 5-8 deg forward, 0.35-0.45 m projection, rafter ends underneath
        cp = P['canopy']
        z_c = oz1 + 0.1
        dz = cp * P['canopy_pitch']
        y0c, y1c = y_post - pw / 2, y_post + pw / 2 + cp
        cw = ox1 - ox0 + 0.3
        Mc = kg.frame(Vector(((ox0 + ox1) / 2, (y0c + y1c) / 2, z_c - dz / 2)), Vector((0, y1c - y0c, -dz)))
        kg.cbox(mb, Mc, (cw, math.hypot(y1c - y0c, dz), 0.05), wood, bevel=0.006 if lod == 0 else 0.0)
        if lod <= 1:
            for x in (ox0 + pw / 2, ox1 - pw / 2):
                Mb_ = kg.frame(Vector((x, y_post + pw / 2 + cp * 0.35, z_c - 0.12)), Vector((0, 1, -0.6)))
                kg.cbox(mb, Mb_, (0.07, cp * 0.8, 0.07), wood)                                          # bracket
            if lod == 0:
                n = max(4, int(cw / 0.28))
                for k in range(n + 1):
                    x = (ox0 + ox1) / 2 - cw / 2 + 0.05 + (cw - 0.1) * k / n
                    yr0, yr1 = y_post + pw / 2, y1c - 0.03
                    Mt = kg.frame(Vector((x, (yr0 + yr1) / 2, z_c - 0.025 - dz * 0.5 - 0.03)), Vector((0, yr1 - yr0, -dz)))
                    kg.cbox(mb, Mt, (0.035, yr1 - yr0, 0.045), wood)                                    # rafter ends
        # shoji
        z0s = z_s + (0.016 if lod <= 1 else 0.0)
        koshi = min(0.3, max(0.25, 0.18 * (z_k - z0s)))
        if R['kumiko'] == 'panel':
            ks.shoji_run(mb, M, sw0, sw1, z0s, z_k, y_sh, mats, lod, P['panels'], r, cols=P['cols'], rows=P['rows'],
                         koshi=koshi, depth=0.03, bars_lod=0)
        else:
            vq = y_sh - 0.02
            ks.quad(mb, M, [(sw0, vq, z0s + koshi), (sw1, vq, z0s + koshi), (sw1, vq, z_k), (sw0, vq, z_k)], paper)
            ks.lbox(mb, M, ((sw0 + sw1) / 2, vq + 0.01, z0s + koshi / 2), (sw1 - sw0, 0.025, koshi), wood_l)
            if R['kumiko'] == 'long':
                ks.lattice_long(mb, M, sw0, sw1, z0s + koshi, z_k, y_sh, wood_l, P['panels'] * P['cols'], P['rows'],
                                bar=0.012, bar_d=0.02)
                for k in range(1, P['panels']):
                    u = sw0 + (sw1 - sw0) * k / P['panels']
                    ks.lbox(mb, M, (u, y_sh + 0.01, (z0s + z_k) / 2), (0.05, 0.02, z_k - z0s), wood_l)
                for zz in (z0s + koshi + 0.02, z_k - 0.02):
                    ks.lbox(mb, M, ((sw0 + sw1) / 2, y_sh + 0.01, zz), (sw1 - sw0, 0.02, 0.04), wood_l)
            else:
                ks.lattice_long(mb, M, sw0, sw1, z0s + koshi, z_k, y_sh, wood_l, P['panels'] * 2, 3, bar=0.03, bar_d=0.02)
    else:
        vq = y_sh
        ks.quad(mb, M, [(ox0, vq, z_s), (ox1, vq, z_s), (ox1, vq, oz1), (ox0, vq, oz1)], paper)
        fr = pw
        ring_o = [(ox0, z_s), (ox1, z_s), (ox1, oz1), (ox0, oz1)]
        ring_i = [(ox0 + fr, z_s), (ox1 - fr, z_s), (ox1 - fr, oz1 - 0.2), (ox0 + fr, oz1 - 0.2)]
        for k in (1, 2, 3):
            k2 = (k + 1) % 4
            ks.quad(mb, M, [(ring_o[k][0], y_fr, ring_o[k][1]), (ring_o[k2][0], y_fr, ring_o[k2][1]),
                            (ring_i[k2][0], y_fr, ring_i[k2][1]), (ring_i[k][0], y_fr, ring_i[k][1])], wood)
        ks.quad(mb, M, [(ox0 - 0.08, y_fr, oz1 + 0.05), (ox1 + 0.08, y_fr, oz1 + 0.05), (ox1 + 0.08, y_fr + 0.35, oz1),
                        (ox0 - 0.08, y_fr + 0.35, oz1)], wood)                                       # canopy

    # ---------------------------------------------------------------- ledge: lanterns + potted plants
    yl = (y_fr + yf - 0.05) / 2
    ls, lh = 0.2, 0.34
    ends = {-1: ox0 + 0.17, 1: ox1 - 0.17}
    inner = {-1: ox0 + 0.5, 1: ox1 - 0.5}
    ts = P['tall_side']
    if P['swap'] or (ox1 - ox0) < 1.3:
        lan_x = [ends[-1], ends[1]]
        pl = [(inner[-1], P['shrub_h'][0], P['shrub_kind'][0]), (inner[1], P['shrub_h'][1], P['shrub_kind'][1])]
    else:
        # tall shrub against one jamb, a lantern beside it; lantern at the other jamb, a short shrub beside it
        lan_x = [inner[ts], ends[-ts]]
        pl = [(ends[ts], P['tall_h'], 'pine'), (inner[-ts], P['shrub_h'][1] * 0.85, P['shrub_kind'][1])]
    if (ox1 - ox0) < 1.3:
        pl = []
    for x in lan_x:
        if lod <= 2:
            c = kg.lantern_box(mb, (x, yl, z_s), dict(iron=iron, paper=lpaper), lod, r, size=ls, height=lh,
                               roof='pyramid', corner_bars=lod == 0)
        else:
            mb.box((x, yl, z_s + lh / 2), (ls, ls, lh), lpaper)
            c = Vector((x, yl, z_s + lh / 2))
        lights.append(dict(type='point', pos=[round(c.x, 3), round(c.y, 3), round(c.z, 3)], color=[1.0, 0.6, 0.3],
                           radius=2.0, source='lantern_andon'))
    if P['plants'] and lod <= 2:
        pm = dict(pot=pot, bark=bark, leaf=leaf)
        for x, hh, kind in pl:
            tall = hh > 0.9
            hh = min(hh, z_k - z_s - 0.05)
            ks.bonsai_geo(mb, (x, yl, z_s), pm, lod, r, height=hh, tall=tall, y_lim=(y_fr - 0.05, yf))
    for v in mb.bm.verts:
        v.co.x = min(max(v.co.x, -W / 2), W / 2)
        v.co.y = min(max(v.co.y, yb), yf)
        v.co.z = min(max(v.co.z, 0.0), H)
    for v in mb.bm.verts:                           # rounded base blocks lift their bottom edge: seat on z = 0
        if v.co.z < 0.03:
            v.co.z = 0.0
    o = mb.to_object(ASSET)
    ks.orient_slot(o, [paper], (0, 1, 0))           # paper faces the viewer
    cx = (ox0 + ox1) / 2
    lights.insert(0, dict(type='area', pos=[round(cx, 3), round(y_sh + 0.08, 3), round((z_s + oz1) / 2, 3)], normal=[0, 1, 0],
                          size=[round(ox1 - ox0, 3), round(oz1 - z_s, 3)], color=[1.0, 0.63, 0.34], watts=60,
                          source='lantern_andon (shoji)'))
    o['kz_lights'] = json.dumps(lights)
    o['kz_flicker'] = json.dumps(sorted({paper, lpaper}))
    o['kz_params'] = json.dumps({k: v for k, v in P.items()})
    genlib.finish(o)
    ks.smooth_slots(o, [pot] if lod <= 1 else [])
    kg.uv_grain(o, [wood, wood_l])
    if lpaper != paper:
        kg.uv_unit(o, [lpaper])
    return o
