"""Sparse slatted Kawagiri deck (deck_slatted): hinoki boards laid across the walking direction with open
gaps on longitudinal stringers, so the river shows through. Per-metre asset; walk collision stays solid.

Targets (no elevation sheet; measured off the lookbook):
  lookbook 06 (Kawagiri restaurant): the dining decks are boards across the walk on stringers that bear
  on the pier cap beams; the river is visible between the stringers. Seated diners (~1.2 m) give a board
  of ~0.12 m and a stringer pitch of ~0.6-0.9 m. lookbook 08: deck boards with dark open joints.
  lookbook 34 (B2 plan, 147 px / 20 m): the Kawagiri spine is 3-4 m wide, gangways 2 m.
  Row: boards ~0.12 m with ~0.06 m gaps; board 0.10-0.14, gap 0.04-0.08; width 2-4 m.
  Built: board 0.035 thick (rounded top edges, 2-segment, 10 mm), stringers 0.09 wide x 0.085 deep so the
  whole deck is 0.12 m (proxy h 0.12: the deck sits on pier_trestle cap beams, snap 'given'); stringer
  pitch 0.55-0.95 m; boards overhang the outer stringers by 0.04-0.06 m.

Proxy (w 3.0, d 2.0, h 0.12): the module runs along X; default width 2.0 (row minimum, proxy d). Per-metre:
the default module is 1.0 m so genlib.check measures the row's per-metre budget (900/360/120/30).

Parameters build(lod, seed, **p)
  length    run length when no path is given (default 1.0)
  path      polyline [(x, y, z), ...] of the deck centreline (z = deck top offset)
  width     2.0-4.0 (default 2.0)
  board     board width 0.10-0.14 (seeded per style)   gap  0.04-0.08 (seeded per style)
  stringer  stringer spacing 0.55-0.95 (seeded per style)
  style     even | rustic | strapped (default cycles with the seed)
Seeds change shape: seed 1 'even' (0.12 boards / 0.06 gaps, 4 stringers, square ends);
seed 2 'rustic' (each board 0.10-0.14 and each gap 0.04-0.08 drawn, ragged ends +-4 cm, warped boards
+-1.5 deg / +-4 mm, 3 stringers, ~1 in 5 boards replaced in darker oiled timber); seed 3 'strapped'
(0.14 boards / 0.075 gaps, 4 stringers, iron flat bars bolted over the board ends on both edges).
LOD0 rounded-top boards, chamfered stringers, an iron bolt head at every board-stringer crossing.
LOD1 all boards and stringers as boxes, bolts as flat iron quads. LOD2 boards and stringers without
hidden faces (gaps stay as real geometry, so no alpha card is needed). LOD3 boards as top quads,
stringers as one card each (the gaps still read from above).
Materials: boards hinoki natural (wear 0.3; replaced boards wet_oiled), stringers hinoki dark_timber,
bolts and straps iron. Props: kz_deck_z, kz_collision (solid box: the walk does not fall through the
gaps), kz_params. Animation none. Lighting lightmap.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_boardwalk as K

ASSET = 'deck_slatted'
FEATURES = ['boards ~12 cm across the walk', 'open gaps ~6 cm (river visible)', 'stringers below']
STYLES = ['even', 'rustic', 'strapped']
SD = {'even': dict(board=(0.12, 0.12), gap=(0.06, 0.06), stringer=0.62, ragged=0.0, warp=0.0, swap=0.0, straps=False),
      'rustic': dict(board=(0.10, 0.14), gap=(0.04, 0.08), stringer=0.90, ragged=0.04, warp=1.5, swap=0.2, straps=False),
      'strapped': dict(board=(0.14, 0.14), gap=(0.075, 0.075), stringer=0.62, ragged=0.0, warp=0.4, swap=0.0, straps=True)}
BT, SH, SW = 0.035, 0.085, 0.09        # board thickness, stringer depth, stringer width


def build(lod, seed, length=1.0, path=None, width=2.0, board=None, gap=None, stringer=None, style=None):
    style = style or C.cycle(seed, STYLES)
    S = SD[style]
    g = C.rng(seed, ASSET + ':layout')
    b0, b1 = (board, board) if board else S['board']
    g0, g1 = (gap, gap) if gap else S['gap']
    sp = stringer or S['stringer'] * g.uniform(0.95, 1.05)
    P = K.run_path(path, length)
    L, W = P.L, width
    over = 0.05
    n_str = max(2, int(round((W - 2 * over - SW) / sp)) + 1)
    s_off = [-(W / 2 - over - SW / 2) + (W - 2 * over - SW) * k / (n_str - 1) for k in range(n_str)]

    rb = C.rng(seed, ASSET + ':boards')
    boards = []
    for s, w in K.plank_layout(L, lambda: (rb.uniform(b0, b1), rb.uniform(g0, g1))):
        boards.append(dict(s=s, w=w, dz=rb.uniform(-1, 1) * S['warp'] * 0.0027, yaw=math.radians(rb.uniform(-1, 1) * S['warp']),
                           l0=rb.uniform(0, S['ragged']), l1=rb.uniform(0, S['ragged']), swap=rb.random() < S['swap']))

    mb = genlib.MeshBuilder()
    m_board = mb.slot('hinoki', variant='natural', wear=0.3)
    m_swap = mb.slot('hinoki', variant='wet_oiled', wear=0.2)
    m_str = mb.slot('hinoki', variant='dark_timber')
    m_iron = mb.slot('iron')
    zt = BT + SH
    fr = K.frames(P, K.stations(P, 0.25))

    # ---------------- stringers (bear on the pier cap beams)
    for off in s_off:
        if lod == 0:
            prof = [(x, z - SH / 2) for x, z in K.profile('oct', SW, SH, 0.01)]
            K.hsweep(mb, fr, prof, m_str, off=off, z=SH)
        elif lod == 1:
            K.hsweep(mb, fr, [(-SW / 2, -SH), (SW / 2, -SH), (SW / 2, 0), (-SW / 2, 0)], m_str, off=off, z=SH)
        elif lod == 2:
            K.hsweep(mb, fr, [(-SW / 2, 0), (-SW / 2, -SH), (SW / 2, -SH), (SW / 2, 0)], m_str, off=off, z=SH,
                     caps=(False, False), skip=(3,))
        else:
            K.hsweep(mb, fr, [(0, 0), (0, -SH)], m_str, off=off, z=SH, caps=(False, False), skip=(1,))

    # ---------------- boards across the walk
    for bd in boards:
        p, t = K.fan_tangent(P, bd['s'], W * 0.6)
        n = K.left(t)
        cy, sy = math.cos(bd['yaw']), math.sin(bd['yaw'])
        ty = Vector((cy * t.x - sy * t.y, sy * t.x + cy * t.y, 0))
        ny = K.left(ty)
        c = Vector((p.x, p.y, p.z + SH + BT / 2 + bd['dz']))
        a = c - ny * (W / 2 - bd['l0']); b = c + ny * (W / 2 - bd['l1'])
        mi = m_swap if bd['swap'] else m_board
        if lod == 0:
            K.beam(mb, a, b, ty, bd['w'], BT, mi, kind='round', ch=0.010)
        elif lod == 1:
            K.beam(mb, a, b, ty, bd['w'], BT, mi)
        elif lod == 2:
            K.beam(mb, a, b, ty, bd['w'], BT, mi, caps=(False, False), skip=(0,))
        else:
            h = ty * bd['w'] / 2; zz = Vector((0, 0, BT / 2))
            K.quad(mb, [a - h + zz, a + h + zz, b + h + zz, b - h + zz], mi)
        # bolt heads at every board / stringer crossing
        if lod <= 1:
            for off in s_off:
                q = Vector((p.x, p.y, p.z + zt + bd['dz'])) + n * off
                if lod == 0:
                    K.beam(mb, q - Vector((0, 0, 0.002)), q + Vector((0, 0, 0.005)), ty, 0.02, 0.02, m_iron, caps=(False, True))
                else:
                    e1 = ty * 0.011; e2 = n * 0.011; zz = Vector((0, 0, 0.002))
                    K.quad(mb, [q - e1 - e2 + zz, q + e1 - e2 + zz, q + e1 + e2 + zz, q - e1 + e2 + zz], m_iron)

    # ---------------- iron flat bars over the board ends (strapped style)
    if S['straps']:
        for side in (-1, 1):
            off = side * (W / 2 - 0.045)
            if lod <= 2:
                K.hsweep(mb, fr, [(-0.025, 0), (0.025, 0), (0.025, 0.006), (-0.025, 0.006)], m_iron, off=off, z=zt,
                         skip=(0,) if lod == 2 else ())
            else:
                K.hsweep(mb, fr, [(0.025, 0.006), (-0.025, 0.006)], m_iron, off=off, z=zt, caps=(False, False), skip=(1,))
            if lod == 0:                              # bolt heads along the bar, one per board
                for bd in boards:
                    p, t, _ = P.at(bd['s'])
                    q = Vector((p.x, p.y, p.z + zt + 0.006)) + K.left(t) * off
                    K.beam(mb, q, q + Vector((0, 0, 0.006)), t, 0.018, 0.018, m_iron, caps=(False, True))

    C.centre_base(mb, centre_x=path is None, centre_y=path is None)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    K.grain_uv(o, [m_board, m_swap, m_str])
    C.set_json_props(o, kz_deck_z=round(zt, 3),
                     kz_collision=dict(type='solid_box', z_top=round(zt, 3), half_width=round(W / 2, 3),
                                       note='walk collision is solid; the gaps are visual only'),
                     kz_anim=dict(type='none'),
                     kz_params=dict(style=style, width=W, boards=len(boards), stringers=n_str, stringer_spacing=round(sp, 3),
                                    board=[round(b0, 3), round(b1, 3)], gap=[round(g0, 3), round(g1, 3)]))
    return o
