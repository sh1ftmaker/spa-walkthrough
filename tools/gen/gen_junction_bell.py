"""Bronze junction bell in a two-post timber frame, with a hanging log striker (b1_junction_w, 1-3 instances).
Lookbook: after 22:00 a small bell at each junction is the only sound.

Targets (measured on refs/gen/sheet-vs-grotto-garden.png #3 'BRONZE JUNCTION BELL', label W 0.8 x D 0.6 x H 1.8;
crop .scratch/op15/bell_panel.png at 2x: frame 1.8 m = 670 px -> 372 px/m on the front view; the 0.8 m label
spans the beam, so widths are taken at the label scale and heights at the 1.8 m frame):
  - frame: two square posts 0.12 m on post centres +-0.27 m; crossbeam 0.80 x 0.14 x 0.15 overhanging the
    posts by ~0.08 m; iron strap plates (4 bolts) on the beam over each post; iron shoe sleeves (0.2 m, bolted)
    at the post feet; stone plinths 0.30 x 0.30 x 0.13 (cut in two blocks on the sheet).
  - a short striker arm along y on top of the beam over the right post, carrying the striker rope ring at
    y ~ +0.38 (side view: the top piece runs forward past the post; this is what makes D 0.6).
  - bell: verdigris bronze, body h:d 1.53 (0.72 x 0.47 m at the bar, 0.58 x 0.38 m built: the row caps bell h
    at 0.6), lip at z ~0.50, three grooved bands above the lip, a raised middle band, four vertical bands
    (kesa) dividing the upper zone into panels, each with a grid of bosses (2-3 rows x 3), a lotus striking
    seat front and back, a domed crown and a dragon loop (ryuzu) on an iron ring and U strap under the beam.
  - striker: a 0.30 m log (r 0.045) along y, hung level at z ~0.74 from the arm by a rope, rope wraps at both
    ends, a pull-rope tail below.

Parameters:
  bell_h   0.30-0.60 m bell body height (default 0.58 / 0.45 / 0.52 by seed); lip radius 0.33 x bell_h
  h        1.60-2.00 m frame height (default 1.80 / 1.70 / 1.65)
  roof     True / False small gabled kawara board roof on the beam (default False / True / False; it sits
           inside h: the posts get shorter)
  striker  'log' (hanging shumoku) | 'mallet' (wooden mallet hanging from the arm)  (default log / mallet / log)
Seeds change (row: 2 seeds; seed 3 is an alternate): bell size and boss rows (3 / 2 / 3), frame height, roof,
striker style, plinth shape (two-block / single), post chamfer.

Materials: hinoki dark_timber (posts, beam, arm, roof boards), hinoki walnut (striker log / mallet), bronze
smooth tinted (0.6, 1.3, 1.4) (bell: the plain 'patina' variant rendered as dark crumpled foil, the smooth one
brown; the tint pushes it toward the sheet's verdigris green-grey),
iron (straps, plates, bolts, shoes, ring, U strap), rope (striker rope), basalt_wet wetness 0.4 (plinths),
kawara (roof).
Animation (rigid, rare swing when struck): vertex groups 'bell' (bronze) and 'striker' (log / mallet + rope);
obj['kz_anim'] gives the pivots (bell about the ring under the beam, swing axis x; striker about the arm ring,
axis x). Lighting: lightmap only, no lights.
LOD: LOD0 all of the above. LOD1 same parts, 14-seg bell, one boss row per panel, no bolts, plain boxes.
LOD2 8-seg bell with the lip and crown, posts, beam, arm, shoes, plinths, log on a card rope. LOD3: posts, beam,
5-seg bell (~56 tris).
"""
import math

from mathutils import Matrix, Vector

import genlib
import kzgeo_common as C

ASSET = 'junction_bell'
FEATURES = ['bronze temple bell with bands, boss panels and a dragon loop', 'two-post timber frame with iron straps',
            'stone plinths and iron shoes', 'hanging log striker on a rope']

# bell outer profile, (r / lip radius, z / bell height), bottom to top
_OUT0 = [(1.0, 0.0), (1.04, 0.015), (1.04, 0.06), (1.0, 0.07), (1.025, 0.10), (1.025, 0.13), (0.99, 0.14),
         (1.01, 0.18), (1.01, 0.205), (0.975, 0.215), (0.965, 0.45), (0.985, 0.46), (0.985, 0.49), (0.955, 0.50),
         (0.93, 0.86), (0.86, 0.95), (0.6, 0.995), (0.0, 1.0)]
