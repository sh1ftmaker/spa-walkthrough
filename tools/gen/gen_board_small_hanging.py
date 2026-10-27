"""Small hanging board (temperature / table number): a hinoki plate in a dark stained frame, hung by a cord
or an iron back-bracket. Read by the guest at 2-5 m: the numeral is the identifying part.

Targets (measured):
  - lookbook/img/16-steam-grotto.jpg, the 45 degree board (crop .scratch/gen40_n/board45.png, 1600x900 source):
    outer frame ~87 x 86 px, so w:h = 1.0; frame border ~0.12 of the width (~0.06 m at 0.52 m);
    the numeral fills ~60 % of the plate width; cap height ~0.31 of the board width; a small kanji line above;
    iron corner rivets on the frame. No scale bar exists for this board, so sizes come from the row.
  - Row: w 0.3-0.7, h 0.3-0.6, depth 0.08 m. Default w 0.52, h 0.50, plus a hang cord 0.08 m above:
    bbox 0.52 x 0.08 x 0.58 (proxy 0.70 x 0.08 x 0.60). The row's typical 0.7 x 0.6 would be 1.17:1;
    the concept is ~1:1, so the default follows the concept. For h above ~0.52 the cord goes past the proxy
    height: propose proxy h 0.66 if the bigger boards are needed.
  - Frame border 0.06 m, chamfer 4 mm (LOD0), plate 12 mm thick, relief 6 mm.

Parameters: w, h (m), text (numeral; default by seed: 1 '45°', 2 'T7', 3 '6°C', 4 '55°', 5 'T12', 6 '65°'),
label (bool: the small line above the numeral), hang ('cord' | 'bracket'; default by seed).

Seeds change the shape, not only the tint: seed 1 is the 45 degree board (wide frame, cord), seed 2 a
shorter-framed table plate 'T7' with no label line and a taller board, seed 3 the '6°C' plunge board on
an iron bracket with two rivets. Seeds also set the numeral and the plate grain tint.

Budget note: the numeral is raised text. Closed glyph solids ('45°' at res 1) cost 296 tris; op22 builds
them open at the back (kzgeo_board_small_hanging.open_text: front + walls, the back sits on the plate),
which saves the back faces. The kanji line would cost 536 tris at res 1, so it is an ink block.
LOD0 and LOD1 both keep the numeral at res 1 (no pop between them). The row budget 200/80/30/10 cannot
hold raised numerals; proposed budget in the op22 report.

Materials: frame hinoki 'walnut' (darkest timber in the library, calibrated #33221a neutral; dark_timber
#4d3124 rendered mid-orange in r2), plate hinoki 'natural', ink lacquer_black, cord rope,
hardware iron. Animation: none. Lighting: lightmap.

LOD: LOD0 chamfered frame, plate, rivets, cord, numeral res 1, label block. LOD1 box frame, cord, numeral
res 1, label block, straight cords. LOD2 one frame block with front quads (plate, numeral block, label
block) and a cord card or bracket stub. LOD3 a 10-tri open box (the silhouette).
"""
import genlib
import kzgeo_board_small_hanging as B
import kzgeo_common as C
from mathutils import Vector

ASSET = 'board_small_hanging'
FEATURES = ['hinoki board in a dark stained frame', 'pale plate with black numeral',
            'hang cord or bracket', 'iron corner rivets']
TEXTS = ['45°', 'T7', '6°C', '55°', 'T12', '65°']     # row: 45/55/65 degree pools, 6 C plunge, tables T1-T12


def _em_width(text, font, tracking):
    """total width of `text` at cap height 1.0, laid out like C.tracked_text"""
    _, (rx0, ry0, rx1, ry1) = C.glyph_tris('H', font, 2)
    s = 1.0 / max(1e-6, ry1)
    total = 0.0
    for ch in text:
        if ch == ' ':
            total += 0.3 * s
            continue
        groups, (x0, y0, x1, y1) = C.glyph_tri_groups(ch, font, 2)
        total += ((x1 - x0) if groups else 0.3) * s
    return total + tracking * max(0, len(text) - 1)


def _lowpoly_box(mb, W, D, H, mi):
    """open-back box for LOD3: 5 quads = 10 tris"""
    bm = mb.bm
    v = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0, 1):
                v[(sx, sy, z)] = bm.verts.new((sx * W / 2, sy * D / 2, z * H))
    quads = [
        ((-1, -1, 0), (1, -1, 0), (1, -1, 1), (-1, -1, 1)),     # front
        ((-1, 1, 0), (-1, -1, 0), (-1, -1, 1), (-1, 1, 1)),     # left
        ((1, -1, 0), (1, 1, 0), (1, 1, 1), (1, -1, 1)),         # right
        ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),       # top
        ((-1, 1, 0), (1, 1, 0), (1, -1, 0), (-1, -1, 0)),       # bottom
    ]
    faces = [bm.faces.new([v[k] for k in q]) for q in quads]
    mb._tag(faces, mi)
    return faces


