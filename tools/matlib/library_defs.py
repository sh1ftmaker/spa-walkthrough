"""Kazan-yu material library: per-material data + procedural pattern generators (round 2).

Every pattern works in *tile space*: uv in [0,1) is one texture repeat, sampled through
B.torus() (a flat 4D torus), so every pattern tiles exactly.  A tile may be non-square:
`tile` is metres along u and `tile / aspect` metres along v (use b.torus(uv, ax, ay) with
ay = ax * aspect... see iso()).

A pattern returns a dict of sockets (missing keys get defaults):
    albedo (linear colour)   rough   metal   height (0..1)   ao (0..1, pattern occlusion;
    the bake multiplies in a cavity term computed from height)   emission (colour)
    mask  (base.a: foam for water/ice/glass, thinness for paper, coverage for decals)
    wet   (nh.a: where a water film collects when wetness > 0; hollows are added by KZ_Core)

Round 2 (review r1): detail is carried by albedo (+-10-20 % at 2-3 scales), roughness
(wet pockets vs dry tops) and occlusion, not only by the normal map; Voronoi crack networks
are gone from basalt, obsidian, ice, lava and clay; large areas also get the shared 8 m
macro texture (KZ_Core input Macro, MacroAmount per material).
"""
from kzdsl import blackbody_rgb, hexlin

LANTERN = blackbody_rgb(2700)
PAPER_GLOW = blackbody_rgb(2100)
EDGE_GLOW = blackbody_rgb(1800)
TAU = 6.2831853


# ------------------------------------------------------------------ shared helpers
def iso(b, uv, aspect=1.0, f=1.0):
    """Metric-isotropic torus for a tile `aspect` times longer in u than in v."""
    return b.torus(uv, ax=f, ay=f / aspect)


def warp(b, t, amt=0.08, scale=3.0):
    """Domain-warp a torus coordinate with periodic noise (keeps tiling)."""
    vec, w = t
    n = b.noise4(t, scale=scale, detail=3, color=True)
    off = b.cmul(b.vmath('SUBTRACT', n, (0.5, 0.5, 0.5)), amt)
    return (b.vmath('ADD', vec, off), w)


def facets(b, t, scale, amp):
    """Piecewise-planar chips: each Voronoi cell gets its own tilted plane (no outlines).

    Returns (height, distance-to-edge, cell random 0..1)."""
    d, c, p, w = b.voronoi4(t, scale=scale, feature='F1', out=['Distance', 'Color', 'Position', 'W'])
    vec, ww = t
    rc = b.vmath('SUBTRACT', c, (0.5, 0.5, 0.5))
    dv = b.vmath('SUBTRACT', vec, p)
    tilt = b.vmath('DOT_PRODUCT', rc, dv, out='Value') * (scale * 2.2)
    cr, cg, _ = b.rgb_sep(c)
    tilt = tilt + (ww - w) * (cg - 0.5) * (scale * 2.2)
    e = b.voronoi4(t, scale=scale, feature='DISTANCE_TO_EDGE')
    return tilt * amp, e, cr


def jitter(b, t, scale):
    """Per-grain random 0..1 (Voronoi cell colour) at `scale` cells per repeat."""
    _, c = b.voronoi4(t, scale=scale, feature='F1', out=['Distance', 'Color'])
    r, g, bb = b.rgb_sep(c)
    return r, g, bb


def holes(b, t, scale, lo, hi):
    """Round pits: 1 inside, 0 outside (F1 distance below lo..hi)."""
    return 1.0 - b.voronoi4(t, scale=scale, feature='F1').smooth(lo, hi)


def cracks(b, t, scale, lo, hi, detail=2):
    """Meandering hairline cracks from ridged noise (not a cell network)."""
    return b.ridge(b.noise4(t, scale=scale, detail=detail, rough=0.5)).smooth(lo, hi)


def streaks_v(b, uv, aspect, across, along, lo, hi):
    """Vertical (along v) streaks: `across` features per repeat in u, stretched along v."""
    return b.noise4(b.torus(uv, ax=1.0, ay=along / across / aspect), scale=across, detail=3).smooth(lo, hi)


def cmul3(b, c, f):
    return b.cmul(c, f)


# --------------------------------------------------------------------------- stone
def pat_basalt(b, uv):
    """One set for basalt_dry and basalt_wet (2 m tile).  Vesicular cool-neutral basalt:
    vesicles 2-15 mm (a few to 30 mm), per-grain jitter, feldspar/olivine flecks, 5-20 cm
    conchoidal chips, sparse 0.3-1 m fractures (groove + AO, no albedo outline), vertical
    drip/run-off streaks (darker, wetter) and rare pale efflorescence."""
    t = b.torus(uv)
    large = b.noise4(t, scale=1.5, detail=6, rough=0.55)
    e1, c1 = b.voronoi4(warp(b, t, 0.05, 3.0), scale=12.0, feature='DISTANCE_TO_EDGE', out=['Distance', 'Color'])
    cell, _, _ = b.rgb_sep(b.voronoi4(warp(b, t, 0.05, 3.0), scale=12.0, feature='F1', out='Color'))
    chips = (0.35 - e1.min(0.35)) * 0.28 + cell * 0.04  # conchoidal scoops meeting at sharp ridges
    e2 = b.voronoi4(warp(b, t, 0.03, 7.0), scale=30.0, feature='DISTANCE_TO_EDGE')
    chips2 = (0.3 - e2.min(0.3)) * 0.09
    mid = b.noise4(warp(b, t, 0.04, 2.0), scale=9, detail=5, rough=0.6)
    fine = b.noise4(t, scale=140, detail=3)
    dens = b.noise4(t, scale=3, detail=2).smooth(0.35, 0.65)
    v1 = holes(b, t, 300, 0.07, 0.17) * dens
    v2 = holes(b, t, 120, 0.09, 0.2) * (dens * 0.7 + 0.15)
    v3 = holes(b, t, 40, 0.05, 0.12) * b.noise4(t, scale=4).smooth(0.62, 0.72)
    hole = v1.max(v2).max(v3)
    frac = cracks(b, warp(b, t, 0.12, 1.4), 1.6, 0.988, 0.998) * b.noise4(t, scale=2.2).smooth(0.56, 0.64)
    drip = streaks_v(b, uv, 1.0, 22, 2.0, 0.64, 0.76) * b.noise4(t, scale=3).smooth(0.35, 0.7)
    efflo = streaks_v(b, uv, 1.0, 9, 1.6, 0.78, 0.86) * b.noise4(t, scale=2).smooth(0.6, 0.75)
    height = (large * 0.45 + chips + chips2 + mid * 0.2 + fine * 0.05 + 0.18
              - hole * 0.32 - frac * 0.3 - drip * 0.03).clamp()
    gr, gg, _ = jitter(b, t, 520)
    tone = (gr - 0.5) * 0.45 + (mid - 0.5) * 0.6 + (large - 0.5) * 0.45 + (cell - 0.5) * 0.15 + 1.0
    col = b.cmul((0.021, 0.023, 0.027), tone)
    col = b.mixc(gg.smooth(0.982, 0.99) * 0.8, col, (0.13, 0.13, 0.12))         # feldspar
    col = b.mixc(gr.smooth(0.988, 0.995) * 0.7, col, (0.05, 0.075, 0.035))     # olivine
    col = b.mixc(hole * 0.75, col, (0.006, 0.006, 0.007))
    col = b.cmul(col, 1.0 - drip * 0.3)
    col = b.mixc(efflo * 0.35, col, (0.16, 0.16, 0.15))
    rough = (0.70 + (mid - 0.5) * 0.25 + (gr - 0.5) * 0.08 + hole * 0.15 + frac * 0.1 - drip * 0.3
             - efflo * 0.05).clamp()
    ao = (1.0 - hole * 0.75) * (1.0 - frac * 0.6)
    film = (b.noise4(warp(b, t, 0.05, 2.0), scale=8, detail=3).smooth(0.48, 0.66) * 0.8
            + drip * 0.9 + hole * 0.6).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=ao, wet=film)


def pat_obsidian(b, uv):
    """Large flat conchoidal facets 8-40 cm with crisp ridges, faint concentric ripple arcs on
    some facets, flat black with a smoky warm tint at thin edges (2 m tile)."""
    t = b.torus(uv)
    tw = warp(b, t, 0.04, 1.5)
    f1, e1, c1 = facets(b, tw, 6.5, 0.55)
    f2, e2, c2 = facets(b, warp(b, t, 0.03, 4.0), 15.0, 0.06)
    d1 = b.voronoi4(tw, scale=6.5, feature='F1')
    ring_on = c1.smooth(0.55, 0.62)
    ripple = ((d1 * (TAU * 40.0)).sin() * 0.5 + 0.5) * d1.lin(0.05, 0.35) * ring_on
    ridge1 = 1.0 - e1.smooth(0.0, 0.01)
    ridge2 = (1.0 - e2.smooth(0.0, 0.008)) * 0.6
    height = (f1 + f2 + ripple * 0.012 + ridge1 * 0.02 + 0.3).clamp()
    edge = (1.0 - e1.smooth(0.0, 0.05)).max(ridge2)
    col = b.cmul((0.0085, 0.0088, 0.0098), (c2 - 0.5) * 0.12 + 1.0)
    col = b.mixc(edge * 0.15, col, (0.032, 0.02, 0.014))
    rough = (0.025 + c1 * 0.025 + c2 * 0.01 + edge * 0.1 + ripple * 0.02).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - ridge2 * 0.3, wet=0.0)


def pat_rimstone_top(b, uv):
    """Tops: micro-gours (scalloped rim terraces 2-10 cm) with raised white crust rims and
    water-filled pockets; cream white, teal-grey in the wet lows, a few ochre bands."""
    t = b.torus(uv)
    tw = warp(b, t, 0.06, 2.0)
    e = b.voronoi4(tw, scale=24, feature='DISTANCE_TO_EDGE', rand=0.95)
    e2 = b.voronoi4(warp(b, t, 0.03, 6.0), scale=70, feature='DISTANCE_TO_EDGE')
    rim = 1.0 - e.smooth(0.0, 0.09)
    rim2 = (1.0 - e2.smooth(0.0, 0.08)) * 0.45
    bowl = e.smooth(0.05, 0.4)
    lumpy = b.noise4(t, scale=30, detail=5, rough=0.6)
    height = (0.35 + rim * 0.4 + rim2 * 0.15 - bowl * 0.15 + lumpy * 0.12).clamp()
    pool = bowl * (1.0 - rim) * b.noise4(t, scale=6).smooth(0.3, 0.6)
    col = b.cmul((0.74, 0.72, 0.66), (lumpy - 0.5) * 0.18 + 1.0)
    col = b.mixc(rim * 0.6, col, (0.86, 0.85, 0.80))
    col = b.mixc(pool * 0.7, col, (0.42, 0.55, 0.53))
    ochre = b.noise4(b.torus(uv, ax=0.3, ay=1.0), scale=5, detail=3).smooth(0.62, 0.72)
    col = b.mixc(ochre * 0.45, col, (0.55, 0.36, 0.17))
    rough = (0.5 - rim * 0.25 - pool * 0.4 + lumpy * 0.08).clamp()
    film = (pool + rim * 0.6).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - pool * 0.2, wet=film)


