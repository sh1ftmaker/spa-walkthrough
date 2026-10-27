"""Generator check sheet: LOD0-3 x 3 variants, triangle counts, proxy-fit problems.

  blender -b -P tools/gen/render_lod_sheet.py -- <asset> [--seeds 1 2 3] [--dims '{"h":1.0}']

Writes 3d/renders/lod/<asset>/sheet.jpg (labelled grid, same warm lantern rig as the material previews),
3d/renders/lod/<asset>/phone-lod2-lod3.jpg (LOD2/LOD3 at phone size at switch distance, shaded + silhouette,
for the recognition test) and 3d/checks/gen/<asset>.json. Saves the built variants to
3d/assets/<asset>.blend (collection per LOD) for the assembly step.
"""
import bpy, json, math, os, sys
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'gen'))
argv = sys.argv[sys.argv.index('--') + 1:]
ASSET = argv[0]
SEEDS = [int(x) for x in argv[argv.index('--seeds') + 1:argv.index('--seeds') + 4]] if '--seeds' in argv else [1, 2, 3]
DIMS = json.loads(argv[argv.index('--dims') + 1]) if '--dims' in argv else {}
bpy.ops.wm.read_factory_settings(use_empty=True)
import genlib  # noqa: E402

OUT = os.path.join(ROOT, '3d', 'renders', 'lod', ASSET); os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(ROOT, '3d', 'checks', 'gen'), exist_ok=True)
os.makedirs(os.path.join(ROOT, '3d', 'assets'), exist_ok=True)
sc = bpy.context.scene
budget = genlib.budget_of(ASSET)
p = genlib.proxy(ASSET)
span = max(p['w'], p['d']) * 1.6 + 0.2
row = p['h'] * 1.35 + 0.2
row = max(row, span * len(SEEDS) * (1400 / 1200) / 4)   # frame is exactly 4 rows tall (1200x1400), so the labels line up
grid = {}
report = dict(asset=ASSET, budget=budget, proxy=p, results=[])
for li, lod in enumerate(range(4)):
    coll = bpy.data.collections.new(f'{ASSET}_LOD{lod}'); sc.collection.children.link(coll)
    for si, seed in enumerate(SEEDS):
        o = genlib.build(ASSET, lod=lod, seed=seed, **DIMS)
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
        o.location = (-si * span, 0, -li * row)        # camera looks down -Y, so world +X is screen-left: lay seeds out to -X
        r = genlib.check(o, ASSET, lod, budget)
        report['results'].append(dict(lod=lod, seed=seed, **r))
        grid[(lod, seed)] = (o, r)
json.dump(report, open(os.path.join(ROOT, '3d', 'checks', 'gen', f'{ASSET}.json'), 'w'), indent=1)
# save the asset library blend before adding the rig
for o in list(sc.objects):
    pass
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, '3d', 'assets', f'{ASSET}.blend'), compress=True)

