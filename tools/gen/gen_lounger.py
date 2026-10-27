"""Beach lounger with mattress (lounger): low hinoki loungers on the B3 wave-grotto black-sand beach.

Identifying features kept at every LOD: low hinoki frame, thick cream mattress, raised back.

Targets (measured before coding)
  * lookbook 20 (wave grotto), front-left lounger, measured against the 0.5 m tea kettle table and the
    rolled towel (~0.45 m long): mattress ~0.75-0.8 m wide, 0.13-0.16 m thick with a soft rolled edge,
    cream-white; frame dark oiled timber, a deep side rail (~0.12 m) under a lip, short block legs, frame
    top ~0.30 m, mattress top ~0.43-0.46 m. The lounger behind it shows the raised back: a separate back
    cushion on a hinged back board at ~35-50 deg, its top ~0.85-0.95 m above the sand. Row l 1.8-2.1,
    w 0.7-0.9, dims 0.8 x 2 x 0.5 (the proxy height 0.5 only holds the flat seat: the raised back needs
    ~0.9; proposed in the report).
  Built: L 1.85-2.05, W 0.72-0.79 (proxy w 0.8), frame top 0.26-0.31, mattress T 0.12-0.16, back 30-48 deg over
  0.62-0.72 m, back top 0.78-0.92 m.

Construction (head end at -Y, so the front 3/4 view sees the raised back behind the seat)
  * frame (`hinoki` walnut, dark oiled as in lookbook 20): two deep side rails and two end rails with 6 mm rounded edges, a top lip
    rail, a deck board under the mattress; 'block' style: a recessed plinth base (toe kick); 'legs' style:
    six square legs with a long stretcher each side.
  * back: a back board hinged at the seat break, held by an angled strut on each side; back cushion and
    seat mattress are separate `pillow()` slabs (full thickness to a rolled edge, never a knife edge) in
    `linen` (cream). Seed option: a rolled head bolster (lathe, linen) on top of the back cushion.
LOD1: same parts, square rails, chamfered lips only, pillow corners m=1. LOD2: one frame box, plain base /
open 4-sided legs, mattress and back cushion as chamfered boxes; no deck, back board, bolster or struts. LOD3: frame box + one extruded side silhouette of the mattress with the raised back.
Animation: none. Lighting: lightmap.

Parameters (build kwargs)
  style      block | legs                (cycles with the seed)
  l          1.8-2.1 m   w 0.7-0.9 m     back_angle 20-55 deg   mattress (thickness) 0.10-0.18 m
  bolster    True/False (seeded)
Seeds change: base style (plinth vs six legs + stretchers), length, width, frame height, mattress
thickness, back angle and length, head bolster.
"""
import math

from mathutils import Matrix, Vector
import bmesh

import genlib
import kzgeo_common as C
import kzgeo_table_low as KT

ASSET = 'lounger'
FEATURES = ['low hinoki frame', 'thick cream mattress', 'raised back']
STYLES = ['block', 'legs']


def _rotate_x(mb, verts, pivot, ang):
    bmesh.ops.rotate(mb.bm, verts=verts, cent=pivot, matrix=Matrix.Rotation(ang, 3, 'X'))


