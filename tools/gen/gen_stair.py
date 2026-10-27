"""Stair generator: straight / switchback flights in seven styles.

Identifying features kept at every LOD: 17 cm risers and 29 cm treads (every riser is real geometry down to
LOD3), landings, rough-cut stone or hinoki treads, stringer / cheek wall and rail on the open sides, the
lantern newels (LOD0-2 lantern heads, LOD3 lit crossed quads).

Orientation: the flight CLIMBS TOWARDS -Y. The first riser faces +Y (the front); the top of the stair is at
-Y. Pivot at the base centre of the bounding box, metres. (Matches b2_boat ladder_stair: top at -Y.)

Parameters (all optional):
    steps / risers   number of risers (default 12, or round(rise / 0.17))
    rise             total rise; negative values (pool entries going down) are built with abs(rise)
    run              total horizontal run of the flights; sets the tread if no tread is given
    riser            0.15-0.18 m (default 0.17, or rise / steps; ladder 0.20)
    tread            default 0.29 (ladder 0.12: a ~60 degree ladder-stair)
    w / width        0.8-4 m overall width incl. cheeks / stringers / host wall (default proxy 2.4;
                     ladder 0.9, cantilever 1.4, cliff 1.6)
    style            stone_rough | stone_polished | hinoki | pool_entry | ladder | cantilever | cliff
                     cliff = stone_rough cut into rock: a rough basalt wall rising 1.5 m above the treads on the
                     closed side, cheek + hinoki rail on the open side.
                     cantilever = slabs keyed 0.15 m into a 0.3 m basalt host wall (always emitted).
    landing_every    a landing after every n risers (landing='mid' -> half the flight). Default: none for
                     <= 16 risers, otherwise at the middle.
    landing_depth    default max(1.0, min(w, 1.5)) (switchback: the lane width)
    open_side        L | R | both | none  - sides that get cheek/stringer + rail, seen walking UP the first
                     flight (cantilever and cliff default R: the wall is on the left)
    plan             straight | switchback (switchback: flights alternate -Y / +Y in two lanes; landings
                     span both lanes; the inner edges always get a rail; stone upper flights are hollow,
                     carried on a soffit beam, the landing on two rock piers)
    lanterns         none | bottom | top | both - slim iron-framed lanterns (0.24 x 0.24 x 0.42 m) on 0.4 m stone
                     newel piers on the open sides, plus one on the coping every ~8 risers on long flights
                     (stone styles and cliff default both; pool_entry top; hinoki both on timber newels;
                     ladder: one at the head)
Seeded variation (shape, not only scale): cheek treatment (raking coping over a bulging rock face / stepped
rubble blocks / bare rock with a ragged top), rail scheme (balusters at 0.18 m vs two rails), post spacing
0.9-1.2 m, finial (giboshi onion / hoshu ball), lantern roof (hip / round), slab splits (1-3 per tread) and
tilt, coping height 0.25-0.35 m, hinoki closed vs open risers, tint and wetness.
Custom properties: kz_lights (lantern centres for the bake, JSON), kz_stair (JSON: rise, run, steps, riser,
tread, top and bottom nosing positions in local metres) for walk-mesh / snapping.
Budget: per flight of 12 risers 1500/600/180/40; scaled by risers/12 for longer runs.
Animation: none. Lighting: lightmap (+ emissive washi_backlit panels in the lanterns).
"""
import json
import math
from mathutils import Vector, Matrix
import genlib
import kzgeo_bridge_arched as kg

ASSET = 'stair'
FEATURES = ['17 cm risers / 29 cm treads', 'landings', 'stone or hinoki treads',
            'stringer or cheek + rail posts on open sides', 'lantern newels']
STYLES = ['stone_rough', 'stone_polished', 'hinoki', 'pool_entry', 'ladder', 'cantilever', 'cliff']
BASE_BUDGET = [1500, 600, 180, 40]


def budget(steps):
    k = max(1.0, steps / 12.0)
    return [int(b * k) for b in BASE_BUDGET]


def _resolve(seed, rise, run, riser, tread, w, width, steps, risers, style, landing_every, landing,
             landing_depth, open_side, plan, lanterns):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    style = style or 'stone_rough'
    if style not in STYLES:
        raise ValueError(f'style {style!r} not in {STYLES}')
    n = steps or risers
    rise_abs = abs(rise) if rise else None
    if not n:
        n = max(1, int(round(rise_abs / 0.17))) if rise_abs else 12
    n = int(n)
    if riser is None:
        riser = rise_abs / n if rise_abs else {'ladder': 0.2, 'pool_entry': 0.15}.get(style, 0.17)
    if tread is None:
        tread = (run / n) if run else {'ladder': 0.12, 'pool_entry': 0.38}.get(style, 0.29)
    W = w or width or {'ladder': 0.9, 'cantilever': 1.4, 'cliff': 1.6, 'pool_entry': 3.2}.get(style, p['w'])
    if landing_every is None and landing == 'mid':
        landing_every = int(math.ceil(n / 2))
    if landing_every is None:
        landing_every = int(math.ceil(n / 2)) if n > 16 else 0
    plan = plan or 'straight'
    if plan == 'switchback' and not landing_every:
        landing_every = int(math.ceil(n / 2))
    if open_side is None:
        open_side = 'R' if style in ('cantilever', 'cliff') else 'both'
    if lanterns is None:
        lanterns = {'stone_rough': 'both', 'stone_polished': 'both', 'cliff': 'both', 'hinoki': 'both',
                    'pool_entry': 'both', 'ladder': 'top'}.get(style, 'none')
    ld = landing_depth or (W if plan == 'switchback' else max(1.0, min(W, 1.5)))
    return r, dict(steps=n, riser=float(riser), tread=float(tread), w=float(W), style=style,
                   landing_every=int(landing_every or 0), landing_depth=float(ld), open_side=open_side,
                   plan=plan, lanterns=lanterns, descends=bool(rise and rise < 0))


