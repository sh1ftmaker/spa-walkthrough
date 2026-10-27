"""Engawa pavilion (rest / tea pavilion, warming hut, robing pavilion, beach lounge).

Identifying features kept at every LOD: timber pavilion on a raised engawa deck, glowing shoji front, tiled roof
edge, lanterns at the steps.

Construction (one mesh, library materials):
  * podium       - optional rough basalt podium (0.8-1.4 m, default on for 'mirror' / 'glacier' and seed-cycled
                   otherwise): carved core block skirted by clustered rounded boulders (0.4-0.8 m), with a central
                   cut-stone stair (4-6 risers, up to 2.5 m wide) set between boulder cheeks and cut into the engawa
                   edge, lanterns on the cheeks. Without it: carved plinth wall, soseki footings, slab steps.
  * deck         - engawa planks running along the front (and the side decks), edge beam (en-gamachi), tatami
                   floor inside the room.
  * frame        - dark-timber hashira on a bays x side-bays grid (thick 0.2-0.24 m veranda posts, slimmer room
                   posts), keta eave beams, side beams, nuki tie beam with protruding ends, masu + hijiki brackets,
                   ceiling with battens.
  * walls        - 2 sliding shoji per bay (lighter timber, kumiko, lit paper, koshi boards on sides and back), lit
                   ranma transoms; 'open' front leaves the room front open (lit back and side shoji, low table,
                   cushions, scroll show through), 'shoji' front closes it with one bay slid open.
  * roof         - kzgeo_pavilion_engawa.roof: restrained Japanese roof ('irimoya' hip-and-gable with the gable in
                   the top ~40 % of the rise, 'hip' or 'gable'), only 5-8 deg of tip lift, semi-round tile ribs,
                   round eave-end tiles, tile lip, noshi ridge with low blocky onigawara, hip and rake ridges, gable
                   board with slats + bargeboards, fascia, soffit, rafter ends.
  * lean-to      - optional single-side hisashi (~1.2 m, tiled mono-pitch) under the main side eave, on two posts,
                   with a deck extension (default on for 'mirror' and seed 1).
  * lanterns     - iron-framed andon lanterns flanking the stair, optional floor andon on the deck corners; side
                   railings (koran) where there are no steps.

Parameters (defaults = proxy 8 x 5 x 5.5 m in 3d/assets.json; stay inside it):
  w        4-8 m      overall width (eave tip to eave tip, lean-to included)
  d        3.5-5 m    overall depth (eave to eave; the stair stays under the front eave)
  h        overall height to the ridge ends (default podium + 4.2, capped by the proxy)
  floor_h  0.45 m     deck height above the podium (or the ground)
  bays     2-4        front bays (default seeded from w)
  roof     'irimoya' | 'hip' | 'gable' (the roof_tiled component is built here; default cycles with the seed)
  front    'shoji' | 'open'
  steps    'front' | 'left' | 'right'   (the podium always takes the central front stair)
  podium   None | False | height 0.8-1.4 m
  leanto   None | False | True | width 1.0-1.5 m  (side seeded)
  variant  None | 'mirror' | 'glacier' | 'falls' | 'beach'  (presets for the four uses; explicit params win)
Seeded shape variation: roof style, podium and lean-to (cycle with the seed), pitch curve, overhang, gable line,
post height, engawa depth, side decks, bays, which bay is slid open, boulder layout, corner lanterns, railings,
kumiko grid, ranma lattice style, timber tint.

Materials: hinoki (dark_timber variant for the structure, lighter tints for shoji frames / kumiko and the deck),
lacquer_dark (bargeboards, gable board), kawara for the tiles when the library has it (else iron), lantern_andon (lit
shoji / ranma / lantern paper; washi_backlit still renders without emission here), basalt_dry (podium, boulders),
paving (cut-stone stair), moss on boulder tops when the library has it, tatami (room floor), noren (cushions).
Lighting: lightmap + emissive.  obj['kz_lights'] = JSON list: {type:'area', pos, normal, size, color, watts} for each
lit wall (front / back / sides; watts split from the 150 W proxy light) and {type:'point', pos, color, radius} per
lantern.  obj['kz_flicker'] = slot indices of the emissive paper (optional soft flicker).  Animation: none.
"""
import json
import math

from mathutils import Matrix, Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_pavilion_engawa as kp
import kzgeo_shoji_wall_bay as ks
from gen_torii_basalt import Rock, rounded_rock

ASSET = 'pavilion_engawa'
FEATURES = ['timber pavilion on a raised engawa deck', 'glowing shoji front', 'tiled roof edge',
            'lanterns at the steps']

VARIANTS = {
    'mirror': dict(w=8.0, d=5.0, roof='irimoya', front='shoji', steps='front', bays=3, podium=True, leanto=True, eng=1.3),
    'glacier': dict(w=4.6, d=3.8, roof='irimoya', front='shoji', steps='front', bays=2, hb=4.0, podium=True, leanto=False),
    'falls': dict(w=6.4, d=4.4, roof='hip', front='shoji', steps='front', bays=3, podium=False, leanto=False),
    'beach': dict(w=7.2, d=4.6, roof='hip', front='open', steps='front', bays=4, podium=False, leanto=False),
}

