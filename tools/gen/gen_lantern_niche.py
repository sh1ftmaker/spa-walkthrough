"""Wall-niche lantern (lantern_niche). op01 rewrite of the gen40_l build.

TARGETS (measured before coding)
  Sheet refs/gen/sheet-mod-lights.png panel 5 (label W 0.30 x D 0.30 x H 0.30; crop .scratch/op01/m_niche.png).
  Against the 0.30 m front arrow (375 px at 2x): rock 0.32 w x 0.41 h, opening 0.20 x 0.20 with its floor at
  0.30 of the rock height, lantern 0.14 w x 0.18 h (with roof) = 0.45 of the rock width, roof 0.2 of the
  lantern height, lantern set back ~0.05 m from the face. Side view: rock 0.25-0.30 deep, flat back.
  Build follows the proxy (0.30 x 0.25 x 0.35) with those ratios. Lookbook 05: ankle-height niches in dark
  wet basalt, warm glow spilling onto the rock lip.

FEATURES kept at every LOD: small timber box lantern, rough rock niche around it, glowing panel facing +Y.

PARAMETERS
  w, h         outer rock size, m (w 0.25-0.6 default 0.30; h 0.25-0.6 default 0.35; d = proxy 0.25)
  niche_depth  niche depth behind the lip, m (0.10-0.18; default by seed)
  mount        'niche' (default) | 'floor' (lantern on a low rough stone, no surround) | 'rail_post'
               (lantern on a short hinoki post with an iron foot)
  pattern      'plain' (1 muntin per face) | 'lattice' (2 x 2)
SEEDS change shape: outline lumps and bites, rock aspect x0.9-1.1, opening arch (round-top / square),
  opening size x0.9-1.08, niche depth, lantern proportion (squat 0.13 x 0.15 to tall 0.12 x 0.20) and
  pattern (seed 1 plain, 2 lattice, 3 plain tall).
MATERIALS: rock = basalt_wet (face wetness 0.6, niche inside 0.35, tint cooled 0.45/0.47/0.55),
  frame = hinoki dark_timber, paper = washi_backlit (emissive; lantern_andon's printed frame fights the muntins), roof/finial = iron.
  The row lists basalt_dry: it renders pale brown against the near-black wet rock of lookbook 05 (GUIDE §7),
  so basalt_wet is used (report). rail_post mount uses hinoki wet_oiled.
ANIMATION: shader flicker on the paper slot. LIGHT: kz_lights at the lantern centre, 2300 K, 25 W.
BUDGET 400 / 160 / 60 / 30. LOD1 keeps the rock ring set (no mid crag ring), lantern with front muntin;
  LOD2 rock N 6 + paper box + roof; LOD3 rock N 4 + lit front quad.
Pivot: base centre; +Y is the path side; the flat back (y = -d/2) goes against the cave wall.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_lantern_floor as L
import kzgeo_lantern_niche as N

ASSET = 'lantern_niche'
FEATURES = ['small timber box lantern', 'rough rock niche', 'glowing panel facing the path']
TINT = (0.45, 0.47, 0.55)


def build(lod, seed, w=None, h=None, niche_depth=None, mount='niche', pattern=None, style=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'rock')
    W = (w or p['w']) * g.uniform(0.9, 1.0)
    H = (h or p['h']) * g.uniform(0.9, 1.0)
    D = p['d']
    go = C.rng(seed, 'opening')
    arch = C.cycle(seed, ['round', 'square', 'round'])
    ow = W * 0.64 * go.uniform(0.92, 1.05)
    oh = H * 0.58 * go.uniform(0.92, 1.08)
    sill = H * go.uniform(0.2, 0.26)
    depth = niche_depth or go.uniform(0.13, 0.17)
    gl = C.rng(seed, 'lantern')
    lw, lh = C.cycle(seed, [(0.13, 0.15), (0.13, 0.16), (0.115, 0.19)])
    lw *= gl.uniform(0.95, 1.05)
    pattern = pattern or C.cycle(seed, ['plain', 'lattice', 'plain'])

    mb = genlib.MeshBuilder()
    face = mb.slot('basalt_wet', wetness=0.6, tint=TINT, normal_strength=1.6)
    inner = mb.slot('basalt_wet', wetness=0.35, tint=TINT, roughness_offset=0.08)
    frame = mb.slot('hinoki', variant='dark_timber', wear=0.3)
    paper = mb.slot('washi_backlit', emissive_level=1.0)
    iron = mb.slot('iron')

    # ---------------------------------------------------------------- support
    if mount == 'niche':
        f_out = N.outline(C.rng(seed, 'outline'), W, H, p=C.cycle(seed, [3.2, 4.0, 2.8]), amp=0.07, bites=C.cycle(seed, [1, 2, 1]))
        cz = sill + oh / 2 - H / 2          # outline centred on z = 0 here; centre_base lifts it
        f_open = N.opening(ow, oh, cz, p_top=2.4 if arch == 'round' else 7.0, p_bot=12.0)
        n = C.lod_pick(lod, 16, 8, 8, 4)
        if lod >= 3:      # 4 corners at 45 deg would cut the lumpy outline in by ~15 %: push them out
            f_out0 = f_out
            f_out = lambda t: tuple(c * 1.16 for c in f_out0(t))
        N.niche_rock(mb, f_out, f_open, D, depth, face, inner, seed, N=n, mid=lod == 0, crag=0.016 if lod == 0 else 0.008, back_cap=lod == 0)
        z_floor = cz - oh / 2 * L.shape_r('sq', 1.5 * math.pi, 12.0)
        depth = max(depth, lw + 0.045)
        y_l = D / 2 - 0.018 - lw / 2                 # lantern front just inside the lip (sheet: set back in the rock)
        # keep the lantern under the opening top
        lh = min(lh, oh * 0.82)
    elif mount == 'floor':
        bh = 0.09
        rr = C.rng(seed, 'outline')
        L.srings(mb, [(W * 0.42, D * 0.42, 0.0), (W * 0.46, D * 0.45, bh * 0.55), (W * 0.40, D * 0.40, bh)],
                 C.lod_pick(lod, 12, 8, 6, 4), face, shape='sq', p=3.0, disp=L.rough(seed, 0.012 if lod <= 1 else 0.0, 9.0))
        z_floor, y_l = bh - 0.004, 0.0
    else:   # rail_post
        post_h = H - lh - 0.06
        wood = mb.slot('hinoki', variant='wet_oiled', wear=0.3)
        if lod <= 1:
            mb.box((0, 0, 0.012), (0.12, 0.12, 0.024), iron)
            mb.box((0, 0, post_h / 2), (0.055, 0.055, post_h), wood)
            mb.box((0, 0, post_h - 0.006), (lw + 0.03, lw + 0.03, 0.012), frame)
        else:
            L.open_box(mb, (0, 0, post_h / 2), (0.055, 0.055, post_h), wood, skip=('top', 'bottom'))
        z_floor, y_l = post_h, 0.0

    # ---------------------------------------------------------------- lantern
    roof_h = lh * 0.2
    body_h = lh - roof_h
    st = 0.014
    if lod <= 1:
        kz = L.andon_frame(mb, (0, y_l), z_floor, lw, body_h, dict(wood=frame, paper=paper), lod, stile=st, rail=0.014,
                           pattern=pattern if lod == 0 else 'plain', n_lattice=(2, 1) if pattern == 'lattice' else (1, 0),
                           bev=0.0, muntin_faces=((0, 1, 3) if pattern == 'lattice' else (0, 1, 2, 3)) if lod == 0 else (0,),
                           top_rail=lod == 0)
        L.hip_roof(mb, (0, y_l), z_floor + body_h, lw / 2 + 0.018, 0.008, roof_h - 0.008, iron, segs=4,
                   top_half=0.008 if lod == 0 else 0.0, simple=lod >= 1)
        if lod == 0:
            C.lathe(mb, [(0.006, 0), (0.011, 0.008), (0, 0.02)], 5, iron, base=(0, y_l, z_floor + lh - 0.003))
    elif lod == 2:
        L.open_box(mb, (0, y_l, z_floor + body_h / 2), (lw * 0.9, lw * 0.9, body_h), paper, skip=('top', 'bottom', 'back'))
        hr = lw / 2 + 0.018
        L.srings(mb, [(hr, hr, z_floor + body_h), (0.0, 0.0, z_floor + lh)], 4, iron, shape='sq', p=40.0, phase=math.pi / 4,
                 centre=(0, y_l), cap_bot=False)
        kz = Vector((0, y_l, z_floor + body_h / 2))
    else:
        bm = mb.bm
        yq = y_l + lw * 0.45
        q = [bm.verts.new((x, yq, z)) for x, z in ((-lw / 2, z_floor), (lw / 2, z_floor), (lw / 2, z_floor + lh), (-lw / 2, z_floor + lh))]
        mb._tag([bm.faces.new(q)], paper)
        kz = Vector((0, y_l, z_floor + body_h / 2))

    d = Vector(C.centre_base(mb))
    o = mb.to_object(ASSET)
    genlib.finish(o)
    L.lights_props(o, [kz + d], 2300, 25, [paper],
                   dict(mount=mount, w=round(W, 3), h=round(H, 3), niche_depth=round(depth, 3), arch=arch, pattern=pattern,
                        lantern=[round(lw, 3), round(lh, 3)]))
    return o
