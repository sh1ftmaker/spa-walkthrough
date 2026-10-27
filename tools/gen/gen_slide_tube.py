"""Magma Glass Slide: clear glass tube helix with dark bronze ring clamps and vertical bronze support columns.

Targets (asset row + lookbook 13 / sheet-ref-deep #02 / lookbook 24 + 23, measured from the riders and doors):
  * overall 10 x 10 x 48 m (proxy): helix centreline radius 3.6 m, tube outer radius 0.6-0.8 m (concept rider,
    ~1.7 m, fills ~0.9 of the bore when sitting up -> bore 1.3-1.5 m, so tube r 0.65-0.75 by default).
  * pitch 6-9 m per turn (concept 24 shows ~5-6 turns over the drop; 20-22 degree mean slope), ring clamps
    every 1.5-3 m (concept 13: ~2-2.5 m, rings ~0.12 m wide, standing ~5 cm proud of the glass, near black
    bronze), 3-5 vertical bronze columns just outside the helix with a radial bracket arm at every pass.
  * top: a short near-level inlet stub at z ~ 47 m for the launch gate; bottom: the helix eases out over the last
    ~110 degrees to a near-level outlet whose mouth sits ~0.25 m above the pool (z = 0 is the pool floor / base
    of the columns) and whose straight run-out points along `outlet_dir` (default +Y, the front).

Construction (one mesh): glass tube double-walled (outer r, inner r - 30 mm, annulus lips at both mouths) at
LOD0, single wall from LOD1; ring clamps are closed rectangular-section bands (4 bands, 110 mm wide, 45 mm proud)
with a heavier collar at each mouth; water film = a single-sided strip on the bore floor, banked 20 degrees toward
the outside of the bend (material `waterfall`, attribute 'kz_flow_s' = metres along the slide for the scroll);
columns = 0.38 m 12-sided bronze shafts with a base plate and a cap, radial bronze bracket arms with a clamp ring at
every place the helix passes a column.

Parameters (defaults from the proxy):
  h            overall height 30-48 m (default 48 = proxy)
  helix_r      helix centreline radius (default 3.6)
  tube_r       tube outer radius 0.6-0.8 (default seeded 0.66-0.74)
  pitch        rise per turn 6-9 m (default seeded per style)
  ring_spacing 1.5-3 m (default seeded 1.9-2.6)
  columns      number of support columns 3-5 (default per style)
  outlet_dir   outlet run-out heading in degrees about +Z, 0 = +Y (front)  (default 0)
  hand         +1 counter-clockwise / -1 clockwise descent (default seeded)
Styles (seed cycles): 'classic' (pitch ~7.5, 4 columns), 'tight' (pitch ~6.2, 3 columns, slimmer tube),
'open' (pitch ~8.6, 5 columns, fatter tube). Seeds therefore change turn count, tube bore, ring rhythm,
column count/phase and handedness.

Animation: shader. obj['kz_anim'] names the water slot (scrolls along 'kz_flow_s') and the glass slot.
Lighting: probe + emissive (orange lava glow comes from the scene). obj['kz_water_path'] = slide centreline
(top -> outlet), obj['kz_outlet'] = {pos, dir}, obj['kz_inlet'] = {pos, dir} for the launch gate.
"""
import json
import math

from mathutils import Vector, Matrix

import genlib
import kzgeo_common as C

ASSET = 'slide_tube'
FEATURES = ['clear glass tube helix', 'dark bronze ring clamps every few metres', 'vertical bronze support columns',
            'outlet into the splash pool']
STYLES = ['classic', 'tight', 'open']

# per-LOD resolution: glass sides, station length (m), double wall, ring bands/sides, water strip segs, column sides
RES = {
    0: dict(sides=12, step=0.85, double=True, ring_sides=12, ring_bands=4, water=3, col_sides=12, ring_every=1, arms=2),
    1: dict(sides=10, step=1.5, double=False, ring_sides=10, ring_bands=3, water=2, col_sides=8, ring_every=1, arms=1),
    2: dict(sides=7, step=3.2, double=False, ring_sides=6, ring_bands=2, water=1, col_sides=5, ring_every=2, arms=1),
    3: dict(sides=3, step=3.6, double=False, ring_sides=0, ring_bands=0, water=0, col_sides=4, ring_every=0, arms=0),
}


