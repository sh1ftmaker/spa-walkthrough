"""Pool basin and rim generator (pool_shell): bed, inner wall and rim built from a pool's WATER FOOTPRINT.

Covers the ~20 ordinary pools (mist corridors, grotto soaking pools, glacier plunge, b3 falls / slide-foot /
wave pools, spring). The heroes with their own rim (mirror_pool, koi_pond, caldera_rim, cascade_pool, ...) are
separate generators. The water surface is NOT built (runtime fx_water_surface): this asset is bed + wall + rim,
and the level / outline are custom properties.

Concepts and measured targets
  lookbook 05 mist corridor   shallow corridor water ~0.25-0.3 m over a dark stone bed with teal glow, dry
                              cut-stone kerb along the corridor sides standing ~0.1-0.15 m above the water
                              (kerb ~0.35-0.45 m wide by the 0.3 m stepping stones beside it).
  lookbook 16 steam grotto    soaking pools ~0.7 m deep (seated bathers chest-deep), rims of dark wet flat-topped
                              basalt masses 0.3-0.6 m across, deck paving at rim level, low spill gaps.
  lookbook 17 glacier plunge  same rocky rim, stone entry steps (0.17-0.2 m risers, ~0.35 m treads, ~1.2 m wide).
  lookbook 13 / 19 b3 pools   round splash basin at the slide foot: cut coping ~0.4 m wide, ~0.9 m deep, the slide
                              tube entering through a slot in the rim at water level.
Target dims (default modules, ~10 m of rim each so totals compare with the per-10 m budget):
  kerb   corridor rect 3.6-4.4 x 1.0-1.5 m water, depth 0.26-0.32, kerb 0.30-0.60 w, 0.12 above water
  rock   free-form 3.0-3.6 x 2.2-2.8 m water, depth 0.65-0.80, rim rocks r 0.18-0.55, tops 0.05-0.38 above deck
  coping round r 1.45-1.7 m water (aspect 1-1.15), depth 0.85-0.95, coping 0.38-0.45 w, outlet slot 0.9-1.1 m
  tile   rect 3.2-3.8 x 1.6-2.0 m water, depth 0.55-0.65, cut coping + obsidian waterline tile band, 4 steps
Budget per 10 m of rim 2000/800/240/60 (kz_tris_per_10m is recorded so long pools can be checked per metre).

Parameters (build(lod, seed, ...)):
  footprint  [(x, y)] water outline (any winding; resampled). None -> a seeded preset `shape`, centred.
  shape      'rect' | 'round' | 'free' (preset footprint; default by style: kerb/tile rect, rock free, coping round)
  style      'kerb' | 'rock' | 'coping' | 'tile' (default C.cycle(seed): 1 kerb, 2 rock, 3 coping, 4 tile)
  bed_z      bed level (default 0)
  depth      water depth over the bed (style default above); water level = bed_z + depth
  rim_z      rim / kerb / coping top (default: water + 0.12 kerb, +0.10 coping/tile, deck +0.08 rock)
  kerb_w     0.30-0.60 rim width (kerb / coping / tile)
  steps      entry step count 0-5 (default kerb 0, rock 2, coping 3, tile 4); step_w 0.9-1.4
  outlet     True/False slot in the rim at water level (default True for coping) ; outlet_w 0.9-1.1
Seeds change the shape: footprint proportions (L, W, R, aspect, lobes and bites), kerb / coping block lengths
and width, rock size mix, overlap and heights, step count side and width, outlet position.
Custom props: kz_style, kz_water_level, kz_water_outline, kz_grade_z, kz_grade_outline (outer edge of the
rim where the place floor meets it), kz_outlet {pos, dir, width, z}, kz_steps [x, y, z_top], kz_rim_len,
kz_tris_per_10m, kz_params. Pivot: footprint centre, bed at z = 0 (presets only; a given footprint keeps its
coordinates). Materials: bed stepping_stone, wall basalt_wet, kerb paving (dry), coping stepping_stone, tile
obsidian, rocks basalt_wet, steps stepping_stone, outlet sill obsidian, bed glow caustics_decal (LOD0-2).
LODs: same layout; LOD1 coarser outline, 1-segment chamfers, 6-sided rocks; LOD2 rim as one continuous band
whose height follows the rock / kerb layout (outlet gap kept), steps as boxes; LOD3 one shell section.
"""
import json
import math

