"""Slipper wall cubbies (getabako): a wall of open hinoki pigeonholes, each holding a pair of slippers,
on a drawer plinth with a lit toe-kick.

Identifying features kept at every LOD: the grid of open pigeonholes, the pale slipper pairs inside them,
the lit plinth. Proxy (3d/assets.json): 14 x 0.5 x 2.6 m (wall-snapped; back face at y = -d/2, +Y forward).

Construction (LOD0)
  * Carcass in modules of ~1.8-2.4 m (seeded): planked end panels with grooved boards and black iron
    strap brackets, proud module stiles, a moulded cornice (stepped crown or plain slab, seeded) over a
    frieze board, a darker back panel per module.
  * Cells: chamfered shelves and dividers (open at the back where they meet the back panel).
  * Plinth: drawer band with raised-panel drawer fronts and dark pulls (drawer rhythm seeded), optional lit
    end niches, and a recessed toe-kick whose underside carries a back-lit washi strip (the plinth light).
  * Slippers: room slippers (sole + rounded toe cover) toe-out in each cell; fill fraction, pair skew and
    colour mix seeded. The slipper mesh detail is picked to fit the LOD's triangle budget, so a short 2 m
    run gets fully modelled slippers and the 14 m wall gets simpler ones.
  * obj['kz_instances'] (JSON) lists every slipper pair as [x, y, z, yaw, colour] so the runtime can swap
    them for instanced cards (LOD1+); the merged geometry is in vertex group-free material slots
    'tatami' / 'tatami~*' (the slippers) and can be dropped when instancing.

Lights: obj['kz_lights'] (JSON) gives the plinth strip(s): {'type': 'strip', 'p0', 'p1', 'normal', 'color',
'power_w_per_m'}; the strip surface is washi_backlit (emissive) so it also lights the bake.
No animation.
"""
import json
import math
import random

import bmesh
import bpy
from mathutils import Vector

import genlib

ASSET = 'slipper_cubbies'
FEATURES = ['grid of open hinoki pigeonholes', 'a pair of slippers in each cell', 'lit plinth']
PARAMS = dict(w=(2.0, 14.0), h=(2.0, 2.6), cols=None, rows=None, cell=(0.3, 0.25), fill=(0.5, 1.0),
              plinth_light=(True, False), module_w=(1.6, 2.6), cornice=('crown', 'slab'))

LIGHT_COL = (1.0, 0.66, 0.36)


# ------------------------------------------------------------------ low-level helpers
def _to_object(mb, name):
    me = bpy.data.meshes.new(name)
    mb.bm.to_mesh(me)
    mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for i, (mid, params) in enumerate(mb.slots):
        genlib.matlib.assign(o, mid, slot=i, **params)
    return o


def _face(bm, vs, mi, out):
    f = bm.faces.new(vs)
    f.material_index = mi
    f.normal_update()
    if f.normal.dot(Vector(out)) < 0:
        f.normal_flip()
    return f


def quad(bm, a, b, c, d, mi, out):
    return _face(bm, [bm.verts.new(p) for p in (a, b, c, d)], mi, out)


def prism(bm, section, axis, a0, a1, mi, open_edges=(), caps=(False, False), mi_front=None):
    """extrude a closed 2D section along an axis. axis 'x': section in (y, z); 'y': (x, z); 'z': (x, y).
    open_edges: indices i of section edges (i -> i+1) that get no face (hidden against something)."""
    def P(u, v, t):
        if axis == 'x':
            return (t, u, v)
        if axis == 'y':
            return (u, t, v)
        return (u, v, t)
    n = len(section)
    cu = sum(p[0] for p in section) / n
    cv = sum(p[1] for p in section) / n
    A = [bm.verts.new(P(u, v, a0)) for u, v in section]
    B = [bm.verts.new(P(u, v, a1)) for u, v in section]
    faces = []
    for i in range(n):
        if i in open_edges:
            continue
        j = (i + 1) % n
        mu, mv = (section[i][0] + section[j][0]) / 2 - cu, (section[i][1] + section[j][1]) / 2 - cv
        faces.append(_face(bm, [A[i], A[j], B[j], B[i]], mi, P(mu, mv, 0)))
    if caps[0]:
        faces.append(_face(bm, A[::-1], mi, P(0, 0, -1)))
    if caps[1]:
        faces.append(_face(bm, B, mi, P(0, 0, 1)))
    if mi_front is not None:                      # lit face-frame edge vs darker inner faces
        for f in faces:
            if f.normal.y > 0.6:
                f.material_index = mi_front
    return faces


def iron_plate(bm, x0, x1, y, z0, z1, mi, t=0.004):
    """thin front-facing iron plate (front + 4 edges), standing proud of the plane y"""
    prism(bm, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 'y', y - 0.001, y + t, mi, caps=(False, True))


def iron_plate_side(bm, x, y0, y1, z0, z1, mi, sx, t=0.004):
    """thin iron plate on an end face (normal +-X)"""
    xa, xb = sorted((x, x + sx * t))
    prism(bm, [(y0, z0), (y1, z0), (y1, z1), (y0, z1)], 'x', xa, xb, mi, caps=(sx < 0, sx > 0))


def _drawer_groups(mods, n_per_module, gap):
    """drawer slots: n equal fronts per module (the first and last slot of the run become the lit niches)"""
    out = []
    for mi_, (a, b) in enumerate(mods):
        n = max(2, min(n_per_module, int((b - a) / 0.25)))
        wdr = (b - a - (n - 1) * gap) / n
        for k in range(n):
            x0 = a + k * (wdr + gap)
            out.append((mi_, x0, x0 + wdr))
    return out


