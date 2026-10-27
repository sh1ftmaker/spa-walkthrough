"""Hanging paper lantern (chochin) generator.

Identifying features kept at every LOD: ribbed paper body between dark lacquer caps, hung on a cord,
with its print (Kazan-yu volcano-and-steam logo, a crest (mon) or ラーメン lettering).

Construction
  * Paper body: a lathe whose profile is pinched at each bamboo rib and bulges between ribs (the rib
    rings line up with the rib lines painted in the `lantern_paper` texture, see RIB_V). Profile
    families: round (ovoid), tall_cylinder (flat sides, rounded shoulders), giant (barrel).
  * Caps: lathe hoops with a chamfered lip, bronze rim rings (face-assigned, no extra geometry), a
    domed lid with a bronze hanging ring + stem on top and a lacquer finial knob under the bottom cap.
  * Cord: twisted rope (helical 6-sided sweep) to the hang point, with a knot at the ring.
  * Print: real geometry decals projected onto the faceted paper surface 2.5 mm proud of it
    (lacquer_dark ink, matte), so the logo survives every LOD: volcano + three steam wisps (logo),
    the same mark inside a mon ring on a back-lit disc (crest), vertical ラーメン (ramen, Noto Sans CJK
    Black glyphs). LOD0 round/tall logo lanterns also carry 火山湯 under the mark.

Parameters (build(lod, seed, **params))
  variant   round_logo | tall_cylinder | red_crest | giant_ramen | chain | cluster
            (seed picks one of the first three, which fit the 0.45 x 0.45 x 0.7 m proxy; the last
            three are explicit-only presets that are larger than the proxy by design)
  r         body radius 0.15-0.45 m        h        lantern height (caps + paper) 0.3-1.2 m
  shape     round | tall_cylinder | giant  colour   cream | red
  print     logo | crest | ramen | none    cord     cord length from the top ring to the hang point (m)
  cluster_n 1-12 lanterns on a porch cluster rig (variant cluster); chain_n 2-6 (variant chain)

Pivot: base centre (bottom of the lowest finial) at z = 0; the hang point is the top of the cord.

Animation (for the web runtime; nothing is animated here)
  * Rigid pendulum sway: every lantern (body, caps, print, its own cord) is in vertex group
    `sway_<i>`; obj['kz_sway'] lists, per group, its pivot (cord top, object space), a suggested
    amplitude (deg) and period (s). Cluster/chain rig parts that do not move are in group `static`.
  * Vertex colour attribute `sway` (POINT, float colour; R = 0 at the hang point -> 1 at the bottom of
    the lowest lantern, G = lantern index / 16) for a cheap vertex-shader sway instead.
  * Flame flicker: obj['kz_flicker'] = material slot indices of the emissive paper (and crest disc).
Light: obj['kz_lights'] = [{pos (body centre), color (linear RGB of 2200 K, red-filtered for red paper),
watts}] - one point light per lantern; the paper itself is the emissive bake source.
"""
import json
import math

import bmesh
import bpy
from mathutils import Vector, Matrix

import genlib
import kzgeo_chochin as K

ASSET = 'chochin'
FEATURES = ['ribbed paper body', 'dark caps top and bottom', 'hanging cord', 'logo / crest / ラーメン print']

# rib lines painted in lantern_paper_base (v = 0 bottom .. 1 top), measured from the texture
RIB_V = [0.047, 0.154, 0.313, 0.42, 0.512, 0.618, 0.724, 0.831, 0.937]
RIB_TILE = (0.425, 0.507)           # one painted rib interval (lines trimmed to a hairline), re-used per modelled rib
FONT_JP = '/usr/share/fonts/noto-cjk/NotoSansCJK-Black.ttc'
FONT_KANJI = '/usr/share/fonts/noto-cjk/NotoSerifCJK-SemiBold.ttc'
FONT_LATIN = '/usr/share/fonts/noto/NotoSerif-Medium.ttf'
K2200 = (1.0, 0.42, 0.11)          # linear RGB of ~2200 K

PRESETS = {
    'round_logo':    dict(shape='round', colour='cream', print='logo', r=(0.195, 0.21), h=(0.55, 0.58)),
    'tall_cylinder': dict(shape='tall_cylinder', colour='cream', print='logo', r=(0.135, 0.15), h=(0.54, 0.58)),
    'red_crest':     dict(shape='round', colour='red', print='crest', r=(0.19, 0.2), h=(0.53, 0.56)),
    'giant_ramen':   dict(shape='giant', colour='red', print='ramen', r=(0.30, 0.32), h=(1.15, 1.2)),
    'chain':         dict(shape='round', colour='cream', print='logo', r=(0.15, 0.165), h=(0.32, 0.36)),
    'cluster':       dict(shape='round', colour='cream', print='none', r=(0.15, 0.20), h=(0.3, 0.42)),
}
SEED_VARIANTS = ['round_logo', 'tall_cylinder', 'red_crest']
CAP_RATIO = {'round': 0.48, 'tall_cylinder': 0.84, 'giant': 0.78}     # cap radius / body radius (sheet)

# per-LOD resolution
LODS = {
    0: dict(S=24, ribs=True, cap='full', cord=6, ring=(10, 4), text=True, latin=True, steam=True, rivets=True),
    1: dict(S=10, ribs=False, cap='mid', cord=4, ring=None, text=False, latin=False, steam=True, rivets=False),
    2: dict(S=8, ribs=False, cap='low', cord=2, ring=None, text=False, latin=False, steam=False, rivets=False),
    3: dict(S=6, ribs=False, cap='min', cord=1, ring=None, text=False, latin=False, steam=False, rivets=False),
}


