"""Shared Blender-side helpers for tools/export/bake_place.py and export_place.py."""
import json, os
import bpy, bmesh
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def cycles_gpu(sc):
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    ok = False
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
        ok = ok or d.use
    sc.cycles.device = 'GPU' if ok else 'CPU'
    if not ok:
        print('[kzexport] WARNING: no OptiX device, baking on CPU', flush=True)
    return ok


_LIB = None


def library():
    global _LIB
    if _LIB is None:
        m = json.load(open(os.path.join(ROOT, '3d', 'materials.json')))
        _LIB = {x['id']: x for x in m['materials']}
    return _LIB


def mat_params(m):
    try:
        return json.loads(m.get('kz_params') or '{}')
    except Exception:
        return {}


def mat_id(m):
    return m.get('kz_id') or m.name.split('~')[0].split('.')[0]


def nobake_material(m, lib):
    """Emissive-only, transparent and water materials take no lightmap (PLACE_CONTRACT §4 kz_bake)."""
    d = lib.get(mat_id(m))
    if d is None:
        return False
    p = mat_params(m)
    if d.get('water') or d.get('transparent') or mat_id(m) in ('glass_clear', 'lava_glass', 'water_still', 'water_river', 'water_sea', 'waterfall', 'caustics_decal'):
        return True
    if d.get('emissive') and float(p.get('emissive_level', d['params'].get('emissive_level', 1)) or 0) > 0:
        return True
    return False


def _attr(me, name, n):
    a = me.attributes.get(name)
    if a is None or a.domain != 'POINT':
        return np.zeros(n, np.float32)
    v = np.zeros(n, np.float32)
    a.data.foreach_get('value', v)
    return v


