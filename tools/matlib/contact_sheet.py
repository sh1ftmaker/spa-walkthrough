"""Contact sheet of the material previews, by category, with the concept crops they came from.

    python3 tools/matlib/contact_sheet.py        (needs ImageMagick 7 `magick`)

Reads 3d/materials.json + 3d/renders/materials/<id>.jpg, writes 3d/renders/materials/sheet.jpg
(1600 px wide).  Variant renders (<id>__<tag>.jpg) are placed after their base material.
"""
import glob
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
REN = os.path.join(ROOT, '3d', 'renders', 'materials')
TMP = os.path.join(ROOT, '.scratch', 'matlib', 'sheet')
W, CROPW, THW, PER_ROW, GAP = 1600, 300, 252, 5, 6
BG, FG, DIM = '#101010', '#e6e0d6', '#9a9284'
FONT, BOLD = 'Liberation-Sans', 'Liberation-Sans-Bold'


def mk(*args):
    args = list(map(str, args))
    subprocess.run(['magick', *args[:-1], '+repage', args[-1]], check=True)


def label(text, w, h, size, font=FONT, color=FG, gravity='center'):
    return ['(', '-size', f'{w}x{h}', '-background', BG, '-fill', color, '-font', font, '-pointsize', size,
            '-gravity', gravity, f'label:{text}', ')']


def main():
    os.makedirs(TMP, exist_ok=True)
    man = json.load(open(os.path.join(ROOT, '3d', 'materials.json')))
    blocks = []
    mk('-size', f'{W}x64', f'xc:{BG}', '-fill', FG, '-font', BOLD, '-pointsize', 28, '-gravity', 'west',
       '-annotate', '+20+0', 'Kazan-yu material library', '-fill', DIM, '-font', FONT, '-pointsize', 15,
       '-gravity', 'east', '-annotate', '+20+0',
       'Cycles + OptiX, AgX  |  one 2700 K lantern + dim teal fill  |  sphere r = 0.5 m, swatch 0.9 m',
       os.path.join(TMP, 'title.png'))
    blocks.append(os.path.join(TMP, 'title.png'))
    for cat in man['categories']:
        items = []
        for m in man['materials']:
            if m['category'] != cat['id']:
                continue
            items.append((m['id'], m['name']))
            for v in sorted(glob.glob(os.path.join(REN, m['id'] + '__*.jpg'))):
                tag = os.path.basename(v)[len(m['id']) + 2:-4]
                items.append((m['id'] + '__' + tag, f"{m['name']} ({tag})"))
        thumbs = []
        for iid, name in items:
            t = os.path.join(TMP, f'th_{iid}.png')
            mk(os.path.join(REN, iid + '.jpg'), '-resize', f'{THW}x', *label(name, THW, 20, 13),
               *label(iid, THW, 16, 11, color=DIM), '-append', '-bordercolor', BG, '-border', f'{GAP // 2}', t)
            thumbs.append(t)
        rows = []
        for i in range(0, len(thumbs), PER_ROW):
            r = os.path.join(TMP, f'row_{cat["id"]}_{i}.png')
            mk('-background', BG, *thumbs[i:i + PER_ROW], '+append', r)
            rows.append(r)
        grid = os.path.join(TMP, f'grid_{cat["id"]}.png')
        mk('-background', BG, *rows, '-append', grid)
        gh = int(subprocess.run(['magick', 'identify', '-format', '%h', grid], capture_output=True,
                                text=True).stdout)
        crops = []
        n = len(cat['sheet_concept_crops'])
        each_h = (gh - 22 * n) // n
        for k, c in enumerate(cat['sheet_concept_crops']):
            src = os.path.join(ROOT, c['image'])
            iw, ih = map(int, subprocess.run(['magick', 'identify', '-format', '%w %h', src],
                                             capture_output=True, text=True).stdout.split())
            l, t_, r_, b_ = c['box_fraction_ltrb']
            geo = f'{int((r_ - l) * iw)}x{int((b_ - t_) * ih)}+{int(l * iw)}+{int(t_ * ih)}'
            cp = os.path.join(TMP, f'crop_{cat["id"]}_{k}.png')
            mk(src, '-crop', geo, '+repage', '-resize', f'{CROPW - 12}x{each_h}^', '-gravity', 'center',
               '-extent', f'{CROPW - 12}x{each_h}', *label('concept: ' + os.path.basename(c['image']), CROPW - 12,
                                                         22, 11, color=DIM), '-append', cp)
            crops.append(cp)
        col = os.path.join(TMP, f'col_{cat["id"]}.png')
        mk('-background', BG, *crops, '-append', '-gravity', 'north', '-extent', f'{CROPW}x{gh}', col)
        blk = os.path.join(TMP, f'blk_{cat["id"]}.png')
        mk('-background', BG, col, grid, '+append', '-gravity', 'northwest', '-extent', f'{W}x{gh}', '(',
           '-size', f'{W}x34', f'xc:{BG}', '-fill', FG, '-font', BOLD, '-pointsize', 20, '-gravity', 'west',
           '-annotate', '+16+0', cat['label'], ')', '+swap', '-append', blk)
        blocks.append(blk)
    out = os.path.join(REN, 'sheet.jpg')
    mk('-background', BG, *blocks, '-append', '-quality', '88', out)
    print('wrote', out)


main()
