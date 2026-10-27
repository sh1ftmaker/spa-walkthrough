"""Build the Kazan-yu material library from scratch (round 2).

    /home/agent-tom/.local/bin/blender -b -P tools/matlib/build_library.py [-- --skip-bake]

Writes
    3d/materials/library.blend          materials + shared node groups + packed shipping textures
    .scratch/matlib/tex/<set>_*.png     shipping-resolution tiling textures (KTX2 sources)
    .scratch/matlib/tex/mips/<set>_orm_L<k>.png   ORM mip chain with Toksvig roughness
    3d/materials.json                   manifest for the web app
Then: tools/matlib/encode_ktx2.py, render_previews.py, render_scale_previews.py,
tile_checks.py, contact_sheet.py.  See 3d/materials/README.md.

Every material <id> is one group node "KZ" (= KZM_<id>, inputs: the 7 artist settings).
KZM_<id> samples the *shipped* texture set (the same PNGs that become KTX2, so Blender shows
what the phone gets), optionally a side set blended by world normal, and the shared 8 m macro
texture, and feeds the shared KZ_Core group, which applies the settings with the formulas
listed in materials.json -> kz_core (the web shader repeats them).  The procedural generators
(KZP_<set>) stay in the library with a fake user as the source of the textures.
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
import kzimg  # noqa: E402
import library_defs as L  # noqa: E402
from kzdsl import B  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_BLEND = os.path.join(ROOT, '3d', 'materials', 'library.blend')
OUT_JSON = os.path.join(ROOT, '3d', 'materials.json')
TEX_PNG = os.path.join(ROOT, '.scratch', 'matlib', 'tex')
MIPS = os.path.join(TEX_PNG, 'mips')
BAKE_TMP = os.path.join(ROOT, '.scratch', 'matlib', 'bake')
STATS = os.path.join(ROOT, '.scratch', 'matlib', 'bake_stats.json')
TEX_KTX_REL = 'materials/tex'           # relative to 3d/
SETTINGS = ['tint', 'wetness', 'wear', 'roughness_offset', 'scale', 'normal_strength', 'emissive_level']
VERSION = 2

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SKIP_BAKE = '--skip-bake' in argv

CORE_DEFAULTS = dict(
    TileSize=1.0, HeightDepth=0.01, Specular=0.5, IOR=1.5, Transmission=0.0, ThinWall=0.0,
    Coat=0.0, CoatRough=0.05, Sheen=0.0, Translucency=0.0, Porosity=1.0,
    WornColor=(0.5, 0.5, 0.5), WornRough=0.5, WornMetal=0.0, WornMax=1.0, FoamColor=(0.8, 0.85, 0.85),
    FoamFromMask=0.0, ThinFromMask=0.0, AlphaFromMask=0.0, AlphaMin=1.0, FrostUp=0.0,
    EmitStrength=1.0, EmitColor=(0.0, 0.0, 0.0), EmitMapScale=1.0, EmitCore=0.0, EmitMacro=0.0,
    MacroAmount=0.0, Absorb=(1.0, 1.0, 1.0), AbsorbDensity=0.0, Scatter=(1.0, 1.0, 1.0), ScatterDensity=0.0)
NOT_CORE = ('Cavity',)
PATTERN_OUT = [('Albedo', 'c', (0.5, 0.5, 0.5), 'albedo'), ('Roughness', 'f', 0.5, 'rough'),
               ('Metallic', 'f', 0.0, 'metal'), ('Height', 'f', 0.5, 'height'), ('AO', 'f', 1.0, 'ao'),
               ('Emission', 'c', (0.0, 0.0, 0.0), 'emission'), ('Mask', 'f', 1.0, 'mask'),
               ('WetMask', 'f', 0.0, 'wet')]


def log(*a):
    print('[matlib]', *a, flush=True)


# ------------------------------------------------------------------ helpers
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
    return bpy.data.node_groups.new(name, 'ShaderNodeTree')


def full_params(m):
    p = dict(tint=(1.0, 1.0, 1.0), wetness=0.0, wear=0.0, roughness_offset=0.0, scale=1.0,
             normal_strength=1.0, emissive_level=0.0)
    if m:
        p['scale'] = 1.0 if m.get('uvmode') == 'object' else m['tile']
        p.update(m.get('params', {}))
        p['tint'] = tuple(p['tint'])
    return p


def settings_iface(ng, m=None):
    p = full_params(m)
    sock(ng, 'tint', 'INPUT', 'c', p['tint'], desc='Linear RGB multiplier: albedo, worn colour, emission, absorption')
    sock(ng, 'wetness', 'INPUT', 'f', p['wetness'], 0.0, 1.0, 'Water film: darkens porous albedo; films in hollows '
         'and wet-mask pockets go mirror-wet (0.04), tops stay damp (0.32)')
    sock(ng, 'wear', 'INPUT', 'f', p['wear'], 0.0, 1.0, 'High points towards the worn colour/roughness/metal')
    sock(ng, 'roughness_offset', 'INPUT', 'f', p['roughness_offset'], -1.0, 1.0, 'Added to roughness')
    sock(ng, 'scale', 'INPUT', 'f', p['scale'], 0.001, 100.0, 'Metres per texture repeat along u (UVs in metres)')
    sock(ng, 'normal_strength', 'INPUT', 'f', p['normal_strength'], 0.0, 4.0, 'Detail normal strength')
    sock(ng, 'emissive_level', 'INPUT', 'f', p['emissive_level'], 0.0, 100.0, 'Emission multiplier (0 = off)')


def core_consts(m):
    c = dict(CORE_DEFAULTS)
    c.update({k: v for k, v in m.get('core', {}).items() if k not in NOT_CORE})
    c['TileSize'] = 1.0 if m.get('uvmode') == 'object' else m['tile']
    c['HeightDepth'] = m['depth']
    return c


def set_inputs(node, values):
    for k, v in values.items():
        s = node.inputs[k]
        if isinstance(v, (tuple, list)):
            v = tuple(v) + ((1.0,) if len(v) == 3 and len(s.default_value) == 4 else ())
        s.default_value = v


# ------------------------------------------------------------------ texture sets
def texture_sets():
    """Every texture set to bake: one per material (unless tex_from), side sets, the macro set."""
    sets = []
    for m in L.MATERIALS:
        if m.get('tex_from'):
            continue
        c = m.get('core', {})
        uses_mask = bool(m.get('transparent') or c.get('ThinFromMask') or c.get('AlphaFromMask')
                         or m['category'] in ('light',) and m.get('uvmode') == 'object')
        base = dict(sid=m['id'], pattern=m['pattern'], plate=m.get('plate'), tile=m['tile'], aspect=m.get('aspect', 1.0), res=m['res'],
                    depth=m['depth'], cavity=c.get('Cavity', 1.0), mask=uses_mask, emissive=bool(m.get('emissive')),
                    mat=m['id'])
        sets.append(base)
        if m.get('side'):
            sets.append(dict(base, sid=m['id'] + '_side', pattern=m['side'], plate=None, emissive=False))
    sets.append(dict(sid=L.MACRO['id'], pattern=L.pat_macro, tile=L.MACRO['tile'], aspect=1.0, res=L.MACRO['res'],
                     depth=0.0, cavity=0.0, mask=True, emissive=False, macro=True, mat=None))
    return sets


def dims(s):
    a = s['aspect']
    return (s['res'], max(4, int(round(s['res'] / a)))) if a >= 1 else (max(4, int(round(s['res'] * a))), s['res'])


def build_pattern(s):
    ng = new_group('KZP_' + s['sid'])
    sock(ng, 'UV', 'INPUT', 'v', (0, 0, 0), desc='tile space: [0,1) = one repeat')
    for name, typ, d, _ in PATTERN_OUT:
        sock(ng, name, 'OUTPUT', typ, d)
    b = B(ng)
    gi = b.node('NodeGroupInput')
    res = s['pattern'](b, b.out(gi, 'UV'))
    go = b.node('NodeGroupOutput')
    go.location = (max(b.cols) * 220 + 400, 0)
    for name, typ, d, key in PATTERN_OUT:
        b.set_in(go, name, res.get(key, d))
    ng.use_fake_user = True
    return ng


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
    st = scene.render.image_settings
    st.file_format = 'OPEN_EXR'
    st.color_depth = '32'
    st.color_mode = 'RGBA'
    st.exr_codec = 'ZIP'
    world = bpy.data.worlds.new('KZ_BakeWorld')
    scene.world = world
    world.color = (0, 0, 0)
    cam_d = bpy.data.cameras.new('KZ_BakeCam')
    cam_d.type = 'ORTHO'
    cam = bpy.data.objects.new('KZ_BakeCam', cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    mat = bpy.data.materials.new('KZ_BakeMat')
    nt = mat.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.name = 'TC'
    grp = nt.nodes.new('ShaderNodeGroup')
    grp.name = 'PAT'
    em = nt.nodes.new('ShaderNodeEmission')
    em.name = 'EM'
    comb = nt.nodes.new('ShaderNodeCombineColor')
    comb.name = 'COMB'
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return scene, cam, mat


def bake_plane(scene, cam, mat, aspect):
    """3x3-tile plane in camera space: x spans u (1 per repeat), y spans v (1/aspect per repeat)."""
    old = bpy.data.objects.get('KZ_BakePlane')
    if old:
        me_old = old.data
        bpy.data.objects.remove(old)
        bpy.data.meshes.remove(me_old)
    ya = 1.0 / aspect
    me = bpy.data.meshes.new('KZ_BakePlane')
    me.from_pydata([(-1, -ya, 0), (2, -ya, 0), (2, 2 * ya, 0), (-1, 2 * ya, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        uv.data[li].uv = (co.x, co.y * aspect)
    ob = bpy.data.objects.new('KZ_BakePlane', me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    cam.location = (0.5, 0.5 * ya, 1.0)
    cam.data.ortho_scale = max(1.0, ya)


def bake_set(scene, cam, mat, s):
    nt = mat.node_tree
    grp, em, comb, tc = nt.nodes['PAT'], nt.nodes['EM'], nt.nodes['COMB'], nt.nodes['TC']
    grp.node_tree = bpy.data.node_groups['KZP_' + s['sid']]
    nt.links.new(tc.outputs['UV'], grp.inputs['UV'])
    bake_plane(scene, cam, mat, s['aspect'])
    W, H = dims(s)
    scene.render.resolution_x, scene.render.resolution_y = W, H
    scene.render.resolution_percentage = 100
    passes = {'albedo': [('Albedo', None)], 'orm': [('AO', 0), ('Roughness', 1), ('Metallic', 2)],
              'hmw': [('Height', 0), ('Mask', 1), ('WetMask', 2)]}
    if s['emissive']:
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
        path = os.path.join(BAKE_TMP, f"{s['sid']}_{pname}.exr")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path, check_existing=False)
        a = np.empty(W * H * 4, np.float32)
        img.pixels.foreach_get(a)
        bpy.data.images.remove(img)
        out[pname] = a.reshape(H, W, 4).astype(np.float64)
    return out


def plate_px(s):
    """Texture-set channels from a painted plate (plates.py), in bake_set's layout."""
    import plates as P
    p = s['plate']
    img = P.cut(P.load_sheet(os.path.join(ROOT, p['sheet'])))[p['idx']]
    d = P.make_set(p, img)
    H, W = d['albedo'].shape[:2]
    assert (W, H) == dims(s), (s['sid'], (W, H), dims(s))
    one = np.ones((H, W))
    st = lambda *ch: np.dstack(list(ch))[::-1]          # plates are top-first; Blender rows are bottom-first
    px = {'albedo': st(*np.moveaxis(d['albedo'], -1, 0), one), 'orm': st(d['ao'], d['rough'], d['metal'], one),
          'hmw': st(d['height'], d['mask'], d['wet'], one)}
    if s['emissive']:
        e = d['emis'] if d['emis'] is not None else np.zeros((H, W, 3))
        px['emis'] = st(*np.moveaxis(e, -1, 0), one)
    return px


