"""Place helpers for g_arrival, the Arrival hall (lava window). Used by tools/place/build_g_arrival.py.

Shell (decision 61: one coherent model, no prisms):
  * rock_shell()  one carved basalt cave vault over the whole hall. Built as a rounded box (walls -> vault,
    squarish corners) mapped onto the footprint x 40-100, y 42-80, the crown rising 12 m (south) -> 16.8 m
    (north), then displaced along its normal by fbm lumps, Voronoi column cells (columnar basalt: each cell a
    different depth, grooves between), and stepped ledge bands that make real overhangs above 2.6 m. Below
    2.3 m the rock only moves outward (never into the walk). Openings: the lava-window bay (faces cut behind
    the frame), the west gate and the east changing door (the wall is pushed out into a short rock tunnel and
    its back cut away), the south side below the vault spring (replaced by the timber facade).
    Split into `shell_wall` (role wall) and `shell_vault` (role ceiling, above the spring line).
  * floor()       wet stone paving slab with the stream corridor, the lift well (r 7.75) and the drain slot cut out.
  * facade_south() timber post-and-beam bays (9 m) with lit shoji, board upper register, gallery, head beam.
  * door frames   east changing door, spiral-stair landing door (doorway + surround on the well rim).
  * water         one kz_water ribbon on the stream's centre line (levels from the stream_channel generator).
  * walk          kz_walk grid floor + deck strips + curbs/walls; flood-fill / clearance / portal / float checks.
"""
import json
import math
import os
import sys
import time
from collections import deque

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import kzplace_common as P  # noqa: E402
import genlib  # noqa: E402
import kzgeo_common as C  # noqa: E402

SID = 'g_arrival'
ROOT = P.ROOT

# space-file asset id -> generator module (gen_<id>.py); proposed for kzplace_common.dress
ALIAS = {'lift_core': 'lift_drum', 'lantern_hanging': 'chochin', 'pine_bonsai': 'pine_niwaki',
         'banner': 'banner_hanging', 'sign_kanji': 'signboard_kanji', 'bench_stone': 'bench'}

# ------------------------------------------------------------------------------------------------ shell frame
CX, CY, A, B = 70.0, 61.0, 30.0, 19.0          # footprint centre and half extents (x 40-100, y 42-80)
CZ, RX, RY, RZ = 7.0, 5.5, 5.5, 3.5            # rounded-box: vault radii (horizontal 5.5 m, vertical 0.25 of h)
ZB = -0.6                                      # wall foot (below the floor slab top)
NX, NY, NZ = 80, 52, 24                        # NZ multiple of 4: lattice row 18 is exactly the spring line
SPRING_K = 18

WINDOW = dict(x0=44.6, x1=77.4, ztop=11.3)     # rock cut behind the lava window frame (frame 43.88-78.12, z 0-12)
GATE = dict(yc=55.0, half=4.5, z_side=6.0, z_crown=8.6, push=3.6)       # west opening (portal 6 m wide)
EAST = dict(yc=52.0, half=2.25, ztop=3.45, push=2.6)                     # changing-hall door (portal 4 m)


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def ceil_h(x, y):
    """crown height of the vault: 12 m over the south facade rising to 16.8 m over the lava window"""
    n = noise.noise(Vector((x * 0.07, y * 0.07, 3.3)))
    return 12.0 + 4.8 * smoothstep(46, 74, y) + 0.9 * n * smoothstep(44, 50, y)


def spring_z(x, y):
    return ZB + 0.75 * (ceil_h(x, y) - ZB)


def _base(i, j, k):
    """lattice point on the cube surface -> (x, y, zf, z): rounded box, squarish (superellipse) wall corners"""
    X = -A + 2 * A * i / NX; Y = -B + 2 * B * j / NY; Z = -CZ + 2 * CZ * k / NZ
    core = Vector((clamp(X, -A + RX, A - RX), clamp(Y, -B + RY, B - RY), min(Z, CZ - RZ)))
    d = Vector((X, Y, Z)) - core
    n = Vector((d.x / RX, d.y / RY, d.z / RZ))
    if n.length < 1e-9:
        n = Vector((0, 0, 1))
    n.normalize()
    h = math.hypot(n.x, n.y)
    if h > 1e-9:
        ux, uy = n.x / h, n.y / h
        sx = math.copysign(abs(ux) ** (1 / 3), ux); sy = math.copysign(abs(uy) ** (1 / 3), uy)
    else:
        sx = sy = 0.0
    q = core + Vector((h * sx * RX, h * sy * RY, n.z * RZ))
    x, y = CX + q.x, CY + q.y
    zf = (q.z + CZ) / (2 * CZ)
    return x, y, zf, ZB + zf * (ceil_h(x, y) - ZB)


def _cells(p):
    """Voronoi column cells in plan (columnar basalt): (groove 0..1 at cell borders, per-cell offset -1..1)"""
    q = Vector((p.x * 0.42, p.y * 0.42, p.z * 0.035))
    ds, pts = noise.voronoi(q, distance_metric='DISTANCE')
    f = ds[1] - ds[0]
    groove = 1.0 - smoothstep(0.0, 0.22, f)
    c = pts[0]
    off = noise.noise(Vector((c.x * 7.13 + 0.5, c.y * 7.13 + 0.25, c.z * 7.13 + 0.75)))
    return groove, off


def _gate_w(y, z):
    """1 inside the west gate arch (in the wall plane), falling to 0 over 0.9 m outside it"""
    t = (y - GATE['yc']) / GATE['half']
    arch = GATE['z_side'] + (GATE['z_crown'] - GATE['z_side']) * math.sqrt(max(0.0, 1 - min(1.0, t * t)))
    out = max(abs(y - GATE['yc']) - GATE['half'], z - arch)
    return 1.0 - smoothstep(0.0, 0.9, out)


def _east_w(y, z):
    out = max(abs(y - EAST['yc']) - EAST['half'], z - EAST['ztop'])
    return 1.0 - smoothstep(0.0, 0.7, out)