# ------------------------------------------------------------------ profile
def paper_profile(shape, r, re, n, rng):
    """t in 0..1 -> radius; returns callable. re = end (cap) radius."""
    if shape == 'round':
        p = rng.uniform(0.5, 0.68)
        lean = rng.uniform(-0.05, 0.05)          # fuller low or high

        def f(t):
            tt = min(1.0, max(0.0, t + lean * math.sin(math.pi * t)))
            return re + (r - re) * math.sin(math.pi * tt) ** p
    elif shape == 'tall_cylinder':
        sh = rng.uniform(0.10, 0.16)

        def f(t):
            s = min(1.0, math.sin(math.pi * t) / math.sin(math.pi * sh))
            return re + (r - re) * s ** 0.5
    else:   # giant barrel
        sh = rng.uniform(0.07, 0.10)
        barrel = rng.uniform(0.04, 0.08)

        def f(t):
            s = min(1.0, math.sin(math.pi * t) / math.sin(math.pi * sh))
            return (re + (r * (1 - barrel) - re) * s ** 0.45) + r * barrel * math.sin(math.pi * t) ** 2
    return f


def ring_plan(lod, Hp):
    """[(t, pinched)] along the paper (t 0..1) and per band its (v0, v1) on the lantern_paper texture.
    LOD0: 22-26 modelled ribs (pinched rings) with a bulge ring between each pair; every rib interval maps onto
    one painted rib interval of the texture so painted lines and modelled pinches coincide.
    LOD1-3: smooth profile, texture v 0..1 (its 9 painted ribs stand in for the ribs)."""
    if LODS[lod]['ribs']:
        nr = max(14, min(20, int(round(Hp / 0.022))))     # sheet-mod-lights #2: ~18 ribs on the 0.45 m lantern
        pts = [(k / (2 * nr), k % 2 == 0 and 0 < k < 2 * nr) for k in range(2 * nr + 1)]
        bandv = []
        for b in range(2 * nr):
            j = b // 2
            v0, v1 = (0.0, RIB_V[0]) if j == 0 else ((RIB_V[-1], 1.0) if j == nr - 1 else RIB_TILE)
            vm = (v0 + v1) / 2
            bandv.append((v0, vm) if b % 2 == 0 else (vm, v1))
        return pts, bandv
    ts = {1: [0.0, 0.14, 0.34, 0.66, 0.86, 1.0], 2: [0.0, 0.3, 0.7, 1.0], 3: [0.0, 0.5, 1.0]}[lod]
    return [(t, False) for t in ts], [(ts[i], ts[i + 1]) for i in range(len(ts) - 1)]


# ------------------------------------------------------------------ lathe
def lathe(bm, prof, S, mis, phase, uvs=None):
    """prof: [(r, z)] bottom->top; r == 0 makes a pole (fan). mis[i] = material of band i.
    Returns (rings, faces_by_band). Vertex columns at angle (j + 0.5) * 2pi/S + phase from +Y (clockwise
    seen from above, i.e. x = r sin(a), y = r cos(a))."""
    rings = []
    for (r, z) in prof:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            ring = []
            for j in range(S):
                a = (j + 0.5) * 2 * math.pi / S + phase
                ring.append(bm.verts.new((r * math.sin(a), r * math.cos(a), z)))
            rings.append(ring)
    bands = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        fs = []
        for j in range(S):
            k = (j + 1) % S
            if len(A) == 1 and len(B) == 1:
                continue
            if len(A) == 1:
                f = bm.faces.new((A[0], B[k], B[j]))
            elif len(B) == 1:
                f = bm.faces.new((A[j], A[k], B[0]))
            else:
                f = bm.faces.new((A[j], A[k], B[k], B[j]))
            f.material_index = mis[i]
            fs.append(f)
        bands.append(fs)
    return rings, bands


def facet_point(prof, S, phase, theta, z, off):
    """point on the faceted lathe surface (prof = paper rings [(r,z)]) at angle theta, height z, pushed out
    by `off` along the surface normal."""
    for i in range(len(prof) - 1):
        if prof[i][1] <= z <= prof[i + 1][1] or i == len(prof) - 2:
            r0, z0 = prof[i]; r1, z1 = prof[i + 1]
            break
    f = (z - z0) / (z1 - z0) if z1 > z0 else 0.0
    rf = r0 + f * (r1 - r0)
    step = 2 * math.pi / S
    # facet centre angle nearest theta (vertex columns at (j+0.5)*step + phase -> facet centres at j*step + phase)
    j = round((theta - phase) / step)
    tc = j * step + phase
    rr = rf * math.cos(step / 2) / math.cos(theta - tc)
    slope = (r1 - r0) / (z1 - z0) if z1 > z0 else 0.0
    nh = 1.0 / math.sqrt(1 + slope * slope)
    nz = -slope * nh
    d = Vector((math.sin(theta), math.cos(theta), 0))
    nrm = Vector((math.sin(tc), math.cos(tc), 0)) * nh + Vector((0, 0, nz))
    return d * rr + Vector((0, 0, z)) + nrm * off


# ------------------------------------------------------------------ 2D print shapes (x right, y up, metres)
def volcano_poly(w, hgt, crater=True, n=7):
    """concave-sided volcano with a crater notch; w base width, hgt peak height"""
    L = []
    top = 0.17 * w
    for i in range(n + 1):
        t = i / n
        x = -w / 2 + t * (w / 2 - top / 2)
        y = hgt * (t ** 1.7)
        L.append((x, y))
    if crater:
        L += [(-top * 0.22, hgt * 0.93), (0.0, hgt * 0.97), (top * 0.22, hgt * 0.93)]
    for i in range(n, -1, -1):
        t = i / n
        x = w / 2 - t * (w / 2 - top / 2)
        L.append((x, hgt * (t ** 1.7)))
    return L


