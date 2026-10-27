"""Geometry helpers for gen_bridge_arched (also imported by gen_stair via kzgeo_stair).

All helpers add faces to a genlib.MeshBuilder's bmesh and tag them with a material slot index.
Frames: `frame(origin, fwd, up)` gives a 4x4 matrix whose local +Y is `fwd`, +Z is (re-orthogonalised) `up`
and +X = fwd x up, so profiles are written as (x = sideways, z = up) and swept along +Y.
"""
import math
import bmesh
from mathutils import Matrix, Vector, noise

Z = Vector((0, 0, 1))


def frame(origin, fwd, up=Z):
    f = Vector(fwd).normalized()
    x = f.cross(Vector(up))
    if x.length < 1e-6:
        x = f.cross(Vector((1, 0, 0)))
    x.normalize()
    u = x.cross(f).normalized()
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = x[i], f[i], u[i], origin[i]
    return M


def _faces_of(vs):
    return list({f for v in vs for f in v.link_faces})


def cbox(mb, M, size, mi, bevel=0.0, segs=1, jitter=0.0, r=None, drop_bottom=False):
    """Box of `size` (local x,y,z) centred on local origin of matrix M; optional bevel + vertex jitter."""
    bm = mb.bm
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res['verts']
    bmesh.ops.scale(bm, vec=size, verts=vs)
    if jitter and r is not None:
        for v in vs:
            v.co += Vector((r.uniform(-jitter, jitter), r.uniform(-jitter, jitter), r.uniform(-jitter, jitter) * 0.6))
    faces = _faces_of(vs)
    if drop_bottom:
        bot = [f for f in faces if f.normal.z < -0.9]
        bmesh.ops.delete(bm, geom=bot, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    mb._tag(faces, mi)                       # tag first: bevel copies the material to the rebuilt faces
    if bevel > 0:
        edges = list({e for f in faces for e in f.edges})
        res = bmesh.ops.bevel(bm, geom=edges + list(vs), offset=bevel, segments=segs, affect='EDGES', profile=0.5,
                              clamp_overlap=True)
        faces = [f for f in set(faces) | set(res['faces']) if f.is_valid]
        vs2 = [v for v in vs if v.is_valid] + list(res['verts'])
        faces = list(set(faces) | set(_faces_of(vs2)))
    allv = list({v for f in faces for v in f.verts})
    bmesh.ops.transform(bm, matrix=M, verts=allv)
    mb._tag(faces, mi)
    return faces


def prism_x(mb, poly_yz, x0, x1, mi, M=None, caps=(True, True)):
    """Extrude a 2D polygon given in (y, z) between x0 and x1 (closed solid unless caps are dropped)."""
    bm = mb.bm
    a = sum(poly_yz[i][0] * poly_yz[(i + 1) % len(poly_yz)][1] - poly_yz[(i + 1) % len(poly_yz)][0] * poly_yz[i][1]
            for i in range(len(poly_yz)))
    if a < 0:
        poly_yz = poly_yz[::-1]
    L = [bm.verts.new((x0, y, z)) for y, z in poly_yz]
    R = [bm.verts.new((x1, y, z)) for y, z in poly_yz]
    faces = ([bm.faces.new(L[::-1])] if caps[0] else []) + ([bm.faces.new(R)] if caps[1] else [])
    n = len(poly_yz)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((L[i], L[j], R[j], R[i])))
    if M is not None:
        bmesh.ops.transform(bm, matrix=M, verts=L + R)
    mb._tag(faces, mi)
    return faces