def rock_shell():
    """the carved basalt cave vault: returns (shell_wall, shell_vault)"""
    bm = bmesh.new()
    V = {}
    info = {}

    def vert(i, j, k):
        key = (i, j, k)
        if key not in V:
            x, y, zf, z = _base(i, j, k)
            v = bm.verts.new((x, y, z)); V[key] = v; info[v] = (x, y, zf, z, k)
        return V[key]

    def quad(a, b, c, d):
        try:
            bm.faces.new((vert(*a), vert(*b), vert(*c), vert(*d)))
        except ValueError:
            pass
    for i in range(NX):
        for j in range(NY):
            quad((i, j, NZ), (i + 1, j, NZ), (i + 1, j + 1, NZ), (i, j + 1, NZ))
    for i in range(NX):
        for k in range(NZ):
            quad((i, NY, k), (i + 1, NY, k), (i + 1, NY, k + 1), (i, NY, k + 1))
            quad((i, 0, k), (i, 0, k + 1), (i + 1, 0, k + 1), (i + 1, 0, k))
    for j in range(NY):
        for k in range(NZ):
            quad((NX, j, k), (NX, j, k + 1), (NX, j + 1, k + 1), (NX, j + 1, k))
            quad((0, j, k), (0, j + 1, k), (0, j + 1, k + 1), (0, j, k + 1))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    top = next(f for f in bm.faces if all(info[v][2] > 0.99 for v in f.verts))
    if top.normal.z > 0:                                  # make every normal face into the hall
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()

    # ---- displacement along the outward normal
    disp = {}
    for v in bm.verts:
        x, y, zf, z, k = info[v]
        p = Vector((x, y, z))
        nout = -v.normal
        big = noise.fractal(p * 0.085, 0.75, 2.1, 4, noise_basis='PERLIN_ORIGINAL')
        groove, off = _cells(p)
        if nout.z > 0.55:                                 # vault: lumps, column ends, a few deep pockets
            d = 1.0 * big + 0.22 * off + 0.2 * groove + 0.2 * noise.fractal(p * 0.45, 0.6, 2.2, 3, noise_basis='PERLIN_ORIGINAL')
            d = clamp(d, -1.3, 1.6)
        else:
            t = (z + 1.7 * big) / 3.1
            fr = t - math.floor(t)
            ledge = smoothstep(0.55, 0.97, fr) * smoothstep(2.6, 3.6, z)
            fine = noise.fractal(p * 0.45, 0.6, 2.2, 3, noise_basis='PERLIN_ORIGINAL')
            d = 0.55 + 1.05 * big + 0.12 * off + 0.16 * groove - 0.55 * ledge + 0.22 * fine
            lo = -1.6 * smoothstep(2.3, 3.6, z) + 0.1 * (1 - smoothstep(2.3, 3.6, z))
            if d < lo + 0.3:                              # soft floor: never into the walk below 2.3 m
                d = lo + 0.3 * math.exp((d - lo - 0.3) / 0.3)
        # flush zones
        if nout.y > 0.6 and 42.0 < x < 80.0 and z < 13.6:             # lava window bay: rock behind the frame
            wgt = smoothstep(80.0, 78.6, x) * smoothstep(42.0, 43.4, x) * smoothstep(13.6, 12.4, z)
            d = d * (1 - wgt) + clamp(d, 0.0, 0.3) * wgt
        if y < 43.5 and 7.8 < z < 10.6:                               # south spring: rock meets the head beam
            wgt = smoothstep(7.8, 8.6, z) * smoothstep(10.6, 9.6, z)
            d = d * (1 - wgt) + clamp(d, -0.1, 0.25) * wgt
        if 83.0 < x < 97.0 and y > 78.5 and z < 3.0:                  # lift-door strip stays clear
            d = max(d, 0.15)
        w = 0.0
        if nout.x < -0.6:
            w = _gate_w(y, z)
            if w > 0:
                d = d * (1 - w) + (GATE['push'] + 0.25 * big) * w
        elif nout.x > 0.6:
            w = _east_w(y, z)
            if w > 0:
                d = d * (1 - w) + (EAST['push'] + 0.15 * big) * w
        disp[v] = (d, w)
    for v in bm.verts:
        v.co = v.co + (-v.normal) * disp[v][0]

    # ---- openings
    kill = set()
    for f in bm.faces:
        vs = f.verts
        n = sum((v.normal for v in vs), Vector()).normalized()
        if n.y < -0.6:                                    # north wall (normals face into the hall)
            if any(WINDOW['x0'] < info[v][0] < WINDOW['x1'] and info[v][3] < WINDOW['ztop'] for v in vs):
                kill.add(f)
        if all(disp[v][1] > 0.97 for v in vs):            # back of the gate / door tunnels
            kill.add(f)
        if all(info[v][1] < 42.9 and info[v][4] <= SPRING_K for v in vs):   # south side below the spring
            kill.add(f)
    bmesh.ops.delete(bm, geom=list(kill), context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')

    # ---- split wall / vault
    vault_faces = [f for f in bm.faces if all(info[v][4] >= SPRING_K for v in f.verts)]
    bm2 = bm.copy()
    vf_idx = {f.index for f in vault_faces}
    bm.faces.ensure_lookup_table(); bm2.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in vf_idx], context='FACES')
    bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.index not in vf_idx], context='FACES')
    for b in (bm, bm2):
        bmesh.ops.delete(b, geom=[v for v in b.verts if not v.link_faces], context='VERTS')
    wall = P.mesh_object('shell_wall', bm, 'kz_render', role='wall', material='basalt_wet', bake=True)
    vault = P.mesh_object('shell_vault', bm2, 'kz_render', role='ceiling', material='cave_rock', bake=True)
    for o in (wall, vault):
        _finish_shell(o, 20)                              # low angle: faceted basalt, not smooth lumps
    return wall, vault


def lava_cavern(y1=95.8, x0=42.5, x1=79.5, peak=7.0):
    """dark rock cave round the lava world behind the glass (beyond the footprint; backdrops behind glass are
    exempt from the 3 m rule): a roof rising from behind the window head (y 80.4, z 12.4) by `peak` m and
    falling as side and back walls to z -1.6 outside the backdrops, so every view through the glass ends in
    lava-lit rock (04), never in the world background."""
    bm = bmesh.new()
    nx, ny = 46, 26
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [80.4 + (y1 - 80.4) * j / ny for j in range(ny + 1)]
    cx, hx = (x0 + x1) / 2, (x1 - x0) / 2
    G = {}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            u = (x - cx) / hx; v = (y - 80.4) / (y1 - 80.4)
            side = max(0.0, 1 - abs(u) ** 4)
            arch = math.sin(math.pi * min(1.0, 0.12 + 0.88 * v)) ** 0.5
            p = Vector((x, y, 0))
            z = 12.4 + peak * arch * side + (1.6 * noise.fractal(p * 0.09, 0.7, 2.0, 3) + 0.6 * _cells(Vector((x, y, 20.0)))[1]) * side
            if i in (0, nx) or j == ny:
                z = -1.6
            elif i in (1, nx - 1) or j == ny - 1:
                z = 0.5 * z + 0.5 * 8.0
            if j == 0:
                z = 12.4
            G[i, j] = bm.verts.new((x, y, z))
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((G[i, j], G[i, j + 1], G[i + 1, j + 1], G[i + 1, j]))
    bm.normal_update()
    cen = Vector((cx, (80.4 + y1) / 2, 4.0))
    for f in bm.faces:
        if f.normal.dot(cen - f.calc_center_median()) < 0:
            f.normal_flip()
    o = P.mesh_object('lava_cavern_roof', bm, 'kz_render', role='ceiling', material='cave_rock', bake=True)
    return _finish_shell(o, 32)


LAVA = dict(molten=dict(emissive_level=4.0, tint=(1.0, 0.42, 0.1)), hot=dict(emissive_level=2.6, tint=(1.0, 0.27, 0.03)),
            cliff=dict(tint=(1.0, 0.35, 0.15), emissive_level=3.5))


def glass_standin(o, slot=0):
    """Render stand-in for lava_glass (its library shader overflows Cycles' 64-closure limit and loses the
    emission): clear, low-roughness, faintly warm glass. kz_id / kz_material stay lava_glass for the exporter."""
    src = o.data.materials[slot]
    m = bpy.data.materials.get('lava_glass~place_standin') or bpy.data.materials.new('lava_glass~place_standin')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); out = nt.nodes.new('ShaderNodeOutputMaterial')
    b.inputs['Base Color'].default_value = (1.0, 0.95, 0.9, 1); b.inputs['Roughness'].default_value = 0.03
    b.inputs['Transmission Weight'].default_value = 1.0; b.inputs['IOR'].default_value = 1.45
    nt.links.new(b.outputs[0], out.inputs[0])
    m['kz_id'] = 'lava_glass'; m['kz_params'] = src.get('kz_params', '{}') if src else '{}'
    m['kz_render_standin'] = 'Principled clear glass; runtime uses library lava_glass'
    o.data.materials[slot] = m
    o['kz_glass_standin'] = True
    return m


def heat_backdrop(o):
    """re-assign the backdrop's lava slots with hotter library variants (same ids): molten field and the
    fall / river cores glow orange-yellow, the cliff veins hotter"""
    for i, m in enumerate(o.data.materials):
        if not m:
            continue
        mid = m.get('kz_id', m.name.split('~')[0])
        par = json.loads(m.get('kz_params', '{}')) if m.get('kz_params') else {}
        if mid == 'lava_molten':
            key = 'hot' if float(par.get('emissive_level', 1.0)) > 1.05 else 'molten'
            P.matlib.assign(o, 'lava_molten', slot=i, **LAVA[key])
        elif mid == 'lava':
            P.matlib.assign(o, 'lava', slot=i, **LAVA['cliff'])
        elif mid == 'basalt_dry':                                  # side walls / arch / near rocks: veined lava rock
            P.matlib.assign(o, 'lava', slot=i, tint=(0.8, 0.3, 0.13), emissive_level=2.5)


def lava_view(win, dress_fn, scale=(1.7, 1.7, 1.75)):
    """the lava world behind the glass: one lava_backdrop (cascade style, falls + arch) heated and scaled
    (x 1.18, depth 1.7, height 1.75: the proxy box is 34 x 20 x 12; the field then recedes ~35 m and the falls
    rise above the 12 m glass head), under a high lava-lit cave roof that sits behind it."""
    glass_standin(win, 0)
    far = dress_fn('lava_backdrop', 1, (61.0, 100.0, -1.2), 180, name='lava_backdrop', role='emissive', bake=False,
                   style='cascade')
    far.scale = scale
    bpy.context.view_layer.update()
    far.location.y += 80.05 - min((far.matrix_world @ v.co).y for v in far.data.vertices)
    bpy.context.view_layer.update()
    heat_backdrop(far)
    far['kz_note'] = 'backdrop behind glass (contract 3 m rule exempt); object scale ' + str(tuple(scale))
    y1 = max((far.matrix_world @ v.co).y for v in far.data.vertices) + 1.5
    cav = lava_cavern(y1=y1, x0=30.0, x1=92.0, peak=12.0)
    return far, cav


def _finish_shell(o, angle=35):
    """smooth with sharp edges over `angle`, UV0 in metres (no UV1: the exporter makes it)"""
    for p in o.data.polygons:
        p.use_smooth = True
    genlib._flat_by_angle(o, angle)
    genlib.uv0_metric(o)
    o['kz_shell'] = True
    return o