_OUT1 = [(1.0, 0.0), (1.04, 0.02), (1.04, 0.06), (1.0, 0.07), (1.01, 0.18), (0.985, 0.215), (0.98, 0.47),
         (0.93, 0.86), (0.82, 0.96), (0.45, 1.0), (0.0, 1.0)]
_OUT2 = [(1.0, 0.0), (1.04, 0.05), (0.97, 0.3), (0.93, 0.86), (0.7, 0.98), (0.0, 1.0)]
_OUT3 = [(1.03, 0.0), (0.9, 0.85), (0.0, 1.0)]
_IN = [(0.86, 0.0), (0.8, 0.82), (0.0, 0.9)]

RES = {
    0: dict(segs=20, prof=_OUT0, inner=True, boss_rows=None, bolts=True, cham=0.012, seat=2, loop=10, rope=(6, 0.08),
            wraps=True, plates=True),
    1: dict(segs=12, prof=_OUT1, inner=True, boss_rows=1, bolts=False, cham=0.0, seat=1, loop=6, rope=(4, 0.09),
            wraps=False, plates=True),
    2: dict(segs=8, prof=_OUT2, inner=False, boss_rows=0, bolts=False, cham=0.0, seat=0, loop=0, rope=(2, 0.3),
            wraps=False, plates=False),
    3: dict(segs=5, prof=_OUT3, inner=False, boss_rows=0, bolts=False, cham=0.0, seat=0, loop=0, rope=(0, 0),
            wraps=False, plates=False),
}


def params(seed, h=None, bell_h=None, roof=None, striker=None):
    P = dict(H=float(h or C.cycle(seed, [1.80, 1.70, 1.65])), Hb=float(bell_h or C.cycle(seed, [0.58, 0.45, 0.52])),
             roof=C.cycle(seed, [False, True, False]) if roof is None else bool(roof),
             striker=striker or C.cycle(seed, ['log', 'mallet', 'log']))
    P['boss_rows'] = C.cycle(seed, [3, 2, 3])
    P['plinth'] = C.cycle(seed, ['split', 'single', 'single'])
    g = C.rng(seed, 'frame')
    P['post_w'] = 0.12 + g.uniform(-0.008, 0.008)
    P['post_x'] = 0.27
    P['R'] = 0.33 * P['Hb']
    return P


def _vgroup(o, name, mats):
    idx = set()
    for poly in o.data.polygons:
        if poly.material_index in mats:
            idx.update(poly.vertices)
    vg = o.vertex_groups.new(name=name)
    vg.add(sorted(idx), 1.0, 'REPLACE')


def _rot_new(mb, lay, M):
    """apply matrix M to the verts of every face built since `lay` was marked"""
    vs = {v for f in mb._new_faces(lay) for v in f.verts}
    for v in vs:
        v.co = M @ v.co


