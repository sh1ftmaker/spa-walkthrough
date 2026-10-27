"""Tall hero stone toro (toro_tall): the cape (misaki) toro on g_east_path and the summit toro on s_rim_west.

TARGETS (measured before coding)
  No sheet shows a 3.4 m toro. Proportions come from refs/gen/sheet-mod-lights.png panel 3 (stone toro, label
  0.90 x 0.90 x 1.60 m; grid crop .scratch/op01/m_toro.png, 377 px/m), stretched to the row's 3.0-3.4 m by
  lengthening the shaft and adding base tiers (the row: "multi-tier base"). Panel 3 fractions of the total h:
    finial 0.10 (hoju ball on a collar), cap 0.18 (eave 0.87 m wide = 0.97 of the label width, thick rough eave,
    upturned corners), fire box 0.16 (0.44 m wide = 0.49 w, square lattice window on the front, ROUND window
    on the side), platform (chudai) 0.08 (0.66 m = 0.73 w), shaft 0.32 (0.36 -> 0.48 m, tapering upwards),
    base 0.17 (0.78 m wide, two rough tiers).
  Built (h 3.4 default): base tiers 0.20-0.24 h, shaft 0.32 h, chudai 0.065 h, fire box 0.15 h (w 0.50 W),
  cap 0.13 h + finial 0.10 h; cap span 0.92-1.0 W, W = 1.1 m (proxy). Bottom tier is a rough natural pad
  (the sheet's base), the upper tiers are cut steps that shrink to 0.62 W.
  Lookbook 01 / 11 only show andon on the rims; the toro reads as the same dark rough basalt as panel 3.

FEATURES kept at every LOD: stepped multi-tier base, tapered shaft, platform, glowing fire box with windows,
  broad cap with lifted corners, hoju finial.

PARAMETERS
  h       2.6-3.4 m overall (style default 3.4 misaki, 3.0 summit)
  tiers   3-5 base tiers (seeded 3-5)
  span    cap span as a fraction of W, 0.85-1.0
  windows 'lattice' (square lattice front/back, round sides) | 'round' (round all faces) | 'crescent' (sq + round)
  moss    0-1 moss cover on the up-facing stone (misaki 0.55, summit 0.2)
  style   'misaki' (square plan, broad cap, heavy corner lift, heavy moss) |
          'summit' (hexagonal plan, steeper cap, crisper tiers, light moss)

SEEDS change shape: style cycles (1 misaki, 2 summit, 3 misaki ...); tiers 3-5, h x0.9-1.0, cap span,
  cap lift, shaft taper and node band position, window type, rough-stone noise field.

MATERIALS (slots by part): stone = basalt_dry tint (0.42, 0.40, 0.42) (all stone; dry outdoor stone, cooled
  as the guide asks), moss = moss tint (0.45, 0.55, 0.32) (up-facing stone faces picked by a positional noise,
  same rule at every LOD), paper = washi_backlit (window panels, emissive), lattice = hinoki dark_timber.
ANIMATION: shader flicker on the paper slot (kz_anim). LIGHT: kz_lights point at the fire-box centre, 2300 K 25 W.
BUDGET 6000 / 2400 / 720 / 150.
"""
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_lantern_floor as L

ASSET = 'toro_tall'
FEATURES = ['multi-tier stone base', 'tapered shaft', 'platform', 'glowing fire box with windows',
            'broad cap with lifted corners', 'hoju finial']
STYLES = ['misaki', 'summit']
STYLE_DEF = dict(
    misaki=dict(shape='sq', h=3.4, span=1.0, lift=0.09, moss=0.55, windows='lattice', rise=0.55, W=1.1),
    summit=dict(shape='hex', h=3.0, span=0.9, lift=0.06, moss=0.2, windows='crescent', rise=0.7, W=0.95),
)
STONE_TINT = (0.42, 0.40, 0.42)


def _shape(shape, th):
    return L.shape_r(shape, th, 8.0)