# ------------------------------------------------------------------------------------------------ floor
def _offset_poly(cl, hw_add, end_ext=0.0):
    """closed outline round a centre line [(x, y, hw)] at hw + hw_add (ends extended by end_ext)"""
    pts = [Vector((p[0], p[1], 0)) for p in cl]
    left, right = [], []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]; b = pts[min(len(pts) - 1, i + 1)]
        t = (b - a).normalized(); nrm = Vector((-t.y, t.x, 0))
        q = p.copy()
        if i == 0:
            q = p - t * end_ext
        elif i == len(pts) - 1:
            q = p + t * end_ext
        hw = cl[i][2] + hw_add
        left.append(q + nrm * hw); right.append(q - nrm * hw)
    return [(v.x, v.y) for v in left + right[::-1]]


def floor(stream_cl, slot_box):
    """paving slab (top z 0) with the stream corridor, the lift well and the drain slot cut out (booleans)"""
    mb = genlib.MeshBuilder()
    mb.box((70.0, 61.0, -0.2), (68.0, 43.0, 0.4), 0)       # x 36-104, y 39.5-82.5
    fl = P.mesh_object('floor', mb.bm, 'kz_render', role='floor', material='paving', bake=True)
    cutters = []
    mb = genlib.MeshBuilder()
    mb.poly_prism(_offset_poly(stream_cl, 0.5, end_ext=0.3), -3.0, 1.0, 0)
    cutters.append(_tmp_obj('cut_stream', mb))
    mb = genlib.MeshBuilder()
    mb.cylinder((90.0, 70.0, -1.0), 7.75, 4.0, 0, segs=72)
    cutters.append(_tmp_obj('cut_well', mb))
    mb = genlib.MeshBuilder()
    (x0, y0, x1, y1) = slot_box
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, -1.0), (x1 - x0, y1 - y0, 4.0), 0)
    cutters.append(_tmp_obj('cut_slot', mb))
    for c in cutters:
        m = fl.modifiers.new(c.name, 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = c; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = fl
    for m in list(fl.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)
    bm = bmesh.new(); bm.from_mesh(fl.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=0.01, verts=bm.verts, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(fl.data); bm.free()
    _finish_shell(fl, 40)
    return fl


def _tmp_obj(name, mb):
    me = bpy.data.meshes.new(name); mb.bm.to_mesh(me); mb.bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    return o


def drain_pit(slot_box, depth=1.6):
    """dark rock-lined slot under the drain grate where the stream sinks toward B1 (open top)"""
    x0, y0, x1, y1 = slot_box
    bm = bmesh.new()
    zt, zb = -0.02, -depth
    c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    top = [bm.verts.new((x, y, zt)) for x, y in c]
    bot = [bm.verts.new((x, y, zb)) for x, y in c]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((top[i], top[j], bot[j], bot[i]))
    bm.faces.new(bot)
    bm.normal_update()
    cen = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (zt + zb) / 2))
    for f in bm.faces:                                    # normals into the pit
        if f.normal.dot(cen - f.calc_center_median()) < 0:
            f.normal_flip()
    o = P.mesh_object('drain_pit', bm, 'kz_render', role='basin', material='cave_rock', bake=True)
    return _finish_shell(o, 40)


# ------------------------------------------------------------------------------------------------ timber
FY = 42.0                                              # facade back plane
POSTS = [40.25, 44.5, 48.75, 53.0, 57.15, 62.85, 67.0, 71.2, 75.4, 79.6, 83.8, 88.0, 92.0, 96.0, 99.75]
TERRACE = (57.15, 62.85)                               # open bay (portal x 57.5-62.5, h 4)
GALLERY_Z = 6.0                                        # gallery deck top
HEAD = (8.55, 9.4)                                     # head beam z
PORCH_X, PORCH_Y, PORCH_BAR_Z = 96.6, (49.25, 54.75), 3.57   # changing-door porch (lantern bar underside)


def facade_south():
    """timber post-and-beam bays along the south wall: returns {material: object}"""
    frame = genlib.MeshBuilder(); boards = genlib.MeshBuilder(); shoji = genlib.MeshBuilder()
    kumiko = genlib.MeshBuilder(); deck = genlib.MeshBuilder()
    py = FY + 0.2
    for x in POSTS:
        C.chamfered_bar(frame, (x, py, HEAD[1] / 2), (0.36, 0.36, HEAD[1]), 0, ch=0.03, axis='z')
        C.board(frame, (x, py, 0.1), (0.5, 0.5, 0.2), 0, bevel=0.02)                     # base block
        if x not in (POSTS[0], POSTS[-1]):                                               # gallery bracket
            _strut(frame, Vector((x, py + 0.15, 4.4)), Vector((x, FY + 1.8, GALLERY_Z - 0.3)), 0.16)
    x0, x1 = POSTS[0], POSTS[-1]
    L = x1 - x0
    C.board(frame, ((x0 + x1) / 2, FY + 0.35, (HEAD[0] + HEAD[1]) / 2), (L + 0.6, 0.9, HEAD[1] - HEAD[0]), 0, bevel=0.03)
    C.board(frame, ((x0 + x1) / 2, FY + 0.15, HEAD[1] + 0.2), (L + 0.6, 0.6, 0.4), 0, bevel=0.02)   # top plate
    for a, b in zip(POSTS[:-1], POSTS[1:]):
        open_bay = (a, b) == TERRACE
        cx, w = (a + b) / 2, b - a - 0.36
        if not open_bay:
            C.board(frame, (cx, py, 0.16), (w, 0.3, 0.32), 0, bevel=0.015)                 # sill
            C.board(frame, (cx, py + 0.02, 3.15), (w, 0.3, 0.3), 0, bevel=0.015)            # nuki tie
            n = max(2, round(w / 0.95))                                                   # shoji panels
            pw = w / n
            for k in range(n):
                px = a + 0.18 + pw * (k + 0.5)
                C.board(shoji, (px, FY + 0.06, 1.66), (pw - 0.08, 0.02, 2.66), 0, bevel=0.0)
                _kumiko(kumiko, px, FY + 0.1, 0.32, 3.0, pw - 0.02)
            for k in range(1, n):
                C.board(frame, (a + 0.18 + pw * k, FY + 0.12, 1.66), (0.07, 0.1, 2.66), 0, bevel=0.01)
        else:
            C.board(frame, (cx, py + 0.02, 4.25), (w, 0.36, 0.42), 0, bevel=0.02)           # lintel over the opening
            C.board(frame, (cx, py, 0.03), (w + 0.36, 0.5, 0.06), 0, bevel=0.01)            # threshold
        zb0 = 4.46 if open_bay else 3.3
        nb = int(w / 0.26)                                                                # upper board register
        for k in range(nb):
            bx = a + 0.18 + (k + 0.5) * w / nb
            C.board(boards, (bx, FY + 0.06, (zb0 + GALLERY_Z - 0.3) / 2), (w / nb - 0.012, 0.05, GALLERY_Z - 0.3 - zb0), 0, bevel=0.0)
        C.board(frame, (cx, py + 0.02, GALLERY_Z - 0.4), (w, 0.3, 0.26), 0, bevel=0.015)     # beam under the gallery
        # clerestory: lit shoji band over the gallery in every other bay, boards in the rest
        lit = (POSTS.index(a) % 2 == 0)
        zc0, zc1 = GALLERY_Z + 1.05, HEAD[0] - 0.25
        if lit:
            n = max(2, round(w / 0.95)); pw = w / n
            for k in range(n):
                px = a + 0.18 + pw * (k + 0.5)
                C.board(shoji, (px, FY + 0.06, (zc0 + zc1) / 2), (pw - 0.08, 0.02, zc1 - zc0), 0, bevel=0.0)
                _kumiko(kumiko, px, FY + 0.1, zc0, zc1, pw - 0.02)
            C.board(frame, (cx, py + 0.02, zc0 - 0.1), (w, 0.26, 0.2), 0, bevel=0.012)
            C.board(boards, (cx, FY + 0.06, (GALLERY_Z + zc0) / 2), (w, 0.05, zc0 - GALLERY_Z), 0, bevel=0.0)
            C.board(boards, (cx, FY + 0.06, (zc1 + HEAD[0]) / 2), (w, 0.05, HEAD[0] - zc1), 0, bevel=0.0)
        else:
            nb2 = int(w / 0.26)
            for k in range(nb2):
                bx = a + 0.18 + (k + 0.5) * w / nb2
                C.board(boards, (bx, FY + 0.06, (GALLERY_Z + HEAD[0]) / 2), (w / nb2 - 0.012, 0.05, HEAD[0] - GALLERY_Z), 0, bevel=0.0)
    # gallery deck, fascia, joist ends
    C.board(deck, ((x0 + x1) / 2, FY + 1.0, GALLERY_Z - 0.09), (L, 2.0, 0.18), 0, bevel=0.01)
    C.board(frame, ((x0 + x1) / 2, FY + 2.05, GALLERY_Z - 0.2), (L, 0.16, 0.4), 0, bevel=0.015)
    out = {}
    for name, mb, mat, role in (('facade_frame', frame, 'hinoki:dark_timber', 'wall'),
                                ('facade_boards', boards, 'hinoki:walnut', 'wall'),
                                ('facade_shoji', shoji, 'washi_backlit', 'emissive'),
                                ('facade_kumiko', kumiko, 'hinoki:stained', 'wall'),
                                ('gallery_deck', deck, 'hinoki:wet_oiled', 'floor')):
        o = P.mesh_object(name, mb.bm, 'kz_render', role=role, material=mat, bake=(mat != 'washi_backlit'))
        out[name] = _finish_shell(o, 40)
    return out


