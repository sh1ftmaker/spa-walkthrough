#!/usr/bin/env python3
"""Extract what the sound demo needs from 3d/layout.json + 3d/spaces/*.json.

Writes 3d/research/sound/demo/data/layout_extract.json (read-only use of the shared files).
Run: python3 3d/research/sound/tools/extract_layout.py
"""
import json, glob, math, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
LEVELS = ['summit', 'ground', 'b1', 'b2', 'b3', 'b4']
OUT = os.path.join(ROOT, '3d/research/sound/demo/data/layout_extract.json')

lay = json.load(open(os.path.join(ROOT, '3d/layout.json')))
spaces_l = {s['id']: s for s in lay['spaces']}
water_l = {w['id']: w for w in lay['water']}
files = {}
for f in glob.glob(os.path.join(ROOT, '3d/spaces/*.json')):
    s = json.load(open(f))
    if 'id' in s:
        files[s['id']] = s

def r(v, n=2):
    if isinstance(v, (list, tuple)):
        return [r(x, n) for x in v]
    if isinstance(v, float):
        return round(v, n)
    return v

def centroid(fp):
    xs = [p[0] for p in fp]; ys = [p[1] for p in fp]
    return [sum(xs) / len(xs), sum(ys) / len(ys)]

out_spaces = []
for sid, s in spaces_l.items():
    if s['level'] not in LEVELS:
        continue
    f = files.get(sid, {})
    water = []
    for w in f.get('water', []):
        e = {'id': w.get('id'), 'kind': w.get('kind')}
        lw = water_l.get(w.get('id') or '', {})
        for k in ('z', 'z_top', 'z_bottom', 'z_start', 'z_end', 'width', 'at', 'lip', 'footprint', 'path', 'waves'):
            if k in w and not (k in ('footprint', 'path') and not isinstance(w[k], list)):
                e[k] = w[k]
        if 'path' not in e and 'centerline' in lw:
            e['path'] = lw['centerline']
        if 'footprint' not in e and 'footprint' in lw:
            e['footprint'] = lw['footprint']
        for k in ('z', 'z_start', 'z_end', 'z_top', 'z_bottom', 'widths', 'lip', 'at'):
            if k not in e and k in lw:
                e[k] = lw[k]
        water.append(r(e))
    anchored = []
    for a in f.get('anchored', []):
        at = a.get('at')
        pts = at if (at and isinstance(at[0], list)) else [at]
        for i, p in enumerate(pts):
            if p:
                anchored.append({'id': a.get('id') + (f'_{i}' if len(pts) > 1 else ''), 'asset': a.get('asset'), 'at': r(p)})
    hero = f.get('hero') or {}
    cp = f.get('ceiling_profile') or {}
    out_spaces.append(r({
        'id': sid, 'name': s['name'], 'level': s['level'], 'kind': s['kind'],
        'footprint': s['footprint'], 'floor_z': s['floor_z'],
        'ceiling_z': cp.get('max_z', s.get('ceiling_z')),
        'ceiling_type': cp.get('type'),
        'area_m2': s.get('area_m2'),
        'spine': f.get('spine'),
        'water': water, 'anchored': anchored,
        'hero': {'asset': hero.get('asset'), 'at': hero.get('at'), 'dims': hero.get('dims')} if hero else None,
        'mood': (f.get('mood') or {}).get('key'),
    }))

sids = {s['id'] for s in out_spaces}
floor = {s['id']: s['floor_z'] for s in out_spaces}

portals = []
for p in lay['portals']:
    a, b = p['a'], p['b']
    if a not in sids and b not in sids:
        continue
    z = floor.get(a, floor.get(b))
    portals.append(r({'id': p['id'], 'a': a, 'b': b, 'at': p['at'] + [z], 'width': p.get('width', 3), 'height': p.get('height', 3)}))

# Walkable connections become pseudo-rooms; add synthetic portals for places that lack one.
conns = []
keep = {'spiral_stair', 'mist_steps', 'falls_stair_1', 'falls_gallery', 'falls_stair_2', 'rimstone_stair', 'lava_stair',
        'north_walk_stair', 'beach_steps', 'thunder_falls'}
for c in lay['connections']:
    if c['id'] not in keep:
        continue
    places = [pl for pl in (c.get('places') or []) if pl in sids]
    have = {p['a'] if p['b'] == c['id'] else p['b'] for p in portals if c['id'] in (p['a'], p['b'])}
    plan = c.get('plan') or c.get('path') or []
    for pl in places:
        if pl in have:
            continue
        sp = next(s for s in out_spaces if s['id'] == pl)
        cen = centroid(sp['footprint'])
        if plan:
            best = min(plan, key=lambda q: (q[0] - cen[0]) ** 2 + (q[1] - cen[1]) ** 2)
            at = [best[0], best[1]]
        elif c['id'] == 'thunder_falls':
            at = [29.0, 76.0]
        elif c['id'] == 'mist_steps':
            box = c.get('box')
            at = [49.0, 72.0] if pl == 'b2_core' else [49.0, 79.0]
        else:
            at = cen
        portals.append(r({'id': f"syn_{c['id']}_{pl}", 'a': pl, 'b': c['id'], 'at': at + [sp['floor_z']],
                          'width': c.get('width', c.get('flight_width', 3.0)), 'height': 3.0, 'synthetic': True}))
    conns.append({'id': c['id'], 'kind': c['kind'], 'places': places, 'z_top': c.get('z_top'), 'z_bottom': c.get('z_bottom')})

out = {
    'source': '3d/layout.json + 3d/spaces/*.json (extracted by 3d/research/sound/tools/extract_layout.py)',
    'grid': lay['grid'], 'sea_level': lay['sea_level'],
    'levels': [l for l in lay['levels'] if l['id'] in LEVELS],
    'spaces': out_spaces, 'portals': portals, 'connections': conns,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print('wrote', OUT, os.path.getsize(OUT), 'bytes;', len(out_spaces), 'spaces,', len(portals), 'portals,', len(conns), 'connections')