def std255(a):
    return round(float(np.std(a) * 255.0), 1)


def write_set(s, px):
    """Post-process one baked set into shipping PNGs (+ ORM mips) and return stats."""
    sid = s['sid']
    W, H = dims(s)
    tile_u = s['tile']
    tile_v = s['tile'] / s['aspect']
    alb = np.clip(px['albedo'][..., :3], 0, 1)
    ao_p, ro, me = px['orm'][..., 0], px['orm'][..., 1], px['orm'][..., 2]
    h, mask, wet = np.clip(px['hmw'][..., 0], 0, 1), px['hmw'][..., 1], px['hmw'][..., 2]
    files, stats = {}, {'size': [W, H]}
    if s.get('macro'):
        files['base'] = np.dstack([kzimg.to_u8(alb), kzimg.to_u8(mask)])        # linear data
    else:
        srgb = kzimg.to_u8(kzimg.lin_to_srgb(alb))
        files['base'] = np.dstack([srgb, kzimg.to_u8(mask)]) if s['mask'] else srgb
        cav = kzimg.cavity_ao(h, s['depth'], tile_u, tile_v, s['cavity']) if s['cavity'] > 0 else 1.0
        ao = np.clip(ao_p, 0, 1) * cav
        n = kzimg.normals_from_height(h, s['depth'], tile_u, tile_v)
        orm = np.dstack([ao, np.clip(ro, 0, 1), np.clip(me, 0, 1), h])
        files['orm'] = kzimg.to_u8(orm)
        files['nh'] = np.dstack([kzimg.to_u8(n[..., 0] * 0.5 + 0.5), kzimg.to_u8(n[..., 1] * 0.5 + 0.5),
                                 kzimg.to_u8(h), kzimg.to_u8(wet)])
        if s['emissive'] and 'emis' in px:
            e = np.clip(px['emis'][..., :3], 0, None)
            sc = max(float(e.max()), 1e-6)
            files['emis'] = kzimg.to_u8(kzimg.lin_to_srgb(e / sc))
            stats['emissive_map_scale'] = round(sc, 4)
        lv = kzimg.toksvig_mips(orm, n)
        for k, o in enumerate(lv):
            kzimg.write_png(os.path.join(MIPS, f'{sid}_orm_L{k}.png'), kzimg.to_u8(o))
        stats['orm_mip_levels'] = len(lv)
        stats['albedo_std_srgb255'] = std255(kzimg.lin_to_srgb(alb).mean(-1))
        stats['roughness_std_255'] = std255(ro)
        stats['ao_mean_255'] = round(float(ao.mean() * 255), 1)
        stats['mean_albedo_linear'] = [round(float(x), 4) for x in alb.reshape(-1, 3).mean(0)]
        stats['mean_roughness'] = round(float(ro.mean()), 3)
        stats['normal_mean_slope_deg'] = round(float(np.degrees(np.arccos(np.clip(n[..., 2], -1, 1))).mean()), 2)
        stats['height_min_max'] = [round(float(h.min()), 3), round(float(h.max()), 3)]
    for k, arr in files.items():
        kzimg.write_png(os.path.join(TEX_PNG, f'{sid}_{k}.png'), arr)
    return stats


