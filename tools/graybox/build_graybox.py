"""Graybox of Kazan-yu from 3d/layout.json, built in Blender.

  /home/agent-tom/.local/bin/blender -b -P tools/graybox/build_graybox.py -- [--out 3d/blend/graybox.blend]

What it builds (one collection per level):
  shell_<level>   interior of every enclosed space: union of space prisms + portal boxes + shafts,
                  normals inward, solidified outward so it reads from both sides
  stairs          real treads for every stair connection (17 cm risers)
  water           water surfaces at their exact z (pools get basins)
  terrain         outdoor heightfield (mountain, ground flats, flank cut by the Terrace Path, sea cliffs)
  shafts          lift core, slide tube stand-in
Proxies (inventory assets) are added later by tools/assembly/place.py.
"""
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(ROOT, '.bpy_deps'))   # shapely for Blender's Python (pip install --target .bpy_deps shapely)
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(ROOT, argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, '3d', 'blend', 'graybox.blend')
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
SP = {s['id']: s for s in L['spaces']}
import glob
sys.path.insert(0, os.path.join(ROOT, 'tools', 'assembly'))
from spaces_io import load_spaces
SPACEFILES = load_spaces(ROOT)


def space_water():
    """water bodies declared in space files: (space, id, kind, polygon, z, rim_z, depth)"""
    from shapely.geometry import LineString as _LS, Polygon as _PG
    out = []
    for sid, j in SPACEFILES.items():
        for w in j.get('water', []):
            if w.get('kind') == 'fall' or w.get('z') is None:
                continue
            if 'path' in w:
                g = _LS(w['path']).buffer(w.get('width', 2.0) / 2, cap_style=1)
            elif 'footprint' in w:
                g = _PG(w['footprint'])
            else:
                continue
            if g.geom_type != 'Polygon':
                continue
            poly = [tuple(c) for c in list(g.exterior.coords)[:-1]]
            rim = w['rim_z'] if w.get('rim_z') is not None else w['z'] + 0.05
            depth = w['depth'] if w.get('depth') is not None else (0.6 if w.get('kind') == 'flow' else 0.9)
            out.append((sid, w['id'], w.get('kind', 'still'), poly, w['z'], rim, depth))
    return out
LEVELS = {l['id']: l for l in L['levels']}
RISER, TREAD = L['step']['riser'], L['step']['tread']

# ------------------------------------------------------------------ scene helpers
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    return sc


def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in (parent or bpy.context.scene.collection).children:
        (parent or bpy.context.scene.collection).children.link(c)
    return c


MATS = {}
def mat(name, rgba, rough=0.8, emit=None, alpha=None):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = rgba
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = emit[:3] + (1,)
        b.inputs['Emission Strength'].default_value = emit[3]
    if alpha is not None:
        b.inputs['Alpha'].default_value = alpha
        b.inputs['Transmission Weight'].default_value = 0.0
    m.diffuse_color = rgba
    MATS[name] = m
    return m


def obj_from_bm(name, bm, c, material=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    if material:
        me.materials.append(material)
    return o


def ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return poly if a > 0 else poly[::-1]


def prism_bm(bm, poly, z0, z1):
    poly = ccw(poly)
    bot = [bm.verts.new((x, y, z0)) for x, y in poly]
    top = [bm.verts.new((x, y, z1)) for x, y in poly]
    bm.faces.new(bot[::-1]); bm.faces.new(top)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))


def prism(name, poly, z0, z1, c, material=None):
    bm = bmesh.new(); prism_bm(bm, poly, z0, z1)
    return obj_from_bm(name, bm, c, material)


def circle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def box_bm(bm, center, size, rot_z=0.0):
    """size = (sx, sy, sz); center = bottom-centre? no: full centre."""
    cx, cy, cz = center; sx, sy, sz = size
    R = Matrix.Rotation(rot_z, 3, 'Z')
    vs = []
    for dz in (-0.5, 0.5):
        for dx, dy in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
            p = R @ Vector((dx * sx, dy * sy, dz * sz))
            vs.append(bm.verts.new((cx + p.x, cy + p.y, cz + p.z)))
    b, t = vs[:4], vs[4:]
    bm.faces.new(b[::-1]); bm.faces.new(t)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b[i], b[j], t[j], t[i]))


