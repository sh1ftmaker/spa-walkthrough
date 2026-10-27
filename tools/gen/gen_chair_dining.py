"""Pod dining chair (chair_dining) for the Kawagiri chair pods (T4 armchairs; T5, T6, T10-T12 side chairs).

Identifying features kept at every LOD: low hinoki chair with a dark cushion; armchair variant with broad
arms (07 section A-A).

Targets (07 section A-A, crop .scratch/op19/c07_chairs.png; the printed 1:50 bar over-reads the scene,
so heights are scaled off the 0.75 m table beside the chairs: table 59 px, seat 36 px, arm 50 px, back
frame 70 px, pillow top 79 px)
  * seat (cushion top) 0.46 m, arm 0.63 m, back frame 0.89 m, pillow top ~1.0 m. Row/proxy: 0.6 x 0.6 x
    0.8 with back h 0.6-0.9 and seat 0.35-0.45, so I build seat 0.40-0.45, back frame 0.76-0.84 (inside
    the proxy +5 %) and keep the pillow below the top rail. Proposed proxy h 0.9 to match the drawing.
  * armchair ~0.60 wide, 0.58 deep; square near-black legs ~0.045 m; flat broad arms ~0.10 m wide that
    run past the front post; a deep apron under the seat; amber seat cushion ~0.06 m; a large dark
    pillow leaning on the back.
Construction
  * frame `hinoki` walnut (the darkest hinoki, #33221a neutral; 'stained' now calibrates mid-brown): four square legs (6 mm chamfers), the rear legs run up
    as back posts; a 60 mm apron on four sides; a seat board; two low side stretchers and a front one.
  * back: a top rail (seeded 'ears' overhang), a low back rail and a seeded filling: 3-5 vertical slats,
    2-3 ladder rails, or a solid panel.
  * seat cushion: `noren` pillow 50-70 mm with a rolled edge (no knife edge). Colour amber | black |
    indigo | vermilion (amber is the cream variant warmed). Back pillow: `noren` black, 0.09-0.11 thick,
    leaning 12-18 degrees, on every armchair and on half the side chairs.
  * armchair: front legs rise to arm posts; broad flat arms 0.09-0.11 x 0.03 m, front overhang 30-45 mm;
    a side rail under each arm.
  * LOD1: same parts as boxes, pillows with 1-segment corners. LOD2: legs, seat, cushion, back panel,
    top rail, pillow, arms as boxes. LOD3: one extruded side silhouette (rear post, seat, front leg; arm
    level on the armchair) with the cushion and pillow colours on the seat top and the back face.
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 0.6 x 0.6 x 0.8 m)
  style    side | armchair        (default: cycles with the seed: odd side, even armchair)
  seat_h   0.35-0.45 m (cushion top; default seeded 0.40-0.45)
  back_h   0.6-0.9 m (top rail; default seeded 0.76-0.82 side, 0.80-0.84 armchair)
  cushion  amber | black | indigo | vermilion (default seeded; seed 2 is amber as in 07)
  w, d     frame width 0.46-0.60, depth 0.48-0.60 (default seeded; side-chair ears add up to 0.08)
Seeds change: style, back filling (slats/ladder/panel), slat count, ear overhang, back height, seat width
and depth, leg size, cushion colour and thickness, pillow presence and lean.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import genlib
import kzgeo_bridge_arched as KG
import kzgeo_common as C
import kzgeo_table_low as KT

ASSET = 'chair_dining'
FEATURES = ['low hinoki chair', 'dark cushion', 'armchair with broad arms']
STYLES = ['side', 'armchair']
CUSHION = {'amber': ('cream', (0.95, 0.62, 0.34)), 'black': ('black', None), 'indigo': (None, None),
           'vermilion': ('vermilion', None)}


def _noren(mb, name):
    var, tint = CUSHION.get(name, CUSHION['black'])
    kw = {}
    if var:
        kw['variant'] = var
    if tint:
        kw['tint'] = tint
    return mb.slot('noren', **kw)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build(lod, seed, style=None, seat_h=None, back_h=None, cushion=None, w=None, d=None):
    style = style or C.cycle(seed, STYLES)
    arm = style == 'armchair'
    g = C.rng(seed, 'dims')
    W = _clamp(w, 0.46, 0.60) if w else (g.uniform(0.56, 0.59) if arm else g.uniform(0.48, 0.52))
    D = _clamp(d, 0.48, 0.60) if d else g.uniform(0.52, 0.58)
    SH = _clamp(seat_h, 0.35, 0.45) if seat_h else g.uniform(0.40, 0.45)
    BH = _clamp(back_h, 0.6, 0.9) if back_h else (g.uniform(0.80, 0.84) if arm else g.uniform(0.76, 0.82))
    L = g.uniform(0.04, 0.05)
    gb = C.rng(seed, 'back')
    fill = gb.choice(['slats', 'slats', 'ladder', 'panel'])
    n_slat = gb.randint(3, 5)
    n_rung = gb.randint(2, 3)
    ears = 0.0 if arm else gb.choice([0.0, 0.025, 0.04])
    gc = C.rng(seed, 'cushion')
    cu = cushion or ('amber' if seed == 2 else gc.choice(['black', 'amber', 'indigo', 'vermilion']))
    CT = gc.uniform(0.05, 0.07)
    pillow_on = arm or gc.random() < 0.5
    lean = math.radians(gc.uniform(12, 18))
    ga = C.rng(seed, 'arms')
    AW = ga.uniform(0.09, 0.11)
    AO = ga.uniform(0.03, 0.045)
    ZA = SH + ga.uniform(0.17, 0.20)

    mb = genlib.MeshBuilder()
    m_wood = mb.slot('hinoki', variant='walnut', wear=0.15)
    m_seat = _noren(mb, cu)
    m_pil = mb.slot('noren', variant='black')

    zb = SH - CT                 # top of the seat board (cushion sits on it)
    yb, yf = -D / 2, D / 2       # back / front
    x0 = W / 2 - L / 2           # leg centre x
    yr = yb + L / 2              # rear leg centre y
    yfl = yf - L / 2             # front leg centre y

    if lod == 3:
        zl = ZA if arm else zb
        zu = (ZA - 0.10) if arm else (zb - 0.08)
        prof = [(yb, 0.0), (yb + L, 0.0), (yb + L, zu), (yf - L, zu), (yf - L, 0.0), (yf, 0.0), (yf, zl),
                (yb + L, zl), (yb + L, BH), (yb, BH)]
        em = {7: m_pil if pillow_on else m_wood}
        if not arm:
            em[6] = m_seat
        KT.extrude_profile(mb, prof, -W / 2, W / 2, m_wood, axis='x', edge_mats=em)
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    def bar(c, size, axis='z'):
        if lod == 0:
            C.chamfered_bar(mb, c, size, m_wood, ch=0.005, axis=axis)
        else:
            mb.box(c, size, m_wood)

    def plank(c, size, segs=1):
        if lod == 0:
            C.board(mb, c, size, m_wood, bevel=0.004, segs=segs)
        else:
            mb.box(c, size, m_wood)

    # legs: rear legs run up as back posts, front legs rise to arm posts on the armchair
    for sx in (-1, 1):
        bar((sx * x0, yr, BH / 2), (L, L, BH))
        ftop = ZA - 0.015 if arm else zb
        bar((sx * x0, yfl, ftop / 2), (L, L, ftop))

    # seat board and apron
    plank((0, 0, zb - 0.01), (W - 2 * L + 0.01, D - 2 * L + 0.01, 0.02))
    AP = 0.06
    za = zb - 0.02 - AP / 2
    if lod <= 1:
        for sy, yy in ((-1, yr), (1, yfl)):
            plank((0, yy, za), (W - 2 * L, 0.022, AP))
        for sx in (-1, 1):
            plank((sx * x0, 0, za), (0.022, D - 2 * L, AP))
        # low stretchers: both sides and the front
        zst = 0.14
        for sx in (-1, 1):
            plank((sx * x0, 0, zst), (0.022, D - 2 * L, 0.03))
        plank((0, yfl - 0.005, zst + 0.05), (W - 2 * L, 0.02, 0.03))
    else:
        plank((0, 0, za), (W - 2 * L, D - 2 * L, AP))

    # back: top rail with seeded ears, low back rail, filling
    TR = 0.06
    ztr = BH - TR / 2 - 0.005
    plank((0, yr, ztr), (W - 2 * L + 2 * (L + ears) if ears else W - 2 * L, 0.03, TR), segs=2)
    zlo = SH + 0.06
    zhi = ztr - TR / 2
    if lod <= 1:
        plank((0, yr, zlo), (W - 2 * L, 0.025, 0.04))
        span = W - 2 * L
        if fill == 'slats':
            for k in range(n_slat):
                x = -span / 2 + span * (k + 0.5) / n_slat
                plank((x, yr, (zlo + zhi) / 2), (0.032, 0.018, zhi - zlo))
        elif fill == 'ladder':
            for k in range(n_rung):
                z = zlo + (zhi - zlo) * (k + 1) / (n_rung + 1)
                plank((0, yr, z), (span, 0.022, 0.035))
        else:
            plank((0, yr, (zlo + zhi) / 2), (span, 0.016, zhi - zlo + 0.02))
    else:
        mb.box((0, yr, (zlo + zhi) / 2), (W - 2 * L, 0.018, zhi - zlo + 0.02), m_wood)

    # seat cushion
    cw, cd = W - 0.02, D - 0.03
    if lod <= 1:
        C.pillow(mb, (0, 0.005, zb), cw, cd, CT * 0.82, m_seat, rc=0.045, m=C.lod_pick(lod, 2, 1),
                 puff=CT * 0.18, edge_w=0.012, edge_k=0.45)
    else:
        mb.box((0, 0.005, zb + CT / 2), (cw, cd, CT), m_seat)

    # back pillow, leaning on the back
    if pillow_on:
        PW = W - 2 * L - 0.04
        PT = gc.uniform(0.09, 0.11)
        PH = min(BH - SH - 0.04, 0.42)
        lay = mb._mark_old()
        if lod <= 1:
            C.pillow(mb, (0, 0, -PT / 2), PW, PH, PT * 0.7, m_pil, rc=0.06, m=C.lod_pick(lod, 2, 1),
                     puff=PT * 0.15, edge_w=0.015, edge_k=0.45)
        else:
            mb.box((0, 0, 0), (PW, PH, PT), m_pil)
        vs = list({v for f in mb._new_faces(lay) for v in f.verts})
        # stand it up: local +Y (pillow height) -> up and leaning back by `lean`; local +Z (puffed face) ->
        # the front. Then rest it on the cushion against the front of the back frame.
        U = Vector((0, -math.sin(lean), math.cos(lean)))
        N = Vector((0, math.cos(lean), math.sin(lean)))
        for v in vs:
            x, y, z = v.co
            v.co = Vector((x, 0, 0)) + y * U + z * N
        dy = (yr + 0.022) - min(v.co.y for v in vs)
        dz = (SH - 0.012) - min(v.co.z for v in vs)
        for v in vs:
            v.co.y += dy
            v.co.z += dz

    # armchair: broad flat arms and a side rail under each
    if arm:
        for sx in (-1, 1):
            xa = sx * (W / 2 - AW / 2 + 0.01)
            al = (yf + AO) - (yr - L / 2)
            if lod == 0:
                C.board(mb, (xa, (yf + AO + yr - L / 2) / 2, ZA), (AW, al, 0.03), m_wood, bevel=0.008, segs=2)
            else:
                mb.box((xa, (yf + AO + yr - L / 2) / 2, ZA), (AW, al, 0.03), m_wood)
            if lod <= 1:
                plank((sx * x0, 0, (zb + ZA) / 2 + 0.02), (0.022, D - 2 * L, 0.035))

    C.centre_base(mb)
    o = genlib.finish(mb.to_object(ASSET))
    KG.uv_grain(o, [m_wood])                # grain along legs, rails, slats and arms
    return o