def _strut(mb, a, b, s):
    """diagonal bracket in the y-z plane from a to b (square section s)"""
    d = b - a
    C.board(mb, (a + b) / 2, (s, s, d.length), 0, bevel=0.01, rot=(math.atan2(-d.y, d.z), 0, 0))


def _kumiko(mb, cx, y, z0, z1, w):
    """shoji frame grid in front of one panel: stiles, rails, bars (0.03 m)"""
    C.board(mb, (cx - w / 2 + 0.025, y, (z0 + z1) / 2), (0.05, 0.05, z1 - z0), 0, bevel=0.0)
    C.board(mb, (cx + w / 2 - 0.025, y, (z0 + z1) / 2), (0.05, 0.05, z1 - z0), 0, bevel=0.0)
    C.board(mb, (cx, y, z0 + 0.03), (w, 0.05, 0.06), 0, bevel=0.0)
    C.board(mb, (cx, y, z1 - 0.03), (w, 0.05, 0.06), 0, bevel=0.0)
    C.board(mb, (cx, y, z0 + 0.3), (w, 0.04, 0.05), 0, bevel=0.0)                  # kick rail
    C.board(mb, (cx, y, (z0 + z1) / 2), (0.028, 0.03, z1 - z0), 0, bevel=0.0)
    nrow = max(2, int((z1 - z0) / 0.6))
    for r in range(1, nrow):
        C.board(mb, (cx, y, z0 + (z1 - z0) * r / nrow), (w, 0.03, 0.028), 0, bevel=0.0)


def door_frames():
    """east changing-hall door frame and the spiral-stair landing doorway with its surround"""
    fr = genlib.MeshBuilder(); lit = genlib.MeshBuilder(); cap = genlib.MeshBuilder()
    # east door (x = 100, y 49.75-54.25, clear h 3.3)
    for y in (49.62, 54.38):
        C.chamfered_bar(fr, (100.05, y, 1.85), (0.4, 0.34, 3.7), 0, ch=0.03, axis='z')
        C.board(fr, (100.05, y, 0.1), (0.55, 0.5, 0.2), 0, bevel=0.02)
    C.board(fr, (100.05, 52.0, 3.55), (0.44, 5.5, 0.36), 0, bevel=0.02)
    C.board(cap, (100.0, 52.0, 3.86), (0.7, 6.2, 0.18), 0, bevel=0.02)
    C.board(fr, (100.1, 52.0, 0.03), (0.6, 4.6, 0.06), 0, bevel=0.01)
    # porch frame in front of the door: two posts at x 96.6 and beams back to the wall (lantern bar)
    for y in (PORCH_Y[0], PORCH_Y[1]):
        C.chamfered_bar(fr, (PORCH_X, y, 1.95), (0.28, 0.28, 3.9), 0, ch=0.025, axis='z')
        C.board(fr, (PORCH_X, y, 0.08), (0.42, 0.42, 0.16), 0, bevel=0.02)
        C.board(fr, ((PORCH_X + 100.2) / 2, y, 3.72), (100.2 - PORCH_X + 0.3, 0.24, 0.3), 0, bevel=0.015)
    C.board(fr, (PORCH_X, 52.0, 3.72), (0.26, PORCH_Y[1] - PORCH_Y[0] + 0.7, 0.3), 0, bevel=0.015)
    C.board(cap, (PORCH_X, 52.0, 3.95), (0.42, PORCH_Y[1] - PORCH_Y[0] + 1.0, 0.16), 0, bevel=0.015)
    # stair landing door on the well rim (90, 62), clear 2.6 x 2.7
    for x in (88.52, 91.48):
        C.chamfered_bar(fr, (x, 61.8, 1.6), (0.32, 0.32, 3.2), 0, ch=0.025, axis='z')
        C.board(fr, (x, 61.8, 0.1), (0.46, 0.46, 0.2), 0, bevel=0.02)
    C.board(fr, (90.0, 61.8, 2.85), (3.6, 0.3, 0.3), 0, bevel=0.015)                 # lintel
    C.board(fr, (90.0, 61.8, 3.12), (2.64, 0.06, 0.24), 0, bevel=0.0)                # transom frame
    C.board(lit, (90.0, 61.76, 3.12), (2.6, 0.02, 0.2), 0, bevel=0.0)
    C.board(fr, (90.0, 61.8, 3.36), (3.9, 0.36, 0.24), 0, bevel=0.015)               # head beam
    _kasagi(cap, 90.0, 61.8, 3.48, 4.6, 0.62)
    out = {}
    for name, mb, mat, role in (('door_frames', fr, 'hinoki:dark_timber', 'wall'),
                                ('door_transom', lit, 'washi_backlit', 'emissive'),
                                ('door_caps', cap, 'lacquer_black', 'wall')):
        o = P.mesh_object(name, mb.bm, 'kz_render', role=role, material=mat, bake=(mat != 'washi_backlit'))
        out[name] = _finish_shell(o, 40)
    return out


def _kasagi(mb, cx, cy, z, w, d):
    """slightly upswept cap beam (lacquer) over the stair door"""
    pts = []
    for k in range(13):
        t = -1 + 2 * k / 12
        pts.append(Vector((cx + t * w / 2, cy, z + 0.12 * t ** 4)))
    prof = [(-d / 2, 0), (d / 2, 0), (d / 2 + 0.03, 0.1), (d / 2 + 0.05, 0.16), (-d / 2 - 0.05, 0.16), (-d / 2 - 0.03, 0.1)]
    C.sweep(mb, pts, prof, 0)


# ------------------------------------------------------------------------------------------------ water
def water_ribbon(stream_obj, offset):
    """kz_water surface on the stream centre line, z from the generator's pool levels"""
    cl = json.loads(stream_obj['kz_centerline'])
    wp = json.loads(stream_obj['kz_water_path'])
    pools = []
    for a, b in zip(wp[:-1], wp[1:]):
        if abs(a[2] - b[2]) < 1e-6 and (abs(a[0] - b[0]) + abs(a[1] - b[1])) > 1e-6:
            pools.append((Vector((a[0], a[1])), Vector((b[0], b[1])), a[2]))

    def level(x, y):
        p = Vector((x, y)); best = None
        for a, b, z in pools:
            ab = b - a; t = clamp((p - a).dot(ab) / max(ab.length_squared, 1e-9), 0, 1)
            dd = (a + ab * t - p).length
            if best is None or dd < best[0]:
                best = (dd, z)
        return best[1]
    bm = bmesh.new()
    prev = None
    pts = [Vector((c[0], c[1], 0)) for c in cl]
    for i, c in enumerate(cl):
        a = pts[max(0, i - 1)]; b = pts[min(len(pts) - 1, i + 1)]
        t = (b - a).normalized(); n = Vector((-t.y, t.x, 0))
        hw = c[2] + 0.12
        z = level(c[0], c[1]) + offset.z
        L = Vector((c[0] + offset.x, c[1] + offset.y, z)) + n * hw
        R = Vector((c[0] + offset.x, c[1] + offset.y, z)) - n * hw
        cur = (bm.verts.new(L), bm.verts.new(R))
        if prev:
            bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
        prev = cur
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    o = P.mesh_object('water_w_hall_stream', bm, 'kz_water', role='water', material='water_river', bake=False)
    genlib.uv0_metric(o)
    o['kz_water'] = 'w_hall_stream'; o['kz_water_kind'] = 'flow'; o['kz_planar'] = False
    o['kz_absorption'] = [0.45, 0.12, 0.08]
    o['kz_flow'] = json.dumps({'path': [[c[0] + offset.x, c[1] + offset.y] for c in cl[::4]], 'speed_mps': 0.35,
                               'weirs': [[w[0] + offset.x, w[1] + offset.y, w[2] + offset.z, w[3] + offset.z]
                                         for w in json.loads(stream_obj['kz_weirs'])]})
    return o


