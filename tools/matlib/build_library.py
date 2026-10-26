"""Build the Kazan-yu material library from scratch.

    /home/agent-tom/.local/bin/blender -b -P tools/matlib/build_library.py [-- --only id,id --skip-bake]

Writes
    3d/materials/library.blend          materials + shared node groups (+ packed tiling images)
    .scratch/matlib/tex/<id>_*.png      tiling texture sources (build intermediates)
    3d/materials.json                   manifest for the web app
Then run tools/matlib/encode_ktx2.py (KTX2), tools/matlib/render_previews.py and
tools/matlib/contact_sheet.py.  See 3d/materials/README.md.

Structure of every material  <id>:
    [Material Output] <- group node "KZ" = KZM_<id>   (inputs: the 7 artist settings)
    KZM_<id>:  UV -> KZ_Tile(scale) -> KZP_<id> (procedural pattern)  -> KZ_Core -> shader/volume
          or   UV -> KZ_Tile(scale) -> baked tiling images (mode 'image') -> KZ_Core
    KZ_Core is shared by all materials and applies tint / wetness / wear / roughness_offset /
    normal_strength / emissive_level with formulas the web shader repeats (see materials.json).
"""
import datetime
import json
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kzdsl  # noqa: E402
import kzimg  # noqa: E402
import library_defs as L  # noqa: E402
from kzdsl import B, S  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_BLEND = os.path.join(ROOT, '3d', 'materials', 'library.blend')
OUT_JSON = os.path.join(ROOT, '3d', 'materials.json')
TEX_PNG = os.path.join(ROOT, '.scratch', 'matlib', 'tex')
BAKE_TMP = os.path.join(ROOT, '.scratch', 'matlib', 'bake')
TEX_KTX_REL = 'materials/tex'           # relative to 3d/
SETTINGS = ['tint', 'wetness', 'wear', 'roughness_offset', 'scale', 'normal_strength', 'emissive_level']
VERSION = 1

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = None
SKIP_BAKE = '--skip-bake' in argv
if '--only' in argv:
    ONLY = set(argv[argv.index('--only') + 1].split(','))

CORE_DEFAULTS = dict(
    TileSize=1.0, HeightDepth=0.01, HeightGain=1.0, Specular=0.5, IOR=1.5, Transmission=0.0, ThinWall=0.0,
    Coat=0.0, CoatRough=0.05, Sheen=0.0, Translucency=0.0, Porosity=1.0,
    WornColor=(0.5, 0.5, 0.5), WornRough=0.5, WornMetal=0.0, FoamColor=(0.8, 0.85, 0.85),
    EmitStrength=1.0, Absorb=(1.0, 1.0, 1.0), AbsorbDensity=0.0, Scatter=(1.0, 1.0, 1.0), ScatterDensity=0.0)
PATTERN_OUT = [('Albedo', 'c', (0.5, 0.5, 0.5)), ('Roughness', 'f', 0.5), ('Metallic', 'f', 0.0),
               ('Height', 'f', 0.5), ('AO', 'f', 1.0), ('Emission', 'c', (0.0, 0.0, 0.0)),
               ('Foam', 'f', 0.0), ('Alpha', 'f', 1.0)]
PKEY = dict(Albedo='albedo', Roughness='rough', Metallic='metal', Height='height', AO='ao',
            Emission='emission', Foam='foam', Alpha='alpha')


def log(*a):
    print('[matlib]', *a, flush=True)


# ------------------------------------------------------------------ node-group helpers
STYPE = {'f': 'NodeSocketFloat', 'c': 'NodeSocketColor', 'v': 'NodeSocketVector', 's': 'NodeSocketShader'}


def sock(ng, name, io, typ, default=None, mn=None, mx=None, desc=''):
    s = ng.interface.new_socket(name=name, in_out=io, socket_type=STYPE[typ])
    if default is not None and hasattr(s, 'default_value'):
        if typ == 'c' and len(default) == 3:
            default = tuple(default) + (1.0,)
        s.default_value = default
    if mn is not None:
        s.min_value = mn
    if mx is not None:
        s.max_value = mx
    if desc:
        s.description = desc
    return s


def new_group(name):
    old = bpy.data.node_groups.get(name)
    if old:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    return ng


