"""Lift core drum and doors: one storey of the main lift's bronze-and-glass drum, with its well balustrade.

Identifying features kept at every LOD: round bronze-and-glass drum (ribbed, banded), kumiko lattice glazing
(back-lit washi behind glass), double bronze doors in a lit frame, vertical level plaque (B1 / 火山湯), call
panel, balustrade round the well (with the bridge from the doors to the well rim).

Layout (3d/layout.json): lift at the cell centre, well radius `r` = 8 m (shaft_r), doors at the bearing of the
lift portal; the portal bridge runs from the drum (~2.2 m) to the well rim, the stair landing is opposite.
Pivot = drum axis at floor level (z = 0), +Y = the (first) door's bearing, metres.

Construction
  * N bays (glass slot count + door/plaque/panel bays) between chamfered bronze ribs on a polygonal drum.
  * Plinth, cornice (between door storey and glazing) and crown rings are turned profiles (lathes) proud
    of the ribs; storeys taller than 6.5 m get a balcony ledge with its own fret railing (sheet-vs-lift-cable).
  * Lower register: each bay a dark bronze panel framing one tall lit glass slot (washi_backlit behind
    lava_glass) with a vertical kumiko grille.
  * Upper register: kumiko glazing - washi_backlit panel, a square kumiko grid plus asanoha-style diagonals
    (LOD0) in front, glass over it. `lattice` = cells per metre.
  * Door portal: recessed flat facade (chord across two bays), bronze architrave, lit frame strip, lit
    transom plate, two lattice-glazed bronze door leaves with long pulls, threshold; bracket lanterns on
    the flanking ribs; vertical hinoki level plaque (viewer's right) with glowing raised letters "B1" + 火山湯;
    call panel (viewer's left) with lit up/down buttons.
  * Well: bronze-post balustrade with hinoki handrail and fret lattice on the rim circle, gaps at the bridge
    and the stair landing; the bridge (hinoki deck, bronze fascia, railings) spans drum -> rim.

Parameters build(lod, seed, **p)
  r            well/balustrade radius (8 m; <= proxy w/2)       h        storey height 4.5-10 m (proxy 4.5)
  drum_r       drum radius 2.0-2.5 (2.2 from the portal bridge)   doors    door bearings (deg, clockwise from +Y)
  label        level label G | B1 | B2 | B3 | B4 (default from seed)  lattice  kumiko cells per metre 3-6
  slots        bay count around the drum 12-24 (glass slots = bays - 3 per door)
  balustrade   True/False      bridge  True/False      stair    stair-landing bearing (deg; default door + 180)

Animation / runtime
  * Doors are rigid with lift_car: leaves are vertex groups `door<i>_L` / `door<i>_R`; obj['kz_doors'] gives,
    per door, the bearing, the slide axis (object space, unit, pointing to each leaf's open side) and travel.
  * Shader glow: the lit door frame strips, transom, buttons and bead share one washi_backlit slot
    (emissive_level 1.8); bracket lanterns and plaque letters have their own washi_backlit slots
    listed in obj['kz_glow_slots'] for a pulse when the car arrives.
Lights: obj['kz_lights'] = emissive light sources for the bake (pos, colour, watts): door frame, transom,
bracket lanterns, plaque, and the kumiko band (as a ring of samples).
"""
import json
import math

import bmesh
from mathutils import Matrix, Vector

import genlib
import kzgeo_lift_drum as G

ASSET = 'lift_drum'
FEATURES = ['round bronze-and-glass drum', 'kumiko lattice glazing', 'double bronze doors in a lit frame',
            'vertical level plaque (B1 火山湯)', 'call panel', 'balustrade round the well']
LEVELS = ['G', 'B1', 'B2', 'B3', 'B4']
FONT_LATIN = '/usr/share/fonts/noto-cjk/NotoSerifCJK-SemiBold.ttc'
FONT_KANJI = '/usr/share/fonts/noto-cjk/NotoSerifCJK-Black.ttc'   # heavy strokes stay legible on a 0.45 m board
WARM = (1.0, 0.55, 0.22)

LODS = {
    0: dict(ring=48, rail=40, bev=0.008, kumiko=1.0, diag=True, motif=True, slot_bars=3, lantern=True, glyph_res=2, glyph_depth=0.012, post_step=1.0, fret='key', rod=8),
    1: dict(ring=32, rail=32, bev=0.0, kumiko=0.5, diag=False, motif=True, slot_bars=2, lantern=True, glyph_res=1, glyph_depth=0.0, post_step=2.0, fret='simple', rod=6),
    2: dict(ring=24, rail=24, bev=0.0, kumiko=0.22, diag=False, motif=False, slot_bars=0, lantern=False, glyph_res=1, glyph_depth=0.0, post_step=3.2, fret=None, rod=4),
}