def sweep(mb, pts, prof, mi, up=Z, caps=True, closed_prof=True, ups=None, profs=None):
    """Sweep a 2D profile [(x, z)] along a polyline `pts` (list of Vector). Frame per point uses the
    averaged tangent; x = tangent x up. Returns faces."""
    bm = mb.bm
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        u = ups[i] if ups else up
        M = frame(p, t, u)
        # keep the profile width constant on mitred joints
        sc = 1.0
        if 0 < i < n - 1:
            a = (pts[i + 1] - pts[i]).normalized().angle((pts[i] - pts[i - 1]).normalized(), 0.0)
            sc = 1.0 / max(0.5, math.cos(a / 2))
        ring = []
        for x, z in (profs[i] if profs else prof):
            ring.append(bm.verts.new(M @ Vector((x, 0, z * sc))))
        rings.append(ring)
    faces = []
    m = len(profs[0] if profs else prof)
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(m if closed_prof else m - 1):
            k2 = (k + 1) % m
            faces.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    if caps and closed_prof:
        faces.append(bm.faces.new(rings[0][::-1]))
        faces.append(bm.faces.new(rings[-1]))
    mb._tag(faces, mi)
    return faces


def lathe(mb, base, prof, mi, segs=8, rot=0.0):
    """Surface of revolution about local Z at `base`; prof = [(r, z)] bottom to top. r == 0 -> pole."""
    bm = mb.bm
    base = Vector(base)
    rings = []
    for r_, z in prof:
        if r_ <= 1e-6:
            rings.append([bm.verts.new(base + Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(base + Vector((r_ * math.cos(rot + 2 * math.pi * k / segs),
                                                      r_ * math.sin(rot + 2 * math.pi * k / segs), z)))
                          for k in range(segs)])
    faces = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for k in range(segs):
                faces.append(bm.faces.new((A[0], B[k], B[(k + 1) % segs])))
        elif len(B) == 1:
            for k in range(segs):
                faces.append(bm.faces.new((A[k], A[(k + 1) % segs], B[0])))
        else:
            for k in range(segs):
                faces.append(bm.faces.new((A[k], A[(k + 1) % segs], B[(k + 1) % segs], B[k])))
    if len(rings[0]) > 1:
        faces.append(bm.faces.new(rings[0][::-1]))
    if len(rings[-1]) > 1:
        faces.append(bm.faces.new(rings[-1]))
    mb._tag(faces, mi)
    return faces


def rock(mb, center, size, mi, r, subdiv=1, rough=0.18, facets=3, zmin=None, zmax=None, freq=1.7):
    """Faceted basalt lump: icosphere -> anisotropic scale -> noise displacement -> planar facet cuts
    (vertices beyond a random plane are projected onto it, giving cut faces) -> optional flat bottom / top."""
    bm = mb.bm
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    vs = res['verts']
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    sx, sy, sz = size
    for v in vs:
        d = noise.noise(v.co * freq + off)
        v.co = v.co * (1.0 + rough * d)
    planes = []
    for _ in range(facets):
        n = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.2, 1.0))).normalized()
        planes.append((n, r.uniform(0.55, 0.85)))
    for v in vs:
        for n, dist in planes:
            k = v.co.dot(n) - dist
            if k > 0:
                v.co -= n * k
    for v in vs:
        v.co = Vector((v.co.x * sx / 2, v.co.y * sy / 2, v.co.z * sz / 2)) + Vector(center)
        if zmin is not None and v.co.z < zmin:
            v.co.z = zmin
        if zmax is not None and v.co.z > zmax:
            v.co.z = zmax
    faces = _faces_of(vs)
    mb._tag(faces, mi)
    return faces, vs


def clamp_verts(vs, xlim=None, ylim=None):
    for v in vs:
        if xlim:
            v.co.x = min(max(v.co.x, xlim[0]), xlim[1])
        if ylim:
            v.co.y = min(max(v.co.y, ylim[0]), ylim[1])


# ------------------------------------------------------------------ shared kit parts
def giboshi(mb, base, mi, lod, scale=1.0, style='giboshi', rscale=1.0, segs=None):
    """Post finial: lathe 'onion' (giboshi) or stepped pyramid cap; base = top of the post."""
    s = scale
    if style == 'giboshi':
        q = s * rscale
        prof = [(0.064 * q, 0), (0.064 * q, 0.022 * s), (0.036 * q, 0.045 * s), (0.064 * q, 0.088 * s),
                (0.03 * q, 0.138 * s), (0, 0.18 * s)]
        if lod >= 1:
            prof = [prof[0], prof[2], prof[3], prof[5]]
        return lathe(mb, base, prof, mi, segs=segs or (8 if lod == 0 else 6), rot=math.pi / 8)
    # 'hoshu' style: flat iron cap + ball
    prof = [(0.07 * s, 0), (0.07 * s, 0.02 * s), (0.03 * s, 0.035 * s), (0.045 * s, 0.07 * s), (0.03 * s, 0.1 * s), (0, 0.11 * s)]
    if lod >= 1:
        prof = [prof[0], prof[1], prof[3], prof[5]]
    return lathe(mb, base, prof, mi, segs=segs or (8 if lod == 0 else 6), rot=math.pi / 8)