def steam_strip(x0, y0, length, amp, width, n=6, phase=0.0):
    """S-curve tapered strip: returns list of quads (4 points each)"""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + amp * math.sin(2 * math.pi * 1.25 * t + phase)          # two inflections along the wisp
        y = y0 + t * length
        wd = width * (0.55 + 0.45 * min(1.0, t * 5)) * (1.0 if t < 0.7 else max(0.15, 1 - (t - 0.7) / 0.3))
        pts.append((x, y, wd))
    quads = []
    for i in range(n):
        (xa, ya, wa), (xb, yb, wb) = pts[i], pts[i + 1]
        quads.append([(xa - wa / 2, ya), (xa + wa / 2, ya), (xb + wb / 2, yb), (xb - wb / 2, yb)])
    return quads


def annulus(r0, r1, n):
    quads = []
    for i in range(n):
        a, b = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        quads.append([(r1 * math.cos(a), r1 * math.sin(a)), (r1 * math.cos(b), r1 * math.sin(b)),
                      (r0 * math.cos(b), r0 * math.sin(b)), (r0 * math.cos(a), r0 * math.sin(a))])
    return quads


def glyph_polys(text, font, res=1, rotate=False):
    """triangles (2D) of a glyph string, height 1, centred (robust fill: overlapping CJK strokes stay solid)"""
    tris, w = K.glyph_tris(text, font, res)
    if rotate:      # rotate 90 deg (vertical long-vowel mark) and renormalise to height 1
        tris = [[(-y, x) for x, y in t] for t in tris]
        ys = [p[1] for t in tris for p in t]
        s_ = 1.0 / max(1e-6, max(ys) - min(ys))
        tris = [[(x * s_, y * s_) for x, y in t] for t in tris]
    xs = [p[0] for t in tris for p in t] or [0]
    return tris, max(xs) - min(xs), 1.0