def build(lod, seed, r=None, h=None, drum_r=None, doors=None, label=None, lattice=None, slots=None,
          balustrade=True, bridge=True, stair=None, rise=1.0, **_):
    p = genlib.proxy(ASSET)
    rng = genlib.rng(seed, ASSET)
    r = min(r or p['w'] / 2, p['w'] / 2 * 1.04)
    h = h or (p['h'] - rise)              # proxy h covers the storey plus the guide columns rising over it
    R = drum_r or 2.2
    N = int(slots or rng.choice([14, 16, 18]))
    doors = [math.radians(d) for d in (doors if doors is not None else [0.0])]
    label = label or LEVELS[seed % len(LEVELS)]
    lat = lattice or rng.uniform(6.2, 7.6)
    # seeded style: the five level copies differ in pattern, motif, plaque side, lanterns, crown rods and ribs
    style = dict(pattern=rng.choice(['asanoha', 'kikko', 'fine']), motif=rng.choice(['pine', 'cloud', 'pine']),
                 plaque_side=rng.choice([-1, 1]), lantern=rng.choice(['box', 'round']), rods=rng.choice([6, 8]),
                 fluted=rng.random() < 0.5, cornice=rng.choice([0, 1]), seed=seed)
    stair_b = math.radians(stair) if stair is not None else doors[0] + math.pi
    mb = genlib.MeshBuilder()
    bm = mb.bm
    bm.faces.layers.float_vector.new('kz_n')          # intended normals of open parts (see kzgeo.intend)
    M = dict(
        bronze=mb.slot('bronze', wear=round(rng.uniform(0.3, 0.45), 2)),
        bronze_dk=mb.slot('bronze', wear=round(rng.uniform(0.1, 0.2), 2), roughness_offset=0.1),
        glass=mb.slot('glass_clear'),
        washi=mb.slot('washi_backlit', emissive_level=round(rng.uniform(0.9, 1.05), 2)),
        glow=mb.slot('washi_backlit', emissive_level=1.8),                     # door frame strips, transom, buttons, bead
        wood=mb.slot('hinoki', wear=0.25),
        board=mb.slot('hinoki', wear=0.1),
        shade=mb.slot('washi_backlit', tint=(0.3, 0.26, 0.22), emissive_level=0.5),     # ink-wash motif: darker back-lit paper
        lamp=mb.slot('washi_backlit', emissive_level=1.6, tint=(1.0, 0.8, 0.55)),       # amber bracket lanterns
        letter=mb.slot('washi_backlit', emissive_level=1.0),                             # plaque letters
        lacquer=mb.slot('lacquer_black'),
    )
    step = 2 * math.pi / N
    phase = doors[0]                                   # ribs on the door bearing so each door spans two bays
    door_idx = []
    for d in doors:                                    # snap extra doors to the rib grid
        k = round((d - phase) / step) % N
        door_idx.append(k)
    info = dict(lights=[], doors=[], R=R, N=N, step=step, phase=phase)
    Z = heights(h)
    if lod == 3:
        _lod3(mb, bm, M, R, r, h, Z, doors, balustrade, bridge, stair_b, label, rise, style)
    else:
        C = LODS[lod]
        _drum(mb, bm, M, C, lod, rng, R, h, Z, N, step, phase, door_idx, lat, info, label, style, rise)
        if balustrade:
            _well(mb, bm, M, C, lod, r, [phase + k * step for k in door_idx], stair_b, bridge, R, info)
    o = mb.to_object(ASSET)
    G.fix_normals(o)
    genlib.finish(o)
    # (lit parts are washi_backlit now: metric UVs from genlib.finish are right, no object-UV remap needed)
    _groups(o, info)
    o['kz_params'] = json.dumps(dict(r=r, h=h, drum_r=R, slots=N, doors=[math.degrees(d) for d in doors], label=label,
                                     lattice=round(lat, 2), balustrade=balustrade, bridge=bridge, style=style))
    o['kz_label'] = label
    o['kz_glow_slots'] = json.dumps([M['glow'], M['lamp'], M['letter']])
    o['kz_doors'] = json.dumps(info['doors'])
    o['kz_lights'] = json.dumps(info['lights'])
    return o


def heights(h):
    # glazing dominates (sheet / ref-b1-lobby): door storey to 2.7 m, kumiko from 2.9 m to the open crown ring
    Z = dict(plinth=0.1, door_top=0.1 + 2.4, head=2.66, cornice0=2.7, cornice1=2.9, crown0=h - 0.26, crown1=h, top=h)
    Z['balcony'] = None
    if h >= 6.5:                                       # tall storey: balcony ring halfway up the glazing
        Z['balcony'] = (Z['cornice1'] + Z['crown0']) / 2 - 0.2
    return Z


