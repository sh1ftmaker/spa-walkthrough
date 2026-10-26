"""Kazan-yu material library: per-material data + procedural pattern generators.

Every pattern works in *tile space*: uv in [0,1) is exactly one texture repeat, and every
texture is sampled through B.torus() (a flat 4D torus), so all patterns tile seamlessly by
construction.  A pattern returns a dict of sockets:
    albedo (linear colour), rough, metal, height (0..1), ao (0..1),
    emission (colour, multiplied by EmitStrength in KZ_Core), foam (0..1), alpha (0..1)
Missing keys get defaults.  Patterns know nothing about the 7 artist settings; those are
applied afterwards by the shared KZ_Core group (see build_library.py), using only data that
is also baked into the web textures, so Blender and three.js can apply the same formulas.
"""
from kzdsl import blackbody_rgb, hexlin

LANTERN = blackbody_rgb(2700)
PAPER_GLOW = blackbody_rgb(2100)   # light through washi is filtered warmer than the bulb


# --------------------------------------------------------------------------- stone
def warp(b, t, amt=0.08, scale=3.0):
    """Domain-warp a torus coordinate with periodic noise (keeps tiling)."""
    vec, w = t
    n = b.noise4(t, scale=scale, detail=3, color=True)
    off = b.cmul(b.vmath('SUBTRACT', n, (0.5, 0.5, 0.5)), amt)
    return (b.vmath('ADD', vec, off), w)


def pat_basalt_dry(b, uv):
    t = b.torus(uv)
    large = b.noise4(t, scale=2.5, detail=7, rough=0.58)
    mid = b.noise4(t, scale=11, detail=5, rough=0.6, dist=0.25)
    fine = b.noise4(t, scale=70, detail=3, rough=0.6)
    vd = b.voronoi4(t, scale=75, feature='F1', rand=1.0)
    dens = b.noise4(t, scale=4, detail=2).smooth(0.38, 0.62)
    holes = (1.0 - vd.smooth(0.10, 0.26)) * dens
    vd2 = b.voronoi4(t, scale=140, feature='F1')
    pin = (1.0 - vd2.smooth(0.06, 0.16)) * 0.6
    crag = b.ridge(b.noise4(t, scale=6, detail=6, rough=0.62)) ** 2.0
    height = (large * 0.4 + mid * 0.3 + crag * 0.18 + fine * 0.14 - holes * 0.4 - pin * 0.12 + 0.06).clamp()
    shade = (large * 0.5 + mid * 0.3 + fine * 0.2)
    col = b.ramp(shade, [(0.25, (0.016, 0.0155, 0.015)), (0.75, (0.046, 0.044, 0.042))])
    ox = b.noise4(t, scale=1.6, detail=3).smooth(0.55, 0.75)
    col = b.mixc(ox * 0.25, col, (0.05, 0.038, 0.03))
    col = b.mixc(holes, col, (0.010, 0.010, 0.010))
    rough = (b.noise4(t, scale=20, detail=2) * 0.12 + 0.78 + holes * 0.08).clamp()
    ao = (1.0 - holes * 0.7 - pin * 0.3) * height.lin(0.0, 0.6, 0.7, 1.0)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def _facets(b, t, scale, amp):
    d, c, p, w, = b.voronoi4(t, scale=scale, feature='F1', out=['Distance', 'Color', 'Position', 'W'])
    vec, ww = t
    rc = b.vmath('SUBTRACT', c, (0.5, 0.5, 0.5))
    dv = b.vmath('SUBTRACT', vec, p)
    tilt = b.vmath('DOT_PRODUCT', rc, dv, out='Value') * (scale * 2.2)
    cr, cg, _ = b.rgb_sep(c)
    tilt = tilt + (ww - w) * (cg - 0.5) * (scale * 2.2)
    e = b.voronoi4(t, scale=scale, feature='DISTANCE_TO_EDGE')
    return (tilt + cr * 0.6) * amp, e, cr


