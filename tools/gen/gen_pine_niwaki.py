"""Niwaki / windswept pine, planted in the ground (split from pine_bonsai).

Identifying features kept at every LOD: a thick twisted S-curved trunk with root buttresses; bare twisting limbs
carrying broad, flat-bottomed cloud pads; the leaning / windswept form for cliff edges; a pale Mirror variant.
Concept: refs/gen/sheet-mod-nature.png #1 (niwaki pine 3 m), lookbook 04-arrival-gate, 15-obsidian-mirror (pale),
18 / 19 (pines on ledges; 19 = windswept with one long horizontal limb).
Proxy (3d/assets.json): 2.6 x 2.6 x 3.2 m.  The concept canopy is ~0.95-1.0 x the height; the generator reads the
proxy, so with the proposed proxy 3.0 x 3.0 x 3.2 the canopy widens automatically.

Construction (one skeleton, every LOD swept from it)
  * trunk: base 0.4-0.5 m across, a two-bend S-curve (0.35-0.5 m lateral, in the front X-Z plane for niwaki),
    deep twisting bark ridges, 4-6 root buttresses flaring to ~0.9-1.0 m at the ground, surface roots.
  * limbs: one per pad, 0.6-1.1 m (x h/3.2), rising 10-20 deg, sinuous, tapering 0.10 -> 0.04 m across; the
    lowest limb on one side is the longest (asymmetric niwaki balance).  Windswept: the trunk leans 25-35 deg
    and one long near-horizontal limb (1.5-2 m) carries 2-3 pads streaming downwind.
  * pads: broad flat-bottomed cloud pads (thickness 0.25-0.33 of the width; lowest pads widest, crown pad
    0.6-0.7 m): an opaque core (flat underside, gently domed top) under `foliage_pine` needle-tuft cards
    (alpha-tested, double-sided; card UV 1 = 0.5 m) set over the core: fringe cards around the rim, tilted
    cards on the top.  LOD1 fewer larger cards, LOD2 core + a few big cards, LOD3 a 5-sided flat core per pad.
  * UV0: cylindrical on trunk / limbs / roots (bark plates run along them), per-card 0..w on the cards.

Animation (vertex sway, outdoors only): colour attribute `kz_sway` (point domain, COLOR_0):
  R = sway weight 0..1 (0 at the trunk base, rising up the trunk, ~0.6 along limbs, 0.8-1 in the pads),
  G = per-pad phase 0..1, B = 1 on foliage.  Also vertex group `sway` (= R).  kz_sway_default_indoor = 0.

Parameters (seeded defaults):
  h      1.5-5 m        overall height (seeded 0.72-1.0 x proxy h)
  pads   3-9            pad count incl. the crown pad (seeded over the full range)
  lean   0-35 deg       (niwaki 0-6, leaning 12-25, windswept 25-35)
  style  'niwaki' | 'windswept' | 'leaning'   (default by seed: 1 niwaki, 2 windswept, 3 leaning, 4 niwaki pale, 5 niwaki)
  twist  0.6-1.4        S-curve + bark ridge strength
  tint   'green' | 'pale'
Custom props: kz_trunk_base (xy of the trunk foot; off-centre for windswept, snap it to the cliff edge), kz_params.
"""
import json
import math
import bmesh
from mathutils import Vector, noise
import genlib

ASSET = 'pine_niwaki'
FEATURES = ['twisted S-curved trunk with root buttresses', 'bare limbs carrying flat cloud pads',
            'leaning / windswept form', 'pale variant for the Mirror']

STAND_IN = {'bark': ('rope', dict(tint=(0.36, 0.24, 0.17), normal_strength=1.3, scale=0.35)),
            'foliage_pine': ('rope', dict(tint=(0.30, 0.50, 0.17), roughness_offset=0.1, normal_strength=1.6, scale=0.22))}
CORE = ('moss', dict(tint=(0.45, 0.55, 0.32)))   # opaque pad core (library moss, darkened: it sits in the cards' shadow)
CORE_PALE = ('moss', dict(tint=(0.75, 0.8, 0.75)))
STYLE_BY_SEED = ['niwaki', 'windswept', 'leaning', 'niwaki', 'niwaki']

