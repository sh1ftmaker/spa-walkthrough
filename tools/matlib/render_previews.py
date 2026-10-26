"""Preview renders: a sphere + a flat swatch per library material under one fixed rig.

    /home/agent-tom/.local/bin/blender -b -P tools/matlib/render_previews.py [-- --only id,id --samples 256]

Rig (identical for every material): one amber 2700 K point lantern, one dim teal area fill,
near-black world, dark floor.  Cycles + OptiX, AgX.  Materials come in through
matlib.assign(), so this also tests the asset-side helper.  Transparent materials get a pale
stone tile under them so absorption colour can be read; washi_backlit gets a lamp inside
the sphere and behind the swatch (that is what "back-lit" means).
Output: 3d/renders/materials/<id>.jpg (800x520), plus variants listed in VARIANTS.
"""
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import matlib  # noqa: E402
from kzdsl import blackbody_rgb  # noqa: E402

ROOT = matlib.ROOT
OUT = os.path.join(ROOT, '3d', 'renders', 'materials')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
SAMPLES = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 256
VARIANTS = [('neon_tube', 'cyan', {}), ('basalt_dry', None, dict(wetness=1.0)),
            ('hinoki', None, dict(wear=0.7))]
LANTERN = blackbody_rgb(2700)
SPHERE_C = Vector((-0.62, 0.0, 0.52))
SWATCH_C = Vector((0.66, 0.12, 0.47))


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    c = sc.cycles
    c.device = 'GPU'
    c.samples = SAMPLES
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.01
    c.use_denoising = True
    c.denoiser = 'OPTIX'
    c.max_bounces = 16
    c.transmission_bounces = 16
    c.transparent_max_bounces = 16
    c.volume_bounces = 2
    c.glossy_bounces = 6
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.5
    c.sample_clamp_indirect = 8.0
    sc.render.resolution_x, sc.render.resolution_y = 800, 520
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 90
    w = bpy.data.worlds.new('PV_World')
    w.color = (0.0, 0.0, 0.0)
    bg = w.node_tree.nodes.get('Background') if w.node_tree else None
    if bg:
        bg.inputs['Color'].default_value = (0, 0, 0, 1)
        bg.inputs['Strength'].default_value = 0.0
    sc.world = w
    return sc


def simple_mat(name, color, rough, checker=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF') or nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Roughness'].default_value = rough
    if checker:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        ck = nt.nodes.new('ShaderNodeTexChecker')
        ck.inputs['Scale'].default_value = checker[0]
        ck.inputs['Color1'].default_value = tuple(color) + (1,)
        ck.inputs['Color2'].default_value = tuple(checker[1]) + (1,)
        nt.links.new(tc.outputs['Object'], ck.inputs['Vector'])
        nt.links.new(ck.outputs['Color'], p.inputs['Base Color'])
    else:
        p.inputs['Base Color'].default_value = tuple(color) + (1,)
    return m


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_sphere(r=0.5):
    me = bpy.data.meshes.new('PV_Sphere')
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=128, v_segments=64, radius=r)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        f.smooth = True
        us = []
        for lp in f.loops:
            co = lp.vert.co
            u = math.atan2(co.x, -co.y) / (2 * math.pi) + 0.5      # seam faces away (+Y)
            v = math.acos(max(-1.0, min(1.0, -co.z / r))) / math.pi
            us.append([u, v])
        if max(a[0] for a in us) - min(a[0] for a in us) > 0.5:
            for a in us:
                if a[0] < 0.5:
                    a[0] += 1.0
        for lp, (u, v) in zip(f.loops, us):
            lp[uv].uv = (u * 2 * math.pi * r, v * math.pi * r)        # metres
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new('PV_Sphere', me))
    ob.location = SPHERE_C
    return ob