def pat_basalt_wet(b, uv):
    t0 = b.torus(uv)
    t = warp(b, t0, 0.10, 2.5)
    f1, e1, cell = _facets(b, t, 5.0, 0.30)
    f2, e2, _ = _facets(b, warp(b, t0, 0.04, 9.0), 16.0, 0.14)
    lumps = b.noise4(t0, scale=4, detail=5, rough=0.6)
    crack = (1.0 - e1.smooth(0.0, 0.014)) * b.noise4(t0, scale=6).smooth(0.3, 0.55)
    crack2 = (1.0 - e2.smooth(0.0, 0.01)) * 0.35
    mid = b.noise4(t, scale=26, detail=4, rough=0.6)
    fine = b.noise4(t, scale=90, detail=2)
    t = t0
    height = (f1 + f2 + lumps * 0.3 + mid * 0.14 + fine * 0.05 + 0.18 - crack * 0.25 - crack2 * 0.1).clamp()
    col = b.ramp(cell * 0.6 + mid * 0.4, [(0.2, (0.016, 0.015, 0.014)), (0.8, (0.036, 0.031, 0.027))])
    speck = b.noise4(t, scale=150, detail=1).smooth(0.72, 0.8)
    col = b.mixc(speck * 0.5, col, (0.07, 0.065, 0.06))
    col = b.mixc(crack, col, (0.006, 0.006, 0.006))
    rough = (mid * 0.16 + 0.42 + crack * 0.3).clamp()
    ao = (1.0 - crack * 0.75 - crack2 * 0.4) * height.lin(0.0, 0.5, 0.75, 1.0)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_obsidian(b, uv):
    t = b.torus(uv)
    d1 = b.voronoi4(t, scale=3.2, feature='F1', rand=0.9)
    e1 = b.voronoi4(t, scale=3.2, feature='DISTANCE_TO_EDGE', rand=0.9)
    d2 = b.voronoi4(t, scale=11, feature='F1')
    ripple = (d1 * 46.0).sin() * 0.025 * d1.lin(0.05, 0.5)
    ridge = 1.0 - e1.smooth(0.0, 0.03)
    height = (0.75 - d1 * d1 * 1.1 - d2 * d2 * 0.25 + ripple + ridge * 0.12).clamp()
    tb = b.torus(uv, ax=0.25, ay=1.0)
    band = b.noise4(tb, scale=6, detail=4, dist=0.6)
    col = b.ramp(band, [(0.3, (0.0085, 0.0085, 0.0095)), (0.7, (0.0135, 0.0125, 0.0130))])
    smudge = b.noise4(t, scale=7, detail=5).smooth(0.5, 0.8)
    rough = smudge * 0.07 + 0.025
    ao = 1.0 - ridge * 0.0
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_rimstone(b, uv):
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    warp = b.noise4(t, scale=2.5, detail=3)
    layer = v * 11.0 + warp * 5.0
    band = ((layer * 6.2831853).sin() * 0.5 + 0.5) ** 4.0
    ts = b.torus(uv, ax=5.0, ay=0.6)
    streak = b.noise4(ts, scale=9, detail=4)
    lumpy = b.noise4(t, scale=14, detail=5, rough=0.55)
    pd = b.voronoi4(t, scale=90, feature='F1')
    pores = (1.0 - pd.smooth(0.05, 0.16)) * b.noise4(t, scale=6).smooth(0.45, 0.7)
    height = (band * 0.05 + lumpy * 0.52 + streak * 0.34 - pores * 0.3 + 0.06).clamp()
    col = b.ramp(lumpy * 0.85 + band * 0.15, [(0.15, (0.50, 0.44, 0.33)), (0.85, (0.74, 0.70, 0.60))])
    stain = (1.0 - band) * b.noise4(t, scale=3.5, detail=3).smooth(0.5, 0.75)
    col = b.mixc(stain * 0.55, col, (0.42, 0.30, 0.17))
    col = b.mixc(pores, col, (0.22, 0.18, 0.12))
    rough = (lumpy * 0.15 + 0.42 + pores * 0.25).clamp()
    ao = (1.0 - pores * 0.6) * height.lin(0.0, 0.6, 0.7, 1.0)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_black_sand(b, uv):
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    gd, gc = b.voronoi4(t, scale=170, feature='F1', out=['Distance', 'Color'])
    gr, gg, _ = b.rgb_sep(gc)
    grain = 1.0 - (gd * gd * 2.2).clamp()
    rip_n = b.noise4(t, scale=3, detail=3)
    ripple = ((v * 9.0 + rip_n * 1.8) * 6.2831853).sin() * 0.5 + 0.5
    lump = b.noise4(t, scale=12, detail=4)
    height = (ripple * 0.32 + lump * 0.3 + grain * 0.28 + 0.05).clamp()
    sparkle = gg.smooth(0.90, 0.93)
    col = b.ramp(gr * 0.6 + lump * 0.4, [(0.2, (0.017, 0.016, 0.015)), (0.85, (0.045, 0.041, 0.037))])
    col = b.mixc(sparkle, col, (0.09, 0.085, 0.07))
    rough = (0.88 - sparkle * 0.6 - grain * 0.04).clamp()
    ao = grain.lin(0.0, 0.6, 0.8, 1.0)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_ash_clay(b, uv):
    t = b.torus(uv)
    tw = warp(b, t, 0.06, 3.0)
    e1 = b.voronoi4(tw, scale=10, feature='DISTANCE_TO_EDGE', rand=0.95)
    e2 = b.voronoi4(tw, scale=28, feature='DISTANCE_TO_EDGE')
    crack = (1.0 - e1.smooth(0.0, 0.014)) * b.noise4(t, scale=4).smooth(0.4, 0.6)
    crack2 = (1.0 - e2.smooth(0.0, 0.012)) * b.noise4(t, scale=5).smooth(0.45, 0.65)
    curl = e1.smooth(0.0, 0.15)
    large = b.noise4(t, scale=3, detail=4)
    grain = b.noise4(t, scale=90, detail=2)
    height = (0.42 + large * 0.3 + grain * 0.1 + (1.0 - curl) * 0.04 - crack * 0.4 - crack2 * 0.15).clamp()
    col = b.ramp(large * 0.7 + grain * 0.3, [(0.2, (0.085, 0.081, 0.077)), (0.85, (0.15, 0.142, 0.132))])
    col = b.mixc(crack * 0.8 + crack2 * 0.4, col, (0.03, 0.028, 0.026))
    rough = (0.9 + grain * 0.06 - large * 0.04).clamp()
    ao = 1.0 - crack * 0.8 - crack2 * 0.4
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_paving(b, uv):
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    rows, cols = 4.0, 3.0
    y = v * rows
    r = y.floor()
    fy = y.fract()
    x = u * cols + b.white1(r + 101.0) * 0.8 + r.mod(2.0) * 0.1
    c = x.floor()
    fx = x.fract()
    cid = r * cols + c.mod(cols)
    rnd = b.white1(cid)
    rnd2 = b.white1(cid + 37.0)
    dx = fx.min(1.0 - fx) / cols
    dy = fy.min(1.0 - fy) / rows
    jn = b.noise4(t, scale=40, detail=2) * 0.002
    e = dx.min(dy) + jn
    joint = 1.0 - e.smooth(0.0025, 0.0045)
    bevel = e.smooth(0.004, 0.022)
    surf = b.noise4(t, scale=28, detail=6, rough=0.55)
    pits = 1.0 - b.voronoi4(t, scale=120, feature='F1').smooth(0.04, 0.14)
    pits = pits * b.noise4(t, scale=9).smooth(0.55, 0.75)
    tilt = (fx - 0.5) * (rnd2 - 0.5) * 0.12
    slab = 0.72 + (rnd - 0.5) * 0.08 + tilt - (1.0 - bevel) * 0.2 + surf * 0.16 - pits * 0.1
    height = b.mixf(joint, slab, 0.08).clamp()
    col = b.ramp(rnd, [(0.0, (0.024, 0.023, 0.022)), (0.5, (0.046, 0.043, 0.040)), (1.0, (0.085, 0.074, 0.062))])
    col = b.mixc(surf.lin(0.3, 0.7) * 0.35, col, (0.085, 0.080, 0.074))
    col = b.mixc(joint, col, (0.012, 0.011, 0.010))
    rough = (0.5 + surf * 0.18 + joint * 0.35 + pits * 0.15 - bevel * 0.04).clamp()
    ao = (1.0 - joint * 0.65) * (bevel * 0.2 + 0.8) * (1.0 - pits * 0.4)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


