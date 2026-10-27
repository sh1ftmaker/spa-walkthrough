"""Lava tube vault segment (B3 lazy river): ribbed basalt vault in concentric rings with amber lava cracks,
channel walls and a towpath.

Targets (asset row 10 x 10 x 4.5 m proxy; lookbook 12 for the look, plan 35 for the channel; scale from the
bathers in tubes ~1.3 m wide and the 0.6 m floating lanterns):
  * segment along Y, length 4-10 m (default 10 = proxy d) so ~25 segments make the 250 m river.
  * inner span 9.2 m at the floor (channel 6.0 m + towpath 2.0 m + far rock bank ~1.2 m), crown 4.2 m inside,
    ribs 0.30-0.34 m deep -> outer 9.8 x 4.5 m.
  * concentric rings (lookbook 12: shingled receding rings, each lip proud of the next): ribs every 0.4-1.0 m
    (default seeded 0.55-0.85), each rib a closed sawtooth section, lip 0.08-0.12 m proud, per-rib inset
    0-0.2 m and low-frequency rock noise (+-5 cm) so the rings read as rough basalt, not a machined tunnel.
  * amber lava cracks: 2-5 long jagged cracks running along the vault plus short wall cracks climbing from the
    towpath (lookbook 12: thin bright seams on the walls/shoulders, a few cm wide), emissive `lava_flow` (scale 0.6 so the thin strips sample the bright flow).
  * towpath 2.0 m wide, top 0.26 m above the water (water 0.9 m, towpath top 1.16 m), basalt kerb face,
    flag slabs 0.9-1.4 m long; the far side is a bank of craggy wet basalt boulders.
Construction: ribs + an outer cave_rock skin seen through the 3 cm joints, bed plane at z = 0 (no mass below),
towpath body + rounded flag slabs (basalt_wet, wet tops), crag-rock bank, crack ribbons (lava, emissive).
Water is data: kz_water_level 0.9, kz_water_outline (channel rectangle), kz_water_path (centreline).

Parameters: length 4-10 (default 10), channel_w (6.0), towpath_w (2.0), rib_spacing 0.4-1.0 (seeded),
crack_density 0-1 (seeded 0.4-0.9 -> 2-5 long cracks), open_roof (False; style 'open' sets it), towpath_side
(+1 = +X, seeded), style 'round' | 'pointed' | 'open' (seed cycles).
Seeds change: vault profile (round half-ellipse / pointed ogival crown / round with an open skylight slot in the
crown), rib spacing and lip depth, inset rhythm, towpath side, crack count and paths, bank boulder layout.
Animation: shader, crack glow pulse: point attribute 'kz_pulse' (0-1 phase along each crack) on the lava slot;
obj['kz_anim'] describes it. Lighting: lightmap + emissive; obj['kz_lights'] has one 1300 K point per crack.
"""
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'lava_tube'
FEATURES = ['ribbed basalt vault in concentric rings', 'amber lava cracks', 'channel walls', 'towpath']
STYLES = ['round', 'pointed', 'open']

RES = {
    0: dict(st=30, sec='full', skin=True, crack_step=0.12, slabs=True, rocks=7, rock_bands=3, rock_sides=7),
    1: dict(st=16, sec='full', skin=True, crack_step=0.3, slabs=True, rocks=7, rock_bands=2, rock_sides=6),
    2: dict(st=8, sec='saw', skin=False, crack_step=1.0, slabs=False, rocks=3, rock_bands=1, rock_sides=5),
    3: dict(st=4, sec='saw', skin=False, crack_step=3.0, slabs=False, rocks=0, rock_bands=1, rock_sides=4),
}


