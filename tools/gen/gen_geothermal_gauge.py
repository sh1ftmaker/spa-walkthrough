"""Brass geothermal gauge (geothermal_gauge) on the rock wall of the B4 lift lobby (b4_lobby): a round
brass dial with a needle in a riveted iron housing, fed by small pipes.

Targets
  * lookbook 36 (B4 plan) and dh-lobby-b4 (B4 lift lobby) place the lobby but do not draw the gauge at a
    readable size (no sheet-mod-b4 sheet yet). Built to the asset row: 0.9 x 0.5 x 1.6 m, dial r 0.3-0.5
    (bezel radius; r > 0.4 needs w > 0.9, so the default build uses 0.30-0.36), housing h 1.4-1.8.
    Scale from people (1.7 m): dial centre at ~1.2-1.3 m, the dial reads at eye level.
  Built: housing h 1.5-1.7 (default 1.6), dial r 0.30-0.36, bezel 45 mm wide, cabinet 0.56 w x 0.20 d,
  drum 0.24 deep, 2-4 pipes r 30-38 mm with flanges, one valve hand wheel r 0.09.

Construction (front +Y, back flat against the wall at -Y; pivot at the base centre)
  * housing: iron plinth plate, iron cabinet with a riveted front frame, iron drum behind the dial with a
    ring of rivets (`iron`).
  * dial: bronze bezel (lathe about Y, `bronze` smooth), white enamel face (`ceramic` white), 31 printed ticks
    over 270 deg (7 major), a glowing red zone at the hot end (`lava`, emissive 0.7), bronze hub, black needle
    (`lacquer_black`); no glass lens (a realtime glass dome hid the face on the sheet).
  * sight glass under the dial: a glowing `lava` core in a `lava_glass` sleeve and a bronze cage (magma level), and a bronze name plate
    with raised 地熱 (`lacquer_black`).
  * pipes: bronze smooth tubes from the floor with rounded elbows into the cabinet sides / the wall,
    lathe flanges at each joint; a valve hand wheel on the right pipe.
  LOD1: 16-seg lathes, rivets as 4-sided studs, ticks as quads. LOD2: no rivets, 7 major ticks, no wheel
  spokes or text (plate kept). LOD3: drum with the enamel face as its cap, cabinet, needle, two pipe
  blocks (~60 tris).
Animation: rigid. Needle verts carry int attribute '_needle' = 1; obj['kz_anim'] =
  {type rigid, needle: {attr, pivot kz_needle_pivot, axis [0, 1, 0], drive 'output', deg_min, deg_max}}:
  the needle angle = deg_min + output * (deg_max - deg_min) plus a slow drift. Lighting: lightmap (the
  sight glass and red zone are emissive lava_glass, so a small kz_lights entry is recorded for the bake).

Parameters (build kwargs; proxy 0.9 x 0.5 x 1.6 m)
  dial_r   0.30-0.42 m bezel radius      housing_h  1.4-1.8 m      pipes  2-4
  needle   rest angle as output 0-1 (default seeded 0.45-0.7)
Seeds change: housing height, dial radius, pipe count and routing (side elbows / wall return / capillary
to the drum), valve side, sight glass length, needle rest.
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_geothermal_gauge as K

ASSET = 'geothermal_gauge'
FEATURES = ['round brass dial with needle', 'riveted iron housing on the wall', 'small pipes']
DEG0, DEG1 = -135.0, 135.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build(lod, seed, dial_r=None, housing_h=None, pipes=None, needle=None):
    g = C.rng(seed, 'dims')
    H = _clamp(housing_h, 1.4, 1.8) if housing_h else g.uniform(1.52, 1.64)
    R = _clamp(dial_r, 0.3, 0.42) if dial_r else g.uniform(0.30, 0.36)
    gp = C.rng(seed, 'pipes')
    npipe = int(_clamp(pipes, 2, 4)) if pipes else gp.choice([2, 3, 4])
    valve_side = gp.choice([-1, 1])
    sight_l = gp.uniform(0.26, 0.36)
    out = _clamp(needle, 0.0, 1.0) if needle is not None else C.rng(seed, 'needle').uniform(0.45, 0.7)

    mb = genlib.MeshBuilder()
    m_iron = mb.slot('iron')
    m_brass = mb.slot('bronze', variant='smooth')
    m_face = mb.slot('ceramic', variant='white')
    m_glow = mb.slot('lava', emissive_level=0.7, scale=0.25)
    m_lglass = mb.slot('lava_glass')
    m_black = mb.slot('lacquer_black')

    yb = -0.20                                  # wall plane (back of the housing)
    RH = R + 0.05                               # drum radius
    zc = H - RH                                 # dial centre
    WC, DC = 0.56, 0.20                         # cabinet
    DD = 0.24                                   # drum depth
    yf, yd = yb + DC, yb + DD                   # cabinet front, drum front
    zc_top = zc - RH * 0.55                     # cabinet top (tucked under the drum)
    lay = mb.bm.verts.layers.int.new('_needle')
    th_n = math.radians(DEG0 + out * (DEG1 - DEG0))

    def needle(y0, tris_only=False):
        L, Lb = R * 0.86, R * 0.2
        pts = [(0.0, -Lb), (0.012, 0.0), (0.004, L), (-0.004, L), (-0.012, 0.0)]
        if tris_only:
            pts = [(0.0, -Lb), (0.01, 0.0), (0.0, L), (-0.01, 0.0)]
        c, s = math.cos(th_n), math.sin(th_n)
        world = [(-(px * c + py * s), px * -s + py * c) for px, py in pts]   # rotate clockwise for the viewer
        world = [(x, zc + z) for x, z in world]
        bm = mb.bm
        F = [bm.verts.new((x, y0 + 0.006, z)) for x, z in world]
        fs = [bm.faces.new(F)]
        if not tris_only:
            B = [bm.verts.new((x, y0, z)) for x, z in world]
            fs.append(bm.faces.new(B[::-1]))
            n = len(world)
            for i in range(n):
                j = (i + 1) % n
                fs.append(bm.faces.new((B[i], B[j], F[j], F[i])))
            F += B
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        for v in F:
            v[lay] = 1
        mb._tag(fs, m_black)

    if lod == 3:
        mb.box((0, yb + DC / 2, zc_top / 2), (WC, DC, zc_top), m_iron)
        vs, fs = K.lathe_y(mb, [(RH, 0.0), (RH, DD), (0.0, DD)], 8, m_iron, (0, yb, zc), phase=math.pi / 8, closed=False)
        cap = max(fs, key=lambda f: sum(v.co.y for v in f.verts) / len(f.verts))
        for f in fs:
            if all(abs(v.co.y - (yb + DD)) < 1e-4 for v in f.verts):
                f.material_index = m_face
        needle(yb + DD, tris_only=True)
        for sx in (-1, 1):
            mb.box((sx * (WC / 2 + 0.05), yb + 0.1, 0.3), (0.07, 0.07, 0.6), m_brass)
        dx, dy, dz = C.centre_base(mb, centre_x=False)
        o = genlib.finish(mb.to_object(ASSET))
        return _props(o, zc, yb + DD, dx, dy, dz, sight_l, R, out)

    seg = C.lod_pick(lod, 24, 14, 8)
    # plinth plate and cabinet with a front frame
    C.board(mb, (0, yb + 0.15, 0.025), (WC + 0.12, 0.30, 0.05), m_iron, bevel=C.lod_pick(lod, 0.006, 0.004, 0.0), segs=1)
    C.board(mb, (0, yb + DC / 2, 0.05 + (zc_top - 0.05) / 2), (WC, DC, zc_top - 0.05), m_iron,
            bevel=C.lod_pick(lod, 0.01, 0.006, 0.0), segs=C.lod_pick(lod, 2, 1, 1))
    if lod <= 1:
        for sx in (-1, 1):       # raised frame stiles on the cabinet front
            mb.box((sx * (WC / 2 - 0.03), yf + 0.005, 0.05 + (zc_top - 0.05) / 2), (0.05, 0.01, zc_top - 0.07), m_iron)
        for zz in (0.1, zc_top - 0.04):
            mb.box((0, yf + 0.005, zz), (WC - 0.11, 0.01, 0.05), m_iron)
    # drum behind the dial
    K.lathe_y(mb, [(0.0, 0.0), (RH, 0.0), (RH, DD - 0.012), (RH - 0.012, DD), (0.0, DD)], seg, m_iron, (0, yb, zc))
    # bezel
    bez = [(RH - 0.006, 0.0), (RH - 0.004, 0.014), (RH - 0.02, 0.034), (R + 0.016, 0.04), (R, 0.03), (R - 0.004, 0.012)]
    if lod == 2:
        bez = [(RH - 0.006, 0.0), (RH - 0.012, 0.03), (R, 0.03), (R - 0.004, 0.012)]
    K.lathe_y(mb, bez, seg, m_brass, (0, yd, zc), closed=False)
    # enamel face, slightly recessed
    yface = yd + 0.012
    K.lathe_y(mb, [(0.0, 0.0), (R, 0.0), (R, 0.006), (0.0, 0.006)], seg, m_face, (0, yd, zc))
    ytick = yface + 0.0
    nt = C.lod_pick(lod, 31, 31, 7)
    for k in range(nt):
        frac = k / (nt - 1)
        th = math.radians(DEG0 + frac * (DEG1 - DEG0))
        major = (k % 5 == 0) if nt == 31 else True
        r0, r1 = (R * 0.74 if major else R * 0.82), R * 0.92
        w = 0.01 if major else 0.005
        rm = (r0 + r1) / 2
        x, z = K.dial_xz(0, zc, rm, th)
        if True:          # printed enamel ticks: single quads just proud of the face
            bm = mb.bm
            ca, sa = math.cos(th), math.sin(th)
            corners = [(-w / 2, -(r1 - r0) / 2), (w / 2, -(r1 - r0) / 2), (w / 2, (r1 - r0) / 2), (-w / 2, (r1 - r0) / 2)]
            vs = [bm.verts.new((x + px * ca - pz * sa, ytick + 0.003, z + px * sa + pz * ca)) for px, pz in corners]
            f = bm.faces.new(vs)
            bmesh.ops.recalc_face_normals(bm, faces=[f])
            if f.normal.y < 0:
                f.normal_flip()
            mb._tag([f], m_black)
    # red hot zone (last 45 deg)
    K.annulus_band(mb, 0, zc, ytick, R * 0.93, R * 0.985, math.radians(DEG1 - 45), math.radians(DEG1),
                   C.lod_pick(lod, 8, 4, 2), m_glow, depth=0.003)
    # hub + needle
    if lod <= 1:
        K.lathe_y(mb, [(0.03, 0.0), (0.03, 0.012), (0.018, 0.022), (0.0, 0.024)], C.lod_pick(lod, 12, 8, 6),
                  m_brass, (0, ytick, zc), closed=False)
    needle(ytick + 0.012)
    # no glass lens: an Eevee/realtime glass dome renders the dial black and pops at the LOD2 switch
    # rivets: a ring on the drum face outside the bezel, and down both cabinet stiles
    if lod <= 1:
        studs = []
        nr = 16
        for k in range(nr):
            a = 2 * math.pi * (k + 0.5) / nr
            studs.append((math.cos(a) * (RH - 0.0), yd - 0.001, zc + math.sin(a) * (RH + 0.0), 'y'))
        nz = max(4, int((zc_top - 0.15) / 0.16))
        for sx in (-1, 1):
            for k in range(nz):
                zz = 0.12 + (zc_top - 0.2) * k / (nz - 1)
                studs.append((sx * (WC / 2 - 0.03), yf + 0.01, zz, 'y'))
        for x, y, z, _ in studs:
            if lod == 0:
                K.lathe_y(mb, [(0.009, -0.002), (0.007, 0.005), (0.0, 0.008)], 5, m_iron, (x, y, z), closed=False)
            else:
                K.lathe_y(mb, [(0.008, 0.0), (0.0, 0.007)], 4, m_iron, (x, y, z), closed=False, phase=math.pi / 4)
    # name plate with 地熱 and the sight glass (magma level) on the cabinet front
    zp = zc - RH - 0.075
    C.board(mb, (0, yf + 0.006, zp), (0.24, 0.012, 0.085), m_brass, bevel=C.lod_pick(lod, 0.003, 0.0, 0.0), segs=1)
    if lod == 0:
        C.text_solid(mb, '地熱', 0.0, zp, yf + 0.012, 0.055, m_black, depth=C.lod_pick(lod, 0.003, 0.002), res=1)
    zs0 = zp - 0.1 - sight_l
    ys = yf + 0.055
    sseg = C.lod_pick(lod, 12, 8, 6)
    C.lathe(mb, [(0.0, 0.0), (0.02, 0.0), (0.02, sight_l), (0.0, sight_l)], sseg, m_glow, base=(0, ys, zs0))
    if lod <= 1:     # thick lava-glass sleeve round the glowing core
        C.lathe(mb, [(0.028, 0.0), (0.028, sight_l)], sseg, m_lglass, base=(0, ys, zs0), closed=False)
    for zz, s in ((zs0 - 0.03, 1), (zs0 + sight_l, 1)):
        if lod == 2:
            mb.box((0, ys - 0.01, zz + 0.015), (0.09, 0.09 + 0.02, 0.03), m_brass)
            continue
        C.lathe(mb, [(0.0, 0.0), (0.045, 0.0), (0.045, 0.03), (0.0, 0.03)], sseg, m_brass, base=(0, ys, zz))
        mb.box((0, (yf + ys) / 2, zz + 0.015), (0.04, ys - yf, 0.025), m_brass)
    if lod == 0:
        for k in range(3):
            a = 2 * math.pi * k / 3 + math.pi / 2
            px, py = 0.038 * math.cos(a), ys + 0.038 * math.sin(a)
            C.stick(mb, (px, py, zs0), (px, py, zs0 + sight_l), 0.005, 0.005, m_brass, segs=4)

    # pipes: (corner points, radius)
    pr = gp.uniform(0.03, 0.038)
    xo = WC / 2 + 0.07
    yp = yb + 0.1
    routes = [
        ([(-xo, yp, 0.0), (-xo, yp, 0.62), (-WC / 2, yp, 0.62)], pr),                       # left: floor -> cabinet side
        ([(xo, yp, 0.0), (xo, yp, 0.42), (WC / 2, yp, 0.42)], pr),                          # right: floor -> cabinet side
    ]
    if npipe >= 3:     # return into the wall from the left elbow height
        routes.append(([(-WC / 2, yp - 0.04, 1.0), (-xo, yp - 0.04, 1.0), (-xo, yb + 0.0, 1.0)], pr * 0.7))
    if npipe >= 4:     # capillary from the cabinet top up into the drum side
        ang = math.radians(60)
        routes.append(([(WC / 2 - 0.06, yb + 0.1, zc_top), (WC / 2 - 0.06, yb + 0.1, zc_top + 0.06),
                        (RH * math.cos(ang) + 0.02, yb + 0.1, zc - RH * math.sin(ang) + 0.0)], 0.012))
    psides = C.lod_pick(lod, 8, 5, 4)
    for k, (cp, rad) in enumerate(routes):
        if lod == 2 and rad < 0.02:
            continue                                  # capillary: a small part, dropped at LOD2
        path = K.elbow_path(cp, max(rad * 2.2, 0.03), C.lod_pick(lod, 3, 2, 1))
        C.tube(mb, path, [rad] * len(path), m_brass, sides=psides if rad > 0.02 else C.lod_pick(lod, 6, 4, 4), cap0=True, cap1=True)
        if rad > 0.02 and lod == 0:
            # flanges where the pipe meets the floor / the housing / the wall
            a, b = Vector(cp[0]), Vector(cp[1])
            if abs(a.z) < 1e-3:
                C.lathe(mb, [(0.0, 0.0), (rad + 0.025, 0.0), (rad + 0.025, 0.018), (rad + 0.008, 0.03), (0.0, 0.03)],
                        psides, m_brass, base=(a.x, a.y, 0.0))
            e, f = Vector(cp[-2]), Vector(cp[-1])
            d = (f - e).normalized()
            fc = f - d * 0.012
            C.stick(mb, fc - d * 0.012, fc + d * 0.012, rad + 0.02, rad + 0.02, m_brass, segs=psides)
    # valve hand wheel on the right (or left) floor pipe
    vx = valve_side * xo
    vz = 0.28 if valve_side > 0 else 0.4
    if lod <= 1:
        C.stick(mb, (vx, yp, vz), (vx, yp + 0.11, vz), 0.012, 0.012, m_brass, segs=6)
        C.lathe(mb, [(0.0, -0.04), (pr + 0.012, -0.04), (pr + 0.012, 0.04), (0.0, 0.04)], C.lod_pick(lod, 10, 6), m_brass,
                base=(vx, yp, vz))
        K.hand_wheel(mb, (vx, yp + 0.12, vz), 0.085, m_iron, lod)

    dx, dy, dz = C.centre_base(mb, centre_x=False)
    o = genlib.finish(mb.to_object(ASSET))
    return _props(o, zc, ytick + 0.012, dx, dy, dz, sight_l, R, out)


def _props(o, zc, yn, dx, dy, dz, sight_l, R, out):
    pivot = [0.0 + dx, round(yn + dy, 4), round(zc + dz, 4)]
    C.set_json_props(o, kz_needle_pivot=pivot,
                     kz_anim=dict(type='rigid', needle=dict(attr='_needle', value=1, pivot='kz_needle_pivot', axis=[0, 1, 0],
                                                            drive='output', deg_min=DEG0, deg_max=DEG1,
                                                            sense='clockwise seen from +Y',
                                                            drift=dict(amp_deg=3.0, period=11.0))),
                     kz_lights=[C.light_entry((0.0, 0.0, max(0.3, zc + dz - R - 0.4)), color_k=1500, watts=4,
                                              note='lava_glass sight glass glow')],
                     kz_wall_y=round(-0.20 + dy, 4),
                     kz_params=dict(dial_r=round(R, 3), output_rest=round(out, 3), sight_l=round(sight_l, 3)))
    return o
