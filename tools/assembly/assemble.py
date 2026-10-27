"""Assemble proxies from 3d/placements.json into the graybox and snap them to real surfaces.

  blender -b 3d/blend/graybox.blend -P tools/assembly/assemble.py -- [--out 3d/blend/assembled.blend]

Writes the assembled .blend (collection 'proxies' + 'proxy_lights') and 3d/placements_resolved.json
(final transforms + snap results) which checks/placement.py reads.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(ROOT, argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, '3d', 'blend', 'assembled.blend')
P = json.load(open(os.environ.get('KZ_PLACEMENTS') or os.path.join(ROOT, '3d', 'placements.json')))['placements']
L = json.load(open(os.path.join(ROOT, '3d', 'layout.json')))
WATER_Z = {w['id']: w.get('z', w.get('z_end')) for w in L['water']}


def kelvin_rgb(k):
    if not k:
        return (1.0, 0.25, 0.75)
    t = k / 100.0
    r = 255 if t <= 66 else 329.7 * ((t - 60) ** -0.1332)
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * ((t - 60) ** -0.0755)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    return tuple(max(0, min(255, c)) / 255 for c in (r, g, b))


def world_bvh():
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name.startswith('w_') or 'proxies' in [c.name for c in o.users_collection]:
            continue
        e = o.evaluated_get(dg); me = e.to_mesh()
        off = len(verts); M = o.matrix_world
        verts += [M @ v.co for v in me.vertices]
        me.calc_loop_triangles()
        polys += [[off + i for i in t.vertices] for t in me.loop_triangles]   # proper triangulation (n-gons with holes)
        e.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


MATS = {}
def mat(name, rgba, emit=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = rgba; b.inputs['Roughness'].default_value = 0.7
    if emit:
        b.inputs['Emission Color'].default_value = rgba; b.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = rgba
    MATS[name] = m
    return m


def _box(bm, cx, cy, cz, sx, sy, sz):
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=r['verts'])
    bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=r['verts'])


def proxy_mesh(name, w, d, h, kind='box'):
    bm = bmesh.new()
    if kind == 'frame':          # two posts + lintel: you walk through it
        t = min(0.6, w * 0.15)
        _box(bm, -w / 2 + t / 2, 0, h / 2, t, d, h); _box(bm, w / 2 - t / 2, 0, h / 2, t, d, h)
        _box(bm, 0, 0, h - 0.25, w, d, 0.5)
    elif kind == 'slats':        # sparse deck: boards across the local Y (walking) axis with open gaps
        board, gap = 0.12, 0.06
        n = max(1, int(d / (board + gap)))
        for k in range(n):
            _box(bm, 0, -d / 2 + (k + 0.5) * (board + gap), h - 0.025, w, board, 0.05)
        _box(bm, -w / 2 + 0.06, 0, h / 2 - 0.05, 0.12, d, 0.15); _box(bm, w / 2 - 0.06, 0, h / 2 - 0.05, 0.12, d, 0.15)   # stringers
    elif kind == 'deck':         # walkable slab at the top, open below
        _box(bm, 0, 0, 0.12, w, d, 0.25)
    elif kind == 'lamp':         # clay body (slot 0) + glowing head (slot 1)
        _box(bm, 0, 0, h * 0.35, w * 0.7, d * 0.7, h * 0.7)
        nb = len(bm.faces)
        _box(bm, 0, 0, h * 0.8, w, d, h * 0.35)
        for f in list(bm.faces)[nb:]:
            f.material_index = 1
    else:
        _box(bm, 0, 0, h / 2, w, d, h)
    # a notch on the front (+Y) top edge so facing reads in renders
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me


def water_bvh():
    dg = bpy.context.evaluated_depsgraph_get(); verts, polys = [], []
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith('w_'):
            me = o.evaluated_get(dg).to_mesh(); off = len(verts)
            verts += [o.matrix_world @ v.co for v in me.vertices]; me.calc_loop_triangles()
            polys += [[off + i for i in t.vertices] for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, polys) if polys else None


def main():
    bvh = world_bvh()
    wbvh = water_bvh()
    pc = bpy.data.collections.new('proxies'); bpy.context.scene.collection.children.link(pc)
    lc = bpy.data.collections.new('proxy_lights'); bpy.context.scene.collection.children.link(lc)
    cc = bpy.data.collections.new('collision'); bpy.context.scene.collection.children.link(cc)
    # readable graybox: warm mid-grey clay, orange hero, small amber emissive lights (lanterns light the scene)
    # hierarchy: the hero glows (it must be the brightest thing), lanterns glow softly, props are clay, rails are thin dark
    m_prop = mat('px_prop', (0.30, 0.27, 0.24, 1)); m_hero = mat('px_hero', (1.0, 0.45, 0.12, 1), emit=4.0)
    m_light = mat('px_light', (1.0, 0.5, 0.18, 1), emit=1.2); m_unknown = mat('px_unknown', (1, 0, 1, 1))
    m_hero_clay = mat('px_hero_clay', (0.42, 0.2, 0.08, 1))
    m_rail = mat('px_rail', (0.12, 0.10, 0.09, 1))
    meshes = {}
    resolved = []
    ASSETS = json.load(open(os.path.join(ROOT, '3d', 'assets.json')))['assets']
    for p in P:
        if ASSETS.get(p['asset'], {}).get('structural'):
            resolved.append(dict(p, snap_status='structural')); continue
        if ASSETS.get(p['asset'], {}).get('marker'):
            if p.get('light') and p['light'].get('kind') == 'point':
                ld = bpy.data.lights.new(p['id'] + '_L', 'POINT'); ld.energy = p['light']['watts'] * 5   # uplights/glows must read in the graybox
                ld.color = kelvin_rgb(p['light'].get('color_k')); ld.shadow_soft_size = 0.4
                lo = bpy.data.objects.new(p['id'] + '_L', ld); lc.objects.link(lo); lo.location = (p['pos'][0], p['pos'][1], p['pos'][2] + 0.1)
            resolved.append(dict(p, snap_status='marker')); continue
        w, d, h = p['dims']['w'] * p['scale'], p['dims']['d'] * p['scale'], p['dims']['h'] * p['scale']
        x, y, z = p['pos']
        yaw = -math.radians(p['facing_deg'])
        fwd = Vector((math.sin(math.radians(p['facing_deg'])), math.cos(math.radians(p['facing_deg'])), 0))
        snap, status, gap = p['snap'], 'ok', None
        if snap == 'ground':
            hit = None
            for start in (z + 4.0, z + 2.5, z + 0.6):     # from 4 m up first, so slopes above the space floor (beaches, decks) are found
                loc, nor, idx, dist = bvh.ray_cast(Vector((x, y, start)), Vector((0, 0, -1)), 12.0)
                if loc is not None:
                    hit = loc; break
            if hit is None:
                status = 'no_ground'
            else:
                z = hit.z - p.get('embed', 0.0)
                # rocks in water break the surface instead of vanishing on the bed
                if wbvh is not None and ASSETS.get(p['asset'], {}).get('cluster_ok'):
                    wl, _, _, _ = wbvh.ray_cast(Vector((x, y, hit.z + 0.01)), Vector((0, 0, 1)), 3.0)
                    if wl is not None:
                        z = max(z, wl.z - 0.45 * h)
        elif snap.startswith('height:'):
            hoff = float(snap.split(':')[1])
            base = z - hoff
            for start in (base + 4.0, base + 2.5, base + 0.6):
                loc, nor, idx, dist = bvh.ray_cast(Vector((x, y, start)), Vector((0, 0, -1)), 12.0)
                if loc is not None:
                    z = loc.z + hoff; break
            else:
                status = 'no_ground'
        elif snap == 'ceiling':
            loc, nor, idx, dist = bvh.ray_cast(Vector((x, y, z + h * 0.5)), Vector((0, 0, 1)), 30.0)
            if loc is None:
                status = 'no_ceiling'
            else:
                z = loc.z - h - (0.6 if p['asset'] in ('lantern_hanging', 'banner') else 0.0)
        elif snap == 'wall':
            loc, nor, idx, dist = bvh.ray_cast(Vector((x, y, z + min(h * 0.5, 1.2))), -fwd, 4.0)
            if loc is None:
                status = 'no_wall'
            else:
                x, y = loc.x + fwd.x * (d / 2 + 0.02), loc.y + fwd.y * (d / 2 + 0.02)
            g, _, _, _ = bvh.ray_cast(Vector((x, y, z + 1.0)), Vector((0, 0, -1)), 20.0)
            if p['asset'] not in ('lantern_niche', 'neon_sign', 'sign_kanji') and g is not None and abs(g.z - z) < 1.5:
                z = g.z
        elif snap == 'water':
            # floats sit at the water level the rule gave (pos z); nothing to raycast against (water is excluded)
            z = p['pos'][2]
        A_ = ASSETS.get(p['asset'], {})
        is_lamp = bool(p.get('light') and p['light'].get('kind') == 'point' and w * d < 1.0 and not p.get('hero'))
        kind = 'frame' if A_.get('frame') else ('slats' if A_.get('slatted') else ('deck' if A_.get('deck') else ('lamp' if is_lamp else 'box')))
        key = (p['asset'], round(w, 2), round(d, 2), round(h, 2), kind)
        if key not in meshes:
            meshes[key] = proxy_mesh(f"px_{p['asset']}", w, d, h, kind)
        o = bpy.data.objects.new(p['id'], meshes[key]); pc.objects.link(o)
        o.location = (x, y, z); o.rotation_euler = (0, 0, yaw)
        o['asset'] = p['asset']; o['space'] = p['space']; o['rule'] = p['rule']
        if kind == 'slats':          # invisible solid walk surface under the boards (web walk mesh is solid too)
            co = bpy.data.objects.new(p['id'] + '_col', proxy_mesh('col_' + p['asset'], w, d, 0.05, 'box')); cc.objects.link(co)
            co.location = (x, y, z + h - 0.05); co.rotation_euler = (0, 0, yaw); co.hide_render = True
        mm = m_unknown if p.get('unknown_asset') else (m_rail if p['asset'] == 'railing' else None) or ((m_hero if ASSETS.get(p['asset'], {}).get('hero_glow') else m_hero_clay) if p.get('hero') else (m_light if p.get('light') and p['light'].get('kind') == 'point' and w * d < 1.0 else m_prop))   # only lantern-sized pieces glow
        ge = A_.get('gb_emit')
        if ge and kind != 'lamp':
            mm = mat(f"px_emit_{p['asset']}", tuple(ge[:3]) + (1,), emit=ge[3])
        if kind == 'lamp':
            if not o.data.materials:
                o.data.materials.append(m_prop); o.data.materials.append(m_light)
        elif not o.data.materials:
            o.data.materials.append(mm)
        else:
            o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = mm
        if p.get('light') and p['light']['kind'] == 'point':
            ld = bpy.data.lights.new(p['id'] + '_L', 'POINT'); ld.energy = p['light']['watts']
            ld.color = kelvin_rgb(p['light'].get('color_k')); ld.shadow_soft_size = 0.15
            lo = bpy.data.objects.new(p['id'] + '_L', ld); lc.objects.link(lo)
            lo.location = (x, y, z + h * 0.6)
        if p.get('hero'):          # every hero carries its own light so it reads as the focal point
            hl = bpy.data.lights.new(p['id'] + '_H', 'POINT'); hl.energy = max(300.0, 40.0 * w * h); hl.color = (1.0, 0.62, 0.32); hl.shadow_soft_size = max(w, h) * 0.3
            ho = bpy.data.objects.new(p['id'] + '_H', hl); lc.objects.link(ho)
            ho.location = (x + fwd.x * (d / 2 + 1.5), y + fwd.y * (d / 2 + 1.5), z + h * 0.6)
        resolved.append(dict(p, pos=[round(x, 3), round(y, 3), round(z, 3)], snap_status=status))
    json.dump(dict(placements=resolved), open(os.environ.get('KZ_RESOLVED') or os.path.join(ROOT, '3d', 'placements_resolved.json'), 'w'), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    bad = [r for r in resolved if r['snap_status'] not in ('ok', 'structural', 'marker')]
    print('ASSEMBLED', len(resolved), 'proxies;', len(bad), 'snap problems', [(b['id'], b['snap_status']) for b in bad][:20])


main()