def extract_sprites(me, obj):
    """Loose glowworm points and thread edges (world space already applied to me)."""
    n = len(me.vertices)
    co = np.zeros(n * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    used = np.zeros(n, bool)
    for p in me.polygons:
        used[list(p.vertices)] = True
    sprite, size, phase = _attr(me, 'kz_sprite', n), _attr(me, 'kz_size', n), _attr(me, 'kz_phase', n)
    bright, hz, thread = _attr(me, 'kz_bright', n), _attr(me, 'kz_hz', n), _attr(me, 'kz_thread', n)
    pts = []
    for i in np.nonzero((~used) & (sprite > 0))[0]:
        pts.append([*co[i], size[i], phase[i], bright[i], hz[i], sprite[i]])
    edge_face = set()
    for p in me.polygons:
        for e in p.edge_keys:
            edge_face.add(e)
    thr = []
    for e in me.edges:
        a, b = e.vertices
        if (min(a, b), max(a, b)) in edge_face or (a, b) in edge_face:
            continue
        if thread[a] > 0 or thread[b] > 0:
            top, bot = (a, b) if co[a][2] >= co[b][2] else (b, a)
            thr.append([*co[top], *co[bot], max(bright[a], bright[b]), 0.0])
    return pts, thr


def strip_loose(me):
    bm = bmesh.new(); bm.from_mesh(me)
    wire = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=wire, context='EDGES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(me); bm.free()


def keep_uv0(me):
    uvs = list(me.uv_layers)
    for u in uvs[1:]:
        me.uv_layers.remove(u)
    if me.uv_layers:
        me.uv_layers[0].name = 'UVMap'


def save_exr(img, path):
    img.filepath_raw = path
    img.file_format = 'OPEN_EXR'
    img.save()


def denoise_exr(src, dst, w, h):
    """OIDN (compositor Denoise node, HDR) on an EXR, written to dst."""
    sc = bpy.data.scenes.new('kz_denoise')
    cam = bpy.data.objects.new('kz_dn_cam', bpy.data.cameras.new('kz_dn_cam'))
    sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_depth = '32'
    sc.render.filepath = dst
    img = bpy.data.images.load(src, check_existing=False)
    ng = bpy.data.node_groups.new('kz_denoise', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    ni = ng.nodes.new('CompositorNodeImage'); ni.image = img
    dn = ng.nodes.new('CompositorNodeDenoise')
    if 'HDR' in dn.inputs:
        dn.inputs['HDR'].default_value = True
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(ni.outputs['Image'], dn.inputs['Image']); ng.links.new(dn.outputs['Image'], out.inputs[0])
    sc.compositing_node_group = ng
    bpy.ops.render.render(write_still=True, scene=sc.name)
    bpy.data.images.remove(img)
    bpy.data.node_groups.remove(ng)
    bpy.data.objects.remove(cam)
    bpy.data.scenes.remove(sc)


def load_exr_rgb(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[:, :, :3].copy()


def dump_f32(arr, path):
    """Raw float32 RGB, rows bottom-first (Blender order), with a JSON sidecar."""
    h, w, _ = arr.shape
    arr.astype(np.float32).tofile(path)
    json.dump({'width': w, 'height': h, 'channels': 3, 'rows': 'bottom-first'}, open(path + '.json', 'w'))


def _pdist(a, b):
    import math
    ta, tb = a.get('tint', [1, 1, 1]), b.get('tint', [1, 1, 1])
    d = 0.5 * max(abs(math.log((x + 0.02) / (y + 0.02))) for x, y in zip(ta, tb))
    d += 0.5 * abs(a.get('wetness', 0) - b.get('wetness', 0)) + 0.5 * abs(a.get('wear', 0) - b.get('wear', 0))
    d += abs(a.get('roughness_offset', 0) - b.get('roughness_offset', 0)) + 0.2 * abs(a.get('normal_strength', 1) - b.get('normal_strength', 1))
    sa, sb = a.get('scale', 1) or 1, b.get('scale', 1) or 1
    d += 0.3 * abs(sa - sb) / max(sa, sb, 1e-3)
    ea, eb = a.get('emissive_level', 0) or 0, b.get('emissive_level', 0) or 0
    d += 99 if (ea > 0) != (eb > 0) else 0.5 * abs(math.log((ea + 0.05) / (eb + 0.05)))
    return d


def consolidate_materials(mats, faces, thr=0.1, max_per_id=4, min_faces=200):
    """Greedy clustering of the library variants of each kz_id (biggest first). Returns {material name: representative name}."""
    by = {}
    for m in mats:
        by.setdefault(mat_id(m), []).append(m)
    out = {}
    for mid, ms in by.items():
        ms.sort(key=lambda m: -faces.get(m.name, 0))
        reps = []
        for m in ms:
            p = mat_params(m)
            best = min(((r, _pdist(p, mat_params(r))) for r in reps), key=lambda x: x[1], default=(None, 1e9))
            if best[0] is not None and (best[1] <= thr or ((len(reps) >= max_per_id or faces.get(m.name, 0) < min_faces) and best[1] < 50)):
                out[m.name] = best[0].name
            else:
                reps.append(m); out[m.name] = m.name
    return out


def select_sparse_islands(obj, uvname, fill_min=0.12, min_faces=8):
    """Edit mode: select only the faces of UV islands whose area fills less than fill_min of their UV bounding box."""
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    uvl = bm.loops.layers.uv[uvname]
    bm.faces.ensure_lookup_table()
    seen = set(); bad = 0
    for f in bm.faces:
        f.select = False
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack = [f0]; isl = []; seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for l in f.loops:
                e = l.edge
                for l2 in e.link_loops:
                    g = l2.face
                    if g.index in seen or g is f:
                        continue
                    # connected in UV: both edge ends coincide
                    a1, b1 = l[uvl].uv, l.link_loop_next[uvl].uv
                    a2, b2 = l2.link_loop_next[uvl].uv, l2[uvl].uv
                    if (a1 - a2).length < 1e-6 and (b1 - b2).length < 1e-6:
                        seen.add(g.index); stack.append(g)
        if len(isl) < min_faces:
            continue
        us = [l[uvl].uv for f in isl for l in f.loops]
        w = max(u.x for u in us) - min(u.x for u in us); h = max(u.y for u in us) - min(u.y for u in us)
        area = 0.0
        for f in isl:
            u = [l[uvl].uv for l in f.loops]
            for k in range(1, len(u) - 1):
                area += abs((u[k] - u[0]).cross(u[k + 1] - u[0])) / 2
        if w * h > 0 and area / (w * h) < fill_min:
            for f in isl:
                f.select = True
            bad += len(isl)
    bmesh.update_edit_mesh(me)
    return bad


def coll_objects(c):
    """Objects of a collection and its children (Collection.all_objects crashed Blender 5.2 on some place files)."""
    if c is None:
        return []
    out, seen = [], set()

    def walk(cc):
        for o in cc.objects:
            if o.name not in seen:
                seen.add(o.name); out.append(o)
        for ch in cc.children:
            walk(ch)
    walk(c)
    return out
