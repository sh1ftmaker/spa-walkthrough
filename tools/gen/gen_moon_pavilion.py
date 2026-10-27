"""Tsukimi moon-viewing pavilion (s_moon, Tsukimi Moon Deck H2): open pyramidal-roof pavilion on the cliff top.

Identifying features kept at every LOD: open pavilion under a pyramidal (hokei) tiled roof with a finial, on
posts over a raised timber deck, railings round the deck with a stair in front, lit by paper lanterns.

Targets (measured):
  * refs/gen/sheet-mod-pavilions.png #03 "Tsukimi moon-viewing pavilion" (front + side, labels 10 m / 10 m / 7 m;
    the drawn 5 m bar (~39 px/m) disagrees with the labels by ~40 %, so the build follows the labels and takes
    ratios off the drawing): square plan, roof eave-to-eave 10 m on both views; overall height 7 m from the deck
    foot to the finial top; post line ~0.71 of the eave width (eave overhang ~1.4 m beyond the posts); deck top
    ~0.1 of the height above grade with a 4-riser stair (0.17 m risers) in the middle of the front; koran railing
    ~0.8 m round the deck with newel posts and lanterns on the posts either side of the stair; four posts visible
    per side on the front (three bays), a dark lattice frieze under the head beam, one large lantern glowing under
    the roof centre; roof: pyramidal with strongly lifted corners (sori), ridge-less apex with a roban block and a
    hoju finial (~0.8 m).  The rock plinth under the deck in the sheet belongs to the place model.
  * lookbook 30 (H2 Tsukimi Moon Deck) and 32 (suites cliff): the pavilion on a timber deck at the cliff edge,
    dark tiled pyramid roof, warm light inside.
  * Row: w 7-10 m, h 6.5-7 m, posts 4-8, rail, steps, roof via roof_tiled; budget 15000/6000/1800/250.
    Proxy 10 x 10 x 7 m (frame=true, host=true).

Construction (one mesh): timber deck (planks over joists, edge beam, under-deck stub posts and sill beams), stair
with stringers, dark-timber posts (chamfered at LOD0) with bronze-less wooden bases and masu bracket blocks, head
beams (keta), nuki tie beams, lattice frieze between head and frieze rail, coffered ceiling with battens under the
roof, koran railing (top / mid / bottom rails, posts with giboshi caps), newel lanterns flanking the stair and on the
deck corners, a large round paper lantern hanging from the ceiling centre, roof from kzgeo_roof_tiled
(type 'pyramid': kawara field, tile ribs, eave discs, hip ridges, fascia, soffit, rafter tails, roban + finial).
The roof pitch is solved per seed so the finial top lands on h.

Parameters (defaults inside the proxy):
  w        7-10 m   eave-to-eave (square), default 9.6-10.0 seeded
  h        6.5-7 m  overall height, default 6.8-7.0 seeded
  posts    posts per side 2-4 (total 4 / 8 / 12; the row's "posts 4-8" counts the corner + mid posts, the sheet
           shows 4 per side), default cycles with the seed: 1 -> 4 (sheet), 2 -> 2 (four posts), 3 -> 3
  rail     True / False (default True)
  steps    'front' | 'front_back' (default seeded, mostly 'front')
  eave     roof overhang beyond the post line, 1.1-1.5 m (default seeded)
Seeds change: post count per side, eave overhang (post spacing), roof pitch / sori lift, deck height (3-5 risers),
stair width, corner lanterns, back stair, frieze lattice spacing, ceiling battens.

Materials: hinoki dark_timber (posts, beams, frieze, ceiling frame), hinoki stained (railing), hinoki wet_oiled
(deck, stair treads), lacquer_dark (lantern caps, ceiling panels, frieze backing), lantern_paper (round lantern),
lantern_andon (newel lanterns), iron (lantern frames, finial), kawara (roof via roof_tiled).
Lighting: lightmap + emissive.  obj['kz_lights']: the centre lantern (2600 K, 120 W) + one point per newel lantern.
Custom props: kz_deck_z (walkable deck top), kz_roof (wall_top, top_z), kz_params.  Animation: none.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_roof_tiled as KR

ASSET = 'moon_pavilion'
FEATURES = ['open pavilion under a pyramidal tiled roof with finial', 'posts over a raised timber deck',
            'railings with a front stair', 'paper lanterns']


def params(seed, w=None, h=None, posts=None, rail=None, steps=None, eave=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'pavilion')
    P = dict(w=float(w) if w else p['w'] * g.uniform(0.96, 0.995),
             h=float(h) if h else p['h'] * g.uniform(0.97, 0.995))
    P['posts'] = int(posts) if posts else C.cycle(seed, [4, 2, 3])
    P['rail'] = True if rail is None else bool(rail)
    gs = C.rng(seed, 'steps')
    P['steps'] = steps or ('front_back' if gs.random() < 0.3 else 'front')
    P['risers'] = gs.choice([4, 4, 3])
    P['step_w'] = gs.uniform(2.0, 2.6)
    P['eave'] = float(eave) if eave else g.uniform(1.35, 1.55)
    P['up'] = g.uniform(0.3, 0.42)
    P['tp'] = g.uniform(0.25, 0.29)
    P['p'] = g.uniform(1.15, 1.35)
    P['post_h'] = g.uniform(3.0, 3.3)
    gd = C.rng(seed, 'detail')
    P['corner_lanterns'] = gd.random() < 0.7
    P['frieze_sp'] = gd.uniform(0.2, 0.28)
    P['battens'] = gd.choice([5, 7, 9])
    return P


def _quad(mb, pts, mi):
    bm = mb.bm
    f = bm.faces.new([bm.verts.new(p) for p in pts]); f.material_index = mi
    return f


def _post_open(mb, x, y, z0, z1, w, mi):
    """4-sided post without caps (LOD3: 8 tris)"""
    h = w / 2
    c = [(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]
    for i in range(4):
        (ax, ay), (bx, by) = c[i], c[(i + 1) % 4]
        _quad(mb, [(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], mi)


def _roof_mats(mb):
    return dict(tile=mb.slot('kawara'), ridge=mb.slot('kawara'), wood=mb.slot('hinoki', variant='dark_timber'),
                wood_d=mb.slot('lacquer_dark', wear=0.1), iron=mb.slot('iron', wear=0.2))


def solve_roof(P):
    """pitch so that the finial top lands on h: dry runs of the LOD2 roof at z_e = 0"""
    hw = P['w'] / 2
    deck = 0.17 * P['risers']
    def dry(pitch):
        tmp = genlib.MeshBuilder()
        info = KR.roof_into(tmp, _roof_mats(tmp), 2, 'pyramid', hw, hw, z_e=0.0, pitch=pitch, eave=P['eave'],
                            up=P['up'], tp=P['tp'], p=P['p'])
        tmp.bm.free()
        return info
    post_h = P['post_h']
    for _ in range(3):
        lo, hi = 16.0, 40.0
        for _ in range(18):
            mid = (lo + hi) / 2
            info = dry(mid)
            top = deck + post_h - info['wall_top'] + info['top_z']
            if top > P['h']:
                hi = mid
            else:
                lo = mid
        info = dry(lo)
        top = deck + post_h - info['wall_top'] + info['top_z']
        if abs(top - P['h']) < 0.05:
            break
        post_h -= (top - P['h'])          # pitch hit a bound: give the difference to the posts
        post_h = max(2.6, min(3.8, post_h))
    return lo, post_h, info


def build(lod, seed, w=None, h=None, posts=None, rail=None, steps=None, eave=None, **_):
    P = params(seed, w, h, posts, rail, steps, eave)
    pitch, post_h, info0 = solve_roof(P)
    P['pitch'], P['post_h'] = pitch, post_h
    budget = genlib.budget_of(ASSET)
    mb = genlib.MeshBuilder()
    rm = _roof_mats(mb)
    m_post, m_lac = rm['wood'], rm['wood_d']
    m_rail = mb.slot('hinoki', variant='stained', wear=0.2)
    m_deck = mb.slot('hinoki', variant='wet_oiled', wear=0.3)
    m_iron = rm['iron']
    m_paper = mb.slot('lantern_paper', emissive_level=0.8)
    m_andon = mb.slot('lantern_andon', emissive_level=0.9)
    lights = []
    hw = P['w'] / 2
    a = hw - P['eave']                       # post line half extent
    deck_top = 0.17 * P['risers']
    dh = min(a + 0.45, hw - 0.22 - 0.28 * (P['risers'] - 1))   # deck half extent (stair stays under the eave)
    ps = 0.26 if P['posts'] <= 2 else 0.24
    wall_top = deck_top + post_h
    z_e = wall_top - info0['wall_top']
    # ---------------------------------------------------------------- roof (pyramid via roof_tiled)
    rb = int(budget[lod] * (0.5 if lod < 3 else 0.42)) if budget else None
    info = KR.roof_into(mb, rm, lod, 'pyramid', hw, hw, z_e=z_e, pitch=pitch, eave=P['eave'], up=P['up'], tp=P['tp'],
                        p=P['p'], budget=rb)
    if info['notes'] and any(info['notes']):
        print(f'moon_pavilion LOD{lod} s{seed} roof resolution fallback: {info["notes"]}')
    wt = info['wall_top']
    # ---------------------------------------------------------------- deck
    dt = 0.06                                # plank thickness
    if lod == 0:
        n = int(2 * dh / 0.19)
        pw = 2 * dh / n
        for i in range(n):
            y = -dh + pw * (i + 0.5)
            mb.box((0, y, deck_top - dt / 2), (2 * dh - 0.02, pw - 0.012, dt), m_deck)
    elif lod <= 2:
        mb.box((0, 0, deck_top - dt / 2), (2 * dh, 2 * dh, dt), m_deck)
    else:                                    # LOD3: the deck as one block on the ground
        mb.box((0, 0, deck_top / 2), (2 * dh + 0.2, 2 * dh + 0.2, deck_top), m_deck)
    # edge beam (en-gamachi) and under-deck structure
    eb = 0.22
    for sgn in ((-1, 1) if lod <= 2 else ()):
        mb.box((0, sgn * (dh + 0.05), deck_top - eb / 2 - 0.01), (2 * dh + 0.2, 0.1, eb), m_post)
        mb.box((sgn * (dh + 0.05), 0, deck_top - eb / 2 - 0.01), (0.1, 2 * dh, eb), m_post)
    if lod <= 2:
        k = max(2, int(round(2 * dh / 2.0)))
        for i in range(k + 1):
            for j in range(k + 1):
                x, y = -dh + 0.15 + (2 * dh - 0.3) * i / k, -dh + 0.15 + (2 * dh - 0.3) * j / k
                if lod <= 1 or (i in (0, k) and j in (0, k)):
                    mb.box((x, y, (deck_top - dt - eb) / 2), (0.18, 0.18, deck_top - dt - eb + 0.02), m_post)
        if lod <= 1:
            for j in range(k + 1):               # sill beams under the joists
                y = -dh + 0.15 + (2 * dh - 0.3) * j / k
                mb.box((0, y, deck_top - dt - 0.08), (2 * dh - 0.1, 0.14, 0.16), m_post)
    # ---------------------------------------------------------------- stairs
    sw = P['step_w']
    nr = P['risers']
    sides = [1] + ([-1] if P['steps'] == 'front_back' else [])
    for sy in sides:
        if lod == 3:
            L3 = 0.28 * (nr - 1)
            mb.box((0, sy * (dh + 0.1 + L3 / 2), deck_top * 0.33), (sw, L3, deck_top * 0.66), m_deck)
            continue
        for k in range(1, nr):
            ztop = deck_top - 0.17 * k
            y0 = dh + 0.1 + 0.28 * (k - 1)
            mb.box((0, sy * (y0 + 0.14), ztop / 2), (sw, 0.28, ztop), m_deck)
        if lod <= 2:
            L = 0.28 * (nr - 1) + 0.12
            for sx in (-1, 1):                   # stringers (side cheeks)
                bm = mb.bm
                ys = [dh + 0.1, dh + 0.1, dh + 0.1 + L, dh + 0.1 + L]
                zs = [0.0, deck_top + 0.02, 0.17 + 0.02, 0.0]
                prof = [(sy * yy, zz) for yy, zz in zip(ys, zs)]
                x0, x1 = (sw / 2, sw / 2 + 0.07) if sx > 0 else (-sw / 2 - 0.07, -sw / 2)
                kg.prism_x(mb, prof, x0, x1, m_post)
    # ---------------------------------------------------------------- posts, brackets, beams
    n = P['posts']
    xs = [-a + 2 * a * i / (n - 1) for i in range(n)]
    perim = []
    for i, x in enumerate(xs):
        perim.append((x, -a)); perim.append((x, a))
    for y in xs[1:-1]:
        perim.append((-a, y)); perim.append((a, y))
    for x, y in perim:
        if lod == 0:
            C.chamfered_bar(mb, (x, y, deck_top + (wt - 0.05 - deck_top) / 2), (ps, ps, wt - 0.05 - deck_top),
                            m_post, ch=0.03)
            mb.box((x, y, deck_top + 0.09), (ps + 0.06, ps + 0.06, 0.18), m_lac)       # lacquered post foot
            mb.box((x, y, wt - 0.36), (ps + 0.1, ps + 0.1, 0.12), m_post)            # masu bracket block
        elif lod <= 2:
            mb.box((x, y, (wt + deck_top) / 2), (ps, ps, wt - deck_top), m_post)
        else:
            _post_open(mb, x, y, deck_top, wt, ps, m_post)
    # head beams (keta) close the gap to the soffit, nuki tie + frieze rail below, lattice between
    kb = 0.3
    zk = wt - 0.3 + kb / 2 + 0.1
    for sgn in ((-1, 1) if lod <= 2 else ()):
        mb.box((0, sgn * a, zk), (2 * a + ps + 0.3, ps * 0.9, kb + 0.2), m_post)
        mb.box((sgn * a, 0, zk), (ps * 0.9, 2 * a + ps + 0.3, kb + 0.2), m_post)
    zf = wt - 0.95                           # frieze rail
    if lod <= 2:
        for sgn in (-1, 1):
            mb.box((0, sgn * a, zf), (2 * a + ps + 0.3 * (lod <= 1), 0.12, 0.14), m_post)
            mb.box((sgn * a, 0, zf), (0.12, 2 * a + ps + 0.3 * (lod <= 1), 0.14), m_post)
    zb = wt - 0.30                          # head beam underside
    if lod <= 1:
        sp = P['frieze_sp']
        for sgn in (-1, 1):
            for along in ('x', 'y'):
                for x0, x1 in zip(xs[:-1], xs[1:]):
                    a0, a1 = x0 + ps / 2, x1 - ps / 2
                    m = max(2, int((a1 - a0) / sp))
                    for k in range(1, m):
                        u = a0 + (a1 - a0) * k / m
                        c = (u, sgn * a, (zf + zb) / 2) if along == 'x' else (sgn * a, u, (zf + zb) / 2)
                        s = (0.045, 0.05, zb - zf) if along == 'x' else (0.05, 0.045, zb - zf)
                        mb.box(c, s, m_post)
                    # lit-ish backing panel recessed behind the lattice (dark lacquer)
                    c = ((a0 + a1) / 2, sgn * (a - 0.04), (zf + zb) / 2) if along == 'x' else (sgn * (a - 0.04), (a0 + a1) / 2, (zf + zb) / 2)
                    s = (a1 - a0, 0.02, zb - zf - 0.05) if along == 'x' else (0.02, a1 - a0, zb - zf - 0.05)
                    if lod == 0:
                        mb.box(c, s, m_lac)
    elif lod == 2:
        for sgn in (-1, 1):
            mb.box((0, sgn * (a - 0.02), (zf + zb) / 2), (2 * a, 0.05, zb - zf), m_post)
            mb.box((sgn * (a - 0.02), 0, (zf + zb) / 2), (0.05, 2 * a, zb - zf), m_post)
    # ceiling under the roof (closes the open underside inside the post line), battens at LOD0
    zc = wt + 0.1
    if lod <= 2:
        mb.box((0, 0, zc - 0.05), (2 * a + 0.2, 2 * a + 0.2, 0.1), m_lac)
    else:
        e = a + 0.1
        _quad(mb, [(-e, -e, zc - 0.1), (-e, e, zc - 0.1), (e, e, zc - 0.1), (e, -e, zc - 0.1)], m_lac)
    if lod == 0:
        nb = P['battens']
        for i in range(1, nb + 1):
            u = -a + 2 * a * i / (nb + 1)
            mb.box((u, 0, zc - 0.13), (0.07, 2 * a, 0.06), m_post)
            mb.box((0, u, zc - 0.13), (2 * a, 0.07, 0.06), m_post)
    # ---------------------------------------------------------------- railings (koran)
    if P['rail']:
        rh = 0.82
        r_in = dh - 0.08
        open_w = sw / 2 + 0.05
        segs = []                            # (p0, p1) runs along the deck edge
        for sgn in (-1, 1):
            if sgn == 1 or P['steps'] == 'front_back':
                segs.append(((-r_in, sgn * r_in), (-open_w, sgn * r_in)))
                segs.append(((open_w, sgn * r_in), (r_in, sgn * r_in)))
            else:
                segs.append(((-r_in, sgn * r_in), (r_in, sgn * r_in)))
            segs.append(((sgn * r_in, -r_in), (sgn * r_in, r_in)))
        newels = set()
        for (x0, y0), (x1, y1) in segs:
            L = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            m = max(1, int(math.ceil(L / 1.25)))
            for k in range(m + 1):
                px, py = x0 + ux * L * k / m, y0 + uy * L * k / m
                key = (round(px, 2), round(py, 2))
                if key in newels:
                    continue
                newels.add(key)
                end = k in (0, m)
                pw = 0.11 if end else 0.08
                ph = rh + (0.12 if end else 0.0)
                if lod <= 2:
                    mb.box((px, py, deck_top + ph / 2), (pw, pw, ph), m_rail)
                if lod <= 1 and end:
                    kg.giboshi(mb, (px, py, deck_top + ph), m_rail, lod, scale=1.1)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if lod == 3:                     # top rail as one outward quad
                zt_ = deck_top + rh
                _quad(mb, [(x0, y0, zt_ - 0.25), (x1, y1, zt_ - 0.25), (x1, y1, zt_), (x0, y0, zt_)], m_rail)
                continue
            for z, t, hh in ((rh - 0.03, 0.075, 0.06), (0.45, 0.05, 0.045), (0.1, 0.06, 0.05)):
                if lod == 2 and z < 0.4:
                    continue
                if lod == 3 and z < rh - 0.1:
                    continue
                sx = abs(x1 - x0) + (0.0 if lod else 0.0)
                size = (L, t, hh) if abs(ux) > 0.5 else (t, L, hh)
                mb.box((cx, cy, deck_top + z), size, m_rail)
        # newel lanterns flanking the stair(s) and on the deck corners
        spots = []
        for sy in sides:
            spots += [(-open_w, sy * r_in), (open_w, sy * r_in)]
        if P['corner_lanterns']:
            spots += [(sx * r_in, sy * r_in) for sx in (-1, 1) for sy in (-1, 1)]
        for x, y in spots:
            base = (x, y, deck_top + rh + 0.12 + (0.16 if lod <= 1 else 0.0))
            if lod <= 2:
                c = C.lantern_head(mb, base, dict(iron=m_iron, paper=m_andon), lod, size=0.22, height=0.38, roof='hip')
            else:
                bm = mb.bm
                q = [bm.verts.new(v) for v in ((x - 0.11, y, base[2]), (x + 0.11, y, base[2]),
                                                (x + 0.11, y, base[2] + 0.38), (x - 0.11, y, base[2] + 0.38))]
                f = bm.faces.new(q); f.material_index = m_andon
                c = Vector((x, y, base[2] + 0.19))
            lights.append(C.light_entry(c, color_k=2200, watts=15))
    # ---------------------------------------------------------------- the big round lantern under the roof centre
    R, LH = 0.34, 0.72
    zl = zc - 0.9 - LH
    segs = C.lod_pick(lod, 20, 12, 8, 6)
    if lod <= 2:
        prof = [(R * 0.62, 0.0), (R * 0.88, LH * 0.12), (R, LH * 0.35), (R, LH * 0.65), (R * 0.88, LH * 0.88), (R * 0.62, LH)]
        if lod == 2:
            prof = [prof[0], prof[2], prof[3], prof[5]]
        C.lathe(mb, prof, segs, m_paper, base=(0, 0, zl))
        for z0, z1 in ((zl - 0.06, zl + 0.02), (zl + LH - 0.02, zl + LH + 0.06)):
            C.lathe(mb, [(R * 0.66, z0), (R * 0.66, z1)], segs, m_lac, closed=True)
        C.rope_cord(mb, (0, 0, zl + LH + 0.06), (0, 0, zc - 0.1), 0.012, m_iron, sides=C.lod_pick(lod, 6, 4, 2),
                    twist=False)
        if lod == 0:                         # rib hoops
            for t in (0.2, 0.5, 0.8):
                zz = zl + LH * t
                rr = R * (0.94 if t != 0.5 else 1.0) + 0.004
                C.lathe(mb, [(rr, zz - 0.006), (rr + 0.004, zz), (rr, zz + 0.006)], segs, m_lac, closed=False)
    else:
        C.lathe(mb, [(R * 0.62, 0.0), (R, LH * 0.5), (R * 0.62, LH)], 5, m_paper, base=(0, 0, zl))
    lights.append(C.light_entry((0, 0, zl + LH / 2), color_k=2600, watts=120))
    # ---------------------------------------------------------------- finish
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    kg.uv_grain(o, [m_post, m_rail, m_deck])
    for L in lights:
        L['pos'] = [round(L['pos'][0] + dx, 4), round(L['pos'][1] + dy, 4), round(L['pos'][2] + dz, 4)]
    C.set_json_props(o, kz_lights=lights, kz_deck_z=round(deck_top + dz, 3),
                     kz_roof=dict(type='pyramid', wall_top=round(wt + dz, 3), top_z=round(info['top_z'] + dz, 3),
                                  pitch=round(pitch, 2)),
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o