def _layout(P):
    """Flights and landings in a provisional frame (re-centred later). Flight: lane x-extent, front y,
    climbing direction (-1 = towards -Y), base z, risers, sides {'L':bool,'R':bool} (walking frame)."""
    n, R, T, W = P['steps'], P['riser'], P['tread'], P['w']
    every = P['landing_every'] or n
    counts = []
    left = n
    while left > 0:
        counts.append(min(every, left)); left -= counts[-1]
    open_L = P['open_side'] in ('L', 'both')
    open_R = P['open_side'] in ('R', 'both')
    flights, landings = [], []
    z = 0.0
    if P['plan'] == 'switchback':
        g = 0.12 if P['style'] in ('stone_rough', 'stone_polished', 'pool_entry', 'cliff') else 0.25
        lanes = [(-W - g / 2, -g / 2), (g / 2, W + g / 2)]
        frun = max(counts) * T
        for i, c in enumerate(counts):
            d = -1 if i % 2 == 0 else 1
            lane = lanes[i % 2]
            yf = frun / 2 if d < 0 else -frun / 2
            outer_is_minx = (i % 2 == 0)
            right_is_minx = d < 0
            sides = {}
            for side in ('L', 'R'):
                is_minx = (side == 'R') == right_is_minx
                outer = is_minx == outer_is_minx
                sides[side] = (open_L if side == 'L' else open_R) if outer else True
            flights.append(dict(x0=lane[0], x1=lane[1], yf=yf, dir=d, z0=z, n=c, sides=sides))
            z += c * R
            if i < len(counts) - 1:
                ly0 = yf + d * c * T
                ly1 = ly0 + d * P['landing_depth']
                landings.append(dict(x0=lanes[0][0], x1=lanes[1][1], y0=min(ly0, ly1), y1=max(ly0, ly1), z=z,
                                     edge_y=ly1, sides={'L': open_L, 'R': open_R}))
    else:
        y = 0.0
        for i, c in enumerate(counts):
            flights.append(dict(x0=-W / 2, x1=W / 2, yf=y, dir=-1, z0=z, n=c, sides={'L': open_L, 'R': open_R}))
            y -= c * T
            z += c * R
            if i < len(counts) - 1:
                landings.append(dict(x0=-W / 2, x1=W / 2, y0=y - P['landing_depth'], y1=y, z=z, edge_y=None,
                                     sides={'L': open_L, 'R': open_R}))
                y -= P['landing_depth']
    return flights, landings


