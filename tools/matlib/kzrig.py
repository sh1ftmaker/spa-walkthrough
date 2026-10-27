"""Shared preview rig for the Kazan-yu material library (round 2).

Calibration: the lantern key is set so that an 18 % grey card in the lit area renders as
display middle grey (~sRGB 115-125 under AgX), i.e. the level the baked lightmaps aim for in a
lantern-lit area.  Black basalt (albedo ~0.02) then reads near-black, as in the concept art.
Every scene carries an 18 % grey card and a 4 % black card for reference.

Glossy materials get something to reflect: 30 small warm lantern dots and 70 cyan glowworm
dots on a dim cave dome (as in concepts 05 and 15).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kzdsl import blackbody_rgb  # noqa: E402

LANTERN = blackbody_rgb(2700)
NEUTRAL = blackbody_rgb(5000)
AMBER_SPLIT = 0.45      # amber lantern power relative to the neutral key (r3 rig: neutral key + amber split)
KEY_W = 600.0           # one lantern key (W), calibrated with the grey card
FILL_W = 30.0           # dim teal fill (W, area)


def setup_scene(res=(800, 520), samples=256):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    c = sc.cycles
    c.device = 'GPU'
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.01
    c.use_denoising = True
    c.denoiser = 'OPTIX'
    c.max_bounces = 16
    c.transmission_bounces = 16
    c.transparent_max_bounces = 16
    c.volume_bounces = 2
    c.glossy_bounces = 6
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.5
    c.sample_clamp_indirect = 8.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 90
    w = bpy.data.worlds.new('RIG_World')
    sc.world = w
    w.color = (0, 0, 0)
    bg = w.node_tree.nodes.get('Background') if w.node_tree else None
    if bg:
        bg.inputs['Color'].default_value = (0.0006, 0.0007, 0.0009, 1)
        bg.inputs['Strength'].default_value = 1.0
    return sc


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def simple_mat(name, color, rough=0.6, emission=None, strength=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF') or nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = tuple(color) + (1,)
    p.inputs['Roughness'].default_value = rough
    if emission:
        p.inputs['Emission Color'].default_value = tuple(emission) + (1,)
        p.inputs['Emission Strength'].default_value = strength
    return m


def neutral():
    return simple_mat('RIG_Neutral18', (0.18, 0.18, 0.18), 0.6)


def make_box(name, sx, sy, sz, uv='metric', bevel=0.012):
    """Box with box-projected UVs: metric (1 UV = 1 m) or 'face' (each face 0..1)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(min(sx, sy, sz) * 0.3, bevel), segments=3,
                        affect='EDGES')
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            co = lp.vert.co
            if ax == 2:
                u, v, du, dv = co.x + sx / 2, co.y + sy / 2, sx, sy
            elif ax == 1:
                u, v, du, dv = co.x + sx / 2, co.z + sz / 2, sx, sz
            else:
                u, v, du, dv = co.y + sy / 2, co.z + sz / 2, sy, sz
            lp[uvl].uv = (u / du, v / dv) if uv == 'face' else (u, v)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def box(name, loc, size, mat=None, uv='metric', bevel=0.012):
    ob = make_box(name, *size, uv=uv, bevel=bevel)
    ob.location = loc
    if mat is not None:
        ob.data.materials.append(mat)
    return ob


def cylinder(name, a, b, r, seg=48, uv='metric', caps=False):
    """Cylinder from a to b.  metric UVs: u along the axis, v around (arc length);
    'object' UVs: u around 0..1, v along 0..1 (lanterns)."""
    a, b = Vector(a), Vector(b)
    ax = b - a
    length = ax.length
    q = ax.normalized().to_track_quat('Z', 'Y')
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    r0, r1 = [], []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        p = Vector((r * math.cos(t), r * math.sin(t), 0))
        r0.append(bm.verts.new(a + q @ p))
        r1.append(bm.verts.new(a + q @ (p + Vector((0, 0, length)))))
    uvl = bm.loops.layers.uv.new('UVMap')
    for i in range(seg):
        j = (i + 1) % seg
        f = bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        f.smooth = True
        if uv == 'object':
            pts = ((i / seg, 0), ((i + 1) / seg, 0), ((i + 1) / seg, 1), (i / seg, 1))
        else:
            arc = 2 * math.pi * r / seg
            pts = ((0, i * arc), (0, (i + 1) * arc), (length, (i + 1) * arc), (length, i * arc))
        for lp, p in zip(f.loops, pts):
            lp[uvl].uv = p
    if caps:
        bm.faces.new(list(reversed(r0)))
        bm.faces.new(r1)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def uv_sphere(name, loc, r=0.5):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=128, v_segments=64, radius=r)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        f.smooth = True
        us = []
        for lp in f.loops:
            co = lp.vert.co
            u = math.atan2(co.x, -co.y) / (2 * math.pi) + 0.5          # seam faces away (+Y)
            v = math.acos(max(-1.0, min(1.0, -co.z / r))) / math.pi
            us.append([u, v])
        if max(a[0] for a in us) - min(a[0] for a in us) > 0.5:
            for a in us:
                if a[0] < 0.5:
                    a[0] += 1.0
        for lp, (u, v) in zip(f.loops, us):
            lp[uvl].uv = (u * 2 * math.pi * r, v * math.pi * r)        # metres
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.location = loc
    return ob