LODS = {
    #  trunk rings/sides, limb segs/sides, core segs/rings, cards per m^2 of pad, card scale, roots
    0: dict(tr=24, ts=12, bs=6, bsd=7, cs=12, cr=2, cards=280, csz=1.0, roots=6, twig=True),
    1: dict(tr=13, ts=8, bs=4, bsd=5, cs=9, cr=1, cards=80, csz=1.35, roots=4, twig=False),
    2: dict(tr=7, ts=5, bs=2, bsd=4, cs=7, cr=1, cards=12, csz=1.5, roots=0, twig=False),
    3: dict(tr=3, ts=4, bs=1, bsd=3, cs=6, cr=0, cards=0, csz=1.0, roots=0, twig=False),
}


def _n(v, off):
    return noise.noise(Vector(v) + off)


def _slot(mb, mid, **override):
    if mid in genlib.matlib.manifest():
        return mb.slot(mid, **override), None
    sid, params = STAND_IN[mid]
    return mb.slot(sid, **dict(params, **override)), sid


class Skeleton:
    def __init__(self, seed, h, pads, lean, style, twist, w):
        rnd = genlib.rng(seed, 'skel')
        self.off = Vector((rnd.uniform(-90, 90), rnd.uniform(-90, 90), rnd.uniform(-90, 90)))
        S = h / 3.2
        self.h, self.S, self.style, self.twist = h, S, style, twist
        self.phi = {'niwaki': rnd.uniform(0, 2 * math.pi), 'leaning': rnd.choice([0.0, math.pi]) + rnd.uniform(-0.5, 0.5),
                    'windswept': rnd.choice([0.0, math.pi]) + rnd.uniform(-0.35, 0.35)}[style]
        ld = Vector((math.cos(self.phi), math.sin(self.phi), 0))
        self.ld = ld
        L = math.radians(lean)
        self.r0 = 0.23 * S * rnd.uniform(0.95, 1.08) * (1.0 if style == 'niwaki' else 0.9)    # base 0.45-0.55 m across
        self.wig_ph = rnd.uniform(0, 2 * math.pi)
        lat_dir = Vector((1, 0, 0)) if style == 'niwaki' else Vector((-ld.y, ld.x, 0))
        A = rnd.uniform(0.3, 0.38) * S * twist                    # S-curve: two bends, 0.4-0.6 m lateral
        Ht = h * {'niwaki': 0.88, 'leaning': 0.86, 'windswept': 0.62}[style]
        self.trunk = []
        nt = 48
        for i in range(nt + 1):
            t = i / nt
            if style == 'windswept':
                lean_off = math.tan(L) * Ht * (1.15 * t - 0.2 * t * t)
            else:
                lean_off = math.tan(L) * Ht * t
            s_curve = A * math.sin(2 * math.pi * t * 1.05 + self.wig_ph) * min(1.0, t * 4)     # two bends
            depth = 0.35 * A * math.sin(2 * math.pi * t * 0.7 + self.wig_ph * 1.7) * t
            p = ld * lean_off + lat_dir * s_curve + lat_dir.cross(Vector((0, 0, 1))) * depth
            p.z = Ht * t * (1 - 0.12 * math.sin(L) * t)
            self.trunk.append(p)
        self.trunk = [q - Vector((self.trunk[0].x, self.trunk[0].y, 0)) for q in self.trunk]
        # ---- pads
        self.pads = []
        top = self.trunk[-1]
        crown_R = S * rnd.uniform(0.4, 0.48)
        self.pads.append(self._pad(top, crown_R, 1.0, None, rnd))
        nside = pads - 1
        if style == 'windswept':
            self._windswept(nside, rnd)
        else:
            self._tiers(nside, rnd)
        self.roots = [(2 * math.pi * (j + rnd.uniform(-0.25, 0.25)) / 6 + 0.3, rnd.uniform(0.28, 0.45) * S, rnd.uniform(0.38, 0.5)) for j in range(6)]
        self.n_lobes = rnd.choice([4, 5, 6])
        self.fit(w)

    def _tiers(self, nside, rnd):
        """niwaki composition (sheet-mod-nature #1): a broad low pair, a mid pair, an upper pad, then back pads
        for depth; tiers are spaced so 0.25-0.4 m of sky shows between them"""
        S = self.S
        Ht = self.trunk[-1].z
        gap = rnd.uniform(0.28, 0.38) * S
        Tt = {'B': 0.72 * 0.5 * S, 'M': 0.6 * 0.5 * S, 'U': 0.5 * 0.5 * S}      # typical pad thickness per tier
        zB = 0.3 * self.h
        tier_z = {'B': zB, 'M': zB + Tt['B'] + gap, 'U': zB + Tt['B'] + Tt['M'] + 2 * gap}
        order = [('B', 0), ('B', 1), ('M', 1), ('M', 0), ('U', 0), ('B', 2), ('M', 2), ('U', 1)]
        heavy = rnd.choice([0, 1])
        for k in range(nside):
            tier, side = order[k % len(order)]
            if side == 2:                                            # behind (-Y) for depth
                a = math.radians(270 + rnd.uniform(-35, 35))
            else:
                a = math.pi * ((side + heavy) % 2) + math.radians(rnd.uniform(-28, 28))
            if self.style == 'leaning':                              # crown streams over the lean
                a = self.phi + _adiff(a, self.phi) * 0.75
            d = Vector((math.cos(a), math.sin(a), 0))
            R = S * {'B': rnd.uniform(0.66, 0.78), 'M': rnd.uniform(0.55, 0.65), 'U': rnd.uniform(0.45, 0.55)}[tier]
            Lb = S * {'B': rnd.uniform(0.95, 1.15), 'M': rnd.uniform(0.75, 0.95), 'U': rnd.uniform(0.55, 0.7)}[tier]
            if tier == 'B' and side == 0:
                Lb = S * rnd.uniform(1.15, 1.3)                      # the long low limb: asymmetric overhang
            if side == 2:
                Lb *= 0.75; R *= 0.85
            rise_deg = rnd.uniform(10, 20)
            rise = math.tan(math.radians(rise_deg)) * Lb
            t = min(max((tier_z[tier] + rnd.uniform(-0.04, 0.04) - rise) / Ht, 0.12), 0.92)
            path = self._limb(self.at(t), d, Lb, rnd, rise_deg=rise_deg)
            self.pads.append(self._pad(path[-1], R, t, path, rnd))

    def _limb(self, p0, d, Lb, rnd, rise_deg=None):
        rise = math.tan(math.radians(rise_deg if rise_deg is not None else rnd.uniform(10, 20))) * Lb
        q = Vector((-d.y, d.x, 0)) * Lb * rnd.uniform(0.1, 0.18) * rnd.choice([-1, 1])
        sag = Lb * rnd.uniform(0.04, 0.08)
        return [p0, p0 + d * Lb * 0.3 + q * 0.8 + Vector((0, 0, rise * 0.45)),
                p0 + d * Lb * 0.62 - q * 0.6 + Vector((0, 0, rise * 0.8 - sag)), p0 + d * Lb + q * 0.3 + Vector((0, 0, rise))]

    def _windswept(self, nside, rnd):
        S = self.S
        t0 = rnd.uniform(0.5, 0.62)
        Lm = S * rnd.uniform(1.5, 2.0)
        main = self._limb(self.at(t0), self.ld, Lm, rnd, rise_deg=rnd.uniform(-3, 6))
        self.main = main
        k_on = min(3, max(1, nside - 1))
        for j in range(k_on):                                       # pads streaming along the long limb
            f = 1.0 - j * 0.32
            base = _along(main, f)
            d = (self.ld + Vector((-self.ld.y, self.ld.x, 0)) * rnd.uniform(-0.6, 0.6)).normalized()
            R = S * rnd.uniform(0.42, 0.55) * (1.0 - 0.15 * j)
            path = [base, base + d * 0.12 * S + Vector((0, 0, 0.1 * S))] if j else None
            c = path[-1] if path else base
            self.pads.append(dict(t=t0, path=path, main_part=f, c=c + Vector((0, 0, 0.03)), R=R, T=R * rnd.uniform(0.52, 0.62),
                                  ph=rnd.random(), d=d, flat=rnd.uniform(1.15, 1.35)))
        for i in range(nside - k_on):                               # the rest up the leaning trunk, streaming downwind
            t = 0.7 + 0.25 * (i + 0.5) / max(nside - k_on, 1)
            a = self.phi + math.radians(rnd.uniform(-60, 60))
            d = Vector((math.cos(a), math.sin(a), 0))
            Lb = S * rnd.uniform(0.6, 0.9)
            R = S * rnd.uniform(0.38, 0.48)
            path = self._limb(self.at(t), d, Lb, rnd)
            self.pads.append(self._pad(path[-1], R, t, path, rnd))

    def _pad(self, c, R, t, path, rnd):
        return dict(t=t, path=path, c=c + Vector((0, 0, 0.03)), R=R, T=R * rnd.uniform(0.46, 0.54), ph=rnd.random(),
                    d=(path[-1] - path[0]).normalized() if path else self.ld, flat=rnd.uniform(1.05, 1.25))

    def at(self, t):
        f = t * (len(self.trunk) - 1)
        i = min(int(f), len(self.trunk) - 2)
        return self.trunk[i].lerp(self.trunk[i + 1], f - i)

    def radius(self, t):
        return self.r0 * (1 - 0.72 * t) ** 1.3 + 0.018 * self.S

    def fit(self, w):
        def pts2d():
            xs, ys = [], []
            for P in self.pads:
                R = P['R'] * 1.12 + 0.1
                for a in [2 * math.pi * q / 16 for q in range(16)]:
                    x, y = math.cos(a) * (R + P['R'] * (P['flat'] - 1)), math.sin(a) * R
                    d = P['d']
                    xs.append(P['c'].x + x * d.x - y * d.y); ys.append(P['c'].y + x * d.y + y * d.x)
            for p in self.trunk:
                xs.append(p.x); ys.append(p.y)
            for a, l, _ in self.roots:
                xs.append(math.cos(a) * l); ys.append(math.sin(a) * l)
            return min(xs), max(xs), min(ys), max(ys)
        for _ in range(3):
            x0, x1, y0, y1 = pts2d()
            k = min(1.0, w * 0.94 / max(x1 - x0, 1e-3), w * 0.94 / max(y1 - y0, 1e-3))
            if k >= 1:
                break
            sc = lambda v: Vector((v.x * k, v.y * k, v.z))
            self.trunk = [sc(p) for p in self.trunk]
            if hasattr(self, 'main'):
                self.main = [sc(p) for p in self.main]
            for P in self.pads:
                P['c'] = sc(P['c'])
                if P['path']:
                    P['path'] = [sc(p) for p in P['path']]
                P['R'] *= 0.6 + 0.4 * k
            self.roots = [(a, l * k, s) for a, l, s in self.roots]
        x0, x1, y0, y1 = pts2d()
        self.shift = Vector((-(x0 + x1) / 2, -(y0 + y1) / 2, 0))
        top = max(P['c'].z + P['T'] * 1.08 for P in self.pads)
        kz = self.h * 0.99 / top
        sz = lambda v: Vector((v.x, v.y, v.z * kz))
        self.trunk = [sz(p) for p in self.trunk]
        if hasattr(self, 'main'):
            self.main = [sz(p) for p in self.main]
        for P in self.pads:
            P['c'] = sz(P['c'])
            if P['path']:
                P['path'] = [sz(p) for p in P['path']]


