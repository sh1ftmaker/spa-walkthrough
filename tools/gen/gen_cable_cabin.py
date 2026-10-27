"""Cable lift cabin (cable_cabin): small barrel-sided glass cabin in a dark bronze frame, hanging from a gooseneck grip
arm with a four-sheave carriage on the twin cables, a lamp under the floor.

Concept: refs/gen/sheet-vs-lift-cable.png panel 4 "Cable lift cabin, W 2.4 x D 3 x H 2.6 m (cabin only)" (front +
side), panel 3 (cabin hanging in the station bay), lookbook 30 (summit plan: cabin on the line at D4).
Measured (2x crop .scratch/op16/m_cabin.png, 1 m bar = 143 px):
  * door face 2.9 m wide, end face 2.2 m, body (roof to pan) 2.7 m, lamp ~0.35 m below the pan; whole thing incl.
    grip ~5.1 m. The labels say 2.4 x 3.0 x 2.6; the bar runs ~10-20 % large, so the labels are used, and the
    drawn ratios are kept: the DOOR face is the long one (3.0 m), the end face the short one (2.4 m).
  * barrel sides: widest at the waist, ~0.93 at the top band and ~0.95 at the floor band; domed roof ~0.3 m;
    rounded plan corners r ~0.35 m
  * frame: dark bronze mullions at the corners and thirds, polished bands at floor, waist (dado ~0.55 m above the
    floor) and cornice; a double glass door with a centre seam on the long face; lower fret panels on the ends;
    a bench inside each end; small lanterns inside the upper corners
  * gooseneck arm ~0.12 m section rising ~1.6 m from a roof mount, bowed ~0.35 m sideways, to a carriage with
    four sheaves (two per cable) riding twin cables ~0.4 m apart
Orientation: the cable runs along Y (d = 3.0 m, the long door faces look out along +-X onto the station platforms),
+Y is the leading end. Pivot: base centre under the lamp (z = 0).
Proxy (assets.json 2.4 x 3.0 x 2.6) covers the cabin only; with the grip arm (an identifying feature) the build is
4.6 m tall: PROXY_SHEET proposes h 4.7.

Parameters build(lod, seed, **p)
  w 2.0-3.0 (seed 2.4 / 2.2 / 2.6)   d 2.4-3.0 (3.0 / 2.7 / 2.8)   h body 2.4-3.0 (2.6 / 2.75 / 2.45)
  bulge 0-0.1 barrel (0.06 / 0.1 / 0.02)   bars 1-2 end mullions (1 / 2 / 2)   roof 'dome' | 'tall' | 'flat'
  lamp True/False (under-floor lamp lit; geometry always present)
Seeds change: proportion (standard / tall narrow barrel / squat square), bulge, end mullion count, roof form
(low dome / tall dome with finial / flat cornice roof), arm bow side.

Materials (slots by part): frame bronze (wear 0, normal 0.03: dark); polish bronze smooth (bands, handles,
sheaves); glass glass_clear (closed 10 mm shell; the row's lava_glass is not used for clear cabin glass, GUIDE 7);
panel lacquer_dark (lower end panels); wood hinoki wet_oiled (floor, benches); paper lantern_paper (under-floor lamp,
emissive), lantern_andon (inside lanterns); ceiling washi_backlit 0.8; core lantern_paper 0.3 tint (0.45, 0.32, 0.22) (LOD2/3 dim amber inner
volume, so the cabin reads lit at distance).
Animation (rigid): obj['kz_anim'] = travel along the cable_line (kz_cables) + gentle swing about the grip axis.
obj['kz_grip'] = cable attach (x of each cable, z of the cable centre). Lights: kz_lights (lamp + ceiling +
lanterns), obj['kz_light'] = ceiling (probe, moving). Lighting: probe + emissive.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_cable_station as K

ASSET = 'cable_cabin'
FEATURES = ['glass cabin', 'bronze frame with bands', 'grip arm with sheave carriage', 'lamp under the floor',
            'double glass door']
PROXY_SHEET = dict(w=2.6, d=3.1, h=4.8)        # proposed: cabin 2.4 x 3.0 x 2.6 + grip arm (assets.json h 2.6)
STYLES = ['dome', 'tall', 'flat']
GAUGE = 0.40                                   # twin cable spacing (x)
CABLE_R = 0.028

SEEDS = {1: dict(w=2.4, d=3.0, h=2.6, bulge=0.06, bars=1, roof='dome', bow=1),
         2: dict(w=2.2, d=2.7, h=2.65, bulge=0.10, bars=2, roof='tall', bow=-1),
         3: dict(w=2.6, d=2.8, h=2.45, bulge=0.02, bars=2, roof='flat', bow=1)}


def params(seed, **p):
    P = dict(SEEDS[(seed - 1) % 3 + 1])
    g = C.rng(seed, 'cabin')
    if seed > 3:
        P['w'] *= g.uniform(0.95, 1.05); P['h'] *= g.uniform(0.95, 1.05)
    P['lamp'] = True
    for k, v in p.items():
        if v is not None and k in ('w', 'd', 'h', 'bulge', 'bars', 'roof', 'bow', 'lamp'):
            P[k] = v
    return P


def outline(W, D, rc, m, mids):
    """rounded-rect outline (ccw from +X/+Y corner) with `mids` extra points on each straight edge.
    Returns pts and a dict of named indices: corner mids c0..c3, edge e0 (+Y), e1 (-X), e2 (-Y), e3 (+X) lists."""
    pts, idx = [], {}
    corners = [((W / 2 - rc), (D / 2 - rc), 0.0), ((-W / 2 + rc), (D / 2 - rc), math.pi / 2),
               ((-W / 2 + rc), (-D / 2 + rc), math.pi), ((W / 2 - rc), (-D / 2 + rc), 1.5 * math.pi)]
    for i, (cx, cy, a0) in enumerate(corners):
        for k in range(m + 1):
            a = a0 + (math.pi / 2) * k / m
            if k == m // 2:
                idx[f'c{i}'] = len(pts)
            pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
        nx, ny, _ = corners[(i + 1) % 4]
        e = {0: 'e0', 1: 'e1', 2: 'e2', 3: 'e3'}[i]
        sx, sy = pts[-1]
        ex = nx + rc * math.cos(corners[(i + 1) % 4][2]); ey = ny + rc * math.sin(corners[(i + 1) % 4][2])
        idx[e] = []
        for j in range(1, mids + 1):
            f = j / (mids + 1)
            idx[e].append(len(pts))
            pts.append((sx + (ex - sx) * f, sy + (ey - sy) * f))
    return pts, idx


def build(lod, seed, **p):
    P = params(seed, **p)
    W, D, Hb = P['w'], P['d'], P['h']
    bul = P['bulge']
    mb = genlib.MeshBuilder()
    M = dict(frame=mb.slot('bronze', wear=0.0, normal_strength=0.03),
             polish=mb.slot('bronze', variant='smooth', wear=0.6, roughness_offset=-0.1),
             glass=mb.slot('glass_clear'), panel=mb.slot('lacquer_dark', wear=0.1),
             wood=mb.slot('hinoki', variant='wet_oiled'),
             lamp=mb.slot('lantern_paper', emissive_level=1.0 if P['lamp'] else 0.0),
             andon=mb.slot('lantern_andon', emissive_level=0.9), ceil=mb.slot('washi_backlit', emissive_level=0.8),
             core=mb.slot('lantern_paper', emissive_level=0.3, tint=(0.45, 0.32, 0.22)))
    rc = 0.36 * min(W, D) / 2.4
    m = C.lod_pick(lod, 4, 2, 2, 1)
    mids = C.lod_pick(lod, 3, 3, 1, 0)
    # heights (body h = pan bottom -> roof top; the lamp hangs 0.25 below)
    zl = 0.25                                   # pan bottom
    zf = zl + 0.17                              # floor band / glass bottom
    roof_h = {'dome': 0.30, 'tall': 0.42, 'flat': 0.16}[P['roof']]
    zt = zl + Hb - roof_h                       # cornice / glass top
    zd = zf + 0.55                              # dado (waist) rail
    s_waist = 1.0

    def s_of(z):                                # barrel scale of the plan at height z (1 at the waist)
        zm = (zf + zt) / 2 + 0.1
        u = (z - zm) / ((zt - zf) / 2)
        return s_waist - bul * u * u

    def ring(z, s=None, inset=0.0):
        s = s_of(z) if s is None else s
        pts, _ = outline(W * s - 2 * inset, D * s - 2 * inset, max(0.02, rc * s - inset), m, mids)
        return [Vector((x, y, z)) for x, y in pts]

    _, IDX = outline(W, D, rc, m, mids)
    N = len(_)
    bm = mb.bm

    def loft(rows, mi, close_bottom=False, close_top=False):
        vrows = [[bm.verts.new(v) for v in r] for r in rows]
        fs = []
        for A, B in zip(vrows[:-1], vrows[1:]):
            fs += C.bridge_rings(bm, A, B)
        if close_bottom:
            fs.append(bm.faces.new(vrows[0][::-1]))
        if close_top:
            fs.append(bm.faces.new(vrows[-1]))
        mb._tag(fs, mi)
        return vrows, fs

    nz = C.lod_pick(lod, 5, 4, 1, 1)
    zs = [zf + (zt - zf) * i / nz for i in range(nz + 1)]
    # ---- glass shell (closed 10 mm solid at LOD0-1, single surface at LOD2, core-lit band at LOD3)
    if lod == 0:
        outer = [ring(z) for z in zs]
        inner = [ring(z, inset=0.01) for z in zs]
        vo, fo = loft(outer, M['glass'])
        vi, fi = loft(inner, M['glass'])
        for f in fi:
            f.normal_flip()
        fs = C.bridge_rings(bm, vi[0], vo[0]) + C.bridge_rings(bm, vo[-1], vi[-1])
        mb._tag(fs, M['glass'])
    elif lod == 1:
        loft([ring(z) for z in zs], M['glass'])
    if lod == 2:
        loft([ring(z) for z in zs], M['glass'])
        mb.box((0, 0, (zf + zt) / 2), (W * 0.8, D * 0.85, (zt - zf) * 0.85), M['core'])
    # ---- pan (under the floor) and roof
    pan_rows = [ring(zl, s=0.84), ring(zl + 0.08, s=0.95), ring(zf, s=s_of(zf) + 0.01)]
    if lod == 3:
        rows = [ring(zl, s=0.86), ring(zf), ring(zt), ring(zl + Hb, s=0.55)]
        vr = [[bm.verts.new(v) for v in r] for r in rows]
        mb._tag(C.bridge_rings(bm, vr[0], vr[1]) + [bm.faces.new(vr[0][::-1])], M['frame'])
        mb._tag(C.bridge_rings(bm, vr[1], vr[2]), M['core'])
        mb._tag(C.bridge_rings(bm, vr[2], vr[3]) + [bm.faces.new(vr[3])], M['frame'])
    else:
        loft(pan_rows, M['frame'], close_bottom=True)
        st = s_of(zt)
        if P['roof'] == 'flat':
            rr = [(0.0, st + 0.015), (0.06, st + 0.04), (0.1, st + 0.04), (0.12, st * 0.9), (roof_h, st * 0.86)]
        elif P['roof'] == 'tall':
            rr = [(0.0, st + 0.015), (0.06, st + 0.035), (0.1, st * 0.97), (0.22, st * 0.84), (0.34, st * 0.6), (roof_h, st * 0.3)]
        else:
            rr = [(0.0, st + 0.015), (0.06, st + 0.035), (0.1, st * 0.96), (0.2, st * 0.8), (roof_h, st * 0.45)]
        if lod == 2:
            rr = [rr[0], rr[2], rr[-1]]
        loft([ring(zt + dz, s=s) for dz, s in rr], M['frame'], close_bottom=True, close_top=True)
    # ---- floor, ceiling, interior
    if lod <= 1:
        fl = [(v.x, v.y) for v in ring(zf + 0.02, inset=0.03)]
        mb.poly_prism(fl, zf - 0.02, zf + 0.03, M['wood'])
        ce = [(v.x, v.y) for v in ring(zt - 0.03, inset=0.06)]
        if lod == 0:
            mb.poly_prism(ce, zt - 0.05, zt - 0.02, M['ceil'])
        else:
            mb.box((0, 0, zt - 0.035), (W * 0.6, D * 0.6, 0.03), M['ceil'])
        for sy in (-1, 1):                     # benches along the ends
            yb = sy * (D * s_of(zf + 0.45) / 2 - 0.32)
            K.box(mb, (0, yb, zf + 0.44), (W * 0.62, 0.42, 0.06), M['wood'], bevel=C.lod_pick(lod, 0.01, 0.0))
            K.box(mb, (0, yb + sy * 0.16, zf + 0.75), (W * 0.62, 0.05, 0.4), M['wood'], bevel=C.lod_pick(lod, 0.008, 0.0))
            for sx in (-1, 1):
                mb.box((sx * W * 0.27, yb, zf + 0.21), (0.05, 0.36, 0.42), M['wood'])
    lights = []
    if lod <= 1:                               # inside lanterns, upper corners of the ends
        for sy in (-1, 1):
            for sx in (-1, 1):
                if sx * sy < 0:
                    continue
                q = Vector((sx * (W * s_of(zt - 0.5) / 2 - 0.22), sy * (D * s_of(zt - 0.5) / 2 - 0.22), zt - 0.75))
                c = C.lantern_head(mb, tuple(q), dict(iron=M['frame'], paper=M['andon']), lod, size=0.12, height=0.24,
                                   roof='hip', frame_w=0.012, ball=False)
                K.beam(mb, q + Vector((0, 0, 0.3)), Vector((q.x, q.y, zt - 0.03)), 0.012, 0.012, M['frame'])
                lights.append(C.light_entry(c, color_k=2300, watts=6))
    # ---- lower end panels (opaque lacquer with a bronze fret), behind the glass on the ends + corners
    if lod <= 1:
        end_idx = []
        for i in range(N):
            x, y = _[i]
            if abs(y) > D / 2 - rc * 1.2:
                end_idx.append(i)
        for i in end_idx:
            j = (i + 1) % N
            if j not in end_idx:
                continue
            lo = ring(zf + 0.03, inset=0.03); hi = ring(zd - 0.03, inset=0.03)
            q = [bm.verts.new(v) for v in (lo[i], lo[j], hi[j], hi[i])]
            f = bm.faces.new(q); f.material_index = M['panel']
        if lod == 0:                           # fret: a key bar course on the +-Y faces
            for sy in (-1, 1):
                yy = sy * (D * s_of(zf + 0.3) / 2 - 0.045)
                for zz in (zf + 0.14, zf + 0.42):
                    K.beam(mb, (-W * 0.3, yy, zz), (W * 0.3, yy, zz), 0.02, 0.02, M['polish'])
                for k in range(7):
                    x = -W * 0.3 + W * 0.6 * k / 6
                    K.beam(mb, (x, yy, zf + 0.14), (x, yy, zf + 0.42 - (0.14 if k % 2 else 0)), 0.02, 0.02, M['polish'])
    # ---- polished bands (floor, dado, cornice) as loops proud of the glass
    if lod <= 2:
        bz = [zf, zd, zt] if lod <= 1 else [zf, zt]
        for z in bz:
            r0 = ring(z - 0.03, inset=-0.012); r1 = ring(z + 0.03, inset=-0.012)
            if lod == 0:
                ri0 = ring(z - 0.03, inset=0.012); ri1 = ring(z + 0.03, inset=0.012)
                loft([ri0, r0, r1, ri1], M['polish'], close_bottom=False)      # inner face sits on the glass
            else:
                loft([r0, r1], M['polish'])

    # ---- vertical frame members following the barrel: corners, end mullions, door jambs + centre seam
    def member(i, w=0.07, out=0.03, zz=None, mi=None):
        zz = zz or (zs if lod == 0 else [zs[0], (zs[0] + zs[-1]) / 2, zs[-1]] if lod == 1 else [zs[0], zs[-1]])
        pts = [ring(z, inset=-0.004)[i] for z in zz]
        nrm = Vector((pts[len(pts) // 2].x, pts[len(pts) // 2].y, 0)).normalized()
        if lod <= 2:
            C.sweep(mb, pts, [(-w / 2, -0.015), (w / 2, -0.015), (w / 2, out), (-w / 2, out)], mi or M['frame'], up=nrm)
    if lod <= 2:
        for c in ('c0', 'c1', 'c2', 'c3'):
            member(IDX[c])
        if lod <= 1:
            for e in ('e0', 'e2'):              # end mullions
                lst = IDX[e]
                pick = [lst[len(lst) // 2]] if P['bars'] == 1 else [lst[len(lst) // 3], lst[-1 - len(lst) // 3]]
                for i in pick:
                    member(i, w=0.05)
        for e in ('e1', 'e3'):                  # long sides: door jambs (outer thirds) + centre seam
            lst = IDX[e]
            if len(lst) >= 3:
                jam = [lst[0 + len(lst) // 5], lst[-1 - len(lst) // 5]] if len(lst) >= 5 else [lst[0], lst[-1]]
                for i in jam:
                    member(i, w=0.09, out=0.04)
                member(lst[len(lst) // 2], w=0.045, mi=M['frame'])
                if lod == 0:                    # door head rail + handles
                    a = ring(zt - 0.22, inset=-0.01)[jam[0]]; b = ring(zt - 0.22, inset=-0.01)[jam[1]]
                    K.beam(mb, a, b, 0.05, 0.05, M['frame'])
                    mid = ring(zf + 0.95, inset=-0.05)[lst[len(lst) // 2]]
                    t = (b - a).normalized()
                    for s in (-1, 1):
                        q = mid + t * s * 0.07
                        K.beam(mb, q - Vector((0, 0, 0.2)), q + Vector((0, 0, 0.2)), 0.025, 0.025, M['polish'])
            elif lod == 2:
                member(lst[0], w=0.06)
    # ---- roof ribs + mount
    zr = zl + Hb                               # roof top
    if lod == 0 and P['roof'] != 'flat':
        for c in ('c0', 'c1', 'c2', 'c3'):
            i = IDX[c]
            st = s_of(zt)
            pts = [ring(zt + dz, s=s)[i] for dz, s in rr[1:]]
            pts[-1] = pts[-1].lerp(Vector((0, 0, pts[-1].z)), 0.3)
            C.tube(mb, pts, [0.02] * len(pts), M['polish'], sides=6 if lod == 0 else 4, cap0=True, cap1=True)
    if P['roof'] == 'tall' and lod <= 2:
        C.lathe(mb, [(0.06, 0), (0.1, 0.05), (0.03, 0.12), (0, 0.16)], C.lod_pick(lod, 10, 8, 6), M['polish'],
                base=(0, 0, zr - 0.02))
    # ---- grip arm (gooseneck in XZ), roof mount, carriage with 4 sheaves on the twin cables
    bow = 0.36 * P['bow']
    zm = zr - (0.05 if P['roof'] != 'tall' else 0.1)
    zc = zr + 1.62                              # cable centre height
    zg = zc - 0.22                              # carriage beam
    arm = [Vector((0, 0, zm)), Vector((0, 0, zm + 0.3)), Vector((bow * 0.35, 0, zm + 0.62)),
           Vector((bow * 0.9, 0, zm + 0.9)), Vector((bow, 0, zm + 1.15)), Vector((bow * 0.7, 0, zm + 1.36)),
           Vector((bow * 0.15, 0, zg - 0.12)), Vector((0, 0, zg))]
    if lod >= 2:
        arm = [arm[0], arm[3], arm[5], arm[7]] if lod == 2 else [arm[0], arm[4], arm[7]]
    if lod <= 2:
        C.sweep(mb, arm, [(-0.07, -0.05), (0.07, -0.05), (0.07, 0.05), (-0.07, 0.05)], M['frame'], up=Vector((0, 1, 0)))
    else:
        for a, b in zip(arm[:-1], arm[1:]):
            K.beam(mb, a, b, 0.12, 0.12, M['frame'])
    if lod <= 1:                                # roof mount: plate + hub collar + clamp at the carriage
        K.box(mb, (0, 0, zm + 0.04), (0.5, 0.4, 0.1), M['frame'], bevel=C.lod_pick(lod, 0.015, 0.0))
        C.stick(mb, (0, 0, zm + 0.08), (0, 0, zm + 0.26), 0.11, 0.09, M['polish'], segs=C.lod_pick(lod, 12, 8))
        C.stick(mb, (-0.1, 0, zg - 0.04), (0.1, 0, zg - 0.04), 0.09, 0.09, M['polish'], segs=C.lod_pick(lod, 12, 8))
    # carriage: yoke across X, two side plates along Y (one per cable), sheaves on the cables
    sr = 0.12
    if lod <= 2:
        K.box(mb, (0, 0, zg), (GAUGE + 0.18, 0.22, 0.12), M['frame'])
        for sx in (-1, 1):
            x = sx * GAUGE / 2
            K.box(mb, (x + sx * 0.06, 0, zc + 0.02), (0.035, 0.95, 0.24), M['frame'], bevel=C.lod_pick(lod, 0.008, 0.0, 0.0))
            for sy in ((-1, 1) if lod <= 1 else (0,)):
                y = sy * 0.3
                K.wheel(mb, (x, y, zc + CABLE_R + sr - 0.02), (1, 0, 0), sr,
                        dict(rim=M['polish'], spoke=M['frame'], hub=M['polish']), lod, spokes=C.lod_pick(lod, 4, 0, 0),
                        rim_w=0.05, rim_t=0.06, hub_r=0.035, segs=C.lod_pick(lod, 14, 6, 6))
        if lod <= 1:                            # side-plate bolts
            for sx in (-1, 1):
                for sy in (-1, 1):
                    C.stick(mb, (sx * (GAUGE / 2 + 0.085), sy * 0.3, zc + CABLE_R + sr - 0.02),
                            (sx * (GAUGE / 2 + 0.11), sy * 0.3, zc + CABLE_R + sr - 0.02), 0.03, 0.03, M['polish'], segs=6)
    else:
        mb.box((0, 0, zc), (GAUGE + 0.2, 0.9, 0.3), M['frame'])
    # ---- lamp under the floor: bronze cap, paper globe, finial
    if lod <= 2:
        C.lathe(mb, [(0.0, zl - 0.07), (0.15, zl - 0.07), (0.1, zl + 0.02)], C.lod_pick(lod, 12, 8, 6), M['frame'])
        C.lathe(mb, [(0, 0.035), (0.07, 0.05), (0.1, 0.11), (0.085, zl - 0.07)], C.lod_pick(lod, 12, 8, 6), M['lamp'], closed=True)
        if lod <= 1:
            C.lathe(mb, [(0, 0.0), (0.03, 0.01), (0.025, 0.04), (0, 0.045)], 6, M['polish'])
    else:
        mb.cylinder((0, 0, (zl + 0.0) / 2), 0.1, zl, M['lamp'], segs=4)
    lights.append(C.light_entry((0, 0, 0.12), color_k=2200, watts=15))
    ceil_light = C.light_entry((0, 0, zt - 0.1), color_k=2400, watts=30, radius=1.6)
    lights.append(ceil_light)
    _, _, dz = C.centre_base(mb, centre_x=False, centre_y=False)
    zc += dz
    for L in lights:
        L['pos'][2] = round(L['pos'][2] + dz, 4)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=lights, kz_light=ceil_light,
                     kz_grip=dict(cables_x=[-GAUGE / 2, GAUGE / 2], z=round(zc, 3), cable_r=CABLE_R, axis='y'),
                     kz_anim=dict(type='rigid', travel=dict(path_from='cable_line kz_cables', attach='kz_grip',
                                                            axis='y', mode='shuttle'),
                                  swing=dict(pivot=[0, 0, round(zc, 3)], axis=[1, 0, 0], amp_deg=3.0, period_s=4.5,
                                             lateral=dict(axis=[0, 1, 0], amp_deg=1.2, period_s=6.0))),
                     kz_glow_slots=[M['lamp'], M['andon'], M['ceil'], M['core']],
                     kz_params={k: v for k, v in P.items()})
    return o
