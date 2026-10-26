"""Render walk-check maps per level from .scratch/checks/walk_nodes.npy (green reached, red not).
  .venv/bin/python checks/walk_map.py [--zoom x0 y0 x1 y1 zmin zmax name]"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = np.load(os.path.join(ROOT, '.scratch', 'checks', 'walk_nodes.npy'))
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
OUT = os.path.join(ROOT, '3d', 'renders', 'checks'); os.makedirs(OUT, exist_ok=True)
F = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Bold.ttf', 18)
def draw(name, x0, y0, x1, y1, zmin, zmax, px=7):
    W, H = int((x1 - x0) * px), int((y1 - y0) * px)
    im = Image.new('RGB', (W, H + 30), (15, 16, 18)); d = ImageDraw.Draw(im)
    for s in L['spaces']:
        if s['footprint'] and zmin - 1 <= s['floor_z'] <= zmax:
            d.polygon([((x - x0) * px, (y1 - y) * px) for x, y in s['footprint']], outline=(90, 90, 110))
    sel = A[(A[:, 2] >= zmin) & (A[:, 2] <= zmax)]
    for x, y, z, r in sel:
        c = (70, 220, 110) if r else (240, 70, 70)
        X, Y = (x - x0) * px, (y1 - y) * px
        d.rectangle([X - 1, Y - 1, X + 1, Y + 1], fill=c)
    d.text((8, H + 4), f'walk {name}: z {zmin}..{zmax}  green = reachable from the Basalt Gate on foot, red = not', fill=(255, 255, 255), font=F)
    im.save(os.path.join(OUT, f'walk-{name}.jpg'), quality=85)
if '--zoom' in sys.argv:
    a = sys.argv[sys.argv.index('--zoom') + 1:]
    draw(a[6], *map(float, a[:6]), px=20)
else:
    for name, zmin, zmax in (('summit', 100, 130), ('cliff', 5, 99), ('ground', -6, 4.9), ('b1', -26, -10), ('b2', -46, -27), ('b3', -72, -47), ('b4', -101, -88)):
        draw(name, -10, 0, 210, 122, zmin, zmax)
    print('maps written')
