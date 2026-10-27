"""Shared helpers for place models (3d/PLACE_CONTRACT.md). Lead-owned: propose additions, don't edit.

    import sys; sys.path.insert(0, '<root>/tools/place'); import kzplace_common as P
    P.reset()                                   # empty scene, collections, AgX, near-black world
    S = P.space('b1_mirror')                    # 3d/spaces/<id>.json merged with its layout.json entry
    o = P.mesh_object('floor', bm, 'kz_render', role='floor', material='basalt_wet')
    d = P.dress('lantern_post', seed=2, at=(x, y, z), heading=90, lod=0, h=1.2)
    P.cameras(S); P.probe(S['id'], 0, centre, box_min, box_max)
    P.save(S['id'])
"""
import json, math, os, sys
import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
for _p in ('tools/gen', 'tools/matlib'):
    if os.path.join(ROOT, _p) not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, _p))
import matlib  # noqa: E402

COLLS = ('kz_render', 'kz_lod', 'kz_walk', 'kz_water', 'kz_lights', 'kz_probes', 'kz_fx', 'kz_cameras', 'kz_anim')
_L = None


def layout():
    global _L
    if _L is None:
        _L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
    return _L


def space(sid):
    """The space file, with the layout entry under 'layout' and the layout water bodies it touches under 'layout_water'."""
    s = json.load(open(os.path.join(ROOT, '3d', 'spaces', f'{sid}.json')))
    s['layout'] = next(x for x in layout()['spaces'] if x['id'] == sid)
    ids = {w.get('id') for w in s.get('water', [])}
    s['layout_water'] = [w for w in layout()['water'] if w['id'] in ids or sid in json.dumps(w)]
    return s


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for c in COLLS:
        col = bpy.data.collections.new(c); sc.collection.children.link(col)
        if c in ('kz_lod', 'kz_walk'):
            col.hide_render = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0
    w = bpy.data.worlds.new('kz_world'); w.use_nodes = True; sc.world = w
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.018, 1)
    sc.unit_settings.system = 'METRIC'
    return sc


def coll(name):
    return bpy.data.collections[name]


def link(obj, collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll(collection).objects.link(obj)
    return obj


def tag(obj, role=None, material=None, bake=None, **extra):
    if role is not None:
        obj['kz_role'] = role
    if material is not None:
        mid, _, var = material.partition(':')
        matlib.assign(obj, mid, variant=var or None)
        obj['kz_material'] = material
    if bake is not None:
        obj['kz_bake'] = bool(bake)
    for k, v in extra.items():
        obj[k if k.startswith('kz_') else 'kz_' + k] = v
    return obj


def mesh_object(name, bm, collection='kz_render', **tags):
    """bmesh -> object in a contract collection, tagged (role=, material='id[:variant]', bake=)."""
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    coll(collection).objects.link(obj)
    return tag(obj, **tags)


# space-file asset ids that are built by a differently named generator
ALIASES = {'lift_core': 'lift_drum', 'lantern_hanging': 'chochin', 'pine_bonsai': 'pine_niwaki', 'banner': 'banner_hanging',
           'sign_kanji': 'signboard_kanji', 'bench_stone': 'bench'}


def dress(asset, seed=1, at=(0, 0, 0), heading=0.0, lod=0, name=None, collection='kz_render', gen_kw=None, **params):
    """Build a generator asset in place. heading: degrees clockwise from north (+y), like the space files.
    Generator front is +Y, so heading 0 faces north. Space-file ids resolve through ALIASES. Generator
    params go in **params, or in gen_kw={...} when a name collides with this wrapper (e.g. staff_figure role=).
    Child objects (figure armatures) move into the same collection."""
    import genlib
    gen = ALIASES.get(asset, asset)
    params = dict(params, **(gen_kw or {}))
    o = genlib.build(gen, lod=lod, seed=seed, **params)
    o.name = name or f'{asset}.{seed}'
    o.location = at
    o.rotation_euler = (0, 0, -math.radians(heading))
    o['kz_asset'] = gen; o['kz_seed'] = seed; o['kz_params'] = json.dumps(params); o['kz_role'] = o.get('kz_role', 'prop')
    link(o, collection)
    for ch in o.children_recursive:
        link(ch, collection)
    bpy.context.view_layer.update()          # matrix_world is stale until the depsgraph updates
    return o


def cameras(S, extra=None):
    out = {}
    for k, c in dict(S.get('cameras') or {}, **(extra or {})).items():
        if not isinstance(c, dict) or 'pos' not in c:
            continue
        cam = bpy.data.cameras.new(f'cam_{k}'); cam.sensor_fit = 'VERTICAL'; cam.sensor_height = 24
        cam.lens = 12 / math.tan(math.radians(c.get('fov_v', 60) / 2)); cam.clip_start = 0.05; cam.clip_end = 500
        o = bpy.data.objects.new(f'cam_{k}', cam); coll('kz_cameras').objects.link(o)
        from mathutils import Vector
        o.location = c['pos']
        o.rotation_euler = (Vector(c['target']) - Vector(c['pos'])).to_track_quat('-Z', 'Y').to_euler()
        out[k] = o
    return out


def probe(sid, n, centre, box_min, box_max):
    e = bpy.data.objects.new(f'probe_{sid}_{n}', None); e.location = centre
    e['kz_box_min'] = list(box_min); e['kz_box_max'] = list(box_max)
    coll('kz_probes').objects.link(e)
    return e


def fx(name, kind, at, **params):
    e = bpy.data.objects.new(name, None); e.location = at; e['kz_fx'] = kind
    for k, v in params.items():
        e[k] = v
    coll('kz_fx').objects.link(e)
    return e


def light(name, kind, at, energy, kelvin=2700, size=0.2, runtime=False, rot=None, **kw):
    l = bpy.data.lights.new(name, kind); l.energy = energy; l.color = kelvin_rgb(kelvin)
    if hasattr(l, 'shadow_soft_size'):
        l.shadow_soft_size = size
    if kind == 'AREA':
        l.size = size
    for k, v in kw.items():
        setattr(l, k, v)
    o = bpy.data.objects.new(name, l); o.location = at
    if rot:
        o.rotation_euler = rot
    o['kz_runtime'] = bool(runtime); o['kz_kelvin'] = kelvin
    coll('kz_lights').objects.link(o)
    return o


def kelvin_rgb(k):
    t = k / 100.0
    r = 255 if t <= 66 else 329.7 * ((t - 60) ** -0.1332)
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * ((t - 60) ** -0.0755)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    return tuple(max(0, min(255, c)) / 255 for c in (r, g, b))


def save(sid):
    os.makedirs(os.path.join(ROOT, '3d', 'places'), exist_ok=True)
    p = os.path.join(ROOT, '3d', 'places', f'{sid}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
    return p