def _adiff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def _along(path, f):
    f = f * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    return path[i].lerp(path[i + 1], f - i)


def _resample(path, n):
    return [_along(path, j / n) for j in range(n + 1)]


class Geo:
    """bmesh helpers that also record cylindrical / card UVs and sway weights"""

    def __init__(self, mb):
        self.mb = mb
        bm = mb.bm
        L = bm.verts.layers.float
        self.ls, self.lp, self.lf = L.new('_kz_sw'), L.new('_kz_ph'), L.new('_kz_lf')
        self.lu, self.lv, self.luf = L.new('_kz_u'), L.new('_kz_v'), L.new('_kz_uf')

    def tag(self, v, sway, ph, leaf, u=None, vv=None):
        v[self.ls] = sway; v[self.lp] = ph; v[self.lf] = leaf
        if u is not None:
            v[self.lu] = u; v[self.lv] = vv; v[self.luf] = 1.0

    def tube(self, pts, radii, mi, sides, sway, ph=0.0, mod=None, cap1=False):
        bm = self.mb.bm
        n = len(pts)
        tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
        up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
        u = tans[0].cross(up).normalized()
        rings, s_len = [], 0.0
        circ = 2 * math.pi * sum(radii) / len(radii)
        for i in range(n):
            if i:
                u = (u - tans[i] * u.dot(tans[i])).normalized()
                s_len += (pts[i] - pts[i - 1]).length
            v = tans[i].cross(u)
            ring = []
            for k in range(sides + 1):          # duplicated seam column -> clean cylindrical UVs
                th = 2 * math.pi * (k % sides) / sides
                rr = radii[i] * (mod(i, th) if mod else 1.0)
                vv = bm.verts.new(pts[i] + (u * math.cos(th) + v * math.sin(th)) * rr) if k < sides else None
                if vv is None:
                    vv = bm.verts.new(ring[0].co)
                self.tag(vv, sway(i / max(n - 1, 1)), ph, 0.0, circ * k / sides, s_len)
                ring.append(vv)
            rings.append(ring)
        for i in range(n - 1):
            for k in range(sides):
                f = bm.faces.new((rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k])); f.material_index = mi
        if cap1:
            f = bm.faces.new(rings[-1][:-1]); f.material_index = mi
        return rings

    def card(self, base, right, up, w, hgt, mi, sway, ph, u0):
        bm = self.mb.bm
        vs = []
        for (a, b) in ((-0.5, 0), (0.5, 0), (0.5, 1), (-0.5, 1)):
            v = bm.verts.new(base + right * (a * w) + up * (b * hgt))
            self.tag(v, sway, ph, 1.0, u0 + (a + 0.5) * w, b * hgt)
            vs.append(v)
        f = bm.faces.new(vs); f.material_index = mi