# --------------------------------------------------------------- wood, paper, cloth
def _grain(b, uv, rings, wobble, ax=0.06):
    """Straight grain along u.  Returns (latewood mask, ring index noise, streaks)."""
    u, v, _ = b.sep(uv)
    tl = b.torus(uv, ax=ax, ay=1.0)
    d = b.noise4(tl, scale=3, detail=3) - 0.5
    d2 = b.noise4(tl, scale=14, detail=2) - 0.5
    ring = v * rings + d * wobble + d2 * (wobble * 0.15)
    f = ring.fract()
    # growth ring: gradual earlywood -> latewood, sharp boundary to the next year's earlywood;
    # latewood share varies ring to ring (wide/narrow years)
    share = b.white1(ring.floor()) * 0.35 + 0.35
    late = f.lin(1.0 - share, 0.97) ** 1.6 * (1.0 - f.smooth(0.975, 1.0))
    ts = b.torus(uv, ax=0.02, ay=1.0)
    streak = b.noise4(ts, scale=260, detail=2).smooth(0.55, 0.75)
    return late, ring, streak


def pat_hinoki(b, uv):
    t = b.torus(uv)
    late, ring, streak = _grain(b, uv, 40.0, 5.0)
    weather = b.noise4(b.torus(uv, ax=0.3), scale=3, detail=4)
    band = b.noise4(b.torus(uv, ax=0.05, ay=1.0), scale=9, detail=3)
    col = b.ramp(late, [(0.0, (0.42, 0.275, 0.14)), (0.6, (0.33, 0.20, 0.095)), (1.0, (0.19, 0.10, 0.045))])
    col = b.mixc(band.lin(0.25, 0.75) * 0.7, col, (0.24, 0.145, 0.065))
    pores = b.noise4(b.torus(uv, ax=0.08, ay=1.0), scale=400, detail=1).smooth(0.62, 0.72)
    col = b.mixc(pores * 0.3, col, (0.18, 0.1, 0.045))
    col = b.mixc(weather.smooth(0.5, 0.8) * 0.35, col, (0.26, 0.21, 0.16))
    col = b.mixc(streak * 0.35, col, (0.22, 0.13, 0.06))
    fine = b.noise4(t, scale=160, detail=2)
    height = (0.42 + late * 0.32 - streak * 0.12 + fine * 0.1 + weather * 0.1).clamp()
    rough = (0.62 - late * 0.12 + streak * 0.05 + weather * 0.06).clamp()
    ao = 1.0 - streak * 0.25
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_lacquer(b, uv):
    t = b.torus(uv)
    late, ring, streak = _grain(b, uv, 45.0, 5.0)
    peel = b.noise4(t, scale=130, detail=2)
    col = b.ramp(late, [(0.0, (0.020, 0.0105, 0.0075)), (1.0, (0.030, 0.016, 0.010))])
    smudge = b.noise4(t, scale=5, detail=5).smooth(0.45, 0.8)
    height = (0.5 + late * 0.12 + peel * 0.08).clamp()
    rough = smudge * 0.08 + 0.10
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - streak * 0.1)


def pat_bamboo(b, uv):
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    nu = (u * 2.0).fract()
    dn = nu.min(1.0 - nu)
    ridge = 1.0 - dn.smooth(0.0, 0.016)
    band = 1.0 - dn.smooth(0.0, 0.07)
    fib = b.noise4(b.torus(uv, ax=0.04, ay=1.0), scale=150, detail=2)
    long = b.noise4(b.torus(uv, ax=0.3, ay=1.0), scale=4, detail=3)
    spots = b.noise4(t, scale=36, detail=3).smooth(0.70, 0.76) * b.noise4(t, scale=4).smooth(0.4, 0.7)
    col = b.ramp(long, [(0.2, (0.40, 0.30, 0.11)), (0.8, (0.52, 0.41, 0.17))])
    col = b.mixc(fib.lin(0.3, 0.7) * 0.25, col, (0.33, 0.24, 0.09))
    col = b.mixc(band * 0.55, col, (0.26, 0.17, 0.065))
    col = b.mixc(ridge * 0.6, col, (0.55, 0.45, 0.24))
    col = b.mixc(spots * 0.8, col, (0.10, 0.06, 0.03))
    height = (0.45 + ridge * 0.4 - band * 0.06 + fib * 0.06).clamp()
    rough = (0.34 + band * 0.12 + spots * 0.15).clamp()
    ao = 1.0 - band * 0.1 + ridge * 0.05
    return dict(albedo=col, rough=rough, height=height, ao=ao.clamp())


