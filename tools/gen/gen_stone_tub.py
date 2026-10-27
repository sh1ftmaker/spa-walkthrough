"""Natural basalt tub (stone_tub): a rough basalt block sunk into the floor with a smooth carved inner face,
glowing teal water, fed by a bamboo spout. Suite hero (suite_1a..4c) and the b1_grotto cold-rinse tubs.

Concept: refs/gen/sheet-mod-water.png #5 (label: length 2.6 m; 1 m bar = 102 px: outer 2.6 x ~2.0 m, rim top
~0.55-0.6 m over its base, rim wall 0.22-0.30 m thick, craggy faceted dark exterior with wet highlights, a
smooth pale-grey carved inner face with rounded bottom corners, water ~4 cm under the rim, a bamboo post
~1.25 m tall at one end with a horizontal spout arm reaching ~0.4 m over the water, a small stone footing),
lookbook/img/21-private-suite.jpg (tub sunk flush into the wet stone terrace, teal glow from below, wooden
bucket and towel on the rim: those are separate props), lookbook/img/32-suites-cliff.jpg.
Targets: w 2.6 x d 2.0 x h 0.6 (proxy, embed 0.4), rim 0.22-0.30, inner depth 0.50 (row 0.5-0.7), water 0.04
under the rim low point, overflow lip dips 0.03 over ~0.35 m, spout post 1.0-1.1 m above the floor.

Parameters (build(lod, seed, ...)):
  w 1.6-3.4, d 1.4-3.2   outer plan size (default proxy 2.6 x 2.0; seeds vary +-8 %)
  depth   0.5-0.7         water depth (default 0.5; the block grows: h = depth + 0.04 + 0.06 floor)
  rim     'raised' | 'flush'  raised: rim stands 0.2 m above the floor (grade = h - 0.2); flush: rim at grade
  overflow 'front' | 'back' | 'left' | 'right' | 'none'   lip side (default by seed)
  spout   True/False      bamboo spout (post + arm) at the end opposite the overflow (False: use kakehi_spout)
  plan    'oval' | 'rounded' | 'lobed' | 'boulder'  (default C.cycle(seed)): superellipse exponent / lobes
Seeds change: plan shape (oval / rounded-rect / lobed / boulder-outlined), aspect and size +-8 %, rim
thickness 0.22-0.30, raised / flush, overflow side, spout end, facet pattern and crag depth.
Custom props: kz_water_level, kz_water_outline, kz_grade_z, kz_grade_outline, kz_overflow_dir, kz_spout_mouth,
kz_lights (teal uplight under water), kz_params. Pivot: plan centre, block base z = 0.
Materials: exterior basalt_wet (wetness 0.5, tinted near-black), rim top basalt_wet (wetness 0.9), inner face
basalt_wet polished + lighter (the carved smooth face), floor glow caustics_decal, spout bamboo (+ rope
lashing), footing basalt_dry. water_still is the runtime surface (not built).
LODs (same layout): LOD1 half the angles and rings, no lashing; LOD2 24 angles, 6 rings, 6-sided bamboo; LOD3
10 angles, rim + inner wall + floor, a 4-sided post and arm.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_pool_shell as K

ASSET = 'stone_tub'
FEATURES = ['rough basalt tub block sunk into the floor', 'smooth carved inner face, glowing teal water',
            'bamboo spout feeding it']
PLANS = ['rounded', 'oval', 'lobed', 'boulder']
SIDES = {'front': (0, 1), 'back': (0, -1), 'left': (-1, 0), 'right': (1, 0)}
TINT = (0.55, 0.56, 0.62)


def _se(t, a, b, e):
    c, s = math.cos(t), math.sin(t)
    return a * math.copysign(abs(c) ** (2 / e), c), b * math.copysign(abs(s) ** (2 / e), s)


def build(lod, seed, w=None, d=None, depth=None, rim=None, overflow=None, spout=True, plan=None):
    plan = plan or C.cycle(seed, PLANS)
    g = C.rng(seed, 'layout')
    k = g.uniform(0.9, 0.97)
    W = w if w is not None else 2.6 * k * (0.97 if plan == 'boulder' else 1.0)
    Dd = d if d is not None else 2.0 * g.uniform(0.9, 1.0) * (0.97 if plan == 'boulder' else 1.0)
    dep = depth if depth is not None else 0.5
    rim = rim or C.cycle(seed, ['raised', 'flush'])
    t_rim = g.uniform(0.22, 0.30)
    e_out = dict(oval=2.2, rounded=3.4, lobed=2.8, boulder=2.6)[plan]
    e_in = dict(oval=2.1, rounded=3.0, lobed=2.4, boulder=2.2)[plan]
    wob = dict(oval=0.015, rounded=0.012, lobed=0.06, boulder=0.09)[plan]
    ro = C.rng(seed, 'outline')
    ph = [ro.uniform(0, 2 * math.pi) for _ in range(4)]
    off = Vector((ro.uniform(0, 60), ro.uniform(0, 60), ro.uniform(0, 60)))
    nfac = ro.randint(13, 19)
    fac = [ro.uniform(-1, 1) for _ in range(nfac)]
    crag = g.uniform(0.025, 0.04)
    floor_t = 0.06
    H = floor_t + dep + 0.04                           # block base -> rim top
    zbed = floor_t
    grade = H - 0.2 if rim == 'raised' else H - 0.015
    ov = overflow or C.pick(seed, 'overflow', ['front', 'right', 'left', 'front'])
    ov_ang = math.atan2(*SIDES[ov][::-1]) if ov != 'none' else None
    sp_dir = (-SIDES[ov][0], -SIDES[ov][1]) if ov != 'none' else (0, -1)
    if abs(sp_dir[0]) < 0.5 and W > Dd * 1.1 and ov in ('front', 'back'):
        sp_dir = (C.pick(seed, 'spside', [-1, 1]), 0)        # long tubs: spout at an end
    sp_ang = math.atan2(sp_dir[1], sp_dir[0])

    def lobe(t):
        return 1 + wob * (math.sin(2 * t + ph[0]) * 0.6 + math.sin(3 * t + ph[1]) * 0.5 + math.sin(5 * t + ph[2]) * 0.3)

    def outer(t, z):
        x, y = _se(t, W / 2, Dd / 2, e_out)
        L = lobe(t)
        i = int((t % (2 * math.pi)) / (2 * math.pi) * nfac)
        fz = z / H
        nv = noise.noise(Vector((math.cos(t) * 2.2, math.sin(t) * 2.2, fz * 1.8)) + off)
        dr = crag * (0.6 * fac[i] + nv) * (0.6 + 0.4 * fz)
        rr = math.hypot(x, y) or 1
        sc = L + dr / rr
        return x * sc, y * sc

    def inner(t, s=1.0):
        x, y = _se(t, W / 2 - t_rim, Dd / 2 - t_rim, e_in)
        L = 1 + 0.4 * wob * math.sin(2 * t + ph[0])
        return x * L * s, y * L * s

    def dip(t):
        if ov_ang is None:
            return 0.0
        dd = math.atan2(math.sin(t - ov_ang), math.cos(t - ov_ang))
        ang_w = 0.18 / max(0.5, math.hypot(*inner(t)))
        return 0.03 * math.exp(-(dd / ang_w) ** 2)

    N = C.lod_pick(lod, 96, 48, 24, 9)
    ts = [2 * math.pi * i / N for i in range(N)]
    mb = genlib.MeshBuilder()
    m_out = mb.slot('basalt_wet', wetness=0.5, tint=TINT)
    m_top = mb.slot('basalt_wet', wetness=0.9, tint=TINT)
    m_in = mb.slot('basalt_wet', wetness=0.95, roughness_offset=-0.12, tint=(1.15, 1.17, 1.22))
    m_glow = mb.slot('caustics_decal', emissive_level=0.9)
    m_bam = mb.slot('bamboo')
    m_node = mb.slot('bamboo', tint=(0.5, 0.45, 0.38), wear=0.5)
    m_rope = mb.slot('rope')
    m_foot = mb.slot('basalt_dry', tint=(0.5, 0.5, 0.55))

    # ring specs: (kind, param, z) bottom outside -> top -> inside -> floor
    zt = lambda t: H - dip(t)
    rough_top = lambda t, a: 0.008 * noise.noise(Vector((math.cos(t) * 4, math.sin(t) * 4, a)) + off)
    outer_z = C.lod_pick(lod, [0.0, 0.2, 0.42, 0.62, 0.82], [0.0, 0.4, 0.75], [0.0, 0.6], [0.0, 0.85])
    rings = []
    for fz in outer_z:
        z = fz * H
        rings.append(([(*outer(t, z), z) for t in ts], m_out))
    # shoulder + rim top (rough) -> inner edge round-over
    sh = C.lod_pick(lod, [(0.985, -0.03), (0.955, -0.008)], [(0.97, -0.015)], [(0.97, -0.01)], [])
    for s_, dz in sh:
        rings.append(([(*[c * s_ for c in outer(t, H)], zt(t) + dz + rough_top(t, s_)) for t in ts], m_out if dz < -0.02 else m_top))
    top_fr = C.lod_pick(lod, [0.45], [0.5], [], [])
    for fr in top_fr:            # mid rim-top ring, lumpy
        rings.append(([(*[(1 - fr) * a + fr * b for a, b in zip([c * 0.94 for c in outer(t, H)], inner(t, 1.04))],
                        zt(t) + rough_top(t, 3.0) * 1.5) for t in ts], m_top))
    inner_r = C.lod_pick(lod, [(1.05, 0.0), (1.01, -0.025), (1.0, -0.06), (0.99, -0.25), (0.97, None), (0.9, 'c1'), (0.8, 'c2'), (0.7, 'bed')],
                         [(1.04, 0.0), (1.0, -0.06), (0.98, None), (0.85, 'c1'), (0.72, 'bed')],
                         [(1.02, 0.0), (0.98, None), (0.75, 'bed')],
                         [(1.0, 0.0), (0.75, 'bed')])
    for j, (s_, zs) in enumerate(inner_r):
        if zs == 'bed':
            z = lambda t: zbed
        elif zs == 'c2':
            z = lambda t: zbed + 0.02
        elif zs == 'c1':
            z = lambda t: zbed + 0.07
        elif zs is None:
            z = lambda t: zbed + 0.16
        else:
            z = (lambda zz: (lambda t: zt(t) + zz))(zs)
        rings.append(([(*inner(t, s_), z(t)) for t in ts], m_top if j == 0 else m_in))
    loops = [[mb.bm.verts.new(p) for p in pts] for pts, _ in rings]
    for i in range(len(loops) - 1):
        K.strip(mb, loops[i], loops[i + 1], rings[i + 1][1])
    K.fill(mb, loops[-1], m_in)                      # inner floor
    if lod <= 2:
        K.fill(mb, loops[0], m_out, up=False)        # block base (closed solid)
        gl = [mb.bm.verts.new((*inner(t, 0.66), zbed + 0.006)) for t in ts]
        K.fill(mb, gl, m_glow)

    # ---------------------------------------------------------------- bamboo spout
    mouth = None
    if spout:
        ca, sa = math.cos(sp_ang), math.sin(sp_ang)
        # outer edge along the spout direction
        best = max(ts, key=lambda t: math.cos(t - sp_ang))
        ox, oy = outer(best, H)
        rout = math.hypot(ox, oy)
        px, py = ca * (rout + 0.1), sa * (rout + 0.1)
        z_foot = grade
        post_top = grade + 0.9
        arm_z = post_top - 0.12
        r_p, r_a = 0.048, 0.036
        ri = math.hypot(*inner(best))
        reach = rout + 0.1 - ri + 0.38                # arm runs from the post to ~0.38 m over the water
        mx, my = px - ca * reach, py - sa * reach
        mz = arm_z - 0.06
        mouth = (mx, my, mz)
        sides = C.lod_pick(lod, 10, 8, 6, 4)
        if lod <= 2:
            # post with node bulges
            nodes = [z_foot + f * (post_top - z_foot) for f in (0.28, 0.62)]
            zs = sorted(set([z_foot, post_top] + [n + dz for n in nodes for dz in ((-0.012, 0.0, 0.012) if lod == 0 else (0.0,))]))
            rad = [r_p * (1.12 if any(abs(z - n) < 0.001 for n in nodes) else 1.0) for z in zs]
            C.tube(mb, [(px, py, z) for z in zs], rad, m_bam, sides=sides, cap0=False, cap1=True)
            if lod == 0:
                for n in nodes:
                    C.lathe(mb, [(r_p * 1.13, n - 0.01), (r_p * 1.13, n + 0.01)], sides, m_node, base=(px, py, 0), closed=False)
            # arm: stub behind the post, through it, to the mouth
            na = C.lod_pick(lod, 7, 4, 2)
            pts = [(px + ca * 0.07 - ca * (reach + 0.07) * i / na, py + sa * 0.07 - sa * (reach + 0.07) * i / na,
                    arm_z - 0.06 * (i / na) ** 1.5) for i in range(na + 1)]
            C.tube(mb, pts, [r_a] * len(pts), m_bam, sides=sides, cap0=True, cap1=False)
            if lod == 0:
                C.rope_band(mb, (px, py, arm_z), (0, 0, 1), r_p + 0.004, 0.07, m_rope, N=6)
                C.hull_rock(mb, (px, py, z_foot), (0.16, 0.14, 0.09), m_foot, C.rng(seed, 'foot'), npts=12, ground=z_foot)
            elif lod == 1:
                C.hull_rock(mb, (px, py, z_foot), (0.16, 0.14, 0.09), m_foot, C.rng(seed, 'foot'), npts=8, ground=z_foot)
        else:
            mb.box((px, py, (z_foot + post_top) / 2), (0.09, 0.09, post_top - z_foot), m_bam)
            cx_, cy_ = (px + mx) / 2, (py + my) / 2
            mb.box((cx_, cy_, arm_z - 0.03), (reach, 0.07, 0.07), m_bam, rot=(0, 0, sp_ang))

    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=False)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    lvl = H - 0.03 - 0.04 + dz if ov_ang is not None else H - 0.04 + dz
    wl = [inner(2 * math.pi * i / 48, 1.02) for i in range(48)]
    C.water_props(o, lvl, outline_xy=wl, kz_grade_z=round(grade + dz, 4),
                  kz_grade_outline=[[round(c, 3) for c in outer(2 * math.pi * i / 48, grade)] for i in range(48)],
                  kz_overflow_dir=list(SIDES[ov]) if ov != 'none' else [0, 0])
    C.set_json_props(o, kz_lights=[C.light_entry((0, 0, zbed + 0.08 + dz), color_k=9000, watts=15, kind='point', underwater=True,
                                                 color=[0.3, 0.85, 0.8])],
                     kz_params=dict(plan=plan, w=round(W, 3), d=round(Dd, 3), depth=dep, rim=rim, overflow=ov, rim_t=round(t_rim, 3)))
    if mouth:
        C.set_json_props(o, kz_spout_mouth=[round(mouth[0], 3), round(mouth[1], 3), round(mouth[2] + dz, 3)])
    return o