def _niche(bm, x0, x1, yf, zb0, zb1, st, wood, nglow):
    """open bay 0.28 m deep: wooden back, floor and sides lit by an emissive strip hidden on the bay ceiling"""
    yn = yf - 0.28
    z0, z1 = zb0 + 0.01, zb1 - st
    quad(bm, (x0, yn, z0), (x1, yn, z0), (x1, yn, z1), (x0, yn, z1), wood, (0, 1, 0))
    quad(bm, (x0, yn, z0), (x1, yn, z0), (x1, yf - 0.004, z0), (x0, yf - 0.004, z0), wood, (0, 0, 1))
    for xs_ in (x0, x1):
        quad(bm, (xs_, yn, z0), (xs_, yf - 0.004, z0), (xs_, yf - 0.004, z1), (xs_, yn, z1), wood, (1 if xs_ == x0 else -1, 0, 0))
    quad(bm, (x0 + 0.015, yf - 0.1, z1 - 0.002), (x1 - 0.015, yf - 0.1, z1 - 0.002), (x1 - 0.015, yf - 0.045, z1 - 0.002),
         (x0 + 0.015, yf - 0.045, z1 - 0.002), nglow, (0, 0, -1))


def tri_count(bm):
    return sum(len(f.verts) - 2 for f in bm.faces)


def chamfer_rect(u0, u1, v0, v1, c, front_side):
    """rectangle (u0..u1, v0..v1) with the two corners on `front_side` ('v1' or 'u1') chamfered by c.
    Returned CCW, starting at the back-left corner; the back edge index is returned too (for open_edges)."""
    if c <= 0:
        pts = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    elif front_side == 'v1':
        pts = [(u0, v0), (u1, v0), (u1, v1 - c), (u1 - c, v1), (u0 + c, v1), (u0, v1 - c)]
    else:   # front at u = u1
        pts = [(u0, v0), (u1 - c, v0), (u1, v0 + c), (u1, v1 - c), (u1 - c, v1), (u0, v1)]
    return pts


# ------------------------------------------------------------------ slippers
# tier: (outline points, sole walls, toe-cover segments across, along)
TIERS = [(10, True, 4, 3), (8, True, 4, 2), (6, True, 3, 2), (5, True, 2, 2), (6, False, 3, 2), (5, False, 3, 1), (4, False, 2, 1), (0, False, 2, 1), ('card', 0, 0, 0)]


def tier_tris(t):
    if t[0] == 'card':
        return 2
    n, walls, k, m = t
    return 2 * ((max(0, n - 2) + (2 * n if walls else 0) + 2 * k * m))   # per pair


def _hw(y, L, W):
    """sole half-width at y (toe at +L/2): ellipse, wider at the ball, slight waist"""
    t = max(-1.0, min(1.0, 2 * y / L))
    return W / 2 * math.sqrt(max(0.0, 1 - t * t)) ** 0.85 * (0.86 + 0.14 * t) * (1.0 - 0.07 * math.exp(-((t + 0.15) / 0.3) ** 2))


def _sole_outline(L, W, n):
    """slipper sole outline, toe at +y, centred; n points CCW from the toe"""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + math.pi / 2
        y = math.sin(a) * L / 2 * 0.995
        pts.append((math.copysign(_hw(y, L, W), math.cos(a)) if abs(math.cos(a)) > 1e-6 else 0.0, y))
    return pts


def slipper(bm, cx, cy, z, yaw, L, W, tier, m_top, m_sole, m_cover, m_strap=None):
    c, s = math.cos(yaw), math.sin(yaw)
    T = lambda x, y, zz: (cx + c * x - s * y, cy + s * x + c * y, z + zz)
    if tier[0] == 'card':
        return
    n, walls, k, m = tier
    th = 0.025 if walls else 0.012          # thick tan footbed (concept)
    if n:
        ol = _sole_outline(L, W, n)
        top = [bm.verts.new(T(x, y, th)) for x, y in ol]
        _face(bm, top, m_top, (0, 0, 1))
        if walls:
            bot = [bm.verts.new(T(x * 0.96, y * 0.97, 0.0)) for x, y in ol]
            for i in range(n):
                j = (i + 1) % n
                mx, my = (ol[i][0] + ol[j][0]) / 2, (ol[i][1] + ol[j][1]) / 2
                _face(bm, [top[i], top[j], bot[j], bot[i]], m_sole, (c * mx - s * my, s * mx + c * my, 0))
    # toe cover: an elliptical dome over the front ~55 %, highest at the instep opening
    H = 0.045                                # cover crown ~0.07 m above the shelf
    y_open, y_tip = -0.06 * L / 0.25, L / 2 * 0.9
    grid = []
    for j in range(m + 1):
        v = (j / m) ** 0.7
        y = y_open + (y_tip - y_open) * v
        half = _hw(y, L, W) * 1.03 + 0.002
        # loaf profile: instep opening at 0.62 H, crown at ~45 %, blunt rounded toe (never a point)
        prof = 0.62 + 0.38 * math.sin(math.pi * min(1.0, v / 0.9)) if v < 0.45 else max(0.22, math.cos((v - 0.45) / 0.55 * math.pi / 2) ** 0.7)
        row = []
        for i in range(k + 1):
            u = 2 * i / k - 1
            hh = H * math.sqrt(max(0.0, 1 - u * u)) ** 0.6 * prof
            row.append(bm.verts.new(T(u * half, y, th + hh)))
        grid.append(row)
    for j in range(m):
        for i in range(k):
            q = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
            if len({v.co.to_tuple(5) for v in q}) < 4:
                q = [v for idx, v in enumerate(q) if v.co.to_tuple(5) not in {w.co.to_tuple(5) for w in q[:idx]}]
                if len(q) < 3:
                    continue
            ctr = sum((v.co for v in q), Vector()) / len(q)
            mi_ = m_strap if (m_strap is not None and j == 0 and m >= 2) else m_cover   # brown band at the instep opening
            _face(bm, q, mi_, (ctr.x - cx, ctr.y - cy, 0.02 + (ctr.z - z)))