def pat_rimstone_side(b, uv):
    """Vertical faces: flowstone drapery, drip flutes 1-4 cm and bulbous drips; wet glossy
    flute ridges and tips, semi-matte crust between."""
    t = b.torus(uv)
    fl = b.ridge(b.noise4(warp(b, b.torus(uv, ax=1.0, ay=0.12), 0.05, 2.0), scale=55, detail=2))
    fl2 = b.ridge(b.noise4(b.torus(uv, ax=1.0, ay=0.2), scale=18, detail=2))
    d, c = b.voronoi4(warp(b, b.torus(uv, ax=1.0, ay=0.35), 0.04, 3.0), scale=30, feature='F1',
                      out=['Distance', 'Color'])
    cr, _, _ = b.rgb_sep(c)
    blob = (1.0 - d.smooth(0.15, 0.5)) * cr.smooth(0.55, 0.7)
    lumpy = b.noise4(t, scale=25, detail=5)
    height = (fl ** 1.5 * 0.45 + fl2 * 0.2 + blob * 0.25 + lumpy * 0.12).clamp()
    col = b.cmul((0.76, 0.73, 0.66), (lumpy - 0.5) * 0.2 + (fl - 0.5) * 0.12 + 1.0)
    groove = (1.0 - fl).smooth(0.55, 0.95)
    col = b.mixc(groove * 0.5, col, (0.47, 0.52, 0.5))
    ochre = b.noise4(b.torus(uv, ax=1.0, ay=0.15), scale=6, detail=3).smooth(0.62, 0.72)
    col = b.mixc(ochre * 0.5, col, (0.56, 0.37, 0.18))
    rough = (0.5 - fl.smooth(0.7, 0.95) * 0.35 - blob * 0.3 + groove * 0.05).clamp()
    film = (fl.smooth(0.7, 0.95) + blob + groove * 0.4).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - groove * 0.35, wet=film)


def pat_black_sand(b, uv):
    """Near-black volcanic sand (sRGB 25-35), per-grain jitter, 0.5-1 % glassy grains as
    low roughness only, irregular ripples ~0.7 m, footprint dimples, damp patches (2 m tile)."""
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    gd, gc = b.voronoi4(t, scale=700, feature='F1', out=['Distance', 'Color'])
    gr, gg, gb = b.rgb_sep(gc)
    grain = 1.0 - (gd * gd * 2.2).clamp()
    rn = b.noise4(warp(b, t, 0.08, 1.5), scale=2.0, detail=3)
    ripple = ((v * 3.0 + u * 0.0 + rn * 2.2) * TAU).sin() * 0.5 + 0.5
    ripple = ripple * b.noise4(t, scale=2.5).smooth(0.3, 0.7)
    fp = holes(b, warp(b, t, 0.04, 4.0), 6, 0.0, 0.14) * b.noise4(t, scale=3).smooth(0.6, 0.7)
    lump = b.noise4(t, scale=14, detail=4)
    height = (ripple * 0.3 + lump * 0.22 + grain * 0.18 + 0.2 - fp * 0.2).clamp()
    tone = (gr - 0.5) * 0.6 + (lump - 0.5) * 0.6 + (rn - 0.5) * 0.5 + 1.0
    col = b.cmul((0.0125, 0.012, 0.0118), tone)
    col = b.mixc(gb.smooth(0.97, 0.99) * 0.5, col, (0.03, 0.028, 0.026))
    glint = gg.smooth(0.99, 0.993)
    rough = (0.86 - glint * 0.76 - grain * 0.03 + (lump - 0.5) * 0.08).clamp()
    damp = b.noise4(warp(b, t, 0.06, 2.0), scale=3, detail=3).smooth(0.5, 0.65)
    return dict(albedo=col, rough=rough, height=height, ao=grain.lin(0.0, 0.6, 0.7, 1.0) * (1.0 - fp * 0.2),
                wet=(damp + (1.0 - ripple) * 0.3).clamp())


def pat_ash_clay(b, uv):
    """Tsuchikabe-style grey ash-clay plaster (2 m tile): +-10 % mottling at 10-50 cm, soft
    trowel arcs 20-60 cm in roughness and albedo, chopped straw fibres, a few hairline cracks."""
    t = b.torus(uv)
    mott = b.noise4(t, scale=7, detail=4)
    mott2 = b.noise4(t, scale=22, detail=3)
    d, c = b.voronoi4(warp(b, t, 0.05, 2.0), scale=5, feature='F1', out=['Distance', 'Color'])
    cr, _, _ = b.rgb_sep(c)
    arc = ((d * (TAU * 4.0) + cr * 6.0).sin() * 0.5 + 0.5)
    arc = arc * b.noise4(t, scale=4).smooth(0.35, 0.65)
    f1 = b.ridge(b.noise4(b.torus(uv, ax=1.0, ay=8.0), scale=40, detail=1)) ** 30.0
    f2 = b.ridge(b.noise4(b.torus(uv, ax=8.0, ay=1.0), scale=40, detail=1)) ** 30.0
    f3 = b.ridge(b.noise4(b.torus(uv, ax=6.0, ay=1.0, rot=(1, 1, 1, -1)), scale=30, detail=1)) ** 30.0
    straw = f1.max(f2).max(f3) * b.noise4(t, scale=30).smooth(0.5, 0.6)
    crack = cracks(b, warp(b, t, 0.1, 2.0), 3.0, 0.992, 0.999) * b.noise4(t, scale=2).smooth(0.55, 0.65)
    grain = b.noise4(t, scale=160, detail=2)
    height = (0.45 + mott * 0.2 + arc * 0.15 + grain * 0.08 + straw * 0.1 - crack * 0.35).clamp()
    tone = (mott - 0.5) * 0.35 + (mott2 - 0.5) * 0.25 + (arc - 0.5) * 0.08 + (grain - 0.5) * 0.06 + 1.0
    col = b.cmul((0.15, 0.142, 0.132), tone)
    col = b.mixc(straw * 0.7, col, (0.34, 0.27, 0.14))
    col = b.mixc(crack * 0.7, col, (0.04, 0.037, 0.034))
    rough = (0.86 - arc * 0.14 + (grain - 0.5) * 0.06).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - crack * 0.6,
                wet=b.noise4(t, scale=5).smooth(0.55, 0.7))


# paving: 4 m tile, five courses of uneven height, 3-5 slabs per course, warped joints.
PAVING_COURSES = [0.80, 0.95, 0.62, 0.88, 0.75]   # metres, sum = 4.0


def pat_paving(b, uv):
    """Large dark irregular basalt flagstones 0.5-1.4 m, thin joints, per-slab tone (no two
    neighbours alike), +-3 mm tilt, per-slab roughness 0.08-0.3, puddles in low areas and a
    wet band along joints (4 m tile)."""
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    tot = sum(PAVING_COURSES)
    bnd = [0.0]
    for h_ in PAVING_COURSES:
        bnd.append(bnd[-1] + h_ / tot)
    r = v * 0.0
    lo = v * 0.0
    hgt = v * 0.0 + PAVING_COURSES[0] / tot
    for i in range(1, len(PAVING_COURSES)):
        st = b.math('GREATER_THAN', v, bnd[i])
        r = r + st
        lo = lo + st * (bnd[i] - bnd[i - 1])
        hgt = hgt + st * ((bnd[i + 1] - bnd[i]) - (bnd[i] - bnd[i - 1]))
    fy = ((v - lo) / hgt).clamp()
    n = (b.white1(r * 3.1 + 0.7) * 3.999).floor() + 2.0          # 2..5 slabs per course (0.8-2 m)
    x1 = u * n + b.white1(r + 7.3)
    ph = b.white1(r + 11.0) * TAU
    x2 = x1 + (x1 * TAU + ph).sin() * (0.85 / TAU)
    c = x2.floor()
    fx = x2.fract()
    sid = r * 8.0 + c.mod(n)
    tone = (sid * 0.618034 + b.white1(r + 3.0) * 0.3).fract()
    r2 = b.white1(sid + 37.0)
    r3 = b.white1(sid + 71.0)
    r4 = b.white1(sid + 13.0)
    jn = (b.noise4(t, scale=60, detail=3) - 0.5) * 0.008
    ex = fx.min(1.0 - fx) * (4.0 / n)
    ey = fy.min(1.0 - fy) * (hgt * 4.0)
    e = ex.min(ey) + jn                                            # metres to the joint
    joint = 1.0 - e.smooth(0.002, 0.005)
    bevel = e.smooth(0.003, 0.03)
    surf = b.noise4(t, scale=20, detail=6, rough=0.55)
    fine = b.noise4(t, scale=120, detail=2)
    dish = b.noise4(warp(b, t, 0.03, 4.0), scale=7, detail=2)
    pits = holes(b, t, 260, 0.05, 0.13) * b.noise4(t, scale=6).smooth(0.55, 0.7)
    tilt = ((fx - 0.5) * (r2 - 0.5) + (fy - 0.5) * (r3 - 0.5)) * 0.6
    slab = (0.62 + (r4 - 0.5) * 0.06 + tilt + (surf - 0.5) * 0.14 + (dish - 0.5) * 0.12 + fine * 0.03
            - (1.0 - bevel) * 0.18 - pits * 0.08)
    height = b.mixf(joint, slab, 0.05).clamp()
    col = b.ramp(tone, [(0.0, (0.030, 0.031, 0.034)), (0.35, (0.042, 0.042, 0.045)),
                        (0.7, (0.052, 0.050, 0.050)), (1.0, (0.064, 0.060, 0.057))])
    grain = b.noise4(t, scale=400, detail=1)
    col = b.cmul(col, (surf - 0.5) * 0.6 + (fine - 0.5) * 0.3 + (grain - 0.5) * 0.25 + 1.0)
    col = b.mixc(pits * 0.6, col, (0.012, 0.012, 0.013))
    col = b.mixc(joint, col, (0.010, 0.010, 0.011))
    scuff = b.noise4(b.torus(uv, ax=1.0, ay=0.2, rot=(1, 1, 1, -1)), scale=60, detail=2).smooth(0.6, 0.7)
    rough = (0.06 + r3 * 0.16 + (surf - 0.5) * 0.15 + (fine - 0.5) * 0.1 + scuff * 0.12 + pits * 0.2 + joint * 0.45 + (1.0 - bevel) * 0.05).clamp()
    puddle = (0.5 - dish).smooth(0.02, 0.12)
    band = 1.0 - e.smooth(0.0, 0.035)
    film = (puddle + band * 0.8 + pits * 0.4).clamp()
    ao = (1.0 - joint * 0.7) * (bevel * 0.15 + 0.85) * (1.0 - pits * 0.5)
    return dict(albedo=col, rough=rough, height=height, ao=ao, wet=film)


