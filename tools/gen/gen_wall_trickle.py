"""Wall trickle threads and basin.

Concept: refs/gen/sheet-vs-water-2.png #6, lookbook/img/05-mist-corridor.jpg.
Identifying features kept at every LOD: thin bright water threads falling from a lipped stone trough at the top down
a wet basalt face into a bulky rock pedestal with a lipped bowl that projects past the wall.

Round 2 construction (LOD0)
  * face: basalt columns (6-7) with calm 3-5 cm facet noise, large planar fall-lines, a recessed chute behind the
    threads with buttresses either side, and 3 ledge steps (rows are inserted at each ledge so it reads);
    ~26 small crag stones (5-11 cm) on top; tapers toward the top.
  * trough: a stone channel (~1.0 m x 0.12 m inside) lofted along X at the top: back wall, a 5 cm lip that projects
    4 cm past the face so the threads detach, and a water-filled floor (emissive `waterfall` plane).
    slot 'straight' | 'arched' (lip bows forward in plan) | 'stepped' (lip top steps down at the sides).
  * threads: 8-15 mm ribbons, wider at the top and tapering down, irregular spacing with some pairs, from the lip
    to the bowl water level; they hang free off the lip then cling to and follow the face (envelope-smoothed).
  * pedestal: a ~0.8 m high lumpy elliptical rock pedestal (~1.0 x 0.55 m, projecting ~0.35 m past the face) with a
    sunken bowl, a raised 5 cm rim lip and a spill notch; two tiers of hull boulders make it craggy.
    `basin=False` gives a drain slab with pebbles instead.
  * cheek: staggered ashlar paving (0.25-0.3 m courses, 2 blocks per course, offset each course) on one side.
Parameters (build(lod, seed, ...)):
  h 1.5-3 m (default ~2.3-2.5; proxy 2.5 +5 %)   threads 1-8 (seed defaults 6/4/8)   spread 0.2-1.2 m
  basin True/False   slot 'straight'|'arched'|'stepped'   w 0.9-1.2 m
Animation: shader flow scroll on the `waterfall` faces (UV0 v runs along each thread) and sim splash/fx_drips at:
  kz_water_level (m), kz_thread_xs, kz_thread_top_z, kz_splash_pts, kz_drip_slot, kz_basin, kz_light (40 W, 6500 K).
Emissive: thread faces and the trough water (`waterfall`).
Proxy note: the pedestal brings the footprint to ~0.6-0.65 m deep (proxy d 0.6); propose d 0.7.
"""
import json
import math
import bmesh
from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_wall_trickle as kw
from kzgeo_wall_trickle import n3, hull_rock

