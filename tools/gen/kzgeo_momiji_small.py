"""Tree toolkit for gen_momiji_small and gen_conifer_tall (op06).

TreeGeo wraps a genlib.MeshBuilder and tags every vertex it makes with sway weight / phase / leaf flag and,
for tubes and cards, its own UV (u around the branch, v along it; card UV 0..w in metres). post() restores
those UVs after genlib.finish() (which box-projects UV0), smooths the foliage, and writes the runtime sway
data: colour attribute `kz_sway` (POINT, R = sway weight, G = phase, B = 1 on foliage) and vertex group `sway`.
Adapted from gen_pine_niwaki's Geo / _post (passed review).
"""
import math

import bmesh
from mathutils import Vector, noise


def along(path, f):
    f = max(0.0, min(1.0, f)) * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    return path[i].lerp(path[i + 1], f - i)


def resample(path, n):
    return [along(path, j / n) for j in range(n + 1)]


def smooth_path(ctrl, n):
    """Catmull-Rom through the control points, n + 1 samples"""
    P = [Vector(p) for p in ctrl]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    segs = len(P) - 3
    out = []
    for j in range(n + 1):
        t = j / n * segs
        i = min(int(t), segs - 1)
        u = t - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out


def nz(v, off):
    return noise.noise(Vector(v) + off)


class TreeGeo:
    def __init__(self, mb):
        self.mb = mb
        L = mb.bm.verts.layers.float
        self.ls, self.lp, self.lf = L.new('_kz_sw'), L.new('_kz_ph'), L.new('_kz_lf')
        self.lu, self.lv, self.luf = L.new('_kz_u'), L.new('_kz_v'), L.new('_kz_uf')

    def tag(self, v, sway, ph, leaf, u=None, vv=None):
        v[self.ls] = sway; v[self.lp] = ph; v[self.lf] = leaf
        if u is not None:
            v[self.lu] = u; v[self.lv] = vv; v[self.luf] = 1.0

    def tube(self, pts, radii, mi, sides, sway, ph=0.0, mod=None, cap1=False):
        """round tube with a duplicated seam column (clean cylindrical UVs); sway(t) -> weight"""
        bm = self.mb.bm
        pts = [Vector(p) for p in pts]
        n = len(pts)
        tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
        up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
        u = tans[0].cross(up).normalized()
        rings, s_len = [], 0.0
        circ = 2 * math.pi * sum(radii) / len(radii)
        for i in range(n):
            if i:
                u = (u - tans[i] * u.dot(tans[i])).normalized()
                s_len += (pts[i] - pts[i - 1]).length
            v = tans[i].cross(u)
            ring = []
            for k in range(sides + 1):
                th = 2 * math.pi * (k % sides) / sides
                if k < sides:
                    rr = radii[i] * (mod(i, th) if mod else 1.0)
                    vv = bm.verts.new(pts[i] + (u * math.cos(th) + v * math.sin(th)) * rr)
                else:
                    vv = bm.verts.new(ring[0].co)
                self.tag(vv, sway(i / max(n - 1, 1)), ph, 0.0, circ * k / sides, s_len)
                ring.append(vv)
            rings.append(ring)
        for i in range(n - 1):
            for k in range(sides):
                f = bm.faces.new((rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]))
                f.material_index = mi
        if cap1:
            c = bm.verts.new(pts[-1] + tans[-1] * radii[-1] * 0.6)
            self.tag(c, sway(1.0), ph, 0.0)
            for k in range(sides):
                f = bm.faces.new((rings[-1][k], rings[-1][k + 1], c)); f.material_index = mi
        return rings

    def card(self, base, right, up, w, hgt, mi, sway, ph, u0):
        bm = self.mb.bm
        vs = []
        for (a, b) in ((-0.5, 0), (0.5, 0), (0.5, 1), (-0.5, 1)):
            v = bm.verts.new(base + right * (a * w) + up * (b * hgt))
            self.tag(v, sway, ph, 1.0, u0 + (a + 0.5) * w, b * hgt)
            vs.append(v)
        f = bm.faces.new(vs); f.material_index = mi
        return f

    def lens(self, c, R, T, mi, segs, sway, ph, off, inner=True, lobes=5, flat=1.0, d=None, below=0.35,
             rough=0.12):
        """closed foliage core: scalloped rim at c, domed top (T above), shallow underside (below*T).
        Returns (edge(th), top(th, f)) samplers for card placement."""
        bm = self.mb.bm
        d = (d or Vector((1, 0, 0))).normalized()
        side = Vector((-d.y, d.x, 0))

        def edge(th):
            return R * (1 + rough * math.cos(lobes * th + ph * 6) + 0.6 * rough * nz((math.cos(th) * 1.7, math.sin(th) * 1.7, 0.3), off))

        def P_(th, f, z):
            e = edge(th) * f
            return c + d * (math.cos(th) * e * flat) + side * (math.sin(th) * e) + Vector((0, 0, z))

        def top_z(th, f):
            return T * (0.25 + 0.75 * (1 - f * f) ** 0.7) + T * 0.12 * nz((math.cos(th) * f * 2.5, math.sin(th) * f * 2.5, 1.1), off)

        ths = [2 * math.pi * i / segs for i in range(segs)]
        rim = [bm.verts.new(P_(th, 1.0, T * 0.12 * nz((math.cos(th) * 3, math.sin(th) * 3, 2.0), off))) for th in ths]
        rows = [rim]
        if inner:
            rows.insert(0, [bm.verts.new(P_(th, 0.55, top_z(th, 0.55))) for th in ths])
        top = bm.verts.new(c + Vector((0, 0, T)))
        bot = bm.verts.new(c - Vector((0, 0, T * below)))
        for v in [top, bot] + [v for r_ in rows for v in r_]:
            self.tag(v, sway, ph, 1.0)
        for i in range(segs):
            f = bm.faces.new((top, rows[0][i], rows[0][(i + 1) % segs])); f.material_index = mi
        for a, b in zip(rows[:-1], rows[1:]):
            for i in range(segs):
                i2 = (i + 1) % segs
                f = bm.faces.new((a[i], b[i], b[i2], a[i2])); f.material_index = mi
        for i in range(segs):
            f = bm.faces.new((bot, rim[(i + 1) % segs], rim[i])); f.material_index = mi
        return edge, P_, top_z