# ------------------------------------------------------------------------------------------------ dressing
def dress(asset, seed, at, heading=0.0, name=None, collection='kz_render', role=None, bake=None, gen_kw=None, **params):
    gen = ALIAS.get(asset, asset)
    params.update(gen_kw or {})
    o = P.dress(gen, seed=seed, at=at, heading=heading, name=name, collection=collection, **params)
    o['kz_space_asset'] = asset
    if role:
        o['kz_role'] = role
    if bake is not None:
        o['kz_bake'] = bool(bake)
    for ch in list(o.children):                             # figure rigs follow their mesh
        P.link(ch, collection)
    return o


def lights_from_props(o, scale=1.0, runtime=False, skip=(), push=0.0):
    """kz_lights (generator JSON, object space) -> Blender lights in kz_lights (world space)"""
    raw = o.get('kz_lights') or o.get('kz_light')
    if not raw:
        return []
    L = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(L, dict):
        L = [L]
    M = o.matrix_world; R = M.to_3x3().normalized()
    made = []
    for n, e in enumerate(L):
        if n in skip:
            continue
        kind = (e.get('kind') or e.get('type') or 'point').lower()
        k = e.get('color_k')
        col = e.get('color')
        w = e.get('watts') or e.get('energy') or e.get('power') or 15.0
        name = f'L_{o.name}_{n}'
        if kind == 'strip' or 'p0' in e:
            p0 = M @ Vector(e['p0']); p1 = M @ Vector(e['p1'])
            ln = (p1 - p0).length
            w = e.get('power_w_per_m', 6.0) * ln
            nrm = (R @ Vector(e.get('normal', (0, 0, -1)))).normalized()
            l = _mk_light(name, 'AREA', (p0 + p1) / 2, w * scale, col, k, runtime)
            l.data.shape = 'RECTANGLE'; l.data.size = max(ln, 0.05); l.data.size_y = 0.1
            _aim(l, nrm, (p1 - p0).normalized())
        elif kind == 'area':
            nrm = (R @ Vector(e.get('normal', (0, 1, 0)))).normalized()
            pos = M @ Vector(e['pos']) + nrm * push           # push: move it in front of the glass
            sz = e.get('size', [1, 1])
            l = _mk_light(name, 'AREA', pos, w * scale, col, k, runtime)
            l.data.shape = 'RECTANGLE'; l.data.size = sz[0]; l.data.size_y = sz[1]
            _aim(l, nrm, (R @ Vector((1, 0, 0))).normalized())
        elif 'len' in e:
            pos = M @ Vector(e['pos'])
            l = _mk_light(name, 'AREA', pos, w * scale, col, k, runtime)
            l.data.shape = 'RECTANGLE'; l.data.size = e['len']; l.data.size_y = 0.08
            _aim(l, Vector((0, 0, -1)), (R @ Vector((1, 0, 0))).normalized())
        elif kind in ('spot_down', 'uplight', 'spot'):
            pos = M @ Vector(e['pos'])
            aim = (M @ Vector(e['aim']) - pos).normalized() if 'aim' in e else Vector((0, 0, -1 if kind == 'spot_down' else 1))
            l = _mk_light(name, 'SPOT', pos, w * scale, col, k, runtime)
            l.data.spot_size = math.radians(e.get('cone_deg', 60)) * 1.4
            l.data.spot_blend = 0.6
            _aim(l, aim, None)
        else:
            pos = M @ Vector(e['pos'])
            l = _mk_light(name, 'POINT', pos, w * scale, col, k, runtime)
            l.data.shadow_soft_size = 0.08
        l['kz_from'] = o.name
        made.append(l)
    return made


def _mk_light(name, kind, pos, watts, col, k, runtime):
    kel = k or 2400
    l = P.light(name, kind, pos, watts, kelvin=kel, runtime=runtime)
    l.visible_camera = False                          # the emissive meshes are what the eye sees
    l.visible_transmission = False                    # ... also through the lava glass
    if kind == 'AREA':
        l.visible_glossy = False
    if col and not k:
        l.data.color = tuple(col[:3])
    return l


def _aim(l, nrm, xaxis):
    """point a light's -Z along nrm"""
    z = -nrm.normalized()
    if xaxis is None or abs(xaxis.dot(z)) > 0.99:
        xaxis = Vector((1, 0, 0)) if abs(z.x) < 0.9 else Vector((0, 1, 0))
    x = (xaxis - z * xaxis.dot(z)).normalized(); y = z.cross(x)
    l.rotation_euler = Matrix((x, y, z)).transposed().to_euler()


def ceiling_z_at(objs, x, y, z0=1.0):
    """first rock hit straight up from (x, y, z0)"""
    best = None
    for o in objs:
        bvh = _bvh(o)
        hit = bvh.ray_cast(Vector((x, y, z0)), Vector((0, 0, 1)), 60.0)
        if hit[0] is not None and (best is None or hit[0].z < best):
            best = hit[0].z
    return best


_BVH = {}


def _bvh(o):
    if o.name not in _BVH:
        dg = bpy.context.evaluated_depsgraph_get()
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world)
        _BVH[o.name] = BVHTree.FromBMesh(bm)
        bm.free(); oe.to_mesh_clear()
    return _BVH[o.name]