def pat_tatami(b, uv):
    u, v, _ = b.sep(uv)
    sv = v * 170.0
    sid = sv.floor()
    sf = sv.fract()
    prof = (sf * 3.14159265).sin() ** 0.55
    wu = u * 24.0
    wid = wu.floor()
    wf = wu.fract()
    dw = wf.min(1.0 - wf)
    par = (sid + wid).mod(2.0)
    dent = (1.0 - dw.smooth(0.0, 0.05)) * (par * 0.5 + 0.5)
    rnd = b.white1(sid)
    rnd2 = b.white1(sid * 1.0 + 911.0)
    along = b.noise4(b.torus(uv, ax=1.0, ay=40.0), scale=3, detail=2)
    shade = rnd * 0.7 + along * 0.3
    col = b.ramp(shade, [(0.0, (0.30, 0.235, 0.095)), (0.45, (0.42, 0.345, 0.15)),
                         (0.8, (0.40, 0.37, 0.15)), (1.0, (0.47, 0.40, 0.19))])
    col = b.mixc(dent * 0.45, col, (0.13, 0.10, 0.04))
    col = b.mixc((1.0 - prof) * 0.7, col, (0.14, 0.105, 0.045))
    height = (prof * 0.72 - dent * 0.32 + rnd2 * 0.06 + 0.2).clamp()
    rough = (0.55 + (1.0 - prof) * 0.2 + dent * 0.1).clamp()
    ao = (1.0 - (1.0 - prof) * 0.45) * (1.0 - dent * 0.45)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def _washi_core(b, uv):
    t = b.torus(uv)
    f1 = b.ridge(b.noise4(b.torus(uv, ax=0.3, ay=2.0), scale=22, detail=2)) ** 14.0
    f2 = b.ridge(b.noise4(b.torus(uv, ax=0.3, ay=2.0, rot=(1, 1, 1, -1)), scale=16, detail=2)) ** 14.0
    f3 = b.ridge(b.noise4(b.torus(uv, ax=2.0, ay=0.3, rot=(1, -1, 1, 1)), scale=16, detail=2)) ** 14.0
    f4 = b.ridge(b.noise4(b.torus(uv, ax=2.0, ay=0.3), scale=22, detail=2)) ** 14.0
    fib = f1.max(f2).max(f3).max(f4)
    cloud = b.noise4(t, scale=7, detail=6, rough=0.6)
    thick = (cloud * 0.55 + fib * 0.45 + 0.15).clamp()
    return t, fib, cloud, thick


def pat_washi(b, uv):
    t, fib, cloud, thick = _washi_core(b, uv)
    col = b.ramp(cloud, [(0.2, (0.66, 0.60, 0.48)), (0.8, (0.74, 0.69, 0.57))])
    col = b.mixc(fib * 0.6, col, (0.80, 0.76, 0.64))
    height = (cloud * 0.35 + fib * 0.5 + 0.1).clamp()
    rough = (0.86 - fib * 0.06).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - (1.0 - cloud) * 0.08)


def pat_noren(b, uv):
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    n = 96.0
    x = u * n
    y = v * n
    ix, iy, fx, fy = x.floor(), y.floor(), x.fract(), y.fract()
    par = (ix + iy).mod(2.0)
    pw = (fx * 3.14159265).sin() ** 0.6     # warp thread runs along v
    pf = (fy * 3.14159265).sin() ** 0.6     # weft thread runs along u
    slub_w = b.noise4(b.torus(uv, ax=n, ay=0.6), scale=1.0, detail=2)
    slub_f = b.noise4(b.torus(uv, ax=0.6, ay=n), scale=1.0, detail=2)
    hw = pw * (0.75 + slub_w * 0.3)
    hf = pf * (0.75 + slub_f * 0.3)
    height = (b.mixf(par, hf * 0.8 + 0.1 * pw, hw * 0.8 + 0.1 * pf)).clamp()
    fade = b.noise4(t, scale=3, detail=4)
    col = b.ramp(fade, [(0.25, (0.008, 0.013, 0.040)), (0.85, (0.016, 0.027, 0.068))])
    thread = b.mixf(par, slub_f, slub_w)
    col = b.mixc(thread.lin(0.3, 0.8) * 0.4, col, (0.035, 0.052, 0.105))
    col = b.mixc((1.0 - height).smooth(0.5, 1.0) * 0.7, col, (0.004, 0.006, 0.014))
    rough = (0.86 + (1.0 - height) * 0.1).clamp()
    ao = height.lin(0.0, 0.5, 0.55, 1.0)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


def pat_rope(b, uv):
    u, v, _ = b.sep(uv)
    s = v * 3.0 + u * 2.0
    sf = s.fract()
    prof = (sf * 3.14159265).sin() ** 0.7
    tf = b.torus(uv, ax=1.0, ay=0.05, rot=(2, 3, 3, -2))
    fib = b.noise4(tf, scale=45, detail=3)
    fib2 = b.ridge(b.noise4(tf, scale=18, detail=1)) ** 6.0
    tone = b.noise4(b.torus(uv), scale=4, detail=2)
    height = (prof * 0.72 + fib * 0.14 + fib2 * 0.08).clamp()
    col = b.ramp(fib * 0.6 + tone * 0.4, [(0.2, (0.24, 0.175, 0.075)), (0.8, (0.43, 0.345, 0.17))])
    col = b.mixc(fib2 * 0.5, col, (0.52, 0.44, 0.24))
    col = b.mixc((1.0 - prof).smooth(0.55, 1.0) * 0.55, col, (0.09, 0.065, 0.03))
    rough = (0.82 + (1.0 - prof) * 0.12).clamp()
    ao = prof.lin(0.0, 0.6, 0.35, 1.0)
    return dict(albedo=col, rough=rough, height=height, ao=ao)


# ------------------------------------------------------------- metal, ice, glass
def pat_iron(b, uv):
    t = b.torus(uv)
    d = b.voronoi4(t, scale=22, feature='F1')
    dimple = d.smooth(0.0, 0.7)
    mott = b.noise4(t, scale=8, detail=6)
    fine = b.noise4(t, scale=80, detail=3)
    height = (dimple * 0.4 + mott * 0.32 + fine * 0.12 + 0.1).clamp()
    rust = (b.noise4(t, scale=10, detail=8) * 0.7 + (1.0 - height) * 0.55).smooth(0.70, 0.80)
    col = b.ramp(mott, [(0.2, (0.030, 0.029, 0.028)), (0.8, (0.055, 0.050, 0.046))])
    col = b.mixc(rust, col, b.ramp(fine, [(0.3, (0.11, 0.035, 0.012)), (0.7, (0.20, 0.08, 0.025))]))
    metal = 0.45 - rust * 0.45
    rough = (0.52 + fine * 0.12 + rust * 0.3).clamp()
    height = (height + rust * 0.08).clamp()
    return dict(albedo=col, rough=rough, metal=metal, height=height, ao=height.lin(0.0, 0.5, 0.7, 1.0))


