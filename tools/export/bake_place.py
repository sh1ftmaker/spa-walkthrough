"""Bake a place model (3d/PLACE_CONTRACT.md) for the web contract (web/ASSET_CONTRACT.md §5-7).

    blender -b 3d/places/<space>.blend -P tools/export/bake_place.py -- [--tier low|high] [--space <id>]
            [--out 3d/bake/<space>/<tier>] [--samples N] [--probe-samples N] [--no-probes]

Steps:
  1. Evaluate every object in kz_render (modifiers applied, except the one named by kz_preview_modifier),
     pull glowworm points / threads out of the meshes, then merge by library material into parts.
     Parts whose objects carry kz_bake = false (or tiny props < 0.3 m, emissive-only and transparent
     materials) are not lightmapped.
  2. Lightmap UVs (UV1, layer 'kz_lm'): smart project, average island scale, pack into one atlas sized by texel
     density (Low about 4-8 cm, High about 2-3.5 cm, power of two, capped).
  3. Cycles Diffuse bake, Direct + Indirect, Color off, linear HDR, OptiX (view-layer kz_bake = 1 only with
     --kz-bake: it brightened some library materials ~60x), then OIDN denoise in the compositor. EXR (raw and denoised) + raw float32 dump.
  4. Probes: Cycles equirect panoramas (1024 x 512, linear HDR, denoised) at every kz_probes empty. Oriented
     for three's equirectUv (u = 0.5 looks east, u grows clockwise seen from above, row 0 = down).
  5. Saves baked.blend (the merged parts with UV1 + the untouched walk / water / anim / lights / fx / cameras)
     and bake.json for tools/export/export_place.py.
"""
import json, math, os, sys, time
import bpy, bmesh
import numpy as np
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None, flag=False):
    if flag:
        return f'--{name}' in argv
    return argv[argv.index(f'--{name}') + 1] if f'--{name}' in argv else default


TIER = arg('tier', 'low')
SRC = bpy.data.filepath
SPACE = arg('space') or os.path.splitext(os.path.basename(SRC))[0]
OUT = os.path.abspath(arg('out') or os.path.join(ROOT, '3d', 'bake', SPACE, TIER))
os.makedirs(OUT, exist_ok=True)
CFG = {
    'low': dict(texel=0.06, texel_max=0.08, cap=2048, samples=256, probe_samples=96, margin_px=3,
                consolidate=dict(thr=0.3, max_per_id=2, min_faces=800)),
    'high': dict(texel=0.025, texel_max=0.035, cap=2048, samples=512, probe_samples=160, margin_px=3,
                 consolidate=dict(thr=0.15, max_per_id=4, min_faces=300)),
}[TIER]
SAMPLES = int(arg('samples', CFG['samples']))
PROBE_SAMPLES = int(arg('probe-samples', CFG['probe_samples']))
PACK_EFF = 0.62
T0 = time.time()
log = []


def say(*a):
    s = ' '.join(str(x) for x in a)
    log.append(f'{time.time() - T0:7.1f}s {s}')
    print('[bake]', s, flush=True)


sys.path.insert(0, os.path.join(ROOT, 'tools', 'export'))
import kzexport_common as K  # noqa: E402

sc = bpy.context.scene
K.cycles_gpu(sc)
LIB = K.library()

# ---------------------------------------------------------------- 1. evaluate and merge
coll = bpy.data.collections.get('kz_render')
if coll is None:
    raise SystemExit('no kz_render collection: not a place file (PLACE_CONTRACT §3)')
parts_coll = bpy.data.collections.new('kz_parts')
sc.collection.children.link(parts_coll)

lod_coll = bpy.data.collections.get('kz_lod')
src_objs = [o for o in K.coll_objects(coll) + [x for x in K.coll_objects(lod_coll) if x.get('kz_lod_render')]
            if o.type in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT')
            and o.get('kz_role') != 'render_only' and not any(c.name == 'render_only' for c in o.users_collection)]