def pad_core(G, P, sk, mi, segs, rings, ph, lobes, core_k=0.8):
    """flat-bottomed, gently domed cloud pad with a scalloped rim; returns a surface sampler for the cards"""
    bm = G.mb.bm
    c, R, T, d, flat = P['c'], P['R'], P['T'], P['d'], P['flat']
    off = sk.off + Vector((ph * 31, ph * 17, ph * 7))
    side = Vector((-d.y, d.x, 0))

    def edge(th):
        return R * (1 + 0.11 * math.cos(lobes * th + ph * 6) + 0.07 * _n((math.cos(th) * 1.6, math.sin(th) * 1.6, 0.3), off))

    def P_(th, f, z, k=1.0):
        e = edge(th) * f * k
        x, y = math.cos(th) * e * flat, math.sin(th) * e
        return c + d * x + side * y + Vector((0, 0, z))

    def top_z(th, f):
        return T * (0.3 + 0.7 * (1 - f * f) ** 0.7) + T * 0.1 * _n((math.cos(th) * f * 2.5, math.sin(th) * f * 2.5, 1.1), off)

    ths = [2 * math.pi * i / segs for i in range(segs)]
    sw = lambda v, f: G.tag(v, min(1.0, 0.8 + 0.2 * f), ph, 1.0)
    rows = []
    fr = [1.0 - 0.7 * (rings - j) / rings for j in range(rings)] if rings else []
    for f in fr:
        rows.append([bm.verts.new(P_(th, f, top_z(th, f) * 0.85, core_k)) for th in ths])
    rim = [bm.verts.new(P_(th, 1.0, T * 0.3 + T * 0.06 * _n((math.cos(th) * 3, math.sin(th) * 3, 2.0), off), core_k)) for th in ths]
    und = [bm.verts.new(P_(th, 0.96, 0.03 * _n((math.cos(th) * 3, math.sin(th) * 3, 4.0), off), core_k)) for th in ths]   # flat underside
    lens = rings == 0                 # LOD3: a flattened lens (hexagonal dome + shallow flat underside, 12 tris)
    if lens:
        for v in und:
            bm.verts.remove(v)
        for v in rim:
            v.co.z += T * 0.15
        rows += [rim]
    else:
        rows += [rim, und]
    top = bm.verts.new(c + Vector((0, 0, T * (1.15 if lens else 0.85))))
    for v in [top] + [v for r_ in rows for v in r_]:
        sw(v, (v.co - c).to_2d().length / max(R, 1e-3))
    first = rows[0]
    for i in range(segs):
        f = bm.faces.new((top, first[i], first[(i + 1) % segs])); f.material_index = mi
    for a, b in zip(rows[:-1], rows[1:]):
        for i in range(segs):
            i2 = (i + 1) % segs
            f = bm.faces.new((a[i], b[i], b[i2], a[i2])); f.material_index = mi
    if lens:
        bc = bm.verts.new(c - Vector((0, 0, T * 0.2)))
        sw(bc, 0.0)
        for i in range(segs):
            f = bm.faces.new((bc, rim[(i + 1) % segs], rim[i])); f.material_index = mi
    else:
        f = bm.faces.new(und[::-1]); f.material_index = mi        # flat bottom (an n-gon: tris = segs-2)
    return edge, P_, top_z