def apply_mods(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


# ------------------------------------------------------------------ shells
def enclosed(s):
    return s['ceiling_z'] is not None and s['kind'] not in ('outdoor',) and s['level'] not in ('summit',)


def portal_boxes(level_ids, tmpc):
    out = []
    for p in L['portals']:
        a, b = SP.get(p['a']), SP.get(p['b'])
        if not a or a['id'] not in level_ids:
            continue
        fz = p.get('z0', min(a['floor_z'], b['floor_z']) if b else a['floor_z'])
        h = p.get('height', 3.2)
        w = p['width']; dp = p.get('depth', w)
        hw, hd = w / 2 + 0.6, dp / 2 + 0.6
        if 'depth' in p:     # thin opening through a wall running N-S (wide in y)
            hw, hd = dp / 2 + 0.6, w / 2 + 0.6
        out.append(prism(f"portal_{p['id']}", [(p['at'][0] - hw, p['at'][1] - hd), (p['at'][0] + hw, p['at'][1] - hd),
                                                (p['at'][0] + hw, p['at'][1] + hd), (p['at'][0] - hw, p['at'][1] + hd)],
                         fz, fz + h, tmpc))
    return out


def shaft_prisms(level, tmpc):
    out = []
    lx, ly = L['lift']['at']
    if level == 'ground':          # one continuous spiral well from the hall floor to B4 (all levels are one union)
        out.append(prism('well', circle(lx, ly, L['lift']['shaft_r'] - 0.01), -100.5, 0.6, tmpc))
    sx, sy = L['slide_shaft']['at']
    if level == 'b1':
        out.append(prism('slideshaft', circle(sx, sy, L['slide_shaft']['r']), -67.5, -12.0, tmpc))
    if level == 'b1':                                  # Mist Steps hall (B1 -> B2)
        c = next(c for c in L['connections'] if c['id'] == 'mist_steps')
        xs = [p[0] for p in c['box']]; ys = [p[1] for p in c['box']]
        out.append(prism('mist_steps_hall', [(min(xs) - 0.5, min(ys)), (max(xs) + 0.5, min(ys)), (max(xs) + 0.5, max(ys) + 1), (min(xs) - 0.5, max(ys) + 1)], -40.6, -14.0, tmpc))
    if level == 'ground':                              # culvert slot only (no walk)
        pass
    return out


def basin_prisms(level, tmpc):
    out = []
    for w in L['water']:
        if w.get('level') == level and w['kind'] == 'still' and 'footprint' in w and level != 'b3' or (w.get('level') == level == 'b3' and w['id'] in ('w_geyser', 'w_splash')):
            depth = 1.4 if w['id'] in ('w_mirror',) else 1.0
            out.append(prism(f"basin_{w['id']}", w['footprint'], w['rim_z'] - depth, w['rim_z'] + 0.01, tmpc))
    for sid, wid, kind, poly, z, rim, depth in space_water():
        if SP.get(sid, {}).get('level') == level and enclosed(SP[sid]):
            out.append(prism(f'basin_{sid}_{wid}', poly, rim - depth, rim + 0.01, tmpc))
    return out


def build_shell(levels, c, tmpc, material):
    level = levels
    ids = [s['id'] for s in L['spaces'] if s['level'] in levels and enclosed(s) and s['footprint']]
    # B1 corridors are ankle-deep pools: bed 0.2 m below the walk datum, stepping stones on top
    bed = lambda s: s['floor_z'] - 0.2 if (s['level'] == 'b1' and s['kind'] == 'corridor') else s['floor_z']
    parts = [prism(f'sp_{i}', SP[i]['footprint'], bed(SP[i]), SP[i]['ceiling_z'], tmpc) for i in ids]
    parts += portal_boxes(set(ids), tmpc)
    for lv in levels:
        parts += shaft_prisms(lv, tmpc) + basin_prisms(lv, tmpc)
    if 'b3' in levels:                                  # sea mouth: carry the wave grotto out past the cliff
        parts.append(prism('mouth', [(196, 16), (216, 14), (216, 62), (196, 62)], -71.0, -52.0, tmpc))
    base = parts[0]
    for o in parts[1:]:
        o.parent = None
    opc = bpy.data.collections.new(f'_ops_{level}')
    for o in parts[1:]:
        tmpc.objects.unlink(o); opc.objects.link(o)
    mod = base.modifiers.new('u', 'BOOLEAN'); mod.operation = 'UNION'; mod.solver = 'MANIFOLD'
    mod.operand_type = 'COLLECTION'; mod.collection = opc
    apply_mods(base)
    for o in list(opc.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(opc)
    tmpc.objects.unlink(base); c.objects.link(base)
    base.name = 'shell'
    # inward normals; open the sea mouth end cap
    bm = bmesh.new(); bm.from_mesh(base.data)
    # n-gons with holes (floors around the stair wells) break solidify and fan triangulation: ear-clip them now
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    if 'b3' in levels:
        cap = [f for f in bm.faces if all(v.co.x > 215.5 for v in f.verts)]
        bmesh.ops.delete(bm, geom=cap, context='FACES')
    bm.to_mesh(base.data); bm.free()
    base.data.materials.clear(); base.data.materials.append(material)
    sol = base.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.6; sol.offset = -1.0  # grows outward (normals point in)
    return base


# ------------------------------------------------------------------ stairs
def helix_stairs(c, bm, r_in, r_out, thick=0.32):
    cx, cy = c['center']
    pts = c['path']
    for k in range(len(pts) - 1):
        a0 = math.atan2(pts[k][1] - cy, pts[k][0] - cx); a1 = math.atan2(pts[k + 1][1] - cy, pts[k + 1][0] - cx)
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        z = pts[k + 1][2]
        n = max(1, int(abs(d) / 0.08))
        ring_i = [(cx + r_in * math.cos(a0 + d * t / n), cy + r_in * math.sin(a0 + d * t / n)) for t in range(n + 1)]
        ring_o = [(cx + r_out * math.cos(a0 + d * t / n), cy + r_out * math.sin(a0 + d * t / n)) for t in range(n + 1)]
        poly = ring_o + ring_i[::-1]
        prism_bm(bm, poly, z - thick, z)


def polyline_at(plan, s):
    """point and direction at arc length s along a 2D polyline"""
    acc = 0.0
    for (x0, y0), (x1, y1) in zip(plan, plan[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if acc + seg >= s or (x1, y1) == tuple(plan[-1]):
            t = min(1.0, max(0.0, (s - acc) / seg)) if seg else 0.0
            return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t), math.atan2(y1 - y0, x1 - x0)
        acc += seg
    return tuple(plan[-1]), 0.0


def path_profile(c):
    """(s0, s1, z) tread intervals for a path stair: [level walk][run][landing]..."""
    n, rise = c['steps'], c['riser']
    runs = c['runs']; spare = c['level_walk'] / runs
    out, s, z, i = [], 0.0, c['z_top'], 0
    for r in range(runs):
        k = min(14, n - i)
        out.append((s, s + spare, z)); s += spare
        for _ in range(k):
            z -= rise; out.append((s, s + TREAD, z)); s += TREAD; i += 1
        if r < runs - 1:
            out.append((s, s + 1.5, z)); s += 1.5
    return out


def path_stairs(c, bm, depth=0.6):
    plan = c['plan']; w = c['width']
    for s0, s1, z in path_profile(c):
        if s1 - s0 < 1e-3:
            continue
        # split long level pieces at polyline corners
        m = max(1, int((s1 - s0) / 0.6))
        for q in range(m):
            a, b = s0 + (s1 - s0) * q / m, s0 + (s1 - s0) * (q + 1) / m
            (x, y), ang = polyline_at(plan, (a + b) / 2)
            box_bm(bm, (x, y, z - depth / 2), (b - a + 0.04, w, depth), ang)


def switchback_stairs(c, bm):
    w = c['flight_width']
    fl = c['flights']
    for i, f in enumerate(fl):
        d = 1 if f['y_end'] > f['y_start'] else -1
        y, z = f['y_start'], f['z_start']
        k = 0
        for st in range(f['steps']):
            z -= c['riser']
            box_bm(bm, (f['x'], y + d * TREAD / 2, z - 0.3), (w, TREAD + 0.02, 0.6))
            y += d * TREAD; k += 1
            if k % 14 == 0 and st < f['steps'] - 1:
                box_bm(bm, (f['x'], y + d * 0.75, z - 0.3), (w, 1.5, 0.6)); y += d * 1.5
        # turn landing joining this flight's end to the next flight's start
        if i < len(fl) - 1:
            x0 = f['x'] - w / 2; x1 = fl[i + 1]['x'] + w / 2
            box_bm(bm, ((x0 + x1) / 2, f['y_end'] + d * 1.25, z - 0.3), (x1 - x0, 2.5, 0.6))
    # top and bottom landings
    f0, fN = fl[0], fl[-1]
    d0 = 1 if f0['y_end'] > f0['y_start'] else -1
    box_bm(bm, (f0['x'], f0['y_start'] - d0 * 1.5, f0['z_start'] - 0.3), (w, 3.0, 0.6))
    dN = 1 if fN['y_end'] > fN['y_start'] else -1
    box_bm(bm, (fN['x'], fN['y_end'] + dN * 1.5, fN['z_end'] - 0.3), (w, 3.0, 0.6))


def walkway(c, bm):
    plan = c['plan']; L_ = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(plan, plan[1:]))
    m = max(1, int(L_ / 0.6))
    for q in range(m):
        (x, y), ang = polyline_at(plan, L_ * (q + 0.5) / m)
        box_bm(bm, (x, y, c['z'] - 0.3), (L_ / m + 0.04, c['width'], 0.6), ang)


# ------------------------------------------------------------------ water
def water_surfaces(c, m_still, m_flow, m_sea):
    for w in L['water']:
        if w['kind'] == 'still' and 'footprint' in w:
            bm = bmesh.new(); f = bm.faces.new([bm.verts.new((x, y, w['z'])) for x, y in ccw(w['footprint'])])
            obj_from_bm(w['id'], bm, c, m_still)
    # river: footprint with z sloping along x (east high, west low)
    rv = next(w for w in L['water'] if w['id'] == 'w_river')
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, rv['z_end'] + (rv['z_start'] - rv['z_end']) * max(0, min(1, (x - 30) / 170)))) for x, y in ccw(rv['footprint'])]
    bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=bm.faces)
    obj_from_bm('w_river', bm, c, m_flow)
    # lazy river annulus
    lz = next(w for w in L['water'] if w['id'] == 'w_lazy')
    cl = lz['centerline']; cx = sum(p[0] for p in cl) / len(cl); cy = sum(p[1] for p in cl) / len(cl)
    bm = bmesh.new(); ring = []
    for x, y in cl:
        dx, dy = x - cx, y - cy; r = math.hypot(dx, dy)
        ring.append((bm.verts.new((cx + dx * (r - lz['width'] / 2) / r, cy + dy * (r - lz['width'] / 2) / r, lz['z_end'])),
                     bm.verts.new((cx + dx * (r + lz['width'] / 2) / r, cy + dy * (r + lz['width'] / 2) / r, lz['z_end']))))
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        bm.faces.new((a[0], b[0], b[1], a[1]))
    obj_from_bm('w_lazy', bm, c, m_flow)
    # B1 corridor water: one level sheet under every corridor / junction footprint
    bwz = next(w for w in L['water'] if w['id'] == 'w_b1_corridors')['z']
    for s in L['spaces']:
        if s['level'] == 'b1' and s['kind'] == 'corridor':
            bm = bmesh.new(); bm.faces.new([bm.verts.new((x, y, bwz)) for x, y in ccw(s['footprint'])])
            obj_from_bm(f'w_{s["id"]}', bm, c, m_still)
    # water declared in space files
    for sid, wid, kind, poly, z, rim, depth in space_water():
        bm = bmesh.new(); bm.faces.new([bm.verts.new((x, y, z)) for x, y in ccw(poly)])
        obj_from_bm(f'w_{sid}_{wid}', bm, c, m_flow if kind == 'flow' else m_still)
    # sea: big plane, one level
    sea = next(w for w in L['water'] if w['id'] == 'w_sea')
    bm = bmesh.new(); bm.faces.new([bm.verts.new(v) for v in ((150, -150, sea['z']), (600, -150, sea['z']), (600, 350, sea['z']), (150, 350, sea['z']))])
    obj_from_bm('w_sea_open', bm, c, m_sea)
    bm = bmesh.new(); bm.faces.new([bm.verts.new((x, y, sea['z'])) for x, y in ccw(sea['footprint'])])
    obj_from_bm('w_sea_grotto', bm, c, m_sea)
    # Thunder Curtain sheet
    th = next(w for w in L['water'] if w['id'] == 'w_thunder')
    (x0, y0), (x1, y1) = th['lip']
    bm = bmesh.new(); bm.faces.new([bm.verts.new(v) for v in ((x0, y0, th['z_top']), (x1, y1, th['z_top']), (x1, y1 - 2.5, th['z_bottom']), (x0, y0 - 2.5, th['z_bottom']))])
    obj_from_bm('w_thunder_sheet', bm, c, m_flow)


