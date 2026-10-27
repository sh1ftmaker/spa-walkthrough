"""Steam room chamber and arch mouth (b1_grotto, 3 instances: the 45 / 55 / 65 C rooms).

Targets (measured):
  * refs/gen/sheet-vs-grotto-garden.png #1 'STEAM CHAMBER & ARCH' (label W 6 x D 2 x H 4 m, 1 m bar = 88 px front):
    one thick craggy basalt ring round the mouth (jambs ~1.3-1.5 m wide, crown ~1.0-1.2 m, front face standing
    0.45-0.6 m proud of the wall line), an inner timber frame (two posts + lintel) just behind the rock, a lamp
    slot in the ceiling with a light beam, two wall lanterns on the frame posts, two floor lanterns at the mouth,
    two stone steps up to the chamber floor (~0.3 m), a slab bench against the back wall (seat ~0.45 m, depth
    ~0.5 m), a warm glowing back wall. Side view: rock ~0.7 m deep at the front, timber chamber behind, D 2 m.
  * lookbook/img/16-steam-grotto.jpg: three basalt arches in a row, each with a small hanging plaque over the
    crown ('45 deg', '55 deg', '65 deg', light wood field, dark numerals), glowing hotter room by room.
    Arch clear opening ~3.0 w x 2.8 h (bathers 1.6 m for scale).
  * Defaults: clear opening 2.6-3.5 w x 2.6-3.0 h (row), overall 6.0 x 2.0 x 4.0 (proxy = sheet label).
  * Conflict: the row gives 'chamber depth 4-6 m', the sheet label and the proxy give D 2 m overall. Built to the
    sheet (default depth 2.0 overall); `depth` accepts up to 6 m for a deep chamber (then the proxy d must grow:
    see the report).

Parts (all at LOD0): craggy basalt arch ring (swept craggy section along the opening, Voronoi plate field from
gen_torii_basalt.Rock), faceted base / crown chunks, basalt threshold steps, chamber floor, hinoki lined chamber
(side walls, back wall, ceiling with the lamp slot, vertical battens), inner timber frame (posts, lintel, head
rail), slab bench (basalt slab on two blocks with three hinoki seat boards), glowing washi back panel with
kumiko bars, ceiling lamp housing over the slot (iron box, emissive lens), 2 wall lanterns on iron brackets,
2 floor lanterns on stone pads, temperature plaque on the crown hung from two iron hooks.

Parameters:
  arch_w   clear opening width 2.6-3.5 m       (default per seed: 2.9 / 3.2 / 2.7)
  arch_h   clear opening height 2.6-3.0 m      (default per seed: 2.75 / 2.95 / 2.65)
  depth    overall depth 1.6-6.0 m             (default 2.0 = sheet / proxy)
  glow     0.5 | 0.7 | 1.0                     (default per seed: 45 C 0.5, 55 C 0.7, 65 C 1.0)
  slot     True / False ceiling lamp slot      (default True)
  temp     plaque text, default '45°' / '55°' / '65°' from glow
  style    'lintel' | 'vault' | 'cleft'        (opening shape; default cycles with the seed)
Seeds change: opening style (lintel: square-shouldered mouth over the timber frame as on the sheet; vault: round
arch as in lookbook 16; cleft: tall pointed asymmetric cleft), opening size, ring thickness and crag lumps,
Voronoi plate layout, chunk positions, glow / temperature, bench board count.

Materials: basalt_wet (ring face wetness 0.5, reveal 0.7, steps / floor 0.85), hinoki dark_timber (chamber
shell, battens), hinoki wet_oiled (frame, bench boards, plaque frame), hinoki natural (plaque field),
basalt_dry tinted (0.5, 0.5, 0.55) (bench blocks), iron (lamp housing, brackets, hooks), lantern_andon (lantern
paper, lamp lens; emissive scaled by glow), washi_backlit (back panel; emissive scaled by glow),
lacquer_black (plaque numerals).
Lighting: lightmap + emissive. obj['kz_lights']: spot under the slot (down), 4 lantern points, back panel area.
FX (runtime, not built): obj['kz_fx'] = fx_steam emitter at the chamber floor centre, fx_light_shaft from the
slot to the floor. Animation: none. Pivot: base centre; +Y faces the bather (mouth side).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
from gen_torii_basalt import Rock

ASSET = 'steam_room'
FEATURES = ['rough basalt arch mouth', 'glowing chamber (hotter room by room)', 'slab bench inside',
            'ceiling slot with a lamp', 'temperature plaque']
STYLES = ['lintel', 'vault', 'cleft']
GLOWS = {0.5: '45°', 0.7: '55°', 1.0: '65°'}

RES = {
    0: dict(stations=96, prof=12, disp=1.0, crack=1.0, chunks=7, face_chunks=16, chunk_pts=14, battens=True, boards=3, kumiko=True,
            lantern=0, text_res=2, bevel=0.012, steps=2),
    1: dict(stations=34, prof=8, disp=0.85, crack=0.6, chunks=7, face_chunks=12, chunk_pts=10, battens=False, boards=3, kumiko=True,
            lantern=1, text_res=1, bevel=0.0, steps=2),
    2: dict(stations=14, prof=6, disp=0.4, crack=0.0, chunks=4, face_chunks=6, chunk_pts=8, battens=False, boards=0, kumiko=False,
            lantern=2, text_res=0, bevel=0.0, steps=1),
    3: dict(stations=7, prof=4, disp=0.0, crack=0.0, chunks=0, face_chunks=0, chunk_pts=0, battens=False, boards=0, kumiko=False,
            lantern=3, text_res=-1, bevel=0.0, steps=0),
}

# craggy section of the ring, (a, y): a = out from the opening edge (x T), y = toward the front (x Df / Db)
PROF = {
    12: [(0.0, -1.0, 'b'), (0.0, -0.3, 'b'), (0.0, 0.45, 'f'), (0.1, 0.85, 'f'), (0.3, 1.0, 'f'), (0.55, 0.95, 'f'),
         (0.8, 0.65, 'f'), (0.97, 0.2, 'f'), (1.0, -0.4, 'b'), (0.9, -1.0, 'b'), (0.6, -1.0, 'b'), (0.3, -1.0, 'b')],
    8: [(0.0, -1.0, 'b'), (0.0, 0.45, 'f'), (0.15, 0.92, 'f'), (0.5, 1.0, 'f'), (0.85, 0.6, 'f'), (1.0, -0.4, 'b'),
        (0.9, -1.0, 'b'), (0.4, -1.0, 'b')],
    6: [(0.0, -1.0, 'b'), (0.0, 0.5, 'f'), (0.3, 1.0, 'f'), (0.85, 0.65, 'f'), (1.0, -0.6, 'b'), (0.6, -1.0, 'b')],
    4: [(0.0, -1.0, 'b'), (0.0, 0.7, 'f'), (1.0, 0.6, 'f'), (1.0, -1.0, 'b')],
}


def params(seed, arch_w=None, arch_h=None, depth=None, glow=None, slot=True, temp=None, style=None):
    """all shape parameters, drawn before any LOD branch, one stream per concern"""
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'opening')
    w0 = {'lintel': 2.9, 'vault': 3.2, 'cleft': 2.7}[style]
    h0 = {'lintel': 2.75, 'vault': 2.95, 'cleft': 2.65}[style]
    if seed > 3:
        w0, h0 = g.uniform(2.6, 3.5), g.uniform(2.6, 3.0)
    W_ = 6.0
    H_ = 4.0
    P = dict(style=style, w=float(arch_w or w0), h=float(arch_h or h0), D=float(depth or 2.0), slot=bool(slot))
    P['glow'] = float(glow if glow is not None else C.cycle(seed, [0.5, 0.7, 1.0]))
    P['temp'] = temp or GLOWS.get(P['glow'], '%d°' % round(45 + (P['glow'] - 0.5) * 40))
    P['Tj'] = max(0.9, (W_ - P['w']) / 2 - 0.06)          # jamb ring thickness
    P['Tc'] = max(0.8, H_ - P['h'] - 0.08)               # crown ring thickness
    gr = C.rng(seed, 'ring')
    P['Df'] = gr.uniform(0.46, 0.56)                      # front face proud of the wall line
    P['Db'] = 0.38                                        # rock depth behind the wall line
    P['lump_ph'] = [gr.uniform(0, 6.28) for _ in range(4)]
    P['lump_a'] = gr.uniform(0.08, 0.14)
    P['cleft_skew'] = gr.uniform(-0.18, 0.18)
    P['rock_seed'] = seed
    gb = C.rng(seed, 'bench')
    P['boards'] = gb.choice([3, 3, 4])
    P['bench_h'] = gb.uniform(0.43, 0.47)
    gf = C.rng(seed, 'facechunks')
    P['face_chunks'] = []
    for k in range(16):
        u = (k + gf.uniform(0.15, 0.85)) / 16
        P['face_chunks'].append((u, gf.uniform(0.25, 0.85), gf.uniform(0.22, 0.42), gf.uniform(0, 3), gf.random()))
    P['face_chunks'].sort(key=lambda c: -c[2])         # biggest first: lower LODs keep the biggest
    gc = C.rng(seed, 'chunks')
    P['chunks'] = []
    for k in range(7):
        side = -1 if k % 2 else 1
        if k < 4:      # base chunks at the jamb feet, in front of the ring
            x = side * (P['w'] / 2 + gc.uniform(0.35, 1.1 if k < 2 else 1.6))
            P['chunks'].append(((x, P['Df'] * gc.uniform(0.55, 0.9), 0.0),
                                (gc.uniform(0.28, 0.42), gc.uniform(0.2, 0.3), gc.uniform(0.25, 0.45)), gc.uniform(0, 3)))
        else:          # crown chunks that break the top line
            x = gc.uniform(-1.6, 1.6)
            P['chunks'].append(((x, gc.uniform(-0.1, 0.15), P['h'] + P['Tc'] * gc.uniform(0.55, 0.75)),
                                (gc.uniform(0.35, 0.55), gc.uniform(0.3, 0.4), gc.uniform(0.2, 0.3)), gc.uniform(0, 3)))
    return P


def _path(P, n):
    """opening outline in x-z from the bottom right, over the top, to the bottom left: [(x, z, nx, nz)] with the
    outward (into the rock) normal; n stations"""
    w, h, style = P['w'], P['h'], P['style']
    hw = w / 2
    pts = []
    if style == 'vault':
        r = hw
        zs = h - r
        L1, L2 = zs, math.pi * r
        tot = 2 * L1 + L2
        for i in range(n + 1):
            s = tot * i / n
            if s <= L1:
                pts.append((hw, s, 1.0, 0.0))
            elif s <= L1 + L2:
                a = (s - L1) / r
                pts.append((r * math.cos(a), zs + r * math.sin(a), math.cos(a), math.sin(a)))
            else:
                pts.append((-hw, zs - (s - L1 - L2), -1.0, 0.0))
    else:
        rc = 0.55 if style == 'lintel' else hw * 0.98
        zs = h - rc if style == 'lintel' else h - hw * 1.25
        L1, Lc, Lt = zs, 0.5 * math.pi * rc, (w - 2 * rc)
        tot = 2 * L1 + 2 * Lc + Lt
        for i in range(n + 1):
            s = tot * i / n
            if s <= L1:
                pts.append((hw, s, 1.0, 0.0))
            elif s <= L1 + Lc:
                a = (s - L1) / rc
                pts.append((hw - rc + rc * math.cos(a), zs + rc * math.sin(a), math.cos(a), math.sin(a)))
            elif s <= L1 + Lc + Lt:
                t = s - L1 - Lc
                pts.append((hw - rc - t, zs + rc, 0.0, 1.0))
            elif s <= L1 + 2 * Lc + Lt:
                a = math.pi / 2 + (s - L1 - Lc - Lt) / rc
                pts.append((-hw + rc + rc * math.cos(a), zs + rc * math.sin(a), math.cos(a), math.sin(a)))
            else:
                pts.append((-hw, zs - (s - L1 - 2 * Lc - Lt), -1.0, 0.0))
        if style == 'cleft':
            # pull the shoulders up into a pointed, slightly skewed cleft
            out = []
            for x, z, nx, nz in pts:
                if z > zs:
                    t = (z - zs) / rc
                    z = z + (h - (zs + rc)) * t * (1 - abs(x) / hw) ** 0.6
                    x = x + P['cleft_skew'] * t * hw * 0.5
                out.append((x, z, nx, nz))
            pts = out
    return pts


def _ring(mb, P, R, mi_face, mi_reveal, rock):
    """craggy basalt ring swept along the opening path; open ends sit on the ground (z = 0)"""
    bm = mb.bm
    path = _path(P, R['stations'])
    prof = PROF[R['prof']]
    lp = P['lump_ph']
    rows = []
    for i, (x, z, nx, nz) in enumerate(path):
        u = i / max(1, len(path) - 1)
        lump = 1.0 + P['lump_a'] * (math.sin(6.0 * u * math.pi + lp[0]) + 0.6 * math.sin(11.0 * u * math.pi + lp[1]))
        T = (P['Tj'] * (1 - abs(nz)) + P['Tc'] * abs(nz)) * lump
        Df = P['Df'] * (1.0 + 0.12 * math.sin(9.0 * u * math.pi + lp[2]))
        Db = P['Db']
        row = []
        for a, yy, part in prof:
            y = yy * (Df if yy > 0 else Db)
            px, pz = x + nx * a * T, z + nz * a * T
            p = Vector((px, y, max(0.0, pz)))
            if R['disp'] > 0 and p.z > 0.02:
                # displace along the section normal (approx: blend of out-of-opening and +Y)
                nrm = Vector((nx * (a - 0.5), 1.4 * yy, nz * (a - 0.5))).normalized()
                if a < 0.02:
                    nrm = Vector((-nx, 0.25 * yy, -nz)).normalized()      # reveal faces the opening
                d, _ = rock.sample(p, R['disp'], R['crack'])
                p = p + nrm * d
                p.z = max(0.0, p.z)
            row.append(bm.verts.new(p))
        rows.append(row)
    faces = []
    m = len(prof)
    for A, B in zip(rows[:-1], rows[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = mi_reveal if (prof[k][0] < 0.01 and prof[k2][0] < 0.01) else mi_face
            faces.append(f)
    return faces


def build(lod, seed, arch_w=None, arch_h=None, depth=None, glow=None, slot=True, temp=None, style=None, **_):
    P = params(seed, arch_w, arch_h, depth, glow, slot, temp, style)
    R = RES[lod]
    w, h, D, Df, Db = P['w'], P['h'], P['D'], P['Df'], P['Db']
    glowk = P['glow']
    mb = genlib.MeshBuilder()
    face = mb.slot('basalt_wet', wetness=0.5)
    reveal = mb.slot('basalt_wet', wetness=0.7)
    floor = mb.slot('basalt_wet', wetness=0.85)
    shell = mb.slot('hinoki', variant='dark_timber')
    frame_w = mb.slot('hinoki', variant='wet_oiled')
    block = mb.slot('basalt_dry', tint=(0.5, 0.5, 0.55))
    iron = mb.slot('iron')
    paper = mb.slot('lantern_andon', emissive_level=round(0.55 + 0.55 * glowk, 2))
    washi = mb.slot('washi_backlit', emissive_level=round(0.35 + 0.6 * glowk, 2))
    plaque_f = mb.slot('hinoki', variant='natural')
    ink = mb.slot('lacquer_black')
    rock = Rock(C.rng(P['rock_seed'], 'rockfield'), cell=0.36, stretch=(1.0, 1.0, 1.5), amp=0.12, crack=0.08,
                width=0.2, fbm=0.1)
    lights = []

    # ------------------------------------------------------------ the rock ring + chunks
    _ring(mb, P, R, face, reveal, rock)
    gch = C.rng(seed, 'chunkshape')
    order = list(range(7))
    path = _path(P, 400)
    for (u, a, sz, rot, _) in P['face_chunks'][:R['face_chunks']]:
        x, z, nx, nz = path[int(u * 400)]
        T = P['Tj'] * (1 - abs(nz)) + P['Tc'] * abs(nz)
        c = (x + nx * a * T, P['Df'] * 0.75, max(sz * 0.5, z + nz * a * T))
        C.hull_rock(mb, c, (sz, sz * 0.7, sz * 0.85), face, gch, npts=R['chunk_pts'], rot=rot)
    for k in order[:R['chunks']]:
        c, sz, rot = P['chunks'][k]
        C.hull_rock(mb, c, sz, face, gch, npts=R['chunk_pts'], ground=0.0 if c[2] == 0 else None, rot=rot)

    # ------------------------------------------------------------ chamber shell (behind the wall line)
    cw = w + 0.5                     # interior width (side walls hide behind the jambs)
    zf = 0.30                        # chamber floor
    zc = h + 0.12                    # ceiling underside
    yb = -(D - Df - 0.2)             # back face of the shell (0.2 m left for the crag and the plaque)
    t = 0.12
    yi = yb + t                      # interior back wall face
    y0 = -Db + 0.08                  # shell front (inside the rock)
    yd = (y0 + yi) / 2
    dep = y0 - yi
    # floor slab + steps
    mb.box((0, (y0 + yb) / 2 + 0.0, zf / 2), (cw + 2 * t, y0 - yb, zf), floor)
    nst = R['steps']
    if nst:
        sw = w - 0.1
        for k in range(nst):
            zt = zf * (nst - k) / (nst + 1) if nst == 2 else zf / 2
            y_a, y_b = -Db + 0.02, Df * (0.55 + 0.3 * k / max(1, nst - 1)) if nst > 1 else Df * 0.7
            if R['bevel']:
                C.board(mb, (0, (y_a + y_b) / 2, zt / 2), (sw - 0.2 * k, y_b - y_a, zt), floor, bevel=R['bevel'])
            else:
                mb.box((0, (y_a + y_b) / 2, zt / 2), (sw - 0.2 * k, y_b - y_a, zt), floor)
    # walls and ceiling
    for sx in (-1, 1) if lod < 3 else ():
        mb.box((sx * (cw / 2 + t / 2), (y0 + yb) / 2, (zf + zc + t) / 2), (t, y0 - yb, zc + t - zf), shell)
    mb.box((0, yb + t / 2, (zf + zc) / 2), (cw, t, zc - zf), shell)
    sl_w = 0.32 if P['slot'] else 0.0
    ys = yi + dep * 0.55                    # slot line (over the bench front)
    if lod == 3:
        mb.box((0, (y0 + yb) / 2, zc + t / 2), (cw + 2 * t, y0 - yb, t), shell)
    else:
        for (ya, yb2) in ((yb, ys - sl_w / 2), (ys + sl_w / 2, y0)):
            if yb2 - ya > 0.01:
                mb.box((0, (ya + yb2) / 2, zc + t / 2), (cw + 2 * t, yb2 - ya, t), shell)
    # battens on the interior walls
    if R['battens']:
        nb = int(cw / 0.42)
        for k in range(1, nb):
            x = -cw / 2 + cw * k / nb
            mb.box((x, yi + 0.012, (zf + zc) / 2), (0.05, 0.024, zc - zf), frame_w)
        for sx in (-1, 1):
            for k in range(1, max(2, int(dep / 0.42))):
                yy = yi + dep * k / max(2, int(dep / 0.42))
                mb.box((sx * (cw / 2 - 0.012), yy, (zf + zc) / 2), (0.024, 0.05, zc - zf), frame_w)

    # ------------------------------------------------------------ inner timber frame (posts, lintel, head rail)
    fy = y0 - 0.1
    pw = 0.16
    zl = min(zc - 0.05, h - 0.02) if P['style'] == 'lintel' else zc - 0.05
    if lod <= 2:
        for sx in (-1, 1):
            x = sx * (cw / 2 - pw / 2)
            if R['bevel']:
                C.chamfered_bar(mb, (x, fy, (zf + zl) / 2), (pw, pw, zl - zf), frame_w, ch=0.015)
            else:
                mb.box((x, fy, (zf + zl) / 2), (pw, pw, zl - zf), frame_w)
        if R['bevel']:
            C.chamfered_bar(mb, (0, fy, zl - 0.09), (cw + 0.1, 0.18, 0.18), frame_w, ch=0.015, axis='x')
        else:
            mb.box((0, fy, zl - 0.09), (cw + 0.1, 0.18, 0.18), frame_w)
        if lod <= 1:
            mb.box((0, fy, zl - 0.42), (cw - 2 * pw, 0.08, 0.07), frame_w)        # head rail (nageshi)

    # ------------------------------------------------------------ bench
    bh = P['bench_h']
    bl = cw - 0.7
    bd = min(0.5, dep * 0.55)
    by = yi + bd / 2 + 0.02
    if lod <= 2:
        for sx in (-1, 1):
            mb.box((sx * bl * 0.33, by, zf + (bh - 0.09) / 2), (0.32, bd * 0.8, bh - 0.09), block)
        if R['bevel']:
            C.board(mb, (0, by, zf + bh - 0.09 + 0.03), (bl, bd, 0.06), floor, bevel=0.01)
        else:
            mb.box((0, by, zf + bh - 0.09 + 0.03), (bl, bd, 0.06), floor)
        nbd = P['boards'] if R['boards'] else 1
        gap = 0.012
        bw_ = (bd - gap * (nbd - 1)) / nbd
        for k in range(nbd):
            yy = by - bd / 2 + bw_ / 2 + k * (bw_ + gap)
            if R['bevel']:
                C.board(mb, (0, yy, zf + bh - 0.015), (bl - 0.04, bw_, 0.03), frame_w, bevel=0.006)
            else:
                mb.box((0, yy, zf + bh - 0.015), (bl - 0.04, bw_, 0.03), frame_w)
    else:
        mb.box((0, by, zf + bh / 2), (bl, bd, bh), floor)

    # ------------------------------------------------------------ glowing back panel
    pz0, pz1 = zf + bh + 0.25, zc - 0.35
    pwid = cw - 1.0
    if lod <= 2:
        mb.box((0, yi + 0.01, (pz0 + pz1) / 2), (pwid + 0.12, 0.02, pz1 - pz0 + 0.12), frame_w)
    q = [mb.bm.verts.new(v) for v in ((-pwid / 2, yi + 0.025, pz0), (pwid / 2, yi + 0.025, pz0),
                                     (pwid / 2, yi + 0.025, pz1), (-pwid / 2, yi + 0.025, pz1))]
    mb._tag([mb.bm.faces.new(q)], washi)
    if R['kumiko']:
        ncol = max(3, int(pwid / 0.45))
        for k in range(1, ncol):
            mb.box((-pwid / 2 + pwid * k / ncol, yi + 0.035, (pz0 + pz1) / 2), (0.02, 0.02, pz1 - pz0), frame_w)
        for k in (1, 2):
            mb.box((0, yi + 0.035, pz0 + (pz1 - pz0) * k / 3), (pwid, 0.02, 0.02), frame_w)
    lights.append(C.light_entry((0, yi + 0.3, (pz0 + pz1) / 2), color_k=2400, watts=round(40 * glowk), kind='area',
                                size=[round(pwid, 2), round(pz1 - pz0, 2)], dir=[0, 1, 0]))

    # ------------------------------------------------------------ ceiling slot lamp
    if P['slot'] and lod <= 2:
        if True:
            mb.box((0, ys, zc + t + 0.09), (cw - 0.6, sl_w + 0.16, 0.18), iron)      # lamp housing over the slot
        q = [mb.bm.verts.new(v) for v in ((-(cw - 0.8) / 2, ys - sl_w / 2 + 0.02, zc + t - 0.005),
                                         (-(cw - 0.8) / 2, ys + sl_w / 2 - 0.02, zc + t - 0.005),
                                         ((cw - 0.8) / 2, ys + sl_w / 2 - 0.02, zc + t - 0.005),
                                         ((cw - 0.8) / 2, ys - sl_w / 2 + 0.02, zc + t - 0.005))]
        mb._tag([mb.bm.faces.new(q)], paper)                                       # emissive lens, faces down
    if P['slot']:
        lights.append(C.light_entry((0, ys, zc + t - 0.02), color_k=2200, watts=round(60 + 60 * glowk), kind='spot',
                                    dir=[0, 0, -1], angle_deg=28))

    # ------------------------------------------------------------ lanterns: 2 on the frame posts, 2 at the mouth
    lm = dict(iron=iron, paper=paper)
    llod = R['lantern']
    for sx in (-1, 1) if llod <= 2 else ():
        x = sx * (cw / 2 - pw - 0.14)
        zl0 = zf + 1.15
        if llod <= 2:
            if llod <= 1:
                mb.box((sx * (cw / 2 - pw - 0.04), fy + 0.0, zl0 + 0.36), (0.12, 0.03, 0.03), iron)   # bracket
            ctr = C.lantern_head(mb, (x, fy, zl0), lm, llod, size=0.17, height=0.32)
        else:
            mb.box((x, fy, zl0 + 0.16), (0.15, 0.15, 0.3), paper)
            ctr = Vector((x, fy, zl0 + 0.16))
        lights.append(C.light_entry(ctr, color_k=2100, watts=round(15 + 15 * glowk)))
        xf = sx * (w / 2 - 0.3)
        yfl = Df * 0.62
        if llod <= 2:
            if llod <= 1:
                mb.box((xf, yfl, 0.03), (0.3, 0.3, 0.06), floor)
            ctr = C.lantern_head(mb, (xf, yfl, 0.06), lm, llod, size=0.24, height=0.46)
        else:
            mb.box((xf, yfl, 0.25), (0.22, 0.22, 0.46), paper)
            ctr = Vector((xf, yfl, 0.25))
        lights.append(C.light_entry(ctr, color_k=2000, watts=20))

    # ------------------------------------------------------------ temperature plaque on the crown
    if R['text_res'] >= -1:
        path = _path(P, 40)
        ztop = max(z for _, z, _, _ in path)
        tops = [x for x, z, _, _ in path if z > ztop - 0.01]
        xtop = sum(tops) / len(tops)
        pzc = ztop + 0.36
        PW, PH = 0.62, 0.42
        yp = Df + 0.06
        if lod <= 1:
            for sx in (-1, 1):                              # iron hooks from the rock
                C.stick(mb, (xtop + sx * 0.2, Df * 0.4, pzc + PH / 2 + 0.12), (xtop + sx * 0.2, yp, pzc + PH / 2 + 0.12),
                        0.01, 0.01, iron, segs=4)
                C.stick(mb, (xtop + sx * 0.2, yp, pzc + PH / 2 + 0.12), (xtop + sx * 0.2, yp, pzc + PH / 2 - 0.01),
                        0.008, 0.008, iron, segs=4)
        if R['bevel']:
            C.board(mb, (xtop, yp - 0.02, pzc), (PW, 0.04, PH), frame_w, bevel=0.008)
        else:
            mb.box((xtop, yp - 0.02, pzc), (PW, 0.04, PH), frame_w)
        if lod <= 2:
            mb.box((xtop, yp - 0.12, pzc), (PW * 0.6, 0.16, PH * 0.5), frame_w)            # backing into the rock
        q = [mb.bm.verts.new(v) for v in ((xtop + PW / 2 - 0.045, yp + 0.001, pzc - PH / 2 + 0.045),
                                         (xtop - PW / 2 + 0.045, yp + 0.001, pzc - PH / 2 + 0.045),
                                         (xtop - PW / 2 + 0.045, yp + 0.001, pzc + PH / 2 - 0.045),
                                         (xtop + PW / 2 - 0.045, yp + 0.001, pzc + PH / 2 - 0.045))]
        f = mb.bm.faces.new(q[::-1])
        mb._tag([f], plaque_f)
        if R['text_res'] >= 1:
            C.tracked_text(mb, P['temp'], xtop, pzc - 0.03, yp + 0.001, 0.16, ink, depth=0.006, tracking=0.05,
                           res=R['text_res'])
        elif R['text_res'] == 0:
            for k, dx in enumerate((-0.07, 0.05)):
                mb.box((xtop + dx, yp + 0.004, pzc - 0.03), (0.09, 0.008, 0.16), ink)

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    for L in lights:
        L['pos'] = [round(L['pos'][0] + dx, 4), round(L['pos'][1] + dy, 4), round(L['pos'][2] + dz, 4)]
    yy = round(ys + dy, 3)
    fx = [dict(kind='fx_steam', pos=[round(dx, 3), yy, round(zf + 0.05, 3)], rate=round(0.4 + 0.6 * glowk, 2))]
    if P['slot']:
        fx.append(dict(kind='fx_light_shaft', top=[round(dx, 3), yy, round(zc, 3)], bottom=[round(dx, 3), yy, round(zf, 3)],
                       width=0.32))
    C.set_json_props(o, kz_lights=lights, kz_fx=fx,
                     kz_params=dict(style=P['style'], arch_w=round(w, 3), arch_h=round(h, 3), depth=round(D, 3),
                                    glow=glowk, slot=P['slot'], temp=P['temp']))
    return genlib.finish(o)
