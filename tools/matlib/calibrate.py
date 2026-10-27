"""Measure library materials as rendered swatches under a warm 2700 K key and a neutral 5000 K key.

    blender -b -P tools/matlib/calibrate.py -- id[:variant],id[:variant],...

One 0.5 m panel at the origin (so world-space macro variation is identical for every item), metric UVs,
lit by a sun from the camera side (strength KZ_CAL_K, default 4 W/m^2: an 18 % card reads ~#897a6f under
the neutral key), AgX.  Prints the mean sRGB hex of the panel centre (alpha cards: the brighter half of a
larger crop) for both keys.
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kzrig as R  # noqa: E402
import matlib  # noqa: E402

items = sys.argv[sys.argv.index('--') + 1].split(',')
sc = R.setup_scene((120, 120), 64)
sc.render.image_settings.file_format = 'PNG'
p = R.box('P', (0.0, 0.0, 0.0), (0.5, 0.05, 0.5), bevel=0.0)
R.camera(sc, (0, -6.0, 0), (0, 0, 0), ortho=0.6)
kd = bpy.data.lights.new('Key', 'SUN'); kd.energy = float(os.environ.get('KZ_CAL_K', '6.0')); kd.angle = 0.05
key = R.link(bpy.data.objects.new('Key', kd)); key.rotation_euler = (0.8, 0.0, -0.8)   # 45 deg off-axis: little mirror specular in the patch
out = os.path.join(matlib.ROOT, '.scratch', 'matlib', 'calib_tmp.png')
for it in items:
    mid, _, var = it.partition(':')
    p.data.materials.clear()
    for o in [o for o in bpy.data.objects if o.name.startswith('GLOWBG')]:
        bpy.data.objects.remove(o)
    if var == 'overglow':                                   # glass in front of an orange glow plane
        var = ''
        g = R.box('GLOWBG', (0.0, 0.6, 0.0), (1.0, 0.02, 1.0), R.simple_mat('CAL_glow', (0, 0, 0), 1.0,
                  emission=(1.0, 0.35, 0.05), strength=2.0), bevel=0.0)
    if mid == 'card18':
        p.data.materials.append(R.simple_mat('CAL_18', (0.18, 0.18, 0.18), 0.7))
    else:
        matlib.assign(p, mid, variant=var or None)
    res = {}
    for tag, col in (('warm', R.LANTERN), ('neutral', R.NEUTRAL)):
        key.data.color = col
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(out, check_existing=False)
        W, H = im.size
        a = np.array(im.pixels[:]).reshape(H, W, 4)[:, :, :3]
        bpy.data.images.remove(im)
        if mid in ('foliage_fern', 'blossom', 'foliage_pine', 'maple_leaf'):
            blk = a[20:100, 20:100].reshape(-1, 3)
            l = blk.mean(1)
            c = blk[l >= np.percentile(l, 88)].mean(0)
        else:
            c = a[45:75, 45:75].reshape(-1, 3).mean(0)
        res[tag] = '#' + ''.join(f'{int(round(min(max(v, 0), 1) * 255)):02x}' for v in c)
    print(f'CAL {it:28s} warm {res["warm"]}  neutral {res["neutral"]}', flush=True)