def settings_iface(ng, m=None):
    p = full_params(m) if m else full_params(None)
    sock(ng, 'tint', 'INPUT', 'c', p['tint'], desc='Multiplies albedo, worn colour, emission and absorption colour')
    sock(ng, 'wetness', 'INPUT', 'f', p['wetness'], 0.0, 1.0, 'Water film: darkens porous albedo, roughness -> 0.04 in low areas first')
    sock(ng, 'wear', 'INPUT', 'f', p['wear'], 0.0, 1.0, 'Polish/abrasion of high points towards the material worn colour/roughness/metal')
    sock(ng, 'roughness_offset', 'INPUT', 'f', p['roughness_offset'], -1.0, 1.0, 'Added to roughness')
    sock(ng, 'scale', 'INPUT', 'f', p['scale'], 0.001, 100.0, 'Metres per texture repeat (UVs are in metres)')
    sock(ng, 'normal_strength', 'INPUT', 'f', p['normal_strength'], 0.0, 4.0, 'Detail normal / bump strength')
    sock(ng, 'emissive_level', 'INPUT', 'f', p['emissive_level'], 0.0, 100.0, 'Emission multiplier (0 = off)')


def full_params(m):
    p = dict(tint=(1.0, 1.0, 1.0), wetness=0.0, wear=0.0, roughness_offset=0.0, scale=1.0,
             normal_strength=1.0, emissive_level=0.0)
    if m:
        p['scale'] = m['tile']
        p.update(m.get('params', {}))
        p['tint'] = tuple(p['tint'])
    return p


# ------------------------------------------------------------------ shared groups
def build_tile():
    ng = new_group('KZ_Tile')
    sock(ng, 'UV', 'INPUT', 'v', (0, 0, 0), desc='UV in metres')
    sock(ng, 'scale', 'INPUT', 'f', 1.0, 0.001, 100.0)
    sock(ng, 'Vector', 'OUTPUT', 'v')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    v = b.vmath('DIVIDE', b.out(gi, 'UV'), b.xyz(b.out(gi, 'scale'), b.out(gi, 'scale'), 1.0))
    go = b.node('NodeGroupOutput', {'Vector': v})
    return ng


def build_normal_xy():
    """Tangent normal from the XY of the baked normal_height texture (same decode as the web)."""
    ng = new_group('KZ_NormalXY')
    sock(ng, 'Color', 'INPUT', 'c', (0.5, 0.5, 1.0))
    sock(ng, 'Strength', 'INPUT', 'f', 1.0, 0.0, 10.0)
    sock(ng, 'Normal', 'OUTPUT', 'v')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    r, g, _ = b.rgb_sep(b.out(gi, 'Color'))
    x = r * 2.0 - 1.0
    y = g * 2.0 - 1.0
    z = (1.0 - x * x - y * y).max(0.0).sqrt()
    col = b.rgb(x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5)
    nm = b.node('ShaderNodeNormalMap', {'Strength': b.out(gi, 'Strength'), 'Color': col}, {'space': 'TANGENT'})
    b.node('NodeGroupOutput', {'Normal': b.out(nm, 'Normal')})
    return ng


