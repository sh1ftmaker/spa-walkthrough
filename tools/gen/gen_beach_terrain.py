"""Black sand beach and sea mouth (beach_terrain): the Wave Grotto beach - a black sand slope running down to
the waterline with braided runnels, a wet band and a foam edge at the waterline, basalt rocks along the
shore, and the stalactite-fringed sea arch at the seaward (+Y) end that frames the moon.

Concepts: lookbook 20 (hero: black sand beach curving down to teal surf, glossy wet band and a white foam
line at the waterline, dark basalt rocks scattered on the sand, the cave mouth as a rock arch ~25-30 m
wide hung with amber dripstone stalactites, sea stacks and the moon beyond); lookbook 35 (B3 plan
I3-J5 'Wave Grotto (30 C)' + 'SEA MOUTH ->': beach fan ~40 x 40 m at the 20 m grid = 150 px; lounger
row on the sand, the sea mouth on the east wall).
Targets: footprint 40 x 40 m; beach rises 1.2 m from the sea floor at the front to the back edge
(dry sand 0.7 m above water), waterline z 0.5 m at ~y = +4 (shore curve +-3 m), 2-4 braided runnels
0.4-0.9 m wide, 5-9 cm deep, foam band +-6 cm around the waterline, 7-11 basalt rocks 0.5-1.6 m,
arch span 26 m (clear opening ~20 m), crown 15 m above water, rib section 3.5-5 m, 30-60 stalactites
1.0-5.0 m long on the intrados (fringe density). A lounger (2.0 m) from lookbook 20 sets the scale.
Proxy 40 x 40 x 1.0: the beach fits at 1.2 m; the arch makes it 17 m -> proposed h 17.5 (or split the
arch into its own asset; arch=False builds the beach alone).

Parameters: footprint (w, d), slope (beach rise, default 1.2), water_z (0.5), runnels 2-4 (seeded
paths), arch (bool), arch_span 20-30, arch_h 12-18, fringe 0-1 (stalactite density).
Seeds change: shore curve, runnel count and braid paths, rock layout, arch span / height / lean,
stalactite layout. Variants: 1 (+ seeds).

Construction: a height-field grid (LOD0 0.36 m, LOD1 0.6 m, LOD2 1.15 m, LOD3 2.9 m cells) with the
slope profile, low dunes, the curved shoreline, runnels carved by distance to braided polylines and
ripples at LOD0. Grid rows follow the shoreline so the height bands (dry / wet / foam / under water) are
smooth curves; the runnel beds are smooth glossy ribbons laid in the carved channels.
The arch is a tube with a lumpy, tapering rock section along a raised semi-ellipse whose feet stand in
the sea; stalactites are 5-6 sided cones on the intrados. No water mesh: kz_water_level / outline.
Materials (slots by part): dry sand black_sand 0.15; wet band black_sand wet 0.85 rough -0.1;
runnel bed black_sand wet 1.0 rough -0.15; under water black_sand 0.9; foam edge waterfall 0.3;
rocks basalt_wet 0.75; arch + stalactites cave_rock.
Animation: none (waves are fx_waves; kz_water_level + kz_shoreline feed them). Lighting: lightmap.
Budget: per 100 m2 2000/800/240/60 -> 1600 m2 = 32000/12800/3840/960 (BUDGET_SHEET).
"""
import math

import bmesh
from mathutils import Matrix, Vector, noise

import genlib
import kzgeo_common as C
from kzgeo_falls_lip_rock import smoothstep

ASSET = 'beach_terrain'
FEATURES = ['black sand slope to the waterline', 'braided runnels', 'wet foam edge', 'stalactite-fringed sea arch']
PROXY_SHEET = dict(w=40.0, d=40.0, h=17.5)
BUDGET_SHEET = [32000, 12800, 3840, 960]


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy or 1e-9
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - ax - vx * t, py - ay - vy * t)


