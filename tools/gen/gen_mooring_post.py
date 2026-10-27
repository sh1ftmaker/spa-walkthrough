"""Mooring bollard with rope (mooring_post): short weathered timber posts on the B2 boat landing.

Identifying features kept at every LOD: short weathered timber post, iron cap, coil of rope (LOD0-2; LOD3
is a 20-tri post with a flared iron cap only).

Targets (measured before coding)
  * No scale sheet shows the bollard. refs/gen/dh-core-boat.png (boat landing, 10 m bar = 205 px): pier
    posts stand ~0.8-1.0 m above the deck, ~0.25-0.3 m thick, dark weathered timber, rope wound round
    them with a loop hanging to the boats. Lookbook 06 / 34 show the landing only at plan scale.
  * Row: h 0.6-1.2 m, r 0.12-0.2 m, rope turns, cap on/off; proxy 0.35 x 0.35 x 0.9 m. The proxy width
    holds post + rope, so post radius is 0.12-0.15 m (rope cord 14 mm sits outside it).
  Built: h 0.70-0.92 (seed), post r 0.115-0.135, 2-5 rope turns of 14 mm cord at 45-65 % height, a
  hanging loop (sag 0.10-0.22 m) and a tail, iron cap 0.05-0.09 m tall.

Construction
  * post: turned weathered timber (`hinoki` dark_timber, wear 0.6), 12 staves at LOD0 with 2 mm V-grooves
    (checks/splits), slight top taper, 12 mm chamfer under the cap. 'square' style: chamfered square post.
  * cap: `iron`. 'dome' style: rimmed dome with a knob; 'square': flat plate cap with a pyramid top;
    'pin': dome cap plus an iron cross pin (bitt) through the post above the rope.
  * rope (`rope`): rope_turns coil round the post, a sagging loop tube (catenary) on the +Y side and a short
    tail. Vertex attribute `_sway` = 0 on the post / turns, rising to 1 at the loop bottom and tail tip.
LOD1: same parts, 8 sides, 2 turns, 5-sided loop, no iron band. LOD2: 5 sides, rope band (loop, tail and
cross pin dropped).
LOD3: 4-sided post with a flared iron top (20 tris).
Animation: vertex sway (obj['kz_anim'] = vertex_sway on '_sway'). Lighting: lightmap.

Parameters (build kwargs)
  style  dome | square | pin   (cycles with the seed)
  h      0.6-1.2 m  (seeded 0.70-0.92)   r 0.1-0.2 m (post radius, seeded 0.115-0.135: proxy w 0.35)
  turns  rope turns 2-5 (seeded)         cap True/False (default True)
Seeds change: style (cap / post section / cross pin), height, radius, rope height, turns, loop sag and side.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'mooring_post'
FEATURES = ['short weathered timber post', 'iron cap', 'coil of rope']
STYLES = ['dome', 'square', 'pin']


def build(lod, seed, style=None, h=None, r=None, turns=None, cap=True):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'post')
    H = max(0.6, min(1.2, h)) if h else g.uniform(0.70, 0.92)
    R = max(0.1, min(0.2, r)) if r else g.uniform(0.115, 0.135)
    taper = g.uniform(0.9, 0.97)
    gr = C.rng(seed, 'rope')
    nt = int(turns) if turns else gr.randint(2, 5)
    rope_z = H * gr.uniform(0.45, 0.65)
    sag = gr.uniform(0.10, 0.22)
    side = gr.choice([1, -1])
    tail_a = gr.uniform(-0.6, 0.6)
    gc = C.rng(seed, 'cap')
    cap_h = gc.uniform(0.05, 0.09)

    mb = genlib.MeshBuilder()
    m_post = mb.slot('hinoki', variant='dark_timber', wear=0.6)
    m_iron = mb.slot('iron')
    m_rope = mb.slot('rope')
    L_sway = mb.bm.verts.layers.float.new('_sway')
    zc = H - (cap_h if cap else 0.0)            # top of the timber
    Rt = R * taper

    # ---------------------------------------------------------------- LOD3: 4-sided post + flared iron top
    if lod == 3:
        _, fs = C.lathe(mb, [(R * 1.1, 0.0), (Rt * 1.1, zc), (Rt * 1.2, H)], 4, m_post, phase=math.pi / 4)
        top = [f for f in fs if f.calc_center_median().z > zc - 1e-4]
        mb._tag(top, m_iron)
        return _finish(mb, H, R)

    segs = C.lod_pick(lod, 12, 8, 5)
    # ---------------------------------------------------------------- post
    ch = C.lod_pick(lod, 0.012, 0.008, 0.0)
    if style == 'square':
        s0, s1 = 2 * R * 0.86, 2 * Rt * 0.86
        if lod == 0:
            C.chamfered_bar(mb, (0, 0, zc / 2), (s0, s0, zc), m_post, ch=0.02, axis='z')
        else:
            prof = [(s0 * 0.707, 0.0), (s1 * 0.707, zc)]
            C.lathe(mb, prof, 4, m_post, phase=math.pi / 4)
    else:
        prof = [(R, 0.0), (Rt, zc - ch), (Rt - ch, zc)] if ch else [(R, 0.0), (Rt, zc)]
        if lod == 0:
            C.lathe_grooved(mb, prof, segs // 2, 0.002, m_post, closed=True)
        else:
            C.lathe(mb, prof, segs, m_post)

    # ---------------------------------------------------------------- cap
    if cap:
        cr = (Rt if style != 'square' else Rt * 0.86 * 1.0) + 0.012
        if style == 'square':
            pr = cr * 1.05
            if lod <= 1:
                C.board(mb, (0, 0, zc + 0.012), (2 * pr, 2 * pr, 0.024), m_iron, bevel=C.lod_pick(lod, 0.004, 0.0))
                C.lathe(mb, [(pr * 1.0 * 1.0, zc + 0.024), (0.0, H)], 4, m_iron, phase=math.pi / 4)
            else:
                C.lathe(mb, [(pr * 1.41, zc), (pr * 1.41, zc + 0.024), (0.0, H)], 4, m_iron, phase=math.pi / 4)
        else:
            if lod == 0:
                prof = [(cr, zc - 0.02), (cr + 0.006, zc + 0.004), (cr * 0.8, zc + cap_h * 0.55),
                        (cr * 0.38, zc + cap_h * 0.85), (0.03, H - 0.012), (0.0, H)]
            elif lod == 1:
                prof = [(cr, zc - 0.02), (cr + 0.006, zc + 0.004), (cr * 0.75, zc + cap_h * 0.65), (0.0, H)]
            else:
                prof = [(cr + 0.004, zc - 0.02), (cr * 0.75, zc + cap_h * 0.65), (0.0, H)]
            C.lathe(mb, prof, segs, m_iron)
            if lod == 0 and style != 'pin':   # iron band nailed round the post under the cap
                C.lathe(mb, [(Rt + 0.004, zc - 0.07), (Rt + 0.004, zc - 0.045)], segs, m_iron, closed=False)
    if style == 'pin' and lod <= 1:
        zp = min(zc - 0.12, rope_z + 0.16)
        L = 2 * R + 0.07
        C.stick(mb, (-L / 2, 0, zp), (L / 2, 0, zp), 0.02, 0.02, m_iron, segs=C.lod_pick(lod, 8, 4))

    # ---------------------------------------------------------------- rope
    rr = R * (0.995 if style != 'square' else 0.86 * 1.0) - 0.002
    if style == 'square':
        rr = R * 0.86 * 1.40                   # coil rounds the square post's corners
    cord = 0.014
    if lod == 2:
        C.rope_band(mb, (0, 0, rope_z), (0, 0, 1), rr, 0.05, m_rope, N=5, bulge=cord)
    else:
        n = nt if lod == 0 else 2
        C.rope_turns(mb, (0, 0, rope_z), (0, 0, 1), rr, n, m_rope, cord=cord, pitch=0.026,
                     N=C.lod_pick(lod, 8, 6))
    # hanging loop: leaves the coil on one side, sags out towards +Y and back
    half_w = rr + cord
    loop_n = C.lod_pick(lod, 9, 6)
    pts = []
    for i in range(loop_n):
        t = i / (loop_n - 1)
        a = math.pi * (0.15 + 0.7 * t)                 # around the front of the post
        x = side * math.cos(a) * half_w * 1.15
        y = math.sin(a) * (half_w + 0.008 + 0.012 * math.sin(math.pi * t))
        z = rope_z - 0.01 - sag * math.sin(math.pi * t) ** 1.3
        pts.append(Vector((x, y, z)))
    if lod <= 1:
        vs_before = set(mb.bm.verts)
        C.tube(mb, pts, [cord * 0.9] * len(pts), m_rope, sides=C.lod_pick(lod, 6, 5), cap0=True, cap1=True)
        for v in mb.bm.verts:
            if v not in vs_before:
                v[L_sway] = max(0.0, min(1.0, (rope_z - v.co.z) / max(sag, 1e-3)))
    # tail hanging from the coil
    if lod <= 1:
        a = math.pi / 2 + tail_a
        p0 = Vector((math.cos(a) * half_w, math.sin(a) * half_w, rope_z - nt * 0.013))
        p1 = p0 + Vector((math.cos(a) * 0.03, math.sin(a) * 0.03, -0.14))
        vs_before = set(mb.bm.verts)
        if lod == 0:
            C.rope_cord(mb, p0, p1, cord * 0.85, m_rope, sides=6, seg_len=0.045)
        else:
            C.stick(mb, p0, p1, cord * 0.85, cord * 0.85, m_rope, segs=5)
        for v in mb.bm.verts:
            if v not in vs_before:
                v[L_sway] = max(0.0, min(1.0, (p0.z - v.co.z) / 0.14))
    return _finish(mb, H, R, style=style, nt=nt, cap=cap)


def _finish(mb, H, R, **params):
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_anim=dict(type='vertex_sway', attrs=['_sway'], what='rope loop and tail sag sway',
                                     amp_m=0.02, period_s=3.5),
                     kz_params=dict(h=round(H, 3), r=round(R, 3), **params))
    return o
