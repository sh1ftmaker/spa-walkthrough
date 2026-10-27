"""Floor cushion (zabuton) for the Kawagiri floor pods (T1-T3, T7-T9), s_moon and the suites.

Identifying features kept at every LOD: thick square cushion with a tufted centre, dark or patterned cloth.

Targets (measured before coding)
  * sheet-mod-kawagiri #1 (dining pod, 5.0 m bar = 318 px, 64 px/m): cushions 0.60-0.65 m wide, about
    0.10 m thick with a strongly rolled edge and a domed top, dark indigo-black cloth, set on the deck
    beside a 0.33 m floor table.
  * 21 private suite (crop .scratch/op19/c21.png): a ~0.6 m square, ~0.08-0.10 m thick cushion with a
    woven brown top (tatami-like) and a darker bound edge; corners only slightly rounded.
  * Row: w 0.5-0.7, thickness 0.06-0.12, dims 0.6 x 0.6 x 0.1 (proxy). A real zabuton is slightly deeper
    than wide (55 x 59 cm), with a three-thread tuft (shoe-ito) at the centre that pulls a dimple.
  Built: W 0.55-0.62, D = W x 1.0-1.06, shoulder thickness 0.065-0.085 + 16-24 mm dome (total <= 0.11),
  edge rolls to 30-45 % of T over two rings (no knife edge), dimple r 0.08-0.11 m sinking 18-28 mm.

Construction
  * one closed cushion (kzgeo_zabuton_cushion.cushion): rings from the outline in to a centre pole, with a
    tuft ring, a border seam ring (bordered pattern) and a 25-35 mm rolled shoulder.
  * tuft: a small cloth button and three crossed thread tufts (contrast colour) in the dimple.
  * patterns: plain (one noren colour), bordered (centre panel + a 0.10-0.13 m border band and sides in a
    second colour), woven (tatami top as in 21, noren black binding on the shoulder and sides).
  * LOD1: 1-segment corners, button only. LOD2: square outline, dimple as a sunk centre pole, border
    colour on the shoulder. LOD3: a 12-triangle slab in the top colour.
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 0.6 x 0.6 x 0.1 m)
  w        0.5-0.7 m (default seeded 0.55-0.62)
  thickness 0.06-0.12 m (shoulder thickness; default seeded 0.07-0.095)
  pattern  plain | bordered | woven (default: cycles with the seed: 1 plain, 2 bordered, 3 woven)
  colour   black | indigo | vermilion | cream (default seeded; dark colours twice as likely)
Seeds change: pattern, size, depth/width ratio, thickness, dome, corner radius (crisp 25 mm to soft 70 mm),
edge roll, dimple size and depth, border width, colour.
"""
import genlib
import kzgeo_common as C
import kzgeo_zabuton_cushion as K

ASSET = 'zabuton_cushion'
FEATURES = ['thick square cushion', 'tufted centre', 'dark or patterned cloth']
PATTERNS = ['plain', 'bordered', 'woven']
VARIANT = {'black': 'black', 'indigo': None, 'vermilion': 'vermilion', 'cream': 'cream'}


def _cloth(mb, colour):
    v = VARIANT.get(colour)
    return mb.slot('noren', variant=v) if v else mb.slot('noren')


def build(lod, seed, w=None, thickness=None, pattern=None, colour=None):
    pattern = pattern or C.cycle(seed, PATTERNS)
    g = C.rng(seed, 'shape')
    W = max(0.5, min(0.7, w)) if w else g.uniform(0.55, 0.62)
    D = min(W * g.uniform(1.0, 1.06), 0.64)
    T = max(0.06, min(0.12, thickness)) if thickness else g.uniform(0.065, 0.085)
    puff = g.uniform(0.016, 0.024)
    rc = g.choice([0.025, 0.04, 0.07])
    edge_k = g.uniform(0.3, 0.45)
    edge_w = g.uniform(0.025, 0.035)
    gt = C.rng(seed, 'tuft')
    tuft_r = gt.uniform(0.08, 0.11)
    tuft_d = gt.uniform(0.018, 0.028)
    gc = C.rng(seed, 'colour')
    colour = colour or gc.choice(['black', 'black', 'indigo', 'indigo', 'vermilion', 'cream'])
    second = gc.choice([c for c in ('black', 'indigo', 'vermilion', 'cream') if c != colour])
    band = gc.uniform(0.10, 0.13)

    mb = genlib.MeshBuilder()
    if pattern == 'woven':
        m_top = mb.slot('tatami', tint=(0.62, 0.48, 0.34))
        m_side = mb.slot('noren', variant='black')
        m_border = m_side
        border_s = None
    elif pattern == 'bordered':
        m_top = _cloth(mb, colour)
        m_side = _cloth(mb, second)
        m_border = m_side
        border_s = 1.0 - band / (min(W, D) / 2)
    else:
        m_top = _cloth(mb, colour)
        m_side = m_top
        m_border = None
        border_s = None
    m_thread = mb.slot('noren', variant='vermilion' if colour != 'vermilion' else 'cream')

    if lod == 3:
        mb.box((0, 0, (T + puff) / 2), (W, D, T + puff), m_top)
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    K.cushion(mb, W, D, T, m_top, m_side, m=C.lod_pick(lod, 2, 1, 0), rc=rc, puff=puff, edge_k=edge_k,
              edge_w=edge_w, tuft_r=tuft_r, tuft_d=tuft_d, edge_mid=lod == 0,
              border_s=border_s if lod <= 1 else None, mi_border=m_border,
              top_rings=C.lod_pick(lod, [0.55], None, [0.45]), tuft_ring=lod <= 1)

    # tuft: button and three crossed threads, sitting in the dimple
    if lod <= 1:
        zt = T + puff - tuft_d
        br = 0.012
        segs = C.lod_pick(lod, 8, 6)
        C.lathe(mb, [(br, zt - 0.004), (br * 0.85, zt + 0.006), (0.0, zt + 0.008)], segs, m_thread)
        if lod == 0:
            import math
            for k in range(3):
                a = math.pi * k / 3 + gt.uniform(-0.15, 0.15)
                dx, dy = 0.03 * math.cos(a), 0.03 * math.sin(a)
                C.stick(mb, (-dx, -dy, zt + 0.001), (dx, dy, zt + 0.001), 0.003, 0.003, m_thread, segs=4)

    C.centre_base(mb)
    o = mb.to_object(ASSET)
    return genlib.finish(o)
