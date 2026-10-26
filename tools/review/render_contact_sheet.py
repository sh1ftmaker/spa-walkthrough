"""Compose a review contact sheet per space (brief §5.5).

  .venv/bin/python tools/review/render_contact_sheet.py <space_id> [--round N] [--views-dir 3d/renders/graybox]

Needs: Blender views in <views-dir>/<space>/{entry,reveal,concept}-{16x9,9x16}.jpg and strip-0..7.jpg
(tools/graybox/render_views.py --set spaces), 3d/placements_resolved.json, 3d/checks/placement.json.
Writes 3d/renders/contact/<space>/contact-r<N>.jpg (~1600 px wide) and prints its path.
Layout:  [labelled top-down plan | concept image + concept-match view]
         [entry 16:9 | reveal 16:9 | 9:16 trio]
         [8-frame spine strip]
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sid = sys.argv[1]
RND = int(sys.argv[sys.argv.index('--round') + 1]) if '--round' in sys.argv else 1
VIEWS = os.path.join(ROOT, sys.argv[sys.argv.index('--views-dir') + 1]) if '--views-dir' in sys.argv else os.path.join(ROOT, '3d', 'renders', 'graybox')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'assembly'))
from spaces_io import load_spaces
sp = load_spaces(ROOT)[sid]
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
lsp = next(s for s in L['spaces'] if s['id'] == sid)
P = [p for p in json.load(open(os.environ.get('KZ_RESOLVED') or os.path.join(ROOT, '3d', 'placements_resolved.json')))['placements'] if p['space'] == sid]
_CP = os.environ.get('KZ_CHECKS') or os.path.join(ROOT, '3d', 'checks', 'placement.json')
CHK = json.load(open(_CP)).get(sid, {}) if os.path.exists(_CP) else {}
FB = '/usr/share/fonts/noto/NotoSans-Bold.ttf'; FR = '/usr/share/fonts/noto/NotoSans-Regular.ttf'
F = lambda n, b=False: ImageFont.truetype(FB if b else FR, n)
BG, INK, DIM, RED, AMB, TEAL = (16, 17, 19), (235, 235, 230), (140, 145, 150), (255, 80, 80), (242, 166, 74), (70, 214, 200)
W = 1600


def bad_ids():
    ids = set()
    for k, v in CHK.items():
        if v.get('status') in ('fail', 'warn'):
            for key in ('floating', 'sunk', 'blocked', 'on_cell_centres', 'ids'):
                for e in v.get(key, []) or []:
                    ids.add(e[0] if isinstance(e, list) else e)
            for e in v.get('worst', []) or []:
                ids.add(e[0]); ids.add(e[1])
    return ids


def plan(w, h):
    im = Image.new('RGB', (w, h), BG); d = ImageDraw.Draw(im)
    fp = lsp['footprint']
    xs = [p[0] for p in fp]; ys = [p[1] for p in fp]
    pad = 3
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    s = min((w - 20) / (x1 - x0), (h - 60) / (y1 - y0))
    ox = (w - (x1 - x0) * s) / 2; oy = 40
    T = lambda x, y: (ox + (x - x0) * s, oy + (y1 - y) * s)
    # grid lines (to show nothing sits on cell centres)
    for gx in range(int(x0 // 20) * 20, int(x1) + 21, 20):
        d.line([T(gx, y0), T(gx, y1)], fill=(40, 42, 46))
    for gy in range(int(y0 // 20) * 20, int(y1) + 21, 20):
        d.line([T(x0, gy), T(x1, gy)], fill=(40, 42, 46))
    d.polygon([T(*p) for p in fp], outline=(150, 150, 160), fill=(28, 30, 33))
    # neighbours (portals lead to them)
    for o in L['spaces']:
        if o['id'] != sid and o['footprint'] and o['level'] == lsp['level']:
            d.polygon([T(*p) for p in o['footprint']], outline=(55, 58, 64))
    for w_ in sp.get('water', []):
        if 'path' in w_:
            d.line([T(*p[:2]) for p in w_['path']], fill=TEAL, width=max(2, int(w_.get('width', 2) * s)))
        elif 'footprint' in w_:
            d.polygon([T(*p) for p in w_['footprint']], fill=(20, 80, 80), outline=TEAL)
    for w_ in L['water']:
        if w_.get('level') == lsp['level'] and 'footprint' in w_:
            d.polygon([T(*p) for p in w_['footprint']], outline=TEAL)
    if sp.get('spine'):
        d.line([T(*p[:2]) for p in sp['spine']], fill=(90, 200, 120), width=3)
    for sl in sp.get('sightlines', []):
        src = next((pp['at'] for pp in sp.get('portals', []) if pp['id'] == sl.get('from')), None)
        if src and sl.get('target'):
            d.line([T(*src[:2]), T(*sl['target'][:2])], fill=(120, 120, 255), width=1)
    bad = bad_ids()
    fs = F(11)
    for p in P:
        if p.get('snap_status') == 'structural':
            continue
        wv, dv = p['dims']['w'] * p['scale'], p['dims']['d'] * p['scale']
        a = math.radians(p['facing_deg'])
        cx, cy = p['pos'][:2]
        pts = []
        for ux, uy in ((-wv / 2, -dv / 2), (wv / 2, -dv / 2), (wv / 2, dv / 2), (-wv / 2, dv / 2)):
            pts.append(T(cx + ux * math.cos(a) + uy * math.sin(a), cy - ux * math.sin(a) + uy * math.cos(a)))
        col = RED if p['id'] in bad else (AMB if p.get('light') else ((255, 140, 60) if p.get('hero') else (170, 160, 140)))
        d.polygon(pts, outline=col, width=2 if p['id'] in bad or p.get('hero') else 1)
        fx, fy = T(cx + math.sin(a) * dv / 2, cy + math.cos(a) * dv / 2)
        d.line([T(cx, cy), (fx, fy)], fill=col)
        if p.get('hero') or p['id'] in bad or p['rule'].startswith('anchored'):
            d.text(T(cx, cy), p['id'].split(':', 1)[1], fill=col, font=fs, anchor='mm', stroke_width=2, stroke_fill=BG)
    for pr in sp.get('portals', []):
        if 'at' in pr:
            x, y = T(*pr['at'][:2]); r = max(4, pr.get('width', 2) * s / 2)
            d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 210, 0), width=2)
    for k, c in (sp.get('cameras') or {}).items():
        if isinstance(c, dict) and 'pos' in c:
            x, y = T(*c['pos'][:2]); tx, ty = T(*c['target'][:2])
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 255, 255))
            ang = math.atan2(ty - y, tx - x)
            d.line([(x, y), (x + 30 * math.cos(ang), y + 30 * math.sin(ang))], fill=(255, 255, 255), width=2)
            d.text((x + 8, y - 14), k, fill=INK, font=F(12, True))
    d.text((10, 8), f'{sid} — plan (north up, grid 20 m). green spine, yellow portals, amber lights, orange hero, red = check failure, blue = sightlines',
           fill=INK, font=F(13, True))
    return im


def fit(path, w, h):
    if not os.path.exists(path):
        im = Image.new('RGB', (w, h), (30, 30, 34)); ImageDraw.Draw(im).text((10, 10), f'missing\n{os.path.basename(path)}', fill=DIM, font=F(14))
        return im
    im = Image.open(path).convert('RGB'); im.thumbnail((w, h))
    out = Image.new('RGB', (w, h), BG); out.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def label(im, text):
    d = ImageDraw.Draw(im); d.rectangle([0, 0, im.width, 22], fill=(0, 0, 0)); d.text((6, 3), text, fill=INK, font=F(13, True))
    return im


def checks_panel(w, h):
    im = Image.new('RGB', (w, h), BG); d = ImageDraw.Draw(im)
    d.text((10, 6), 'placement checks', fill=INK, font=F(15, True))
    y = 32
    for k, v in CHK.items():
        st = v.get('status')
        col = {'pass': (95, 211, 141), 'warn': (242, 193, 74), 'fail': RED, 'waived': DIM}.get(st, DIM)
        extra = ''
        if k == 'hero_visible':
            extra = str(v.get('fraction'))
        elif v.get('fails') or v.get('warns'):
            extra = f"fails {v.get('fails', 0)} warns {v.get('warns', 0)}"
        d.text((10, y), f'{k:14s} {st:6s} {extra}', fill=col, font=F(13)); y += 19
    hero = sp.get('hero', {})
    d.text((10, y + 8), 'hero: ' + str(hero.get('asset')), fill=AMB, font=F(13, True))
    why = hero.get('why', '')
    for i in range(0, min(len(why), 360), 60):
        d.text((10, y + 28 + (i // 60) * 17), why[i:i + 60], fill=DIM, font=F(12))
    return im


V = lambda n: os.path.join(VIEWS, sid, n)
concept = (sp.get('cameras') or {}).get('concept', {})
cimg = os.path.join(ROOT, concept['image']) if concept.get('image') else None
H1 = 640
sheet = Image.new('RGB', (W, 30 + H1 + 10 + 300 + 10 + 260 + 10 + 180), BG)
d = ImageDraw.Draw(sheet)
d.text((12, 6), f'Kazan-yu contact sheet — {lsp["name"]} ({sid}) — round {RND}', fill=INK, font=F(18, True))
sheet.paste(plan(900, H1), (0, 30))
right = Image.new('RGB', (W - 910, H1), BG)
right.paste(label(fit(cimg, W - 910, 310) if cimg else Image.new('RGB', (W - 910, 310), BG), 'concept ' + os.path.basename(concept.get('image', '') or '')), (0, 0))
right.paste(label(fit(V('concept-16x9.jpg'), W - 910, 320), 'concept-match view (graybox)'), (0, 320))
sheet.paste(right, (910, 30))
y = 30 + H1 + 10
sheet.paste(label(fit(V('entry-16x9.jpg'), 520, 300), 'entry 16:9'), (0, y))
sheet.paste(label(fit(V('reveal-16x9.jpg'), 520, 300), 'reveal 16:9'), (530, y))
for i, k in enumerate(('entry', 'reveal', 'concept')):
    sheet.paste(label(fit(V(f'{k}-9x16.jpg'), 170, 300), f'{k} 9:16'), (1060 + i * 180, y))
y += 310
for i in range(8):
    sheet.paste(fit(V(f'strip-{i}.jpg'), 196, 110), (i * 200, y))
d.text((6, y + 112), 'walk along the spine (8 frames, eye height 1.6 m)', fill=DIM, font=F(12))
sheet.paste(checks_panel(W, 300), (0, y + 135))
out = os.path.join(os.environ.get('KZ_CONTACT_DIR') or os.path.join(ROOT, '3d', 'renders', 'contact'), sid); os.makedirs(out, exist_ok=True)
path = os.path.join(out, f'contact-r{RND}.jpg')
sheet.save(path, quality=84)
print(path)
