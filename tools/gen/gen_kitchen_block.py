"""Open kitchen with steam hood (kitchen_block): stoves and a binchotan grill, shelving with bowl stacks, a timber
steam hood over the fumarole whose duct rises through the roof.

TARGETS (lookbook 07 plan: KITCHEN box beside the ramen counter, ~6 x 5 m at 1:100; lookbook 34: STEAM VENT
over the kitchen, kitchen + ramen counter block ~17 m; lookbook 09: chef at the pass, binchotan flames, bowl
stacks on shelves, stock pots, timber frame, hanging lanterns). No sheet panel exists yet.
  Row: w 12-17, d 5-8, h 4 (typical 17 x 5 x 4); proxy 12 x 8 x 4. Built default 12 x 6 x 4 (inside the proxy);
  w is a parameter (12-17; the 17 m row value needs the proxy w raised, reported).
  Heights from doors/risers: work counters 0.88-0.9 m, shelving 2.2 m (4 boards), beams 3.15-3.4 m, plank roof
  3.4-3.52 m, hood skirt 2.3 m (clears a 1.8 m cook by 0.5 m), hood top 3.3 m, duct + cap to 4.0 m.
  Fumarole: a basalt rock ring ~1.4 m across with a dark throat, under the hood (steam rises through the duct).

FEATURES kept at every LOD: stoves, binchotan grill, shelving with bowl stacks, timber steam hood + duct through
  the roof, fumarole ring, open front (+Y).  LOD1: no bevels, simpler lathes, fewer grill bars; LOD2: shelving
  ware as strips, pots as 3-ring lathes, hood without cladding battens; LOD3: boxes + frustum hood.

PARAMETERS  w 12-17 (12) | d 5-8 (6) | hood 1.8-3.0 (hood skirt width) | shelf_runs 1-3 | stoves 2-5 |
  fumarole_x (-0.3..0.3 of w)
SEEDS change: stove count (3 / 5 / 2), shelf runs (2 / 1 / 3), hood size (2.6 / 2.2 / 3.0) and the fumarole
  position (centre-right / left / centre), d (6 / 5.5 / 7), island counter on / off, pot mix.
MATERIALS (slots by part): frame + hood hinoki dark_timber; back wall + counters lacquer_dark; worktops hinoki
  wet_oiled; stoves, grill, pots iron; coal bed lava (emissive 0.35, embers); shelves hinoki walnut; bowls ceramic
  white / tenmoku; fumarole basalt_wet; duct cap kawara; pendants lantern_andon.
ANIMATION sim-driven: kz_steam (fx_steam) at the fumarole throat (rising through the duct) and over the pots;
  kz_fire (fire glow) at each burner and along the grill. LIGHTS kz_lights: area 3000 K under the hood, andon
  pendants, grill ember glow.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_kawagiri_pod as KK

ASSET = 'kitchen_block'
FEATURES = ['stoves', 'binchotan grill', 'shelving with bowl stacks', 'timber steam hood over the fumarole',
            'duct rising through the roof']


def params(seed, w=None, d=None, hood=None, shelf_runs=None, stoves=None, fumarole_x=None):
    k = (seed - 1) % 3
    return dict(w=w or 12.0, d=d or [6.0, 5.5, 7.0][k], hood=hood or [2.6, 2.2, 3.0][k],
                shelf_runs=shelf_runs or [2, 1, 3][k], stoves=stoves or [3, 5, 2][k],
                fumarole_x=[0.18, -0.22, 0.0][k] if fumarole_x is None else fumarole_x, island=k != 1)


def hood(mb, lod, c, wb, db, wt, z0, z1, M):
    """truncated-pyramid timber hood: 4 clad panels, corner beams, skirt beam; returns nothing"""
    x, y = c
    bm = mb.bm
    t = 0.05
    B = [(x - wb / 2, y - db / 2), (x + wb / 2, y - db / 2), (x + wb / 2, y + db / 2), (x - wb / 2, y + db / 2)]
    T = [(x - wt / 2, y - wt / 2), (x + wt / 2, y - wt / 2), (x + wt / 2, y + wt / 2), (x - wt / 2, y + wt / 2)]
    # panels as closed slabs (outer + inner surfaces)
    fs = []
    for off in (0.0, t):
        vb = [bm.verts.new((px + (x - px) * off / (wb / 2), py + (y - py) * off / (db / 2), z0 + (0 if off == 0 else t))) for px, py in B]
        vt = [bm.verts.new((px + (x - px) * off / max(wt / 2, 0.1), py + (y - py) * off / max(wt / 2, 0.1), z1)) for px, py in T]
        ring = C.bridge_rings(bm, vb, vt)
        fs += ring
        if off == 0:
            outer_b, outer_t = vb, vt
        else:
            inner_b, inner_t = vb, vt
    fs += C.bridge_rings(bm, inner_b, outer_b)            # skirt edge
    fs += C.bridge_rings(bm, outer_t, inner_t)            # top lip
    import bmesh
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, M['hood'])
    if lod <= 1:                                          # skirt beam + corner ridges + battens
        KK.beam_x(mb, lod, x - wb / 2 - 0.05, x + wb / 2 + 0.05, y - db / 2, z0 - 0.06, z0 + 0.12, 0.12, M['frame'])
        KK.beam_x(mb, lod, x - wb / 2 - 0.05, x + wb / 2 + 0.05, y + db / 2, z0 - 0.06, z0 + 0.12, 0.12, M['frame'])
        KK.beam_y(mb, lod, y - db / 2, y + db / 2, x - wb / 2, z0 - 0.06, z0 + 0.12, 0.12, M['frame'])
        KK.beam_y(mb, lod, y - db / 2, y + db / 2, x + wb / 2, z0 - 0.06, z0 + 0.12, 0.12, M['frame'])
        for (bx, by), (tx, ty) in zip(B, T):
            KK.brace(mb, lod, (bx, by, z0 + 0.1), (tx, ty, z1), 0.08, M['frame'])
        if lod == 0:                                      # horizontal battens on the front and back faces
            for f in (0.33, 0.66):
                zz = z0 + (z1 - z0) * f
                ww = wb + (wt - wb) * f
                dd = db + (wt - db) * f
                for sy in (-1, 1):
                    mb.box((x, y + sy * (dd / 2 + 0.02), zz), (ww, 0.04, 0.07), M['frame'])
    else:
        for sy in (-1, 1):
            mb.box((x, y + sy * db / 2, z0 + 0.03), (wb + 0.1, 0.12, 0.18), M['frame'])


def build(lod, seed, w=None, d=None, hood_size=None, shelf_runs=None, stoves=None, fumarole_x=None, **_):
    P = params(seed, w, d, hood_size, shelf_runs, stoves, fumarole_x)
    W, D, H = P['w'], P['d'], 4.0
    hw, hd = W / 2, D / 2
    mb = genlib.MeshBuilder()
    M = dict(frame=mb.slot('hinoki', variant='dark_timber'), hood=mb.slot('hinoki', variant='dark_timber', wear=0.3),
             wall=mb.slot('lacquer_dark', wear=0.3), top=mb.slot('hinoki', variant='wet_oiled'),
             shelf=mb.slot('hinoki', variant='walnut'), iron=mb.slot('iron', wear=0.3),
             coal=mb.slot('lava', emissive_level=0.35), white=mb.slot('ceramic', variant='white'),
             tenmoku=mb.slot('ceramic', variant='tenmoku'), stone=mb.slot('basalt_wet', wetness=0.6),
             tile=mb.slot('kawara'), andon=mb.slot('lantern_andon', emissive_level=0.9),
             counter=mb.slot('lacquer_dark', wear=0.15))
    lights, steam, fire = [], [], []
    z_b0, z_b1 = 3.15, 3.4
    z_r1 = 3.52
    fx = P['fumarole_x'] * W
    fy = -0.05 * D
    hs = P['hood']
    if lod >= 3:
        return _lod3(mb, M, P, W, D, H, fx, fy, hs)
    # ---------------- frame + roof deck (with the duct opening) + back wall
    xs = [-hw + 0.12 + (W - 0.24) * i / 3 for i in range(4)]
    for x in xs:
        KK.post(mb, lod, x, -hd + 0.12, 0, z_b1, 0.22, M['frame'])
    for x in (xs[0], xs[-1]):
        KK.post(mb, lod, x, hd - 0.12, 0, z_b1, 0.22, M['frame'])
    KK.post(mb, lod, 0.0 if abs(fx) > 1.6 else (xs[1] if fx > 0 else xs[2]), hd - 0.12, 0, z_b1, 0.22, M['frame'])
    for sy in (-1, 1):
        KK.beam_x(mb, lod, -hw, hw, sy * (hd - 0.12), z_b0, z_b1, 0.24, M['frame'])
    for x in xs:
        KK.beam_y(mb, lod, -hd, hd, x, z_b0 + 0.05, z_b1, 0.18, M['frame'])
    duct = 1.0
    dx0, dx1 = fx - duct / 2 - 0.05, fx + duct / 2 + 0.05
    dy0, dy1 = fy - duct / 2 - 0.05, fy + duct / 2 + 0.05
    # roof planks run along y; split around the duct
    npl = C.lod_pick(lod, 24, 12, 4)
    pitch = W / npl
    for i in range(npl):
        x0, x1 = -hw + i * pitch, -hw + (i + 1) * pitch
        xc = (x0 + x1) / 2
        ww = pitch - (0.01 if lod <= 1 else 0)
        if x1 > dx0 and x0 < dx1:
            mb.box((xc, (-hd + dy0) / 2, (z_b1 + z_r1) / 2), (ww, dy0 + hd, z_r1 - z_b1), M['frame'])
            mb.box((xc, (dy1 + hd) / 2, (z_b1 + z_r1) / 2), (ww, hd - dy1, z_r1 - z_b1), M['frame'])
        else:
            mb.box((xc, 0, (z_b1 + z_r1) / 2), (ww, D, z_r1 - z_b1), M['frame'])
    KK.timber(mb, lod, (0, -hd + 0.03, z_b0 / 2), (W - 0.1, 0.06, z_b0), M['wall'], 0.006)
    if lod <= 1:                         # vertical battens on the back wall
        for i in range(int(W / 1.0) + 1):
            x = -hw + 0.1 + (W - 0.2) * i / int(W / 1.0)
            mb.box((x, -hd + 0.08, z_b0 / 2), (0.06, 0.04, z_b0), M['frame'])
    # ---------------- shelving runs on the back wall (bowl stacks)
    runs = P['shelf_runs']
    rl = 2.6
    run_x = [(-hw + 0.4 + rl / 2) + i * (rl + 0.5) for i in range(runs)]
    ys = -hd + 0.28
    rs = C.rng(seed, 'shelf')
    for xr in run_x:
        for s in (-1, 1):
            mb.box((xr + s * (rl / 2 - 0.03), ys, 1.1), (0.06, 0.36, 2.2), M['shelf'])
        for j in range(4):
            z = 0.45 + j * 0.55
            KK.timber(mb, lod, (xr, ys, z), (rl, 0.36, 0.035), M['shelf'], 0.004)
            if lod >= 2:
                mb.box((xr, ys, z + 0.1), (rl - 0.3, 0.24, 0.17), M['white'] if j % 2 else M['tenmoku'])
                continue
            nst = 4
            for i in range(nst):
                x = xr - rl / 2 + 0.35 + (rl - 0.7) * i / (nst - 1)
                KK.bowl_stack(mb, lod, (x, ys, z + 0.018), 0.11, 0.08, 3 + rs.randint(0, 2),
                              M['white'] if (i + j) % 2 else M['tenmoku'], segs=6, steps=1, simple_from=1)
    # ---------------- stove range (left of the fumarole along the back) + binchotan grill
    ns = P['stoves']
    sw = 0.95
    x_st0 = run_x[-1] + rl / 2 + 0.4 if runs else -hw + 0.5
    sx = []
    xcur = x_st0
    for i in range(ns):
        if abs(xcur + sw / 2 - fx) < hs / 2 + 0.4:      # skip the fumarole zone
            xcur = fx + hs / 2 + 0.45
        sx.append(xcur + sw / 2)
        xcur += sw + 0.04
    sx = [x for x in sx if x + sw / 2 < hw - 0.2]
    if len(sx) < ns:                                     # not enough room on the back: wrap onto the left end
        extra = ns - len(sx)
        for i in range(extra):
            sx.append(-hw + 0.5 + sw / 2 + i * (sw + 0.04))
    rp = C.rng(seed, 'pots')
    ysv = -hd + 0.75
    for x in sx:
        KK.timber(mb, lod, (x, ysv, 0.42), (sw, 0.75, 0.84), M['iron'], 0.01)
        mb.box((x, ysv, 0.86), (sw + 0.02, 0.77, 0.04), M['iron'])
        for bxo in (-0.22, 0.22):
            if lod <= 1:
                C.lathe(mb, [(0.13, 0.88), (0.14, 0.9), (0.1, 0.9), (0.09, 0.885)], C.lod_pick(lod, 12, 8), M['iron'], closed=False,
                        base=(x + bxo, ysv, 0))
                C.lathe(mb, [(0.09, 0.881), (0.0, 0.881)], C.lod_pick(lod, 8, 6), M['coal'], base=(x + bxo, ysv, 0))
            fire.append([round(x + bxo, 3), round(ysv, 3), 0.9])
        kind = rp.choice(['pot', 'wok', 'pot'])
        if kind == 'pot':
            R = rp.uniform(0.18, 0.24)
            KK.pot(mb, lod, (x - 0.22, ysv, 0.9), R, rp.uniform(0.28, 0.4), M['iron'])
            steam.append([round(x - 0.22, 3), round(ysv, 3), 1.35])
        else:
            C.lathe(mb, [(0.05, 0.9), (0.2, 0.95), (0.27, 1.02), (0.255, 1.02), (0.18, 0.96), (0.0, 0.93)],
                    C.lod_pick(lod, 14, 8, 6), M['iron'], base=(x - 0.22, ysv, 0))
        if lod <= 2:
            KK.pot(mb, lod, (x + 0.22, ysv, 0.9), 0.14, 0.2, M['iron'], handles=False)
    # binchotan grill on a counter at the front-left (faces the pass)
    gx, gy = -hw + 1.6, hd - 1.1
    KK.timber(mb, lod, (gx, gy, 0.37), (2.2, 0.7, 0.74), M['counter'], 0.01)
    KK.timber(mb, lod, (gx, gy, 0.76), (2.3, 0.78, 0.04), M['top'], 0.006)
    KK.timber(mb, lod, (gx, gy, 0.9), (1.9, 0.46, 0.24), M['iron'], 0.008)              # grill box
    if lod <= 2:
        mb.box((gx, gy, 0.95), (1.78, 0.36, 0.04), M['coal'])                          # ember bed
        nb = C.lod_pick(lod, 16, 8, 3)
        for i in range(nb):
            x = gx - 0.85 + 1.7 * i / (nb - 1)
            mb.box((x, gy, 1.025), (0.012, 0.42, 0.012), M['iron'])
    lights.append(C.light_entry((gx, gy, 1.1), kind='point', color_k=1500, watts=40, color=[1.0, 0.35, 0.1]))
    fire.append([round(gx, 3), round(gy, 3), 1.0])
    # ---------------- island prep counter (bowls, ladles) on some seeds
    if P['island']:
        ix, iy = (fx + (2.4 if fx < 2.0 else -2.4)), hd - 1.0
        ix = max(-hw + 1.8, min(hw - 1.8, ix))
        if abs(ix - gx) < 2.6:
            ix = gx + 2.8
        KK.timber(mb, lod, (ix, iy, 0.44), (2.6, 0.85, 0.88), M['counter'], 0.01)
        KK.timber(mb, lod, (ix, iy, 0.9), (2.7, 0.92, 0.05), M['top'], 0.006)
        for i in range(4):
            KK.bowl_stack(mb, lod, (ix - 1.0 + 0.66 * i, iy + 0.15, 0.925), 0.11, 0.085, 4, M['white'] if i % 2 else M['tenmoku'],
                          steps=3 if lod == 0 else 0, simple_from=1)
    # ---------------- fumarole ring + hood + duct + cap
    rf = C.rng(seed, 'fumarole')
    nr = C.lod_pick(lod, 11, 9, 7)
    for i in range(nr):
        a = 2 * math.pi * i / nr + rf.uniform(-0.12, 0.12)
        R = 0.62
        size = (rf.uniform(0.26, 0.34), rf.uniform(0.22, 0.3), rf.uniform(0.16, 0.24))
        C.hull_rock(mb, (fx + R * math.cos(a), fy + R * math.sin(a), 0.0), size, M['stone'], rf,
                    npts=C.lod_pick(lod, 12, 8, 6), ground=0.0, rot=a)
    C.lathe(mb, [(0.5, 0.0), (0.42, 0.03), (0.0, 0.02)], C.lod_pick(lod, 12, 8, 6), M['stone'], base=(fx, fy, 0))   # dark throat
    steam.append([round(fx, 3), round(fy, 3), 0.3])
    z_h0, z_h1 = 2.3, 3.3
    hood(mb, lod, (fx, fy), hs, hs * 0.85, duct, z_h0, z_h1, M)
    # duct through the roof
    KK.timber(mb, lod, (fx, fy, (z_h1 + 3.82) / 2), (duct, duct, 3.82 - z_h1), M['hood'], 0.012)
    if lod <= 1:
        for zz in (z_r1 + 0.05, 3.75):
            mb.box((fx, fy, zz), (duct + 0.06, duct + 0.06, 0.06), M['frame'])
    # cap: pyramid roof on four short posts (steam escapes under it)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            mb.box((fx + sx_ * (duct / 2 - 0.05), fy + sy_ * (duct / 2 - 0.05), 3.86), (0.08, 0.08, 0.08), M['frame'])
    import bmesh
    capw = duct + 0.5
    res = bmesh.ops.create_cone(mb.bm, cap_ends=True, cap_tris=False, segments=4, radius1=capw * 0.707, radius2=0.04, depth=0.1)
    from mathutils import Matrix
    bmesh.ops.transform(mb.bm, matrix=Matrix.Translation((fx, fy, 3.95)) @ Matrix.Rotation(math.pi / 4, 4, 'Z'), verts=res['verts'])
    mb._tag(C._faces_of(res['verts']), M['tile'])
    lights.append(C.light_entry((fx, fy, z_h0 - 0.1), kind='area', color_k=3000, watts=300, size=[hs, hs * 0.85]))
    # ---------------- pendant andon over the island / stoves
    for i, x in enumerate([-hw + 2.5, 0.0 if abs(fx) > 1.5 else fx + 2.8, hw - 2.0][:3]):
        y = hd - 1.6
        if lod <= 2:
            C.stick(mb, (x, y, 2.55), (x, y, z_b1), 0.006, 0.006, M['iron'], segs=4)
        cen = KK.andon(mb, dict(iron=M['iron'], paper=M['andon']), lod, (x, y, 2.25), size=0.22, height=0.3)
        lights.append(C.light_entry(cen, color_k=2200, watts=15))
    off = C.centre_base(mb, centre_x=True, centre_y=True)
    KK.shift_points(off, lights, steam, fire)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=lights, kz_steam=dict(fx='fx_steam', points=steam, vent=steam[-1], duct_top=[round(fx + off[0], 3), round(fy + off[1], 3), 3.9]),
                     kz_fire=dict(fx='fire_glow', points=fire), kz_anim={'type': 'sim', 'fx': ['fx_steam', 'fire_glow']},
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o


def _lod3(mb, M, P, W, D, H, fx, fy, hs):
    """LOD3 (~150 tris): back wall, roof slab, corner posts, stove row, grill counter, hood frustum, duct, cap."""
    hw, hd = W / 2, D / 2
    mb.box((0, -hd + 0.03, 1.6), (W - 0.1, 0.06, 3.2), M['wall'])
    mb.box((0, 0, 3.4), (W, D, 0.24), M['frame'])
    for sx in (-1, 1):
        mb.box((sx * (hw - 0.12), hd - 0.12, 1.65), (0.22, 0.22, 3.3), M['frame'])
    mb.box((hw * 0.35, -hd + 0.75, 0.45), (W * 0.45, 0.75, 0.9), M['iron'])
    mb.box((-hw * 0.5, -hd + 0.28, 1.1), (W * 0.4, 0.36, 2.2), M['tenmoku'])
    mb.box((-hw + 1.6, hd - 1.1, 0.5), (2.3, 0.78, 1.0), M['counter'])
    KK.frustum(mb, (fx, fy, 2.3), hs, hs * 0.85, 1.0, 1.0 / hs, M['hood'])
    mb.box((fx, fy, 3.6), (1.0, 1.0, 0.6), M['hood'])
    mb.box((fx, fy, 3.94), (1.5, 1.5, 0.12), M['tile'])
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o
