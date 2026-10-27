"""Render graybox views with Eevee.

  blender -b 3d/blend/graybox.blend -P tools/graybox/render_views.py -- --set overview|plans|spaces [--space id ...] [--outdir 3d/renders/graybox]

Views:
  overview   two cutaway isometrics of the whole site (terrain hidden / shown)
  plans      top-down orthographic per level (camera just under that level's ceiling)
  spaces     entry / reveal / concept cameras from 3d/spaces/<id>.json at 16:9 and 9:16
Each space render gets temporary point lights at its lantern rules' rough positions so the graybox is readable.
"""
import bpy, json, math, os, sys, glob
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None, many=False):
    if k not in argv:
        return d
    i = argv.index(k)
    if many:
        out = []
        for a in argv[i + 1:]:
            if a.startswith('--'):
                break
            out.append(a)
        return out
    return argv[i + 1]
SET = arg('--set', 'overview')
OUTDIR = os.path.join(ROOT, arg('--outdir', '3d/renders/graybox'))
ONLY = arg('--space', None, many=True)
os.makedirs(OUTDIR, exist_ok=True)
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
sc = bpy.context.scene


def setup():
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 88
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.eevee.taa_render_samples = 32
    sc.view_settings.exposure = 0.0
    try:
        sc.eevee.use_raytracing = True
    except Exception:
        pass
    w = bpy.data.worlds.new('gb_world'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.02, 0.025, 0.035, 1); bg.inputs['Strength'].default_value = 1.0
    # apply solidify etc. are kept as modifiers; fine for render


def cam(name, pos, target, fov_v=60, ortho=None, w=1600, h=900, clip=(0.1, 2000)):
    c = bpy.data.cameras.new(name); o = bpy.data.objects.new(name, c); sc.collection.objects.link(o)
    o.location = Vector(pos)
    d = Vector(target) - Vector(pos)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    c.clip_start, c.clip_end = clip
    sc.render.resolution_x, sc.render.resolution_y = w, h
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.sensor_fit = 'VERTICAL'; c.sensor_height = 24.0
        c.lens = 12.0 / math.tan(math.radians(fov_v) / 2)
    sc.camera = o
    return o


def light(pos, energy, color=(1.0, 0.72, 0.42), r=0.3, kind='POINT'):
    l = bpy.data.lights.new('gb_l', kind); l.energy = energy; l.color = color
    l.specular_factor = 0.0 if energy < 300 and color[2] > 0.8 else 1.0      # soft fills must not show as discs on water
    if kind == 'POINT':
        l.shadow_soft_size = r
    o = bpy.data.objects.new('gb_l', l); o.location = pos; sc.collection.objects.link(o)
    return o


def hide(names, state=True):
    for c in bpy.data.collections:
        if c.name in names:
            c.hide_render = state


