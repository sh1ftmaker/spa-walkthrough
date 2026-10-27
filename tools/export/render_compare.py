"""Cycles reference render for the colour match (web/ASSET_CONTRACT.md §10): same camera as tools/shot.mjs.

    blender -b <place.blend> -P tools/export/render_compare.py -- --out <file.png> [--cam concept | --pos x,y,z --target x,y,z --fov 58]
            [--size 1280x720] [--samples 128] [--albedo 0.18]

AgX, Look None, exposure 0 (the place file's own settings are forced to these). The fov is vertical, like the
space-file cameras and __kz.setCamera. Walk / LOD / probe / fx collections are hidden; water and anim are shown.
"""
import math, os, sys
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import kzexport_common as K  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
a = lambda k, d=None: argv[argv.index(f'--{k}') + 1] if f'--{k}' in argv else d
sc = bpy.context.scene
K.cycles_gpu(sc)
W, H = (int(v) for v in a('size', '1280x720').split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.cycles.samples = int(a('samples', 128)); sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0; sc.view_settings.gamma = 1
sc.display_settings.display_device = 'sRGB'
for n in ('kz_walk', 'kz_lod', 'kz_probes', 'kz_fx'):
    c = bpy.data.collections.get(n)
    if c:
        c.hide_render = True
if a('pos'):
    pos = Vector([float(v) for v in a('pos').split(',')]); tgt = Vector([float(v) for v in a('target').split(',')]); fov = float(a('fov', 60))
else:
    cam = bpy.data.objects.get(f'cam_{a("cam", "concept")}')
    pos = cam.matrix_world.translation.copy(); tgt = pos + cam.matrix_world.to_quaternion() @ Vector((0, 0, -10))
    fov = math.degrees(2 * math.atan(cam.data.sensor_height / 2 / cam.data.lens))
cd = bpy.data.cameras.new('kz_compare'); cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 24
cd.lens = 12 / math.tan(math.radians(fov) / 2); cd.clip_start = 0.05; cd.clip_end = 1000
co = bpy.data.objects.new('kz_compare', cd); sc.collection.objects.link(co)
co.location = pos; co.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
sc.camera = co
if a('kzbake'):
    bpy.context.view_layer['kz_bake'] = 1
if a('albedo'):
    g = float(a('albedo'))
    mo = bpy.data.materials.new('kz_grey'); mo.use_nodes = True
    bsdf = mo.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (g, g, g, 1); bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
    bpy.context.view_layer.material_override = mo   # emissive meshes lose their emission: compare where lamps dominate
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.abspath(a('out'))
bpy.ops.render.render(write_still=True)
print('[compare] wrote', sc.render.filepath, 'pos', list(pos), 'fov', fov)
