"""Waterfall lip and cut channel: the black rock outcrop a fall leaves from (fx_falls_sheet attaches to it).

Identifying features kept at every LOD: a black wet basalt outcrop; the worn notch / channel the water
leaves from, with a rounded polished lip that overhangs a darker undercut face; a vertical face below.

Concepts: lookbook 19 (Thunder Curtain: a ~12 m wide overhanging cave-mouth lip, the curtain falls clear
of a recessed face), 01 (hero: falls leave worn notches in black terrace rock), 32 (suite cliff: small
falls leave 0.5-1 m notches cut into black rock outcrops at each tier; tiers +10/+26/+43 m, so faces
~3-4 m between landings measured off the 0-20 m bar), 29 (B2: the fall drops through a slot cut down
into the rock), 11 (caldera crown edge). People in 19 (~1.7 m) put the Thunder lip at ~12 m wide and
the face at 6+ m; a suite fall notch in 32 is ~0.6-0.9 m wide.

Targets (default build per style, seeded +-12 %):
  style  w x d x H (m)       lip_w   notch   overhang  what it is
  flank  3.6 x 2.6 x 3.2     0.8     0.35    0.35      outcrop on a slope, short worn channel (suite / ledge falls)
  slot   4.0 x 3.0 x 3.8     0.6     1.6     0.12      narrow slot cut down and back into the face (B2 rock)
  gully  3.2 x 3.2 x 2.4     1.2     0.6     0.50      a channel cut right through the rock, U section
  lip    12  x 4.5 x 6.0     10      0.35    1.6       the Thunder lip: wide overhanging lip, undercut face
Ranges: lip width 0.5-12 m, overhang 0-2 m, notch depth 0.1-2 m, face height 1-8 m.
Proxy (3d/assets.json): none (per-fall generator, genlib defaults to 1 x 1 x 1). Proposed proxy for the
default (flank/slot/gully) build: 4.4 x 3.4 x 4.4; the lip style is 12 x 4.5 x 6 by design.

Construction: X stations (dense at the notch walls) each carry a YZ profile: toe -> front face (slight
batter, concave under the lip) -> lip underside -> rounded lip nose -> top (the notch lowers it, fading
back along the channel) -> back face; open bottom; domed fan caps on the tapered ends. Displaced along
the profile normal by ridged 3D noise (smoother in the water-worn notch). 4-7 faceted hull boulders
flank the notch and sit at the toe. Shape params are drawn once per seed, so every LOD samples the same
surface; LOD3 keeps the key stations (ends, notch walls) so the notch survives at 100 tris.

Materials (slots by part): rock = basalt_wet (wetness 0.55); bed = basalt_wet (0.98, polish -0.08) on
the notch floor and lip; face = cave_rock on the undercut and the face behind the fall.
Water: none (fx_falls_sheet). Custom props: kz_falls (lip polyline, width, drop, dir), kz_water_path
(channel centreline), kz_params.

Seeds change: style (cycles flank, slot, gully, lip), proportions +-12 %, notch position (flank),
top tilt, boulder count / layout, face lean, noise.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_falls_lip_rock as K

ASSET = 'falls_lip_rock'
FEATURES = ['black wet basalt outcrop', 'worn notch / channel the water leaves from',
            'rounded overhanging lip over an undercut face']
STYLES = ['flank', 'slot', 'gully', 'lip']
BASE = {
    'flank': dict(w=3.6, d=2.6, H=3.2, lip_w=0.8, notch=0.35, overhang=0.35, chan=1.2, wall=0.22, recess=0.08, rocks=6),
    'slot': dict(w=4.0, d=3.0, H=3.8, lip_w=0.6, notch=1.6, overhang=0.12, chan=9.0, wall=0.07, recess=0.9, rocks=5),
    'gully': dict(w=3.2, d=3.2, H=2.4, lip_w=1.2, notch=0.6, overhang=0.5, chan=9.0, wall=0.4, recess=0.0, rocks=6),
    'lip': dict(w=12.0, d=4.5, H=6.0, lip_w=10.0, notch=0.35, overhang=1.6, chan=2.5, wall=0.8, recess=0.0, rocks=7),
}
PROXY_SHEET = dict(w=4.4, d=3.4, h=4.4)      # proposed; used by .scratch/op10/lod_sheet.py for layout + check


def layout(seed, style=None, w=None, d=None, face_h=None, lip_w=None, notch=None, overhang=None, rocks=None):
    style = style or C.cycle(seed, STYLES)
    B = BASE[style]
    g = C.rng(seed, 'dims')
    j = lambda v: v * g.uniform(0.88, 1.12)
    L = dict(style=style)
    L['w'] = w if w is not None else j(B['w'])
    L['d'] = d if d is not None else j(B['d'])
    L['H'] = face_h if face_h is not None else j(B['H'])
    L['lip_w'] = min(lip_w if lip_w is not None else j(B['lip_w']), L['w'] * 0.86)
    L['notch'] = notch if notch is not None else j(B['notch'])
    L['overhang'] = overhang if overhang is not None else j(B['overhang'])
    L['chan'], L['recess'] = B['chan'], B['recess']
    L['wall'] = B['wall'] * g.uniform(0.85, 1.2)
    L['tilt'] = g.uniform(0.02, 0.09)
    L['lean'] = g.uniform(-0.04, 0.08)
    L['end'] = min(0.22 * L['w'], 1.4 + 0.05 * L['w'])
    room = max(0.0, L['w'] / 2 - L['end'] - L['lip_w'] / 2 - L['wall'] - 0.15)
    L['lip_x'] = g.uniform(-room, room) * (0.8 if style == 'flank' else 0.25)
    L['lip_t'] = max(0.25, min(0.9, 0.16 * L['H']))
    L['nose'] = min(0.45 * L['lip_t'], 0.12 + 0.03 * L['H'])
    gn = C.rng(seed, 'noise')
    L['off'] = Vector((gn.uniform(0, 90), gn.uniform(0, 90), gn.uniform(0, 90)))
    L['amp'] = 0.05 + 0.02 * L['H']
    # boulders: flanking the notch on top, and at the toe of the face
    gr = C.rng(seed, 'rocks')
    n = rocks if rocks is not None else B['rocks'] + gr.randint(-1, 1)
    R = []
    s0 = min(0.9, 0.11 * L['H'] + 0.12)
    for k in range(n):
        side = -1 if k % 2 == 0 else 1
        if k < n - 2:          # on top, beside the channel
            x = L['lip_x'] + side * (L['lip_w'] / 2 + L['wall'] + gr.uniform(0.15, 0.6) * s0 + 0.5 * s0 * (k // 2))
            y = L['d'] / 2 - gr.uniform(0.35, 1.1) * s0 - 0.4 * s0 * (k // 2)
            top = True
        else:                  # at the toe
            x = L['lip_x'] + side * (L['lip_w'] / 2 + gr.uniform(0.3, 1.0) * s0)
            y = L['d'] / 2 - L['overhang'] + gr.uniform(0.0, 0.3) * s0
            top = False
        sz = s0 * gr.uniform(0.6, 1.1)
        x = max(-L['w'] / 2 + L['end'] * 0.7, min(L['w'] / 2 - L['end'] * 0.7, x))
        R.append(dict(x=x, y=y, sx=sz, sy=sz * gr.uniform(0.7, 1.0), sz=sz * gr.uniform(0.5, 0.8), top=top, rot=gr.uniform(0, 3.14)))
    R.sort(key=lambda r: -r['sx'] * r['sy'] * r['sz'])
    L['rocks'] = R
    return L


def wn(L, x):
    """notch weight: 1 in the channel, falling to 0 over the wall width"""
    a = abs(x - L['lip_x']) - L['lip_w'] / 2
    return 1.0 - K.smoothstep(0.0, L['wall'], a)


def endf(L, x):
    """end taper 1 -> 0.32 over the last `end` metres"""
    a = L['w'] / 2 - abs(x)
    return 0.32 + 0.68 * math.sqrt(K.smoothstep(0.0, L['end'], a))


def rnd(L, x):
    """plan rounding: 0 at the centre, 1 at the ends"""
    return (x / (L['w'] / 2)) ** 2


def bulge(L, x):
    """low-frequency buttresses and bays along the face (m)"""
    return 0.14 * min(L['H'], 4.0) * noise.noise(Vector((x * 0.55, 0.3, 1.7)) + L['off'])


def yfront(L, x):
    return L['d'] / 2 - L['recess'] * wn(L, x) - 0.2 * L['d'] * rnd(L, x)


def ztop(L, x, y):
    e = endf(L, x)
    yf = L['d'] / 2
    z = L['H'] * (1 + L['tilt'] * (yf - y) / L['d']) * (1 - 0.16 * rnd(L, x)) + 0.07 * L['H'] * noise.noise(Vector((x * 0.45, y * 0.3, 4.2)) + L['off'])
    cf = 1.0 if L['chan'] >= L['d'] else K.smoothstep(yf - L['chan'] - 0.5, yf - L['chan'] + 0.3, y)
    z -= L['notch'] * wn(L, x) * cf
    return z * e


def profile(L, x, lod):
    """[(y, z, kind)] CCW seen from +X, open at the bottom"""
    e = endf(L, x)
    w = wn(L, x)
    yf = yfront(L, x)
    yb = -L['d'] / 2 + 0.15 * L['d'] * rnd(L, x)
    yc = 0.0
    sh = lambda y: yc + (y - yc) * (0.55 + 0.45 * e)      # ends shrink in depth too
    o = L['overhang'] * ((0.45 + 0.55 * w) if L['style'] != 'lip' else 1.0) * e
    zt = ztop(L, x, yf)
    lt = L['lip_t'] * (0.7 + 0.3 * e)
    zu = max(0.35 * zt, zt - lt)
    rr = L['nose'] * (1.0 + 0.6 * w)
    nf, nn, nt, nb = C.lod_pick(lod, (8, 3, 12, 3), (5, 2, 6, 2), (3, 1, 3, 1), (1, 0, 1, 0))
    P = []
    for k in range(nf + 1):                       # front face, toe -> under the lip
        t = k / nf
        y = yf - o + bulge(L, x) * (1 - 0.6 * w) - 0.09 * zu * t - L['lean'] * zu * (1 - t) - 0.12 * o * math.sin(math.pi * t) + 0.18 * min(1.0, L['H'] / 4) * (1 - t) ** 2
        P.append((sh(y), zu * t if k < nf else zu, 'face'))
    P.append((sh(yf - 0.25 * min(o, 0.4)), zu + 0.25 * (zt - zu), 'under'))   # lip underside rising to the nose
    for k in range(nn):                           # nose round-over
        a = math.pi / 2 * (k + 1) / (nn + 1)
        P.append((sh(yf - rr * (1 - math.cos(a))), zt - rr * (1 - math.sin(a)) - 0.0, 'nose'))
    P.append((sh(yf - rr), ztop(L, x, yf - rr), 'nose'))
    y0, y1 = yf - rr, yb + 0.25 * L['d'] / max(nt, 1) * 0.6
    for k in range(1, nt + 1):                    # top, front -> back
        y = y0 + (y1 - y0) * k / nt
        P.append((sh(y), ztop(L, x, y), 'top'))
    zb = ztop(L, x, yb)
    for k in range(nb + 1):                       # back face, down to the ground
        t = k / (nb + 1)
        P.append((sh(yb - 0.05 * L['d'] * math.sin(math.pi * t)), zb * (1 - t), 'back'))
    P.append((sh(yb + 0.06 * L['d']), 0.0, 'back'))
    return P


def build(lod=0, seed=1, style=None, w=None, d=None, face_h=None, lip_w=None, notch=None, overhang=None, rocks=None):
    L = layout(seed, style, w, d, face_h, lip_w, notch, overhang, rocks)
    mb = genlib.MeshBuilder()
    m_rock = mb.slot('basalt_wet', wetness=0.55)
    m_bed = mb.slot('basalt_wet', wetness=0.98, roughness_offset=-0.08)
    m_face = mb.slot('cave_rock', wetness=0.85)
    W, lx, lw, wall = L['w'], L['lip_x'], L['lip_w'], L['wall']
    keys = [-W / 2, W / 2, lx - lw / 2 - wall, lx - lw / 2, lx + lw / 2, lx + lw / 2 + wall,
            -W / 2 + L['end'], W / 2 - L['end']]
    keys = [k for k in keys if -W / 2 <= k <= W / 2]
    n_st = C.lod_pick(lod, 58, 34, 14, 6)
    segs_w = []
    sk = sorted(set(round(k, 5) for k in keys))
    for a, b in zip(sk[:-1], sk[1:]):
        m = (a + b) / 2
        segs_w.append(3.5 if 0.02 < wn(L, m) < 0.98 else (1.6 if wn(L, m) >= 0.98 else 1.0))
    xs = K.stations(keys, n_st, segs_w) if lod < 3 else sk
    amp = L['amp'] * C.lod_pick(lod, 1.0, 0.9, 0.6, 0.0)
    rows = []
    kinds = None
    for x in xs:
        pr = profile(L, x, lod)
        kinds = [k for _, _, k in pr]
        nrm = K.prof_normals([(y, z) for y, z, _ in pr])
        row = []
        for (y, z, kind), (ny, nz) in zip(pr, nrm):
            p = Vector((x, y, z))
            if amp > 0 and z > 0.02:
                smooth = 1.0 - 0.75 * wn(L, x) * (kind in ('top', 'nose')) * (y > L['d'] / 2 - L['chan'] - 0.4)
                dd = amp * smooth * K.craggy(p, L['off'], 0.55) * min(1.0, z / 0.4)
                p += Vector((0.25 * dd * (1 if x > 0 else -1) * (abs(x) > W / 2 - L['end']), ny * dd, nz * dd))
            row.append(p)
        rows.append(row)

    def mi_fn(i, j, c):
        x = c.x
        k0, k1 = kinds[j], kinds[min(j + 1, len(kinds) - 1)]
        w = wn(L, x)
        if w > 0.5 and (k0 in ('nose', 'top') and k1 in ('nose', 'top')) and c.y > L['d'] / 2 - L['chan'] - 0.3:
            return m_bed
        if k0 in ('face', 'under') and (w > 0.25 or L['style'] == 'lip') and c.z > 0.25 * L['H'] * 0.3:
            return m_face
        return m_rock
    V, faces = K.grid(mb, rows, mi_fn)
    for end, sgn in ((V[0], -1), (V[-1], 1)):
        cy = sum(v.co.y for v in end) / len(end); cz = sum(v.co.z for v in end) / len(end) * 0.8
        x0 = end[0].co.x
        faces += K.fan_cap(mb, end, (x0 + sgn * 0.12 * L['end'], cy, cz), m_rock)

    # boulders: same set at LOD0/1, the largest 4 at LOD2, none at LOD3
    keep = C.lod_pick(lod, len(L['rocks']), len(L['rocks']), 4, 0)
    npts = C.lod_pick(lod, 14, 9, 6, 0)
    gr = C.rng(seed, 'rockpts')
    for r in L['rocks'][:keep]:
        if r['top']:
            zg = min(ztop(L, r['x'], r['y'] + s) for s in (-r['sy'], 0, r['sy']))
        else:
            zg = 0.0
        g = C.rng(seed, f"rock{round(r['x'], 3)}")
        C.hull_rock(mb, (r['x'], r['y'], zg + r['sz'] * 0.35), (r['sx'], r['sy'], r['sz']), m_rock, g,
                    npts=npts, ground=zg - (0.1 if r['top'] else 0.0), rot=r['rot'])
    bmesh_faces = faces
    import bmesh
    bmesh.ops.recalc_face_normals(mb.bm, faces=bmesh_faces)
    # lip polyline for fx_falls_sheet (on the notch floor at the nose), before centring
    lip = []
    nlp = max(2, int(lw / 0.5) + 1)
    for k in range(nlp):
        x = lx - lw / 2 + lw * k / (nlp - 1)
        lip.append([round(x, 3), round(yfront(L, x), 3), round(ztop(L, x, yfront(L, x)), 3)])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    lip = [[p[0] + dx, p[1] + dy, p[2] + dz] for p in lip]
    yf = L['d'] / 2
    path = [[lx + dx, max(-L['d'] / 2 + 0.2, yf - L['chan']) + dy, ztop(L, lx, max(-L['d'] / 2 + 0.2, yf - L['chan'])) + dz],
            [lx + dx, yfront(L, lx) + dy, ztop(L, lx, yfront(L, lx)) + dz]]
    C.set_json_props(o, kz_falls=dict(lip=lip, width=round(lw, 3), drop=round(ztop(L, lx, yf), 3), dir=[0, 1, 0],
                                      overhang=round(L['overhang'], 3), fx='fx_falls_sheet'),
                     kz_water_path=path,
                     kz_params=dict(style=L['style'], w=round(W, 3), d=round(L['d'], 3), face_h=round(L['H'], 3),
                                    lip_w=round(lw, 3), notch=round(L['notch'], 3), overhang=round(L['overhang'], 3)))
    return o
