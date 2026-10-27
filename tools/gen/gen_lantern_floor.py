"""Floor andon lantern (lantern_floor). Rewritten by op01 (was the LOD pilot).

TARGETS (measured before coding)
  Sheet refs/gen/sheet-mod-lights.png panel 1 (label W 0.45 x D 0.45 x H 1.05 m; crop .scratch/op01/m_floor.png).
  The 1.05 m arrow spans only part of the drawn object, so the label is the total and the drawing gives ratios
  of the total height: feet 0.09, base frame 0.075, body (stiles) 0.65, cap 0.10, finial 0.08.
  Widths: body 0.84 w, base frame 0.94 w, cap eave = w (the 0.45 label), stiles 0.035-0.04 m, finial block 0.06 m.
  One vertical muntin per face in panel 1 (two tall washi sub-panels), iron studs on the base frame.
  Table variant: refs/gen/sheet-vs-lights-2.png panel 6, W 0.25 x D 0.25 x H 0.40 m, flat lid with crossed bars,
  stile tops proud, plain panel, corner feet.
  Lookbook 05 / 15 / 08 / 14: the same box andon on paths and decks, amber glow, dark aged timber.

FEATURES kept at every LOD: square timber box with a cap (pyramid / hip / lid), glowing washi panels, short legs.

PARAMETERS (all optional; defaults from the style)
  h        overall height, m      0.35-1.30 (floor default 1.05, table 0.40)
  w        overall width, m       0.25-0.50 (floor default 0.45 incl. the cap eave, table 0.25)
  cap      'pyramid' | 'hip' (concave, corner lift) | 'lid' (flat lid with crossed bars, table)
  pattern  'plain' (1 muntin per face) | 'lattice' (2 x 3 grid) | 'kumiko' (3 x 4 fine grid)
  legs     True (4 corner feet) | False (deep plinth on the ground)
  scale    'floor' | 'table'
  style    'classic' | 'lattice' | 'table' | 'tall' (seed 1, 2, 3, 4 ...; seeds cycle the styles)

SEEDS change shape, not tint: the style (cap / pattern / legs / scale, see STYLES), height x0.92-1.0,
  width x0.94-1.0, cap pitch x0.85-1.2, foot height x0.8-1.15, finial height x0.8-1.3.

MATERIALS (slots by part): frame = hinoki dark_timber (stiles, rails, plinth, feet, muntins),
  cap = hinoki stained (cap, ridges, finial), paper = washi_backlit (emissive, fibre washi as in the sheet),
  studs = iron. lantern_andon was tried: its texture prints its own cross-bar frame that does not line up
  with the geometry's muntins (reads as a shadow cross), so washi_backlit is the default; paper_mat='lantern_andon'
  switches it. Param wood= picks the hinoki variant of the frame.

ANIMATION: shader flicker on the paper slot (kz_flicker / kz_anim). LIGHT: kz_lights, one point at the
  paper centre, 2400 K, 30 W (proxy light).
BUDGET 900 / 360 / 110 / 60. LOD1 keeps every part (no bevels, no studs/ridges, lattice 2 x 2);
  LOD2 paper core + open stiles + plinth + feet + cap; LOD3 paper core + cap + leg plinth prism.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_lantern_floor as L

ASSET = 'lantern_floor'
FEATURES = ['square timber box', 'pyramidal cap', 'glowing washi panels', 'short legs']
STYLES = ['classic', 'lattice', 'table', 'tall']
STYLE_DEF = dict(
    classic=dict(scale='floor', cap='pyramid', pattern='plain', legs=True, h=1.05, w=0.45, body=0.84),
    lattice=dict(scale='floor', cap='hip', pattern='lattice', legs=True, h=0.95, w=0.42, body=0.82),
    table=dict(scale='table', cap='lid', pattern='plain', legs=True, h=0.40, w=0.25, body=0.86),
    tall=dict(scale='floor', cap='pyramid', pattern='kumiko', legs=False, h=1.05, w=0.36, body=0.86),
)


def build(lod, seed, h=None, w=None, cap=None, pattern=None, legs=None, scale=None, style=None, paper_mat=None, wood=None):
    style = style or C.cycle(seed, STYLES)
    S = dict(STYLE_DEF[style])
    if scale == 'table' and style != 'table':
        S.update(h=0.40, w=0.25)
    g = C.rng(seed, 'dims')
    H = h or S['h'] * g.uniform(0.92, 1.0)
    W = w or S['w'] * g.uniform(0.94, 1.0)
    cap = cap or S['cap']
    pattern = pattern or S['pattern']
    legs = S['legs'] if legs is None else legs
    gp = C.rng(seed, 'parts')
    pitch = gp.uniform(0.85, 1.2)
    foot_k = gp.uniform(0.8, 1.15)
    fin_k = gp.uniform(0.8, 1.3)
    table = S['scale'] == 'table' or scale == 'table'

    mb = genlib.MeshBuilder()
    frame = mb.slot('hinoki', variant=wood or 'dark_timber', wear=0.35)
    capm = mb.slot('hinoki', variant='stained', wear=0.3)
    paper = mb.slot(paper_mat or 'washi_backlit', emissive_level=1.0)
    iron = mb.slot('iron')

    # ---- vertical layout (fractions of H, from the sheet)
    foot_h = (0.09 * foot_k if legs else 0.0) * H
    plinth_h = (0.075 if legs else 0.12) * H
    if table:
        plinth_h = 0.06 * H
        foot_h = 0.09 * foot_k * H if legs else 0.0
    cap_h = (0.10 if cap != 'lid' else 0.05) * H * (pitch if cap != 'lid' else 1.0)
    fin_h = (0.075 * fin_k * H) if cap != 'lid' else 0.0
    body_h = H - foot_h - plinth_h - cap_h - fin_h
    Wb = W * S['body']                       # body (stile outer) width
    Wp = W * (0.94 if not table else 0.96)   # base frame
    st = max(0.022, 0.085 * Wb) if not table else 0.022
    z_pl = foot_h
    z_body = foot_h + plinth_h
    z_cap = z_body + body_h

    # ---- feet + base frame
    fw = max(0.05, 0.2 * Wp)
    if lod <= 1:
        if legs:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    p = (sx * (Wp / 2 - fw / 2), sy * (Wp / 2 - fw / 2), foot_h / 2)
                    if lod == 0:
                        C.board(mb, p, (fw, fw, foot_h), frame, bevel=0.005)
                    else:
                        mb.box(p, (fw, fw, foot_h), frame)
        if lod == 0:
            C.board(mb, (0, 0, z_pl + plinth_h / 2), (Wp, Wp, plinth_h), frame, bevel=0.006)
            # iron studs: two 4-sided domes per face on the base frame
            sr = min(0.012, plinth_h * 0.18)
            for f in range(4):
                a = f * math.pi / 2
                nx, ny = math.sin(a), math.cos(a)
                tx, ty = ny, -nx
                for s in (-1, 1):
                    off = s * Wp * 0.3
                    cx_, cy_ = nx * Wp / 2 + tx * off, ny * Wp / 2 + ty * off
                    L.stud(mb, (cx_ - nx * 0.001, cy_ - ny * 0.001, z_pl + plinth_h / 2), (nx, ny, 0), sr, 0.008, iron)
        else:
            mb.box((0, 0, z_pl + plinth_h / 2), (Wp, Wp, plinth_h), frame)
    elif lod == 2:
        L.open_box(mb, (0, 0, z_pl + plinth_h / 2), (Wp, Wp, plinth_h), frame, skip=('bottom',) if legs else ())
        if legs:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    L.open_box(mb, (sx * (Wp / 2 - fw / 2), sy * (Wp / 2 - fw / 2), foot_h / 2), (fw, fw, foot_h), frame, skip=('top',))
    else:
        # LOD3: base frame and legs as one notched prism (two legs from the front and the side reads)
        if legs:
            x0, x1 = Wp / 2, Wp / 2 - fw
            poly = [(-x0, 0), (-x1, 0), (-x1, foot_h), (x1, foot_h), (x1, 0), (x0, 0), (x0, z_body), (-x0, z_body)]
        else:
            poly = [(-Wp / 2, 0), (Wp / 2, 0), (Wp / 2, z_body), (-Wp / 2, z_body)]
        L.prism_xz(mb, poly, -Wp / 2, Wp / 2, frame)

    # ---- body
    nl = (2, 3) if lod == 0 else (2, 2)
    if pattern == 'plain':
        nl = (1 if not table else 0, 0)
    kz = L.andon_frame(mb, (0, 0), z_body, Wb, body_h, dict(wood=frame, paper=paper), lod, stile=st,
                       rail=st * (0.9 if not table else 1.2), pattern=pattern, n_lattice=nl, bev=0.004)

    # ---- cap
    if cap == 'lid':
        lid_t = cap_h * 0.55
        if lod <= 1:
            if lod == 0:
                C.board(mb, (0, 0, z_cap + lid_t / 2), (Wb + 0.02, Wb + 0.02, lid_t), capm, bevel=0.004)
            else:
                mb.box((0, 0, z_cap + lid_t / 2), (Wb + 0.02, Wb + 0.02, lid_t), capm)
            for ax in (0, 1):     # two crossed bars proud of the lid, overhanging like the sheet
                size = (W, 0.03, cap_h - lid_t) if ax == 0 else (0.03, W, cap_h - lid_t)
                mb.box((0, 0, z_cap + lid_t + (cap_h - lid_t) / 2), size, capm)
        else:
            mb.box((0, 0, z_cap + cap_h / 2), (W if lod == 2 else Wb + 0.02, W if lod == 2 else Wb + 0.02, cap_h), capm)
    else:
        concave = 0.45 if cap == 'hip' else 0.0
        lift = 0.012 * (W / 0.45) if cap == 'hip' else 0.0
        thick = max(0.012, 0.018 * H)
        rise = cap_h - thick + (fin_h * 0.7 if lod >= 3 else 0.0)    # LOD3: the apex carries the finial height
        top_half = 0.045 if lod <= 2 else 0.0
        L.hip_roof(mb, (0, 0), z_cap, W / 2, thick, rise, capm, segs=4, top_half=top_half,
                   concave=concave if lod <= 1 else 0.0, lift=lift if lod == 0 else 0.0, N=8 if (lod == 0 and cap == 'hip') else 4,
                   simple=lod >= 1)
        if lod == 0:
            # hip ridges: four battens from the eave corners to the top
            for sx in (-1, 1):
                for sy in (-1, 1):
                    a = (sx * W / 2 * 0.97, sy * W / 2 * 0.97, z_cap + thick + lift)
                    b = (sx * 0.04, sy * 0.04, z_cap + cap_h)
                    C.stick(mb, a, b, 0.009, 0.007, capm, segs=4)
        if lod <= 2:
            # finial: square post block with a small cap
            fb = 0.06 * (W / 0.45) ** 0.5
            if lod == 0:
                C.board(mb, (0, 0, z_cap + cap_h + fin_h * 0.45 - 0.01), (fb, fb, fin_h * 0.9 + 0.02), capm, bevel=0.004)
                mb.box((0, 0, z_cap + cap_h + fin_h * 0.95), (fb * 1.25, fb * 1.25, fin_h * 0.1), capm)
            elif lod == 1:
                mb.box((0, 0, z_cap + cap_h + fin_h / 2 - 0.01), (fb, fb, fin_h + 0.02), capm)
            else:
                L.open_box(mb, (0, 0, z_cap + cap_h + fin_h / 2 - 0.01), (fb, fb, fin_h + 0.02), capm, skip=('bottom',))
        else:
            pass    # LOD3: the pyramid apex carries the finial read
    if table and lod <= 1:
        # stile tops proud of the lid (sheet panel 6)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (Wb / 2 - st / 2), sy * (Wb / 2 - st / 2), z_cap + cap_h * 0.55 + 0.012), (st, st, 0.024), frame)

    kz = kz + Vector(C.centre_base(mb))
    o = mb.to_object(ASSET)
    genlib.finish(o)
    L.lights_props(o, [kz], 2400, 30, [paper],
                   dict(style=style, h=round(H, 3), w=round(W, 3), cap=cap, pattern=pattern, legs=legs,
                        scale='table' if table else 'floor'))
    return o
