"""Bamboo spout (kakehi) on posts.

Measured from refs/gen/sheet-vs-bath-props.png #3 (front 0.20 m = 57 px, side 1.2 m = 248 px, height 1.4 m = 305 px):
two posts ~0.07 m side by side (0.16 m centre to centre, same y), 1.4 m tall, with the ~0.10 m pipe lying in the
notch between them just under the post tops (pipe rear end ~0.1 m behind the posts, mouth ~0.6 m in front,
tilt ~15-20 deg in the sheet; built at ~11 deg), rope wrapped at the top and again ~0.65 m up, hanging tails,
black rock footing, a pool below. Pipe ~100 mm, nodes every ~0.25 m.

Seeds are three layouts (Both uprights exist at every LOD):
  1 'gate'   concept layout: two side-by-side posts, pipe between them, long front overhang, rail + wraps.
  2 'run'    low long run: 1.1 m pipe lashed on top of two in-line posts, ~0.5 m drop (lookbook 04 horizontal run).
  3 'single' one fat post with the pipe lashed beside it and cantilevered, plus a diagonal prop.
Pipe: clean cylinder, nodes with dark bands, closed rear, last ~30 % sawn open (dark hollow ~6 mm wall, wide mouth).
Rope: 2-4 tight 6 mm turns per wrap (kzgeo_kakehi_spout.turns), tails hang from the wraps.
LOD2/LOD3 widen the pipe (x1.6 / x2.0) and keep the open mouth and both uprights.

Parameters (build(lod, seed, ...)):
  length 0.5-2.0 m   drop_h 0.3-1.5 m (mouth height)   posts 1|2   diameter 0.06-0.13 m   lashings 1-3 turns+
  style  'gate'|'run'|'single'  (default by seed)
Custom properties: kz_drop_h, kz_spout_tip, kz_spout_dir, kz_water_start (for fx_drips). No moving parts.
Proxy note: proxy w 0.2 limits posts to ~70 mm; a 0.28 m wide proxy would allow the 80-100 mm posts the review asks for.
"""
import math
import bmesh
from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_kakehi_spout as kk
from kzgeo_kakehi_spout import frame
from kzgeo_wall_trickle import hull_rock

ASSET = 'kakehi_spout'
FEATURES = ['thick cut bamboo pipe on posts', 'tight rope turns with tails', 'open sawn spout mouth', 'bamboo nodes', 'rock footing']
Z = Vector((0, 0, 1))
Y = Vector((0, 1, 0))
X = Vector((1, 0, 0))
CFG = {1: dict(mode='gate', L=(0.92, 0.98), tip=(0.96, 1.02), slope=(0.18, 0.2), droop=0.0),
       2: dict(mode='run', L=(1.08, 1.14), tip=(0.46, 0.52), slope=(0.09, 0.11), droop=0.03),
       3: dict(mode='single', L=(0.74, 0.8), tip=(0.84, 0.9), slope=(0.15, 0.17), droop=0.04)}


def _nodes(r, length, step=(0.22, 0.28), first=0.6):
    out, s = [], r.uniform(*step) * first
    while s < length * 0.97:
        out.append(s / length)
        s += r.uniform(*step)
    return out