def pat_bronze(b, uv):
    t = b.torus(uv)
    mott = b.noise4(t, scale=6, detail=6)
    fine = b.noise4(t, scale=60, detail=3)
    pits = 1.0 - b.voronoi4(t, scale=70, feature='F1').smooth(0.03, 0.12)
    pits = pits * b.noise4(t, scale=5).smooth(0.5, 0.75)
    height = (mott * 0.55 + fine * 0.2 + 0.2 - pits * 0.25).clamp()
    verd = (b.noise4(t, scale=9, detail=7) * 0.6 + (1.0 - height) * 0.6 + pits * 0.3).smooth(0.62, 0.76)
    col = b.ramp(mott, [(0.2, (0.095, 0.068, 0.036)), (0.8, (0.18, 0.125, 0.06))])
    col = b.mixc(verd, col, (0.09, 0.21, 0.15))
    metal = 1.0 - verd
    rough = (0.36 + fine * 0.12 + verd * 0.4).clamp()
    return dict(albedo=col, rough=rough, metal=metal, height=height, ao=(1.0 - pits * 0.5))


def pat_glacier_ice(b, uv):
    t = b.torus(uv)
    d = b.voronoi4(t, scale=4.5, feature='F1', rand=0.9)
    e = b.voronoi4(t, scale=2.6, feature='DISTANCE_TO_EDGE', rand=0.8)
    e2 = b.voronoi4(t, scale=9, feature='DISTANCE_TO_EDGE')
    crack = 1.0 - e.smooth(0.0, 0.012)
    crack2 = (1.0 - e2.smooth(0.0, 0.008)) * b.noise4(t, scale=4).smooth(0.45, 0.65)
    frost = b.noise4(t, scale=3.5, detail=5).smooth(0.5, 0.72)
    fine = b.noise4(t, scale=40, detail=3)
    height = (0.8 - d * d * 1.2 + fine * 0.1 - crack * 0.15).clamp()
    col = b.ramp(frost, [(0.0, (0.80, 0.93, 0.98)), (1.0, (0.88, 0.95, 1.0))])
    rough = (0.03 + frost * 0.3 + crack * 0.25 + fine * 0.03).clamp()
    foam = (crack * 0.1 + crack2 * 0.06 + frost * 0.1).clamp()
    return dict(albedo=col, rough=rough, height=height, foam=foam)


def pat_lava_glass(b, uv):
    t = b.torus(uv)
    wave = b.noise4(t, scale=1.4, detail=2)
    d = b.voronoi4(t, scale=85, feature='F1')
    bub = (1.0 - d.smooth(0.02, 0.07)) * b.noise4(t, scale=3).smooth(0.6, 0.8)
    smudge = b.noise4(t, scale=6, detail=5).smooth(0.55, 0.85)
    height = (wave * 0.85 + bub * 0.12).clamp()
    rough = smudge * 0.06 + 0.008
    return dict(albedo=(0.98, 0.97, 0.95), rough=rough, height=height, foam=bub * 0.25)


# ------------------------------------------------------------------------- water
def pat_water_still(b, uv):
    t = b.torus(uv)
    n1 = b.noise4(t, scale=7, detail=3, rough=0.45)
    n2 = b.noise4(t, scale=26, detail=2)
    height = (n1 * 0.7 + n2 * 0.3).clamp()
    return dict(albedo=(0.95, 0.97, 0.97), rough=0.015, height=height, foam=0.0)


def pat_water_river(b, uv):
    t = b.torus(uv)
    tl = b.torus(uv, ax=0.45, ay=1.0)
    n1 = b.noise4(tl, scale=6, detail=4, rough=0.55, dist=0.4)
    n2 = b.noise4(t, scale=22, detail=3)
    height = (n1 * 0.7 + n2 * 0.3).clamp()
    streak = b.noise4(b.torus(uv, ax=0.25, ay=1.0), scale=10, detail=4, dist=0.3).smooth(0.62, 0.78)
    foam = (streak * b.noise4(t, scale=14, detail=3).smooth(0.4, 0.7) * 0.85).clamp()
    rough = 0.03 + foam * 0.5
    return dict(albedo=(0.92, 0.96, 0.96), rough=rough, height=height, foam=foam)


def pat_water_sea(b, uv):
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    wn = b.noise4(t, scale=2.5, detail=3)
    ph = (v * 5.0 + wn * 1.6).fract()
    crest = 1.0 - (ph - 0.5).abs() * 2.0
    swell = crest ** 2.2
    chop = b.noise4(t, scale=18, detail=4, rough=0.55)
    height = (swell * 0.6 + chop * 0.4).clamp()
    whitecap = (swell * 0.7 + chop * 0.5).smooth(0.78, 0.92) * b.noise4(t, scale=6, detail=3).smooth(0.4, 0.65)
    foam = whitecap.clamp()
    rough = 0.03 + foam * 0.5
    return dict(albedo=(0.92, 0.96, 0.97), rough=rough, height=height, foam=foam)


def pat_waterfall(b, uv):
    t = b.torus(uv)
    ts = b.torus(uv, ax=1.0, ay=0.07)
    streak = b.noise4(ts, scale=38, detail=4, rough=0.55)
    cloud = b.noise4(t, scale=5, detail=3).smooth(0.3, 0.7)
    aer = streak.smooth(0.30, 0.62)
    foam = (aer * (cloud * 0.5 + 0.5)).clamp()
    height = (streak * 0.8 + cloud * 0.2).clamp()
    return dict(albedo=(0.86, 0.91, 0.92), rough=0.05 + foam * 0.3, height=height, foam=foam,
                alpha=(foam * 0.7 + 0.3).clamp())


