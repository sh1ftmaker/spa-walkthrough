"""Lift car: cylindrical glass-and-bronze cabin of the main lift (sheet-vs-lift-cable #2, ref-spiral-stair, ref-b1-lobby).

Identifying features kept at every LOD: cylindrical clear-glass cabin, dark bronze frame with polished bands
(base and under the cornice), lit sunburst ceiling, shallow dome with a turned hub + guide rods, front sliding door
with a centre seam.
Style matches gen_lift_drum: blackened bronze, polished gold edges, key-fret lattice (the drum's balustrade fret).

Construction (round 2)
  * Base: dark plinth with a 0.18 m polished brass band; hinoki floor disc with two brass inlay rings + medallion;
    dark bronze threshold.
  * Glazing: N curved clear panes (closed thin shells; glass_clear when the library has it, else lava_glass set
    clear) between slim blackened-bronze mullions; heavier jambs at the door.
  * Rings: `rings` bands in total (3-6): base band + cornice band always, then 1-4 thin polished rings on the
    glass (waist 0.95 m first). Rings stop at the jambs; each door leaf carries matching ring segments, so the
    closed car reads continuous.
  * Inside: a continuous 0.9 m key-fret band (one interlocking-key unit per bay, as lift_drum's balustrade)
    behind the glass, topped by a polished brass handrail ring at 0.95 m on brackets.
  * Ceiling: a dished lit disc (washi_backlit, high emissive) sloping down to a bronze boss, 16 polished radial
    spokes and a rim, so it reads through the glass from eye height; seeds add an inner ring or a kumiko
    grid overlay. Two vertical bronze-framed lanterns (0.12 x 0.35 m, lit at 2.0 m) on the door jambs.
  * Roof: cornice (0.12 m polished band under a dark overhang), dome (low | tall | onion) with polished rib
    straps, turned hub (r 0.25, h 0.18) with 2 or 4 guide rods rising to the top and 1-2 sheave wheels.

Parameters build(lod, seed, **p)
  r        outer radius of the cabin 1.2-1.6 (seeded 1.25-1.42; door lanterns add 0.13 m)  h  total 2.6-3.0
  rings    bands in total 3-6 (seeded)        door_w   door opening 0.9-1.3 (default 1.05)
  bays     glazing bays (seeded 10-15)        ceiling  sunburst | rings | kumiko overlay (seed % 3)
  dome     low | tall | onion (seeded)        rods     2 | 4 guide rods (seeded)
  doors_open  0..1 (default 0 = closed; the runtime animates the leaves instead)
Pivot: car axis at the floor of the base (z = 0); +Y = the door.

Animation (rigid, the web runtime animates it):
  * Whole object: vertical travel between layout.json main_lift.stops (timed loop) -> obj['kz_anim'].
  * Doors: vertex groups 'door_L' (+X leaf) and 'door_R' (-X leaf), glass + frame + ring segments + pull.
    They open by ROTATING about the car axis (object Z through the pivot), sliding round just inside the fixed
    glazing (leaf radius r_glass - 0.03, inside the panes and clear of the fret band): obj['kz_anim']['doors']
    ['open_deg'] gives the right-handed rotation about +Z (door_L negative, door_R positive).
Lights: obj['kz_light'] = ceiling light (pos, colour, watts, radius) for the SH probe; obj['kz_lights'] = ceiling +
the two door lanterns. Emissive slots in obj['kz_glow_slots']. Lighting: probe (moving) + emissive.
"""
import json
import math

from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_lift_drum as G
import kzgeo_spiral_stair as S

ASSET = 'lift_car'
FEATURES = ['cylindrical clear-glass cabin', 'dark bronze frame with polished bands', 'lit sunburst ceiling',
            'shallow dome with hub and guide rods', 'front sliding door with centre seam']
WARM = (1.0, 0.6, 0.3)
LODS = {
    0: dict(seg=40, gseg=3, fret='key', rail=True, lamps=True, spokes=16, ribs=8, sheave=14, inlay=True),
    1: dict(seg=26, gseg=1, fret='simple', rail=True, lamps=True, spokes=8, ribs=6, sheave=8, inlay=False),
    2: dict(seg=12, gseg=1, fret='band', rail=False, lamps=False, spokes=0, ribs=0, sheave=6, inlay=False),
    3: dict(seg=9, gseg=1, fret=None, rail=False, lamps=False, spokes=0, ribs=0, sheave=0, inlay=False),
}


