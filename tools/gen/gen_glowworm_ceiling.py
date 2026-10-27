"""Glowworm starfield (glowworm_ceiling): thousands of tiny cyan points with hanging silk threads on dark cave
rock, for the Obsidian Mirror dome (B1), the B3 cavern and the lava-tube lazy river. Ceiling-snapped patch:
the skin top is the attach plane (z = h), the lowest thread tip is z = 0.

Targets (lookbook 15 Obsidian Mirror ceiling, 12 lazy-river vault, 14 geyser plaza; no scale sheet shows
glowworms, measured off lookbook 15 against the 1.7 m floating guests):
  * patch 30 x 30 m (proxy; the row's typical Mirror dome is 24 x 24, pass w / d), 0.5 m deep.
  * point density 25-60 per m2 in the bright band of 15, falling to 3-8 per m2 at the edges / voids:
    ~20k-45k points per 900 m2 patch (row: 20k-60k sprites); points 1-2 px at 10 m -> sprite radius
    5-17 mm including the halo; most points dim, a few bright (brightness ~ u^2.2).
  * threads hang from ~30 % of the points, 0.05-0.32 m (row range 0.05-0.6; longer ones exceed the
    0.5 m proxy, see report); they read as faint vertical cyan streaks under the dense band (15, 12).
  * colour: cyan-blue, ~9000 K (row); 15 measures #3fc6e8-ish cores on #04080c rock.

Construction (one mesh; the dots and threads are runtime-instanced, not triangles):
  * skin    - (x, y) grid of cave rock facing down (-Z), relief 0.05-0.15 m (seeded lumps and a crevice in
              the 'curtain' style). Slot `rock` = cave_rock. Optional (skin=False when the host ceiling
              already carries the rock: then the patch is points + threads only).
  * points  - loose vertices 5 mm under the skin, sampled by a clustered density field. Point attributes:
              kz_sprite (1 = glow point, 0.5 = thread bead, 0 = rock), kz_size (sprite radius m),
              kz_phase (0-1 twinkle phase), kz_bright (0.25-1), kz_hz (twinkle rate 0.05-0.3 Hz).
  * threads - loose edges from a point straight down (+-4 deg) to a bead vertex; kz_thread = 1 on both.
  Colour attribute kz_sprite_col = (bright, phase, size * 20, sprite) for exporters that keep colours only.
  Preview: a Geometry Nodes modifier 'kz_glowworm_preview' instances ico spheres (radius kz_size) on the
  points and 0.6 mm tubes on the threads with the `glow` / `silk` slots, so the LOD sheet and renders show
  them. Runtime: draw kz_sprite points as additive sprites and threads as lines; DO NOT export the
  modifier (obj['kz_preview_modifier'] names it).
Materials: rock cave_rock; glow neon_tube variant cyan, emissive_level 1.4 (NEW:glowworm requested in the
row; neon cyan is the closest library emitter, #2b8bb1 at level 1); silk neon_tube cyan, emissive_level 0.12.

Parameters (build kwargs):
  w, d        patch size 4-30 m (default proxy 30 x 30)
  density     mean points per m2 over the patch 10-60 (default seeded 25-40 -> 22k-36k on 30 x 30;
              peaks ~3-5x that in the band / clusters)
  thread_len  longest thread 0.05-0.6 m (default 0.32, keeps h <= 0.5)
  thread_frac fraction of points with threads 0-0.6 (default by style)
  colour_k    colour temperature for kz_params / the runtime tint (default 9000)
  cluster     cluster noise strength 0-1 (default 0.7)
  skin        build the rock skin (default True)
  style       'galaxy' | 'scatter' | 'curtain' (default seed-cycled):
              galaxy  = a dense curving band across the dome (15) over a sparse field;
              scatter = clustered patches and voids, short threads;
              curtain = points crowding 1-2 crevices in the rock with long threads (12 vault seams).
Seeds change shape: style, band / crevice paths, cluster layout, relief, density, thread fraction.

LODs (row budget: instanced points 20k-60k, threads as lines; skin tris LOD0 <= 2000):
  LOD0 skin 30 x 30 (1800 tris), every point and thread; LOD1 skin 16 x 16, 50 % of the points (the
  brightest first), 50 % of the threads; LOD2 skin 8 x 8, 18 % of the points, 20 % of the threads;
  LOD3 skin 4 x 4, 5 % of the points, no threads. Same layout, subsets by a per-point rank.
Animation (shader, slow twinkle): obj['kz_anim'] = {type shader, attrs, hz range}. Lights: kz_lights one
downward area light, 60 W, 9000 K (proxy light) sized to the patch.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'glowworm_ceiling'
FEATURES = ['thousands of tiny cyan points', 'hanging silk threads', 'dark cave rock']
STYLES = ['galaxy', 'scatter', 'curtain']
RES = {0: dict(skin=30, keep=1.0, threads=1.0), 1: dict(skin=16, keep=0.5, threads=0.5),
       2: dict(skin=8, keep=0.18, threads=0.2), 3: dict(skin=4, keep=0.05, threads=0.0)}


def kelvin_rgb(k):
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c)
    return [round(x / m, 3) for x in c]


def noise2(r, n=5, f0=0.12, f1=0.6):
    waves = []
    for k in range(n):
        f = f0 * (f1 / f0) ** (k / max(1, n - 1))
        a = r.uniform(0, math.pi)
        waves.append((f * math.cos(a), f * math.sin(a), r.uniform(0, 2 * math.pi), 1.0 / (1 + k * 0.6)))
    tot = sum(w[3] for w in waves)
    return lambda x, y: sum(w[3] * math.sin(w[0] * x + w[1] * y + w[2]) for w in waves) / tot * 1.6


def curve_dist(pts, x, y):
    best = 1e9
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def layout(seed, W, D, H, style, density, thread_len, thread_frac, cluster):
    g = C.rng(seed, 'field')
    dens = density if density is not None else g.uniform(25, 40)
    ncl = noise2(C.rng(seed, 'clusters'), 5, 0.25, 1.4)
    nrel = noise2(C.rng(seed, 'relief'), 5, 0.3, 1.5)
    relief = g.uniform(0.05, 0.15)
    # band / crevice paths (local coords)
    gb = C.rng(seed, 'band')
    ang = gb.uniform(0, math.pi); ca, sa = math.cos(ang), math.sin(ang)
    R = max(W, D)
    paths = []
    for k in range(1 if style == 'galaxy' else gb.choice([1, 2])):
        off = gb.uniform(-0.25, 0.25) * R
        amp = gb.uniform(0.08, 0.2) * R; ph = gb.uniform(0, 6.3); fq = gb.uniform(0.6, 1.4)
        pts = []
        for i in range(25):
            t = -0.7 + 1.4 * i / 24
            u, v = t * R, off + amp * math.sin(fq * math.pi * t + ph)
            pts.append((u * ca - v * sa, u * sa + v * ca))
        paths.append(pts)
    band_w = gb.uniform(0.12, 0.2) * R if style == 'galaxy' else gb.uniform(0.6, 1.2)

    def dfield(x, y):
        """0..1 relative density"""
        edge = min(1.0, (W / 2 - abs(x)) / (0.12 * W), (D / 2 - abs(y)) / (0.12 * D))
        edge = max(0.0, edge) ** 0.7
        c = 0.5 + 0.5 * ncl(x, y)
        c = (1 - cluster) + cluster * max(0.0, min(1.0, (c - 0.25) / 0.6)) ** 1.6
        if style == 'galaxy':
            b = math.exp(-(curve_dist(paths[0], x, y) / band_w) ** 2)
            v = 0.12 + 0.88 * b
        elif style == 'curtain':
            b = max(math.exp(-(curve_dist(p, x, y) / band_w) ** 2) for p in paths)
            v = 0.1 + 0.9 * b
        else:
            v = 0.55
        return edge * c * v

    def skin_z(x, y):
        z = H - relief * (0.5 + 0.5 * nrel(x, y))
        if style == 'curtain':
            z += 0.08 * max(math.exp(-(curve_dist(p, x, y) / 0.7) ** 2) for p in paths)   # crevice pushed up
        return min(H, z)

    # points: rejection sampling of the field (deterministic, LOD independent)
    gp = C.rng(seed, 'points')
    gm = C.rng(seed, 'mean')
    mean = sum(dfield(gm.uniform(-W / 2, W / 2), gm.uniform(-D / 2, D / 2)) for _ in range(3000)) / 3000.0
    n_try = int(dens * W * D / max(0.02, mean))          # density = mean points per m2 over the patch
    tl = thread_len if thread_len is not None else 0.32
    tf = thread_frac if thread_frac is not None else {'galaxy': 0.3, 'scatter': 0.22, 'curtain': 0.5}[style]
    pts = []
    for _ in range(n_try):
        x, y = gp.uniform(-W / 2, W / 2), gp.uniform(-D / 2, D / 2)
        a = gp.random()
        if a > dfield(x, y):
            continue
        bright = 0.25 + 0.75 * gp.random() ** 2.2
        size = 0.005 + 0.012 * bright * gp.uniform(0.7, 1.0)
        thread = gp.random() < tf
        L = gp.uniform(0.05, tl) ** 1.0 if thread else 0.0
        if style == 'curtain' and thread:
            L = gp.uniform(0.4, 1.0) * tl
        pts.append(dict(x=x, y=y, z=skin_z(x, y) - 0.005, bright=bright, size=size, phase=gp.random(),
                        hz=gp.uniform(0.05, 0.3), L=L, tilt=(gp.uniform(-0.07, 0.07), gp.uniform(-0.07, 0.07)),
                        rank=gp.random() * (1.4 - bright)))
    pts.sort(key=lambda p: p['rank'])        # brightest-ish first: LOD subsets keep the head of the list
    return dict(points=pts, skin_z=skin_z, relief=relief, density=dens, thread_len=tl, thread_frac=tf, paths=paths)


def preview_modifier(o, mat_glow, mat_silk):
    """Geometry Nodes preview: ico spheres on kz_sprite points, thin tubes on kz_thread edges."""
    ng = bpy.data.node_groups.get('kz_glowworm_preview')
    if ng is None:
        ng = bpy.data.node_groups.new('kz_glowworm_preview', 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        N, Lk = ng.nodes, ng.links
        gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')

        def sel(name, domain):
            na = N.new('GeometryNodeInputNamedAttribute'); na.data_type = 'FLOAT'; na.inputs['Name'].default_value = name
            cm = N.new('FunctionNodeCompare'); cm.data_type = 'FLOAT'; cm.operation = 'GREATER_THAN'
            cm.inputs[1].default_value = 0.0
            Lk.new(na.outputs['Attribute'], cm.inputs[0])
            sp = N.new('GeometryNodeSeparateGeometry'); sp.domain = domain
            Lk.new(gi.outputs[0], sp.inputs['Geometry']); Lk.new(cm.outputs[0], sp.inputs['Selection'])
            return sp
        sp = sel('kz_sprite', 'POINT')
        m2p = N.new('GeometryNodeMeshToPoints'); m2p.mode = 'VERTICES'
        Lk.new(sp.outputs['Selection'], m2p.inputs['Mesh'])
        ico = N.new('GeometryNodeMeshIcoSphere'); ico.inputs['Radius'].default_value = 1.0; ico.inputs['Subdivisions'].default_value = 1
        nsz = N.new('GeometryNodeInputNamedAttribute'); nsz.data_type = 'FLOAT'; nsz.inputs['Name'].default_value = 'kz_size'
        iop = N.new('GeometryNodeInstanceOnPoints')
        Lk.new(m2p.outputs['Points'], iop.inputs['Points']); Lk.new(ico.outputs['Mesh'], iop.inputs['Instance'])
        Lk.new(nsz.outputs['Attribute'], iop.inputs['Scale'])
        sm = N.new('GeometryNodeSetMaterial'); sm.name = 'glow'
        Lk.new(iop.outputs['Instances'], sm.inputs['Geometry'])
        st = sel('kz_thread', 'EDGE')
        m2c = N.new('GeometryNodeMeshToCurve')
        Lk.new(st.outputs['Selection'], m2c.inputs['Mesh'])
        cc = N.new('GeometryNodeCurvePrimitiveCircle'); cc.inputs['Resolution'].default_value = 4; cc.inputs['Radius'].default_value = 0.0006
        c2m = N.new('GeometryNodeCurveToMesh')
        Lk.new(m2c.outputs['Curve'], c2m.inputs['Curve']); Lk.new(cc.outputs['Curve'], c2m.inputs['Profile Curve'])
        sm2 = N.new('GeometryNodeSetMaterial'); sm2.name = 'silk'
        Lk.new(c2m.outputs['Mesh'], sm2.inputs['Geometry'])
        jn = N.new('GeometryNodeJoinGeometry')
        for src in (gi.outputs[0], sm.outputs['Geometry'], sm2.outputs['Geometry']):
            Lk.new(src, jn.inputs['Geometry'])
        Lk.new(jn.outputs['Geometry'], go.inputs[0])
    ng.nodes['glow'].inputs['Material'].default_value = mat_glow
    ng.nodes['silk'].inputs['Material'].default_value = mat_silk
    md = o.modifiers.new('kz_glowworm_preview', 'NODES'); md.node_group = ng
    return md


def build(lod=0, seed=1, w=None, d=None, h=None, density=None, thread_len=None, thread_frac=None, colour_k=9000,
          cluster=0.7, skin=True, style=None):
    p = genlib.proxy(ASSET)
    W = float(w or p['w']); D = float(d or p['d']); H = float(h or p['h'])
    style = style or C.cycle(seed, STYLES)
    L = layout(seed, W, D, H, style, density, thread_len, thread_frac, cluster)
    R = RES[lod]
    mb = genlib.MeshBuilder(); bm = mb.bm
    m_rock = mb.slot('cave_rock')
    m_glow = mb.slot('neon_tube', variant='cyan', emissive_level=1.4)
    m_silk = mb.slot('neon_tube', variant='cyan', emissive_level=0.12)
    lay = {k: bm.verts.layers.float.new(k) for k in ('kz_sprite', 'kz_size', 'kz_phase', 'kz_bright', 'kz_hz', 'kz_thread')}
    if skin:
        n = R['skin']
        V = [[bm.verts.new((-W / 2 + W * i / n, -D / 2 + D * j / n, L['skin_z'](-W / 2 + W * i / n, -D / 2 + D * j / n)))
              for j in range(n + 1)] for i in range(n)] + [[None] * (n + 1)]
        V[n] = [bm.verts.new((W / 2, -D / 2 + D * j / n, L['skin_z'](W / 2, -D / 2 + D * j / n))) for j in range(n + 1)]
        fs = [bm.faces.new((V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j])) for i in range(n) for j in range(n)]
        mb._tag(fs, m_rock)        # winding (i,j)->(i,j+1)->(i+1,j+1): normal -Z, facing the guests below
    pts = L['points']
    npt = int(len(pts) * R['keep'])
    n_thr = 0
    for k, q in enumerate(pts[:npt]):
        v = bm.verts.new((q['x'], q['y'], q['z']))
        v[lay['kz_sprite']] = 1.0; v[lay['kz_size']] = q['size']; v[lay['kz_phase']] = q['phase']
        v[lay['kz_bright']] = q['bright']; v[lay['kz_hz']] = q['hz']
        if q['L'] > 0 and (k / max(1, npt)) < R['threads'] * 1.0 + 1e-9 and R['threads'] > 0:
            if R['threads'] < 1.0 and (hash((seed, k)) % 1000) / 1000.0 > R['threads']:
                continue
            tx, ty = q['tilt']
            b = bm.verts.new((q['x'] + tx * q['L'], q['y'] + ty * q['L'], q['z'] - q['L']))
            b[lay['kz_sprite']] = 0.5; b[lay['kz_size']] = q['size'] * 0.4; b[lay['kz_phase']] = q['phase']
            b[lay['kz_bright']] = q['bright'] * 0.35; b[lay['kz_hz']] = q['hz']
            v[lay['kz_thread']] = 1.0; b[lay['kz_thread']] = 1.0
            bm.edges.new((v, b))
            n_thr += 1
    dx, dy, dz = C.centre_base(mb)
    me = bpy.data.meshes.new(ASSET); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(ASSET, me); bpy.context.scene.collection.objects.link(o)
    import matlib
    for i, (mid, params) in enumerate(mb.slots):
        matlib.assign(o, mid, slot=i, **params)
    col = me.color_attributes.new('kz_sprite_col', 'FLOAT_COLOR', 'POINT')
    A = {k: me.attributes[k] for k in ('kz_sprite', 'kz_size', 'kz_phase', 'kz_bright')}
    for i in range(len(me.vertices)):
        col.data[i].color = (A['kz_bright'].data[i].value, A['kz_phase'].data[i].value,
                             A['kz_size'].data[i].value * 20, A['kz_sprite'].data[i].value)
    C.set_json_props(o, kz_snap='ceiling', kz_attach_z=round(H + dz, 3),
                     kz_anim=dict(type='shader', what='slow twinkle of instanced glow sprites; threads static',
                                  sprite_attr='kz_sprite', size_attr='kz_size', phase_attr='kz_phase', bright_attr='kz_bright',
                                  hz_attr='kz_hz', thread_attr='kz_thread', hz_range=[0.05, 0.3], amp=0.45,
                                  color_attr='kz_sprite_col', sprite_slot=m_glow, thread_slot=m_silk),
                     kz_lights=[C.light_entry((0, 0, H * 0.5 + dz), color_k=colour_k, watts=60 * W * D / 900.0, kind='area',
                                              size=[round(W, 2), round(D, 2)], normal=[0, 0, -1], color=kelvin_rgb(colour_k))],
                     kz_preview_modifier='kz_glowworm_preview (Blender preview only; do not export)',
                     kz_params=dict(style=style, w=W, d=D, points=npt, points_lod0=len(pts), threads=n_thr,
                                    density=round(L['density'], 1), thread_len=L['thread_len'], thread_frac=L['thread_frac'],
                                    relief=round(L['relief'], 3), colour_k=colour_k, skin=skin))
    genlib.finish(o, smooth_angle=40)
    preview_modifier(o, o.material_slots[m_glow].material, o.material_slots[m_silk].material)
    return o