# ------------------------------------------------------------------ drum
def _drum(mb, bm, M, C, lod, rng, R, h, Z, N, step, phase, door_idx, lat, info, label, style, rise=1.0):
    bev = C['bev']
    ring = C['ring']
    door_bays = set()
    for k in door_idx:
        door_bays |= {(k - 1) % N, k % N}
    ps = style['plaque_side']                           # -1: plaque on the viewer's right of the door
    plaque_bays = {(k - 2) % N if ps < 0 else (k + 1) % N for k in door_idx}
    panel_bays = {(k + 1) % N if ps < 0 else (k - 2) % N for k in door_idx}
    rd = 0.2 if lod == 0 else 0.18                      # ring reference depth (o_ = R + rd/2)
    rw = 0.1                                            # bay gap under each half-column
    chord_d = R * math.cos(step / 2)                    # bay plane distance
    bay_w = 2 * R * math.sin(step / 2) - rw
    k0, k1 = Z['crown0'], Z['crown1']
    # --- rings: plinth, cornice, crown (turned profiles proud of the ribs)
    o_ = R + rd / 2
    plinth = [(o_ + 0.16, 0.0), (o_ + 0.16, 0.05), (o_ + 0.1, 0.08), (o_ + 0.04, Z['plinth']), (o_ - 0.06, Z['plinth'])]
    G.lathe(bm, plinth if lod == 0 else [plinth[0], plinth[2], plinth[4]], ring,
            [M['lacquer'], M['bronze'], M['bronze_dk'], M['bronze_dk']] if lod == 0 else [M['lacquer'], M['bronze_dk']])
    c0, c1 = Z['cornice0'], Z['cornice1']
    if lod == 0 and style['cornice'] == 0:          # stepped cornice with a cavetto
        cornice = [(o_ - 0.04, c0 - 0.01), (o_ + 0.08, c0 + 0.02), (o_ + 0.2, c0 + 0.09), (o_ + 0.24, c0 + 0.13),
                   (o_ + 0.24, c1 - 0.04), (o_ + 0.14, c1), (o_ - 0.06, c1)]
        mis = [M['bronze_dk'], M['bronze'], M['bronze'], M['lacquer'], M['bronze'], M['bronze_dk']]
    elif lod == 0:                                   # flat banded cornice with a lacquer frieze
        cornice = [(o_ - 0.04, c0 - 0.01), (o_ + 0.2, c0), (o_ + 0.2, c0 + 0.05), (o_ + 0.16, c0 + 0.06),
                   (o_ + 0.16, c1 - 0.06), (o_ + 0.22, c1 - 0.05), (o_ + 0.22, c1), (o_ - 0.06, c1)]
        mis = [M['bronze_dk'], M['bronze'], M['bronze_dk'], M['lacquer'], M['bronze_dk'], M['bronze'], M['bronze_dk']]
    else:
        cornice = [(o_ - 0.04, c0), (o_ + 0.22, c0 + 0.08), (o_ + 0.22, c1), (o_ - 0.06, c1)]
        mis = [M['bronze'], M['lacquer'], M['bronze_dk']]
    G.lathe(bm, cornice, ring, mis)
    # crown: an OPEN band ring that the next storey stacks onto (no lid); the inner lip hangs down
    if lod == 0:
        crown = [(o_ - 0.04, k0), (o_ + 0.14, k0 + 0.05), (o_ + 0.14, k1 - 0.05), (o_ + 0.2, k1 - 0.025), (o_ + 0.2, k1),
                 (R - 0.06, k1), (R - 0.06, k1 - 0.12)]
        cmis = [M['bronze_dk'], M['lacquer'], M['bronze'], M['bronze'], M['bronze_dk'], M['bronze_dk']]
    else:
        crown = [(o_ - 0.04, k0), (o_ + 0.18, k0 + 0.04), (o_ + 0.18, k1), (R - 0.06, k1)]
        cmis = [M['bronze'], M['lacquer'], M['bronze_dk']]
    G.lathe(bm, crown, ring, cmis)
    # glowing bead under the cornice (concept: warm light line round the drum)
    G.lathe(bm, [(o_ + 0.05, c0 - 0.035), (o_ + 0.05, c0 - 0.008)], ring, M['glow'])
    # guide rods: vertical bronze rods running up through the crown ring past the top (stacking guides)
    # crown guide columns (sheet's signature silhouette): 6-8 capped bronze columns rising `rise` m over the ring
    nro = style['rods']
    for q in range(nro):
        a = phase + (q + 0.5) * 2 * math.pi / nro
        c = G.polar(o_ + 0.1, a)
        G.rod(bm, (c.x, c.y), k0 - 0.3, h + rise - 0.06, 0.035, C['rod'], M['bronze'])
        G.rod(bm, (c.x, c.y), h + rise - 0.06, h + rise - 0.02, 0.05, C['rod'], M['bronze_dk'])     # cap
        G.rod(bm, (c.x, c.y), h + rise - 0.02, h + rise, 0.022, C['rod'], M['bronze'])          # finial
        if lod == 0:
            for zc in (h + 0.04, h + rise * 0.55):
                G.rod(bm, (c.x, c.y), zc - 0.02, zc + 0.02, 0.048, 8, M['bronze_dk'])          # collars
    bal = Z['balcony']
    if bal:
        ledge = [(o_ - 0.04, bal - 0.12), (o_ + 0.3, bal - 0.06), (o_ + 0.62, bal - 0.02), (o_ + 0.62, bal + 0.1), (o_ - 0.06, bal + 0.1)]
        G.lathe(bm, ledge, ring, [M['bronze_dk'], M['bronze'], M['lacquer'], M['wood']])
        _railing_ring(bm, M, dict(C, post_step=C['post_step'] * 1.4), lod, o_ + 0.52, bal + 0.1, 0.0, 2 * math.pi, 0.9, ring, closed=True)
    # --- ribs: round bronze half-columns (dia 0.11, ~7 cm proud of the bays) with base / capital rings
    pr = 0.055 if not style['fluted'] else 0.06
    pc = chord_d + 0.07 - pr                            # column centre radius
    csegs = {0: 12, 1: 6, 2: 5}[lod]
    for k in range(N):
        b = phase + k * step
        c = G.polar(pc, b)
        z0 = Z['cornice0'] if k in door_idx else Z['plinth']
        z1 = k0
        G.rod(bm, (c.x, c.y), z0, z1, pr, csegs, M['bronze'], cap=False)
        if lod < 2:
            rings_ = ((z0 + 0.05, 0.1), (c0 - 0.05, 0.08), (c1 + 0.05, 0.08), (k0 - 0.05, 0.08)) if lod == 0 else ((z0 + 0.05, 0.1), (c1 + 0.05, 0.08))
            for zc, hh in rings_:
                if z0 <= zc - hh / 2 and zc + hh / 2 <= z1:
                    G.rod(bm, (c.x, c.y), zc - hh / 2, zc + hh / 2, pr + 0.018, csegs, M['bronze_dk'])
    # --- bays
    for k in range(N):
        bmid = phase + (k + 0.5) * step
        Mb = G.frame(bmid, chord_d)
        zones = [(c1, k0)] if not bal else [(c1, bal - 0.12), (bal + 0.1, k0)]
        glaze = sum(z1 - z0 for z0, z1 in zones)
        br = genlib.rng(style['seed'], f'bay{k}')
        for zi, (z0, z1) in enumerate(zones):
            Cz = dict(C, diag=C['diag'] and (zi == 0 or glaze < 3.5))
            _kumiko(bm, Mb, M, Cz, lod, bay_w, z0 + 0.03, z1 - 0.02, lat * min(1.0, (2.0 / max(glaze, 1.0)) ** 0.3),
                    style, br, feature=(zi == len(zones) - 1))
        if k in door_bays:
            continue
        if k in plaque_bays:
            _lower_panel(bm, Mb, M, C, lod, bay_w, Z, slot=False)
            _plaque(bm, Mb, M, C, lod, Z, label, info)
        elif k in panel_bays:
            _lower_panel(bm, Mb, M, C, lod, bay_w, Z, slot=lod < 2, narrow=True)
            _call_panel(bm, Mb, M, C, lod, info)
        else:
            _lower_panel(bm, Mb, M, C, lod, bay_w, Z, slot=True)
    for i, k in enumerate(door_idx):
        _door(bm, M, C, lod, R, rd, rw, step, phase + k * step, Z, i, info, style)
    # the lit shaft: warm lights on the drum axis back-light every washi panel (washi_backlit is translucent);
    # in the bake they stand in for the lift car's interior glow
    for zz in (1.3, (c1 + k0) / 2) + ((Z['balcony'] + 1.2,) if bal else ()):
        info['lights'].append(dict(kind='point', role='shaft_interior', pos=[0.0, 0.0, round(zz, 3)], color=list(WARM), watts=round(260 * R / 2.2)))


def _diag_lines(nx, nz, period=1):
    """two families of diagonals through the cell-edge midpoints (asanoha-like diamonds); period 2 = kikko-like
    larger lozenges. Returns segments in cell units."""
    segs = []
    for sgn in (1, -1):
        for m in range(-nz - 2, nx + nz + 2):
            if m % period:
                continue
            c = m + 0.5 * period
            pts = []
            for v in (0.0, float(nz)):
                u = c + v if sgn == 1 else c - v
                if 0 <= u <= nx:
                    pts.append((u, v))
            for u in (0.0, float(nx)):
                v = (u - c) if sgn == 1 else c - u
                if 0 <= v <= nz:
                    pts.append((u, v))
            pts = sorted(set((round(a, 6), round(b, 6)) for a, b in pts))
            if len(pts) >= 2 and pts[0] != pts[-1]:
                segs.append((pts[0], pts[-1]))
    return segs