# ------------------------------------------------------------- light sources
def pat_lava(b, uv):
    t0 = b.torus(uv)
    vec, w = t0
    warp = b.noise4(t0, scale=3, detail=3, color=True)
    off = b.vmath('SUBTRACT', warp, (0.5, 0.5, 0.5))
    off = b.cmul(off, 0.09)
    t = (b.vmath('ADD', vec, off), w)
    e = b.voronoi4(t, scale=4.5, feature='DISTANCE_TO_EDGE', rand=1.0)
    d, c = b.voronoi4(t, scale=4.5, feature='F1', out=['Distance', 'Color'])
    cr, cg, _ = b.rgb_sep(c)
    chan = b.ridge(b.noise4(t0, scale=2.2, detail=4, rough=0.55)).smooth(0.95, 0.992)
    seam = 1.0 - e.smooth(0.0, 0.035 + cg * 0.035)
    crust_glow = b.noise4(t, scale=24, detail=3).smooth(0.74, 0.86) * 0.25
    heat = (seam.max(chan) + crust_glow * (cr * 0.5 + 0.5)).clamp()
    emis = b.ramp(heat, [(0.0, (0.0, 0.0, 0.0)), (0.25, (0.05, 0.003, 0.0)), (0.55, (0.55, 0.10, 0.004)),
                         (0.8, (1.0, 0.34, 0.02)), (1.0, (1.0, 0.68, 0.22))])
    crustn = b.noise4(t, scale=16, detail=5)
    crust = b.ramp(crustn, [(0.2, (0.020, 0.017, 0.016)), (0.8, (0.050, 0.040, 0.034))])
    col = b.mixc(heat.smooth(0.2, 0.7), crust, (0.30, 0.07, 0.015))
    height = (0.72 - heat * 0.55 + crustn * 0.22 + (1.0 - d) * 0.05).clamp()
    rough = (0.85 - heat * 0.4).clamp()
    return dict(albedo=col, rough=rough, height=height, emission=emis, ao=1.0 - heat * 0.0)


def pat_neon(b, uv):
    t = b.torus(uv)
    n = b.noise4(t, scale=6, detail=2)
    e = b.cmul((1.0, 1.0, 1.0), n * 0.08 + 0.92)
    return dict(albedo=(0.12, 0.12, 0.12), rough=0.06, height=n * 0.2 + 0.4, emission=e)


def pat_lantern_paper(b, uv):
    t, fib, cloud, thick = _washi_core(b, uv)
    col = b.ramp(cloud, [(0.2, (0.66, 0.60, 0.48)), (0.8, (0.74, 0.69, 0.57))])
    col = b.mixc(fib * 0.6, col, (0.80, 0.76, 0.64))
    glow = (1.25 - thick) .clamp() * 0.6 + 0.4
    emis = b.cmul(PAPER_GLOW, glow)
    height = (cloud * 0.35 + fib * 0.5 + 0.1).clamp()
    return dict(albedo=col, rough=0.86, height=height, emission=emis)


# ------------------------------------------------------------------- the library
# tile = metres per repeat at scale default; res = bake size; mode: 'proc' (live procedural
# in library.blend) or 'image' (library samples the baked tiling textures).
# core = constants for KZ_Core; params = defaults of the 7 artist settings.
WATER_CORE = dict(Transmission=1.0, IOR=1.333, Specular=0.5, Porosity=0.0, FoamColor=(0.80, 0.85, 0.85))