# ------------------------------------------------------------------ terrain
def poly_mask(X, Y, poly):
    """vectorised even-odd point in polygon"""
    inside = np.zeros(X.shape, bool)
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % n]
        cond = ((y0 > Y) != (y1 > Y)) & (X < (x1 - x0) * (Y - y0) / ((y1 - y0) if y1 != y0 else 1e-9) + x0)
        inside ^= cond
    return inside


def dist_to_poly(X, Y, poly):
    d = np.full(X.shape, np.inf)
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0; l2 = dx * dx + dy * dy or 1e-9
        t = np.clip(((X - x0) * dx + (Y - y0) * dy) / l2, 0, 1)
        d = np.minimum(d, np.hypot(X - (x0 + t * dx), Y - (y0 + t * dy)))
    return d


PLATEAU = [(46, 64), (82, 62), (150, 60), (166, 80), (190, 86), (190, 106), (140, 106), (120, 112), (100, 117), (46, 117)]
ISLAND = [(-120, 4), (60, 2), (150, 4), (200, 6), (214, 12), (214, 64), (200, 70), (199, 119.5), (100, 119.5), (-120, 119.5)]


def build_terrain(c, material, res=1.0):
    x = np.arange(-120, 240 + res, res); y = np.arange(-40, 160 + res, res)
    X, Y = np.meshgrid(x, y)
    Z = np.zeros(X.shape)
    # west hills beyond the grid, road kept flat
    hills = 6 * (np.sin(X * 0.05) * np.cos(Y * 0.07) + 1) * np.clip(-X / 40, 0, 1)
    Z += hills * (np.abs(Y - 57) > 8)
    # mountain
    d = dist_to_poly(X, Y, PLATEAU); inside = poly_mask(X, Y, PLATEAU)
    for s in L['spaces']:                       # the plateau holds every summit space with a 3 m margin
        if s['level'] == 'summit' and s['footprint']:
            ds = dist_to_poly(X, Y, s['footprint']) - 3.0
            ins = poly_mask(X, Y, s['footprint'])
            inside |= ins | (ds < 0)
            d = np.minimum(d, np.maximum(ds, 0))
    d = np.where(inside, 0, d)
    rng = np.random.default_rng(7)
    def fbm(X, Y, oct=5, f=0.02):
        out = np.zeros(X.shape); a = 1.0
        for o in range(oct):
            ph = rng.uniform(0, 100, 4)
            out += a * np.sin(X * f + ph[0]) * np.cos(Y * f * 1.3 + ph[1]) + a * 0.5 * np.sin((X + Y) * f * 0.7 + ph[2])
            f *= 2.03; a *= 0.5
        return out
    N = fbm(X, Y)
    D = np.where(X < 50, 40.0, np.where(Y < 66, 20.0, 9.0)) * (1 + 0.25 * N)
    t = np.clip(1 - d / np.maximum(D, 3), 0, 1)
    M = np.where(inside, 120.0 + 0.6 * N, 120.0 * (t ** 0.7) + 3.0 * N * t * (1 - t) * 4)
    Z = np.maximum(Z, M)
    # flank shaped by the Terrace Path: cones under each point of the path, then cut the path ledge
    tp = next(c_ for c_ in L['connections'] if c_['id'] == 'terrace_path')
    prof = path_profile(tp); plan = tp['plan']
    samples = []
    for s0, s1, z in prof:
        for s in np.arange(s0, s1, 0.5):
            (px, py), _ = polyline_at(plan, s); samples.append((px, py, z))
    samples = np.array(samples)
    cone = np.full(X.shape, -1e9); cut = np.full(X.shape, np.nan); cutd = np.full(X.shape, np.inf)
    win = (X > -10) & (X < 90) & (Y > 50) & (Y < 125)
    xi, yi = X[win], Y[win]; cone_w = np.full(xi.shape, -1e9); cut_w = np.full(xi.shape, np.nan); cd_w = np.full(xi.shape, np.inf)
    for px, py, z in samples:
        r = np.hypot(xi - px, yi - py)
        cone_w = np.maximum(cone_w, z - 2.6 * np.maximum(r - tp['width'] / 2 - 0.5, 0))
        near = r < cd_w
        cd_w = np.where(near, r, cd_w); cut_w = np.where(near, z, cut_w)
    zw = Z[win]
    zw = np.maximum(zw, cone_w)
    zw = np.where(cd_w <= tp['width'] / 2 + 0.6, cut_w - 0.02, zw)
    Z[win] = zw
    # ground flats and lower pools
    for s in L['spaces']:
        if s['level'] == 'ground' and s['footprint']:
            m = poly_mask(X, Y, s['footprint']) | (dist_to_poly(X, Y, s['footprint']) < 0.8)
            if s['id'] in ('g_arrival', 'g_changing'):
                continue
            Z = np.where(m, s['floor_z'] - (0.02 if s['kind'] == 'outdoor' else 0), Z)
    # summit: plateau features
    for s in L['spaces']:
        if s['level'] == 'summit' and s['footprint']:
            m = poly_mask(X, Y, s['footprint'])
            Z = np.where(m, s['floor_z'], Z)
    for sid, wid, kind, poly, z, rim, depth in space_water():
        if SP.get(sid) and not enclosed(SP[sid]):
            Z = np.where(poly_mask(X, Y, poly), rim - depth, Z)
    cal = next(w for w in L['water'] if w['id'] == 'w_caldera')
    Z = np.where(poly_mask(X, Y, cal['footprint']), cal['rim_z'] - 1.6, Z)
    spr = next(w for w in L['water'] if w['id'] == 'w_spring')
    Z = np.where(poly_mask(X, Y, spr['footprint']), spr['rim_z'] - 1.0, Z)
    # sea cliffs outside the island
    isl = poly_mask(X, Y, ISLAND)
    di = dist_to_poly(X, Y, ISLAND)
    Z = np.where(isl, Z, np.maximum(-76.0, -76.0 + 76.0 * np.clip(1 - di / 3.0, 0, 1) * 0))  # vertical sea cliffs
    # mesh
    ny, nx = Z.shape
    bm = bmesh.new()
    V = [[bm.verts.new((X[j, i], Y[j, i], Z[j, i])) for i in range(nx)] for j in range(ny)]
    mouth = lambda xs, ys, zs: min(xs) > 195 and min(xs) < 217 and 12 < sum(ys) / 4 < 66 and min(zs) < -45
    for j in range(ny - 1):
        for i in range(nx - 1):
            q = (V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i])
            xs = [v.co.x for v in q]; ys = [v.co.y for v in q]; zs = [v.co.z for v in q]
            if mouth(xs, ys, zs):
                continue
            bm.faces.new(q)
    o = obj_from_bm('terrain', bm, c, material)
    # headland wall over the sea mouth
    prism('sea_mouth_lintel', [(211, 12), (213.5, 12), (213.5, 66), (211, 66)], -52.0, 0.0, c, material)
    return o