def bvh_of(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in objs:
        oe = o.evaluated_get(dg); me = oe.to_mesh()
        tmp = bmesh.new(); tmp.from_mesh(me); tmp.transform(o.matrix_world)
        tme = bpy.data.meshes.new('tmp'); tmp.to_mesh(tme); tmp.free(); bm.from_mesh(tme)
        bpy.data.meshes.remove(tme); oe.to_mesh_clear()
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


# ------------------------------------------------------------------------------------------------ walk mesh
CELL = 0.5


def walk_mesh(stream_cl, cut_add, slot_box, decks, blockers, portals):
    """kz_walk: 0.5 m floor cells (footprint minus stream corridor, lift well, drain slot and blockers),
    deck strips (bridge, lift bridge), 1.1 m walls on every open edge except portal spans and deck joins.
    Returns (object, graph info for the checks)."""
    nx, ny = int(60 / CELL), int(38 / CELL)
    seg = [(Vector((a[0], a[1])), Vector((b[0], b[1])), a[2], b[2]) for a, b in zip(stream_cl[:-1], stream_cl[1:])]

    def in_stream(p):
        for a, b, ha, hb in seg:
            ab = b - a; t = clamp((p - a).dot(ab) / max(ab.length_squared, 1e-9), 0, 1)
            if (a + ab * t - p).length < (ha + (hb - ha) * t) + cut_add:
                return True
        # ends extended
        return False
    walk = {}
    for i in range(nx):
        for j in range(ny):
            x = 40 + (i + 0.5) * CELL; y = 42 + (j + 0.5) * CELL
            p = Vector((x, y))
            if in_stream(p):
                continue
            if math.hypot(x - 90, y - 70) < 7.75 + 0.25:
                continue
            if slot_box[0] - 0.1 < x < slot_box[2] + 0.1 and slot_box[1] - 0.1 < y < slot_box[3] + 0.1:
                continue
            if any(bx0 <= x <= bx1 and by0 <= y <= by1 for bx0, by0, bx1, by1 in blockers):
                continue
            walk[(i, j)] = 0.0
    bm = bmesh.new()
    VV = {}

    def gv(i, j, z=0.0):
        k = (i, j)
        if k not in VV:
            VV[k] = bm.verts.new((40 + i * CELL, 42 + j * CELL, z))
        return VV[k]
    for (i, j) in walk:
        bm.faces.new((gv(i, j), gv(i + 1, j), gv(i + 1, j + 1), gv(i, j + 1)))
    deck_cells = []
    for name, pts, half in decks:                           # pts: [(x, y, z)] along the deck centre
        prev = None
        for k, p in enumerate(pts):
            a = Vector(pts[max(0, k - 1)][:2]); b = Vector(pts[min(len(pts) - 1, k + 1)][:2])
            t = (b - a).normalized(); n = Vector((-t.y, t.x))
            Lv = bm.verts.new((p[0] + n.x * half, p[1] + n.y * half, p[2]))
            Rv = bm.verts.new((p[0] - n.x * half, p[1] - n.y * half, p[2]))
            if prev:
                bm.faces.new((prev[0], prev[1], Rv, Lv))
                for s in (prev[0], Lv), (Rv, prev[1]):       # rails
                    top = [bm.verts.new(v.co + Vector((0, 0, 1.1))) for v in s]
                    bm.faces.new((s[0], s[1], top[1], top[0]))
            prev = (Lv, Rv)
        deck_cells.append((name, pts, half))

    def portal_hit(x0, y0, x1, y1):
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for pt in portals:
            (px, py), w = pt['at'], pt['width']
            if abs(mx - px) < 0.2 + (w / 2 if abs(x0 - x1) > 1e-6 else 0.0) and abs(my - py) < 0.2 + (w / 2 if abs(y0 - y1) > 1e-6 else 0.0):
                return True
        return False

    def deck_join(x, y):
        for name, pts, half in decks:
            for p in (pts[0], pts[-1]):
                if math.hypot(x - p[0], y - p[1]) < half + 0.8:
                    return True
        return False
    walls = 0
    for (i, j) in walk:
        for di, dj, e in ((1, 0, ((i + 1, j), (i + 1, j + 1))), (-1, 0, ((i, j), (i, j + 1))),
                          (0, 1, ((i, j + 1), (i + 1, j + 1))), (0, -1, ((i, j), (i + 1, j)))):
            if (i + di, j + dj) in walk:
                continue
            (a0, b0), (a1, b1) = e
            x0, y0 = 40 + a0 * CELL, 42 + b0 * CELL
            x1, y1 = 40 + a1 * CELL, 42 + b1 * CELL
            if portal_hit(x0, y0, x1, y1) or deck_join((x0 + x1) / 2, (y0 + y1) / 2):
                continue
            v0, v1 = gv(*e[0]), gv(*e[1])
            t0 = bm.verts.new(v0.co + Vector((0, 0, 1.1))); t1 = bm.verts.new(v1.co + Vector((0, 0, 1.1)))
            bm.faces.new((v0, v1, t1, t0)); walls += 1
    o = P.mesh_object('walk_g_arrival', bm, 'kz_walk', role='walk')
    o['kz_cell'] = CELL
    return o, dict(cells=walk, decks=decks, walls=walls)


def flood(walk, decks, sources, targets):
    """BFS over walk cells (4-neighbour) plus deck strips joining the cells at both ends."""
    nbr = {}
    cells = set(walk)

    def cell_of(x, y):
        return (int((x - 40) / CELL), int((y - 42) / CELL))

    def nearest(x, y, r=1.6):
        best = None
        for c in cells:
            cx, cy = 40 + (c[0] + 0.5) * CELL, 42 + (c[1] + 0.5) * CELL
            d = math.hypot(cx - x, cy - y)
            if d < r and (best is None or d < best[0]):
                best = (d, c)
        return best[1] if best else None
    for c in cells:
        nbr[c] = [(c[0] + di, c[1] + dj) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (c[0] + di, c[1] + dj) in cells]
    for name, pts, half in decks:
        ends = [nearest(pts[0][0], pts[0][1], half + 1.0), nearest(pts[-1][0], pts[-1][1], half + 1.0)]
        node = ('deck', name)
        nbr[node] = [e for e in ends if e]
        for e in ends:
            if e:
                nbr[e].append(node)
    res = {}
    for sname, (sx, sy) in sources.items():
        s = nearest(sx, sy)
        seen = {s} if s else set()
        dq = deque([s] if s else [])
        while dq:
            c = dq.popleft()
            for n in nbr.get(c, []):
                if n not in seen:
                    seen.add(n); dq.append(n)
        res[sname] = {t: (nearest(tx, ty) in seen) for t, (tx, ty) in targets.items()}
    return res


# ------------------------------------------------------------------------------------------------ checks
HANGING = {'chochin', 'banner_hanging', 'stalactite_cluster', 'noren'}
WALLMOUNT = {'signboard_kanji'}


def _layer(name, exclude):
    lc = bpy.context.view_layer.layer_collection.children.get(name)
    if lc:
        lc.exclude = exclude


def _tris(objs):
    dg = bpy.context.evaluated_depsgraph_get(); n = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        oe = o.evaluated_get(dg); me = oe.to_mesh(); me.calc_loop_triangles(); n += len(me.loop_triangles); oe.to_mesh_clear()
    return n


def run_checks(S, WI, DECKS, floor, stream, bridge, drum, hero_view=(61.0, 75.0), extra_ground=()):
    out = {'space': SID, 'contract': 'PLACE_CONTRACT v1'}
    render = [o for o in P.coll('kz_render').objects if o.type == 'MESH']
    anim = [o for o in P.coll('kz_anim').objects if o.type == 'MESH']
    water = [o for o in P.coll('kz_water').objects if o.type == 'MESH']
    by_role, by_obj = {}, []
    for o in render:
        t = _tris([o]); by_role[o.get('kz_role', '?')] = by_role.get(o.get('kz_role', '?'), 0) + t
        by_obj.append((t, o.name))
    mats = set(); ids = set()
    for o in render + water + anim:
        for m in o.data.materials:
            if m:
                mats.add(m.name); ids.add(m.get('kz_id', m.name.split('~')[0]))
    out['triangles'] = {'kz_render': sum(by_role.values()), 'kz_anim': _tris(anim), 'kz_water': _tris(water),
                        'by_role': by_role, 'top_objects': [[n, t] for t, n in sorted(by_obj, reverse=True)[:14]],
                        'budget_hero': 250000}
    out['materials'] = {'blender_materials': len(mats), 'library_ids': len(ids), 'ids': sorted(ids), 'budget': 40}
    # flood fill
    portals = {p['id']: tuple(p['at']) for p in S['portals']}
    targets = dict(portals); targets['hero_view'] = hero_view
    fl = flood(WI['cells'], DECKS, portals, targets)
    ok = all(all(v.values()) for v in fl.values())
    out['flood_fill'] = {'pass': ok, 'cells': len(WI['cells']), 'wall_quads': WI['walls'], 'reach': fl}
    # clearance along the spine
    for c in ('kz_anim', 'kz_walk', 'kz_probes', 'kz_fx', 'kz_cameras', 'kz_lights', 'render_only'):
        _layer(c, True)
    dg = bpy.context.evaluated_depsgraph_get(); sc = bpy.context.scene
    bb = _bvh(bridge)
    sp = [Vector(p) for p in S['spine']]
    worst, samples, low = 99.0, 0, []
    for a, b in zip(sp[:-1], sp[1:]):
        n = max(1, int((b - a).length / 0.5))
        for k in range(n + 1):
            p = a + (b - a) * (k / n)
            if 62.4 < p.x < 69.6 and abs(p.y - 62.0) < 1.7:          # on the bridge: walk the clear deck
                p = Vector((p.x, 62.0 + max(-0.85, min(0.85, p.y - 62.0)), 0))
                h = bb.ray_cast(Vector((p.x, p.y, 3.0)), Vector((0, 0, -1)), 6.0)
                z = h[0].z if h[0] is not None else 0.0
            else:
                z = 0.0
            hit, loc, *_ = sc.ray_cast(dg, Vector((p.x, p.y, z + 0.1)), Vector((0, 0, 1)), distance=40.0)
            cl = (loc.z - z) if hit else 40.0
            samples += 1
            if cl < worst:
                worst = cl
            if cl < 2.1:
                low.append([round(p.x, 2), round(p.y, 2), round(cl, 2)])
    out['clearance'] = {'pass': worst >= 2.1, 'min_m': round(worst, 2), 'samples': samples, 'below_2.1': low[:20]}
    # portals open at floor_z
    fb = _bvh(floor)
    pres = {}
    for p in S['portals']:
        px, py = p['at']; w = p['width']; h = min(p.get('height', 2.4), 2.4)
        if abs(px - 40) < 1e-6:
            d = Vector((-1, 0, 0))
        elif abs(px - 100) < 1e-6:
            d = Vector((1, 0, 0))
        elif abs(py - 42) < 1e-6:
            d = Vector((0, -1, 0))
        elif abs(py - 80) < 1e-6:
            d = Vector((0, 1, 0))
        else:
            bdeg = next((q.get('bearing') for q in P.layout()['portals'] if q['id'] == p['id']), 0.0) or 0.0
            d = -Vector((math.sin(math.radians(bdeg)), math.cos(math.radians(bdeg)), 0))
        lat = Vector((-d.y, d.x, 0))
        hits = []
        for i in range(7):
            s = (-0.5 + i / 6) * (w - 0.3)
            for z in (0.15, 0.9, 1.7, h - 0.15):
                o0 = Vector((px, py, z)) + lat * s - d * 0.6
                hit, loc, nrm, idx, ob, mtx = sc.ray_cast(dg, o0, d, distance=1.2)
                if hit:
                    hits.append([round(s, 2), z, ob.name])
        g = fb.ray_cast(Vector((px, py, 1.0)) - d * 0.3, Vector((0, 0, -1)), 3.0)
        fz = round(g[0].z, 3) if g[0] is not None else None
        pres[p['id']] = {'open': not hits, 'floor_z': fz, 'width': w, 'blocked_by': hits[:6]}
    out['portals'] = {'pass': all(v['open'] and v['floor_z'] is not None and abs(v['floor_z']) < 0.03 for v in pres.values()),
                      'each': pres}
    # dressing floating / sunk
    eg = list(extra_ground)
    grounds = {'all': bvh_of([floor, stream, bridge, drum] + eg), 'nobridge': bvh_of([floor, stream, drum] + eg),
               'nodrum': bvh_of([floor, stream, bridge] + eg)}
    res, bad = [], 0
    for o in render + anim:
        a = o.get('kz_asset')
        if not a or o.get('kz_shell') or a in ('stream_channel', 'lava_backdrop') or a in HANGING or a in WALLMOUNT:
            continue
        if o.name.startswith('hall_sign'):
            continue
        ws = [o.matrix_world @ v.co for v in o.data.vertices]
        zmin = min(v.z for v in ws)
        org = o.matrix_world.translation
        ground = grounds['nobridge' if o == bridge else 'nodrum' if o == drum else 'all']
        probes = [Vector((org.x, org.y))]
        if a in ('lift_drum', 'culvert_grate', 'bridge_arched'):      # spans a hole: test its footprint corners
            xs = [v.x for v in ws]; ys = [v.y for v in ws]
            probes = [Vector((x, y)) for x in (min(xs) + 0.05, max(xs) - 0.05) for y in (min(ys) + 0.05, max(ys) - 0.05)]
        gz = []
        for q in probes:
            g = ground.ray_cast(Vector((q.x, q.y, zmin + 1.5)), Vector((0, 0, -1)), 6.0)
            if g[0] is not None:
                gz.append(g[0].z)
        if not gz:
            res.append([o.name, a, None, 'no ground under the pivot']); continue
        gap = zmin - max(gz)
        if a == 'culvert_grate':                                     # flush grate: its top against the paving
            gap = max(v.z for v in ws) - max(gz) - 0.01
        emb = float(o.get('kz_embed', 0.25 if a in ('boulder_rim', 'rock_cluster', 'wall_trickle') else 0.0))
        ok = (-emb - 0.02) <= gap <= 0.02
        if a in ('boulder_rim', 'rock_cluster', 'wall_trickle') and gap < 0:
            ok = gap >= -emb - 0.05
        bad += (not ok)
        res.append([o.name, a, round(gap, 3), 'ok' if ok else ('floating' if gap > 0 else 'sunk')])
    out['dressing_ground'] = {'pass': bad == 0, 'failures': bad, 'objects': res}
    for c in ('kz_anim', 'kz_walk', 'kz_probes', 'kz_fx', 'kz_cameras', 'kz_lights', 'render_only'):
        _layer(c, False)
    out['summary'] = {k: out[k]['pass'] for k in ('flood_fill', 'clearance', 'portals', 'dressing_ground')}
    out['summary'].update(tris=out['triangles']['kz_render'], tris_anim=out['triangles']['kz_anim'],
                          materials=out['materials']['blender_materials'], library_ids=out['materials']['library_ids'])
    return out


# ------------------------------------------------------------------------------------------------ renders
RDIR = os.path.join(ROOT, '3d', 'renders', 'places', SID)


def _cycles(samples, res):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    c = sc.cycles
    c.device = 'GPU'; c.samples = samples; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.015
    c.use_denoising = True; c.denoiser = 'OPTIX'
    c.max_bounces = 8; c.glossy_bounces = 4; c.transmission_bounces = 8; c.transparent_max_bounces = 16
    c.caustics_reflective = False; c.caustics_refractive = False; c.blur_glossy = 0.5; c.sample_clamp_indirect = 10.0
    c.light_sampling_threshold = 0.01
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0.0


def context_standins():
    """render-only context outside the footprint (NOT saved): g_gate torii + paving + two lanterns"""
    made = []
    col = bpy.data.collections.new('ctx_render_only'); bpy.context.scene.collection.children.link(col)
    gs = json.load(open(os.path.join(ROOT, '3d', 'spaces', 'g_gate.json')))['hero']
    o = P.dress('torii_basalt', seed=1, at=tuple(gs['at']), heading=gs['facing_deg'] - 180, collection='kz_render',
                h=8.9, post_d=1.5, overhang=1.6)
    P.link(o, 'ctx_render_only'); made.append(o)
    mb = genlib.MeshBuilder(); mb.box((24.0, 55.0, -0.2), (24.0, 30.0, 0.4), 0)
    g = P.mesh_object('ctx_gate_floor', mb.bm, 'kz_render', material='paving'); genlib.uv0_metric(g)
    P.link(g, 'ctx_render_only'); made.append(g)
    for k, y in enumerate((50.0, 60.0)):
        lo = P.dress('lantern_stone', seed=1, at=(23.0, y, 0), heading=90, collection='kz_render')
        P.link(lo, 'ctx_render_only'); made.append(lo)
        lights_from_props(lo)
    for k, x in enumerate((17.0, 21.0)):
        l = P.light(f'ctx_torii_up.{k}', 'SPOT', (x, 55.0 + (-3.2 if k else 3.2), 0.4), 300, kelvin=2400)
        l.data.spot_size = math.radians(50); _aim(l, Vector((0, 0, 1)), None)
        made.append(l)
    l = P.light('ctx_gate_glow', 'AREA', (14.0, 55.0, 4.0), 2500, kelvin=2600, size=8.0)
    _aim(l, Vector((1, 0, 0)), None); made.append(l)
    return made


def _render(cam, path, res, samples):
    sc = bpy.context.scene
    _cycles(samples, res)
    sc.camera = bpy.data.objects[cam]
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('rendered', path, flush=True)


def renders(S, only=()):
    os.makedirs(RDIR, exist_ok=True)
    context_standins()
    for c in P.coll('kz_cameras').objects:
        c.data.clip_end = 400
    jobs = [('cam_concept', 'canonical_raw.jpg', (1600, 900), 128),
            ('cam_entry', 'entry_169.jpg', (1280, 720), 96), ('cam_reveal', 'reveal_169.jpg', (1280, 720), 96),
            ('cam_entry', 'entry_916.jpg', (540, 960), 96), ('cam_reveal', 'reveal_916.jpg', (540, 960), 96)]
    want = {a.split('=')[1] for a in only}
    for cam, fn, res, smp in jobs:
        if want and fn.split('.')[0] not in want:
            continue
        _render(cam, os.path.join(RDIR, fn), res, smp)
    if not want or 'plan' in want:
        render_plan()


def render_plan():
    sc = bpy.context.scene
    for o in P.coll('kz_render').objects:
        if o.get('kz_role') == 'ceiling' or o.get('kz_asset') in ('stalactite_cluster', 'chochin', 'banner_hanging') \
                or o.name in ('facade_boards', 'gallery_deck', 'facade_frame', 'facade_kumiko', 'facade_shoji', 'door_caps'):
            o.hide_render = True
    for o in bpy.data.collections['ctx_render_only'].objects:
        o.hide_render = True
    P.coll('kz_walk').hide_render = False
    w = bpy.data.objects['walk_g_arrival']; w.location.z = 0.05
    m = bpy.data.materials.new('plan_walk_tint'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.1, 1.0, 0.35, 1); em.inputs['Strength'].default_value = 0.6
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs[0].default_value = 0.55
    outn = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], outn.inputs[0])
    w.data.materials.clear(); w.data.materials.append(m)
    sun = bpy.data.lights.new('plan_sun', 'SUN'); sun.energy = 1.6; sun.color = (1.0, 0.92, 0.82)
    so = bpy.data.objects.new('plan_sun', sun); so.rotation_euler = (math.radians(25), math.radians(10), 0)
    sc.collection.objects.link(so)
    cd = bpy.data.cameras.new('cam_plan'); cd.type = 'ORTHO'; cd.ortho_scale = 66.0; cd.clip_end = 200
    co = bpy.data.objects.new('cam_plan', cd); co.location = (70.0, 61.0, 60.0); sc.collection.objects.link(co)
    _render('cam_plan', os.path.join(RDIR, 'plan.jpg'), (1320, 900), 48)


