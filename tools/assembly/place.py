"""Turn space intent files into placements.

  .venv/bin/python tools/assembly/place.py [space_id ...]      -> 3d/placements.json

Reads 3d/layout.json, 3d/spaces/<id>.json, 3d/assets.json, 3d/overrides.json.
Every placement records the rule that produced it. Never hand-edit placements.json: change the rule,
or add a reasoned nudge to overrides.json. z here is provisional (floor_z / height rules); the Blender
assembly step snaps to the real surface by raycast and the checks measure contact.
"""
import json, math, os, sys, glob, random
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union, nearest_points

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
ASSETS = json.load(open(os.path.join(ROOT, '3d', 'assets.json')))['assets']
OVR_PATH = os.path.join(ROOT, '3d', 'overrides.json')
OVR = json.load(open(OVR_PATH)) if os.path.exists(OVR_PATH) else {}
WARN = []
LSP = {s['id']: s for s in L['spaces']}
LWATER = {w['id']: w for w in L['water']}
CONN = {c['id']: c for c in L['connections']}


def dims(asset, override=None):
    d = dict(ASSETS.get(asset, dict(w=1, d=1, h=1, snap='ground', unknown=True)))
    if override:
        for k, v in override.items():
            if k in ('w', 'd', 'h'):
                d[k] = sum(v) / len(v) if isinstance(v, list) else v
    return d


def bearing(dx, dy):
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def line_of(sp, src):
    """resolve a polyline source name to a list of (x, y)"""
    if isinstance(src, list):
        return [tuple(p[:2]) for p in src]
    if src == 'spine':
        return [tuple(p[:2]) for p in sp['spine']]
    if src == 'wall':
        poly = Polygon(sp['footprint'])
        return list(poly.exterior.coords)
    if src.startswith('water:'):
        wid = src.split(':', 1)[1]
        for w in sp.get('water', []):
            if w['id'] == wid:
                if 'path' in w:
                    return [tuple(p) for p in w['path']]
                if 'footprint' in w:
                    return list(Polygon(w['footprint']).exterior.coords)
        w = LWATER.get(wid)
        if w:
            if 'centerline' in w:
                return [tuple(p) for p in w['centerline']]
            if 'footprint' in w:
                return list(Polygon(w['footprint']).exterior.coords)
    if src.startswith('balcony:'):
        b = LSP.get(sp['id'], {}).get('balcony')
        if b:
            xs = [q[0] for q in b]; ys = [q[1] for q in b]
            edge = src.split(':', 1)[1]
            return {'north_edge': [(min(xs), max(ys) - 0.15), (max(xs), max(ys) - 0.15)],
                    'south_edge': [(min(xs), min(ys) + 0.15), (max(xs), min(ys) + 0.15)],
                    'east_end': [(max(xs) - 0.15, min(ys)), (max(xs) - 0.15, max(ys))],
                    'west_end': [(min(xs) + 0.15, min(ys)), (min(xs) + 0.15, max(ys))]}[edge]
    if src.startswith('conn:') or src.startswith('stair:'):
        c = CONN[src.split(':', 1)[1]]
        return [tuple(p[:2]) for p in (c.get('plan') or c.get('path'))]
    if src.startswith('anchored:') or ' ' in src or any(a['id'] == src for a in sp.get('anchored', [])):
        ids = [x.split(':', 1)[-1] for x in src.split()]
        pts = []
        for a in sp.get('anchored', []):
            if a['id'] in ids:
                dd = dims(a['asset'], a.get('dims'))
                ang = math.radians(a.get('facing_deg', 0))
                ux, uy = math.cos(ang), -math.sin(ang)          # the asset's local +X in world
                cx, cy = a['at'][:2]
                pts += [(cx - ux * dd['w'] / 2, cy - uy * dd['w'] / 2), (cx + ux * dd['w'] / 2, cy + uy * dd['w'] / 2)]
        if len(pts) >= 2:
            return pts
    raise ValueError(f'unknown line source {src}')


def water_z(sp, wid):
    for w in sp.get('water', []):
        if w['id'] == wid:
            return w.get('z')
    w = LWATER.get(wid)
    return w.get('z', w.get('z_end')) if w else None