def post(o, soft_slots):
    """restore tube / card UVs, smooth foliage edges, write kz_sway colour attribute + vertex group 'sway'"""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    L = bm.verts.layers.float
    lu, lv, luf = L['_kz_u'], L['_kz_v'], L['_kz_uf']
    uv = bm.loops.layers.uv['UVMap']
    for f in bm.faces:
        if all(v[luf] > 0 for v in f.verts):
            for l in f.loops:
                l[uv].uv = (l.vert[lu], l.vert[lv])
    for e in bm.edges:
        if e.link_faces and all(f.material_index in soft_slots for f in e.link_faces):
            e.smooth = True
    for name in ('_kz_u', '_kz_v', '_kz_uf'):
        L.remove(L[name])
    bm.to_mesh(me); bm.free()
    n = len(me.vertices)
    s = [0.0] * n; p_ = [0.0] * n; l_ = [0.0] * n
    me.attributes['_kz_sw'].data.foreach_get('value', s)
    me.attributes['_kz_ph'].data.foreach_get('value', p_)
    me.attributes['_kz_lf'].data.foreach_get('value', l_)
    col = me.color_attributes.new('kz_sway', 'FLOAT_COLOR', 'POINT')
    flat = []
    for i in range(n):
        flat += [s[i], p_[i], l_[i], 1.0]
    col.data.foreach_set('color', flat)
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    vg = o.vertex_groups.new(name='sway')
    for i in range(n):
        if s[i] > 0:
            vg.add([i], s[i], 'REPLACE')
    for a in ('_kz_sw', '_kz_ph', '_kz_lf'):
        me.attributes.remove(me.attributes[a])