# ------------------------------------------------------------------------------------------------ fix round 1
TERRACE_BOX = (52.6, 44.2, 62.6, 50.4)      # raised reception terrace (one 0.17 m step)
TERRACE_Z = 0.17
BASIN_C, BASIN_R = (76.3, 45.3), 2.5        # blossom basin round the sakura (dollhouse)


def reception_terrace():
    """one 0.17 m stone step: paving top on a basalt kerb (a stepped floor, not one plane)"""
    x0, y0, x1, y1 = TERRACE_BOX
    mb = genlib.MeshBuilder()
    C.board(mb, ((x0 + x1) / 2, (y0 + y1) / 2, TERRACE_Z / 2 - 0.01), (x1 - x0 - 0.3, y1 - y0 - 0.3, TERRACE_Z + 0.02), 0, bevel=0.01)
    top = P.mesh_object('reception_terrace', mb.bm, 'kz_render', role='floor', material='paving', bake=True)
    mb = genlib.MeshBuilder()
    for (cx, cy, sx, sy) in (((x0 + x1) / 2, y0 + 0.15, x1 - x0, 0.3), ((x0 + x1) / 2, y1 - 0.15, x1 - x0, 0.3),
                             (x0 + 0.15, (y0 + y1) / 2, 0.3, y1 - y0 - 0.6), (x1 - 0.15, (y0 + y1) / 2, 0.3, y1 - y0 - 0.6)):
        C.board(mb, (cx, cy, TERRACE_Z / 2), (sx, sy, TERRACE_Z), 0, bevel=0.025, segs=2)
    kerb = P.mesh_object('reception_terrace_kerb', mb.bm, 'kz_render', role='stair', material='basalt_wet', bake=True)
    return _finish_shell(top, 40), _finish_shell(kerb, 40)


