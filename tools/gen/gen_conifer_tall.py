"""Tall cliff conifer (conifer_tall), op06 first build.  Exterior skyline tree, far tier.

Identifying features kept at every LOD: a tall, dark, narrow conifer spire (bare lower trunk, a stack of
drooping needle whorls tapering to a pointed leader) along the cliffs and ridges.

Concept: lookbook 21 (private suite: dark spires behind the deck), 32 (north cliff suites: dark conifers on the
ledges, seen at 30-200 m), 11 (caldera crown: tiered ridge pines and spires on the far ridges).  No scale sheet
shows this tree; scale from the row / proxy: 4 x 4 x 12 m (h 6-15 m).  Measured off lookbook 32 against the
3 m suite storeys: spires 3-5 storeys tall (9-15 m), crown width 0.25-0.35 x h, bare trunk under the lowest
whorl 0.15-0.3 x h.

Targets: h default seeded 0.85-1.0 x proxy h (10.2-12 m); crown base 0.15-0.3 h; crown max width 0.28-0.34 h
  (capped by the proxy 4 m); 8-14 whorls (spire) or 5-7 open tiers (layered); trunk 0.22 m across at 12 m.

Parameters: h (6-15 m), crown (0.7-1.3, crown width factor), tiers (4-14), style 'spire' | 'layered' | 'flagged'.
Seeds (styles cycle: 1 spire, 2 layered, 3 flagged, 4 spire): change the style, whorl count / spacing / droop,
  crown width, crown base height, lean and flag direction, lobing of every whorl, card scatter.  Seed 4 is a
  shorter (0.65-0.75 x h), denser spire.

Materials: trunk `bark` tinted (0.6, 0.55, 0.5); whorl cores `moss` tinted dark (0.14, 0.2, 0.13); needle cards
  `foliage_pine` tinted dark (0.45, 0.55, 0.48).  (NEW:foliage_pine and NEW:bark exist in the library now.)
Animation: vertex sway.  Colour attribute `kz_sway` (POINT): R weight ((z/h)^1.5 on the trunk, + 0.25 out along
  each whorl), G phase per whorl, B 1 on foliage; vertex group `sway`.  kz_sway_default_indoor = 0.
Lighting: lightmap / vertex (far).
LOD (one layout per seed):
  LOD0 whorls 12-seg with a mid ring, ~900 needle cards on the rims and tops, trunk 8 sides with a root flare.
  LOD1 9-seg whorls, ~330 cards.  LOD2 6-seg whorls, a few cards.  LOD3 the whorls merged into 3 (spire) or kept
  per tier (layered, <= 4), 5-seg, trunk 3 sides (~70 tris).
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_momiji_small as T

ASSET = 'conifer_tall'
FEATURES = ['tall dark narrow conifer spire', 'stack of drooping needle whorls', 'bare lower trunk and pointed leader']
STYLES = ['spire', 'layered', 'flagged', 'spire']
LODS = {0: dict(n=12, mid=True, tr=10, ts=8, cards=True, csz=1.0),
        1: dict(n=9, mid=False, tr=5, ts=6, cards=True, csz=1.4),
        2: dict(n=6, mid=False, tr=2, ts=4, cards=True, csz=2.0),
        3: dict(n=5, mid=False, tr=1, ts=3, cards=False, csz=0)}


def layout(seed, h, crown, tiers, style, w):
    g = C.rng(seed, 'layout')
    off = Vector((g.uniform(-90, 90), g.uniform(-90, 90), g.uniform(-90, 90)))
    phi = g.uniform(0, 2 * math.pi)
    fd = Vector((math.cos(phi), math.sin(phi), 0))
    lean = {'spire': g.uniform(0.0, 0.015), 'layered': g.uniform(0.01, 0.04), 'flagged': g.uniform(0.04, 0.07)}[style]
    base = h * {'spire': g.uniform(0.15, 0.24), 'layered': g.uniform(0.28, 0.36), 'flagged': g.uniform(0.25, 0.32)}[style]
    if tiers is None:
        tiers = {'spire': g.randint(10, 13), 'layered': g.randint(6, 8), 'flagged': g.randint(8, 10)}[style]
    Rmax = min(w * 0.4, h * crown * {'spire': 0.15, 'layered': 0.17, 'flagged': 0.16}[style])
    wig = g.uniform(0.01, 0.025) * h
    ph = g.uniform(0, 6.28)

    def trunk_at(z):
        t = z / h
        return fd * lean * z + Vector((-fd.y, fd.x, 0)) * wig * math.sin(ph + 5 * t) * t + Vector((0, 0, z))
    trunk = [trunk_at(h * 0.985 * i / 20) for i in range(21)]
    whorls = []
    span = h * 0.97 - base
    for i in range(tiers):
        u = i / max(tiers - 1, 1)
        if style == 'layered':
            zt = base + span * (0.08 + 0.86 * u ** 0.9) + g.uniform(-0.02, 0.02) * span
        else:
            zt = base + span * (0.06 + 0.9 * u ** 1.05) + g.uniform(-0.01, 0.01) * span
        prof = (1 - u) ** {'spire': 0.85, 'layered': 0.7, 'flagged': 0.8}[style]
        R = 0.24 * Rmax + 0.76 * Rmax * prof * g.uniform(0.9, 1.08)
        dz = span / max(tiers, 1)
        droop = {'spire': g.uniform(1.25, 1.6), 'layered': g.uniform(0.6, 0.8), 'flagged': g.uniform(0.9, 1.2)}[style] * dz
        droop = min(droop, R * (1.1 if style != 'layered' else 0.5))
        c = trunk_at(zt)
        shift = Vector()
        if style == 'layered':          # open ridge-pine tiers: pads pushed off-axis, alternating sides
            a = phi + math.pi * (i % 2) + g.uniform(-0.7, 0.7)
            shift = Vector((math.cos(a), math.sin(a), 0)) * R * g.uniform(0.45, 0.7) * (1 - 0.6 * u)
            R *= 0.8
        if style == 'flagged':
            shift = fd * R * 0.6 * (0.4 + 0.6 * u)
        whorls.append(dict(c=c, shift=shift, R=R, droop=droop, ph=g.random(), lobes=g.choice([5, 6, 7]),
                           flag=(0.75 if style == 'flagged' else (0.12 if style == 'layered' else 0.0)), u=u))
    return dict(trunk=trunk, whorls=whorls, off=off, fd=fd, base=base, r0=0.0095 * h, style=style)


def whorl(G, W, mi, n, mid, off, fd, h, merged=None):
    """closed drooping needle whorl round the trunk: top cap, (mid ring), scalloped rim, inset underside"""
    bm = G.mb.bm
    c, R, dr = W['c'], W['R'], W['droop']
    if merged:
        R, dr = merged
    rim_c = c + W['shift']
    lob = W['lobes']; ph = W['ph']

    def rad(th, f):
        e = 1 + 0.13 * math.cos(lob * th + ph * 6) + 0.08 * T.nz((math.cos(th) * 2, math.sin(th) * 2, ph * 9), off)
        fl = 1 + W['flag'] * math.cos(th - math.atan2(fd.y, fd.x))
        return R * f * e * fl

    def P(th, f, z, k=1.0):
        ctr = c.lerp(rim_c, f)
        r = rad(th, f) * k
        return ctr + Vector((math.cos(th) * r, math.sin(th) * r, z))
    ths = [2 * math.pi * k / n + ph for k in range(n)]
    sw = lambda v: G.tag(v, min(1.0, (v.co.z / h) ** 1.5 + 0.25 * (v.co - c).to_2d().length / max(R, 0.1)), ph, 1.0)
    rows = []
    if mid:
        rows.append([bm.verts.new(P(th, 0.5, -dr * 0.32)) for th in ths])
    rim = [bm.verts.new(P(th, 1.0, -dr * (1 + 0.12 * T.nz((math.cos(th) * 3, math.sin(th) * 3, 1.7), off)))) for th in ths]
    und = [bm.verts.new(P(th, 0.62, -dr * 0.88)) for th in ths]
    rows += [rim, und]
    top = bm.verts.new(c + Vector((0, 0, dr * 0.08)))
    bot = bm.verts.new(c - Vector((0, 0, dr * 0.62)))
    for v in [top, bot] + [v for r_ in rows for v in r_]:
        sw(v)
    for k in range(n):
        f = bm.faces.new((top, rows[0][k], rows[0][(k + 1) % n])); f.material_index = mi
    for A, B in zip(rows[:-1], rows[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((A[k], B[k], B[k2], A[k2])); f.material_index = mi
    for k in range(n):
        f = bm.faces.new((bot, und[(k + 1) % n], und[k])); f.material_index = mi
    return rad, P


def build(lod, seed, h=None, crown=None, tiers=None, style=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    style = style or C.cycle(seed, STYLES)
    if h is None:
        h = p['h'] * (g.uniform(0.62, 0.72) if (seed - 1) % 4 == 3 else g.uniform(0.92, 1.05))
    h = max(6.0, min(15.0, h))
    crown = crown or g.uniform(0.85, 1.15)
    lay = layout(seed, h, crown, tiers, style, min(p['w'], p['d']))
    L = LODS[lod]
    mb = genlib.MeshBuilder()
    bark = mb.slot('bark', tint=(0.6, 0.55, 0.5))
    core = mb.slot('moss', tint=(0.14, 0.2, 0.13))
    fol = mb.slot('foliage_pine', tint=(0.45, 0.55, 0.48))
    G = T.TreeGeo(mb)
    bm = mb.bm
    off = lay['off']

    # trunk: bare below the crown, tapering into the leader
    nt = L['tr']
    ts_ = [i / nt for i in range(nt + 1)]
    if lod < 2:
        ts_ = sorted(set([0.0, 0.01, 0.03] + ts_))
    pts = [T.along(lay['trunk'], t) for t in ts_]
    r0 = lay['r0'] * (1.4 if lod == 3 else 1.0)
    rad = [r0 * (1 - 0.88 * t) + 0.01 for t in ts_]
    mod = (lambda i, th: 1.0 + 0.7 * math.exp(-ts_[i] / 0.015) * (0.5 + 0.5 * max(0.0, math.cos(4 * th)))) if lod < 2 else None
    rings = G.tube(pts, rad, bark, L['ts'], lambda t: 0.6 * t ** 1.5, mod=mod, cap1=True)
    for v in rings[0]:
        v.co.z = 0.0

    # whorls (LOD3: merged into 3 for the spire / flagged styles, all kept for <= 4 layered tiers)
    Ws = lay['whorls']
    samplers = []
    if lod == 3 and len(Ws) > 4:
        groups = [Ws[i * len(Ws) // 3:(i + 1) * len(Ws) // 3] for i in range(3)]
        for grp in groups:
            top_w, bot_w = grp[-1], grp[0]
            dr = (top_w['c'].z - bot_w['c'].z) + bot_w['droop']
            Wm = dict(top_w); Wm['shift'] = bot_w['shift']
            whorl(G, Wm, core, L['n'], False, off, lay['fd'], h, merged=(bot_w['R'] * 1.05, dr))
    else:
        for W in Ws:
            samplers.append((W, whorl(G, W, core, L['n'], L['mid'], off, lay['fd'], h)))
            if W['shift'].length > 0.3 and lod < 3:      # visible limb out to an off-axis pad
                a, b_ = W['c'] - Vector((0, 0, W['droop'] * 0.2)), W['c'] + W['shift'] * 0.8 - Vector((0, 0, W['droop'] * 0.45))
                G.tube([a, a.lerp(b_, 0.5) + Vector((0, 0, 0.12)), b_], [lay['r0'] * 0.55, lay['r0'] * 0.4, lay['r0'] * 0.25], bark,
                       C.lod_pick(lod, 5, 4, 3), lambda t: 0.5 + 0.3 * t, W['ph'])
    # leader tip
    tip = lay['trunk'][-1]
    G.tube([tip - Vector((0, 0, 0.6)), tip + Vector((0, 0, 0.25))], [0.06, 0.005], core, 4 if lod < 2 else 3,
           lambda t: 1.0, 0.0)

    # needle cards: fringe hanging off the rims + a few on the tops, budget-driven
    if L['cards'] and samplers:
        budget = genlib.budget_of(ASSET) or [3000, 1200, 360, 80]
        used = sum(len(f.verts) - 2 for f in bm.faces)
        n_total = max(0, int((budget[lod] * 0.97 - used) / 2))
        areas = [W['R'] ** 2 for W, _ in samplers]
        for wi, (W, (radf, P)) in enumerate(samplers):
            cr = genlib.rng(seed, f'cards{wi}')
            n_c = int(n_total * areas[wi] / sum(areas))
            for j in range(n_c):
                th = cr.uniform(0, 2 * math.pi)
                fringe = cr.random() < 0.7
                f = cr.uniform(0.85, 1.02) if fringe else cr.uniform(0.35, 0.8)
                z = -W['droop'] * (cr.uniform(0.75, 1.05) if fringe else 0.32 * f / 0.5)
                q = P(th, f, z)
                outward = Vector((math.cos(th), math.sin(th), 0))
                n = (outward * (1.0 if fringe else 0.6) + Vector((0, 0, 0.35 if fringe else 1.0))).normalized()
                down = Vector((0, 0, -1))
                tg = (down - n * down.dot(n)).normalized()
                rot = cr.uniform(-0.6, 0.6)
                tg = (tg * math.cos(rot) + n.cross(tg) * math.sin(rot)).normalized()
                up = -tg if fringe else (n.cross(outward)).normalized().cross(n)
                right = up.cross(n).normalized()
                wc, hc = cr.uniform(0.45, 0.7) * L['csz'], cr.uniform(0.35, 0.5) * L['csz']
                base = q - up * hc * (0.7 if fringe else 0.5) + n * 0.02
                G.card(base, right, up, wc, hc, fol, min(1.0, (q.z / h) ** 1.5 + 0.3), W['ph'], cr.choice([0.0, 0.17, 0.33]))

    for v in bm.verts:
        if v.co.z < 0:
            v.co.z = 0.0
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
    sh = Vector((-(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, 0))
    bmesh.ops.translate(bm, vec=sh, verts=bm.verts)
    ext = max(max(xs) - min(xs), max(ys) - min(ys))
    if ext > p['w'] * 0.99:                     # lobes / flag / fringe cards past the proxy: pull the crown in
        k = p['w'] * 0.99 / ext
        for v in bm.verts:
            v.co.x *= k; v.co.y *= k
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=60)
    T.post(o, (fol, core))
    C.set_json_props(o, kz_params=dict(h=round(h, 2), crown=round(crown, 3), tiers=len(Ws), style=style),
                     kz_trunk_base=[round(sh.x, 3), round(sh.y, 3)])
    o['kz_sway_default_indoor'] = 0
    return o