def build(lod, seed, style=None, l=None, w=None, back_angle=None, mattress=None, bolster=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'dims')
    L = max(1.8, min(2.1, l)) if l else g.uniform(1.85, 2.05)
    W = max(0.7, min(0.9, w)) if w else g.uniform(0.72, 0.79)
    zf = g.uniform(0.26, 0.31)                       # frame top
    T = max(0.10, min(0.18, mattress)) if mattress else g.uniform(0.12, 0.16)
    gb = C.rng(seed, 'back')
    ang = math.radians(max(20, min(55, back_angle)) if back_angle else gb.uniform(30, 48))
    blen = gb.uniform(0.62, 0.72)
    bol = (gb.random() < 0.5) if bolster is None else bool(bolster)

    mb = genlib.MeshBuilder()
    m_frame = mb.slot('hinoki', variant='walnut', wetness=0.2)
    m_mat = mb.slot('linen')

    rail_t = 0.045                                   # rail thickness
    rail_h = 0.13
    lip = 0.012                                      # lip overhang
    zd = zf - 0.03                                   # deck top (mattress underside)
    y_head = -L / 2
    y_hinge = y_head + blen                          # seat break

    # ---------------------------------------------------------------- LOD3: frame box + mattress silhouette
    if lod == 3:
        mb.box((0, 0, zf / 2), (W, L, zf), m_frame)
        ca, sa = math.cos(ang), math.sin(ang)
        bx = y_hinge - blen * ca                     # back top end (y), raised
        bz = zd + blen * sa
        prof = [(L / 2 - 0.02, zd), (L / 2 - 0.02, zd + T), (y_hinge + T * 0.4, zd + T),
                (bx + T * sa, bz + T * ca), (bx, bz), (y_hinge - 0.05, zd)]
        KT.extrude_profile(mb, prof, -W / 2 + 0.03, W / 2 - 0.03, m_mat, axis='x')
        return _finish(mb, style, L, W, T, ang, bol)

    bev = C.lod_pick(lod, 0.006, 0.0, 0.0)
    segs = C.lod_pick(lod, 2, 1, 1)
    # ---------------------------------------------------------------- frame rails (box frame)
    zr = zf - rail_h / 2
    if lod == 2:                                     # one frame box under the mattress
        mb.box((0, 0, zr), (W, L, rail_h), m_frame)
    for sx in ((-1, 1) if lod <= 1 else ()):
        C.board(mb, (sx * (W / 2 - rail_t / 2), 0, zr), (rail_t, L, rail_h), m_frame, bevel=bev, segs=segs)
    for sy in ((-1, 1) if lod <= 1 else ()):
        C.board(mb, (0, sy * (L / 2 - rail_t / 2), zr), (W - 2 * rail_t, rail_t, rail_h), m_frame, bevel=bev, segs=segs)
    if lod <= 1:                                     # top lip rail on the long sides
        for sx in (-1, 1):
            C.board(mb, (sx * (W / 2 - rail_t / 2 + lip / 2), 0, zf - 0.011), (rail_t + lip, L + lip, 0.022),
                    m_frame, bevel=C.lod_pick(lod, 0.005, 0.003), segs=segs)
    if lod <= 1:
        mb.box((0, 0, zd - 0.01), (W - 2 * rail_t, L - 2 * rail_t, 0.02), m_frame)     # deck board
    # ---------------------------------------------------------------- base
    zb = zf - rail_h                                 # underside of the rails
    if style == 'block':
        inset = 0.06
        C.board(mb, (0, 0, zb / 2), (W - 2 * inset, L - 2 * inset, zb), m_frame, bevel=C.lod_pick(lod, 0.004, 0.0, 0.0))
    else:
        leg = 0.07
        ys = (-L / 2 + leg / 2 + 0.02, 0.0, L / 2 - leg / 2 - 0.02)
        for sx in (-1, 1):
            for y in ys:
                c = (sx * (W / 2 - leg / 2 - 0.015), y, zb / 2)
                if lod == 0:
                    C.chamfered_bar(mb, c, (leg, leg, zb), m_frame, ch=0.006, axis='z')
                elif lod == 1:
                    mb.box(c, (leg, leg, zb), m_frame)
                else:                                # open 4-sided leg (top and bottom are hidden)
                    C.lathe(mb, [(leg * 0.707, 0.0), (leg * 0.707, zb)], 4, m_frame,
                            base=(c[0], c[1], 0.0), phase=math.pi / 4, closed=False)
            if lod <= 1:
                C.board(mb, (sx * (W / 2 - leg / 2 - 0.015), 0, zb * 0.35), (0.03, L - 0.1, 0.04), m_frame, bevel=bev)

    # ---------------------------------------------------------------- seat mattress
    m_pl = C.lod_pick(lod, 2, 1, 1)
    puff = C.lod_pick(lod, 0.018, 0.014, 0.0)
    seat_len = L / 2 - y_hinge - rail_t - 0.005
    mw = W - 2 * rail_t + 0.02                       # mattress sits between the rails, overlapping the lip
    yc_seat = (L / 2 - rail_t + y_hinge) / 2
    if lod == 2:
        C.board(mb, (0, yc_seat, zd + T / 2), (mw, seat_len, T), m_mat, bevel=0.03)
    else:
        C.pillow(mb, (0, yc_seat, zd), mw, seat_len, T, m_mat, rc=0.05, m=m_pl, puff=puff,
                 creases=[(0.0, 0.006, 0.05)] if lod == 0 else ())
    # ---------------------------------------------------------------- back: board + cushion, hinged at y_hinge
    hinge = Vector((0, y_hinge, zd))
    vs0 = set(mb.bm.verts)
    bl = blen - rail_t - 0.01
    if lod <= 1:
        C.board(mb, (0, y_hinge - bl / 2, zd - 0.012), (W - 2 * rail_t - 0.01, bl, 0.024), m_frame, bevel=bev * 0.5)
        C.pillow(mb, (0, y_hinge - bl / 2 - 0.005, zd), mw, bl - 0.01, T * 0.85, m_mat, rc=0.05, m=m_pl, puff=puff)
    else:
        C.board(mb, (0, y_hinge - bl / 2 - 0.005, zd + T * 0.425), (mw, bl - 0.01, T * 0.85), m_mat, bevel=0.03)
    if bol and lod <= 1:                             # rolled head bolster on the top end of the back cushion
        br = 0.07
        yb = y_hinge - bl + br + 0.02
        vs_b, _ = C.lathe(mb, [(0.0, -mw / 2 + 0.03), (br * 0.75, -mw / 2 + 0.03), (br, -mw / 2 + 0.07),
                               (br, mw / 2 - 0.07), (br * 0.75, mw / 2 - 0.03), (0.0, mw / 2 - 0.03)],
                          C.lod_pick(lod, 12, 8), m_mat)
        # lathe is about Z: lay it along X at the bolster position
        bmesh.ops.rotate(mb.bm, verts=vs_b, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
        bmesh.ops.translate(mb.bm, verts=vs_b, vec=(0, yb, zd + T * 0.85 + br * 0.8))
    back_vs = [v for v in mb.bm.verts if v not in vs0]
    _rotate_x(mb, back_vs, hinge, -ang)              # lift the head end (-Y) upwards
    # struts: from the deck near the head rail up to the back board underside
    if lod <= 1:
        ca, sa = math.cos(ang), math.sin(ang)
        for sx in (-1, 1):
            x = sx * (W / 2 - rail_t - 0.035)
            top = Vector((x, y_hinge - bl * 0.72 * ca, zd + bl * 0.72 * sa - 0.03))
            bot = Vector((x, y_head + rail_t + 0.04, zd - 0.005))
            C.stick(mb, bot, top, 0.016, 0.016, m_frame, segs=C.lod_pick(lod, 6, 4))
    return _finish(mb, style, L, W, T, ang, bol)


def _uv_grain_long(o, slots):
    """genlib's box UV0 runs the hinoki grain vertically on side faces; rails and boards here run along Y
    (sides) or X (ends), so lay the grain horizontally on X- and Y-facing timber faces."""
    me = o.data
    uv = me.uv_layers['UVMap'].data
    for p in me.polygons:
        if p.material_index not in slots:
            continue
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                uv[li].uv = (co.z * (1 if n.x > 0 else -1), co.y)
            elif ax == 1:
                uv[li].uv = (co.z * (1 if n.y < 0 else -1), co.x)


def _finish(mb, style, L, W, T, ang, bol):
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    _uv_grain_long(o, {i for i, (mid, prm) in enumerate(mb.slots) if mid == 'hinoki'})
    C.set_json_props(o, kz_params=dict(style=style, l=round(L, 3), w=round(W, 3), mattress=round(T, 3),
                                       back_angle=round(math.degrees(ang), 1), bolster=bol))
    return o
