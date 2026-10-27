"""Shared helpers for Kazan-yu asset generators (run inside Blender).

Every generator is a module tools/gen/gen_<asset>.py exposing

    ASSET = 'lantern_floor'
    FEATURES = ['box body', 'pyramidal cap', 'glowing washi panel', 'short legs']   # kept at every LOD
    def build(lod: int, seed: int, **dims) -> bpy.types.Object

`build` returns ONE mesh object (pivot at base centre, +Y forward, metres) with library materials assigned
(tools/matlib/matlib.py), UV0 in metres, and UV1 for lightmaps (call genlib.finish(obj)). Dimensions default
to the proxy in 3d/assets.json and must stay inside it (checked). LODs keep the silhouette and the
identifying features; they drop segments / bevels / small parts, never blind-decimate.

    import genlib
    obj = genlib.build('lantern_floor', lod=0, seed=3)
"""
import bmesh, bpy, importlib, json, math, os, random, sys
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'matlib'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matlib  # noqa: E402

ASSETS = json.load(open(os.path.join(ROOT, '3d', 'assets.json')))['assets']
LOD_RATIO = {0: 1.0, 1: 0.40, 2: 0.12}          # of LOD0; LOD3 is absolute (a few hundred max)


def proxy(asset):
    a = ASSETS.get(asset, {})
    return dict(w=a.get('w', 1), d=a.get('d', 1), h=a.get('h', 1))


def rng(seed, salt=''):
    return random.Random(f'{seed}:{salt}')


# ---------------------------------------------------------------- mesh building
class MeshBuilder:
    """Collects parts into one bmesh; each part carries a material slot index."""

    def __init__(self):
        self.bm = bmesh.new()
        self.slots = []                      # [(material_id, params)]

    def slot(self, material_id, **params):
        key = (material_id, json.dumps(params, sort_keys=True))
        for i, s in enumerate(self.slots):
            if (s[0], json.dumps(s[1], sort_keys=True)) == key:
                return i
        self.slots.append((material_id, params))
        return len(self.slots) - 1

    def _tag(self, faces, mi):
        for f in faces:
            f.material_index = mi

    def _mark_old(self):
        """mark every existing face (bevel/subdivide clear BMElem.tag, so use an int layer)"""
        lay = self.bm.faces.layers.int.get('_old') or self.bm.faces.layers.int.new('_old')
        for f in self.bm.faces:
            f[lay] = 1
        return lay

    def _new_faces(self, lay):
        return [f for f in self.bm.faces if f[lay] == 0]

    def box(self, center, size, mi, rot=(0, 0, 0), bevel=0.0, bevel_segs=1):
        lay = self._mark_old()
        r = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = r['verts']
        bmesh.ops.scale(self.bm, vec=size, verts=vs)
        M = Matrix.Translation(center) @ (Matrix.Rotation(rot[2], 4, 'Z') @ Matrix.Rotation(rot[1], 4, 'Y') @ Matrix.Rotation(rot[0], 4, 'X'))
        bmesh.ops.transform(self.bm, matrix=M, verts=vs)
        faces = list({f for v in vs for f in v.link_faces})
        if bevel > 0:
            edges = list({e for f in faces for e in f.edges})
            bmesh.ops.bevel(self.bm, geom=edges + vs, offset=min(bevel, 0.45 * min(size)), segments=bevel_segs, affect='EDGES', profile=0.5, clamp_overlap=True)
            faces = self._new_faces(lay)          # every face of this box, flat and bevel faces alike
        self._tag(faces, mi)
        return faces

    def cylinder(self, center, radius, depth, mi, segs=12, rot=(0, 0, 0), radius2=None, cap=True):
        r = bmesh.ops.create_cone(self.bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=radius,
                                  radius2=radius if radius2 is None else radius2, depth=depth)
        vs = r['verts']
        M = Matrix.Translation(center) @ (Matrix.Rotation(rot[2], 4, 'Z') @ Matrix.Rotation(rot[1], 4, 'Y') @ Matrix.Rotation(rot[0], 4, 'X'))
        bmesh.ops.transform(self.bm, matrix=M, verts=vs)
        faces = list({f for v in vs for f in v.link_faces})
        self._tag(faces, mi)
        return faces

    def sphere(self, center, radius, mi, segs=12, rings=8, scale=(1, 1, 1)):
        r = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=radius)
        vs = r['verts']
        bmesh.ops.scale(self.bm, vec=scale, verts=vs)
        bmesh.ops.translate(self.bm, vec=center, verts=vs)
        faces = list({f for v in vs for f in v.link_faces})
        self._tag(faces, mi)
        return faces

    def ico(self, center, radius, mi, subdiv=1, scale=(1, 1, 1)):
        r = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=radius)
        vs = r['verts']
        bmesh.ops.scale(self.bm, vec=scale, verts=vs)
        bmesh.ops.translate(self.bm, vec=center, verts=vs)
        faces = list({f for v in vs for f in v.link_faces})
        self._tag(faces, mi)
        return faces, vs

    def poly_prism(self, poly, z0, z1, mi):
        """extrude a 2D polygon (local XY) between z0 and z1"""
        a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
        if a < 0:
            poly = poly[::-1]
        bot = [self.bm.verts.new((x, y, z0)) for x, y in poly]
        top = [self.bm.verts.new((x, y, z1)) for x, y in poly]
        faces = [self.bm.faces.new(bot[::-1]), self.bm.faces.new(top)]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            faces.append(self.bm.faces.new((bot[i], bot[j], top[j], top[i])))
        self._tag(faces, mi)
        return faces

    def to_object(self, name):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name); self.bm.to_mesh(me); self.bm.free()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        for i, (mid, params) in enumerate(self.slots):
            matlib.assign(o, mid, slot=i, **params)
        return o


