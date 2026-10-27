"""Export a baked place (tools/export/bake_place.py output) to a web-contract place package.

    blender -b -P tools/export/export_place.py -- --bake 3d/bake/<space>/<tier> [--no-node]

Blender side (this file) dumps, into <bake>/dump/:
  parts/<n>.bin + parts.json   merged render parts: position, normal, uv0, uv1 (lightmap), optional _KZ_FLOW
                               (lava scroll direction in UV0 units per metre), already in three space
                               (X = x, Y = z, Z = -y) and with glTF v (v = 1 - v_blender)
  walk.bin                     kz_walk positions (three space)
  water/<id>.bin               kz_water surfaces + their kz_* properties
  anim/<n>.bin | <n>.glb       kz_anim objects: skinned GLB with clips when 3d/assets/figure_anims.blend exists,
                               otherwise the evaluated static pose as an unbaked part
  sprites.bin, threads.bin     glowworm points / threads (float32 x 8 each, three space)
  place.json                   lights (runtime + baked), fx emitters, cameras, probes, materials, lightmap
Then runs `node tools/export/pack_place.mjs <bake>` (meshopt + quantize GLBs, KTX2 lightmap and probes) which
writes the package <bake>/pkg/place.json + pkg/files/*, merged into the manifests by web/tools/build-mixed.mjs.
"""
import json, math, os, subprocess, sys
import bpy
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'export'))
import kzexport_common as K  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
BAKE = os.path.abspath(argv[argv.index('--bake') + 1])
NO_NODE = '--no-node' in argv
info = json.load(open(os.path.join(BAKE, 'bake.json')))
bpy.ops.wm.open_mainfile(filepath=os.path.join(BAKE, 'baked.blend'))
DUMP = os.path.join(BAKE, 'dump')
for d in ('parts', 'water', 'anim'):
    os.makedirs(os.path.join(DUMP, d), exist_ok=True)
LIB = K.library()
FIG_ANIMS = os.path.join(ROOT, '3d', 'assets', 'figure_anims.blend')


def l2t(a):
    """layout (x, y, z) rows -> three (x, z, -y)"""
    a = np.asarray(a, np.float32).reshape(-1, 3)
    return np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)


def mesh_arrays(me, want_uv1=True):
    me.calc_loop_triangles()
    tris = me.loop_triangles
    nt = len(tris)
    loops = np.zeros(nt * 3, np.int32); tris.foreach_get('loops', loops)
    verts = np.zeros(nt * 3, np.int32); tris.foreach_get('vertices', verts)
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    cn = np.zeros(len(me.loops) * 3, np.float32); me.corner_normals.foreach_get('vector', cn); cn = cn.reshape(-1, 3)
    pos = co[verts]; nor = cn[loops]
    out = {'position': l2t(pos), 'normal': l2t(nor)}

    def uv(name):
        layer = me.uv_layers.get(name)
        if layer is None:
            return None
        u = np.zeros(len(me.loops) * 2, np.float32); layer.data.foreach_get('uv', u); u = u.reshape(-1, 2)[loops]
        u[:, 1] = 1.0 - u[:, 1]
        return u
    uv0 = uv('UVMap') if me.uv_layers.get('UVMap') else (uv(me.uv_layers[0].name) if me.uv_layers else None)
    if uv0 is not None:
        out['uv0'] = uv0
    if want_uv1:
        u1 = uv('kz_lm')
        if u1 is not None:
            out['uv1'] = u1
    # lava flow: per-vertex kz_flow (layout direction) projected into UV0 space per triangle
    fa = me.attributes.get('kz_flow')
    if fa is not None and uv0 is not None and fa.domain == 'POINT' and fa.data_type == 'FLOAT_VECTOR':
        f = np.zeros(len(me.vertices) * 3, np.float32); fa.data.foreach_get('vector', f); f = f.reshape(-1, 3)[verts]
        p = pos.reshape(-1, 3, 3); t = uv0.reshape(-1, 3, 2).copy(); t[:, :, 1] = 1 - t[:, :, 1]
        e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
        d1, d2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
        det = np.where(np.abs(det) < 1e-12, 1e-12, det)
        T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / det[:, None]   # dP/du
        B = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / det[:, None]   # dP/dv
        fl = f.reshape(-1, 3, 3)
        du = np.einsum('tij,tj->ti', fl, T) / np.maximum((T * T).sum(1), 1e-9)[:, None]
        dv = np.einsum('tij,tj->ti', fl, B) / np.maximum((B * B).sum(1), 1e-9)[:, None]
        out['flow'] = np.stack([du.reshape(-1), -dv.reshape(-1)], 1).astype(np.float32)   # glTF v points the other way
    return out


