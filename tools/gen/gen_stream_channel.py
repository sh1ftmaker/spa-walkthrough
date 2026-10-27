"""Stream, rill and runnel channel (per metre along a path). Rebuilt (gen30) from the concept, not the old code.

Concept: refs/gen/sheet-vs-water-2.png #2 (1 m = 197 px: module ~1.5 m wide, black bank rocks 0.3-0.45 m high,
water ~0.9 m wide, drops 0.15-0.17 m), lookbook/img/04-arrival-gate.jpg (dark craggy flat-topped bank masses that
overlap and shelter the water, rock weirs with thin falls), 30-plan-summit.jpg.
The water surface is NOT built (runtime fx_water_surface): this asset is bed, banks / kerbs / treads and weirs.

The run is a chain of flat POOLS between WEIRS. A weir is a pale lip stone whose front edge projects 0.06 m over a
riser; the downstream bed is `drop` (0.12-0.17 m) lower. Nothing is built below a pool's bed (no plinth mass, no
skirt): the place model supplies the terrain at kz_ground_profile around it.
  natural  2-3 sizes of dark faceted craggy flat-topped basalt boulders (0.2-0.6 m) overlapping 30-40 % along
           both banks, small toe rocks at the waterline, a low outer row that buries the terrain edge, a stone bed
           with cobbles. Weir = ragged lip slab with 1-2 spill notches on 2-3 riser boulders.
  kerbed   cut ashlar kerb 0.18 m wide, 0.30 m above the bed: a ~0.15 m course plus a 0.15 m capstone (chamfered,
           joints staggered, a block every 0.45-0.8 m, V-grooved ends), on a thin paved plinth/bed. The kerb top
           steps down with each weir. Rock clusters only at the run ends.
  stepped  4-5 full-width treads (0.17 m drop, 0.28-0.33 m tread) with rounded nosings projecting 0.05 m (the
           lips the water sheets over), ashlar side walls that step with the treads and rise 0.22 m above each
           tread, craggy rock masses flanking the head (and the foot on some seeds).
LODs from the same layout: LOD1 drops toe/outer rows, cobbles, end chamfers, rounded nosings; LOD2 is two bank
strips + a lighter bed band + the weir lips (or stepped wall ribbons + treads); LOD3 is one U-section with the weir
step (or the stair ribbon). Budget per metre 700/280/84/20 (the stock check compares totals, so the default
module is 1 m for natural/kerbed and 1.2-1.65 m for stepped and stays under 770 tris at LOD0).

Parameters (build(lod, seed, ...)):
  path         list of (x, y, z) nodes in metres; z = water level of the pool starting there (sloped paths put
               their drops at the weirs). Default: a 1 m module (natural meanders), straight for kerbed/stepped.
  length       default module length when no path is given (natural/kerbed 1.0 m; stepped = steps x tread)
  width        water width 0.3-2.5 m (natural 0.75-1.15, kerbed 0.32-0.48, stepped 0.34-0.46 by seed)
  depth        water depth 0.1-0.5 m over the bed (stepped: sheet depth on treads)
  style        'natural' | 'kerbed' | 'stepped' (default: by seed, (seed-1) % 3)
  weir_every   metres between weirs (natural 1.3-1.9, kerbed 1.4-2.0 by seed; 0 = none; every module has >= 1)
  bank_density 0.5-1.5 bank rock spacing factor (natural)
  drop         weir / step drop (natural 0.12-0.17, kerbed 0.15, stepped 0.17)
  tread, steps stepped only (0.28-0.33 m, 4-5)
  end_rocks    kerbed/stepped rock clusters: 'both' | 'up' | 'none'
Seeds change the shape: width and its swell along the run, meander, bank asymmetry (one higher cliff bank), rock
size mix and overlap, weir spacing and notch layout; kerb block lengths, capstone overhang, course height; tread
count and depth, wall thickness, which ends carry rock masses.
Custom props: kz_style, kz_width, kz_depth, kz_water_path (JSON [x, y, z_water] per pool end, so drops appear as
pairs), kz_weirs (JSON [x, y, z_up, z_down] per weir crest), kz_ground_z (ground at the upstream end),
kz_ground_profile (JSON [x0, y0, x1, y1, z] per pool: terrain level beside it), kz_centerline (JSON [x, y,
water half-width] every 0.25 m, so the fx surface can follow bends and swells), kz_pool_s (arc length of every pool
boundary / weir), kz_edge_half_width,
kz_tris_per_m. Pivot: bbox centre xy, lowest point z = 0. Front +Y = downstream. No animation (flow is fx).
"""
import json
import math