def layout(seed, w=40.0, d=40.0, slope=1.2, water_z=0.5, runnels=None, arch=True, arch_span=None, arch_h=None, fringe=0.7):
    L = dict(w=w, d=d, rise=slope, wz=water_z, arch=arch, fringe=fringe)
    g = C.rng(seed, 'shore')
    L['shore_y'] = g.uniform(2.5, 5.0)
    L['shore_k'] = [(k, g.uniform(0, 6.28), a) for k, a in ((1, 2.2), (2, 1.2), (3, 0.6))]
    L['off'] = Vector((g.uniform(0, 80), g.uniform(0, 80), g.uniform(0, 80)))
    gr = C.rng(seed, 'runnels')
    n = runnels if runnels is not None else gr.randint(2, 4)
    paths = []
    for k in range(n):
        x = -w / 2 + w * (k + 0.5) / n + gr.uniform(-3, 3)
        y = -d / 2 + gr.uniform(0.5, 3.0)
        pts = [(x, y)]
        while y < L['shore_y'] + 2.0:
            y += 1.6
            x += gr.uniform(-1.1, 1.1)
            pts.append((x, y))
        paths.append((pts, gr.uniform(0.4, 0.9), gr.uniform(0.05, 0.09)))
        if gr.random() < 0.6:        # braid: a branch that leaves and rejoins (or reaches the sea)
            i0 = gr.randint(2, max(3, len(pts) // 2))
            bx, by = pts[i0]
            br = [(bx, by)]
            side = gr.choice([-1, 1])
            for j in range(gr.randint(4, 8)):
                by += 1.6; bx += side * gr.uniform(0.3, 1.0) * (1 if j < 3 else -1)
                br.append((bx, by))
            paths.append((br, gr.uniform(0.3, 0.55), gr.uniform(0.04, 0.06)))
    L['runnels'] = paths
    grk = C.rng(seed, 'rocks')
    rocks = []
    for k in range(grk.randint(7, 11)):
        rx = grk.uniform(-w / 2 + 2, w / 2 - 2)
        ry = L['shore_y'] + grk.uniform(-9, 5)
        s = grk.choice([0.5, 0.7, 0.9, 1.2, 1.6])
        rocks.append((rx, ry, s, grk.uniform(0, 6.28)))
    rocks.sort(key=lambda r: -r[2])
    L['rocks'] = rocks
    ga = C.rng(seed, 'arch')
    L['span'] = arch_span if arch_span is not None else ga.uniform(24.0, 28.0)
    L['ah'] = arch_h if arch_h is not None else ga.uniform(13.0, 16.0)
    L['lean'] = ga.uniform(-0.08, 0.08)
    L['arch_y'] = d / 2 - 7.0
    L['aoff'] = Vector((ga.uniform(0, 50), ga.uniform(0, 50), ga.uniform(0, 50)))
    gs = C.rng(seed, 'stal')
    L['stal'] = [(gs.uniform(0.04, 0.96), gs.uniform(-0.7, 0.7), gs.uniform(1.0, 5.0), gs.uniform(0.22, 0.6))
                 for _ in range(int(20 + 50 * fringe))]
    return L


def shore(L, x):
    return L['shore_y'] + sum(a * math.sin(k * math.pi * x / L['w'] + ph) for k, ph, a in L['shore_k'])


def height(L, x, y, lod):
    """beach surface z (water at L['wz'])"""
    sy = shore(L, x)
    wz, rise = L['wz'], L['rise']
    t = y - sy                                   # + towards the sea
    if t < 0:      # beach: concave rise to the back
        z = wz + (rise - wz) * (1 - math.exp(t / 9.0)) * 1.08
    else:          # under water: falls off to the sea floor
        z = wz - wz * (1 - math.exp(-t / 5.0))
    z = min(z, rise)
    z += 0.12 * noise.noise(Vector((x * 0.09, y * 0.09, 0.0)) + L['off']) * smoothstep(-0.5, -6, t)
    if lod == 0:   # wave-laid ripples on the wet band
        z += 0.012 * math.sin(y * 3.1 + 0.6 * noise.noise(Vector((x * 0.3, y * 0.3, 3.0)) + L['off'])) * smoothstep(-6, -1, t) * smoothstep(2, 0, t)
    m = 0.0
    for pts, wr, dep in L['runnels']:
        dmin = min(seg_dist(x, y, *pts[i], *pts[i + 1]) for i in range(len(pts) - 1))
        k = 1 - smoothstep(wr * 0.35, wr * 0.75, dmin)
        if k > 0:
            z -= dep * k * smoothstep(1.0, -1.5, t)
            m = max(m, k)
    return z, m, t


def build(lod=0, seed=1, w=40.0, d=40.0, slope=1.2, water_z=0.5, runnels=None, arch=True, arch_span=None, arch_h=None,
          fringe=0.7):
    L = layout(seed, w, d, slope, water_z, runnels, arch, arch_span, arch_h, fringe)
    mb = genlib.MeshBuilder()
    m_dry = mb.slot('black_sand', wetness=0.15)
    m_wet = mb.slot('black_sand', wetness=0.85, roughness_offset=-0.1)
    m_run = mb.slot('black_sand', wetness=1.0, roughness_offset=-0.15)
    m_sub = mb.slot('black_sand', wetness=0.9)
    m_foam = mb.slot('waterfall', emissive_level=0.3)
    m_rock = mb.slot('basalt_wet', wetness=0.75)
    m_arch = mb.slot('cave_rock')
    bm = mb.bm
    cell = C.lod_pick(lod, 0.36, 0.6, 1.15, 2.9)
    nx = max(4, int(round(w / cell))); ny = max(4, int(round(d / cell)))
    G, M, T = [], [], []
    # rows follow the shoreline (one grid row lies on it at every x), so the wet / foam bands are smooth curves
    v0 = (L['shore_y'] + d / 2) / d
    j0 = max(1, min(ny - 1, int(round(v0 * ny))))

    def ymap(x, j):
        sy = shore(L, x)
        if j <= j0:
            return -d / 2 + (sy + d / 2) * j / j0
        return sy + (d / 2 - sy) * (j - j0) / (ny - j0)
    for j in range(ny + 1):
        row, mr, tr = [], [], []
        for i in range(nx + 1):
            x = -w / 2 + w * i / nx
            y = ymap(x, j)
            z, m, t = height(L, x, y, lod)
            row.append(bm.verts.new((x, y, z))); mr.append(m); tr.append(z)
        G.append(row); M.append(mr); T.append(tr)
    wz = L['wz']
    fb = max(0.06, 0.25 * cell * 0.1)        # foam half-band in z
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((G[j][i], G[j][i + 1], G[j + 1][i + 1], G[j + 1][i]))
            zs = (T[j][i], T[j][i + 1], T[j + 1][i + 1], T[j + 1][i])
            za, zmin, zmax = sum(zs) / 4, min(zs), max(zs)
            mm = sum((M[j][i], M[j][i + 1], M[j + 1][i + 1], M[j + 1][i])) / 4
            if zmin <= wz + fb * 0.4 and zmax >= wz - fb:
                f.material_index = m_foam
            elif za < wz:
                f.material_index = m_sub
            elif za < wz + 0.28:
                f.material_index = m_wet
            else:
                f.material_index = m_dry
    # ---------------------------------------------------------------- runnel beds: smooth glossy ribbons in the carved channels
    for pts, wr, dep in L['runnels']:
        step = C.lod_pick(lod, 1, 2, 3, 6)
        P2 = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
        sub = C.lod_pick(lod, 3, 2, 1, 1)
        dense = []
        for a_, b_ in zip(P2[:-1], P2[1:]):
            for k in range(sub):
                u = k / sub
                dense.append((a_[0] + (b_[0] - a_[0]) * u, a_[1] + (b_[1] - a_[1]) * u))
        dense.append(P2[-1])
        dense = [p for p in dense if p[1] < shore(L, p[0]) + 0.3]
        if len(dense) < 2:
            continue
        hw = wr * 0.32
        lo, hi = [], []
        for k, (x, y) in enumerate(dense):
            a_ = dense[max(0, k - 1)]; b_ = dense[min(len(dense) - 1, k + 1)]
            tx, ty = b_[0] - a_[0], b_[1] - a_[1]; ln = math.hypot(tx, ty) or 1.0
            nx_, ny_ = -ty / ln * hw, tx / ln * hw
            za, _, _ = height(L, x - nx_, y - ny_, lod)
            zb, _, _ = height(L, x + nx_, y + ny_, lod)
            zc, _, _ = height(L, x, y, lod)
            lo.append(bm.verts.new((x - nx_, y - ny_, max(za, zc) + 0.012)))
            hi.append(bm.verts.new((x + nx_, y + ny_, max(zb, zc) + 0.012)))
        for k in range(len(lo) - 1):
            f = bm.faces.new((lo[k], lo[k + 1], hi[k + 1], hi[k])); f.material_index = m_run
    # ---------------------------------------------------------------- shore rocks (largest kept at far LODs)
    nk = C.lod_pick(lod, len(L['rocks']), len(L['rocks']), min(6, len(L['rocks'])), 3)
    for k, (rx, ry, s, rot) in enumerate(L['rocks'][:nk]):
        z0, _, _ = height(L, rx, ry, 2)
        r = C.rng(seed, f'rock{k}')
        C.hull_rock(mb, (rx, ry, z0 + s * 0.15), (s, s * 0.8, s * 0.6), m_rock, r, npts=C.lod_pick(lod, 16, 11, 8, 6),
                    ground=z0 - 0.15, rot=rot)
    # ---------------------------------------------------------------- sea arch (feet in the sea at +Y)
    if L['arch']:
        ga = C.rng(seed, 'archshape')
        span, ah, ay = L['span'], L['ah'], L['arch_y']
        ns = C.lod_pick(lod, 56, 28, 14, 8)
        sides = C.lod_pick(lod, 18, 10, 6, 5)
        pts, radii = [], []
        for k in range(ns + 1):
            a = math.pi * k / ns
            x = -math.cos(a) * span / 2
            z = max(0.0, math.sin(a)) ** 0.85 * ah
            pts.append(Vector((x, ay + L['lean'] * z, z - 1.2 * (1 - math.sin(a)))))
            th = 2.2 + 2.2 * (1 - math.sin(a)) ** 1.5                     # rib thicker at the feet
            radii.append((th * 1.2, th * 0.95 + 1.0 * math.sin(a) ** 2))   # deep lintel at the crown
        off = L['aoff']

        def mod(i, k, th):
            p = pts[i]
            q = Vector((p.x * 0.22, p.z * 0.22, th * 1.7)) + off
            return 1.0 + (0.4 * noise.noise(q) + 0.2 * noise.noise(q * 2.9)) * (lod <= 2)
        rings, _ = C.tube(mb, pts, radii, m_arch, sides=sides, cap0=True, cap1=True)
        if lod <= 2:          # craggy section (tube ignores mod for elliptical radii): radial fractal noise
            for i, ring in enumerate(rings):
                for v in ring:
                    dv = v.co - pts[i]
                    q = Vector((v.co.x * 0.2, v.co.y * 0.2, v.co.z * 0.2)) + off
                    v.co = pts[i] + dv * (1.0 + 0.32 * noise.noise(q) + 0.16 * noise.noise(q * 2.9) * (lod == 0))
        # fractured blocks bedded into the rib (break the tube silhouette into rock); biggest kept at far LODs
        blocks = []
        for k in range(18):
            u = ga.uniform(0.0, 1.0)
            a = math.pi * u
            x = -math.cos(a) * span / 2
            z = max(0.0, math.sin(a)) ** 0.85 * ah - 1.2 * (1 - math.sin(a))
            th = 2.2 + 2.2 * (1 - math.sin(a)) ** 1.5
            ang = ga.uniform(-1.2, 1.2) + (math.pi / 2 if ga.random() < 0.7 else -math.pi / 2)   # mostly outer / top side
            nrm = Vector((-math.cos(a) * math.cos(ang), 0.0, math.sin(a) * math.cos(ang))).normalized() if abs(math.cos(ang)) > 0.2 else Vector((0, 1, 0))
            off_y = math.sin(ang) * th * 1.1
            c = Vector((x, ay + L['lean'] * z + off_y, z)) + Vector((-math.cos(a), 0, math.sin(a))) * th * 0.85 * math.cos(ang)
            sz = ga.uniform(1.4, 3.0)
            blocks.append((sz, c))
        blocks.sort(key=lambda b: -b[0])
        for k, (sz, c) in enumerate(blocks[:C.lod_pick(lod, 18, 12, 6, 0)]):
            C.hull_rock(mb, c, (sz, sz * 0.8, sz * 0.7), m_arch, C.rng(seed, f'ablk{k}'), npts=C.lod_pick(lod, 12, 9, 7, 6),
                        rot=k * 1.3)
        # stalactites on the intrados (fringe), longest kept at far LODs
        st = sorted(L['stal'], key=lambda s: -s[2])
        nst = C.lod_pick(lod, len(st), len(st) * 2 // 3, 14, 6)
        for u, v, ln, rr in st[:nst]:
            a = math.pi * (0.08 + 0.84 * u)
            x = -math.cos(a) * span / 2
            z = max(0.0, math.sin(a)) ** 0.85 * ah - 1.2 * (1 - math.sin(a))
            th = 2.2 + 2.2 * (1 - math.sin(a)) ** 1.5
            # underside point of the rib section
            cz = z - (th * 0.95 + 1.0 * math.sin(a) ** 2) * 0.7 * math.sin(a)
            cx = x + th * 0.75 * math.cos(a) * 0.6
            cy = ay + L['lean'] * z + v * th * 0.8
            ln2 = ln * (0.5 + 0.5 * math.sin(a))
            if lod >= 2:
                ln2 *= 1.15
            mb.cylinder((cx, cy, cz - ln2 / 2 + 0.2), radius=rr * (1.4 if lod >= 2 else 1.0), depth=ln2 + 0.4, mi=m_arch,
                        segs=C.lod_pick(lod, 6, 5, 4, 3), radius2=0.0, cap=False, rot=(math.pi, 0, 0))   # tip down
    for v in bm.verts:                       # arch feet stand in the sea floor: clip them at the bed (z = 0)
        if v.co.z < 0.0:
            v.co.z = 0.0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # the terrain faces up
    dx, dy, dz = C.centre_base(mb, centre_x=True, centre_y=True)
    o = mb.to_object(ASSET)
    _terrain_up(o, {m_dry, m_wet, m_run, m_sub, m_foam})
    _terrain_up(o, {m_run})
    genlib.finish(o)
    sl = [[round(x + dx, 3), round(shore(L, x) + dy, 3)] for x in [-w / 2 + w * k / 32 for k in range(33)]]
    ol = [[-w / 2 + dx, s[1]] for s in sl[:1]] + sl + [[w / 2 + dx, d / 2 + dy], [-w / 2 + dx, d / 2 + dy]]
    C.water_props(o, level_z=wz + dz, outline_xy=[(p[0], p[1]) for p in sl] + [(w / 2 + dx, d / 2 + dy), (-w / 2 + dx, d / 2 + dy)],
                  kz_shoreline=sl, kz_runnels=[[[round(x + dx, 3), round(y + dy, 3)] for x, y in pts] for pts, _, _ in L['runnels']])
    C.set_json_props(o, kz_anim=dict(type='none', note='waves: fx_waves along kz_shoreline'),
                     kz_params=dict(w=w, d=d, slope=slope, water_z=wz, runnels=len(L['runnels']), arch=bool(L['arch']),
                                    arch_span=round(L['span'], 2), arch_h=round(L['ah'], 2), fringe=fringe))
    return o


def _terrain_up(o, slots):
    bm = bmesh.new(); bm.from_mesh(o.data)
    fs = [f for f in bm.faces if f.material_index in slots]
    if sum(f.normal.z for f in fs) < 0:
        for f in fs:
            f.normal_flip()
    bm.to_mesh(o.data); bm.free()
