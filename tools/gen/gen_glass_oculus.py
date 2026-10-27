"""Glass oculus lens in the paving (g_east, hero, 1 instance): a thick round glass lens set flush in the paving
over the slide / lava-stair shaft, in a bronze ring, fenced by a bronze ring rail with a gate gap.

Targets (measured / derived):
  * lookbook/img/31-plan-ground.jpg grid H4 ('Slide + Lava Stair below B1-B3, no ground access'): the dashed
    shaft circle is ~0.35 of a 20 m grid cell -> ~6-7 m across, which is the row's 7 x 7 m footprint
    (lens + bronze ring + stone collar + rail). Glow is orange (lava_glass), steam rises from vents in the ring.
  * Row: r 2-3.5 m (lens radius, default 2.5), glass thickness (default 0.12 m), ring w (default 0.28 m),
    rail gate w (default 1.1 m). Proxy 7 x 7 x 0.15 m.
  * Conflict: a 'ring rail' with a 'gate' is a standing guard rail; the proxy h 0.15 only holds the flush lens.
    Built: rail on by default at 0.9 m (bronze, 1.0-1.1 m is the usual guard height but the lookbook rails
    near water read ~0.9 m); `rail=False` gives the flush 0.15 m lens. Proposed proxy h 1.2 (PROXY_SHEET below,
    used only by the scratch sheet wrapper).

Parts (LOD0): thick glass lens (closed solid, chamfered top edge, very slight 6 mm crown), radial bronze
support spider under the glass (6-8 ribs + hub, visible through it), bronze ring (stepped section: inner lip
over the glass, raised bead, flat band with 24-32 dome bolts, chamfered outer edge), 8 steam vent grilles in
the ring (slots), two courses of radial basalt-paving flagstones (stone collar) out to r 3.5 m with 10 mm joints,
ring rail: bronze posts on round base plates, top rail tube, mid rail, two heavier gate posts with ball finials
either side of the gate gap.

Parameters:
  r        lens radius 2.0-3.5 m           (default 2.5; the collar shrinks so the footprint stays <= 7 m)
  glass_t  glass thickness 0.08-0.14 m     (default 0.12)
  ring_w   bronze ring width 0.2-0.4 m     (default 0.28)
  gate_w   rail gate gap 0.9-1.6 m         (default 1.1)
  rail     True / False                    (default True)
  rail_h   0.8-1.1 m                       (default 0.9; with the gate finials the asset is 1.21 m tall)
Seeds change (row variant count 1; seeds 2-3 are alternates): lens radius (2.5 / 2.2 / 2.8), support spider
(6 / 8 / 6 ribs), rail style ('two rails' / 'single top rail with balusters' / 'two rails'), post count,
gate direction, flagstone joint layout.

Materials: lava_glass (lens), lava (emissive 1.0: a glow card at the bottom of the lens recess standing in for
the lit slide shaft below, seen through the glass; the runtime may swap it for the real shaft view), bronze smooth (ring,
rail, spider, bolts), iron (vent grilles), paving (collar flagstones).
Animation (shader): obj['kz_anim'] = {'type': 'flicker', 'slot': <lava_glass slot>, 'source': 'slide shaft'}
and the glass faces carry the float attribute 'kz_flicker' (radial 1.0 at the centre -> 0.4 at the rim).
Lighting: emissive + lightmap; obj['kz_lights'] = one 1800 K point 0.6 m below the lens centre (replaces the
oculus_glow marker), obj['kz_fx'] = fx_steam at each vent. Pivot: base centre (top of the lens at z = 0.15).
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'glass_oculus'
FEATURES = ['thick round glass lens flush in the paving', 'bronze ring', 'ring rail with a gate',
            'orange glow from below']
PROXY_SHEET = dict(w=7.0, d=7.0, h=1.2)

RES = {
    0: dict(segs=48, rail_st=40, rail_sides=6, post_segs=6, bolts=16, spider=True, vents=8, stones=True,
            ring='full', posts='stick', balusters=True),
    1: dict(segs=24, rail_st=24, rail_sides=4, post_segs=4, bolts=0, spider=True, vents=8, stones=False,
            ring='simple', posts='stick', balusters=False),
    2: dict(segs=12, rail_st=12, rail_sides=3, post_segs=0, bolts=0, spider=False, vents=0, stones=False,
            ring='simple', posts='slab', balusters=False),
    3: dict(segs=8, rail_st=8, rail_sides=0, post_segs=0, bolts=0, spider=False, vents=0, stones=False,
            ring='top', posts='gate', balusters=False),
}


def params(seed, r=None, glass_t=None, ring_w=None, gate_w=None, rail=True, rail_h=None):
    g = C.rng(seed, 'layout')
    P = dict(R=float(r or C.cycle(seed, [2.5, 2.2, 2.8])), gt=float(glass_t or 0.12), rw=float(ring_w or 0.28),
             gate=float(gate_w or 1.1), rail=bool(rail), rail_h=float(rail_h or 0.9))
    P['ribs'] = C.cycle(seed, [6, 8, 6])
    P['style'] = C.cycle(seed, ['rails', 'balusters', 'rails'])
    P['gate_dir'] = C.cycle(seed, [math.pi / 2, -math.pi / 2, 0.0]) + g.uniform(-0.05, 0.05)
    P['joint_ph'] = g.uniform(0, 1)
    P['Rout'] = 3.5 - 0.02
    P['Rrail'] = min(P['R'] + P['rw'] + 0.32, P['Rout'] - 0.12)
    return P


def _annulus(mb, r0, r1, z0, z1, a0, a1, n, mi, bevel=0.0):
    """closed ring sector (flagstone) between radii r0..r1, angles a0..a1, z0..z1, n arc segments"""
    bm = mb.bm
    prof = [(r0, z0), (r1, z0), (r1, z1 - bevel), (r1 - bevel, z1), (r0 + bevel, z1), (r0, z1 - bevel)] if bevel else \
        [(r0, z0), (r1, z0), (r1, z1), (r0, z1)]
    cols = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        ca, sa = math.cos(a), math.sin(a)
        cols.append([bm.verts.new((rr * ca, rr * sa, zz)) for rr, zz in prof])
    fs = []
    m = len(prof)
    for A, B in zip(cols[:-1], cols[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            fs.append(bm.faces.new((A[k], B[k], B[k2], A[k2])))
    fs.append(bm.faces.new(cols[0]))
    fs.append(bm.faces.new(cols[-1][::-1]))
    mb._tag(fs, mi)
    return fs


def build(lod, seed, r=None, glass_t=None, ring_w=None, gate_w=None, rail=True, rail_h=None, **_):
    P = params(seed, r, glass_t, ring_w, gate_w, rail, rail_h)
    R_ = RES[lod]
    R, gt, rw = P['R'], P['gt'], P['rw']
    H = 0.15                                   # paving top
    mb = genlib.MeshBuilder()
    glass = mb.slot('lava_glass')
    glow = mb.slot('lava', emissive_level=1.0)
    bronze = mb.slot('bronze', variant='smooth')
    iron = mb.slot('iron')
    pave = mb.slot('paving')
    segs = R_['segs']
    bm = mb.bm

    # ---------------------------------------------------------------- glass lens (closed solid)
    ch = 0.012 if lod <= 1 else 0.0
    crown = 0.006 if lod == 0 else 0.0
    prof = [(R - 0.01, H - gt), (R, H - gt + 0.01), (R, H - ch - 0.004), (R - ch, H - 0.004)]
    if lod == 0:
        prof += [(R * 0.5, H - 0.004 + crown * 0.7), (0.0, H - 0.004 + crown)]
    else:
        prof += [(0.0, H - 0.004)]
    prof = [(0.0, H - gt)] + prof
    if lod == 3:
        prof = [(R, H - 0.004), (0.0, H - 0.004)]
    vs, gfaces = C.lathe(mb, prof, segs, glass, closed=lod < 3)
    # ---------------------------------------------------------------- glow card: the lit shaft seen through the glass
    if lod <= 2:
        C.lathe(mb, [(R - 0.02, 0.002), (0.0, 0.002)], max(8, segs // 2), glow, closed=False)
    # ---------------------------------------------------------------- support spider under the glass
    if R_['spider']:
        hb = max(0.012, H - gt - 0.002)          # ribs fill the space under the glass, z 0 .. glass bottom
        for k in range(P['ribs']):
            a = 2 * math.pi * (k + 0.5) / P['ribs']
            mb.box((math.cos(a) * R / 2, math.sin(a) * R / 2, hb / 2), (R - 0.1, 0.05, hb), bronze, rot=(0, 0, a))
        C.lathe(mb, [(0.0, 0.0), (0.22, 0.0), (0.22, hb), (0.0, hb)], 16 if lod == 0 else 8, bronze)
    # ---------------------------------------------------------------- bronze ring
    if R_['ring'] == 'full':
        rprof = [(R - 0.03, H - gt - 0.02), (R + rw, H - gt - 0.02), (R + rw, H - 0.012), (R + rw - 0.012, H),
                 (R + rw * 0.5, H + 0.008), (R + rw * 0.4, H + 0.008), (R + 0.02, H), (R - 0.03, H - 0.004)]
    elif R_['ring'] == 'simple':
        rprof = [(R - 0.03, H - gt - 0.02), (R + rw, H - gt - 0.02), (R + rw, H), (R - 0.03, H)]
    else:
        rprof = [(R + rw, 0.0), (R + rw, H + 0.002), (R - 0.03, H + 0.002)]
    rings = []
    for rr, zz in rprof:
        rings.append([bm.verts.new((rr * math.cos(2 * math.pi * k / segs), rr * math.sin(2 * math.pi * k / segs), zz))
                      for k in range(segs)])
    rf = []
    pairs = zip(rings, rings[1:] + rings[:1]) if R_['ring'] != 'top' else zip(rings[:-1], rings[1:])
    for A, B in pairs:
        rf += C.bridge_rings(bm, A, B)
    mb._tag(rf, bronze)
    if R_['bolts']:
        nbt = R_['bolts']
        for k in range(nbt):
            a = 2 * math.pi * (k + 0.5) / nbt
            rr = R + rw * 0.76
            mb.cylinder((rr * math.cos(a), rr * math.sin(a), H + 0.004), 0.02, 0.012, bronze, segs=6, radius2=0.012)
    if R_['vents']:
        for k in range(R_['vents']):
            a = 2 * math.pi * k / R_['vents'] + math.pi / R_['vents']
            rr = R + rw * 0.22
            mb.box((rr * math.cos(a), rr * math.sin(a), H + 0.001), (0.06, 0.12, 0.004), iron, rot=(0, 0, a))
    # ---------------------------------------------------------------- stone collar
    r0, r1, r2 = R + rw + 0.01, None, P['Rout']
    r1 = r0 + (r2 - r0) * 0.5
    if R_['stones']:
        jt = 0.01
        for (ra, rb, pitch, ph) in ((r0, r1 - jt / 2, 1.0, P['joint_ph']), (r1 + jt / 2, r2, 1.25, P['joint_ph'] + 0.5)):
            n = max(8, int(2 * math.pi * rb / pitch))
            for k in range(n):
                a0 = 2 * math.pi * (k + ph) / n + jt / rb / 2
                a1 = 2 * math.pi * (k + 1 + ph) / n - jt / rb / 2
                _annulus(mb, ra, rb, 0.0, H, a0, a1, 2, pave)
    elif lod <= 2:
        nn = max(8, segs)
        A = [bm.verts.new((r0 * math.cos(2 * math.pi * k / nn), r0 * math.sin(2 * math.pi * k / nn), H)) for k in range(nn)]
        B = [bm.verts.new((r2 * math.cos(2 * math.pi * k / nn), r2 * math.sin(2 * math.pi * k / nn), H)) for k in range(nn)]
        Bb = [bm.verts.new((v.co.x, v.co.y, 0.0)) for v in B]
        fs = C.bridge_rings(bm, B, A) + C.bridge_rings(bm, Bb, B)
        mb._tag(fs, pave)

    # ---------------------------------------------------------------- ring rail with a gate gap
    lights = [C.light_entry((0, 0, -0.6), color_k=1800, watts=60)]
    fx = []
    if P['rail']:
        Rr, rh = P['Rrail'], P['rail_h']
        half_gap = (P['gate'] / 2) / Rr
        g0 = P['gate_dir'] + half_gap
        span = 2 * math.pi - 2 * half_gap
        npost = max(6, int(span * Rr / 1.25))
        posts = [g0 + span * k / npost for k in range(npost + 1)]
        ps = R_['post_segs']
        for k, a in enumerate(posts):
            x, y = Rr * math.cos(a), Rr * math.sin(a)
            gate = k in (0, npost)
            rad = 0.04 if gate else 0.026
            pst = R_['posts']
            if pst == 'stick':
                C.stick(mb, (x, y, H), (x, y, H + rh + (0.06 if gate else 0.0)), rad, rad * 0.9, bronze, segs=ps)
                if lod == 0:
                    mb.cylinder((x, y, H + 0.012), rad + 0.035, 0.024, bronze, segs=ps, radius2=rad + 0.01)
                if gate:
                    C.lathe(mb, [(0.0, 0.0), (0.045, 0.02), (0.05, 0.05), (0.03, 0.085), (0.0, 0.1)], ps, bronze,
                            base=(x, y, H + rh + 0.06))
            elif pst == 'slab' or gate:
                # open-ended square tube, no caps (8 tris)
                hz = rh + (0.06 if gate else 0.0)
                qs = [bm.verts.new((x + dx, y + dy, zz)) for zz in (H, H + hz) for dx, dy in
                      ((-rad, -rad), (rad, -rad), (rad, rad), (-rad, rad))]
                fs = C.bridge_rings(bm, qs[:4], qs[4:])
                mb._tag(fs, bronze)
        nst = max(4, int(R_['rail_st'] * span / (2 * math.pi)))
        heights = [(H + rh, 0.026)] + ([(H + rh * 0.45, 0.016)] if P['style'] == 'rails' and lod <= 1 else []) + \
                  ([(H + 0.12, 0.014)] if P['style'] == 'balusters' and lod <= 1 else [])
        for (zz, rad) in heights:
            pts = [Vector((Rr * math.cos(g0 + span * i / nst), Rr * math.sin(g0 + span * i / nst), zz)) for i in range(nst + 1)]
            if R_['rail_sides'] >= 3:
                C.tube(mb, pts, [rad] * len(pts), bronze, sides=R_['rail_sides'], cap0=lod <= 1, cap1=lod <= 1)
            else:
                rows = [[bm.verts.new((p.x, p.y, p.z - 0.05)), bm.verts.new((p.x, p.y, p.z + 0.02))] for p in pts]
                fs = []
                for A, B in zip(rows[:-1], rows[1:]):
                    fs.append(bm.faces.new((A[0], B[0], B[1], A[1])))
                mb._tag(fs, bronze)
        if P['style'] == 'balusters' and R_['balusters']:
            for k in range(npost):
                for j in (1, 2):
                    a = posts[k] + (posts[k + 1] - posts[k]) * j / 3
                    x, y = Rr * math.cos(a), Rr * math.sin(a)
                    C.stick(mb, (x, y, H + 0.12), (x, y, H + rh), 0.01, 0.01, bronze, segs=3)
    for k in range(RES[0]['vents']):
        a = 2 * math.pi * k / RES[0]['vents'] + math.pi / RES[0]['vents']
        rr = R + rw * 0.22
        fx.append(dict(kind='fx_steam', pos=[round(rr * math.cos(a), 3), round(rr * math.sin(a), 3), H], rate=0.3))

    C.centre_base(mb, centre_x=False, centre_y=False)
    o = mb.to_object(ASSET)
    # flicker attribute on the glass (radial falloff) and the shader animation descriptor
    att = o.data.attributes.new('kz_flicker', 'FLOAT', 'POINT')
    for v in o.data.vertices:
        d = math.hypot(v.co.x, v.co.y)
        att.data[v.index].value = max(0.4, 1.0 - 0.6 * d / R) if d <= R + 0.001 and v.co.z <= H + 0.01 else 0.0
    C.set_json_props(o, kz_lights=lights, kz_fx=fx,
                     kz_anim=dict(type='flicker', slot=glass, attribute='kz_flicker', source='slide shaft below',
                                  rate_hz=[0.3, 1.2]),
                     kz_params=dict(r=R, glass_t=gt, ring_w=rw, gate_w=P['gate'], rail=P['rail'], rail_h=P['rail_h']))
    return genlib.finish(o)