def post_oct(mb, x, y, z0, z1, wid, mi, chamfer=0.25):
    """Square post with chamfered vertical edges (octagonal prism)."""
    c = wid / 2
    k = c * (1 - chamfer)
    poly = [(k, c), (c, k), (c, -k), (k, -c), (-k, -c), (-c, -k), (-c, k), (-k, c)]
    poly = [(x + px, y + py) for px, py in poly]
    return mb.poly_prism(poly, z0, z1, mi)


def lantern_box(mb, base, mats, lod, r, size=0.26, height=0.34, roof='pyramid', corner_bars=True):
    """Iron-framed square lantern on a post top; returns the light centre (Vector).
    mats = dict(iron=, paper=)"""
    bx, by, bz = base
    iron, paper = mats['iron'], mats['paper']
    s = size
    plate = 0.03
    if lod >= 2:
        mb.box((bx, by, bz + height * 0.5), (s * 0.86, s * 0.86, height), paper)
        mb.cylinder((bx, by, bz + height + 0.06), radius=s * 0.78, radius2=0.01, depth=0.12, mi=iron, segs=4,
                    rot=(0, 0, math.pi / 4), cap=lod == 2)
        return Vector((bx, by, bz + height * 0.5))
    # base plate, paper body, corner bars, top plate, roof, finial
    mb.box((bx, by, bz + plate / 2), (s, s, plate), iron)
    mb.box((bx, by, bz + plate + (height - 2 * plate) / 2), (s * 0.84, s * 0.84, height - 2 * plate), paper)
    cb = 0.022
    for sx in ((-1, 1) if (lod == 0 and corner_bars) else ()):
        for sy in (-1, 1):
            mb.box((bx + sx * (s / 2 - cb / 2 - 0.006), by + sy * (s / 2 - cb / 2 - 0.006), bz + height / 2),
                   (cb, cb, height), iron)
    if lod == -1:
        # horizontal mid muntins on each face (kumiko bar)
        for ang in range(4):
            a = ang * math.pi / 2
            cx, cy = math.sin(a) * (s * 0.42 + 0.003), math.cos(a) * (s * 0.42 + 0.003)
            sz = (s * 0.84, 0.008, 0.012) if ang % 2 == 0 else (0.008, s * 0.84, 0.012)
            mb.box((bx + cx, by + cy, bz + height * 0.55), sz, iron)
    mb.box((bx, by, bz + height - plate / 2), (s * 1.04, s * 1.04, plate), iron)
    rh = 0.11 if roof == 'pyramid' else 0.08
    segs = 4 if roof == 'pyramid' else 8
    mb.cylinder((bx, by, bz + height + rh / 2), radius=s * (0.86 if segs == 4 else 0.66), radius2=0.02, depth=rh,
                mi=iron, segs=segs, rot=(0, 0, math.pi / 4 if segs == 4 else math.pi / 8))
    lathe(mb, (bx, by, bz + height + rh - 0.005), [(0.022, 0), (0.03, 0.025), (0.012, 0.05), (0, 0.065)], iron,
          segs=6 if lod == 0 else 4)
    return Vector((bx, by, bz + plate + (height - 2 * plate) / 2))