class Decal:
    """2D polygons in (s, z) (arc length, height) -> projected onto the lathe facets."""

    def __init__(self):
        self.polys = []      # (points, mi)

    def add(self, pts, mi):
        self.polys.append((pts, mi))

    def emit(self, bm, prof, S, phase, off, max_edge=None, theta0=0.0, cut_rings=True):
        """Cut the decal along every facet ridge (vertical) and ring (horizontal) of the faceted lathe so each
        piece lies flat on one planar facet, then place it `off` metres proud of the paper."""
        if not self.polys:
            return []
        tmp = bmesh.new()
        for pts, mi in self.polys:
            vs = [tmp.verts.new((x, y, 0)) for x, y in pts]
            try:
                f = tmp.faces.new(vs)
            except ValueError:
                continue
            f.material_index = mi
        bmesh.ops.remove_doubles(tmp, verts=tmp.verts, dist=1e-5)
        xs = [v.co.x for v in tmp.verts]; ys = [v.co.y for v in tmp.verts]
        zc = (min(ys) + max(ys)) / 2
        r_ref = _r_at(prof, zc)
        step = 2 * math.pi / S
        cuts = []
        for j in range(-S, 2 * S):
            th = (j + 0.5) * step + phase
            sx = (theta0 - th) * r_ref
            if min(xs) < sx < max(xs):
                cuts.append(((sx, 0, 0), (1, 0, 0)))
        for (rr, z) in (prof if cut_rings else []):
            if min(ys) < z < max(ys):
                cuts.append(((0, z, 0), (0, 1, 0)))
        for co, no in cuts:
            geom = list(tmp.verts) + list(tmp.edges) + list(tmp.faces)
            bmesh.ops.bisect_plane(tmp, geom=geom, dist=1e-6, plane_co=co, plane_no=no)
        bmesh.ops.triangulate(tmp, faces=tmp.faces, quad_method='BEAUTY', ngon_method='EAR_CLIP')
        new = {}
        out = []
        for v in tmp.verts:
            sv, z = v.co.x, v.co.y
            zz = min(max(z, prof[0][1] + 1e-4), prof[-1][1] - 1e-4)
            new[v] = bm.verts.new(facet_point(prof, S, phase, theta0 - sv / r_ref, zz, off))
        for f in tmp.faces:
            try:
                nf = bm.faces.new([new[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = f.material_index
            out.append(nf)
        tmp.free()
        return out


def _r_at(prof, z):
    for i in range(len(prof) - 1):
        if prof[i][1] <= z <= prof[i + 1][1]:
            f = (z - prof[i][1]) / max(1e-9, prof[i + 1][1] - prof[i][1])
            return prof[i][0] + f * (prof[i + 1][0] - prof[i][0])
    return prof[-1][0]


# ------------------------------------------------------------------ one lantern
def lantern(mb, bm, lod, rng, r, h, shape, print_, mats, origin_z=0.0, cord=0.0, x=0.0, y=0.0, yaw=0.0):
    """One lantern: bottom finial at origin_z, hang point (top of the cord) at origin_z + h + 0.075 + cord."""
    C = LODS[lod]
    S = C['S']
    phase = 0.0
    paper, ink, rim, cap, rope = mats['paper'], mats['ink'], mats['rim'], mats['cap'], mats['rope']
    start = len(bm.verts)
    k_ = max(0.75, min(1.6, r / 0.225))
    cap_r = r * CAP_RATIO[shape] * rng.uniform(0.97, 1.03)
    re = cap_r * 0.96                            # paper opening tucked under the cap
    cap_h = 0.06 * k_                            # sheet: black caps ~0.06 m with two bronze rims
    kh = 0.018 * k_                              # bottom finial
    stem = 0.015 * k_
    ring_R, ring_t = 0.0255 * k_, 0.0045 * k_    # 60 mm OD ring
    z_cb = origin_z + kh
    z_p0 = z_cb + cap_h
    z_ct = origin_z + h - 0.015 * k_             # lid dome above
    z_p1 = z_ct - cap_h
    Hp = z_p1 - z_p0
    hang_z = origin_z + h + stem + 2 * ring_R + cord
    f = paper_profile(shape, r, re, 0, rng)
    plan, bandv = ring_plan(lod, Hp)
    pinch = 0.0015 * k_
    prof_paper = []
    for t, pinched in plan:
        rr = f(t) - (pinch if pinched else 0.0)
        if t in (0.0, 1.0):
            rr = re if lod < 2 else cap_r
        prof_paper.append((rr, z_p0 + t * Hp))
    rp, rh = 0.003 * k_, 0.0045 * k_             # rim bead: proud 3 mm, 9 mm tall
    if C['cap'] == 'full':
        bot = [(0.0, origin_z), (0.011 * k_, origin_z + 0.004 * k_), (0.015 * k_, origin_z + kh * 0.7), (0.02 * k_, z_cb),
               (cap_r * 0.92, z_cb), (cap_r, z_cb + 0.0015), (cap_r + rp, z_cb + rh), (cap_r, z_cb + 2 * rh),
               (cap_r, z_cb + cap_h - 2 * rh), (cap_r + rp, z_cb + cap_h - rh), (cap_r, z_cb + cap_h - 0.0015), (re, z_p0)]
        bmis = [rim, rim, rim, cap, rim, rim, rim, cap, rim, rim, cap]
        top = [(re, z_p1), (cap_r, z_p1 + 0.0015), (cap_r + rp, z_p1 + rh), (cap_r, z_p1 + 2 * rh), (cap_r, z_ct - 2 * rh),
               (cap_r + rp, z_ct - rh), (cap_r, z_ct - 0.0015), (cap_r * 0.92, z_ct), (cap_r * 0.5, z_ct + 0.011 * k_),
               (0.02 * k_, z_ct + 0.015 * k_), (0.011 * k_, z_ct + 0.015 * k_ + stem), (0.0, z_ct + 0.015 * k_ + stem)]
        tmis = [cap, rim, rim, cap, rim, rim, rim, cap, cap, rim, rim]
    elif C['cap'] == 'mid':
        bot = [(0.0, origin_z), (cap_r, z_cb), (cap_r, z_cb + 2 * rh), (cap_r, z_cb + cap_h - 2 * rh), (cap_r, z_cb + cap_h), (re, z_p0)]
        bmis = [cap, rim, cap, rim, cap]
        top = [(re, z_p1), (cap_r, z_p1), (cap_r, z_p1 + 2 * rh), (cap_r, z_ct - 2 * rh), (cap_r, z_ct), (0.0, z_ct + 0.015 * k_ + stem)]
        tmis = [cap, rim, cap, rim, cap]
    else:
        bot = [(0.0, origin_z), (cap_r, z_cb), (cap_r, z_p0)]
        bmis = [cap, cap]
        top = [(cap_r, z_p1), (cap_r, z_ct), (0.0, z_ct + 0.015 * k_)]
        tmis = [cap, cap]
    if lod == 3:
        # capped barrel: 6-sided body in 3 segments + flat 6-gon cap faces (no bicone)
        zt3 = z_ct + 0.01
        prof = [(cap_r, origin_z), (r * 0.97, z_p0 + Hp * 0.3), (r * 0.97, z_p0 + Hp * 0.7), (cap_r, zt3)]
        rings, _ = lathe(bm, prof, S, [paper, paper, paper], phase)
        for rg, up in ((rings[0], False), (rings[-1], True)):
            fc = bm.faces.new(rg if up else rg[::-1]); fc.material_index = cap
        prof_paper = prof
        bandv = [(0.0, 0.3), (0.3, 0.7), (0.7, 1.0)]
    else:
        full = bot + prof_paper[1:-1] + top
        mis = bmis + [paper] * (len(prof_paper) - 1) + tmis
        rings, _ = lathe(bm, full, S, mis, phase)
        i0 = len(bot) - 1
        if C['ribs']:
            for rg in rings[i0 + 1:i0 + len(prof_paper) - 1]:
                for j in range(0, S, 2):
                    v = rg[j]
                    v.co.x *= 1 - 0.0012 / max(0.05, r); v.co.y *= 1 - 0.0012 / max(0.05, r)
        prof_paper = [(full[i0][0], full[i0][1])] + prof_paper[1:-1] + [(top[0][0], top[0][1])]
    # rivets: four bosses on each cap band (45 deg off the print)
    if C['rivets']:
        for zc in (z_cb + cap_h / 2, z_p1 + cap_h / 2):
            for q in range(6):
                a = math.pi / 6 + q * math.pi / 3
                res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=5, radius1=0.0045 * k_, radius2=0.002 * k_, depth=0.004 * k_)
                M = Matrix.Translation((math.sin(a) * (cap_r + 0.0015), math.cos(a) * (cap_r + 0.0015), zc)) @ \
                    Vector((math.sin(a), math.cos(a), 0)).to_track_quat('Z', 'Y').to_matrix().to_4x4()
                bmesh.ops.transform(bm, matrix=M, verts=res['verts'])
                for fc in {fc for v in res['verts'] for fc in v.link_faces}:
                    fc.material_index = rim
    # hanging ring + twisted rope
    z_top = z_ct + 0.015 * k_ + stem
    if C['ring']:
        segs, rs = C['ring']
        _torus(bm, (0, 0, z_top + ring_R), ring_R - ring_t, ring_t, segs, rs, rim)
    z_cord0 = z_top + 2 * ring_R - ring_t
    cordl = hang_z - z_cord0
    if cordl > 0:
        _rope(bm, z_cord0, hang_z, 0.005 * k_, C['cord'], rope, twist=lod == 0, rng=rng)
    if print_ != 'none':
        # the print lies on the envelope through the bulge rings (1 mm proud of every crest, bridging the rib
        # grooves like a pasted print); only facet-ridge cuts are needed, so the lettering stays cheap
        env = prof_paper if lod == 3 else \
            [prof_paper[0]] + [prof_paper[i] for i, (t, pin) in enumerate(plan) if 0 < i < len(plan) - 1 and not pin] + [prof_paper[-1]]
        _print(bm, lod, print_, env, S, phase, r, z_p0, z_p1, mats, rng, shape)
        if lod < 3:
            _print(bm, lod, print_, env, S, phase, r, z_p0, z_p1, mats, rng, shape, back=True)
    bm.verts.ensure_lookup_table()
    vs = [bm.verts[i] for i in range(start, len(bm.verts))]
    M = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(yaw, 4, 'Z')
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    return dict(vidx=(start, len(bm.verts)), prof=prof_paper, bandv=bandv, z_p0=z_p0, z_p1=z_p1, phase=phase + yaw,
                S=S, centre=(x, y, (z_p0 + z_p1) / 2), top=hang_z, bottom=origin_z, xy=(x, y), yaw=yaw)


def _torus(bm, c, R, rr, segs, rsegs, mi):
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ring = []
        for k in range(rsegs):
            b = 2 * math.pi * k / rsegs
            rad = R + rr * math.cos(b)
            # ring stands in the XZ plane (faces front)
            ring.append(bm.verts.new((c[0] + rad * math.cos(a), c[1] + rr * math.sin(b), c[2] + rad * math.sin(a))))
        rings.append(ring)
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % segs]
        for k in range(rsegs):
            kk = (k + 1) % rsegs
            f = bm.faces.new((A[k], B[k], B[kk], A[kk])); f.material_index = mi


def _rope(bm, z0, z1, rad, sides, mi, twist=True, rng=None, knot=False):
    L = z1 - z0
    if sides <= 2:      # LOD2: two crossed cards, LOD3: one card
        for ax in (((1, 0), (0, 1)) if sides == 2 else ((1, 0),)):
            vs = [bm.verts.new((ax[0] * s_ * rad, ax[1] * s_ * rad, z)) for s_, z in ((-1, z0), (1, z0), (1, z1), (-1, z1))]
            f = bm.faces.new(vs); f.material_index = mi
        return
    nseg = max(1, int(round(L / 0.018))) if twist else 1
    rings = []
    for i in range(nseg + 1):
        z = z0 + L * i / nseg
        tw = i * (2 * math.pi / sides) if twist else 0.0
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + tw
            rr = rad * (1.0 if k % 2 == 0 or not twist else 0.72)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        rings.append(ring)
    for i in range(nseg):
        A, B = rings[i], rings[i + 1]
        for k in range(sides):
            kk = (k + 1) % sides
            f = bm.faces.new((A[k], A[kk], B[kk], B[k])); f.material_index = mi
    if knot:
        # knot (fat rope ball) just above the ring
        r = bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=rad * 2.2)
        bmesh.ops.scale(bm, vec=(1, 1, 1.3), verts=r['verts'])
        bmesh.ops.translate(bm, vec=(0, 0, z0 + rad * 2.0), verts=r['verts'])
        for f in {f for v in r['verts'] for f in v.link_faces}:
            f.material_index = mi