def _motif(kind, rng):
    """feature silhouette (pine or cloud) as polygons in a unit box (x -0.5..0.5, z 0..1)"""
    polys = []
    def ell(cx, cz, rx, rz, n=10):
        return [(cx + rx * math.cos(2 * math.pi * i / n), cz + rz * math.sin(2 * math.pi * i / n)) for i in range(n)]
    if kind == 'pine':
        # ink-style niwaki pine: leaning tapered trunk, 3 branch strokes, thin layered needle pads with tufted
        # undersides (pad thickness <= ~0.06 m at the drum's glazing height)
        lean = rng.uniform(0.08, 0.16) * rng.choice([-1, 1])
        spine = []
        for i in range(7):
            t = i / 6
            spine.append((lean * math.sin(t * math.pi * 0.9) + 0.06 * t * (1 if lean > 0 else -1), 0.02 + 0.82 * t, 0.045 * (1 - 0.7 * t) + 0.008))
        for (xa, za, wa), (xb, zb, wb) in zip(spine, spine[1:]):
            polys.append([(xa - wa / 2, za), (xa + wa / 2, za), (xb + wb / 2, zb), (xb - wb / 2, zb)])
        def at(t):
            i = min(5, int(t * 6)); f = t * 6 - i
            (xa, za, _), (xb, zb, _) = spine[i], spine[i + 1]
            return xa + (xb - xa) * f, za + (zb - za) * f
        def pad(cx, cz, rx, rz, n=14):
            pts = []
            for i in range(n):
                a = 2 * math.pi * i / n
                if a < math.pi:
                    pts.append((cx + rx * math.cos(a), cz + rz * math.sin(a)))
                else:   # tufted underside
                    tuft = 0.35 if i % 2 else 0.1
                    pts.append((cx + rx * math.cos(a), cz + rz * tuft * math.sin(a)))
            return pts
        side = 1
        for t, rx in ((0.42, 0.26), (0.62, 0.24), (0.8, 0.2)):
            x0, z0 = at(t)
            side = -side
            xe, ze = x0 + side * rx * 1.1, z0 + 0.06
            polys.append([(x0, z0 - 0.008), (xe, ze - 0.006), (xe, ze + 0.006), (x0, z0 + 0.008)])        # branch stroke
            polys.append(pad(xe + side * 0.02, ze + 0.005, rx * rng.uniform(0.85, 1.05), 0.032))
        xt, zt = at(1.0)
        polys.append(pad(xt, zt + 0.02, 0.17, 0.034))
    else:   # stylised clouds: stacked bumps with a flat base, two banks
        for bz, n, w in ((0.28, 4, 0.8), (0.66, 3, 0.6)):
            x0 = rng.uniform(-0.12, 0.12) - w / 2
            polys.append([(x0, bz - 0.04), (x0 + w, bz - 0.04), (x0 + w, bz + 0.02), (x0, bz + 0.02)])
            for i in range(n):
                cx = x0 + w * (i + 0.5) / n
                r_ = w / n * rng.uniform(0.5, 0.62)
                polys.append(ell(cx, bz + r_ * 0.4, r_, r_ * 0.8, 10))
    return polys


def _kumiko(bm, Mb, M, C, lod, w, z0, z1, lat, style, br, feature=True):
    """washi panel + kumiko (square grid, + diamond diagonals standing 10 mm proud at LOD0) + glass; a pine /
    cloud feature silhouette in the washi of every bay (the sheet's shaped centre panels)."""
    hgt = z1 - z0
    G.quad(bm, Mb, -w / 2, w / 2, z0, z1, -0.05, M['washi'])
    dens = lat * C['kumiko']
    nx = max(1, round(w * dens)); nz = max(1, round(hgt * dens))
    bw, bd = (0.013, 0.02) if lod == 0 else ((0.02, 0.025) if lod == 1 else (0.04, 0.04))
    if C['motif'] and feature:
        mh = min(hgt * 0.78, w * 1.25)
        mw = mh * 0.85
        flip = br.choice([-1, 1])
        zb = z0 + (hgt - mh) * br.uniform(0.25, 0.6)
        for poly in _motif(style['motif'], br):
            pts = [(flip * x * mw, zb + zz * mh) for x, zz in poly]
            if lod > 0:
                pts = pts[::2] if len(pts) > 8 else pts
            if len(pts) >= 3:
                G.poly2d(bm, Mb, pts, -0.047, M['shade'])
    if lod < 2:
        for x in (-w / 2, w / 2):
            G.bar(bm, Mb, (x, z0), (x, z1), 0.04, 0.05, M['bronze_dk'], y=-0.05)
        for z in (z0, z1):
            G.bar(bm, Mb, (-w / 2, z), (w / 2, z), 0.04, 0.05, M['bronze_dk'], y=-0.05)
    for i in range(1, nx):
        x = -w / 2 + w * i / nx
        G.bar(bm, Mb, (x, z0), (x, z1), bw, bd, M['wood'], y=-0.05)
    for j in range(1, nz):
        z = z0 + hgt * j / nz
        G.bar(bm, Mb, (-w / 2, z), (w / 2, z), bw, bd, M['wood'], y=-0.05)
    if C['diag'] and style['pattern'] != 'fine':
        cw, ch = w / nx, hgt / nz
        for a, b in _diag_lines(nx, nz, 1 if style['pattern'] == 'asanoha' else 2):
            G.bar(bm, Mb, (-w / 2 + a[0] * cw, z0 + a[1] * ch), (-w / 2 + b[0] * cw, z0 + b[1] * ch), 0.013, bd + 0.01, M['wood'], y=-0.05)
    if lod < 2:
        G.pane(bm, Mb, -w / 2, w / 2, z0, z1, 0.008, M['glass'])