def point(name, loc, energy, radius=0.05, color=LANTERN, visible=False):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = color
    ld.energy = energy
    ld.shadow_soft_size = radius
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    ob.visible_camera = visible
    ob.visible_glossy = visible
    return ob


def area(name, loc, target, energy, size=(1.6, 1.0), color=(0.18, 0.80, 0.74)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = size
    ld.color = color
    ld.energy = energy
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def camera(sc, loc, target, lens=50.0, ortho=None):
    cd = bpy.data.cameras.new('RIG_Cam')
    cd.lens = lens
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    cam = link(bpy.data.objects.new('RIG_Cam', cd))
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    return cam


def cards(loc, facing, size=(0.2, 0.28)):
    """18 % grey and 4 % black reference cards side by side, facing `facing`."""
    obs = []
    d = Vector(facing) - Vector(loc)
    d.z = 0
    rot = d.to_track_quat('Y', 'Z').to_euler()
    side = Vector((d.y, -d.x, 0)).normalized()
    for i, (nm, val) in enumerate((('RIG_Grey18', 0.18), ('RIG_Black04', 0.04))):
        o = box(nm, Vector(loc) + side * (i - 0.5) * (size[0] + 0.04), (size[0], 0.01, size[1]),
                simple_mat(nm, (val, val, val), 0.7), bevel=0.0)
        o.rotation_euler = rot
        o.rotation_euler.x += math.radians(-90) * 0
        obs.append(o)
    return obs


def env_dots(center=(0, 0, 1.0), radius=7.0, warm=30, cyan=70, seed=7, zmin=0.6):
    """Cave-like reflection environment: small warm lantern dots + cyan glowworm dots."""
    rnd = random.Random(seed)
    warm_m = simple_mat('RIG_DotWarm', (0, 0, 0), 1.0, emission=LANTERN, strength=40.0)
    cyan_m = simple_mat('RIG_DotCyan', (0, 0, 0), 1.0, emission=(0.10, 0.85, 1.0), strength=60.0)
    obs = []
    c = Vector(center)
    for i in range(warm + cyan):
        while True:
            v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.1, 1)))
            if 0.3 < v.length <= 1.0:
                break
        p = c + v.normalized() * radius * rnd.uniform(0.75, 1.0)
        p.z = max(p.z, zmin)
        is_warm = i < warm
        me = bpy.data.meshes.new('RIG_Dot')
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.05 if is_warm else 0.014)
        bm.to_mesh(me)
        bm.free()
        ob = link(bpy.data.objects.new('RIG_Dot', me))
        ob.location = p
        ob.data.materials.append(warm_m if is_warm else cyan_m)
        ob.visible_shadow = False
        obs.append(ob)
    return obs


def bloom(sc, on=True, threshold=1.0, strength=0.35):
    """Subtle bloom in the compositor (Glare, Bloom); off = straight render."""
    if not on:
        sc.compositing_node_group = None
        return
    ng = bpy.data.node_groups.get('RIG_Bloom') or bpy.data.node_groups.new('RIG_Bloom', 'CompositorNodeTree')
    ng.nodes.clear()
    if not ng.interface.items_tree:
        ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    gl = ng.nodes.new('CompositorNodeGlare')
    gl.inputs['Type'].default_value = 'Bloom'
    gl.inputs['Threshold'].default_value = threshold
    gl.inputs['Strength'].default_value = strength
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
    ng.links.new(gl.outputs[0], out.inputs[0])
    sc.compositing_node_group = ng