def _mark(d, lod, cx, y0, mw, mi, facet_w=None):
    """Kazan-yu mark: concave volcano with crater + three steam wisps; base centre (cx, y0), base width mw.
    Returns the top of the steam. At LOD2/3 the volcano is one trapezoid inside the front facet."""
    mh = mw * 0.34
    if lod >= 2:
        mw = min(mw, facet_w * 0.85) if facet_w else mw
        mh = mw * 0.42
        d.add([(cx - mw / 2, y0), (cx + mw / 2, y0), (cx + mw * 0.1, y0 + mh), (cx - mw * 0.1, y0 + mh)], mi)
        return y0 + mh
    d.add([(cx + x, y + y0) for x, y in volcano_poly(mw, mh, crater=True, n=6 if lod == 0 else 3)], mi)
    top = y0 + mh
    if LODS[lod]['steam']:
        sl = mw * 0.42
        for dx, ln, ph in ((-0.13, 0.78, 0.4), (0.0, 1.0, 1.3), (0.13, 0.78, 0.4)):
            for q in steam_strip(cx + dx * mw, y0 + mh * 1.12, ln * sl, 0.03 * mw, max(0.012, 0.06 * mw),
                                 n=10 if lod == 0 else 3, phase=0.0):
                d.add(q, mi)
        top = y0 + mh * 1.12 + sl
    return top