# --------------------------------------------------------------- wood, paper, cloth
def pat_hinoki(b, uv):
    """Aged hinoki, 2 m along the grain (u) x 0.25 m across (v), aspect 8.  Growth rings 4-8 mm
    with late wood ~30 % darker, wandering flat-sawn figure, fibre streaks, rare pin knots."""
    asp = 8.0
    u, v, _ = b.sep(uv)
    t = iso(b, uv, asp)
    kd, kc = b.voronoi4(iso(b, uv, asp, 0.5), scale=3.0, feature='F1', out=['Distance', 'Color'])
    kr, _, _ = b.rgb_sep(kc)
    kon = kr.smooth(0.72, 0.8)
    knot_field = (1.0 - kd.smooth(0.0, 0.35)) * kon
    knot = (1.0 - kd.smooth(0.03, 0.06)) * kon
    wob = b.noise4(b.torus(uv, ax=1.0, ay=0.6), scale=4, detail=4) - 0.5
    fig = b.noise4(b.torus(uv, ax=1.0, ay=0.6 / asp), scale=2, detail=2) - 0.5
    ring = v * 42.0 + wob * 3.0 + fig * 9.0 + knot_field * 5.0
    f = ring.fract()
    share = b.white1(ring.floor()) * 0.3 + 0.3
    late = f.lin(1.0 - share, 0.97) ** 1.5 * (1.0 - f.smooth(0.975, 1.0))
    fib = b.noise4(b.torus(uv, ax=1.0, ay=40.0 / asp), scale=40, detail=2)
    streak = b.noise4(b.torus(uv, ax=0.6, ay=60.0 / asp), scale=10, detail=2).smooth(0.6, 0.75)
    board = b.noise4(t, scale=3, detail=2)
    col = b.ramp(late, [(0.0, (0.52, 0.33, 0.165)), (0.5, (0.44, 0.27, 0.13)), (1.0, (0.34, 0.205, 0.095))])
    col = b.cmul(col, (fib - 0.5) * 0.12 + (board - 0.5) * 0.15 + 1.0)
    col = b.mixc(streak * 0.3, col, (0.30, 0.18, 0.085))
    col = b.mixc(knot, col, (0.12, 0.06, 0.03))
    col = b.mixc(knot_field * 0.25, col, (0.30, 0.17, 0.08))
    height = (0.4 + late * 0.12 + (fib - 0.5) * 0.12 - streak * 0.08 - knot * 0.1).clamp()
    rough = (0.46 - late * 0.08 + (fib - 0.5) * 0.06 + knot * 0.1).clamp()
    ao = 1.0 - streak * 0.15 - knot * 0.3
    film = (1.0 - late) * 0.4
    return dict(albedo=col, rough=rough, height=height, ao=ao, wet=film)


def pat_lacquer(b, uv):
    """Urushi over wood: very soft, wide, low-contrast figure (3-5 %), surface imperfections in
    roughness only (brush ripples, dust/fingerprint patches 0.08-0.25), no ribbing."""
    t = b.torus(uv)
    fig = b.noise4(b.torus(uv, ax=0.15, ay=1.0), scale=6, detail=3, dist=0.4)
    figb = ((fig * 9.0).sin() * 0.5 + 0.5)
    col = b.cmul((0.024, 0.0125, 0.009), (figb - 0.5) * 0.08 + (fig - 0.5) * 0.06 + 1.0)
    brush = b.noise4(b.torus(uv, ax=0.08, ay=1.0), scale=40, detail=2)
    smudge = b.noise4(warp(b, t, 0.1, 2.0), scale=6, detail=5).smooth(0.55, 0.8)
    dust = b.noise4(t, scale=60, detail=2).smooth(0.7, 0.85) * b.noise4(t, scale=3).smooth(0.5, 0.7)
    rough = (0.07 + (brush - 0.5) * 0.04 + smudge * 0.14 + dust * 0.1).clamp()
    peel = b.noise4(t, scale=150, detail=2)
    height = (0.5 + (brush - 0.5) * 0.05 + (peel - 0.5) * 0.04 + figb * 0.02).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0, wet=0.0)


BAMBOO_NODES = (0.06, 0.38, 0.69)


def pat_bamboo(b, uv):
    """Culm skin, 0.25 m around (u) x 1.0 m along (v), aspect 0.25.  Raised node rings 3-5 mm
    with a darker band and scar line at uneven 31-37 cm spacing, longitudinal fibres, waxy
    sheen, green-yellow to straw mottling, dark speckles."""
    asp = 0.25
    u, v, _ = b.sep(uv)
    t = iso(b, uv, asp)
    ridge = v * 0.0
    band = v * 0.0
    scar = v * 0.0
    for nv in BAMBOO_NODES:
        dv = ((v - nv + 0.5).fract() - 0.5)        # metres = dv * 1.0
        ad = dv.abs()
        ridge = ridge.max(1.0 - ad.smooth(0.0, 0.0025))
        band = band.max(1.0 - ad.smooth(0.004, 0.03))
        scar = scar.max((1.0 - (dv + 0.006).abs().smooth(0.0, 0.0008)))
    fib = b.noise4(b.torus(uv, ax=1.0, ay=4.0 * 0.05), scale=70, detail=2)
    mot = b.noise4(b.torus(uv, ax=1.0, ay=4.0 * 0.4), scale=4, detail=3)
    spk = b.noise4(t, scale=90, detail=2).smooth(0.72, 0.76) * b.noise4(t, scale=5).smooth(0.45, 0.7)
    col = b.ramp(mot, [(0.15, (0.30, 0.30, 0.09)), (0.5, (0.42, 0.34, 0.12)), (0.85, (0.50, 0.40, 0.17))])
    col = b.cmul(col, (fib - 0.5) * 0.12 + 1.0)
    col = b.mixc(band * 0.5, col, (0.24, 0.17, 0.06))
    col = b.mixc(ridge * 0.4, col, (0.55, 0.46, 0.24))
    col = b.mixc(scar * 0.8, col, (0.08, 0.05, 0.02))
    col = b.mixc(spk * 0.8, col, (0.07, 0.045, 0.02))
    height = (0.45 + ridge * 0.45 - band * 0.05 - scar * 0.15 + (fib - 0.5) * 0.06).clamp()
    rough = (0.28 + band * 0.1 + spk * 0.2 + (fib - 0.5) * 0.04).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - scar * 0.4, wet=band * 0.3)


def pat_tatami(b, uv):
    """One-directional igusa rush rows (along u) at 3.5 mm pitch, faint warp threads every
    17 mm, per-stalk tone +-8 %, gentle normals (~9 deg), golden straw with a hint of green."""
    u, v, _ = b.sep(uv)
    sv = v * 143.0
    sid = sv.floor()
    sf = sv.fract()
    prof = (sf * 3.14159265).sin() ** 0.7
    wu = u * 30.0
    wf = wu.fract()
    dw = wf.min(1.0 - wf)
    dent = (1.0 - dw.smooth(0.0, 0.03)) * ((sid + wu.floor()).mod(2.0) * 0.6 + 0.4)
    rnd = b.white1(sid)
    rnd2 = b.white1(sid + 911.0)
    along = b.noise4(b.torus(uv, ax=1.0, ay=143.0), scale=2.0, detail=2)
    shade = (rnd - 0.5) * 0.16 + (along - 0.5) * 0.08 + 1.0
    col = b.cmul((0.48, 0.38, 0.14), shade)
    col = b.mixc(rnd2.smooth(0.75, 0.9) * 0.5, col, (0.40, 0.38, 0.13))
    col = b.cmul(col, 1.0 - (1.0 - prof) * 0.22 - dent * 0.06)
    height = (prof * 0.6 - dent * 0.12 + 0.25).clamp()
    rough = (0.5 + (1.0 - prof) * 0.15 + (rnd - 0.5) * 0.06).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0 - (1.0 - prof) * 0.3, wet=(1.0 - prof) * 0.3)


def _washi(b, uv):
    """Shared washi fibre field: (thickness 0..1, fibres 0..1, cloud 0..1, bundles 0..1)."""
    t = b.torus(uv)
    fibs = []
    for i, rot in enumerate((None, (1, 1, 1, -1), (1, -1, 1, 1), (2, 1, -1, 2))):
        tf = b.torus(uv, ax=0.4, ay=3.0, rot=rot) if i % 2 == 0 else b.torus(uv, ax=3.0, ay=0.4, rot=rot)
        f = b.ridge(b.noise4(tf, scale=26, detail=2)) ** 18.0
        seg = b.noise4(b.torus(uv, rot=rot), scale=18 + i * 3, detail=1).smooth(0.45, 0.6)
        fibs.append(f * seg)
    fib = fibs[0].max(fibs[1]).max(fibs[2]).max(fibs[3])
    bund = b.ridge(b.noise4(b.torus(uv, ax=0.5, ay=2.0, rot=(1, 1, 1, -1)), scale=8, detail=2)) ** 25.0
    bund = bund * b.noise4(t, scale=5).smooth(0.6, 0.7)
    cloud = b.noise4(warp(b, t, 0.05, 2.0), scale=2.5, detail=6, rough=0.62)
    thick = (cloud * 0.65 + fib * 0.3 + bund * 0.5 + 0.05).clamp()
    return thick, fib, cloud, bund


def pat_washi(b, uv):
    """Kozo washi: long fibres in random directions, fibre bundles, 10-40 cm cloudiness
    (albedo +-6 %, thinness in base.a), warm off-white sRGB ~(230,220,195)."""
    thick, fib, cloud, bund = _washi(b, uv)
    col = b.cmul((0.77, 0.70, 0.54), (cloud - 0.5) * 0.4 + 1.0)
    col = b.mixc(fib * 0.5, col, (0.85, 0.80, 0.66))
    col = b.mixc(bund * 0.5, col, (0.68, 0.60, 0.44))
    height = (cloud * 0.35 + fib * 0.4 + bund * 0.4 + 0.1).clamp()
    rough = (0.84 - fib * 0.08).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=1.0, mask=(1.0 - thick).clamp(), wet=0.0)


def pat_washi_backlit(b, uv):
    """Same paper as washi; the emissive map is the back-lit look: brighter where thin."""
    thick, fib, cloud, bund = _washi(b, uv)
    d = pat_washi(b, uv)
    thin = (1.0 - thick).clamp()
    glow = (thin * 0.9 + 0.25 - bund * 0.3).clamp()
    d['emission'] = b.mixc(glow, b.cmul(EDGE_GLOW, glow * 0.6), b.cmul(LANTERN, glow))
    return d


def pat_noren(b, uv):
    """Heavy indigo cotton/linen: plain weave at 1 mm thread pitch with 5-20 mm slubs, uneven
    dyeing (fade +-15 %), dark navy sRGB ~(25,35,70).  0.3 m tile."""
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    n = 300.0
    x = u * n
    y = v * n
    ix, iy, fx, fy = x.floor(), y.floor(), x.fract(), y.fract()
    par = (ix + iy).mod(2.0)
    slub_w = b.noise4(b.torus(uv, ax=n, ay=6.0), scale=1.0, detail=2)
    slub_f = b.noise4(b.torus(uv, ax=6.0, ay=n), scale=1.0, detail=2)
    pw = (fx * 3.14159265).sin() ** (0.8 - slub_w * 0.4)
    pf = (fy * 3.14159265).sin() ** (0.8 - slub_f * 0.4)
    height = b.mixf(par, pf * 0.8 + 0.1 * pw, pw * 0.8 + 0.1 * pf).clamp()
    fade = b.noise4(warp(b, t, 0.05, 2.0), scale=3, detail=4)
    thread = b.mixf(par, slub_f, slub_w)
    tone = (fade - 0.5) * 0.35 + (thread - 0.5) * 0.3 + 1.0
    col = b.cmul((0.0105, 0.018, 0.062), tone * 1.0)
    col = b.mixc((1.0 - height).smooth(0.45, 1.0) * 0.6, col, (0.003, 0.005, 0.015))
    rough = (0.8 + (1.0 - height) * 0.12).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=height.lin(0.0, 0.5, 0.6, 1.0), wet=0.0)