for o in src_objs:
    pm = o.get('kz_preview_modifier')
    if pm:
        name = str(pm).split(' ')[0]
        for m in o.modifiers:
            if m.name == name:
                m.show_render = m.show_viewport = False
deps = bpy.context.evaluated_depsgraph_get()
points_out, threads_out = [], []
baked_srcs, unbaked_srcs = [], []
src_info = {}
for o in src_objs:
    ev = o.evaluated_get(deps)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=deps)
    me.transform(o.matrix_world)
    if o.matrix_world.determinant() < 0:
        me.flip_normals()
    # glowworm points / threads: loose geometry with the sprite attributes
    if 'kz_sprite' in me.attributes:
        pts, thr = K.extract_sprites(me, o)
        points_out.extend(pts); threads_out.extend(thr)
    K.strip_loose(me)
    if not me.polygons:
        bpy.data.meshes.remove(me); continue
    K.keep_uv0(me)
    t = bpy.data.objects.new(f'src_{o.name}', me)
    parts_coll.objects.link(t)
    dims = o.dimensions
    bake = bool(o.get('kz_bake', True)) and max(dims) >= 0.3
    (baked_srcs if bake else unbaked_srcs).append(t)
    src_info[o.name] = dict(bake=bake, role=o.get('kz_role'), asset=o.get('kz_asset'))
say(f'{len(src_objs)} render objects -> {len(baked_srcs)} baked, {len(unbaked_srcs)} unbaked; {len(points_out)} sprite points, {len(threads_out)} threads')

# ---- material consolidation (draw calls): fold near-identical and tiny variants of one kz_id into a representative
faces_by_mat = {}
for t in baked_srcs + unbaked_srcs:
    me = t.data
    idx = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', idx)
    for i, m in enumerate(me.materials):
        if m is not None:
            faces_by_mat[m.name] = faces_by_mat.get(m.name, 0) + int((idx == i).sum())
remap = K.consolidate_materials([bpy.data.materials[n] for n in faces_by_mat], faces_by_mat, **CFG['consolidate'])
for t in baked_srcs + unbaked_srcs:
    for i, m in enumerate(t.data.materials):
        if m is not None and remap.get(m.name, m.name) != m.name:
            t.data.materials[i] = bpy.data.materials[remap[m.name]]
n_after = len(set(remap.get(n, n) for n in faces_by_mat))
say(f'materials: {len(faces_by_mat)} used -> {n_after} after consolidation')

# role per material: dominant kz_role of the objects that use it (used for extras.kz.role)
role_votes = {}
for o in src_objs:
    if o.type != 'MESH':
        continue
    for s in o.material_slots:
        if s.material:
            role_votes.setdefault(s.material.name, {}).setdefault(o.get('kz_role', 'prop'), 0)
            role_votes[s.material.name][o.get('kz_role', 'prop')] += len(o.data.polygons)


def merge_split(objs, tag):
    if not objs:
        return []
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT'); j.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')
    out = [o for o in parts_coll.objects if o.select_get()]
    res = []
    for o in out:
        mat = o.data.materials[o.data.polygons[0].material_index] if o.data.polygons and o.data.materials else None
        # drop unused slots
        if mat is not None:
            o.data.materials.clear(); o.data.materials.append(mat)
            for p in o.data.polygons:
                p.material_index = 0
        res.append(o)
    # one part per material (two slots may hold the same material)
    by = {}
    for o in res:
        by.setdefault(o.data.materials[0].name if o.data.materials else None, []).append(o)
    final = []
    for mname, os_ in by.items():
        if len(os_) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for o in os_:
                o.select_set(True)
            bpy.context.view_layer.objects.active = os_[0]
            bpy.ops.object.join()
            o = bpy.context.view_layer.objects.active
            o.data.materials.clear(); o.data.materials.append(bpy.data.materials[mname])
            for p in o.data.polygons:
                p.material_index = 0
        else:
            o = os_[0]
        o.name = f'part_{tag}_{mname or "none"}'
        final.append(o)
    return final


