"""Shoulder massage spout niche (b3_falls, 3 instances): an arched niche in a black wet rock wall, a bronze
spout high in the niche back, a contoured stone lounger seat under the stream.

Concepts: refs/gen/sheet-mod-water.png #6 (front + side section; 1 m bar = 100 px at sheet scale: rock
surround ~2.3 m wide x ~2.9 m tall drawn, niche opening ~1.2 m, spout ~2.0 m above the seat base, the
reclined seat ~1.0 m long, backrest top ~0.9 m, seat pan ~0.4 m, the nozzle a short wide bronze tube angled
down-forward on a wall flange; the stream lands on the backrest at shoulder height), lookbook/img/19-thunder-
curtain.jpg (right side: a row of round-arched niches ~1.4 m wide x 2.4 m in the cliff, a focused stream on
each seated bather's shoulders, warm light high in each niche). The drawn rock (2.3 m) is wider than the row
(1 x 1.2 x 2.6 m, niche w 1-1.4): I built to the row's niche range + a 0.26-0.30 m rock jamb each side.

Targets (default, seed 1): overall 1.62-1.98 x 1.15-1.2 x 2.55-2.7 m
  niche opening w 1.0-1.4 (default 1.05-1.25), h 2.0-2.6 (default 2.15-2.4), round or 4-centred arch,
  depth 0.42-0.5 into a 0.55-0.6 m thick rock face; jambs 0.26-0.30; crag top +0.15-0.35 over the arch
  spout: mouth height 1.8-3.4 clamped to niche h - 0.2 (default 1.95-2.15); flange r 0.10, pipe r 0.045,
         reach 0.24 then a 40-50 deg elbow to a flared nozzle r 0.065
  seat: lounger 0.62-0.86 wide, 1.0 long, backrest top 0.9-0.98, pan 0.38-0.42 with a 0.03 m dish, knee
        roll 0.47, rounded ends; base on the pool floor (z = 0); water kz_water_level 0.72
Parameters: niche_w 1-1.4, niche_h 2-2.6, spout_h 1.8-3.4, seat ('lounger' | 'upright' contour),
  arch ('round' | 'pointed'), water.
Seeds (2 variants in the row; three on the sheet): seed 1 round arch + lounger, seed 2 pointed arch +
  upright seat (steeper back, shorter pan), seed 3 round arch, wide niche, lounger; plus niche w/h, jamb
  rock layout and sizes, crag top profile, seat width.
Materials (slots by part): m_rock basalt_wet 0.5 (surround), m_niche basalt_wet 0.95 polish -0.05 (inside
  the niche, water-polished), m_seat basalt_wet 0.6 rough +0.05 (seat, a touch duller than the niche), m_bronze bronze smooth (spout).
Stream: not built (fx_falls_sheet narrow). Custom props: kz_spout_mouth [x, y, z], kz_spout_dir,
  kz_spills (preview lip + landing z), kz_stream_target, kz_water_level, kz_lights (warm niche downlight +
  teal pool uplight), kz_anim.
LODs from one layout: LOD1 halves the face grid and seat stations; LOD2 9 x 11 face grid, 3-station seat,
  6-sided straight-elbow spout; LOD3 5 x 6 front grid (no returns) that still shows the arch, block seat, 4-sided spout.
Pivot: bbox centre x/y, z = 0 at the pool floor; the back (y min) goes against the wall; front +Y.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'massage_spout'
FEATURES = ['arched black rock niche', 'bronze spout high in the niche', 'contoured stone seat under the stream']
STYLES = [('round', 'lounger', 1.1), ('pointed', 'upright', 1.05), ('round', 'lounger', 1.3)]
PROXY_SHEET = dict(w=1.9, d=1.2, h=2.75)     # proposed (row proxy 1.0 x 1.2 x 2.6 has no room for jambs)


def _layout(seed, niche_w=None, niche_h=None, spout_h=None, seat=None, arch=None, water=None):
    st = C.cycle(seed, STYLES)
    g = C.rng(seed, 'niche')
    L = {}
    L['arch'] = arch or st[0]
    L['seat'] = seat or st[1]
    L['nw'] = niche_w or min(1.4, st[2] * g.uniform(0.95, 1.05))
    L['nh'] = niche_h or g.uniform(2.15, 2.4)
    L['jamb'] = g.uniform(0.26, 0.30)
    L['T'] = g.uniform(0.55, 0.6)
    L['dep'] = g.uniform(0.42, 0.5)
    L['crag'] = g.uniform(0.15, 0.3)
    L['noff'] = Vector((g.uniform(0, 60), g.uniform(0, 60), g.uniform(0, 60)))
    L['sh'] = min(spout_h or g.uniform(1.95, 2.15), L['nh'] - 0.2)
    L['water'] = 0.72 if water is None else water
    gs = C.rng(seed, 'seat')
    L['sw'] = min(L['nw'] - 0.2, gs.uniform(0.62, 0.86))
    L['back_top'] = gs.uniform(0.9, 0.98)
    gr = C.rng(seed, 'jambrocks')
    W = L['nw'] + 2 * L['jamb']
    rocks = []
    for i in range(gr.randint(4, 6)):
        side = (-1, 1)[i % 2]
        top = i >= 4 or gr.random() < 0.35
        if top:
            x = gr.uniform(-W * 0.35, W * 0.35); z = L['nh'] + gr.uniform(0.0, 0.15)
        else:
            x = side * (L['nw'] / 2 + L['jamb'] * gr.uniform(0.45, 0.7)); z = gr.uniform(0.25, L['nh'] * 0.8)
        s = gr.uniform(0.16, 0.26)
        rocks.append(dict(c=(x, L['T'] - s * 0.35, z), s=(s, s * gr.uniform(0.7, 0.9), s * gr.uniform(0.8, 1.15)),
                          rot=gr.uniform(0, 3), rs=gr.randint(0, 10 ** 6)))
    rocks.sort(key=lambda d: -d['s'][0])
    L['rocks'] = rocks
    return L


def _sd_arch(L, x, z):
    """signed distance inside the niche opening (positive inside)"""
    hw = L['nw'] / 2
    spring = L['nh'] - hw * (1.0 if L['arch'] == 'round' else 1.25)
    if z <= spring:
        return min(hw - abs(x), 9.0)
    if L['arch'] == 'round':
        return hw - math.hypot(x, z - spring)
    # pointed (two-centred) arch: centres offset sideways by 0.3 hw, radius 1.3 hw
    cxo = 0.3 * hw if x < 0 else -0.3 * hw
    return 1.3 * hw - math.hypot(x - cxo, (z - spring) * 1.0)


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _seat_profile(L, lod):
    """closed (y, z) profile of the seat, from the back foot round the top to the front foot"""
    bt = L['back_top']
    if L['seat'] == 'lounger':
        top = [(0.02, bt - 0.04), (0.08, bt), (0.16, bt - 0.03), (0.26, 0.7), (0.38, 0.48), (0.5, 0.40), (0.64, 0.40),
               (0.76, 0.44), (0.85, 0.47), (0.93, 0.45), (0.99, 0.38)]
    else:
        top = [(0.02, bt - 0.03), (0.08, bt + 0.02), (0.15, bt - 0.02), (0.2, 0.75), (0.26, 0.5), (0.34, 0.43),
               (0.52, 0.42), (0.64, 0.46), (0.72, 0.47), (0.79, 0.44), (0.84, 0.37)]
    foot_y = top[-1][0] + 0.02
    prof = [(0.0, 0.0), (0.0, bt - 0.12)] + top + [(foot_y, 0.2), (foot_y + 0.01, 0.0)]
    if lod >= 2:
        keep = [0, 1, 3, 6, 8, 11, len(prof) - 2, len(prof) - 1] if lod == 2 else [0, 3, 8, 11, len(prof) - 1]
        prof = [prof[i] for i in keep if i < len(prof)]
    return prof, 2, len(top)


def build(lod, seed, niche_w=None, niche_h=None, spout_h=None, seat=None, arch=None, water=None):
    L = _layout(seed, niche_w, niche_h, spout_h, seat, arch, water)
    mb = genlib.MeshBuilder()
    m_rock = mb.slot('basalt_wet', wetness=0.5)
    m_niche = mb.slot('basalt_wet', wetness=0.95, roughness_offset=-0.05)
    m_seat = mb.slot('basalt_wet', wetness=0.6, roughness_offset=0.05)
    m_bronze = mb.slot('bronze', variant='smooth')
    bm = mb.bm
    nw, nh, jamb, T, dep = L['nw'], L['nh'], L['jamb'], L['T'], L['dep']
    W = nw + 2 * jamb
    Htop = nh + L['crag']
    off = L['noff']

    # ------------------------------------------------ rock face with the niche: a (x, z) grid displaced in y
    NX, NZ = C.lod_pick(lod, (30, 44), (16, 24), (9, 11), (5, 6))
    amp = C.lod_pick(lod, 0.045, 0.04, 0.03, 0.0)

    def ztop(x):
        u = x / (W / 2)
        return Htop - 0.18 * u * u * Htop / 2.6 + L['crag'] * 0.5 * noise.noise(Vector((x * 1.6, 0.3, 0)) + off)

    def face(x, zf):
        zt = ztop(x)
        z = zf * zt
        sd = _sd_arch(L, x, z)
        m = _smooth(-0.03, 0.14, sd)
        p = Vector((x * 2.2, z * 2.2, 0.0)) + off
        crag = amp * (noise.noise(p) + 0.5 * noise.noise(p * 2.3)) * (1 - 0.7 * m)
        bowl = dep * (0.82 + 0.18 * max(0.0, 1 - (2 * x / nw) ** 2))
        y = T + crag - m * bowl
        # roll the crown back over the top edge
        if zf > 0.92:
            y -= (zf - 0.92) / 0.08 * T * 0.35
        return Vector((x, y, z)), m
    xs = [-W / 2 + W * i / (NX - 1) for i in range(NX)]
    zf_ = [k / (NZ - 1) for k in range(NZ)]
    grid = [[face(x, zf) for x in xs] for zf in zf_]
    V = [[bm.verts.new(p) for p, _ in row] for row in grid]
    for k in range(NZ - 1):
        for i in range(NX - 1):
            f = bm.faces.new((V[k][i], V[k][i + 1], V[k + 1][i + 1], V[k + 1][i]))
            mm = (grid[k][i][1] + grid[k][i + 1][1] + grid[k + 1][i][1] + grid[k + 1][i + 1][1]) / 4
            f.material_index = m_niche if mm > 0.5 else m_rock
    # side returns and the top back to the wall plane y = 0
    for col, sgn in (((0, -1), (NX - 1, 1)) if lod < 3 else ()):
        back = [bm.verts.new((V[k][col].co.x + sgn * 0.02, 0.0, V[k][col].co.z)) for k in range(NZ)]
        for k in range(NZ - 1):
            a, b, c, d = V[k][col], V[k + 1][col], back[k + 1], back[k]
            f = bm.faces.new((a, b, c, d) if sgn < 0 else (d, c, b, a)); f.material_index = m_rock
        if col == 0:
            back_l = back
        else:
            back_r = back
    topb = [bm.verts.new((V[-1][i].co.x, 0.0, V[-1][i].co.z - 0.05)) for i in range(NX)]
    if lod < 3:
        topb[0] = back_l[-1]; topb[-1] = back_r[-1]
    for i in range(NX - 1):
        f = bm.faces.new((V[-1][i], topb[i], topb[i + 1], V[-1][i + 1])); f.material_index = m_rock

    # ------------------------------------------------ jamb / crown rocks (faceted, seated into the face)
    keep = C.lod_pick(lod, len(L['rocks']), len(L['rocks']), 2, 0)
    for rk in L['rocks'][:keep]:
        C.hull_rock(mb, rk['c'], rk['s'], m_rock, genlib.rng(rk['rs'], 'r'), npts=C.lod_pick(lod, 14, 9, 6), rot=rk['rot'])

    # ------------------------------------------------ contoured seat (loft across x with rounded ends)
    prof, t0, nt = _seat_profile(L, lod)
    sw = L['sw']
    y0 = T - dep + 0.04
    NS = C.lod_pick(lod, 14, 7, 3, 1)
    cy_ = sum(p[0] for p in prof) / len(prof); cz_ = sum(p[1] for p in prof) / len(prof) * 0.5
    rows = []
    for s in range(NS + 1):
        u = -1 + 2 * s / NS
        x = u * sw / 2
        endk = 0.0 if lod >= 2 else max(0.0, (abs(u) - 0.8) / 0.2) ** 2
        dish = 0.03 * (1 - u * u) if lod < 2 else 0.0
        row = []
        for j, (py, pz) in enumerate(prof):
            topface = 1 <= j < len(prof) - 2 and pz > 0.25
            yy = py + (cy_ - py) * 0.12 * endk
            zz = pz - (dish if topface else 0.0) - (0.05 * endk if topface else 0.0)
            row.append(bm.verts.new((x * (1 - 0.04 * endk), y0 + yy, max(0.0, zz))))
        rows.append(row)
    m = len(prof)
    for s in range(NS):
        for j in range(m):
            a, b = rows[s][j], rows[s][(j + 1) % m]
            c, d = rows[s + 1][(j + 1) % m], rows[s + 1][j]
            f = bm.faces.new((a, b, c, d)); f.material_index = m_seat
    for row, flip in ((rows[0], True), (rows[-1], False)):
        f = bm.faces.new(row[::-1] if flip else row); f.material_index = m_seat

    # ------------------------------------------------ bronze spout: flange, pipe, elbow, flared nozzle
    sh = L['sh']
    yb = T - dep * (0.82 + 0.18) + 0.01           # niche back at x = 0
    sides = C.lod_pick(lod, 16, 10, 6, 4)
    if lod < 3:
        C.tube(mb, [(0, yb - 0.03, sh), (0, yb + 0.02, sh), (0, yb + 0.04, sh)], [0.1, 0.1, 0.075], m_bronze,
               sides=sides, cap0=True, cap1=True)
        ang = math.radians(45)
        bend = C.lod_pick(lod, 5, 3, 1)
        pts = [Vector((0, yb + 0.02, sh)), Vector((0, yb + 0.2, sh))]
        rc = 0.09
        for k in range(1, bend + 1):
            a = ang * k / bend
            pts.append(Vector((0, yb + 0.2 + rc * math.sin(a), sh - rc * (1 - math.cos(a)))))
        d = Vector((0, math.cos(ang), -math.sin(ang)))
        pts += [pts[-1] + d * 0.06, pts[-1] + d * 0.1, pts[-1] + d * 0.105]
        radii = [0.045] * (len(pts) - 3) + [0.05, 0.066, 0.055]
        C.tube(mb, pts, radii, m_bronze, sides=sides, cap0=False, cap1=True)
        if lod == 0:
            C.tube(mb, [Vector((0, yb + 0.11, sh)), Vector((0, yb + 0.14, sh))], [0.056, 0.056], m_bronze, sides=sides,
                   cap0=True, cap1=True)
        mouth = pts[-1]
    else:
        C.stick(mb, (0, yb - 0.02, sh), (0, yb + 0.3, sh - 0.08), 0.07, 0.06, m_bronze, segs=4)
        mouth = Vector((0, yb + 0.3, sh - 0.08)); d = Vector((0, 0.7, -0.7))

    # ------------------------------------------------ object + data
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=40)
    sh_off = Vector((dx, dy, dz))
    mo = mouth + sh_off
    land = Vector((0, y0 + 0.2, L['back_top'] + 0.08)) + sh_off
    C.water_props(o, L['water'] + dz)
    lip = [[round(mo.x + k * 0.035, 4), round(mo.y, 4), round(mo.z - 0.02, 4)] for k in (-1, 0, 1)]
    C.set_json_props(o, kz_spout_mouth=[round(c, 4) for c in mo], kz_spout_dir=[0.0, round(d.y, 3), round(d.z, 3)],
                     kz_stream_target=[round(c, 4) for c in land],
                     kz_spills=[dict(lip=lip, to=round(land.z, 3))],
                     kz_lights=[C.light_entry((dx, T - dep * 0.5 + dy, nh - 0.12), color_k=2700, watts=20, role='niche downlight'),
                                C.light_entry((dx, y0 + 0.9 + dy, 0.1), color_k=7500, watts=40, role='pool uplight',
                                              color=(0.35, 0.95, 0.85))],
                     kz_anim=dict(type='sim-driven', fx='fx_falls_sheet', mode='narrow', source='kz_spout_mouth'),
                     kz_params=dict(niche_w=round(nw, 3), niche_h=round(nh, 3), spout_h=round(sh, 3), arch=L['arch'],
                                    seat=L['seat']))
    return o