import genlib
import kzgeo_stream_channel as kz
from kzgeo_wall_trickle import hull_rock

ASSET = 'stream_channel'
FEATURES = ['weirs: pale lip stones projecting over 0.12-0.17 m bed drops (stepped: nosed treads)',
            'rock-lined banks of craggy flat-topped boulders / cut-stone ashlar kerbs / stepped treads with walls',
            'lighter stone bed band between darker banks']


def _default_path(style, L, r):
    if style != 'natural':
        return [(0.0, 0.0, 0.0), (0.0, L, 0.0)]
    amp = r.uniform(0.03, 0.07) * max(1.0, L) * r.choice((-1, 1))
    ph = r.uniform(0, math.pi)
    n = max(2, int(math.ceil(L / 0.5)))
    return [(amp * math.sin(math.pi * i / n * max(1.0, L / 1.5) + ph) - amp * math.sin(ph) * (1 - i / n), L * i / n, 0.0)
            for i in range(n + 1)]


def build(lod, seed, path=None, length=None, width=None, depth=None, style=None, weir_every=None,
          bank_density=1.0, drop=None, tread=None, steps=None, end_rocks=None):
    r = genlib.rng(seed, ASSET)
    style = style or ['natural', 'kerbed', 'stepped'][(seed - 1) % 3]
    # ---------------------------------------------------------------- shape parameters (independent of LOD)
    if style == 'natural':
        W = width or r.uniform(0.75, 1.15)
        D = depth or r.uniform(0.14, 0.2)
        dr = drop or r.uniform(0.12, 0.17)
        we = r.uniform(1.3, 1.9) if weir_every is None else weir_every
    elif style == 'kerbed':
        W = width or r.uniform(0.32, 0.48)
        D = depth or r.uniform(0.12, 0.16)
        dr = drop or 0.15
        we = r.uniform(1.4, 2.0) if weir_every is None else weir_every
    else:
        W = width or r.uniform(0.34, 0.46)
        D = depth or 0.03
        dr = drop or 0.17
        we = 0
    nst = steps or r.choice((4, 5, 5))
    tr = tread or r.uniform(0.28, 0.33)
    user_path = path is not None
    if path is None:
        Lm = length or (nst * tr if style == 'stepped' else 1.0)
        path = _default_path(style, Lm, r)
    P = kz.Path(path)
    L = P.L
    if style == 'stepped':
        if user_path or (length and not steps):
            nst = max(2, int(round(L / tr)))
        tr = L / nst
        bounds = [k * tr for k in range(nst + 1)]
        events = bounds[1:-1]
    else:
        nw = max(1, int(round(L / we))) if we else 0
        rw = genlib.rng(seed, 'weirs')
        events = [L * (k + 0.5) / nw + rw.uniform(-0.12, 0.12) * L / max(nw, 1) * 0.5 for k in range(nw)]
        bounds = [0.0] + events + [L]
    npool = len(bounds) - 1
    z0 = P.z(0.0)
    zw = [z0 - k * dr if P.flat else P.z(bounds[k]) for k in range(npool)]
    bed = [z - D for z in zw]
    if style == 'natural':
        gz = [z + 0.06 for z in zw]
    elif style == 'kerbed':
        gz = [b - 0.06 for b in bed]
    else:
        gz = [b for b in bed]                       # stair beside the runnel at tread level

    rsw = genlib.rng(seed, 'swell')
    swell = rsw.uniform(0.0, 0.18) if style == 'natural' else 0.0
    ph = rsw.uniform(0, 2 * math.pi)

    def Wl(s):
        return W * (1.0 + swell * math.sin(2 * math.pi * s / 1.7 + ph))

    def pool_at(s):
        return max(0, min(npool - 1, sum(1 for e in events if s > e)))

    mb = genlib.MeshBuilder()
    rock_a = mb.slot('basalt_wet', wetness=0.75, scale=1.1, tint=(0.62, 0.62, 0.66))
    rock_b = mb.slot('basalt_wet', wetness=0.65, scale=0.8, tint=(0.5, 0.5, 0.54))
    lipm = mb.slot('stepping_stone', wear=0.55, scale=1.0)
    bedn = mb.slot('stepping_stone', wear=0.2, scale=1.6, tint=(0.55, 0.55, 0.57))
    ash = [mb.slot('stepping_stone', wear=0.35, wetness=0.45, scale=0.9, tint=t)
           for t in ((1.0, 0.97, 0.92), (0.9, 0.87, 0.82), (0.8, 0.78, 0.75))]
    pave = mb.slot('paving', wear=0.3, scale=1.2)
    rocks = (rock_a, rock_b)

    # ---------------------------------------------------------------- LOD3: one section
    if lod == 3:
        bm = mb.bm
        if style == 'stepped':
            T = [bed[k] + D for k in range(npool)]
            hw = W / 2 + 0.18
            prof = []
            for k in range(npool):
                prof += [(bounds[k], T[k]), (bounds[k + 1], T[k])]
            A = [bm.verts.new(P.pt(s, -hw, z)) for s, z in prof]
            B = [bm.verts.new(P.pt(s, hw, z)) for s, z in prof]
            fs = [bm.faces.new((A[i], A[i + 1], B[i + 1], B[i])) for i in range(len(prof) - 1)]
            mb._tag(fs, ash[0])
        else:
            kmid = npool // 2 if npool > 1 else 0
            sw = bounds[kmid] if npool > 1 else None
            ui = W / 2
            uo = W / 2 + (0.55 if style == 'natural' else 0.2)
            top0 = (gz[0] + 0.24) if style == 'natural' else bed[0] + 0.3
            top1 = (gz[-1] + 0.24) if style == 'natural' else bed[-1] + 0.3
            b0, b1 = bed[0], bed[-1]
            bankm = rock_a if style == 'natural' else ash[0]
            for sd in (-1, 1):
                q = [bm.verts.new(P.pt(0, sd * uo, top0)), bm.verts.new(P.pt(L, sd * uo, top1)),
                     bm.verts.new(P.pt(L, sd * ui, top1)), bm.verts.new(P.pt(0, sd * ui, top0))]
                mb._tag([bm.faces.new(q)], bankm)
                if sw is None:
                    w_ = [q[3], q[2], bm.verts.new(P.pt(L, sd * ui, b1)), bm.verts.new(P.pt(0, sd * ui, b0))]
                else:
                    w_ = [q[3], q[2], bm.verts.new(P.pt(L, sd * ui, b1)), bm.verts.new(P.pt(sw, sd * ui, b1)),
                          bm.verts.new(P.pt(sw, sd * ui, b0)), bm.verts.new(P.pt(0, sd * ui, b0))]
                mb._tag([bm.faces.new(w_)], bankm)
            if sw is None:
                f = bm.faces.new([bm.verts.new(P.pt(0, -ui, b0)), bm.verts.new(P.pt(0, ui, b0)), bm.verts.new(P.pt(L, ui, b1)), bm.verts.new(P.pt(L, -ui, b1))])
                mb._tag([f], bedn if style == 'natural' else pave)
            else:
                c = [[bm.verts.new(P.pt(s, u, z)) for u in (-ui, ui)] for s, z in ((0, b0), (sw, b0), (sw, b1), (L, b1))]
                mb._tag([bm.faces.new((c[0][0], c[0][1], c[1][1], c[1][0]))], bedn if style == 'natural' else pave)
                mb._tag([bm.faces.new((c[1][0], c[1][1], c[2][1], c[2][0]))], lipm)
                mb._tag([bm.faces.new((c[2][0], c[2][1], c[3][1], c[3][0]))], bedn if style == 'natural' else pave)
        return _finish(mb, P, style, W, D, L, npool, bounds, events, zw, bed, gz, seed, lod, wfn=Wl)

    # ---------------------------------------------------------------- weirs (natural, kerbed)
    def weir(k, sw):
        """pale lip stone over a riser at the end of pool k; crest a little below pool k's water"""
        crest = zw[k] - 0.02
        lt = 0.07
        ld = 0.2
        hw = (W / 2 + (0.22 if style == 'natural' else 0.05))
        M = P.M(sw)
        rl = genlib.rng(seed, f'lip{k}')
        if style == 'natural':
            if lod == 2:
                kz.block(mb, M, -hw, hw, -ld, 0.06, crest - lt, crest, lipm, bottom=True, caps=(False, True))
                kz.block(mb, M, -hw, hw, -ld, 0.002, bed[k + 1], crest - lt, rock_b)
                return
            kz.lip_slab(mb, M, -hw, hw, -ld, 0.06, crest - lt, crest, lipm, rl, notches=rl.choice((1, 2, 2)),
                        npts=6 if lod == 0 else 4)
            if lod == 0:
                nr = 2 if W < 1.0 else 3
                for i in range(nr):
                    x = -hw + (2 * hw) * (i + 0.5) / nr
                    kz.crag_rock(mb, P.M(sw - 0.1, x), hw / nr * 1.15, 0.12, bed[k + 1] - 0.01, crest - lt + 0.005,
                                 rocks[i % 2], genlib.rng(seed, f'riser{k}{i}'), nside=6, bands=1, tilt=0.0, crag=0.08,
                                 top_inset=0.95)
            else:
                kz.block(mb, M, -hw, hw, -ld + 0.02, 0.002, bed[k + 1], crest - lt, rock_b)
        else:
            hw = W / 2 + 0.04
            if lod == 2:
                kz.block(mb, M, -hw, hw, -ld, 0.06, bed[k + 1], crest, lipm)
                return
            kz.block(mb, M, -hw, hw, -ld, 0.06, crest - lt, crest, lipm, ch=0.012 if lod == 0 else 0.0, bottom=True,
                     caps=(False, True))
            kz.block(mb, M, -hw, hw, -ld + 0.03, 0.002, bed[k + 1], crest - lt, ash[1])

    # ---------------------------------------------------------------- NATURAL
    if style == 'natural':
        rs = genlib.rng(seed, 'shape')
        hi_side = rs.choice((-1, 1))                 # one bank higher (cliff side), seeds differ
        asym = rs.uniform(1.0, 1.2)
        mix = rs.choice(((0.45, 0.4), (0.3, 0.5), (0.55, 0.25)))    # P(big), P(mid); rest small

        def bed_z(s, u):
            k = pool_at(s)
            return bed[k] + 0.012 * math.sin(7 * s + 3 * u + seed) - 0.02 * (1 - min(1, abs(u) / (Wl(s) / 2)))
        # bed: one surface per pool, reaching under the bank rocks and under the weir risers
        for k in range(npool):
            a = bounds[k] - (0.04 if k else 0.0)
            b = bounds[k + 1] - (0.17 if k < npool - 1 else 0.0)
            ue = Wl((a + b) / 2) / 2 + 0.25
            ns = 1 if lod == 2 else max(1, int(math.ceil((b - a) / 0.35)))
            kz.grid_strip(mb, P, a, b, -ue, ue, (lambda s, u, k=k: bed[k] + (0 if lod else bed_z(s, u) - bed[pool_at(s)])),
                          bedn, ns=ns, nu=1 if lod else 2)
        for k in range(npool - 1):
            weir(k, bounds[k + 1])
        # bank layout (identical for every LOD; LODs only choose detail)
        banks = []
        for sd in (-1, 1):
            rb = genlib.rng(seed, f'bank{sd}')
            hs = asym if sd == hi_side else 1.0
            s = rb.uniform(-0.1, 0.0)
            j = 0
            while s < L - 0.05:
                u_ = rb.random()
                near_weir = any(abs(s + 0.2 - e) < 0.25 for e in events)
                cls = 'big' if (u_ < mix[0] or near_weir) else ('mid' if u_ < mix[0] + mix[1] else 'small')
                if cls == 'big':
                    rx, ry, hab = rb.uniform(0.24, 0.3), rb.uniform(0.26, 0.32), rb.uniform(0.2, 0.3) * hs
                elif cls == 'mid':
                    rx, ry, hab = rb.uniform(0.15, 0.2), rb.uniform(0.17, 0.22), rb.uniform(0.13, 0.22) * hs
                else:
                    rx, ry, hab = rb.uniform(0.11, 0.15), rb.uniform(0.12, 0.16), rb.uniform(0.08, 0.15)
                sc_ = s + ry
                if sc_ > L + 0.02:
                    break
                ov = rb.uniform(0.3, 0.4)
                banks.append(dict(row='front', sd=sd, s=max(ry * 0.6 - 0.05, min(sc_, L + 0.05 - ry * 0.6)), rx=rx, ry=ry, hab=hab, cls=cls,
                                  inset=rb.uniform(0.52, 0.68), yaw=rb.uniform(-0.45, 0.45), key=f'f{sd}{j}'))
                if j and rb.random() < 0.65:     # toe rock at the waterline between two bank rocks
                    banks.append(dict(row='toe', sd=sd, s=s + rb.uniform(-0.04, 0.04), rx=rb.uniform(0.08, 0.11),
                                      ry=rb.uniform(0.09, 0.13), hab=rb.uniform(0.02, 0.08), cls='small', inset=0.05,
                                      yaw=rb.uniform(-1, 1), key=f't{sd}{j}'))
                s += 2 * ry * (1 - ov) / max(0.5, bank_density)
                j += 1
            s = rb.uniform(0.1, 0.3)
            j = 0
            while s < L - 0.05:
                banks.append(dict(row='outer', sd=sd, s=min(s, L - 0.15), rx=rb.uniform(0.2, 0.26), ry=rb.uniform(0.26, 0.36),
                                  hab=rb.uniform(0.12, 0.26) * hs, cls='mid', inset=0, yaw=rb.uniform(-0.6, 0.6), key=f'o{sd}{j}'))
                s += rb.uniform(0.36, 0.48) / max(0.5, bank_density)
                j += 1
        if lod == 2:
            # two lumpy bank strips (inner face + top + outer slope), a flanking rock at each weir
            bm = mb.bm
            nseg = max(3, int(round(L / 0.3)))
            for sd in (-1, 1):
                hs = asym if sd == hi_side else 1.0
                rows = []
                rb = genlib.rng(seed, f'strip{sd}')
                for i in range(nseg + 1):
                    s = L * i / nseg
                    k = pool_at(s)
                    kmin = pool_at(min(L, s + 0.03))
                    ui = Wl(s) / 2 - 0.04
                    rows.append([bm.verts.new(P.pt(s, sd * ui, bed[kmin] - 0.01)),
                                 bm.verts.new(P.pt(s, sd * (ui + 0.12), gz[k] + rb.uniform(0.14, 0.3) * hs)),
                                 bm.verts.new(P.pt(s, sd * (ui + 0.5), gz[k] + rb.uniform(0.05, 0.14)))])
                fs = []
                for A, B in zip(rows[:-1], rows[1:]):
                    for jj in range(2):
                        fs.append(bm.faces.new((A[jj], A[jj + 1], B[jj + 1], B[jj])))
                mb._tag(fs, rock_a)
            for k, e in enumerate(events):
                for sd in (-1, 1):
                    kz.crag_rock(mb, P.M(e, sd * (Wl(e) / 2 + 0.2)), 0.24, 0.26, bed[k + 1] - 0.02, zw[k] + 0.32,
                                 rock_b, genlib.rng(seed, f'w{k}{sd}'), nside=5, bands=1)
        else:
            for b in banks:
                if lod == 1 and b['row'] != 'front':
                    continue
                s, sd = b['s'], b['sd']
                span = (s - b['ry'], s + b['ry'])
                ks = range(pool_at(max(0, span[0])), pool_at(min(L, span[1])) + 1)
                zb = min(bed[k] for k in ks) - 0.02
                if b['row'] == 'outer':
                    zt = max(gz[k] for k in ks) + b['hab']
                    u = sd * (Wl(s) / 2 + 0.32 + b['rx'] * 0.4)
                    zb = min(gz[k] for k in ks) - 0.12
                elif b['row'] == 'toe':
                    zt = zw[pool_at(s)] + b['hab']
                    u = sd * (Wl(s) / 2 + b['rx'] * 0.1)
                else:
                    zt = max(zw[k] for k in ks) + b['hab']
                    u = sd * (Wl(s) / 2 + b['rx'] * b['inset'])
                rr = genlib.rng(seed, 'rk' + b['key'])
                if lod == 0:
                    ns_, bands = ((9 if b['cls'] == 'big' else 7), 3) if b['row'] == 'front' and b['cls'] != 'small' \
                        else ((7, 3) if b['row'] == 'outer' else (6, 2))
                else:
                    ns_, bands = (6, 2) if b['cls'] != 'small' else (5, 1)
                kz.crag_rock(mb, P.M(s, u, 0, yaw=b['yaw']), b['rx'], b['ry'], zb, zt, rocks[int(rr.random() * 2)], rr,
                             nside=ns_, bands=bands, tilt=0.06 if b['cls'] == 'big' else 0.1,
                             dome=(lod == 0 and b['cls'] == 'big'),
                             lean=((-sd * b['rx'] * 0.22, 0.0) if b['row'] == 'front' and b['cls'] != 'small' else (0.0, 0.0)))
            if lod == 0:
                rc = genlib.rng(seed, 'cobbles')
                for i in range(max(4, int(round(5 * L)))):
                    s = rc.uniform(0.04, 0.96) * L
                    if any(-0.22 < s - e < 0.08 for e in events):
                        continue
                    k = pool_at(s)
                    rx = rc.uniform(0.03, 0.06)
                    c = P.pt(s, rc.uniform(-0.38, 0.38) * Wl(s), bed[k] + rx * 0.15)
                    hull_rock(mb, c, (rx * 1.3, rx, rx * 0.6), bedn if i % 3 else lipm, rc, npts=7, ground=bed[k] - 0.005,
                              rot=rc.uniform(0, 6))
        return _finish(mb, P, style, W, D, L, npool, bounds, events, zw, bed, gz, seed, lod, edge=W / 2 * (1 + swell) + 0.8, wfn=Wl)

    # ---------------------------------------------------------------- KERBED
    if style == 'kerbed':
        rs = genlib.rng(seed, 'shape')
        kw = 0.18
        c1 = rs.uniform(0.14, 0.16)
        kh = max(0.27, min(0.4, D + 0.14))
        ovh = rs.choice((0.0, 0.02, 0.02))
        er = end_rocks or rs.choice(('both', 'up', 'both'))
        for k in range(npool):
            a, b = bounds[k], bounds[k + 1]
            m = (a + b) / 2
            M = P.M(m)
            hwp = W / 2 + kw + 0.05
            kz.block(mb, M, -hwp, hwp, a - m, b - m, bed[k] - 0.06, bed[k], pave, caps=(lod < 2 or k == 0, lod < 2 or k < npool - 1))
            if k < npool - 1:
                weir(k, b)
            for sd in (-1, 1):
                x0, x1 = (W / 2, W / 2 + kw) if sd > 0 else (-W / 2 - kw, -W / 2)
                if lod == 2:
                    kz.block(mb, M, x0, x1, a - m, b - m, bed[k], bed[k] + kh, ash[0], caps=(k == 0, True))
                    continue
                for ci, (za, zb_, xo) in enumerate(((bed[k], bed[k] + c1, 0.0), (bed[k] + c1, bed[k] + kh, ovh))):
                    if lod == 1:
                        kz.block(mb, M, x0 - xo, x1 + xo, a - m, b - m, za, zb_, ash[ci], ch=0.012 if ci else 0.0,
                                 caps=(k == 0, True))
                        continue
                    rb = genlib.rng(seed, f'k{k}{sd}{ci}')
                    s_ = a - (rb.uniform(0.2, 0.35) if ci else 0.0)
                    while s_ < b - 0.02:
                        seg = rb.uniform(0.45, 0.8)
                        s0, s1 = max(a, s_), min(b, s_ + seg)
                        s_ += seg
                        if s1 - s0 < 0.08:
                            continue
                        mm = (s0 + s1) / 2
                        kz.block(mb, P.M(mm), x0 - xo, x1 + xo, s0 - mm + 0.004, s1 - mm - 0.004, za, zb_ - 0.003,
                                 ash[int(rb.random() * 3)], ch=0.014 if ci else 0.006, ch_end=0.008)
        # rock clusters at the ends only
        ends = [] if er == 'none' else ([0.0] if (er == 'up' or lod == 2) else [0.0, L])
        for e in ends:
            k = 0 if e == 0.0 else npool - 1
            for sd in (-1, 1):
                rr = genlib.rng(seed, f'end{e}{sd}')
                parts = [(0.2, 0.22, 0.36, 0.0)] + ([(0.12, 0.13, 0.2, 0.28)] if lod == 0 else [])
                if e > 0:
                    parts = [(0.15, 0.16, 0.24, 0.0)]
                for i, (rx, ry, hab, ds) in enumerate(parts):
                    s = min(L - 0.05, max(0.05, e + (ry * 0.7 + ds if e == 0 else -ry * 0.7 - ds)))
                    u = sd * (W / 2 + kw + rx * 0.75 + rr.uniform(-0.03, 0.03))
                    nsd, bands = ((7, 3) if i == 0 else (6, 2)) if lod == 0 else ((6, 2) if lod == 1 else (5, 1))
                    if lod == 2 and i:
                        continue
                    kz.crag_rock(mb, P.M(s, u, 0, yaw=rr.uniform(-0.5, 0.5)), rx * rr.uniform(0.9, 1.15), ry,
                                 bed[k] - 0.06, bed[k] + hab * rr.uniform(0.85, 1.15), rocks[i % 2], rr, nside=nsd, bands=bands)
        return _finish(mb, P, style, W, D, L, npool, bounds, events, zw, bed, gz, seed, lod, edge=W / 2 + kw + 0.4)

    # ---------------------------------------------------------------- STEPPED
    rs = genlib.rng(seed, 'shape')
    kw = rs.uniform(0.16, 0.2)
    wall_up = rs.uniform(0.2, 0.23)                # wall top above each tread (<= 0.25)
    c1 = 0.07
    er = end_rocks or rs.choice(('both', 'up'))
    T = list(bed)                                   # tread tops; the water sheet (D) runs over them
    for k in range(npool):
        a, b = bounds[k], bounds[k + 1]
        m = (a + b) / 2
        M = P.M(m)
        zb = (T[k + 1] - 0.04) if k < npool - 1 else T[k] - 0.07
        if lod == 2:
            kz.tread(mb, M, -W / 2 - 0.02, W / 2 + 0.02, a - m, b - m, T[k + 1] if k < npool - 1 else zb, T[k], ash[0],
                     nose=0.0, lip_t=0.0, round_=False)
        else:
            kz.tread(mb, M, -W / 2 - 0.03, W / 2 + 0.03, a - m, b - m, zb, T[k], lipm, nose=0.05,
                     lip_t=0.06, round_=(lod == 0))
        for sd in (-1, 1):
            x0, x1 = (W / 2, W / 2 + kw) if sd > 0 else (-W / 2 - kw, -W / 2)
            if lod == 2:
                continue
            if lod == 1:
                kz.block(mb, M, x0, x1, a - m, b - m, zb, T[k] + wall_up, ash[(k + (sd > 0)) % 3], ch=0.012)
                continue
    if lod == 0:
        # coursed ashlar side walls: courses one drop (0.17 m) high, aligned so every wall top is a course line;
        # running bond, capstones chamfered; the wall steps down with the treads (sheet side view)
        bot = [(T[k + 1] - 0.04) if k < npool - 1 else T[k] - 0.07 for k in range(npool)]
        top = [T[k] + wall_up for k in range(npool)]
        nc = int(math.ceil((top[-1] - min(bot)) / dr - 1e-6))
        zbase = top[-1] - nc * dr
        for sd in (-1, 1):
            x0, x1 = (W / 2, W / 2 + kw) if sd > 0 else (-W / 2 - kw, -W / 2)
            rb = genlib.rng(seed, f'wall{sd}')
            i = 0
            while zbase + i * dr < max(top) - 0.01:
                zc0, zc1 = zbase + i * dr, zbase + (i + 1) * dr
                runs = []
                for k in range(npool):
                    lo, hi = max(zc0, bot[k]), min(zc1, top[k])
                    if hi - lo < 0.03:
                        continue
                    cap = abs(hi - top[k]) < 1e-4
                    if runs and abs(runs[-1][2] - lo) < 1e-4 and abs(runs[-1][3] - hi) < 1e-4 and runs[-1][4] == cap \
                            and abs(runs[-1][1] - bounds[k]) < 1e-6:
                        runs[-1][1] = bounds[k + 1]
                    else:
                        runs.append([bounds[k], bounds[k + 1], lo, hi, cap])
                for s0r, s1r, lo, hi, cap in runs:
                    s_ = s0r - (rb.uniform(0.1, 0.18) if i % 2 else 0.0)
                    while s_ < s1r - 0.02:
                        seg = rb.uniform(0.26, 0.42)
                        b0, b1 = max(s0r, s_), min(s1r, s_ + seg)
                        s_ += seg
                        if b1 - b0 < 0.06:
                            continue
                        mm = (b0 + b1) / 2
                        xo = 0.012 if cap else 0.0
                        kz.block(mb, P.M(mm), x0 - xo, x1 + xo, b0 - mm + 0.004, b1 - mm - 0.004, lo + 0.003, hi,
                                 ash[int(rb.random() * 3)], ch=0.014 if cap else 0.0)
                i += 1
    if lod == 2:
        # walls as stepped ribbons (tops + wall-top risers + inner faces above the treads)
        bm = mb.bm
        for sd in (-1, 1):
            xi, xo = sd * W / 2, sd * (W / 2 + kw)
            tops = []
            for k in range(npool):
                for s in (bounds[k], bounds[k + 1]):
                    tops.append((s, T[k] + wall_up))
            A = [bm.verts.new(P.pt(s, xi, z)) for s, z in tops]
            B = [bm.verts.new(P.pt(s, xo, z)) for s, z in tops]
            fs = [bm.faces.new((A[i], A[i + 1], B[i + 1], B[i])) for i in range(len(tops) - 1)]
            for k in range(npool):
                fs.append(bm.faces.new((A[2 * k], A[2 * k + 1], bm.verts.new(P.pt(bounds[k + 1], xi, T[k])),
                                        bm.verts.new(P.pt(bounds[k], xi, T[k])))))
            mb._tag(fs, ash[1])
    # craggy rock masses flanking the head (and the foot)
    ends = [0.0] if er == 'up' else [0.0, L]
    for e in ends:
        for sd in (-1, 1):
            rr = genlib.rng(seed, f'end{e}{sd}')
            if e == 0.0:
                rx, ry, zt = rr.uniform(0.2, 0.26), rr.uniform(0.22, 0.28), T[0] + wall_up + rr.uniform(0.03, 0.14)
                zt = min(zt, T[-1] - 0.07 + 1.03)            # stay inside the 1.0 m proxy height
                s, k = ry * 0.8, 0
            else:
                if rr.random() < 0.5 and lod > 0:
                    continue
                rx, ry, zt = rr.uniform(0.15, 0.2), rr.uniform(0.16, 0.2), T[-1] + wall_up + rr.uniform(0.0, 0.1)
                s, k = L - ry * 0.8, npool - 1
            zb = (T[1] - 0.04) if e == 0.0 and npool > 1 else T[-1] - 0.07
            nsd, bands = ((7, 2) if e == 0.0 else (6, 2)) if lod == 0 else ((6, 2) if lod == 1 else (5, 1))
            if lod == 2 and (e > 0 or sd > 0):
                continue
            kz.crag_rock(mb, P.M(s, sd * (W / 2 + kw + rx * 0.7), 0, yaw=rr.uniform(-0.4, 0.4)), rx, ry, zb, zt,
                         rocks[(sd > 0)], rr, nside=nsd, bands=bands)
    return _finish(mb, P, style, W, D, L, npool, bounds, events, zw, bed, gz, seed, lod, edge=W / 2 + kw + 0.45,
                   treads=T)