RES = {
    0: dict(roof=dict(rings=7, n_long=18, n_short=10, up_rows=4, ribs=True, rib_segs=3, rib_prof=3, discs=True,
                      disc_n=5, rafters=True, rafter_sp=0.38, fascia=True, fascia_n=8, soffit=True, ridge_prof='full', teeth=0),
            planks=True, post='oct', brackets=True, shoji='panel', ranma=True, steps_cuts=2, lantern=0, props=2,
            plinth_cuts=3, rail='full', ceiling_battens=True),
    1: dict(roof=dict(rings=4, n_long=10, n_short=6, up_rows=2, ribs=True, rib_segs=2, rib_prof=2, discs=False,
                      disc_n=4, rafters=False, fascia=True, fascia_n=4, soffit=True, ridge_prof='box', teeth=0),
            planks=False, post='box', brackets=True, shoji='long', ranma=True, steps_cuts=1, lantern=1, props=1,
            plinth_cuts=1, rail='simple', ceiling_battens=False),
    2: dict(roof=dict(rings=2, n_long=6, n_short=4, up_rows=1, ribs=False, rib_segs=0, rib_prof=0, discs=False,
                      disc_n=0, rafters=False, fascia=True, fascia_n=2, soffit=True, ridge_prof='box', teeth=0.5),
            planks=False, post='box', brackets=False, shoji='min', ranma=False, steps_cuts=0, lantern=2, props=0,
            plinth_cuts=0, rail='none', ceiling_battens=False),
    3: dict(roof=dict(rings=1, n_long=2, n_short=1, up_rows=1, ribs=False, rib_segs=0, rib_prof=0, discs=False,
                      disc_n=0, rafters=False, fascia=False, fascia_n=1, soffit=False, ridge_prof='tri', teeth=0),
            planks=False, post='none', brackets=False, shoji='none', ranma=False, steps_cuts=-1, lantern=3, props=0,
            plinth_cuts=-1, rail='none', ceiling_battens=False),
}


def _params(seed, w, d, h, floor_h, bays, roof, front, steps, variant, podium=None, leanto=None):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    V = dict(VARIANTS.get(variant, {}))
    w = float(w or V.get('w') or p['w'])
    d = float(d or V.get('d') or p['d'])
    P = dict(w=w, d=d, variant=variant)
    P['floor_h'] = float(floor_h or 0.45)
    k = (int(seed) - 1) % 3
    P['roof'] = roof or V.get('roof') or ['irimoya', 'hip', 'gable'][k]
    P['front'] = front or V.get('front') or (['shoji', 'open', 'shoji'][k] if r.random() < 0.8 else r.choice(['shoji', 'open']))
    pod = podium if podium is not None else V.get('podium', [True, False, True][k])
    P['podium'] = 0.0 if not pod else (float(pod) if not isinstance(pod, bool) else r.uniform(1.1, 1.3))
    P['podium'] = min(1.4, P['podium'])
    P['steps'] = 'front' if P['podium'] else (steps or V.get('steps') or r.choice(['front', 'front', 'left', 'right']))
    lt = leanto if leanto is not None else V.get('leanto', [True, False, False][k] and w >= 6.5)
    P['leanto'] = 0.0 if not lt else (float(lt) if not isinstance(lt, bool) else r.uniform(0.95, 1.1))
    P['leanto_side'] = r.choice([-1, 1])
    hb = float(V.get('hb', 4.2))
    P['h'] = float(h) if h else min(p['h'], P['podium'] + hb)
    P['bays'] = int(bays or V.get('bays') or max(2, min(4, round((w - P['leanto']) / r.uniform(2.1, 2.6)))))
    sc = min(1.0, d / 5.0)
    P['ov'] = r.uniform(0.85, 1.0) * (0.75 + 0.25 * sc)
    P['ovs'] = P['ov'] * r.uniform(0.85, 0.98)
    P['post_h'] = r.uniform(1.95, 2.1) * (0.93 + 0.07 * sc)
    P['eng'] = max(V.get('eng', 0.0), r.uniform(1.15, 1.45) * (0.75 + 0.25 * sc))
    P['side_deck'] = r.uniform(0.25, 0.5) if r.random() < 0.75 else 0.12
    P['p'] = r.uniform(1.15, 1.35)
    P['up'] = r.uniform(0.13, 0.17)                 # sori: ~8 deg tip lift over the last 0.8 m (measured on sheet 01)
    P['dg'] = 0.6 ** (1 / P['p']) + r.uniform(-0.03, 0.03)   # irimoya gable in the top ~40 % of the rise
    P['tp'] = r.uniform(0.21, 0.24)
    P['open_bay'] = P['bays'] // 2 if r.random() < 0.7 else r.randrange(P['bays'])
    P['open_frac'] = r.uniform(0.55, 0.9)
    P['corner_lanterns'] = True
    P['rails'] = r.random() < 0.7
    P['cols'] = r.choice([3, 4])
    P['rows'] = r.choice([6, 7, 7])
    P['ranma_style'] = r.choice(['tate', 'yoko'])
    P['step_w'] = r.uniform(1.3, 1.8) * (0.8 + 0.2 * sc)
    P['wood_tint'] = (round(r.uniform(0.26, 0.3), 3), round(r.uniform(0.17, 0.2), 3), round(r.uniform(0.11, 0.13), 3))
    P['shoji_tint'] = (round(r.uniform(0.42, 0.48), 3), round(r.uniform(0.29, 0.32), 3), round(r.uniform(0.17, 0.2), 3))
    P['paper_tint'] = (1.0, round(r.uniform(0.7, 0.75), 3), round(r.uniform(0.36, 0.42), 3))
    return P, r


def _step_stone(mb, c, size, mi, rk, cuts, r, top):
    if cuts < 0:
        mb.box(c, size, mi)
        return
    if cuts == 0:
        mb.box(c, size, mi)
        return
    fs = rounded_rock(mb, c, size, mi, rk, cuts, 0.7, 0.5, round_r=0.05, batter=0.04)
    for v in {v for f in fs for v in f.verts}:
        if v.co.z > top:
            v.co.z = top
        if v.co.z < 0:
            v.co.z = 0.0


def _variant(mid, name, **over):
    v = dict(genlib.matlib.manifest()[mid].get('variants', {}).get(name, {}))
    v.update(over)
    if 'tint' in v:
        v['tint'] = tuple(v['tint'])
    return v


def _has(mid):
    return mid in genlib.matlib.manifest()


