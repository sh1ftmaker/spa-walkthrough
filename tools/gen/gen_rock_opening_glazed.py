"""Glazed slot or window through rock (rock_opening_glazed; covers slot_window and rock_window).

Targets (no scale sheet shows it; from the row and the lookbook):
  slot   lookbook 05 mist corridor / plan 35 b3 walk: a knee-high glazed slot along the corridor wall,
         w 8.0 m x h 0.45 m, sill 0.30 m above the walk (knee height ~0.5 m on the 1.65 m guests), the rock
         2 m deep so the slot reads as a long dark reveal with light at the far end.
  window framed window onto the terraces: w 2.4-3.0 x h 1.4-1.6 m, sill 0.6-0.9 m, reveal 0.6-1.0 m,
         dark hinoki frame with 1-2 mullions set in the reveal.
  Both: raw, faceted rock reveal (no dressed jambs), splayed mouth 0.06-0.14 m, the rock bulging into the
  opening by up to 4-6 cm so the glass edge is always buried; a rock collar 0.35 m beside and 0.30 m above
  the opening, and the rock face continuous down to the floor under the sill.
  Built bbox (slot default): 8.7 x 2.1 x 1.05 m. The proxy (8 x 2 x 0.45) is the bare opening; proposed
  proxy 8.7 x 2.1 x 1.05 (slot) - the window default fits inside it (3.1 x 0.9 x 2.6 is taller: see report).

Parameters build(lod, seed, **p)
  variant  slot | window (seed 1 slot, seed 2 window, seed 3 slot ...)
  w 2.4-8, h 0.45-1.6, sill 0.3-0.9, depth (reveal) 0.3-2, frame True/False (window default True)
  margin_x / margin_top: rock collar beyond the opening (0.35 / 0.30)
Seeds change shape: the variant; w +-6 %, depth, corner radius, mouth splay, glass station in the depth
(front / middle), mullion count (window 1-2), rock noise phase and amplitude.
Construction: one closed rock solid. Index-matched loops (rounded-rect opening, mid face ring, outer
rect) are bridged: reveal tube through the depth (rings displaced by 3D noise, inward only), splayed mouth,
front and back faces with a bumpy mid ring, then the outer sides. Glass is a 20 mm pane (glass_clear)
buried 30 mm into the rock all round; window frame is hinoki boards round the pane plus mullions.
LOD0 54-point loops x 6 stations; LOD1 32 x 4; LOD2 14 x 2 (no noise, splay kept, frame kept);
LOD3 4-point loops (box with a hole), single-quad glass.
Materials: basalt_wet (face wetness 0.45, reveal 0.6, sill floor 0.85: the corridor rock is wet and black
in lookbook 05, so not the row's basalt_dry), glass_clear (not lava_glass: clear glazing, see GUIDE 7),
hinoki dark_timber frame. Animation none. Lighting lightmap. Front (corridor side) is +Y.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'rock_opening_glazed'
FEATURES = ['deep raw-rock reveal', 'glazed opening (slot or window)', 'rock collar / face', 'frame (window)']
VARIANTS = {'slot': dict(w=8.0, h=0.45, sill=0.30, depth=2.0, frame=False),
            'window': dict(w=2.6, h=1.5, sill=0.8, depth=0.8, frame=True)}


def _loop(W, H, rc, m, nb, nr, z0=0.0):
    """rounded rectangle centred at x 0, bottom at z0: [(x, z, nx, nz)], fixed counts per side so that
    loops of different sizes stay index-matched. Starts at the bottom-right corner arc, counter-clockwise
    seen from +Y (x right... order is consistent for every loop)."""
    rc = max(0.0, min(rc, W / 2 - 1e-3, H / 2 - 1e-3))
    cx, cz = W / 2 - rc, H / 2 - rc
    zc = z0 + H / 2
    pts = []
    corners = [(cx, -cz, -math.pi / 2), (cx, cz, 0.0), (-cx, cz, math.pi / 2), (-cx, -cz, math.pi)]
    sides = [nr, nb, nr, nb]                     # segments on the straight run after each corner
    for (ax, az, a0), ns in zip(corners, sides):
        for k in range(m + 1):
            a = a0 + (math.pi / 2) * (k / m if m else 0.5)
            nx, nz = math.cos(a), math.sin(a)
            pts.append((ax + rc * nx, zc + az + rc * nz, nx, nz))
        # straight run to the next corner start
        x0, z0_, _, _ = pts[-1]
        nxt = corners[(corners.index((ax, az, a0)) + 1) % 4]
        a1 = nxt[2]
        x1, z1 = nxt[0] + rc * math.cos(a1), zc + nxt[1] + rc * math.sin(a1)
        n_side = (math.cos(a0 + math.pi / 2), math.sin(a0 + math.pi / 2)) if m == 0 else (math.cos(a0 + math.pi / 2), math.sin(a0 + math.pi / 2))
        for k in range(1, ns):
            t = k / ns
            pts.append((x0 + (x1 - x0) * t, z0_ + (z1 - z0_) * t, n_side[0], n_side[1]))
    return pts


def build(lod, seed, variant=None, w=None, h=None, sill=None, depth=None, frame=None, margin_x=0.35, margin_top=0.30):
    variant = variant or C.cycle(seed, ['slot', 'window'])
    V = VARIANTS[variant]
    g = C.rng(seed, 'layout')
    W = w if w is not None else V['w'] * (g.uniform(0.94, 1.06) if variant == 'window' else 1.0)
    H = h if h is not None else V['h'] * g.uniform(0.95, 1.05)
    S = sill if sill is not None else V['sill'] * g.uniform(0.95, 1.05)
    D = depth if depth is not None else V['depth'] * g.uniform(0.85, 1.0)
    frame = V['frame'] if frame is None else frame
    rc = min(H * g.uniform(0.18, 0.32), 0.25)
    splay = g.uniform(0.06, 0.14)
    glass_f = g.choice([0.15, 0.5, 0.75])          # glass station: fraction of depth from the back (+Y is front)
    mull = g.choice([1, 2]) if variant == 'window' else 0
    amp = g.uniform(0.035, 0.06)
    off = Vector((g.uniform(0, 50), g.uniform(0, 50), g.uniform(0, 50)))

    m, nb, nr, ns = C.lod_pick(lod, (3, 18, 3, 5), (2, 10, 2, 3), (1, 4, 1, 1), (0, 1, 1, 1))
    if variant == 'window':
        nb = max(1, nb // 2 + (1 if lod < 2 else 0)); nr = max(1, nr + (2 if lod < 2 else 0))
    noisy = lod <= 1
    Wo, Ho = W + 2 * margin_x, S + H + margin_top

    mb = genlib.MeshBuilder()
    face = mb.slot('basalt_wet', wetness=0.45)
    reveal = mb.slot('basalt_wet', wetness=0.6)
    sillm = mb.slot('basalt_wet', wetness=0.85)
    glass = mb.slot('glass_clear')
    wood = mb.slot('hinoki', variant='dark_timber')
    bm = mb.bm

    def nz3(x, y, z, f=1.6):
        return noise.noise(Vector((x * f, y * f, z * f)) + off)

    inner = _loop(W, H, rc, m, nb, nr, S)
    # ---- reveal rings through the depth (y from -D/2 back to +D/2 front); mouth rings splayed
    rings = []
    for k in range(ns + 1):
        t = k / ns
        y = -D / 2 + D * t
        sp = splay if k in (0, ns) else 0.0
        ring = []
        for (x, z, nx, nz) in inner:
            d = sp
            if noisy:
                d -= amp * (0.5 + 0.5 * nz3(x, y, z)) * (0.6 if k in (0, ns) else 1.0)
            ring.append(bm.verts.new((x + nx * d, y, z + nz * d)))
        rings.append(ring)
    fr = []
    for A, B in zip(rings[:-1], rings[1:]):
        fr += C.bridge_rings(bm, A, B)
    # ---- faces: inner mouth -> mid ring -> outer rect, front and back
    outer = _loop(Wo, Ho, 0.05, m, nb, nr, 0.0)
    ff = []
    for side, mouth in ((1, rings[-1]), (-1, rings[0])):
        y0 = side * D / 2
        out_ring = []
        for (x, z, nx, nz) in outer:
            z = max(z, 0.0)
            yb = y0 + (side * 0.04 * nz3(x, y0 * 3, z, 0.9) if noisy else 0.0)
            out_ring.append(bm.verts.new((x, yb, z)))
        if lod <= 1:
            mid = []
            for (xi, zi, _, _), (xo, zo, _, _) in zip(inner, outer):
                x, z = xi + (xo - xi) * 0.4, zi + (zo - zi) * 0.4
                bulge = side * (0.05 + 0.05 * nz3(x, y0 * 2, z, 1.2))
                mid.append(bm.verts.new((x, y0 + bulge, max(z, 0.0))))
            seq = [mouth, mid, out_ring]
        else:
            seq = [mouth, out_ring]
        for A, B in zip(seq[:-1], seq[1:]):
            ff += C.bridge_rings(bm, A, B)
        if side == 1:
            front_out = out_ring
        else:
            back_out = out_ring
    ff += C.bridge_rings(bm, front_out, back_out)
    import bmesh
    bmesh.ops.recalc_face_normals(bm, faces=fr + ff)
    mb._tag(ff, face)
    for f in fr:                                           # reveal: floor of the opening is the wet sill
        mb._tag([f], sillm if f.normal.z > 0.6 else reveal)
    # ---- glass, buried 30 mm into the rock on every side
    yg = -D / 2 + D * glass_f
    gw, gh = W + 0.06, H + 0.06
    if lod == 3:
        vs = [bm.verts.new((x, yg, z)) for x, z in ((-gw / 2, S - 0.03), (gw / 2, S - 0.03), (gw / 2, S + H + 0.03), (-gw / 2, S + H + 0.03))]
        mb._tag([bm.faces.new(vs)], glass)
    else:
        mb.box((0, yg, S + H / 2), (gw, 0.02, gh), glass)
    # ---- frame (window): boards round the pane, mullions
    if frame and lod <= 2:
        fw, fd = 0.09, 0.12
        bev = 0.008 if lod == 0 else 0.0
        bx = lambda c, s: C.board(mb, c, s, wood, bevel=bev) if lod < 2 else mb.box(c, s, wood)
        bx((0, yg, S + fw / 2 - 0.02), (W + 0.04, fd, fw))
        bx((0, yg, S + H - fw / 2 + 0.02), (W + 0.04, fd, fw))
        for sx in (-1, 1):
            bx((sx * (W / 2 - fw / 2 + 0.02), yg, S + H / 2), (fw, fd, H))
        for k in range(1, mull + 1):
            bx((-W / 2 + W * k / (mull + 1), yg, S + H / 2), (0.06, fd * 0.85, H - 0.1))
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=40)
    C.set_json_props(o, kz_params=dict(variant=variant, w=round(W, 3), h=round(H, 3), sill=round(S, 3), depth=round(D, 3),
                                       frame=bool(frame), mullions=mull),
                     kz_opening=dict(w=round(W, 3), h=round(H, 3), sill=round(S, 3), glass_y=round(yg, 3)))
    return o