def _lower_panel(bm, Mb, M, C, lod, w, Z, slot=True, narrow=False):
    z0, z1 = Z['plinth'], Z['cornice0']
    bev = C['bev']
    if not slot or lod >= 2:
        G.obox(bm, Mb, (0, -0.03, (z0 + z1) / 2), (w, 0.06, z1 - z0), M['bronze_dk'], skip_back=True)
        if slot:
            sw = w * (0.3 if narrow else 0.5)
            G.quad(bm, Mb, -sw / 2, sw / 2, z0 + 0.45, z1 - 0.2, 0.002, M['washi'])
        return
    sw = w * (0.3 if narrow else 0.5)        # lit glass slot ~half the bay: the drum reads as a lantern
    s0, s1 = z0 + 0.45, z1 - 0.2
    # panel pieces around the slot (stiles, spandrel, lintel) - the slot is a real opening
    G.obox(bm, Mb, (-(w + sw) / 4, -0.03, (z0 + z1) / 2), ((w - sw) / 2, 0.06, z1 - z0), M['bronze_dk'], skip_back=True)
    G.obox(bm, Mb, ((w + sw) / 4, -0.03, (z0 + z1) / 2), ((w - sw) / 2, 0.06, z1 - z0), M['bronze_dk'], skip_back=True)
    G.obox(bm, Mb, (0, -0.03, (z0 + s0) / 2), (sw, 0.06, s0 - z0), M['bronze_dk'], skip_back=True)
    G.obox(bm, Mb, (0, -0.03, (s1 + z1) / 2), (sw, 0.06, z1 - s1), M['bronze_dk'], skip_back=True)
    if lod == 0:    # raised moulded frames on the stiles / spandrel (relief)
        for sx in (-1, 1):
            G.obox(bm, Mb, (sx * (w + sw) / 4, 0.008, (s0 + s1) / 2), ((w - sw) / 2 - 0.08, 0.016, s1 - s0 - 0.1), M['bronze'], skip_back=True)
        G.obox(bm, Mb, (0, 0.008, (z0 + s0) / 2), (sw + 0.02, 0.016, s0 - z0 - 0.14), M['bronze'], skip_back=True)
    # slot: lit washi deep inside, vertical kumiko grille, glass, bronze slot frame
    G.quad(bm, Mb, -sw / 2, sw / 2, s0, s1, -0.14, M['washi'])
    for i in range(C['slot_bars']):
        x = -sw / 2 + sw * (i + 1) / (C['slot_bars'] + 1)
        G.bar(bm, Mb, (x, s0), (x, s1), 0.018, 0.03, M['bronze_dk'], y=-0.14)
    if lod == 0:
        for z in (s0 + (s1 - s0) * 0.33, s0 + (s1 - s0) * 0.66):
            G.bar(bm, Mb, (-sw / 2, z), (sw / 2, z), 0.018, 0.03, M['bronze_dk'], y=-0.14)
    G.pane(bm, Mb, -sw / 2, sw / 2, s0, s1, -0.04, M['glass'])
    if lod == 0:
        for x in (-sw / 2, sw / 2):
            G.bar(bm, Mb, (x, s0 - 0.03), (x, s1 + 0.03), 0.04, 0.05, M['bronze'], y=-0.02)
        for z in (s0, s1):
            G.bar(bm, Mb, (-sw / 2 - 0.02, z), (sw / 2 + 0.02, z), 0.04, 0.05, M['bronze'], y=-0.02)


