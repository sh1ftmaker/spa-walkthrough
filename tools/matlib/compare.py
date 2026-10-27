"""Before/after and repeat-vs-concept comparison images (needs ImageMagick 7).

    python3 tools/matlib/compare.py

compare/<id>.jpg : round-0 real-scale render (r0/scale/<id>.jpg) | round-2 neutral | round-2 in context
                   (or the sphere previews when no round-0 scale render exists)
repeat/<id>__vs_concept.jpg : the 10 x 10 m top-down view next to the material's concept/reference crop
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
REN = os.path.join(ROOT, '3d', 'renders', 'materials')
BG, FG = '#101010', '#e6e0d6'


def lab(path, text, w=640, h=360):
    if not os.path.exists(path):
        return ['(', '-size', f'{w}x{h + 24}', f'xc:{BG}', ')']
    return ['(', path, '-resize', f'{w}x{h}', '-gravity', 'center', '-background', BG, '-extent', f'{w}x{h}',
            '(', '-size', f'{w}x24', f'xc:{BG}', '-fill', FG, '-font', 'Liberation-Sans', '-pointsize', '14',
            '-gravity', 'center', '-annotate', '+0+0', text, ')', '-append', ')']


def main():
    man = json.load(open(os.path.join(ROOT, '3d', 'materials.json')))
    os.makedirs(os.path.join(REN, 'compare'), exist_ok=True)
    n = 0
    for m in man['materials']:
        mid = m['id']
        r0s = os.path.join(REN, 'r2', 'scale', mid + '.jpg')
        parts = (lab(r0s, 'round 2 (before)') if os.path.exists(r0s) else
                 lab(os.path.join(REN, 'r2', mid + '.jpg'), 'round 2 preview (before)'))
        parts += lab(os.path.join(REN, 'scale', mid + '.jpg'), 'now: neutral surround')
        parts += lab(os.path.join(REN, 'scale', mid + '__context.jpg'), 'now: in context')
        subprocess.run(['magick', '-background', BG, *parts, '+append', '(', '-size', '1920x34', f'xc:{BG}',
                        '-fill', FG, '-font', 'Liberation-Sans-Bold', '-pointsize', '18', '-gravity', 'west',
                        '-annotate', '+10+0', f"{m['name']} [{mid}]", ')', '+swap', '-append', '+repage',
                        '-quality', '86', os.path.join(REN, 'compare', mid + '.jpg')], check=True)
        n += 1
        rp = os.path.join(REN, 'repeat', mid + '.jpg')
        if os.path.exists(rp):
            ref = m.get('reference') or ''
            ref = ref.split(' ')[0]
            src = os.path.join(ROOT, ref) if ref and os.path.exists(os.path.join(ROOT, ref)) else None
            if not src:
                c = m['concept'][0].split(' ')[0]
                src = os.path.join(ROOT, 'lookbook', 'img', c)
            subprocess.run(['magick', '-background', BG, *lab(rp, '10 x 10 m top-down (shipped textures)', 600, 600),
                            *lab(src, 'reference: ' + os.path.relpath(src, ROOT), 900, 600), '+append', '+repage',
                            '-quality', '86', os.path.join(REN, 'repeat', mid + '__vs_concept.jpg')], check=True)
    print('wrote', n, 'comparisons')


main()