def write_bin(path, arrays):
    meta, off = {}, 0
    with open(path, 'wb') as fh:
        for k, a in arrays.items():
            a = np.ascontiguousarray(a, np.float32)
            fh.write(a.tobytes())
            meta[k] = {'offset': off, 'count': int(a.shape[0]), 'size': int(a.shape[1]) if a.ndim > 1 else 1}
            off += a.nbytes
    return meta


def mat_entry(m):
    if m.name.endswith('~place_standin'):
        # render stand-in (e.g. lava_glass~place_standin on the window panes): the runtime uses the real library material
        return {'id': K.mat_id(m), 'name': m.name, 'params': {}, 'library': True, 'standin': True}
    p = K.mat_params(m)
    mid = K.mat_id(m)
    d = LIB.get(mid)
    return {'id': mid, 'name': m.name, 'params': p, 'library': d is not None}


# ---------------------------------------------------------------- parts
parts, materials = [], {}
pc = bpy.data.collections['kz_parts']
bake_parts = {p['object']: p for p in info['parts']}
for o in sorted(pc.objects, key=lambda x: x.name):
    if o.type != 'MESH' or not o.data.polygons:
        continue
    m = o.data.materials[0] if o.data.materials else None
    bp = bake_parts.get(o.name, {})
    lm = bool(bp.get('lightmap')) and bool(bp.get('lightmap_id') or info.get('lightmap'))
    arr = mesh_arrays(o.data, want_uv1=lm)
    if lm and 'uv1' not in arr:
        lm = False
    name = o.name.replace('part_', '')
    fn = f'parts/{len(parts):03d}.bin'
    attrs = write_bin(os.path.join(DUMP, fn), arr)
    if m is not None:
        materials[m.name] = mat_entry(m)
    parts.append({'name': name, 'file': fn, 'attrs': attrs, 'tris': attrs['position']['count'] // 3,
                  'extras': {'role': bp.get('role', 'prop'), 'material': m.name if m else 'missing',
                             **({'lightmap': bp.get('lightmap_id') or info['lightmap']['id']} if lm else {})}})
print(f'[export] {len(parts)} parts, {sum(p["tris"] for p in parts)} tris, {len(materials)} materials', flush=True)

deps = bpy.context.evaluated_depsgraph_get()


