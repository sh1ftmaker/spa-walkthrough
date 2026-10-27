"""Magma viewing glass wall (B4 magma chamber): long curved thick glass in 7.5 m bronze-framed bays with dark
bronze mullions standing proud.

Targets (asset row; plan 36 for the run and the curve, sheet-ref-deep #03 and lookbook 23 for the elevation; scale
from the seated bathers ~1.25 m and the 0.45 m benches):
  * glass run 82 m along the plan curve, 11 bays of ~7.45 m (bay 7.5 m), h 7.0 m overall (proxy; the row's 7.6 m is
    the B4 room height: pass h=7.6 if the place model wants it). Plan 36 measures the glass bowing ~2-3 m towards
    the lava over the run (the 82 m chord is ~1.4 grid squares; the curve's sag is ~0.15 of a square).
  * mullions 0.35 m wide, standing 0.30 m proud of the glass on the room side (+Y) and 0.12 m on the lava side;
    near-black bronze tee section with a face cap, base shoe and a bracket capital (sheet-ref-deep #03).
  * thick glass 0.10 m (lava_glass), from the sill at 0.45 m to the head; one high transom at 0.80-0.86 of the
    glass height (sheet #03 shows the bar near the top) or none (seeded).
  * heavy bronze sill (0.45 m) with a nosing and a toe plinth; deep head beam 0.55 m with a stepped cornice.
  * lean rail at `rail_offset` (default 1.3 m) on the room side: bronze top rail 1.05 m high on posts at every
    mullion and mid-bay, one mid rail. rail_offset=0 drops it (the railing generator can supply it instead).
Faceted plan: each bay is a flat pane on the chord (sagitta inside one bay < 25 mm at the default curve).

Parameters: length 20-82 (default 82), curve = plan sag in metres (default seeded 1.8-2.8; 0 = straight),
curve_kind 'arc' | 's' (S-bend: the reverse end of plan 36) , bay 7.5, h (7.0), mullion 0.35, rail_offset 1.3,
glass_t 0.10, transom (seeded True/False). Seeds change: curve kind and sag, transom presence and height,
mullion face (grooved cap / twin fins), head cornice steps (1 or 2), rail mid-posts.
Animation: shader heat shimmer on the glass: point attribute 'kz_shimmer' (1.0 at the sill falling to 0.35 at the
head, 0 off the glass) + colour attribute 'kz_shimmer_col', described in obj['kz_anim'].
Lighting: emissive + lightmap; obj['kz_lights'] = one 1500 K area light per bay behind the glass (lava side).
Lava behind is the lava_backdrop asset. Orientation: room side +Y, lava side -Y; the curve bows towards -Y.
Budget: the row is per bay (3000/1200/360/60); the whole 11-bay wall is built as one object.
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'magma_glass_wall'
FEATURES = ['long curved thick glass', '7.5 m bronze-framed bays', 'dark bronze mullions standing proud',
            'heavy sill and head beam']
STYLES = ['arc', 's', 'arc_transomless']


def kelvin_rgb(k):
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c)
    return [round(x / m, 3) for x in c]


def zprism(mb, poly, M, z0, z1, mi):
    """extrude a plan polygon [(s, n)] (s along the wall, n normal to it, +n = room side) placed by frame
    function M(s, n) -> (x, y), between z0 and z1"""
    bm = mb.bm
    pts = [M(s, n) for s, n in poly]
    a = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if a < 0:
        pts = pts[::-1]
    A = [bm.verts.new((x, y, z0)) for x, y in pts]
    B = [bm.verts.new((x, y, z1)) for x, y in pts]
    fs = [bm.faces.new(A[::-1]), bm.faces.new(B)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    mb._tag(fs, mi)
    return fs


def band(mb, P, Nrm, prof, mi, closed=True):
    """sweep a section [(n, z)] along plan points P (with plan normals Nrm) -> closed beam along the wall"""
    bm = mb.bm
    rings = [[bm.verts.new((p.x + nm.x * n, p.y + nm.y * n, z)) for n, z in prof] for p, nm in zip(P, Nrm)]
    fs = []
    m = len(prof)
    for A, B in zip(rings[:-1], rings[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            fs.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    if closed:
        fs.append(bm.faces.new(rings[0][::-1])); fs.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def build(lod, seed, w=None, d=None, h=None, length=82.0, curve=None, curve_kind=None, bay=7.5, mullion=0.35,
          rail_offset=1.3, glass_t=0.10, transom=None, style=None):
    p = genlib.proxy(ASSET)
    H = h or p['h']
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    sag = curve if curve is not None else g.uniform(1.8, 2.8)
    kind = curve_kind or ('s' if style == 's' else 'arc')
    has_tr = transom if transom is not None else (style != 'arc_transomless')
    tr_f = g.uniform(0.80, 0.86)
    face = g.choice(['groove', 'fins'])
    cornice = g.choice([1, 2])
    Lw = min(length, (w or 1e9))

    # ---------------------------------------------------------------- plan curve: arc-length parametrised
    def raw(u):                              # u in [0, 1]
        x = (u - 0.5) * Lw
        if kind == 's':
            y = -sag * math.sin(math.pi * u) * (1.0 - 0.9 * u) * 1.25 + sag * 0.55 * max(0.0, (u - 0.72) / 0.28) ** 2
        else:
            y = -sag * (1 - (2 * u - 1) ** 2)
        return Vector((x, y, 0))
    NS = 400
    pts = [raw(i / NS) for i in range(NS + 1)]
    cum = [0.0]
    for a_, b_ in zip(pts[:-1], pts[1:]):
        cum.append(cum[-1] + (b_ - a_).length)
    scale = Lw / cum[-1]

    def at(s):                               # plan point at arc length s (0..Lw) after rescale
        s = max(0.0, min(Lw, s)) / scale
        i = 1
        while i < NS and cum[i] < s:
            i += 1
        f = (s - cum[i - 1]) / max(1e-9, cum[i] - cum[i - 1])
        q = pts[i - 1].lerp(pts[i], f)
        return Vector((q.x * scale, q.y * scale, 0))

    nb = max(1, int(round(Lw / bay)))
    bw = Lw / nb
    S = [bw * i for i in range(nb + 1)]          # mullion stations (arc length)
    MP = [at(s) for s in S]

    def nrm_at(i):                                # plan normal (room side, +Y-ish) at mullion i
        a_ = MP[max(0, i - 1)]; b_ = MP[min(nb, i + 1)]
        t = (b_ - a_).normalized()
        return Vector((-t.y, t.x, 0))

    MN = [nrm_at(i) for i in range(nb + 1)]
    MT = [Vector((n.y, -n.x, 0)) for n in MN]

    mb = genlib.MeshBuilder()
    m_glass = mb.slot('lava_glass', emissive_level=1.0)
    m_br = mb.slot('bronze', variant='smooth', tint=(0.26, 0.22, 0.19), wear=0.05)
    m_br2 = mb.slot('bronze', variant='smooth', tint=(0.50, 0.42, 0.33), wear=0.05)
    bm = mb.bm
    bev = 0.012 if lod == 0 else 0.0

    sill_h = 0.45
    head_h = 0.55
    zg0, zg1 = sill_h, H - head_h
    gh = zg1 - zg0
    ztr = zg0 + gh * tr_f
    mw = mullion
    fwd, back = 0.30, 0.12                         # mullion projection room side / lava side

    # ---------------------------------------------------------------- glass panes (flat on the chord)
    for i in range(nb):
        A_, B_ = MP[i], MP[i + 1]
        t = (B_ - A_).normalized(); n = Vector((-t.y, t.x, 0))
        inset = mw * 0.35
        a0 = A_ + t * inset; b0 = B_ - t * inset
        zs = [(zg0, ztr - 0.06), (ztr + 0.06, zg1)] if has_tr and lod <= 2 else [(zg0, zg1)]
        for z0, z1 in zs:
            ctr = (a0 + b0) / 2
            ln = (b0 - a0).length
            yaw = math.atan2(t.y, t.x)
            if lod == 0:
                C.board(mb, (ctr.x, ctr.y, (z0 + z1) / 2), (ln, glass_t, z1 - z0), m_glass, bevel=0.02, segs=1,
                        rot=(0, 0, yaw))
            elif lod <= 2:
                mb.box((ctr.x, ctr.y, (z0 + z1) / 2), (ln, glass_t, z1 - z0), m_glass, rot=(0, 0, yaw))
            else:   # LOD3: a single quad per bay facing the room
                v = [bm.verts.new((q.x, q.y, z)) for q, z in ((a0, z0), (b0, z0), (b0, z1), (a0, z1))]
                f = bm.faces.new(v); f.normal_update()
                if f.normal.dot(n) < 0:
                    f.normal_flip()
                mb._tag([f], m_glass)
        if has_tr and lod <= 2:      # transom bar
            ctr = (A_ + B_) / 2; ln = (B_ - A_).length
            mb.box((ctr.x + n.x * 0.05, ctr.y + n.y * 0.05, ztr), (ln, glass_t + 0.18, 0.14), m_br,
                   rot=(0, 0, math.atan2(t.y, t.x)), bevel=bev)

    # ---------------------------------------------------------------- sill and head (swept along the mullion points)
    stp = 1 if lod <= 1 else (2 if lod == 2 else max(1, nb))
    idx = list(range(0, nb + 1, stp))
    if idx[-1] != nb:
        idx.append(nb)
    P = [MP[i] for i in idx]; Nn = [MN[i] for i in idx]
    if lod <= 1:
        band(mb, P, Nn, [(-0.25, 0.0), (0.30, 0.0), (0.30, 0.10), (0.26, 0.14), (0.26, sill_h - 0.06),
                         (0.34, sill_h - 0.04), (0.34, sill_h), (-0.25, sill_h)], m_br)        # sill + nosing + toe
        prof_h = [(-0.25, H - head_h), (0.32, H - head_h), (0.32, H - 0.18)]
        if cornice == 2:
            prof_h += [(0.40, H - 0.18), (0.40, H - 0.08), (0.46, H - 0.08), (0.46, H), (-0.25, H)]
        else:
            prof_h += [(0.44, H - 0.18), (0.44, H), (-0.25, H)]
        band(mb, P, Nn, prof_h, m_br)
    else:
        band(mb, P, Nn, [(-0.25, 0.0), (0.32, 0.0), (0.32, sill_h), (-0.25, sill_h)], m_br)
        band(mb, P, Nn, [(-0.25, H - head_h), (0.40, H - head_h), (0.40, H), (-0.25, H)], m_br)

    # ---------------------------------------------------------------- mullions
    for i in range(nb + 1):
        c, n, t = MP[i], MN[i], MT[i]
        M = lambda s, nn, c=c, n=n, t=t: (c.x + t.x * s + n.x * nn, c.y + t.y * s + n.y * nn)
        if lod <= 1:
            web = [(-0.07, -back), (0.07, -back), (0.07, fwd - 0.08), (-0.07, fwd - 0.08)]
            capp = [(-mw / 2, fwd - 0.08), (mw / 2, fwd - 0.08), (mw / 2, fwd - 0.015), (mw / 2 - 0.015, fwd),
                    (-mw / 2 + 0.015, fwd), (-mw / 2, fwd - 0.015)] if lod == 0 else \
                   [(-mw / 2, fwd - 0.08), (mw / 2, fwd - 0.08), (mw / 2, fwd), (-mw / 2, fwd)]
            zprism(mb, web, M, sill_h, H - head_h, m_br)
            zprism(mb, capp, M, sill_h, H - head_h, m_br)
            if lod == 0:
                if face == 'groove':       # shadow groove = two slim polished strips either side of a gap
                    for sx in (-1, 1):
                        zprism(mb, [(sx * 0.05, fwd), (sx * 0.12, fwd), (sx * 0.12, fwd + 0.012), (sx * 0.05, fwd + 0.012)],
                               M, sill_h + 0.5, H - head_h - 0.5, m_br2)
                else:                      # twin fins standing off the face
                    for sx in (-1, 1):
                        zprism(mb, [(sx * 0.10 - 0.015, fwd), (sx * 0.10 + 0.015, fwd), (sx * 0.10 + 0.015, fwd + 0.07),
                                    (sx * 0.10 - 0.015, fwd + 0.07)], M, sill_h + 0.3, H - head_h - 0.3, m_br)
                # lava-side glazing stop
                zprism(mb, [(-mw * 0.45, -back - 0.04), (mw * 0.45, -back - 0.04), (mw * 0.45, -back), (-mw * 0.45, -back)],
                       M, sill_h, H - head_h, m_br)
                # bolted splice plates at the transom height and mid-height, 4 bolts each
                for zb in ([ztr] if has_tr else []) + [zg0 + gh * 0.38]:
                    zprism(mb, [(-mw / 2 - 0.03, fwd), (mw / 2 + 0.03, fwd), (mw / 2 + 0.03, fwd + 0.025), (-mw / 2 - 0.03, fwd + 0.025)],
                           M, zb - 0.22, zb + 0.22, m_br)
                    for bx in (-0.12, 0.12):
                        for bz in (-0.14, 0.14):
                            x, y = M(bx, fwd + 0.025)
                            mb.cylinder((x, y, zb + bz), 0.022, 0.03, m_br2, segs=6,
                                        rot=(math.pi / 2, 0, math.atan2(n.y, n.x) - math.pi / 2))
            # base shoe + bracket capital
            zprism(mb, [(-mw / 2 - 0.05, -back - 0.05), (mw / 2 + 0.05, -back - 0.05), (mw / 2 + 0.05, fwd + 0.08),
                        (-mw / 2 - 0.05, fwd + 0.08)], M, sill_h, sill_h + 0.32, m_br)
            zprism(mb, [(-mw / 2 - 0.04, -back - 0.04), (mw / 2 + 0.04, -back - 0.04), (mw / 2 + 0.04, fwd + 0.10),
                        (-mw / 2 - 0.04, fwd + 0.10)], M, H - head_h - 0.30, H - head_h, m_br)
            if lod == 0:   # tapered bracket under the capital
                zprism(mb, [(-mw / 2, fwd), (mw / 2, fwd), (mw / 2, fwd + 0.10), (-mw / 2, fwd + 0.10)],
                       M, H - head_h - 0.55, H - head_h - 0.30, m_br)
        else:
            zprism(mb, [(-mw / 2, -back), (mw / 2, -back), (mw / 2, fwd), (-mw / 2, fwd)], M,
                   sill_h if lod == 2 else 0.0, H - head_h if lod == 2 else H, m_br)

    # ---------------------------------------------------------------- lean rail on the room side
    if rail_offset and lod <= 2:
        ro = rail_offset
        rz = 1.05
        ns = C.lod_pick(lod, 8, 6, 4)
        # rail path: offset of the plan points, sampled 4 per bay (LOD0-1), 1 per bay (LOD2)
        k = C.lod_pick(lod, 4, 2, 1)
        RS = [bw * j / k for j in range(nb * k + 1)]
        RP = []
        for s in RS:
            q = at(s); e = 0.02
            t = (at(min(Lw, s + e)) - at(max(0, s - e))).normalized()
            n = Vector((-t.y, t.x, 0))
            RP.append(q + n * ro)
        C.tube(mb, [Vector((q.x, q.y, rz)) for q in RP], [0.03] * len(RP), m_br2, sides=ns, cap0=True, cap1=True)
        if lod <= 1:
            C.tube(mb, [Vector((q.x, q.y, 0.55)) for q in RP], [0.016] * len(RP), m_br, sides=max(4, ns - 2),
                   cap0=True, cap1=True)
        post_every = 2 if lod <= 1 else k
        for j, q in enumerate(RP):
            if j % post_every:
                continue
            C.stick(mb, (q.x, q.y, 0.0), (q.x, q.y, rz - 0.02), 0.03, 0.026, m_br, segs=ns)
            if lod == 0:
                mb.cylinder((q.x, q.y, 0.015), 0.07, 0.03, m_br, segs=8)

    dx, dy, dz = C.centre_base(mb)
    bm.verts.index_update()
    o = mb.to_object(ASSET)
    me = o.data
    attr = me.attributes.new('kz_shimmer', 'FLOAT', 'POINT')
    col = me.color_attributes.new('kz_shimmer_col', 'FLOAT_COLOR', 'POINT')
    gv = set()
    for poly in me.polygons:
        if poly.material_index == m_glass:
            gv.update(poly.vertices)
    for v in me.vertices:
        s = 0.0
        if v.index in gv:
            s = round(1.0 - 0.65 * max(0.0, min(1.0, (v.co.z - zg0) / gh)), 3)
        attr.data[v.index].value = s
        col.data[v.index].color = (s, 0, 0, 1)
    lights = []
    for i in range(nb):
        c = (MP[i] + MP[i + 1]) / 2; n = (MN[i] + MN[i + 1]).normalized()
        lights.append({'type': 'area', 'kind': 'area', 'pos': [round(c.x - n.x * 0.6 + dx, 3), round(c.y - n.y * 0.6 + dy, 3),
                                                              round((zg0 + zg1) / 2, 3)],
                       'size': [round(bw - mw, 3), round(gh, 3)], 'normal': [round(n.x, 3), round(n.y, 3), 0],
                       'color': kelvin_rgb(1500), 'color_k': 1500, 'watts': round(6000 / nb, 1),
                       'note': 'lava behind the glass'})
    C.set_json_props(o,
                     kz_anim={'type': 'shader', 'what': 'heat shimmer on the glass', 'attr': 'kz_shimmer',
                              'color_attr': 'kz_shimmer_col', 'material_slot': m_glass, 'material': 'lava_glass'},
                     kz_lights=lights,
                     kz_wall_path=[[round(q.x + dx, 3), round(q.y + dy, 3)] for q in MP],
                     kz_params=dict(style=style, length=round(Lw, 2), curve=round(sag, 3), curve_kind=kind, bays=nb,
                                    bay=round(bw, 3), h=H, mullion=mw, rail_offset=rail_offset, glass_t=glass_t,
                                    transom=bool(has_tr), transom_f=round(tr_f, 3), face=face, cornice=cornice))
    genlib.finish(o, smooth_angle=30)
    return o