def build_core():
    ng = new_group('KZ_Core')
    settings_iface(ng)
    # pattern data (from KZP_* procedural patterns or from baked textures)
    sock(ng, 'Albedo', 'INPUT', 'c', (0.5, 0.5, 0.5))
    sock(ng, 'Roughness', 'INPUT', 'f', 0.5, 0.0, 1.0)
    sock(ng, 'Metallic', 'INPUT', 'f', 0.0, 0.0, 1.0)
    sock(ng, 'Height', 'INPUT', 'f', 0.5, 0.0, 1.0)
    sock(ng, 'AO', 'INPUT', 'f', 1.0, 0.0, 1.0)
    sock(ng, 'Emission', 'INPUT', 'c', (0, 0, 0))
    sock(ng, 'Foam', 'INPUT', 'f', 0.0, 0.0, 1.0)
    sock(ng, 'Alpha', 'INPUT', 'f', 1.0, 0.0, 1.0)
    sock(ng, 'NormalIn', 'INPUT', 'v', (0, 0, 1))
    # per-material constants
    for k, v in CORE_DEFAULTS.items():
        sock(ng, k, 'INPUT', 'c' if isinstance(v, tuple) else 'f', v)
    sock(ng, 'Shader', 'OUTPUT', 's')
    sock(ng, 'Volume', 'OUTPUT', 's')

    b = B(ng)
    gi = b.node('NodeGroupInput')
    I = lambda n: b.out(gi, n)  # noqa: E731
    tint = I('tint')
    h = I('Height')
    wear_m = ((h + I('wear') * 1.2 - 1.0) * 4.0).clamp()
    wet_m = (I('wetness') * (1.5 - h)).clamp()
    alb = b.cmul(b.cmul(I('Albedo'), tint), I('AO'))
    alb = b.mixc(wear_m, alb, b.cmul(I('WornColor'), tint))
    alb = b.cmul(alb, 1.0 - I('Porosity') * 0.55 * wet_m)
    alb = b.mixc(I('Foam'), alb, I('FoamColor'))
    rough = b.mixf(wear_m, I('Roughness'), I('WornRough')) + I('roughness_offset')
    rough = b.mixf(wet_m, rough, 0.04)
    rough = b.mixf(I('Foam'), rough, 0.45).max(0.0).min(1.0)
    metal = b.mixf(wear_m, I('Metallic'), I('WornMetal'))
    trans = I('Transmission') * (1.0 - I('Foam'))
    dist = I('HeightDepth') * I('scale') / I('TileSize')
    bump = b.node('ShaderNodeBump', {'Strength': I('normal_strength'), 'Distance': dist,
                                     'Height': h * I('HeightGain'), 'Normal': I('NormalIn')})
    nrm = b.out(bump, 'Normal')
    emis = b.cmul(I('Emission'), tint)
    p = b.node('ShaderNodeBsdfPrincipled', {
        'Base Color': alb, 'Metallic': metal, 'Roughness': rough, 'IOR': I('IOR'), 'Alpha': I('Alpha'),
        'Normal': nrm, 'Specular IOR Level': I('Specular'), 'Transmission Weight': trans,
        'Coat Weight': I('Coat'), 'Coat Roughness': I('CoatRough'), 'Sheen Weight': I('Sheen'),
        'Sheen Roughness': 0.5, 'Emission Color': emis,
        'Emission Strength': I('EmitStrength') * I('emissive_level')})
    tw = p.inputs['Thin Wall']
    if tw.type in ('VALUE', 'BOOLEAN', 'INT'):
        try:
            ng.links.new(I('ThinWall').sock, tw)
        except Exception as e:  # pragma: no cover
            log('thin wall link failed', e)
    tl = b.node('ShaderNodeBsdfTranslucent', {'Color': alb, 'Normal': nrm})
    mix = b.node('ShaderNodeMixShader', {0: I('Translucency'), 1: b.out(p, 0), 2: b.out(tl, 0)})
    ab = b.node('ShaderNodeVolumeAbsorption', {'Color': b.cmul(I('Absorb'), tint), 'Density': I('AbsorbDensity')})
    sc = b.node('ShaderNodeVolumeScatter', {'Color': I('Scatter'), 'Density': I('ScatterDensity')})
    vol = b.node('ShaderNodeAddShader', {0: b.out(ab, 0), 1: b.out(sc, 0)})
    b.node('NodeGroupOutput', {'Shader': b.out(mix, 0), 'Volume': b.out(vol, 0)})
    return ng


# ------------------------------------------------------------------ per-material groups
def build_pattern(m):
    ng = new_group('KZP_' + m['id'])
    sock(ng, 'UV', 'INPUT', 'v', (0, 0, 0), desc='tile space: [0,1) = one repeat')
    for name, typ, d in PATTERN_OUT:
        sock(ng, name, 'OUTPUT', typ, d)
    b = B(ng)
    gi = b.node('NodeGroupInput')
    res = m['pattern'](b, b.out(gi, 'UV'))
    go = b.node('NodeGroupOutput')
    go.location = (max(b.cols) * 220 + 400, 0)
    for name, typ, d in PATTERN_OUT:
        v = res.get(PKEY[name], d)
        b.set_in(go, name, v)
    return ng


def set_inputs(node, values):
    for k, v in values.items():
        s = node.inputs[k]
        if isinstance(v, (tuple, list)):
            v = tuple(v) + ((1.0,) if len(v) == 3 and len(s.default_value) == 4 else ())
        s.default_value = v