def slipper_card(bm, cx, cy, z, yaw, cw, L, mi):
    """LOD2/LOD3-style pair: one pale quad tilted up towards the toes"""
    c, s = math.cos(yaw), math.sin(yaw)
    T = lambda x, y, zz: (cx + c * x - s * y, cy + s * x + c * y, z + zz)
    quad(bm, T(-cw / 2, -L / 2, 0.01), T(cw / 2, -L / 2, 0.01), T(cw / 2, L / 2, 0.045), T(-cw / 2, L / 2, 0.045), mi, (0, 0.6, 1))


# ------------------------------------------------------------------ build
def build(lod, seed, w=None, h=None, d=None, cols=None, rows=None, cell_w=0.3, cell_h=0.25, fill=None,
          plinth_light=True, module_w=None, cornice=None, **_):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    budget = (genlib.budget_of(ASSET) or [8000, 3200, 900, 80])[lod]
    # seed 1 is the 14 m arrival wall; other seeds sample the parameter ranges (width, height/rows, fill, cornice)
    w_seed = p['w'] if seed == 1 else r.choice([2.0, 3.0, 4.2, 6.0, 8.4, 10.0])
    h_seed = p['h'] if seed == 1 else r.choice([2.0, 2.1, 2.3, 2.6])
    w = min(max(w or w_seed, 2.0), 14.0)
    h = min(max(h or h_seed, 2.0), 2.6)
    d = min(d or p['d'], p['d'])
    fill_seed = r.uniform(0.82, 0.95) if seed == 1 else r.choice([r.uniform(0.5, 0.65), r.uniform(0.85, 0.97)])
    fill = fill if fill is not None else fill_seed
    empty_end = 0 if fill > 0.8 else r.choice([1, 2, 3])   # emptied columns at the desk end on part-filled walls
    cornice = cornice or ('slab' if seed % 2 else 'crown')   # concept: flat top board; crown is the alternative
    module_w = module_w or r.uniform(1.75, 2.45)
    tk = r.uniform(0.09, 0.11)                  # toe-kick height (light pool under the plinth)
    db = r.uniform(0.23, 0.27)                  # drawer band height
    drawer_rhythm = r.choice([4, 5, 6])         # drawer fronts per module
    niches = plinth_light                       # lit open end niches: the concept's signature
    straps = True
    cell_h = cell_h * r.uniform(0.94, 1.06)
    mb = genlib.MeshBuilder()
    bm = mb.bm
    k = r.uniform(0.82, 0.95)
    base = (0.47 * k * 1.08, 0.36 * k * 1.08, 0.25 * k * 1.08)   # library hinoki wet_oiled tint (aged honey-brown), seeded shade
    wood = mb.slot('hinoki', tint=base, wear=round(r.uniform(0.15, 0.35), 2))                     # face frame
    mid = mb.slot('hinoki', tint=tuple(round(c * 0.55, 4) for c in base), roughness_offset=0.05)    # shelf tops, divider sides
    inner = mb.slot('hinoki', tint=tuple(round(c * 0.37, 4) for c in base), roughness_offset=0.1)   # cell backs (35-40 %)
    cap = mb.slot('hinoki', variant='dark_timber')                                                  # heavier dark cornice cap
    dark = mb.slot('iron', wear=0.35)                                                               # straps, plates, pulls
    # back-lit washi (metric UVs); levels against its EmitStrength 0.3
    glow = mb.slot('washi_backlit', tint=LIGHT_COL, emissive_level=90.0) if plinth_light else dark    # hidden strip: floor wash
    niche_glow = mb.slot('washi_backlit', tint=LIGHT_COL, emissive_level=75.0) if plinth_light else dark  # hidden niche-ceiling strip
    sole = mb.slot('hinoki', variant='natural')                                                     # honey-tan wood footbed
    s_cols = [sole, sole, sole]
    # uppers (linen): warm tan, light honey, charcoal (<10 %), with a darker brown band at the instep opening
    s_cov = [mb.slot('linen', tint=(0.62, 0.44, 0.26)), mb.slot('linen', tint=(0.76, 0.6, 0.4)), mb.slot('linen', tint=(0.2, 0.2, 0.22))]
    strap = mb.slot('linen', tint=(0.36, 0.22, 0.12))
    s_weights = [0.7, 0.23, 0.07]

    # ---------------- layout
    over = 0.03                                  # cornice overhang (front)
    yb, yf = -d / 2, d / 2 - over                # carcass back / front
    side_in = 0.012                              # carcass inset from the cornice ends
    es, ms = 0.06, 0.07                          # end panel / module post widths
    xL, xR = -w / 2 + side_in, w / 2 - side_in
    M = max(1, round((xR - xL) / module_w))
    inner_w = (xR - xL) - 2 * es - (M - 1) * ms
    mod_w = inner_w / M
    dt = 0.04                                    # vertical dividers (module posts 0.07)
    cpm = max(1, round((mod_w + dt) / (cell_w + dt))) if not cols else max(1, round(cols / M))
    ch = (0.095 if cornice == 'crown' else 0.07)
    fr = 0.06
    st = 0.022                                   # shelf thickness
    z_c0 = tk + db + st
    z_c1 = h - ch - fr
    nrows = rows or max(1, round((z_c1 - z_c0) / cell_h))
    pitch = (z_c1 - z_c0) / nrows
    recess = 0.012                               # shelves/dividers sit back from the stiles
    yfi = yf - recess
    mods = []
    for mi_ in range(M):
        a = xL + es + mi_ * (mod_w + ms)
        mods.append((a, a + mod_w))
    cw_clear = (mod_w - (cpm - 1) * dt) / cpm

    def cells():
        for mi_, (a, b) in enumerate(mods):
            for ci in range(cpm):
                x0 = a + ci * (cw_clear + dt)
                for ri in range(nrows):
                    zf = z_c0 + ri * pitch
                    yield mi_, ci, ri, x0, x0 + cw_clear, zf

    # slipper placement (same at every LOD: seeded independently of the LOD)
    rs = random.Random(f'{seed}:slippers')
    pairs = []
    total_cols = M * cpm
    for mi_, ci, ri, x0, x1, zf in cells():
        if rs.random() > fill or (mi_ * cpm + ci) >= total_cols - empty_end:
            continue
        col = rs.choices(range(3), weights=s_weights)[0]
        pairs.append(dict(x=(x0 + x1) / 2 + rs.uniform(-0.012, 0.012), z=zf, yaw=rs.uniform(-0.07, 0.07),
                          splay=rs.uniform(0.0, 0.06), col=col, back=rs.uniform(0.0, 0.04), single=False))
    depth_clear = yfi - (yb + 0.012)
    L = min(0.26, depth_clear - 0.08)
    Wd = min(0.095, (cw_clear - 0.03) / 2.2)    # 0.095 m soles + 0.02 m gap: the pair fills ~70 % of a 0.30 m cell

    # ---------------- carcass
    if lod == 0:
        _carcass_lod0(bm, r, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, cpm, dt, cw_clear, z_c0, z_c1, nrows, pitch, st,
                      tk, db, ch, fr, cornice, drawer_rhythm, niches, straps, wood, inner, dark, glow, niche_glow, mid, cap)
    elif lod == 1:
        _carcass_lod1(bm, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, cpm, dt, cw_clear, z_c0, z_c1, nrows, pitch, st,
                      tk, db, ch, fr, drawer_rhythm, niches, wood, inner, dark, glow, niche_glow, mid, cap)
    elif lod == 2:
        _carcass_lod2(bm, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, cpm, dt, cw_clear, z_c0, z_c1, nrows, pitch, st,
                      tk, db, ch, fr, wood, inner, dark, glow, mid, cap, niche_glow if niches else None)
    else:
        _carcass_lod3(bm, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, z_c0, z_c1, nrows, pitch, st, tk, db, ch, wood, inner, glow, cap,
                      niche_glow if niches else None, cpm=cpm, dt=dt, cw_clear=cw_clear, budget=budget, nrows_s=nrows)

    # ---------------- slippers, detail chosen to fit what is left of the budget
    left = budget - tri_count(bm)
    if lod <= 2:
        # mixed tiers: the richest pair of consecutive tiers that fits; eye-level cells get the better one
        avail = TIERS if lod == 0 else TIERS[3:] if lod == 1 else TIERS[6:]
        cost = lambda t, q: tier_tris(t) / (2 if q['single'] and t[0] != 'card' else 1)
        order = sorted(range(len(pairs)), key=lambda i: abs(pairs[i]['z'] + 0.1 - 1.25))
        choice = [avail[-1]] * len(pairs)
        for hi, lo_ in zip(avail, avail[1:] + [avail[-1]]):
            base = sum(cost(lo_, q) for q in pairs)
            if base > left and lo_ is not avail[-1]:
                continue
            spent, n_hi = base, 0
            for i in order:
                extra = cost(hi, pairs[i]) - cost(lo_, pairs[i])
                if spent + extra > left:
                    break
                spent += extra; n_hi += 1
            choice = [lo_] * len(pairs)
            for i in order[:n_hi]:
                choice[i] = hi
            break
        for qi, q in enumerate(pairs):
            tier = choice[qi]
            y_c = yfi - 0.02 - L / 2 - q['back']
            if tier[0] == 'card':
                slipper_card(bm, q['x'], y_c, q['z'], math.pi + q['yaw'], 2 * Wd + 0.018, L * 0.9, s_cov[q['col']])
                continue
            gap = 0.018 + q['splay'] * 0.03
            for side in ((-1,) if q['single'] else (-1, 1)):
                sx = q['x'] + side * (Wd / 2 + gap / 2)
                slipper(bm, sx, y_c, q['z'], math.pi + q['yaw'] + side * q['splay'] * 0.5, L, Wd, tier, s_cols[q['col']], strap, s_cov[q['col']], strap)   # heel-out (concept)
    else:
        # LOD3: one pale strip per row across the whole run
        for ri in range(nrows):
            zf = z_c0 + ri * pitch
            quad(bm, (xL + es, yfi - 0.06, zf + 0.03), (xR - es, yfi - 0.06, zf + 0.03), (xR - es, yfi - 0.3, zf + 0.06),
                 (xL + es, yfi - 0.3, zf + 0.06), s_cov[0], (0, 0.5, 1))
        # interior verticals with what is left, at real divider positions, so it still reads as pigeonholes
        per_mod = max(0, (budget - tri_count(bm)) // 2 // M) if cpm > 1 else 0
        for a_, b_ in mods:
            for j in range(min(per_mod, cpm - 1)):
                ci = round((j + 1) * cpm / (min(per_mod, cpm - 1) + 1))
                ci = max(1, min(cpm - 1, ci))
                x0 = a_ + ci * cw_clear + (ci - 1) * dt
                quad(bm, (x0, yfi, z_c0), (x0 + dt, yfi, z_c0), (x0 + dt, yfi, z_c1), (x0, yfi, z_c1), wood, (0, 1, 0))

    o = _to_object(mb, ASSET)
    o['kz_instances'] = json.dumps({'slipper_pair': [[round(q['x'], 3), round(yfi - 0.02 - L / 2 - q['back'], 3), round(q['z'], 3),
                                                      round(q['yaw'], 3), q['col']] for q in pairs], 'pair_size': [round(2 * Wd + 0.015, 3), round(L, 3)]})
    if plinth_light:
        o['kz_lights'] = json.dumps([{'type': 'strip', 'p0': [round(xL + es, 3), round(yf - 0.03, 3), round(tk - 0.002, 3)],
                                      'p1': [round(xR - es, 3), round(yf - 0.03, 3), round(tk - 0.002, 3)], 'normal': [0, 0.35, -1],
                                      'color': list(LIGHT_COL), 'power_w_per_m': 6.0}])
    o['kz_params'] = json.dumps(dict(w=round(w, 3), h=round(h, 3), d=round(d, 3), modules=M, cols=M * cpm, rows=nrows,
                                     fill=round(fill, 3), empty_end=empty_end, cornice=cornice, plinth_light=plinth_light, niches=niches, pairs=len(pairs)))
    genlib.finish(o, smooth_angle=60)
    return o


def _object_uvs(o, slot):
    """UV0 0..1 per face on one 'object'-UV slot (the andon panel expects one paper face per 0..1 tile)"""
    me = o.data
    idx = {slot}
    uv = me.uv_layers['UVMap'].data
    for p in me.polygons:
        if p.material_index not in idx:
            continue
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(0, 1), (0, 2), (0, 1)][ax] if ax != 0 else (1, 2)
        if ax == 1:
            a, b = 0, 2
        cs = [me.vertices[me.loops[li].vertex_index].co for li in p.loop_indices]
        lo = [min(c[a] for c in cs), min(c[b] for c in cs)]
        hi = [max(c[a] for c in cs), max(c[b] for c in cs)]
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = ((c[a] - lo[0]) / max(1e-6, hi[0] - lo[0]), (c[b] - lo[1]) / max(1e-6, hi[1] - lo[1]))


