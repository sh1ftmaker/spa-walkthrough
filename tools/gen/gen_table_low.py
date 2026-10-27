"""Low hinoki table (table_low): dining, floor (tea) and side tables for Kawagiri pods and the suites.

Identifying features kept at every LOD: wet-dark hinoki table top on short legs; small side table version.

Targets (measured before coding)
  * 07 section A-A (chair pod, 1:50, bar 0-5 m = 235 px at 1600 w): table top to floor 59 px against the
    chair back 79 px and seat 36 px; with the row's 0.75 m table that gives seat 0.46, back 1.0 (pillow).
    Top is a thick dark slab (~1/12 of the height, 0.06 m) on square near-black legs (~0.09 m) with an
    apron; no stretchers. Row dims 2.0 x 0.9 x 0.75 (proxy).
  * sheet-mod-kawagiri #1 (dining pod, 5 m platform = 318 px): floor table ~2.0 m long, top ~0.33 m above the
    deck, top 0.07 m thick, chunky square legs ~0.10 m, deep apron; zabutons beside it.
  * 08 close-up: wet, dark-brown plank top with strong grain and glossy reflections (planks along the
    long axis).
  * 21 private suite: small dark side table, thick plank top on block (slab) ends, ~0.5 x 0.4 x 0.4 m.
  Built: dining 1.5-2.0 x 0.80-0.90 x 0.72-0.75, top 0.05-0.065; tea 1.2-1.8 x 0.70-0.85 x 0.32-0.36,
  top 0.06-0.08, legs 0.09-0.12; side 0.50-0.70 x 0.38-0.45 x 0.33-0.45, top 0.04-0.05.

Construction
  * top: 1-4 planks along X (count by style and seed), each a board with a 6 mm rounded edge, so the
    joints read as V-grooves; `hinoki` dark_timber with wetness 0.5 (wet-dark, glossy).
  * legs 'post' form: four square legs with 6 mm chamfers and a 25 mm apron rail on all four sides
    (tenoned under the top); 'panel' form: two slab ends with a foot notch, a low through-stretcher whose
    tenons show 30 mm past the slabs (dining and side) or none (tea). Legs, apron, slabs: `lacquer_dark`.
  * LOD1: same parts, 1-step chamfers, square legs. LOD2: single-slab top, legs, long apron rails / slabs.
    LOD3: one extruded front silhouette (top + two legs, ~28 tris).
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 2.0 x 0.9 x 0.75 m)
  style   dining | tea | side        (default: cycles with the seed: 1 dining, 2 tea, 3 side, 4 dining ...)
  w       0.5-2.0 m   d 0.4-0.9 m   h 0.3-0.75 m   (defaults seeded inside the style's range)
  top_t   top thickness 0.035-0.09 m
  legs    post | panel               (default: seeds 1-3 post, 4-6 panel)
Seeds change: style, leg form, length, depth, height, plank count (1-4), top thickness, overhang, leg size.
"""
import math

import genlib
import kzgeo_bridge_arched as KG
import kzgeo_common as C
import kzgeo_table_low as K