def _transport(pts):
    """tangents + parallel-transport frames (u, v) for a polyline"""
    n = len(pts)
    T = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    u = T[0].cross(Vector((0, 0, 1)))
    if u.length < 1e-6:
        u = Vector((1, 0, 0))
    u.normalize()
    U, V = [], []
    for i in range(n):
        u = (u - T[i] * u.dot(T[i])).normalized()
        U.append(u.copy()); V.append(T[i].cross(u))
    return T, U, V


def _ring(bm, c, u, v, r, n, phase=0.0):
    return [bm.verts.new(c + (u * math.cos(phase + 2 * math.pi * k / n) + v * math.sin(phase + 2 * math.pi * k / n)) * r)
            for k in range(n)]


def build(lod, seed, h=None, w=None, d=None, helix_r=3.6, tube_r=None, pitch=None, ring_spacing=None, columns=None,
          outlet_dir=0.0, hand=None, style=None, _step=None):
    R = dict(RES[min(lod, 3)])
    if _step:
        R['step'] = _step
    p = genlib.proxy(ASSET)
    H = h or p['h']
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    base_pitch = dict(classic=7.5, tight=6.2, open=8.6)[style]
    j_pitch = g.uniform(-0.35, 0.35)
    j_r = g.uniform(-0.03, 0.03)
    j_ring = g.uniform(1.9, 2.6)
    hand_d = g.choice([1, -1])
    col_phase = g.uniform(0, 2 * math.pi)
    pitch = pitch or base_pitch + j_pitch
    tr = tube_r or dict(classic=0.70, tight=0.66, open=0.74)[style] + j_r
    ring_spacing = ring_spacing or j_ring
    ncol = columns or dict(classic=4, tight=3, open=5)[style]
    hand = hand or hand_d
    Rh = helix_r
    k = pitch / (2 * math.pi)                       # drop per radian on the main helix

    # ---------------------------------------------------------------- centreline (angle a from the TOP)
    z_top = H - tr - 0.35
    z_out = tr + 0.25                                # outlet mouth centre: tube bottom ~0.25 m above the floor
    e_top, e_bot = 0.35 * math.pi, 0.6 * math.pi     # ease-in at the top, ease-out at the bottom

    def slope(a, A):
        s0 = min(1.0, a / e_top); s1 = min(1.0, (A - a) / e_bot)
        sm = lambda t: t * t * (3 - 2 * t)
        return 0.12 + 0.88 * min(sm(s0), sm(s1))

    # total sweep A so that the integrated drop = z_top - z_out
    def drop(A, n=400):
        return sum(slope((i + 0.5) * A / n, A) for i in range(n)) * A / n * k
    A = (z_top - z_out) / k
    for _ in range(30):
        A += ((z_top - z_out) - drop(A)) / k
    turns = A / (2 * math.pi)
    L_path = math.hypot(Rh * A, z_top - z_out)
    nst = max(6, int(round(L_path / R['step'])))
    a_list = [A * i / nst for i in range(nst + 1)]
    z_list = [z_top]
    for i in range(1, len(a_list)):
        a0, a1 = a_list[i - 1], a_list[i]
        z_list.append(z_list[-1] - k * slope((a0 + a1) / 2, A) * (a1 - a0))
    # the helix angle about +Z: theta = theta0 + hand * a
    th0 = 0.0
    pts = [Vector((Rh * math.cos(th0 + hand * a), Rh * math.sin(th0 + hand * a), z)) for a, z in zip(a_list, z_list)]
    # straight stubs: inlet (1.4 m, near level) before the top, run-out (1.6 m, 4 % fall) after the bottom
    t_in = Vector((-math.sin(th0) * hand, math.cos(th0) * hand, 0))                    # analytic: LOD-independent
    t_out = Vector((-math.sin(th0 + hand * A) * hand, math.cos(th0 + hand * A) * hand, 0))
    n_in = 2 if lod < 2 else 1
    inlet = [pts[0] - t_in * (1.4 * (n_in - i) / n_in) for i in range(n_in)]
    n_out = 2 if lod < 2 else 1
    outlet = [pts[-1] + t_out * (1.6 * (i + 1) / n_out) - Vector((0, 0, 0.064 * (i + 1) / n_out)) for i in range(n_out)]
    path = inlet + pts + outlet

    # rotate so the run-out heads along outlet_dir (0 = +Y)
    want = math.radians(outlet_dir) + math.pi / 2
    rot = Matrix.Rotation(want - math.atan2(t_out.y, t_out.x), 4, 'Z')
    path = [rot @ q for q in path]
    T, U, V = _transport(path)
    s_along = [0.0]
    for i in range(1, len(path)):
        s_along.append(s_along[-1] + (path[i] - path[i - 1]).length)

    mb = genlib.MeshBuilder()
    m_glass = mb.slot('glass_clear')
    m_ring = mb.slot('bronze', variant='smooth', tint=(0.42, 0.36, 0.3), wear=0.15)
    m_col = mb.slot('bronze', variant='smooth', tint=(0.34, 0.3, 0.26), wear=0.25)
    m_water = mb.slot('waterfall', emissive_level=0.35)
    bm = mb.bm

    # ---------------------------------------------------------------- glass tube
    ns = R['sides']
    outer = [_ring(bm, c, u, v, tr, ns) for c, u, v in zip(path, U, V)]
    gf = []
    for i in range(len(outer) - 1):
        gf += C.bridge_rings(bm, outer[i], outer[i + 1])
    if R['double']:
        ti = 0.03
        inner = [_ring(bm, c, u, v, tr - ti, ns) for c, u, v in zip(path, U, V)]
        for i in range(len(inner) - 1):
            gf += [f for f in C.bridge_rings(bm, inner[i + 1], inner[i])]
        for A_, B_ in ((outer[0], inner[0]), (inner[-1], outer[-1])):
            gf += C.bridge_rings(bm, A_, B_)
    mb._tag(gf, m_glass)
    import bmesh
    bmesh.ops.recalc_face_normals(bm, faces=gf) if not R['double'] else None

    # ---------------------------------------------------------------- water film on the bore floor
    water_vs = []
    if R['water']:
        nw = R['water']
        alpha = math.radians(42)
        rw = tr - 0.06
        strips = []
        for i, (c, t) in enumerate(zip(path, T)):
            down = Vector((0, 0, -1)); down = (down - t * down.dot(t)).normalized()
            radial = Vector((c.x, c.y, 0)).normalized() if Vector((c.x, c.y, 0)).length > 0.5 else Vector((0, 0, 0))
            radial = radial - t * radial.dot(t)
            bank = math.radians(20) if i > n_in and i < len(path) - n_out - 1 else 0.0
            wdir = (down * math.cos(bank) + (radial.normalized() if radial.length > 1e-6 else down) * math.sin(bank)).normalized()
            side = t.cross(wdir)
            row = [bm.verts.new(c + (wdir * math.cos(psi) + side * math.sin(psi)) * rw)
                   for psi in [-alpha + 2 * alpha * q / nw for q in range(nw + 1)]]
            strips.append(row); water_vs.append([(vv, s_along[i]) for vv in row])
        wf = []
        for i in range(len(strips) - 1):
            for q in range(nw):
                wf.append(bm.faces.new((strips[i][q], strips[i + 1][q], strips[i + 1][q + 1], strips[i][q + 1])))
        mb._tag(wf, m_water)
        # orient towards the axis: flip a face if its normal points away from the centreline
        for i in range(len(strips) - 1):
            for q in range(nw):
                f = wf[i * nw + q]
                if f.normal.dot(path[i] - f.calc_center_median()) < 0:
                    f.normal_flip()

    # ---------------------------------------------------------------- ring clamps
    def clamp(i_f, width=0.11, proud=0.045, sides=None, bands=None, mi=m_ring):
        """closed rectangular-section bronze band round the tube at fractional station index i_f"""
        sides = sides or R['ring_sides']; bands = bands or R['ring_bands']
        i0 = int(i_f); fr = i_f - i0; i1 = min(i0 + 1, len(path) - 1)
        c = path[i0].lerp(path[i1], fr); t = T[i0].lerp(T[i1], fr).normalized()
        u = U[i0].lerp(U[i1], fr); u = (u - t * u.dot(t)).normalized(); v = t.cross(u)
        r0, r1 = tr + 0.004, tr + proud
        if bands >= 4:
            sec = [(r0, -width / 2), (r1, -width / 2), (r1, width / 2), (r0, width / 2)]
        elif bands == 3:
            sec = [(r0, -width / 2), (r1, 0.0), (r0, width / 2)]
        else:
            sec = [(r1, -width / 2), (r1, width / 2)]
        rings = [_ring(bm, c + t * dz, u, v, rr, sides) for rr, dz in sec]
        fs = []
        for a_ in range(len(rings) - 1):
            fs += C.bridge_rings(bm, rings[a_], rings[a_ + 1])
        if bands >= 3:
            fs += C.bridge_rings(bm, rings[-1], rings[0])
        if bands == 2:      # open outer band: cap edges as a thin flat ring face-on is not needed at LOD2 distance
            pass
        bmesh.ops.recalc_face_normals(bm, faces=fs) if bands >= 3 else None
        mb._tag(fs, mi)
        return c

    # stations at the column passes (bracket clamps), from the helix angle
    rot_ang = want - math.atan2(t_out.y, t_out.x)
    # keep every column clear of the outlet run-out and the inlet stub (angles of their tangent points)
    keep_out = [rot_ang + th0 + hand * A, rot_ang + th0 + hand * A + hand * math.atan2(1.6, Rh), rot_ang + th0]
    angd = lambda x, y: abs((x - y + math.pi) % (2 * math.pi) - math.pi)
    best = None
    for k_ in range(36):
        ph = col_phase + 2 * math.pi * k_ / 36 / ncol
        clear = min(angd(ph + 2 * math.pi * q / ncol, ko) for q in range(ncol) for ko in keep_out)
        if best is None or clear > best[0] + 1e-6:
            best = (clear, ph)
        if clear > math.radians(50):
            best = (clear, ph); break
    col_phase = best[1]
    col_angles = [col_phase + 2 * math.pi * q / ncol for q in range(ncol)]
    Rc = Rh + tr + 0.50                               # column axis radius
    passes = []                                       # (fractional station index, column angle)
    off = len(inlet)
    for ca in col_angles:
        # helix angle theta = th0 + hand * a, rotated by rot_ang -> world angle
        base = (ca - rot_ang - th0) * hand
        m0 = math.ceil((0.25 - base) / (2 * math.pi))
        a = base + 2 * math.pi * m0
        while a < A - 0.15:
            fi = off + a / A * nst
            passes.append((fi, ca))
            a += 2 * math.pi
    if R['ring_every']:
        n_r = max(2, int(L_path / ring_spacing))
        pass_s = [fi for fi, _ in passes]
        for q in range(0, n_r + 1, R['ring_every']):
            fi = off + q / n_r * nst
            if any(abs(fi - ps) * L_path / nst < ring_spacing * 0.45 for ps in pass_s):
                continue
            clamp(min(fi, len(path) - 1.001))
        # heavier mouth collars
        clamp(0.02, width=0.22, proud=0.07); clamp(len(path) - 1.02, width=0.22, proud=0.07)

    # ---------------------------------------------------------------- columns + bracket arms
    cs = R['col_sides']
    cr = 0.19
    for ca in col_angles:
        x, y = Rc * math.cos(ca), Rc * math.sin(ca)
        zc_top = H
        mb.cylinder((x, y, zc_top / 2), cr, zc_top - (0.06 if lod < 3 else 0), m_col, segs=cs)
        if lod < 3:
            mb.box((x, y, 0.03), (0.5, 0.5, 0.06), m_col, bevel=0.012 if lod == 0 else 0.0)          # base plate
            mb.cylinder((x, y, H - 0.08), cr + 0.05, 0.16, m_col, segs=cs)                           # cap
        if lod < 2:
            mb.cylinder((x, y, 0.32), cr + 0.035, 0.5, m_col, segs=cs)                               # shoe
    if R['arms']:
        for fi, ca in passes:
            i0 = int(fi); fr = fi - i0; i1 = min(i0 + 1, len(path) - 1)
            c = path[i0].lerp(path[i1], fr)
            if R['ring_sides']:
                clamp(fi, width=0.16, proud=0.06)
            radial = Vector((math.cos(ca), math.sin(ca), 0))
            a0 = c + radial * (tr + 0.04)
            # project the bracket's outer end onto the column axis
            a1 = Vector((Rc * math.cos(ca), Rc * math.sin(ca), c.z)) - radial * (cr * 0.6)
            mid = (a0 + a1) / 2; ln = (a1 - a0).length
            yaw = math.atan2(radial.y, radial.x)
            if lod == 0:
                mb.box(mid, (ln, 0.12, 0.16), m_col, rot=(0, 0, yaw), bevel=0.012)
                # diagonal strut under the arm (column to arm root)
                s0 = Vector((Rc * math.cos(ca), Rc * math.sin(ca), c.z - 0.9)) - radial * cr * 0.6
                s1 = a0 + radial * 0.25 + Vector((0, 0, -0.06))
                C.stick(mb, s0, s1, 0.04, 0.04, m_col, segs=6)
                mb.cylinder((Rc * math.cos(ca), Rc * math.sin(ca), c.z), cr + 0.035, 0.3, m_col, segs=8)   # collar
            else:
                mb.box(mid, (ln, 0.12, 0.16), m_col, rot=(0, 0, yaw))

    bm.verts.index_update()
    flow_idx = [(vv.index, s) for row in water_vs for vv, s in row]
    # budget by resolution: if the glass/water stations push us over, lengthen the station step once and say so
    budget = genlib.budget_of(ASSET)
    ntri = C.tri_count(bm)
    if budget and _step is None and ntri > budget[min(lod, 3)] * 1.02:
        per_st = ns * 2 * (2 if R['double'] else 1) + 2 * R['water']
        fixed = ntri - per_st * len(path)
        new_n = max(6, (budget[min(lod, 3)] * 0.99 - fixed) / per_st)
        step2 = R['step'] * len(path) / new_n
        print(f'[slide_tube] LOD{lod} s{seed}: {ntri} tris > budget; station step {R["step"]:.2f} -> {step2:.2f} m')
        bm.free()
        return build(lod, seed, h=h, helix_r=helix_r, tube_r=tube_r, pitch=pitch, ring_spacing=ring_spacing,
                     columns=columns, outlet_dir=outlet_dir, hand=hand, style=style, _step=step2)
    for v in bm.verts:              # coarse LODs: a chord through the eased outlet can dip under the pool floor
        if v.co.z < 0:
            v.co.z = 0.0
    o = mb.to_object(ASSET)
    # ---------------------------------------------------------------- attributes and props
    me = o.data
    flow = me.attributes.new('kz_flow_s', 'FLOAT', 'POINT')
    for vi, s in flow_idx:
        flow.data[vi].value = round(s, 3)
    C.set_json_props(o,
                     kz_anim={'type': 'shader', 'what': 'water film scrolls down the slide; glass catches lava glow',
                              'attr': 'kz_flow_s', 'material_slot': m_water, 'material': 'waterfall',
                              'speed_mps': 9.0, 'glass_slot': m_glass},
                     kz_water_path=[[round(c.x, 3), round(c.y, 3), round(c.z - tr + 0.08, 3)] for c in path[::max(1, len(path) // 60)]],
                     kz_outlet={'pos': [round(c, 3) for c in path[-1]], 'dir': [round(c, 3) for c in T[-1]]},
                     kz_inlet={'pos': [round(c, 3) for c in path[0]], 'dir': [round(c, 3) for c in (-T[0])]},
                     kz_params=dict(style=style, h=H, helix_r=Rh, tube_r=round(tr, 3), pitch=round(pitch, 3),
                                    turns=round(turns, 2), ring_spacing=round(ring_spacing, 2), columns=ncol,
                                    hand=hand, outlet_dir=outlet_dir, path_len=round(s_along[-1], 1), station_step=round(R['step'], 3)))
    genlib.finish(o, smooth_angle=50)
    return o
