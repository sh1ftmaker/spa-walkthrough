"""Obsidian monolith (b1_glacier hero shard mass; slender spires standing in the b1_mirror pool).

Identifying features kept at every LOD: a tall glossy-black mass of volcanic glass made of a few broad, slightly
curved conchoidal sheets with razor ridges, a raked top with a stepped secondary break (never a crystal point
or a flat top), a visible lean. LOD0/1 add shell-shaped scallops with ripple rings on the two broadest faces and
a rubble skirt the body rises out of.

Styles (seed picks one unless `style` is given; seeds 1/2/3 show cluster/spire/slab):
  cluster  main sheet-mass + stepped shoulder sheet + 1-2 leaning secondary blades (b1_glacier hero)
  spire    slender, tall, single raked break, strongly offset apex (b1_mirror pool)
  slab     truly flat broad blade, w/d 2.0-2.5, raked top with a stepped shoulder
Construction:
  * Each sheet-mass is a convex polytope: a tall box clipped by 5-8 broad planes per broad side plus a few
    edge planes and ONE dominant rake plane (25-40 deg off vertical) up to an apex offset 20-35 % of w.
    No top pyramid. The stepped break is a second, lower "shoulder" polytope on the far side whose rake is
    shallower, so the silhouette steps down rather than closing into a point.
  * Every face is poked and its centre pushed in by ~8 % of its width: slightly curved conchoidal sheets.
    The two broadest faces (LOD0/1) are grid-subdivided and carry a broad dish plus 1-3 scallops
    (0.3-0.8 m across, 0.03-0.06 m deep, 2-3 ripple rings, crisp lip). LOD0 has a 1.2 cm ridge micro-bevel.
  * Base: the mass is sunk 0.15-0.3 m below grade, its lowest 0.3 m flared out ~10 %, and it rises out of
    3-6 chunky shards / blocks of 0.2-0.5 m (LOD0: 5, LOD1: 3).
  * Lean: shear (m per m); every LOD is centred on the full-detail reference shape (no LOD pop).
Parameters (proxy 1.4 x 0.8 x 3.0 m, 3d/assets.json; never exceeded by > 5 %):
  h 1.5-3.5 (seeded by style), w 0.8-1.6, d (seeded from w/d), facets (broad planes per side 5-8), lean, style.
Animation: none.  Lighting: lightmap (UV1) + probe reflections.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import genlib

ASSET = 'obsidian_monolith'
FEATURES = ['tall glossy black mass of broad curved conchoidal sheets', 'raked top with stepped break',
            'shell scallops with ripple rings (LOD0/1)', 'lean', 'rubble skirt (LOD0/1)']
STYLES = ('cluster', 'spire', 'slab')
RES = {0: dict(sub_b=9, curve=1.0, scallops=True, frags=5, bevel=0.012),
       1: dict(sub_b=3, curve=1.0, scallops=True, frags=3, bevel=0.0),
       2: dict(sub_b=0, curve=0.8, scallops=False, frags=0, bevel=0.0),
       3: dict(sub_b=-1, curve=0.0, scallops=False, frags=0, bevel=0.0)}


# ------------------------------------------------------------------ polytope
def polytope(bm, box_min, box_max, planes):
    """box clipped by half-spaces n.p <= off"""
    r = bmesh.ops.create_cube(bm, size=1.0)
    size = Vector(box_max) - Vector(box_min)
    bmesh.ops.scale(bm, vec=size, verts=r['verts'])
    bmesh.ops.translate(bm, vec=(Vector(box_min) + Vector(box_max)) / 2, verts=r['verts'])
    for n, off in planes:
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=n * off, plane_no=n, clear_outer=True)
        cut = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        if cut:
            bmesh.ops.holes_fill(bm, edges=cut, sides=0)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-4)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=list(bm.verts), edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))


def support(pts, n):
    return max(n.dot(p) for p in pts)


def sheet_planes(r, w, d, h, n_broad, style, side, rake_deg, apex_off):
    """broad planes per side + edge planes + one rake plane through an offset apex"""
    a0, b0 = w / 2, d / 2
    apex = Vector((side * apex_off * w, r.uniform(-0.12, 0.12) * d, h))
    narrow = {'spire': 0.5, 'slab': 0.92, 'cluster': 0.75}[style]
    mid = r.uniform(0.4, 0.55)
    pts = [Vector((sx * a0 * r.uniform(0.85, 1.0), sy * b0 * r.uniform(0.85, 1.0), 0)) for sx in (-1, 1) for sy in (-1, 1)]
    shift = side * a0 * r.uniform(0.05, 0.15)
    pts += [Vector((shift + sx * a0 * narrow * r.uniform(0.85, 1.0), sy * b0 * r.uniform(0.75, 0.92), h * mid))
            for sx in (-1, 1) for sy in (-1, 1)]
    pts += [apex, Vector((side * a0 * 0.4, apex.y * 0.5, h * 0.85))]
    planes = []
    rake = math.radians(rake_deg)
    n = Vector((-side * math.cos(rake), r.uniform(-0.2, 0.2), math.sin(rake))).normalized()
    planes.append((n, support(pts, n), 'rake'))
    # broad sheets: per broad side, n_broad planes fanned in azimuth and tilt, small insets (fewer, bigger faces)
    flat = style == 'slab'
    for sy in (-1, 1):
        for k in range(n_broad):
            u = (k + 0.5) / n_broad - 0.5
            ph = sy * math.pi / 2 + u * (0.9 if flat else 1.6) + r.uniform(-0.12, 0.12)
            el = r.uniform(-0.3, 0.45) * (0.5 if flat else 1.0)
            n = Vector((math.cos(ph) * math.cos(el), math.sin(ph) * math.cos(el), math.sin(el))).normalized()
            planes.append((n, support(pts, n) * r.uniform(0.9, 0.98), 'side'))
    for sx in (-1, 1):            # narrow ends
        for k in range(2):
            ph = (0 if sx > 0 else math.pi) + r.uniform(-0.35, 0.35)
            el = r.uniform(-0.2, 0.35)
            n = Vector((math.cos(ph) * math.cos(el), math.sin(ph) * math.cos(el), math.sin(el))).normalized()
            planes.append((n, support(pts, n) * r.uniform(0.92, 1.0), 'end'))
    return planes


# ------------------------------------------------------------------ conchoidal surface
def _seg_dist(p, a, b):
    ab = b - a
    L = ab.length_squared
    if L < 1e-12:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / L))
    return (p - (a + ab * t)).length


def conchoidal(bm, r, R, k_scale=1.0):
    """poke every face (curved sheet: centre pushed in), grid-subdivide the two broadest faces and dish them with
    a broad bowl + 1-3 rippled scallops. Returns the ridge edges (for the micro-bevel)."""
    fl = bm.faces.layers.int.new('kz_facet')
    info = {}
    faces = list(bm.faces)
    for i, f in enumerate(faces):
        f[fl] = i
        vs = [v.co.copy() for v in f.verts]
        info[i] = dict(n=f.normal.copy(), c=f.calc_center_median(), w=math.sqrt(max(f.calc_area(), 1e-6)),
                       edges=[(vs[j], vs[(j + 1) % len(vs)]) for j in range(len(vs))], area=f.calc_area())
    if R['sub_b'] < 0:
        bm.faces.layers.int.remove(fl)
        return []
    broad = sorted([i for i in info if abs(info[i]['n'].z) < 0.6], key=lambda i: -info[i]['area'])[:2]
    if not R['scallops'] or R['sub_b'] == 0:
        broad = []
    res = bmesh.ops.poke(bm, faces=faces)
    centres = set(res['verts'])
    if broad:
        bset = set(broad)
        edges = [e for e in bm.edges if any(f[fl] in bset for f in e.link_faces)]
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=R['sub_b'], use_grid_fill=True)
    # per-facet inradius proxy for the vertices that sit inside one facet
    owner, inr = {}, {}
    for v in bm.verts:
        ids = {f[fl] for f in v.link_faces}
        if len(ids) != 1:
            continue
        i = ids.pop()
        e = min(_seg_dist(v.co, a, b) for a, b in info[i]['edges'])
        owner[v] = (i, e)
        inr[i] = max(inr.get(i, 0.0), e)
    # scallops on the broad faces
    for i in broad:
        F = info[i]
        sc = []
        cand = [v for v, (j, e) in owner.items() if j == i and e > 0.25]
        for k in range(r.randint(1, 3)):
            if not cand:
                break
            c = r.choice(cand).co.copy()
            rad = r.uniform(0.15, 0.4) * k_scale
            sc.append(dict(c=c, rad=rad, depth=r.uniform(0.03, 0.06) * k_scale, rings=r.choice((2, 3)),
                           ph=r.uniform(0, 0.25)))
        F['scallops'] = sc
    for v, (i, e) in owner.items():
        F = info[i]
        if inr.get(i, 0) <= 0 or e < 1e-4:
            continue
        x = min(1.0, e / inr[i])
        # slightly curved sheet: ~8 % of facet width at the centre, zero at the ridges
        d = R['curve'] * 0.08 * F['w'] * k_scale * (1 - (1 - x) ** 2) * (1.0 if i in broad or v in centres else 1.0)
        for s in F.get('scallops', ()):
            rr = (v.co - s['c']).length / s['rad']
            if rr < 1.0:
                ripple = 0.3 * math.cos(2 * math.pi * (rr * s['rings'] + s['ph'])) * (1 - rr)
                d += s['depth'] * ((1 - rr * rr) + ripple)        # crisp lip at rr = 1 (slope break)
        v.co = v.co - F['n'] * d
    ridges = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0][fl] != e.link_faces[1][fl]]
    bm.faces.layers.int.remove(fl)
    return ridges


# ------------------------------------------------------------------ one sheet-mass
def sheet_mass(r, w, d, h, lean, lod, R, style, side, rake_deg, apex_off, n_broad, budget, k_scale=1.0,
               lod3_keep=(2, 1)):
    planes = sheet_planes(r, w, d, h, n_broad, style, side, rake_deg, apex_off)
    box = ((-w / 2, -d / 2, -0.4), (w / 2, d / 2, h * 1.6))
    ref_bm = bmesh.new()
    polytope(ref_bm, *box, [(n, o) for n, o, _ in planes])
    for v in ref_bm.verts:
        v.co.x += lean * v.co.z
    xs = [v.co.x for v in ref_bm.verts]; ys = [v.co.y for v in ref_bm.verts]; zs = [v.co.z for v in ref_bm.verts]
    ref = (min(xs), max(xs), min(ys), max(ys), max(zs))
    ref_bm.free()
    use = planes
    if lod == 3:
        rake = [p for p in planes if p[2] == 'rake']
        side_p = [p for p in planes if p[2] == 'side']
        end_p = [p for p in planes if p[2] == 'end']
        keep = []
        for sy in (-1, 1):
            keep += sorted([p for p in side_p if p[0].y * sy > 0], key=lambda p: -abs(p[0].y))[:lod3_keep[0]]
        keep += end_p[:lod3_keep[1]] + end_p[2:2 + lod3_keep[1]]
        use = rake + keep
    RR = dict(R)
    state = r.getstate()
    while True:
        r.setstate(state)
        bm = bmesh.new()
        polytope(bm, *box, [(n, o) for n, o, _ in use])
        for v in bm.verts:
            v.co.x += lean * v.co.z
        zt = max(v.co.z for v in bm.verts)
        if zt > ref[4]:
            for v in bm.verts:
                v.co.z *= ref[4] / zt
        ridges = conchoidal(bm, r, RR, k_scale)
        if RR['bevel'] > 0 and ridges:
            bmesh.ops.bevel(bm, geom=ridges, offset=RR['bevel'], segments=1, affect='EDGES', profile=0.5,
                            clamp_overlap=True)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        if len(bm.faces) <= budget or RR['sub_b'] < 0:
            return bm, ref
        bm.free()
        if RR['bevel'] > 0 and RR['sub_b'] <= 4:
            RR['bevel'] = 0.0
        else:
            RR['sub_b'] -= 1


def _bm_bbox(bm):
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def _chunk(r, size, lod):
    """chunky rubble block / shard: small polytope with a few random planes"""
    w, d, h = size
    planes = []
    for k in range(7):
        ph = r.uniform(0, 2 * math.pi); el = r.uniform(-0.2, 1.0)
        n = Vector((math.cos(ph) * math.cos(el), math.sin(ph) * math.cos(el), math.sin(el))).normalized()
        sup = abs(n.x) * w / 2 + abs(n.y) * d / 2 + max(0.0, n.z) * h
        planes.append((n, sup * r.uniform(0.7, 0.92)))
    bm = bmesh.new()
    polytope(bm, (-w / 2, -d / 2, 0), (w / 2, d / 2, h), planes)
    if lod == 0:
        bmesh.ops.poke(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    return bm


# ------------------------------------------------------------------ build
def build(lod, seed, w=None, h=None, d=None, facets=None, lean=None, style=None):
    P = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    R = RES[min(3, max(0, lod))]
    style = style or STYLES[(seed - 1) % 3]
    W = min(w or P['w'], P['w'])
    H = min(h or {'cluster': r.uniform(2.6, 3.0), 'spire': r.uniform(2.7, 3.0), 'slab': r.uniform(2.0, 2.6)}[style],
            P['h'])
    ratio = {'slab': r.uniform(2.0, 2.5), 'spire': r.uniform(1.3, 1.6), 'cluster': r.uniform(1.6, 2.0)}[style]
    D = min(d or W / ratio, P['d'])
    n_broad = max(5, min(8, int(facets or r.randint(5, 8))))
    lean = lean if lean is not None else r.choice((-1, 1)) * r.uniform(0.06, 0.12)
    sink = r.uniform(0.15, 0.3)
    budget = (genlib.budget_of(ASSET) or [2000, 800, 240, 40])[min(lod, 3)]

    mb = genlib.MeshBuilder()
    glass = mb.slot('obsidian', wetness=round(r.uniform(0.2, 0.4), 2))   # library obsidian is jet black now

    side = r.choice((-1, 1))                       # apex side
    w_main = {'spire': W * r.uniform(0.42, 0.5), 'cluster': W * r.uniform(0.6, 0.68), 'slab': W * 0.82}[style]
    w_main = max(0.35, w_main - abs(lean) * H * 0.8 * (w_main / W))
    n_bl = r.choice((1, 2)) if style == 'cluster' else 0
    has_sh = style != 'spire'
    n_fr = R['frags'] if style != 'spire' else max(0, R['frags'] - 2)
    lod3 = lod == 3
    # LOD3 must stay <= 40 tris: main mass only (+ shoulder for slab/cluster at the coarsest cut)
    if lod3:
        n_bl = 0
    shares = dict(main=0.55 if (has_sh or n_bl) else 0.8, sh=0.18, bl=0.12 / max(1, n_bl), fr=0.15 / max(1, n_fr))
    if lod3:
        shares = dict(main=26 / 40 if has_sh else 1.0, sh=14 / 40, bl=0, fr=0)
    full_h = H + sink
    body, ref = sheet_mass(genlib.rng(seed, 'body'), w_main, D * 0.96, full_h, lean, lod, R, style, side,
                           r.uniform(50, 62) if style == 'slab' else r.uniform(25, 40),
                           {'spire': r.uniform(0.25, 0.35), 'slab': r.uniform(0.35, 0.45)}.get(style, r.uniform(0.2, 0.3)),
                           n_broad, budget * shares['main'], lod3_keep=(1, 1) if (lod3 and has_sh) else (2, 1))
    parts = [body]
    sh = None
    if has_sh:
        rs = genlib.rng(seed, 'shoulder')
        sh_h = full_h * rs.uniform(0.66, 0.8)
        sh_w = w_main * rs.uniform(0.55, 0.7)
        sh, _ = sheet_mass(rs, sh_w, D * rs.uniform(0.75, 0.9), sh_h, lean, lod, R, style, side,
                           rs.uniform(62, 72) if style == 'slab' else rs.uniform(48, 62), 0.3, max(3, n_broad - 2), budget * shares['sh'], k_scale=0.8,
                           lod3_keep=(1, 0))
        # sit on the far side of the main mass, overlapping it: the silhouette steps down from the apex
        for v in sh.verts:
            v.co.x += -side * w_main * 0.33
        parts.append(sh)
    # centre on the reference footprint (identical for every LOD), sink, flare the foot
    cx = (ref[0] + ref[1]) / 2 + (-side * w_main * 0.12 if has_sh else 0.0)
    bl_side = -side
    if style == 'cluster':
        cx += bl_side * W * 0.05
    cy = (ref[2] + ref[3]) / 2
    kz = full_h / ref[4]
    for bm in parts:
        for v in bm.verts:
            v.co.x -= cx; v.co.y -= cy
            v.co.z = v.co.z * kz - sink
            if v.co.z < 0.3:                       # flare the lowest 0.3 m out by ~10 %
                f = 1 + 0.1 * (1 - max(0.0, v.co.z) / 0.3)
                v.co.x = (v.co.x - (-side * w_main * 0.1 if has_sh else 0.0)) * f + (-side * w_main * 0.1 if has_sh else 0.0)
                v.co.y *= f
    foot = [v.co for bm in parts for v in bm.verts if v.co.z < 0.35]
    fx0, fx1 = min(p.x for p in foot), max(p.x for p in foot)
    fy0, fy1 = min(p.y for p in foot), max(p.y for p in foot)

    for k in range(n_bl):
        rb = genlib.rng(seed, f'blade{k}')
        bh = H * (rb.uniform(0.45, 0.6) if k == 0 else rb.uniform(0.3, 0.42)) + 0.1
        bw, bd = W * rb.uniform(0.26, 0.34), D * rb.uniform(0.6, 0.85)
        bm, _ = sheet_mass(rb, bw, bd, bh, 0.0, lod, R, 'spire', -bl_side, rb.uniform(25, 40), 0.25,
                           5, budget * shares['bl'], k_scale=0.6)
        tilt = bl_side * rb.uniform(0.15, 0.35)                  # leans in against the main mass
        M = Matrix.Rotation(tilt, 4, 'Y') @ Matrix.Rotation(rb.uniform(-0.5, 0.5), 4, 'Z')
        bmesh.ops.transform(bm, matrix=M, verts=list(bm.verts))
        x0, x1, y0, y1, z0, z1 = _bm_bbox(bm)
        ox = bl_side * (W / 2 * 0.985) - (x1 if bl_side > 0 else x0)
        oy = (-1 if k == 0 else 1) * rb.uniform(0.0, 0.2) * D - (y0 + y1) / 2
        for v in bm.verts:
            v.co += Vector((ox, oy, -z0 - 0.12))
        parts.append(bm)

    # ---- rubble skirt: chunky shards / blocks 0.2-0.5 m, two leaning on the base
    rf = genlib.rng(seed, 'frags')
    for k in range(n_fr):
        lean_on = k < 2
        sz = (rf.uniform(0.25, 0.5), rf.uniform(0.18, 0.32), rf.uniform(0.35, 0.5) if lean_on else rf.uniform(0.2, 0.34))
        bm = _chunk(genlib.rng(seed, f'frag{k}'), sz, lod)
        sx = rf.choice((-1, 1)); sy = -1 if k % 2 == 0 else 1
        tilt = (rf.uniform(0.2, 0.45) if lean_on else rf.uniform(0.0, 0.5)) * -sx
        M = Matrix.Rotation(rf.uniform(-0.8, 0.8), 4, 'Z') @ Matrix.Rotation(tilt, 4, 'Y')
        bmesh.ops.transform(bm, matrix=M, verts=list(bm.verts))
        x0, x1, y0, y1, z0, z1 = _bm_bbox(bm)
        if lean_on:
            ox = (fx0 + fx1) / 2 + sx * rf.uniform(0.0, 0.3) * (fx1 - fx0) - (x0 + x1) / 2
            oy = (fy1 if sy > 0 else fy0) - sy * 0.04 - (y0 + y1) / 2 + sy * (y1 - y0) * 0.35
        else:
            ox = (fx1 if sx > 0 else fx0) + sx * rf.uniform(-0.05, 0.08) - (x0 + x1) / 2
            oy = sy * rf.uniform(0.0, 0.4) * D - (y0 + y1) / 2
        ox = max(-W / 2 * 0.985 - x0, min(W / 2 * 0.985 - x1, ox))
        oy = max(-P['d'] / 2 * 0.985 - y0, min(P['d'] / 2 * 0.985 - y1, oy))
        for v in bm.verts:
            v.co += Vector((ox, oy, -z0 - 0.06 * sz[2]))
        parts.append(bm)

    for bm in parts:
        for v in bm.verts:
            v.co.z = max(0.0, v.co.z)               # sunk parts are cut at the floor line
        for f in bm.faces:
            f.material_index = glass
        me = bpy.data.meshes.new('kz_tmp'); bm.to_mesh(me); bm.free()
        mb.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.remove_doubles(mb.bm, verts=list(mb.bm.verts), dist=1e-4)
    bmesh.ops.dissolve_degenerate(mb.bm, edges=list(mb.bm.edges), dist=1e-4)
    # faces flattened onto the floor by the sink are invisible: drop them (saves budget, esp. LOD3)
    flat = [f for f in mb.bm.faces if all(v.co.z < 1e-5 for v in f.verts)]
    bmesh.ops.delete(mb.bm, geom=flat, context='FACES')
    x0, x1, y0, y1, z0, z1 = _bm_bbox(mb.bm)
    kx = min(1.0, W / 2 * 0.995 / max(abs(x0), abs(x1))); ky = min(1.0, P['d'] / 2 * 0.995 / max(abs(y0), abs(y1)))
    for v in mb.bm.verts:                     # scale about the pivot only (no re-centring: no LOD pop)
        v.co.x *= kx; v.co.y *= ky
    o = mb.to_object(ASSET)
    o['kz_params'] = repr(dict(style=style, w=round(W, 3), d=round(D, 3), h=round(H, 3), broad_planes=n_broad,
                               lean=round(lean, 3), sink=round(sink, 3)))
    o['kz_style'] = style
    return genlib.finish(o, smooth_angle=26)