def build(lod, seed, w=None, h=None, text=None, label=True, hang=None):
    p = genlib.proxy(ASSET)
    text = text or C.cycle(seed, TEXTS)
    if seed == 2:
        label = False                       # seed 2: numeral only
    if hang is None:
        hang = C.cycle(seed, ['cord', 'cord', 'bracket'])     # seed 3 hangs from a bracket
    r = C.rng(seed, 'board')
    W = (w or 0.52) * (0.92 if seed == 2 else 1.0)
    H = (h or 0.50) * (1.08 if seed == 2 else 1.0)
    W = min(W, p['w'] * 0.99)
    H = min(H, 0.52 * 1.08)
    fb = 0.06 * (0.8 if seed == 2 else 1.0)
    D = 0.08
    cord = 0.08
    rivets = 2 if seed == 3 else 4
    grain = r.uniform(0.95, 1.05)

    mb = genlib.MeshBuilder()
    frame = mb.slot('hinoki', variant='walnut')
    plate = mb.slot('hinoki', variant='natural', tint=(grain, grain * 0.97, grain * 0.9))
    ink = mb.slot('lacquer_black')
    rope = mb.slot('rope')
    iron = mb.slot('iron')

    if lod == 3:
        _lowpoly_box(mb, W, D, H, frame)
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))
    if lod == 2:                     # frame block + front quads (plate, numeral, label) + cord card / bracket
        mb.box((0, 0, H / 2), (W, D, H), frame)
        bm = mb.bm

        def quad(cx, cz, qw, qh, y, mi):
            vs = [bm.verts.new((cx + a * qw / 2, y, cz + b * qh / 2)) for a, b in ((1, -1), (-1, -1), (-1, 1), (1, 1))]
            mb._tag([bm.faces.new(vs)], mi)
        iw, ih = W - 2 * fb, H - 2 * fb
        quad(0, H / 2, iw, ih, D / 2 + 0.001, plate)
        nz = H / 2 - (0.09 * ih if label else 0.0)
        quad(0, nz, 0.7 * iw, 0.32 * ih, D / 2 + 0.002, ink)
        if label:
            quad(0, H / 2 + 0.33 * ih, 0.35 * iw, 0.10 * ih, D / 2 + 0.002, ink)
        if hang == 'cord':
            C.rope_cord(mb, (0, 0, H), (0, 0, H + cord), 0.008, rope, sides=1)
        else:
            mb.box((0, -D / 2 + 0.004, H + 0.02), (0.012, 0.008, 0.04), iron)
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    # frame: four bars (chamfered at LOD0, boxes at LOD1-2); the bars butt at the corners
    ch = 0.004 if lod == 0 else 0.0
    bars = [((W, D, fb), (0, 0, H - fb / 2), 'x'), ((W, D, fb), (0, 0, fb / 2), 'x'),
            ((fb, D, H - 2 * fb), (-(W / 2 - fb / 2), 0, H / 2), 'z'),
            ((fb, D, H - 2 * fb), (W / 2 - fb / 2, 0, H / 2), 'z')]
    for size, c, ax in bars:
        if ch > 0:
            C.chamfered_bar(mb, c, size, frame, ch=ch, axis=ax)
        else:
            mb.box(c, size, frame)

    # plate behind the frame's front edge, so the frame reads as a border
    inner_w, inner_h = W - 2 * fb, H - 2 * fb
    C.board(mb, (0, 0, H / 2), (inner_w + 0.004, 0.012, inner_h + 0.004), plate, bevel=0.002 if lod == 0 else 0.0)
    y_face = 0.006
    cap = min(0.5 * inner_h, 0.70 * inner_w / max(1e-6, _em_width(text, C.FONT_LATIN, 0.08)))
    num_z = H / 2 - (0.09 * inner_h if label else 0.0)
    label_z = H / 2 + 0.33 * inner_h
    if lod <= 1:
        B.open_text(mb, text, 0.0, num_z, y_face, cap, ink, depth=0.006, font=C.FONT_LATIN, tracking=0.08, res=1)
        if label:
            mb.box((0, y_face + 0.003, label_z), (0.35 * inner_w, 0.006, 0.10 * inner_h), ink)
    else:
        mb.box((0, y_face + 0.003, num_z), (0.7 * inner_w, 0.006, cap * 0.7), ink)
        if label:
            mb.box((0, y_face + 0.003, label_z), (0.35 * inner_w, 0.006, 0.10 * inner_h), ink)

    # hanging: a cord from the two top corners to one eye above the centre, or an iron bracket
    if hang == 'cord':
        eye = Vector((0, 0, H + cord))
        if lod <= 1:
            n = 4
            for sx in (-1, 1):
                C.rope_cord(mb, (sx * (W / 2 - fb / 2) * 0.85, 0, H - 0.005), eye, 0.0045 if lod == 0 else 0.006,
                            rope, sides=n, twist=lod == 0, seg_len=0.035)
            mb.sphere((0, 0, H + cord), 0.012 if lod == 0 else 0.016, iron, segs=4, rings=3)
        else:
            mb.cylinder((0, 0, H + cord / 2), radius=0.006, depth=cord, mi=rope, segs=4)
    else:
        mb.box((0, -D / 2 + 0.004, H - 0.03), (0.12, 0.008, 0.07), iron)           # back plate at the top edge
        if lod <= 1:
            mb.cylinder((0, -D / 2 - 0.002, H + 0.03), radius=0.007, depth=0.06, mi=iron, segs=6 if lod == 0 else 4)

    # iron rivets on the frame corners (LOD0 only)
    if lod == 0:
        pts = [(-1, 1), (1, 1), (-1, -1), (1, -1)][:rivets]
        for sx, sz in pts:
            mb.cylinder((sx * (W / 2 - fb / 2), D / 2 + 0.002, H - fb / 2 if sz > 0 else fb / 2), radius=0.007,
                        depth=0.006, mi=iron, segs=6, rot=(1.5707963, 0, 0))

    C.centre_base(mb)
    return genlib.finish(mb.to_object(ASSET))
