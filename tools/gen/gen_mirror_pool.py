"""Obsidian Mirror float pool basin (mirror_pool, b1_mirror): a black, dead-still salt pool ~24 m across with a
low wet rock rim and a 4-step entry. The surface is runtime fx_water_surface (planar reflection), not built.

Concept: lookbook/img/15-obsidian-mirror.jpg (black mirror water reflecting the glow-worm vault; a low rim of
dark wet flat-topped basalt masses 0.6-2 m long standing 0.05-0.3 m above the water; no visible bed),
lookbook/img/33-plan-b1-thermal.jpg (E-F 2-3: near-round pool, ~24 m across by the 20 m scale bar, wrapped by
a hinoki deck ring, entry from the lift side to the south), refs/gen/mat-obsidian.png (polished obsidian:
black glass with sharp highlights -> bed and inner wall).
Targets: water outline r ~11.3 m (lumpy circle, aspect 1.0-1.08), rim rock band to r 12 m (24 m overall),
rock tops 0-0.3 m above water (param rim_h, default 0.12-0.18), water 0.55 m deep (salt float pool; enough
for the 4 x 0.155 m entry steps), deck / walkway grade 0.07 m above water. Built height ~0.75 m, bed z = 0.
Proxy 24 x 24 x 0.4: the 4-step entry needs >= 0.55 m of water, so the basin is ~0.75 m tall: proposed
proxy h 0.8 (embed 0.62: everything below the deck).

Parameters (build(lod, seed, ...)):
  r        11-13 m   outer radius incl. the rim band (default 12)
  bed_z    bed level (default 0); depth 0.45-0.8 water depth (default 0.55)
  rim_h    0-0.3     rock tops above the water (default 0.12-0.18 by seed); 0 = a flush wet stone lip
  rocks    rim rock count (default ~ perimeter / 1.25 = 56-62)
  steps    entry step count (default 4), step_w 2.0-3.0 (default 2.4), entry azimuth deg (default 90 = +Y)
Seeds change: outline lobes / aspect, rock size mix, spacing, heights and lean, the flanking entry rocks.
Custom props: kz_water_level, kz_water_outline, kz_grade_z, kz_grade_outline, kz_planar_reflection,
kz_steps, kz_params. Materials: bed + inner wall obsidian, rim rocks + under-rim ledge basalt_wet, entry
steps basalt_wet (polished, wet). water_still (variant mirror) is the runtime surface.
LODs (same layout): LOD1 coarser loop, 6-sided 2-band rocks; LOD2 rocks become a low lumpy rim band that
follows the rock heights, steps as boxes; LOD3 one ring section with the entry block.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_pool_shell as K

ASSET = 'mirror_pool'
FEATURES = ['black dead-still pool basin (obsidian bed and wall)', 'low wet basalt rock rim', '4-step entry']
TINT = (0.55, 0.56, 0.62)


def build(lod, seed, r=None, bed_z=0.0, depth=None, rim_h=None, rocks=None, steps=4, step_w=None, entry=90.0):
    g = C.rng(seed, 'layout')
    Ro = r if r is not None else 12.0
    D = depth if depth is not None else 0.55
    rh = rim_h if rim_h is not None else g.uniform(0.12, 0.18)
    sw = step_w or 2.4
    band = 0.7
    Rw = Ro - band
    zw = bed_z + D
    grade = zw + 0.07
    W0 = K.fp_round(Rw, aspect=g.uniform(1.0, 1.08), r=C.rng(seed, 'outline'), wob=g.uniform(0.015, 0.03), n=240)
    k_fit = (Ro - 0.75) / max(max(abs(x), abs(y)) for x, y in W0)          # rocks reach ~0.75 m past the water edge
    W0 = [(x * k_fit, y * k_fit) for x, y in W0]
    # entry on the requested azimuth
    Pf = K.resample(W0, 480)
    cf = K.cumlen(Pf)
    ea = math.radians(entry)
    s_st = K.s_near(Pf, cf, (math.cos(ea) * Ro * 2, math.sin(ea) * Ro * 2))
    per = cf[-1]
    rr = C.rng(seed, 'rocks')
    n_target = rocks or int(per / 1.25)
    gap = per / n_target
    sizes = [(3, 0.45, 0.6), (4, 0.65, 0.85), (2, 0.9, 1.15)]
    ov = 1 - gap / (2 * 0.72)
    rk_all = K.rock_layout(Pf, cf, rr, sizes, (-0.1, 0.1), zw - 0.2,
                           lambda r_, q: zw + max(0.03, rh * q.uniform(0.55, 1.15) + (r_ - 0.45) * 0.06),
                           overlap=(ov - 0.06, ov + 0.06), skips=[(s_st, sw / 2 + 0.25)])
    # two big flanking rocks at the entry
    rf = C.rng(seed, 'flank')
    for sd in (-1, 1):
        rk_all.append(dict(s=(s_st + sd * (sw / 2 + 0.75)) % per, u=0.3, rx=0.85, ry=0.95, z0=zw - 0.2,
                           ztop=zw + max(0.08, rh * rf.uniform(1.15, 1.5)), salt=900 + sd, rot=rf.uniform(-0.2, 0.2)))
    rk_all.sort(key=lambda k: -(k['rx'] * k['ry'] * (k['ztop'] - k['z0'])))
    for k in rk_all:                               # flatter, longer rim masses than a boulder bank
        k['ry'] *= 1.25

    mb = genlib.MeshBuilder()
    m_bed = mb.slot('obsidian', roughness_offset=0.05)
    m_wall = mb.slot('obsidian', roughness_offset=0.15)
    m_ledge = mb.slot('basalt_wet', wetness=0.85, tint=TINT)
    m_rock = mb.slot('basalt_wet', wetness=0.8, tint=TINT)
    m_step = mb.slot('basalt_wet', wetness=0.95, roughness_offset=-0.05, tint=TINT)

    N = C.lod_pick(lod, 240, 100, 48, 14)
    P = K.resample(W0, N, start=s_st) if lod <= 1 else K.decimate(K.resample(W0, 4 * N, start=s_st), N)
    nrm = K.normals(P)
    cum = K.cumlen(P)
    sc = cum[-1] / per
    # re-express rock arc positions on this loop (start moved to the entry)
    s_shift = s_st
    rk = [dict(k, s=((k['s'] - s_shift) % per) * sc) for k in rk_all]
    s_e = 0.0
    env = K.rock_envelope(P, cum, rk, zw + 0.02)
    if lod <= 1:
        rings = [(band + 0.05, grade), (0.0, zw - 0.12), (-0.12, zw - 0.3), (-0.35, bed_z)]
        if lod == 1:
            rings = [rings[0], rings[1], rings[3]]
        K.shell(mb, P, rings, [m_ledge] + [m_wall] * (len(rings) - 2), bed_mi=m_bed, nrm=nrm)
        K.build_rocks(mb, P, cum, rk, m_rock, seed, lod, nside=(8, 6), bands=(3, 2), crag=0.1, top_inset=0.8)
    elif lod == 2:
        K.shell(mb, P, [(band + 0.05, grade), (0.75, env), (0.1, env), (-0.05, zw - 0.12), (-0.35, bed_z)],
                [m_rock, m_rock, m_rock, m_wall], bed_mi=m_bed, nrm=nrm)
    else:
        K.shell(mb, P, [(band + 0.05, grade), (0.3, env), (-0.35, bed_z)], [m_rock, m_wall], bed_mi=m_bed, nrm=nrm)
    tops = []
    if steps:
        if lod <= 2:
            tops = K.steps(mb, P, cum, s_e, steps, sw, grade, bed_z, 0.38, m_step, lod, embed=0.3, bevel=0.02)
            # landing slab through the rim band at deck level
            p, t, nn = K.at_s(P, cum, s_e)
            c = p + nn * (band / 2)
            size = (sw + 0.2, band + 0.4, 0.12)
            if lod <= 1:
                C.board(mb, (c.x, c.y, grade - 0.06), size, m_step, bevel=0.02, segs=C.lod_pick(lod, 2, 1), rot=(0, 0, math.atan2(t.y, t.x)))
            else:
                mb.box((c.x, c.y, grade - 0.06), size, m_step, rot=(0, 0, math.atan2(t.y, t.x)))
        else:
            p, t, nn = K.at_s(P, cum, s_e)
            c = p - nn * (steps * 0.38 / 2 - band / 2)
            mb.box((c.x, c.y, bed_z + (grade - bed_z) * 0.3), (sw, steps * 0.38 + band, (grade - bed_z) * 0.6), m_step,
                   rot=(0, 0, math.atan2(t.y, t.x)))

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    Wout = K.resample(W0, 120)
    C.water_props(o, zw + dz, outline_xy=[(x + dx, y + dy) for x, y in Wout], kz_grade_z=round(grade + dz, 4),
                  kz_grade_outline=[[round(x + dx, 3), round(y + dy, 3)] for x, y in K.offset(Wout, band + 0.05)],
                  kz_planar_reflection=True, kz_water_material='water_still:mirror')
    C.set_json_props(o, kz_steps=[[round(x + dx, 3), round(y + dy, 3), round(z + dz, 3)] for x, y, z in tops],
                     kz_params=dict(r=Ro, depth=D, rim_h=round(rh, 3), rocks=len(rk_all), steps=steps, step_w=sw, entry=entry))
    return o
