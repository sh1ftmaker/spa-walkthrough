"""2x2 tiling checks of every texture set (needs ImageMagick 7 `magick`).

    python3 tools/matlib/tile_checks.py

Per material: base | ORM (RGB) | normal XY + height | base.a mask | normal_height.a wet mask,
each repeated 2x2 (non-square sets keep their aspect).  A seam would show as a cross through
the middle of a panel.  Output 3d/renders/materials/tiles/<id>.jpg (side sets get a second row).
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, '3d', 'renders', 'materials', 'tiles')
TEX = os.path.join(ROOT, '.scratch', 'matlib', 'tex')
PW = 300                      # panel width = 2 repeats
BG, FG = '#101010', '#e6e0d6'


def panel(src, title, chan=None, ph=None):
    sel = ['-alpha', 'off'] if chan is None else ['-alpha', 'extract'] if chan == 'a' else []
    return ['(', src, *sel, '-resize', f'{PW // 2}x{(ph or PW) // 2}!', '-write', 'mpr:t', '+delete',
            '(', 'mpr:t', 'mpr:t', '+append', ')', '(', 'mpr:t', 'mpr:t', '+append', ')', '-append',
            '(', '-size', f'{PW}x22', f'xc:{BG}', '-fill', FG, '-font', 'Liberation-Sans', '-pointsize', '12',
            '-gravity', 'center', '-annotate', '+0+0', title, ')', '-append', '-bordercolor', BG, '-border', '3', ')']


def row(sid, aspect):
    ph = max(24, int(round(PW / aspect))) if aspect >= 1 else min(900, int(round(PW / aspect)))
    p = lambda k: os.path.join(TEX, f'{sid}_{k}.png')  # noqa: E731
    out = panel(p('base'), 'base (sRGB)', None, ph) + panel(p('orm'), 'ORM: R ao  G rough  B metal', None, ph) + \
        panel(p('nh'), 'normal XY + height (B)', None, ph)
    out += panel(p('base'), 'base.a mask', 'a', ph) if _has_alpha(p('base')) else []
    out += panel(p('nh'), 'nh.a wet-film mask', 'a', ph)
    return ['(', *out, '+append', ')']


def _has_alpha(path):
    with open(path, 'rb') as f:
        return f.read(26)[25] in (4, 6)


def main():
    os.makedirs(OUT, exist_ok=True)
    man = json.load(open(os.path.join(ROOT, '3d', 'materials.json')))
    for m in man['materials']:
        sid = os.path.basename(m['textures']['base'])[:-len('_base.ktx2')]
        rows = row(sid, m['aspect'])
        if m.get('textures_side'):
            rows += row(sid + '_side', m['aspect'])
        rep = m['tiling_m_per_repeat']
        size = 'x'.join(map(str, m['texture_size'] or []))
        title = (f"{m['name']}  [{m['id']}]   2x2 repeats, " +
                 (f"{rep} m x {round(rep / m['aspect'], 3)} m per repeat" if rep else 'object UVs (0..1)') +
                 f", {size} px" + (f"  (set {sid})" if sid != m['id'] else ''))
        out = os.path.join(OUT, m['id'] + '.jpg')
        subprocess.run(['magick', '-background', BG, *rows, '-append',
                        '(', '-size', f'{5 * (PW + 6)}x34', f'xc:{BG}', '-fill', FG, '-font', 'Liberation-Sans-Bold',
                        '-pointsize', '16', '-gravity', 'west', '-annotate', '+10+0', title, ')', '+swap', '-append',
                        '+repage', '-quality', '88', out], check=True)
    print('wrote', len(man['materials']), 'tiling checks to', OUT)


main()
