"""Parts for gen_tsuboniwa (op06): rake ridges, moss mound, niwaki pine, stone toro, washi ceiling light box."""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C


# ------------------------------------------------------------------ raked gravel
def _ridge_strip(mb, pts, w, hgt, mi, caps=True):
    """triangular-section ridge along a polyline on z = 0 (two sloped quads per segment, end triangles)"""
    bm = mb.bm
    pts = [Vector(p) for p in pts]
    n = len(pts)
    L, R_, T_ = [], [], []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
        t.z = 0
        t = t.normalized()
        s = Vector((-t.y, t.x, 0)) * (w / 2)
        L.append(bm.verts.new(p + s)); R_.append(bm.verts.new(p - s)); T_.append(bm.verts.new(p + Vector((0, 0, hgt))))
    fs = []
    for i in range(n - 1):
        fs.append(bm.faces.new((L[i], L[i + 1], T_[i + 1], T_[i])))
        fs.append(bm.faces.new((T_[i], T_[i + 1], R_[i + 1], R_[i])))
    if caps:
        fs.append(bm.faces.new((R_[0], L[0], T_[0])))
        fs.append(bm.faces.new((L[-1], R_[-1], T_[-1])))
    mb._tag(fs, mi)
    return fs


def rake(mb, IW, ID, feats, mi, lod, pattern='straight', period=0.15, hgt=0.026, n_rings=3, ring_segs=24,
         wave_amp=0.06, wave_len=1.6, margin=0.1):
    """Karesansui rake: concentric ridges round every feature [(x, y, r)], straight (or wave) ridges along x
    elsewhere, cut where they meet a feature's outer ring.  Returns the faces."""
    fs = []
    w = period * 0.92
    for (x, y, r) in feats:
        for k in range(n_rings):
            rr = r + period * (0.6 + k)
            pts = [Vector((x + rr * math.cos(2 * math.pi * j / ring_segs), y + rr * math.sin(2 * math.pi * j / ring_segs), 0))
                   for j in range(ring_segs + 1)]
            keep = [abs(p.x) < IW / 2 - margin and abs(p.y) < ID / 2 - margin for p in pts]
            run = []
            for p, kp in zip(pts, keep):           # split rings where they would cross the walls
                if kp:
                    run.append(p)
                else:
                    if len(run) > 1:
                        fs += _ridge_strip(mb, run, w, hgt, mi)
                    run = []
            if len(run) > 1:
                fs += _ridge_strip(mb, run, w, hgt, mi, caps=len(run) < ring_segs + 1)
    if lod >= 2:
        return fs
    outer = [(x, y, r + period * (n_rings + 0.1)) for (x, y, r) in feats]
    ny = int((ID - 2 * margin) / period)
    step = 0.4 if lod == 0 else 0.8
    for i in range(ny):
        y0 = -ID / 2 + margin + period * (i + 0.5)
        if pattern == 'straight':
            xs = [-IW / 2 + margin, IW / 2 - margin]
            cuts = []
            for (x, y, r) in outer:
                dy = y0 - y
                if abs(dy) < r:
                    dx = math.sqrt(r * r - dy * dy)
                    cuts.append((x - dx, x + dx))
            cuts.sort()
            segs, a = [], xs[0]
            for c0, c1 in cuts:
                if c0 > a:
                    segs.append((a, min(c0, xs[1])))
                a = max(a, c1)
            if a < xs[1]:
                segs.append((a, xs[1]))
            for a, b in segs:
                if b - a > period:
                    fs += _ridge_strip(mb, [Vector((a, y0, 0)), Vector((b, y0, 0))], w, hgt, mi)
        else:
            n = max(2, int((IW - 2 * margin) / step))
            run = []
            for j in range(n + 1):
                x = -IW / 2 + margin + (IW - 2 * margin) * j / n
                yy = y0 + wave_amp * math.sin(2 * math.pi * x / wave_len)
                inside = any((x - fx) ** 2 + (yy - fy) ** 2 < fr * fr for fx, fy, fr in outer) or abs(yy) > ID / 2 - margin
                if inside:
                    if len(run) > 1:
                        fs += _ridge_strip(mb, run, w, hgt, mi)
                    run = []
                else:
                    run.append(Vector((x, yy, 0)))
            if len(run) > 1:
                fs += _ridge_strip(mb, run, w, hgt, mi)
    return fs