def _finish(mb, P, style, W, D, L, npool, bounds, events, zw, bed, gz, seed, lod, edge=None, treads=None, wfn=None):
    o = mb.to_object(ASSET)
    me = o.data
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    dx, dy, dz = -(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, -min(zs)
    for v in me.vertices:
        v.co.x += dx; v.co.y += dy; v.co.z += dz
    genlib.finish(o, smooth_angle=34)
    kz.uv_island_jitter(o, genlib.rng(seed, 'uv'))
    if style == 'stepped':
        zwat = [t + D for t in (treads or bed)]
    else:
        zwat = zw
    wp = []
    for k in range(npool):
        for s_ in (bounds[k], bounds[k + 1]):
            p = P.at(s_)[0]
            wp.append([round(p.x + dx, 3), round(p.y + dy, 3), round(zwat[k] + dz, 3)])
    o['kz_style'] = style
    o['kz_width'] = round(W, 3)
    o['kz_depth'] = round(D, 3)
    o['kz_water_path'] = json.dumps(wp)
    o['kz_weirs'] = json.dumps([[round(P.at(e)[0].x + dx, 3), round(P.at(e)[0].y + dy, 3), round(zwat[k] + dz, 3),
                                 round(zwat[k + 1] + dz, 3)] for k, e in enumerate(events)])
    o['kz_ground_z'] = round(gz[0] + dz, 3)
    gp = []
    for k in range(npool):
        a, b = P.at(bounds[k])[0], P.at(bounds[k + 1])[0]
        gp.append([round(a.x + dx, 3), round(a.y + dy, 3), round(b.x + dx, 3), round(b.y + dy, 3), round(gz[k] + dz, 3)])
    o['kz_ground_profile'] = json.dumps(gp)
    cl = []
    n = max(2, int(math.ceil(L / 0.25)))
    for i in range(n + 1):
        s_ = L * i / n
        p = P.at(s_)[0]
        cl.append([round(p.x + dx, 3), round(p.y + dy, 3), round((wfn(s_) if wfn else W) / 2, 3)])
    o['kz_centerline'] = json.dumps(cl)
    o['kz_pool_s'] = json.dumps([round(b, 3) for b in bounds])
    o['kz_edge_half_width'] = round(edge if edge else W / 2 + 0.3, 3)
    o['kz_tris_per_m'] = round(genlib.tris(o) / max(L, 0.01), 1)
    return o