# ------------------------------------------------------------------ shared groups
def build_tile():
    ng = new_group('KZ_Tile')
    sock(ng, 'UV', 'INPUT', 'v', (0, 0, 0), desc='UV in metres')
    sock(ng, 'scale', 'INPUT', 'f', 1.0, 0.001, 100.0, 'metres per repeat along u')
    sock(ng, 'aspect', 'INPUT', 'f', 1.0, 0.01, 100.0, 'u extent / v extent of one repeat')
    sock(ng, 'Vector', 'OUTPUT', 'v')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    sc = b.out(gi, 'scale')
    v = b.vmath('DIVIDE', b.out(gi, 'UV'), b.xyz(sc, sc / b.out(gi, 'aspect'), 1.0))
    b.node('NodeGroupOutput', {'Vector': v})


def build_normal_xy():
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


def build_core():
    ng = new_group('KZ_Core')
    settings_iface(ng)
    sock(ng, 'Albedo', 'INPUT', 'c', (0.5, 0.5, 0.5))
    sock(ng, 'Roughness', 'INPUT', 'f', 0.5, 0.0, 1.0)
    sock(ng, 'Metallic', 'INPUT', 'f', 0.0, 0.0, 1.0)
    sock(ng, 'Height', 'INPUT', 'f', 0.5, 0.0, 1.0)
    sock(ng, 'AO', 'INPUT', 'f', 1.0, 0.0, 1.0)
    sock(ng, 'Emission', 'INPUT', 'c', (0, 0, 0))
    sock(ng, 'Mask', 'INPUT', 'f', 1.0, 0.0, 1.0)
    sock(ng, 'WetMask', 'INPUT', 'f', 0.0, 0.0, 1.0)
    sock(ng, 'Macro', 'INPUT', 'c', (0.5, 0.5, 0.5))
    sock(ng, 'MacroA', 'INPUT', 'f', 0.0, 0.0, 1.0)
    sock(ng, 'NormalIn', 'INPUT', 'v', (0, 0, 1))
    for k, v in CORE_DEFAULTS.items():
        sock(ng, k, 'INPUT', 'c' if isinstance(v, tuple) else 'f', v)
    sock(ng, 'Shader', 'OUTPUT', 's')
    sock(ng, 'Volume', 'OUTPUT', 's')

    b = B(ng)
    gi = b.node('NodeGroupInput')
    I = lambda n: b.out(gi, n)  # noqa: E731
    tint = I('tint')
    h = I('Height')
    m = I('MacroAmount')
    mr, mg, mb = b.rgb_sep(I('Macro'))
    geo = b.node('ShaderNodeNewGeometry')
    _, _, nz = b.sep(b.out(geo, 'Normal'))
    foam = (I('Mask') * I('FoamFromMask') + nz.smooth(0.6, 0.9) * I('FrostUp')).clamp()
    thin = b.mixf(I('ThinFromMask'), 1.0, I('Mask'))
    streak = I('MacroA') * m
    wear_m = ((h + I('wear') * 1.2 - 1.0) * 4.0).clamp() * I('WornMax')
    film = (I('WetMask') * 1.2 + (0.5 - h) * 0.8 + (mb - 0.5) * 0.6 * m + streak * 0.5).clamp()
    bright = (mr - 0.5) * 0.4 * m + 1.0
    hue = (mg - 0.5) * m
    huev = b.xyz(1.0 - hue * 0.2, 1.0, hue * 0.24 + 1.0)
    alb = b.cmul(b.cmul(I('Albedo'), tint), I('AO') * bright * (1.0 - streak * 0.25))
    alb = b.cmul(alb, huev)
    worn = b.cmul(b.cmul(I('WornColor'), tint), h * 0.6 + 0.7)
    alb = b.mixc(wear_m, alb, worn)
    alb = b.cmul(alb, 1.0 - I('Porosity') * 0.55 * I('wetness') * (film * 0.4 + 0.6))
    alb = b.mixc(foam, alb, I('FoamColor'))
    rough = b.mixf(wear_m, I('Roughness'), I('WornRough')) + I('roughness_offset') - (mb - 0.5) * 0.2 * m
    wet_t = b.mixf(film, 0.32, 0.04)
    rough = b.mixf((I('wetness') * 1.4).clamp(), rough, rough.min(wet_t))
    rough = b.mixf(foam, rough, 0.45).max(0.02).min(1.0)
    metal = b.mixf(wear_m, I('Metallic'), I('WornMetal'))
    trans = I('Transmission') * (1.0 - foam)
    alpha = b.mixf(I('AlphaFromMask'), 1.0, I('AlphaMin') + (1.0 - I('AlphaMin')) * I('Mask'))
    nrm = I('NormalIn')                         # detail normal decoded from normal_height (KZ_NormalXY)
    emis = b.cadd(b.cmul(I('Emission'), I('EmitMapScale')), I('EmitColor'))
    emis = b.cmul(b.cmul(emis, tint), I('EmitStrength') * I('emissive_level') * ((mr - 0.5) * 1.2 * I('EmitMacro') + 1.0))
    lw = b.node('ShaderNodeLayerWeight', {'Blend': 0.5})
    core_f = ((1.0 - b.out(lw, 'Facing')) ** 2.0) * I('EmitCore') * 0.85
    er, eg, eb = b.sep(emis)
    emax = er.max(eg).max(eb)
    ewhite = b.xyz(emax, emax * 0.93, emax * 0.95)
    emis = b.mixc(core_f, emis, ewhite)
    p = b.node('ShaderNodeBsdfPrincipled', {
        'Base Color': alb, 'Metallic': metal, 'Roughness': rough, 'IOR': I('IOR'), 'Alpha': alpha,
        'Normal': nrm, 'Specular IOR Level': I('Specular'), 'Transmission Weight': trans,
        'Coat Weight': I('Coat'), 'Coat Roughness': I('CoatRough'), 'Sheen Weight': I('Sheen'),
        'Sheen Roughness': 0.5, 'Emission Color': emis, 'Emission Strength': 1.0})
    tw = p.inputs['Thin Wall']
    if tw.type in ('VALUE', 'BOOLEAN', 'INT'):
        ng.links.new(I('ThinWall').sock, tw)
    tl = b.node('ShaderNodeBsdfTranslucent', {'Color': alb, 'Normal': nrm})
    tfac = (I('Translucency') * thin * (I('ThinFromMask') + 1.0)).clamp()
    mix = b.node('ShaderNodeMixShader', {0: tfac, 1: b.out(p, 0), 2: b.out(tl, 0)})
    ab = b.node('ShaderNodeVolumeAbsorption', {'Color': b.cmul(I('Absorb'), tint), 'Density': I('AbsorbDensity')})
    sc = b.node('ShaderNodeVolumeScatter', {'Color': I('Scatter'), 'Density': I('ScatterDensity')})
    vol = b.node('ShaderNodeAddShader', {0: b.out(ab, 0), 1: b.out(sc, 0)})
    b.node('NodeGroupOutput', {'Shader': b.out(mix, 0), 'Volume': b.out(vol, 0)})