def loft(mb, rings, N, mi, shape, phase, disp=None, cap_bot=True, cap_top=True, petals=0):
    """stack of rings [(hw, z, lift, petal_amp)] in a square (superellipse) or hex plan; hw = mid-edge
    half-width for 'sq', corner radius for 'hex'. hw 0 = pole. disp(co) -> offset. Closed solid."""
    bm = mb.bm
    out = []
    for rg in rings:
        hw, z = rg[0], rg[1]
        lift = rg[2] if len(rg) > 2 else 0.0
        pa = rg[3] if len(rg) > 3 else 0.0
        if hw <= 1e-6:
            v = bm.verts.new((0, 0, z))
            out.append([v]); continue
        ring = []
        for k in range(N):
            th = phase + 2 * math.pi * k / N
            f = _shape(shape, th)
            if pa and petals:
                f *= 1.0 + pa * (abs(math.cos(petals * th / 2)) ** 0.6 - 0.5)
            p = Vector((hw * f * math.cos(th), hw * f * math.sin(th), z + lift * L.corner_k(shape, th, 8.0) ** 2))
            if disp:
                p += disp(p)
            ring.append(bm.verts.new(p))
        out.append(ring)
    fs = []
    for A, B in zip(out[:-1], out[1:]):
        for k in range(N):
            k2 = (k + 1) % N
            if len(A) == 1 and len(B) == 1:
                continue
            if len(A) == 1:
                q = (A[0], B[k], B[k2])
            elif len(B) == 1:
                q = (A[k], A[k2], B[0])
            else:
                q = (A[k], A[k2], B[k2], B[k])
            fs.append(bm.faces.new(q))
    if cap_bot and len(out[0]) > 1:
        fs.append(bm.faces.new(out[0][::-1]))
    if cap_top and len(out[-1]) > 1:
        fs.append(bm.faces.new(out[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def block(mb, z0, z1, hw0, hw1, mi, shape, N, phase, disp, ch, lod):
    """rough stone block with chamfered top/bottom edges (LOD0-1) or plain (LOD2-3)"""
    if lod <= 1 and ch > 0:
        rings = [(hw0 - ch, z0), (hw0, z0 + ch * 0.8), (hw1, z1 - ch * 0.8), (hw1 - ch, z1)]
        if lod == 0:
            rings.insert(2, ((hw0 + hw1) / 2 * 1.008, (z0 + z1) / 2))
    else:
        rings = [(hw0, z0), (hw1, z1)]
    return loft(mb, rings, N, mi, shape, phase, disp)


def build(lod, seed, h=None, tiers=None, span=None, windows=None, moss=None, style=None):
    style = style or C.cycle(seed, STYLES)
    S = STYLE_DEF[style]
    shape = S['shape']
    g = C.rng(seed, 'dims')
    H = h or S['h'] * g.uniform(0.8, 1.0)
    H = max(2.6, min(3.4, H))
    W = S['W']
    nt = tiers or C.rng(seed, 'tiers').randint(3, 5)
    gc = C.rng(seed, 'cap')
    span_k = span or S['span'] * gc.uniform(0.86, 1.0)
    lift = S['lift'] * gc.uniform(0.6, 1.5)
    rise_k = S['rise'] * gc.uniform(0.9, 1.1)
    gs = C.rng(seed, 'shaft')
    taper = gs.uniform(0.72, 0.82)
    node_t = gs.uniform(0.38, 0.6)
    if windows is None:
        windows = C.pick(seed, 'windows', ['lattice', 'lattice', 'crescent']) if style == 'misaki' else S['windows']
    moss_k = S['moss'] if moss is None else moss

    mb = genlib.MeshBuilder()
    stone = mb.slot('basalt_dry', tint=STONE_TINT)
    mossm = mb.slot('moss', tint=(0.45, 0.55, 0.32))
    paper = mb.slot('washi_backlit')
    wood = mb.slot('hinoki', variant='dark_timber')

    # resolution per LOD
    if shape == 'sq':
        N = C.lod_pick(lod, 32, 16, 12, 4)
        ph = C.lod_pick(lod, 0.0, 0.0, 0.0, math.pi / 4)
    else:
        N = C.lod_pick(lod, 24, 12, 6, 6)
        ph = 0.0
    amp = C.lod_pick(lod, 1.0, 0.8, 0.5, 0.25)
    _r1 = L.rough(seed, 0.028 * amp, freq=5.0)
    _r2 = L.rough(seed + 7, 0.06 * amp, freq=3.2)

    def rough(p):
        return _r1(p, 0, 0)

    def rough_big(p):
        return _r2(p, 0, 0)
    hexk = 1.0 if shape == 'sq' else 1.0 / math.cos(math.pi / 6)     # hex: corner radius from mid-edge half-width

    def hw(x):
        return x * hexk

    stone_parts = []
    # ---- vertical layout
    fin_h = 0.10 * H
    cap_h = 0.14 * H
    fb_h = 0.165 * H
    pl_h = 0.065 * H
    base_h = (0.20 + 0.01 * (nt - 3)) * H
    eave_t = 0.038 * H * (1.15 if style == 'misaki' else 0.95)
    rise = cap_h * rise_k
    sh_h = H - fin_h - (eave_t + rise) - fb_h - pl_h - base_h
    z = 0.0
    # ---- base tiers: bottom is a rough pad, upper tiers are cut steps narrowing to 0.62 W
    th_w = [1.0 - 0.38 * i / max(1, nt - 1) for i in range(nt)]
    th_h = [1.35] + [1.0 - 0.12 * i for i in range(1, nt)]
    hs = sum(th_h)
    tiers_draw = list(range(nt)) if lod <= 2 else [0, nt - 1]
    for i in tiers_draw:
        tz = base_h * th_h[i] / hs
        w0 = W / 2 * th_w[i]
        if lod == 3 and i > 0:          # LOD3: the upper tiers as one block tapering to the top tier
            tz = base_h - z
            fs = block(mb, z, z + tz, hw(W / 2 * th_w[1]), hw(w0), stone, shape, N, ph, rough, 0, lod)
        elif i == 0:
            fs = block(mb, z, z + tz, hw(w0), hw(w0 * 0.93), stone, shape, N, ph,
                       lambda p: rough(p) + rough_big(p) * (0.6 + 0.4 * min(1, p.z / 0.1)), 0.05, lod)
        else:
            fs = block(mb, z, z + tz, hw(w0), hw(w0 * 0.985), stone, shape, N, ph, rough, 0.025, lod)
        stone_parts += fs
        z += tz
    # ---- shaft: tapered, a carved node band (LOD0-2), lotus foot ring
    s0 = W / 2 * 0.52
    s1 = s0 * taper
    zs0, zs1 = z, z + sh_h
    if lod <= 2:
        zn = zs0 + sh_h * node_t
        sn = s0 + (s1 - s0) * node_t
        band = 0.035 * H / 3.4
        rings = [(hw(s0 * 1.04), zs0), (hw(s0 * 0.99), zs0 + 0.02)]
        rings += [(hw(sn * 0.99), zn - band), (hw(sn * 1.07), zn - band * 0.5), (hw(sn * 1.07), zn + band * 0.5),
                  (hw(sn * 0.99), zn + band)] if lod <= 1 else [(hw(sn * 1.06), zn)]
        rings += [(hw(s1), zs1)]
    else:
        rings = [(hw(s0), zs0), (hw(s1), zs1)]
    stone_parts += loft(mb, rings, N, stone, shape, ph, rough)
    z = zs1
    # ---- platform (chudai): lotus-petal collar under a chamfered slab
    p_w = W / 2 * 0.74
    if lod <= 1:
        pet = 8 if shape == 'sq' else 12
        stone_parts += loft(mb, [(hw(s1 * 0.95), z - 0.01), (hw(p_w * 0.82), z + pl_h * 0.35, 0, 0.12),
                                 (hw(p_w * 0.9), z + pl_h * 0.42, 0, 0.12)],
                            N, stone, shape, ph, rough, petals=pet)
        stone_parts += block(mb, z + pl_h * 0.38, z + pl_h, hw(p_w), hw(p_w * 0.97), stone, shape, N, ph, rough, 0.02, lod)
    else:
        stone_parts += loft(mb, [(hw(s1), z - 0.01), (hw(p_w), z + pl_h * 0.4), (hw(p_w), z + pl_h)], N, stone, shape, ph, rough)
    z += pl_h
    # ---- fire box
    f_w = W / 2 * 0.52          # mid-edge half-width
    z_fb0, z_fb1 = z, z + fb_h
    zc = (z_fb0 + z_fb1) / 2
    nf = 4 if shape == 'sq' else 6
    apo = f_w
    side = 2 * apo * (1.0 if shape == 'sq' else math.tan(math.pi / 6))
    T = 0.07
    kz = Vector((0, 0, zc))
    face_ang = [math.pi / 2 + 2 * math.pi * i / nf for i in range(nf)]       # face 0 looks at +Y (front)
    win = []
    for i, a in enumerate(face_ang):
        if windows == 'round':
            win.append('round')
        elif windows == 'crescent':
            win.append('sq' if i % 2 == 0 else 'round')
        else:
            win.append('sq' if (i % 2 == 0 if nf == 4 else i in (0, 3)) else 'round')
    hole_w = side * 0.62
    hole_h = fb_h * 0.62
    if lod <= 1:
        for i, a in enumerate(face_ang):
            n = Vector((math.cos(a), math.sin(a), 0))
            M = C.frame(n * (apo - T / 2) + Vector((0, 0, zc)), n)
            hw_ = hole_w if win[i] == 'sq' else min(hole_w, hole_h) * 0.95
            hh_ = hole_h if win[i] == 'sq' else hw_
            stone_parts += L.wall_hole(mb, M, side + (0.02 if shape == 'sq' else 0.012), fb_h, T, hw_, hh_, stone,
                                       N=C.lod_pick(lod, 20, 12), hole=win[i], disp=lambda co, ri, k: rough(co) * 0.7)
            # washi panel set back in the opening, lattice bars proud of it (square windows)
            rot = (0, 0, a - math.pi / 2)
            pc = n * (apo - T * 0.62) + Vector((0, 0, zc))
            mb.box(pc, (hw_ * 1.12 if win[i] == 'sq' else hw_ * 1.08, 0.006, hh_ * 1.08), paper, rot=rot)
            if win[i] == 'sq':
                nb = C.lod_pick(lod, 2, 1)
                bw = 0.022
                for j in range(nb):
                    t = (j + 1) / (nb + 1) - 0.5
                    side_v = Vector((-math.sin(a), math.cos(a), 0))
                    mb.box(pc + side_v * (t * hw_) + n * 0.008, (bw, 0.016, hh_ * 1.04), wood, rot=rot)
                for j in range(nb):
                    t = (j + 1) / (nb + 1) - 0.5
                    mb.box(pc + Vector((0, 0, t * hh_)) + n * 0.008, (hw_ * 1.04, 0.016, bw), wood, rot=rot)
        # corner posts close the wall joints
        for i in range(nf):
            a = face_ang[i] + math.pi / nf
            rc = apo / math.cos(math.pi / nf)
            c = Vector((math.cos(a), math.sin(a), 0)) * (rc - T * 0.55)
            pf = []
            pr = T * 0.75
            rings = [(pr, z_fb0), (pr * 1.05, zc), (pr, z_fb1)]
            vs = []
            bm = mb.bm
            ring_vs = []
            for (r_, zz) in rings:
                rv = []
                for k in range(6):
                    t = 2 * math.pi * k / 6 + a
                    p = c + Vector((r_ * math.cos(t), r_ * math.sin(t), zz))
                    p += rough(p) * 0.6
                    rv.append(bm.verts.new(p))
                ring_vs.append(rv)
            for A_, B_ in zip(ring_vs[:-1], ring_vs[1:]):
                pf += C.bridge_rings(bm, A_, B_)
            pf.append(bm.faces.new(ring_vs[0][::-1])); pf.append(bm.faces.new(ring_vs[-1]))
            bmesh.ops.recalc_face_normals(bm, faces=pf)
            mb._tag(pf, stone)
            stone_parts += pf
    else:
        # solid box + glowing window quads just proud of each face
        stone_parts += loft(mb, [(hw(f_w), z_fb0), (hw(f_w), z_fb1)], N if lod == 2 else (4 if shape == 'sq' else 6),
                            stone, shape, ph if shape == 'hex' else (math.pi / 4 if lod == 3 or N == 4 else ph), None)
        bm = mb.bm
        sel = range(nf) if lod == 2 else [i for i in range(nf) if win[i] == 'sq' or nf == 4]
        for i in sel:
            a = face_ang[i]
            n = Vector((math.cos(a), math.sin(a), 0)); sv = Vector((-math.sin(a), math.cos(a), 0))
            c = n * (apo + 0.004) + Vector((0, 0, zc))
            ww = hole_w / 2 if win[i] == 'sq' else min(hole_w, hole_h) * 0.45
            hh = hole_h / 2 if win[i] == 'sq' else ww
            q = [bm.verts.new(c + sv * sx * ww + Vector((0, 0, sz * hh))) for sx, sz in ((1, -1), (-1, -1), (-1, 1), (1, 1))]
            f = bm.faces.new(q)
            if f.normal.dot(n) < 0:
                f.normal_flip()
            f.material_index = paper
    z = z_fb1
    # ---- cap (kasa): thick rough eave with lifted corners, concave slope, top boss
    half = W / 2 * span_k
    lft = lift if lod <= 2 else lift * 0.6
    _r3 = L.rough(seed + 3, 0.012 * amp, freq=7.0)

    def cap_rough(p):
        return _r3(p, 0, 0)
    if lod <= 1:
        cr = [(hw(f_w * 1.02), z - 0.005, 0), (hw(half * 0.9), z + eave_t * 0.15, lft * 0.7), (hw(half), z + eave_t * 0.55, lft),
              (hw(half * 0.99), z + eave_t, lft), (hw(half * 0.72), z + eave_t + rise * 0.22, lft * 0.35),
              (hw(half * 0.45), z + eave_t + rise * 0.6, 0.0), (hw(half * 0.26), z + eave_t + rise * 0.92, 0.0),
              (hw(half * 0.2), z + eave_t + rise, 0.0), (0.0, z + eave_t + rise + 0.005, 0.0)]
    elif lod == 2:
        cr = [(hw(f_w), z, 0), (hw(half), z + eave_t * 0.5, lft), (hw(half), z + eave_t, lft),
              (hw(half * 0.5), z + eave_t + rise * 0.62, 0), (hw(half * 0.2), z + eave_t + rise, 0), (0.0, z + eave_t + rise, 0)]
    else:
        cr = [(hw(half), z, lft), (hw(half), z + eave_t, lft), (0.0, z + eave_t + rise + fin_h * 0.9, 0)]
    stone_parts += loft(mb, cr, N, stone, shape, ph, cap_rough)
    # warabi: rough knobs riding on each lifted eave corner (LOD0-1)
    if lod <= 1:
        gk = C.rng(seed, 'knobs')
        nc = 4 if shape == 'sq' else 6
        for i in range(nc):
            a = (math.pi / 4 if shape == 'sq' else 0.0) + 2 * math.pi * i / nc
            rr = half * (_shape(shape, a) if shape == 'sq' else 1.0) * hexk * 0.97
            p = (rr * math.cos(a), rr * math.sin(a), z + eave_t + lft + 0.02)
            C.hull_rock(mb, p, (0.06, 0.06, 0.05), stone, gk, npts=C.lod_pick(lod, 10, 8))
    z_top = z + eave_t + rise
    # ---- finial: lotus collar (ukebana) + hoju jewel
    if lod <= 2:
        segs = C.lod_pick(lod, 16, 10, 6)
        fr = W / 2 * 0.2
        prof_u = [(fr * 0.75, 0), (fr * 1.05, fin_h * 0.12), (fr * 1.0, fin_h * 0.22), (fr * 0.6, fin_h * 0.27)]
        prof_h = [(fr * 0.6, fin_h * 0.25), (fr * 0.95, fin_h * 0.42), (fr * 1.0, fin_h * 0.55), (fr * 0.8, fin_h * 0.72),
                  (fr * 0.35, fin_h * 0.9), (0.0, fin_h)]
        if lod == 2:
            prof_h = [(fr * 0.95, fin_h * 0.4), (fr * 0.7, fin_h * 0.75), (0.0, fin_h)]
            prof_u = [(fr * 0.8, 0), (fr, fin_h * 0.2), (fr * 0.6, fin_h * 0.3)]
        _, f1 = C.lathe(mb, prof_u, segs, stone, base=(0, 0, z_top - 0.01))
        _, f2 = C.lathe(mb, prof_h, segs, stone, base=(0, 0, z_top - 0.01))
        stone_parts += f1 + f2

    # ---- moss on up-facing stone (positional noise -> the same patches at every LOD)
    if moss_k > 0:
        off = Vector((seed * 3.7 % 50, seed * 1.3 % 40, 11.0))
        thr = 0.35 - 0.7 * moss_k
        for f in stone_parts:
            if not f.is_valid:
                continue
            nz = f.normal.z
            c = f.calc_center_median()
            if nz > 0.45 and noise.noise(c * 2.6 + off) + 0.25 * noise.noise(c * 9.0 + off) > thr + (0.25 if c.z > H * 0.7 else 0.0) * (1 - moss_k):
                f.material_index = mossm
            elif lod == 0 and nz > 0.1 and c.z < H * 0.12 and noise.noise(c * 3.1 + off) > thr + 0.35:
                f.material_index = mossm
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=[C.light_entry(kz, color_k=2300, watts=25)],
                     kz_flicker=[paper],
                     kz_anim={'type': 'shader_flicker', 'slots': [paper], 'amount': 0.12, 'hz': [2.3, 5.7]},
                     kz_params=dict(style=style, h=round(H, 3), tiers=nt, span=round(span_k, 3), windows=windows,
                                    moss=moss_k, shape=shape))
    return o