baked_parts = merge_split(baked_srcs, 'lm')
unbaked_parts = merge_split(unbaked_srcs, 'nolm')
# materials that should not take a lightmap
for o in list(baked_parts):
    m = o.data.materials[0] if o.data.materials else None
    if m is None or K.nobake_material(m, LIB):
        baked_parts.remove(o); unbaked_parts.append(o)
        o.name = o.name.replace('part_lm_', 'part_nolm_')
say(f'parts: {len(baked_parts)} lightmapped, {len(unbaked_parts)} not')

# ---------------------------------------------------------------- 2 + 3. lightmap atlases: UVs and bake
for name in ('kz_render', 'kz_water', 'kz_anim', 'kz_walk', 'kz_lod', 'kz_fx', 'kz_probes', 'kz_cameras'):
    c = bpy.data.collections.get(name)
    if c:
        c.hide_render = True
area = sum(p.area for o in baked_parts for p in o.data.polygons)


def atlas_size(a, texel, texel_max):
    need = math.sqrt(a / PACK_EFF)
    size = 256
    while size < CFG['cap'] and need / size > texel_max:
        size *= 2
    while size < CFG['cap'] and need / size > texel * 1.25:
        size *= 2
    return size, need / size


def split_by_height(objs, z_split):
    """Separate each part into faces below / above z_split (face centroid). Returns (lower, upper)."""
    lower, upper = [], []
    for o in objs:
        me = o.data
        zs = np.zeros(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('center', zs)
        up = zs.reshape(-1, 3)[:, 2] > z_split
        if not up.any():
            lower.append(o); continue
        if up.all():
            upper.append(o); continue
        bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
        for p, u in zip(me.polygons, up):
            p.select = bool(u)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        new = [x for x in parts_coll.objects if x.select_get() and x is not o]
        lower.append(o); upper.extend(new)
    return lower, upper


# One atlas normally. When the cap would leave walk-level surfaces coarser than texel_max (big halls), split at
# floor + 3.5 m: walk-level surfaces get their own atlas at the target density, the rock mass above a coarser one.
size0, texel0 = atlas_size(area, CFG['texel'], CFG['texel_max'])
groups = [(f'lm_{SPACE}', baked_parts, CFG['texel'], CFG['texel_max'])]
if baked_parts and texel0 > CFG['texel_max'] and not arg('one-atlas', flag=True):
    L_ = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
    fz = next((x['floor_z'] for x in L_['spaces'] if x['id'] == SPACE), None)
    if fz is not None:
        lo, up = split_by_height(baked_parts, fz + 3.5)
        groups = [(f'lm_{SPACE}', lo, CFG['texel'], CFG['texel_max']), (f'lm_{SPACE}_upper', up, CFG['texel'] * 2, CFG['texel_max'] * 2.5)]
        say(f'lightmap: {area:.0f} m2 would be {texel0 * 100:.1f} cm/texel in one atlas: split at z {fz + 3.5:.1f} into walk-level ({len(lo)} parts) and upper ({len(up)} parts)')
lm_infos, final_baked = [], []
vl = bpy.context.view_layer
for gi, (lm_id, objs, t_target, t_max) in enumerate(groups):
    objs = [o for o in objs if o.data.polygons]
    if not objs:
        continue
    a = sum(p.area for o in objs for p in o.data.polygons)
    size, texel = atlas_size(a, t_target, t_max)
    say(f'{lm_id}: {a:.0f} m2 -> {size} px atlas, ~{texel * 100:.1f} cm/texel (target {t_target * 100:.1f})')
    for o in objs:
        uv = o.data.uv_layers.get('kz_lm') or o.data.uv_layers.new(name='kz_lm')
        o.data.uv_layers.active = uv
    # join for the unwrap + pack and the bake (Blender writes the bake margin per object: several objects sharing one
    # image overwrote each other's texels), then split by material again
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    J = bpy.context.view_layer.objects.active
    J.data.uv_layers.active = J.data.uv_layers['kz_lm']
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='ADD', margin=CFG['margin_px'] / size, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    me = J.data; uvl = me.uv_layers['kz_lm'].data
    uva, a3 = 0.0, 0.0
    for p in me.polygons:
        u = [uvl[i].uv for i in p.loop_indices]
        for k in range(1, len(u) - 1):
            uva += abs((u[k] - u[0]).cross(u[k + 1] - u[0])) / 2
        a3 += p.area
    texel_meas = math.sqrt(a3 / max(uva, 1e-9)) / size
    say(f'{lm_id} packed: uv coverage {uva * 100:.1f} %, measured {texel_meas * 100:.2f} cm/texel')
    img = bpy.data.images.new(lm_id, size, size, float_buffer=True, alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    mats = {m for m in J.data.materials if m}
    for m in mats:
        nt = m.node_tree
        n = nt.nodes.get('kz_bake_target') or nt.nodes.new('ShaderNodeTexImage'); n.name = 'kz_bake_target'; n.image = img
        for x in nt.nodes:
            x.select = False
        n.select = True; nt.nodes.active = n
    # The library asks for view-layer kz_bake = 1 (geometric normals only) during bakes, but with it set the hinoki deck
    # of b1_mirror baked at E ~ 6 instead of ~ 0.1 (single-object test bake, 2026-10-27). Off until the library fixes it.
    if arg('kz-bake', flag=True):
        vl['kz_bake'] = 1
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = False
    sc.render.bake.use_pass_direct = True; sc.render.bake.use_pass_indirect = True; sc.render.bake.use_pass_color = False
    sc.render.bake.margin = 8; sc.render.bake.margin_type = 'EXTEND'; sc.render.bake.target = 'IMAGE_TEXTURES'
    sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 4; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 4
    bpy.ops.object.select_all(action='DESELECT'); J.select_set(True); bpy.context.view_layer.objects.active = J
    t = time.time()
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'}, use_clear=True, margin=8)
    say(f'{lm_id} bake {size}^2 @ {SAMPLES} spp: {time.time() - t:.1f} s')
    sfx = '' if gi == 0 else f'_{gi}'
    raw = os.path.join(OUT, f'lightmap{sfx}_raw.exr'); K.save_exr(img, raw)
    den = os.path.join(OUT, f'lightmap{sfx}.exr'); K.denoise_exr(raw, den, size, size)
    arr = np.maximum(K.load_exr_rgb(den), 0)   # (h, w, 3), row 0 = bottom
    K.dump_f32(arr, os.path.join(OUT, f'lightmap{sfx}.f32'))
    st = dict(mean=[float(x) for x in arr.reshape(-1, 3).mean(0)], p99=float(np.percentile(arr, 99)), max=float(arr.max()))
    lm_infos.append(dict(id=lm_id, width=size, height=size, texel_m=texel_meas, file=f'lightmap{sfx}.f32', exr=f'lightmap{sfx}.exr', stats=st))
    say(f'{lm_id} stats {st}')
    if 'kz_bake' in vl:
        del vl['kz_bake']
    bpy.ops.object.select_all(action='DESELECT'); J.select_set(True); bpy.context.view_layer.objects.active = J
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in [x for x in parts_coll.objects if x.select_get()]:
        mat = o.data.materials[o.data.polygons[0].material_index]
        o.data.materials.clear(); o.data.materials.append(mat)
        for p in o.data.polygons:
            p.material_index = 0
        o.name = f'part_lm{gi}_{mat.name}'
        o.data.uv_layers.active = o.data.uv_layers['kz_lm']
        o['kz_lightmap_id'] = lm_id
        final_baked.append(o)
for m in bpy.data.materials:
    if m.node_tree and m.node_tree.nodes.get('kz_bake_target'):
        m.node_tree.nodes.remove(m.node_tree.nodes['kz_bake_target'])
baked_parts = final_baked
lm_info = lm_infos[0] if lm_infos else None

# ---------------------------------------------------------------- 4. probes
probes = []
pcoll = bpy.data.collections.get('kz_probes')
if pcoll and not arg('no-probes', flag=True):
    wc = bpy.data.collections.get('kz_water')
    if wc:
        wc.hide_render = False       # reflections see the water
    sc.cycles.samples = PROBE_SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPTIX'
    cd = bpy.data.cameras.new('kz_probe_cam'); cd.type = 'PANO'; cd.panorama_type = 'EQUIRECTANGULAR'
    cd.clip_start = 0.05; cd.clip_end = 1000
    cam = bpy.data.objects.new('kz_probe_cam', cd); sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1024, 512, 100
    sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_depth = '32'
    sc.render.film_transparent = False
    sc.compositing_node_group = None
    lc = bpy.data.collections.get('kz_lights')
    for lo in K.coll_objects(lc):
        # lamps stay visible so wet and glossy surfaces reflect them through the probe; big proxy panels
        # (glowworm field, > 1 m) are not surfaces and stay hidden
        big = lo.type == 'LIGHT' and lo.data.type == 'AREA' and max(lo.data.size, getattr(lo.data, 'size_y', 0) or 0) > 1.0
        lo.visible_camera = not big; lo.visible_glossy = not big
    for e in sorted(pcoll.objects, key=lambda x: x.name):
        cam.location = e.matrix_world.translation
        cam.rotation_euler = (math.pi / 2, 0, -math.pi / 2)   # image centre looks east (+x), see docstring
        f = os.path.join(OUT, f'{e.name}.exr')
        sc.render.filepath = f
        t = time.time()
        bpy.ops.render.render(write_still=True)
        arr = np.maximum(K.load_exr_rgb(f), 0)
        K.dump_f32(arr, os.path.join(OUT, f'{e.name}.f32'))
        c = list(e.matrix_world.translation)
        bmin = list(e.get('kz_box_min', [c[0] - 10, c[1] - 10, c[2] - 3]))
        bmax = list(e.get('kz_box_max', [c[0] + 10, c[1] + 10, c[2] + 8]))
        probes.append(dict(id=e.name, center=[round(v, 3) for v in c], box_min=[float(v) for v in bmin], box_max=[float(v) for v in bmax],
                           file=f'{e.name}.f32', exr=f'{e.name}.exr', width=1024, height=512, projection='equirect',
                           mean=[float(x) for x in arr.reshape(-1, 3).mean(0)]))
        say(f'probe {e.name}: {time.time() - t:.1f} s, mean {probes[-1]["mean"]}')
    if wc:
        wc.hide_render = True

# ---------------------------------------------------------------- 5. save
for o in list(parts_coll.objects):
    if o not in baked_parts and o not in unbaked_parts:
        bpy.data.objects.remove(o)
info = dict(
    space=SPACE, tier=TIER, source=SRC, generated=time.strftime('%Y-%m-%dT%H:%M:%S'), samples=SAMPLES,
    lightmap=lm_info, lightmaps=lm_infos, probes=probes,
    parts=[dict(object=o.name, material=o.data.materials[0].name if o.data.materials else None, lightmap=o in baked_parts,
                lightmap_id=o.get('kz_lightmap_id'),
                role=max(role_votes.get(o.data.materials[0].name, {'prop': 1}).items(), key=lambda kv: kv[1])[0] if o.data.materials else 'prop',
                tris=sum(len(p.vertices) - 2 for p in o.data.polygons)) for o in baked_parts + unbaked_parts],
    sprites=dict(points=len(points_out), threads=len(threads_out)),
    texel_target_m=CFG['texel'], area_m2=area, seconds=round(time.time() - T0, 1), log=log,
)
np.save(os.path.join(OUT, 'sprites.npy'), np.array(points_out, dtype=np.float32).reshape(-1, 8)) if points_out else None
np.save(os.path.join(OUT, 'threads.npy'), np.array(threads_out, dtype=np.float32).reshape(-1, 8)) if threads_out else None
json.dump(info, open(os.path.join(OUT, 'bake.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'baked.blend'), compress=True, copy=True)
say(f'done -> {OUT}')