def build(lod, seed, h=None, pads=None, lean=None, style=None, twist=None, tint=None):
    p = genlib.proxy(ASSET)
    rnd = genlib.rng(seed, ASSET)
    h = h or p['h'] * rnd.uniform(0.72, 1.0)
    style = style or STYLE_BY_SEED[(seed - 1) % 5]
    if pads is None:
        pads = [7, 6, 5, 9, 4, 8, 3, 7, 6][(seed - 1) % 9]      # seeds walk the full 3-9 range
    pads = max(3, min(9, int(pads)))
    if lean is None:
        lean = {'niwaki': rnd.uniform(0, 6), 'leaning': rnd.uniform(12, 25), 'windswept': rnd.uniform(25, 35)}[style]
    twist = rnd.uniform(0.85, 1.3) if twist is None else twist
    tint = tint or ('pale' if (seed - 1) % 5 == 3 else 'green')
    w = min(p['w'], p['d']) * max(1.0, h / p['h'])
    sk = Skeleton(seed, h, pads, lean, style, twist, w)
    L = LODS[lod]

    mb = genlib.MeshBuilder()
    bark, bark_si = _slot(mb, 'bark', tint=(round(rnd.uniform(0.92, 1.0), 3),) * 3)
    if tint == 'pale':
        fol, fol_si = mb.slot('foliage_pine', variant='sage'), None      # library pale sage for the Mirror pine
        core = mb.slot(CORE_PALE[0], **CORE_PALE[1])
    else:
        fol, fol_si = _slot(mb, 'foliage_pine', tint=(round(rnd.uniform(0.94, 1.0), 3),) * 3)
        core = mb.slot(CORE[0], **CORE[1])
    G = Geo(mb)
    bm = mb.bm
    trunk_sway = lambda t: 0.35 * max(0.0, (t - 0.3) / 0.7) ** 1.5

    # ---------------- trunk
    nr = L['tr']
    ts_ = [(i / (nr - 1)) ** 1.1 for i in range(nr)]
    if lod < 2:
        ts_ = sorted(set([0.0, 0.015, 0.035, 0.065, 0.1] + ts_))
    pts = [sk.at(t) for t in ts_]
    rad = [sk.radius(t) * (1.3 if lod == 3 else 1.0) for t in ts_]
    tw = sk.twist
    nlob = 5 if lod < 2 else 4

    def tmod(i, th):
        t = ts_[i]
        if lod < 3:
            flare = 1.0 + 1.5 * math.exp(-t / 0.075) * (0.3 + 0.7 * max(0.0, math.cos(nlob * th + 0.7)) ** 1.3)   # 1.0-1.2 m root flare
        else:
            flare = 1.0 + 1.0 * math.exp(-t / 0.08)
        rel = min(0.013 * min(tw, 1.4) / max(rad[i], 0.02), 0.14)                    # 8-15 mm spiral ridges, ~0.5 turn
        ridge = 1.0 + (rel * math.cos(5 * th + math.pi * t * 1.0) + 0.35 * rel * math.cos(11 * th - 2 * t)) if lod < 2 else 1.0
        knot = 1.0 + 0.07 * _n((math.cos(th), math.sin(th), t * 9), sk.off) if lod == 0 else 1.0
        return flare * ridge * knot
    rings = G.tube(pts, rad, bark, L['ts'], lambda t: trunk_sway(t), mod=tmod)
    for v in rings[0]:
        v.co.z = 0.0
    for (a, l, s) in sk.roots[:L['roots']]:
        dd = Vector((math.cos(a), math.sin(a), 0))
        r0 = sk.radius(0)
        rp = [Vector((0, 0, 0.12 * sk.S)) + dd * r0 * 0.9, dd * (r0 + l * 0.45) + Vector((0, 0, 0.07 * sk.S)), dd * (r0 + l) + Vector((0, 0, 0.01))]
        G.tube(rp, [0.085 * sk.S, 0.06 * sk.S, 0.02], bark, 5 if lod == 0 else 4, lambda t: 0.0)

    # ---------------- windswept main limb
    if hasattr(sk, 'main'):
        n_seg = max(2, L['bs'] + 1)
        mp = _resample(sk.main, n_seg)
        r0 = sk.radius(0.55) * 0.85
        G.tube(mp, [r0 * (1 - 0.55 * j / n_seg) for j in range(n_seg + 1)], bark, L['bsd'] + 1, lambda t: trunk_sway(0.55) + 0.35 * t)

    # ---------------- limbs (taper 0.12 -> 0.03 m) forking into each pad, pad cores
    budget = genlib.budget_of(ASSET) or [6000, 2400, 700, 150]
    pads_draw = list(sk.pads)
    if lod == 3 and len(pads_draw) > 2:          # merge the top two pads into one crown dome
        hi = sorted(range(1, len(pads_draw)), key=lambda k: -pads_draw[k]['c'].z)[0]
        crown = dict(pads_draw[0]); crown['R'] = max(crown['R'], pads_draw[hi]['R']) * 1.2
        pads_draw = [crown] + [q for k, q in enumerate(pads_draw) if k not in (0, hi)]
    samplers = []
    for pi, P in enumerate(pads_draw):
        ph = P['ph']
        if P['path']:
            n_seg = L['bs']
            bp = _resample(P['path'], n_seg)
            r0 = max(0.06 * sk.S, min(sk.radius(P['t']) * 0.7, 0.07 * sk.S))
            br = [r0 * (1 - 0.72 * (j / n_seg) ** 0.9) for j in range(n_seg + 1)]
            s0 = trunk_sway(P['t'])
            G.tube(bp, br, bark, L['bsd'], lambda t, s0=s0: s0 + (0.65 - s0) * t, ph)
            if lod < 2:                # 2-4 forks fanning up into the pad
                tr = genlib.rng(seed, f'twig{pi}')
                base = _along(P['path'], 0.72)
                for j in range((tr.randint(2, 4) if lod == 0 else 2)):
                    a = tr.uniform(0, 2 * math.pi)
                    tip = P['c'] + Vector((math.cos(a), math.sin(a), 0)) * P['R'] * tr.uniform(0.35, 0.65) + Vector((0, 0, P['T'] * 0.2))
                    mid = base.lerp(tip, 0.5) + Vector((0, 0, 0.04))
                    G.tube([base, mid, tip], [0.028 * sk.S, 0.018 * sk.S, 0.009], bark, 4 if lod == 0 else 3,
                           lambda t: 0.6 + 0.3 * t, ph)
        samplers.append((P, pad_core(G, P, sk, core, L['cs'], L['cr'], ph, sk.n_lobes, core_k=(0.82 if lod < 2 else 0.95) if L['cards'] else 1.25)))

    # ---------------- needle cards: the budget left after wood + cores, spread by pad area
    if L['cards']:
        used = sum(len(f.verts) - 2 for f in bm.faces)
        n_total = max(0, int((budget[lod] * 0.97 - used) / 2))
        areas = [math.pi * P['R'] ** 2 * P['flat'] for P, _ in samplers]
        csz = L['csz']
        for pi, (P, (edge, P_, top_z)) in enumerate(samplers):
            cr = genlib.rng(seed, f'cards{pi}')
            n_c = max(6, int(n_total * areas[pi] / sum(areas)))
            ph = P['ph']
            for j in range(n_c):
                th = cr.uniform(0, 2 * math.pi)
                side_band = cr.random() < 0.25
                if side_band:       # the soft cloud edge: cards hang down along the side, < 8 cm proud
                    f = 1.0
                    z = P['T'] * cr.uniform(0.08, 0.32)
                else:
                    f = math.sqrt(cr.uniform(0.0, 0.94))
                    z = top_z(th, f)
                q = P_(th, f * 0.98, z)
                outward = (q - P['c']).to_2d()
                outward = Vector((outward.x, outward.y, 0)).normalized() if outward.length > 1e-4 else Vector((math.cos(th), math.sin(th), 0))
                n = (outward * 0.95 + Vector((0, 0, 0.1))).normalized() if side_band else (Vector((0, 0, 1)) * (1.05 - 0.8 * f) + outward * f * 0.9).normalized()
                g = outward - Vector((0, 0, 0.9))                       # down-slope direction
                tg = (g - n * g.dot(n)).normalized()
                rot = cr.uniform(-0.7, 0.7)                             # scatter round the normal
                tg = (tg * math.cos(rot) + n.cross(tg) * math.sin(rot)).normalized()
                a = math.radians(cr.uniform(20, 35))                    # cards lie 20-35 deg off the surface
                up = (tg * math.cos(a) + n * math.sin(a)).normalized()
                right = up.cross(n).normalized()
                wc, hc = cr.uniform(0.32, 0.45) * csz, cr.uniform(0.22, 0.3) * csz
                base = q - up * hc * 0.3 + n * 0.012
                G.card(base, right, up, wc, hc, fol, min(1.0, 0.85 + 0.15 * f), ph, cr.choice([0.0, 0.17, 0.33]))

    for v in bm.verts:
        if v.co.z < 0:
            v.co.z = 0.0
    bmesh.ops.translate(bm, vec=sk.shift, verts=bm.verts)
    if lod == 3:      # the merged crown / card-less pads shift the box a little: re-centre (invisible at 80 m)
        xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
        bmesh.ops.translate(bm, vec=Vector((-(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, 0)), verts=bm.verts)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=60)
    _post(o, fol, core)
    o['kz_trunk_base'] = [round(sk.shift.x, 3), round(sk.shift.y, 3)]
    o['kz_sway_default_indoor'] = 0
    o['kz_params'] = str(dict(h=round(h, 3), pads=pads, lean=round(lean, 1), style=style, twist=round(twist, 2), tint=tint))
    pend = {k: v for k, v in (('bark', bark_si), ('foliage_pine', fol_si)) if v}
    if pend:
        o['kz_material_pending'] = json.dumps({k: f'stand-in {v}' for k, v in pend.items()})
    return o