# ------------------------------------------------------------------ carcass by LOD
def _cornice_section(cornice, yb, yf, d, z0, ch, lod):
    yfront = d / 2
    if cornice == 'crown':
        # squared fascia, one 0.04 m step, flat top board overhanging ~0.03 m with a square edge
        return [(yb, z0), (yf + 0.002, z0), (yf + 0.002, z0 + 0.04), (yfront, z0 + 0.04), (yfront, z0 + ch), (yb, z0 + ch)]
    # slab (default): fascia board + flat top board, squared edges
    return [(yb, z0), (yf + 0.002, z0), (yf + 0.002, z0 + ch - 0.035), (yfront, z0 + ch - 0.035), (yfront, z0 + ch), (yb, z0 + ch)]


def _carcass_lod0(bm, r, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, cpm, dt, cw_clear, z_c0, z_c1, nrows, pitch, st,
                  tk, db, ch, fr, cornice, rhythm, niches, straps, wood, inner, dark, glow, nglow, mid, cap):
    c = 0.004
    # cornice: full width, moulded profile, end caps, dark timber cap
    sec = _cornice_section(cornice, yb, yf, d, h - ch, ch, 0)
    prism(bm, sec, 'x', -w / 2, w / 2, cap, open_edges=(len(sec) - 1,), caps=(True, True))
    # iron corner plates on the front cornice corners (front face + wrapping onto the end)
    for sx in (-1, 1):
        xe = sx * w / 2
        x0, x1 = sorted((xe, xe - sx * 0.07))
        iron_plate(bm, x0, x1, d / 2 + 0.002, h - ch + 0.012, h - 0.012, dark)
        iron_plate_side(bm, xe + sx * 0.002, d / 2 - 0.07, d / 2, h - ch + 0.012, h - 0.012, dark, sx)
    # frieze board under the cornice (front + underside)
    quad(bm, (xL + es, yf, z_c1), (xR - es, yf, z_c1), (xR - es, yf, h - ch), (xL + es, yf, h - ch), wood, (0, 1, 0))
    # end panels: planked outer face (two V grooves), chamfered front edge, full height
    for sx in (-1, 1):
        x_out, x_in = (xL, xL + es) if sx < 0 else (xR, xR - es)
        dd = yf - yb
        gs = [yb + dd * k / 4 for k in (1, 2, 3)]          # plank seams at ~0.12 m pitch
        groove = []
        for g in gs:                                       # back-to-front along the outer face
            groove += [(x_out, g - 0.004), (x_out - sx * 0.004, g), (x_out, g + 0.004)]
        if sx < 0:
            sec = [(x_out, yb), (x_in, yb), (x_in, yf), (x_out + c * 2, yf), (x_out, yf - c * 2)] + list(reversed(groove))
        else:
            sec = [(x_in, yb), (x_out, yb)] + groove + [(x_out, yf - c * 2), (x_out - c * 2, yf), (x_in, yf)]
        prism(bm, sec, 'z', 0.0, h - ch, wood, open_edges=(0,), caps=(False, False))
        # iron strap brackets on the outer face, front and back edges, top and bottom
        if straps:
            # iron L-straps: top, middle, bottom; each wraps the front corner (side leg + front leg) and the back edge
            for zc in (tk + db * 0.5, (z_c0 + z_c1) / 2, h - ch - 0.1):
                iron_plate_side(bm, x_out + sx * 0.002, yf - 0.13, yf, zc - 0.025, zc + 0.025, dark, sx)
                iron_plate_side(bm, x_out + sx * 0.002, yb, yb + 0.1, zc - 0.025, zc + 0.025, dark, sx)
                xa, xb = sorted((x_out, x_in))
                iron_plate(bm, xa, xb, yf + 0.002, zc - 0.06, zc + 0.06, dark)
    # module stiles: proud, chamfered front, full height of the cell zone + plinth
    for i in range(len(mods) - 1):
        a = mods[i][1]
        sec = chamfer_rect(a, a + ms, yb + 0.012, yf, c, 'v1')
        prism(bm, sec, 'z', tk, z_c1, wood, open_edges=(0,))
        for z0_, z1_ in ((z_c1 - 0.125, z_c1 - 0.005), (z_c0 - st - 0.02, z_c0 + 0.1)):
            iron_plate(bm, a - 0.006, a + ms + 0.006, yf + 0.002, z0_, z1_, dark)
    # back panel per module (dark interior)
    for a, b in mods:
        quad(bm, (a, yb + 0.012, z_c0), (b, yb + 0.012, z_c0), (b, yb + 0.012, z_c1), (a, yb + 0.012, z_c1), inner, (0, 1, 0))
    # shelves (incl. the plinth top and the cell-zone ceiling), chamfered nosing, open back
    for a, b in mods:
        for ri in range(nrows + 1):
            zt = z_c0 + ri * pitch if ri < nrows else z_c1 + st
            # shelf with a 5 mm raised front lip
            sec = [(yb + 0.012, zt - st), (yfi - c, zt - st), (yfi, zt - st + c), (yfi, zt + 0.005), (yfi - 0.012, zt + 0.005),
                   (yfi - 0.012, zt), (yb + 0.012, zt)]
            prism(bm, sec, 'x', a, b, mid, open_edges=(6,), mi_front=wood)
        # dividers between cells
        for ci in range(1, cpm):
            x0 = a + ci * cw_clear + (ci - 1) * dt
            sec = chamfer_rect(x0, x0 + dt, yb + 0.012, yfi, c, 'v1')
            prism(bm, sec, 'z', z_c0, z_c1, mid, open_edges=(0,), mi_front=wood)
    # plinth: drawer band face, drawers, niches, toe-kick + light strip
    zb0, zb1 = tk, tk + db
    all_cols = []
    for mi_, (a, b) in enumerate(mods):
        for ci in range(cpm):
            all_cols.append((mi_, a + ci * (cw_clear + dt), a + ci * (cw_clear + dt) + cw_clear))
    groups = _drawer_groups(mods, rhythm, dt)
    for gi, (mi_, x0, x1) in enumerate(groups):
        is_niche = niches and (gi == 0 or gi == len(groups) - 1)
        m = 0.012
        if is_niche:
            _niche(bm, x0, x1, yf, zb0, zb1, st, wood, nglow)
            continue
        # band face behind this drawer (skipped at niches so their glow shows)
        quad(bm, (x0 - dt / 2, yf - 0.006, zb0), (x1 + dt / 2, yf - 0.006, zb0), (x1 + dt / 2, yf - 0.006, zb1 - st), (x0 - dt / 2, yf - 0.006, zb1 - st), inner, (0, 1, 0))
        # raised-panel drawer front: back rectangle at the band face, smaller front face, sloped fields
        y0f, y1f = yf - 0.006, yf + 0.006
        bx0, bx1, bz0, bz1 = x0 + m * 0.3, x1 - m * 0.3, zb0 + 0.012, zb1 - st - 0.008
        inset = 0.014
        back = [(bx0, y0f, bz0), (bx1, y0f, bz0), (bx1, y0f, bz1), (bx0, y0f, bz1)]
        front = [(bx0 + inset, y1f, bz0 + inset), (bx1 - inset, y1f, bz0 + inset), (bx1 - inset, y1f, bz1 - inset), (bx0 + inset, y1f, bz1 - inset)]
        Bv = [bm.verts.new(q) for q in back]; Fv = [bm.verts.new(q) for q in front]
        _face(bm, Fv, wood, (0, 1, 0))
        for i in range(4):
            j = (i + 1) % 4
            mv = Vector(back[i]).lerp(Vector(back[j]), 0.5) - Vector(((bx0 + bx1) / 2, y0f, (bz0 + bz1) / 2))
            _face(bm, [Bv[i], Bv[j], Fv[j], Fv[i]], wood, (mv.x, 0.5, mv.z))
        # pull: small dark bar with chamfered ends
        pxc, pzc, pw = (x0 + x1) / 2, (bz0 + bz1) / 2 + 0.01, min(0.11, (x1 - x0) * 0.35)
        sec = [(pxc - pw / 2, pzc - 0.009), (pxc + pw / 2, pzc - 0.009), (pxc + pw / 2 - 0.006, pzc + 0.009), (pxc - pw / 2 + 0.006, pzc + 0.009)]
        prism(bm, [(x, z) for x, z in sec], 'y', y1f, y1f + 0.012, dark, caps=(False, True))
    # toe-kick: recessed face, underside of the band, light strip
    yk = yf - 0.06
    quad(bm, (xL + es, yk, 0.0), (xR - es, yk, 0.0), (xR - es, yk, tk), (xL + es, yk, tk), inner, (0, 1, 0))
    quad(bm, (xL + es, yk, tk), (xR - es, yk, tk), (xR - es, yf - 0.006, tk), (xL + es, yf - 0.006, tk), inner, (0, 0, -1))
    quad(bm, (xL + es, yf - 0.045, tk - 0.002), (xR - es, yf - 0.045, tk - 0.002), (xR - es, yf - 0.018, tk - 0.002), (xL + es, yf - 0.018, tk - 0.002), glow, (0, 0, -1))
    # plinth front rail under the drawers (a thin lip that hides the strip from eye height)
    sec = [(yf - 0.014, tk), (yf, tk), (yf, tk + 0.012), (yf - 0.014, tk + 0.012)]
    prism(bm, sec, 'x', xL + es, xR - es, wood)


