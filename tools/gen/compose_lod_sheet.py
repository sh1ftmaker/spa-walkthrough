"""Label the raw LOD render (venv python): .venv/bin/python tools/gen/compose_lod_sheet.py <asset>"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A = sys.argv[1]
J = json.load(open(os.path.join(ROOT, '.scratch', f'lod_{A}.json')))
F = lambda n, b=False: ImageFont.truetype('/usr/share/fonts/noto/NotoSans-%s.ttf' % ('Bold' if b else 'Regular'), n)
raw = Image.open(J['raw']).convert('RGB')
W = 1600
sheet = Image.new('RGB', (W, raw.height + 120), (16, 17, 19)); d = ImageDraw.Draw(sheet)
sheet.paste(raw, (0, 60))
d.text((12, 12), f'{A} — LOD0..3 (rows) x seeds {J["seeds"]} (columns)', fill=(235, 235, 230), font=F(22, True))
y = 70
for lod in range(4):
    row = [g for g in J['grid'] if g[0] == lod]
    d.text((12, 60 + lod * raw.height / 4 + 8), f'LOD{lod}', fill=(242, 166, 74), font=F(20, True))
    for k, (l, s, t, pr) in enumerate(row):
        x = 30 + k * (raw.width - 60) / len(J['seeds'])
        d.text((x + 50, 60 + (lod + 1) * raw.height / 4 - 30), f'seed {s}: {t} tris' + (' ⚠' if pr else ''), fill=(255, 90, 90) if pr else (150, 210, 160), font=F(15))
x0 = raw.width + 20
d.text((x0, 70), 'phone-size recognition (390x844)', fill=(235, 235, 230), font=F(16, True))
for i, (lod, mode, f) in enumerate(J['phone']):
    im = Image.open(f).convert('RGB'); im.thumbnail((180, 390))
    sheet.paste(im, (x0 + (i % 2) * 190, 100 + (i // 2) * 420))
    d.text((x0 + (i % 2) * 190, 100 + (i // 2) * 420 + im.height + 2), f'LOD{lod} {mode} @ {J["switch"][str(lod)]:.0f} m', fill=(150, 150, 150), font=F(12))
probs = [f'LOD{l} s{s}: ' + '; '.join(pr) for l, s, t, pr in J['grid'] if pr]
d.text((12, raw.height + 66), ('PROBLEMS: ' + ' | '.join(probs))[:220] if probs else 'proxy fit + budgets: OK', fill=(255, 90, 90) if probs else (95, 211, 141), font=F(15, True))
out = os.path.join(ROOT, '3d', 'renders', 'lod', A, 'sheet.jpg'); sheet.save(out, quality=86); print(out)