def uv_grain(obj, slots):
    """Re-project UV0 (still metres) on the faces of the given material slots so that v runs along each
    part's long axis: wood grain follows planks, rails, girders and posts instead of the box projection.
    Parts are found as connected islands; the long axis is the island's principal direction (PCA)."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap')
    seen = set()
    slots = set(slots)
    for f0 in bm.faces:
        if f0.index in seen or f0.material_index not in slots:
            continue
        isl, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for v in f.verts:
                for g in v.link_faces:
                    if g.index not in seen and g.material_index in slots:
                        seen.add(g.index); stack.append(g)
        vs = list({v for f in isl for v in f.verts})
        c = sum((v.co for v in vs), Vector()) / len(vs)
        # principal axis by power iteration on the covariance
        C = [[0.0] * 3 for _ in range(3)]
        for v in vs:
            d = v.co - c
            for i in range(3):
                for j in range(3):
                    C[i][j] += d[i] * d[j]
        a = Vector((1, 0.3, 0.1))
        for _ in range(30):
            a = Vector([sum(C[i][j] * a[j] for j in range(3)) for i in range(3)])
            if a.length < 1e-9:
                a = Vector((1, 0, 0)); break
            a.normalize()
        for f in isl:
            n = f.normal
            if abs(n.dot(a)) > 0.7:          # end grain: keep the box projection
                continue
            b = n.cross(a).normalized()
            for l in f.loops:
                l[uv].uv = (l.vert.co.dot(b), l.vert.co.dot(a))
    bm.to_mesh(me); bm.free()


def uv_unit(obj, slots):
    """Per-face 0..1 UV0 for 'object'-mode lantern materials (lantern_andon): each panel face spans the
    whole lantern texture, v up."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap')
    slots = set(slots)
    for f in bm.faces:
        if f.material_index not in slots:
            continue
        n = f.normal
        if abs(n.z) > 0.7:
            a, b = Vector((1, 0, 0)), Vector((0, 1, 0))
        else:
            a = Vector((-n.y, n.x, 0)).normalized(); b = Vector((0, 0, 1))
        us = [l.vert.co.dot(a) for l in f.loops]; vs = [l.vert.co.dot(b) for l in f.loops]
        du, dv = max(us) - min(us) or 1, max(vs) - min(vs) or 1
        for l, u_, v_ in zip(f.loops, us, vs):
            l[uv].uv = ((u_ - min(us)) / du, (v_ - min(vs)) / dv)
    bm.to_mesh(me); bm.free()


def prism_local_y(mb, poly_xz, y0, y1, mi, M):
    """Extrude a 2D polygon given in local (x, z) along local y (y0..y1), then transform by M."""
    sw = [(x, z) for x, z in poly_xz]
    poly_yz = [(-x, z) for x, z in sw]           # build along x via prism_x in a rotated frame
    R = M @ Matrix.Rotation(math.pi / 2, 4, 'Z')  # local x' = local y, local y' = -local x
    return prism_x(mb, poly_yz, y0, y1, mi, M=R)