def _params(seed, p):
    r = genlib.rng(seed, ASSET)
    pr = genlib.proxy(ASSET)
    D = {}
    D['dome'] = p.get('dome') or ['onion', 'low', 'tall'][seed % 3]
    # body = plinth to top of cornice; crown (hub + rods) 0.45 m above the dome; total <= ~3.5 m (proxy 3.4)
    D['dome_h'] = {'low': 0.2, 'tall': 0.36, 'onion': 0.55}[D['dome']]
    body = float(p.get('body') or r.uniform(2.6, 2.9))
    D['body'] = round(min(body, (p.get('h') or 3.5) - D['dome_h'] - 0.45), 3)
    # tall, not squat: body / diameter >= 1.1
    D['R'] = round(min(float(p.get('r') or r.uniform(1.15, 1.3)), D['body'] / 2.2), 3)
    D['h'] = D['body'] + D['dome_h'] + 0.45
    D['dado'] = float(p.get('dado') or r.uniform(0.6, 1.0))         # fret band (kumiko dado) height
    D['rings'] = int(p.get('rings') or [4, 3, 6, 5][seed % 4])
    D['door_w'] = float(p.get('door_w') or 1.05)
    D['bays'] = int(p.get('bays') or [8, 11, 13, 10][seed % 4])
    D['ceiling'] = p.get('ceiling') or ['kumiko', 'sunburst', 'rings'][seed % 3]
    D['rods'] = 4
    D['sheaves'] = 2
    D['base_h'] = 0.2
    D['cornice_h'] = r.uniform(0.18, 0.22)
    D['doors_open'] = float(p.get('doors_open') or 0.0)
    D['rng'] = r
    return D


def _glass(mb):
    if 'glass_clear' in genlib.matlib.manifest():
        return mb.slot('glass_clear')
    return mb.slot('lava_glass', tint=(1.0, 1.0, 1.0), normal_strength=0.0, roughness_offset=-1.0)


