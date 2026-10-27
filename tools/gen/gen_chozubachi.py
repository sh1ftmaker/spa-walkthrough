"""Chozubachi: carved rough-basalt hand-washing basin, brimming and overflowing, free-standing bamboo kakehi, hishaku.

Identifying features kept at every LOD: faceted basalt basin with a rim lip and water flush with the brim; the
overflow notch with thin streams down the wall; the tall bamboo post standing on the ground beside the basin with
its near-horizontal arm reaching over the basin centre; the ladle across the rim.
Concept: refs/gen/sheet-mod-arrival.png #2 (W 1.6 x H 1.0, post about 1.35 m), lookbook 04-arrival-gate.
Proxy (3d/assets.json): 1.6 x 1.6 x 0.9 m today.  The kakehi post is 1.35 m, so the asset is ~1.4 m tall:
proposed proxy 1.6 x 1.6 x 1.45 (until then the sheet flags h).  Pivot at base centre, +Y front, object right +X.

Construction
  * basin: a lathe whose radius is an analytic R(theta, z): a seeded plan (round / oval / lobed / squared,
    aspect 0.75-1), a stepped chunky foot, bulge + taper, then 90-130 small cutting planes (cut depth 1-4 cm)
    that chisel 0.1-0.2 m flat facets into the wall, plus 6-10 deep planes for big fractures.  Rim thickness
    0.08-0.18 m, a low noisy rim with a 0.15-0.25 m overflow notch.
  * water: `water_still` at the brim (1-2 cm under the rim's low point, level with the notch lip).
  * overflow: 3-5 thin (2-4 cm) braided streams (`waterfall`, low emission) that leave the notch, ride the
    facets and fall clear of overhangs, down to a splash pool among the rubble.
  * rubble: 4-12 convex-hull basalt chunks (0.1-0.25 m) around the foot.  Lower LODs keep the largest.
  * kakehi: a free-standing noded culm (1.3-1.4 m) on the ground beside the basin, darker node bands, closed top;
    a near-horizontal arm (0-5 deg fall, 0.55-0.7 m, one node mid-span, stub behind the post, oblique hollow
    mouth over the basin centre ~0.25 m above the water); rope lashing at the junction and near the foot;
    a thin falling stream.  LOD3: 4-sided post + the arm as a single quad strip.
  * hishaku: hinoki cup and handle resting across the rim.

Animation: none.  Runtime FX: fx_water_surface on `water_still`, flow/drips on `waterfall` (streams).
Custom props: kz_water_level, kz_spout_mouth (xyz), kz_overflow_dir (xy), kz_pool (xy, r), kz_params.

Parameters (seeded defaults):
  r        0.45-0.80   footprint radius incl. rubble (basin rim radius ~0.74 r)
  h        0.60-1.00   basin rim height
  post_h   1.30-1.40   kakehi post height (independent of h)
  overflow 'front'|'back'|'left'|'right'|'none'
  plan     'round'|'oval'|'lobed'|'squared'  (default cycles with the seed: 1 oval, 2 lobed, 3 squared, 4 round)
  rim_t    0.08-0.18   rim thickness
  rubble   4-16        boulder count (seeded 10-16, 0.2-0.45 m, sunk 30-40 %)
  spout    True/False  kakehi on/off (False: use the separate kakehi_spout asset)
  ladle    True/False
"""
import math
import bmesh
from mathutils import Vector, noise
import genlib

ASSET = 'chozubachi'
FEATURES = ['carved faceted basalt basin brimming with water', 'overflow notch with thin streams',
            'tall bamboo post on the ground with a horizontal spout arm', 'ladle across the rim']

OVERFLOW_ANGLE = {'front': 90.0, 'back': 270.0, 'right': 0.0, 'left': 180.0}


def _n(v, off):
    return noise.noise(Vector(v) + off)


def _adiff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


