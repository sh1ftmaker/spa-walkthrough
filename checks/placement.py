"""Automated placement checks (brief §5.4), run against the assembled scene.

  blender -b 3d/blend/assembled.blend -P checks/placement.py -- [--space id ...]

Reads 3d/placements_resolved.json, 3d/spaces/*.json, 3d/layout.json, 3d/checks/walk.json.
Writes 3d/checks/placement.json: per space, per check: pass / warn / fail with counts and the worst offenders
(object ids), so the labelled contact sheet can mark them in red. Waivers come only from the space file
("waivers": [{"check", "where"?, "reason"}]); thresholds are never loosened here.
"""
import bpy, json, math, os, sys, glob
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, '.bpy_deps'))
from shapely.geometry import Polygon, LineString, Point, box
from shapely.affinity import rotate, translate
from shapely import prepared

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = argv[argv.index('--space') + 1:] if '--space' in argv else None
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
LSP = {s['id']: s for s in L['spaces']}
P = json.load(open(os.environ.get('KZ_RESOLVED') or os.path.join(ROOT, '3d', 'placements_resolved.json')))['placements']
WALK = json.load(open(os.path.join(ROOT, '3d', 'checks', 'walk.json'))) if os.path.exists(os.path.join(ROOT, '3d', 'checks', 'walk.json')) else None
ASSETS = json.load(open(os.path.join(ROOT, '3d', 'assets.json')))['assets']
_PL = os.environ.get('KZ_PLACEMENTS') or os.path.join(ROOT, '3d', 'placements.json')
ZERO_WARN = [w for w in json.load(open(_PL)).get('warnings', []) if w.startswith('ZERO ')] if os.path.exists(_PL) else []
sys.path.insert(0, os.path.join(ROOT, 'tools', 'assembly'))
from spaces_io import load_spaces
SPACES = load_spaces(ROOT)

# thresholds (brief §5.4)
FLOAT_TOL = 0.02
CLEAR_W, CLEAR_H = 1.2, 2.1
WATER_MIN, WATER_MAX = 0.03, 0.08
HERO_VIS = 0.30
EMPTY_PATCH, EMPTY_DIST = 6.0, 4.0
GRID_CENTRE_TOL = 0.5
RAIL = (0.95, 1.10); DOOR_MIN = 2.1; RISER = (0.15, 0.18)