import genlib
import kzgeo_common as C
import kzgeo_pool_shell as K

ASSET = 'pool_shell'
FEATURES = ['pool bed and inner wall following the water footprint',
            'rim: dry cut-stone kerb | rocky wet basalt rim | cut coping | coping with waterline tile band',
            'entry steps and the slide-tube outlet slot where present']
STYLES = ['kerb', 'rock', 'coping', 'tile']
DEPTH = dict(kerb=(0.26, 0.32), rock=(0.65, 0.80), coping=(0.85, 0.95), tile=(0.55, 0.65))
TINT = (0.62, 0.62, 0.68)


def _preset(shape, r):
    if shape == 'rect':
        L, W = r.uniform(3.6, 4.4), r.uniform(1.0, 1.5)
        return K.fp_rect(L, W, r.uniform(0.25, 0.45))
    if shape == 'round':
        return K.fp_round(r.uniform(1.45, 1.7), aspect=r.uniform(1.0, 1.15), r=r, wob=0.0)
    R = r.uniform(1.2, 1.38)
    return K.fp_free(r, R, aspect=r.uniform(1.25, 1.6), bites=r.choice([1, 2]), rot=r.uniform(-0.3, 0.3))


def build(lod, seed, footprint=None, shape=None, style=None, bed_z=0.0, depth=None, rim_z=None, kerb_w=None,
          steps=None, step_w=None, outlet=None, outlet_w=None):
    style = style or C.cycle(seed, STYLES)
    shape = shape or dict(kerb='rect', rock='free', coping='round', tile='rect')[style]
    # ---------------------------------------------------------------- layout (independent of LOD)
    rf = C.rng(seed, 'footprint')
    centred = footprint is None
    W0 = K.ccw(footprint if footprint is not None else _preset(shape, rf))
    if shape == 'rect' and style == 'tile' and footprint is None:
        W0 = K.fp_rect(rf.uniform(3.2, 3.8), rf.uniform(1.6, 2.0), rf.uniform(0.2, 0.3))
    per = K.perimeter(W0)
    rd = C.rng(seed, 'depth')
    D = depth if depth is not None else rd.uniform(*DEPTH[style])
    zw = bed_z + D
    rk = C.rng(seed, 'kerb')
    kw = kerb_w if kerb_w is not None else dict(kerb=rk.uniform(0.32, 0.55), rock=0.75, coping=rk.uniform(0.38, 0.45),
                                                tile=rk.uniform(0.32, 0.4))[style]
    if style == 'rock':
        grade = zw + 0.08
        top = rim_z if rim_z is not None else grade
    else:
        top = rim_z if rim_z is not None else zw + (0.12 if style == 'kerb' else 0.10)
        grade = top - (0.05 if style == 'kerb' else 0.0)
    rs = C.rng(seed, 'steps')
    nst = steps if steps is not None else dict(kerb=0, rock=2, coping=3, tile=4)[style]
    sw = step_w or rs.uniform(0.9, 1.3)
    has_out = outlet if outlet is not None else style == 'coping'
    ow = outlet_w or rs.uniform(0.9, 1.1)
    # positions along the loop (arc length on the fine loop)
    Nf = max(64, int(per / 0.05))
    Pf = K.resample(W0, Nf)
    cf = K.cumlen(Pf)
    bb = (min(p[0] for p in Pf), max(p[0] for p in Pf), min(p[1] for p in Pf), max(p[1] for p in Pf))
    cx, cy = (bb[0] + bb[1]) / 2, (bb[2] + bb[3]) / 2
    side = rs.choice([-1, 1])
    s_out = K.s_near(Pf, cf, (cx + side * (bb[1] - bb[0]) * 0.6, cy)) if has_out else None
    if nst:
        if shape == 'round' or (has_out and style != 'kerb'):
            tgt = (cx - side * (bb[1] - bb[0]) * 0.6, cy + rs.uniform(-0.3, 0.3))
        else:
            tgt = (cx + rs.uniform(0.15, 0.3) * (bb[1] - bb[0]) * side, bb[3] + 1.0)
        s_st = K.s_near(Pf, cf, tgt)
    else:
        s_st = None
    skips = []
    if s_out is not None:
        skips.append((s_out, ow / 2))
    if s_st is not None:
        skips.append((s_st, sw / 2 + 0.05))
    # blocks / rocks layout once per seed
    rb = C.rng(seed, 'blocks')
    spans = K.block_spans(cf, rb, *(dict(kerb=(0.55, 0.95), coping=(0.6, 1.0), tile=(0.5, 0.7)).get(style, (0.6, 1.0))),
                          gap=0.008, skips=skips) if style != 'rock' else []
    rr = C.rng(seed, 'rocks')
    rocks = []
    if style == 'rock':
        rocks = K.rock_layout(Pf, cf, rr, [(3, 0.18, 0.28), (4, 0.3, 0.42), (2, 0.45, 0.55)], (0.05, 0.22), zw - 0.3,
                              lambda r_, g: grade + 0.05 + (r_ - 0.18) * 0.55 + g.uniform(0.0, 0.12),
                              skips=skips)
    # ---------------------------------------------------------------- slots (one place)
    mb = genlib.MeshBuilder()
    m_bed = mb.slot('stepping_stone', wear=0.25, tint=TINT)
    m_wall = mb.slot('basalt_wet', wetness=0.9, tint=TINT)
    m_kerb = mb.slot('paving', wetness=0.3, wear=0.25, tint=(0.42, 0.42, 0.46))
    m_cope = mb.slot('stepping_stone', wear=0.35, wetness=0.6)
    m_tile = mb.slot('obsidian', roughness_offset=0.05)
    m_rock = mb.slot('basalt_wet', wetness=0.75, tint=TINT)
    m_step = mb.slot('stepping_stone', wear=0.3)
    m_sill = mb.slot('obsidian')
    m_glow = mb.slot('caustics_decal', emissive_level=0.6)

    # ---------------------------------------------------------------- outline at this LOD
    N = C.lod_pick(lod, max(48, int(per / 0.12)), max(24, int(per / 0.3)), max(14, int(per / 0.6)), max(8, int(per / 1.25)))
    P = K.resample(W0, N, start=0.0) if lod <= 1 else K.decimate(K.resample(W0, 4 * N), N)
    nrm = K.normals(P)
    cum = K.cumlen(P)
    sc = cum[-1] / cf[-1]
    bat = min(0.08, 0.1 * D)

    def gap_of(s_list_fine, hw, s):
        return any(abs(K.sdist(cum, s, c * sc)) < hw for c in s_list_fine)

    z_wall = dict(kerb=zw - 0.08, rock=zw - 0.12, coping=top - 0.09, tile=top - 0.08)[style]
    # rim heights per vertex for LOD2/3 bands (derived from the layout)
    if style == 'rock':
        env = K.rock_envelope(P, cum, [dict(k, s=k['s'] * sc) for k in rocks], grade)
    else:
        env = [top] * N
    sill_z = zw + 0.03
    if s_out is not None:
        env = [sill_z if abs(K.sdist(cum, cum[i], s_out * sc)) < ow / 2 else env[i] for i in range(N)]

    # ---------------------------------------------------------------- bed + wall (+ ledge for rock)
    if lod <= 2:
        rings = [(-bat, bed_z), (-0.01, z_wall - 0.02), (0.0, z_wall)]
        mis = [m_wall, m_wall]
        if style == 'rock':
            rings = [(0.75, grade), (0.0, z_wall)] + rings[::-1]
            rings = rings[:1] + [(0.0, z_wall), (-0.01, z_wall - 0.02), (-bat, bed_z)]
            mis = [m_rock, m_wall, m_wall]
        else:
            rings = rings[::-1]
        if lod >= 1:
            rings = [rg for rg in rings if rg[0] != -0.01]
            mis = mis[-(len(rings) - 1):]
        K.shell(mb, P, rings, mis, bed_mi=m_bed, nrm=nrm)
        if lod <= 2:
            gl = K.loop_verts(mb, K.offset(P, -bat - 0.04, nrm), bed_z + 0.008)
            K.fill(mb, gl, m_glow)
    else:
        # LOD3: one section: grade/rim top -> water edge -> bed
        if style == 'rock':
            rings = [(0.75, grade), (0.25, env), (-0.02, zw - 0.1), (-bat, bed_z)]
            mis = [m_rock, m_rock, m_wall]
        else:
            rings = [(kw, [min(e, grade) for e in env]), (kw * 0.5, env), (-0.02, [min(e, zw - 0.06) for e in env]), (-bat, bed_z)]
            mis = [dict(kerb=m_kerb, coping=m_cope, tile=m_cope)[style]] * 2 + [m_wall]
        K.shell(mb, P, rings, mis, bed_mi=m_bed, nrm=nrm)

    # ---------------------------------------------------------------- rim
    if lod <= 1:
        if style in ('kerb', 'coping', 'tile'):
            ch = C.lod_pick(lod, 0.02, 0.025)
            if style == 'kerb':
                zb = min(z_wall, grade - 0.04)
                u0 = -0.01
                prof0 = [(u0, zb), (kw, zb), (kw, top - ch), (kw - ch, top), (u0 + ch, top), (u0, top - ch)]
                mis0 = [m_kerb] * 6
            elif style == 'coping':
                zb = top - 0.09
                prof0 = [(-0.03, zb), (kw, zb), (kw, top - 0.012), (kw - 0.012, top), (-0.02, top), (-0.045, top - 0.014),
                         (-0.056, top - 0.04), (-0.05, zb + 0.012)]
                mis0 = [m_cope] * 8
            else:
                zb = top - 0.08
                prof0 = [(-0.03, zb), (kw, zb), (kw, top - 0.008), (kw - 0.008, top), (-0.022, top), (-0.03, top - 0.008)]
                mis0 = [m_cope] * 6
            if lod == 1:
                keep = [0, 1, 2, 4] if len(prof0) == 6 else [0, 1, 2, 4, 6]
                prof0 = [prof0[k] for k in keep]
                mis0 = [mis0[k] for k in keep]
            rbu = C.rng(seed, 'blockjit')
            for (a, b) in spans:
                a2, b2 = a * sc, b * sc
                dz = rbu.uniform(-0.006, 0.006)
                du = rbu.uniform(-0.012, 0.012) if style == 'kerb' else 0.0
                K.segment_sweep(mb, P, cum, a2, b2, [(u + (du if u > 0.1 else 0), z + (dz if z > zb + 0.01 else 0)) for u, z in prof0],
                                mis0, step=C.lod_pick(lod, 0.15, 0.4))
            if style == 'tile':
                if lod == 0:
                    pitch, tz = 0.125, [(zw - 0.13, zw - 0.045), (zw - 0.04, zb - 0.005)]
                    n_t = int(cum[-1] / pitch)
                    for j in range(n_t):
                        s0 = cum[-1] * j / n_t + 0.004
                        s1 = cum[-1] * (j + 1) / n_t - 0.004
                        if s_st is not None and abs(K.sdist(cum, (s0 + s1) / 2, s_st * sc)) < sw / 2 + 0.02:
                            continue
                        pa, _, na = K.at_s(P, cum, s0)
                        pb, _, nb = K.at_s(P, cum, s1)
                        for z0, z1 in tz:
                            qa, qb = pa - na * 0.008, pb - nb * 0.008
                            vs = [mb.bm.verts.new((q.x, q.y, z)) for q, z in ((qa, z0), (qb, z0), (qb, z1), (qa, z1))]
                            f = mb.bm.faces.new(vs[::-1]); f.material_index = m_tile
                else:
                    K.shell(mb, P, [(-0.008, zb - 0.005), (-0.008, zw - 0.13)], [m_tile], nrm=nrm)
        else:
            K.build_rocks(mb, P, cum, [dict(k, s=k['s'] * sc) for k in rocks], m_rock, seed, lod, nside=(8, 6), bands=(3, 2))
    elif lod == 2:
        if style == 'rock':
            K.shell(mb, P, [(-0.06, zw - 0.1), (0.04, env), (0.42, env), (0.75, grade)], [m_rock] * 3, nrm=nrm)
        else:
            u0 = -0.01 if style == 'kerb' else -0.05
            zb = dict(kerb=min(z_wall, grade - 0.04), coping=top - 0.09, tile=top - 0.08)[style]
            mi = m_kerb if style == 'kerb' else m_cope
            K.shell(mb, P, [(u0, [min(zb, e - 0.02) for e in env]), (u0, env), (kw, env), (kw, [min(grade - 0.04, e) for e in env])],
                    [mi] * 3, nrm=nrm)
            if style == 'tile':
                K.shell(mb, P, [(-0.008, zb - 0.005), (-0.008, zw - 0.13)], [m_tile], nrm=nrm)

    # ---------------------------------------------------------------- outlet sill, steps
    out_info = None
    if s_out is not None:
        p, t, nn = K.at_s(P, cum, s_out * sc)
        ang = math.atan2(t.y, t.x)
        c = p + nn * (kw * 0.5 + 0.15)
        if lod <= 2:
            size = (ow + 0.04, kw + 0.5, 0.09)
            if lod <= 1:
                C.board(mb, (c.x, c.y, sill_z - 0.045), size, m_sill, bevel=0.012, segs=C.lod_pick(lod, 2, 1), rot=(0, 0, ang))
            else:
                mb.box((c.x, c.y, sill_z - 0.045), size, m_sill, rot=(0, 0, ang))
        out_info = dict(pos=[round(p.x, 3), round(p.y, 3), round(sill_z, 3)], dir=[round(-nn.x, 3), round(-nn.y, 3)], width=round(ow, 3))
    step_tops = []
    if s_st is not None and nst and lod <= 2:
        step_tops = K.steps(mb, P, cum, s_st * sc, nst, sw, (top if style != 'rock' else grade), bed_z, 0.34, m_step, lod,
                            bevel=0.015 if style == 'rock' else 0.01)
    elif s_st is not None and nst and lod == 3:
        p, t, nn = K.at_s(P, cum, s_st * sc)
        c = p - nn * (nst * 0.34 / 2)
        hz = (grade - bed_z) * 0.5
        mb.box((c.x, c.y, bed_z + hz / 2), (sw, nst * 0.34, hz), m_step, rot=(0, 0, math.atan2(t.y, t.x)))

    # ---------------------------------------------------------------- finish
    if centred:
        dx, dy, dz = C.centre_base(mb)
    else:
        dx = dy = dz = 0.0
    tri = C.tri_count(mb.bm)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    sh = lambda pts: [(x + dx, y + dy) for x, y in pts]
    Wout = K.resample(W0, max(24, int(per / 0.25)))
    C.water_props(o, zw + dz, outline_xy=sh(Wout),
                  kz_grade_z=round(grade + dz, 4), kz_style=style,
                  kz_grade_outline=[[round(x, 3), round(y, 3)] for x, y in sh(K.offset(Wout, kw if style != 'rock' else 0.75))],
                  kz_rim_len=round(per, 3), kz_tris_per_10m=round(tri * 10.0 / per, 1),
                  kz_params=dict(shape=shape, depth=round(D, 3), rim_z=round(top + dz, 3), kerb_w=round(kw, 3), steps=nst,
                                 step_w=round(sw, 3), outlet=bool(has_out)))
    if out_info:
        out_info['pos'] = [out_info['pos'][0] + dx, out_info['pos'][1] + dy, out_info['pos'][2] + dz]
        C.set_json_props(o, kz_outlet=out_info)
    if step_tops:
        C.set_json_props(o, kz_steps=[[round(x + dx, 3), round(y + dy, 3), round(z + dz, 3)] for x, y, z in step_tops])
    return o