def blossom_basin():
    """the dollhouse's blossom basin: a raised round pool of rough basalt (kerb 0.45 m, lumpy rim) round the
    sakura, which stands on a mossy rock island; water surface as kz_water (proposed id w_blossom_basin)"""
    cx, cy = BASIN_C; R = BASIN_R
    mb = genlib.MeshBuilder()
    n = 64
    f = C.stone_outline(C.rng(1, 'basin'), 1.0, aspect=1.0, harmonics=((3, 0.03), (5, 0.025), (8, 0.02)), bites=0)
    rings = []
    prof = [(R + 0.12, -0.05), (R + 0.16, 0.2), (R + 0.06, 0.45), (R - 0.12, 0.48), (R - 0.3, 0.42), (R - 0.34, 0.1), (R - 0.34, -0.25)]
    bm = mb.bm
    for k in range(n):
        th = 2 * math.pi * k / n
        ox, oy = f(th); sc = math.hypot(ox, oy)
        ring = []
        for (r, z) in prof:
            rr_ = r * sc + 0.05 * noise.noise(Vector((math.cos(th) * 3, math.sin(th) * 3, z * 4)))
            ring.append(bm.verts.new((cx + rr_ * math.cos(th), cy + rr_ * math.sin(th), z)))
        rings.append(ring)
    for k in range(n):
        A, B = rings[k], rings[(k + 1) % n]
        for i in range(len(prof) - 1):
            bm.faces.new((A[i], B[i], B[i + 1], A[i + 1]))
    bed = [bm.verts.new((cx + (R - 0.34) * math.cos(2 * math.pi * k / n), cy + (R - 0.34) * math.sin(2 * math.pi * k / n), -0.25)) for k in range(n)]
    bm.faces.new(bed)
    ring = P.mesh_object('blossom_basin', mb.bm, 'kz_render', role='basin', material='basalt_wet', bake=True)
    _finish_shell(ring, 30)
    for fc in ring.data.polygons:
        pass
    # island: a low cobble under the tree
    mb = genlib.MeshBuilder()
    fo = C.stone_outline(C.rng(2, 'island'), 0.85, aspect=1.1, bites=1)
    C.cobble(mb, fo, 40, 0.55, 0, 0, side_noise=0.03, r=C.rng(2, 'isl'))
    isl = P.mesh_object('blossom_island', mb.bm, 'kz_render', role='rock', material='basalt_wet', bake=True)
    isl.location = (cx, cy, -0.25)
    _finish_shell(isl, 30)
    # water
    bmw = bmesh.new()
    vs = [bmw.verts.new((cx + (R - 0.3) * math.cos(2 * math.pi * k / n), cy + (R - 0.3) * math.sin(2 * math.pi * k / n), 0.3)) for k in range(n)]
    bmw.faces.new(vs)
    w = P.mesh_object('water_w_blossom_basin', bmw, 'kz_water', role='water', material='water_still', bake=False)
    genlib.uv0_metric(w)
    w['kz_water'] = 'w_blossom_basin'; w['kz_water_kind'] = 'still'; w['kz_planar'] = True
    w['kz_absorption'] = [0.45, 0.12, 0.08]; w['kz_flow'] = '{}'; w['kz_note'] = 'proposed layout water id'
    return ring, isl, w


def haze_volume():
    """render-only warm haze (Principled Volume box over hall + lava cave); kz_role render_only, not exported"""
    col = bpy.data.collections.get('render_only') or bpy.data.collections.new('render_only')
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    mb = genlib.MeshBuilder(); mb.box((70.0, 61.0, 8.0), (64.0, 38.6, 18.0), 0)     # hall only (x 38-102, y 41.7-79.3)
    me = bpy.data.meshes.new('haze'); mb.bm.to_mesh(me); mb.bm.free()
    o = bpy.data.objects.new('haze_render_only', me); col.objects.link(o)
    m = bpy.data.materials.new('haze_render_only'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    v = nt.nodes.new('ShaderNodeVolumePrincipled'); out = nt.nodes.new('ShaderNodeOutputMaterial')
    v.inputs['Color'].default_value = (1.0, 0.82, 0.62, 1); v.inputs['Density'].default_value = 0.0012
    v.inputs['Anisotropy'].default_value = 0.45
    nt.links.new(v.outputs[0], out.inputs['Volume'])
    me.materials.append(m)
    o['kz_role'] = 'render_only'; o['kz_bake'] = False
    return o


def walk_from_floor(floor, extra_boxes, portals, decks, raise_box=None, raise_z=0.0):
    """kz_walk with smooth outlines: the floor's top faces clipped to the footprint, minus blocker boxes,
    the reception terrace raised (split edges + riser quads), plus deck strips and 1.1 m walls on open edges."""
    bm = bmesh.new(); bm.from_mesh(floor.data); bm.transform(floor.matrix_world)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < 0.9 or f.calc_center_median().z < -0.05], context='FACES')
    for co, no in (((40, 0, 0), (-1, 0, 0)), ((100, 0, 0), (1, 0, 0)), ((0, 42, 0), (0, -1, 0)), ((0, 80, 0), (0, 1, 0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
    boxes = list(extra_boxes) + ([raise_box] if raise_box else [])
    for (x0, y0, x1, y1) in boxes:
        for co, no in (((x0, 0, 0), (1, 0, 0)), ((x1, 0, 0), (1, 0, 0)), ((0, y0, 0), (0, 1, 0)), ((0, y1, 0), (0, 1, 0))):
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    inside = lambda c, b: b[0] - 1e-4 <= c.x <= b[2] + 1e-4 and b[1] - 1e-4 <= c.y <= b[3] + 1e-4
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if any(inside(f.calc_center_median(), b) for b in extra_boxes)], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    if raise_box:
        tf = [f for f in bm.faces if inside(f.calc_center_median(), raise_box)]
        border = [e for e in bm.edges if len(e.link_faces) == 2 and sum(f in tf for f in e.link_faces) == 1]
        bmesh.ops.split_edges(bm, edges=border)
        tv = {v for f in tf for v in f.verts}
        for v in tv:
            v.co.z = raise_z
        for e in [e for e in bm.edges if len(e.link_faces) == 1 and all(v in tv for v in e.verts)]:
            a, b = e.verts
            a0 = bm.verts.new((a.co.x, a.co.y, 0.0)); b0 = bm.verts.new((b.co.x, b.co.y, 0.0))
            bm.faces.new((a0, b0, b, a))
    bm.normal_update()
    top = [f for f in bm.faces if f.normal.z > 0.9]

    def portal_hit(mx, my):
        for pt in portals:
            (px, py), w = pt['at'], pt['width']
            if math.hypot(mx - px, my - py) < w / 2 + 0.2:
                return True
        return False

    def deck_join(x, y):
        for name, pts, half in decks:
            for p in (pts[0], pts[-1]):
                if math.hypot(x - p[0], y - p[1]) < half + 0.8:
                    return True
        return False
    walls = 0
    for e in [e for e in bm.edges if sum(1 for f in e.link_faces if f in top) == 1 and len(e.link_faces) == 1]:
        a, b = e.verts
        m = (a.co + b.co) / 2
        if portal_hit(m.x, m.y) or deck_join(m.x, m.y):
            continue
        ta = bm.verts.new(a.co + Vector((0, 0, 1.1))); tb = bm.verts.new(b.co + Vector((0, 0, 1.1)))
        bm.faces.new((a, b, tb, ta)); walls += 1
    for name, pts, half in decks:
        prev = None
        for k, p in enumerate(pts):
            A_ = Vector(pts[max(0, k - 1)][:2]); B_ = Vector(pts[min(len(pts) - 1, k + 1)][:2])
            t = (B_ - A_).normalized(); n = Vector((-t.y, t.x))
            Lv = bm.verts.new((p[0] + n.x * half, p[1] + n.y * half, p[2]))
            Rv = bm.verts.new((p[0] - n.x * half, p[1] - n.y * half, p[2]))
            if prev:
                bm.faces.new((prev[0], prev[1], Rv, Lv))
                for s_ in (prev[0], Lv), (Rv, prev[1]):
                    tops = [bm.verts.new(v.co + Vector((0, 0, 1.1))) for v in s_]
                    bm.faces.new((s_[0], s_[1], tops[1], tops[0]))
            prev = (Lv, Rv)
    o = P.mesh_object('walk_g_arrival', bm, 'kz_walk', role='walk')
    return o, walls