def _door(bm, M, C, lod, R, rd, rw, step, b, Z, i, info, style):
    """flat recessed portal on the chord between the two ribs either side of bearing b"""
    d = R * math.cos(step)                                  # chord distance (ribs at b +/- step)
    W = 2 * R * math.sin(step) - rw                         # clear width between ribs
    Mf = G.frame(b, d)
    bev = C['bev']
    z0, zt, zh, zc = Z['plinth'], Z['door_top'], Z['head'], Z['cornice0']
    ow = W - 0.36                                           # opening width (architrave 0.18 each side)
    # back wall of the portal above the head and returns (cheeks) to the ribs
    G.obox(bm, Mf, (0, -0.03, (zh + zc) / 2), (W, 0.06, zc - zh), M['bronze_dk'], skip_back=True)
    for sx in (-1, 1):
        G.obox(bm, Mf, (sx * (W / 2 - 0.09), 0.0, (z0 + zh) / 2), (0.18, 0.12, zh - z0), M['bronze'], bevel=bev)
        if lod == 0:    # architrave mouldings
            G.obox(bm, Mf, (sx * (ow / 2 + 0.035), 0.075, (z0 + zt) / 2 + 0.02), (0.05, 0.05, zt - z0 + 0.04), M['bronze_dk'], bevel=0.006)
    G.obox(bm, Mf, (0, 0.02, (zt + zh) / 2 + 0.02), (W, 0.16, zh - zt + 0.04), M['bronze'], bevel=bev)
    if lod == 0:
        G.obox(bm, Mf, (0, 0.11, zh - 0.02), (W + 0.06, 0.06, 0.06), M['bronze_dk'], bevel=0.008)
    # lit transom plate in the head (glow slot) with the level name on it at LOD0 is the plaque's job
    G.quad(bm, Mf, -ow * 0.35, ow * 0.35, zt + 0.05, zh - 0.05, 0.102, M['glow'])
    # lit frame strip lining the opening (shader glow)
    gs = 0.035
    G.obox(bm, Mf, (-ow / 2 + gs / 2, 0.0, (z0 + zt) / 2), (gs, 0.1, zt - z0), M['glow'])
    G.obox(bm, Mf, (ow / 2 - gs / 2, 0.0, (z0 + zt) / 2), (gs, 0.1, zt - z0), M['glow'])
    G.obox(bm, Mf, (0, 0.0, zt - gs / 2), (ow, 0.1, gs), M['glow'])
    # threshold
    G.obox(bm, Mf, (0, 0.12, 0.03), (W + 0.1, 0.42, 0.06), M['bronze_dk'], bevel=bev)
    # leaves
    lw = (ow - 2 * gs) / 2
    start = len(bm.verts)
    groups = {}
    for side in (-1, 1):
        s0 = len(bm.verts)
        cx = side * lw / 2
        lz0, lz1 = z0 + 0.02, zt - gs
        hgt = lz1 - lz0
        st = 0.075
        y = -0.04
        G.obox(bm, Mf, (cx - lw / 2 + st / 2, y, (lz0 + lz1) / 2), (st, 0.06, hgt), M['bronze'], bevel=bev)
        G.obox(bm, Mf, (cx + lw / 2 - st / 2, y, (lz0 + lz1) / 2), (st, 0.06, hgt), M['bronze'], bevel=bev)
        for zz, hh in ((lz0 + 0.12, 0.24), (lz1 - st / 2, st), (lz0 + hgt * 0.36, 0.05)):
            G.obox(bm, Mf, (cx, y, zz), (lw - 2 * st, 0.06, hh), M['bronze'], bevel=bev)
        # glazed lattice panel (lit car interior behind)
        p0, p1 = lz0 + 0.24, lz1 - st
        G.quad(bm, Mf, cx - lw / 2 + st, cx + lw / 2 - st, p0, p1, y - 0.035, M['washi'])
        nb = {0: 5, 1: 3, 2: 1}[lod]
        for q in range(nb):
            x = cx - lw / 2 + st + (lw - 2 * st) * (q + 1) / (nb + 1)
            G.bar(bm, Mf, (x, p0), (x, p1), 0.016, 0.03, M['bronze_dk'], y=y - 0.035)
        if lod < 2:
            for zz in (p0 + (p1 - p0) * 0.5,) + ((p0 + (p1 - p0) * 0.25, p0 + (p1 - p0) * 0.75) if lod == 0 else ()):
                G.bar(bm, Mf, (cx - lw / 2 + st, zz), (cx + lw / 2 - st, zz), 0.016, 0.03, M['bronze_dk'], y=y - 0.035)
            G.pane(bm, Mf, cx - lw / 2 + st, cx + lw / 2 - st, p0, p1, y + 0.005, M['glass'])
            # long pull handle at the meeting stiles
            hx = cx - side * (lw / 2 - st - 0.05)
            G.obox(bm, Mf, (hx, y + 0.06, 1.15), (0.025, 0.025, 0.7), M['bronze'], bevel=0.004 if lod == 0 else 0)
            if lod == 0:
                for zz in (0.82, 1.48):
                    G.obox(bm, Mf, (hx, y + 0.04, zz), (0.02, 0.04, 0.02), M['bronze'])
            # dragon-cloud ornament plates top/bottom (concept: chased bronze corners) as raised panels
            if lod == 0:
                for zz in (lz0 + 0.12,):
                    G.obox(bm, Mf, (cx, y + 0.035, zz), (lw - 2 * st - 0.08, 0.012, 0.14), M['bronze_dk'], bevel=0.004)
        groups['L' if side < 0 else 'R'] = (s0, len(bm.verts))
    ax = Vector((-math.cos(b), math.sin(b), 0))      # local +x (viewer's right) in object space
    info['doors'].append(dict(index=i, bearing_deg=round(math.degrees(b), 2), travel_m=round(lw * 0.95, 3),
                              leaves={k: dict(group=f'door{i}_{k}', slide=[round(c, 4) for c in (ax * (-1 if k == 'L' else 1))]) for k in groups}))
    info.setdefault('vgroups', {}).update({f'door{i}_{k}': v for k, v in groups.items()})
    gl0 = len(bm.verts)
    # bracket lanterns: 0.18 x 0.5 m amber lanterns with dark caps and finials on scroll brackets (sheet)
    if C['lantern']:
        for sx in (-1, 1):
            # on the portal cheeks (inside the door bays) so they never cover the plaque or the call panel
            Mr = G.frame(b, d) @ Matrix.Translation((sx * (W / 2 - 0.09), 0.0, 0.0))
            y0, ly = 0.06, 0.06 + 0.2                  # cheek face, lantern axis distance
            zc, lh, lw_ = 1.85, 0.5, 0.18
            # scroll bracket: back plate, out-arm, C-scroll under it, hanger
            G.obox(bm, Mr, (0, y0 + 0.01, zc + 0.3), (0.06, 0.02, 0.22), M['bronze'])
            G.strut(bm, Mr @ Vector((0, y0, zc + 0.36)), Mr @ Vector((0, ly + 0.02, zc + 0.36)), 0.025, 0.025, M['bronze'])
            if lod == 0:
                pts = [(y0, zc + 0.22), (y0 + 0.06, zc + 0.2), (y0 + 0.12, zc + 0.24), (y0 + 0.14, zc + 0.3), (y0 + 0.1, zc + 0.33)]
                for (ya, za), (yb, zb) in zip(pts, pts[1:]):
                    G.strut(bm, Mr @ Vector((0, ya, za)), Mr @ Vector((0, yb, zb)), 0.016, 0.016, M['bronze'])
            G.strut(bm, Mr @ Vector((0, ly, zc + 0.36)), Mr @ Vector((0, ly, zc + lh / 2 + 0.04)), 0.014, 0.014, M['bronze'])
            c = Mr @ Vector((0, ly, 0))
            sg = 12 if lod == 0 else 8
            if style['lantern'] == 'box':
                G.obox(bm, Mr, (0, ly, zc), (lw_ - 0.02, lw_ - 0.02, lh - 0.08), M['lamp'])
                for cx_ in (-1, 1):
                    for cy_ in (-1, 1):
                        if lod == 0 or cx_ == cy_:
                            G.obox(bm, Mr, (cx_ * (lw_ / 2 - 0.012), ly + cy_ * (lw_ / 2 - 0.012), zc), (0.022, 0.022, lh - 0.08), M['bronze_dk'])
                G.obox(bm, Mr, (0, ly, zc + lh / 2 - 0.02), (lw_ + 0.04, lw_ + 0.04, 0.04), M['lacquer'], bevel=bev)
                G.obox(bm, Mr, (0, ly, zc + lh / 2 + 0.015), (lw_ * 0.6, lw_ * 0.6, 0.03), M['lacquer'])
                G.obox(bm, Mr, (0, ly, zc - lh / 2 + 0.02), (lw_ + 0.02, lw_ + 0.02, 0.04), M['lacquer'], bevel=bev)
            else:       # tall round chochin-style lamp
                G.rod(bm, (c.x, c.y), zc - lh / 2 + 0.04, zc + lh / 2 - 0.04, lw_ / 2, sg, M['lamp'])
                G.rod(bm, (c.x, c.y), zc + lh / 2 - 0.05, zc + lh / 2, lw_ / 2 * 0.8, sg, M['lacquer'])
                G.rod(bm, (c.x, c.y), zc - lh / 2, zc - lh / 2 + 0.05, lw_ / 2 * 0.8, sg, M['lacquer'])
                for z_ in (zc + lh / 2 - 0.055, zc - lh / 2 + 0.05):
                    G.rod(bm, (c.x, c.y), z_ - 0.006, z_ + 0.006, lw_ / 2 * 0.84, sg, M['bronze'])
            G.rod(bm, (c.x, c.y), zc - lh / 2 - 0.06, zc - lh / 2, 0.015, 6, M['bronze'])          # bottom finial
            info['lights'].append(dict(kind='point', pos=[round(v, 3) for v in (Mr @ Vector((0, ly, zc)))], color=[1.0, 0.45, 0.12], watts=20))
    info['lights'].append(dict(kind='area', pos=[round(c, 3) for c in (Mf @ Vector((0, 0.15, (z0 + zt) / 2)))], color=list(WARM), watts=80,
                               size=[round(ow, 2), round(zt - z0, 2)], note='door frame glow + lit car behind'))


