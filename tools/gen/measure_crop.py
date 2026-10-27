"""Measure a concept sheet against its scale bar with PIL (run with .venv/bin/python, the only Python here
that has PIL). Usage:
    .venv/bin/python .scratch/guide/measure_crop.py refs/gen/sheet-vs-bath-props.png 1030 490 1540 1020 out.png
It crops the panel (x0 y0 x1 y1), saves a 2x enlarged crop with a 50 px grid and pixel coordinates so you
can read off positions, and prints the px-per-metre once you tell it the two x pixels of the scale bar.
Workflow: 1) crop the panel, 2) read the scale-bar end pixels off the grid, 3) read the object's extents,
4) metres = pixels / px_per_m. Write the numbers into your generator docstring before you code."""
import sys

from PIL import Image, ImageDraw, ImageFont

src, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
bar = tuple(map(int, sys.argv[7:9])) if len(sys.argv) >= 9 else None       # scale bar x pixels (in the crop)
bar_m = float(sys.argv[9]) if len(sys.argv) >= 10 else 1.0                 # its length in metres
im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
S = 2
im = im.resize((im.width * S, im.height * S), Image.LANCZOS)
d = ImageDraw.Draw(im)
F = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', 12)
for x in range(0, im.width, 50 * S):
    d.line([(x, 0), (x, im.height)], fill=(255, 80, 80) if (x // S) % 100 == 0 else (120, 60, 60), width=1)
    d.text((x + 2, 2), str(x // S), fill=(255, 200, 200), font=F)
for y in range(0, im.height, 50 * S):
    d.line([(0, y), (im.width, y)], fill=(255, 80, 80) if (y // S) % 100 == 0 else (120, 60, 60), width=1)
    d.text((2, y + 2), str(y // S), fill=(255, 200, 200), font=F)
if bar:
    ppm = (bar[1] - bar[0]) / bar_m
    d.text((8, im.height - 20), f'scale bar {bar[0]}..{bar[1]} px = {bar_m} m  ->  {ppm:.1f} px/m', fill=(120, 255, 160), font=F)
    print(f'px_per_m = {ppm:.2f}; a 60 px span = {60 / ppm:.3f} m')
im.save(out)
print(out)