def eval_mesh(o):
    me = bpy.data.meshes.new_from_object(o.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
    me.transform(o.matrix_world)
    return me


# ---------------------------------------------------------------- walk
walk = []
standin_walk = []   # walk patches the place adds over stretches that stay stand-in (kz_standin): xy bounds
wc = bpy.data.collections.get('kz_walk')
for o in K.coll_objects(wc):
    if o.type == 'MESH':
        me = eval_mesh(o); a = mesh_arrays(me, False); walk.append(a['position'])
        if o.get('kz_standin'):
            co = np.array([v.co[:] for v in me.vertices])
            standin_walk.append({'name': o.name, 'bounds': [float(co[:, 0].min()), float(co[:, 1].min()), float(co[:, 0].max()), float(co[:, 1].max())]})
walk_meta = None
if walk:
    walk_meta = write_bin(os.path.join(DUMP, 'walk.bin'), {'position': np.concatenate(walk)})
else:
    print('[export] WARNING: no kz_walk mesh', flush=True)

# ---------------------------------------------------------------- water
def flow_speed(v):
    if isinstance(v, str):
        try:
            d = json.loads(v)
            return float(d.get('speed_mps', d.get('speed', 0.35))) if isinstance(d, dict) else 0.35
        except Exception:
            return 0.35
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return float(np.linalg.norm(np.array(list(v), np.float32)))   # a flow vector: its length


waters = []
wat = bpy.data.collections.get('kz_water')
for o in K.coll_objects(wat):
    if o.type != 'MESH':
        continue
    me = eval_mesh(o); a = mesh_arrays(me, False)
    wid = o.get('kz_water') or o.name
    fn = f'water/{wid}.bin'
    meta = write_bin(os.path.join(DUMP, fn), {'position': a['position'], 'normal': a['normal']})
    co = np.array([o.matrix_world @ v.co for v in o.data.vertices])
    m = o.data.materials[0] if o.data.materials else None
    waters.append({'id': wid, 'file': fn, 'attrs': meta, 'kind': o.get('kz_water_kind', 'still'), 'planar': bool(o.get('kz_planar', False)),
                   'absorption': list(o.get('kz_absorption', [0.75, 0.16, 0.12])), 'flow': flow_speed(o.get('kz_flow', 0)),
                   'z': float(np.median(co[:, 2])), 'bounds': [float(co[:, 0].min()), float(co[:, 1].min()), float(co[:, 0].max()), float(co[:, 1].max())],
                   'bed_z': float(o['kz_bed_z']) if o.get('kz_bed_z') is not None else None, 'material': m.name if m else None})

# ---------------------------------------------------------------- anim
POSE_CLIP = {'floating': 'float_back', 'standing': 'idle_shift', 'sitting': 'sit_bench', 'seiza': 'sit_seiza', 'soaking': 'soak_rim',
             'walking': 'walk_slow', 'lounging': 'sit_lounger'}
_CLIPS = None


def load_clips():
    global _CLIPS
    if _CLIPS is None:
        with bpy.data.libraries.load(FIG_ANIMS, link=False) as (src, dst):
            dst.actions = list(src.actions)
        _CLIPS = {a.name: a for a in dst.actions if a is not None}
    return _CLIPS


anims = []
ac = bpy.data.collections.get('kz_anim')
have_clips = os.path.exists(FIG_ANIMS)
for o in K.coll_objects(ac):
    if o.type != 'MESH':
        continue
    kz_anim = o.get('kz_anim')
    try:
        ka = json.loads(kz_anim) if isinstance(kz_anim, str) else dict(kz_anim or {})
    except Exception:
        ka = {}
    rig = next((m.object for m in o.modifiers if m.type == 'ARMATURE' and m.object), None) \
        or (o.parent if o.parent and o.parent.type == 'ARMATURE' else None) \
        or next((c for c in o.children if c.type == 'ARMATURE'), None)
    if rig is not None and have_clips and ka.get('type') == 'skinned':
        # skinned GLB with the figure's clip from figure_anims.blend (kz_clip, else by pose)
        clips = load_clips()
        want = o.get('kz_clip') or POSE_CLIP.get(str(o.get('kz_pose', ka.get('pose', 'standing'))), 'idle_shift')
        act = clips.get(want) or clips.get('idle_shift') or next(iter(clips.values()))
        # the rig may be parented under the mesh: make the mesh the rig's child for the exporter, keep world matrices
        mw_rig, mw_o = rig.matrix_world.copy(), o.matrix_world.copy()
        rig.parent = None; rig.matrix_world = mw_rig
        o.parent = rig; o.matrix_world = mw_o
        ad = rig.animation_data_create()
        ad.action = act
        if hasattr(ad, 'action_slot') and getattr(act, 'slots', None):
            ad.action_slot = act.slots[0]
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True); rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        fn = f'anim/{len(anims):03d}.glb'
        bpy.ops.export_scene.gltf(filepath=os.path.join(DUMP, fn), export_format='GLB', use_selection=True, export_yup=True,
                                  export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_skins=True, export_extras=False,
                                  export_materials='EXPORT', export_image_format='NONE', export_apply=False, export_morph=False,
                                  export_force_sampling=False)
        anims.append({'name': o.name, 'file': fn, 'kind': 'glb', 'anim': {'type': 'skinned', 'clip': act.name}, 'clips': [act.name],
                      'materials': [s.material.name for s in o.material_slots if s.material]})
        for s in o.material_slots:
            if s.material:
                materials[s.material.name] = mat_entry(s.material)
        continue
    # static pose: one primitive per material slot
    me = eval_mesh(o)
    K.keep_uv0(me)
    me.calc_loop_triangles()
    slots = [s.material for s in o.material_slots]
    full = mesh_arrays(me, False)
    mi = np.zeros(len(me.loop_triangles), np.int32); me.loop_triangles.foreach_get('material_index', mi)
    prims = []
    for idx in sorted(set(mi.tolist())):
        sel = np.repeat(mi == idx, 3)
        sub = {k: v[sel] for k, v in full.items()}
        m = slots[idx] if idx < len(slots) else None
        fn = f'anim/{len(anims):03d}_{idx}.bin'
        prims.append({'file': fn, 'attrs': write_bin(os.path.join(DUMP, fn), sub), 'material': m.name if m else 'missing'})
        if m is not None:
            materials[m.name] = mat_entry(m)
    anims.append({'name': o.name, 'kind': 'static', 'prims': prims, 'anim': ka, 'clips': [],
                  'note': 'static pose (no 3d/assets/figure_anims.blend)' if ka.get('type') == 'skinned' else 'static'})