def build(lod, seed, rise=None, run=None, riser=None, tread=None, w=None, width=None, steps=None, risers=None,
          style=None, landing_every=None, landing=None, landing_depth=None, open_side=None, plan=None,
          lanterns=None, cheek=None, rail_scheme=None, **_unused):
    r, P = _resolve(seed, rise, run, riser, tread, w, width, steps, risers, style, landing_every, landing,
                    landing_depth, open_side, plan, lanterns)
    S, R, T = P['style'], P['riser'], P['tread']
    flights, landings = _layout(P)
    mb = genlib.MeshBuilder()
    rough = S in ('stone_rough', 'cliff')
    stone_kind = S in ('stone_rough', 'stone_polished', 'pool_entry', 'cliff')
    timber = S in ('hinoki', 'ladder')
    hollow = P['plan'] == 'switchback'

    # ---------------- seeded shape choices
    if cheek is None:
        cheek = ['stepped', 'stepped', 'raking'][(seed - 1) % 3] if S == 'stone_rough' else 'raking'
    if rail_scheme is None:
        rail_scheme = 'two_rail' if (seed % 3 == 2 and S != 'cantilever') else 'balusters'
    P.update(cheek=cheek, rail_scheme=rail_scheme)
    spacing = r.uniform(1.08, 1.2)
    finial = r.choice(['giboshi', 'giboshi', 'hoshu'])
    roof = r.choice(['hip', 'round'])
    split_base = r.choice([1, 2, 3])
    hc = {'stone_polished': 0.3, 'pool_entry': 0.14, 'cliff': 0.1}.get(S, r.uniform(0.25, 0.35))   # cheek top over the nosing line
    nos = r.uniform(0.02, 0.035) if S != 'ladder' else 0.02
    closed_risers = S == 'hinoki' and r.random() < 0.6

    # ---------------- materials (hinoki tint relative to the library's warm default -> deep oiled brown)
    wood = mb.slot('hinoki', variant=r.choice(['wet_oiled', 'stained']), wear=round(r.uniform(0.25, 0.45), 2))
    wood_d = mb.slot('hinoki', variant='stained', wear=round(r.uniform(0.35, 0.55), 2))
    iron = mb.slot('iron', wear=round(r.uniform(0.15, 0.35), 2))
    paper = mb.slot('washi_backlit', emissive_level=round(r.uniform(0.9, 1.1), 2))
    if rough:
        tread_m = mb.slot('stepping_stone', wetness=round(r.uniform(0.45, 0.7), 2), wear=round(r.uniform(0.2, 0.4), 2), tint=[1.25, 1.2, 1.15])
        cheek_m = mb.slot('basalt_wet', wetness=round(r.uniform(0.35, 0.6), 2), tint=[1.2, 1.15, 1.1])
    elif S == 'stone_polished':
        tread_m = mb.slot('paving', wetness=round(r.uniform(0.3, 0.6), 2), wear=round(r.uniform(0.1, 0.25), 2), tint=[1.3, 1.25, 1.2])
        cheek_m = mb.slot('paving', wetness=round(r.uniform(0.2, 0.4), 2), wear=0.3, tint=[0.8, 0.8, 0.8])
    elif S == 'pool_entry':
        tread_m = mb.slot('basalt_wet', wetness=0.95)
        cheek_m = mb.slot('basalt_wet', wetness=0.8, tint=[0.85, 0.85, 0.85])
    elif S == 'cantilever':
        tread_m = mb.slot('stepping_stone', wetness=round(r.uniform(0.3, 0.7), 2))
        cheek_m = mb.slot('basalt_wet', wetness=round(r.uniform(0.3, 0.6), 2), tint=[1.1, 1.08, 1.05])
    else:
        tread_m = wood
        cheek_m = wood_d
    rail_m = iron if S in ('pool_entry', 'cantilever') else wood
    M = dict(iron=iron, paper=paper)
    lights = []

    ct = {'stone_rough': r.uniform(0.3, 0.36), 'cliff': 0.3, 'stone_polished': 0.3, 'pool_entry': 0.26,
          'hinoki': 0.075, 'ladder': 0.07}.get(S, 0.0)          # cheek / stringer thickness
    wall_t = {'cliff': 0.35, 'cantilever': 0.3}.get(S, 0.0)    # host wall on the closed side
    rail_h = 0.90                                                # handrail top over the nosing line
    zn = lambda s_: R + s_ * R / T                               # nosing line (flight-local)

    def side_local_x(F, side):
        half = (F['x1'] - F['x0']) / 2
        return half if side == 'R' else -half                  # walking frame: right = local +X

    def flight_frame(F):
        xc = (F['x0'] + F['x1']) / 2
        return kg.frame(Vector((xc, F['yf'], F['z0'])), Vector((0, F['dir'], 0)))

    def wall_side(F):
        if not wall_t:
            return None
        if not F['sides']['L']:
            return 'L'
        if not F['sides']['R']:
            return 'R'
        return 'L'                                               # cantilever with both sides open: wall left

    def add_lantern(Mf, xc_, s_, zbase, zpier, lod_, pier=True, pier_w=0.4):
        """coping lantern: stone post (zbase..zpier, flight-local) + slim head on top"""
        P0 = Mf @ Vector((xc_, s_, 0))
        if pier and lod_ <= 2:
            kg.cbox(mb, Mf @ Matrix.Translation((xc_, s_, (zbase + zpier) / 2)), (pier_w, pier_w, zpier - zbase),
                    cheek_m if stone_kind or S == 'cantilever' else wood_d,
                    jitter=0.01 if (lod_ == 0 and rough) else 0.0, r=r, drop_bottom=True)
        c_ = kg.lantern_slim(mb, (P0.x, P0.y, P0.z + zpier), M, lod_, size=0.24, height=0.42, roof=roof, frame=0.03)
        lights.append([round(c_.x, 3), round(c_.y, 3), round(c_.z, 3)])

    def add_newel(Mf, xc_, s_, zbase, ztread, lod_):
        """tall newel lantern, ~1.45 m over its tread: stone (or timber) plinth to +0.35, timber post to +0.85,
        iron cap band, 0.28 x 0.28 x 0.50 iron-framed lantern with hip/round roof and ball finial"""
        P0 = Mf @ Vector((xc_, s_, 0))
        zp, zq = ztread + 0.35, ztread + 0.85
        stone_p = stone_kind or S == 'cantilever'
        if lod_ == 2:
            kg.cbox(mb, Mf @ Matrix.Translation((xc_, s_, (zbase + zq) / 2)), (0.2, 0.2, zq - zbase),
                    cheek_m if stone_p else wood_d, drop_bottom=True)
        elif lod_ <= 1:
            kg.cbox(mb, Mf @ Matrix.Translation((xc_, s_, (zbase + zp) / 2)), (0.36, 0.36, zp - zbase),
                    cheek_m if stone_p else wood_d, jitter=0.012 if (lod_ == 0 and rough) else 0.0, r=r, drop_bottom=True)
            kg.cbox(mb, Mf @ Matrix.Translation((xc_, s_, (zp + zq) / 2)), (0.12, 0.12, zq - zp), wood_d, drop_bottom=True)
            if lod_ == 0:
                kg.band(mb, (P0.x, P0.y, P0.z + zq - 0.02), 0.15, 0.15, 0.04, iron)
        c_ = kg.lantern_slim(mb, (P0.x, P0.y, P0.z + zq), M, lod_, size=0.28, height=0.5, roof=roof, frame=0.03)
        lights.append([round(c_.x, 3), round(c_.y, 3), round(c_.z, 3)])

    # =================================================================== LOD2 / LOD3
    if lod >= 2:
        for fi, F in enumerate(flights):
            Mf = flight_frame(F)
            n = F['n']
            half = (F['x1'] - F['x0']) / 2
            ws = wall_side(F)
            if lod == 3:
                # solid wedge with a 4-step sawtooth top (closed, no gaps); lantern cards seated on the wedge top
                nm = 4
                hs = [n * R * (k + 1) / nm for k in range(nm)]
                ssx = [n * T * k / nm for k in range(nm + 1)]
                wpoly = [(0.0, 0.0)]
                for k in range(nm):
                    wpoly += [(ssx[k], hs[k]), (ssx[k + 1], hs[k])]
                wpoly += [(n * T, 0.0)]
                kg.prism_x(mb, wpoly, -half, half, cheek_m if (stone_kind or S == 'cantilever') else wood_d, M=Mf)
                if P['lanterns'] != 'none' and (stone_kind or S == 'hinoki'):
                    bm = mb.bm
                    for side in ('L', 'R'):
                        if not F['sides'][side] or side == ws:
                            continue
                        lx = side_local_x(F, side); sg = 1 if lx > 0 else -1
                        spots = []
                        if fi == 0 and P['lanterns'] in ('bottom', 'both'):
                            spots.append((0.12, hs[0]))
                        if fi == len(flights) - 1 and P['lanterns'] in ('top', 'both'):
                            spots.append((n * T - 0.12, hs[-1]))
                        for s_, z_ in spots:
                            xc_ = lx - sg * 0.2
                            q = [bm.verts.new(Mf @ Vector(c)) for c in ((xc_ - 0.15, s_, z_), (xc_ + 0.15, s_, z_),
                                                                       (xc_ + 0.15, s_, z_ + 0.9), (xc_ - 0.15, s_, z_ + 0.9))]
                            mb._tag([bm.faces.new(q)], paper)
                            c_ = Mf @ Vector((xc_, s_, z_ + 0.6)); lights.append([round(c_.x, 3), round(c_.y, 3), round(c_.z, 3)])
                continue
            poly = [(0.0, 0.0)]
            for i in range(n):
                poly += [(i * T, (i + 1) * R), ((i + 1) * T, (i + 1) * R)]
            if stone_kind and not (hollow and F['z0'] > 0.01):
                poly += [(n * T, 0.0)]
            else:
                poly += [(n * T, n * R - 0.32), (0.25, 0.0)]
            covered = {s: F['sides'][s] and (stone_kind or timber) or s == ws for s in ('L', 'R')}
            kg.prism_x(mb, poly, -half, half, tread_m, M=Mf, caps=(not covered['L'], not covered['R']))
            if stone_kind and F['z0'] > 0.01 and not hollow:
                kg.cbox(mb, Mf @ Matrix.Translation((0, n * T / 2, -F['z0'] / 2)), (2 * half, n * T, F['z0']), cheek_m,
                        drop_bottom=True)
            for side in ('L', 'R'):
                lx = side_local_x(F, side)
                sg = 1 if lx > 0 else -1
                if side == ws:
                    top = 1.5 if S == 'cliff' else 1.2
                    cpoly = [(-0.05, -F['z0']), (n * T, -F['z0']), (n * T, n * R + top), (-0.05, R + top)]
                    kg.prism_x(mb, cpoly, min(lx, lx - sg * wall_t), max(lx, lx - sg * wall_t), cheek_m, M=Mf)
                    continue
                if not F['sides'][side]:
                    continue
                xin = lx - sg * max(ct, 0.06)
                if stone_kind or timber:
                    zb0 = -F['z0'] if not hollow else -0.6
                    cpoly = [(-0.05, zb0 if stone_kind else 0.0),
                             (n * T, zb0 + n * R if (hollow or not stone_kind) else zb0),
                             (n * T, zn(n * T) + hc), (-0.05, zn(-0.05) + hc)]
                    if timber:
                        cpoly = [(-0.05, 0.0), (n * T, n * R - 0.3), (n * T, n * R + 0.06), (-0.05, R + 0.06)]
                    kg.prism_x(mb, cpoly, min(lx, xin), max(lx, xin), cheek_m, M=Mf)
                xr = (lx + xin) / 2
                base = (lambda s_: zn(s_) + hc) if stone_kind else (lambda s_: zn(s_) + 0.06)
                if not (stone_kind or timber):
                    base = lambda s_: R * (1 + int(max(0.0, s_) / T))
                for s_ in (0.15, n * T - 0.15):
                    z0_ = base(s_)
                    kg.cbox(mb, Mf @ Matrix.Translation((xr, s_, (z0_ + zn(s_) + rail_h) / 2)), (0.09, 0.09, zn(s_) + rail_h - z0_),
                            rail_m, drop_bottom=True)
                pts = [Mf @ Vector((xr, 0.1, zn(0.1) + rail_h - 0.035)), Mf @ Vector((xr, n * T - 0.1, zn(n * T - 0.1) + rail_h - 0.035))]
                kg.sweep(mb, pts, [(-0.04, -0.035), (0.04, -0.035), (0.04, 0.035), (-0.04, 0.035)], rail_m, caps=False)
                if P['lanterns'] != 'none' and (stone_kind or S == 'hinoki'):
                    if fi == 0 and P['lanterns'] in ('bottom', 'both'):
                        add_newel(Mf, lx - sg * 0.18, -0.22, 0, 0.0, 2)
                    if fi == len(flights) - 1 and P['lanterns'] in ('top', 'both'):
                        add_newel(Mf, lx - sg * 0.18, n * T + 0.2, n * R - 0.4, n * R, 2)
        for Ld in landings:
            if lod == 3:
                bm = mb.bm
                vs = [bm.verts.new((x, y, Ld['z'])) for x, y in ((Ld['x0'], Ld['y0']), (Ld['x1'], Ld['y0']), (Ld['x1'], Ld['y1']), (Ld['x0'], Ld['y1']))]
                mb._tag([bm.faces.new(vs)], tread_m)
            else:
                th = Ld['z'] if (stone_kind and not hollow) else 0.25
                kg.cbox(mb, Matrix.Translation(((Ld['x0'] + Ld['x1']) / 2, (Ld['y0'] + Ld['y1']) / 2, Ld['z'] - th / 2)),
                        (Ld['x1'] - Ld['x0'], Ld['y1'] - Ld['y0'], th), tread_m, drop_bottom=stone_kind and not hollow)
        return _finish(mb, P, lights, lod, flights, [wood, wood_d], paper)

    # =================================================================== LOD0 / LOD1
    for fi, F in enumerate(flights):
        Mf = flight_frame(F)
        n = F['n']
        half = (F['x1'] - F['x0']) / 2
        L_ = n * T
        ws = wall_side(F)
        upper_hollow = stone_kind and hollow and F['z0'] > 0.01
        # tread extents: between cheeks / stringers / host wall
        xa, xb = -half, half
        for side in ('L', 'R'):
            has = F['sides'][side] and (stone_kind or timber) or (timber and S == 'hinoki') or S == 'ladder'
            inset = 0.0
            if side == ws:
                inset = wall_t - (0.15 if S == 'cantilever' else 0.0)      # cantilever slabs keyed 0.15 into the wall
            elif has and stone_kind:
                inset = ct
            if side == 'L':
                xa = -half + inset
            else:
                xb = half - inset
        # solid plinth under an upper stone flight of a straight plan; switchback upper flights stay hollow
        if stone_kind and F['z0'] > 0.01 and not hollow:
            kg.cbox(mb, Mf @ Matrix.Translation((0, L_ / 2, -F['z0'] / 2)), (2 * half - 0.01, L_ + 0.02, F['z0']), cheek_m,
                    drop_bottom=True)
        if upper_hollow:
            # soffit beam under the slabs (the void below shows from the side)
            spoly = [(0.0, -0.24), (L_, n * R - 0.24 - R), (L_, n * R - R), (0.0, 0.0)]
            kg.prism_x(mb, spoly, xa + 0.02, xb - 0.02, cheek_m, M=Mf)
        # ---------------- treads
        for i in range(n):
            z_top = (i + 1) * R
            y0 = i * T
            if stone_kind:
                lw = xb - xa
                if rough and lod == 0:
                    k = max(1, min(2 if lw < 2.6 else 3, split_base + r.choice([-1, 0, 0, 1])))
                    k = min(k, max(1, int(lw / 0.6)))
                else:
                    k = 1
                cuts = [xa] + sorted(xa + lw * (j + r.uniform(-0.2, 0.2)) / k for j in range(1, k)) + [xb]
                for j in range(k):
                    gx = 0.01 if (lod == 0 and k > 1) else 0.0
                    pxa, pxb = cuts[j] + (gx if j > 0 else 0), cuts[j + 1] - (gx if j < k - 1 else 0)
                    no = nos + (r.uniform(-0.015, 0.015) if rough else 0)
                    thick = R + 0.06 if (i > 0 or upper_hollow) else R
                    if S == 'pool_entry' and lod == 0:
                        rr = 0.035
                        prof = [(-no, -thick), (-no, -rr), (-no + rr * 0.3, -rr * 0.3), (-no + rr, 0.0), (T + 0.02, 0.0), (T + 0.02, -thick)]
                    elif lod == 0 and k == 1:
                        c = 0.02 if rough else 0.008
                        prof = [(-no, -thick), (-no, -c), (-no + c, 0.0), (T + 0.02, 0.0), (T + 0.02, -thick)]
                    else:
                        prof = [(-no, -thick), (-no, 0.0), (T + 0.02, 0.0), (T + 0.02, -thick)]
                    Mi = Mf @ Matrix.Translation((0, y0, z_top))
                    if rough and lod == 0:
                        Mi = Mi @ Matrix.Rotation(r.uniform(-0.02, 0.02), 4, 'Z') @ Matrix.Rotation(r.uniform(-0.012, 0.006), 4, 'X')
                    fs = kg.prism_x(mb, prof, pxa, pxb, tread_m, M=Mi)
                    if rough and lod == 0:
                        for v in {v for f in fs for v in f.verts}:
                            v.co += Vector((r.uniform(-0.012, 0.012), r.uniform(-0.01, 0.01), r.uniform(-0.007, 0.004)))
            elif timber:
                tt = 0.045 if S == 'hinoki' else 0.04
                dep_t = T + nos if S == 'hinoki' else T + 0.06
                Mi = Mf @ Matrix.Translation(((xa + xb) / 2, y0 + dep_t / 2 - nos, z_top - tt / 2))
                kg.cbox(mb, Mi, (xb - xa - 2 * ct + 0.03, dep_t, tt), wood)          # housed into the stringers
                if closed_risers:
                    Mi = Mf @ Matrix.Translation(((xa + xb) / 2, y0 + 0.012, z_top - tt - (R - tt) / 2))
                    kg.cbox(mb, Mi, (xb - xa - 2 * ct + 0.02, 0.02, R - tt), wood_d)
            else:  # cantilever: floating slabs keyed into the host wall
                tt = 0.09 if i > 0 else R
                Mi = Mf @ Matrix.Translation(((xa + xb) / 2, y0 + (T + nos) / 2 - nos + 0.01, z_top - tt / 2))
                kg.cbox(mb, Mi, (xb - xa, T + nos, tt), tread_m, bevel=0.012 if lod == 0 else 0.0,
                        jitter=0.006 if lod == 0 else 0.0, r=r)
        # ---------------- host wall on the closed side (cliff rock face / cantilever basalt stub)
        if ws:
            lx = side_local_x(F, ws); sg = 1 if lx > 0 else -1
            top = 1.5 if S == 'cliff' else r.uniform(1.0, 1.3)
            zb_ = -F['z0']
            kg.rock_body(mb, Mf, -0.1 if fi == 0 else 0.0, L_ + 0.1, lx, lx - sg * wall_t,
                         lambda s_: min(zn(s_), n * R) + top, lambda s_: zb_,
                         max(2, int(L_ / (0.6 if lod == 0 else 1.4))), (4 if S == 'cliff' else 2) if lod == 0 else 1,
                         (0.09 if S == 'cliff' else 0.025) if lod == 0 else 0.0, r, cheek_m,
                         top_noise=0.12 if (S == 'cliff' and lod == 0) else 0.0)
        # ---------------- open sides: cheek walls (stone) / stringers (timber)
        stepped_blocks = {}
        for side in ('L', 'R'):
            lx = side_local_x(F, side)
            sg = 1 if lx > 0 else -1
            if stone_kind and F['sides'][side] and side != ws:
                xo, xi = lx, lx - sg * ct
                xlo, xhi = min(xo, xi), max(xo, xi)
                bot = (lambda s_: max(-F['z0'], zn(s_) - hc - 0.75)) if upper_hollow else (lambda s_: -F['z0'] if not hollow else 0.0)
                if cheek in ('raking', 'bare') or not rough or lod == 1:
                    cop = 0.08 if (cheek == 'raking' or not rough) else 0.0
                    disp = (0.06 if cheek in ('raking', 'bare') else 0.0) if (rough and lod == 0) else 0.0
                    ns = max(2, int(L_ / (0.65 if lod == 0 else 1.6)))
                    nz = (3 if not upper_hollow else 2) if (rough and lod == 0) else 1
                    kg.rock_body(mb, Mf, 0.0, L_ + 0.02, xo, xi, lambda s_: zn(s_) + hc - cop, bot, ns, nz, disp, r, cheek_m,
                                 top_noise=0.07 if (cheek == 'bare' and lod == 0) else 0.0)
                    if cop:
                        # raking coping slabs following the pitch
                        nseg = max(1, int(round(L_ / r.uniform(0.7, 1.0)))) if lod == 0 else max(1, int(round(L_ / 1.6)))
                        cut = [0.0] + sorted(L_ * (j + r.uniform(-0.15, 0.15)) / nseg for j in range(1, nseg)) + [L_ + 0.02]
                        sl = math.atan2(R, T)
                        for j in range(nseg):
                            sa, sb = cut[j], cut[j + 1]
                            Lc = math.hypot(sb - sa, (sb - sa) * R / T)
                            Mc = Mf @ Matrix.Translation(((xlo + xhi) / 2 + (r.uniform(-0.01, 0.01) if lod == 0 else 0), (sa + sb) / 2,
                                                          zn((sa + sb) / 2) + hc - cop / 2)) @ Matrix.Rotation(sl, 4, 'X')
                            kg.cbox(mb, Mc, (xhi - xlo + 0.04, Lc - (0.008 if lod == 0 else 0), cop), cheek_m,
                                    jitter=0.006 if (rough and lod == 0) else 0.0, r=r)
                else:
                    # stepped rubble cheek: columns 2-3 treads long with level tops that step 0.15-0.3 m,
                    # each column built from 0.4-0.6 m courses of rough basalt blocks (chipped corners,
                    # 0.03-0.06 m per-block face offsets, joints staggered between columns)
                    nseg = max(2, int(round(L_ / r.uniform(0.66, 0.85))))
                    cut = [0.0] + sorted(L_ * (j + r.uniform(-0.15, 0.15)) / nseg for j in range(1, nseg)) + [L_ + 0.02]
                    blocks = []
                    zfloor = 0.0
                    for j in range(nseg):
                        sa, sb = cut[j], cut[j + 1]
                        zl = zn(sa) + hc + r.uniform(-0.03, 0.04)
                        blocks.append((sa, sb, zl))
                        zs = [zl]
                        while zs[-1] - zfloor > 0.9 and len(zs) < 3:
                            zs.append(zs[-1] - r.uniform(0.4, 0.6))
                        zs.append(zfloor)
                        for q in range(len(zs) - 1):
                            zt_, zb_ = zs[q], zs[q + 1]
                            gj = 0.014
                            c1 = r.uniform(0.03, 0.06)
                            c2 = r.uniform(0.02, 0.05) if q == 0 else r.uniform(0.0, 0.03)
                            ya_, yb_ = sa + gj, sb - gj
                            if r.random() < 0.5:
                                poly = [(ya_, zb_ + gj * 0.5), (yb_, zb_ + gj * 0.5), (yb_, zt_), (ya_ + c1, zt_), (ya_, zt_ - c1)]
                            else:
                                poly = [(ya_, zb_ + gj * 0.5), (yb_, zb_ + gj * 0.5), (yb_, zt_ - c1), (yb_ - c1, zt_), (ya_, zt_)]
                            off = sg * r.choice([-1, -1, 0.4]) * r.uniform(0.03, 0.05)
                            capsx = (True, True) if q == 0 else ((False, True) if sg > 0 else (True, False))
                            fs = kg.prism_x(mb, poly, xlo + 0.004 + off, xhi - 0.004 + off, cheek_m, M=Mf, caps=capsx)
                            for v in {v for f in fs for v in f.verts}:
                                v.co += Vector((r.uniform(-0.015, 0.015), r.uniform(-0.01, 0.01), r.uniform(-0.01, 0.01)))
                    stepped_blocks[side] = blocks
            elif timber:
                xo, xi = lx, lx - sg * ct
                xlo, xhi = min(xo, xi), max(xo, xi)
                dep = 0.28 if S == 'hinoki' else 0.25
                kk = R / T
                over = 0.06
                s_end = L_
                poly = [(-0.06, 0.0), (min(s_end, dep / kk * 0.9) - 0.06, 0.0), (s_end, max(0.0, R + s_end * kk - dep)),
                        (s_end, n * R + over), (-0.06, R - 0.06 * kk + over)]
                kg.prism_x(mb, poly, xlo, xhi, wood_d, M=Mf)
                if S == 'ladder':
                    # stringers run up past the head as the handrail posts (and a short newel at the foot)
                    for s_, z0_, z1_ in ((L_ - 0.04, n * R - 0.1, n * R + 0.9), (0.04, 0.0, R + 0.9)):
                        kg.cbox(mb, Mf @ Matrix.Translation(((xlo + xhi) / 2, s_, (z0_ + z1_) / 2)), (xhi - xlo, 0.09, z1_ - z0_), wood_d)
                        if lod == 0:
                            P0 = Mf @ Vector(((xlo + xhi) / 2, s_, 0))
                            kg.giboshi(mb, (P0.x, P0.y, P0.z + z1_), iron, 1, scale=0.8, style=finial, rscale=1.0)
                if lod == 0:
                    kg.cbox(mb, Mf @ Matrix.Translation(((xlo + xhi) / 2, 0.1, 0.06)), (xhi - xlo + 0.012, 0.2, 0.12), iron)
                    kg.cbox(mb, Mf @ Matrix.Translation(((xlo + xhi) / 2, s_end - 0.08, n * R - 0.06)), (xhi - xlo + 0.012, 0.14, 0.2), iron)
        # ---------------- rails on open sides
        for side in ('L', 'R'):
            if not F['sides'][side] or side == ws:
                continue
            lx = side_local_x(F, side)
            sg = 1 if lx > 0 else -1
            if stone_kind:
                xr = lx - sg * ct / 2
                if side in stepped_blocks:
                    bl = stepped_blocks[side]
                    base = lambda s_, bl=bl: next((zl for sa, sb, zl in bl if sa <= s_ <= sb), zn(s_) + hc) - 0.02
                else:
                    base = lambda s_: zn(s_) + hc
            elif timber:
                xr = lx - sg * ct / 2
                base = lambda s_: zn(s_) + 0.06
            else:
                xr = lx - sg * 0.05
                base = lambda s_: R * (1 + min(n - 1, int(max(0.0, s_) / T)))
            hand = lambda s_: zn(s_) + rail_h
            sa, sb = 0.12, L_ - 0.12
            if S == 'ladder':
                sa, sb = 0.04, L_ - 0.04
            nb = max(1, int(math.ceil((sb - sa) / spacing)))
            ss = [sa + (sb - sa) * j / nb for j in range(nb + 1)]
            wooden = rail_m == wood
            pw = {'stone_rough': 0.11, 'cliff': 0.11, 'stone_polished': 0.1, 'hinoki': 0.09}.get(S, 0.04)
            # posts (ladder: the stringer extensions are the posts; iron stanchions in between)
            for j, s_ in enumerate(ss):
                if S == 'ladder' and j in (0, len(ss) - 1):
                    continue
                z0_ = base(s_)
                z1_ = hand(s_) + (0.06 if wooden else -0.01)
                P0 = Mf @ Vector((xr, s_, 0))
                if S == 'ladder':
                    mb.cylinder((P0.x, P0.y, P0.z + (z0_ + z1_) / 2), radius=0.014, depth=z1_ - z0_, mi=iron, segs=4, cap=False)
                elif wooden:
                    if lod == 0:
                        kg.cbox(mb, Mf @ Matrix.Translation((xr, s_, (z0_ + z1_) / 2)), (pw, pw, z1_ - z0_), wood_d, drop_bottom=True)
                        kg.band(mb, (P0.x, P0.y, P0.z + hand(s_) - 0.035), pw + 0.016, pw + 0.016, 0.06, iron)    # rail collar
                        kg.giboshi(mb, (P0.x, P0.y, P0.z + z1_), iron, 1, scale=1.0, style=finial, rscale=pw * 1.3 / 2 / 0.064, segs=5)
                    else:
                        kg.cbox(mb, Mf @ Matrix.Translation((xr, s_, (z0_ + z1_) / 2)), (pw, pw, z1_ - z0_), wood_d, drop_bottom=True)
                        mb.cylinder((P0.x, P0.y, P0.z + z1_ + 0.05), radius=pw * 0.75, radius2=0.0, depth=0.1, mi=iron, segs=4,
                                    rot=(0, 0, math.pi / 4), cap=False)
                else:
                    mb.cylinder((P0.x, P0.y, P0.z + (z0_ + z1_) / 2), radius=pw / 2, depth=z1_ - z0_, mi=iron,
                                segs=6 if lod == 0 else 4, cap=False)
            # handrail
            if wooden:
                prof = [(0.033 * math.cos(a), 0.033 * math.sin(a)) for a in [k * math.pi / 4 + math.pi / 8 for k in range(8)]] if lod == 0 \
                    else [(-0.04, -0.035), (0.04, -0.035), (0.04, 0.035), (-0.04, 0.035)]
            else:
                rr = 0.024
                prof = [(rr * math.cos(a), rr * math.sin(a)) for a in [k * math.pi / 3 for k in range(6)]] if lod == 0 \
                    else [(-rr, -rr), (rr, -rr), (rr, rr), (-rr, rr)]
            if S == 'ladder':
                prof = [(0.025 * math.cos(a), 0.025 * math.sin(a)) for a in [k * math.pi / 3 for k in range(6)]]
            e0, e1 = ss[0] - 0.08, ss[-1] + 0.08
            pts = [Mf @ Vector((xr, e0, hand(e0) - 0.035)), Mf @ Vector((xr, e1, hand(e1) - 0.035))]
            if S == 'pool_entry' and lod == 0:
                pts = pts + [Mf @ Vector((xr, e1 + 0.12, hand(e1) - 0.1)), Mf @ Vector((xr, e1 + 0.16, hand(e1) - 0.3))]
            kg.sweep(mb, pts, prof, wood if S == 'ladder' else rail_m)
            mprof = [(-0.022, -0.03), (0.022, -0.03), (0.022, 0.03), (-0.022, 0.03)] if wooden else \
                [(-0.012, -0.012), (0.012, -0.012), (0.012, 0.012), (-0.012, 0.012)]
            if S != 'ladder':
                if rail_scheme == 'balusters' and lod == 0:
                    lowz = lambda s_: base(s_) + 0.07 if wooden else zn(s_) + 0.12
                    pts = [Mf @ Vector((xr, ss[0], lowz(ss[0]))), Mf @ Vector((xr, ss[-1], lowz(ss[-1])))]
                    kg.sweep(mb, pts, mprof, rail_m)
                    # balusters at 0.18 m centres between the bottom rail and the handrail
                    nbal = int((ss[-1] - ss[0]) / 0.18)
                    for k in range(1, nbal):
                        s_ = ss[0] + (ss[-1] - ss[0]) * k / nbal
                        if min(abs(s_ - q) for q in ss) < 0.07:
                            continue
                        za, zb = lowz(s_), hand(s_) - 0.06
                        P0 = Mf @ Vector((xr, s_, 0))
                        mb.cylinder((P0.x, P0.y, P0.z + (za + zb) / 2), radius=0.024 if wooden else 0.009, depth=zb - za,
                                    mi=rail_m, segs=3, cap=False, rot=(0, 0, r.uniform(0, 1)))
                else:
                    mid = lambda s_: (base(s_) + hand(s_)) / 2 if (stone_kind or timber) else zn(s_) + 0.45
                    pts = [Mf @ Vector((xr, ss[0], mid(ss[0]))), Mf @ Vector((xr, ss[-1], mid(ss[-1])))]
                    kg.sweep(mb, pts, mprof, rail_m)
        # ---------------- lanterns: newel piers at the bottom / top, coping lanterns every ~8 risers
        if P['lanterns'] != 'none':
            for side in ('L', 'R'):
                if not F['sides'][side] or side == ws:
                    continue
                lx = side_local_x(F, side); sg = 1 if lx > 0 else -1
                if stone_kind or S == 'hinoki':
                    xc_ = lx - sg * 0.18
                    if fi == 0 and P['lanterns'] in ('bottom', 'both'):
                        add_newel(Mf, xc_, -0.22, -F['z0'] if not hollow else 0.0, 0.0, lod)
                    if fi == len(flights) - 1 and P['lanterns'] in ('top', 'both'):
                        add_newel(Mf, xc_, L_ + 0.2, (-F['z0'] if not hollow else n * R - 0.6) if stone_kind else n * R - 0.4,
                                  n * R, lod)
                    if stone_kind:
                        for k in range(8, n - 5, 8):
                            s_ = k * T
                            add_lantern(Mf, lx - sg * ct / 2, s_, zn(s_) + hc - 0.05, zn(s_) + hc + 0.4, lod, pier_w=0.26)
                elif S == 'ladder' and fi == len(flights) - 1 and side == ('R' if F['sides']['R'] else 'L'):
                    # hung outboard of the head post on an iron bracket arm
                    P0 = Mf @ Vector((lx + sg * 0.17, L_ - 0.04, 0))
                    Pa = Mf @ Vector((lx + sg * 0.08, L_ - 0.04, n * R + 0.82))
                    kg.cbox(mb, Matrix.Translation(Pa), (0.2 if abs(Pa.x - P0.x) > 0.01 else 0.02, 0.02, 0.02), iron)
                    c_ = kg.lantern_slim(mb, (P0.x, P0.y, P0.z + n * R + 0.36), M, lod, size=0.2, height=0.36, roof=roof)
                    lights.append([round(c_.x, 3), round(c_.y, 3), round(c_.z, 3)])

    # ---------------- landings
    for Ld in landings:
        xc, yc = (Ld['x0'] + Ld['x1']) / 2, (Ld['y0'] + Ld['y1']) / 2
        lw, ll = Ld['x1'] - Ld['x0'], Ld['y1'] - Ld['y0']
        if stone_kind or S == 'cantilever':
            if S == 'cantilever':
                kg.cbox(mb, Matrix.Translation((xc, yc, Ld['z'] - 0.07)), (lw, ll, 0.14), tread_m, bevel=0.012 if lod == 0 else 0)
            elif hollow:
                # slab on two rock piers at the outer corners, open underneath
                kg.cbox(mb, Matrix.Translation((xc, yc, Ld['z'] - 0.14)), (lw - 0.02, ll - 0.02, 0.2), cheek_m)
                ye = Ld['edge_y']; yp = ye - 0.3 if ye > yc else ye + 0.3
                for xp in (Ld['x0'] + 0.3, Ld['x1'] - 0.3):
                    kg.rock_body(mb, Matrix.Translation((xp, yp, 0)), -0.25, 0.25, 0.25, -0.25,
                                 lambda s_: Ld['z'] - 0.24, lambda s_: 0.0, 2, 3 if lod == 0 else 1,
                                 0.05 if (rough and lod == 0) else 0.0, r, cheek_m)
            else:
                kg.cbox(mb, Matrix.Translation((xc, yc, (Ld['z'] - 0.08) / 2)), (lw - 0.02, ll - 0.02, Ld['z'] - 0.08), cheek_m,
                        drop_bottom=True)
            if S != 'cantilever':
                k = max(1, int(round(lw / 1.1))) if lod == 0 else 1
                for j in range(k):
                    xa_ = Ld['x0'] + lw * j / k
                    kg.cbox(mb, Matrix.Translation((xa_ + lw / k / 2, yc, Ld['z'] - 0.04)), (lw / k - 0.01, ll, 0.08), tread_m,
                            jitter=0.006 if (lod == 0 and rough) else 0, r=r)
        else:
            nbd = max(3, int(ll / 0.18)) if lod == 0 else max(2, int(ll / 0.4))
            for j in range(nbd):
                yy = Ld['y0'] + ll * (j + 0.5) / nbd
                kg.cbox(mb, Matrix.Translation((xc, yy, Ld['z'] - 0.0225)), (lw, ll / nbd - (0.008 if lod == 0 else 0), 0.045), wood)
            for sx in (Ld['x0'] + 0.06, Ld['x1'] - 0.06):
                kg.cbox(mb, Matrix.Translation((sx, yc, Ld['z'] - 0.045 - 0.11)), (0.08, ll, 0.22), wood_d)
                for sy_ in (Ld['y0'] + 0.06, Ld['y1'] - 0.06):
                    mb.box((sx, sy_, (Ld['z'] - 0.26) / 2), (0.1, 0.1, Ld['z'] - 0.26), wood_d)
        if P['plan'] == 'straight':
            for side, xr in (('R', Ld['x0'] + (ct / 2 if stone_kind or timber else 0.05)), ('L', Ld['x1'] - (ct / 2 if stone_kind or timber else 0.05))):
                if not Ld['sides'][side]:
                    if wall_t:
                        xo = Ld['x0'] if side == 'R' else Ld['x1']
                        sg = -1 if side == 'R' else 1
                        top = 1.5 if S == 'cliff' else 1.2
                        kg.rock_body(mb, Matrix.Translation((xo, Ld['y1'], 0)) @ Matrix.Rotation(math.pi, 4, 'Z'), 0.0, ll,
                                     -sg * 0.0, sg * wall_t, lambda s_: Ld['z'] + top, lambda s_: 0.0, 2, 2 if lod == 0 else 1,
                                     0.06 if (S == 'cliff' and lod == 0) else 0.0, r, cheek_m)
                    continue
                if stone_kind:
                    kg.cbox(mb, Matrix.Translation((xr, yc, Ld['z'] + hc / 2)), (ct + 0.04, ll + 0.02, hc), cheek_m, drop_bottom=True)
                kg.sweep(mb, [Vector((xr, Ld['y1'], Ld['z'] + rail_h - 0.035)), Vector((xr, Ld['y0'], Ld['z'] + rail_h - 0.035))],
                         [(-0.035, -0.035), (0.035, -0.035), (0.035, 0.035), (-0.035, 0.035)], rail_m)
        else:
            ye = Ld['edge_y']
            yr = ye - 0.05 if ye > yc else ye + 0.05
            if stone_kind:
                kg.cbox(mb, Matrix.Translation((xc, yr, Ld['z'] + hc / 2)), (lw, ct if ct else 0.1, hc), cheek_m, drop_bottom=True)
            kg.sweep(mb, [Vector((Ld['x0'] + 0.05, yr, Ld['z'] + rail_h - 0.035)), Vector((Ld['x1'] - 0.05, yr, Ld['z'] + rail_h - 0.035))],
                     [(-0.035, -0.035), (0.035, -0.035), (0.035, 0.035), (-0.035, 0.035)], rail_m)
            zb_ = hc if stone_kind else 0.0
            for xp in (Ld['x0'] + 0.08, xc, Ld['x1'] - 0.08):
                kg.cbox(mb, Matrix.Translation((xp, yr, Ld['z'] + zb_ + (rail_h - zb_) / 2)), (0.08, 0.08, rail_h - zb_), rail_m,
                        drop_bottom=True)
    return _finish(mb, P, lights, lod, flights, [wood, wood_d], paper)