def _carcass_lod1(bm, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, cpm, dt, cw_clear, z_c0, z_c1, nrows, pitch, st,
                  tk, db, ch, fr, rhythm, niches, wood, inner, dark, glow, nglow, mid, cap):
    sec = _cornice_section('crown', yb, yf, d, h - ch, ch, 1) if ch > 0.1 else _cornice_section('slab', yb, yf, d, h - ch, ch, 1)
    prism(bm, sec, 'x', -w / 2, w / 2, cap, open_edges=(len(sec) - 1,), caps=(True, True))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * w / 2, sx * (w / 2 - 0.07)))
        quad(bm, (x0, d / 2 + 0.002, h - ch + 0.012), (x1, d / 2 + 0.002, h - ch + 0.012), (x1, d / 2 + 0.002, h - 0.012), (x0, d / 2 + 0.002, h - 0.012), dark, (0, 1, 0))
        xa, xb = sorted((sx * (w / 2 - 0.012), sx * (w / 2 - 0.012 - es)))
        for zc in (tk + db * 0.5, (z_c0 + z_c1) / 2, h - ch - 0.1):
            quad(bm, (xa, yf + 0.002, zc - 0.06), (xb, yf + 0.002, zc - 0.06), (xb, yf + 0.002, zc + 0.06), (xa, yf + 0.002, zc + 0.06), dark, (0, 1, 0))
    quad(bm, (xL + es, yf, z_c1), (xR - es, yf, z_c1), (xR - es, yf, h - ch), (xL + es, yf, h - ch), wood, (0, 1, 0))
    for sx in (-1, 1):
        x_out, x_in = (xL, xL + es) if sx < 0 else (xR, xR - es)
        a, b = sorted((x_out, x_in))
        prism(bm, [(a, yb), (b, yb), (b, yf), (a, yf)], 'z', 0.0, h - ch, wood, open_edges=(0,))
    for i in range(len(mods) - 1):
        a = mods[i][1]
        prism(bm, [(a, yb + 0.012), (a + ms, yb + 0.012), (a + ms, yf), (a, yf)], 'z', tk, z_c1, wood, open_edges=(0,))
    for a, b in mods:
        quad(bm, (a, yb + 0.012, z_c0), (b, yb + 0.012, z_c0), (b, yb + 0.012, z_c1), (a, yb + 0.012, z_c1), inner, (0, 1, 0))
        for ri in range(nrows + 1):
            zt = z_c0 + ri * pitch if ri < nrows else z_c1 + st
            prism(bm, [(yb + 0.012, zt - st), (yfi, zt - st), (yfi, zt), (yb + 0.012, zt)], 'x', a, b, mid, open_edges=(3,), mi_front=wood)
        for ci in range(1, cpm):
            x0 = a + ci * cw_clear + (ci - 1) * dt
            prism(bm, [(x0, yb + 0.012), (x0 + dt, yb + 0.012), (x0 + dt, yfi), (x0, yfi)], 'z', z_c0, z_c1, mid, open_edges=(0,), mi_front=wood)
    zb0, zb1 = tk, tk + db
    quad(bm, (xL + es, yf - 0.006, zb0), (xR - es, yf - 0.006, zb0), (xR - es, yf - 0.006, zb1 - st), (xL + es, yf - 0.006, zb1 - st), inner, (0, 1, 0))
    groups = [(x0, x1) for _, x0, x1 in _drawer_groups(mods, rhythm, dt)]
    for gi, (x0, x1) in enumerate(groups):
        if niches and (gi == 0 or gi == len(groups) - 1):
            _niche(bm, x0, x1, yf, zb0, zb1, st, wood, nglow)
            continue
        quad(bm, (x0 + 0.004, yf + 0.004, zb0 + 0.012), (x1 - 0.004, yf + 0.004, zb0 + 0.012), (x1 - 0.004, yf + 0.004, zb1 - st - 0.008),
             (x0 + 0.004, yf + 0.004, zb1 - st - 0.008), wood, (0, 1, 0))
        pxc, pzc, pw = (x0 + x1) / 2, (zb0 + zb1 - st) / 2 + 0.01, min(0.09, (x1 - x0) * 0.3)
        quad(bm, (pxc - pw / 2, yf + 0.008, pzc - 0.006), (pxc + pw / 2, yf + 0.008, pzc - 0.006), (pxc + pw / 2, yf + 0.008, pzc + 0.006),
             (pxc - pw / 2, yf + 0.008, pzc + 0.006), dark, (0, 1, 0))
    yk = yf - 0.06
    quad(bm, (xL + es, yk, 0.0), (xR - es, yk, 0.0), (xR - es, yk, tk), (xL + es, yk, tk), inner, (0, 1, 0))
    quad(bm, (xL + es, yf - 0.045, tk), (xR - es, yf - 0.045, tk), (xR - es, yf - 0.006, tk), (xL + es, yf - 0.006, tk), glow, (0, 0, -1))