ASSET = 'table_low'
FEATURES = ['wet-dark hinoki table top', 'short square legs', 'small side table version']
STYLES = ['dining', 'tea', 'side']
RANGES = {  # w, d, h, top_t, leg, apron, planks
    'dining': ((1.5, 2.0), (0.80, 0.90), (0.72, 0.75), (0.05, 0.065), (0.085, 0.10), (0.07, 0.09), (3, 4)),
    'tea': ((1.2, 1.8), (0.70, 0.85), (0.32, 0.36), (0.06, 0.08), (0.09, 0.12), (0.06, 0.08), (2, 3)),
    'side': ((0.50, 0.70), (0.38, 0.45), (0.33, 0.45), (0.04, 0.05), (0.05, 0.065), (0.04, 0.05), (1, 2)),
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build(lod, seed, style=None, w=None, d=None, h=None, top_t=None, legs=None):
    style = style or C.cycle(seed, STYLES)
    legs = legs or ('post' if ((seed - 1) // 3) % 2 == 0 else 'panel')
    R = RANGES[style]
    g = C.rng(seed, 'dims')
    W = _clamp(w, 0.5, 2.0) if w else g.uniform(*R[0])
    D = _clamp(d, 0.4, 0.9) if d else g.uniform(*R[1])
    H = _clamp(h, 0.3, 0.75) if h else g.uniform(*R[2])
    T = _clamp(top_t, 0.035, 0.09) if top_t else g.uniform(*R[3])
    L = g.uniform(*R[4])
    AP = g.uniform(*R[5])
    np_ = g.randint(*R[6])
    ov_x = g.uniform(0.06, 0.14) * (0.5 if style == 'side' else 1.0)
    ov_y = g.uniform(0.04, 0.07) * (0.6 if style == 'side' else 1.0)
    gp = C.rng(seed, 'planks')
    widths = [gp.uniform(0.8, 1.2) for _ in range(np_)]
    s = sum(widths)
    widths = [D * x / s for x in widths]

    mb = genlib.MeshBuilder()
    m_top = mb.slot('hinoki', variant='dark_timber', wetness=0.5)
    m_leg = mb.slot('lacquer_dark')
    zt0 = H - T                      # underside of the top

    # LOD3: one extruded front silhouette (top + two legs)
    if lod == 3:
        xi = W / 2 - ov_x - L
        prof = [(-W / 2, H), (-W / 2, 0.0), (-xi, 0.0), (-xi, zt0 - AP), (xi, zt0 - AP), (xi, 0.0), (W / 2, 0.0),
                (W / 2, H)]
        K.extrude_profile(mb, prof, -D / 2, D / 2, m_leg, axis='y', edge_mats={7: m_top})
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    # top
    if lod == 2:
        C.board(mb, (0, 0, zt0 + T / 2), (W, D, T), m_top, bevel=0.0)
    else:
        y = -D / 2
        for pw in widths:
            C.board(mb, (0, y + pw / 2, zt0 + T / 2), (W, pw, T), m_top,
                    bevel=C.lod_pick(lod, 0.006, 0.004), segs=C.lod_pick(lod, 2, 1))
            y += pw

    lx = W / 2 - ov_x - L / 2        # leg / slab centre x
    ly = D / 2 - ov_y - L / 2        # leg centre y
    if legs == 'post':
        for sx in (-1, 1):
            for sy in (-1, 1):
                c = (sx * lx, sy * ly, zt0 / 2)
                if lod == 0:
                    C.chamfered_bar(mb, c, (L, L, zt0), m_leg, ch=0.006, axis='z')
                else:
                    mb.box(c, (L, L, zt0), m_leg)
        # apron rails, set 10 mm in from the leg faces
        ra = 0.025
        zc = zt0 - AP / 2
        bev = C.lod_pick(lod, 0.004, 0.0, 0.0)
        for sy in (-1, 1):
            C.board(mb, (0, sy * (ly + L / 2 - 0.01 - ra / 2), zc), (2 * lx - L, ra, AP), m_leg, bevel=bev)
        if lod <= 1:
            for sx in (-1, 1):
                C.board(mb, (sx * (lx + L / 2 - 0.01 - ra / 2), 0, zc), (ra, 2 * ly - L, AP), m_leg, bevel=bev)
    else:
        # slab ends with a foot notch, extruded along X
        sd = 2 * ly + L              # slab depth = leg footprint depth
        notch_h = min(0.03, zt0 * 0.12)
        fw = min(0.10, sd * 0.22)
        prof = [(-sd / 2, 0.0), (-sd / 2 + fw, 0.0), (-sd / 2 + fw, notch_h), (sd / 2 - fw, notch_h), (sd / 2 - fw, 0.0),
                (sd / 2, 0.0), (sd / 2, zt0), (-sd / 2, zt0)]
        if lod == 2:
            prof = [(-sd / 2, 0.0), (sd / 2, 0.0), (sd / 2, zt0), (-sd / 2, zt0)]
        for sx in (-1, 1):
            K.extrude_profile(mb, prof, sx * lx - L / 2, sx * lx + L / 2, m_leg, axis='x')
        # under-top battens joining the slabs (one each side), and a low through-stretcher
        bev = C.lod_pick(lod, 0.004, 0.0, 0.0)
        if lod <= 1:
            for sy in (-1, 1):
                C.board(mb, (0, sy * (sd / 2 - 0.05), zt0 - AP / 2), (2 * lx - L, 0.03, AP), m_leg, bevel=bev)
        if style != 'tea':
            zs = max(notch_h + 0.05, zt0 * 0.22)
            sh = 0.05 if style == 'dining' else 0.035
            ext = 0.03 if lod <= 1 else 0.0
            C.board(mb, (0, 0, zs), (2 * lx + L + 2 * ext, 0.035, sh), m_leg, bevel=bev)

    C.centre_base(mb)
    o = genlib.finish(mb.to_object(ASSET))
    KG.uv_grain(o, [m_top, m_leg])          # grain along each plank, leg and rail
    return o