def avoid_geom(sp, names, extra=0.0):
    geoms = []
    for n in names or []:
        if n == 'nav':
            if sp.get('spine') and len(sp['spine']) > 1:
                geoms.append(LineString([p[:2] for p in sp['spine']]).buffer(0.9 + extra))
        elif n == 'portals':
            for p in sp.get('portals', []):
                geoms.append(Point(p['at']).buffer(p['width'] / 2 + 1.2 + extra))
        elif n == 'water':
            for w in sp.get('water', []):
                if 'path' in w:
                    geoms.append(LineString(w['path']).buffer(w.get('width', 2) / 2 + 0.3 + extra))
                elif 'footprint' in w:
                    geoms.append(Polygon(w['footprint']).buffer(0.3 + extra))
            for w in L['water']:
                if w.get('level') == sp.get('level') and 'footprint' in w and w['kind'] in ('still', 'sea'):
                    geoms.append(Polygon(w['footprint']).buffer(0.2 + extra))
        elif n == 'hero':
            h = sp.get('hero')
            if h:
                dd = dims(h['asset'], h.get('dims'))
                geoms.append(Point(h['at'][:2]).buffer(max(dd['w'], dd['d']) / 2 + 1.0 + extra))
        elif n in ('stairs', 'stair'):
            for c in L['connections']:
                if sp['id'] in c.get('places', []) and c.get('walk'):
                    if c['kind'] == 'path_stair':
                        geoms.append(LineString(c['plan']).buffer(c['width'] / 2 + 0.6))
                    elif c['kind'] == 'helix':
                        geoms.append(Point(c['center']).buffer(c['r_walk'] + c['width'] / 2 + 0.6))
                    elif c['kind'] == 'switchback':
                        geoms.append(Polygon(c['box']).buffer(0.6))
        elif isinstance(n, (int, float)):
            pass
        elif isinstance(n, dict):
            if 'near' in n:
                geoms.append(Point(n['near'][:2]).buffer(n.get('r', 1.0) + extra))
            elif 'poly' in n:
                geoms.append(Polygon(n['poly']).buffer(extra))                                  # numeric radius applies to the listed geometries via `extra`
        elif isinstance(n, str) and n.startswith('anchored:'):
            aid = n.split(':', 1)[1]
            for a in sp.get('anchored', []):
                if a['id'] == aid:
                    dd = dims(a['asset'], a.get('dims'))
                    geoms.append(Point(a['at'][:2]).buffer(max(dd['w'], dd['d']) / 2 + 0.4 + extra))
        elif isinstance(n, str) and n.startswith('space:'):
            o = LSP.get(n.split(':', 1)[1])
            if o and o.get('footprint'):
                geoms.append(Polygon(o['footprint']).buffer(0.2 + extra))
        elif n == 'anchored':
            for a in sp.get('anchored', []):
                dd = dims(a['asset'], a.get('dims'))
                geoms.append(Point(a['at'][:2]).buffer(max(dd['w'], dd['d']) / 2 + 0.4 + extra))
    return unary_union(geoms) if geoms else None


def sample_along(line, spacing, rng, start_off=None):
    ls = LineString(line)
    L_ = ls.length
    s = start_off if start_off is not None else rng.uniform(0, spacing[0] / 2)
    out = []
    while s <= L_:
        p = ls.interpolate(s)
        p2 = ls.interpolate(min(L_, s + 0.25)); p1 = ls.interpolate(max(0, s - 0.25))
        out.append((p.x, p.y, math.atan2(p2.y - p1.y, p2.x - p1.x), s))
        s += rng.uniform(*spacing)
    return out


def face_deg(face, x, y, path_angle, side_sign, sp, hero_at=None):
    if face is None:
        return None
    if isinstance(face, (int, float)):
        return float(face)
    if face == 'path':     # look back across to the path line
        return bearing(-side_sign * -math.sin(path_angle), -side_sign * math.cos(path_angle))
    if face == 'out':
        return bearing(side_sign * -math.sin(path_angle), side_sign * math.cos(path_angle))
    if face == 'along':
        return bearing(math.cos(path_angle), math.sin(path_angle))
    if face in ('hero',) and sp.get('hero'):
        hx, hy = sp['hero']['at'][:2]
        return bearing(hx - x, hy - y)
    if face == 'water':
        return bearing(-side_sign * -math.sin(path_angle), -side_sign * math.cos(path_angle))
    if face == 'wall':
        poly = Polygon(sp['footprint']); q = nearest_points(poly.exterior, Point(x, y))[0]
        return bearing(q.x - x, q.y - y)
    if face in ('center', 'in'):
        c = Polygon(sp['footprint']).centroid
        return bearing(c.x - x, c.y - y)
    return None