def core_consts(m):
    c = dict(CORE_DEFAULTS)
    c.update(m.get('core', {}))
    c['TileSize'] = m['tile']
    c['HeightDepth'] = m['depth']
    c['HeightGain'] = 0.0 if m['mode'] == 'image' else 1.0
    return c


def build_kzm(m, images=None):
    """The per-material wrapper: the 7 settings in, shader + volume out."""
    ng = new_group('KZM_' + m['id'])
    settings_iface(ng, m)
    sock(ng, 'Shader', 'OUTPUT', 's')
    sock(ng, 'Volume', 'OUTPUT', 's')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    I = lambda n: b.out(gi, n)  # noqa: E731
    tc = b.node('ShaderNodeTexCoord')
    geo = b.node('ShaderNodeNewGeometry')
    tile = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_Tile']}, name='Tile')
    b.set_in(tile, 'UV', b.out(tc, 'UV'))
    b.set_in(tile, 'scale', I('scale'))
    vec = b.out(tile, 'Vector')
    core = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_Core']}, name='Core')
    for k in SETTINGS:
        b.set_in(core, k, I(k))
    set_inputs(core, core_consts(m))
    if m['mode'] == 'image':
        tb = b.node('ShaderNodeTexImage', {'Vector': vec}, {'image': images['base'], 'interpolation': 'Linear',
                                                           'extension': 'REPEAT'}, label='base (sRGB)')
        to = b.node('ShaderNodeTexImage', {'Vector': vec}, {'image': images['orm'], 'interpolation': 'Linear',
                                                           'extension': 'REPEAT'}, label='orm + height')
        tn = b.node('ShaderNodeTexImage', {'Vector': vec}, {'image': images['nh'], 'interpolation': 'Linear',
                                                           'extension': 'REPEAT'}, label='normal XY + height')
        ao, ro, me = b.rgb_sep(b.out(to, 'Color'))
        nxy = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_NormalXY']})
        b.set_in(nxy, 'Color', b.out(tn, 'Color'))
        b.set_in(nxy, 'Strength', I('normal_strength'))
        b.set_in(core, 'Albedo', b.out(tb, 'Color'))
        b.set_in(core, 'AO', ao)
        b.set_in(core, 'Roughness', ro)
        b.set_in(core, 'Metallic', me)
        b.set_in(core, 'Height', b.out(to, 'Alpha'))
        b.set_in(core, 'NormalIn', b.out(nxy, 'Normal'))
    else:
        pat = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZP_' + m['id']]}, name='Pattern')
        b.set_in(pat, 'UV', vec)
        for name, _, _ in PATTERN_OUT:
            b.set_in(core, name, b.out(pat, name))
        b.set_in(core, 'NormalIn', b.out(geo, 'Normal'))
    b.node('NodeGroupOutput', {'Shader': b.out(core, 'Shader'), 'Volume': b.out(core, 'Volume')})
    return ng


def build_material(m, kzm):
    old = bpy.data.materials.get(m['id'])
    if old:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(m['id'])
    if hasattr(mat, 'use_nodes'):
        try:
            mat.use_nodes = True
        except Exception:
            pass
    nt = mat.node_tree
    nt.nodes.clear()
    g = nt.nodes.new('ShaderNodeGroup')
    g.node_tree = kzm
    g.name = g.label = 'KZ'
    g.width = 220
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (400, 0)
    nt.links.new(g.outputs['Shader'], out.inputs['Surface'])
    if m.get('transparent') and core_consts(m)['AbsorbDensity'] + core_consts(m)['ScatterDensity'] > 0:
        nt.links.new(g.outputs['Volume'], out.inputs['Volume'])
    mat['kz_id'] = m['id']
    mat['kz_library_version'] = VERSION
    mat.use_fake_user = True
    if m.get('transparent') and hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'BLENDED' if m['id'] == 'waterfall' else 'DITHERED'
    mat.diffuse_color = tuple(m.get('_mean_albedo', (0.3, 0.3, 0.3))) + (1.0,)
    mat.roughness = float(m.get('_mean_rough', 0.5))
    try:
        mat.asset_mark()
        mat.asset_data.description = f"Kazan-yu library: {m['name']} ({m['category']})"
        mat.asset_data.tags.new(m['category'])
    except Exception as e:
        log('asset mark failed', e)
    return mat


# ------------------------------------------------------------------ baking
def setup_gpu(scene):
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = (d.type == 'OPTIX')
    scene.cycles.device = 'GPU'


