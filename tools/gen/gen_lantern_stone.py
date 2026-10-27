"""Stone toro lantern (lantern_stone). op01 first build.

TARGETS (measured before coding)
  Sheet refs/gen/sheet-mod-lights.png panel 3 (label W 0.90 x D 0.90 x H 1.60; crop .scratch/op01/m_toro.png,
  the 1.60 m arrow = 603 px at 2x, 377 px/m). Parts bottom -> top (height, width):
    base (kiso)        0.27 h, 0.79-0.86 w (label 0.90 spans the base), chamfered / stepped rough top
    shaft (sao)        0.52 h, 0.42 w at the flared foot, 0.34 w at the top
    platform (chudai)  0.13 h, 0.64 w, flared underside
    fire box (hibukuro) 0.27 h, 0.43 w; square 3 x 3 lattice window on the front, round window on the side
    roof (kasa)        0.25 h incl. upturned corners, 0.88 w, eave ~0.06 thick
    neck + jewel (hoju) 0.05 + 0.17 h, 0.19 w
  Drawn total 1.66 m vs label 1.60: built to the label, ratios from the drawing. Lookbook 01 / 11: the same
  dark rough toro by the terraces, moss in the joints, warm window glow.

FEATURES kept at every LOD: stacked rough stone base, fire box with openings, curved roof cap and finial.

PARAMETERS
  h         overall height, m (0.8-2.6; default 1.60 x seed 0.9-1.0, capped at the proxy; 3 m+ is toro_tall)
  base      'tiered' | 'block' | 'rubble'
  window    fire box openings: 'square' (square front, round sides) | 'round' (round all round)
  overhang  roof eave half-width / fire box width, 0.85-1.15 (default by style)
  moss      0..1 amount of moss on the top-facing stone (default by style)
  style     'kasuga' | 'block' | 'rubble' | 'slim' (seeds 1-4 cycle)
SEEDS change shape: base style, shaft length x0.8-1.15 and taper, roof overhang and corner lift, window shape,
  moss amount and the crag noise field (shape, not tint).
MATERIALS: stone = basalt_wet, wetness 0.3, tint (0.45, 0.47, 0.55), normal 1.6. The row lists basalt_dry; it
  rendered pale grey-brown "concrete" in the first canonical against the near-black craggy stone of the sheet
  (GUIDE §7), so the low-wetness basalt_wet is used (report). moss = moss tinted (0.35, 0.42, 0.25) painted on
  top-facing faces at LOD0/1 (row NEW:moss: the library has `moss`), paper = washi_backlit (lit core). kz_lights carries the bake light.
ANIMATION: shader flicker on the washi slot. LIGHT: kz_lights in the fire box, 2300 K, 15 W.
BUDGET 2500 / 1000 / 300 / 100.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_lantern_floor as L
import kzgeo_lantern_stone as T

ASSET = 'lantern_stone'
FEATURES = ['stacked rough stone base', 'fire box with openings', 'curved roof cap', 'finial']
STYLES = ['kasuga', 'block', 'rubble', 'slim']
SDEF = dict(
    kasuga=dict(base='tiered', window='square', overhang=1.0, moss=0.35, shaft=1.0, p=6.0),
    block=dict(base='block', window='round', overhang=1.08, moss=0.2, shaft=0.95, p=3.5),
    rubble=dict(base='rubble', window='square', overhang=1.12, moss=0.45, shaft=0.8, p=5.0),
    slim=dict(base='tiered', window='round', overhang=0.9, moss=0.1, shaft=1.15, p=8.0),
)


def build(lod, seed, h=None, base=None, window=None, overhang=None, moss=None, style=None):
    style = style or C.cycle(seed, STYLES)
    S = SDEF[style]
    base = base or S['base']
    window = window or S['window']
    g = C.rng(seed, 'dims')
    H = h or 1.60 * g.uniform(0.9, 1.0)
    ov = overhang or S['overhang'] * g.uniform(0.95, 1.05)
    moss = S['moss'] if moss is None else moss
    sk = S['shaft'] * g.uniform(0.95, 1.05)
    lift_k = g.uniform(0.7, 1.3)
    taper = g.uniform(0.76, 0.88)

    mb = genlib.MeshBuilder()
    stone = mb.slot('basalt_wet', wetness=0.3, tint=(0.45, 0.47, 0.55), roughness_offset=0.1, normal_strength=1.6)
    paper = mb.slot('washi_backlit', emissive_level=1.0)
    mossm = mb.slot('moss', tint=(0.35, 0.42, 0.25))
    N = C.lod_pick(lod, 28, 12, 8, 4)
    amp = 0.026

    # ---- heights (fractions of the measured 1.60 stack; the shaft takes the seed's length change)
    parts = dict(base=0.27, shaft=0.52 * sk, chudai=0.13, fire=0.27, roof=0.21, hoju=0.22)
    k = H / sum(parts.values())
    hb, hs, hc, hf, hr, hh = (parts[n] * k for n in ('base', 'shaft', 'chudai', 'fire', 'roof', 'hoju'))
    wk = min(1.0, H / 1.45)                  # short toro are narrower too
    z = 0.0

    # ---- base
    gb = C.rng(seed, 'base')
    if base == 'tiered':
        w1, w2 = 0.43 * wk, 0.31 * wk
        h1 = hb * 0.6
        T.block(mb, [(w1 * 0.97, w1 * 0.97, 0.0), (w1, w1, h1 * 0.5), (w1 * 0.98, w1 * 0.98, h1 * 0.85), (w1 * 0.86, w1 * 0.86, h1)]
                if lod <= 1 else [(w1, w1, 0.0), (w1 * 0.98, w1 * 0.98, h1 * 0.85), (w1 * 0.86, w1 * 0.86, h1)],
                N, stone, seed, amp, p=S['p'], lod=lod)
        T.block(mb, [(w2, w2, h1 - 0.02), (w2, w2, hb * 0.85), (w2 * 0.9, w2 * 0.9, hb)], N, stone, seed + 1, amp * 0.8, p=S['p'], lod=lod)
    elif base == 'block':
        w1 = 0.41 * wk
        T.block(mb, [(w1, w1, 0.0), (w1 * 1.01, w1 * 1.01, hb * 0.55), (w1 * 0.9, w1 * 0.9, hb * 0.8), (w1 * 0.62, w1 * 0.62, hb)]
                if lod <= 1 else [(w1, w1, 0.0), (w1 * 0.92, w1 * 0.92, hb * 0.75), (w1 * 0.62, w1 * 0.62, hb)],
                N, stone, seed, amp * 1.3, p=S['p'], lod=lod)
    else:   # rubble: a ring of faceted boulders under a flat cap stone
        nrock = 5 if lod <= 1 else (4 if lod == 2 else 0)
        npts = C.lod_pick(lod, 14, 9, 7, 5)
        a0 = gb.uniform(0, math.pi)
        R = 0.25 * wk
        if lod <= 2:     # core boulder: fills the middle so the cap stone sits on rock, not on 'legs'
            C.hull_rock(mb, (0, 0, 0.0), (0.27 * wk, 0.27 * wk, hb * 0.78), stone, C.rng(seed, 'core'), npts=npts, ground=0.0)
        for i in range(nrock):
            a = a0 + 2 * math.pi * i / 5
            rx = gb.uniform(0.17, 0.21) * wk
            C.hull_rock(mb, (R * math.cos(a), R * math.sin(a), 0.0), (rx, rx * gb.uniform(0.8, 1.0), hb * 0.62), stone,
                        C.rng(seed, f'rock{i}'), npts=npts, ground=0.0)
        if lod >= 3:
            L.open_box(mb, (0, 0, hb * 0.35), (0.8 * wk, 0.8 * wk, hb * 0.7), stone, skip=('bottom',))
        T.block(mb, [(0.30 * wk, 0.30 * wk, hb * 0.55), (0.32 * wk, 0.32 * wk, hb * 0.85), (0.27 * wk, 0.27 * wk, hb)],
                N, stone, seed + 2, amp * 0.8, p=S['p'], lod=lod, cap_bot=lod >= 2)
    z = hb

    # ---- shaft (flared foot, taper, a neck ring under the platform at LOD0)
    s0 = 0.21 * wk
    if lod <= 1:
        rings = [(s0 * 1.1, s0 * 1.1, z - 0.01), (s0, s0, z + hs * 0.12)] + \
                [(s0 * (1 - (1 - taper) * t), s0 * (1 - (1 - taper) * t), z + hs * (0.12 + 0.88 * t)) for t in ((0.2, 0.4, 0.6, 0.8, 1.0) if lod == 0 else (1.0,))]
    else:
        rings = [(s0 * 1.05, s0 * 1.05, z - 0.01), (s0 * taper, s0 * taper, z + hs)]
    T.block(mb, rings, N if lod != 2 else 8, stone, seed + 3, amp * 1.2, p=S['p'] * 0.8, lod=lod)
    z += hs

    # ---- platform (chudai): flared underside, chamfered top
    c0 = 0.32 * wk
    T.block(mb, [(c0 * 0.72, c0 * 0.72, z - 0.01), (c0 * 0.95, c0 * 0.95, z + hc * 0.45), (c0, c0, z + hc * 0.8), (c0 * 0.92, c0 * 0.92, z + hc)]
            if lod <= 2 else [(c0 * 0.75, c0 * 0.75, z - 0.01), (c0, c0, z + hc * 0.7), (c0 * 0.92, c0 * 0.92, z + hc)],
            N, stone, seed + 4, amp, p=S['p'], lod=lod, cap_bot=True)
    z += hc

    # ---- fire box
    Wf = 0.43 * wk
    kz = T.firebox(mb, z, Wf, hf, 0.06 * wk, 'sq' if window == 'square' else 'round', 'round', dict(stone=stone, paper=paper),
                   lod, seed, lattice=(2, 2))
    z += hf

    # ---- roof (kasa): eave with lifted corners, concave slope, a small top seat
    e = 0.44 * wk * min(1.02, ov)
    rise = hr * 0.72
    lift = 0.05 * lift_k * wk * (lod <= 2)
    th = hr - rise
    if lod == 0:
        rr = [(Wf * 0.55, Wf * 0.55, z - 0.005), (e * 0.96, e * 0.96, z + th * 0.15, lift * 0.85), (e, e, z + th * 0.55, lift),
              (e * 0.97, e * 0.97, z + th, lift), (e * 0.7, e * 0.7, z + th + rise * 0.22, lift * 0.35),
              (e * 0.42, e * 0.42, z + th + rise * 0.58, 0.0), (e * 0.24, e * 0.24, z + th + rise * 0.9), (e * 0.2, e * 0.2, z + th + rise)]
    elif lod == 1:
        rr = [(Wf * 0.55, Wf * 0.55, z - 0.005), (e, e, z + th * 0.4, lift), (e * 0.97, e * 0.97, z + th, lift),
              (e * 0.55, e * 0.55, z + th + rise * 0.4, 0.0), (e * 0.2, e * 0.2, z + th + rise)]
    elif lod == 2:
        rr = [(Wf * 0.55, Wf * 0.55, z - 0.005), (e, e, z + th, lift), (e * 0.45, e * 0.45, z + th + rise * 0.55), (e * 0.2, e * 0.2, z + th + rise)]
    else:
        rr = [(e, e, z), (e * 0.2, e * 0.2, z + th + rise)]
    T.block(mb, rr, N, stone, seed + 5, amp * 0.9, p=12.0 if lod <= 2 else 40.0, lod=lod, cap_bot=lod >= 3)
    z += hr

    # ---- jewel
    T.hoju(mb, z - 0.005, 0.09 * wk, hh * (1.15 if style == 'slim' else 1.0), stone, lod, 0.08 * wk)

    if lod <= 1:    # moss patches need the small faces of LOD0/1; at LOD2/3 one face would turn green whole
        T.moss_paint(mb, {stone}, mossm, seed, moss)
    d = Vector(C.centre_base(mb))
    o = mb.to_object(ASSET)
    genlib.finish(o)
    L.lights_props(o, [kz + d], 2300, 15, [paper],
                   dict(style=style, h=round(H, 3), base=base, window=window, overhang=round(ov, 3), moss=moss))
    return o