# ------------------------------------------------------------------ moss mound
def mound(mb, c, R, H, mi, r, lod, aspect=1.0):
    f = C.stone_outline(r, R, aspect=aspect, harmonics=((2, 0.08), (3, 0.07), (5, 0.04)), bites=0)
    if lod >= 3:                       # a low 5-sided cone, open underneath (it sits on the gravel)
        bm = mb.bm
        rim = [bm.verts.new(Vector(c) + Vector((*f(2 * math.pi * k / 5), 0))) for k in range(5)]
        top = bm.verts.new(Vector(c) + Vector((0, 0, H)))
        fs = [bm.faces.new((rim[k], rim[(k + 1) % 5], top)) for k in range(5)]
        mb._tag(fs, mi)
        return fs
    N = C.lod_pick(lod, 24, 10, 5, 5)
    rings = C.lod_pick(lod, ((1.0, 0.0), (0.97, 0.16), (0.86, 0.46), (0.66, 0.76)),
                       ((1.0, 0.0), (0.9, 0.4), (0.66, 0.76)), ((1.0, 0.0), (0.75, 0.62)), ((1.0, 0.0),))
    sh = C.lod_pick(lod, (0.42, 0.93), (0.42, 0.93), (0.42, 0.92), (0.55, 0.85))
    return C.cobble(mb, f, N, H, mi, mi, rings=rings, shoulder=sh, top_scale=0.16 if lod < 3 else 0.2, centre=c,
                    side_noise=0.0, r=r)


# ------------------------------------------------------------------ niwaki pine (a small garden pine on the mound)
def pine(mb, base, h, mats, r, lod):
    """S-curved trunk, 4-5 limbs to flat cloud pads (moss core + needle cards). base = trunk foot (x, y, z)."""
    bark, core, fol = mats['bark'], mats['core'], mats['fol']
    b = Vector(base)
    lean = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)).normalized() * h * 0.12
    ph = r.uniform(0, 6.28)
    n = C.lod_pick(lod, 12, 7, 4, 2)
    pts = []
    for i in range(n + 1):
        t = i / n
        s = Vector((math.sin(ph + t * 5.0), math.cos(ph * 1.3 + t * 4.0), 0)) * h * 0.06 * math.sin(math.pi * t)
        pts.append(b + lean * t + s + Vector((0, 0, h * 0.82 * t)))
    rad = [h * 0.045 * (1 - 0.65 * i / n) * (1 + 0.6 * math.exp(-i / n / 0.08)) for i in range(n + 1)]
    C.tube(mb, pts, rad, bark, sides=C.lod_pick(lod, 9, 6, 4, 3), cap1=True)
    n_pad = 5
    pads = [(pts[-1] + Vector((0, 0, h * 0.04)), h * 0.24, None)]
    a0 = r.uniform(0, 6.28)
    for k in range(n_pad - 1):
        t = 0.42 + 0.42 * k / (n_pad - 1) + r.uniform(-0.03, 0.03)
        p0 = pts[min(n, int(round(t * n)))]
        a = a0 + k * 2.4 + r.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        Lb = h * r.uniform(0.28, 0.4) * (1.15 - 0.4 * k / n_pad)
        tip = p0 + d * Lb + Vector((0, 0, Lb * r.uniform(0.15, 0.3)))
        pads.append((tip, h * r.uniform(0.17, 0.22) * (1.1 - 0.3 * k / n_pad), (p0, tip)))
    pad_seeds = [r.random() for _ in pads]
    for (c, R, limb), ps in zip(pads, pad_seeds):
        if limb and lod < 3:
            p0, tip = limb
            mid = p0.lerp(tip, 0.5) + Vector((0, 0, 0.05))
            C.tube(mb, [p0, mid, tip] if lod < 2 else [p0, tip], [h * 0.02, h * 0.014, h * 0.008], bark, sides=C.lod_pick(lod, 6, 4, 3), cap1=True)
        if lod < 2:
            C.foliage_pad(mb, c, R, R * 0.42, core, fol, genlib.rng(ps, 'pad'),
                          n_cards=C.lod_pick(lod, 52, 8), segs=C.lod_pick(lod, 12, 8), rings=C.lod_pick(lod, 2, 1),
                          card_w=(0.2, 0.28), card_h=(0.14, 0.2))
        elif lod == 2:
            C.lathe(mb, [(0, 0), (R, R * 0.1), (R * 0.6, R * 0.3), (0, R * 0.38)], 6, core, base=c)
        elif R >= sorted(q[1] for q in pads)[-3]:
            C.lathe(mb, [(0, 0), (R, R * 0.1), (0, R * 0.38)], 5, core, base=c)
    return pts[-1]