def bake_setup():
    scene = bpy.context.scene
    setup_gpu(scene)
    c = scene.cycles
    c.samples = 16
    c.use_adaptive_sampling = False
    c.use_denoising = False
    c.max_bounces = 0
    c.pixel_filter_type = 'BOX'
    c.filter_width = 1.0
    c.seed = 1
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.exr_codec = 'ZIP'
    scene.render.film_transparent = False
    world = bpy.data.worlds.new('KZ_BakeWorld')
    scene.world = world
    world.color = (0, 0, 0)
    me = bpy.data.meshes.new('KZ_BakePlane')
    me.from_pydata([(-1, -1, 0), (2, -1, 0), (2, 2, 0), (-1, 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        uv.data[li].uv = (co.x, co.y)
    ob = bpy.data.objects.new('KZ_BakePlane', me)
    scene.collection.objects.link(ob)
    cam_d = bpy.data.cameras.new('KZ_BakeCam')
    cam_d.type = 'ORTHO'
    cam_d.ortho_scale = 1.0
    cam = bpy.data.objects.new('KZ_BakeCam', cam_d)
    cam.location = (0.5, 0.5, 1.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    mat = bpy.data.materials.new('KZ_BakeMat')
    nt = mat.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    grp = nt.nodes.new('ShaderNodeGroup')
    grp.name = 'PAT'
    em = nt.nodes.new('ShaderNodeEmission')
    em.name = 'EM'
    comb = nt.nodes.new('ShaderNodeCombineColor')
    comb.name = 'COMB'
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    ob.data.materials.append(mat)
    return scene, ob, cam, mat


def bake_material(scene, mat, m):
    nt = mat.node_tree
    grp, em, comb, tc = nt.nodes['PAT'], nt.nodes['EM'], nt.nodes['COMB'], nt.nodes['Texture Coordinate']
    grp.node_tree = bpy.data.node_groups['KZP_' + m['id']]
    for l in list(nt.links):
        if l.to_node in (grp, comb) or (l.to_node == em and l.to_socket.name == 'Color'):
            nt.links.remove(l)
    nt.links.new(tc.outputs['UV'], grp.inputs['UV'])
    res = m['res']
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    passes = {'albedo': [('Albedo', None)], 'orm': [('AO', 0), ('Roughness', 1), ('Metallic', 2)],
              'hfa': [('Height', 0), ('Foam', 1), ('Alpha', 2)]}
    if m.get('emissive'):
        passes['emis'] = [('Emission', None)]
    out = {}
    for pname, chans in passes.items():
        for l in list(nt.links):
            if l.to_node == comb or (l.to_node == em and l.to_socket.name == 'Color'):
                nt.links.remove(l)
        if chans[0][1] is None:
            nt.links.new(grp.outputs[chans[0][0]], em.inputs['Color'])
        else:
            for c in comb.inputs:
                if hasattr(c, 'default_value'):
                    c.default_value = 0.0
            for name, idx in chans:
                nt.links.new(grp.outputs[name], comb.inputs[idx])
            nt.links.new(comb.outputs[0], em.inputs['Color'])
        path = os.path.join(BAKE_TMP, f"{m['id']}_{pname}.exr")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path, check_existing=False)
        a = np.empty(res * res * 4, np.float32)
        img.pixels.foreach_get(a)
        bpy.data.images.remove(img)
        out[pname] = a.reshape(res, res, 4)
    return out


def write_textures(m, px):
    """Pack baked channels into the web texture set (PNG sources)."""
    mid, res = m['id'], m['res']
    stats = {}
    alb = px['albedo'][..., :3]
    ao, ro, me = px['orm'][..., 0], px['orm'][..., 1], px['orm'][..., 2]
    h, foam, alpha = px['hfa'][..., 0], px['hfa'][..., 1], px['hfa'][..., 2]
    files = {}
    if m.get('transparent'):
        base = np.dstack([kzimg.to_u8(kzimg.lin_to_srgb(alb)), kzimg.to_u8(foam)])
    else:
        base = kzimg.to_u8(kzimg.lin_to_srgb(alb))
    files['base'] = base
    files['orm'] = np.dstack([kzimg.to_u8(ao), kzimg.to_u8(ro), kzimg.to_u8(me), kzimg.to_u8(h)])
    n = kzimg.normals_from_height(np.clip(h, 0, 1).astype(np.float64), m['depth'], m['tile'])
    files['nh'] = np.dstack([kzimg.to_u8(n[..., 0] * 0.5 + 0.5), kzimg.to_u8(n[..., 1] * 0.5 + 0.5),
                             kzimg.to_u8(h), np.full(h.shape, 255, np.uint8)])
    if m.get('emissive') and 'emis' in px:
        e = px['emis'][..., :3]
        files['emis'] = kzimg.to_u8(kzimg.lin_to_srgb(e / max(float(e.max()), 1e-6)))
        stats['emissive_max'] = float(e.max())
    paths = {}
    for k, arr in files.items():
        p = os.path.join(TEX_PNG, f'{mid}_{k}.png')
        kzimg.write_png(p, arr)
        paths[k] = p
        stats[f'seam_{k}'] = round(kzimg.seam_ratio(arr), 3)
    stats['mean_albedo_linear'] = [round(float(x), 4) for x in alb.reshape(-1, 3).mean(0)]
    stats['mean_roughness'] = round(float(ro.mean()), 3)
    stats['height_min_max'] = [round(float(h.min()), 3), round(float(h.max()), 3)]
    stats['normal_mean_slope_deg'] = round(float(np.degrees(np.arccos(np.clip(n[..., 2], -1, 1))).mean()), 2)
    if m.get('transparent'):
        stats['mean_foam'] = round(float(foam.mean()), 3)
    return paths, stats


def load_images(m, paths):
    imgs = {}
    for k, cs in (('base', 'sRGB'), ('orm', 'Non-Color'), ('nh', 'Non-Color')):
        name = f"{m['id']}_{k}"
        old = bpy.data.images.get(name)
        if old:
            bpy.data.images.remove(old)
        img = bpy.data.images.load(paths[k], check_existing=False)
        img.name = name
        img.colorspace_settings.name = cs
        img.alpha_mode = 'CHANNEL_PACKED'
        img.pack()
        img.filepath = '//tex/' + os.path.basename(paths[k])
        imgs[k] = img
    return imgs


# ------------------------------------------------------------------ manifest
KZ_SHADER_DOC = {
    'uv_convention': 'UV0 in metres (1 UV unit = 1 m). Texture coordinate = uv / scale. Textures are '
                     'authored with v = 1 on the first image row (glTF/Blender convention).',
    'normal_convention': 'Tangent space, OpenGL / glTF (+Y = +v). normal_height.rg = XY*0.5+0.5, '
                         'z = sqrt(1 - x^2 - y^2); normalScale = normal_strength.',
    'formulas': [
        'h = height (orm.a or normal_height.b), ao = orm.r',
        'wear_m = saturate((h + 1.2*wear - 1) * 4)',
        'wet_m  = saturate(wetness * (1.5 - h))',
        'albedo = base.rgb * tint * ao',
        'albedo = mix(albedo, worn_color * tint, wear_m)',
        'albedo *= 1 - porosity * 0.55 * wet_m',
        'albedo = mix(albedo, foam_color, foam)            // foam = base.a for transparent materials',
        'rough  = mix(orm.g, worn_rough, wear_m) + roughness_offset',
        'rough  = mix(rough, 0.04, wet_m); rough = clamp(mix(rough, 0.45, foam), 0, 1)',
        'metal  = mix(orm.b, worn_metal, wear_m)',
        'transmission = transmission * (1 - foam)',
        'emissive = emissive_map_or_white * emissive_color * tint, intensity = emit_strength * emissive_level',
        'attenuationColor = absorb_color * tint (three.js: attenuationColor/attenuationDistance given per material)',
        'In three.js the AO term is applied as aoMap (orm.r) on the baked lightMap, not multiplied into albedo.',
    ],
    'note': 'All lighting is baked irradiance (AGENT_PROMPT_3D 7.1); these textures carry albedo/ORM/detail '
            'only. View transform AgX in Blender and AgXToneMapping in three.js (7.5).',
}


def manifest_entry(m, stats, ktx_status):
    p = full_params(m)
    c = core_consts(m)
    src = m.get('tex_from', m['id'])
    tex = {'base': f'{TEX_KTX_REL}/{src}_base.ktx2', 'orm': f'{TEX_KTX_REL}/{src}_orm.ktx2',
           'normal_height': f'{TEX_KTX_REL}/{src}_nh.ktx2'}
    png = {'base': f'.scratch/matlib/tex/{src}_base.png', 'orm': f'.scratch/matlib/tex/{src}_orm.png',
           'normal_height': f'.scratch/matlib/tex/{src}_nh.png'}
    if m.get('emissive') and m['id'] == 'lava':
        tex['emissive'] = f'{TEX_KTX_REL}/{src}_emis.ktx2'
        png['emissive'] = f'.scratch/matlib/tex/{src}_emis.png'
    transparent = bool(m.get('transparent'))
    physical = transparent or c['Coat'] > 0 or c['Sheen'] > 0
    th = dict(m.get('three', {}))
    three = {'class': 'MeshPhysicalMaterial' if physical else 'MeshStandardMaterial',
             'roughness': 1.0, 'metalness': 1.0, 'roughnessMap': 'orm.g', 'metalnessMap': 'orm.b',
             'aoMap': 'orm.r', 'aoMapIntensity': 1.0, 'normalMap': 'normal_height (XY)',
             'normalScale': p['normal_strength'], 'envMapIntensity': th.pop('env', 1.0),
             'map': 'base (sRGB)', 'repeat_per_metre': round(1.0 / p['scale'], 5)}
    if transparent:
        three.update({'transparent': True, 'transmission_from_foam': 'transmission * (1 - base.a)'})
    three.update(th)
    em = None
    if m.get('emissive'):
        em = {'color_linear': [round(x, 4) for x in p['tint']] if m['id'] == 'neon_tube'
              else ([1, 1, 1] if m['id'] == 'lava' else [round(x, 4) for x in L.PAPER_GLOW]),
              'map': 'emissive' if m['id'] == 'lava' else 'base',
              'strength': c['EmitStrength'], 'emissive_level': p['emissive_level'],
              'note': 'Blender Emission Strength (W/m^2-ish); in three.js scale so the AgX result matches the '
                      'Cycles preview; keep bloom subtle (7.5).'}
    vol = None
    if transparent and (c['AbsorbDensity'] > 0 or c['ScatterDensity'] > 0):
        vol = {'absorb_color': list(c['Absorb']), 'absorb_density_per_m': c['AbsorbDensity'],
               'scatter_color': list(c['Scatter']), 'scatter_density_per_m': c['ScatterDensity'],
               'blender': 'transmittance = exp(-(1 - absorb_color) * density * distance_m)'}
    consts = {k: (list(v) if isinstance(v, tuple) else v) for k, v in c.items()
              if k not in ('TileSize', 'HeightDepth', 'HeightGain')}
    e = {
        'id': m['id'], 'name': m['name'], 'category': m['category'],
        'blender': {'material': m['id'], 'group': 'KZM_' + m['id'], 'node': 'KZ',
                    'mode': 'procedural (live KZP_%s pattern)' % m['id'] if m['mode'] == 'proc'
                    else 'image (baked tiling textures, packed)'},
        'params': {'tint': [round(x, 4) for x in p['tint']], 'wetness': p['wetness'], 'wear': p['wear'],
                   'roughness_offset': p['roughness_offset'], 'scale': p['scale'],
                   'normal_strength': p['normal_strength'], 'emissive_level': p['emissive_level']},
        'tiling_m_per_repeat': m['tile'],
        'texture_size': m['res'],
        'textures': tex,
        'texture_sources_png': png,
        'srgb': {'base': True, 'orm': False, 'normal_height': False, 'emissive': True},
        'channels': {'base': 'RGB albedo (sRGB)' + ('; A = foam/aeration coverage' if transparent else ''),
                     'orm': 'R occlusion, G roughness, B metalness, A height (linear)',
                     'normal_height': 'R,G normal XY (OpenGL +Y), B height, A 1 (linear)'},
        'height_depth_m': m['depth'],
        'constants': consts,
        'emissive': em,
        'transmission': c['Transmission'] > 0,
        'transparent': transparent,
        'thin_wall': c['ThinWall'] > 0,
        'volume': vol,
        'variants': {k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
                     for k, v in m.get('variants', {}).items()},
        'texture_source': {'origin': 'self-made procedural texture, tools/matlib/library_defs.py:%s, rendered to a '
                                     'seamless tile by tools/matlib/build_library.py' % m['pattern'].__name__,
                           'licence': 'CC0-1.0 (generated for this project; no third-party images)',
                           'shared_with': m.get('tex_from')},
        'concept': m['concept'],
        'three': three,
        'ktx2': ktx_status.get(src, {'encoded': False}),
        'stats': {k: v for k, v in stats.items() if not k.startswith('seam_')},
    }
    return e


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    os.makedirs(TEX_PNG, exist_ok=True)
    os.makedirs(BAKE_TMP, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_tile()
    build_normal_xy()
    build_core()
    mats = [m for m in L.MATERIALS if not ONLY or m['id'] in ONLY or m['id'] in
            {x.get('tex_from') for x in L.MATERIALS if x['id'] in (ONLY or ())}]
    for m in L.MATERIALS:
        build_pattern(m).use_fake_user = True   # keep generators in the library (re-bake reference)
    stats_path = os.path.join(ROOT, '.scratch', 'matlib', 'bake_stats.json')
    all_stats = json.load(open(stats_path)) if os.path.exists(stats_path) else {}
    paths = {}
    if not SKIP_BAKE:
        scene, ob, cam, bmat = bake_setup()
        for m in mats:
            if m.get('tex_from'):
                continue
            t = time.time()
            px = bake_material(scene, bmat, m)
            paths[m['id']], all_stats[m['id']] = write_textures(m, px)
            log(f"baked {m['id']:14s} {m['res']}px  {time.time() - t:5.1f}s  {all_stats[m['id']]}")
        for o in (ob, cam):
            bpy.data.objects.remove(o)
        bpy.data.materials.remove(bmat)
        json.dump(all_stats, open(stats_path, 'w'), indent=1)
    for m in L.MATERIALS:
        src = m.get('tex_from', m['id'])
        paths.setdefault(m['id'], {k: os.path.join(TEX_PNG, f'{src}_{k}.png') for k in ('base', 'orm', 'nh', 'emis')})
        st = all_stats.get(src, {})
        if 'mean_albedo_linear' in st:
            m['_mean_albedo'] = st['mean_albedo_linear']
            m['_mean_rough'] = st['mean_roughness']
    # library materials
    for m in L.MATERIALS:
        imgs = load_images(m, paths[m['id']]) if m['mode'] == 'image' else None
        kzm = build_kzm(m, imgs)
        build_material(m, kzm)
    # variants are documented, not duplicated: matlib.assign() creates them on demand
    for sc in list(bpy.data.scenes):
        sc.world = None
    for w in list(bpy.data.worlds):
        bpy.data.worlds.remove(w)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for cm in list(bpy.data.cameras):
        bpy.data.cameras.remove(cm)
    bpy.data.orphans_purge(do_recursive=True)
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.view_settings.view_transform = 'AgX'
    bpy.context.preferences.filepaths.save_version = 0      # no library.blend1 backup
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    log('saved', OUT_BLEND)
    # manifest
    ktx_path = os.path.join(ROOT, '.scratch', 'matlib', 'ktx_status.json')
    ktx = json.load(open(ktx_path)) if os.path.exists(ktx_path) else {}
    manifest = {
        'version': VERSION,
        'generated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'generator': 'tools/matlib/build_library.py (Blender %s)' % bpy.app.version_string,
        'library_blend': 'materials/library.blend',
        'settings': SETTINGS,
        'colour_management': 'AgX (Blender) / AgXToneMapping (three.js); albedo textures sRGB, data linear',
        'ktx2': ktx.get('_tool', {'tool': 'KTX-Software ktx create', 'version': '4.4.2', 'encoded': False,
                                  'note': 'run tools/matlib/encode_ktx2.py'}),
        'kz_core': KZ_SHADER_DOC,
        'categories': [{'id': c[0], 'label': c[1],
                        'sheet_concept_crops': [{'image': 'lookbook/img/' + im, 'box_fraction_ltrb': list(bx)}
                                                for im, bx in c[2]]}
                       for c in L.CATEGORIES],
        'materials': [manifest_entry(m, all_stats.get(m.get('tex_from', m['id']), {}), ktx) for m in L.MATERIALS],
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(manifest, f, indent=1)
    log('wrote', OUT_JSON, f'({len(manifest["materials"])} materials) in {time.time() - t0:.0f}s')


main()