def _print(bm, lod, kind, prof, S, phase, r, z_p0, z_p1, mats, rng, shape, back=False):
    """front print centred on +Y (back=True: the reverse side, one detail step lower, mark only).
    Stack from the sheet (sheet-mod-lights #2): steam / volcano / K A Z A N - Y U / 火山湯."""
    ink, disc = mats['ink'], mats['disc']
    dl = min(3, lod + 1) if back else lod
    theta0 = math.pi if back else 0.0
    H = z_p1 - z_p0
    zc = z_p0 + H * 0.5
    off = {0: 0.001, 1: 0.002, 2: 0.004, 3: 0.006}[lod]
    r_c = _r_at(prof, zc)
    facet_w = 2 * r_c * math.sin(math.pi / S)
    mark, flat, text = Decal(), Decal(), Decal()
    tall = shape == 'tall_cylinder'
    if kind == 'logo':
        u = r * (1.25 if tall else 1.0)                   # layout unit
        mw = 0.78 * u
        latin = LODS[dl]['latin'] and not back
        kanji = LODS[dl]['text'] and not back and not tall
        cap = 0.1 * u * (1.3 if tall else 1.0)            # ~22 mm on a 0.45 m lantern, 30 % larger on the tall one
        kh = 0.17 * u
        stack = 0.62 * u + (0.08 * u + cap if latin else 0) + (0.07 * u + kh if kanji else 0)
        if dl >= 2:
            stack = 0.2 * u
        ytop = zc + stack / 2
        y = ytop - 0.62 * u
        if dl >= 2:
            y = zc - 0.05 * u if lod < 3 else z_p0 + H * 0.36
        _mark(mark, dl, 0.0, y, mw, ink, facet_w)
        if latin:
            y -= 0.08 * u + cap
            tris, w = K.tracked_line('KAZAN-YU', FONT_LATIN, cap, tracking=0.42, res=1)
            for t in tris:
                text.add([(px, py + y) for px, py in t], ink)
        if kanji:
            y -= 0.07 * u + kh
            tris, gw, _ = glyph_polys('火山湯', FONT_KANJI, res=2)
            for t in tris:
                text.add([(px * kh, py * kh + y + kh / 2) for px, py in t], ink)
    elif kind == 'crest':
        cr = min(r * 0.6, H * 0.34)                        # mon: back-lit cream disc, ink ring, mark inside
        seg = {0: 32, 1: 10, 2: 6, 3: 6}[dl]
        if dl < 2 and not back:
            flat.add([(cr * 0.97 * math.cos(2 * math.pi * k / seg), zc + cr * 0.97 * math.sin(2 * math.pi * k / seg)) for k in range(seg)], disc)
        if dl == 0:
            for q in annulus(cr * 0.86, cr, seg):
                mark.add([(x, y + zc) for x, y in q], ink)
        _mark(mark, dl, 0.0, (zc - cr * 0.5) if lod < 3 else z_p0 + H * 0.36, cr * 1.2, ink, facet_w)
    elif kind == 'ramen':
        chars = ['ラ', 'ー', 'メ', 'ン']
        gh = H * 0.86 / 4
        th = min(gh * 0.9, r * 1.2)
        for k, ch in enumerate(chars):
            tris, gw, _ = glyph_polys(ch, FONT_JP, res=1 if dl > 0 else 2, rotate=(ch == 'ー'))
            cy = z_p1 - H * 0.07 - gh * (k + 0.5)
            for t in tris:
                mark.add([(x * th, y * th + cy) for x, y in t], ink)
            if dl == 3 and k == 0:
                break
    # big shapes are cut on every (envelope) ring so they stay on the surface; small lettering only on ridges
    out = flat.emit(bm, prof, S, phase, off * 0.5, theta0=theta0)
    out += mark.emit(bm, prof, S, phase, off, theta0=theta0)
    out += text.emit(bm, prof, S, phase, off + 0.0005, theta0=theta0)
    return out


def C_steam(lod):
    return LODS[lod]['steam']


