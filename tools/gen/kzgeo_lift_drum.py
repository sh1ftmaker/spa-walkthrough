"""Geometry helpers for gen_lift_drum (oriented boxes, bars, circular sweeps, lathes, glyph decals)."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def intend(bm, f, n):
    """record the outward normal a single-sided face must keep (MeshBuilder.to_object recalculates normals,
    which is unreliable on open parts); fix_normals() applies it after the mesh is built"""
    lay = bm.faces.layers.float_vector.get('kz_n') or bm.faces.layers.float_vector.new('kz_n')
    f[lay] = Vector(n).normalized()


def fix_normals(obj):
    me = obj.data
    a = me.attributes.get('kz_n')
    if a is None:
        return 0
    bm = bmesh.new(); bm.from_mesh(me)
    lay = bm.faces.layers.float_vector.get('kz_n')
    flip = [f for f in bm.faces if f[lay].length > 0.5 and f.normal.dot(f[lay]) < 0]
    bmesh.ops.reverse_faces(bm, faces=flip)
    bm.faces.layers.float_vector.remove(lay)
    bm.to_mesh(me); bm.free()
    return len(flip)


def polar(r, bearing, z=0.0):
    """bearing in radians, clockwise from +Y seen from above (x = r sin b, y = r cos b)"""
    return Vector((r * math.sin(bearing), r * math.cos(bearing), z))


def frame(bearing, dist, z=0.0):
    """local frame on a vertical plane facing outward at `bearing`, `dist` from the axis.
    local x = tangent (viewer's right when standing outside looking at the drum), y = outward normal, z = up."""
    n = Vector((math.sin(bearing), math.cos(bearing), 0))
    t = Vector((-math.cos(bearing), math.sin(bearing), 0))      # viewer's right
    M = Matrix(((t.x, n.x, 0, 0), (t.y, n.y, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    M.translation = n * dist + Vector((0, 0, z))
    return M


def obox(bm, M, c, size, mi, bevel=0.0, segs=1, skip_back=False):
    """box with centre c and size in the local frame M; optional bevel; returns faces"""
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    bmesh.ops.scale(bm, vec=size, verts=vs)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    faces = list({f for v in vs for f in v.link_faces})
    if skip_back:
        for f in faces:
            f.normal_update()
            intend(bm, f, M.to_3x3() @ f.normal)
        back = [f for f in faces if f.normal.y < -0.9]
        bmesh.ops.delete(bm, geom=back, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    if bevel > 0 and not skip_back:
        edges = list({e for f in faces for e in f.edges})
        res = bmesh.ops.bevel(bm, geom=edges + vs, offset=bevel, segments=segs, affect='EDGES', profile=0.5)
        faces = [f for f in set(faces) | set(res['faces']) if f.is_valid]
    vs = list({v for f in faces for v in f.verts})
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    for f in faces:
        f.material_index = mi
    return faces


def bar(bm, M, a, b, w, d, mi, y=0.0):
    """kumiko / lattice stick in a local frame's xz plane from a to b (2D points), width w (in-plane) and depth d
    (towards +y); only the front and the two side faces are built (the back sits on a panel)."""
    a = Vector((a[0], 0, a[1])); b = Vector((b[0], 0, b[1]))
    t = (b - a); L = t.length
    if L < 1e-6:
        return []
    t /= L
    s = Vector((-t.z, 0, t.x)) * (w / 2)           # in-plane side offset
    yb, yf = Vector((0, y, 0)), Vector((0, y + d, 0))
    P = [a - s + yb, b - s + yb, b + s + yb, a + s + yb, a - s + yf, b - s + yf, b + s + yf, a + s + yf]
    vs = [bm.verts.new(M @ p) for p in P]
    fs = [bm.faces.new((vs[4], vs[5], vs[6], vs[7])),       # front
          bm.faces.new((vs[0], vs[1], vs[5], vs[4])),       # side
          bm.faces.new((vs[3], vs[7], vs[6], vs[2]))]       # side
    R3 = M.to_3x3()
    sn = s.normalized()
    for f, n in zip(fs, (Vector((0, 1, 0)), -sn, sn)):
        f.material_index = mi
        intend(bm, f, R3 @ n)
    return fs


def quad(bm, M, x0, x1, z0, z1, y, mi):
    vs = [bm.verts.new(M @ Vector(p)) for p in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]
    f = bm.faces.new(vs); f.material_index = mi
    intend(bm, f, M.to_3x3() @ Vector((0, 1, 0)))
    return f


def pane(bm, M, x0, x1, z0, z1, y, mi, t=0.008):
    """closed thin glass pane (the library glass absorbs by volume, so panes must be solids)"""
    return obox(bm, M, ((x0 + x1) / 2, y, (z0 + z1) / 2), (x1 - x0, t, z1 - z0), mi)


def rod(bm, xy, z0, z1, rad, segs, mi, cap=True):
    """vertical round rod (capped unless cap=False)"""
    r = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=rad, radius2=rad, depth=z1 - z0)
    bmesh.ops.translate(bm, vec=(xy[0], xy[1], (z0 + z1) / 2), verts=r['verts'])
    for f in {f for v in r['verts'] for f in v.link_faces}:
        f.material_index = mi


def poly2d(bm, M, pts, y, mi):
    """flat polygon (local xz points) at depth y in frame M, facing +y; triangulated"""
    vs = [bm.verts.new(M @ Vector((x, y, z))) for x, z in pts]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        return []
    f.material_index = mi
    intend(bm, f, M.to_3x3() @ Vector((0, 1, 0)))
    res = bmesh.ops.triangulate(bm, faces=[f], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    for t in res['faces']:
        intend(bm, t, M.to_3x3() @ Vector((0, 1, 0)))
    return res['faces']


def frame_xyz(origin, xdir, ydir):
    """general local frame: x along xdir, y = ydir (normal), z up"""
    x = Vector(xdir).normalized(); y = Vector(ydir).normalized(); z = x.cross(y)
    if z.z < 0:
        z = -z
    M = Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
    M.translation = Vector(origin)
    return M


def lathe(bm, prof, segs, mis, a0=0.0, a1=2 * math.pi, closed=True):
    """surface of revolution over bearings a0..a1; prof [(r, z)] (r=0 -> pole). mis per band."""
    n = segs if closed else segs + 1
    rings = []
    for (r, z) in prof:
        if r <= 1e-6:
            rings.append(None if False else [bm.verts.new((0, 0, z))])
            continue
        rings.append([bm.verts.new(polar(r, a0 + (a1 - a0) * j / segs, z)) for j in range(n)])
    faces = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(segs):
            k = (j + 1) % n if closed else j + 1
            if len(A) == 1:
                f = bm.faces.new((A[0], B[k], B[j]))
            elif len(B) == 1:
                f = bm.faces.new((A[j], A[k], B[0]))
            else:
                f = bm.faces.new((A[j], A[k], B[k], B[j]))
            f.material_index = mis[i] if isinstance(mis, (list, tuple)) else mis
            (r0, z0), (r1, z1) = prof[i], prof[i + 1]
            am = a0 + (a1 - a0) * (j + 0.5) / segs
            rad = Vector((math.sin(am), math.cos(am), 0))
            intend(bm, f, rad * (z1 - z0) + Vector((0, 0, -(r1 - r0))))   # outward of a bottom->top profile
            faces.append(f)
    return faces


def arc_sweep(bm, radius, z, a0, a1, segs, section, mi, cap=True):
    """sweep a closed 2D section [(dr, dz)] along a circular arc (open, capped ends)"""
    rings = []
    for j in range(segs + 1):
        a = a0 + (a1 - a0) * j / segs
        rings.append([bm.verts.new(polar(radius + dr, a, z + dz)) for dr, dz in section])
    n = len(section)
    faces = []
    for j in range(segs):
        A, B = rings[j], rings[j + 1]
        for k in range(n):
            kk = (k + 1) % n
            f = bm.faces.new((A[k], A[kk], B[kk], B[k])); f.material_index = mi; faces.append(f)
    if cap:
        for R in (rings[0], rings[-1]):
            try:
                f = bm.faces.new(R); f.material_index = mi; faces.append(f)
            except ValueError:
                pass
    return faces


def rect_section(w, h, ch=0.0):
    """rectangle (radial width w, height h) centred at 0, optionally chamfered corners"""
    if ch <= 0:
        return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(-w / 2 + ch, -h / 2), (w / 2 - ch, -h / 2), (w / 2, -h / 2 + ch), (w / 2, h / 2 - ch),
            (w / 2 - ch, h / 2), (-w / 2 + ch, h / 2), (-w / 2, h / 2 - ch), (-w / 2, -h / 2 + ch)]


def strut(bm, a, b, w, d, mi, up=(0, 0, 1)):
    """free box from a to b (world), cross-section w x d"""
    a, b = Vector(a), Vector(b)
    if (b - a).length < 1e-6:
        return []
    t = (b - a); L = t.length; t.normalize()
    u = Vector(up)
    if abs(t.dot(u)) > 0.95:
        u = Vector((1, 0, 0))
    s = t.cross(u).normalized(); u2 = s.cross(t).normalized()
    M = Matrix(((t.x, s.x, u2.x, 0), (t.y, s.y, u2.y, 0), (t.z, s.z, u2.z, 0), (0, 0, 0, 1)))
    M.translation = (a + b) / 2
    return obox(bm, M, (0, 0, 0), (L, w, d), mi)


_glyphs = {}


def glyph_tris(text, font, res=1):
    """robust fill (overlapping CJK strokes stay solid): see kzgeo_chochin"""
    import kzgeo_chochin
    return kzgeo_chochin.glyph_tris(text, font, max(1, res))


def glyph_tris_evenodd(text, font, res=1):
    """filled glyph triangles (2D), normalised to height 1, centred at 0. Returns (tris, width)."""
    key = (text, font, res)
    if key in _glyphs:
        return _glyphs[key]
    f = bpy.data.fonts.load(font, check_existing=True)
    cu = bpy.data.curves.new('kz_glyph', 'FONT'); cu.body = text; cu.font = f
    cu.resolution_u = res; cu.fill_mode = 'BOTH'
    o = bpy.data.objects.new('kz_glyph', cu); bpy.context.scene.collection.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get(); me = o.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    tris = [[(me.vertices[i].co.x, me.vertices[i].co.y) for i in t.vertices] for t in me.loop_triangles]
    o.evaluated_get(dg).to_mesh_clear(); bpy.data.objects.remove(o); bpy.data.curves.remove(cu)
    xs = [p[0] for t in tris for p in t]; ys = [p[1] for t in tris for p in t]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    s = 1.0 / (max(ys) - min(ys))
    out = ([[((x - cx) * s, (y - cy) * s) for x, y in t] for t in tris], (max(xs) - min(xs)) * s)
    _glyphs[key] = out
    return out


def glyph_slab(bm, M, tris, cx, cz, hgt, y, depth, mi):
    """raised glyph: front triangles at y + depth (local frame), plus side walls from the outline edges"""
    vmap = {}
    edges = {}
    front = []
    for t in tris:
        pts = [(cx + x * hgt, cz + y_ * hgt) for x, y_ in t]
        vs = []
        for p in pts:
            k = (round(p[0], 5), round(p[1], 5))
            if k not in vmap:
                vmap[k] = (bm.verts.new(M @ Vector((p[0], y + depth, p[1]))), bm.verts.new(M @ Vector((p[0], y, p[1]))))
            vs.append(k)
        try:
            f = bm.faces.new([vmap[k][0] for k in vs]); f.material_index = mi; front.append(f)
            intend(bm, f, M.to_3x3() @ Vector((0, 1, 0)))
        except ValueError:
            continue
        for i in range(3):
            e = tuple(sorted((vs[i], vs[(i + 1) % 3])))
            edges[e] = edges.get(e, 0) + 1
    if depth > 0:
        for (a, b), n in edges.items():
            if n == 1:      # outline edge
                try:
                    f = bm.faces.new((vmap[a][1], vmap[b][1], vmap[b][0], vmap[a][0])); f.material_index = mi
                except ValueError:
                    pass
    return front
