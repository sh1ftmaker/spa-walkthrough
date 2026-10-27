"""Flowering sakura: a dark twisted trunk forking low into spreading limbs, crowned by layered clouds of
pale-pink blossom clusters.

Identifying features kept at every LOD: dark twisted trunk, broad umbrella crown of layered pale-pink (white /
magenta-lit) blossom clusters with gaps showing the branches.
Concept: refs/gen/sheet-mod-nature.png #2 "Flowering sakura - 4.5 m" (52 px/m off the 4.5 m arrow): crown
4.1 m wide, trunk ~0.35 m across at the foot with root flare, forking at ~1.7 m (0.38 h) into 2-3 main limbs
with an S-twist; the crown is a broad dome from ~1.9 m to the top, made of many separate small clusters
(0.2-0.5 m) with sky / branches showing between them.  Lookbook 04 (a white-blossom tree by the counter),
06 (magenta-lit sakura in Kawagiri), 30 (plan).

Targets (proxy 4 x 4 x 4.5): h 3.8-4.5 (seeded 0.85-1.0 x proxy h; param 3-5), crown 3.4-3.9 m wide, fork at
0.32-0.42 h, trunk base r 0.15-0.19 m (x h/4.5) with flare, 3 (sometimes 2 or 4) main limbs rising 30-55 deg,
each generation 0.6-0.75 x shorter and spreading flatter; clusters 0.18-0.42 m, flattened (z 0.6), grouped at
the branch tips and along the outer branches.
Parameters: h 3-5, lean 0-15 deg, levels 3-5 (branch generations incl. the trunk: 3 -> 2 forks, 5 -> 4),
  density 0.6-1.4 (blossom clusters), tint pale | white | magenta.
Seeds change: levels (4, 3, 5, 4 ...), limb count and azimuths, twist phase, lean, height, tint (1 pale,
  2 pale, 3 white, 4 magenta), cluster layout.

Materials: trunk / branches `bark` darkened (tint 0.42), blossoms `blossom` (NEW: stand-in `washi` tinted
  pink / white / magenta, translucent paper reads as petals; record in kz_material_pending).
LOD: one skeleton.  LOD0 all generations, 12-sided trunk with spiral ridges, ~600 puffs (7-pt hulls);
  LOD1 same branches at lower sides, ~40 % of the puffs at 1.35 x size; LOD2 generations <= 3, one puff per
  cluster at cluster size; LOD3 trunk + main limbs + one blossom mass per main limb (<= 200 tris).
Animation: `kz_sway` colour attribute (R 0 at the trunk foot -> 0.3-0.6 on limbs -> 0.75-1 in blossom, G
  phase per cluster, B 1 on blossom) + vertex group `sway`.  kz_sway_default_indoor = 0.3 (indoor drafts).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_groundcover as P

ASSET = 'sakura_small'
FEATURES = ['dark twisted trunk', 'layered pale-pink blossom clusters']
TINTS = {'pale': (0.98, 0.76, 0.9), 'white': (1.0, 0.96, 0.98), 'magenta': (1.0, 0.4, 0.95)}
TINT_BY_SEED = ['pale', 'pale', 'white', 'magenta']
LEVELS_BY_SEED = [4, 3, 5, 4, 5, 3]


class Branch:
    def __init__(self, pts, r0, r1, gen, parent, limb):
        self.pts, self.r0, self.r1, self.gen, self.parent, self.limb = pts, r0, r1, gen, parent, limb
        self.kids = []


def skeleton(seed, h, lean, levels):
    g = C.rng(seed, 'skel')
    S = h / 4.5
    ph = g.uniform(0, 2 * math.pi)
    la = g.uniform(0, 2 * math.pi)
    ld = Vector((math.cos(la), math.sin(la), 0))
    Hf = h * g.uniform(0.32, 0.42)
    r0 = g.uniform(0.15, 0.19) * S
    trunk = []
    for i in range(11):
        t = i / 10
        tw = Vector((math.cos(ph + 3.0 * t), math.sin(ph + 3.0 * t), 0)) * 0.12 * S * math.sin(math.pi * t)
        trunk.append(ld * math.tan(math.radians(lean)) * Hf * t + tw + Vector((0, 0, Hf * t)))
    T = Branch(trunk, r0, r0 * 0.62, 1, None, -1)
    out = [T]
    br = C.rng(seed, 'branches')
    n1 = br.choice([3, 3, 4])
    gens = levels - 1
    ratio = 0.68
    Lsum = 2.25 * S
    lens = [Lsum * ratio ** i / sum(ratio ** j for j in range(gens)) for i in range(gens)]
    lens = [max(l, 0.35 * S) for l in lens]

    def grow(parent, p0, d, gen, r_start, limb):
        L = lens[gen - 2] * br.uniform(0.85, 1.12)
        side = Vector((-d.y, d.x, 0)).normalized() if Vector((d.x, d.y, 0)).length > 1e-3 else Vector((1, 0, 0))
        wig = br.uniform(0.08, 0.16) * L
        np_ = 4 if gen <= 2 else 3
        pts = [p0]
        droop = 0.04 * (gen - 1) * L
        for i in range(1, np_ + 1):
            t = i / np_
            pts.append(p0 + d * L * t + side * wig * math.sin(math.pi * t * 1.5 + br.uniform(-0.3, 0.3)) - Vector((0, 0, droop * t * t)))
        b = Branch(pts, r_start, r_start * 0.62, gen, parent, limb)
        out.append(b)
        parent.kids.append(b)
        if gen < levels:
            nk = 2 if br.random() > 0.3 else 3
            base_az = math.atan2(d.y, d.x)
            el_p = math.asin(max(-1, min(1, d.z)))
            for j in range(nk):
                az = base_az + (j - (nk - 1) / 2) * br.uniform(0.55, 0.9) + br.uniform(-0.15, 0.15)
                el = max(math.radians(-5), el_p * br.uniform(0.55, 0.8) + br.uniform(-0.1, 0.12))
                dk = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
                at = br.uniform(0.75, 1.0) if j else 1.0
                grow(b, _at(pts, at), dk, gen + 1, r_start * 0.62, limb)
    for j in range(n1):
        az = ph + 2 * math.pi * j / n1 + br.uniform(-0.35, 0.35)
        el = math.radians(br.uniform(42, 62))
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        grow(T, _at(trunk, br.uniform(0.86, 1.0)), d, 2, r0 * 0.6, j)
    return out, S


def _at(pts, t):
    f = t * (len(pts) - 1)
    i = min(int(f), len(pts) - 2)
    return pts[i].lerp(pts[i + 1], f - i)


def clusters(seed, branches, S, density, levels):
    """blossom clusters: at every branch tip of the last two generations, plus along outer branches"""
    cr = C.rng(seed, 'clusters')
    tips = [b for b in branches if not b.kids]
    g0 = max(2, levels - 2)
    out = []
    for b in tips:                               # a big cluster on every tip
        out.append(dict(c=b.pts[-1] + Vector((0, 0, 0.05 * S)), R=cr.uniform(0.45, 0.62) * S * (1.2 if levels <= 3 else 1.0),
                        limb=b.limb, ph=cr.random(), seed=cr.random(), w=1.0))
    for b in branches:                           # layered clusters strung along the outer generations
        if b.gen < g0:
            continue
        ts = (0.4, 0.75) if b.kids else (0.3, 0.62)
        for t in ts:
            out.append(dict(c=_at(b.pts, t) + Vector((0, 0, 0.12 * S)), R=cr.uniform(0.34, 0.48) * S, limb=b.limb,
                            ph=cr.random(), seed=cr.random(), w=0.6))
    return out


def _fit_crown(branches, CL, h, p):
    """stretch / squeeze the crown (everything above the fork) so the blossom top reaches h and the crown
    spans <= 0.97 of the proxy footprint.  Done on the skeleton, so every LOD gets the same tree."""
    Hf = branches[0].pts[-1].z
    top = max(q['c'].z + q['R'] * 0.3 for q in CL)
    kz = max(0.8, min(1.8, (h * 0.97 - Hf) / max(top - Hf, 1e-3)))
    xs0 = min(q['c'].x - q['R'] for q in CL); xs1 = max(q['c'].x + q['R'] for q in CL)
    ys0 = min(q['c'].y - q['R'] for q in CL); ys1 = max(q['c'].y + q['R'] for q in CL)
    kx = min(1.3, p['w'] * 0.93 / (xs1 - xs0), p['d'] * 0.93 / (ys1 - ys0))      # the crown fills ~3.7 m
    cx, cy = branches[0].pts[-1].x, branches[0].pts[-1].y

    def f(v):
        z = v.z if v.z <= Hf else Hf + (v.z - Hf) * kz
        return Vector((cx + (v.x - cx) * kx, cy + (v.y - cy) * kx, z)) if v.z > Hf * 0.8 else Vector((v.x, v.y, z))
    for b in branches[1:]:
        b.pts = [f(v) for v in b.pts]
    for q in CL:
        q['c'] = f(q['c']); q['R'] *= (0.5 + 0.5 * kx)


def build(lod, seed, h=None, lean=None, levels=None, density=1.0, tint=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, ASSET)
    h = h or p['h'] * g.uniform(0.85, 1.0)
    lean = g.uniform(0, 12) if lean is None else lean
    levels = max(3, min(5, int(levels or LEVELS_BY_SEED[(seed - 1) % len(LEVELS_BY_SEED)])))
    tint = tint or TINT_BY_SEED[(seed - 1) % len(TINT_BY_SEED)]
    branches, S = skeleton(seed, h, lean, levels)
    CL = clusters(seed, branches, S, density, levels)
    _fit_crown(branches, CL, h, p)
    budget = (genlib.budget_of(ASSET) or [8000, 3200, 900, 200])[lod]

    mb = genlib.MeshBuilder()
    pending = {}
    bark = mb.slot('bark', tint=(0.32, 0.28, 0.28))
    bl = P.slot(mb, 'blossom', pending, tint=TINTS[tint])
    pl = P.Plant(mb)
    off = Vector((seed * 3.1, seed * 1.7, 0.5))

    # ---------------- wood
    for b in branches:
        if lod == 2 and b.gen > 3:
            continue
        if lod == 3 and b.gen > 3:
            continue
        if b.gen == 1:
            sides = C.lod_pick(lod, 12, 8, 6, 4)
            n = C.lod_pick(lod, 10, 6, 4, 3)
        else:
            sides = max(3, C.lod_pick(lod, {2: 8, 3: 6, 4: 5}.get(b.gen, 4), {2: 6, 3: 5, 4: 4}.get(b.gen, 3), 4 if b.gen == 2 else 3, 3))
            n = C.lod_pick(lod, len(b.pts) - 1, 2, 2 if b.gen == 2 else 1, 1)
        ts = [i / n for i in range(n + 1)]
        pts = [_at(b.pts, t) for t in ts]
        rad = [b.r0 + (b.r1 - b.r0) * t for t in ts]
        gen = b.gen

        def mod(i, k, th, ts=ts, gen=gen):
            t = ts[i]
            m = 1.0
            if gen == 1:
                m *= 1.0 + 0.8 * math.exp(-t / 0.08) * (0.5 + 0.5 * max(0.0, math.cos(5 * th + 0.4)))   # root flare
                if lod == 0:
                    m *= 1.0 + 0.09 * math.cos(6 * th + 7 * t) + 0.05 * noise.noise(Vector((math.cos(th), math.sin(th), t * 5)) + off)
            return m
        s0 = {1: 0.0, 2: 0.15, 3: 0.35}.get(gen, 0.5)
        pl.tube(pts, rad, bark, sides, sway=lambda t, s0=s0, gen=gen: (0.3 * t * t if gen == 1 else s0 + 0.15 * t), cap1=gen > 1 or lod == 3,
                mod=mod)

    # ---------------- blossom puffs
    used = C.tri_count(mb.bm)
    if lod <= 1:
        npts = 7 if lod == 0 else 6
        cost = 2 * npts - 4
        n_total = int((budget * 0.97 - used) / cost)
        if lod == 1:
            n_total = min(n_total, int(((genlib.budget_of(ASSET) or [8000])[0] * 0.97) / 10 / 2.5))
        wsum = sum(q['w'] for q in CL)
        for q in CL:
            cr = genlib.rng(q['seed'], 'puffs')
            x = n_total * q['w'] / wsum * density
            n = max(1 if q['w'] == 1.0 else 0, int(x) + (1 if cr.random() < x - int(x) else 0))
            k = 1.0 if lod == 0 else 1.35
            ps = 0.48 * q['R'] / max(1.0, n ** 0.33) * k * 1.15
            for j in range(n):
                v = Vector((cr.gauss(0, 1), cr.gauss(0, 1), cr.gauss(0, 0.6)))
                v = v.normalized() * cr.uniform(0.1, 1.0) * 0.85 if v.length > 1e-4 else v        # florets clump towards the centre
                c = q['c'] + Vector((v.x * q['R'], v.y * q['R'], v.z * q['R'] * 0.55))
                s = ps * cr.uniform(0.75, 1.25)
                pl.puff(c, (s, s * cr.uniform(0.85, 1.1), s * 0.85), bl, cr, npts=npts, sway=0.75 + 0.25 * cr.random(),
                        ph=q['ph'], rot=cr.uniform(0, 3.1))
    elif lod == 2:                      # tips (plus mid clusters on sparse trees), one puff each
        for q in [q for q in CL if q['w'] == 1.0 or levels <= 4]:
            cr = genlib.rng(q['seed'], 'puffs')
            s = q['R'] * 0.9
            pl.puff(q['c'], (s, s * 0.95, s * 0.6), bl, cr, npts=6, sway=0.85, ph=q['ph'])
    else:  # one blossom mass per main limb
        limbs = sorted({q['limb'] for q in CL})
        for li in limbs:
            qs = [q for q in CL if q['limb'] == li]
            cx = sum(q['c'].x for q in qs) / len(qs); cy = sum(q['c'].y for q in qs) / len(qs); cz = sum(q['c'].z for q in qs) / len(qs)
            rx = max(abs(q['c'].x - cx) + q['R'] for q in qs); ry = max(abs(q['c'].y - cy) + q['R'] for q in qs)
            rz = max(abs(q['c'].z - cz) + q['R'] * 0.6 for q in qs)
            pl.puff((cx, cy, cz), (rx * 0.85, ry * 0.85, rz * 0.8), bl, C.rng(seed, f'mass{li}'), npts=12, sway=0.85)

    for v in mb.bm.verts:
        v.co.z = max(v.co.z, 0.0)
    kf = P.fit_xy(mb, p['w'] * 0.98, p['d'] * 0.98)
    kh = P.fit_h(mb, h)
    if kf < 0.97 or kh < 0.97:
        print(f'[{ASSET}] s{seed} L{lod}: crown scaled xy {kf:.2f} z {kh:.2f} to fit')
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=60)
    P.post(o, soft_slots=(bl,))
    o['kz_sway_default_indoor'] = 0.3
    C.set_json_props(o, kz_params=dict(h=round(h, 3), lean=round(lean, 1), levels=levels, density=density, tint=tint),
                     kz_material_pending=pending)
    return o