# ------------------------------------------------------------------ build
def build(lod, seed, variant=None, r=None, h=None, shape=None, colour=None, print=None, cord=None,
          cluster_n=None, chain_n=None, glow=None, **_):
    rng = genlib.rng(seed, ASSET)
    variant = variant or SEED_VARIANTS[(seed - 1) % len(SEED_VARIANTS)]
    P = PRESETS[variant]
    p = genlib.proxy(ASSET)
    shape = shape or P['shape']
    colour = colour or P['colour']
    print_ = print or P['print']
    r = r or rng.uniform(*P['r'])
    h = h or rng.uniform(*P['h'])
    mb = genlib.MeshBuilder()
    bm = mb.bm
    red = colour == 'red'
    # AgX desaturates bright emission: moderate glow keeps cream warm-amber and red red (tuned in canonical renders)
    tint = (1.0, rng.uniform(0.04, 0.06), rng.uniform(0.015, 0.025)) if red else (1.0, rng.uniform(0.76, 0.84), rng.uniform(0.48, 0.58))
    mats = dict(
        paper=(mb.slot('lantern_paper', tint=tuple(round(t, 3) for t in tint), emissive_level=round(glow if glow is not None else rng.uniform(0.45, 0.55), 2))
               if red else mb.slot('lantern_paper', emissive_level=round(glow if glow is not None else rng.uniform(0.9, 1.05), 2))),
        ink=mb.slot('lacquer_black', roughness_offset=0.5),
        rim=mb.slot('gold_leaf', roughness_offset=0.2),             # brass rims, ring, studs
        cap=mb.slot('lacquer_black', roughness_offset=0.35),        # matte black lacquer caps
        rope=mb.slot('rope'),
    )
    if print_ == 'crest':
        mats['disc'] = mb.slot('lantern_paper', emissive_level=0.9)
    else:
        mats['disc'] = mats['paper']
    lanterns = []
    if variant == 'cluster':
        mats['timber'] = mb.slot('hinoki', variant='stained', wear=0.3)
        n = max(1, min(12, int(cluster_n or rng.randint(5, 9))))
        lanterns, rig_top = _cluster(mb, bm, lod, rng, n, shape, print_, mats, r, h)
    elif variant == 'chain':
        n = max(2, min(6, int(chain_n or rng.randint(3, 4))))
        z = 0.0
        gap = cord if cord is not None else 0.12
        for i in range(n):
            info = lantern(mb, bm, lod, genlib.rng(seed, f'chain{i}'), r, h, shape, print_ if i == n - 1 or lod == 0 else 'none',
                           mats, origin_z=z, cord=gap if i < n - 1 else 0.35)
            lanterns.append(info)
            z = info['top'] + 0.004
        rig_top = lanterns[-1]['top']
    else:
        total = p['h']
        cord_len = cord if cord is not None else max(0.06, total - h - 0.066 * max(0.75, min(1.6, r / 0.225)))
        if variant == 'giant_ramen':
            cord_len = cord if cord is not None else 0.12
        info = lantern(mb, bm, lod, rng, r, h, shape, print_, mats, origin_z=0.0, cord=cord_len)
        lanterns.append(info)
        rig_top = info['top']
    # pivot: base centre at z = 0 (chains / clusters can float above 0 while building)
    bm.verts.ensure_lookup_table()
    zmin = min(v.co.z for v in bm.verts)
    if abs(zmin) > 1e-6:
        bmesh.ops.translate(bm, vec=(0, 0, -zmin), verts=list(bm.verts))
        for L in lanterns:
            for k in ('z_p0', 'z_p1', 'top', 'bottom'):
                L[k] -= zmin
            L['prof'] = [(a, b - zmin) for a, b in L['prof']]
            L['centre'] = (L['centre'][0], L['centre'][1], L['centre'][2] - zmin)
        rig_top -= zmin
    o = mb.to_object(ASSET)
    _orient_prints(o, lanterns, mats['ink'])
    genlib.finish(o)
    _paper_uvs(o, lanterns, mats['paper'])
    _anim(o, lanterns, rig_top, red)
    o['kz_variant'] = variant
    o['kz_params'] = json.dumps(dict(variant=variant, r=round(r, 3), h=round(h, 3), shape=shape, colour=colour, print=print_))
    o['kz_flicker'] = json.dumps([mats['paper']])
    return o


def _cluster(mb, bm, lod, rng, n, shape, print_, mats, r, h):
    """porch cluster rig: a small dark-timber rack (two chamfered rails + cross bars) hung on two ropes, with the
    lanterns on staggered drops underneath in one or two rows (concept 04: clusters at different heights).
    Plan spacing >= 2 r_max + 0.08 m, drops staggered 0.15-0.6 m, radii +-15 %, the front row carries the logo."""
    rows = 1 if n <= 4 else 2
    per = int(math.ceil(n / rows))
    rmax = r * 1.15
    pitch = 2 * rmax + 0.08
    L = per * pitch + (pitch / 2 if rows == 2 else 0)
    depth = pitch * 0.9 if rows == 2 else 0.0
    drop_max = 0.6
    top_z = drop_max + h * 1.1 + 0.2 + 0.5
    rail_z = top_z - 0.5
    infos = []
    k = 0
    for row in range(rows):
        for i in range(per):
            if k >= n:
                break
            lr = genlib.rng(rng.random(), f'cl{k}')
            rr = r * lr.uniform(0.85, 1.15)
            hh = h * lr.uniform(0.85, 1.1)
            x = -L / 2 + pitch * (i + 0.5) + (pitch * 0.5 if row else 0.0)
            y = (0.5 - row) * depth if rows == 2 else 0.0          # row 0 is the front (+Y)
            drop = 0.15 + ((i + row) % 3) / 2 * 0.3 + lr.uniform(0.0, 0.15)
            base = rail_z - 0.03 - drop - hh - 0.066 * max(0.75, min(1.6, rr / 0.225))
            front = row == 0
            info = lantern(mb, bm, lod, lr, rr, hh, shape, ('logo' if front else 'none') if print_ == 'none' else print_, mats,
                           origin_z=base, cord=drop, x=x, y=y, yaw=lr.uniform(-0.3, 0.3))
            infos.append(info)
            k += 1
    wood = mats['timber']
    bev = 0.004 if lod == 0 else 0.0
    sec = 0.05
    ys = [(-depth / 2 - sec / 2), (depth / 2 + sec / 2)] if rows == 2 else [0.0]
    for y in ys:
        mb.box((0, y, rail_z + sec / 2), (L + 0.12, sec, sec * 1.2), wood, bevel=bev)
    if rows == 2 and lod < 3:
        for x in (-L / 2 + 0.03, L / 2 - 0.03) + ((0.0,) if lod == 0 else ()):
            mb.box((x, 0, rail_z + sec * 1.2 + 0.015), (0.04, depth + sec * 2 + 0.06, 0.03), wood, bevel=bev)
    for x in (-L / 2 + 0.06, L / 2 - 0.06):
        _strut(bm, (x, 0, rail_z + sec * 1.2), (x, 0, top_z), 0.007, mats['rope'])
    return infos, top_z