def _plaque(bm, Mb, M, C, lod, Z, label, info):
    """vertical hinoki level board (0.45 x 2.4 m) in a 30 mm bronze frame; lit raised letters 12 mm proud:
    the level label over 火山湯 (vertical), glyph height ~0.32 m"""
    bw, bh = 0.5, 2.4
    z0 = Z['plinth'] + 0.06
    z1 = min(z0 + bh, Z['cornice0'] - 0.04)
    bh = z1 - z0
    y = 0.03
    G.obox(bm, Mb, (0, y, (z0 + z1) / 2), (bw + 0.04, 0.06, bh + 0.04), M['bronze'], bevel=C['bev'] * 0.5)    # 20 mm frame
    G.obox(bm, Mb, (0, y + 0.02, (z0 + z1) / 2), (bw, 0.06, bh), M['board'], bevel=C['bev'] * 0.5)          # hinoki board
    face = y + 0.02 + 0.03
    res, dep = C['glyph_res'], C['glyph_depth']
    gh = min(0.32, (bh - 0.3) / 4.6)
    zc = z1 - 0.12 - gh * 0.5
    tris, gw = G.glyph_tris(label, FONT_LATIN, res)
    G.glyph_slab(bm, Mb, tris, 0.0, zc, gh * 0.9, face, dep, M['letter'])
    if lod < 2:
        for k, ch in enumerate('火山湯'):
            tris, gw = G.glyph_tris(ch, FONT_KANJI, res)
            G.glyph_slab(bm, Mb, tris, 0.0, zc - gh * (1.35 + 1.15 * k), gh, face, dep, M['letter'])
    else:
        G.quad(bm, Mb, -0.07, 0.07, zc - gh * 3.9, zc - gh * 0.8, face + 0.002, M['letter'])
    info['lights'].append(dict(kind='spot_down', pos=[round(c, 3) for c in (Mb @ Vector((0, face + 0.35, z1 + 0.05)))], color=list(WARM), watts=30,
                               note='plaque wash light (cornice soffit)'))


def _call_panel(bm, Mb, M, C, lod, info):
    """lacquer call panel with lit lift pictogram and up/down buttons on a bronze back plate"""
    y = 0.03
    zc = 1.2
    G.obox(bm, Mb, (0, y, zc), (0.24, 0.03, 0.5), M['bronze'], bevel=C['bev'])
    G.obox(bm, Mb, (0, y + 0.02, zc), (0.19, 0.02, 0.44), M['lacquer'], bevel=C['bev'] * 0.5)
    G.quad(bm, Mb, -0.06, 0.06, zc + 0.08, zc + 0.19, y + 0.031, M['glow'])          # pictogram window
    for dz in (-0.03, -0.13):
        G.obox(bm, Mb, (0, y + 0.035, zc + dz), (0.045, 0.02, 0.045), M['glow'] if lod < 2 else M['bronze'])
        if lod == 0:
            G.obox(bm, Mb, (0, y + 0.031, zc + dz), (0.065, 0.012, 0.065), M['bronze'], bevel=0.004)


# ------------------------------------------------------------------ well balustrade + bridge
def _gaps(doors, stair_b, r):
    g = [(d, (2.2 + 0.3) / r) for d in doors] + [(stair_b, (2.6 + 0.3) / r)]
    return [(a - w / 2, a + w / 2) for a, w in g]


def _arcs(gaps):
    """free arcs between gap intervals over 0..2pi"""
    gs = sorted(((a % (2 * math.pi)), (a % (2 * math.pi)) + (b - a)) for a, b in gaps)
    arcs = []
    for i, (a, b) in enumerate(gs):
        na = gs[(i + 1) % len(gs)][0] + (2 * math.pi if i == len(gs) - 1 else 0)
        if na > b:
            arcs.append((b, na))
    return arcs


def _fret(bm, Mm, M, C, w, zb, zt, y=-0.011):
    """key-fret (Chinese lattice) infill of one railing bay in a local frame (x along the rail, z up)"""
    if C['fret'] is None:
        return
    bw = 0.022
    if C['fret'] == 'simple':
        for x in (-w * 0.25, w * 0.25):
            G.bar(bm, Mm, (x, zb), (x, zt), 0.025, 0.025, M['bronze'], y=y)
        G.bar(bm, Mm, (-w / 2, (zb + zt) / 2), (w / 2, (zb + zt) / 2), 0.025, 0.025, M['bronze'], y=y)
        return
    hgt = zt - zb
    U = lambda u, v: (-w / 2 + u * w, zb + v * hgt)
    # interlocking keys: two hooked meanders meeting in the middle + border stubs (frame = posts and rails)
    segs = [((0.0, 0.5), (0.3, 0.5)), ((0.3, 0.5), (0.3, 0.2)), ((0.3, 0.2), (0.7, 0.2)), ((0.7, 0.2), (0.7, 0.62)),
            ((0.7, 0.62), (0.45, 0.62)), ((0.45, 0.62), (0.45, 0.38)),
            ((1.0, 0.5), (0.85, 0.5)), ((0.85, 0.5), (0.85, 0.8)), ((0.85, 0.8), (0.15, 0.8)), ((0.15, 0.8), (0.15, 0.35))]
    for a, b in segs:
        G.bar(bm, Mm, U(*a), U(*b), bw, 0.022, M['bronze'], y=y)


def _railing_ring(bm, M, C, lod, rr, z, a0, a1, H, segs, closed=False, kerb=False):
    """well balustrade on an arc: 50 mm square bronze posts at ~1 m, hinoki 60x40 cap rail, bronze bottom rail,
    key-fret lattice panels between the posts"""
    bev = C['bev']
    if kerb:
        G.arc_sweep(bm, rr, z + 0.06, a0, a1, segs, G.rect_section(0.26, 0.12), M['lacquer'], cap=not closed)
        z = z + 0.12
    cap = ([(-0.03, -0.02), (0.03, -0.02), (0.03, 0.008), (0.018, 0.02), (-0.018, 0.02), (-0.03, 0.008)] if lod == 0
           else G.rect_section(0.06, 0.04))
    G.arc_sweep(bm, rr, z + H - 0.02, a0, a1, segs, cap, M['board'], cap=not closed)
    if lod < 2:
        G.arc_sweep(bm, rr, z + 0.08, a0, a1, segs, G.rect_section(0.04, 0.04), M['bronze'], cap=not closed)
    L = rr * (a1 - a0)
    n = max(1, int(round(L / C['post_step'])))
    for i in range(n + (0 if closed else 1)):
        a = a0 + (a1 - a0) * i / n
        Mp = G.frame(a, rr)
        G.obox(bm, Mp, (0, 0, z + (H - 0.04) / 2), (0.05, 0.05, H - 0.04), M['bronze'])
        if i < n and lod < 2:
            am = a0 + (a1 - a0) * (i + 0.5) / n
            half = rr * math.sin((a1 - a0) / n / 2)
            Mm = G.frame(am, rr * math.cos((a1 - a0) / n / 2))
            _fret(bm, Mm, M, C, half * 2 - 0.05, z + 0.1, z + H - 0.04)


