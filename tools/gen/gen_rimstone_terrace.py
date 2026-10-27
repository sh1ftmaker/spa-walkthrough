"""Rimstone scallop terrace field (b3_rimstone): stacked white travertine trays with scalloped rims, each
teal pool spilling over a curtain-like flowstone lip into the next.

Concepts: refs/gen/sheet-mod-water.png #2 (module 8 m W x 6 m D: two tiers, an upper round-scalloped tray
behind and above a wider lower tray; the lips are pale cream travertine with hanging drip drapery, a thin
rounded crest, the curtain bulging outwards as it drops; side view: the tier drop is ~ the curtain height,
dark basalt boulders flank the trays), lookbook/img/18-rimstone-terraces.jpg (bathers ~1.7 m: tier drops
0.4-0.7 m, pools 0.4-0.6 m deep, trays 3-9 m across, lobes 1-4 m radius, water sheets over most of the
downstream lip), refs/gen/mat-rimstone.png (close-up: cauliflower nodules on the crest, pendant drips 0.1-
0.3 m long at ~0.2-0.35 m pitch), refs/gen/dh-rimstone.png (field of ~13 tiers on a 30 x 35 m slope).

Targets (default module, seed 1): 8.0 x 6.0 m footprint (proxy 8 x 6), 2 tiers, tier drop 0.5 m, so
  h ~1.05 m (proxy h 0.6 only holds one tier: proposed proxy h 1.15); pool depth 0.42 m under the crest,
  water 0.03 m under the crest; crest bead 0.07 m proud, curtain bulging 0.10 -> 0.28 m out at the foot;
  drip flutes at 0.38-0.52 m pitch 0.11 m deep, pendants 0.05-0.12 m; downstream scallop lobes 1.6-2.5 m
  wide (scallop_r 0.9-1.4 default), 0.45-0.7 m deep cusps; outline points concentrated on the downstream side.
Parameters: field (W, D) default (8, 6) (the full field: tiers=13, field=(30, 35)); tiers default 2;
  tier_drop 0.5; scallop_r 1-4 (lobe radius); depth 0.42; curtain (h, defaults to the tier drop);
  flow_axis (recorded; the build always flows to +Y = the asset front, rotate the instance); terrain 'flat' (module: feet on z = 0 outside
  the lower pools) | 'stepped' (field: each tier stands on the ground of its own step); style.
Styles (C.cycle): stacked (one tray per tier, centred), offset (upper tray shifted sideways, wider lower
  tray wrapping it), split (the lower tier is two trays side by side, both fed by the upper). Seeds also
  change tray proportions, lobe count / width, crest wobble, drip pitch and pendant length, spill patches.
Materials (slots by part): m_rim rimstone (crest, lips, curtain), m_floor sinter (pool floors and inner
  walls), m_spill waterfall (thin single-sided spill sheets 2.5 cm off the curtain on the spill patches:
  the row's 'shader spill sheets on lips'; vertex attribute '_flow' 0 at the crest -> 1 at the foot).
Water: not built. kz_pools (JSON [{level, outline, floor}] per tray), kz_spill_lips (JSON [{tray, lip:
  [[x, y, z]], to}]), kz_water_level (top pool), kz_ground_profile, kz_lights (teal uplights under every
  spill patch, 7500 K 40 W, plus the row's emissive uplights), kz_anim.
LODs from one layout: outline points are shared out by tray perimeter (module totals 220 / 110 / 48 / 22,
  LOD3 18; i.e. the budget is met per 2-tray module; a full field scales with its tray count): LOD0 10 section rings +
  spill strips; LOD1 8; LOD2 5 (floor, crest, bulge, curtain, foot) + strips; LOD3 3 (floor fan, crest, foot).
Pivot: bbox centre x/y, z = 0 at the lowest foot. Front +Y = downstream.
Single-sided: spill sheets (render double-sided). Everything else is a closed-over-the-ground shell with an
open base (sits in the place terrain).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'rimstone_terrace'
FEATURES = ['stacked scalloped white travertine rims', 'each teal pool (data) spilling over a curtain-like lip',
            'flowstone curtain with hanging drips']
STYLES = ['stacked', 'offset', 'split']
PROXY_SHEET = dict(w=8.0, d=6.0, h=1.15)      # proposed: the stock proxy h 0.6 holds one tier only


def _trays(seed, W, D, tiers, style, scallop_r):
    g = C.rng(seed, 'trays')
    band = D / tiers
    out = []
    for k in range(tiers):
        if tiers <= 3:
            if style == 'split' and k == tiers - 1:
                n = 2
            else:
                n = 1
        else:
            n = max(1, int(round(W / g.uniform(5.0, 8.5))))
        wfac = 0.78 if k < tiers - 1 else 1.0
        for i in range(n):
            tw = W / n * (g.uniform(0.92, 1.0) if n == 1 else g.uniform(1.0, 1.08)) * (wfac if n == 1 else 1.0)
            tw = min(tw, W)
            td = band * (1.55 if tiers <= 3 else 1.6) * g.uniform(0.94, 1.0)
            xs = -W / 2 + W / n * (i + 0.5)
            if n == 1:
                xs = 0.0
                if style == 'offset' and k < tiers - 1:
                    xs = (W - tw) / 2 * g.choice([-1, 1]) * g.uniform(0.7, 1.0)
            if tiers > 3 and k % 2:
                xs += W / n * 0.25
            xs = max(-W / 2 + tw / 2, min(W / 2 - tw / 2, xs))
            ys = -D / 2 + band * (k + 0.5) + (td - band) * 0.5 * (1 if k == tiers - 1 else 0.0)
            ys = max(-D / 2 + td / 2, min(D / 2 - td / 2, ys))
            sr = scallop_r or g.uniform(0.9, 1.4)
            nl = max(1, int(round(tw / (1.8 * sr))))
            out.append(dict(tier=k, cx=xs, cy=ys, a=tw / 2, b=td / 2, n=g.uniform(2.4, 3.2), lobes=nl,
                            lw=tw / nl, lph=g.uniform(-0.25, 0.25), amp=g.uniform(0.45, 0.7),
                            wob=g.uniform(0.04, 0.09), lam=g.uniform(0.38, 0.52), pend=g.uniform(0.05, 0.12),
                            noff=Vector((g.uniform(0, 80), g.uniform(0, 80), g.uniform(0, 80))),
                            sp=g.uniform(0, 50)))
    return out


def _outline(t, N):
    """N points, outward normals, arc length, and a 0..1 'front' weight (downstream side)"""
    # sample densely on the downstream (visible, spilling) side: density 0.35 + 1.8 * front
    M = 720
    dens = [0.35 + 1.8 * max(0.0, math.sin(2 * math.pi * j / M)) ** 1.2 for j in range(M)]
    cum = [0.0]
    for d_ in dens:
        cum.append(cum[-1] + d_)
    ths, j = [], 0
    for i in range(N):
        target = cum[-1] * i / N
        while cum[j + 1] < target:
            j += 1
        ths.append(2 * math.pi * (j + (target - cum[j]) / dens[j]) / M)
    pts = []
    for i in range(N):
        th = ths[i]
        c, s = math.cos(th), math.sin(th)
        e = 2.0 / t['n']
        x = t['a'] * math.copysign(abs(c) ** e, c)
        y = t['b'] * math.copysign(abs(s) ** e, s)
        front = max(0.0, s) ** 1.2
        # scallops: rounded lobes on the downstream edge, cusps between them
        u = (x + t['a']) / t['lw'] + t['lph']
        lobe = abs(math.cos(math.pi * (u - 0.5))) ** 0.4 - 0.55
        rr = 1.0
        L = math.hypot(x, y) or 1.0
        bump = t['amp'] * front * lobe + t['wob'] * noise.noise(Vector((c * 2.0, s * 2.0, 0.0)) + t['noff'])
        x += x / L * bump * rr
        y += y / L * bump * rr * 1.4
        pts.append(Vector((t['cx'] + x, t['cy'] + y, 0.0)))
    nrm, arc, acc = [], [], 0.0
    for i in range(N):
        a, b = pts[i - 1], pts[(i + 1) % N]
        tng = (b - a)
        n = Vector((tng.y, -tng.x, 0.0)).normalized()
        if n.dot(pts[i] - Vector((t['cx'], t['cy'], 0))) < 0:
            n = -n
        nrm.append(n)
        arc.append(acc)
        acc += (pts[(i + 1) % N] - pts[i]).length
    fr = [max(0.0, (p.y - t['cy']) / t['b']) for p in pts]
    return pts, nrm, arc, fr


def _inside(x, y, poly):
    ins = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            ins = not ins
    return ins


def build(lod, seed, field=None, tiers=None, tier_drop=0.5, scallop_r=None, depth=0.42, curtain=None,
          flow_axis='y', terrain=None, style=None):
    style = style or C.cycle(seed, STYLES)
    tiers = tiers or 2
    W, D = field or ((8.0, 6.0) if tiers <= 3 else (30.0, 35.0))
    terrain = terrain or ('flat' if tiers <= 3 else 'stepped')
    drop = tier_drop
    trays = _trays(seed, W - 0.75, D - 1.0, tiers, style, scallop_r)   # inset: lobes + foot flare stay inside W x D
    mb = genlib.MeshBuilder()
    m_rim = mb.slot('rimstone')
    m_floor = mb.slot('sinter', wetness=0.9)
    m_spill = mb.slot('waterfall')
    bm = mb.bm
    flow = bm.verts.layers.float.new('_flow')

    # outline points shared out by tray perimeter so the module stays inside one budget (per-pt tris ~22/17/11/5)
    per = [2 * math.pi * math.sqrt((t['a'] ** 2 + t['b'] ** 2) / 2) for t in trays]
    tot = C.lod_pick(lod, 220, 110, 48, 18) * (1 if tiers <= 3 else len(trays) / 2.0)
    Ns = [max(C.lod_pick(lod, 48, 24, 12, 6), int(tot * q / sum(per)) // 2 * 2) for q in per]
    ground = lambda k: (tiers - 1 - k) * drop
    rim = lambda k: ground(k) + (curtain or drop)
    # coarse outlines of every tray (for the foot test), independent of LOD
    coarse = []
    for t in trays:
        P, _, _, _ = _outline(t, 48)
        coarse.append([(p.x, p.y) for p in P])
    pools, spills, lights = [], [], []
    for ti, t in enumerate(trays):
        k = t['tier']
        top = rim(k)
        floor = top - depth
        N = Ns[ti]
        P, Nn, S, FR = _outline(t, N)
        ctr = Vector((t['cx'], t['cy'], 0))
        lower = [j for j, u in enumerate(trays) if u['tier'] == k + 1]

        def foot_z(p):
            for j in lower:
                if _inside(p.x, p.y, coarse[j]):
                    return rim(k + 1) - depth
            return ground(k) if terrain == 'stepped' else 0.0
        rings = []      # list of lists of verts
        spec = C.lod_pick(lod,
                          ['floor', 'iwall', 'ilip', 'crest', 'bulge', 'c1', 'c2', 'c3', 'c4', 'foot'],
                          ['floor', 'iwall', 'crest', 'bulge', 'c1', 'c2', 'c3', 'foot'],
                          ['floor', 'crest', 'bulge', 'c2', 'foot'],
                          ['floor', 'crest', 'foot'])
        feet = [foot_z(P[i] + Nn[i] * 0.25) for i in range(N)]
        for name in spec:
            ring = []
            for i in range(N):
                p, n, s = P[i], Nn[i], S[i]
                fz = feet[i]
                hc = max(0.05, top - fz)
                rib = (0.5 + 0.5 * math.cos(2 * math.pi * s / t['lam'] + 0.7 * noise.noise(Vector((s * 0.9, 0, 0)) + t['noff']))) ** 3
                q = Vector((s * 1.3, ti * 3.1, 0.0)) + t['noff']
                nod = noise.noise(q) * 0.5 + 0.5          # cauliflower nodules on the crest / lips
                if lod >= 2:
                    rib, nod = 0.5, 0.5
                if name == 'floor':
                    v = ctr + (p - ctr) * 0.72; z = floor
                elif name == 'iwall':
                    v = p - n * 0.2; z = floor + 0.16
                elif name == 'ilip':
                    v = p - n * 0.07; z = top - 0.035
                elif name == 'crest':
                    v = p + n * 0.01 * nod; z = top + 0.02 * nod
                elif name == 'bulge':
                    v = p + n * (0.07 + 0.03 * nod); z = top - 0.07 - 0.02 * nod
                elif name in ('c1', 'c2', 'c3', 'c4'):
                    f = {'c1': 0.22, 'c2': 0.45, 'c3': 0.68, 'c4': 0.86}[name]
                    out = 0.10 + 0.14 * f + 0.11 * rib * (0.5 + f)
                    z = top - 0.07 - (hc - 0.07) * f - t['pend'] * rib * math.sin(math.pi * min(1.0, f * 1.1))
                    v = p + n * out
                else:   # foot
                    v = p + n * (0.28 + 0.04 * nod); z = fz
                vv = bm.verts.new((v.x, v.y, z))
                vv[flow] = 0.0
                ring.append(vv)
            rings.append(ring)
        # floor fan
        cv = bm.verts.new((ctr.x, ctr.y, floor - 0.02))
        for i in range(N):
            f = bm.faces.new((cv, rings[0][i], rings[0][(i + 1) % N])); f.material_index = m_floor
        for r_ in range(len(rings) - 1):
            mi = m_floor if spec[r_] in ('floor', 'iwall') and spec[r_ + 1] in ('iwall', 'ilip') else m_rim
            for f in C.bridge_rings(bm, rings[r_], rings[r_ + 1]):
                f.material_index = mi
        # ---- spill sheets on the downstream patches (thin water skins over the curtain)
        on = [FR[i] > 0.25 and noise.noise(Vector((S[i] * 0.45 + t['sp'], 0.5, 0.0))) > -0.15 for i in range(N)]
        sheet_rings = [r_ for r_, nm in enumerate(spec) if nm in ('crest', 'bulge', 'c1', 'c2', 'c3', 'c4', 'foot')]
        runs, cur = [], []
        for i in range(N):
            if on[i]:
                cur.append(i)
            elif cur:
                runs.append(cur); cur = []
        if cur:
            if runs and runs[0][0] == 0:
                runs[0] = cur + runs[0]
            else:
                runs.append(cur)
        for run in runs:
            if len(run) < 3:
                continue
            cols = []
            for i in run:
                col = []
                n = Nn[i]
                for jj, r_ in enumerate(sheet_rings):
                    src = rings[r_][i].co
                    fr = jj / (len(sheet_rings) - 1)
                    z = src.z + (0.03 if jj == 0 else 0.0)
                    if spec[r_] == 'foot':
                        z = feet[i] + (0.0 if terrain == 'stepped' or feet[i] > 0 else 0.0)
                    vv = bm.verts.new((src.x + n.x * 0.025, src.y + n.y * 0.025, z))
                    vv[flow] = fr
                    col.append(vv)
                cols.append(col)
            for a_, b_ in zip(cols[:-1], cols[1:]):
                for jj in range(len(sheet_rings) - 1):
                    f = bm.faces.new((a_[jj], b_[jj], b_[jj + 1], a_[jj + 1])); f.material_index = m_spill
            mid = run[len(run) // 2]
            lights.append(C.light_entry(P[mid] + Nn[mid] * 0.6 + Vector((0, 0, feet[mid] + 0.05)), color_k=7500, watts=40,
                                        role='spill uplight', color=(0.35, 0.95, 0.85)))
            spills.append(dict(tray=ti, lip=[[round(P[i].x, 3), round(P[i].y, 3), round(top, 3)] for i in run[::max(1, len(run) // 8)]],
                               to=round(feet[mid], 3)))
        pools.append(dict(tray=ti, tier=k, level=round(top - 0.03, 3), floor=round(floor, 3),
                          outline=[[round(P[i].x - Nn[i].x * 0.04, 3), round(P[i].y - Nn[i].y * 0.04, 3)] for i in range(0, N, max(1, N // 40))]))

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=50)
    for p in pools:
        p['level'] = round(p['level'] + dz, 3); p['floor'] = round(p['floor'] + dz, 3)
        p['outline'] = [[round(x + dx, 3), round(y + dy, 3)] for x, y in p['outline']]
    for s in spills:
        s['lip'] = [[round(x + dx, 3), round(y + dy, 3), round(z + dz, 3)] for x, y, z in s['lip']]; s['to'] = round(s['to'] + dz, 3)
    for L_ in lights:
        L_['pos'] = [round(L_['pos'][0] + dx, 3), round(L_['pos'][1] + dy, 3), round(L_['pos'][2] + dz, 3)]
    o['kz_water_level'] = pools[0]['level']
    C.set_json_props(o, kz_pools=pools, kz_spill_lips=spills, kz_lights=lights, kz_style=style,
                     kz_ground_profile=[[k, round(ground(k) + dz if terrain == 'stepped' else dz, 3)] for k in range(tiers)],
                     kz_anim=dict(type='shader', what='spill sheets on lips', slot='waterfall', attr='_flow'),
                     kz_params=dict(field=[W, D], tiers=tiers, tier_drop=drop, depth=depth, trays=len(trays),
                                    flow_axis=flow_axis, terrain=terrain))
    return o