def _torus_h(bm, c, R, rr, segs, rsegs, mi):
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ring = []
        for k in range(rsegs):
            b = 2 * math.pi * k / rsegs
            rad = R + rr * math.cos(b)
            ring.append(bm.verts.new((c[0] + rad * math.cos(a), c[1] + rad * math.sin(a), c[2] + rr * math.sin(b))))
        rings.append(ring)
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % segs]
        for k in range(rsegs):
            kk = (k + 1) % rsegs
            f = bm.faces.new((A[k], A[kk], B[kk], B[k])); f.material_index = mi


def _rope_xy(bm, z0, z1, rad, sides, mi):
    _rope(bm, z0, z1, rad, sides, mi, twist=False)


def _strut(bm, a, b, rad, mi):
    a, b = Vector(a), Vector(b)
    d = (b - a); L = d.length
    q = d.to_track_quat('Z', 'Y')
    vs = []
    for z in (0, L):
        ring = []
        for k in range(3):
            ang = 2 * math.pi * k / 3
            ring.append(bm.verts.new(a + q @ Vector((rad * math.cos(ang), rad * math.sin(ang), z))))
        vs.append(ring)
    for k in range(3):
        kk = (k + 1) % 3
        f = bm.faces.new((vs[0][k], vs[0][kk], vs[1][kk], vs[1][k])); f.material_index = mi


def _orient_prints(o, lanterns, ink_mi):
    """single-sided decals: recalc_face_normals can flip isolated faces, so point every print face away from its
    lantern's axis (they must survive backface culling in the web viewer)"""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    flip = []
    for f in bm.faces:
        if f.material_index != ink_mi:
            continue
        c = f.calc_center_median()
        L = min(lanterns, key=lambda L: (c.x - L['xy'][0]) ** 2 + (c.y - L['xy'][1]) ** 2)
        radial = Vector((c.x - L['xy'][0], c.y - L['xy'][1], 0))
        if f.normal.dot(radial) < 0:
            flip.append(f)
    bmesh.ops.reverse_faces(bm, faces=flip)
    bm.to_mesh(me); bm.free()


# ------------------------------------------------------------------ UVs + animation data
def _paper_uvs(o, lanterns, paper_mi):
    """object-mode UVs for lantern_paper: u around the lantern 0..1, v per band from ring_plan() (at LOD0 every
    modelled rib interval re-uses one painted rib interval, so painted rib lines sit in the pinches)."""
    me = o.data
    uv = me.uv_layers['UVMap']
    for poly in me.polygons:
        if poly.material_index != paper_mi:
            continue
        c = poly.center
        L = min(lanterns, key=lambda L: (Vector((c.x - L['xy'][0], c.y - L['xy'][1], 0)).length
                                         + (0 if L['z_p0'] - 0.01 <= c.z <= L['z_p1'] + 0.01 else 10)))
        zs = [p_[1] for p_ in L['prof']]
        bi = max(0, min(len(zs) - 2, next((i for i in range(len(zs) - 1) if zs[i] <= c.z <= zs[i + 1]), 0)))
        z0, z1 = zs[bi], zs[bi + 1]
        v0, v1 = L['bandv'][bi]
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            x, y = co.x - L['xy'][0], co.y - L['xy'][1]
            a = (math.atan2(x, y) - L['yaw']) / (2 * math.pi) % 1.0
            t = (co.z - z0) / max(1e-9, z1 - z0)
            us.append([a, v0 + max(0.0, min(1.0, t)) * (v1 - v0), li])
        if max(u[0] for u in us) - min(u[0] for u in us) > 0.5:
            for u in us:
                if u[0] < 0.5:
                    u[0] += 1.0
        for a, v, li in us:
            uv.data[li].uv = (a, v)


def _anim(o, lanterns, rig_top, red):
    me = o.data
    vg_static = None
    idx = {}
    for i, L in enumerate(lanterns):
        for k in range(*L['vidx']):
            idx[k] = i
    groups = [o.vertex_groups.new(name=f'sway_{i}') for i in range(len(lanterns))]
    static = [v.index for v in me.vertices if v.index not in idx]
    if static:
        vg_static = o.vertex_groups.new(name='static'); vg_static.add(static, 1.0, 'REPLACE')
    for i, g in enumerate(groups):
        g.add([k for k, li in idx.items() if li == i], 1.0, 'REPLACE')
    attr = me.color_attributes.new('sway', 'FLOAT_COLOR', 'POINT')
    zmin = min(L['bottom'] for L in lanterns)
    for v in me.vertices:
        i = idx.get(v.index)
        if i is None:
            attr.data[v.index].color = (0, 0, 0, 1)
            continue
        L = lanterns[i]
        w = (L['top'] - v.co.z) / max(1e-6, L['top'] - zmin)
        attr.data[v.index].color = (max(0.0, min(1.0, w)), i / 16.0, 0, 1)
    col = (K2200[0], K2200[1] * (0.55 if red else 1.0), K2200[2] * (0.6 if red else 1.0))
    o['kz_sway'] = json.dumps([dict(group=f'sway_{i}', pivot=[round(L['xy'][0], 4), round(L['xy'][1], 4), round(L['top'], 4)],
                                    amp_deg=round(1.2 + 0.4 * (i % 3), 2), period_s=round(2 * math.pi * math.sqrt(max(0.2, L['top'] - L['centre'][2]) / 9.81) * 1.6, 2))
                               for i, L in enumerate(lanterns)])
    o['kz_lights'] = json.dumps([dict(pos=[round(c, 4) for c in L['centre']], color=[round(c, 4) for c in col], watts=25 if len(lanterns) == 1 else 12)
                                 for L in lanterns])