ASSET = 'wall_trickle'
FEATURES = ['water threads from lipped trough', 'wet basalt column face', 'bulky rock pedestal basin with lip and spill notch', 'stone trough lip']


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def build(lod, seed, h=None, threads=None, spread=None, basin=True, slot=None, w=None):
    r = genlib.rng(seed, ASSET)
    H = h or r.uniform(2.3, 2.5)
    W = w or r.uniform(1.08, 1.18)
    nT = max(1, min(8, threads or [6, 4, 8][(seed - 1) % 3]))
    nT_geo = min(nT, 2) if lod == 3 else nT
    spread = spread or [0.55, 0.32, 0.9][(seed - 1) % 3] * r.uniform(0.9, 1.1)
    spread = min(spread, W - 0.3, 1.2)
    slot = slot or ['straight', 'arched', 'stepped'][(seed - 1) % 3]
    off = Vector((r.uniform(0, 90), r.uniform(0, 90), r.uniform(0, 90)))
    xc = r.uniform(-0.16, 0.16) * (W - spread) / 0.5 if nT > 1 else r.uniform(-0.15, 0.15)
    xc = max(-(W / 2 - spread / 2 - 0.1), min(W / 2 - spread / 2 - 0.1, xc))
    LV = {0: dict(ncol=r.randint(6, 7), nrow=6, tseg=12, bN=14, ncheek=7, ncrag=22),
          1: dict(ncol=4, nrow=4, tseg=4, bN=10, ncheek=4, ncrag=4),
          2: dict(ncol=3, nrow=2, tseg=2, bN=8, ncheek=0, ncrag=0),
          3: dict(ncol=0, nrow=0, tseg=1, bN=6, ncheek=0, ncrag=0)}[lod]
    mb = genlib.MeshBuilder()
    rock = mb.slot('basalt_wet', wetness=1.0)
    rock2 = mb.slot('basalt_wet', wetness=0.85, scale=1.4)
    stone = mb.slot('paving', wear=0.35)
    trough_m = mb.slot('paving', wear=0.6, scale=1.6)
    water = mb.slot('waterfall', emissive_level=1.4)
    bm = mb.bm
    y_back = -0.27
    y0 = -0.10
    lean = r.uniform(0.04, 0.09)
    # ------------------------------------------------------------ pedestal parameters
    zb = r.uniform(0.52, 0.58)                       # rim height: measured ~0.55 m on sheet-vs-water-2 #6 (297 px = 2.5 m)
    PX = r.uniform(0.47, 0.52)                       # base half width of the pedestal
    PY = 0.30                                        # base half depth
    bx = max(-0.06, min(0.06, xc * 0.4 + r.uniform(-0.04, 0.04)))
    by = 0.0
    zw = zb - 0.045
    z_end = zw if basin else 0.05
    notch_ang = math.pi / 2 + r.uniform(-0.3, 0.3)
    bulge_k = r.uniform(0.03, 0.06)
    ledges = sorted(r.uniform(1.0, H - 0.5) for _ in range(3))

    def mass(z):
        return bulge_k * (1 - z / H) ** 1.7 + lean * (z / H) ** 3.0

    def conv(x):
        d = abs(x - xc) - (spread / 2 + 0.07)
        t = _smooth(d / 0.16)
        return -0.07 * (1 - t) + 0.06 * t

    def ledge_y(col, z):
        return sum((0.055 * n3((col * 1.3, k * 3.1, 0.2), off)) * _smooth((z - zk) / 0.05) for k, zk in enumerate(ledges))

    def face_y(x, z):
        i = int((x + W / 2) / W * 7)
        return y0 + n3((i * 1.7, 0.31, seed), off) * 0.1 + ledge_y(i, z) + n3((x * 5.0, z * 5.0, 1.3), off) * 0.008 + mass(z) + conv(x)

    # ------------------------------------------------------------ face
    bvh = None
    if lod <= 1:
        ncol, nrow = LV['ncol'], LV['nrow']
        ws = [r.uniform(0.7, 1.35) for _ in range(ncol)]
        sx = W / sum(ws)
        edges = [-W / 2]
        for q in ws:
            edges.append(edges[-1] + q * sx)
        zl = [0.0] + [(k / nrow) * H + r.uniform(-0.2, 0.2) * H / nrow for k in range(1, nrow)] + [H]
        if lod == 0:
            for zk in ledges:
                zl += [zk - 0.01, zk + 0.06]
        zrows = sorted(zl)
        rows = []
        for zi, z in enumerate(zrows):
            row = []
            jag_l = 0.09 * (0.5 + 0.5 * n3((0.3, z * 1.3, 5), off)) if lod == 0 else 0.0
            jag_r = 0.09 * (0.5 + 0.5 * n3((0.9, z * 1.3, 6), off)) if lod == 0 else 0.0
            for ci in range(ncol):
                for xe, side in ((edges[ci], -1), (edges[ci + 1], 1)):
                    tilt = side * 0.012 * n3((ci, 4.0, 4.0), off)
                    yv = y0 + n3((ci * 2.3, 0.1, 3.0), off) * 0.1 + ledge_y(ci, z) + tilt + mass(z) + conv(xe) + n3((xe * 9, z * 7, 2.0), off) * 0.008
                    xv = xe + (0.007 * side if ci < ncol - 1 else 0)
                    if ci == 0 and side == -1:
                        xv += jag_l
                    if ci == ncol - 1 and side == 1:
                        xv -= jag_r
                    row.append(bm.verts.new((xv * (1 - 0.1 * (z / H) ** 1.4), yv, z)))
            rows.append(row)
        mb._tag(kw.grid(bm, rows, None, flip=True), rock)
        for side in (0, -1):
            ring = [bm.verts.new((rows[zi][side].co.x, y_back, z)) for zi, z in enumerate(zrows)]
            col = [row[side] for row in rows]
            for k in range(len(zrows) - 1):
                q = (col[k], col[k + 1], ring[k + 1], ring[k])
                f = bm.faces.new(q if side == 0 else q[::-1])
                f.material_index = rock2
        # small crag stones (5-11 cm: facet scale 3-5 cm after the hull) keyed onto the face
        for k in range(LV['ncrag']):
            u = r.random()
            x = (u ** 0.8 if r.random() < 0.5 else 1 - u ** 0.8) * W - W / 2 if r.random() < 0.55 else r.uniform(-W / 2, W / 2)
            z = 0.85 + (H - 1.45) * r.random() ** 1.3
            sz_ = r.uniform(0.045, 0.1)
            x = max(-W / 2 + sz_ * 1.75, min(W / 2 - sz_ * 1.75, x))
            hull_rock(mb, (x, face_y(x, z) + sz_ * 0.1, z), (sz_ * r.uniform(1.0, 1.7), sz_ * r.uniform(0.55, 0.9), sz_ * r.uniform(0.7, 1.2)),
                      rock if k % 2 else rock2, r, npts=7 if lod == 0 else 6, rot=r.uniform(-0.5, 0.5), rmin=0.8)
        # 2-3 ledges projecting 0.1-0.2 m (threads touch and break on them) and corner overhangs
        for k, zk in enumerate(ledges if lod == 0 else ledges[:1]):
            lx = max(-W / 2 + 0.3, min(W / 2 - 0.3, xc + r.uniform(-0.18, 0.18)))
            hull_rock(mb, (lx, face_y(lx, zk) + 0.02, zk), (r.uniform(0.2, 0.3), r.uniform(0.14, 0.2), 0.045), rock2, r, npts=8, rot=r.uniform(-0.15, 0.15), rmin=0.85)
        for sd in (-1, 1):
            hull_rock(mb, (sd * (W / 2 - 0.17), face_y(sd * (W / 2 - 0.17), H - 0.5) + 0.09, H - 0.5), (0.16, 0.17, 0.2), rock, r, npts=8 if lod == 0 else 6)
        from mathutils.bvhtree import BVHTree
        bvh = BVHTree.FromBMesh(bm)
    elif lod == 2:
        ncol = 3
        xs = [-W / 2 + W * i / ncol for i in range(ncol + 1)]
        rows = [[bm.verts.new((xs[ci], face_y(xs[ci], z), z)) for ci in range(ncol + 1)] for z in (0.0, H * 0.5, H)]
        mb._tag(kw.grid(bm, rows, None, flip=True), rock)
        mb.box((0, (y_back + y0) / 2, H / 2), (W, abs(y0 - y_back) - 0.02, H), rock2)
    else:
        kg.prism_x(mb, [(y_back, 0.0), (y0 + bulge_k, 0.0), (y0 + lean * 0.3, H * 0.5), (y0 + lean + 0.03, H - 0.2),
                        (y0 + 0.1, H - 0.2), (y0 + 0.1, H), (y_back, H)], -W * 0.5, W * 0.5, rock)

    def face_hit(x, z):
        if bvh is None:
            return face_y(x, z)
        hit = bvh.ray_cast(Vector((x, 1.0, z)), Vector((0, -1, 0)))
        return hit[0].y if hit[0] is not None else face_y(x, z)

    # ------------------------------------------------------------ thread x positions (irregular, some pairs)
    tx = []
    for i in range(nT_geo):
        u = (i + 0.5) / nT_geo
        x = xc + (u - 0.5) * spread + r.uniform(-0.3, 0.3) * spread / max(nT_geo, 2)
        if i % 3 == 1 and nT_geo > 3:
            x = tx[-1] + r.uniform(0.028, 0.045)            # a close pair
        tx.append(max(-W / 2 + 0.08, min(W / 2 - 0.08, x)))
    tx.sort()
    thin = []
    if lod == 0 and nT >= 3:
        for i in range(2):
            thin.append(max(-W / 2 + 0.08, min(W / 2 - 0.08, xc + r.uniform(-0.5, 0.5) * spread)))
    # ------------------------------------------------------------ trough with a projecting lip
    yf_top = max(face_hit(x, H - 0.3) for x in tx)
    yl = yf_top + 0.04 + 0.01                          # lip front: 4 cm past the face
    zt0 = H - 0.2
    xl = W * 0.46
    lip_top = H - 0.012
    if lod <= 1:
        nx = 9 if slot != 'straight' else 4
        xs_list = [-xl + 2 * xl * k / (nx - 1) for k in range(nx)]
        rows = []
        for x in xs_list:
            u = x / xl
            bow = 0.12 * (1 - u * u) if slot == 'arched' else 0.0
            lz = lip_top - (0.06 if (slot == 'stepped' and abs(u) > 0.5) else 0.0)
            yl_x = yl + bow + 0.01 * n3((x * 4, 1.5, 0.2), off)
            P = [(y_back, zt0), (yl_x, zt0), (yl_x + 0.006, H - 0.1), (yl_x, lz), (yl_x - 0.05, lz), (yl_x - 0.05, H - 0.07),
                 (yl_x - 0.17, H - 0.07), (yl_x - 0.17, H), (y_back, H)]
            rows.append([bm.verts.new((x, y, z)) for y, z in P])
        fs = kw.grid(bm, rows, None, close_u=True)
        fs.append(bm.faces.new(rows[0][::-1])); fs.append(bm.faces.new(rows[-1]))
        mb._tag(fs, trough_m)
        # water in the trough
        yw0, yw1 = rows[0][6].co.y + 0.01, rows[0][5].co.y - 0.01
        wq = [bm.verts.new((-xl + 0.02, yw0, H - 0.035)), bm.verts.new((xl - 0.02, yw0, H - 0.035)),
              bm.verts.new((xl - 0.02, yw1, H - 0.035)), bm.verts.new((-xl + 0.02, yw1, H - 0.035))]
        mb._tag([bm.faces.new(wq[::-1])], water)
    elif lod == 2:
        mb.box((0, (y_back + yl) / 2, H - 0.1), (xl * 2, yl - y_back, 0.2), trough_m)
    # ------------------------------------------------------------ threads
    thread_info = []
    for ti, x in enumerate(tx + thin):
        is_thin = ti >= len(tx)
        w_top = 0.006 if is_thin else r.uniform(0.011, 0.015) * (1.1 if nT <= 3 else 1.0)
        w_bot = 0.0035 if is_thin else r.uniform(0.008, 0.0105)
        nseg = LV['tseg']
        ztop = lip_top - 0.006
        zs = [ztop - (ztop - z_end) * (k / nseg) for k in range(nseg + 1)]
        raw = [face_hit(x, z) if lod <= 1 else face_y(x, z) for z in zs]
        if lod <= 1:
            env = [max(raw[max(0, k - 1):k + 2]) for k in range(len(raw))]
            for _ in range(2):
                env = [env[0]] + [(env[k - 1] + 2 * env[k] + env[k + 1]) / 4 for k in range(1, len(env) - 1)] + [env[-1]]
            raw = env
        pts, wd = [], []
        for k, z in enumerate(zs):
            t = k / nseg
            att = _smooth((ztop - z) / 0.55)
            y = raw[k] + 0.018 + (yl + 0.008 - raw[k] - 0.018) * (1 - att)
            pts.append(Vector((x, y, z)))
            wd.append(w_top + (w_bot - w_top) * t)
        kw.ribbon(mb, pts, wd, water)
        thread_info.append((x, pts[-1]))
    # ------------------------------------------------------------ pedestal basin (elliptical lathe, lumpy)
    N = LV['bN']
    rimlip = 0.07
    if basin:
        if lod == 0:
            specs = [(0.0, PX, PY), (0.18, PX * 0.96, PY * 0.97), (0.36, PX * 0.88, PY * 0.92), (zb - 0.05, PX * 0.82, PY * 0.88),
                     (zb, PX * 0.8, PY * 0.86), (zb + rimlip, PX * 0.76, PY * 0.82), (zb + rimlip, PX * 0.66, PY * 0.72),
                     (zb - 0.05, PX * 0.62, PY * 0.66), (zb - 0.15, PX * 0.5, PY * 0.52)]
        elif lod == 1:
            specs = [(0.0, PX, PY), (0.3, PX * 0.9, PY * 0.94), (zb, PX * 0.8, PY * 0.86), (zb + rimlip, PX * 0.76, PY * 0.82),
                     (zb + rimlip, PX * 0.66, PY * 0.72), (zb - 0.13, PX * 0.5, PY * 0.55)]
        elif lod == 2:
            specs = [(0.0, PX, PY), (zb, PX * 0.8, PY * 0.86), (zb + rimlip, PX * 0.74, PY * 0.8), (zb - 0.1, PX * 0.55, PY * 0.6)]
        else:
            specs = [(0.0, PX * 1.02, PY), (zb + rimlip, PX * 0.78, PY * 0.84)]
        rr_ = []
        for si, (z, rx, ry) in enumerate(specs):
            row = []
            for k in range(N):
                a = 2 * math.pi * k / N
                rj = (1.0 + 0.1 * n3((math.cos(a) * 1.5, math.sin(a) * 1.5, si * 0.7), off)) if lod <= 1 else 1.0
                zz = z
                rim_rows = (4, 5, 6) if lod == 0 else ((3, 4) if lod == 1 else (1, 2))
                if lod <= 2 and si in rim_rows:
                    d = abs(((a - notch_ang) + math.pi) % (2 * math.pi) - math.pi)
                    if d < 0.5:
                        zz -= 0.05 * (1 - d / 0.5)
                row.append(bm.verts.new((bx + rx * rj * math.cos(a), max(y_back + 0.01, by + ry * rj * math.sin(a)), zz)))
            rr_.append(row)
        fs = kw.grid(bm, rr_, None, close_u=True)
        fs.append(bm.faces.new(rr_[-1] if lod == 3 else rr_[-1][::-1]))
        mb._tag(fs, rock2)
        if lod <= 1:                                   # craggy lumps around the pedestal body
            tiers = [(0.14, 0.95, 9 if lod == 0 else 4, 0.1, 0.16), (0.32, 0.86, 7 if lod == 0 else 3, 0.08, 0.13)]
            for ti_, (zt, rk, cnt, smin, smax) in enumerate(tiers):
                for k in range(cnt):
                    a = (k + r.uniform(-0.25, 0.25) + 0.5 * ti_) * 2 * math.pi / cnt
                    d = abs(((a - notch_ang) + math.pi) % (2 * math.pi) - math.pi)
                    if d < 0.5:
                        continue
                    s_ = r.uniform(smin, smax)
                    ext = s_ * 1.25
                    ex = max(-W / 2 + ext * 0.85, min(W / 2 - ext * 0.85, bx + PX * rk * math.cos(a)))
                    ey = max(y_back + ext * 0.85, min(0.3 - ext * 0.85, by + PY * rk * math.sin(a)))
                    hull_rock(mb, (ex, ey, zt + r.uniform(-0.03, 0.06)), (s_ * 1.25, s_ * 0.85, s_ * r.uniform(0.8, 1.15)),
                              rock if (k + ti_) % 2 else rock2, r, npts=8 if lod == 0 else 6, ground=0.0, rot=a + r.uniform(-0.4, 0.4))
    else:
        row = [bm.verts.new((bx + PX * 0.8 * math.cos(2 * math.pi * k / N), by + PY * 0.9 * math.sin(2 * math.pi * k / N), 0.0)) for k in range(N)]
        top = [bm.verts.new((v.co.x * 0.97, v.co.y * 0.97, 0.045)) for v in row]
        mb._tag(kw.grid(bm, [row, top], None, close_u=True) + [bm.faces.new(top)], stone)
    # ------------------------------------------------------------ thin stepped ashlar cheek
    side = [1, -1, 1][(seed - 1) % 3]
    if LV['ncheek']:
        ncs = 8 if lod == 0 else 4
        ch = (H * 0.8) / ncs
        cw = 0.3
        for c in range(ncs):
            xr = cw - 0.1 * (c // 3)                         # steps back 0.1 m every 3 courses
            depth = r.uniform(0.15, 0.19)
            nb_ = 2 if (lod == 0 or c % 2) else 1
            split = xr * (0.5 if c % 2 == 0 else r.uniform(0.3, 0.4))
            spans = ((0.0, split), (split, xr)) if nb_ == 2 else ((0.0, xr),)
            for bi, (b0, b1) in enumerate(spans):
                xa, xb = side * (W / 2 - xr + b0), side * (W / 2 - xr + b1)
                mb.box(((xa + xb) / 2, y_back + depth / 2 + 0.01, ch * (c + 0.5)), (abs(xb - xa) - 0.006, depth, ch - 0.006),
                       stone if (c + bi) % 2 else trough_m)
    o = mb.to_object(ASSET)
    me = o.data
    b2 = bmesh.new(); b2.from_mesh(me)
    for f in b2.faces:
        if f.material_index == water:
            if abs(f.normal.z) < 0.9 and f.normal.y < 0:
                f.normal_flip()
            elif abs(f.normal.z) >= 0.9 and f.normal.z < 0:
                f.normal_flip()
    b2.to_mesh(me); b2.free()
    ys_ = [v.co.y for v in me.vertices]
    dy = -(max(ys_) + min(ys_)) / 2
    for v in me.vertices:
        v.co.y += dy
    genlib.finish(o, smooth_angle=48)
    b2 = bmesh.new(); b2.from_mesh(me)
    uv = b2.loops.layers.uv.get('UVMap')
    for f in b2.faces:
        if f.material_index == water and abs(f.normal.z) < 0.9:
            for l in f.loops:
                l[uv].uv = ((l.vert.co.x - xc) * 18.0 + 0.5, l.vert.co.z)
    b2.to_mesh(me); b2.free()
    thread_info = [(x, pt + Vector((0, dy, 0))) for x, pt in thread_info]
    o['kz_water_level'] = round(zw if basin else 0.05, 3)
    o['kz_thread_xs'] = json.dumps([round(x, 3) for x in tx])
    o['kz_thread_top_z'] = round(lip_top, 3)
    o['kz_splash_pts'] = json.dumps([[round(x, 3), round(pt.y, 3), round(z_end, 3)] for x, pt in thread_info])
    o['kz_drip_slot'] = json.dumps([round(xc, 3), round(yl + dy + 0.008, 3), round(lip_top, 3)])
    o['kz_light'] = json.dumps(dict(pos=[round(bx, 3), round(by + dy + 0.1, 3), round(zb + 0.3, 3)], color=[0.55, 0.85, 1.0], watts=40))
    o['kz_basin'] = json.dumps(dict(c=[round(bx, 3), round(by + dy, 3), round(zw if basin else 0.05, 3)], rx=round(PX * 0.5, 3), ry=round(PY * 0.62, 3)))
    o['kz_slot'] = slot
    return o
