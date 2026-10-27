"""Library previews, one JPEG per material (+ named variants), on one calibrated rig.

    /home/agent-tom/.local/bin/blender -b -P tools/matlib/render_previews.py [-- --only id,id --samples 256]

Stone, wood/paper/cloth, metal/ice/glass: a 1 m sphere and a 0.9 m swatch.
Water: a pool over basalt with bottom steps at 0.1 / 0.5 / 2.0 m depth (left to right),
white under-water fixtures, lantern reflections.  Light sources: a dark room, the emitter
0.3 m in front of a wall to show spill, subtle bloom.
Every image has an 18 % grey and a 4 % black card, the 2700 K lantern key (calibrated so
the grey card reads middle grey), a dim teal fill and a dome of lantern / glowworm dots to
reflect.  Materials come in through matlib.assign(), i.e. the shipped texture sets.
Output: 3d/renders/materials/<id>.jpg (800x520) and <id>__<variant>.jpg.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kzrig as R  # noqa: E402
import matlib  # noqa: E402

OUT = os.path.join(matlib.ROOT, '3d', 'renders', 'materials')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
SAMPLES = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 256
VARIANTS = [('neon_tube', 'cyan', {}), ('hinoki', 'dark_timber', {}), ('hinoki', None, dict(wear=0.7)),
            ('water_still', 'mirror', {}), ('basalt_dry', None, dict(wetness=0.5))]
SPHERE_C = Vector((-0.62, 0.0, 0.52))
SWATCH_C = Vector((0.62, 0.12, 0.47))


def base_rig(sc):
    """Floor, key, fill, cards, dots, camera (shared by every preview)."""
    floor = R.box('PV_Floor', (0, 2.0, -0.01), (14, 14, 0.02), R.simple_mat('PV_FloorMat', (0.03, 0.03, 0.032), 0.6))
    key = R.point('PV_Key', (-1.55, -1.75, 2.05), R.KEY_W, 0.08)
    fill = R.area('PV_Fill', (2.4, -0.9, 1.3), (0, 0, 0.5), R.FILL_W)
    cards = R.cards((1.3, -0.45, 0.16), (0.0, -3.55, 1.0))
    dots = R.env_dots()
    cam = R.camera(sc, (0.0, -3.55, 1.38), (0.02, 0, 0.42), lens=48)
    return dict(floor=floor, key=key, fill=fill, cards=cards, dots=dots, cam=cam)


def scene_sphere(mid, variant, params):
    sph = R.uv_sphere('PV_Sphere', SPHERE_C)
    sw = R.make_box('PV_Swatch', 0.9, 0.9, 0.05)
    sw.location = SWATCH_C
    sw.rotation_euler = (math.radians(62), 0, math.radians(-14))
    objs = [sph, sw]
    info = matlib.manifest()[mid]
    if info['transparent']:
        sw.scale.z = 4.0
        objs.append(R.box('PV_Pale', (0.0, 0.25, 0.012), (2.9, 1.6, 0.02),
                          R.simple_mat('PV_PaleMat', (0.35, 0.34, 0.31), 0.6)))
    for ob in (sph, sw):
        matlib.assign(ob, mid, variant=variant, **params)
    if mid == 'washi_backlit':
        objs.append(R.point('PV_Inner', SPHERE_C, 1.2, 0.04))
        objs.append(R.point('PV_Behind', SWATCH_C + sw.matrix_world.to_3x3() @ Vector((0, 0, -0.3)), 4.0, 0.2))
    return objs


def scene_pool(mid, variant, params):
    water = matlib.material('water_still' if mid == 'caustics_decal' else
                            ('water_river' if mid == 'waterfall' else mid), variant=variant, **params)
    objs = R.stepped_pool(water, matlib.material('basalt_dry'), matlib.material('basalt_wet'),
                          x0=-1.5, y0=0.3, y1=2.3)
    if mid == 'caustics_decal':
        for i, d in enumerate((0.1, 0.5)):
            dec = R.box(f'PV_Caustic{i}', (-1.0 + i, 1.3, -d + 0.002), (0.98, 1.98, 0.001), bevel=0.0)
            matlib.assign(dec, mid)
            objs.append(dec)
    if mid == 'waterfall':
        wall = R.box('PV_FallWall', (0, 2.62, 0.8), (3.6, 0.2, 2.2))
        matlib.assign(wall, 'basalt_wet')
        sheet = R.make_box('PV_Fall', 1.6, 0.02, 1.6, bevel=0.0)
        sheet.location = (0.0, 2.45, 0.8)
        matlib.assign(sheet, mid)
        objs += [wall, sheet]
    return objs


def scene_emissive(mid, variant, params):
    objs = [R.box('PV_DarkWall', (0, 0.62, 1.2), (4.0, 0.1, 2.6), R.neutral())]
    if mid in ('lava', 'lava_flow'):
        p = R.box('PV_Panel', (0.0, 0.3, 0.75), (1.8, 0.05, 1.2))
        p.rotation_euler.x = math.radians(90) * 0
        matlib.assign(p, mid, variant=variant, **params)
        objs.append(p)
    elif mid == 'neon_tube':
        y, r = 0.30, 0.016
        pts = [(math.cos(a) * 0.32 - 0.45, y, math.sin(a) * 0.32 + 0.9) for a in
               [i * 2 * math.pi / 24 for i in range(25)]]
        for i in range(24):
            c = R.cylinder(f'PV_NeonC{i}', pts[i], pts[i + 1], r, seg=16)
            matlib.assign(c, mid, variant=variant, **params)
            objs.append(c)
        for i, (a, b) in enumerate((((0.15, y, 0.55), (0.15, y, 1.3)), ((0.15, y, 1.3), (0.75, y, 1.3)),
                                    ((0.45, y, 0.55), (0.45, y, 1.3)))):
            c = R.cylinder(f'PV_NeonS{i}', a, b, r, seg=16)
            matlib.assign(c, mid, variant=variant, **params)
            objs.append(c)
    elif mid == 'lantern_paper':
        c = R.cylinder('PV_Lantern', (-0.35, 0.32, 0.35), (-0.35, 0.32, 1.0), 0.24, uv='object')
        matlib.assign(c, mid, variant=variant, **params)
        objs.append(c)
        c2 = R.cylinder('PV_Lantern2', (0.45, 0.32, 0.25), (0.45, 0.32, 0.65), 0.15, uv='object')
        matlib.assign(c2, mid, variant=variant, **params)
        objs.append(c2)
    elif mid == 'lantern_andon':
        for i, (x, s) in enumerate(((-0.35, 0.3), (0.45, 0.22))):
            b = R.box(f'PV_Andon{i}', (x, 0.3, 0.2 + s * 0.9), (s, s, s * 1.6), uv='face', bevel=0.0)
            matlib.assign(b, mid, variant=variant, **params)
            objs.append(b)
    return objs


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = R.setup_scene((800, 520), SAMPLES)
    rig = base_rig(sc)
    jobs = [(mid, None, {}) for mid in matlib.manifest()] + VARIANTS
    for mid, variant, params in jobs:
        if ONLY and mid not in ONLY:
            continue
        info = matlib.manifest()[mid]
        cat = info['category']
        emissive_scene = cat == 'light'
        pool = cat == 'water'
        if pool:
            objs = scene_pool(mid, variant, params)
            rig['cam'].location = (0.0, -2.1, 1.55)
            rig['cam'].rotation_euler = (Vector((0.0, 1.3, -0.35)) - rig['cam'].location).to_track_quat('-Z', 'Y').to_euler()
        elif emissive_scene:
            objs = scene_emissive(mid, variant, params)
            rig['cam'].location = (0.0, -2.6, 1.15)
            rig['cam'].rotation_euler = (Vector((0.05, 0.3, 0.8)) - rig['cam'].location).to_track_quat('-Z', 'Y').to_euler()
        else:
            objs = scene_sphere(mid, variant, params)
            rig['cam'].location = (0.0, -3.55, 1.38)
            rig['cam'].rotation_euler = (Vector((0.02, 0, 0.42)) - rig['cam'].location).to_track_quat('-Z', 'Y').to_euler()
        rig['floor'].location.z = -2.4 if pool else -0.01      # the floor would cap the pool
        rig['key'].data.energy = R.KEY_W * (0.12 if emissive_scene else 1.0)
        rig['fill'].data.energy = R.FILL_W * (0.3 if emissive_scene else 1.0)
        for c, x in zip(rig['cards'], (-0.12, 0.12)):
            c.location = (x, -0.75, 0.14) if not pool else (x - 1.75, 0.0, 0.18)
        R.bloom(sc, emissive_scene)
        tag = '' if not (variant or params) else '__' + (variant or '_'.join(f'{k}{v}' for k, v in params.items()))
        sc.render.filepath = os.path.join(OUT, mid + tag + '.jpg')
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f'[preview] {mid + tag:26s} {time.time() - t:5.1f}s', flush=True)
        R.clear(objs)
    dup = [ng.name for ng in bpy.data.node_groups if '.0' in ng.name]
    print('[preview] node groups:', len(bpy.data.node_groups), 'duplicates:', dup, flush=True)


if __name__ == '__main__':
    main()
