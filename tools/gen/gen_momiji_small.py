"""Red momiji maple (momiji_small), op06 first build.

Identifying features kept at every LOD: a slender twisting trunk splitting low into 2-3 sinuous leaders, and a
broad, layered crown of red palmate-leaf sprays with sky between the layers.

Concept: refs/gen/sheet-mod-nature.png panel 3 "Red momiji maple - 4.5 m" (bar 50 px/m; height arrow 230 px =
4.5 m, the drawn tree is ~5 m: built to the 4.5 m label).  Measured off the FRONT / SIDE views:
  crown width front 1.0 x h, side 0.72 x h (the proxy 4 x 4 caps it at 4.0 m); crown underside at 0.40 h;
  trunk splits at 0.25-0.32 h; trunk 0.22 m across above a 0.40 m root flare; 3 leaders fanning 20-45 deg;
  foliage in flat, layered sprays (8-15 per tree) 0.5-1.0 m across, thin (0.2-0.3 x their width).
Lookbook 08 (table aqueduct) and 22 (brand board): vivid red / orange-red maple sprays in front of basalt.
Proxy (3d/assets.json): 4.0 x 4.0 x 4.5 m.

Targets: h 2.5-5 m (default: seeded 0.85-1.0 x proxy h), crown 0.75-0.95 x h wide (fit inside the proxy),
  trunk base diameter 0.05 h, 9-16 sprays, card size 0.22-0.34 m.

Parameters: h (2.5-5 m), spread (0.7-1.0, crown width / h), density (0.5-1.5, leaf-card density), colour
  'red' | 'orange', style 'upright' | 'spreading' | 'leaning'.
Seeds (styles cycle: 1 upright, 2 spreading, 3 leaning, 4 upright ...): change the style, the number of leaders
  (2-3), the leader azimuths and lean, sub-branch counts and lengths, spray count / size / height, trunk wiggle.
  Seed 3 defaults to 'orange', the others to 'red'.

Materials:
  bark  `bark` tinted down (0.55, 0.5, 0.5) for the dark maple trunk (library bark reads orange-tan).
  leaf  `foliage_pine` cards tinted red (2.5, 0.3, 0.45) / orange (2.5, 0.85, 0.3): STAND-IN for NEW:maple_leaf
        (needle-tuft alpha, not palmate).  Proposed library material: maple_leaf, palmate alpha cards,
        base #B8301E red, variant orange #D2601E, translucency 0.45.
  core  `noren` variant 'vermilion' tinted (0.45, 0.38, 0.38): the opaque spray core (dark red, hidden inside the
        cards; it carries LOD2/LOD3).  STAND-IN until maple_leaf exists.
Animation: vertex sway.  Colour attribute `kz_sway` (POINT): R weight (0 at the base .. 0.3 at the split ..
  0.6 along branches .. 0.85-1 in the sprays), G phase per spray, B 1 on foliage; vertex group `sway` (= R).
  kz_sway_default_indoor = 0.
Lighting: lightmap (no lights).
LOD (one skeleton per seed, every LOD swept from it):
  LOD0 trunk 18 rings x 10 sides with spiral ridges and a root flare, leaders 9 x 7, sub-branches 5 x 5, twigs,
       10-seg two-ring spray cores, ~2800 cards.  LOD1 9 x 7 / 4 x 5 / 3 x 4, 8-seg one-ring cores, ~1100 larger
       cards.  LOD2 4 x 5 / 2 x 4 / 1 x 3, 6-seg cores, ~280 big cards.  LOD3 trunk + leaders (4 / 3 sides),
       a 5-sided lens per spray (no cards).
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_momiji_small as T

ASSET = 'momiji_small'
FEATURES = ['slender twisting trunk splitting into 2-3 leaders', 'broad layered crown of red leaf sprays']
STYLES = ['upright', 'spreading', 'leaning']
LEAF_TINT = {'red': (2.5, 0.3, 0.45), 'orange': (2.5, 0.85, 0.3)}
CORE_TINT = {'red': (0.085, 0.008, 0.006), 'orange': (0.11, 0.028, 0.006)}   # noren tint is the absolute colour

LODS = {
    0: dict(tr=18, ts=10, ls=9, lsd=7, bs=4, bsd=4, cs=10, inner=True, card=1.0, twig=True),
    1: dict(tr=9, ts=7, ls=4, lsd=5, bs=2, bsd=4, cs=8, inner=False, card=1.3, twig=False),
    2: dict(tr=4, ts=5, ls=2, lsd=4, bs=1, bsd=3, cs=6, inner=False, card=1.7, twig=False),
    3: dict(tr=2, ts=4, ls=1, lsd=3, bs=0, bsd=0, cs=4, inner=False, card=0, twig=False),
}


def skeleton(seed, h, spread, style, w, d):
    """trunk, leaders, spray layout (a layered dome of sprays, each fed by a sub-branch), fitted to w x d x h"""
    g = C.rng(seed, 'skel')
    off = Vector((g.uniform(-90, 90), g.uniform(-90, 90), g.uniform(-90, 90)))
    lean_az = g.uniform(0, 2 * math.pi)
    lean = {'upright': g.uniform(0.0, 0.05), 'spreading': g.uniform(0.03, 0.08), 'leaning': g.uniform(0.22, 0.3)}[style]
    split = h * {'upright': g.uniform(0.26, 0.32), 'spreading': g.uniform(0.2, 0.26), 'leaning': g.uniform(0.3, 0.36)}[style]
    ld = Vector((math.cos(lean_az), math.sin(lean_az), 0))
    wig = g.uniform(0.06, 0.1) * h / 4.5
    ph = g.uniform(0, 6.28)
    lat = Vector((-ld.y, ld.x, 0))
    trunk_ctrl = [ld * lean * split * (k / 4) * 1.6 + lat * wig * math.sin(ph + k / 4 * 4.2) * min(1, k / 4 * 3)
                  + Vector((0, 0, split * k / 4)) for k in range(5)]
    trunk = T.smooth_path(trunk_ctrl, 24)
    top = trunk[-1]
    # crown envelope: tiers of sprays between zb and h
    Rw = 0.56 * h * spread                     # crown half-width before the proxy fit
    zb = h * {'upright': 0.42, 'spreading': 0.38, 'leaning': 0.44}[style]
    cen = Vector((top.x, top.y, 0)) + ld * (lean * h * 0.9 if style == 'leaning' else 0.0)
    n_t = 4
    Rs = 0.13 * h * g.uniform(0.95, 1.1)       # spray radius (0.55-0.65 m on a 4.5 m tree)
    sprays = []
    for ti in range(n_t):
        u = ti / (n_t - 1)
        z = zb + (h - zb - Rs * 0.5) * u
        prof = {'upright': 0.7 + 0.3 * math.sin(math.pi * (0.25 + 0.6 * u)), 'spreading': 1.0 - 0.55 * u ** 1.6,
                'leaning': 0.95 - 0.45 * u ** 1.4}[style]
        rt = Rw * prof - Rs * 0.6
        n = max(1, int(round(2 * math.pi * rt / (2.0 * Rs))))
        if ti == n_t - 1:
            n = max(1, min(n, 3))
        a0 = g.uniform(0, 2 * math.pi)
        for k in range(n):
            a = a0 + 2 * math.pi * (k + g.uniform(-0.2, 0.2)) / n
            rr = rt * g.uniform(0.8, 1.0) if n > 1 else rt * 0.25
            c = cen + Vector((math.cos(a) * rr, math.sin(a) * rr, z + g.uniform(-0.06, 0.06) * h))
            if style == 'leaning':
                c += ld * (u * 0.25 * h * lean)
            sprays.append(dict(c=c, R=Rs * g.uniform(0.82, 1.12) * (1.08 - 0.15 * u), ph=g.random(),
                               d=Vector((math.cos(a), math.sin(a), 0)), tier=ti))
    if n_t >= 3:                                # an inner mid-height spray fills the centre
        sprays.append(dict(c=cen + Vector((g.uniform(-0.1, 0.1) * h, g.uniform(-0.1, 0.1) * h, zb + (h - zb) * 0.55)),
                           R=Rs * 0.95, ph=g.random(), d=ld if ld.length else Vector((1, 0, 0)), tier=1))
    for S in sprays:
        S['T'] = S['R'] * g.uniform(0.22, 0.3)
        S['flat'] = g.uniform(1.1, 1.3)
        S['lobes'] = g.choice([4, 5, 6])
    # leaders: 2-3 sinuous stems from the split towards the crown, each aimed at a sector of sprays
    n_lead = 2 if style == 'leaning' else g.choice([2, 3, 3])
    az0 = g.uniform(0, 2 * math.pi)
    branches = []
    leads = []
    r_split = 0.02 * h
    for li in range(n_lead):
        az = az0 + 2 * math.pi * li / n_lead + g.uniform(-0.3, 0.3)
        if style == 'leaning':
            az = lean_az + (li - 0.5) * g.uniform(0.8, 1.2)
        reach = Rw * {'upright': g.uniform(0.3, 0.45), 'spreading': g.uniform(0.45, 0.6), 'leaning': g.uniform(0.35, 0.5)}[style]
        tipz = zb + (h - zb) * g.uniform(0.55, 0.75)
        dv = Vector((math.cos(az), math.sin(az), 0))
        sw = Vector((-dv.y, dv.x, 0)) * reach * g.uniform(0.15, 0.3) * g.choice([-1, 1])
        tip = cen + dv * reach + Vector((0, 0, tipz))
        ctrl = [top, top.lerp(tip, 0.33) + sw, top.lerp(tip, 0.66) - sw * 0.6, tip]
        lead = T.smooth_path(ctrl, 18)
        leads.append(lead)
        branches.append(dict(pts=lead, r0=r_split * 0.72, r1=0.009 * h, s0=0.3, s1=0.6, level=1, ph=g.random()))
    # one sub-branch per spray, from the nearest leader point below it, arching up into the spray
    for S in sprays:
        best = None
        for lead in leads:
            for j, q in enumerate(lead[3:], 3):
                if q.z > S['c'].z - 0.15:
                    continue
                dd = (q - S['c']).length
                if best is None or dd < best[0]:
                    best = (dd, q, j / (len(lead) - 1))
        if best is None:
            best = (0, leads[0][-1], 1.0)
        _, q, tq = best
        mid = q.lerp(S['c'], 0.5) + Vector((0, 0, 0.08 * (S['c'] - q).length))
        side = (S['c'] - q).cross(Vector((0, 0, 1)))
        side = side.normalized() * 0.08 * (S['c'] - q).length * g.choice([-1, 1]) if side.length > 1e-4 else Vector()
        sub = T.smooth_path([q, mid + side, S['c'] - Vector((0, 0, S['T'] * 0.2))], 8)
        branches.append(dict(pts=sub, r0=max(0.008, 0.6 * (r_split * 0.72 + (0.009 * h - r_split * 0.72) * tq)), r1=0.006,
                             s0=0.35 + 0.25 * tq, s1=0.8, level=2, ph=S['ph']))

    def ext():
        xs, ys = [], []
        for S in sprays:
            R = S['R'] * S['flat'] * 1.15 + 0.1
            xs += [S['c'].x - R, S['c'].x + R]; ys += [S['c'].y - R, S['c'].y + R]
        for p in trunk:
            xs.append(p.x); ys.append(p.y)
        return min(xs), max(xs), min(ys), max(ys)
    x0, x1, y0, y1 = ext()
    k = min(1.0, w * 0.96 / (x1 - x0), d * 0.96 / (y1 - y0))
    kz = h / max(S['c'].z + S['T'] * 1.2 for S in sprays)

    def sc(v):
        return Vector((v.x * k, v.y * k, v.z * kz))
    trunk = [sc(p) for p in trunk]
    for B in branches:
        B['pts'] = [sc(p) for p in B['pts']]
    for S in sprays:
        S['c'] = sc(S['c']); f = 0.6 + 0.4 * k
        S['R'] *= f; S['T'] *= f
    x0, x1, y0, y1 = ext()
    shift = Vector((-(x0 + x1) / 2, -(y0 + y1) / 2, 0))
    return dict(trunk=trunk, branches=branches, sprays=sprays, off=off, shift=shift, r_base=0.026 * h)


def build(lod, seed, h=None, spread=None, density=None, colour=None, style=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    style = style or C.cycle(seed, STYLES)
    h = max(2.5, min(5.0, h or p['h'] * g.uniform(0.9, 1.0)))
    spread = spread or g.uniform(0.88, 1.0)
    density = density if density is not None else g.uniform(0.85, 1.15)
    colour = colour or ('orange' if (seed - 1) % 3 == 2 else 'red')
    w = min(p['w'], h * spread)
    sk = skeleton(seed, h, spread, style, w, min(p['d'], w * 0.92))
    L = LODS[lod]

    mb = genlib.MeshBuilder()
    bark = mb.slot('bark', tint=(0.55, 0.5, 0.5))
    leaf = mb.slot('foliage_pine', tint=LEAF_TINT[colour])
    core = mb.slot('noren', variant='vermilion', tint=CORE_TINT[colour])
    G = T.TreeGeo(mb)
    bm = mb.bm
    off = sk['off']

    # ---------------- trunk: twisting, spiral ridges, root flare
    nr = L['tr']
    ts_ = [i / (nr - 1) for i in range(nr)]
    if lod < 2:
        ts_ = sorted(set([0.0, 0.02, 0.05, 0.1] + ts_))
    pts = [T.along(sk['trunk'], t) for t in ts_]
    rb = sk['r_base']
    rad = [rb * (1 - 0.35 * t) * (1.2 if lod == 3 else 1.0) for t in ts_]

    def tmod(i, th):
        t = ts_[i]
        flare = 1.0 + 0.9 * math.exp(-t / 0.06) * (0.4 + 0.6 * max(0.0, math.cos(4 * th + 0.5)) ** 1.5) if lod < 3 else 1.0 + 0.5 * math.exp(-t / 0.06)
        ridge = 1.0 + 0.09 * math.cos(3 * th + 5.0 * t) + 0.04 * math.cos(7 * th - 3 * t) if lod < 2 else 1.0
        knot = 1.0 + 0.06 * T.nz((math.cos(th), math.sin(th), t * 6), off) if lod == 0 else 1.0
        return flare * ridge * knot
    rings = G.tube(pts, rad, bark, L['ts'], lambda t: 0.3 * t ** 1.5, mod=tmod)
    for v in rings[0]:
        v.co.z = 0.0

    # ---------------- leaders and sub-branches
    for bi, B in enumerate(sk['branches']):
        if B['level'] == 2 and L['bs'] == 0:
            continue
        n_seg = L['ls'] if B['level'] == 1 else L['bs']
        sides = L['lsd'] if B['level'] == 1 else L['bsd']
        bp = T.resample(B['pts'], n_seg)
        r0, r1 = B['r0'], B['r1']
        if lod == 3:
            r0, r1 = r0 * 1.3, r1 * 2
        br = [r0 + (r1 - r0) * (j / n_seg) ** 0.8 for j in range(n_seg + 1)]
        G.tube(bp, br, bark, sides, lambda t, B=B: B['s0'] + (B['s1'] - B['s0']) * t, B['ph'], cap1=(lod < 2))

    # ---------------- spray cores
    samplers = []
    for si, S in enumerate(sk['sprays']):
        cr = genlib.rng(seed, f'spray{si}')
        k_core = 0.72 if lod < 2 else (0.92 if lod == 2 else 1.2)
        segs = L['cs'] if lod < 3 else (4 if len(sk['sprays']) <= 22 else 3)
        smp = G.lens(S['c'], S['R'] * k_core, S['T'] * (0.8 if lod < 2 else (1.0 if lod == 2 else 2.2)), core, segs, 0.9, S['ph'],
                     off + Vector((si * 3.1, si * 1.7, 0)), inner=L['inner'], lobes=S['lobes'], flat=S['flat'], d=S['d'])
        samplers.append((S, smp))
        if L['twig']:              # 2-3 twigs fanning from the branch tip into the spray
            for j in range(2):
                a = cr.uniform(0, 2 * math.pi)
                tip = S['c'] + Vector((math.cos(a), math.sin(a), 0)) * S['R'] * cr.uniform(0.45, 0.8) + Vector((0, 0, S['T'] * 0.1))
                base = S['c'] - Vector((0, 0, 0.03))
                G.tube([base, base.lerp(tip, 0.5) + Vector((0, 0, 0.04)), tip], [0.012, 0.008, 0.004], bark, 3,
                       lambda t: 0.75 + 0.2 * t, S['ph'])

    # ---------------- leaf cards: the budget left after wood + cores, spread by spray area
    if L['card']:
        budget = genlib.budget_of(ASSET) or [8000, 3200, 900, 200]
        used = sum(len(f.verts) - 2 for f in bm.faces)
        n_total = max(0, int((budget[lod] * 0.97 - used) / 2 * min(1.0, density)))
        areas = [S['R'] ** 2 * S['flat'] for S, _ in samplers]
        csz = L['card'] * (1.0 + 0.25 * max(0.0, 1.0 - density))
        for si, (S, (edge, P_, top_z)) in enumerate(samplers):
            cr = genlib.rng(seed, f'cards{si}')
            n_c = max(4, int(n_total * areas[si] / sum(areas)))
            for j in range(n_c):
                th = cr.uniform(0, 2 * math.pi)
                rimc = cr.random() < 0.35
                f = cr.uniform(0.92, 1.25) if rimc else math.sqrt(cr.uniform(0.0, 1.0)) * 1.05
                z = S['T'] * cr.uniform(-0.25, 0.25) if rimc else top_z(th, min(f, 1.0)) * cr.uniform(0.7, 1.05)
                q = P_(th, f * (0.72 if lod < 2 else 0.85), z)
                outward = (q - S['c']).to_2d()
                outward = Vector((outward.x, outward.y, 0)).normalized() if outward.length > 1e-4 else Vector((math.cos(th), math.sin(th), 0))
                # layered sprays: cards lie close to horizontal (10-30 deg), drooping a little at the rim
                n = (Vector((0, 0, 1)) + outward * (cr.uniform(0.8, 1.6) if rimc else cr.uniform(0.3, 0.9) * f)).normalized()
                rot = cr.uniform(0, 2 * math.pi)
                tg = Vector((math.cos(rot), math.sin(rot), 0))
                tg = (tg - n * tg.dot(n)).normalized()
                a = math.radians(cr.uniform(15, 40))
                up = (tg * math.cos(a) + n * math.sin(a)).normalized()
                right = up.cross(n).normalized()
                wc, hc = cr.uniform(0.28, 0.4) * csz, cr.uniform(0.24, 0.34) * csz
                base = q - up * hc * 0.45
                G.card(base, right, up, wc, hc, leaf, min(1.0, 0.85 + 0.15 * f), S['ph'], cr.choice([0.0, 0.17, 0.33]))

    for v in bm.verts:
        if v.co.z < 0:
            v.co.z = 0.0
    from mathutils import Vector as _V
    import bmesh
    bmesh.ops.translate(bm, vec=sk['shift'], verts=bm.verts)
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
    bmesh.ops.translate(bm, vec=_V((-(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, 0)), verts=bm.verts)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=60)
    T.post(o, (leaf, core))
    C.set_json_props(o, kz_params=dict(h=round(h, 3), spread=round(spread, 3), density=round(density, 3), colour=colour,
                                       style=style, sprays=len(sk['sprays']), leaders=sum(1 for B in sk['branches'] if B['level'] == 1)),
                     kz_material_pending={'maple_leaf': 'stand-in foliage_pine tinted', 'bark': 'library bark tinted 0.5'})
    o['kz_sway_default_indoor'] = 0
    return o