# ------------------------------------------------------------------ stone toro (yukimi / kasuga hybrid, ~1.1 m)
def toro(mb, c, H, mats, lod):
    """hexagonal stone toro: footing, post, platform, glowing firebox between 6 stone posts, flared roof, hoju.
    Returns the light centre."""
    st, paper = mats['stone'], mats['paper']
    b = Vector(c)
    k = H / 1.1
    seg = C.lod_pick(lod, 6, 6, 6, 4)
    ph = math.pi / 6
    if lod < 2:
        C.lathe(mb, [(0.2 * k, 0), (0.22 * k, 0.04 * k), (0.2 * k, 0.09 * k), (0.12 * k, 0.11 * k), (0, 0.11 * k)], seg, st, base=b, phase=ph)
        C.lathe(mb, [(0.075 * k, 0.1 * k), (0.068 * k, 0.32 * k), (0.075 * k, 0.44 * k)], seg, st, base=b, phase=ph)
        C.lathe(mb, [(0.1 * k, 0.43 * k), (0.2 * k, 0.48 * k), (0.2 * k, 0.53 * k), (0.15 * k, 0.55 * k), (0, 0.55 * k)], seg, st, base=b, phase=ph)
    else:
        C.lathe(mb, [(0.2 * k, 0), (0.08 * k, 0.12 * k), (0.08 * k, 0.45 * k), (0.2 * k, 0.53 * k)], seg, st, base=b, phase=ph, closed=False)
    zf0, zf1 = 0.55 * k, 0.77 * k
    C.lathe(mb, [(0.11 * k, zf0), (0.11 * k, zf1)], seg, paper, base=b, phase=ph, closed=False)
    if lod < 2:
        for j in range(6):
            a = ph + 2 * math.pi * j / 6
            q = b + Vector((math.cos(a) * 0.125 * k, math.sin(a) * 0.125 * k, 0))
            C.board(mb, q + Vector((0, 0, (zf0 + zf1) / 2)), (0.04 * k, 0.04 * k, zf1 - zf0), st, bevel=0.004 if lod == 0 else 0.0,
                    rot=(0, 0, a))
        roof = [(0.13 * k, zf1), (0.33 * k, 0.8 * k), (0.34 * k, 0.83 * k), (0.2 * k, 0.9 * k), (0.06 * k, 0.97 * k), (0.045 * k, 1.0 * k)]
        C.lathe(mb, roof, seg, st, base=b, phase=ph)
        C.lathe(mb, [(0.0, 1.0 * k), (0.045 * k, 1.03 * k), (0.05 * k, 1.06 * k), (0.03 * k, 1.09 * k), (0, 1.1 * k)], seg, st, base=b, phase=ph)
    else:
        C.lathe(mb, [(0.33 * k, 0.8 * k), (0.0, 1.1 * k)], seg, st, base=b, phase=ph, closed=False)
    return b + Vector((0, 0, (zf0 + zf1) / 2))


# ------------------------------------------------------------------ washi ceiling light box
def light_box(mb, z, BW, BD, mats, lod, pitch=0.45):
    """the 'false sky': a down-facing back-lit washi panel framed in hinoki with a kumiko grid under it.
    z = the panel face.  Returns the light entries."""
    wood, washi = mats['wood'], mats['washi']
    bm = mb.bm
    q = [bm.verts.new((x, y, z)) for x, y in ((-BW / 2, -BD / 2), (-BW / 2, BD / 2), (BW / 2, BD / 2), (BW / 2, -BD / 2))]
    f = bm.faces.new(q)                 # winding -> normal -Z (faces the court)
    if f.normal.z > 0:
        f.normal_flip()
    f.material_index = washi
    fw, fh = 0.09, 0.2
    bev = 0.006 if lod == 0 else 0.0
    if lod >= 3:                        # frame as one ring (outer side + soffit)
        def loop(hx, hy, zz):
            return [bm.verts.new((x, y, zz)) for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        a, b, c_ = loop(BW / 2, BD / 2, z - 0.05), loop(BW / 2 + fw, BD / 2 + fw, z - 0.05), loop(BW / 2 + fw, BD / 2 + fw, z + 0.15)
        mb._tag(C.bridge_rings(bm, b, a) + C.bridge_rings(bm, c_, b), wood)
        return [C.light_entry((0, 0, z - 0.05), color_k=2600, watts=40, kind='area', size=[round(BW, 3), round(BD, 3)],
                              facing=[0, 0, -1], note='washi ceiling box: the brightest surface in b1_treatment')]
    for sx in (-1, 1):
        C.board(mb, (sx * (BW / 2 + fw / 2), 0, z + fh / 2 - 0.05), (fw, BD + 2 * fw, fh), wood, bevel=bev)
        C.board(mb, (0, sx * (BD / 2 + fw / 2), z + fh / 2 - 0.05), (BW, fw, fh), wood, bevel=bev)
    if lod < 2:
        nx, ny = max(1, int(round(BW / pitch)) - 1), max(1, int(round(BD / pitch)) - 1)
        for i in range(nx):
            x = -BW / 2 + BW * (i + 1) / (nx + 1)
            C.board(mb, (x, 0, z - 0.02), (0.025, BD, 0.04), wood, bevel=0.0)
        for j in range(ny):
            y = -BD / 2 + BD * (j + 1) / (ny + 1)
            C.board(mb, (0, y, z - 0.025), (BW, 0.025, 0.03), wood, bevel=0.0)
    return [C.light_entry((0, 0, z - 0.05), color_k=2600, watts=40, kind='area', size=[round(BW, 3), round(BD, 3)],
                          facing=[0, 0, -1], note='washi ceiling box: the brightest surface in b1_treatment')]