class Basin:
    """Analytic outer/inner radius of the carved basin."""

    def __init__(self, R0, rim, ov_ang, plan, aspect, rim_t, rnd):
        self.R0, self.rim, self.plan, self.aspect, self.thick = R0, rim, plan, aspect, rim_t
        self.off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
        self.ph = rnd.uniform(0, math.pi)
        self.lobe_k = rnd.choice([3, 4, 5])
        self.bulge = rnd.uniform(0.02, 0.07)
        self.taper = rnd.uniform(-0.03, 0.05)
        self.flare = rnd.uniform(0.06, 0.12)          # the body spreads a little into the foot (the boulders do the rest)
        self.foot_h = rnd.uniform(0.08, 0.16) * rim
        self.foot_k = rnd.uniform(0.05, 0.09)
        self.depth = rnd.uniform(0.3, 0.42) * rim
        self.ov = None if ov_ang is None else math.radians(ov_ang + rnd.uniform(-10, 10))
        self.notch_w = rnd.uniform(0.15, 0.25) / 2 / R0          # half-angle of a 0.15-0.25 m notch
        # 2-3 stepped ledges: the body is a stack of blocks, each step sets the wall back 5-10 cm
        nl = rnd.randint(2, 3)
        self.ledges = sorted((rim * (0.2 + 0.65 * (i + rnd.uniform(0.15, 0.85)) / nl), rnd.uniform(0.05, 0.1)) for i in range(nl))
        self.planes = []
        for i in range(rnd.randint(90, 130)):                     # small chisel facets
            a = rnd.uniform(0, 2 * math.pi)
            zc = rnd.uniform(0.02, 0.98) * rim
            nz = rnd.uniform(-0.6, 0.6)
            self.planes.append(self._plane(a, zc, nz, rnd.uniform(0.04, 0.08), rnd.uniform(0.08, 0.14)))
        for i in range(rnd.randint(7, 11)):                       # big fractures / cracks
            a = rnd.uniform(0, 2 * math.pi)
            self.planes.append(self._plane(a, rnd.uniform(0.15, 0.85) * rim, rnd.uniform(-0.35, 0.35), rnd.uniform(0.10, 0.15), rnd.uniform(0.18, 0.3)))
        # rim broken into 6-10 chunks with 2-5 cm height jumps
        nc = rnd.randint(6, 10)
        cuts = sorted(rnd.uniform(0, 2 * math.pi) for _ in range(nc))
        hs, last = [], 0.0
        for i in range(nc):
            jump = rnd.uniform(0.02, 0.05) * rnd.choice([-1, 1])
            last = max(-0.035, min(0.03, last + jump))
            hs.append(last)
        self.rim_chunks = list(zip(cuts, hs))
        self.rim_noise = 0.004

    def _plane(self, a, zc, nz, depth, ext):
        """a bounded facet: the plane only cuts within +-ext (m) of its centre"""
        n = Vector((math.cos(a), math.sin(a), nz)).normalized()
        p = Vector((math.cos(a), math.sin(a), 0)) * self.base_r(a, zc)
        p.z = zc
        return (n, n.dot(p) - depth, a, zc, ext)

    def plan_r(self, th):
        t = th - self.ph
        a = self.aspect
        if self.plan == 'round':
            return 1.0
        if self.plan == 'oval':
            return 1.0 / math.sqrt(math.cos(t) ** 2 + (math.sin(t) / a) ** 2)
        if self.plan == 'squared':      # superellipse n=4
            return (abs(math.cos(t)) ** 4 + abs(math.sin(t) / a) ** 4) ** -0.25 * 0.93
        return (1 + 0.09 * math.cos(self.lobe_k * t) + 0.04 * math.cos(2 * self.lobe_k * t + 1.3)) / math.sqrt(math.cos(t) ** 2 + (math.sin(t) / (0.5 + 0.5 * a)) ** 2)

    def base_r(self, th, z):
        t = z / self.rim
        prof = 1.0 + self.bulge * math.sin(math.pi * min(1.0, t * 1.1)) - self.taper * t + self.flare * max(0.0, 1 - t / 0.55) ** 2
        if z < self.foot_h:                                       # stepped chunky foot
            prof += self.foot_k
        for li, (zl, kl) in enumerate(self.ledges):              # ledge steps: alternately set back / jut out
            if z > zl:
                sgn = 1 if li % 2 == 0 else -0.8
                prof -= sgn * kl / self.R0 * (0.7 + 0.3 * _n((math.cos(th) * 1.8, math.sin(th) * 1.8, zl * 3), self.off))
        wob = 1.0 + 0.04 * _n((math.cos(th) * 1.3, math.sin(th) * 1.3, t * 0.8), self.off)
        return self.R0 * self.plan_r(th) * prof * wob

    def outer(self, th, z, rough=True):
        r = self.base_r(th, z)
        dx, dy = math.cos(th), math.sin(th)
        for n, d, a, zc, ext in self.planes:
            if abs(z - zc) > ext or abs(_adiff(th, a)) * self.R0 > ext:
                continue
            den = n.x * dx + n.y * dy
            if den > 0.3:
                r = min(r, (d - z * n.z) / den)
        if rough:
            r += 0.006 * _n((dx * 14, dy * 14, z * 14), self.off)
        return max(r, self.R0 * 0.55)

    def notch(self, th):
        if self.ov is None:
            return 0.0
        d = _adiff(th, self.ov)
        if abs(d) > self.notch_w * 1.6:
            return 0.0
        return 0.5 + 0.5 * math.cos(math.pi * min(1.0, abs(d) / (self.notch_w * 1.6)))

    def chunk_h(self, th):
        t = th % (2 * math.pi)
        h = self.rim_chunks[-1][1]
        for a, hh in self.rim_chunks:
            if t >= a:
                h = hh
        return h

    def rim_raw(self, th):
        return self.rim + self.chunk_h(th) + self.rim_noise * _n((math.cos(th) * 2.2, math.sin(th) * 2.2, 3.0), self.off) \
            + 0.005 * _n((math.cos(th) * 8, math.sin(th) * 8, 3.0), self.off)

    @property
    def water(self):
        if not hasattr(self, '_zw'):
            low = min(self.rim_raw(2 * math.pi * k / 90) for k in range(90))
            self._zw = low - 0.012
        return self._zw

    def rim_z(self, th):
        z = self.rim_raw(th)
        f = self.notch(th)
        lip = self.water - 0.006                                 # the notch lip sits just under the water
        return z + (lip - z) * f if f > 0 else z

    def inner(self, th):
        return self.outer(th, self.rim, rough=False) - self.thick * (1 + 0.2 * _n((math.cos(th) * 2, math.sin(th) * 2, 7.0), self.off))