def build(lod, seed, w=None, d=None, h=None, floor_h=None, bays=None, roof=None, front=None, steps=None,
          variant=None, podium=None, leanto=None, **_):
    P, r = _params(seed, w, d, h, floor_h, bays, roof, front, steps, variant, podium, leanto)
    R = RES[lod]
    W_full, D, H = P['w'], P['d'], P['h']
    L, ls = P['leanto'], P['leanto_side']
    W = W_full - L                                  # main building width; the lean-to takes the rest on one side
    cxm = -ls * L / 2                               # main building centre after the final shift
    hw, hd = W / 2 - 0.005, D / 2 - 0.005
    ov, ovs = P['ov'], P['ovs']
    ph = P['podium']
    zg = ph                                         # building ground (podium top or grade)
    zd = ph + P['floor_h']
    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', **_variant('hinoki', 'stained', wear=0.3))                          # structure (aged)
    wood_s = mb.slot('hinoki', wear=0.25) if lod <= 2 else wood                                 # shoji / kumiko
    wood_l = mb.slot('hinoki', wear=0.45)                                                       # deck boards
    wood_d = mb.slot('lacquer_black' if _has('lacquer_black') else 'lacquer_dark', wear=0.15) if lod <= 2 else wood   # lintels, nuki, fascia
    tile = mb.slot('kawara') if _has('kawara') else mb.slot('iron', wear=0.06, roughness_offset=0.12, tint=(0.62, 0.66, 0.72))
    paper = mb.slot('washi_backlit', emissive_level=round(r.uniform(0.95, 1.1), 2))   # lit shoji paper (library fix landed)
    lpaper = mb.slot('lantern_andon', emissive_level=1.0, tint=(1.0, 0.8, 0.55)) if lod <= 2 else paper
    stone = mb.slot('basalt_dry', wetness=0.1)
    rocks = mb.slot('basalt_dry', wetness=0.2) if lod <= 1 else stone            # fractured podium rocks
    cut = mb.slot('basalt_dry', wetness=0.05, roughness_offset=-0.1) if lod <= 2 else stone   # dressed treads / kerb
    moss = None          # moss on single boulder facets read as green shards; left off (see report)
    iron = mb.slot('iron', wear=0.25) if lod <= 2 else tile
    tatami = mb.slot('tatami') if lod <= 1 else wood_l
    cloth = mb.slot('noren') if lod == 0 else wood
    scroll = mb.slot('washi', tint=(0.9, 0.85, 0.75)) if lod == 0 else wood
    rk = Rock(r, cell=0.35, stretch=(1.0, 1.0, 0.8), amp=0.04, crack=0.05, glassy=0.0, width=0.3, fbm=0.1)
    lights = []

    # ---------------------------------------------------------------- plan
    X = hw - ovs                                   # side post line
    y_f, y_b = hd - ov, -(hd - ov)                 # front veranda posts / back posts
    y_r = y_f - P['eng']                           # room front wall
    nb = P['bays']
    # bays: the centre bay is wider (1.6x) for odd counts, as in sheet 01
    wts = [1.6 if (nb % 2 == 1 and i == nb // 2) else 1.0 for i in range(nb)]
    xs = [-X]
    for wt in wts:
        xs.append(xs[-1] + 2 * X * wt / sum(wts))
    n_sb = 1 if (y_r - y_b) < 2.3 else 2
    ys_side = [y_b + (y_r - y_b) * k / n_sb for k in range(n_sb + 1)]
    pw = 0.16 if W > 5.5 else 0.14                 # room posts
    pw_o = 0.24 if W > 5.5 else 0.2                # veranda (outer) posts
    z_beam = zd + P['post_h']
    z_bt = z_beam + 0.18
    z_k = zd + min(1.82, P['post_h'] - 0.38)       # kamoi bottom (shoji top)
    de_s = min(P['side_deck'], ovs - 0.2)          # deck beyond the side posts
    xdk = X + de_s                                 # deck half width
    y_df = y_f + 0.22                              # deck front edge
    y_db = y_b - 0.12
    # central stair (podium) / bay for the front steps
    bi = nb // 2
    sx_c = (xs[bi] + xs[bi + 1]) / 2 if nb % 2 == 1 else (xs[bi - 1] + xs[bi]) / 2 if nb > 2 else 0.0
    if nb == 2:
        sx_c = (xs[0] + xs[1]) / 2 if r.random() < 0.5 else (xs[1] + xs[2]) / 2
    bay_w = xs[1] - xs[0]
    notch = None
    if ph > 0:
        T = zd
        n_r = 4                                     # 3 broad stone treads, then the deck
        rise_s = T / n_r
        nt = n_r - 1
        y_front = hd - 0.02
        td = min(0.42, (y_front - (y_r + 0.6)) / nt)
        y_sb = y_front - td * nt
        cbw = xs[bi + 1] - xs[bi] if nb % 2 == 1 else bay_w
        sw = min(2.6, cbw - pw_o - 0.06)
        if y_sb < y_df:
            notch = (sx_c - sw / 2, sx_c + sw / 2, y_sb)

    # ---------------------------------------------------------------- roof
    rz = H - 0.32
    f = (ov / hd) ** P['p']
    need = z_bt + 0.06 + 0.12
    z_e = (need - f * rz) / (1 - f)
    S = kp.RoofShape(hw, hd, z_e, rz - z_e, p=P['p'], up=P['up'] if lod < 3 else P['up'] * 0.7, style=P['roof'],
                     dg=hd * P['dg'])
    RR = dict(R['roof'], tp=P['tp'], thick=0.12)
    rinfo = kp.roof(mb, S, RR, dict(tile=tile, ridge=tile, wood=wood, wood_d=wood_d), r,
                    wall=dict(ov=ov, ovs=ovs, z_beam=z_bt))

    # ---------------------------------------------------------------- foundation + deck
    if R['plinth_cuts'] >= 0:
        # carved basalt plinth wall under the room + engawa, set back from the deck edge (on the podium if any)
        px0, px1, py0, py1 = -(xdk - 0.14), xdk - 0.14, y_db + 0.1, y_f - 0.06
        hpl = zd - 0.08 - zg
        if notch:
            py1 = min(py1, notch[2] - 0.02)
        if R['plinth_cuts'] > 0:
            nseg = max(2, int((px1 - px0) / 1.6))
            for k in range(nseg):
                a, b = px0 + (px1 - px0) * k / nseg, px0 + (px1 - px0) * (k + 1) / nseg
                rounded_rock(mb, ((a + b) / 2, (py0 + py1) / 2, zg + hpl / 2), (b - a + 0.06, py1 - py0, hpl),
                             stone, rk, max(1, R['plinth_cuts'] - (1 if ph else 0)), 0.9, 0.8, round_r=0.05, batter=0.0)
        else:
            mb.box(((px0 + px1) / 2, (py0 + py1) / 2, zg + hpl / 2), (px1 - px0, py1 - py0, hpl), stone)

    def xbox(c, size, mi, cut_notch=True):
        """box along x that skips the stair notch when it overlaps it"""
        x0, x1 = c[0] - size[0] / 2, c[0] + size[0] / 2
        y0, y1 = c[1] - size[1] / 2, c[1] + size[1] / 2
        if not (cut_notch and notch and y1 > notch[2] and x0 < notch[0] and x1 > notch[1]):
            mb.box(c, size, mi)
            return
        if y0 < notch[2]:
            mb.box((c[0], (y0 + notch[2]) / 2, c[2]), (size[0], notch[2] - y0, size[2]), mi)
            y0 = notch[2]
        for a, b in ((x0, notch[0]), (notch[1], x1)):
            mb.box(((a + b) / 2, (y0 + y1) / 2, c[2]), (b - a, y1 - y0, size[2]), mi)

    if lod <= 2:
        xbox((0, (y_df + y_db) / 2, zd - 0.06 - 0.03), (2 * xdk, y_df - y_db, 0.06), wood_l)
        eb = 0.11
        xbox((0, y_df - 0.04, zd - 0.06 - eb / 2), (2 * xdk, 0.08, eb), wood_d)
        for sx in (-1, 1):
            mb.box((sx * (xdk - 0.04), (y_df + y_db) / 2, zd - 0.06 - eb / 2), (0.08, y_df - y_db, eb), wood_d)
        if R['planks']:
            pwid = r.uniform(0.15, 0.19)
            n = max(3, int((y_df - y_r) / pwid))
            for k in range(n):
                y0 = y_r + (y_df - y_r) * k / n
                xbox((0, y0 + (y_df - y_r) / n / 2, zd - 0.015), (2 * xdk - 0.01, (y_df - y_r) / n - 0.008, 0.03), wood_l)
            if de_s > 0.15:
                for sx in (-1, 1):
                    m = max(1, int(de_s / pwid))
                    for k in range(m):
                        x0 = X + 0.02 + (de_s - 0.02) * k / m
                        mb.box((sx * (x0 + (de_s - 0.02) / m / 2), (y_r + y_db) / 2, zd - 0.015),
                               ((de_s - 0.02) / m - 0.008, y_r - y_db, 0.03), wood_l)
        else:
            xbox((0, (y_df + y_r) / 2, zd - 0.015), (2 * xdk, y_df - y_r, 0.03), wood_l)
        mb.box((0, (y_r + y_b) / 2, zd + 0.02), (2 * X - pw, y_r - y_b - pw, 0.04), tatami)
    else:
        xbox((0, (y_df + y_db) / 2, zg + (zd - zg) / 2), (2 * xdk, y_df - y_db, zd - zg), wood_l)

    # ---------------------------------------------------------------- posts, footings, beams
    post_pts = [(x, y_f) for x in xs] + [(x, y_r) for x in xs] + [(x, y_b) for x in xs]
    for sx in (-1, 1):
        for y in ys_side[1:-1]:
            post_pts.append((sx * X, y))
    seen = set()
    post_pts = [p_ for p_ in post_pts if not (p_ in seen or seen.add(p_))]
    if lod <= 2:
        for x, y in post_pts:
            outer = abs(y - y_f) < 1e-6
            z0 = zg if outer else zd
            pwx = pw_o if outer else pw
            if R['post'] == 'oct':
                kg.post_oct(mb, x, y, z0, z_beam, pwx, wood, chamfer=0.16)
            else:
                mb.box((x, y, (z0 + z_beam) / 2), (pwx, pwx, z_beam - z0), wood)
            if outer and ph == 0:
                # soseki footing stone under the veranda posts
                if lod == 0:
                    fs, vs = kg.rock(mb, (x, y, 0.06), (pwx * 2.2, pwx * 2.2, 0.2), stone, r, subdiv=1, rough=0.12,
                                     facets=2, zmin=0.0, zmax=0.12)
                elif lod == 1:
                    mb.box((x, y, 0.05), (pwx * 1.9, pwx * 1.9, 0.1), stone)
        # keta eave beams (front + back) and side beams, ends protruding
        for y in (y_f, y_b):
            mb.box((0, y, (z_beam + z_bt) / 2), (2 * X + 0.75, (pw_o if y == y_f else pw) * 0.95, z_bt - z_beam), wood)
        for sx in (-1, 1):
            mb.box((sx * X, 0, (z_beam + z_bt) / 2 - 0.005), (pw * 0.9, 2 * (hd - ov) + 0.4, z_bt - z_beam - 0.01), wood)
        # room-front head beam (nageshi) + nuki through the veranda posts
        mb.box((0, y_r, z_beam - 0.07), (2 * X, pw * 0.8, 0.14), wood_d)      # lacquered nageshi
        if lod <= 1:
            mb.box((0, y_f, z_k + 0.1), (2 * X + 0.7, pw * 0.45, 0.13), wood_d)
        # ceiling over room + engawa
        mb.box((0, (y_f + y_b) / 2, z_bt + 0.02), (2 * X + 0.1, y_f - y_b + 0.1, 0.04), wood_l)
        if R['ceiling_battens']:
            for k in range(1, int(2 * X / 0.45)):
                x = -X + k * 0.45
                mb.box((x, (y_f + y_b) / 2, z_bt - 0.015), (0.04, y_f - y_b, 0.03), wood)
        # brackets: masu block + hijiki arm along the beam at the veranda and back post heads
        if R['brackets']:
            for x, y in post_pts:
                if abs(y - y_r) < 1e-6:
                    continue
                if abs(abs(y) - (hd - ov)) < 1e-6:
                    pwx = pw_o if y > 0 else pw
                    mb.box((x, y, z_beam - 0.06), (pwx * 1.3, pwx * 1.3, 0.12), wood, bevel=0.01 if lod == 0 else 0.0)
                    if lod == 0:
                        mb.box((x, y, z_beam - 0.16), (0.62, pwx * 0.7, 0.09), wood)
                        for sxx in (-1, 1):
                            mb.box((x + sxx * 0.27, y, z_beam - 0.06), (0.12, pwx * 0.9, 0.1), wood)
    else:
        # LOD3: four corner posts as thin boxes without bottoms
        for x in (-X, X):
            mb.box((x, y_f, (zd + z_beam) / 2), (pw_o, pw_o, z_beam - zd), wood)

    # ---------------------------------------------------------------- walls (shoji) + transoms
    mats = dict(wood=wood_s, paper=paper)
    z_sh0 = zd + 0.055

    def wall(M, u0, u1, lit_front=True, koshi=0.0, bay_open=None, both=True):
        """one bay of wall in frame M (local x along the wall, +y out of the room)"""
        u0, u1 = u0 + pw / 2, u1 - pw / 2
        if R['shoji'] == 'panel':
            n = 2
            ks.shoji_run(mb, M, u0, u1, z_sh0, z_k, 0.0, mats, lod, n, r, cols=P['cols'], rows=P['rows'], koshi=koshi,
                         open_k=bay_open, open_frac=P['open_frac'], depth=0.03, bars_lod=0, both_sides=both)
        elif R['shoji'] == 'long':
            n = 2
            if bay_open is not None:
                # open bay at LOD1: paper only on one half
                ks.quad(mb, M, [(u0, 0.0, z_sh0), ((u0 + u1) / 2 - 0.1, 0.0, z_sh0), ((u0 + u1) / 2 - 0.1, 0.0, z_k), (u0, 0.0, z_k)], paper)
                ks.lattice_long(mb, M, u0, (u0 + u1) / 2 - 0.1, z_sh0, z_k, 0.015, wood_s, P['cols'], P['rows'])
            else:
                ks.quad(mb, M, [(u0, 0.0, z_sh0), (u1, 0.0, z_sh0), (u1, 0.0, z_k), (u0, 0.0, z_k)], paper)
                if both:
                    ks.quad(mb, M, [(u1, -0.004, z_sh0), (u0, -0.004, z_sh0), (u0, -0.004, z_k), (u1, -0.004, z_k)], paper)
                ks.lattice_long(mb, M, u0, u1, z_sh0, z_k, 0.015, wood_s, n * P['cols'], P['rows'])
                for k in range(1, n):
                    ks.lbox(mb, M, (u0 + (u1 - u0) * k / n, 0.02, (z_sh0 + z_k) / 2), (0.05, 0.025, z_k - z_sh0), wood_s)
            if koshi > 0:
                ks.lbox(mb, M, ((u0 + u1) / 2, 0.012, z_sh0 + koshi / 2), (u1 - u0, 0.02, koshi), wood_s)
        elif R['shoji'] == 'min':
            if bay_open is None:
                ks.quad(mb, M, [(u0, 0.0, z_sh0), (u1, 0.0, z_sh0), (u1, 0.0, z_k), (u0, 0.0, z_k)], paper)
                ks.lattice_long(mb, M, u0, u1, z_sh0, z_k, 0.015, wood_s, 2, 2, bar=0.04, bar_d=0.03)
            else:
                ks.quad(mb, M, [(u0, 0.0, z_sh0), ((u0 + u1) / 2, 0.0, z_sh0), ((u0 + u1) / 2, 0.0, z_k), (u0, 0.0, z_k)], paper)
        # kamoi + ranma (lit transom) up to the head beam
        if lod <= 2:
            ks.lbox(mb, M, ((u0 + u1) / 2, 0.0, z_k + 0.035), (u1 - u0, 0.09, 0.07), wood_d)   # lacquered kamoi
            if R['ranma'] and z_beam - 0.14 - (z_k + 0.07) > 0.12:
                ks.ranma(mb, M, u0, u1, z_k + 0.07, z_beam - 0.14, 0.0, mats, lod, P['ranma_style'], r)
            elif lod == 2:
                ks.quad(mb, M, [(u0, -0.01, z_k + 0.07), (u1, -0.01, z_k + 0.07), (u1, -0.01, z_beam - 0.14),
                                (u0, -0.01, z_beam - 0.14)], paper)

    if lod <= 2:
        Mf = kg.frame(Vector((0, y_r, 0)), Vector((0, 1, 0)))
        Mb = kg.frame(Vector((0, y_b, 0)), Vector((0, -1, 0)))
        for i in range(nb):
            if P['front'] == 'shoji':
                ob = 0 if i == P['open_bay'] else None
                wall(Mf, xs[i], xs[i + 1], bay_open=ob, both=True)
            # back wall: koshi shoji, both faces lit (seen through the open front)
            facing = (i == P['open_bay']) if P['front'] == 'shoji' else (i == nb // 2)
            wall(Mb, -xs[i + 1], -xs[i], koshi=0.32, both=True)
            if facing and lod == 0:
                # kakejiku scroll hanging inside, in front of the lit back shoji (reads as a silhouette)
                uc = -(xs[i] + xs[i + 1]) / 2
                sw_, sh_ = 0.48, min(1.1, z_k - zd - 0.55)
                zc = zd + 0.45 + sh_ / 2
                ks.quad(mb, Mb, [(uc - sw_ / 2, -0.09, zc - sh_ / 2), (uc + sw_ / 2, -0.09, zc - sh_ / 2),
                                 (uc + sw_ / 2, -0.09, zc + sh_ / 2), (uc - sw_ / 2, -0.09, zc + sh_ / 2)], scroll)
                for zz in (zc - sh_ / 2, zc + sh_ / 2):
                    ks.lbox(mb, Mb, (uc, -0.1, zz), (sw_ + 0.08, 0.025, 0.025), wood_d)
                ks.lbox(mb, Mb, (uc, -0.1, (zc + sh_ / 2 + z_k) / 2), (0.006, 0.006, z_k - zc - sh_ / 2), wood_d)
        for sx in (-1, 1):
            Ms = kg.frame(Vector((sx * X, 0, 0)), Vector((sx, 0, 0)))
            for k in range(n_sb):
                a, b = ys_side[k], ys_side[k + 1]
                u0, u1 = (-b, -a) if sx > 0 else (a, b)
                wall(Ms, u0, u1, koshi=0.32, both=True)
        lights.append(dict(type='area', pos=[0.0, round(y_r + 0.05, 3), round((zd + z_beam) / 2, 3)], normal=[0, 1, 0],
                           size=[round(2 * X, 3), round(z_beam - zd, 3)], color=[1.0, 0.63, 0.34], watts=70,
                           source='lantern_andon (front shoji)'))
        for sx in (-1, 1):
            lights.append(dict(type='area', pos=[round(sx * (X + 0.05), 3), round((y_r + y_b) / 2, 3), round((zd + z_beam) / 2, 3)],
                               normal=[sx, 0, 0], size=[round(y_r - y_b, 3), round(z_beam - zd, 3)],
                               color=[1.0, 0.63, 0.34], watts=25, source='lantern_andon (side shoji)'))
        lights.append(dict(type='area', pos=[0.0, round(y_b - 0.05, 3), round((zd + z_beam) / 2, 3)], normal=[0, -1, 0],
                           size=[round(2 * X, 3), round(z_beam - zd, 3)], color=[1.0, 0.63, 0.34], watts=30,
                           source='lantern_andon (back shoji)'))
    else:
        Mf = kg.frame(Vector((0, y_r, 0)), Vector((0, 1, 0)))
        ks.quad(mb, Mf, [(-X, 0.0, zd), (X, 0.0, zd), (X, 0.0, z_beam), (-X, 0.0, z_beam)], paper)
        lights.append(dict(type='area', pos=[0.0, round(y_r + 0.05, 3), round((zd + z_beam) / 2, 3)], normal=[0, 1, 0],
                           size=[round(2 * X, 3), round(z_beam - zd, 3)], color=[1.0, 0.63, 0.34], watts=150,
                           source='lantern_andon (front)'))

    # ---------------------------------------------------------------- interior props (through the open front / bay)
    if R['props'] >= 1 and lod <= 1:
        ty = (y_r + y_b) / 2 + 0.1
        tz = zd + 0.04
        tw, tdp, th_ = min(1.4, X * 0.6), 0.75, 0.33
        mb.box((0, ty, tz + th_ - 0.02), (tw, tdp, 0.04), wood_d)
        if lod == 0:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box((sx * (tw / 2 - 0.06), ty + sy * (tdp / 2 - 0.06), tz + (th_ - 0.04) / 2), (0.05, 0.05, th_ - 0.04), wood_d)
            for sx in (-1, 1):
                mb.box((sx * (tw / 2 + 0.4), ty, tz + 0.04), (0.55, 0.55, 0.08), cloth, bevel=0.025)
        else:
            mb.box((0, ty, tz + (th_ - 0.04) / 2), (tw * 0.8, tdp * 0.8, th_ - 0.04), wood_d)

    # ---------------------------------------------------------------- steps / podium stair + lanterns
    lan = []                                       # (x, y, base z, pedestal height)
    if ph > 0:
        y_pf = y_df + 0.12                         # podium front
        # cut-stone stair between boulder cheeks, cut into the engawa edge
        for k in range(nt):
            top = rise_s * (k + 1)
            yk = y_front - td * k
            if R['steps_cuts'] >= 0:
                mb.box((sx_c, (yk + y_sb) / 2 - 0.01, top / 2), (sw, yk - y_sb + 0.02, top), cut,
                       bevel=0.012 if lod == 0 else 0.0)
            elif k == nt // 2:
                mb.box((sx_c, (yk + y_sb) / 2, top / 2), (sw, yk - y_sb, top), cut)     # LOD3: one block
        kb = 0.18                                  # dressed kerb course at the podium top (deck level)

        def frock(c, size, sub, zmax, mi=None):
            """angular fractured basalt chunk: planar cuts, sharp edges (sheet 01 / 05 rock)"""
            fs, vs = kg.rock(mb, c, size, mi if mi is not None else rocks, r, subdiv=sub, rough=0.12,
                             facets=6 if sub else 3, zmin=0.0, zmax=zmax)
            kg.clamp_verts(vs, ylim=(-hd, hd))
            return fs

        ch = ph - kb * 0.5
        for s_ in (-1, 1):
            cx_ = sx_c + s_ * (sw / 2 + 0.34)
            if lod <= 1:
                frock((cx_, (y_sb + y_front) / 2 + 0.05, ch * 0.5), (0.72, y_front - y_sb + 0.3, ch * 1.1), 1 if lod == 0 else 0, ch)
                mb.box((cx_, (y_sb + y_front) / 2, ch + 0.04), (0.5, 0.5, 0.08), cut, bevel=0.01 if lod == 0 else 0.0)
            elif lod == 2:
                mb.box((cx_, (y_sb + y_front) / 2, ch / 2), (0.62, y_front - y_sb, ch), stone)
            lan.append((cx_, min(y_front - 0.3, (y_sb + y_front) / 2 + 0.05), ch + 0.08, 0.06))
        rail_sides = [-1, 1]
        # podium: core block, 2-3 courses of mixed fractured basalt (0.3-1.2 m), dressed kerb on top
        x_lo, x_hi = -(xdk + 0.06), xdk + 0.06
        if L > 0:
            if ls > 0:
                x_hi = hw + L - 0.15
            else:
                x_lo = -(hw + L - 0.15)
        y_lo = y_db - 0.08
        hr = ph - kb                                # rock face height under the kerb
        if R['plinth_cuts'] > 0:
            rounded_rock(mb, ((x_lo + x_hi) / 2, (y_lo + y_pf) / 2 - 0.1, hr / 2), (x_hi - x_lo - 0.1, y_pf - y_lo - 0.2, hr),
                         stone, rk, max(1, R['plinth_cuts'] - 1), 1.0, 1.0, round_r=0.05, batter=0.0)
        else:
            mb.box(((x_lo + x_hi) / 2, (y_lo + y_pf) / 2, ph / 2), (x_hi - x_lo, y_pf - y_lo, ph), stone)
        skip = (sx_c - sw / 2 - 0.05, sx_c + sw / 2 + 0.05)
        if lod <= 1:
            def course(p0, p1, inward, lo, hi, zc, hfrac, sub, gap_skip):
                Ls_ = (p1 - p0).length
                t = 0.0
                while t < Ls_:
                    sz = r.uniform(lo, hi)
                    q = p0.lerp(p1, min(1.0, (t + sz / 2) / Ls_))
                    t += sz * r.uniform(0.75, 0.95)
                    if gap_skip and skip[0] - 0.3 < q.x < skip[1] + 0.3:
                        continue
                    hz = min(hr, sz * hfrac * r.uniform(0.8, 1.15))
                    c = q + inward * (sz * 0.25 - r.uniform(0.0, 0.08))
                    frock((c.x, c.y, zc(hz)), (sz * r.uniform(1.0, 1.25), sz * r.uniform(0.65, 0.9), hz), sub, hr + 0.02)
            front0, front1 = Vector((x_lo, y_pf, 0)), Vector((x_hi, y_pf, 0))
            # course 1: big blocks on the ground; course 2: smaller ones over them; a few fill stones
            course(front0, front1, Vector((0, -1, 0)), 0.75, 1.2, lambda hz: hz * 0.42, 0.62, lod, True)
            course(front0 + Vector((0.2, 0, 0)), front1, Vector((0, -1, 0)), 0.3, 0.6, lambda hz: hr - hz * 0.45, 0.85,
                   lod, True)
            for xe, inw in ((x_lo, Vector((1, 0, 0))), (x_hi, Vector((-1, 0, 0)))):
                a_, b_ = Vector((xe, y_pf - 0.3, 0)), Vector((xe, y_lo + 0.2, 0))
                course(a_, b_, inw, 0.7, 1.1, lambda hz: hz * 0.42, 0.62, lod, False)
                if lod == 0:
                    course(a_, b_, inw, 0.3, 0.55, lambda hz: hr - hz * 0.45, 0.85, 0, False)
            course(Vector((x_lo, y_lo, 0)), Vector((x_hi, y_lo, 0)), Vector((0, 1, 0)), 0.8, 1.2, lambda hz: hz * 0.5,
                   0.9, 0, False)
        # dressed kerb course across the front and sides (deck level)
        if lod <= 2:
            def kerb(p0, p1, axis_x):
                Ls_ = (p1 - p0).length
                n = max(1, int(Ls_ / r.uniform(0.9, 1.3)))
                for k in range(n):
                    a_ = p0.lerp(p1, k / n); b_ = p0.lerp(p1, (k + 1) / n)
                    c = (a_ + b_) / 2
                    if axis_x and skip[0] < c.x < skip[1]:
                        continue
                    ln = (b_ - a_).length - 0.015
                    size = (ln, 0.42, kb) if axis_x else (0.42, ln, kb)
                    off = Vector((0, -0.17, 0)) if axis_x else Vector((-0.17 * (1 if c.x > 0 else -1), 0, 0))
                    mb.box((c.x + off.x, c.y + off.y + (0.04 if axis_x else 0), ph - kb / 2), size, cut,
                           bevel=0.012 if lod == 0 else 0.0)
            kerb(Vector((x_lo, y_pf, 0)), Vector((x_hi, y_pf, 0)), True)
            for xe in (x_lo, x_hi):
                kerb(Vector((xe + (0.04 if xe > 0 else -0.04), y_pf - 0.42, 0)), Vector((xe, y_lo, 0)), False)
    else:
        nst = max(1, int(round(zd / 0.155)) - 1)
        rise = zd / (nst + 1)
        if P['steps'] == 'front':
            if P['front'] == 'open':
                sx_c = 0.0 if nb % 2 == 1 else sx_c
            avail = hd - 0.02 - y_df
            td = min(0.34, avail / nst)
            sw = min(P['step_w'], bay_w * 1.1)
            for k in range(nst):
                top = rise * (nst - k)
                yc = y_df + td * (k + 0.5)
                _step_stone(mb, (sx_c, yc - (0.02 if k == 0 else 0), top / 2), (sw * (1 + 0.08 * k), td + 0.06, top), stone,
                            rk, R['steps_cuts'], r, top)
            lan = [(sx_c + s_ * (sw / 2 + 0.42), min(y_df + 0.34, hd - 0.22), 0.0, 0.34) for s_ in (-1, 1)]
            rail_sides = [-1, 1]
        else:
            sgn = -1 if P['steps'] == 'left' else 1
            avail = hw - 0.02 - xdk
            td = min(0.34, avail / nst)
            sw = min(P['step_w'], P['eng'] + 0.2)
            yc0 = (y_df + y_r) / 2 + 0.1
            for k in range(nst):
                top = rise * (nst - k)
                xc = sgn * (xdk + td * (k + 0.5))
                _step_stone(mb, (xc, yc0, top / 2), (td + 0.06, sw * (1 + 0.08 * k), top), stone, rk, R['steps_cuts'], r, top)
            lan = [(sgn * min(xdk + 0.3, hw - 0.2), min(yc0 + s_ * (sw / 2 + 0.38), hd - 0.2), 0.0, 0.34) for s_ in (-1, 1)]
            rail_sides = [-sgn]
    for x, y, zb_, ped in lan:
        if lod <= 2:
            if lod <= 1:
                if zb_ == 0.0:
                    _step_stone(mb, (x, y, ped / 2), (0.36, 0.36, ped), stone, rk, max(0, R['steps_cuts']), r, ped)
                else:
                    mb.box((x, y, zb_ + ped / 2), (0.34, 0.34, ped), cut, bevel=0.01 if lod == 0 else 0.0)
                if lod == 0:
                    kg.post_oct(mb, x, y, zb_ + ped, zb_ + ped + 0.12, 0.12, iron)
            else:
                mb.box((x, y, zb_ + ped / 2), (0.34, 0.34, ped), stone)
            base = zb_ + ped + (0.12 if lod == 0 else 0.0)
            c = kg.lantern_box(mb, (x, y, base), dict(iron=iron, paper=lpaper), lod, r, size=0.3, height=0.42,
                               roof='pyramid', corner_bars=lod == 0)
        else:
            mb.box((x, y, zb_ + (ped + 0.42) / 2 + 0.05), (0.28, 0.28, ped + 0.42), lpaper)
            c = Vector((x, y, zb_ + ped + 0.25))
        lights.append(dict(type='point', pos=[round(c.x, 3), round(c.y, 3), round(c.z, 3)], color=[1.0, 0.6, 0.3],
                           radius=3.5, source='lantern_andon'))

    # ---------------------------------------------------------------- lean-to (hisashi) on one side
    if L > 0:
        x_in, x_out = ls * (hw - 0.4), ls * (hw + L)
        z_top = z_e - 0.13
        z_le = z_top - abs(x_out - x_in) * math.tan(math.radians(21))
        y0, y1 = y_b - 0.25, min(hd - 0.15, y_f + 0.35)
        RL = dict(R['roof'])
        kp.lean_to(mb, ls, x_in, x_out, y0, y1, z_top, z_le, P['tp'], RL, dict(tile=tile, wood=wood), r)
        if lod <= 2:
            xp = ls * (hw + L - 0.32)
            zt_p = z_le - 0.16
            for y in (y0 + 0.35, y1 - 0.35):
                mb.box((xp, y, (zg + zt_p) / 2), (0.17, 0.17, zt_p - zg), wood)
                mb.box(((xp + ls * X) / 2, y, zt_p - 0.08), (abs(xp - ls * X) + 0.1, 0.12, 0.14), wood)   # tie beam
            mb.box((xp, (y0 + y1) / 2, zt_p + 0.06), (0.15, y1 - y0 - 0.2, 0.14), wood)                    # eave beam
            # deck extension under the lean-to
            xa, xb = ls * xdk, ls * (hw + L - 0.18)
            mb.box(((xa + xb) / 2, (y0 + y1) / 2, zd - 0.06), (abs(xb - xa), y1 - y0 - 0.3, 0.12), wood_l)
            mb.box((xb - ls * 0.04, (y0 + y1) / 2, zd - 0.12), (0.08, y1 - y0 - 0.3, 0.12), wood)
            if ph == 0:
                for y in (y0 + 0.35, y1 - 0.35):
                    mb.box((xp, y, 0.05), (0.32, 0.32, 0.1), stone)
        else:
            # LOD3: the lean-to roof sits on two flat post cards so it does not float
            xp = ls * (hw + L - 0.32)
            Mp = kg.frame(Vector((0, 0, 0)), Vector((0, 1, 0)))
            for y in (y0 + 0.35, y1 - 0.35):
                ks.quad(mb, Mp, [(xp - 0.08, y, zg), (xp + 0.08, y, zg), (xp + 0.08, y, z_le - 0.1), (xp - 0.08, y, z_le - 0.1)], wood)

    if P['corner_lanterns'] and lod <= 2:
        # ~0.75 m floor andon on the deck at both front corners
        for sx in (-1, 1):
            x, y = sx * (xdk - 0.3), y_df - 0.28
            if lod <= 1:
                for lx in (-1, 1):
                    for ly in (-1, 1):
                        mb.box((x + lx * 0.13, y + ly * 0.13, zd + 0.06), (0.04, 0.04, 0.12), wood_d)
            c = kg.lantern_box(mb, (x, y, zd + 0.12), dict(iron=wood_d, paper=lpaper), lod, r, size=0.34, height=0.52,
                               roof='pyramid', corner_bars=lod == 0)
            lights.append(dict(type='point', pos=[round(c.x, 3), round(c.y, 3), round(c.z, 3)], color=[1.0, 0.6, 0.3],
                               radius=2.5, source='lantern_andon'))

    # ---------------------------------------------------------------- railings (koran) on the step-less sides
    if P['rails'] and R['rail'] != 'none' and lod <= 1:
        for sx in rail_sides:
            if de_s < 0.15:
                continue
            xr_ = sx * (xdk - 0.06)
            ya, yb_ = y_df - 0.08, y_r + 0.05
            rh = 0.62
            for y in (ya, yb_):
                mb.box((xr_, y, zd + rh / 2), (0.08, 0.08, rh), wood)
            mb.box((xr_, (ya + yb_) / 2, zd + rh + 0.02), (0.07, ya - yb_ + 0.16, 0.05), wood)       # kasagi top rail
            if R['rail'] == 'full':
                mb.box((xr_, (ya + yb_) / 2, zd + rh * 0.5), (0.04, ya - yb_, 0.04), wood)
                mb.box((xr_, (ya + yb_) / 2, zd + 0.07), (0.05, ya - yb_, 0.05), wood)
                nbal = max(2, int((ya - yb_) / 0.32))
                for k in range(1, nbal):
                    y = yb_ + (ya - yb_) * k / nbal
                    mb.box((xr_, y, zd + rh * 0.5 + 0.12), (0.03, 0.03, rh * 0.5 - 0.2), wood)

    # shift the main building off-centre so main + lean-to fill the width, then clamp to the proxy box
    if L > 0:
        for v in mb.bm.verts:
            v.co.x += cxm
        for Lg in lights:
            Lg['pos'][0] = round(Lg['pos'][0] + cxm, 3)
    for v in mb.bm.verts:
        v.co.x = min(max(v.co.x, -W_full / 2), W_full / 2)
        v.co.y = min(max(v.co.y, -D / 2), D / 2)
        v.co.z = min(max(v.co.z, 0.0), H)
    o = mb.to_object(ASSET)
    o['kz_lights'] = json.dumps(lights)
    o['kz_flicker'] = json.dumps(sorted({paper, lpaper}))
    o['kz_params'] = json.dumps(P)
    o['kz_roof'] = json.dumps(dict(style=P['roof'], eave_z=round(z_e, 3), ridge_z=round(rz, 3), tile_pitch=round(P['tp'], 3)))
    o['kz_deck'] = json.dumps(dict(z=round(zd, 3), x=[round(cxm - xdk, 3), round(cxm + xdk, 3)],
                                   y=[round(y_db, 3), round(y_df, 3)], steps=P['steps'], podium=round(ph, 3),
                                   leanto=dict(side=ls, width=round(L, 3)) if L else None))
    genlib.finish(o)
    kg.uv_grain(o, [wood, wood_s, wood_l, wood_d])
    if lpaper != paper:
        kg.uv_unit(o, [lpaper])
    return o