def pat_rope(b, uv):
    """Three twisted strands (u along the rope, v around), fibres along each strand, flyaway
    fuzz, per-strand tone (straw to grey-brown), deep dirty crevices.  0.3 m tile."""
    u, v, _ = b.sep(uv)
    s = v * 3.0 + u * 2.0
    sid = s.floor().mod(3.0)
    sf = s.fract()
    prof = (sf * 3.14159265).sin() ** 0.5
    tf = b.torus(uv, ax=1.0, ay=0.04, rot=(2, 3, 3, -2))
    fib = b.noise4(tf, scale=90, detail=2)
    fib2 = b.ridge(b.noise4(tf, scale=35, detail=1)) ** 8.0
    fuzz = b.ridge(b.noise4(b.torus(uv, ax=0.5, ay=3.0, rot=(3, -2, 2, 3)), scale=25, detail=1)) ** 40.0
    tone = b.white1(sid * 1.0 + 5.0)
    base = b.ramp(tone, [(0.0, (0.30, 0.25, 0.15)), (0.5, (0.42, 0.34, 0.17)), (1.0, (0.36, 0.30, 0.20))])
    col = b.cmul(base, (fib - 0.5) * 0.35 + 1.0)
    col = b.mixc(fib2 * 0.4, col, (0.55, 0.47, 0.28))
    col = b.mixc(fuzz * 0.6, col, (0.62, 0.55, 0.36))
    crev = (1.0 - prof).smooth(0.5, 1.0)
    col = b.mixc(crev * 0.75, col, (0.05, 0.04, 0.025))
    height = (prof * 0.7 + (fib - 0.5) * 0.18 + fib2 * 0.08 + fuzz * 0.06).clamp()
    rough = (0.82 + crev * 0.1 - fib2 * 0.05).clamp()
    return dict(albedo=col, rough=rough, height=height, ao=prof.lin(0.0, 0.7, 0.3, 1.0), wet=crev * 0.5)


# ------------------------------------------------------------- metal, ice, glass
def pat_iron(b, uv):
    """Cast/forged iron in a humid onsen: non-metal black oxide (rough 0.6), pitting, rust
    patches and run-down streaks 2-20 cm (non-metal orange-brown, rough 0.85).  Bare metal only
    via `wear` (WornMetal 1).  0.6 m tile."""
    t = b.torus(uv)
    d = b.voronoi4(t, scale=26, feature='F1')
    dimple = d.smooth(0.0, 0.7)
    mott = b.noise4(t, scale=8, detail=6)
    fine = b.noise4(t, scale=90, detail=3)
    pits = holes(b, t, 140, 0.04, 0.12) * b.noise4(t, scale=5).smooth(0.45, 0.7)
    src = (b.noise4(warp(b, t, 0.06, 2.0), scale=7, detail=6) * 0.7 + (0.5 - mott) * 0.5 + pits * 0.3).smooth(0.5, 0.58)
    run = streaks_v(b, uv, 1.0, 14, 2.0, 0.55, 0.66) * b.noise4(t, scale=3).smooth(0.45, 0.7)
    rust = src.max(run * 0.85)
    height = (dimple * 0.35 + mott * 0.3 + fine * 0.12 + 0.12 - pits * 0.2 + rust * 0.06).clamp()
    ox = b.cmul((0.036, 0.034, 0.033), (mott - 0.5) * 0.4 + (fine - 0.5) * 0.15 + 1.0)
    rc = b.ramp(fine, [(0.2, (0.10, 0.032, 0.011)), (0.6, (0.19, 0.075, 0.024)), (0.9, (0.27, 0.13, 0.05))])
    col = b.mixc(rust, ox, rc)
    col = b.mixc(pits * 0.6, col, (0.012, 0.011, 0.01))
    rough = (0.6 + (fine - 0.5) * 0.1 + rust * 0.25 + pits * 0.1).clamp()
    return dict(albedo=col, rough=rough, metal=0.0, height=height, ao=1.0 - pits * 0.6,
                wet=(run + pits).clamp())


def pat_bronze(b, uv):
    """Dark brown patinated bronze (metal, F0 ~ (0.35,0.22,0.12), rough 0.45), verdigris as
    non-metal teal-green crust (sRGB ~90,150,130, rough 0.85) in recesses, crusty patches and
    drips running down; micro pitting.  Polished bright bronze only via `wear`.  0.6 m tile."""
    t = b.torus(uv)
    mott = b.noise4(warp(b, t, 0.06, 2.0), scale=5, detail=6)
    fine = b.noise4(t, scale=70, detail=3)
    pits = holes(b, t, 160, 0.03, 0.1) * b.noise4(t, scale=5).smooth(0.5, 0.75)
    height = (mott * 0.5 + fine * 0.15 + 0.22 - pits * 0.25).clamp()
    crust = (b.noise4(warp(b, t, 0.1, 1.5), scale=4, detail=7) * 0.7 + (0.5 - mott) * 0.6).smooth(0.48, 0.56)
    drip = streaks_v(b, uv, 1.0, 12, 1.5, 0.55, 0.66) * crust.max(b.noise4(t, scale=2).smooth(0.55, 0.65))
    verd = (crust.max(drip * 0.9) + pits * 0.4).clamp()
    pat = b.cmul((0.33, 0.21, 0.11), (mott - 0.5) * 0.3 + (fine - 0.5) * 0.15 + 1.0)
    vc = b.cmul((0.10, 0.30, 0.22), (fine - 0.5) * 0.4 + 1.0)
    col = b.mixc(verd, pat, vc)
    metal = 1.0 - verd
    rough = (0.45 + (fine - 0.5) * 0.08 + verd * 0.4).clamp()
    return dict(albedo=col, rough=rough, metal=metal, height=(height + verd * 0.06).clamp(),
                ao=1.0 - pits * 0.5, wet=drip)


def pat_glacier_ice(b, uv):
    """Vertical melt flutes and icicle drips 1-5 cm, trapped bubble streams, a few large internal
    fracture planes, deep blue where thick, cyan-white where thin (emissive fake glow).  Frost
    on top-facing surfaces comes from KZ_Core (FrostUp).  2 m tile."""
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    fl = b.ridge(b.noise4(warp(b, b.torus(uv, ax=1.0, ay=0.1), 0.04, 2.0), scale=70, detail=2))
    fl2 = b.ridge(b.noise4(b.torus(uv, ax=1.0, ay=0.15), scale=20, detail=2))
    scal = b.noise4(t, scale=4, detail=4)
    lane = streaks_v(b, uv, 1.0, 30, 3.0, 0.72, 0.8)
    bub = holes(b, b.torus(uv, ax=1.0, ay=0.6), 260, 0.08, 0.16) * lane
    plane = cracks(b, warp(b, t, 0.1, 1.0), 1.2, 0.975, 0.995) * b.noise4(t, scale=2).smooth(0.5, 0.65)
    height = (fl ** 1.3 * 0.35 + fl2 * 0.25 + scal * 0.35 - bub * 0.05).clamp()
    thin = (1.0 - scal).smooth(0.3, 0.8) * 0.6 + fl * 0.4
    col = b.mixc(thin, (0.09, 0.30, 0.62), (0.55, 0.85, 0.95))
    col = b.mixc(plane * 0.5, col, (0.8, 0.92, 1.0))
    emis = b.mixc(thin, (0.01, 0.07, 0.30), (0.10, 0.55, 0.85))
    emis = b.cmul(emis, (plane * 0.6 + bub * 0.8 + 1.0))
    rough = (0.05 + (1.0 - fl) * 0.08 + plane * 0.1 + b.noise4(t, scale=8).smooth(0.6, 0.8) * 0.2).clamp()
    mask = (plane * 0.35 + bub * 0.5).clamp()
    return dict(albedo=col, rough=rough, height=height, emission=emis, mask=mask, wet=fl.smooth(0.6, 0.9))


def pat_lava_glass(b, uv):
    """Thick lava-window glass: near-clear, imperfections in roughness only: condensation haze
    patches (rough 0.3-0.5), faint diagonal wipe streaks, dust specks, tiny bubbles.  base.a =
    haze amount (web: raises opacity there).  2 m tile."""
    t = b.torus(uv)
    wave = b.noise4(t, scale=1.2, detail=2)
    bub = holes(b, t, 140, 0.02, 0.06) * b.noise4(t, scale=3).smooth(0.62, 0.8)
    haze = b.noise4(warp(b, t, 0.08, 1.5), scale=3, detail=5).smooth(0.55, 0.75)
    wipe = b.noise4(b.torus(uv, ax=0.15, ay=1.0, rot=(1, 1, 1, -1)), scale=12, detail=2).smooth(0.6, 0.72)
    dust = b.noise4(t, scale=200, detail=1).smooth(0.78, 0.84) * b.noise4(t, scale=4).smooth(0.5, 0.7)
    rough = (0.01 + haze * 0.38 + wipe * 0.06 + dust * 0.2).clamp()
    height = (wave * 0.85 + bub * 0.1).clamp()
    return dict(albedo=(0.97, 0.96, 0.93), rough=rough, height=height,
                mask=(haze * 0.8 + dust * 0.4 + bub * 0.2).clamp(), wet=haze)


# ------------------------------------------------------------------------- water
def pat_water_still(b, uv):
    """Calm pool surface ripples (4 m tile; the web samples it twice at 0.7 m and 3 m)."""
    t = b.torus(uv)
    n1 = b.noise4(t, scale=6, detail=3, rough=0.45)
    n2 = b.noise4(warp(b, t, 0.05, 3.0), scale=24, detail=3)
    height = (n1 * 0.65 + n2 * 0.35).clamp()
    return dict(albedo=(0.95, 0.97, 0.97), rough=0.012, height=height, mask=0.0, wet=1.0)


def pat_water_river(b, uv):
    t = b.torus(uv)
    tl = b.torus(uv, ax=0.45, ay=1.0)
    n1 = b.noise4(warp(b, tl, 0.05, 2.0), scale=6, detail=4, rough=0.55, dist=0.4)
    n2 = b.noise4(t, scale=22, detail=3)
    height = (n1 * 0.7 + n2 * 0.3).clamp()
    e = b.voronoi4(warp(b, b.torus(uv, ax=0.4, ay=1.0), 0.08, 2.0), scale=9, feature='DISTANCE_TO_EDGE')
    lace = (1.0 - e.smooth(0.0, 0.05)) * height.smooth(0.55, 0.75)
    foam = (lace * b.noise4(t, scale=5, detail=3).smooth(0.45, 0.65)).clamp()
    return dict(albedo=(0.92, 0.96, 0.96), rough=0.025, height=height, mask=foam, wet=1.0)


def pat_water_sea(b, uv):
    """Small-scale chop + thin lacy foam on the top ~12 % of crest height (swell is geometry)."""
    u, v, _ = b.sep(uv)
    t = b.torus(uv)
    wn = b.noise4(t, scale=2.5, detail=3)
    ph = (v * 5.0 + wn * 1.6).fract()
    crest = (1.0 - (ph - 0.5).abs() * 2.0) ** 2.2
    chop = b.noise4(t, scale=18, detail=4, rough=0.55)
    height = (crest * 0.55 + chop * 0.45).clamp()
    e = b.voronoi4(warp(b, t, 0.06, 3.0), scale=26, feature='DISTANCE_TO_EDGE')
    lace = 1.0 - e.smooth(0.0, 0.06)
    top = height.smooth(0.8, 0.9)
    foam = (top * (lace * 0.8 + 0.2) * b.noise4(t, scale=6, detail=3).smooth(0.35, 0.6)).clamp()
    return dict(albedo=(0.92, 0.96, 0.97), rough=0.03, height=height, mask=foam, wet=1.0)