# ------------------------------------------------------------------ main
def main():
    sc = reset()
    m_wall = mat('gb_rock', (0.16, 0.16, 0.17, 1), 0.9)
    m_hall = mat('gb_hall', (0.42, 0.36, 0.30, 1), 0.7)
    m_stair = mat('gb_stair', (0.55, 0.47, 0.36, 1), 0.7)
    m_terr = mat('gb_terrain', (0.13, 0.13, 0.13, 1), 0.95)
    m_still = mat('gb_water', (0.05, 0.42, 0.42, 1), 0.05)
    m_flow = mat('gb_water_flow', (0.15, 0.60, 0.58, 1), 0.1)
    m_sea = mat('gb_sea', (0.03, 0.12, 0.20, 1), 0.08)
    m_core = mat('gb_core', (0.6, 0.45, 0.2, 1), 0.4)
    m_lava = mat('gb_lava', (1.0, 0.3, 0.05, 1), 0.6, emit=(1.0, 0.35, 0.05, 6.0))
    root = coll('graybox')
    tmpc = coll('_tmp', root)
    c = coll('shell', root)
    build_shell(('ground', 'b1', 'b2', 'b3', 'b4'), c, tmpc, m_wall)
    # suites (provisional boxes carved into the north face), open on the balcony side
    cs = coll('level_cliff', root)
    for s in L['spaces']:
        if s['level'] == 'cliff':
            o = prism(s['id'], s['footprint'], s['floor_z'], s['ceiling_z'], cs, m_hall)
            bm = bmesh.new(); bm.from_mesh(o.data)
            ymax = max(v.co.y for v in bm.verts)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(abs(v.co.y - ymax) < 1e-4 for v in f.verts)], context='FACES')
            bm.to_mesh(o.data); bm.free()
            o.modifiers.new('t', 'SOLIDIFY').thickness = 0.3
            prism(s['id'] + '_balcony', s['balcony'], s['floor_z'] - 0.3, s['floor_z'], cs, m_stair)
    st = coll('stairs', root)
    for c in L['connections']:
        bm = bmesh.new()
        if c['kind'] == 'helix':
            r = c['r_walk']; helix_stairs(c, bm, r - c['width'] / 2, r + c['width'] / 2 + (0.0 if c['id'] == 'lava_stair' else 1.0))
        elif c['kind'] == 'path_stair':
            path_stairs(c, bm, depth=1.2 if c['id'] in ('terrace_path',) else 0.6)
        elif c['kind'] == 'switchback':
            switchback_stairs(c, bm)
        elif c['kind'] == 'walkway':
            walkway(c, bm)
        else:
            bm.free(); continue
        obj_from_bm(c['id'], bm, st, m_stair)
    # floors under portals between different floor heights are handled by stairs; lift core + slide tube stand-ins
    sh = coll('shafts', root)
    bm = bmesh.new()      # lift bridges over the spiral well, opposite each stair landing
    for p in L['portals']:
        if p.get('bridge'):
            (x0, y0), (x1, y1) = p['bridge']
            ang = math.atan2(y1 - y0, x1 - x0); ln = math.hypot(x1 - x0, y1 - y0) + 0.4
            box_bm(bm, ((x0 + x1) / 2, (y0 + y1) / 2, p['z0'] - 0.25), (ln, p['width'], 0.5), ang)
    obj_from_bm('lift_bridges', bm, sh, m_stair)
    lx, ly = L['lift']['at']
    prism('lift_core', circle(lx, ly, 2.2, 32), -100.0, 9.0, sh, m_core)
    sx, sy = L['slide_shaft']['at']
    sl = next(c for c in L['connections'] if c['id'] == 'glass_slide')
    bm = bmesh.new()
    n = 160
    for k in range(n):
        t0, t1 = k / n, (k + 1) / n
        a0, a1 = -t0 * 2.6 * 2 * math.pi, -t1 * 2.6 * 2 * math.pi
        z0 = sl['z_top'] + (sl['z_bottom'] - sl['z_top']) * t0; z1 = sl['z_top'] + (sl['z_bottom'] - sl['z_top']) * t1
        box_bm(bm, (sx + sl['r'] * math.cos((a0 + a1) / 2), sy + sl['r'] * math.sin((a0 + a1) / 2), (z0 + z1) / 2), (1.4, 0.9 * sl['r'] * abs(a1 - a0) + 0.2, 1.2), (a0 + a1) / 2)
    obj_from_bm('slide_tube', bm, sh, m_core)
    # lava stand-ins (arrival window, B4 glass, slide shaft glow)
    lv = coll('lava', root)
    # emissive stand-ins just inside the glass walls (the lava itself is beyond the glass)
    prism('lava_arrival', [(44, 79.3), (78, 79.3), (78, 79.5), (44, 79.5)], 0.6, 12.5, lv, m_lava)
    prism('lava_b4', [(42, 6.3), (120, 6.3), (120, 6.5), (42, 6.5)], -99.6, -92.5, lv, m_lava)
    prism('lava_slide', circle(150, 50, 8.4, 32)[8:20] + circle(150, 50, 8.6, 32)[8:20][::-1], -67.0, -20.0, lv, m_lava)
    # rimstone terraces (stand-in for the rimstone_terrace generator): stepped trays NW -> SE
    from shapely.geometry import Polygon as _PG, box as _box
    from shapely import affinity as _aff
    rw = next(w for w in L['water'] if w['id'] == 'w_rimstone')
    rim = _PG(SP['b3_rimstone']['footprint'])
    a0, a1 = Vector((50, 72, 0)), Vector((84, 30, 0)); d = (a1 - a0); Lr = d.length; d.normalize()
    ang = math.degrees(math.atan2(d.y, d.x))
    rc = coll('rimstone', root); bm = bmesh.new(); bmw = bmesh.new()
    n = rw['tiers']
    for i in range(n):
        z = rw['z_top'] + (rw['z_bottom'] - rw['z_top']) * i / (n - 1)
        t0, t1 = Lr * i / n - 2, Lr * (i + 1) / n
        strip = _aff.rotate(_box(t0, -60, t1, 60), ang, origin=(0, 0), use_radians=False)
        strip = _aff.translate(strip, a0.x, a0.y)
        g = rim.intersection(strip)
        if g.is_empty:
            continue
        for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
            if gg.geom_type != 'Polygon' or gg.area < 1:
                continue
            poly = [tuple(c) for c in list(gg.exterior.coords)[:-1]]
            prism_bm(bm, poly, -67.0, z - 0.35)                      # pool floor
            pin = gg.buffer(-0.45)
            if pin.geom_type == 'Polygon' and pin.area > 0.5:
                bmw.faces.new([bmw.verts.new((x, y, z)) for x, y in ccw([tuple(c) for c in list(pin.exterior.coords)[:-1]])])
            # rim (lip) along the downstream edge of the tray, 5 cm above the water
            lip = gg.difference(_aff.translate(gg, -d.x * 0.45, -d.y * 0.45))
            for lg in (lip.geoms if hasattr(lip, 'geoms') else [lip]):
                if lg.geom_type == 'Polygon' and lg.area > 0.05:
                    prism_bm(bm, [tuple(c) for c in list(lg.exterior.coords)[:-1]], z - 0.35, z + 0.05)
    obj_from_bm('rimstone_trays', bm, rc, m_stair)
    obj_from_bm('w_rimstone_pools', bmw, rc, m_still)
    ss = coll('stepping_stones', root)
    bm = bmesh.new()
    for s in L['spaces']:
        if s['level'] == 'b1' and s['kind'] == 'corridor' and s.get('centerline'):
            cl = s['centerline']; tot = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(cl, cl[1:]))
            for k in range(int(tot / 0.62)):
                (x, y), ang = polyline_at(cl, k * 0.62 + 0.3)
                off = 0.28 * math.sin(k * 1.7)
                prism_bm(bm, circle(x - math.sin(ang) * off, y + math.cos(ang) * off, 0.29, 10), s['floor_z'] - 0.2, s['floor_z'])
    obj_from_bm('stepping_stones', bm, ss, m_stair)
    wc = coll('water', root)
    water_surfaces(wc, m_still, m_flow, m_sea)
    tc = coll('terrain', root)
    build_terrain(tc, m_terr)
    bpy.data.collections.remove(tmpc)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print('SAVED', OUT)


main()