def z_for(sp, rule, d, rng):
    fz = sp['floor_z']
    if rule.get('z') is not None:
        return rule['z'], 'given'
    if 'height' in rule:
        h = rule['height']
        h = rng.uniform(*h) if isinstance(h, list) else h
        return fz + h, 'height'
    snap = rule.get('snap', d.get('snap', 'ground'))
    if snap == 'ceiling':
        top = sp.get('ceiling_z') or (fz + 6)
        return top - d['h'] - (0.4 if d.get('hang') else 0), 'ceiling'
    return fz, snap


def place_space(sp):
    out = []
    rng_base = sum(map(ord, sp['id']))
    footprint = Polygon(sp['footprint']) if sp.get('footprint') else None
    # the walk corridor (1.2 m clear along the spine and its branches) and doorway zones are kept free of
    # rule-placed items automatically; heroes and anchored pieces are deliberate and are flagged by the checks instead
    walk_lines = []
    if sp.get('spine') and len(sp['spine']) > 1:
        walk_lines.append([tuple(q[:2]) for q in sp['spine']])
    for key in ('branches', 'spurs', 'spine_branches'):
        for b in sp.get(key, []) or []:
            pts = b.get('points') or b.get('path') or b.get('spine') if isinstance(b, dict) else b
            if isinstance(pts, list) and len(pts) > 1 and all(isinstance(q, list) and len(q) >= 2 for q in pts):
                walk_lines.append([tuple(q[:2]) for q in pts])
    nav_keep = unary_union([LineString(l).buffer(0.6) for l in walk_lines] +
                           [Point(pr['at'][:2]).buffer(pr.get('width', 2) / 2 + 0.3) for pr in sp.get('portals', []) if isinstance(pr.get('at'), list)]) if walk_lines or sp.get('portals') else None
    if footprint is not None and LSP.get(sp['id'], {}).get('balcony'):
        footprint = footprint.union(Polygon(LSP[sp['id']]['balcony']))

    def add(pid, asset, x, y, z, yaw, rule_ref, snap='ground', dd=None, scale=1.0, seed=0, extra=None):
        d = dims(asset, dd)
        e = dict(id=pid, asset=asset, space=sp['id'], level=sp['level'], pos=[round(x, 3), round(y, 3), round(z, 3)],
                 facing_deg=round(yaw if yaw is not None else 0.0, 1), scale=round(scale, 3),
                 dims=dict(w=d['w'], d=d['d'], h=d['h']), snap=snap, embed=d.get('embed', 0.0), seed=seed, rule=rule_ref)
        if d.get('unknown'):
            e['unknown_asset'] = True
        if d.get('light'):
            e['light'] = d['light']
        if extra:
            e.update(extra)
        out.append(e)

    if sp.get('hero') and not (sp['hero'].get('borrowed_from') or sp['hero'].get('outside_ok')):
        h = sp['hero']
        z = h['at'][2] if len(h['at']) > 2 else sp['floor_z']
        add(f"{sp['id']}:hero", h['asset'], h['at'][0], h['at'][1], z, h.get('facing_deg', 0) if not isinstance(h.get('facing_deg'), (list, str)) else 0, 'hero',
            snap=dims(h['asset']).get('snap', 'ground'), dd=h.get('dims'), extra=dict(hero=True))
    for a in sp.get('anchored', []):
        if 'at' not in a:
            continue                                   # line / ring anchored items run through the rule engine below
        pts = a['at'] if isinstance(a['at'][0], list) else [a['at']]      # one point or a list of points
        try:
            fd = a.get('facing_deg', 0)
            for k, q in enumerate(pts):
                z = q[2] if len(q) > 2 else sp['floor_z']
                yaw = fd[k % len(fd)] if isinstance(fd, list) else fd
                if isinstance(yaw, str):
                    yaw = face_deg(yaw, q[0], q[1], 0, 1, sp) or 0
                add(f"{sp['id']}:{a['id']}" + (f"#{k}" if len(pts) > 1 else ''), a['asset'], q[0], q[1], z, yaw, f"anchored:{a['id']}",
                    snap=a.get('snap', dims(a['asset']).get('snap', 'ground')), dd=a.get('dims'))
        except Exception as ex:
            WARN.append(f"{sp['id']}:anchored {a.get('id')}: {type(ex).__name__}: {ex}")

    groups = {'lights': sp.get('lights', []), 'dressing': sp.get('dressing', []),
              'anchored': [dict(a, spacing=a.get('spacing', [1.5, 1.5] if a['asset'] == 'railing' else [3, 4])) for a in sp.get('anchored', []) if 'at' not in a]}
    for group in ('lights', 'dressing', 'anchored'):
        for ri, rule in enumerate(groups[group]):
          try:
            if rule.get('hidden') or not any(k in rule for k in ('at', 'along', 'ring', 'scatter')):
                WARN.append(f"{sp['id']}:{group}[{ri}] {rule.get('asset')}: no placement verb (shader/marker) - skipped")
                continue
            rng = random.Random(rng_base * 1000 + ri * 7 + (1 if group == 'lights' else 0))
            asset = rule['asset']; d = dims(asset, rule.get('dims'))
            ref = f'{group}[{ri}]'
            _rad = [a for a in rule.get('avoid', []) if isinstance(a, (int, float))]
            av = avoid_geom(sp, rule.get('avoid'), extra=max(_rad) if _rad else 0.0)
            sc = rule.get('scale'); variants = rule.get('variants') or list(range(1, 7))
            placed = []

            rad = max(d['w'], d['d']) * (max(sc) if sc else 1.0) / 2
            free_ok = rule.get('allow_on_nav') or ASSETS.get(asset, {}).get('marker') or ASSETS.get(asset, {}).get('deck') \
                or ASSETS.get(asset, {}).get('frame') or d.get('snap') in ('ceiling',) or rule.get('snap') == 'ceiling' or asset == 'stepping_stone'

            def ok(x, y, r):
                if av is not None and av.contains(Point(x, y)):
                    return False
                if not free_ok and nav_keep is not None and nav_keep.intersects(Point(x, y).buffer(rad)):
                    return False
                if footprint is not None and not footprint.buffer(0.05).contains(Point(x, y)) and not rule.get('outside_ok'):
                    return False
                md = rule.get('min_dist', 0)
                return all(math.hypot(x - px, y - py) >= md for px, py in placed)

            def emit(k, x, y, yaw):
                z, snap = z_for(sp, rule, d, rng)
                s = rng.uniform(*sc) if sc else 1.0
                add(f"{sp['id']}:{group}{ri}:{k}", asset, x, y, z, yaw, ref, snap=snap, dd=rule.get('dims'), scale=s,
                    seed=rng.choice(variants))
                placed.append((x, y))

            if 'at' in rule:
                pts = rule['at'] if isinstance(rule['at'][0], list) else [rule['at']]
                for k, p in enumerate(pts):
                    yaw = face_deg(rule.get('face'), p[0], p[1], 0, 1, sp)
                    z, snap = (p[2], 'given') if len(p) > 2 else z_for(sp, rule, d, rng)
                    add(f"{sp['id']}:{group}{ri}:{k}", asset, p[0], p[1], z, yaw if yaw is not None else rule.get('facing_deg', 0), ref,
                        snap=snap, dd=rule.get('dims'), scale=rng.uniform(*sc) if sc else 1.0, seed=rng.choice(variants))
            elif 'along' in rule:
                line = line_of(sp, rule['along'])
                sides = {'left': [1], 'right': [-1], 'both': [1, -1]}.get(rule.get('side', 'both' if rule.get('offset', 0) else 'left'), [1])
                k = 0
                for side in sides:
                    for x, y, ang, s in sample_along(line, rule.get('spacing', [4, 6]), rng):
                        off = rule.get('offset', 0.0)
                        jx = rng.uniform(-1, 1) * rule.get('jitter', 0.0); jy = rng.uniform(-1, 1) * rule.get('jitter', 0.0)
                        px = x - side * math.sin(ang) * off + jx; py = y + side * math.cos(ang) * off + jy
                        if rule.get('cluster'):
                            px += rng.uniform(-0.6, 0.6); py += rng.uniform(-0.4, 0.4)
                        if not ok(px, py, 0):
                            continue
                        yaw = face_deg(rule.get('face', 'path'), px, py, ang, side, sp)
                        emit(k, px, py, yaw); k += 1
            elif 'ring' in rule:
                c = rule['ring']
                if isinstance(c, str) and c.startswith('water:'):
                    wid = c.split(':', 1)[1]
                    wf = next((w.get('footprint') for w in sp.get('water', []) if w['id'] == wid), None) or LWATER.get(wid, {}).get('footprint')
                    g_ = Polygon(wf); cx, cy = g_.centroid.x, g_.centroid.y
                    if 'radius' not in rule:
                        rule = dict(rule, radius=math.sqrt(g_.area / math.pi) + 0.8)
                else:
                    cx, cy = (sp['hero']['at'][:2] if c == 'hero' else c[:2])
                R0 = rule.get('radius', 3.0)
                Rm = (sum(R0) / 2) if isinstance(R0, list) else R0
                sp_ = rule.get('spacing', 3); sp_ = sum(sp_) / 2 if isinstance(sp_, list) else sp_
                n = rule.get('count') or max(3, int(2 * math.pi * Rm / sp_))
                a0 = rng.uniform(0, 2 * math.pi)
                for k in range(n):
                    a = a0 + 2 * math.pi * k / n + rng.uniform(-1, 1) * rule.get('jitter_deg', 0) * math.pi / 180
                    R = rng.uniform(*R0) if isinstance(R0, list) else R0
                    px, py = cx + R * math.cos(a), cy + R * math.sin(a)
                    if not ok(px, py, 0):
                        continue
                    f = rule.get('face', 'center')
                    yaw = bearing(cx - px, cy - py) if f == 'center' else (bearing(px - cx, py - cy) if f == 'out' else face_deg(f, px, py, a, 1, sp))
                    emit(k, px, py, yaw)
            elif 'scatter' in rule:
                kind = rule['scatter']
                if kind == 'area' or isinstance(kind, list):
                    poly = rule.get('polygon') or rule.get('area') or (kind if isinstance(kind, list) else None)
                    area = Polygon(poly) if poly else footprint
                    kind = '_done'
                if kind == '_done':
                    pass
                elif kind == 'edge_band':
                    a, b = rule.get('band', [0.3, 2.5])
                    area = footprint.buffer(-a).difference(footprint.buffer(-b)) if footprint.buffer(-b).area > 0 else footprint.buffer(-a)
                else:
                    raise ValueError(f'scatter kind {kind}')
                if av is not None:
                    area = area.difference(av)
                n = int(area.area * rule.get('density', 0.05))
                minx, miny, maxx, maxy = area.bounds
                tries, k = 0, 0
                md = rule.get('min_dist', max(d['w'], d['d']) * 0.9)
                while k < n and tries < n * 60:
                    tries += 1
                    px, py = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
                    if not area.contains(Point(px, py)):
                        continue
                    if any(math.hypot(px - qx, py - qy) < md for qx, qy in placed):
                        continue
                    if not free_ok and nav_keep is not None and nav_keep.intersects(Point(px, py).buffer(rad)):
                        continue
                    f = rule.get('face', 'wall')
                    yaw = face_deg(f, px, py, 0, 1, sp)
                    yaw = (yaw if yaw is not None else 0) + rng.uniform(-25, 25)
                    emit(k, px, py, yaw); k += 1
          except Exception as ex:
            WARN.append(f"{sp['id']}:{group}[{ri}] {rule.get('asset')}: {type(ex).__name__}: {ex}")
    # overrides (deliberate nudges with reasons)
    for e in out:
        o = OVR.get(e['id'])
        if o:
            e['pos'][0] += o.get('dx', 0); e['pos'][1] += o.get('dy', 0); e['pos'][2] += o.get('dz', 0)
            e['facing_deg'] = (e['facing_deg'] + o.get('dyaw', 0)) % 360
            e['override'] = o.get('reason', '')
    return out