# rig: warm lantern key + dim teal fill, dark floor, AgX, Eevee
sc.render.engine = 'BLENDER_EEVEE'; sc.view_settings.view_transform = 'AgX'
sc.eevee.taa_render_samples = 48
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.018, 1)
cx, cy = -span * (len(SEEDS) - 1) / 2, 0.0
cz = -row * 1.5 + p['h'] / 2
for name, kind, loc, energy, col, size in (('key', 'AREA', (cx - span * 2, cy - span * 3, p['h'] * 2.5 + 1), 900 * span * max(1, span / 0.92), (1.0, 0.72, 0.42), span * 2),
                                           ('fill', 'AREA', (cx + span * 3, cy + span * 2, p['h'] * 1.5 + 1), 150 * span * max(1, span / 0.92), (0.35, 0.8, 0.85), span * 3)):
    l = bpy.data.lights.new(name, kind); l.energy = energy; l.color = col; l.size = size
    lo = bpy.data.objects.new(name, l); sc.collection.objects.link(lo)
    lo.location = (loc[0], abs(loc[1]) + span * 2, cz + p['h'] * 2)   # front is +Y: lights and camera on +Y
    lo.rotation_euler = (Vector((cx, 0, cz)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
# backdrop wall behind the grid
bpy.ops.mesh.primitive_plane_add(size=max(span * len(SEEDS), row * 4) * 3, location=(cx, -max(p['d'], 0.5) * 1.5, cz), rotation=(math.pi / 2, 0, 0))
fl = bpy.context.object
_bg = bpy.data.materials.new('kz_sheet_backdrop'); _bg.use_nodes = True     # flat neutral backdrop (reviewers: rock texture swamped the cells)
_bsdf = _bg.node_tree.nodes.get('Principled BSDF'); _bsdf.inputs['Base Color'].default_value = (0.09, 0.09, 0.095, 1); _bsdf.inputs['Roughness'].default_value = 0.9
fl.data.materials.append(_bg)
cam = bpy.data.cameras.new('c'); co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co)
cam.type = 'ORTHO'; cam.ortho_scale = row * 4                 # portrait: ortho_scale is the frame height
co.location = (cx, 50, cz)                                   # straight front-on, centred on the 4 row bands
co.rotation_euler = (Vector((cx, 0, cz)) - co.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = co
sc.render.resolution_x, sc.render.resolution_y = 1200, 1400
sc.render.image_settings.file_format = 'PNG'
raw = os.path.join(ROOT, '.scratch', f'lod_{ASSET}.png'); sc.render.filepath = raw
bpy.ops.render.render(write_still=True)

# phone-size recognition renders: LOD2 and LOD3 of seed 1 at their switch distance, shaded and silhouette
for o in sc.objects:
    if o.type == 'MESH' and o.get('kz_asset'):
        o.hide_render = True
_m = max(p['w'], p['d'], p['h'])
# switch by screen size on a 390x844 phone (60 deg vertical FOV): LOD2 below ~80 px, LOD3 below ~30 px; capped for indoor halls
_px = lambda n: 844 * _m / (2 * math.tan(math.radians(30)) * n)
switch = {2: min(_px(80), 35.0), 3: min(_px(30), 80.0)}
pcam = bpy.data.cameras.new('pc'); pco = bpy.data.objects.new('pc', pcam); sc.collection.objects.link(pco)
pcam.sensor_fit = 'VERTICAL'; pcam.sensor_height = 24; pcam.lens = 12 / math.tan(math.radians(30))
sc.camera = pco; sc.render.resolution_x, sc.render.resolution_y = 390, 844
phone = []
for lod in (2, 3):
    o, _ = grid[(lod, SEEDS[0])]
    o.hide_render = False
    tgt = Vector((o.location.x, o.location.y, o.location.z + p['h'] * 0.5))      # each LOD row sits at its own z
    pco.location = tgt + Vector((0, switch[lod], 0.0)); pco.location.z = o.location.z + (1.6 if p['h'] < 3 else p['h'] * 0.5)
    pco.rotation_euler = (tgt - pco.location).to_track_quat('-Z', 'Y').to_euler()
    for mode in ('shaded', 'silhouette'):
        if mode == 'silhouette':
            sc.view_settings.view_transform = 'Standard'
            mats = [s.material for s in o.material_slots]
            blk = bpy.data.materials.new('blk'); blk.use_nodes = True
            blk.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0, 0, 0, 1)
            for s in o.material_slots:
                s.link = 'OBJECT'; s.material = blk
            w.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
            fl.hide_render = True
        f = os.path.join(ROOT, '.scratch', f'lodp_{ASSET}_{lod}_{mode}.png'); sc.render.filepath = f
        bpy.ops.render.render(write_still=True); phone.append((lod, mode, f))
        if mode == 'silhouette':
            for s in o.material_slots:
                s.link = 'DATA'
            sc.view_settings.view_transform = 'AgX'
            w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.018, 1)
            fl.hide_render = False
    o.hide_render = True
json.dump(dict(raw=raw, phone=phone, grid=[[l, s, r['tris'], r['problems']] for (l, s), (o, r) in grid.items()],
               switch=switch, seeds=SEEDS), open(os.path.join(ROOT, '.scratch', f'lod_{ASSET}.json'), 'w'))
print('LODSHEET', ASSET, 'problems:', sum(len(r['problems']) for _, r in grid.values()))