def _well(mb, bm, M, C, lod, r, doors, stair_b, bridge, R, info):
    rr = r - 0.12
    arcs = _arcs(_gaps(doors, stair_b, rr))
    for a0, a1 in arcs:
        segs = max(2, int(C['rail'] * (a1 - a0) / (2 * math.pi)))
        _railing_ring(bm, M, C, lod, rr, 0.0, a0, a1, 1.0, segs, closed=False, kerb=True)
    if bridge:
        for d in doors:
            _bridge(bm, M, C, lod, R, rr, d)


def _bridge(bm, M, C, lod, R, rr, b):
    """hinoki-decked bridge from the drum plinth to the well rim at bearing b; fret railings both sides"""
    bev = C['bev']
    r0 = R + 0.3
    L = rr - r0 + 0.12
    Mf = G.frame(b, 0.0)
    W = 2.0
    cy = r0 + L / 2
    G.obox(bm, Mf, (0, cy, 0.04), (W, L, 0.08), M['board'], bevel=bev)
    radial = Vector((math.sin(b), math.cos(b), 0))
    for sx in (-1, 1):
        G.obox(bm, Mf, (sx * (W / 2 + 0.03), cy, 0.06), (0.07, L, 0.12), M['bronze_dk'], bevel=bev)
        x = sx * (W / 2 + 0.02)
        G.obox(bm, Mf, (x, cy, 0.12 + 1.0 - 0.02), (0.06, L, 0.04), M['board'], bevel=bev)
        if lod < 2:
            G.obox(bm, Mf, (x, cy, 0.2), (0.04, L, 0.04), M['bronze'])
        n = max(1, int(round(L / C['post_step'])))
        for i in range(n + 1):
            y = r0 + L * i / n
            G.obox(bm, Mf, (x, y, 0.12 + 0.48), (0.05, 0.05, 0.96), M['bronze'])
            if i < n and lod < 2:
                c = Mf @ Vector((x, y + L / n / 2, 0))
                tang = Vector((-math.cos(b), math.sin(b), 0)) * sx
                Ms = G.frame_xyz(c, radial if sx > 0 else -radial, tang)
                _fret(bm, Ms, M, C, L / n - 0.05, 0.22, 0.12 + 1.0 - 0.04)


def _lod3(mb, bm, M, R, r, h, Z, doors, balustrade, bridge, stair_b, label, rise=1.0, style=None):
    seg = 10
    o_ = R + 0.1
    c0, c1, k0 = Z['cornice0'], Z['cornice1'], Z['crown0']
    G.lathe(bm, [(o_, 0.0), (o_, c0), (o_ + 0.25, c1), (o_, c1), (o_, k0), (o_ + 0.15, h), (0.0, h)], seg,
            [M['bronze_dk'], M['bronze'], M['bronze'], M['washi'], M['bronze'], M['bronze_dk']])
    for q in range(4):          # crown guide columns kept as four thin boxes
        a = doors[0] + (q + 0.5) * math.pi / 2
        Mq = G.frame(a, o_ + 0.1)
        G.obox(bm, Mq, (0, 0, h + rise / 2 - 0.1), (0.07, 0.07, rise + 0.2), M['bronze'])
    for d in doors:
        Mf = G.frame(d, o_ + 0.02)
        G.obox(bm, Mf, (0, 0.03, Z['door_top'] / 2 + 0.1), (1.9, 0.06, Z['door_top'] + 0.2), M['glow'])
        G.obox(bm, Mf, (0, 0.07, Z['door_top'] / 2), (1.5, 0.04, Z['door_top'] - 0.1), M['bronze'])
        Mp = G.frame(d - 1.5 * 2 * math.pi / 16, o_)
        G.obox(bm, Mp, (0, 0.04, 1.75), (0.5, 0.08, 2.4), M['glow'])                 # plaque (lit)
        Mc = G.frame(d + 1.5 * 2 * math.pi / 16, o_)
        G.obox(bm, Mc, (0, 0.03, 1.2), (0.24, 0.06, 0.5), M['lacquer'])               # call panel
        if bridge:
            Mb = G.frame(d, 0.0)
            G.obox(bm, Mb, (0, (R + r) / 2, 0.04), (2.0, r - R - 0.2, 0.08), M['wood'])
    if balustrade:
        rr = r - 0.12
        for a0, a1 in _arcs(_gaps(doors, stair_b, rr)):
            segs = max(2, int(20 * (a1 - a0) / (2 * math.pi)))
            for flip in (False, True):          # double-sided card (two strips, own verts)
                # thin rail strip at handrail height (no solid wall): reads as a railing line at distance
                cols = [(G.polar(rr, a0 + (a1 - a0) * j / segs, 0.94), G.polar(rr, a0 + (a1 - a0) * j / segs, 1.0)) for j in range(segs + 1)]
                vs = [(bm.verts.new(p0), bm.verts.new(p1)) for p0, p1 in cols]
                for j in range(segs):
                    q = (vs[j][0], vs[j + 1][0], vs[j + 1][1], vs[j][1])
                    f = bm.faces.new(q[::-1] if flip else q); f.material_index = M['bronze']
                    f.normal_update(); G.intend(bm, f, f.normal)


def _object_uvs(o, mi):
    """lantern_andon uses object UVs (each paper face 0..1, frame shadow at the border): map every glow face to its own
    0..1 square in its plane (glyph faces keep the centre of the tile, so letters glow evenly)"""
    me = o.data
    uv = me.uv_layers['UVMap']
    for p in me.polygons:
        if p.material_index != mi:
            continue
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
        cos = [me.vertices[me.loops[li].vertex_index].co for li in p.loop_indices]
        if p.area < 0.002:          # glyph / button sliver: sample the tile centre
            for li in p.loop_indices:
                uv.data[li].uv = (0.5, 0.5)
            continue
        us = [c[u_ax] for c in cos]; vs = [c[v_ax] for c in cos]
        if ax == 2:
            us = [c.x for c in cos]; vs = [c.y for c in cos]
        else:
            t = Vector((-n.y, n.x, 0)).normalized() if ax != 2 else Vector((1, 0, 0))
            us = [c.dot(t) for c in cos]; vs = [c.z for c in cos]
        u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        for li, uu, vv in zip(p.loop_indices, us, vs):
            uv.data[li].uv = ((uu - u0) / max(1e-6, u1 - u0), (vv - v0) / max(1e-6, v1 - v0))


def _groups(o, info):
    for name, (a, b) in info.get('vgroups', {}).items():
        g = o.vertex_groups.new(name=name)
        g.add(list(range(a, b)), 1.0, 'REPLACE')