def _post(o, fol, core):
    """restore tube / card UVs (finish() box-projects), soft foliage normals, sway colour attribute + vertex group"""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    L = bm.verts.layers.float
    lu, lv, luf = L['_kz_u'], L['_kz_v'], L['_kz_uf']
    uv = bm.loops.layers.uv['UVMap']
    for f in bm.faces:
        if all(v[luf] > 0 for v in f.verts):
            for l in f.loops:
                l[uv].uv = (l.vert[lu], l.vert[lv])
    for e in bm.edges:
        if all(f.material_index in (fol, core) for f in e.link_faces):
            e.smooth = True
    for name in ('_kz_u', '_kz_v', '_kz_uf'):
        L.remove(L[name])
    bm.to_mesh(me); bm.free()
    n = len(me.vertices)
    s = [0.0] * n; p_ = [0.0] * n; l_ = [0.0] * n
    me.attributes['_kz_sw'].data.foreach_get('value', s)
    me.attributes['_kz_ph'].data.foreach_get('value', p_)
    me.attributes['_kz_lf'].data.foreach_get('value', l_)
    col = me.color_attributes.new('kz_sway', 'FLOAT_COLOR', 'POINT')
    flat = []
    for i in range(n):
        flat += [s[i], p_[i], l_[i], 1.0]
    col.data.foreach_set('color', flat)
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    vg = o.vertex_groups.new(name='sway')
    for i in range(n):
        if s[i] > 0:
            vg.add([i], s[i], 'REPLACE')
    for a in ('_kz_sw', '_kz_ph', '_kz_lf'):
        me.attributes.remove(me.attributes[a])