def pat_waterfall(b, uv):
    """Aerated falling sheet: bright white foam ropes (sRGB 230+), clear teal gaps with soft
    alpha edges.  base.a = foam (alpha = 0.25 + 0.75 a).  2 m tile, flow along -v."""
    t = b.torus(uv)
    ts = b.torus(uv, ax=1.0, ay=0.07)
    streak = b.noise4(warp(b, ts, 0.03, 3.0), scale=36, detail=4, rough=0.55)
    streak2 = b.noise4(b.torus(uv, ax=1.0, ay=0.12), scale=90, detail=2)
    cloud = b.noise4(t, scale=4, detail=3).smooth(0.25, 0.7)
    aer = (streak.smooth(0.32, 0.6) * 0.8 + streak2.smooth(0.5, 0.7) * 0.3).clamp()
    foam = (aer * (cloud * 0.6 + 0.4)).clamp()
    height = (streak * 0.8 + cloud * 0.2).clamp()
    return dict(albedo=(0.90, 0.95, 0.95), rough=0.05, height=height, mask=foam,
                emission=b.cmul((0.80, 0.95, 0.95), foam), wet=1.0)


def pat_caustics(b, uv):
    """Caustic network for a decal on pool floors (1 m tile; web scrolls two layers)."""
    t = b.torus(uv)
    e1 = b.voronoi4(warp(b, t, 0.12, 2.0), scale=7, feature='DISTANCE_TO_EDGE', smooth=1.0)
    e2 = b.voronoi4(warp(b, t, 0.1, 3.0), scale=11, feature='DISTANCE_TO_EDGE')
    c = ((1.0 - e1.smooth(0.0, 0.06)) ** 1.5 * 0.7 + (1.0 - e2.smooth(0.0, 0.05)) ** 1.5 * 0.5).clamp()
    return dict(albedo=(0.0, 0.0, 0.0), rough=1.0, height=c * 0.2 + 0.4, emission=b.cmul((0.55, 1.0, 0.95), c),
                mask=c, wet=0.0)


# ------------------------------------------------------------- light sources
def _lava(b, uv, molten):
    """Shared lava: black ropy/jagged crust islands separated by meandering seams with a hot
    core gradient; `molten` = fraction of flowing lava (0.25 crust field, 0.75 flow)."""
    t = b.torus(uv)
    tw = warp(b, t, 0.15, 1.2)
    r1 = b.ridge(b.noise4(tw, scale=3.2, detail=3))
    r2 = b.ridge(b.noise4(warp(b, t, 0.08, 3.0), scale=9.0, detail=2))
    wv = b.noise4(t, scale=2.5, detail=2)
    seam = (r1.smooth(0.985 - wv * 0.07, 0.998) + r2.smooth(0.982, 0.998) * 0.45 * wv.smooth(0.4, 0.6)).clamp()
    flow = b.noise4(warp(b, b.torus(uv, ax=0.5, ay=1.5), 0.1, 1.0), scale=2.0, detail=4)
    thr = 0.5 + (0.5 - molten) * 0.3
    sheet = flow.smooth(thr - 0.035, thr + 0.035)
    stri = b.noise4(b.torus(uv, ax=1.0, ay=0.12), scale=30, detail=3)
    heat = seam.max(sheet * (b.noise4(t, scale=6, detail=3) * 0.3 + stri * 0.25 + 0.3))
    halo = (r1.smooth(0.85, 0.97) * 0.5 + flow.smooth(thr - 0.12, thr) * 0.5).clamp()
    rope = b.ridge(b.noise4(warp(b, b.torus(uv, ax=1.0, ay=0.3), 0.06, 4.0), scale=26, detail=2))
    jag = b.noise4(t, scale=60, detail=8, rough=0.7)
    emis = b.ramp(heat, [(0.0, (0.0, 0.0, 0.0)), (0.12, (0.18, 0.004, 0.0)), (0.4, (0.85, 0.07, 0.002)),
                         (0.7, (1.0, 0.28, 0.02)), (1.0, (1.0, 0.72, 0.30))])
    emis = b.cadd(emis, b.cmul((0.06, 0.003, 0.0), halo))
    crust = b.cmul((0.010, 0.009, 0.009), (jag - 0.5) * 0.5 + (rope - 0.5) * 0.3 + 1.0)
    col = b.mixc(heat.smooth(0.15, 0.6), crust, (0.25, 0.05, 0.01))
    height = (0.75 - heat * 0.6 + rope * 0.12 + jag * 0.15).clamp()
    rough = (0.55 + (jag - 0.5) * 0.25 - heat * 0.2).clamp()
    return dict(albedo=col, rough=rough, height=height, emission=emis, ao=1.0, wet=0.0)


def pat_lava(b, uv):
    return _lava(b, uv, 0.22)


def pat_lava_flow(b, uv):
    return _lava(b, uv, 0.6)


def pat_neon(b, uv):
    t = b.torus(uv)
    n = b.noise4(t, scale=6, detail=2)
    return dict(albedo=(0.06, 0.06, 0.06), rough=0.05, height=n * 0.2 + 0.4,
                emission=b.cmul((1.0, 1.0, 1.0), n * 0.06 + 0.94), wet=0.0)


def pat_lantern_paper(b, uv):
    """Round chochin lantern on its own UV (u around 0..1, v bottom->top 0..1, not tiling in v):
    bamboo ribs every ~2.5 cm (24 on a 0.6 m lantern) with soft rib shadows, paper cloud and
    fibres, glow brightest at the centre falling to ~45 % near the caps, colour 2700 K centre ->
    1800 K edges."""
    u, v, _ = b.sep(uv)
    thick, fib, cloud, bund = _washi(b, uv)
    rv = (v * 24.0).fract()
    rd = rv.min(1.0 - rv)
    rib = 1.0 - rd.smooth(0.0, 0.06)
    ribsh = 1.0 - rd.smooth(0.0, 0.25)
    g = (v * 3.14159265).sin() ** 0.8
    cap = v.smooth(0.0, 0.05) * (1.0 - v.smooth(0.95, 1.0))
    glow = g * 0.6 + 0.4
    glow = glow * (1.0 - thick * 0.35 + 0.15) * (1.0 - ribsh * 0.25) * (1.0 - rib * 0.55) * cap
    ecol = b.mixc(g, EDGE_GLOW, LANTERN)
    emis = b.cmul(ecol, glow)
    col = b.cmul((0.76, 0.69, 0.53), (cloud - 0.5) * 0.12 + 1.0)
    col = b.mixc(rib * 0.6, col, (0.30, 0.22, 0.12))
    height = (rib * 0.6 + fib * 0.15 + cloud * 0.2).clamp()
    return dict(albedo=col, rough=0.8, height=height, emission=emis, mask=(1.0 - thick).clamp(), wet=0.0)


def pat_lantern_andon(b, uv):
    """Square kaku-andon panel on its own UV (one face = 0..1): wooden frame shadow 1-2 cm
    (6 % of a 25 cm panel), one crossbar, centre-bright glow falling to ~50 % at the frame."""
    u, v, _ = b.sep(uv)
    thick, fib, cloud, bund = _washi(b, uv)
    du = u.min(1.0 - u)
    dv = v.min(1.0 - v)
    frame = 1.0 - du.min(dv).smooth(0.04, 0.07)
    bar = 1.0 - (v - 0.62).abs().smooth(0.006, 0.014)
    shade = 1.0 - (v - 0.62).abs().smooth(0.0, 0.05)
    cen = ((u - 0.5) * 2.0).abs().max(((v - 0.5) * 2.0).abs())
    g = 1.0 - cen ** 2.0 * 0.5
    glow = g * (1.0 - thick * 0.3 + 0.1) * (1.0 - frame) * (1.0 - bar) * (1.0 - shade * 0.2)
    emis = b.cmul(b.mixc(g, EDGE_GLOW, LANTERN), glow)
    col = b.mixc(frame.max(bar), b.cmul((0.76, 0.69, 0.53), (cloud - 0.5) * 0.12 + 1.0), (0.10, 0.06, 0.035))
    height = (frame.max(bar) * 0.8 + fib * 0.1 + cloud * 0.1).clamp()
    rough = (0.8 - frame.max(bar) * 0.35).clamp()
    return dict(albedo=col, rough=rough, height=height, emission=emis, mask=(1.0 - thick).clamp(), wet=0.0)


# ------------------------------------------------------------------- the library
# tile = metres along u per repeat (aspect: u/v extent ratio); res = pixels along the larger
# side.  core = KZ_Core constants; params = defaults of the 7 artist settings.
# tex_from shares another material's texture set; uvmode 'object' = the material expects
# 0..1 object UVs (lanterns) instead of metric UVs (scale = 1).
WATER_CORE = dict(Transmission=1.0, IOR=1.333, Specular=0.5, Porosity=0.0, FoamColor=(0.86, 0.9, 0.9),
                  FoamFromMask=1.0)
STONE_MACRO = 1.0