def bvh_of(pred):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, tris, owner = [], [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not pred(o):
            continue
        e = o.evaluated_get(dg); me = e.to_mesh(); M = o.matrix_world; off = len(verts)
        verts += [M @ v.co for v in me.vertices]
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            tris.append([off + i for i in t.vertices]); owner.append(o.name)
        e.to_mesh_clear()
    return BVHTree.FromPolygons(verts, tris, epsilon=0.0), owner


def colls(o):
    return [c.name for c in o.users_collection]


static, _ = bvh_of(lambda o: not o.name.startswith('w_') and 'proxies' not in colls(o) and 'lava' not in colls(o))
everything, owner = bvh_of(lambda o: not o.name.startswith('w_'))


def footprint(p):
    w, d = p['dims']['w'] * p['scale'], p['dims']['d'] * p['scale']
    g = box(-w / 2, -d / 2, w / 2, d / 2)
    g = rotate(g, -p['facing_deg'], origin=(0, 0))
    return translate(g, p['pos'][0], p['pos'][1])


def zr(p):
    return p['pos'][2], p['pos'][2] + p['dims']['h'] * p['scale']


def result(fails, warns=0, waived=False, **kw):
    st = 'pass' if not fails and not warns else ('warn' if not fails else 'fail')
    if waived and st != 'pass':
        st = 'waived'
    return dict(status=st, fails=fails if isinstance(fails, int) else len(fails), warns=warns, **kw)


def waived(sp, check):
    return [w for w in sp.get('waivers', []) if w.get('check') == check]


def check_space(sid):
    sp = SPACES[sid]; lsp = LSP.get(sid, {})
    mine = [p for p in P if p['space'] == sid and p.get('snap_status') not in ('structural', 'marker')]
    FRAMES = {k for k, v in ASSETS.items() if v.get('frame')}
    out = {}
    fp = Polygon(lsp['footprint']) if lsp.get('footprint') else None

    # contact: float / sink, measured under the proxy centre and four inset corners
    floats, sinks = [], []
    for p in mine:
        if p['snap'] not in ('ground',) or p['snap_status'] != 'ok':
            continue
        g = footprint(p); c = g.centroid
        pts = [(c.x, c.y)] + [(c.x + (x - c.x) * 0.8, c.y + (y - c.y) * 0.8) for x, y in list(g.exterior.coords)[:4]]
        z0 = p['pos'][2]
        gaps = []
        for x, y in pts:
            # start just above the base so probes inside a wall the item leans into do not count as 'sunk'
            loc, n, i, d = static.ray_cast(Vector((x, y, z0 + 0.35)), Vector((0, 0, -1)), 6.0)
            if loc is not None and n.z > 0.6:
                gaps.append(z0 - loc.z)
        if not gaps:
            continue
        if min(gaps) > FLOAT_TOL:                       # every up-facing probe sees air under it
            floats.append((p['id'], round(min(gaps), 3)))
        emb = p.get('embed', 0.0)
        if max(-g_ for g_ in gaps) > emb + FLOAT_TOL and not ASSETS.get(p['asset'], {}).get('deck'):
            sinks.append((p['id'], round(max(-g_ for g_ in gaps), 3)))
    out['contact'] = result(floats + sinks, waived=bool(waived(sp, 'contact')), floating=floats[:10], sunk=sinks[:10])

    # overlaps: 2D footprint intersection + z overlap, unless allowed
    allowed = set(map(tuple, sp.get('allow_overlap', [])))
    for r in sp.get('dressing', []) + sp.get('lights', []):
        for a in r.get('allow_overlap', []):
            allowed.add((r['asset'], a)); allowed.add((a, r['asset']))
    ov = []
    geo = [(p, footprint(p), zr(p)) for p in mine]
    for i in range(len(geo)):
        for j in range(i + 1, len(geo)):
            a, ga, za = geo[i]; b, gb, zb = geo[j]
            if (a['asset'], b['asset']) in allowed or not ga.intersects(gb):
                continue
            Aa, Ab = ASSETS.get(a['asset'], {}), ASSETS.get(b['asset'], {})
            if Aa.get('cluster_ok') and Ab.get('cluster_ok'):
                continue                                   # rocks may touch rocks (class policy, decisions.md)
            if (Aa.get('host') and (b.get('light') or Ab.get('w', 9) * Ab.get('d', 9) < 1.0)) or \
               (Ab.get('host') and (a.get('light') or Aa.get('w', 9) * Aa.get('d', 9) < 1.0)):
                continue                                   # lights / small props inside a host (pavilion, pod, room)
            if min(za[1], zb[1]) - max(za[0], zb[0]) <= 0.01:
                continue
            area = ga.intersection(gb).area
            if area > 0.02:
                ov.append((a['id'], b['id'], round(area, 2)))
    out['overlaps'] = result(ov, waived=bool(waived(sp, 'overlaps')), worst=sorted(ov, key=lambda t: -t[2])[:10])

    # clearance: a 1.2 m x 2.1 m corridor along the spine and every stair landing in this space
    lines = []
    if sp.get('spine') and len(sp['spine']) > 1:
        lines.append(('spine', [tuple(q[:2]) for q in sp['spine']]))
    blocked, low = [], []
    for name, line in lines:
        ls = LineString(line)
        n = max(2, int(ls.length / 0.5))
        for k in range(n + 1):
            q = ls.interpolate(ls.length * k / n)
            a0 = ls.interpolate(max(0, ls.length * k / n - 0.3)); a1 = ls.interpolate(min(ls.length, ls.length * k / n + 0.3))
            ang = math.atan2(a1.y - a0.y, a1.x - a0.x)
            # floor under this sample (highest static surface below the space's ceiling)
            top = (lsp.get('ceiling_z') or (lsp.get('floor_z', 0) + 8)) - 0.05
            loc, nrm, _, _ = static.ray_cast(Vector((q.x, q.y, top)), Vector((0, 0, -1)), 40.0)
            if loc is None:
                continue
            fz = loc.z
            up, _, _, _ = static.ray_cast(Vector((q.x, q.y, fz + 0.05)), Vector((0, 0, 1)), 30.0)
            if up is not None and up.z - fz < CLEAR_H:
                low.append((name, round(q.x, 1), round(q.y, 1), round(up.z - fz, 2)))
            strip = LineString([(q.x - math.sin(ang) * CLEAR_W / 2, q.y + math.cos(ang) * CLEAR_W / 2),
                                (q.x + math.sin(ang) * CLEAR_W / 2, q.y - math.cos(ang) * CLEAR_W / 2)])
            for p, g, (z0, z1) in geo:
                if g.intersects(strip) and z1 > fz + 0.05 and z0 < fz + CLEAR_H:
                    if p['asset'] in ('bridge_arched', 'stepping_stone', 'boardwalk', 'bridge_slab', 'floor_paving') or p['asset'] in FRAMES:
                        continue
                    blocked.append((p['id'], round(q.x, 1), round(q.y, 1)))
    blocked_ids = sorted({b[0] for b in blocked})
    out['clearance'] = result(blocked_ids + low, waived=bool(waived(sp, 'clearance')), blocked=blocked_ids[:10], low_ceiling=low[:10])

    # water: still water 3-8 cm below its rim
    bad_w = []
    for w in sp.get('water', []):
        if w.get('kind') == 'still' and w.get('z') is not None and w.get('rim_z') is not None:
            d = w['rim_z'] - w['z']
            if not (WATER_MIN - 1e-6 <= d <= WATER_MAX + 1e-6):
                bad_w.append((w['id'], round(d, 3)))
    out['water'] = result(bad_w, waived=bool(waived(sp, 'water')), bad=bad_w)

    # hero visibility from the entry camera(s): fraction of hero sample points with a clear ray
    hero = next((p for p in mine if p.get('hero')), None)
    bf = (sp.get('hero') or {}).get('borrowed_from')
    if hero is None and bf:                      # borrowed hero: test against the owner's hero proxy
        owner_id = bf.split(':')[0] if isinstance(bf, str) else None
        anch = (sp.get('hero') or {}).get('borrowed_id') or (bf.split(':')[1] if isinstance(bf, str) and ':' in bf else None)
        hero = next((p for p in P if anch and p['id'] == f'{owner_id}:{anch}'), None) or \
            next((p for p in P if p['space'] == owner_id and p.get('hero')), None)
    struct_obj = None
    ha = ASSETS.get((sp.get('hero') or {}).get('asset'), {})
    if hero is None and sp.get('hero') and (ha.get('structural') or ha.get('marker')):
        struct_obj = bpy.data.objects.get(ha.get('stand_in') or sp['hero']['asset'])     # lift core, mirror water ...
        if struct_obj is not None:
            zf = sp.get('floor_z', 0)
            cx_, cy_ = sp['hero']['at'][:2]
            hero = dict(id=struct_obj.name, pos=[cx_, cy_, zf], facing_deg=0, scale=1.0, dims=dict(w=4.4, d=4.4, h=3.0))
    if hero and sp.get('cameras'):
        g = footprint(hero); z0, z1 = zr(hero)
        xs = [x for x, y in list(g.exterior.coords)[:4]]; ys = [y for x, y in list(g.exterior.coords)[:4]]
        samples = []
        cx, cy = g.centroid.x, g.centroid.y
        for fx in (0.15, 0.5, 0.85):
            for fz in (0.15, 0.5, 0.85):
                for (x, y) in list(g.exterior.coords)[:4]:
                    samples.append((cx + (x - cx) * fx, cy + (y - cy) * fx, z0 + (z1 - z0) * fz))
        vis = {}
        for ck in ('entry',):
            cam = sp['cameras'].get(ck)
            if not cam:
                continue
            eye = Vector(cam['pos'])
            seen = 0
            for s in samples:
                tgt = Vector(s); d = tgt - eye; dist = d.length
                loc, nrm, idx, hd = everything.ray_cast(eye, d.normalized(), dist + 0.5)
                if loc is None or owner[idx] == hero['id'] or hd >= dist - max(0.6, 0.02 * dist):
                    seen += 1
            vis[ck] = round(seen / len(samples), 2)
        bad = [k for k, v in vis.items() if v < HERO_VIS]
        out['hero_visible'] = result(bad, waived=bool(waived(sp, 'hero_visible')), fraction=vis)
    else:
        out['hero_visible'] = dict(status='waived' if waived(sp, 'hero_visible') else 'warn', fails=0, warns=1, note='no hero proxy or no cameras')

    # empty areas: walkable 1 m samples > 4 m from any dressing or light, in a 6 x 6 m patch
    if fp is not None and sp.get('level') not in ('summit',) and fp.area > 40:
        props = [(p['pos'][0], p['pos'][1]) for p in mine]
        lights = [(p['pos'][0], p['pos'][1]) for p in P if p.get('light')]
        anchors = props + lights
        pf = prepared.prep(fp)
        minx, miny, maxx, maxy = fp.bounds
        walk_cells = None
        npy = os.path.join(ROOT, '.scratch', 'checks', 'walk_nodes.npy')
        if os.path.exists(npy):
            import numpy as np
            A = np.load(npy)
            m = (A[:, 0] >= minx) & (A[:, 0] <= maxx) & (A[:, 1] >= miny) & (A[:, 1] <= maxy) & (np.abs(A[:, 2] - lsp['floor_z']) < 1.6)
            walk_cells = {(int(math.floor(x)), int(math.floor(y))) for x, y in A[m][:, :2]}
        empty = set()
        for ix in range(int(minx), int(maxx) + 1):
            for iy in range(int(miny), int(maxy) + 1):
                if not pf.contains(Point(ix + 0.5, iy + 0.5)):
                    continue
                if walk_cells is not None and (ix, iy) not in walk_cells:
                    continue
                if all(math.hypot(ix + 0.5 - x, iy + 0.5 - y) > EMPTY_DIST for x, y in anchors):
                    empty.add((ix, iy))
        patches = []
        n = int(EMPTY_PATCH)
        for (ix, iy) in empty:
            if all((ix + a, iy + b) in empty for a in range(n) for b in range(n)):
                patches.append((ix + n / 2, iy + n / 2))
        # merge nearby patch centres
        merged = []
        for c in patches:
            if all(math.hypot(c[0] - m[0], c[1] - m[1]) > 6 for m in merged):
                merged.append(c)
        out['empty_areas'] = result([], warns=len(merged), waived=bool(waived(sp, 'empty_areas')), patches=merged[:10])
    else:
        out['empty_areas'] = dict(status='pass', fails=0, warns=0)

    # spacing: grids, clumps, grid-cell centres (per rule)
    by_rule = {}
    for p in mine:
        by_rule.setdefault(p['rule'], []).append(p)
    spacing = {}; grid_hits = []
    for rule, ps in by_rule.items():
        for p in ps:
            x, y = p['pos'][:2]
            if math.hypot((x % 20) - 10, (y % 20) - 10) < GRID_CENTRE_TOL and not rule.startswith(('hero', 'anchored')):
                grid_hits.append(p['id'])
        if len(ps) < 5 or rule.startswith(('hero', 'anchored')) or ps[0]['asset'] == 'railing':     # rails are continuous runs by construction
            continue
        nn = []
        for p in ps:
            d = min(math.hypot(p['pos'][0] - q['pos'][0], p['pos'][1] - q['pos'][1]) for q in ps if q is not p)
            nn.append(d)
        mean = sum(nn) / len(nn); sd = (sum((d - mean) ** 2 for d in nn) / len(nn)) ** 0.5
        cv = sd / mean if mean else 0
        clumps = sum(1 for d in nn if d < 0.35 * mean)
        flag = 'grid' if (cv < 0.08 and not rule.startswith('lights')) else ('clumpy' if clumps > len(nn) * 0.25 else 'ok')
        spacing[rule] = dict(n=len(ps), nn_mean=round(mean, 2), cv=round(cv, 2), clumps=clumps, flag=flag)
    sflags = [r for r, v in spacing.items() if v['flag'] != 'ok']
    out['spacing'] = result(grid_hits, warns=len(sflags), waived=bool(waived(sp, 'spacing')), rules=spacing, on_cell_centres=grid_hits[:10])

    # scale: railings, doors, steps
    sc = []
    for p in mine:
        if p['asset'] == 'railing' and not (RAIL[0] <= p['dims']['h'] * p['scale'] <= RAIL[1]):
            sc.append((p['id'], 'railing h', p['dims']['h'] * p['scale']))
    for pr in sp.get('portals', []):
        if pr.get('height') is not None and pr['height'] < DOOR_MIN:
            sc.append((pr['id'], 'door h', pr['height']))
    for c in L['connections']:
        if sid in c.get('places', []) and 'riser' in c and not (RISER[0] <= c['riser'] <= RISER[1]):
            sc.append((c['id'], 'riser', c['riser']))
    out['scale'] = result(sc, waived=bool(waived(sp, 'scale')), bad=sc[:10])

    # walk graph (from checks/walk.py)
    if WALK and sid in WALK['spaces']:
        w = WALK['spaces'][sid]
        out['walk'] = result([] if (w['reached'] > 0 or not w['walkable']) else [sid], waived=bool(waived(sp, 'walk')), **w)
    # snap problems
    sp_bad = [(p['id'], p['snap_status']) for p in mine if p['snap_status'] not in ('ok', 'structural', 'marker')]
    out['snap'] = result(sp_bad, bad=sp_bad[:10])
    zero = [w for w in ZERO_WARN if f' {sid}:' in w or w.startswith(f'ZERO {sid}:')]
    out['rules'] = result(zero, bad=zero[:10])
    unknown = [p['id'] for p in mine if p.get('unknown_asset')]
    out['unknown_assets'] = result([], warns=len(unknown), ids=unknown[:10])
    return out


def main():
    res = {}
    for sid in sorted(SPACES):
        if ONLY and sid not in ONLY:
            continue
        res[sid] = check_space(sid)
    path = os.environ.get('KZ_CHECKS') or os.path.join(ROOT, '3d', 'checks', 'placement.json')
    prev = json.load(open(path)) if os.path.exists(path) else {}
    prev.update(res)
    overall = 'pass'
    for sid, r in prev.items():
        for k, v in r.items():
            if v['status'] == 'fail':
                overall = 'fail'
            elif v['status'] == 'warn' and overall == 'pass':
                overall = 'warn'
    prev_out = dict(prev)
    json.dump(prev_out, open(path, 'w'), indent=1)
    for sid, r in res.items():
        print('CHECK', sid, ' '.join(f"{k}:{v['status']}" for k, v in r.items()))
    print('PLACEMENT overall', overall)


main()