print(f'[export] {len(anims)} animated objects ({"clips from figure_anims.blend" if have_clips else "static pose"})', flush=True)

# ---------------------------------------------------------------- sprites
sprites = {}
for k in ('sprites', 'threads'):
    f = os.path.join(BAKE, f'{k}.npy')
    if os.path.exists(f):
        a = np.load(f).astype(np.float32)
        if k == 'sprites':
            a[:, 0:3] = l2t(a[:, 0:3])
        else:
            a[:, 0:3] = l2t(a[:, 0:3]); a[:, 3:6] = l2t(a[:, 3:6])
        a.tofile(os.path.join(DUMP, f'{k}.bin'))
        sprites[k] = {'file': f'{k}.bin', 'count': int(a.shape[0]), 'stride': 8}
# glow colour of the sprites: the emissive slot that the glowworm generator used (neon_tube cyan), linear
glow = [0.0, 0.48, 1.0]

# ---------------------------------------------------------------- lights, fx, cameras
lights = []
lc = bpy.data.collections.get('kz_lights')
for o in K.coll_objects(lc):
    if o.type != 'LIGHT':
        continue
    L = o.data
    d = o.matrix_world.to_quaternion() @ __import__('mathutils').Vector((0, 0, -1))
    lights.append({'name': o.name, 'type': L.type.lower(), 'pos': [round(v, 4) for v in o.matrix_world.translation], 'dir': [round(v, 4) for v in d],
                   'watts': L.energy, 'color': [round(c, 4) for c in L.color], 'kelvin': o.get('kz_kelvin'), 'runtime': bool(o.get('kz_runtime', False)),
                   'size': getattr(L, 'size', getattr(L, 'shadow_soft_size', 0.1)),
                   'spot_deg': math.degrees(L.spot_size) if L.type == 'SPOT' else None})
fx = []
fc = bpy.data.collections.get('kz_fx')
for o in K.coll_objects(fc):
    if o.get('kz_fx') is None:
        continue
    params = {(k[3:] if k.startswith('kz_') else k): (v if isinstance(v, (int, float, str, bool)) else list(v) if hasattr(v, '__len__') else str(v)) for k, v in o.items() if k != 'kz_fx'}
    fx.append({'name': o.name, 'kind': str(o['kz_fx']), 'pos': [round(v, 4) for v in o.matrix_world.translation], 'params': params})
cams = {}
cc = bpy.data.collections.get('kz_cameras')
for o in K.coll_objects(cc):
    if o.type != 'CAMERA':
        continue
    from mathutils import Vector
    fwd = o.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    fov_v = math.degrees(2 * math.atan(o.data.sensor_height / 2 / o.data.lens)) if o.data.sensor_fit == 'VERTICAL' else math.degrees(o.data.angle_y)
    p = o.matrix_world.translation
    cams[o.name.replace('cam_', '')] = {'pos': [round(v, 4) for v in p], 'target': [round(v, 4) for v in p + fwd * 10], 'fov_v': round(fov_v, 3)}

place = {
    'space': info['space'], 'tier': info['tier'], 'generated': info['generated'], 'source': info['source'],
    'parts': parts, 'walk': {'file': 'walk.bin', 'attrs': walk_meta} if walk_meta else None, 'water': waters, 'anims': anims,
    'materials': materials, 'lightmap': info.get('lightmap'), 'lightmaps': info.get('lightmaps') or ([info['lightmap']] if info.get('lightmap') else []), 'probes': info.get('probes', []), 'sprites': sprites, 'glow_color': glow,
    'lights': lights, 'fx': fx, 'cameras': cams, 'standin_walk': standin_walk,
}
json.dump(place, open(os.path.join(DUMP, 'place.json'), 'w'), indent=1)
print(f'[export] dump -> {DUMP}', flush=True)
if not NO_NODE:
    r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'export', 'pack_place.mjs'), BAKE], cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f'pack_place.mjs failed ({r.returncode})')