def render(path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('WROTE', path)


def level_lights():
    """one warm light per enclosed space plus lava glow, so graybox renders read"""
    out = []
    for s in L['spaces']:
        if not s['footprint']:
            continue
        xs = [p[0] for p in s['footprint']]; ys = [p[1] for p in s['footprint']]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        top = s['ceiling_z'] if s['ceiling_z'] is not None else s['floor_z'] + 6
        z = s['floor_z'] + min(4.0, (top - s['floor_z']) * 0.6)
        out.append(light((cx, cy, z), min(250, 0.25 * area), r=max(6.0, area ** 0.5 * 0.4), color=(0.8, 0.8, 0.85)))   # very soft fill; lanterns + heroes carry the scene
    out.append(light((61, 78, 6), 6000, (1.0, 0.35, 0.08), r=6))
    out.append(light((80, 10, -96), 8000, (1.0, 0.35, 0.08), r=10))
    out.append(light((150, 50, -40), 3000, (1.0, 0.4, 0.1), r=4))
    return out


def overview():
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 2.0; sun.color = (0.7, 0.75, 0.95)
    so = bpy.data.objects.new('sun', sun); so.rotation_euler = (math.radians(50), 0, math.radians(30)); sc.collection.objects.link(so)
    level_lights()
    hide(['terrain'], True)
    cam('ov_se', (330, -190, 140), (100, 60, -30), 32, w=1600, h=1000, clip=(1, 3000))
    render(os.path.join(OUTDIR, 'overview-cutaway-se.jpg'))
    cam('ov_s', (100, -260, 10), (100, 60, -20), 30, w=1600, h=1000, clip=(150, 3000))   # section-like: clip into the mountain
    render(os.path.join(OUTDIR, 'overview-section-south.jpg'))
    hide(['terrain'], False)
    cam('ov_site', (340, -230, 280), (90, 60, 30), 30, w=1600, h=1000, clip=(1, 3000))
    render(os.path.join(OUTDIR, 'overview-site.jpg'))


def plans():
    level_lights()
    hide(['terrain'], True)
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 1.5
    so = bpy.data.objects.new('sun', sun); so.rotation_euler = (0.2, 0.1, 0); sc.collection.objects.link(so)
    for lv in L['levels']:
        if lv['id'] == 'summit':
            hide(['terrain'], False)
            z = 200
        else:
            z = (lv['ceiling_z'] if lv['ceiling_z'] is not None else lv['floor_z'] + 8) - 0.8
            hide(['terrain'], True)
        depth = (z - lv['floor_z'] + 3.0) if lv['id'] != 'summit' else 400
        c = cam(f"plan_{lv['id']}", (100, 60, z), (100, 60, z - 10), ortho=212, w=1600, h=960, clip=(0.05, depth))
        c.rotation_euler = (0, 0, 0)
        render(os.path.join(OUTDIR, f"plan-{lv['id']}.jpg"))


def spaces():
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'assembly'))
    from spaces_io import load_spaces
    for sid_, sp in sorted(load_spaces(ROOT).items()):
        if ONLY and sp['id'] not in ONLY:
            continue
        if 'cameras' not in sp:
            continue
        lights = level_lights()
        outdoor = sp.get('level') in ('ground', 'summit', 'cliff')
        hide(['terrain'], not outdoor)
        sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.02, 0.045, 1) if outdoor else (0.02, 0.025, 0.035, 1)
        sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.6 if outdoor else 1.0
        if outdoor:      # moonlight so the sea, surf and cliffs read at night
            mo = bpy.data.lights.new('moon', 'SUN'); mo.energy = 0.35; mo.color = (0.6, 0.7, 1.0); mo.angle = 0.02
            moo = bpy.data.objects.new('moon', mo); moo.rotation_euler = (math.radians(55), 0, math.radians(120)); sc.collection.objects.link(moo)
            lights.append(moo)
        for k, cdef in sp['cameras'].items():
            if not isinstance(cdef, dict) or 'pos' not in cdef or 'target' not in cdef:
                continue                 # every declared camera is rendered (entry/reveal/concept go on the sheet)
            for tag, (w, h) in (('16x9', (1280, 720)), ('9x16', (540, 960))):
                cam(f'{sp["id"]}_{k}', cdef['pos'], cdef['target'], cdef.get('fov_v', 60), w=w, h=h)
                render(os.path.join(OUTDIR, sp['id'], f'{k}-{tag}.jpg'))
        # 8-frame walk strip along the spine at eye height, looking ahead
        spine = [q if len(q) == 3 else [q[0], q[1], sp['floor_z']] for q in (sp.get('spine') or [])]
        if len(spine) >= 2:
            segs = [(Vector(a), Vector(b)) for a, b in zip(spine, spine[1:])]
            tot = sum((b - a).length for a, b in segs)
            def at(t):
                acc = 0.0
                for a, b in segs:
                    l = (b - a).length
                    if acc + l >= t or (a, b) == segs[-1]:
                        return a + (b - a) * min(1.0, max(0.0, (t - acc) / l if l else 0))
                    acc += l
                return segs[-1][1]
            for k in range(8):
                t = tot * (k + 0.5) / 8
                p0 = at(t); p1 = at(min(tot, t + 3.0))
                if (p1 - p0).length < 0.1:
                    p1 = p0 + (at(tot) - at(max(0, tot - 1))).normalized() * 3
                eye = Vector((p0.x, p0.y, p0.z + 1.6)); tgt = Vector((p1.x, p1.y, p1.z + 1.5))
                cam(f'{sp["id"]}_strip{k}', eye, tgt, 62, w=480, h=270)
                render(os.path.join(OUTDIR, sp['id'], f'strip-{k}.jpg'))
        for o in lights:
            bpy.data.objects.remove(o)


setup()
{'overview': overview, 'plans': plans, 'spaces': spaces}[SET]()