def build(lod, seed, **p):
    D = _params(seed, p)
    C = LODS[min(lod, 3)]
    R, h = D['R'], D['h']
    rg = R - 0.09                                  # glass radius
    mb = genlib.MeshBuilder()
    bm = mb.bm
    bm.faces.layers.float_vector.new('kz_n')
    M = dict(
        # blackened bronze frame + polished gold bands (lift_drum look; the library bronze is being darkened)
        # library bronze is blackened; normal_strength 0.03 (<10 % of the default 0.35) = smooth, not hammered foil
        frame=mb.slot('bronze', wear=0.0, normal_strength=0.03),
        polish=mb.slot('bronze', wear=1.0, roughness_offset=-0.15, normal_strength=0.03),
        dark=mb.slot('lacquer_black', wear=0.1) if 'lacquer_black' in genlib.matlib.manifest() else mb.slot('lacquer_dark', wear=0.1),
        glass=_glass(mb),
        glow=mb.slot('washi_backlit', emissive_level=1.5),
        washi=mb.slot('washi_backlit', emissive_level=2.2),
        core=mb.slot('washi_backlit', emissive_level=0.5),                          # LOD2/3 warm inner shell
        wood=mb.slot('hinoki'),
    )
    info = dict(lights=[], groups={})
    seg = C['seg']
    zb = D['base_h']
    dome_h = D['dome_h']
    zc1 = D['body']
    zdome1 = zc1 + dome_h
    zc0 = zc1 - D['cornice_h']
    door_a = D['door_w'] / rg
    fixed = 2 * math.pi - door_a
    N = D['bays']
    bays = [(door_a / 2 + fixed * i / N, door_a / 2 + fixed * (i + 1) / N) for i in range(N)]
    if lod == 3:
        _lod3(bm, mb, M, D, R, rg, zb, zc0, zc1, zdome1, h, info)
        return _finish(mb, M, D, info, door_a)
    # ------------------------------------------------------------------ base: dark plinth + 0.18 m polished band
    if lod == 0:
        base = [(0.0, 0.0), (R - 0.05, 0.0), (R - 0.01, 0.012), (R, 0.02), (R, zb - 0.01), (R - 0.02, zb), (rg - 0.06, zb)]
        mis = [M['dark'], M['dark'], M['frame'], M['polish'], M['polish'], M['frame']]
    else:
        base = [(0.0, 0.0), (R - 0.03, 0.0), (R, 0.02), (R, zb), (rg - 0.06, zb)]
        mis = [M['dark'], M['frame'], M['polish'], M['frame']]
    G.lathe(bm, base, seg, mis)
    G.lathe(bm, [(rg - 0.05, zb - 0.002), (rg - 0.05, zb + 0.01), (0.0, zb + 0.01)], max(12, seg // 2), [M['wood'], M['wood']])
    if C['inlay']:
        for rr in (rg * 0.42, rg * 0.72):
            G.lathe(bm, [(rr + 0.025, zb + 0.0105), (rr - 0.025, zb + 0.0105)], seg // 2, M['polish'])
        G.lathe(bm, [(0.2, zb + 0.011), (0.0, zb + 0.016)], 16, M['polish'])
    # threshold (dark bronze)
    G.lathe(bm, [(rg + 0.03, zb + 0.003), (rg - 0.1, zb + 0.003)], 6, M['frame'], a0=-door_a / 2, a1=door_a / 2, closed=False)
    # ------------------------------------------------------------------ rings on the glass (open at the jambs)
    ring_z = _ring_heights(D['rings'], zb, zc0, D['dado'])
    if lod == 1:
        ring_z = ring_z[:2]
    elif lod == 2:
        ring_z = ring_z[:1]
    ra0, ra1 = door_a / 2, 2 * math.pi - door_a / 2
    rseg = max(6, int(0.75 * seg * (ra1 - ra0) / (2 * math.pi)))
    for z in ring_z:
        G.lathe(bm, _ring_sec(lod, rg + 0.008, R - 0.035, z), rseg, M['polish'], a0=ra0, a1=ra1, closed=False)
    # ------------------------------------------------------------------ glazing + mullions
    gz0, gz1 = zb, zc0
    if lod <= 1:
        for (a0, a1) in bays:
            bs = [a0 + (a1 - a0) * k / C['gseg'] for k in range(C['gseg'] + 1)]
            S.polar_block(bm, rg - 0.006, rg + 0.006, bs, gz1, gz0, M['glass'])
    else:
        pass        # LOD2: no glass shell (it renders as a dark tin in raster previews); the lit core reads instead
    mulls = [b for b, _ in bays] + [bays[-1][1]]
    for k, b in enumerate(mulls):
        is_jamb = k in (0, len(mulls) - 1)
        if lod >= 2 and not is_jamb and k % 3:
            continue
        w = 0.07 if is_jamb else 0.03
        dpt = 0.09 if is_jamb else 0.05
        Mf = G.frame(b, rg + dpt / 2 - 0.02)
        G.obox(bm, Mf, (0, 0, (gz0 + gz1) / 2), (w, dpt, gz1 - gz0), M['frame'])
        if lod == 0:       # polished edge bead on the mullion face
            G.obox(bm, Mf, (0, dpt / 2 + 0.003, (gz0 + gz1) / 2), (0.01 if not is_jamb else 0.02, 0.008, gz1 - gz0 - 0.04), M['polish'])
    # ------------------------------------------------------------------ door leaves (vertex groups), closed by default
    lr = rg - 0.03
    oa = D['doors_open'] * (door_a / 2 + 0.02)
    for side, name in ((-1, 'door_R'), (1, 'door_L')):
        v0 = len(bm.verts)
        a0, a1 = (-door_a / 2 + 0.004, -0.003) if side < 0 else (0.003, door_a / 2 - 0.004)
        a0, a1 = a0 + side * oa, a1 + side * oa
        bs = [a0 + (a1 - a0) * k / max(1, C['gseg']) for k in range(max(1, C['gseg']) + 1)]
        st = 0.045 / lr
        if lod <= 1:
            S.polar_block(bm, lr - 0.006, lr + 0.006, bs, gz1 - 0.03, gz0 + 0.03, M['glass'])
        # frame: outer stile (jamb side), meeting stile (centre seam), bottom + top rail
        outer = (a0, a0 + st) if side < 0 else (a1 - st, a1)
        meet = (a1 - st * 0.8, a1) if side < 0 else (a0, a0 + st * 0.8)
        for (b0, b1) in (outer, meet):
            S.polar_block(bm, lr - 0.018, lr + 0.018, [b0, b1], gz1, gz0, M['frame'])
        if lod <= 1:
            S.polar_block(bm, lr + 0.018, lr + 0.03, [meet[0] + st * 0.2, meet[1] - st * 0.1], gz1 - 0.02, gz0 + 0.02, M['polish'])  # seam astragal
        for z0, z1 in (((gz0, gz0 + 0.12), (gz1 - 0.06, gz1)) if lod <= 1 else ()):
            S.polar_block(bm, lr - 0.018, lr + 0.018, bs, z1, z0, M['frame'])
        # ring segments matching the fixed glazing rings
        for z in ring_z:
            G.lathe(bm, _ring_sec(min(lod, 1), lr + 0.018, lr + 0.05, z), max(2, C['gseg']), M['polish'], a0=a0, a1=a1, closed=False)
        if lod == 0:
            pb = (meet[0] + meet[1]) / 2 + (st * 1.2 if side > 0 else -st * 1.2)
            S.polar_block(bm, lr + 0.02, lr + 0.045, [pb - 0.01, pb + 0.01], 1.45, 0.75, M['polish'])
        info['groups'][name] = (v0, len(bm.verts))
    # ------------------------------------------------------------------ interior fret band + brass handrail
    if C['fret']:
        _fret(bm, M, C, D, bays, rg, zb, seg)
    if C['rail']:
        hr = rg - 0.085
        zr = zb + D['dado'] + 0.03
        a0, a1 = door_a / 2 + 0.05, 2 * math.pi - door_a / 2 - 0.05
        n = max(8, int(seg * (a1 - a0) / (2 * math.pi)))
        samples = [(a0 + (a1 - a0) * j / n, hr, zr) for j in range(n + 1)]
        sec = [(-0.022, -0.02), (0.022, -0.02), (0.022, 0.02), (-0.022, 0.02)] if lod == 0 else \
              [(-0.022, -0.02), (0.022, -0.02), (0.0, 0.025)]
        S.hsweep(bm, samples, sec, M['polish'])
        if lod == 0:
            for b in [bays[i][0] for i in range(1, N, 2)]:
                G.strut(bm, S.polar(hr + 0.015, b, zr - 0.025), S.polar(rg - 0.03, b, zr - 0.025), 0.02, 0.02, M['frame'])
    # ------------------------------------------------------------------ door lanterns on the jambs (outside face)
    if C['lamps']:
        for sx in (-1, 1):
            b = sx * door_a / 2
            Mo = G.frame(b, R + 0.0)
            zl = 1.82
            G.obox(bm, Mo, (0, 0.025, zl + 0.06), (0.03, 0.05, 0.03), M['frame'])          # bracket arm
            G.obox(bm, Mo, (0, 0.075, zl), (0.1, 0.1, 0.32), M['glow'])
            G.obox(bm, Mo, (0, 0.075, zl + 0.18), (0.13, 0.13, 0.035), M['polish'])
            G.obox(bm, Mo, (0, 0.075, zl - 0.175), (0.12, 0.12, 0.03), M['polish'])
            if lod == 0:
                G.obox(bm, Mo, (0, 0.075, zl + 0.215), (0.06, 0.06, 0.04), M['frame'])
                for cx in (-0.05, 0.05):
                    for cy in (-0.05, 0.05):
                        G.obox(bm, Mo, (cx, 0.075 + cy, zl), (0.014, 0.014, 0.32), M['frame'])
            info['lights'].append(dict(pos=[round(c, 3) for c in (Mo @ Vector((0, 0.075, zl)))], color=list(WARM), watts=10))
    # ------------------------------------------------------------------ ceiling
    _ceiling(bm, M, C, D, lod, rg, zc0, info)
    # ------------------------------------------------------------------ cornice (polished 0.12 band), dome, hub
    if lod == 0:
        cor = [(rg - 0.04, zc0 - 0.01), (R - 0.025, zc0), (R - 0.02, zc0 + 0.012), (R - 0.02, zc0 + 0.12), (R + 0.025, zc0 + 0.14),
               (R + 0.025, zc1 - 0.02), (R, zc1)]
        cmis = [M['frame'], M['frame'], M['polish'], M['frame'], M['dark'], M['frame']]
    else:
        cor = [(rg - 0.04, zc0 - 0.01), (R - 0.02, zc0), (R - 0.02, zc0 + 0.12), (R + 0.02, zc1)]
        cmis = [M['frame'], M['polish'], M['dark']]
    G.lathe(bm, cor, seg, cmis)
    dp = _dome_profile(D['dome'], R, zc1, zdome1, lod)
    G.lathe(bm, dp, min(seg, 32), [M['frame']] * (len(dp) - 1))
    if C['ribs']:          # crisp polished ribs (0.03 m) following the dome profile
        for k in range(C['ribs']):
            b = 2 * math.pi * (k + 0.5) / C['ribs']
            samples = [(b, ra + 0.012, za) for ra, za in dp[:-1]]
            S.hsweep(bm, samples, [(-0.004, -0.015), (0.018, 0.0), (-0.004, 0.015)], M['polish'], caps=False)
    if lod == 0:           # rivet rows at 0.15 m pitch on the base band and the cornice band
        for rr, zz in ((R + 0.004, zb * 0.5), (R - 0.016, zc0 + 0.066)):
            n = int(2 * math.pi * rr / 0.15)
            for k in range(n):
                b = 2 * math.pi * (k + 0.5) / n
                if abs(((b + math.pi) % (2 * math.pi)) - math.pi) < door_a / 2 and zz < zb:
                    pass
                c = S.polar(rr, b, zz)
                mb.cylinder(c + S.polar(0.006, b), radius=0.011, radius2=0.0, depth=0.014, mi=M['polish'], segs=4,
                            rot=(math.pi / 2, 0, -b), cap=False)
    # glowing floor ring (0.03 m) and, at LOD2, a faint warm inner shell so the car reads as a lantern far away
    G.lathe(bm, [(rg - 0.12, zb + 0.012), (rg - 0.15, zb + 0.012)], max(12, seg // 2), M['washi'])
    if lod == 2:
        G.lathe(bm, [(rg - 0.02, zb + 0.02), (rg - 0.02, zc0 - 0.02)], seg, M['core'])
    _hub(bm, mb, M, C, D, lod, zdome1, h)
    return _finish(mb, M, D, info, door_a)


def _ring_sec(lod, r0, r1, z):
    if lod <= 1:
        return [(r0, z - 0.02), (r1, z), (r0, z + 0.02)]
    return [(r0, z - 0.03), (r1, z), (r0, z + 0.03)]


def _finish(mb, M, D, info, door_a):
    o = mb.to_object(ASSET)
    G.fix_normals(o)
    genlib.finish(o)
    kg.uv_unit(o, [M['glow']])
    for name, (a, b) in info['groups'].items():
        g = o.vertex_groups.new(name=name)
        g.add(list(range(a, b)), 1.0, 'REPLACE')
    open_deg = round(math.degrees(door_a / 2 + 0.02), 2)
    o['kz_anim'] = json.dumps(dict(
        type='rigid', travel=dict(axis=[0, 0, 1], stops_from='layout.json connections main_lift.stops', mode='timed loop'),
        doors=dict(groups=['door_L', 'door_R'], kind='rotate_about_axis', axis=[0, 0, 1], pivot=[0, 0, 0],
                   open_deg={'door_L': -open_deg, 'door_R': open_deg}, closed_by_default=True,
                   note='leaves slide round just inside the fixed glazing')))
    main = [L for L in info['lights'] if L.get('radius')][0]
    o['kz_light'] = json.dumps(main)
    o['kz_lights'] = json.dumps(info['lights'])
    o['kz_glow_slots'] = json.dumps([M['glow'], M['washi'], M['core']])
    o['kz_params'] = json.dumps({k: v for k, v in D.items() if k != 'rng'})
    return o


def _ring_heights(n, zb, zc0, dado):
    """n bands in total: base and cornice bands always; 1-4 rings on the glass (the first at the dado rail)"""
    zd = zb + dado + 0.03
    cand = [zd, zc0 - 0.3, (zd + zc0 - 0.3) / 2, zb + 0.3]
    return cand[:max(1, n - 2)]


def _dome_profile(kind, R, z0, z1, lod):
    """smooth surface of revolution; 'onion' is a true ogee: swell over the cornice, S-curve in to a 0.15 m neck"""
    H = z1 - z0
    if kind == 'low':
        f = [(1.0, 0.0), (0.97, 0.25), (0.88, 0.5), (0.72, 0.72), (0.5, 0.9), (0.28, 1.0)]
    elif kind == 'tall':
        f = [(1.0, 0.0), (0.98, 0.2), (0.92, 0.42), (0.8, 0.62), (0.6, 0.8), (0.36, 0.94), (0.2, 1.0)]
    else:
        f = [(1.0, 0.0), (1.07, 0.1), (1.08, 0.22), (0.98, 0.36), (0.74, 0.52), (0.42, 0.68), (0.2, 0.82), (0.125, 0.93), (0.125, 1.0)]
    pts = [(R * fr if fr > 0.3 else max(R * fr, 0.15 if kind == 'onion' else R * fr), z0 + H * fz) for fr, fz in f]
    if lod == 1:
        pts = pts[::2] + ([pts[-1]] if len(pts) % 2 == 0 else [])
    elif lod >= 2:
        pts = [pts[0], pts[len(pts) // 2], pts[-1]]
    return pts + [(0.0, z1)]


def _fret(bm, M, C, D, bays, rg, zb, seg):
    """continuous 0.9 m fret band behind the glass. LOD0: lift_drum's interlocking key fret per bay; LOD1: simple
    lattice; LOD2: a dark band."""
    z0, z1 = zb + 0.05, zb + D['dado']
    a0_, a1_ = bays[0][0], bays[-1][1]
    if C['fret'] != 'band':
        # solid dark kick panel under the lattice; the key fret fills the upper 0.5 m (denser, as on the drum)
        kick = (z1 - z0) * 0.4
        G.lathe(bm, [(rg - 0.03, z0), (rg - 0.03, z0 + kick)], max(6, seg - 4), M['frame'], a0=a0_, a1=a1_, closed=False)
        z0 = z0 + kick
    if C['fret'] == 'band':
        a0, a1 = bays[0][0], bays[-1][1]
        G.lathe(bm, [(rg - 0.03, z0), (rg - 0.03, z1)], max(6, seg - 2), M['frame'], a0=a0, a1=a1, closed=False)
        return
    hgt = z1 - z0
    for (a0, a1) in bays:
        am = (a0 + a1) / 2
        w = 2 * (rg - 0.035) * math.sin((a1 - a0) / 2) - 0.035
        Mb = G.frame(am, (rg - 0.035) * math.cos((a1 - a0) / 2))
        for zz in (z0 + 0.015, z1 - 0.015):
            G.bar(bm, Mb, (-w / 2, zz), (w / 2, zz), 0.03, 0.022, M['frame'], y=-0.022)
        if C['fret'] == 'simple':
            for x in (-w * 0.25, w * 0.25):
                G.bar(bm, Mb, (x, z0), (x, z1), 0.022, 0.02, M['polish'], y=-0.022)
            continue
        U = lambda u, v: (-w / 2 + u * w, z0 + 0.03 + v * (hgt - 0.06))
        segs = [((0.0, 0.5), (0.3, 0.5)), ((0.3, 0.5), (0.3, 0.2)), ((0.3, 0.2), (0.7, 0.2)), ((0.7, 0.2), (0.7, 0.62)),
                ((0.7, 0.62), (0.45, 0.62)), ((0.45, 0.62), (0.45, 0.38)),
                ((1.0, 0.5), (0.85, 0.5)), ((0.85, 0.5), (0.85, 0.8)), ((0.85, 0.8), (0.15, 0.8)), ((0.15, 0.8), (0.15, 0.35))]
        for a, b in segs:
            G.bar(bm, Mb, U(*a), U(*b), 0.02, 0.02, M['polish'], y=-0.02)


def _ceiling(bm, M, C, D, lod, rg, zc0, info):
    """dished lit disc (rim at zl, centre 0.14 lower) so it shows through the glass from eye height"""
    zl = zc0 - 0.02
    rd = rg - 0.05
    dip = 0.14
    zr = lambda rr: zl - dip * (1 - rr / rd)
    nsp = C['spokes'] or 6
    nw = nsp
    for k in range(nw):
        a0, a1 = 2 * math.pi * k / nw, 2 * math.pi * (k + 1) / nw
        G.lathe(bm, [(0.16, zr(0.16)), (rd * 0.55, zr(rd * 0.55)), (rd, zl)] if lod <= 1 else [(0.16, zr(0.16)), (rd, zl)],
                2 if lod == 0 else 1, M['washi'], a0=a0, a1=a1, closed=False)
    G.lathe(bm, [(0.0, zr(0) - 0.05), (0.1, zr(0.1) - 0.04), (0.17, zr(0.17) - 0.005)], 12 if lod < 2 else 6, M['polish'])
    if lod <= 1:
        G.lathe(bm, [(rd - 0.03, zl - 0.005), (rd - 0.03, zl - 0.04), (rd + 0.05, zl - 0.04), (rd + 0.05, zl)], C['seg'] if lod == 0 else C['seg'] // 2, M['polish'])
    if C['spokes']:
        for k in range(nsp):
            b = 2 * math.pi * k / nsp
            G.strut(bm, S.polar(0.16, b, zr(0.16) - 0.012), S.polar(rd, b, zl - 0.012), 0.02, 0.018, M['polish'])
    if lod == 0:
        if D['ceiling'] == 'rings':
            rr = rd * 0.6
            G.lathe(bm, [(rr + 0.02, zr(rr) - 0.01), (rr - 0.02, zr(rr) - 0.01), (rr - 0.02, zr(rr) - 0.035), (rr + 0.02, zr(rr) - 0.035)][::-1], 24, M['polish'])
        elif D['ceiling'] == 'kumiko':
            for x in (-rd * 0.35, rd * 0.35):
                L = math.sqrt(max(0.0, rd * rd - x * x)) * 0.9
                G.strut(bm, (x, -L, zr(abs(x)) - 0.03), (x, L, zr(abs(x)) - 0.03), 0.018, 0.02, M['frame'])
                G.strut(bm, (-L, x, zr(abs(x)) - 0.035), (L, x, zr(abs(x)) - 0.035), 0.018, 0.02, M['frame'])
    info['lights'].append(dict(pos=[0, 0, round(zl - 0.25, 3)], color=list(WARM), watts=120, radius=round(rd * 0.7, 2)))


def _hub(bm, mb, M, C, D, lod, zt, h):
    """crown: turned hub (d 0.5, h 0.2), a 0.9 m crossbeam carrying two sheaves (r 0.18) and four 0.6 m guide rods
    (d 0.03) standing on the dome; tops out 0.45 m above the dome crown"""
    hs = 8 if lod >= 2 else (12 if lod == 1 else 20)
    G.lathe(bm, [(0.25, zt - 0.04), (0.25, zt + 0.14), (0.22, zt + 0.16), (0.0, zt + 0.16)], hs, [M['frame'], M['polish'], M['frame']])
    if lod == 0:
        G.lathe(bm, [(0.257, zt + 0.03), (0.257, zt + 0.07)], hs, M['polish'])
    mb.box((0, 0, zt + 0.2), (0.9, 0.1, 0.08), M['frame'])
    for x in (-0.22, 0.22):
        mb.cylinder((x, 0, zt + 0.24 + 0.02), radius=0.18, depth=0.04, mi=M['polish'], segs=C['sheave'] or 6, rot=(math.pi / 2, 0, 0))
        if lod == 0:
            mb.cylinder((x, 0, zt + 0.26), radius=0.05, depth=0.08, mi=M['frame'], segs=8, rot=(math.pi / 2, 0, 0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.cylinder((sx * 0.42, sy * 0.07, zt + 0.45 - 0.3), radius=0.015, depth=0.6, mi=M['polish'],
                        segs=6 if lod == 0 else 4, cap=False)


def _lod3(bm, mb, M, D, R, rg, zb, zc0, zc1, zt, h, info):
    """silhouette: base band, warm lit core (no opaque glass shell), dado ring, cornice + the seed's dome, hub block"""
    n = 8
    G.lathe(bm, [(R, 0.0), (R, zb)], n, M['polish'])
    G.lathe(bm, [(rg - 0.05, zb), (rg - 0.05, zc0)], n, M['core'])
    zw = zb + D['dado'] + 0.03
    G.lathe(bm, [(R - 0.03, zw - 0.04), (R - 0.03, zw + 0.04)], n, M['polish'])
    dp = _dome_profile(D['dome'], R, zc1, zt, 3)
    G.lathe(bm, [(R, zc0)] + dp, n, M['frame'])
    G.lathe(bm, [(0.0, zc0 - 0.06), (rg - 0.05, zc0 - 0.02)], n, M['washi'])
    mb.box((0, 0, zt + 0.2), (0.9, 0.12, 0.4), M['frame'])
    info['lights'].append(dict(pos=[0, 0, round(zc0 - 0.25, 3)], color=list(WARM), watts=120, radius=round(rg * 0.7, 2)))