def hull_rock(mb, c, size, mi, rnd, npts=12, ground=True, rot=0.0):
    bm = mb.bm
    pts = []
    for _ in range(npts):
        v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(0.72, 1.0)
        v = Vector((v.x * size[0], v.y * size[1], v.z * size[2]))
        x = v.x * math.cos(rot) - v.y * math.sin(rot); y = v.x * math.sin(rot) + v.y * math.cos(rot)
        p = Vector((c[0] + x, c[1] + y, c[2] + v.z))
        p.z = max(p.z, 0.0 if ground else 0.004)
        pts.append(bm.verts.new(p))
    res = bmesh.ops.convex_hull(bm, input=pts)
    dead = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid})
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='VERTS')
    faces = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace) and g.is_valid]
    if ground:
        dead = [f for f in faces if f.normal.z < -0.95 and all(v.co.z < 0.002 for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    for f in faces:
        f.material_index = mi
    return faces


def tube(mb, pts, radii, mi, sides, cap0=False, cap1=False, mod=None, twist0=0.0, mis=None):
    """sweep a ring along a polyline (parallel-transport frames). mis: per-segment material override"""
    bm = mb.bm
    n = len(pts)
    tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    u = tans[0].cross(up).normalized()
    rings = []
    lu = bm.verts.layers.float.get('_tu') or bm.verts.layers.float.new('_tu')
    lv = bm.verts.layers.float.get('_tv') or bm.verts.layers.float.new('_tv')
    lf = bm.verts.layers.float.get('_tf') or bm.verts.layers.float.new('_tf')
    s_len = 0.0
    for i in range(n):
        if i:
            u = (u - tans[i] * u.dot(tans[i])).normalized()
            s_len += (pts[i] - pts[i - 1]).length
        v = tans[i].cross(u)
        ring = []
        for k in range(sides):
            th = twist0 + 2 * math.pi * k / sides
            rr = radii[i] if not isinstance(radii[i], tuple) else None
            if rr is None:      # elliptical section (ru, rv)
                off = u * math.cos(th) * radii[i][0] + v * math.sin(th) * radii[i][1]
            else:
                off = (u * math.cos(th) + v * math.sin(th)) * rr * (mod(i, k, th) if mod else 1.0)
            vv = bm.verts.new(pts[i] + off)
            rmean = radii[i] if not isinstance(radii[i], tuple) else 0.5 * (radii[i][0] + radii[i][1])
            vv[lu] = 2 * math.pi * rmean * k / sides; vv[lv] = s_len; vv[lf] = 2 * math.pi * rmean
            ring.append(vv)
        rings.append(ring)
    faces = []
    for i in range(n - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            f.material_index = mis[i] if mis else mi
            faces.append(f)
    if cap0:
        f = bm.faces.new(rings[0][::-1]); f.material_index = mi; faces.append(f)
    if cap1:
        f = bm.faces.new(rings[-1]); f.material_index = mi; faces.append(f)
    return rings, faces


def grid_faces(bm, rows, mi, closed=True):
    faces = []
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        m = len(a)
        for k in range(m if closed else m - 1):
            k2 = (k + 1) % m
            faces.append(bm.faces.new((a[k], a[k2], b[k2], b[k])))
    for f in faces:
        f.material_index = mi
    return faces


def _layout(B, seed, r, n_rub, post_th, pool):
    """rubble chunks: identical at every LOD (lower LODs keep the largest)"""
    rnd = genlib.rng(seed, 'layout')
    rocks = []
    tries = 0
    while len(rocks) < n_rub and tries < 400:
        tries += 1
        th = rnd.uniform(0, 2 * math.pi)
        if post_th is not None and abs(_adiff(th, post_th)) < math.radians(14):
            continue
        s = rnd.uniform(0.10, 0.22) * (r / 0.8)                  # half-size: boulders 0.2-0.45 m
        base = B.outer(th, 0.0, rough=False)
        rr = max(min(base + s * rnd.uniform(0.1, 0.6), r - s * 0.95), base - s * 0.5)
        c = Vector((math.cos(th) * rr, math.sin(th) * rr, 0))
        if pool and (c.to_2d() - pool[0]).length < pool[1] * 0.55:   # rocks may sit on the pool edge (hides it)
            continue
        hz = s * rnd.uniform(0.8, 1.35)
        sink = rnd.uniform(0.3, 0.4)
        rocks.append(((c.x, c.y, hz * (1 - 2 * sink)), (s * 1.1, s * 1.2, hz), th))
    rocks.sort(key=lambda t: -t[1][0] * t[1][2])
    return rocks


def build(lod, seed, r=None, h=None, post_h=None, overflow=None, plan=None, rim_t=None, rubble=None,
          spout=True, ladle=None, spout_h=None):
    p = genlib.proxy(ASSET)
    rnd = genlib.rng(seed, ASSET)
    half = min(p['w'], p['d']) / 2
    r = min(r or half * rnd.uniform(0.95, 1.0), half * 1.04)
    h = h or rnd.uniform(0.7, 0.9)
    h = max(0.55, min(h, 1.05))
    post_h = post_h or rnd.uniform(1.3, 1.4)
    overflow = overflow or ['front', 'front', 'right', 'front', 'left', 'front'][(seed - 1) % 6]
    plan = plan or ['oval', 'lobed', 'squared', 'round'][(seed - 1) % 4]      # consecutive seeds differ in plan
    aspect = rnd.uniform(0.75, 0.92) if plan != 'round' else 1.0
    rim_t = rim_t or rnd.uniform(0.08, 0.18)
    n_rub = int(rubble or rnd.randint(10, 16))
    if ladle is None:
        ladle = (seed - 1) % 4 != 2          # seeds 3, 7, 11 ... without the ladle
    ov_ang = OVERFLOW_ANGLE.get(overflow)
    R0 = 0.8 * r * rnd.uniform(0.95, 1.0)
    if plan == 'lobed':
        R0 *= 0.93
    B = Basin(R0, h, ov_ang, plan, aspect, rim_t, rnd)

    mb = genlib.MeshBuilder()
    wet = round(rnd.uniform(0.55, 0.72), 2)
    stone = mb.slot('basalt_wet', wetness=wet, tint=(round(rnd.uniform(0.85, 1.0), 2),) * 3)
    rubble_m = mb.slot('basalt_wet', wetness=round(wet - 0.2, 2), tint=(0.9, 0.9, 0.92))
    still = mb.slot('water_still')
    fall = mb.slot('waterfall', emissive_level=0.3)
    bam = mb.slot('bamboo', wear=round(rnd.uniform(0.1, 0.3), 2))
    node_m = mb.slot('bamboo', tint=(0.5, 0.45, 0.38), wear=0.5)          # darker node bands
    wood = mb.slot('hinoki', variant='wet_oiled')
    rope = mb.slot('rope', tint=(0.6, 0.5, 0.4))
    moss = mb.slot('moss', tint=(0.45, 0.55, 0.35))         # subtle, darker than the library default
    bm = mb.bm

    # ---------------- layout (LOD independent)
    lrnd = genlib.rng(seed, 'spout')
    post_th = None
    if spout:
        sgn = lrnd.choice([-1, 1]); off_ = lrnd.uniform(25, 50)
        post_th = math.radians(270 + sgn * off_)
        if B.ov is not None and abs(_adiff(post_th, B.ov)) < math.radians(70):
            post_th = math.radians(270 - sgn * off_)
    pool = None
    if B.ov is not None:
        pc = Vector((math.cos(B.ov), math.sin(B.ov))) * (B.outer(B.ov, 0.0, rough=False) + 0.04)
        pool = (pc, 0.2)
    rocks = _layout(B, seed, r, n_rub, post_th, pool)

    # ---------------- basin lathe (rings doubled at each ledge so the steps read as steps)
    N = (38, 18, 9, 6)[lod]
    lt = [zl / h for zl, _ in B.ledges]
    if lod == 0:
        outer_t = [0.0, 0.05, 0.12, 0.22, 0.34, 0.46, 0.58, 0.7, 0.82, 0.92] + [x - 0.012 for x in lt] + [x + 0.012 for x in lt]
    elif lod == 1:
        outer_t = [0.0, 0.1, 0.3, 0.55, 0.8, 0.92] + [x - 0.015 for x in lt] + [x + 0.015 for x in lt]
    elif lod == 2:
        outer_t = [0.0, 0.15 / h, 0.92] + [x - 0.02 for x in lt[:2]] + [x + 0.02 for x in lt[:2]]
    else:
        outer_t = [0.0, 0.15 / h, lt[0] + 0.02, 0.92]
    outer_t = sorted(set(round(min(max(x, 0.0), 0.95), 4) for x in outer_t))
    rl = genlib.rng(seed, f'lathe{lod}')
    ths = [2 * math.pi * k / N + rl.uniform(-0.2, 0.2) * 2 * math.pi / N for k in range(N)]
    chip = None
    if B.ov is not None:    # vertex columns at the notch so it reads at every LOD
        j = min(range(N), key=lambda k: abs(_adiff(ths[k], B.ov)))
        ths[j] = B.ov
        chip = (j + N // 2) % N                      # LOD2/3: a second chip in the rim opposite the notch
    rough = lod < 2
    foot_k = {0: 1.0, 1: 1.0, 2: 1.06, 3: 1.14}[lod]   # low LODs: keep the foot flare as its own wider ring

    def wall_r(th, z):
        rr = B.outer(th, z, rough)
        return rr * (foot_k if z < 0.16 else 1.0)
    rows = []
    for t in outer_t:
        z = t * h
        rows.append([bm.verts.new((math.cos(th) * wall_r(th, z), math.sin(th) * wall_r(th, z), z)) for th in ths])
    lip = 1.04 if lod >= 2 else 0.99
    def rz(k, th):
        z = B.rim_z(th)
        if lod >= 2 and k == chip:
            z -= 0.06
        return z
    top_o = [bm.verts.new((math.cos(th) * B.outer(th, h, rough) * lip, math.sin(th) * B.outer(th, h, rough) * lip, rz(k, th))) for k, th in enumerate(ths)]
    top_i = [bm.verts.new((math.cos(th) * B.inner(th), math.sin(th) * B.inner(th), rz(k, th) - 0.006)) for k, th in enumerate(ths)]
    rows += [top_o, top_i]
    inner_t = {0: [0.18, 0.6, 1.0], 1: [0.35, 1.0], 2: [1.0], 3: []}[lod]
    for t in inner_t:
        rows.append([bm.verts.new((math.cos(th) * B.inner(th) * (1 - 0.45 * t ** 1.6), math.sin(th) * B.inner(th) * (1 - 0.45 * t ** 1.6),
                                   B.rim_z(th) - 0.01 - B.depth * t)) for th in ths])
    wf = grid_faces(bm, rows, stone)
    if lod < 2:        # a few small moss patches on the rim top (1-2 quads each), never in the notch
        mr = genlib.rng(seed, 'moss')
        band = len(outer_t)
        for _ in range(mr.randint(2, 4)):
            k0 = mr.randrange(N)
            for k in range(k0, k0 + mr.randint(1, 2)):
                if B.notch(ths[k % N]) < 0.05:
                    wf[band * N + k % N].material_index = moss
    zw = B.water
    if lod < 3:
        c = bm.verts.new((0, 0, h - B.depth - 0.02))
        last = rows[-1]
        for k in range(N):
            f = bm.faces.new((last[k], last[(k + 1) % N], c)); f.material_index = stone

    # ---------------- water at the brim (reaches the notch lip)
    wv = []
    for th in ths:
        ri = B.inner(th) + 0.01
        if B.notch(th) > 0.3:
            ri = B.outer(th, h, False) - 0.005
        wv.append(bm.verts.new((math.cos(th) * ri, math.sin(th) * ri, zw)))
    if lod < 2:
        wc = bm.verts.new((0, 0, zw))
        for k in range(N):
            f = bm.faces.new((wv[k], wv[(k + 1) % N], wc)); f.material_index = still
    else:
        f = bm.faces.new(wv); f.material_index = still

    # ---------------- overflow (from the concept, sheet-mod-arrival #2 front): one sheet leaves the notch,
    # narrows, and splits into 2-3 braids over the lower third; a few thin strands spill at the notch sides.
    def wall_path(th0, zs, clear=0.014):
        pts, r_prev = [], None
        for z in zs:
            wall = max(B.outer(th0, zz, rough) for zz in (z, min(h, z + 0.05), min(h, z + 0.1)))
            rr = wall + clear if r_prev is None else max(wall + clear, r_prev - 0.015)   # falls clear of ledges
            r_prev = rr
            pts.append(Vector((math.cos(th0) * rr, math.sin(th0) * rr, z)))
        return pts

    def strip(rows_pts, widths, th0, mi, double=True):
        """a curved sheet: rows of centre points, width per row, laid across the wall tangent"""
        tdir = Vector((-math.sin(th0), math.cos(th0), 0))
        cols = 4 if lod == 0 else 3
        front = []
        for q, wdt in zip(rows_pts, widths):
            front.append([bm.verts.new(q + tdir * wdt * (c_ / (cols - 1) - 0.5) + Vector((math.cos(th0), math.sin(th0), 0)) * 0.006 * math.sin(math.pi * c_ / (cols - 1)))
                          for c_ in range(cols)])
        grid_faces(bm, front, mi, closed=False)
        if double:      # back face so it reads from inside the notch too
            back = [[bm.verts.new(v.co - Vector((math.cos(th0), math.sin(th0), 0)) * 0.008) for v in row] for row in front]
            for f in grid_faces(bm, back, mi, closed=False):
                f.normal_flip()

    if B.ov is not None and lod < 3:
        srnd = genlib.rng(seed, 'streams')
        z_lip = zw - 0.002
        if lod < 2:
            w0 = srnd.uniform(0.3, 0.4)
            z_split = h * srnd.uniform(0.3, 0.4)
            nz = 7 if lod == 0 else 4
            zs = [z_lip - (z_lip - z_split) * (k / nz) ** 0.9 for k in range(nz + 1)]
            cpath = wall_path(B.ov, zs, 0.012)
            cpath[0] = Vector((math.cos(B.ov), math.sin(B.ov), 0)) * (B.outer(B.ov, h, False) - 0.03) + Vector((0, 0, z_lip))
            widths = [w0 * (1 - 0.35 * (k / nz)) for k in range(nz + 1)]
            strip(cpath, widths, B.ov, fall)
            # braids over the lower third
            nb = srnd.randint(2, 3) if lod == 0 else 2
            for bi in range(nb):
                off_m = (bi / (nb - 1) - 0.5) * widths[-1] * 0.8
                th_b = B.ov + off_m / B.R0
                zb = [z_split - z_split * (k / 4) for k in range(5)] if lod == 0 else [z_split, z_split * 0.4, 0.01]
                bp = wall_path(th_b, zb, 0.014)
                bp = [q + Vector((-math.sin(B.ov), math.cos(B.ov), 0)) * 0.02 * math.sin(3 * q.z + bi) for q in bp]
                if pool:
                    bp.append(Vector((pool[0].x, pool[0].y, 0.006)).lerp(bp[-1], 0.75))
                strip(bp, [srnd.uniform(0.04, 0.07)] * len(bp), B.ov, fall, double=lod == 0)
            # thin side strands spilling at the notch edges
            for si, sgn in enumerate([-1, 1] + ([srnd.choice([-1, 1])] if lod == 0 and srnd.random() < 0.5 else [])):
                th_s = B.ov + sgn * B.notch_w * srnd.uniform(1.15, 1.45)
                zs_ = [B.rim_z(th_s) - 0.01 - (B.rim_z(th_s) - 0.02) * (k / (5 if lod == 0 else 3)) for k in range(6 if lod == 0 else 4)]
                sp = wall_path(th_s, zs_, 0.012)
                sp = [q + Vector((-math.sin(th_s), math.cos(th_s), 0)) * 0.015 * math.sin(4 * q.z + si) for q in sp]
                tube(mb, sp, [(srnd.uniform(0.015, 0.02), 0.005)] * len(sp), fall, 3)
        else:           # LOD2: one 5 cm strand
            sp = wall_path(B.ov, [zw, h * 0.5, 0.01], 0.015)
            strip(sp, [0.05] * len(sp), B.ov, fall, double=False)
        # splash pool: soft irregular edge, tucked under the rubble
        if pool:
            np_ = (24, 12, 8)[lod]
            tdir = Vector((-math.sin(B.ov), math.cos(B.ov)))
            rdir = Vector((math.cos(B.ov), math.sin(B.ov)))
            pv = []
            for k in range(np_):
                a = 2 * math.pi * k / np_
                rr = pool[1] * (1 + 0.22 * _n((math.cos(a) * 2, math.sin(a) * 2, 9), B.off) + 0.08 * _n((math.cos(a) * 6, math.sin(a) * 6, 9), B.off))
                q = pool[0] + tdir * math.cos(a) * rr * 1.25 + rdir * math.sin(a) * rr * 0.7
                pv.append(bm.verts.new((q.x, q.y, 0.002)))
            pcv = bm.verts.new((pool[0].x, pool[0].y, 0.009))
            for k in range(np_):
                f = bm.faces.new((pv[k], pv[(k + 1) % np_], pcv)); f.material_index = still

    # ---------------- rubble skirt: boulders sunk 30-40 % into the ground, merging with the foot
    for i, (c_, sz, th) in enumerate(rocks[:(16, 9, 4, 0)[lod]]):
        hull_rock(mb, c_, sz, rubble_m, genlib.rng(seed, f'rock{i}'), npts=(14, 9, 7)[lod], ground=True, rot=th)

    # ---------------- kakehi: free-standing culm on the ground + horizontal arm
    props = {}
    ext = [(math.cos(a) * B.outer(a, 0.0, rough=False), math.sin(a) * B.outer(a, 0.0, rough=False)) for a in [2 * math.pi * k / 48 for k in range(48)]]
    if lod < 3:
        for (c_, sz, th) in rocks[:(16, 9, 4)[lod]]:
            ext += [(c_[0] + sx * sz[1], c_[1] + sy * sz[1]) for sx in (-1, 1) for sy in (-1, 1)]
        if pool:
            ext += [(pool[0].x + pool[1] * 1.3 * math.cos(a), pool[0].y + pool[1] * 1.3 * math.sin(a)) for a in (0, 1.57, 3.14, 4.71)]
    if spout:
        rp = lrnd.uniform(0.038, 0.048)
        wall = max(B.outer(post_th, z, False) for z in (0.0, h * 0.3, h * 0.6, h))
        dist = min(wall + rp + lrnd.uniform(0.03, 0.06), r - rp)
        post = Vector((math.cos(post_th) * dist, math.sin(post_th) * dist, 0))
        toward = Vector((-post.x, -post.y, 0)).normalized()
        zj = spout_h or min(zw + lrnd.uniform(0.25, 0.3), post_h - 0.1)
        arm_L = max(0.55, min(0.7, dist - lrnd.uniform(-0.02, 0.06)))
        fall_deg = lrnd.uniform(0, 5)
        sides = (10, 7, 5, 4)[lod]
        nodes = sorted(set([z for z in [0.28, 0.62] if z < zj - 0.2] + [round(zj - 0.08, 3)] + ([round(post_h - 0.05, 3)] if post_h - zj > 0.12 else []))) if lod < 3 else []
        zs = [0.0]
        for nd in nodes:
            zs += [nd - 0.012, nd, nd + 0.012] if lod < 2 else [nd]
        zs += [post_h - 0.02, post_h] if lod < 3 else [post_h]
        zs = sorted(set(round(z, 4) for z in zs))
        rad = [rp * (1.0 + (0.1 if any(abs(z - nd) < 0.001 for nd in nodes) and lod < 2 else 0.0)) * (1.03 - 0.05 * z / post_h) for z in zs]
        mis = [node_m if any(abs(zs[i] - nd) < 0.0131 and abs(zs[i + 1] - nd) < 0.0131 for nd in nodes) else bam for i in range(len(zs) - 1)]
        if lod < 3:
            mis[-1] = node_m
        tube(mb, [post + Vector((0, 0, z)) for z in zs], rad, bam, sides, cap1=True, mis=mis)
        # arm
        rs = rp * 0.72
        start = post + Vector((0, 0, zj)) - toward * (rp + lrnd.uniform(0.03, 0.05))     # stub 3-5 cm proud behind the post
        mouth = post + toward * arm_L + Vector((0, 0, zj - arm_L * math.tan(math.radians(fall_deg))))
        axis = (mouth - start).normalized()
        if lod == 3:     # an open 3-sided prism (6 tris): reads from every side
            tube(mb, [start, mouth], [rs * 1.2, rs * 1.2], bam, 3)
        else:
            mid = start.lerp(mouth, 0.55)
            if lod < 2:
                ap = [start, start.lerp(mouth, 0.3), mid - axis * 0.012, mid, mid + axis * 0.012, start.lerp(mouth, 0.8), mouth]
                ar = [rs, rs, rs, rs * 1.1, rs, rs, rs]
                am = [bam, bam, node_m, node_m, bam, bam]
            else:
                ap = [start, mid, mouth]; ar = [rs, rs * 1.08, rs]; am = None
            prings, _ = tube(mb, ap, ar, bam, max(sides - 2, 4), cap0=True, mis=am)
            for v in prings[-1]:                    # oblique cut: the top reaches further than the underside
                v.co += axis * ((v.co.z - mouth.z) / rs) * rs * math.tan(math.radians(35))    # 35 deg raked mouth
            if lod < 2:                             # hollow mouth
                inner = [bm.verts.new(mouth + (v.co - mouth) * 0.72 - axis * 0.03) for v in prings[-1]]
                m = len(inner)
                for k in range(m):
                    f = bm.faces.new((prings[-1][k], prings[-1][(k + 1) % m], inner[(k + 1) % m], inner[k])); f.material_index = bam
                f = bm.faces.new(inner[::-1]); f.material_index = node_m
            # lashing: two wraps at the junction, one near the foot
            if lod < 2:
                nseg = 8 if lod == 0 else 5
                # rope band ~6 cm tall at the joint: a wound sleeve (rope grain shows the turns) + edge wraps
                sleeve = [post + Vector((0, 0, zj - 0.03)), post + Vector((0, 0, zj + 0.03))]
                tube(mb, sleeve, [rp * 1.13, rp * 1.13], rope, 8 if lod == 0 else 6)
                for zc, rr_ in ((zj + 0.033, 1.14), (zj - 0.033, 1.14), (0.16, 1.1), (0.19, 1.1)):
                    lp = [post + Vector((math.cos(a) * rp * rr_, math.sin(a) * rp * rr_, zc + 0.004 * math.sin(2 * a)))
                          for a in [2 * math.pi * k / nseg for k in range(nseg + 1)]]
                    tube(mb, lp, [0.006] * len(lp), rope, 4 if lod == 0 else 3)
                if lod == 0:    # diagonal binding across the arm
                    side = axis.cross(Vector((0, 0, 1))).normalized()
                    for s_ in (-1, 1):
                        a0 = post + Vector((0, 0, zj + rs + 0.012)) + side * s_ * rp
                        a1 = post + Vector((0, 0, zj - rs - 0.012)) - side * s_ * rp
                        tube(mb, [a0, a0.lerp(a1, 0.5) + toward * rs * 1.05, a1], [0.005] * 3, rope, 3)
            # stream falling from the mouth
            tip = mouth + axis * rs * 0.5 - Vector((0, 0, rs * 0.3))
            drop = tip.z - zw
            n_ = 4 if lod == 0 else 2
            sp = [tip + axis * 0.04 * math.sin(math.pi * 0.5 * i / n_) - Vector((0, 0, drop * (i / n_) ** 1.4)) for i in range(n_ + 1)]
            tube(mb, sp, [0.0075, 0.0065, 0.006, 0.0055, 0.006][:len(sp)] if lod == 0 else [0.008] * len(sp), fall, 4 if lod == 0 else 3)
        props['kz_spout_mouth'] = mouth
        ext += [(post.x + rp * 1.12 * math.cos(a), post.y + rp * 1.12 * math.sin(a)) for a in (0, 1.57, 3.14, 4.71)]

    # ---------------- hishaku ladle resting across the rim
    lrnd2 = genlib.rng(seed, 'ladle')
    if ladle:
        th_l = math.radians(lrnd2.uniform(15, 55) if lrnd2.random() < 0.5 else lrnd2.uniform(125, 165))
        if B.ov is not None and abs(_adiff(th_l, B.ov)) < math.radians(45):
            th_l = B.ov + math.radians(70)
        ri = B.inner(th_l)
        cup_r, cup_h = 0.042, 0.07
        cc = Vector((math.cos(th_l) * (ri - cup_r * 0.55), math.sin(th_l) * (ri - cup_r * 0.55), B.rim_z(th_l)))
        cs = (12, 8, 6, 4)[lod]
        rad_dir = Vector((math.cos(th_l), math.sin(th_l), 0)); tan_dir = Vector((-math.sin(th_l), math.cos(th_l), 0))
        L = 0.46
        for tw in [0.55, 0.7, 0.85, 1.0, 1.15, 1.3]:
            d = (rad_dir * math.cos(tw) + tan_dir * math.sin(tw)).normalized()
            if (cc + d * L).to_2d().length < r * 0.88:
                break
        end = cc + d * L; end.z = B.rim_z(th_l) - 0.06
        if lod < 3:
            crings, _ = tube(mb, [cc + Vector((0, 0, -cup_h * 0.35)), cc + Vector((0, 0, cup_h * 0.65))], [cup_r * 0.96, cup_r], wood, cs, cap0=True)
            o_ring = crings[-1]
            if lod == 0:
                inn = [bm.verts.new(cc + (v.co - cc) * Vector((0.85, 0.85, 1.0))) for v in o_ring]
                for k in range(cs):
                    f = bm.faces.new((o_ring[k], o_ring[(k + 1) % cs], inn[(k + 1) % cs], inn[k])); f.material_index = wood
                bot = [bm.verts.new(Vector((v.co.x, v.co.y, cc.z - cup_h * 0.2))) for v in inn]
                grid_faces(bm, [inn, bot], wood)
                f = bm.faces.new(bot[::-1]); f.material_index = wood
            else:
                f = bm.faces.new(o_ring); f.material_index = wood
            a0 = cc + d * cup_r * 0.9 + Vector((0, 0, cup_h * 0.35))
            mid = cc + d * 0.16; mid.z = B.rim_z(math.atan2(mid.y, mid.x)) + 0.012
            hp = [a0, mid, end] if lod < 2 else [a0, end]
            tube(mb, hp, [0.009, 0.0085, 0.0075][:len(hp)] if lod < 2 else [0.012, 0.01], wood, (6, 5, 4)[lod], cap1=lod < 2)
        else:            # LOD3: handle as an open 3-sided prism
            tube(mb, [cc + Vector((0, 0, 0.03)), end], [0.02, 0.016], wood, 3)
        ext.append((end.x, end.y))

    # ---------------- recentre the footprint
    sx = (max(e[0] for e in ext) + min(e[0] for e in ext)) / 2
    sy = (max(e[1] for e in ext) + min(e[1] for e in ext)) / 2
    shift = Vector((-sx, -sy, 0))
    bmesh.ops.translate(bm, vec=shift, verts=bm.verts)
    o = mb.to_object(ASSET)
    o['kz_water_level'] = round(zw, 3)
    if B.ov is not None:
        o['kz_overflow_dir'] = [round(math.cos(B.ov), 3), round(math.sin(B.ov), 3)]
        o['kz_pool'] = [round(pool[0].x + shift.x, 3), round(pool[0].y + shift.y, 3), pool[1]]
    if 'kz_spout_mouth' in props:
        o['kz_spout_mouth'] = [round(x, 3) for x in props['kz_spout_mouth'] + shift]
    o['kz_basin_centre'] = [round(shift.x, 3), round(shift.y, 3)]
    o['kz_params'] = str(dict(r=round(r, 3), h=round(h, 3), post_h=round(post_h, 3), overflow=overflow, plan=plan,
                              rim_t=round(rim_t, 3), rubble=n_rub, spout=spout, ladle=ladle))
    genlib.finish(o, smooth_angle=18)
    tube_uvs(o)
    return o


def tube_uvs(o):
    """cylindrical UV0 (metres: u around, v along) on swept tubes, so bamboo / bark grain runs along them"""
    me = o.data
    if '_tu' not in me.attributes:
        return
    bm = bmesh.new(); bm.from_mesh(me)
    lu = bm.verts.layers.float['_tu']; lv = bm.verts.layers.float['_tv']; lf = bm.verts.layers.float['_tf']
    uv = bm.loops.layers.uv['UVMap']
    for f in bm.faces:
        if not all(v[lf] > 0 for v in f.verts) or len(f.verts) != 4:
            continue
        us = [l.vert[lu] for l in f.loops]
        C = max(l.vert[lf] for l in f.loops)
        if max(us) - min(us) > C * 0.5:
            us = [x + C if x < C * 0.5 else x for x in us]
        for l, uu in zip(f.loops, us):
            l[uv].uv = (uu, l.vert[lv])
    for name in ('_tu', '_tv', '_tf'):
        bm.verts.layers.float.remove(bm.verts.layers.float[name])
    bm.to_mesh(me); bm.free()