def band(mb, center, wx, wy, h, mi):
    """Open 4-sided iron band (no caps, 8 tris) around a post."""
    bm = mb.bm
    cx, cy, cz = center
    lo = [bm.verts.new((cx + sx * wx / 2, cy + sy * wy / 2, cz - h / 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    hi = [bm.verts.new((v.co.x, v.co.y, cz + h / 2)) for v in lo]
    fs = [bm.faces.new((lo[i], lo[(i + 1) % 4], hi[(i + 1) % 4], hi[i])) for i in range(4)]
    mb._tag(fs, mi)
    return fs


def rock_body(mb, M, s0, s1, x_out, x_in, top_fn, bot_fn, ns, nz, disp, r, mi, top_noise=0.0):
    """Closed sloped wall body in a local frame (x across, y = s along, z up), transformed by M.
    The outer face (x = x_out) is a ns x nz grid whose interior and top vertices are displaced by up to
    `disp` (rough basalt bulges); the inner face (x = x_in) is flat. top_fn(s) / bot_fn(s) give the z of
    the top and bottom edges. Used for stair cheeks, cliff walls and the cantilever host wall."""
    bm = mb.bm
    sg = 1.0 if x_out > x_in else -1.0
    ss = [s0 + (s1 - s0) * i / ns for i in range(ns + 1)]
    O = []
    for i, s in enumerate(ss):
        col = []
        zt_, zb_ = top_fn(s), bot_fn(s)
        for j in range(nz + 1):
            t = j / nz
            z = zb_ + (zt_ - zb_) * t
            x = x_out
            ds = dz = 0.0
            if disp > 0:
                edge_s = i in (0, ns)
                x += sg * r.uniform(-0.5, 1.0) * disp * (0.5 if j == 0 else 1.0)
                if not edge_s:
                    ds = r.uniform(-0.6, 0.6) * disp
                if 0 < j < nz:
                    dz = r.uniform(-0.6, 0.6) * disp
                if j == nz:
                    dz = r.uniform(-1.0, 1.0) * top_noise
            col.append(bm.verts.new(M @ Vector((x, s + ds, z + dz))))
        O.append(col)
    I = [[bm.verts.new(M @ Vector((x_in, s, bot_fn(s)))), bm.verts.new(M @ Vector((x_in, s, top_fn(s))))] for s in ss]
    fs = []
    for i in range(ns):
        for j in range(nz):
            fs.append(bm.faces.new((O[i][j], O[i + 1][j], O[i + 1][j + 1], O[i][j + 1])))
        fs.append(bm.faces.new((I[i][0], I[i][1], I[i + 1][1], I[i + 1][0])))          # inner face
        fs.append(bm.faces.new((O[i][nz], O[i + 1][nz], I[i + 1][1], I[i][1])))         # top
        fs.append(bm.faces.new((O[i][0], I[i][0], I[i + 1][0], O[i + 1][0])))          # bottom
    for i in (0, ns):
        ring = [I[i][0]] + [O[i][j] for j in range(nz + 1)] + [I[i][1]]
        fs.append(bm.faces.new(ring if i == 0 else ring[::-1]))
    mb._tag(fs, mi)
    return fs


def lantern_slim(mb, base, mats, lod, size=0.24, height=0.42, roof='hip', frame=0.02, ball=True):
    """Lean iron-framed lantern head (~60 tris at LOD0): paper box, iron base/top bands, 4 corner bars,
    hip (4-sided) or round (8-sided) roof, finial. LOD>=1: paper box + roof. Returns the light centre."""
    bx, by, bz = base
    iron, paper = mats['iron'], mats['paper']
    s = size
    kz = Vector((bx, by, bz + height / 2))
    if lod >= 2:
        # crossed quads (4 tris): reads as a lit lantern at distance
        bm = mb.bm
        fs = []
        for dx, dy in ((s / 2, 0), (0, s / 2)):
            q = [bm.verts.new((bx - dx, by - dy, bz)), bm.verts.new((bx + dx, by + dy, bz)),
                 bm.verts.new((bx + dx, by + dy, bz + height)), bm.verts.new((bx - dx, by - dy, bz + height))]
            fs.append(bm.faces.new(q))
        mb._tag(fs, paper)
        return kz
    cbox(mb, Matrix.Translation(kz), (s * 0.86, s * 0.86, height - 0.02), paper, drop_bottom=lod >= 1)
    rh = 0.1
    segs = 4 if roof == 'hip' else 8
    mb.cylinder((bx, by, bz + height + rh / 2 - 0.01), radius=s * (0.86 if segs == 4 else 0.68), radius2=0.012, depth=rh,
                mi=iron, segs=segs, rot=(0, 0, math.pi / 4 if segs == 4 else math.pi / 8), cap=False)
    if lod == 0:
        cb = frame
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.cylinder((bx + sx * (s / 2 - cb / 2), by + sy * (s / 2 - cb / 2), bz + height / 2), radius=cb * 0.7,
                            depth=height, mi=iron, segs=3, cap=False)
        if ball:
            lathe(mb, (bx, by, bz + height + rh - 0.02), [(0.012, 0), (0.03, 0.03), (0.022, 0.055), (0, 0.065)], iron, segs=5)
        else:
            mb.cylinder((bx, by, bz + height + rh + 0.02), radius=0.02, radius2=0.0, depth=0.06, mi=iron, segs=4, cap=False)
    return kz