def stepped_pool(water_mat, bottom_mat, rim_mat, x0=-1.5, step_w=1.0, y0=0.6, y1=2.6, under_lights=True):
    """Pool over basalt with three bottom depths, left to right 0.1 m, 0.5 m, 2.0 m.
    The water surface is at z = 0; small white under-water fixtures stand in for the baked
    under-water lights, so absorption shows its colour."""
    obs = []
    depths = (0.1, 0.5, 2.0)
    for i, dpt in enumerate(depths):
        cx = x0 + step_w * (i + 0.5)
        obs.append(box(f'POOL_Bottom{i}', (cx, (y0 + y1) / 2, -dpt - 0.15), (step_w, y1 - y0, 0.3), bottom_mat))
        if under_lights:
            ld = bpy.data.lights.new(f'POOL_UL{i}', 'AREA')
            ld.shape = 'RECTANGLE'
            ld.size, ld.size_y = step_w * 0.8, 0.12
            ld.color = (0.95, 0.97, 1.0)
            ld.energy = 15.0
            ld.size_y = (y1 - y0) * 0.5
            ob = link(bpy.data.objects.new(f'POOL_UL{i}', ld))
            ob.location = (cx, (y0 + y1) / 2, -0.03)            # fixture just under the surface, shining down
            ob.rotation_euler = (0, 0, 0)
            ob.visible_camera = False
            obs.append(ob)
    xr = x0 + step_w * 3
    obs.append(box('POOL_Water', ((x0 + xr) / 2, (y0 + y1) / 2, -1.0), (xr - x0 - 0.004, y1 - y0 - 0.004, 2.0),
                   water_mat, bevel=0.0))
    t = 0.25
    for i, (cx, cy, sx, sy) in enumerate((((x0 + xr) / 2, y0 - t / 2, xr - x0 + 2 * t, t),
                                          ((x0 + xr) / 2, y1 + t / 2, xr - x0 + 2 * t, t),
                                          (x0 - t / 2, (y0 + y1) / 2, t, y1 - y0),
                                          (xr + t / 2, (y0 + y1) / 2, t, y1 - y0))):
        obs.append(box(f'POOL_Rim{i}', (cx, cy, -1.0 + 0.04), (sx, sy, 2.08), rim_mat))
    return obs


def clear(objs):
    for ob in objs:
        if ob is None or ob.name not in bpy.data.objects:
            continue
        data = ob.data
        bpy.data.objects.remove(ob)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)


def barrel(name, base, height, r_mid, r_end, seg=48, rings=16):
    """Chochin-style bulging lantern (lathe), object UVs: u around 0..1, v bottom->top 0..1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rows = []
    for k in range(rings + 1):
        v = k / rings
        r = r_end + (r_mid - r_end) * math.sin(math.pi * v)
        rows.append([bm.verts.new((base[0] + r * math.cos(2 * math.pi * i / seg),
                                   base[1] + r * math.sin(2 * math.pi * i / seg), base[2] + height * v))
                     for i in range(seg)])
    uvl = bm.loops.layers.uv.new('UVMap')
    for k in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            f = bm.faces.new((rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]))
            f.smooth = True
            for lp, p in zip(f.loops, ((i / seg, k / rings), ((i + 1) / seg, k / rings),
                                       ((i + 1) / seg, (k + 1) / rings), (i / seg, (k + 1) / rings))):
                lp[uvl].uv = p
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def lantern(name, base, height, r_mid, paper_mat, ring_mat):
    """Barrel lantern + dark lacquered top and bottom rings; returns objects."""
    r_end = r_mid * 0.62
    body = barrel(name, base, height, r_mid, r_end)
    body.data.materials.append(paper_mat)
    obs = [body]
    for k, z in enumerate((base[2], base[2] + height)):
        ring = cylinder(f'{name}_ring{k}', (base[0], base[1], z - 0.02), (base[0], base[1], z + 0.02),
                        r_end * 1.08, seg=48, caps=True)
        ring.data.materials.append(ring_mat)
        obs.append(ring)
    return obs


def teal_points(name, centre, target, energy, n=3, spread=0.5):
    """Dim teal fill as a few small point lights (glossy materials reflect dots, not a cyan polygon)."""
    c, t = Vector(centre), Vector(target)
    side = (t - c).cross(Vector((0, 0, 1))).normalized()
    return [point(f'{name}{i}', c + side * (i - (n - 1) / 2) * spread + Vector((0, 0, 0.15 * i)), energy / n, 0.03,
                  color=(0.18, 0.80, 0.74)) for i in range(n)]