def _finish(mb, P, lights, lod, flights, wood_slots, paper):
    # snap to base, re-centre the footprint (pivot = base centre of the bounding box)
    vs = mb.bm.verts
    for v in vs:
        if v.co.z < 0:
            v.co.z = 0.0
    xs = [v.co.x for v in vs]; ys = [v.co.y for v in vs]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    for v in vs:
        v.co.x -= cx; v.co.y -= cy
    o = mb.to_object(ASSET)
    o['kz_lights'] = json.dumps([dict(pos=[p[0] - cx, p[1] - cy, p[2]], color=[1.0, 0.62, 0.3], radius=3.0,
                                      source='washi_backlit') for p in lights])
    F0, F1 = flights[0], flights[-1]
    o['kz_stair'] = json.dumps(dict(steps=P['steps'], riser=round(P['riser'], 4), tread=round(P['tread'], 4),
                                    rise=round(P['steps'] * P['riser'], 3), style=P['style'], plan=P['plan'],
                                    descends=P['descends'],
                                    water_z=round(3 * P['riser'], 3) if P['style'] == 'pool_entry' else None,
                                    bottom_nosing=[round((F0['x0'] + F0['x1']) / 2 - cx, 3), round(F0['yf'] - cy, 3), round(P['riser'], 3)],
                                    top_nosing=[round((F1['x0'] + F1['x1']) / 2 - cx, 3),
                                                round(F1['yf'] + F1['dir'] * F1['n'] * P['tread'] - cy, 3),
                                                round(P['steps'] * P['riser'], 3)]))
    o['kz_params'] = json.dumps(P)
    o['kz_budget'] = json.dumps(budget(P['steps']))
    genlib.finish(o)
    if lod <= 2:
        kg.uv_grain(o, wood_slots)
    return o
