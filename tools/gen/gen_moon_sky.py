"""Moon and night sky backdrop (moon_sky): a 60 x 40 m emissive sky card with a large bright moon, stars, a
Milky Way band and a lit cloud band over the horizon. Used at the B3 sea mouth (wave grotto), the summit
moon deck and the summit pool; the card stands far out, facing the guests (+Y).

Targets (lookbook 11 caldera crown, 20 wave grotto, 32 suites cliff; no scale sheet):
  * card 60 x 1 x 40 m (proxy): a shallow cylindrical section, centre at y = 0, edges bowed back 0.4 m.
  * moon: 11 shows a disc ~7 % of the frame width, upper right, with a soft halo, pale warm-white with grey
    maria -> radius 2.5-4.5 m on the card, centre 60-80 % up, 15-35 % in from one side (seeded side).
  * horizon at ~25-30 % of the card height (11: 270 / 900 px); a sea of lit cloud below and around it
    (3 layered banks, bumpy tops 1.5-5 m), the moon well clear above.
  * stars: dense small points over a deep navy sky, a diagonal Milky Way band (11) with more and brighter
    stars and a faint glow strip; sky lighter toward the horizon.

Construction (one mesh, all emissive; faces +Y):
  * sky     - (x, z) grid on the curved card; three slots by height: `sky_low` (horizon glow), `sky`,
              `sky_top` (zenith).
  * milky   - a faint glow strip (quad strip with a wavy edge) on the card, y + 0.02.
  * moon    - 40-segment disc at y + 0.3 (`moon`), 5-7 irregular maria blobs at y + 0.31 (`maria`), two
              halo rings 1.0-1.35 R and 1.35-2.0 R (`halo1`, `halo2`) at y + 0.25.
  * stars   - small diamonds (2 tris, 0.06-0.2 m) at y + 0.05, denser in the Milky Way band (`star`);
              plus loose vertices (0 tris) carrying runtime-sprite stars (kz_star = 1).
  * clouds  - 3 bank strips with seeded bumpy tops, the front ones lower and darker, y + 0.3 ... 0.46
              (`cloud_far`, `cloud_mid`, `cloud_near`); each vertex carries kz_drift.
Materials: no `sky` material in the library yet (row: NEW:sky). All slots use neon_tube (the only library
emitter whose tint sets an even emission colour) with these tints / levels (swatched under AgX):
  sky_top (0.003, 0.007, 0.024) 1.0  sky (0.004, 0.009, 0.03) 1.0 (#010b1a)  sky_low (0.007, 0.013, 0.034) 1.0
  moon (1.0, 0.95, 0.82) 3.0  maria (0.6, 0.57, 0.5) 2.2  halo1 (0.03, 0.035, 0.05) 1.0  halo2 (0.012, 0.017, 0.035) 1.0
  star (0.85, 0.92, 1.0) 1.8  milky (0.008, 0.012, 0.03) 1.0
  cloud_far (0.07, 0.075, 0.09) 1.0  cloud_mid (0.045, 0.05, 0.065) 1.0  cloud_near (0.028, 0.03, 0.042) 1.0
  The proposed library entry `sky` with these as variants is in the report.

Parameters (build kwargs):
  w, h        card 20-60 x 15-40 m (default 60 x 40)
  moon_r      moon radius 2-5 m (default seeded 2.8-4.2)
  moon_pos    (u, v) as fractions of the card (default seeded: u 0.15-0.35 from a seeded side, v 0.6-0.8)
  stars       star density factor 0.3-2 (default 1)
  clouds      cloud banks 0-3 (default 3)
  horizon     horizon height as a fraction of h (default seeded 0.24-0.3)
Seeds change shape: moon side / position / size, maria layout, Milky Way angle and path, cloud bank
profiles and heights, star layout. Row variants: 1 (seeds are the same sky composed differently).

LODs (row budget: dome 2000): LOD0 sky 24 x 12, moon 40 segs, 6 maria, 2 halo rings, ~420 star diamonds +
4000 sprite stars, clouds 48 segs x 3; LOD1 12 x 6, 24 segs, same maria (12-gon), 180 diamonds + 2000
sprites, 24 segs; LOD2 6 x 3, 12 segs, 3 maria, 1 halo, 60 diamonds + 600 sprites, 2 banks x 10 segs;
LOD3 2 x 2, 8 segs, 1 halo, 16 diamonds, 1 bank x 4 segs. The moon, stars and a cloud band stay at
every LOD.
Animation (shader): stars twinkle (kz_phase, kz_bright on star verts; kz_star 1 diamonds / sprites),
clouds drift sideways (kz_drift = speed factor 0.3-1, larger on the near bank). obj['kz_anim'] names them.
Lights: kz_lights one moonlight entry (directional, 4100 K, from the moon position) for the bake.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'moon_sky'
FEATURES = ['large bright moon with halo', 'stars', 'cloud band over the horizon', 'deep navy sky']
RES = {
    0: dict(grid=(24, 12), moon=40, maria=6, maria_n=10, halo=2, stars=420, sprites=4000, banks=3, cseg=48, milky=16),
    1: dict(grid=(12, 6), moon=24, maria=6, maria_n=6, halo=2, stars=180, sprites=2000, banks=3, cseg=24, milky=8),
    2: dict(grid=(6, 3), moon=12, maria=3, maria_n=5, halo=1, stars=60, sprites=600, banks=2, cseg=10, milky=4),
    3: dict(grid=(2, 2), moon=8, maria=0, maria_n=0, halo=1, stars=16, sprites=0, banks=1, cseg=4, milky=0),
}
SLOTS = dict(sky_top=((0.003, 0.007, 0.024), 1.0), sky=((0.004, 0.009, 0.03), 1.0), sky_low=((0.007, 0.013, 0.034), 1.0),
             moon=((1.0, 0.95, 0.82), 3.0), maria=((0.6, 0.57, 0.5), 2.2), halo1=((0.03, 0.035, 0.05), 1.0),
             halo2=((0.012, 0.017, 0.035), 1.0), star=((0.85, 0.92, 1.0), 1.8), milky=((0.008, 0.012, 0.03), 1.0),
             cloud_far=((0.07, 0.075, 0.09), 1.0), cloud_mid=((0.045, 0.05, 0.065), 1.0), cloud_near=((0.028, 0.03, 0.042), 1.0))


def kelvin_rgb(k):
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c)
    return [round(x / m, 3) for x in c]


def layout(seed, W, H, moon_r, moon_pos, stars, clouds, horizon):
    g = C.rng(seed, 'moon')
    side = g.choice([-1, 1])
    R = moon_r if moon_r is not None else g.uniform(2.8, 4.2) * min(1.0, W / 60)
    if moon_pos:
        mu, mv = moon_pos
    else:
        mu, mv = 0.5 + side * (0.5 - g.uniform(0.15, 0.35)), g.uniform(0.6, 0.8)
    M = dict(x=-W / 2 + W * mu, z=H * mv, R=R)
    M['maria'] = [(g.uniform(0, 2 * math.pi), g.uniform(0.15, 0.62), g.uniform(0.16, 0.3), [g.uniform(-1, 1) for _ in range(4)])
                  for _ in range(7)]
    hz = H * (horizon if horizon is not None else C.rng(seed, 'horizon').uniform(0.24, 0.3))
    gm = C.rng(seed, 'milky')
    ang = math.radians(gm.uniform(50, 75)) * (-side)
    mx0 = gm.uniform(-0.15, 0.15) * W
    wav = (gm.uniform(1.5, 3.5), gm.uniform(0, 6.3))
    def milky_x(z):
        return mx0 + (z - hz) / math.tan(ang) * 0.6 + wav[0] * math.sin(z * 0.15 + wav[1]) if abs(math.tan(ang)) > 1e-3 else mx0
    gs = C.rng(seed, 'stars')
    st = []
    n = int(1400 * (stars or 1.0))
    while len(st) < n:
        x, z = gs.uniform(-W / 2, W / 2), gs.uniform(hz - 1, H)
        dm = abs(x - milky_x(z))
        p = 0.25 + 0.75 * math.exp(-(dm / 4.0) ** 2)
        if math.hypot(x - M['x'], z - M['z']) < M['R'] * 2.1:
            continue
        if gs.random() < p:
            b = 0.3 + 0.7 * gs.random() ** 2.5
            st.append(dict(x=x, z=z, b=b, s=0.05 + 0.15 * b, ph=gs.random(), rank=gs.random() * (1.2 - b)))
    st.sort(key=lambda s: s['rank'])
    gc = C.rng(seed, 'clouds')
    banks = []
    nb = 3 if clouds is None else clouds
    for k in range(nb):
        base = hz - 1.5 - 3.2 * k
        amp = gc.uniform(2.5, 5.0) * (1.0 - 0.15 * k)
        lobes = [(gc.uniform(0.12, 0.6), gc.uniform(0, 6.3), gc.uniform(0.3, 1.0)) for _ in range(6)]
        banks.append(dict(base=base, top=hz + gc.uniform(-0.5, 1.5) - 2.2 * k, amp=amp, lobes=lobes, drift=0.3 + 0.35 * k))
    return dict(M=M, hz=hz, stars=st, banks=banks, milky_x=milky_x)


def build(lod=0, seed=1, w=None, h=None, d=None, moon_r=None, moon_pos=None, stars=None, clouds=None, horizon=None):
    p = genlib.proxy(ASSET)
    W = float(w or p['w']); H = float(h or p['h'])
    L = layout(seed, W, H, moon_r, moon_pos, stars, clouds, horizon)
    R = RES[lod]
    mb = genlib.MeshBuilder(); bm = mb.bm
    S = {k: mb.slot('neon_tube', tint=t, emissive_level=e) for k, (t, e) in SLOTS.items()}
    lay = {k: bm.verts.layers.float.new(k) for k in ('kz_star', 'kz_phase', 'kz_bright', 'kz_drift')}
    bow = lambda x: -0.4 * (2 * x / W) ** 2
    hz = L['hz']
    # sky card
    nx, nz = R['grid']
    V = [[bm.verts.new((-W / 2 + W * i / nx, bow(-W / 2 + W * i / nx), H * j / nz)) for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            f = bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))   # x then z: normal -Y ...
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
            zc = H * (j + 0.5) / nz
            f.material_index = S['sky_low'] if zc < hz + 0.2 * H else (S['sky'] if zc < hz + 0.5 * H else S['sky_top'])

    def quad_strip(pts_a, pts_b, mi, ydef):
        A = [bm.verts.new((x, ydef(x), z)) for x, z in pts_a]
        B = [bm.verts.new((x, ydef(x), z)) for x, z in pts_b]
        fs = []
        for k in range(len(A) - 1):
            f = bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
            fs.append(f)
        mb._tag(fs, mi)
        return A + B
    # milky way glow strip
    if R['milky']:
        n = R['milky']
        zs = [hz + (H - hz) * k / n for k in range(n + 1)]
        mxf = L['milky_x']
        quad_strip([(max(-W / 2, min(W / 2, mxf(z) - 2.2 - 0.6 * math.sin(z * 0.4))), z) for z in zs],
                   [(max(-W / 2, min(W / 2, mxf(z) + 2.2 + 0.6 * math.cos(z * 0.33))), z) for z in zs], S['milky'],
                   lambda x: bow(x) + 0.02)
    # moon, maria, halo
    M = L['M']
    yM = lambda x: bow(x) + 0.3

    def disc(cx, cz, r, n, mi, y, rf=None):
        c = bm.verts.new((cx, y, cz))
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            rr = r * (rf(a) if rf else 1.0)
            ring.append(bm.verts.new((cx + rr * math.cos(a), y, cz + rr * math.sin(a))))
        fs = [bm.faces.new((c, ring[k], ring[(k + 1) % n])) for k in range(n)]
        for f in fs:
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
        mb._tag(fs, mi)
        return [c] + ring

    def annulus(cx, cz, r0, r1, n, mi, y):
        A = [bm.verts.new((cx + r0 * math.cos(2 * math.pi * k / n), y, cz + r0 * math.sin(2 * math.pi * k / n))) for k in range(n)]
        B = [bm.verts.new((cx + r1 * math.cos(2 * math.pi * k / n), y, cz + r1 * math.sin(2 * math.pi * k / n))) for k in range(n)]
        fs = []
        for k in range(n):
            f = bm.faces.new((A[k], A[(k + 1) % n], B[(k + 1) % n], B[k])); f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
            fs.append(f)
        mb._tag(fs, mi)
    yb = bow(M['x'])
    disc(M['x'], M['z'], M['R'], R['moon'], S['moon'], yb + 0.3)
    for a, rr, sz, ph in M['maria'][:R['maria']]:
        cx, cz = M['x'] + M['R'] * rr * math.cos(a), M['z'] + M['R'] * rr * math.sin(a)
        s = M['R'] * sz * min(1.0, (1 - rr) / sz + 0.3)
        disc(cx, cz, s, R['maria_n'], S['maria'], yb + 0.31,
             rf=lambda t, ph=ph: 1 + 0.25 * math.sin(2 * t + ph[0] * 3) + 0.15 * math.sin(3 * t + ph[1] * 3))
    annulus(M['x'], M['z'], M['R'] * 1.0, M['R'] * 1.35, R['moon'], S['halo1'], yb + 0.25)
    if R['halo'] > 1:
        annulus(M['x'], M['z'], M['R'] * 1.35, M['R'] * 2.0, R['moon'], S['halo2'], yb + 0.24)
    # star diamonds
    for k, s in enumerate(L['stars'][:R['stars']]):
        y = bow(s['x']) + 0.05
        e = s['s'] * (1 if lod < 2 else 1.6)
        vs = [bm.verts.new(q) for q in ((s['x'] - e, y, s['z']), (s['x'], y, s['z'] - e), (s['x'] + e, y, s['z']), (s['x'], y, s['z'] + e))]
        f = bm.faces.new(vs); f.normal_update()
        if f.normal.y < 0:
            f.normal_flip()
        mb._tag([f], S['star'])
        for v in vs:
            v[lay['kz_star']] = 1.0; v[lay['kz_phase']] = s['ph']; v[lay['kz_bright']] = s['b']
    # sprite stars (loose vertices, runtime)
    gsp = C.rng(seed, 'sprites')
    for k in range(R['sprites']):
        x, z = gsp.uniform(-W / 2, W / 2), gsp.uniform(hz, H)
        if math.hypot(x - M['x'], z - M['z']) < M['R'] * 2.0 or gsp.random() > 0.3 + 0.7 * math.exp(-((x - L['milky_x'](z)) / 5.0) ** 2):
            continue
        v = bm.verts.new((x, bow(x) + 0.04, z))
        v[lay['kz_star']] = 1.0; v[lay['kz_phase']] = gsp.random(); v[lay['kz_bright']] = 0.15 + 0.5 * gsp.random() ** 2
    # cloud banks (far -> near)
    names = ['cloud_far', 'cloud_mid', 'cloud_near']
    for k, b in enumerate(L['banks'][:R['banks']]):
        n = R['cseg']
        xs = [-W / 2 + W * i / n for i in range(n + 1)]
        def top(x, b=b):
            v = sum(a * (0.5 + 0.5 * math.sin(f * x + ph)) for f, ph, a in b['lobes']) / sum(l[2] for l in b['lobes'])
            return b['top'] + b['amp'] * v ** 2.2
        vs = quad_strip([(x, max(0.0, b['base'] - 2.5)) for x in xs], [(x, top(x)) for x in xs], S[names[k]],
                        lambda x, k=k: bow(x) + 0.3 + 0.08 * k)
        for v in vs:
            v[lay['kz_drift']] = b['drift']
    dx, dy, dz = C.centre_base(mb)
    me = bpy.data.meshes.new(ASSET); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(ASSET, me); bpy.context.scene.collection.objects.link(o)
    import matlib
    for i, (mid, params) in enumerate(mb.slots):
        matlib.assign(o, mid, slot=i, **params)
    col = me.color_attributes.new('kz_sky_col', 'FLOAT_COLOR', 'POINT')
    A = {k: me.attributes[k] for k in ('kz_star', 'kz_phase', 'kz_bright', 'kz_drift')}
    for i in range(len(me.vertices)):
        col.data[i].color = (A['kz_star'].data[i].value, A['kz_phase'].data[i].value, A['kz_bright'].data[i].value, A['kz_drift'].data[i].value)
    mpos = [M['x'] + dx, yb + 0.3 + dy, M['z'] + dz]
    C.set_json_props(o, kz_snap='ground', kz_facing='+Y',
                     kz_anim=dict(type='shader', what='cloud drift, star twinkle', star_attr='kz_star', phase_attr='kz_phase',
                                  bright_attr='kz_bright', drift_attr='kz_drift', color_attr='kz_sky_col',
                                  drift_m_s=0.15, twinkle_hz=[0.2, 1.2], cloud_slots=[S[n] for n in names], star_slot=S['star']),
                     kz_lights=[C.light_entry(mpos, color_k=4100, watts=0, kind='sun', strength=0.08,
                                              direction_from=mpos, color=kelvin_rgb(4100), note='moonlight for the bake')],
                     kz_moon=dict(pos=[round(c, 3) for c in mpos], r=round(M['R'], 3)),
                     kz_params=dict(w=W, h=H, moon_r=round(M['R'], 3), horizon_z=round(hz + dz, 3),
                                    banks=len(L['banks']), star_diamonds=min(R['stars'], len(L['stars']))))
    genlib.finish(o, smooth_angle=30)
    return o