def _carcass_lod2(bm, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, cpm, dt, cw_clear, z_c0, z_c1, nrows, pitch, st,
                  tk, db, ch, fr, wood, inner, dark, glow, mid, cap, nglow=None):
    # cornice box (front, top, bottom) + frieze
    prism(bm, [(yb, h - ch), (d / 2, h - ch), (d / 2, h), (yb, h)], 'x', -w / 2, w / 2, cap, open_edges=(3,))
    quad(bm, (xL, yf, z_c1), (xR, yf, z_c1), (xR, yf, h - ch), (xL, yf, h - ch), wood, (0, 1, 0))
    for sx in (-1, 1):
        x_out, x_in = (xL, xL + es) if sx < 0 else (xR, xR - es)
        quad(bm, (x_out, yb, 0), (x_out, yf, 0), (x_out, yf, h - ch), (x_out, yb, h - ch), wood, (sx, 0, 0))
        quad(bm, (min(x_out, x_in), yf, 0), (max(x_out, x_in), yf, 0), (max(x_out, x_in), yf, h - ch), (min(x_out, x_in), yf, h - ch), wood, (0, 1, 0))
    for i in range(len(mods) - 1):
        a = mods[i][1]
        quad(bm, (a, yf, tk), (a + ms, yf, tk), (a + ms, yf, z_c1), (a, yf, z_c1), wood, (0, 1, 0))
    quad(bm, (xL + es, yb + 0.012, z_c0), (xR - es, yb + 0.012, z_c0), (xR - es, yb + 0.012, z_c1), (xL + es, yb + 0.012, z_c1), inner, (0, 1, 0))
    for ri in range(nrows + 1):
        zt = z_c0 + ri * pitch if ri < nrows else z_c1 + st
        quad(bm, (xL + es, yfi, zt - st), (xR - es, yfi, zt - st), (xR - es, yfi, zt), (xL + es, yfi, zt), wood, (0, 1, 0))
        quad(bm, (xL + es, yfi, zt), (xR - es, yfi, zt), (xR - es, yb + 0.012, zt), (xL + es, yb + 0.012, zt), mid, (0, 0, 1))
    for a, b in mods:
        for ci in range(1, cpm):
            x0 = a + ci * cw_clear + (ci - 1) * dt
            quad(bm, (x0, yfi, z_c0), (x0 + dt, yfi, z_c0), (x0 + dt, yfi, z_c1), (x0, yfi, z_c1), wood, (0, 1, 0))
    quad(bm, (xL + es, yf, tk), (xR - es, yf, tk), (xR - es, yf, tk + db), (xL + es, yf, tk + db), wood, (0, 1, 0))
    quad(bm, (xL + es, yf - 0.06, 0), (xR - es, yf - 0.06, 0), (xR - es, yf - 0.06, tk), (xL + es, yf - 0.06, tk), inner, (0, 1, 0))
    quad(bm, (xL + es, yf - 0.045, tk), (xR - es, yf - 0.045, tk), (xR - es, yf, tk), (xL + es, yf, tk), glow, (0, 0.3, -1))
    if nglow is not None:            # lit end niches (identifying feature at every LOD)
        for x0_, x1_ in ((xL + es, xL + es + 0.3), (xR - es - 0.3, xR - es)):
            quad(bm, (x0_, yf + 0.003, tk + 0.012), (x1_, yf + 0.003, tk + 0.012), (x1_, yf + 0.003, tk + db - 0.03), (x0_, yf + 0.003, tk + db - 0.03), nglow, (0, 1, 0))