def build(lod, seed, h=None, bell_h=None, roof=None, striker=None, **_):
    P = params(seed, h, bell_h, roof, striker)
    R_ = RES[lod]
    H, Hb, R = P['H'], P['Hb'], P['R']
    px, pw = P['post_x'], P['post_w']
    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant='dark_timber')
    bronze = mb.slot('bronze', variant='smooth', tint=(0.6, 1.3, 1.4))   # smooth brown bronze pushed toward verdigris
    iron = mb.slot('iron')
    stone = mb.slot('basalt_wet', wetness=0.4)
    logm = mb.slot('hinoki', variant='walnut')
    rope = mb.slot('rope')
    roof_m = mb.slot('kawara')

    roof_h = 0.16 if P['roof'] else 0.0
    beam_h, beam_d = 0.15, 0.14
    arm_h = 0.1
    z_top = H - roof_h                          # top of the arm (the highest timber under the roof)
    z_bt = z_top - arm_h                        # top of the beam
    z_bb = z_bt - beam_h                        # beam underside
    zm = 0.50 if Hb >= 0.5 else 0.56            # bell mouth height
    zl = 0.74                                   # striker log height
    yS0, yS1 = 0.12, 0.38                       # striker log along y
    yr = 0.25                                   # striker rope (arm ring)
    ya0, ya1 = -0.16, 0.39                      # striker arm along y
    xs = -px                                    # striker on the viewer's right seen from the front (+Y), as on the sheet
    plh = 0.13

    # ------------------------------------------------------------ LOD3 silhouette
    if lod == 3:
        for sx in (-1, 1):
            mb.box((sx * px, 0, z_bb / 2), (pw, pw, z_bb), wood)
        mb.box((0, 0, (z_bb + z_top) / 2), (0.8, beam_d, z_top - z_bb), wood)
        C.lathe(mb, [(1.03 * R, 0), (0.9 * R, 0.85 * Hb), (0.0, Hb)], 5, bronze, base=(0, 0, zm), closed=False)
        bm = mb.bm
        q = [bm.verts.new((xs + dx_, yy, z_top - arm_h / 2 + dz_)) for yy in (ya0, ya1)
             for dx_, dz_ in ((-0.04, -0.05), (0.04, -0.05), (0.04, 0.05), (-0.04, 0.05))]
        mb._tag(C.bridge_rings(bm, q[:4], q[4:]), wood)                       # arm: open-ended tube (8 tris)
        if P['roof']:
            qs = [bm.verts.new(v) for v in ((-0.42, -0.24, z_top), (0.42, -0.24, z_top), (0.42, 0, H), (-0.42, 0, H),
                                             (0.42, 0.24, z_top), (-0.42, 0.24, z_top))]
            mb._tag([bm.faces.new((qs[0], qs[1], qs[2], qs[3])), bm.faces.new((qs[3], qs[2], qs[4], qs[5]))], roof_m)
        C.centre_base(mb)
        o = mb.to_object(ASSET)
        return genlib.finish(o)

    # ------------------------------------------------------------ plinths, shoes, posts
    for sx in (-1, 1):
        x = sx * px
        if P['plinth'] == 'split' and lod <= 1:
            for sy in (-1, 1):
                C.board(mb, (x, sy * 0.076, plh / 2), (0.3, 0.148, plh), stone, bevel=0.012 if lod == 0 else 0.0)
        else:
            C.board(mb, (x, 0, plh / 2), (0.3, 0.3, plh), stone, bevel=0.015 if lod == 0 else 0.0)
        if R_['cham']:
            C.chamfered_bar(mb, (x, 0, (plh + z_bb) / 2), (pw, pw, z_bb - plh), wood, ch=R_['cham'])
        else:
            mb.box((x, 0, (plh + z_bb) / 2), (pw, pw, z_bb - plh), wood)
        sh = 0.2
        mb.box((x, 0, plh + sh / 2), (pw + 0.025, pw + 0.025, sh), iron)                 # iron shoe sleeve
        if R_['bolts']:
            for (dx, dy) in ((0, 1), (0, -1)):
                for bz in (0.1,):
                    for off in (-0.035, 0.035):
                        cx = x + dx * (pw / 2 + 0.014) + (off if dy else 0)
                        cy = dy * (pw / 2 + 0.014) + (off if dx else 0)
                        rot = (math.pi / 2, 0, 0) if dy else (0, math.pi / 2, 0)
                        mb.cylinder((cx, cy, plh + bz), 0.011, 0.008, iron, segs=4, rot=rot)

    # ------------------------------------------------------------ beam, arm, straps, roof
    bl = 2 * px + pw + 0.16
    if R_['cham']:
        C.chamfered_bar(mb, (0, 0, (z_bb + z_bt) / 2), (bl, beam_d, beam_h), wood, ch=R_['cham'], axis='x')
        C.chamfered_bar(mb, (xs, (ya0 + ya1) / 2, (z_bt + z_top) / 2), (0.085, ya1 - ya0, arm_h), wood, ch=0.01, axis='y')
    else:
        mb.box((0, 0, (z_bb + z_bt) / 2), (bl, beam_d, beam_h), wood)
        mb.box((xs, (ya0 + ya1) / 2, (z_bt + z_top) / 2), (0.085, ya1 - ya0, arm_h), wood)
    if R_['plates']:
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * px, sy * (beam_d / 2 + 0.004), (z_bb + z_bt) / 2), (0.15, 0.008, beam_h - 0.01), iron)
                if R_['bolts']:
                    for bx, bz in ((-0.045, 0.045), (0.045, -0.045)):
                        if True:
                            mb.cylinder((sx * px + bx, sy * (beam_d / 2 + 0.01), (z_bb + z_bt) / 2 + bz), 0.011, 0.008,
                                        iron, segs=4, rot=(math.pi / 2, 0, 0))
        # U strap round the beam centre carrying the bell ring, and the arm strap for the striker rope
        for sy in (-1, 1):
            mb.box((0, sy * (beam_d / 2 + 0.006), (z_bb + z_bt) / 2 - 0.03), (0.05, 0.012, beam_h + 0.06), iron)
        mb.box((0, 0, z_bb - 0.04), (0.05, beam_d + 0.024, 0.014), iron)
        mb.box((xs, yr, z_bt - 0.02), (0.1, 0.05, 0.012), iron)
    if P['roof']:
        rw_, rd_ = bl, 0.44
        if R_['cham']:
            C.chamfered_bar(mb, (-xs, 0, (z_bt + z_top) / 2), (0.085, 0.3, arm_h), wood, ch=0.01, axis='y')
        else:
            mb.box((-xs, 0, (z_bt + z_top) / 2), (0.085, 0.3, arm_h), wood)       # roof bearer on the other post
        for sy in (-1, 1):
            C.board(mb, (0, sy * rd_ / 4, z_top + roof_h / 2 - 0.05), (rw_, rd_ / 2 + 0.03, 0.035), roof_m,
                    rot=(sy * -math.atan2(roof_h * 0.8, rd_ / 2), 0, 0), bevel=0.006 if lod == 0 else 0.0)
        mb.box((0, 0, z_top + roof_h - 0.06), (rw_, 0.07, 0.06), roof_m)                   # ridge
        for sx in (-1, 1):
            mb.box((sx * xs, 0, z_top + (roof_h - 0.06) / 2), (0.06, 0.06, roof_h - 0.06), wood)            # ridge struts (tsuka)

    # ------------------------------------------------------------ bell
    segs = R_['segs']
    base = (0, 0, zm)
    prof = [(R * r, Hb * z) for r, z in R_['prof']]
    if R_['inner']:
        prof = [(R * r, Hb * z) for r, z in _IN[::-1]] + prof          # hollow: inner crown down to the lip, then out
    C.lathe(mb, prof, segs, bronze, base=base, phase=math.pi / segs)
    if lod <= 1:
        # kesa bands: four vertical raised straps on the upper body (z 0.5 .. 0.86 Hb)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            rr = R * 0.955
            zc = zm + Hb * 0.68
            M = Matrix.Translation((rr * math.cos(a), rr * math.sin(a), zc)) @ Matrix.Rotation(a, 4, 'Z') @ \
                Matrix.Rotation(-math.atan2(0.025 * R, 0.36 * Hb), 4, 'Y')
            lay = mb._mark_old()
            mb.box((0, 0, 0), (0.016, 0.028, Hb * 0.36), bronze)
            _rot_new(mb, lay, M)
        # bosses (chi) in the four panels
        rows = P['boss_rows'] if R_['boss_rows'] is None else R_['boss_rows']
        for k in range(4):
            a0 = k * math.pi / 2 + math.pi / 4
            for i in range(3):
                a = a0 + (i + 1) * (math.pi / 2) / 4
                for j in range(rows):
                    z = 0.84 - 0.1 * j * (3 / max(rows, 3))
                    rb = R * (0.93 + (0.86 - z) * 0.11)
                    c = Vector((rb * math.cos(a), rb * math.sin(a), zm + Hb * z))
                    lay = mb._mark_old()
                    C.lathe(mb, [(0.015, 0.0), (0.012, 0.012), (0.0, 0.02)], 4, bronze, phase=math.pi / 4)
                    _rot_new(mb, lay, Matrix.Translation(c) @ Vector((0, 0, 1)).rotation_difference(
                        Vector((math.cos(a), math.sin(a), 0))).to_matrix().to_4x4())
        # lotus striking seats front / back, and a chevron emblem on the front
        for sy in ((1, -1) if R_['seat'] == 2 else (1,)):
            zc = zm + Hb * 0.3
            yc = sy * R * 0.975
            mb.cylinder((0, yc + sy * 0.006, zc), 0.065 * Hb / 0.58, 0.014, bronze, segs=12 if lod == 0 else 8,
                        rot=(math.pi / 2, 0, 0), radius2=0.055 * Hb / 0.58)
            if lod == 0:
                mb.cylinder((0, yc + sy * 0.016, zc), 0.03 * Hb / 0.58, 0.012, bronze, segs=8, rot=(math.pi / 2, 0, 0))
        if lod == 0:
            for sx in (-1, 1):
                lay = mb._mark_old()
                mb.box((0, 0, 0), (0.11 * Hb / 0.58, 0.01, 0.018), bronze)
                _rot_new(mb, lay, Matrix.Translation((sx * 0.045 * Hb / 0.58, R * 0.975, zm + Hb * 0.4))
                         @ Matrix.Rotation(sx * 0.45, 4, 'Y'))
    # crown: dragon loop on a boss, iron ring
    zc = zm + Hb
    if R_['loop']:
        C.lathe(mb, [(0.06 * Hb / 0.58, 0.0), (0.05 * Hb / 0.58, 0.02), (0.0, 0.03)], 8, bronze, base=(0, 0, zc - 0.005))
        n = R_['loop']
        lr = 0.055 * Hb / 0.58
        pts = [(lr * math.cos(math.pi * k / (n - 1)), 0, zc + 0.015 + lr * 1.1 * math.sin(math.pi * k / (n - 1)))
               for k in range(n)]
        C.tube(mb, pts, [0.016 * Hb / 0.58] * n, bronze, sides=6 if lod == 0 else 4, cap0=True, cap1=True)
        top = zc + 0.015 + lr * 1.1
        # iron ring linking the loop to the U strap
        rc = 0.03
        rpts = [(0, rc * math.cos(2 * math.pi * k / 10), top + rc + rc * math.sin(2 * math.pi * k / 10)) for k in range(10)]
        rings, faces = C.tube(mb, rpts, [0.007] * 10, iron, sides=4)
        faces += C.bridge_rings(mb.bm, rings[-1], rings[0])
        mb._tag(faces, iron)
        C.stick(mb, (0, 0, top + 2 * rc - 0.005), (0, 0, z_bb - 0.035), 0.01, 0.01, iron, segs=4)
    else:
        mb.box((0, 0, (zc + z_bb) / 2), (0.03, 0.03, z_bb - zc), iron)

    # ------------------------------------------------------------ striker
    sides, sl = R_['rope']
    if P['striker'] == 'log':
        segs_l = 12 if lod == 0 else 8 if lod == 1 else 6
        mb.cylinder((xs, (yS0 + yS1) / 2, zl), 0.045, yS1 - yS0, logm, segs=segs_l, rot=(math.pi / 2, 0, 0))
        if lod == 0:
            for yy in (yS0 + 0.05, yS1 - 0.05):
                C.rope_band(mb, (xs, yy, zl), (0, 1, 0), 0.045, 0.03, rope)
        hang_to = zl + 0.045
        tail = (zl - 0.045, zl - 0.33)
    else:
        # wooden mallet hanging head-down from the arm on a short rope
        mb.cylinder((xs, yr, zl + 0.05), 0.05, 0.16, logm, segs=12 if lod == 0 else 6, rot=(0, math.pi / 2, 0))
        mb.cylinder((xs, yr, zl + 0.3), 0.016, 0.42, logm, segs=6 if lod == 0 else 4)
        hang_to = zl + 0.51
        tail = None
    if sides >= 3:
        C.rope_cord(mb, (xs, yr, z_bt - 0.025), (xs, yr, hang_to), 0.008, rope, sides=sides, seg_len=sl)
        if tail:
            C.rope_cord(mb, (xs, yr, tail[0]), (xs, yr, tail[1]), 0.007, rope, sides=sides, seg_len=sl)
    elif sides == 2:
        C.rope_cord(mb, (xs, yr, z_bt - 0.025), (xs, yr, hang_to), 0.01, rope, sides=2)

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    _vgroup(o, 'bell', {bronze})
    _vgroup(o, 'striker', {logm, rope})
    C.set_json_props(o, kz_anim={
        'bell': {'pivot': [round(dx, 3), round(dy, 3), round(z_bb - 0.04, 3)], 'axis': 'x', 'max_deg': 4,
                 'trigger': 'striker'},
        'striker': {'pivot': [round(xs + dx, 3), round(yr + dy, 3), round(z_bt - 0.025, 3)], 'axis': 'x', 'max_deg': 30},
    }, kz_params=dict(h=H, bell_h=Hb, roof=P['roof'], striker=P['striker']))
    return genlib.finish(o)