def main(only):
    path = os.environ.get('KZ_PLACEMENTS') or os.path.join(ROOT, '3d', 'placements.json')
    prev = json.load(open(path)) if os.path.exists(path) else dict(placements=[])
    keep = [] if os.environ.get('KZ_PLACEMENTS') else [p for p in prev['placements'] if only and p['space'] not in only]
    allp = list(keep); counts = {}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from spaces_io import load_spaces
    for sid_, sp in load_spaces().items():
        if only and sp['id'] not in only:
            continue
        ps = place_space(sp); allp += ps
        counts[sp['id']] = {}
        for p in ps:
            counts[sp['id']][p['rule']] = counts[sp['id']].get(p['rule'], 0) + 1
    tmp = path + '.tmp'
    json.dump(dict(note='Generated by tools/assembly/place.py. Do not edit; change the rules in 3d/spaces/ or add a reasoned nudge to 3d/overrides.json.',
                   warnings=WARN, placements=allp), open(tmp, 'w'), indent=1)
    os.replace(tmp, path)
    for sid, c in counts.items():
        print(sid, sum(c.values()))
    print('TOTAL', len(allp), 'placements;', len(WARN), 'rule warnings')
    for w in WARN:
        print('  WARN', w)


if __name__ == '__main__':
    main(sys.argv[1:])