def build(lod, seed, length=None, drop_h=None, posts=None, diameter=None, lashings=None, style=None):
    r = genlib.rng(seed, ASSET)
    c = CFG[(seed - 1) % 3 + 1]
    mode = style or c['mode']
    L = min(length if length else r.uniform(*c['L']), 2.0)
    dia = diameter or r.uniform(0.098, 0.106)
    R0 = dia / 2
    R = R0 * {0: 1.0, 1: 1.0, 2: 1.6, 3: 2.0}[lod]
    tip_z = drop_h if drop_h else r.uniform(*c['tip'])
    slope = r.uniform(*c['slope'])
    n_ring = {0: 8, 1: 7, 2: 6, 3: 5}[lod]
    bow = r.uniform(-1, 1) * 0.004
    cutk = 0.35
    sgn = 1 if r.random() < 0.5 else -1
    nt = lashings if lashings else (3 if lod == 0 else 2)
    mb = genlib.MeshBuilder()
    bam = mb.slot('bamboo', wear=round(r.uniform(0.15, 0.3), 2))
    bam_dk = mb.slot('bamboo', tint=(0.62, 0.45, 0.26), wear=0.5)
    bam_in = mb.slot('bamboo', tint=(0.3, 0.2, 0.1), wear=0.6)
    bam_post = mb.slot('bamboo', wear=round(r.uniform(0.3, 0.5), 2))
    footm = mb.slot('basalt_wet', wetness=1.0)
    rope = mb.slot('rope')
    y0, y1 = -L / 2, L / 2
    xoff = sgn * 0.044 if mode == 'single' else 0.0

    def zc(y):
        t = (y - y0) / L
        return tip_z + slope * (y1 - y) - c['droop'] * max(0.0, (t - 0.55) / 0.45) ** 2

    def cl(y):
        t = (y - y0) / L
        return Vector((xoff + bow * math.sin(math.pi * t), y, zc(y)))

    fwd = lambda y: (cl(min(y + 0.01, y1 + 0.02)) - cl(max(y - 0.01, y0 - 0.02))).normalized()
    bm = mb.bm
    wall = 0.0055 * (1.3 if lod >= 2 else 1.0)

    # ------------------------------------------------------------ pipe
    cut_t = 1.0 - r.uniform(0.3, 0.34)
    nodes = [t for t in _nodes(r, L) if 0.06 < t < cut_t - 0.05]
    stat = [(0.0, 1.0, False)]
    for t in nodes:
        if lod == 0:
            stat += [(t - 0.012 / L, 1.16, False), (t + 0.012 / L, 1.16, True)]
        elif lod == 1:
            stat += [(t, 1.18, False)]
    stat += [(cut_t, 1.0, False)]
    if lod <= 1:
        stat += [(cut_t + (1 - cut_t) * k / 3, 1.0, False) for k in (1, 2)]
    stat += [(1.0, 1.0, False)]
    if lod >= 2:
        stat = [(0.0, 1.0, False), (cut_t, 1.0, False), (1.0, 1.0, False)] if lod == 2 else [(0.0, 1.0, False), (1.0, 1.0, False)]
    if lod == 0:
        out_, prev = [], None
        for st_ in stat:                          # long internodes get a mid station so the bow reads
            if prev is not None and st_[0] - prev > 0.24 and not st_[2]:
                out_.append(((st_[0] + prev) / 2, 1.0, False))
            out_.append(st_); prev = st_[0]
        stat = out_
    stat.sort(key=lambda a: a[0])
    ts = [a[0] for a in stat]
    i_cut = min(range(len(ts)), key=lambda i: abs(ts[i] - cut_t)) if lod <= 2 and lod != 3 else 0
    open_scoop = lod <= 2 and i_cut > 0
    rot = math.pi / 2 - math.pi / n_ring if n_ring % 2 == 0 else math.pi / 2
    outer, inner = [], []
    for i, (t, bulge, _) in enumerate(stat):
        y = y0 + t * L
        M = frame(cl(y), fwd(y), Z)
        rad = R * (1.0 - 0.12 * t) * bulge * (1.0 + 0.012 * math.sin(t * 17 + seed))
        ro = kk.ring(bm, M, rad, n_ring, rot=rot)
        inn = kk.ring(bm, M, rad - wall, n_ring, rot=rot) if open_scoop and i >= i_cut else None
        if i == len(ts) - 1:
            for k, v in enumerate(ro):
                v.co += fwd(y) * (-math.sin(rot + 2 * math.pi * k / n_ring) * rad * cutk)
            if inn:
                for k, v in enumerate(inn):
                    v.co += fwd(y) * (-math.sin(rot + 2 * math.pi * k / n_ring) * (rad - wall) * cutk)
        outer.append(ro); inner.append(inn)

    def gap(i):
        if not open_scoop or i < i_cut:
            return set()
        frac = (i - i_cut) / max(1, len(ts) - 2 - i_cut)
        m = min(3 if frac < 0.35 else 5, n_ring - 3)
        h = (m - 1) // 2
        return {k % n_ring for k in range(-h, h + 1)}

    f_out, f_in, f_wall = [], [], []
    f_dark = []
    for i in range(len(ts) - 1):
        G = gap(i)
        q = kk.bridge_rings(bm, outer[i], outer[i + 1], skip=G)
        (f_dark if stat[i][2] else f_out).extend(q)
        if open_scoop and i >= i_cut:
            f_in += kk.bridge_rings(bm, inner[i + 1], inner[i], skip=G)
            for k in G:
                if (k - 1) % n_ring not in G:
                    f_wall.append(bm.faces.new((outer[i][k], outer[i + 1][k], inner[i + 1][k], inner[i][k])))
                if (k + 1) % n_ring not in G:
                    k2 = (k + 1) % n_ring
                    f_wall.append(bm.faces.new((outer[i + 1][k2], outer[i][k2], inner[i][k2], inner[i + 1][k2])))
    if open_scoop:
        for k in gap(i_cut):
            k2 = (k + 1) % n_ring
            f_wall.append(bm.faces.new((outer[i_cut][k2], outer[i_cut][k], inner[i_cut][k], inner[i_cut][k2])))
        Gl = gap(len(ts) - 2)
        for k in range(n_ring):
            if k not in Gl:
                k2 = (k + 1) % n_ring
                f_wall.append(bm.faces.new((outer[-1][k], outer[-1][k2], inner[-1][k2], inner[-1][k])))
    elif lod <= 2:
        f_out.append(bm.faces.new(outer[-1]))
    if lod <= 2:
        f_out.append(bm.faces.new(outer[0][::-1]))
    mb._tag(f_out + f_wall, bam); mb._tag(f_dark, bam_dk); mb._tag(f_in, bam_in)

    # ------------------------------------------------------------ uprights, rail, rope
    n_post = {0: 7, 1: 6, 2: 5, 3: 4}[lod]
    PK = {0: 1.0, 1: 1.0, 2: 1.3, 3: 1.6}[lod]
    ups = []                                           # (x, y, h, pr)
    if mode == 'gate':
        pr = 0.034 * PK
        yp = y0 + 0.14
        h = zc(yp) + 0.12
        sep = 0.135
        ups = [(-sep / 2, yp, h, pr), (sep / 2, yp, h, pr)]
    elif mode == 'run':
        pr = 0.042 * PK
        for t in (0.17, 0.8):
            yp = y0 + t * L
            ups.append((0.0, yp, zc(yp) - R0 * 0.8, pr))
    else:
        pr = 0.045 * PK
        yp = y0 + 0.22 * L
        ups.append((xoff - sgn * (R0 + pr) * 0.92, yp, zc(yp) + 0.14, pr))
    for (px, py, h, pr_) in ups:
        zl = [0.0, h * 0.3, h * 0.62, h] if lod == 0 else ([0.0, h * 0.5, h] if lod == 1 else [0.0, h])
        st = [(Vector((px, py, z)), Z, Y, pr_ * (1.08 - 0.12 * z / h) * (1.07 if lod == 0 and 0.05 < z / h < 0.95 and int(z / h * 7) % 3 == 1 else 1.0)) for z in zl]
        f, rr = kk.bamboo_tube(mb, st, bam_post, N=n_post, cap0=False, cap1=(lod in (1, 2)))
        if lod == 0:
            M = frame(Vector((px, py, h)), Z, Y)
            ins = kk.ring(bm, M, pr_ * 0.62, n_post)
            for v in ins:
                v.co.z -= 0.014
            mb._tag(kk.bridge_rings(bm, rr[-1], ins), bam_in)
            mb._tag([bm.faces.new(ins[::-1])], bam_in)
        if lod <= 1:
            sz_ = pr_ * 1.7
            hull_rock(mb, (px, py, 0.0), (sz_, sz_ * 1.1, sz_ * 0.5), footm, r, npts=7 if lod == 0 else 5, ground=0.0, rot=r.uniform(0, 6), rmin=0.85)
    if mode == 'single' and lod <= 2:                    # diagonal prop under the pipe
        cc = cl(y0 + 0.12 * L)
        top = Vector((cc.x, cc.y + 0.02, cc.z - R0 * 0.9)); foot = Vector((cc.x, y0 - 0.04, 0.0))
        kk.bamboo_tube(mb, [(foot, top - foot, X, 0.03 * PK), (top, top - foot, X, 0.026 * PK)], bam_post, N=max(4, n_post - 2), cap0=False, cap1=False)
    if mode == 'gate' and lod <= 2:                      # cross rail between the posts at ~55 % height
        zr = ups[0][2] * 0.55
        kk.bamboo_tube(mb, [(Vector((ups[0][0] + 0.01, ups[0][1], zr)), X, Z, 0.022), (Vector((ups[1][0] - 0.01, ups[1][1], zr)), X, Z, 0.022)],
                       bam_post, N=5 if lod == 0 else 4, cap0=False, cap1=False)
    if mode == 'run' and lod <= 2:                       # low cross rail between the posts, along the run
        zr = ups[0][2] * 0.45
        kk.bamboo_tube(mb, [(Vector((0.0, ups[0][1], zr)), Y, Z, 0.024), (Vector((0.0, ups[1][1], zr)), Y, Z, 0.024)],
                       bam_post, N=5 if lod == 0 else 4, cap0=False, cap1=False)

    if lod <= 1:
        N_ = 5 if lod == 0 else 4
        for (px, py, h, pr_) in ups:
            cc = cl(py)
            tdir = fwd(py)
            taper = 1.0 - 0.12 * ((py - y0) / L)
            kk.turns(mb, cc + Vector((0, 0.0, 0)), tdir, R0 * taper + 0.001, nt + 1 if lod == 0 else nt, rope, N=N_, up=Z)
            if mode != 'run' and lod == 0:
                kk.turns(mb, Vector((px, py, cc.z - 0.005)), Z, pr_ * 0.98, nt - 1 if lod == 0 else 1, rope, N=N_, up=Y)
            if lod == 0:
                if mode == 'gate':
                    kk.turns(mb, Vector((px, py, h * 0.55)), Z, pr_ * 0.98, 2, rope, N=N_, up=Y)
                    kk.bamboo_tube(mb, [(Vector((px + 0.01, py - 0.03, cc.z - 0.02)), Vector((0, 0, -1)), Y, 0.006), (Vector((px + 0.016, py - 0.03, cc.z - 0.12)), Vector((0, 0, -1)), Y, 0.0025)],
                                   rope, N=3, cap0=False, cap1=False)
                elif mode == 'run':
                    kk.turns(mb, Vector((0.0, py, h * 0.45)), Z, pr_ * 0.98, 2, rope, N=N_, up=Y)
                    kk.bamboo_tube(mb, [(Vector((pr_ * 0.9, py, cc.z - R0)), Vector((0, 0, -1)), Y, 0.006), (Vector((pr_ * 1.0, py, cc.z - R0 - 0.1)), Vector((0, 0, -1)), Y, 0.0025)],
                                   rope, N=3, cap0=False, cap1=False)
                else:
                    kk.bamboo_tube(mb, [(Vector((px, py - pr_, cc.z - 0.03)), Vector((0, 0, -1)), X, 0.006), (Vector((px, py - pr_ - 0.01, cc.z - 0.13)), Vector((0, 0, -1)), X, 0.0025)],
                                   rope, N=3, cap0=False, cap1=False)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=50)
    kg.uv_grain(o, [bam, bam_dk, bam_in, bam_post])
    tipc = cl(y1)
    d = fwd(y1)
    o['kz_drop_h'] = round(tip_z, 3)
    o['kz_spout_tip'] = [round(tipc.x, 3), round(tipc.y + 0.01, 3), round(tipc.z - R * 0.8, 3)]
    o['kz_spout_dir'] = [round(d.x, 3), round(d.y, 3), round(d.z, 3)]
    ws = cl(y0 + cut_t * L)
    o['kz_water_start'] = [round(ws.x, 3), round(ws.y, 3), round(ws.z, 3)]
    o['kz_layout'] = mode
    return o