def make_box(name, sx, sy, sz):
    """Box with metric box-projected UVs (1 UV unit = 1 m)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(sz * 0.3, 0.012), segments=3, affect='EDGES')
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        f.smooth = False
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            co = lp.vert.co
            if ax == 2:
                lp[uv].uv = (co.x + sx / 2, co.y + sy / 2)
            elif ax == 1:
                lp[uv].uv = (co.x + sx / 2, co.z + sz / 2)
            else:
                lp[uv].uv = (co.y + sy / 2, co.z + sz / 2)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def build_rig(sc):
    floor = make_box('PV_Floor', 12, 12, 0.02)
    floor.location = (0, 2.0, -0.01)
    floor.data.materials.append(simple_mat('PV_FloorMat', (0.018, 0.017, 0.016), 0.55,
                                           checker=(4.0, (0.026, 0.025, 0.023))))
    sphere = make_sphere()
    sw = make_box('PV_Swatch', 0.9, 0.9, 0.05)
    sw.location = SWATCH_C
    sw.rotation_euler = (math.radians(62), 0, math.radians(-14))
    # pale under-tile for transparent materials (hidden otherwise)
    tile = make_box('PV_PaleTile', 2.9, 1.6, 0.02)
    tile.location = (0.0, 0.25, 0.012)
    tile.data.materials.append(simple_mat('PV_PaleMat', (0.42, 0.40, 0.36), 0.6, checker=(14.0, (0.30, 0.29, 0.26))))
    # lantern key
    kl = bpy.data.lights.new('PV_Lantern', 'POINT')
    kl.color = LANTERN
    kl.energy = 420.0
    kl.shadow_soft_size = 0.09
    k = link(bpy.data.objects.new('PV_Lantern', kl))
    k.location = (-1.55, -1.75, 2.05)
    # dim teal fill
    fl = bpy.data.lights.new('PV_TealFill', 'AREA')
    fl.shape = 'RECTANGLE'
    fl.size, fl.size_y = 1.6, 1.0
    fl.color = (0.18, 0.80, 0.74)
    fl.energy = 70.0
    f = link(bpy.data.objects.new('PV_TealFill', fl))
    f.location = (2.4, -0.9, 1.3)
    f.rotation_euler = (Vector((0, 0, 0.5)) - f.location).to_track_quat('-Z', 'Y').to_euler()
    # back-light lamps (washi_backlit only)
    bl = bpy.data.lights.new('PV_Inner', 'POINT')
    bl.color = LANTERN
    bl.energy = 1.5
    bl.shadow_soft_size = 0.04
    inner = link(bpy.data.objects.new('PV_Inner', bl))
    inner.location = SPHERE_C
    bl2 = bpy.data.lights.new('PV_Behind', 'AREA')
    bl2.color = LANTERN
    bl2.energy = 6.0
    bl2.size = 0.6
    behind = link(bpy.data.objects.new('PV_Behind', bl2))
    behind.rotation_euler = sw.rotation_euler
    behind.location = SWATCH_C + sw.matrix_world.to_3x3() @ Vector((0, 0, -0.25))
    behind.rotation_euler.x += math.pi
    # camera
    cd = bpy.data.cameras.new('PV_Cam')
    cd.lens = 50
    cam = link(bpy.data.objects.new('PV_Cam', cd))
    cam.location = (0.0, -3.55, 1.38)
    cam.rotation_euler = (Vector((0.02, 0, 0.47)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    return dict(sphere=sphere, swatch=sw, tile=tile, inner=inner, behind=behind)


def show(ob, on):
    ob.hide_render = not on


def render_one(sc, rig, mid, out_name, variant=None, params=None):
    info = matlib.manifest()[mid]
    params = params or {}
    for ob in (rig['sphere'], rig['swatch']):
        matlib.assign(ob, mid, variant=variant, **params)
    show(rig['tile'], info['transparent'])
    rig['swatch'].scale.z = 4.0 if info['transparent'] and mid != 'waterfall' else 1.0
    back = mid == 'washi_backlit'
    show(rig['inner'], back)
    show(rig['behind'], back)
    sc.render.filepath = os.path.join(OUT, out_name + '.jpg')
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[preview] {out_name:22s} {time.time() - t:5.1f}s', flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = setup_scene()
    rig = build_rig(sc)
    for mid, info in matlib.manifest().items():
        if ONLY and mid not in ONLY:
            continue
        render_one(sc, rig, mid, mid)
    for mid, var, params in VARIANTS:
        if ONLY and mid not in ONLY:
            continue
        tag = var or '_'.join(f'{k}{v}' for k, v in params.items())
        render_one(sc, rig, mid, f'{mid}__{tag}', variant=var, params=params)
    dup = [ng.name for ng in bpy.data.node_groups if '.0' in ng.name]
    print('[preview] node groups:', len(bpy.data.node_groups), 'duplicates:', dup, flush=True)
    print('[preview] materials:', sorted(m.name for m in bpy.data.materials), flush=True)


main()
