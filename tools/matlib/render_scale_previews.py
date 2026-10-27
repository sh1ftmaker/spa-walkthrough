"""Real-scale previews of every library material (round 2 rig).

    /home/agent-tom/.local/bin/blender -b -P tools/matlib/render_scale_previews.py [-- --only id,id --samples 192 --skip close,repeat,context]

Outputs (3d/renders/materials/...):
  scale/<id>.jpg          corner at real UV scale with a NEUTRAL 18 % grey surround: 6 m wide x 3 m
                          wall, 4 m deep floor, 0.5 m step; eye 1.6 m, 3.4 m from the wall, 20 mm
  scale/<id>__context.jpg the same corner in context: wet basalt walls, worn paving floor
  close/<id>.jpg          0.6 m patch under one raking lantern (micro detail)
  repeat/<id>.jpg         10 x 10 m top-down orthographic view (big-area materials) for repetition
Light: three 2700 K lanterns (key calibrated to the 18 % grey card, see kzrig) + dim teal fill +
a lantern-sized point light 0.3 m above the floor; 18 % grey and 4 % black cards on the floor;
a dome of lantern / glowworm dots to reflect.  Water: stepped pool (0.1 / 0.5 / 2 m).
Light sources: dark room with bloom.  Materials come in through matlib.assign(), i.e. the
shipped 512/1024 px texture sets.
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

BASE = os.path.join(matlib.ROOT, '3d', 'renders', 'materials')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
SAMPLES = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 64
SKIP = set(argv[argv.index('--skip') + 1].split(',')) if '--skip' in argv else set()
WIDTH = 6.0
REPEAT = ['basalt_dry', 'basalt_wet', 'obsidian', 'rimstone', 'black_sand', 'ash_clay', 'paving', 'lava',
          'lava_flow', 'water_still', 'water_sea', 'hinoki', 'tatami']


def assign(ob, mid):
    if mid is None:
        ob.data.materials.append(R.neutral())
    else:
        matlib.assign(ob, mid)
    return ob


def corner(wall, floor, step):
    w = assign(R.box('S_Wall', (0, 4.1, 1.5), (WIDTH, 0.2, 3.0)), wall)
    f = assign(R.box('S_Floor', (0, 2.0, -0.05), (WIDTH, 4.0, 0.1)), floor)
    s = assign(R.box('S_Step', (0.9, 3.65, 0.25), (2.2, 0.7, 0.5)), step)
    return [w, f, s]


def setup_for(mid, cat, ctx):
    """Material on the surfaces that suit it; surround = neutral (ctx False) or context."""
    W = 'basalt_wet' if ctx else None
    F = 'paving' if ctx else None
    if cat == 'stone':
        if mid == 'black_sand':
            return corner(W, mid, W)
        if mid == 'paving':
            return corner(W, mid, W)
        return corner(mid, mid, mid)
    if mid in ('water_still', 'water_river', 'water_sea', 'caustics_decal', 'waterfall'):
        obs = [assign(R.box('S_Wall', (0, 4.1, 1.5), (WIDTH, 0.2, 3.0)), W),
               assign(R.box('S_Floor', (0, 0.4, -0.05), (WIDTH, 1.6, 0.1)), F)]
        water = matlib.material('water_still' if mid == 'caustics_decal' else
                                ('water_river' if mid == 'waterfall' else mid))
        obs += R.stepped_pool(water, matlib.material('basalt_dry'), matlib.material('basalt_wet'),
                              x0=-1.5, y0=1.4, y1=3.9)
        if mid == 'caustics_decal':
            for i, d in enumerate((0.1, 0.5)):
                dec = R.box(f'S_Caustic{i}', (-1.0 + i, 2.65, -d + 0.002), (0.98, 2.48, 0.001), bevel=0.0)
                matlib.assign(dec, mid)
                obs.append(dec)
        if mid == 'waterfall':
            sheet = R.make_box('S_Fall', 2.2, 0.02, 3.0, bevel=0.0)
            sheet.location = (0, 3.86, 1.5)
            matlib.assign(sheet, mid)
            obs.append(sheet)
        return obs
    if mid in ('hinoki', 'lacquer_dark', 'iron', 'bronze'):
        return corner(mid, mid, mid)
    if mid == 'tatami':
        return corner('washi' if ctx else None, mid, 'hinoki' if ctx else None)
    if mid == 'washi':
        return corner(mid, 'hinoki' if ctx else None, 'hinoki' if ctx else None)
    if mid == 'bamboo':
        obs = corner(W, F, W)
        for i in range(30):
            x = -1.9 + i * 0.13
            c = R.cylinder(f'S_Bamboo{i}', (x, 3.92, 0.0), (x, 3.92, 2.2), 0.055 + 0.01 * ((i * 7) % 3))
            for d in c.data.uv_layers[0].data:        # bamboo wants u around, v along; random v offset per pole
                d.uv = (d.uv[1], d.uv[0] + 0.37 * i)
            matlib.assign(c, mid)
            obs.append(c)
        return obs
    if mid == 'rope':
        obs = corner(W, F, 'hinoki' if ctx else None)
        for nm, a, b, r in (('S_Rope', (-1.9, 3.82, 2.25), (1.9, 3.82, 2.25), 0.12),
                            ('S_Rope2', (-0.3, 3.4, 0.62), (2.0, 3.4, 0.62), 0.08)):
            obs.append(assign(R.cylinder(nm, a, b, r), mid))
        return obs
    if mid == 'noren':
        obs = corner(W, F, 'hinoki' if ctx else None)
        obs.append(assign(R.box('S_Lintel', (0, 3.7, 2.15), (3.6, 0.12, 0.12)), 'lacquer_dark'))
        for i in range(3):
            obs.append(assign(R.box(f'S_Noren{i}', (-1.2 + i * 1.2, 3.62, 1.5), (1.15, 0.012, 1.2)), mid))
        return obs
    if mid == 'washi_backlit':
        obs = corner(W, F, 'hinoki' if ctx else None)
        for i in range(3):
            p = assign(R.box(f'S_Shoji{i}', (-1.6 + i * 0.95, 3.85, 1.25), (0.9, 0.02, 1.8)), mid)
            obs.append(p)
            obs.append(R.point(f'S_ShojiLamp{i}', (-1.6 + i * 0.95, 3.97, 1.25), 6.0, 0.3))
        return obs
    if mid in ('lantern_paper', 'lantern_andon'):
        obs = corner(W, F, 'hinoki' if ctx else None)
        for i, (x, y, z, r, h) in enumerate(((0.4, 3.55, 0.5, 0.2, 0.55), (-1.2, 2.6, 0.0, 0.26, 0.75),
                                             (1.6, 2.2, 0.0, 0.16, 0.45))):
            if mid == 'lantern_paper':
                c = R.cylinder(f'S_Lantern{i}', (x, y, z), (x, y, z + h), r, uv='object')
            else:
                c = R.box(f'S_Andon{i}', (x, y, z + h / 2), (r * 1.6, r * 1.6, h), uv='face', bevel=0.0)
            obs.append(assign(c, mid))
        return obs
    if mid == 'glacier_ice':
        return corner(mid, 'basalt_wet' if ctx else None, mid)
    if mid == 'lava_glass':
        obs = corner(None, F, W)
        obs[0].location.y = 4.8
        matlib.assign(obs[0], 'lava_flow')
        obs.append(assign(R.box('S_Glass', (0, 4.05, 1.5), (WIDTH, 0.15, 3.0)), mid))
        for i in range(4):
            obs.append(assign(R.box(f'S_Mullion{i}', (-2.25 + i * 1.5, 3.95, 1.5), (0.08, 0.08, 3.0)), 'iron'))
        return obs
    if mid in ('lava', 'lava_flow'):
        return corner(mid, F, W)
    if mid == 'neon_tube':
        obs = corner(W, F, W)
        y = 3.96
        segs = [((-0.7, y, 1.4), (0.7, y, 1.4)), ((0.7, y, 1.4), (0.7, y, 2.3)), ((0.7, y, 2.3), (-0.7, y, 2.3)),
                ((-0.7, y, 2.3), (-0.7, y, 1.4)), ((-0.35, y, 1.6), (0.0, y, 2.15)), ((0.0, y, 2.15), (0.35, y, 1.6))]
        for i, (a, b) in enumerate(segs):
            obs.append(assign(R.cylinder(f'S_Neon{i}', a, b, 0.016, seg=16), mid))
        return obs
    return corner(mid, mid, mid)


def corner_rig(sc):
    lights = [R.point('S_Key1', (-1.7, 1.2, 2.7), R.KEY_W * 0.75, 0.08, color=R.NEUTRAL),
              R.point('S_Key2', (1.9, 1.6, 2.5), R.KEY_W * 0.35, 0.08),
              R.point('S_Key3', (-2.4, 3.2, 1.8), R.KEY_W * 0.25, 0.06),
              R.point('S_FloorLantern', (1.9, 2.45, 0.3), 25.0),
              *R.teal_points('S_Fill', (2.6, 1.0, 1.8), (0, 3.5, 0.6), R.FILL_W * 3.0, spread=0.8)]
    cardobs = R.cards((-1.55, 2.75, 0.15), (0.15, 0.6, 1.6))
    dots = R.env_dots(center=(0, 2.0, 1.5), radius=9.0)
    cam = R.camera(sc, (0.15, 0.6, 1.6), (0.0, 4.0, 0.75), lens=20)
    return lights + cardobs + dots + [cam]


def render(sc, path):
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[scale] {os.path.relpath(path, BASE):34s} {time.time() - t:5.1f}s', flush=True)


def close_view(sc, mid, info):
    """0.6 m patch, raking lantern from the left, camera 0.55 m away."""
    objs = []
    p = R.box('C_Patch', (0, 0, 0.0), (0.8, 0.8, 0.02), bevel=0.0)
    matlib.assign(p, mid)
    objs.append(p)
    if info['transparent'] and info['category'] == 'water':
        under = R.box('C_Under', (0, 0, -0.16), (0.8, 0.8, 0.02), matlib.material('basalt_dry'), bevel=0.0)
        p.scale.z = 7.0
        p.location.z = -0.06
        objs.append(under)
    objs += [R.point('C_Rake', (-0.9, -0.1, 0.12), R.KEY_W * 0.12, 0.03, color=R.NEUTRAL),
             R.point('C_Top', (0.3, -0.6, 0.9), R.KEY_W * 0.06, 0.05),
             R.area('C_Soft', (0.0, -0.3, 1.2), (0, 0, 0), R.KEY_W * 0.08, size=(1.2, 1.2), color=R.NEUTRAL),
             R.area('C_Fill', (0.8, -0.5, 0.5), (0, 0, 0), R.FILL_W * 0.2, size=(0.6, 0.4))]
    objs += R.env_dots(center=(0, 0, 0.3), radius=3.0, warm=20, cyan=40)
    cam = R.camera(sc, (0.0, -0.42, 0.36), (0.0, 0.0, 0.0), lens=50)
    objs.append(cam)
    return objs


def repeat_view(sc, mid, info):
    objs = []
    p = R.box('R_Plane', (0, 0, 0), (10.0, 10.0, 0.02), bevel=0.0)
    matlib.assign(p, mid)
    objs.append(p)
    if info['category'] == 'water':
        p.scale.z = 25.0
        p.location.z = -0.25
        objs.append(R.box('R_Under', (0, 0, -0.52), (10, 10, 0.02), matlib.material('basalt_dry'), bevel=0.0))
        objs.append(R.area('R_UL', (0, 0, -0.03), (0, 0, -1), 900.0, size=(10, 10), color=(1, 1, 1)))
    objs += [R.area('R_Top', (2.0, -3.0, 8.0), (0, 0, 0), R.KEY_W * 2.2, size=(6, 6), color=R.LANTERN),
             R.area('R_Fill', (-6.0, 4.0, 5.0), (0, 0, 0), R.FILL_W * 6, size=(4, 4))]
    cam = R.camera(sc, (0, 0, 20.0), (0, 0, 0), ortho=10.0)
    objs.append(cam)
    return objs


def main():
    sc = R.setup_scene((1200, 675), SAMPLES)
    for d in ('scale', 'close', 'repeat'):
        os.makedirs(os.path.join(BASE, d), exist_ok=True)
    man = matlib.manifest()
    rig = corner_rig(sc)
    cam = sc.camera
    for mid, info in man.items():
        if ONLY and mid not in ONLY:
            continue
        light = info['category'] == 'light'
        R.bloom(sc, light)
        for k in ('S_Key1', 'S_Key2', 'S_Key3'):
            bpy.data.objects[k].data.energy = (R.KEY_W * {'S_Key1': 0.75, 'S_Key2': 0.35, 'S_Key3': 0.25}[k]
                                               * (0.15 if light else 1.0))
        for ctx in ((False, True) if 'context' not in SKIP else (False,)):
            objs = setup_for(mid, info['category'], ctx)
            if ctx:   # drop the context shot when the material already covers wall, floor and step
                own = [o for o in objs if o.type == 'MESH' and o.data.materials and o.data.materials[0]
                       and o.data.materials[0].get('kz_id') == mid]
                if {o.name for o in own} >= {'S_Wall', 'S_Floor', 'S_Step'}:
                    R.clear(objs)
                    continue
            sc.camera = cam
            render(sc, os.path.join(BASE, 'scale', mid + ('__context' if ctx else '') + '.jpg'))
            R.clear(objs)
    R.bloom(sc, False)
    for ob in rig:
        ob.hide_render = True
    sc.render.resolution_x, sc.render.resolution_y = 1000, 600
    for mid, info in man.items():
        if ONLY and mid not in ONLY:
            continue
        if 'close' not in SKIP and info['uv_mode'] == 'metric':
            objs = close_view(sc, mid, info)
            render(sc, os.path.join(BASE, 'close', mid + '.jpg'))
            R.clear(objs)
    sc.render.resolution_x, sc.render.resolution_y = 800, 800
    for mid in REPEAT:
        if 'repeat' in SKIP or (ONLY and mid not in ONLY):
            continue
        objs = repeat_view(sc, mid, man[mid])
        render(sc, os.path.join(BASE, 'repeat', mid + '.jpg'))
        R.clear(objs)


main()