MATERIALS = [
    # ---- stone
    dict(id='basalt_dry', name='Dry basalt', category='stone', tile=2.0, res=1024,
         pattern=pat_basalt, depth=0.10,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.6, WornColor=(0.05, 0.052, 0.056), WornRough=0.45, MacroAmount=STONE_MACRO,
                   Cavity=1.0),
         concept=['22-brand-board.jpg (BASALT swatch)', '04-arrival-gate.jpg', '19-thunder-curtain.jpg'],
         ref='refs/gen/mat-basalt-wet.png',
         three=dict(env=0.6)),
    dict(id='basalt_wet', name='Wet basalt', category='stone', tile=2.0, res=1024, tex_from='basalt_dry',
         pattern=pat_basalt, depth=0.10,
         params=dict(wetness=0.85, wear=0.0),
         core=dict(Porosity=0.6, WornColor=(0.05, 0.052, 0.056), WornRough=0.45, MacroAmount=STONE_MACRO,
                   Cavity=1.0),
         concept=['16-steam-grotto.jpg', '05-mist-corridor.jpg', '17-glacier-plunge.jpg'],
         ref='refs/gen/mat-basalt-wet.png',
         three=dict(env=1.0, note='Same texture set as basalt_dry; only wetness differs, so wet/dry can blend '
                                  'on one mesh (drive wetness per vertex). Clamp wet roughness >= 0.12 beyond '
                                  'mip 2 (the ORM mips already carry Toksvig roughness).')),
    dict(id='obsidian', name='Polished obsidian', category='stone', tile=2.0, res=1024,
         pattern=pat_obsidian, depth=0.06,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(IOR=1.49, Specular=0.55, Porosity=0.0, WornColor=(0.03, 0.03, 0.032), WornRough=0.25,
                   Cavity=0.6),
         concept=['22-brand-board.jpg (OBSIDIAN swatch)', '17-glacier-plunge.jpg (obsidian monolith)', '15-obsidian-mirror.jpg'],
         ref='refs/gen/mat-obsidian.png',
         three=dict(env=1.0, note='Defined by what it reflects: needs the room reflection probe (lantern and '
                                  'glowworm dots) at envMapIntensity ~1.0.')),
    dict(id='rimstone', name='Rimstone / travertine', category='stone', tile=1.5, res=512,
         pattern=pat_rimstone_top, side=pat_rimstone_side, depth=0.02,
         params=dict(wetness=0.5, wear=0.0),
         core=dict(Porosity=0.5, WornColor=(0.82, 0.8, 0.74), WornRough=0.3, Cavity=0.6),
         concept=['18-rimstone-terraces.jpg'], ref='refs/gen/mat-rimstone.png',
         three=dict(env=0.8, note='Two texture sets: textures (tops, micro-gours) and textures_side (flowstone '
                                  'drapery), blended by world normal: w_top = smoothstep(0.5, 0.8, n.y).')),
    dict(id='black_sand', name='Black sand', category='stone', tile=2.0, res=1024,
         pattern=pat_black_sand, depth=0.03,
         params=dict(wetness=0.15, wear=0.0),
         core=dict(Porosity=1.0, WornColor=(0.02, 0.019, 0.018), WornRough=0.8, MacroAmount=1.0, Cavity=0.8),
         concept=['20-wave-grotto.jpg'], ref='refs/gen/mat-black-sand.png',
         three=dict(env=0.5, note='Drive wetness from a shoreline vertex-colour mask (wet sand -> rough 0.05-0.1).')),
    dict(id='ash_clay', name='Ash clay (tsuchikabe plaster)', category='stone', tile=2.0, res=512,
         pattern=pat_ash_clay, depth=0.01,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, WornColor=(0.2, 0.19, 0.18), WornRough=0.7, MacroAmount=0.6, Cavity=0.8),
         concept=['16-steam-grotto.jpg', '22-brand-board.jpg'],
         three=dict(env=0.4, note='Interior clay/plaster walls. Not for ash-glaze tea ware (use a prop texture).')),
    dict(id='paving', name='Worn paving (basalt flagstones)', category='stone', tile=4.0, res=1024,
         pattern=pat_paving, depth=0.02,
         params=dict(wetness=0.5, wear=0.15),
         core=dict(Porosity=0.5, WornColor=(0.06, 0.06, 0.062), WornRough=0.12, MacroAmount=0.7, Cavity=1.0),
         concept=['16-steam-grotto.jpg (wet flagstones)', '04-arrival-gate.jpg (lobby floor)'],
         ref='refs/gen/mat-obsidian.png (floor)',
         three=dict(env=1.0, note='Walking-path polish: raise wear / lower roughness_offset along paths via '
                                  'vertex colour.')),
    # ---- wood, paper, cloth
    dict(id='hinoki', name='Hinoki (aged)', category='wood_paper_cloth', tile=2.0, aspect=8.0, res=2048,
         pattern=pat_hinoki, depth=0.0015,
         params=dict(wetness=0.0, wear=0.1),
         core=dict(Porosity=0.8, WornColor=(0.30, 0.26, 0.20), WornRough=0.55, WornMax=0.6, Specular=0.45,
                   Sheen=0.15, Cavity=0.6),
         variants=dict(dark_timber=dict(tint=(0.30, 0.27, 0.25), roughness_offset=0.1),
                       handled=dict(tint=(0.8, 0.72, 0.65), roughness_offset=-0.15)),
         concept=['05-mist-corridor.jpg (shoji frames, posts)', '04-arrival-gate.jpg (shoe lockers)', '16-steam-grotto.jpg (bucket, sign post)'],
         ref='refs/gen/mat-hinoki-washi.png',
         three=dict(env=0.5, note='Texture is 2 m along the grain (u) x 0.25 m across (v). Randomise u offset, '
                                  'flip and tint +-10 % per board on the asset side. Variants: dark_timber '
                                  '(stained structural timber), handled (hand-polished rails, darker, glossier).')),
    dict(id='lacquer_dark', name='Lacquered dark wood (urushi)', category='wood_paper_cloth', tile=1.0, res=512,
         pattern=pat_lacquer, depth=0.0005,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.0, Coat=1.0, CoatRough=0.05, WornColor=(0.19, 0.013, 0.007), WornRough=0.3,
                   Cavity=0.3),
         concept=['21-private-suite.jpg (table, trays)', '06-kawagiri-restaurant.jpg'],
         three=dict(env=1.0, clearcoat=1.0, clearcoatRoughness=0.05,
                    note='For furniture and trays. Structural dark timbers: hinoki variant dark_timber. '
                         'Edge wear reveals red undercoat (negoro).')),
    dict(id='bamboo', name='Bamboo', category='wood_paper_cloth', tile=0.25, aspect=0.25, res=1024,
         pattern=pat_bamboo, depth=0.004,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.3, Sheen=0.3, WornColor=(0.55, 0.46, 0.26), WornRough=0.3, Cavity=0.6),
         concept=['04-arrival-gate.jpg (bamboo spout)', '22-brand-board.jpg'],
         three=dict(env=0.7, note='u = around the culm (0.25 m), v = along it (1.0 m). Randomise v offset per '
                                  'pole; tint per culm from green-yellow to straw.')),
    dict(id='tatami', name='Tatami', category='wood_paper_cloth', tile=0.5, res=1024,
         pattern=pat_tatami, depth=0.0007,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=0.9, Sheen=0.3, WornColor=(0.52, 0.44, 0.22), WornRough=0.4, Cavity=0.5),
         concept=['21-private-suite.jpg (tatami floor)'], ref='refs/gen/mat-hinoki-washi.png',
         three=dict(env=0.4, sheen=0.3, note='Rush rows run along u. Per-mat tint and walking-line wear on the '
                                             'asset side; the heri border is geometry.')),
    dict(id='washi', name='Washi paper', category='wood_paper_cloth', tile=0.5, res=512,
         pattern=pat_washi, depth=0.0008,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Translucency=0.3, ThinFromMask=1.0, WornColor=(0.62, 0.56, 0.44), WornRough=0.9,
                   Cavity=0.3),
         concept=['05-mist-corridor.jpg (shoji panels)', '22-brand-board.jpg (menu card)'],
         ref='refs/gen/mat-hinoki-washi.png',
         three=dict(env=0.3, note='base.a = thinness. Faint yellowing at panel bottoms via vertex colour.')),
    dict(id='washi_backlit', name='Washi, back-lit (shoji / lantern shade)', category='wood_paper_cloth',
         tile=0.5, res=512, pattern=pat_washi_backlit, depth=0.0008, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=1.0, Translucency=0.7, ThinFromMask=1.0, EmitStrength=0.8,
                   WornColor=(0.62, 0.56, 0.44), WornRough=0.9, Cavity=0.3),
         preview=dict(backlight=True),
         concept=['05-mist-corridor.jpg (lit shoji)', '22-brand-board.jpg (paper lantern)'],
         ref='refs/gen/mat-hinoki-washi.png',
         three=dict(env=0.3, note='Emissive map = back-lit paper (bright where thin, fibre bundles darker). '
                                  'Per-panel falloff (centre bright, 40-60 % at frame edges, rib shadows) '
                                  'belongs in the lightmap / a per-panel emissive gradient, not this tile.')),
    dict(id='noren', name='Noren cloth (indigo)', category='wood_paper_cloth', tile=0.3, res=1024,
         pattern=pat_noren, depth=0.0008,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Sheen=0.45, Translucency=0.06, WornColor=(0.05, 0.07, 0.13), WornRough=0.9,
                   Cavity=0.5),
         concept=['09-neon-ramen-counter.jpg (noren curtains)', '22-brand-board.jpg (indigo robe)'],
         three=dict(env=0.3, sheen=0.45, sheenColor=(0.25, 0.30, 0.45),
                    note='Fade the hem lighter and darken folds via vertex colour.')),
    dict(id='rope', name='Rope (straw, twisted)', category='wood_paper_cloth', tile=0.3, res=512,
         pattern=pat_rope, depth=0.012,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Porosity=1.0, Sheen=0.25, WornColor=(0.45, 0.38, 0.22), WornRough=0.85, Cavity=0.8),
         concept=['22-brand-board.jpg (braided cord)', '04-arrival-gate.jpg (torii)'],
         three=dict(env=0.3, note='Best on twisted geometry with u along the rope.')),
    # ---- metal, ice, glass
    dict(id='iron', name='Iron (black oxide, rust)', category='metal_ice_glass', tile=0.6, res=512,
         pattern=pat_iron, depth=0.002,
         params=dict(wetness=0.0, wear=0.2),
         core=dict(Porosity=0.3, WornColor=(0.42, 0.42, 0.43), WornRough=0.35, WornMetal=1.0, MacroAmount=0.4,
                   Cavity=0.8),
         concept=['04-arrival-gate.jpg (lantern frames)', '17-glacier-plunge.jpg (handrail)'],
         three=dict(env=1.0, note='Metal is binary: 0 in the texture, 1 only where wear exposes bare iron.')),
    dict(id='bronze', name='Bronze (patina, verdigris)', category='metal_ice_glass', tile=0.6, res=512,
         pattern=pat_bronze, depth=0.0015,
         params=dict(wetness=0.0, wear=0.2),
         core=dict(Porosity=0.2, WornColor=(0.80, 0.55, 0.30), WornRough=0.22, WornMetal=1.0, MacroAmount=0.5,
                   Cavity=0.8),
         concept=['04-arrival-gate.jpg (bronze spout, fittings)', '22-brand-board.jpg (bucket hoops)'],
         three=dict(env=1.0)),
    dict(id='glacier_ice', name='Glacier ice', category='metal_ice_glass', tile=2.0, res=512,
         pattern=pat_glacier_ice, depth=0.05, transparent=True, emissive=True,
         params=dict(wetness=0.3, wear=0.0, emissive_level=1.0),
         core=dict(Transmission=0.8, IOR=1.31, Specular=0.5, Porosity=0.0, FoamColor=(0.88, 0.95, 1.0),
                   FoamFromMask=0.6, FrostUp=0.7, EmitStrength=0.6,
                   Absorb=(0.25, 0.72, 0.95), AbsorbDensity=8.0, Scatter=(0.45, 0.78, 1.0), ScatterDensity=3.0,
                   Cavity=0.5),
         concept=['17-glacier-plunge.jpg (ice cave, icicles)'], ref='refs/gen/mat-glacier-ice.png',
         three=dict(env=1.0, transmission=0.0, transparent=False,
                    note='Phone: opaque; base = deep blue (thick) to cyan-white (thin); emissive map = fake '
                         'internal glow x 0.5-1.5 plus a fresnel rim; frost = base.a + world-up mask.')),
    dict(id='lava_glass', name='Thick lava glass', category='metal_ice_glass', tile=2.0, res=512,
         pattern=pat_lava_glass, depth=0.004, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(Transmission=1.0, IOR=1.5, Specular=0.5, Porosity=0.0, FoamColor=(0.75, 0.74, 0.72),
                   FoamFromMask=0.12, Absorb=(0.72, 0.74, 0.62), AbsorbDensity=3.0, Cavity=0.0),
         concept=['13-magma-glass-slide.jpg (glass wall, glass tube)', '04-arrival-gate.jpg (lava window)'],
         ref='refs/gen/mat-lava-glass.png',
         three=dict(env=1.2, transmission=0.0, transparent=True, opacity=0.14,
                    note='Phone: alpha-blended pane, opacity 0.1-0.2 (+ base.a haze), env reflection + fresnel, '
                         'warm amber fresnel tint at grazing angles; add a 30-60 cm condensation band at the '
                         'bottom via vertex colour (raise opacity/roughness).')),
    # ---- water
    dict(id='water_still', name='Still water', category='water', tile=4.0, res=512,
         pattern=pat_water_still, depth=0.004, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, Absorb=(0.03, 0.67, 0.60), AbsorbDensity=3.0, Scatter=(0.2, 0.9, 0.85),
                   ScatterDensity=0.25, Cavity=0.0),
         variants=dict(mirror=dict(tint=(0.30, 0.36, 0.42), roughness_offset=-0.005)),
         concept=['05-mist-corridor.jpg', '15-obsidian-mirror.jpg (variant mirror)', '17-glacier-plunge.jpg'],
         ref='refs/gen/mat-water-teal.png',
         water=dict(depth_colors_srgb={'0.1': [150, 215, 205], '0.5': [0, 170, 170], '2.0': [4, 30, 45]},
                    underglow_srgb=[0, 200, 190], underglow_strength=[0.2, 0.6],
                    normal_layers_m=[0.7, 3.0], caustics='caustics_decal'),
         three=dict(env=1.0, transmission=0.0, transparent=True,
                    note='Phone: no transmission. Depth-fade colour (water.depth_colors_srgb) from scene depth or '
                         'a per-vertex depth attribute, under-glow emissive masked by depth/lightmap, the normal '
                         'texture sampled twice (0.7 m and 3 m, different scroll directions), caustics_decal on '
                         'the floor. Variant mirror (Obsidian Mirror): emissive 0, roughness 0.01, planar reflection.')),
    dict(id='water_river', name='River water', category='water', tile=3.0, res=512,
         pattern=pat_water_river, depth=0.03, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, Absorb=(0.02, 0.72, 0.70), AbsorbDensity=2.6, Scatter=(0.25, 0.95, 0.95),
                   ScatterDensity=0.6, Cavity=0.0),
         concept=['12-lava-tube-lazy-river.jpg', '06-kawagiri-restaurant.jpg'], ref='refs/gen/mat-water-teal.png',
         water=dict(depth_colors_srgb={'0.1': [120, 225, 215], '0.5': [0, 190, 185], '2.0': [0, 60, 75]},
                    underglow_srgb=[0, 210, 200], underglow_strength=[0.5, 1.0], normal_layers_m=[0.7, 3.0],
                    foam='base.a x vertex-colour flow/obstacle mask'),
         three=dict(env=1.0, transmission=0.0, transparent=True,
                    note='Flow-map two-phase scroll of the normal texture (see water-research agent).')),
    dict(id='water_sea', name='Sea water', category='water', tile=6.0, res=512,
         pattern=pat_water_sea, depth=0.18, transparent=True,
         params=dict(wetness=0.0, wear=0.0),
         core=dict(WATER_CORE, Absorb=(0.0, 0.62, 0.72), AbsorbDensity=2.5, Scatter=(0.3, 0.85, 0.9),
                   ScatterDensity=0.2, Cavity=0.0),
         concept=['20-wave-grotto.jpg'],
         water=dict(depth_colors_srgb={'0.1': [130, 210, 205], '0.5': [0, 150, 160], '2.0': [2, 25, 45]},
                    crest_srgb=[60, 220, 210], trough_srgb=[0, 70, 80], foam='base.a (top 12 % of height) + shoreline mask'),
         three=dict(env=1.0, transmission=0.0, transparent=True,
                    note='Swell is vertex animation; this texture is chop + lacy crest foam. Height-driven '
                         'crest/trough colour lerp.')),
    dict(id='waterfall', name='Waterfall sheet', category='water', tile=2.0, res=512,
         pattern=pat_waterfall, depth=0.02, transparent=True, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(WATER_CORE, ThinWall=1.0, AlphaFromMask=1.0, AlphaMin=0.25, EmitStrength=0.25,
                   Absorb=(0.3, 0.85, 0.8), AbsorbDensity=0.0, Cavity=0.0),
         concept=['19-thunder-curtain.jpg', '18-rimstone-terraces.jpg', '06-kawagiri-restaurant.jpg (water curtains)'],
         three=dict(env=0.8, transmission=0.0, transparent=True, side='DoubleSide', depthWrite=False,
                    opacityFromBaseAlpha='0.25 + 0.75*a',
                    note='Scroll v at two speeds/scales (e.g. 1.5 and 2.3 m/s); spray/mist card at the base; '
                         'emissive = foam x 0.25 so it reads bright in a dark cave.')),
    dict(id='caustics_decal', name='Caustics decal', category='water', tile=1.0, res=256,
         pattern=pat_caustics, depth=0.001, transparent=True, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=0.0, AlphaFromMask=1.0, AlphaMin=0.0, EmitStrength=0.6, Specular=0.0, Cavity=0.0),
         concept=['17-glacier-plunge.jpg (pool floor)', '05-mist-corridor.jpg'],
         three=dict(env=0.0, transparent=True, blending='Additive', depthWrite=False,
                    note='Projected / floor decal under water: two layers scrolling in different directions, '
                         'multiplied by depth fade; teal tint x 0.3-1.0.')),
    # ---- light sources
    dict(id='lava', name='Lava (crust field)', category='light', tile=3.0, res=1024,
         pattern=pat_lava, depth=0.06, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=0.0, EmitStrength=1.2, EmitMacro=1.0, MacroAmount=0.5, WornColor=(0.02, 0.018, 0.017),
                   WornRough=0.6, Cavity=0.6),
         concept=['13-magma-glass-slide.jpg (lava behind glass)', '04-arrival-gate.jpg (lava falls)'],
         ref='refs/gen/mat-lava-glass.png',
         three=dict(env=0.4, note='Scroll the emissive 2-5 cm/s and multiply by the macro texture (R) animated '
                                  'slowly (0.7-1.2 pulse) so it never reads as a static repeat.')),
    dict(id='lava_flow', name='Lava (molten flow)', category='light', tile=3.0, res=1024,
         pattern=pat_lava_flow, depth=0.06, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=0.0, EmitStrength=0.8, EmitMacro=1.0, MacroAmount=0.5, WornColor=(0.02, 0.018, 0.017),
                   WornRough=0.6, Cavity=0.4),
         concept=['13-magma-glass-slide.jpg (lava falls)', '04-arrival-gate.jpg (lava window)'],
         ref='refs/gen/mat-lava-glass.png',
         three=dict(env=0.4, note='Mostly molten with dark crust islands, for the lava window and falls. '
                                  'Flow-scroll along v.')),
    dict(id='neon_tube', name='Neon tube', category='light', tile=0.2, res=256,
         pattern=pat_neon, depth=0.0005, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0, tint=hexlin('#ff1493')),
         core=dict(Porosity=0.0, EmitStrength=1.4, EmitCore=1.0, Specular=0.5, Cavity=0.0),
         variants=dict(cyan=dict(tint=hexlin('#00b8ff'))),
         concept=['09-neon-ramen-counter.jpg (magenta/cyan neon)', '06-kawagiri-restaurant.jpg'],
         three=dict(env=0.5, note='Kawagiri only. emissive = mix(tint, white-pink, (1 - fresnel)^2) for a '
                                  'white-hot core and saturated edges, thin glass highlight (rough 0.05), bloom, '
                                  'plus a coloured light card on the wall behind. Cyan variant (#00b8ff) is bluer '
                                  'than the onsen teal on purpose.')),
    dict(id='lantern_paper', name='Lantern paper, round chochin (emissive)', category='light', tile=1.0, res=512,
         uvmode='object', pattern=pat_lantern_paper, depth=0.002, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=1.0, EmitStrength=1.4, Translucency=0.0, ThinFromMask=0.0, Cavity=0.3),
         concept=['22-brand-board.jpg (paper lantern)', '05-mist-corridor.jpg', '12-lava-tube-lazy-river.jpg'],
         ref='refs/gen/mat-hinoki-washi.png',
         three=dict(env=0.2, note='Object UVs: u around the lantern 0..1, v bottom->top 0..1 (scale stays 1). '
                                  'Keep emissive moderate and let bloom do the glow.')),
    dict(id='lantern_andon', name='Lantern paper, square andon (emissive)', category='light', tile=1.0, res=512,
         uvmode='object', pattern=pat_lantern_andon, depth=0.002, emissive=True,
         params=dict(wetness=0.0, wear=0.0, emissive_level=1.0),
         core=dict(Porosity=1.0, EmitStrength=1.4, Translucency=0.0, Cavity=0.3),
         concept=['05-mist-corridor.jpg (andon)', '12-lava-tube-lazy-river.jpg (floating lanterns)'],
         three=dict(env=0.2, note='Object UVs: each paper face mapped 0..1 (frame shadow at the border).')),
]