def _carcass_lod3(bm, w, h, d, yb, yf, yfi, xL, xR, es, ms, mods, z_c0, z_c1, nrows, pitch, st, tk, db, ch, wood, inner, glow, cap, nglow=None,
                  cpm=1, dt=0.04, cw_clear=0.3, budget=80, nrows_s=8):
    quad(bm, (-w / 2, d / 2, h - ch), (w / 2, d / 2, h - ch), (w / 2, d / 2, h), (-w / 2, d / 2, h), cap, (0, 1, 0))
    for sx in (-1, 1):
        x_out, x_in = (xL, xL + es) if sx < 0 else (xR, xR - es)
        quad(bm, (min(x_out, x_in), yf, 0), (max(x_out, x_in), yf, 0), (max(x_out, x_in), yf, h - ch), (min(x_out, x_in), yf, h - ch), wood, (0, 1, 0))
    quad(bm, (xL + es, yb + 0.012, z_c0), (xR - es, yb + 0.012, z_c0), (xR - es, yb + 0.012, z_c1), (xL + es, yb + 0.012, z_c1), inner, (0, 1, 0))
    for ri in range(nrows + 1):
        zt = z_c0 + ri * pitch if ri < nrows else z_c1 + st
        quad(bm, (xL + es, yfi, zt - st), (xR - es, yfi, zt - st), (xR - es, yfi, zt), (xL + es, yfi, zt), wood, (0, 1, 0))
    # vertical bars: module stiles, plus every other divider if there's room
    for i in range(len(mods) - 1):
        a = mods[i][1]
        quad(bm, (a, yf, z_c0 - st), (a + ms, yf, z_c0 - st), (a + ms, yf, z_c1), (a, yf, z_c1), wood, (0, 1, 0))
    quad(bm, (xL + es, yf, tk), (xR - es, yf, tk), (xR - es, yf, tk + db), (xL + es, yf, tk + db), wood, (0, 1, 0))
    quad(bm, (xL + es, yf - 0.045, tk), (xR - es, yf - 0.045, tk), (xR - es, yf, tk), (xL + es, yf, tk), glow, (0, 0.3, -1))
    if nglow is not None:            # lit end niches (identifying feature at every LOD)
        for x0_, x1_ in ((xL + es, xL + es + 0.3), (xR - es - 0.3, xR - es)):
            quad(bm, (x0_, yf + 0.003, tk + 0.012), (x1_, yf + 0.003, tk + 0.012), (x1_, yf + 0.003, tk + db - 0.03), (x0_, yf + 0.003, tk + db - 0.03), nglow, (0, 1, 0))
