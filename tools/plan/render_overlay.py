"""Render layout.json as plan overlays on the painted level plans, a stacked view, an E-W section,
and run the rock-thickness check. Writes 3d/renders/plan/*.jpg and prints check results.

  .venv/bin/python tools/plan/render_overlay.py
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, LineString

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
OUT = os.path.join(ROOT, '3d', 'renders', 'plan'); os.makedirs(OUT, exist_ok=True)
PX = 7                                       # px per metre
W, H = 200 * PX, 120 * PX
M = 40                                       # margin

# grid box of each painted plan: (left, top, cell_w, cell_h) in image px, read off the column/row labels
PLANS = {
    'summit': ('lookbook/img/30-plan-summit.jpg', (51, 43, 151.4, 129.4)),
    'ground': ('lookbook/img/31-plan-ground.jpg', (75, 34, 146.1, 129.4)),
    'b1': ('lookbook/img/33-plan-b1-thermal.jpg', (38, 40, 154.4, 142.0)),
    'b2': ('lookbook/img/34-plan-b2-river.jpg', (58.5, 32.5, 149.0, 137.0)),
    'b3': ('lookbook/img/35-plan-b3-aqua-cavern.jpg', (35, 24.6, 155.3, 126.8)),
    'b4': ('lookbook/img/36-plan-b4-magma.jpg', (43.5, 103, 153.1, 110.4)),
}
LEVEL_COL = {'summit': (240, 200, 90), 'ground': (230, 230, 230), 'b1': (90, 210, 240), 'b2': (240, 90, 210),
             'b3': (110, 230, 110), 'b4': (250, 150, 60), 'cliff': (190, 160, 250)}
try:
    FONT = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', 13)
    FONTB = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Bold.ttf', 18)
except OSError:
    FONT = FONTB = ImageFont.load_default()


def P(x, y):
    return (M + x * PX, M + (120 - y) * PX)


def underlay(level):
    if level not in PLANS:
        return Image.new('RGB', (W, H), (20, 22, 24))
    path, (l, t, cw, ch) = PLANS[level]
    im = Image.open(os.path.join(ROOT, path)).convert('RGB')
    im = im.crop((int(l), int(t), int(l + 10 * cw), int(t + 6 * ch))).resize((W, H))
    return Image.blend(im, Image.new('RGB', (W, H), (0, 0, 0)), 0.45)


def grid(d):
    for i in range(11):
        d.line([P(i * 20, 0), P(i * 20, 120)], fill=(120, 120, 120), width=1)
    for j in range(7):
        d.line([P(0, j * 20), P(200, j * 20)], fill=(120, 120, 120), width=1)
    for i, c in enumerate('ABCDEFGHIJ'):
        d.text((M + i * 20 * PX + 66, 8), c, fill=(255, 255, 255), font=FONTB)
    for j in range(6):
        d.text((10, M + j * 20 * PX + 60), str(j + 1), fill=(255, 255, 255), font=FONTB)


def poly(d, pts, col, width=3, fill=None):
    q = [P(x, y) for x, y in pts]
    if fill:
        d.polygon(q, fill=fill)
    d.line(q + [q[0]], fill=col, width=width)


def conn_lines(d, c, col):
    if c['kind'] == 'helix':
        d.line([P(p[0], p[1]) for p in c['path']], fill=col, width=2)
    elif c['kind'] in ('path_stair', 'walkway'):
        d.line([P(x, y) for x, y in c['plan']], fill=col, width=3)
    elif c['kind'] == 'switchback':
        for f in c['flights']:
            d.line([P(f['x'], f['y_start']), P(f['x'], f['y_end'])], fill=col, width=int(c['flight_width'] * PX * 0.8))


def level_of_conn(c, lv):
    zs = {l['id']: l['floor_z'] for l in L['levels']}
    z = zs.get(lv)
    if z is None or 'z_top' not in c and c['kind'] != 'walkway':
        return False
    if c['kind'] == 'walkway':
        return lv == 'b3'
    lo, hi = min(c['z_top'], c['z_bottom']), max(c['z_top'], c['z_bottom'])
    return lo - 8 <= z <= hi + 0.5


def draw_level(lv):
    img = Image.new('RGB', (W + 2 * M, H + 2 * M), (12, 13, 14))
    img.paste(underlay(lv), (M, M))
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    grid(d)
    col = LEVEL_COL.get(lv, (255, 255, 255))
    for w in L['water']:
        if w.get('level') == lv and 'footprint' in w:
            poly(d, w['footprint'], (60, 220, 210), 2, fill=(40, 200, 200, 90))
    for s in L['spaces']:
        if s['level'] == lv or (lv == 'summit' and s['level'] == 'cliff'):
            poly(d, s['footprint'], LEVEL_COL.get(s['level']), 3, fill=col + (40,))
            cx, cy = Polygon(s['footprint']).representative_point().coords[0]
            d.text(P(cx, cy), s['id'], fill=(255, 255, 255), font=FONT, anchor='mm', stroke_width=2, stroke_fill=(0, 0, 0))
    for c in L['connections']:
        if level_of_conn(c, lv):
            conn_lines(d, c, (255, 230, 80, 230))
    for p in L['portals']:
        sp = {s['id']: s['level'] for s in L['spaces']}
        if sp.get(p['a']) == lv:
            x, y = p['at']; r = p['width'] / 2 * PX
            d.ellipse([P(x, y)[0] - r, P(x, y)[1] - r, P(x, y)[0] + r, P(x, y)[1] + r], outline=(255, 80, 80), width=3)
    lx, ly = L['lift']['at']
    for r, c in ((L['lift']['shaft_r'], (255, 255, 255)), (2.2, (255, 255, 255))):
        d.ellipse([P(lx - r, ly + r), P(lx + r, ly - r)], outline=c, width=2)
    if lv in ('b1', 'b2', 'b3'):
        sx, sy = L['slide_shaft']['at']; r = L['slide_shaft']['r']
        d.ellipse([P(sx - r, sy + r), P(sx + r, sy - r)], outline=(255, 120, 60), width=2)
    d.text((M + 8, H + M + 8), f"{lv}  floor {next(l['floor_z'] for l in L['levels'] if l['id'] == lv)} m   (layout.json over the painted plan; red = portals, yellow = stairs)",
           fill=(255, 255, 255), font=FONTB)
    img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    img.save(os.path.join(OUT, f'{lv}.jpg'), quality=85)


def section():
    """E-W section along y = 70 (through the lift) and N-S along x = 90, all spaces whose footprint crosses."""
    S = 4
    for name, axis, val in (('section-ew-y70', 'y', 70.0), ('section-ns-x90', 'x', 90.0)):
        span = 200 if axis == 'y' else 120
        Wd, Hd = span * S + 80, 260 * S + 60
        img = Image.new('RGB', (Wd, Hd), (14, 15, 16)); d = ImageDraw.Draw(img)
        Z = lambda z: 30 + (130 - z) * S
        X = lambda t: 40 + t * S
        for z in range(-120, 140, 10):
            d.line([(40, Z(z)), (Wd - 40, Z(z))], fill=(40, 40, 40))
            d.text((2, Z(z) - 6), f'{z}', fill=(140, 140, 140), font=FONT)
        d.line([(40, Z(L['sea_level'])), (Wd - 40, Z(L['sea_level']))], fill=(40, 90, 160), width=2)
        cut = LineString([(0, val), (200, val)]) if axis == 'y' else LineString([(val, 0), (val, 120)])
        for s in L['spaces']:
            g = Polygon(s['footprint']).intersection(cut)
            if g.is_empty:
                continue
            xs = [c[0] if axis == 'y' else c[1] for c in g.coords] if g.geom_type == 'LineString' else \
                 [c[0] if axis == 'y' else c[1] for gg in g.geoms for c in gg.coords]
            top = s['ceiling_z'] if s['ceiling_z'] is not None else s['floor_z'] + 3
            col = LEVEL_COL.get(s['level'])
            d.rectangle([X(min(xs)), Z(top), X(max(xs)), Z(s['floor_z'])], outline=col, fill=tuple(int(c * .25) for c in col), width=2)
            d.text((X(min(xs)) + 3, Z(top) + 2), s['id'], fill=col, font=FONT)
        for w in L['water']:
            if 'footprint' in w and 'z' in w:
                g = Polygon(w['footprint']).intersection(cut)
                if not g.is_empty and g.geom_type == 'LineString':
                    xs = [c[0] if axis == 'y' else c[1] for c in g.coords]
                    d.line([(X(min(xs)), Z(w['z'])), (X(max(xs)), Z(w['z']))], fill=(60, 230, 220), width=3)
        if axis == 'y':
            lx = L['lift']['at'][0]; r = L['lift']['shaft_r']
            d.rectangle([X(lx - r), Z(9), X(lx + r), Z(-100)], outline=(255, 255, 255), width=2)
        d.text((40, Hd - 26), f'{name}: spaces cut by {axis} = {val} m. Blue = sea level.', fill=(255, 255, 255), font=FONTB)
        img.save(os.path.join(OUT, f'{name}.jpg'), quality=85)


def rock_check():
    """Every pair of enclosed spaces that overlap in plan must have >= 4 m rock between the lower ceiling and the upper floor,
    unless they are joined by a connection (shafts)."""
    fails = []
    enclosed = [s for s in L['spaces'] if s['ceiling_z'] is not None]
    allsp = L['spaces']
    for lo in enclosed:
        for up in allsp:
            if up is lo or up['floor_z'] <= lo['floor_z'] or up['level'] == lo['level']:
                continue
            if any(lo['id'] in c.get('places', []) and up['id'] in c.get('places', []) for c in L['connections']):
                continue  # joined by a stair/shaft
            a, b = Polygon(lo['footprint']), Polygon(up['footprint'])
            inter = a.intersection(b).area
            if inter < 2.0:
                continue
            gap = up['floor_z'] - lo['ceiling_z'] - (1.6 if up['id'].startswith('b2_kawagiri') else 0)
            if gap < 4.0:
                fails.append((lo['id'], up['id'], round(gap, 2), round(inter, 1)))
    # river bed over B3 roof
    river = Polygon(next(w for w in L['water'] if w['id'] == 'w_river')['footprint'])
    bed = next(w for w in L['water'] if w['id'] == 'w_river')['bed_z']
    for s in L['spaces']:
        if s['level'] == 'b3' and s['ceiling_z'] is not None and river.intersection(Polygon(s['footprint'])).area > 2:
            if bed - s['ceiling_z'] < 4.0 and s['id'] != 'b3_falls':
                fails.append(('w_river bed', s['id'], round(bed - s['ceiling_z'], 2), 0))
    return fails


def walk_graph():
    import networkx as nx
    G = nx.Graph()
    for s in L['spaces']:
        G.add_node(s['id'])
    for p in L['portals']:
        G.add_edge(p['a'], p['b'])
    for c in L['connections']:
        if c.get('walk') and c.get('places'):
            G.add_node(c['id'])
            for pl in c['places']:
                G.add_edge(c['id'], pl)
    reach = nx.node_connected_component(G, 'g_gate')
    unreached = [s['id'] for s in L['spaces'] if s['id'] not in reach and s.get('walkable', True)]
    return unreached


if __name__ == '__main__':
    for lv in ('summit', 'ground', 'b1', 'b2', 'b3', 'b4'):
        draw_level(lv)
    section()
    rf = rock_check()
    print('rock check:', 'pass' if not rf else f'{len(rf)} fail(s)')
    for f in rf:
        print('  ', f)
    un = walk_graph()
    print('walk graph from g_gate:', 'all spaces reached' if not un else f'unreached: {un}')