def build(lod, seed, w=None, d=None, h=None, length=None, channel_w=6.0, towpath_w=2.0, rib_spacing=None,
          crack_density=None, open_roof=None, towpath_side=None, style=None):
    R = RES[min(lod, 3)]
    p = genlib.proxy(ASSET)
    L = length or d or p['d']
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    sp = rib_spacing or g.uniform(0.55, 0.85)
    lip = g.uniform(0.08, 0.12)
    tp = towpath_side or g.choice([1, -1])
    dens = crack_density if crack_density is not None else g.uniform(0.4, 0.9)
    open_roof = (style == 'open') if open_roof is None else open_roof
    T = 0.32                                         # rib depth
    Hp = h or p['h']
    a = channel_w / 2 + towpath_w / 2 + 0.6          # inner half-span at the floor (4.6 m at the defaults)
    b = Hp - T - 0.02                                 # inner crown height
    a_out = a                                        # (outer = inner + T along the normal)

    # vault centreline curve P(t), t in [0, 1] from the -X springing over the crown to +X
    def P(t):
        th = math.pi * (1 - t)
        if style == 'pointed':
            x = a * math.cos(th)
            z = b * (1 - abs(math.cos(th)) ** 1.55) ** 0.62
        else:
            x = a * math.cos(th); z = b * math.sin(th)
        return Vector((x, 0, z))

    def N(t):                                        # inward normal (towards the tube axis) in the x-z plane
        e = 1e-3
        d_ = P(min(1, t + e)) - P(max(0, t - e))
        n = Vector((-d_.z, 0, d_.x)).normalized()    # rotate tangent by +90 in x-z ... check direction below
        mid = Vector((0, 0, b * 0.45))
        if n.dot(mid - P(t)) < 0:
            n = -n
        return n

    # ribs layout (independent of LOD)
    gr = C.rng(seed, 'ribs')
    n_rib = max(3, int(round(L / sp)))
    sp = L / n_rib
    ribs = []
    for i in range(n_rib):
        ribs.append(dict(y0=-L / 2 + i * sp, y1=-L / 2 + (i + 1) * sp, inset=gr.uniform(0.0, 0.2) * (0.6 + 0.4 * math.sin(i * 1.7)),
                         lip=lip * gr.uniform(0.8, 1.2), off=gr.uniform(0, 50)))
    if lod >= 3:      # far: merge the rings into ~5 sawtooth bands (same lip language, 1/3 of the count)
        k = max(1, math.ceil(n_rib / 5))
        ribs = [dict(ribs[i], y1=ribs[min(i + k, n_rib) - 1]['y1']) for i in range(0, n_rib, k)]
    gap = 0.03 if R['sec'] == 'full' else 0.0
    crown_cut = (0.40, 0.60) if open_roof else None

    def rib_dr(rb, t, y):
        """inward offset of the rib's inner surface at (t, y): sawtooth from the lip (front, -Y end) to the back"""
        u = (y - rb['y0']) / max(1e-6, rb['y1'] - rb['y0'])
        base = rb['inset'] + 0.05 * noise.noise(Vector((t * 7.0, rb['off'], 0.3)))
        # foot of the wall flares out a little (towpath / bank hide it)
        return base + rb['lip'] * (1 - u) ** 1.3

    mb = genlib.MeshBuilder()
    m_rib = mb.slot('cave_rock', wetness=0.75)
    m_skin = mb.slot('cave_rock', wetness=0.5, tint=(0.55, 0.55, 0.6))
    m_lava = mb.slot('lava_flow', emissive_level=1.2, scale=0.6)
    m_kerb = mb.slot('basalt_wet', wetness=0.55, tint=(0.32, 0.36, 0.46))
    m_flag = mb.slot('basalt_wet', wetness=0.9, tint=(0.32, 0.36, 0.46), roughness_offset=-0.05)
    m_bed = mb.slot('basalt_wet', wetness=1.0, tint=(0.32, 0.36, 0.46))
    bm = mb.bm

    # station list along the arch (crown cut leaves two runs)
    st = R['st']
    ts = [i / st for i in range(st + 1)]
    runs = [ts]
    if crown_cut:
        runs = [[t for t in ts if t <= crown_cut[0]] + [crown_cut[0]], [crown_cut[1]] + [t for t in ts if t >= crown_cut[1]]]
        runs = [sorted(set(r_)) for r_ in runs]

    # ---------------------------------------------------------------- ribs
    for rb in ribs:
        y0, y1 = rb['y0'] + gap / 2, rb['y1'] - gap / 2
        for run in runs:
            rings = []
            for t in run:
                c = P(t); n = N(t)
                if R['sec'] == 'full':
                    sec = [(y0, -T), (y1, -T), (y1, rib_dr(rb, t, y1)), (y0 + 0.06, rib_dr(rb, t, y0 + 0.06)),
                           (y0, rib_dr(rb, t, y0) - 0.05)]
                else:
                    sec = [(y0, -T), (y1, -T), (y0, rib_dr(rb, t, y0))]
                rings.append([bm.verts.new(c + n * dr + Vector((0, y, 0))) for y, dr in sec])
            fs = []
            for A, B in zip(rings[:-1], rings[1:]):
                fs += C.bridge_rings(bm, A, B)
            fs.append(bm.faces.new(rings[0])); fs.append(bm.faces.new(rings[-1][::-1]))
            bmesh.ops.recalc_face_normals(bm, faces=fs)
            mb._tag(fs, m_rib)

    # outer skin behind the joints (single-sided, facing in)
    if R['skin']:
        for run in runs:
            ys = [-L / 2, L / 2]
            rows = [[bm.verts.new(P(t) - N(t) * (T + 0.01) + Vector((0, y, 0))) for t in run] for y in ys]
            fs = [bm.faces.new((rows[0][k], rows[0][k + 1], rows[1][k + 1], rows[1][k])) for k in range(len(run) - 1)]
            for f in fs:
                f.normal_update()
                if f.normal.dot(Vector((0, 0, b * 0.45)) - f.calc_center_median()) < 0:
                    f.normal_flip()
            mb._tag(fs, m_skin)

    # ---------------------------------------------------------------- bed (z = 0 plane between the walls)
    bed = [bm.verts.new((x, y, 0.0)) for x, y in ((-a, -L / 2), (a, -L / 2), (a, L / 2), (-a, L / 2))]
    mb._tag([bm.faces.new(bed)], m_bed)

    # ---------------------------------------------------------------- towpath + kerb
    wl = 0.9
    tz = wl + 0.26
    x_in = tp * (a - towpath_w - 0.05)               # water-side kerb face
    x_out = tp * (a + 0.05)                          # buried in the rib feet
    xc = (x_in + x_out) / 2; tw = abs(x_out - x_in)
    body_top = tz - (0.08 if R['slabs'] else 0.0)
    mb.box((xc, 0, body_top / 2), (tw, L, body_top), m_kerb)
    if R['slabs']:
        gs = C.rng(seed, 'slabs')
        y = -L / 2
        rows = []
        while y < L / 2 - 0.3:
            ln = min(gs.uniform(0.9, 1.4), L / 2 - y)
            if L / 2 - (y + ln) < 0.45:
                ln = L / 2 - y
            rows.append((y, ln)); y += ln
        for y, ln in rows:
            if lod == 0:
                C.slab(mb, (xc + tp * 0.04, y + ln / 2, tz - 0.08), tw - 0.12, ln - 0.014, 0.08, m_flag, rc=0.03, m=2)
            else:
                mb.box((xc + tp * 0.04, y + ln / 2, tz - 0.04), (tw - 0.12, ln - 0.014, 0.08), m_flag)
        # kerb coping at the water edge
        mb.box((x_in + tp * 0.11, 0, tz - 0.05), (0.22, L, 0.10), m_kerb, bevel=0.02 if lod == 0 else 0.0)

    # ---------------------------------------------------------------- far bank boulders
    gb = C.rng(seed, 'bank')
    xb = -tp * (a - 0.55)
    nrk = R['rocks']
    placed = []
    yk = -L / 2 + gb.uniform(0.2, 0.6)
    while yk < L / 2 - 0.3:
        rx = gb.uniform(0.45, 0.75); ry = gb.uniform(0.6, 1.1); top = gb.uniform(0.95, 1.35)
        placed.append((yk + ry * 0.7, rx, ry, top, gb.uniform(0, 99)))
        yk += ry * 1.25
    placed.sort(key=lambda q: -q[1] * q[2])          # largest first: lower LODs keep the biggest
    keep = placed[:nrk] if nrk else []
    for yy, rx, ry, top, sd in keep:
        rr = C.rng(seed, f'rock{sd:.3f}')
        if lod <= 1:
            C.crag_rock(mb, C.frame((xb, max(-L / 2 + ry * 0.9, min(L / 2 - ry * 0.9, yy)), 0), (0, 1, 0)), rx, ry * 0.75, 0.0, top,
                        m_kerb, rr, nside=R['rock_sides'], bands=R['rock_bands'])
        else:
            C.hull_rock(mb, (xb, max(-L / 2 + ry * 0.9, min(L / 2 - ry * 0.9, yy)), top * 0.4), (rx, ry * 0.75, top * 0.6),
                        m_kerb, rr, npts=8, ground=0.0)
    if lod >= 3:
        mb.box((xb, 0, 0.5), (1.0, L, 1.0), m_kerb)

    # ---------------------------------------------------------------- lava cracks
    gc = C.rng(seed, 'cracks')
    n_long = max(1, int(round(2 + 3 * dens)))
    n_wall = int(round(3 * dens)) + 1
    cracks = []
    for k in range(n_long):
        side = gc.choice([-1, 1])
        t0 = 0.5 + side * gc.uniform(0.12, 0.38)
        pts = []; t = t0; yv = -L / 2 + 0.02
        y_end = L / 2 - 0.02 if gc.random() < 0.7 else gc.uniform(0, L / 2)
        y_start = -L / 2 + 0.02 if gc.random() < 0.7 else gc.uniform(-L / 2, 0)
        yv = y_start
        while yv <= y_end:
            pts.append((t, yv)); yv += 0.12; t = max(0.06, min(0.94, t + gc.gauss(0, 0.006)))
            if crown_cut and crown_cut[0] - 0.02 < t < crown_cut[1] + 0.02:
                t = crown_cut[0] - 0.03 if t < 0.5 else crown_cut[1] + 0.03
        cracks.append(dict(pts=pts, w=gc.uniform(0.035, 0.07)))
    for k in range(n_wall):
        side = gc.choice([-1, 1])
        y = gc.uniform(-L / 2 + 0.5, L / 2 - 0.5)
        t = 0.5 + side * 0.47
        pts = []
        t_end = 0.5 + side * gc.uniform(0.18, 0.3)
        while (t - t_end) * side > 0:
            pts.append((t, y)); t -= side * 0.012; y += gc.gauss(0, 0.05)
            y = max(-L / 2 + 0.05, min(L / 2 - 0.05, y))
        cracks.append(dict(pts=pts, w=gc.uniform(0.03, 0.05)))
    if lod >= 2:
        cracks = cracks[:max(1, n_long if lod == 2 else 1)]

    def rib_at(y):
        for rb in ribs:
            if rb['y0'] <= y <= rb['y1']:
                return rb
        return ribs[-1] if y > 0 else ribs[0]

    pulse = []                     # (vert, phase)
    lights = []
    for ci, ck in enumerate(cracks):
        pts = ck['pts']
        if len(pts) < 2:
            continue
        # resample by LOD step (in metres along the crack)
        out = [pts[0]]; acc = 0.0
        for q0, q1 in zip(pts[:-1], pts[1:]):
            acc += math.hypot((q1[0] - q0[0]) * a * 2.2, q1[1] - q0[1])
            if acc >= R['crack_step']:
                out.append(q1); acc = 0.0
        if out[-1] != pts[-1]:
            out.append(pts[-1])
        if len(out) < 2:
            continue
        P3 = []
        for t, y in out:
            rb = rib_at(y)
            dr = rib_dr(rb, t, y) if R['sec'] == 'full' else rib_dr(rb, t, rb['y0']) * (1 - (y - rb['y0']) / max(1e-6, rb['y1'] - rb['y0']))
            dr = max(dr, -T + 0.02) if R['sec'] == 'full' else dr
            P3.append((P(t) + N(t) * (dr + 0.015) + Vector((0, y, 0)), N(t)))
        row_l, row_r = [], []
        ncr = len(P3)
        for i, (q, n) in enumerate(P3):
            dvec = (P3[min(i + 1, ncr - 1)][0] - P3[max(i - 1, 0)][0]).normalized()
            wv = dvec.cross(n).normalized()
            taper = math.sin(math.pi * (i + 0.5) / ncr) ** 0.5
            ww = ck['w'] * (0.4 + 0.6 * taper) * (1.6 if lod >= 2 else 1.0)
            row_l.append(bm.verts.new(q - wv * ww / 2)); row_r.append(bm.verts.new(q + wv * ww / 2))
            ph = (ci * 0.37 + i / max(1, ncr - 1)) % 1.0
            pulse += [(row_l[-1], ph), (row_r[-1], ph)]
        fs = []
        for i in range(ncr - 1):
            f = bm.faces.new((row_l[i], row_l[i + 1], row_r[i + 1], row_r[i]))
            f.normal_update()
            if f.normal.dot(P3[i][1]) < 0:
                f.normal_flip()
            fs.append(f)
        mb._tag(fs, m_lava)
        qm = P3[ncr // 2]
        lights.append(C.light_entry(qm[0] + qm[1] * 0.25, color_k=1300, watts=round(12 + 25 * ck['w'] / 0.07, 1)))

    bm.verts.index_update()
    pulse_idx = [(v.index, ph) for v, ph in pulse]
    o = mb.to_object(ASSET)
    me = o.data
    at = me.attributes.new('kz_pulse', 'FLOAT', 'POINT')
    for vi, ph in pulse_idx:
        at.data[vi].value = round(ph, 3)
    ch_x0 = -tp * a if tp > 0 else x_in
    ch_x1 = x_in if tp > 0 else -tp * a
    C.water_props(o, wl, outline_xy=[(min(ch_x0, ch_x1), -L / 2), (max(ch_x0, ch_x1), -L / 2),
                                     (max(ch_x0, ch_x1), L / 2), (min(ch_x0, ch_x1), L / 2)],
                  path=[((ch_x0 + ch_x1) / 2, -L / 2, wl), ((ch_x0 + ch_x1) / 2, L / 2, wl)],
                  kz_flow_dir=[0, 1, 0])
    C.set_json_props(o,
                     kz_anim={'type': 'shader', 'what': 'lava crack glow pulse', 'attr': 'kz_pulse',
                              'material_slot': m_lava, 'material': 'lava_flow', 'period_s': 6.0},
                     kz_lights=lights,
                     kz_params=dict(style=style, length=round(L, 3), channel_w=channel_w, towpath_w=towpath_w,
                                    towpath_side=tp, rib_spacing=round(sp, 3), ribs=n_rib, lip=round(lip, 3),
                                    crack_density=round(dens, 2), cracks=len(cracks), open_roof=bool(open_roof),
                                    towpath_z=round(tz, 3)))
    genlib.finish(o, smooth_angle=40)
    return o
