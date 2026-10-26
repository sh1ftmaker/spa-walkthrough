"""Walk check: can a 1.6 m guest reach every place on foot from the Basalt Gate?

  blender -b 3d/blend/assembled.blend -P checks/walk.py -- [--res 0.25]

Samples the real geometry (shells, stairs, terrain, proxies; not water) in vertical columns on a grid over every
space footprint and stair. A sample is standable if the surface faces up, there is >= 2.0 m of headroom, and it is
not under more than 0.25 m of water. Neighbouring samples connect when the height change is a step (<= 0.19 m per
0.25 m), so walls, proxies and drops cut the graph. Lifts, slide, boat, cable lift are not geometry here, so they
do not count. Writes .scratch/checks/walk.npz and 3d/checks/walk.json (per space: reached / samples).
"""
import bpy, json, math, os, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, '.bpy_deps'))
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from shapely import prepared

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RES = float(argv[argv.index('--res') + 1]) if '--res' in argv else 0.25
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
HEAD = 2.0
STEP = 0.19 * RES / 0.25


def bvh_of(pred):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not pred(o):
            continue
        e = o.evaluated_get(dg); me = e.to_mesh(); M = o.matrix_world; off = len(verts)
        verts += [M @ v.co for v in me.vertices]
        me.calc_loop_triangles()
        polys += [[off + i for i in t.vertices] for t in me.loop_triangles]   # proper triangulation (n-gons with holes)
        e.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None


solid = bvh_of(lambda o: not o.name.startswith('w_') and 'lava' not in [c.name for c in o.users_collection])
water = bvh_of(lambda o: o.name.startswith('w_'))

# region to sample: every footprint + stair corridor, buffered
geoms = []
for s in L['spaces']:
    if s['footprint']:
        geoms.append(Polygon(s['footprint']).buffer(1.0))
for c in L['connections']:
    if c['kind'] == 'path_stair' or c['kind'] == 'walkway':
        geoms.append(LineString(c['plan']).buffer(c['width'] / 2 + 1.0))
    elif c['kind'] == 'helix':
        geoms.append(Point(c['center']).buffer(c['r_walk'] + c['width'] / 2 + 1.5))
    elif c['kind'] == 'switchback':
        geoms.append(Polygon(c['box']).buffer(1.0))
region = unary_union(geoms); preg = prepared.prep(region)
minx, miny, maxx, maxy = region.bounds
xs = np.arange(math.floor(minx), math.ceil(maxx) + RES, RES)
ys = np.arange(math.floor(miny), math.ceil(maxy) + RES, RES)

nodes = []          # (ix, iy, z)
col_index = {}      # (ix, iy) -> [node ids]
TOP = 135.0
for ix, x in enumerate(xs):
    for iy, y in enumerate(ys):
        if not preg.contains(Point(x, y)):
            continue
        z0 = TOP; above = None; hits = []
        while True:
            loc, nor, idx, dist = solid.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)), 300.0)
            if loc is None:
                break
            hits.append((loc.z, nor.z))
            z0 = loc.z - 0.005
            if len(hits) > 80:
                break
        # walk top-down: a floor is an up-facing hit; headroom = distance to the hit just above it (down-facing ceiling)
        for k, (hz, nz) in enumerate(hits):
            if nz < 0.6:
                continue
            ceil = hits[k - 1][0] if k > 0 else 1e9
            if ceil - hz < HEAD:
                continue
            if water is not None:
                wl, wn, _, _ = water.ray_cast(Vector((x, y, hz + 0.001)), Vector((0, 0, 1)), 3.0)
                if wl is not None and wl.z - hz > 0.25:
                    continue
            col_index.setdefault((ix, iy), []).append(len(nodes)); nodes.append((ix, iy, hz))

N = len(nodes)
parent = list(range(N))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb
for i, (ix, iy, z) in enumerate(nodes):
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        lim = STEP * (1.42 if dx and dy else 1.0)
        for j in col_index.get((ix + dx, iy + dy), []):
            if abs(nodes[j][2] - z) <= lim:
                union(i, j)

def nearest_node(x, y, z):
    best, bd = None, 1e9
    for i, (ix, iy, nz) in enumerate(nodes):
        d = (xs[ix] - x) ** 2 + (ys[iy] - y) ** 2 + (nz - z) ** 2 * 4
        if d < bd:
            best, bd = i, d
    return best

start = nearest_node(24.0, 51.0, 0.0)
root = find(start)
reached = np.array([find(i) == root for i in range(N)])

report = {}
for s in L['spaces']:
    if not s['footprint']:
        continue
    poly = prepared.prep(Polygon(s['footprint']))
    tot = rch = 0
    for i, (ix, iy, z) in enumerate(nodes):
        if abs(z - s['floor_z']) < 3.5 and poly.contains(Point(xs[ix], ys[iy])):
            tot += 1; rch += int(reached[i])
    report[s['id']] = dict(samples=tot, reached=rch, walkable=s.get('walkable', True))
fails = [k for k, v in report.items() if v['walkable'] and v['reached'] == 0]
os.makedirs(os.path.join(ROOT, '.scratch', 'checks'), exist_ok=True)
os.makedirs(os.path.join(ROOT, '3d', 'checks'), exist_ok=True)
arr = np.array([(xs[ix], ys[iy], z, r) for (ix, iy, z), r in zip(nodes, reached)], dtype=np.float32)
np.save(os.path.join(ROOT, '.scratch', 'checks', 'walk_nodes.npy'), arr)
json.dump(dict(result='pass' if not fails else 'fail', start=[24, 51, 0], res=RES, unreached=fails, spaces=report),
          open(os.path.join(ROOT, '3d', 'checks', 'walk.json'), 'w'), indent=1)
print('WALK', 'pass' if not fails else 'fail', 'nodes', N, 'reached', int(reached.sum()), 'unreached spaces:', fails)
