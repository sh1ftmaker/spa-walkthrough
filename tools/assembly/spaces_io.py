"""Load 3d/spaces/*.json with templates instantiated. Shared by place.py, the graybox builder, the checks and
the review renderers, so every tool sees the same space data.

A space file with "template": "<id>" and "origin": [x0, y0, z0] is built from <id>.json: every key ending in
"_local" is renamed (portals_local -> portals ...) and every coordinate inside coordinate-bearing keys is offset
by the origin (z only when a coordinate has 3 components). Values in the referencing file win over the template.
"""
import copy, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COORD_KEYS = {'at', 'pos', 'target', 'polygon', 'path', 'footprint', 'spine', 'along', 'ring', 'points', 'line',
              'from', 'to', 'bridge', 'center', 'area', 'branches', 'spurs'}


def _is_pt(v):
    return isinstance(v, list) and 2 <= len(v) <= 3 and all(isinstance(c, (int, float)) for c in v)


def _shift(v, o):
    if _is_pt(v):
        return [v[0] + o[0], v[1] + o[1]] + ([v[2] + o[2]] if len(v) == 3 else [])
    if isinstance(v, list):
        return [_shift(x, o) for x in v]
    if isinstance(v, dict):
        return {k: (_shift(x, o) if k in COORD_KEYS or isinstance(x, (dict, list)) and k not in ('dims', 'scale', 'spacing', 'band', 'height', 'radius', 'variants', 'jitter_deg', 'avoid') else x)
                for k, x in v.items()}
    return v


def instantiate(ref, tpl, layout_space=None):
    t = copy.deepcopy(tpl)
    o = ref['origin']
    out = {}
    for k, v in t.items():
        nk = k[:-6] if k.endswith('_local') else k
        out[nk] = _shift(v, o) if (k.endswith('_local') or k in COORD_KEYS or k in ('hero', 'anchored', 'lights', 'dressing', 'water', 'sightlines', 'cameras', 'zones')) else v
    for k, v in ref.items():
        if k not in ('template', 'origin'):
            out[k] = v
    out['id'] = ref['id']; out['from_template'] = ref['template']
    if layout_space:
        out['footprint'] = layout_space['footprint']; out['level'] = layout_space['level']
        out.setdefault('floor_z', layout_space['floor_z']); out.setdefault('ceiling_z', layout_space['ceiling_z'])
    return out


def valid_poly(p):
    return isinstance(p, list) and len(p) >= 3 and all(_is_pt(q) for q in p)


def load_spaces(root=ROOT):
    L = json.load(open(os.path.join(root, '3d', 'layout.json')))
    LSP = {s['id']: s for s in L['spaces']}
    raw = {}
    for f in sorted(glob.glob(os.path.join(root, '3d', 'spaces', '*.json'))):
        j = json.load(open(f))
        if 'id' in j:
            raw[j['id']] = j
    out = {}
    for sid, j in raw.items():
        if sid.endswith('_template') or 'footprint_local' in j:
            continue
        if j.get('template'):
            j = instantiate(j, raw[j['template']], LSP.get(sid))
        # sanitise water shapes (only real polygons / paths are geometry)
        for w in j.get('water', []):
            if 'footprint' in w and not valid_poly(w['footprint']):
                w.pop('footprint')
            if 'path' in w and not (isinstance(w['path'], list) and len(w['path']) >= 2 and all(_is_pt(q) for q in w['path'])):
                w.pop('path')
        out[sid] = j
    return out