# ---------------------------------------------------------------- UVs
def uv0_metric(obj):
    """Box-projected UV0 in metres (1 UV unit = 1 m), per face by dominant normal axis."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if ax == 2:
                l[uv].uv = (co.x, co.y)
            elif ax == 1:
                l[uv].uv = (co.x * (1 if n.y < 0 else -1), co.z)
            else:
                l[uv].uv = (co.y * (1 if n.x > 0 else -1), co.z)
    bm.to_mesh(me); bm.free()


def uv1_lightmap(obj, margin=0.02):
    """Non-overlapping UV1 for lightmaps (Smart UV Project, then packed)."""
    me = obj.data
    if not me.polygons:                      # points/edges-only meshes (glowworms) have nothing to unwrap
        return
    if 'UVLight' not in me.uv_layers:
        me.uv_layers.new(name='UVLight')
    me.uv_layers.active = me.uv_layers['UVLight']
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj; obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    me.uv_layers.active = me.uv_layers['UVMap']
    me.uv_layers['UVMap'].active_render = True


def finish(obj, smooth_angle=35):
    """Normals, UV0 (metres), UV1 (lightmap). Call at the end of every build()."""
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    _flat_by_angle(obj, smooth_angle)
    uv0_metric(obj)
    uv1_lightmap(obj)
    return obj


def _flat_by_angle(obj, angle_deg):
    """mark sharp edges above an angle (no modifier needed for export)"""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    lim = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > lim:
            e.smooth = False
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(obj.data); bm.free()


def tris(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]; ys = [v.co.y for v in obj.data.vertices]; zs = [v.co.z for v in obj.data.vertices]
    return dict(w=max(xs) - min(xs), d=max(ys) - min(ys), h=max(zs) - min(zs), zmin=min(zs), cx=(max(xs) + min(xs)) / 2, cy=(max(ys) + min(ys)) / 2)


def check(obj, asset, lod, budget=None, tol=0.05):
    """Proxy fit (within 5 %), pivot at base centre, triangle budget."""
    p = proxy(asset); b = bbox(obj); out = dict(tris=tris(obj), problems=[])
    for k in ('w', 'd', 'h'):
        if b[k] > p[k] * (1 + tol) + 0.01:
            out['problems'].append(f'{k} {b[k]:.2f} > proxy {p[k]:.2f}')
    if abs(b['zmin']) > 0.01:
        out['problems'].append(f'base at z {b["zmin"]:.3f}, not 0')
    if abs(b['cx']) > 0.05 * p['w'] + 0.02 or abs(b['cy']) > 0.05 * p['d'] + 0.02:
        out['problems'].append(f'pivot off centre ({b["cx"]:.2f}, {b["cy"]:.2f})')
    if budget:
        lim = budget[lod] if lod < len(budget) else None
        if lim and out['tris'] > lim * 1.1:
            out['problems'].append(f'{out["tris"]} tris > budget {lim}')
    out['bbox'] = {k: round(v, 3) for k, v in b.items()}
    return out


def budget_of(asset):
    """triangle budget per LOD from inventory.csv ('a/b/c/d')"""
    import csv
    for r in csv.DictReader(open(os.path.join(ROOT, '3d', 'asset_list.csv'))):   # master list first
        if r['id'] == asset:
            try:
                import re
                return [int(re.sub(r'\D', '', x)) for x in r['tri_budget (LOD0/1/2/3)'].split('(')[0].split(':')[-1].split('/')[:4]]
            except ValueError:
                break
    for r in csv.DictReader(open(os.path.join(ROOT, '3d', 'inventory.csv'))):
        if r['id'] == asset:
            try:
                return [int(x) for x in r['tri_budget_lod0-3'].split('/')]
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------- registry
def module(asset):
    return importlib.import_module(f'gen_{asset}')


def build(asset, lod=0, seed=1, **dims):
    m = module(asset)
    o = m.build(lod, seed, **dims)
    o.name = f'{asset}_s{seed}_LOD{lod}'
    o['kz_asset'] = asset; o['kz_lod'] = lod; o['kz_seed'] = seed
    o['kz_features'] = json.dumps(getattr(m, 'FEATURES', []))
    return o