# ------------------------------------------------------------------ materials
STATS_CACHE = {}
IMG_CS = {'base': 'sRGB', 'orm': 'Non-Color', 'nh': 'Non-Color', 'emis': 'sRGB'}


def load_image(name, path, cs):
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.load(path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = cs
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pack()
    img.filepath = '//tex/' + os.path.basename(path)
    return img


def load_set(sid, emissive):
    imgs = {}
    for k, cs in IMG_CS.items():
        p = os.path.join(TEX_PNG, f'{sid}_{k}.png')
        if k != 'emis' or emissive:
            imgs[k] = bpy.data.images.get(f'{sid}_{k}') or load_image(f'{sid}_{k}', p, cs)
    return imgs


def build_kzm(m, macro_img):
    ng = new_group('KZM_' + m['id'])
    settings_iface(ng, m)
    sock(ng, 'Shader', 'OUTPUT', 's')
    sock(ng, 'Volume', 'OUTPUT', 's')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    I = lambda n: b.out(gi, n)  # noqa: E731
    tc = b.node('ShaderNodeTexCoord')
    tile = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_Tile']}, name='Tile')
    b.set_in(tile, 'UV', b.out(tc, 'UV'))
    b.set_in(tile, 'scale', I('scale'))
    b.set_in(tile, 'aspect', m.get('aspect', 1.0))
    vec = b.out(tile, 'Vector')
    core = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_Core']}, name='Core')
    for k in SETTINGS:
        b.set_in(core, k, I(k))
    set_inputs(core, core_consts(m))
    src = m.get('tex_from', m['id'])

    def sample(sid):
        imgs = load_set(sid, 'emissive_map_scale' in STATS_CACHE.get(sid, {}))
        nd = {k: b.node('ShaderNodeTexImage', {'Vector': vec}, {'image': im, 'interpolation': 'Linear',
                                                               'extension': 'REPEAT'}, label=f'{sid} {k}')
              for k, im in imgs.items()}
        ch = {'albedo': b.out(nd['base'], 'Color'), 'mask': b.out(nd['base'], 'Alpha'),
              'orm': b.out(nd['orm'], 'Color'), 'height': b.out(nd['orm'], 'Alpha'),
              'nh': b.out(nd['nh'], 'Color'), 'wet': b.out(nd['nh'], 'Alpha')}
        if 'emis' in nd:
            ch['emis'] = b.out(nd['emis'], 'Color')
        return ch

    ch = sample(src)
    if m.get('side'):
        sd = sample(src + '_side')
        geo = b.node('ShaderNodeNewGeometry')
        _, _, nz = b.sep(b.out(geo, 'Normal'))
        wt = nz.smooth(0.5, 0.8)                     # 1 = top set, 0 = side set
        for k in ('albedo', 'orm', 'nh'):
            ch[k] = b.mixc(wt, sd[k], ch[k])
        for k in ('mask', 'height', 'wet'):
            ch[k] = b.mixf(wt, sd[k], ch[k])
    ao, ro, me = b.rgb_sep(ch['orm'])
    nxy = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_NormalXY']})
    b.set_in(nxy, 'Color', ch['nh'])
    b.set_in(nxy, 'Strength', I('normal_strength'))
    mv = b.vmath('DIVIDE', b.out(tc, 'UV'), (L.MACRO['tile'], L.MACRO['tile'], 1.0))
    mac = b.node('ShaderNodeTexImage', {'Vector': mv}, {'image': macro_img, 'interpolation': 'Linear',
                                                       'extension': 'REPEAT'}, label='macro 8 m')
    for k, v in (('Albedo', ch['albedo']), ('AO', ao), ('Roughness', ro), ('Metallic', me),
                 ('Height', ch['height']), ('Mask', ch['mask']), ('WetMask', ch['wet']),
                 ('NormalIn', b.out(nxy, 'Normal')), ('Macro', b.out(mac, 'Color')), ('MacroA', b.out(mac, 'Alpha'))):
        b.set_in(core, k, v)
    if 'emis' in ch:
        b.set_in(core, 'Emission', ch['emis'])
    b.node('NodeGroupOutput', {'Shader': b.out(core, 'Shader'), 'Volume': b.out(core, 'Volume')})
    return ng


def build_material(m, kzm, stats):
    old = bpy.data.materials.get(m['id'])
    if old:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(m['id'])
    nt = mat.node_tree
    nt.nodes.clear()
    g = nt.nodes.new('ShaderNodeGroup')
    g.node_tree = kzm
    g.name = g.label = 'KZ'
    g.width = 220
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (400, 0)
    nt.links.new(g.outputs['Shader'], out.inputs['Surface'])
    c = core_consts(m)
    if m.get('transparent') and c['AbsorbDensity'] + c['ScatterDensity'] > 0:
        nt.links.new(g.outputs['Volume'], out.inputs['Volume'])
    mat['kz_id'] = m['id']
    mat['kz_library_version'] = VERSION
    mat.use_fake_user = True
    if m.get('transparent') and hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'BLENDED' if c['AlphaFromMask'] > 0 else 'DITHERED'
    mat.diffuse_color = tuple(stats.get('mean_albedo_linear', (0.3, 0.3, 0.3))) + (1.0,)
    mat.roughness = float(stats.get('mean_roughness', 0.5))
    try:
        mat.asset_mark()
        mat.asset_data.description = f"Kazan-yu library: {m['name']} ({m['category']})"
        mat.asset_data.tags.new(m['category'])
    except Exception as e:
        log('asset mark failed', e)
    return mat


# ------------------------------------------------------------------ manifest
KZ_SHADER_DOC = {
    'uv_convention': 'UV0 in metres (1 UV unit = 1 m) unless uv_mode is "object" (lanterns: 0..1 per lantern). '
                     'Texture coordinate = (u / scale, v / (scale / aspect)). On walls v points up (drip streaks '
                     'run along v). Textures have v = 1 on the first image row (glTF/Blender convention).',
    'normal_convention': 'Tangent space, OpenGL / glTF (+Y = +v). normal_height.rg = XY*0.5+0.5, '
                         'z = sqrt(1 - x^2 - y^2); normalScale = normal_strength.',
    'channels': {'base': 'RGB albedo (sRGB); A = mask: foam (water/ice/glass), thinness (paper), coverage (decals)',
                 'orm': 'R occlusion incl. baked cavity, G roughness, B metalness, A height (linear). Mip chain is '
                        'supplied with Toksvig roughness (specular anti-aliasing).',
                 'normal_height': 'R,G normal XY, B height, A wet-film mask (where water collects) (linear)',
                 'emissive': 'emission colour (sRGB), multiply by emissive.map_scale',
                 'macro': 'shared materials/tex/kz_macro.ktx2, linear, 8 m repeat in UV metres: R brightness, '
                          'G hue (>0.5 cooler), B wetness/roughness, A vertical stain streaks'},
    'formulas': [
        'h = orm.a; ao = orm.r; film_mask = normal_height.a; mask = base.a',
        'M = macro(uv / 8) ; m = macro_amount ; streak = M.a * m',
        'foam = saturate(mask * foam_from_mask + frost_up * smoothstep(0.6, 0.9, world_normal.y))',
        'thin = mix(1, mask, thin_from_mask)',
        'wear_m = saturate((h + 1.2*wear - 1) * 4) * worn_max',
        'film = saturate(film_mask*1.2 + (0.5 - h)*0.8 + (M.b - 0.5)*0.6*m + streak*0.5)',
        'albedo = base.rgb * tint * ao * (1 + (M.r - 0.5)*0.4*m) * (1 - 0.25*streak) * vec3(1 - 0.2*hue, 1, 1 + 0.24*hue), hue = (M.g - 0.5)*m',
        'albedo = mix(albedo, worn_color * tint * (0.7 + 0.6*h), wear_m)',
        'albedo *= 1 - porosity * 0.55 * wetness * (0.6 + 0.4*film)',
        'albedo = mix(albedo, foam_color, foam)',
        'rough = mix(orm.g, worn_rough, wear_m) + roughness_offset - (M.b - 0.5)*0.2*m',
        'rough = mix(rough, min(rough, mix(0.32, 0.04, film)), saturate(1.4*wetness))',
        'rough = clamp(mix(rough, 0.45, foam), 0.02, 1)',
        'metal = mix(orm.b, worn_metal, wear_m)',
        'alpha = mix(1, alpha_min + (1 - alpha_min) * mask, alpha_from_mask)',
        'emissive = (emissive_map * map_scale + emit_color) * tint * emit_strength * emissive_level * (1 + (M.r - 0.5)*1.2*emit_macro)',
        'emissive = mix(emissive, white(max(emissive)), 0.85 * emit_core * (1 - fresnel_facing)^2)   // neon white core',
        'three.js: apply ao as aoMap on the lightMap (not multiplied into albedo); wetness/wear/tint are uniforms.',
    ],
    'note': 'All lighting is baked irradiance (AGENT_PROMPT_3D 7.1); textures carry albedo/ORM/detail only. '
            'AgX in Blender and AgXToneMapping in three.js (7.5). Water, ice and glass do not use transmission on '
            'the phone (see each material three.note).',
}


def manifest_entry(m, stats):
    p = full_params(m)
    c = core_consts(m)
    src = m.get('tex_from', m['id'])
    files = lambda sid: {'base': f'{TEX_KTX_REL}/{sid}_base.ktx2', 'orm': f'{TEX_KTX_REL}/{sid}_orm.ktx2',  # noqa
                         'normal_height': f'{TEX_KTX_REL}/{sid}_nh.ktx2'}
    tex = files(src)
    st = stats.get(src, {})
    if 'emissive_map_scale' in st:
        tex['emissive'] = f'{TEX_KTX_REL}/{src}_emis.ktx2'
    transparent = bool(m.get('transparent'))
    th = dict(m.get('three', {}))
    note = th.pop('note', None)
    physical = c['Coat'] > 0 or c['Sheen'] > 0
    three = {'class': 'MeshPhysicalMaterial' if physical else 'MeshStandardMaterial',
             'map': 'base (sRGB)', 'roughness': 1.0, 'metalness': 1.0, 'roughnessMap': 'orm.g', 'metalnessMap': 'orm.b',
             'aoMap': 'orm.r', 'aoMapIntensity': 1.0, 'normalMap': 'normal_height (XY)',
             'normalScale': p['normal_strength'], 'envMapIntensity': th.pop('env', 1.0),
             'repeat': [round(1.0 / p['scale'], 5), round(m.get('aspect', 1.0) / p['scale'], 5)]}
    three.update(th)
    if note:
        three['note'] = note
    em = None
    if m.get('emissive') or c['EmitColor'] != (0.0, 0.0, 0.0):
        em = {'map': 'emissive' if 'emissive' in tex else None, 'map_scale': st.get('emissive_map_scale', 1.0),
              'color_linear': list(c['EmitColor']) if 'emissive' not in tex else [1, 1, 1],
              'strength': c['EmitStrength'], 'emissive_level': p['emissive_level'], 'emit_core': c['EmitCore'],
              'emit_macro': c['EmitMacro'],
              'note': 'Blender Emission Strength; keep emissives moderate (AgX desaturates bright values) and let '
                      'a subtle bloom carry the glow (7.5).'}
    vol = None
    if transparent and (c['AbsorbDensity'] > 0 or c['ScatterDensity'] > 0):
        vol = {'absorb_color': list(c['Absorb']), 'absorb_density_per_m': c['AbsorbDensity'],
               'scatter_color': list(c['Scatter']), 'scatter_density_per_m': c['ScatterDensity'],
               'blender': 'transmittance = exp(-(1 - absorb_color) * density * distance_m); Blender bakes/previews only'}
    consts = {k: (list(v) if isinstance(v, tuple) else v) for k, v in c.items() if k not in ('TileSize', 'HeightDepth')}
    e = {
        'id': m['id'], 'name': m['name'], 'category': m['category'],
        'blender': {'material': m['id'], 'group': 'KZM_' + m['id'], 'node': 'KZ',
                    'generator': m.get('source') or f"KZP_{src} ({m['pattern'].__name__})"},
        'uv_mode': m.get('uvmode', 'metric'),
        'params': {'tint': [round(x, 4) for x in p['tint']], 'wetness': p['wetness'], 'wear': p['wear'],
                   'roughness_offset': p['roughness_offset'], 'scale': p['scale'],
                   'normal_strength': p['normal_strength'], 'emissive_level': p['emissive_level']},
        'tiling_m_per_repeat': m['tile'] if m.get('uvmode') != 'object' else None,
        'aspect': m.get('aspect', 1.0),
        'texture_size': st.get('size'),
        'textures': tex,
        'textures_side': files(src + '_side') if m.get('side') else None,
        'side_blend': 'w_top = smoothstep(0.5, 0.8, world_normal.y)' if m.get('side') else None,
        'macro': {'texture': f'{TEX_KTX_REL}/{L.MACRO["id"]}_base.ktx2', 'amount': c['MacroAmount'],
                  'repeat_m': L.MACRO['tile']} if c['MacroAmount'] > 0 or c['EmitMacro'] > 0 else None,
        'texture_sources_png': {k: '.scratch/matlib/tex/' + os.path.basename(v).replace('.ktx2', '.png')
                                for k, v in tex.items()},
        'srgb': {'base': True, 'orm': False, 'normal_height': False, 'emissive': True},
        'height_depth_m': m['depth'],
        'constants': consts,
        'emissive': em,
        'transparent': transparent,
        'volume': vol,
        'water': m.get('water'),
        'variants': {k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
                     for k, v in m.get('variants', {}).items()},
        'texture_source': {'origin': (('self-made Codex-painted plate %s, cut, de-lit and made seamless by periodic '
                                      'image quilting in tools/matlib/plates.py; height/roughness/masks derived '
                                      'from it (recipe library_defs.PLATES)' % m['source']) if m.get('plate') else
                                     'self-made procedural texture, tools/matlib/library_defs.py:%s, rendered to a '
                                     'seamless tile by tools/matlib/build_library.py' % m['pattern'].__name__),
                           'licence': 'self-made for this project (owner-approved); no third-party images',
                           'shared_with': m.get('tex_from')},
        'concept': m['concept'],
        'reference': m.get('ref'),
        'three': three,
        'stats': st,
    }
    return e


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    for d in (TEX_PNG, MIPS, BAKE_TMP, os.path.dirname(OUT_BLEND)):
        os.makedirs(d, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_tile()
    build_normal_xy()
    build_core()
    sets = texture_sets()
    for s in sets:
        build_pattern(s)
    stats = json.load(open(STATS)) if (SKIP_BAKE and os.path.exists(STATS)) else {}
    if not SKIP_BAKE:
        scene, cam, bmat = bake_setup()
        for s in sets:
            t = time.time()
            stats[s['sid']] = write_set(s, plate_px(s) if s.get('plate') else bake_set(scene, cam, bmat, s))
            log(f"baked {s['sid']:16s} {dims(s)}  {time.time() - t:5.1f}s  {stats[s['sid']]}")
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob)
        bpy.data.materials.remove(bmat)
        json.dump(stats, open(STATS, 'w'), indent=1)
    STATS_CACHE.update(stats)
    macro = load_image('kz_macro', os.path.join(TEX_PNG, 'kz_macro_base.png'), 'Non-Color')
    for m in L.MATERIALS:
        build_material(m, build_kzm(m, macro), stats.get(m.get('tex_from', m['id']), {}))
    for sc in list(bpy.data.scenes):
        sc.world = None
    for coll in (bpy.data.worlds, bpy.data.meshes, bpy.data.cameras):
        for x in list(coll):
            coll.remove(x)
    bpy.data.orphans_purge(do_recursive=True)
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.view_settings.view_transform = 'AgX'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    log('saved', OUT_BLEND)
    ktx_path = os.path.join(ROOT, '.scratch', 'matlib', 'ktx_status.json')
    ktx = json.load(open(ktx_path)) if os.path.exists(ktx_path) else {}
    set_list = []
    for s in sets:
        W, H = dims(s)
        kinds = ['base'] if s.get('macro') else ['base', 'orm', 'nh'] + (['emis'] if 'emissive_map_scale' in
                                                                        stats.get(s['sid'], {}) else [])
        set_list.append({'set': s['sid'], 'size': [W, H], 'files': {k: f"{TEX_KTX_REL}/{s['sid']}_{k}.ktx2" for k in kinds},
                         'srgb_base': not s.get('macro'), 'close_up': s['res'] >= 1024,
                         'orm_mips': stats.get(s['sid'], {}).get('orm_mip_levels'),
                         'ktx2': ktx.get(s['sid'], {'encoded': False})})
    manifest = {
        'version': VERSION,
        'generated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'generator': 'tools/matlib/build_library.py (Blender %s)' % bpy.app.version_string,
        'library_blend': 'materials/library.blend',
        'settings': SETTINGS,
        'colour_management': 'AgX (Blender) / AgXToneMapping (three.js); albedo/emissive textures sRGB, data linear',
        'ktx2': ktx.get('_tool', {'tool': 'KTX-Software ktx create', 'version': '4.4.2', 'encoded': False,
                                  'note': 'run tools/matlib/encode_ktx2.py'}),
        'kz_core': KZ_SHADER_DOC,
        'categories': [{'id': c[0], 'label': c[1],
                        'sheet_concept_crops': [{'image': im, 'box_fraction_ltrb': list(bx)} for im, bx in c[2]]}
                       for c in L.CATEGORIES],
        'texture_sets': set_list,
        'materials': [manifest_entry(m, stats) for m in L.MATERIALS],
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(manifest, f, indent=1)
    log('wrote', OUT_JSON, f'({len(manifest["materials"])} materials, {len(sets)} texture sets) in {time.time() - t0:.0f}s')


main()