# shared low-res macro variation (8 m repeat), multiplied in by KZ_Core where MacroAmount > 0
MACRO = dict(id='kz_macro', tile=8.0, res=256)


def pat_macro(b, uv):
    """R brightness (0.5 = x1), G hue (>0.5 cooler/bluer), B wetness/roughness, A vertical
    stain/efflorescence streaks 0.5-2 m."""
    t = b.torus(uv)
    r = (b.noise4(warp(b, t, 0.1, 1.0), scale=1.5, detail=4, rough=0.55) - 0.5) * 1.4 + 0.5
    g = b.noise4(b.torus(uv), scale=1.2, detail=3) * 1.0
    bb = b.noise4(warp(b, t, 0.08, 1.5), scale=2.5, detail=3)
    a = b.noise4(b.torus(uv, ax=1.0, ay=0.25), scale=14, detail=3).smooth(0.62, 0.75) * \
        b.noise4(t, scale=2).smooth(0.4, 0.7)
    return dict(albedo=b.rgb(r.clamp(), g.clamp(), bb.clamp()), mask=a)


# category -> concept crops shown next to it on the contact sheet: (image, (left, top, right, bottom) fractions)
CATEGORIES = [
    ('stone', 'Stone', [('lookbook/img/16-steam-grotto.jpg', (0.0, 0.55, 0.62, 1.0)),
                        ('refs/gen/mat-basalt-wet.png', (0.2, 0.0, 1.0, 0.9))]),
    ('wood_paper_cloth', 'Wood, paper & cloth', [('lookbook/img/05-mist-corridor.jpg', (0.0, 0.0, 0.42, 0.62)),
                                                ('refs/gen/mat-hinoki-washi.png', (0.3, 0.0, 1.0, 1.0))]),
    ('metal_ice_glass', 'Metal, ice & glass', [('lookbook/img/17-glacier-plunge.jpg', (0.0, 0.0, 0.70, 0.62)),
                                               ('refs/gen/mat-lava-glass.png', (0.0, 0.0, 0.6, 1.0))]),
    ('water', 'Water', [('lookbook/img/18-rimstone-terraces.jpg', (0.30, 0.45, 1.0, 1.0)),
                        ('refs/gen/mat-water-teal.png', (0.0, 0.0, 1.0, 1.0))]),
    ('light', 'Light sources', [('lookbook/img/13-magma-glass-slide.jpg', (0.55, 0.0, 1.0, 0.75)),
                                ('lookbook/img/09-neon-ramen-counter.jpg', (0.58, 0.1, 0.72, 0.42))]),
]


# ============================================================ painted plates (round 2b)
# Owner-approved self-made Codex plates (refs/gen/sheet-tex-*.png) are the basis of the
# library: tools/matlib/plates.py cuts, de-lights and quilts them into seamless sets and
# derives height / roughness / masks.  Recipe keys: sheet, idx (row-major 0..5), plate_m =
# metres across the (cropped) source, src_w = working width in px after resampling, out =
# (h, w) output px, block/overlap = quilting, axis ('both' | 'v' along-grain only), rotate,
# joints (crop the source at its outermost vertical joints so boards / culms tile in u),
# crop (y0, y1, x0, x1 fractions), exclude (logo box), albedo_mean (linear), sat, contrast,
# rough (lo, hi, mode), height {bands, weights, sign, dark_deep}, delight {...}, rule.
SHEET = {k: f'refs/gen/sheet-tex-{k}.png' for k in ('stone', 'rock', 'wood', 'cloth')}
B1024 = dict(out=(1024, 1024), block=288, overlap=32)
F1024 = dict(out=(1024, 1024), block=160, overlap=32)
B512 = dict(out=(512, 512), block=160, overlap=32)
BIG = dict(bands=(0.01, 0.05, 0.2), weights=(0.25, 0.45, 0.3))