MATERIALS = [
    # ---- stone
    dict(id='basalt_dry', name='Dry basalt', category='stone', tile=2.0, res=512, mode='proc',
         pattern=pat_basalt_dry, depth=0.10,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.8, WornColor=(0.07, 0.066, 0.062), WornRough=0.45),
         concept=['22-brand-board.jpg (BASALT swatch)', '04-arrival-gate.jpg', '19-thunder-curtain.jpg'],
         three=dict(env=0.6)),
    dict(id='basalt_wet', name='Wet basalt', category='stone', tile=1.5, res=1024, mode='proc',
         pattern=pat_basalt_wet, depth=0.06,
         params=dict(wetness=0.9, wear=0.0),
         core=dict(Porosity=0.6, WornColor=(0.05, 0.046, 0.043), WornRough=0.3),
         concept=['16-steam-grotto.jpg', '05-mist-corridor.jpg', '17-glacier-plunge.jpg'],
         three=dict(env=1.0)),
    dict(id='obsidian', name='Polished obsidian', category='stone', tile=1.0, res=1024, mode='proc',
         pattern=pat_obsidian, depth=0.035,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(IOR=1.49, Specular=0.55, Porosity=0.0, WornColor=(0.03, 0.03, 0.032), WornRough=0.25),
         concept=['22-brand-board.jpg (OBSIDIAN swatch)', '17-glacier-plunge.jpg (obsidian monolith)', '15-obsidian-mirror.jpg'],
         three=dict(env=1.3)),
    dict(id='rimstone', name='Rimstone / travertine', category='stone', tile=1.5, res=512, mode='proc',
         pattern=pat_rimstone, depth=0.03,
         params=dict(wetness=0.45, wear=0.0),
         core=dict(Porosity=0.5, WornColor=(0.78, 0.75, 0.66), WornRough=0.3),
         concept=['18-rimstone-terraces.jpg'],
         three=dict(env=0.8)),
    dict(id='black_sand', name='Black sand', category='stone', tile=1.0, res=512, mode='proc',
         pattern=pat_black_sand, depth=0.012,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, WornColor=(0.03, 0.028, 0.026), WornRough=0.8),
         concept=['20-wave-grotto.jpg'],
         three=dict(env=0.5)),
    dict(id='ash_clay', name='Ash clay', category='stone', tile=2.0, res=512, mode='proc',
         pattern=pat_ash_clay, depth=0.012,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, WornColor=(0.24, 0.225, 0.21), WornRough=0.7),
         concept=['22-brand-board.jpg (tea cup / ash-glaze tones)', '16-steam-grotto.jpg'],
         three=dict(env=0.4)),
    dict(id='paving', name='Worn paving', category='stone', tile=2.0, res=1024, mode='proc',
         pattern=pat_paving, depth=0.02,
         params=dict(wetness=0.35, wear=0.3),
         core=dict(Porosity=0.7, WornColor=(0.085, 0.08, 0.075), WornRough=0.28),
         concept=['16-steam-grotto.jpg (wet flagstones)', '04-arrival-gate.jpg (lobby floor)'],
         three=dict(env=0.9)),
    # ---- wood, paper, cloth
    dict(id='hinoki', name='Hinoki (aged)', category='wood_paper_cloth', tile=0.5, res=1024, mode='image',
         pattern=pat_hinoki, depth=0.0012,
         params=dict(wetness=0.0, wear=0.15),
         core=dict(Porosity=0.8, WornColor=(0.36, 0.30, 0.22), WornRough=0.55, Specular=0.45),
         concept=['05-mist-corridor.jpg (shoji frames, posts)', '04-arrival-gate.jpg (shoe lockers)', '16-steam-grotto.jpg (bucket, sign post)'],
         three=dict(env=0.5)),
    dict(id='lacquer_dark', name='Lacquered dark wood (urushi)', category='wood_paper_cloth', tile=1.0, res=512, mode='image',
         pattern=pat_lacquer, depth=0.0006,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.0, Coat=1.0, CoatRough=0.04, WornColor=(0.20, 0.035, 0.02), WornRough=0.3),
         concept=['06-kawagiri-restaurant.jpg (dark deck timbers)', '21-private-suite.jpg (dark frames, table)'],
         three=dict(env=1.0, clearcoat=1.0, clearcoatRoughness=0.04)),
    dict(id='bamboo', name='Bamboo', category='wood_paper_cloth', tile=0.5, res=512, mode='image',
         pattern=pat_bamboo, depth=0.003,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.3, WornColor=(0.55, 0.46, 0.26), WornRough=0.3),
         concept=['04-arrival-gate.jpg (bamboo spout)', '22-brand-board.jpg'],
         three=dict(env=0.7)),
    dict(id='tatami', name='Tatami', category='wood_paper_cloth', tile=0.5, res=1024, mode='image',
         pattern=pat_tatami, depth=0.0025,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.9, Sheen=0.25, WornColor=(0.50, 0.43, 0.24), WornRough=0.45),
         concept=['21-private-suite.jpg (tatami floor)'],
         three=dict(env=0.4, sheen=0.25)),
    dict(id='washi', name='Washi paper', category='wood_paper_cloth', tile=0.5, res=512, mode='image',
         pattern=pat_washi, depth=0.0008,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Translucency=0.3, WornColor=(0.62, 0.56, 0.44), WornRough=0.9),
         concept=['05-mist-corridor.jpg (shoji panels)', '22-brand-board.jpg (menu card)'],
         three=dict(env=0.3)),
    dict(id='washi_backlit', name='Washi, back-lit (lantern shade)', category='wood_paper_cloth', tile=0.5, res=512,
         mode='image', pattern=pat_washi, tex_from='washi', depth=0.0008,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Translucency=0.72, WornColor=(0.62, 0.56, 0.44), WornRough=0.9),
         preview=dict(backlight=True),
         concept=['22-brand-board.jpg (paper lantern)', '12-lava-tube-lazy-river.jpg (floating lanterns)'],
         three=dict(env=0.3, note='Web: translucency is baked; at runtime use lantern_paper (emissive) for lit shades.')),
    dict(id='noren', name='Noren cloth (indigo)', category='wood_paper_cloth', tile=0.25, res=512, mode='image',
         pattern=pat_noren, depth=0.0012,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Sheen=0.15, Translucency=0.08, WornColor=(0.06, 0.08, 0.13), WornRough=0.9),
         concept=['09-neon-ramen-counter.jpg (noren curtains)', '22-brand-board.jpg (indigo robe)'],
         three=dict(env=0.3, sheen=0.15, sheenColor=(0.25, 0.30, 0.45))),
    dict(id='rope', name='Rope (straw, twisted)', category='wood_paper_cloth', tile=0.3, res=512, mode='image',
         pattern=pat_rope, depth=0.012,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Sheen=0.2, WornColor=(0.45, 0.38, 0.22), WornRough=0.85),
         concept=['22-brand-board.jpg (braided cord)', '04-arrival-gate.jpg (torii)'],
         three=dict(env=0.3)),
    # ---- metal, ice, glass
    dict(id='iron', name='Iron (black patina)', category='metal_ice_glass', tile=0.5, res=512, mode='proc',
         pattern=pat_iron, depth=0.002,
         params=dict(wetness=0.0, wear=0.15),
         core=dict(Porosity=0.3, WornColor=(0.40, 0.40, 0.41), WornRough=0.28, WornMetal=1.0),
         concept=['04-arrival-gate.jpg (lantern frames)', '17-glacier-plunge.jpg (handrail)'],
         three=dict(env=1.0)),
    dict(id='bronze', name='Bronze', category='metal_ice_glass', tile=0.5, res=512, mode='proc',
         pattern=pat_bronze, depth=0.0015,
         params=dict(wetness=0.0, wear=0.25),
         core=dict(Porosity=0.2, WornColor=(0.80, 0.52, 0.27), WornRough=0.2, WornMetal=1.0),
         concept=['04-arrival-gate.jpg (bronze spout, fittings)', '22-brand-board.jpg (bucket hoops)'],
         three=dict(env=1.0)),
    dict(id='glacier_ice', name='Glacier ice', category='metal_ice_glass', tile=2.0, res=512, mode='proc',
         pattern=pat_glacier_ice, depth=0.04, transparent=True,
         params=dict(wetness=0.3, wear=0.0),
         core=dict(Transmission=1.0, IOR=1.31, Specular=0.5, Porosity=0.0, FoamColor=(0.86, 0.94, 1.0),
                   Absorb=(0.25, 0.72, 0.95), AbsorbDensity=8.0, Scatter=(0.45, 0.78, 1.0), ScatterDensity=3.0),
         concept=['17-glacier-plunge.jpg (ice cave, icicles)'],
         three=dict(env=1.0, transmission=1.0, ior=1.31, thickness=0.5, attenuationColor=(0.55, 0.86, 0.97),
                    attenuationDistance=0.45)),
    dict(id='lava_glass', name='Thick lava glass', category='metal_ice_glass', tile=1.0, res=512, mode='proc',
         pattern=pat_lava_glass, depth=0.004, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Transmission=1.0, IOR=1.5, Specular=0.5, Porosity=0.0, FoamColor=(0.9, 0.9, 0.9),
                   Absorb=(0.80, 0.70, 0.55), AbsorbDensity=3.0),
         concept=['13-magma-glass-slide.jpg (glass wall, glass tube)', '04-arrival-gate.jpg (lava window)'],
         three=dict(env=1.2, transmission=1.0, ior=1.5, thickness=0.15, attenuationColor=(0.80, 0.70, 0.55),
                    attenuationDistance=0.33)),
    # ---- water
    dict(id='water_still', name='Still water', category='water', tile=4.0, res=512, mode='proc',
         pattern=pat_water_still, depth=0.004, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, Absorb=(0.02, 0.74, 0.86), AbsorbDensity=2.0, Scatter=(0.45, 0.9, 1.0),
                   ScatterDensity=0.02),
         concept=['15-obsidian-mirror.jpg', '05-mist-corridor.jpg', '17-glacier-plunge.jpg'],
         three=dict(env=1.0, transmission=1.0, ior=1.333, thickness=1.0, attenuationColor=(0.02, 0.74, 0.86),
                    attenuationDistance=0.5)),
    dict(id='water_river', name='River water', category='water', tile=3.0, res=512, mode='proc',
         pattern=pat_water_river, depth=0.03, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, Absorb=(0.0, 0.74, 0.88), AbsorbDensity=1.8, Scatter=(0.4, 0.9, 1.0),
                   ScatterDensity=0.25),
         concept=['12-lava-tube-lazy-river.jpg', '06-kawagiri-restaurant.jpg'],
         three=dict(env=1.0, transmission=1.0, ior=1.333, thickness=1.0, attenuationColor=(0.0, 0.74, 0.88),
                    attenuationDistance=0.55)),
    dict(id='water_sea', name='Sea water', category='water', tile=6.0, res=512, mode='proc',
         pattern=pat_water_sea, depth=0.18, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, Absorb=(0.0, 0.66, 0.76), AbsorbDensity=2.5, Scatter=(0.5, 0.85, 0.9),
                   ScatterDensity=0.15),
         concept=['20-wave-grotto.jpg'],
         three=dict(env=1.0, transmission=1.0, ior=1.333, thickness=1.5, attenuationColor=(0.0, 0.66, 0.76),
                    attenuationDistance=0.4)),
    dict(id='waterfall', name='Waterfall sheet', category='water', tile=2.0, res=512, mode='proc',
         pattern=pat_waterfall, depth=0.02, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, ThinWall=1.0, Absorb=(0.3, 0.85, 0.8), AbsorbDensity=0.0),
         concept=['19-thunder-curtain.jpg', '06-kawagiri-restaurant.jpg (water curtains)'],
         three=dict(env=0.8, transparent=True, opacityFromBaseAlpha='0.3 + 0.7*a', depthWrite=False)),
    # ---- light sources
    dict(id='lava', name='Lava (molten, crusted)', category='light', tile=2.0, res=512, mode='proc',
         pattern=pat_lava, depth=0.05, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=0.0, EmitStrength=1.3, WornColor=(0.05, 0.04, 0.035), WornRough=0.8),
         concept=['13-magma-glass-slide.jpg (lava behind glass)', '04-arrival-gate.jpg (lava falls)'],
         three=dict(env=0.4)),
    dict(id='neon_tube', name='Neon tube', category='light', tile=0.2, res=512, mode='proc',
         pattern=pat_neon, depth=0.0005, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0, tint=hexlin('#ff1f8f')),
         core=dict(Porosity=0.0, EmitStrength=1.1, Specular=0.5),
         variants=dict(cyan=dict(tint=hexlin('#18e8ff'))),
         concept=['09-neon-ramen-counter.jpg (magenta/cyan neon)', '06-kawagiri-restaurant.jpg'],
         three=dict(env=0.5, note='Kawagiri only. tint = emissive colour; cyan variant tint #18e8ff.')),
    dict(id='lantern_paper', name='Lantern paper (emissive)', category='light', tile=0.5, res=512, mode='proc',
         pattern=pat_lantern_paper, depth=0.0008, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=1.0, EmitStrength=1.0, Translucency=0.0),
         concept=['22-brand-board.jpg (paper lantern)', '05-mist-corridor.jpg', '12-lava-tube-lazy-river.jpg'],
         three=dict(env=0.2)),
]

# category -> concept crops shown next to it on the contact sheet: (image, (left, top, right, bottom) fractions)
CATEGORIES = [
    ('stone', 'Stone', [('16-steam-grotto.jpg', (0.0, 0.55, 0.62, 1.0)),
                        ('22-brand-board.jpg', (0.0, 0.25, 0.23, 0.68))]),
    ('wood_paper_cloth', 'Wood, paper & cloth', [('05-mist-corridor.jpg', (0.0, 0.0, 0.42, 0.62)),
                                                ('21-private-suite.jpg', (0.0, 0.5, 0.5, 1.0))]),
    ('metal_ice_glass', 'Metal, ice & glass', [('17-glacier-plunge.jpg', (0.0, 0.0, 0.70, 0.62))]),
    ('water', 'Water', [('18-rimstone-terraces.jpg', (0.30, 0.45, 1.0, 1.0))]),
    ('light', 'Light sources', [('13-magma-glass-slide.jpg', (0.55, 0.0, 1.0, 0.75)),
                                ('09-neon-ramen-counter.jpg', (0.58, 0.1, 0.72, 0.42))]),
]