PLATES = {
    'basalt_wet': dict(sheet='stone', idx=0, plate_m=1.6, src_w=480, **B1024, rotate=False, albedo_mean=0.022,
                       sat=0.6, rough=(0.22, 0.55, 'lum'), height=dict(BIG, dark_deep=0.3),
                       delight=dict(spec_thresh=1.3, spec_sigma=10.0)),
    'basalt_dry': dict(sheet='stone', idx=1, plate_m=1.4, src_w=480, **B1024, rotate=True, albedo_mean=0.024,
                       sat=0.6, rough=(0.62, 0.9, 'lum'), height=dict(BIG, dark_deep=0.45),
                       delight=dict(spec_thresh=2.2), gloss_rough=0.3),
    'paving': dict(sheet='stone', idx=2, plate_m=2.4, src_w=480, **B1024, rotate=True, albedo_mean=0.04, sat=0.5,
                   rough=(0.06, 0.3, 'height'), height=dict(BIG, dark_deep=0.55), delight=dict(spec_thresh=1.6),
                   wet_hollows=0.6),
    'obsidian': dict(sheet='stone', idx=3, plate_m=1.0, src_w=480, **B1024, rotate=True, albedo_mean=0.012,
                     sat=0.3, contrast=0.3, rough=(0.02, 0.12, 'lum'), height=dict(bands=(0.01, 0.04, 0.15),
                     weights=(0.2, 0.5, 0.3), dark_deep=0.25), delight=dict(spec_thresh=1.7), gloss_rough=0.0),
    'rimstone': dict(sheet='stone', idx=4, plate_m=0.8, src_w=480, **B1024, rotate=True, albedo_mean=0.6,
                     sat=0.9, rough=(0.12, 0.55, 'lum'), height=dict(dark_deep=0.2), delight=dict(spec_thresh=2.0)),
    'black_sand': dict(sheet='stone', idx=5, plate_m=0.7, src_w=480, **F1024, rotate=True, albedo_mean=0.014,
                       sat=0.5, rough=(0.72, 0.92, 'lum'), height=dict(dark_deep=0.2), delight=dict(spec_thresh=1.8),
                       gloss_floor=0.08),
    'cave_rock': dict(sheet='rock', idx=0, plate_m=2.0, src_w=480, **B1024, rotate=True, albedo_mean=0.02, sat=0.7,
                      rough=(0.2, 0.5, 'lum'), height=dict(BIG, dark_deep=0.35), delight=dict(spec_thresh=1.6)),
    'stepping_stone': dict(sheet='rock', idx=1, plate_m=0.9, src_w=480, **B1024, rotate=True, albedo_mean=0.025,
                           sat=0.6, rough=(0.05, 0.3, 'lum'), height=dict(BIG, dark_deep=0.3),
                           delight=dict(spec_thresh=1.6)),
    'sinter': dict(sheet='rock', idx=2, plate_m=0.8, src_w=480, **B512, rotate=True, albedo_mean=0.35, sat=1.0,
                   rough=(0.25, 0.6, 'lum'), height=dict(dark_deep=0.15), delight=dict(spec_thresh=2.0)),
    'ash_clay': dict(sheet='rock', idx=3, plate_m=1.8, src_w=480, **B512, rotate=True, albedo_mean=0.15, sat=0.8,
                     rough=(0.75, 0.95, 'lum'), height=dict(BIG, dark_deep=0.3), delight=dict(spec_thresh=2.4)),
    'lava': dict(sheet='rock', idx=4, plate_m=2.0, src_w=480, **B1024, rotate=True, glow=True, rule='lava',
                 albedo_mean=0.012, sat=0.5, rough=(0.45, 0.7, 'lum'), height=dict(BIG),
                 delight=dict(keep_spec=True, grad_strength=0.3)),
    'glacier_ice': dict(sheet='rock', idx=5, plate_m=1.2, src_w=480, **B512, rotate=True, rule='ice',
                        albedo_mean=0.3, sat=1.0, rough=(0.03, 0.25, 'inv'), height=dict(dark_deep=0.0),
                        delight=dict(keep_spec=True, grad_strength=0.5)),
    'hinoki': dict(sheet='wood', idx=0, joints=True, plate_m=0.72, src_w=512, out=(2048, 512), block=288, overlap=32,
                   axis='v', albedo_mean=0.24, sat=0.7, rough=(0.42, 0.62, 'lum'),
                   height=dict(bands=(0.002, 0.008, 0.03), weights=(0.35, 0.45, 0.2), dark_deep=0.3),
                   delight=dict(spec_thresh=2.4)),
    'lacquer_dark': dict(sheet='wood', idx=1, joints=True, plate_m=0.6, src_w=512, out=(1024, 512), block=288,
                         overlap=32, axis='v', albedo_mean=0.022, sat=1.0, rough=(0.06, 0.3, 'lum'),
                         height=dict(bands=(0.002, 0.008, 0.03), weights=(0.4, 0.4, 0.2)),
                         delight=dict(spec_thresh=1.8)),
    'bamboo': dict(sheet='wood', idx=2, joints=True, plate_m=0.6, src_w=512, out=(1024, 512), block=288, overlap=32,
                   axis='v', albedo_mean=0.22, sat=0.9, rough=(0.28, 0.45, 'lum'),
                   height=dict(bands=(0.003, 0.012, 0.04), weights=(0.3, 0.5, 0.2)), delight=dict(spec_thresh=2.2)),
    'tatami': dict(sheet='wood', idx=3, crop=(0.0, 1.0, 0.17, 1.0), plate_m=0.42, src_w=400, **F1024, rotate=False,
                   albedo_mean=0.3, sat=0.9, rough=(0.45, 0.65, 'lum'),
                   height=dict(bands=(0.002, 0.006, 0.02), weights=(0.4, 0.4, 0.2)), delight=dict(spec_thresh=2.4)),
    'washi': dict(sheet='wood', idx=4, plate_m=0.5, src_w=480, **B512, rotate=True, rule='paper', albedo_mean=0.62,
                  sat=0.9, rough=(0.8, 0.9, 'lum'), height=dict(bands=(0.002, 0.01, 0.04), weights=(0.4, 0.4, 0.2)),
                  delight=dict(spec_thresh=2.6)),
    'washi_backlit': dict(sheet='wood', idx=4, plate_m=0.5, src_w=480, **B512, rotate=True, rule='paper_glow',
                          albedo_mean=0.62, sat=0.9, rough=(0.8, 0.9, 'lum'),
                          height=dict(bands=(0.002, 0.01, 0.04), weights=(0.4, 0.4, 0.2)),
                          delight=dict(spec_thresh=2.6)),
    'lantern_paper': dict(sheet='wood', idx=5, rot90=1, plate_m=0.25, src_w=480, **B512, rotate=False, rule='lantern',
                          albedo_mean=0.6, sat=0.8, rough=(0.78, 0.88, 'lum'),
                          height=dict(bands=(0.002, 0.008, 0.03), weights=(0.4, 0.4, 0.2)),
                          delight=dict(spec_thresh=3.0, grad_strength=1.0)),
    'noren': dict(sheet='cloth', idx=0, plate_m=0.45, src_w=480, out=(512, 512), block=80, overlap=16, rotate=False,
                  exclude=(0.13, 0.82, 0.08, 0.95), albedo_mean=0.03, sat=1.0, rough=(0.78, 0.92, 'lum'),
                  height=dict(bands=(0.001, 0.004, 0.015), weights=(0.45, 0.4, 0.15)), delight=dict(spec_thresh=2.6)),
    'rope': dict(sheet='cloth', idx=1, plate_m=0.5, src_w=480, **B512, rotate=True, albedo_mean=0.22, sat=0.9,
                 rough=(0.78, 0.95, 'lum'), height=dict(bands=(0.003, 0.012, 0.04), weights=(0.3, 0.5, 0.2),
                 dark_deep=0.3), delight=dict(spec_thresh=2.4)),
    'bronze': dict(sheet='cloth', idx=2, plate_m=0.8, src_w=480, **B512, rotate=True, rule='bronze',
                   albedo_mean=0.2, sat=0.9, rough=(0.3, 0.55, 'inv'), height=dict(dark_deep=0.2),
                   delight=dict(spec_thresh=2.2, grad_strength=1.0)),
    'iron': dict(sheet='cloth', idx=3, plate_m=0.8, src_w=480, **B512, rotate=False, rule='rust', albedo_mean=0.07,
                 sat=1.0, rough=(0.5, 0.85, 'lum'), height=dict(dark_deep=0.3), delight=dict(spec_thresh=2.2)),
    'water_river': dict(sheet='cloth', idx=4, plate_m=2.0, src_w=480, **B512, rotate=True, rule='foam', water=True,
                        albedo_mean=0.5, sat=1.0, rough=(0.02, 0.05, 'lum'), height=dict(BIG),
                        delight=dict(keep_spec=True, grad_strength=0.5)),
    'water_sea': dict(sheet='cloth', idx=5, plate_m=2.5, src_w=480, **B512, rotate=True, rule='foam', water=True,
                      albedo_mean=0.3, sat=1.0, rough=(0.02, 0.05, 'lum'), height=dict(BIG),
                      delight=dict(keep_spec=True, grad_strength=0.5)),
}


def _plate_geometry():
    for m in MATERIALS:
        p = PLATES.get(m['id'])
        if not p:
            continue
        m['plate'] = dict(p, sheet=SHEET[p['sheet']])
        oh, ow = p['out']
        m['tile'] = round(ow * p['plate_m'] / p['src_w'], 4)
        m['aspect'] = ow / oh
        m['res'] = max(oh, ow)
        m['source'] = f"plate {p['sheet']}#{p['idx']} ({SHEET[p['sheet']]})"
        m.pop('tex_from', None)
        if p.get('rule') in ('lantern', 'paper_glow'):
            m['plate']['colors'] = (EDGE_GLOW, LANTERN)
        if m['id'] == 'water_sea':
            m['depth'] = 0.03


NEW = [
    dict(id='cave_rock', name='Cave rock (ceiling, wet)', category='stone', tile=4.0, res=1024, pattern=pat_basalt,
         depth=0.15, params=dict(wetness=0.5, wear=0.0),
         core=dict(Porosity=0.6, WornColor=(0.05, 0.048, 0.045), WornRough=0.4, MacroAmount=1.0, Cavity=1.0),
         concept=['15-obsidian-mirror.jpg (ceiling)', '12-lava-tube-lazy-river.jpg', '16-steam-grotto.jpg'],
         ref='refs/gen/sheet-tex-rock.png (plate 1)', three=dict(env=0.8)),
    dict(id='stepping_stone', name='Wet stepping stone (top)', category='stone', tile=1.8, res=1024,
         pattern=pat_basalt, depth=0.04, params=dict(wetness=0.8, wear=0.2),
         core=dict(Porosity=0.4, WornColor=(0.05, 0.05, 0.05), WornRough=0.15, MacroAmount=0.5, Cavity=1.0),
         concept=['05-mist-corridor.jpg (stepping stones)'], ref='refs/gen/sheet-tex-rock.png (plate 2)',
         three=dict(env=1.0, note='Mist-corridor stepping stones; waterline ring via vertex colour.')),
    dict(id='sinter', name='Sinter crust (hot-spring mineral)', category='stone', tile=0.85, res=512,
         pattern=pat_rimstone_top, depth=0.02, params=dict(wetness=0.4, wear=0.0),
         core=dict(Porosity=0.5, WornColor=(0.8, 0.75, 0.65), WornRough=0.3, MacroAmount=0.5, Cavity=0.8),
         concept=['14-geyser-plaza.jpg', '18-rimstone-terraces.jpg'], ref='refs/gen/sheet-tex-rock.png (plate 3)',
         three=dict(env=0.7, note='Orange/white mineral crust around vents and geysers.')),
]
_ix = max(i for i, m in enumerate(MATERIALS) if m['category'] == 'stone') + 1
MATERIALS[_ix:_ix] = NEW
_plate_geometry()
