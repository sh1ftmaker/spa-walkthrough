"""Place helpers for b1_cor_mirror (the mist corridor to the Mirror). Used by build_b1_cor_mirror.py.

Geometry model
  * Two swept legs share one cross-section (local u = lateral, + = left of travel, v = height above floor_z):
      leg A  lobby portal (78, 72) -> koi-junction circle edge          (west leg, 6.7 m)
      leg BC junction circle edge -> (66, 92) fillet R 2.3 -> arch (93.6, 92)   (north leg + 26 m east straight)
  * Shell profile: rock walls vertical to 1.9 m, then a quarter-ellipse to the 3.0 m crown (2.4 m at u = +-1.8,
    the space file's 'springing'), half width W = 2.0 m.  Rings every ~0.22 m, ~46 points per ring.
  * Rock: displaced along the profile's inward normal by world-space noise: low fbm lobes (bulges, overhangs),
    horizontal basalt strata (ledges at ankle / knee / head height) and Voronoi blocks (flat-faced chunks with
    stepped joints).  Wall features (shoji bays, trickles, niches, the corner lantern alcove) carve the wall
    behind themselves and pull it flush around themselves; noise is outward-only near open portal ends so the
    portals keep their full width.
  * Floor: two rough rock kerbs (top at floor_z, organic edge 0.35-0.65 m wide, a lip dropping into the pool),
    a flat bed at bed_z under the whole width, and one water ribbon at the layout water level.  The kerbs meet
    over the bed at the dry lobby threshold.
  * Walk mesh: kerb tops + bed + 2.2 m collision walls at the free edge (the nearest rock or feature front).
"""
import math, json
import bmesh, bpy
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

FLOOR = -20.0
BED = -0.18          # bed relative to floor (space file bed_z -20.18; decision 42 depth 0.18)
WATER = -0.05        # water surface relative to floor (layout w_b1_corridors z -20.05)
W = 2.0              # half width (4 m corridor)
WALL_V = 1.9         # vertical wall height before the vault curve
CROWN = 3.0          # crown height (ceiling_z -17)
DS = 0.26            # ring spacing (m)
JUNC_C, JUNC_R = Vector((66.0, 74.0)), 5.5


# ------------------------------------------------------------------------------------------------ paths
def circle_hit(p0, p1, c, r):
    """first t in [0,1] where segment p0->p1 crosses the circle (c, r)"""
    d = p1 - p0; f = p0 - c
    a = d.dot(d); b = 2 * f.dot(d); cc = f.dot(f) - r * r
    disc = math.sqrt(max(0.0, b * b - 4 * a * cc))
    ts = sorted([(-b - disc) / (2 * a), (-b + disc) / (2 * a)])
    for t in ts:
        if 0 <= t <= 1:
            return t
    return None


class Path:
    """Polyline with filleted corners, sampled by arc length. Stations: (s, pos2, tangent2, left2)."""

    def __init__(self, pts, radius=0.0, ds=DS, name=''):
        self.name = name
        pts = [Vector(p) for p in pts]
        segs = []                                    # list of ('L', a, b) / ('A', centre, r, a0, a1, ccw)
        cur = pts[0]
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            d1 = (b - a).normalized(); d2 = (c - b).normalized()
            turn = math.acos(max(-1, min(1, d1.dot(d2))))
            t = radius * math.tan(turn / 2)
            p_in = b - d1 * t; p_out = b + d2 * t
            segs.append(('L', cur, p_in))
            cross = d1.x * d2.y - d1.y * d2.x
            nrm = Vector((-d1.y, d1.x)) if cross > 0 else Vector((d1.y, -d1.x))
            cen = p_in + nrm * radius
            a0 = math.atan2(p_in.y - cen.y, p_in.x - cen.x); a1 = math.atan2(p_out.y - cen.y, p_out.x - cen.x)
            ccw = cross > 0
            if ccw and a1 < a0:
                a1 += 2 * math.pi
            if not ccw and a1 > a0:
                a1 -= 2 * math.pi
            segs.append(('A', cen, radius, a0, a1, ccw))
            cur = p_out
        segs.append(('L', cur, pts[-1]))
        self.segs = segs
        self.length = sum(self._seglen(s) for s in segs)
        n = max(2, int(round(self.length / ds)) + 1)
        self.st = [self.at(self.length * i / (n - 1)) for i in range(n)]

    def _seglen(self, s):
        return (s[2] - s[1]).length if s[0] == 'L' else abs(s[4] - s[3]) * s[2]

    def at(self, s):
        s_glob = s
        for sg in self.segs:
            L = self._seglen(sg)
            if s <= L + 1e-9 or sg is self.segs[-1]:
                if sg[0] == 'L':
                    t = (sg[2] - sg[1]).normalized()
                    p = sg[1] + t * min(s, L)
                else:
                    cen, r, a0, a1, ccw = sg[1], sg[2], sg[3], sg[4], sg[5]
                    a = a0 + (a1 - a0) * (min(s, L) / L)
                    p = cen + Vector((math.cos(a), math.sin(a))) * r
                    t = Vector((-math.sin(a), math.cos(a))) * (1 if ccw else -1)
                return (s_glob, p, t, Vector((-t.y, t.x)))
            s -= L
        raise ValueError

    def nearest(self, xy):
        xy = Vector(xy[:2])
        best = min(self.st, key=lambda q: (q[1] - xy).length)
        # local refine
        s0 = best[0]; bs = best
        for k in range(-10, 11):
            q = self.at(min(self.length, max(0.0, s0 + k * DS / 10)))
            if (q[1] - xy).length < (bs[1] - xy).length:
                bs = q
        return bs


def make_paths():
    A0, A1 = Vector((78.0, 72.0)), Vector((68.0, 74.0))
    ta = circle_hit(A0, A1, JUNC_C, JUNC_R)
    legA = Path([A0, A0 + (A1 - A0) * ta], name='west_leg')
    B0, B1 = Vector((68.0, 74.0)), Vector((66.0, 92.0))
    tb = circle_hit(B1, B0, JUNC_C, JUNC_R)            # from the north end back toward the junction
    start = B1 + (B0 - B1) * tb
    legB = Path([start, B1, Vector((93.6, 92.0))], radius=2.3, name='north_east')
    return legA, legB


# ------------------------------------------------------------------------------------------------ profile
def profile(n_wall=9, n_vault=22):
    """(u, v) from the right foot up over the crown to the left foot, with the inward normal per point."""
    pts = []
    for i in range(n_wall):                       # right wall, v from -0.12 up to WALL_V
        v = -0.12 + (WALL_V + 0.12) * i / n_wall
        pts.append((-W, v))
    for i in range(n_vault + 1):                  # quarter ellipses, phi 0..pi
        ph = math.pi * i / n_vault
        pts.append((-W * math.cos(ph), WALL_V + (CROWN - WALL_V) * math.sin(ph)))
    for i in range(1, n_wall + 1):
        v = WALL_V - (WALL_V + 0.12) * i / n_wall
        pts.append((W, v))
    out = []
    for i, (u, v) in enumerate(pts):
        a = Vector(pts[max(0, i - 1)]); b = Vector(pts[min(len(pts) - 1, i + 1)])
        t = (b - a).normalized()
        nrm = Vector((t.y, -t.x))                 # right-hand normal of a path going up the right wall = +u (inward)
        if nrm.dot(Vector((0, 1.2)) - Vector((u, v))) < 0:
            nrm = -nrm
        out.append((u, v, nrm))
    return out


# ------------------------------------------------------------------------------------------------ rock noise
def _cell_offset(pt):
    return noise.noise(Vector(pt) * 3.7 + Vector((11.3, 2.1, 7.7)))


def rock_disp(p, v, vault=False):
    """inward displacement (m) of the rock surface at world point p (nominal), height v above floor"""
    big = noise.fractal(Vector((p.x / 1.9, p.y / 1.9, p.z / 1.4)), 1.0, 2.0, 3, noise_basis='PERLIN_ORIGINAL')
    # horizontal basalt strata: stretched along the corridor, tight in z -> ledges and overhang lips
    st = noise.noise(Vector((p.x * 0.33, p.y * 0.33, v * 2.4 + 3.1)), noise_basis='PERLIN_ORIGINAL')
    ledge = max(-1.0, min(1.0, st * 2.6))
    # blocky joints: per-Voronoi-cell flat offsets
    dists, pts = noise.voronoi(Vector((p.x / 0.62, p.y / 0.62, p.z / 0.5)), distance_metric='DISTANCE')
    chunk = _cell_offset(pts[0])
    crack = max(0.0, 1.0 - (dists[1] - dists[0]) / 0.09)      # thin joint lines sink back
    d = 0.20 * big + 0.09 * ledge + 0.10 * chunk - 0.05 * crack
    if vault:
        d *= 0.85
    return d


# ------------------------------------------------------------------------------------------------ features
class Feature:
    """Something set into / against the wall. heading = compass bearing of its front (+Y)."""

    def __init__(self, name, at, heading, w, d, h, kind, z0=None, mid=0.0, margin=0.45):
        self.name, self.kind = name, kind
        self.c = Vector(at)
        hr = math.radians(heading)
        self.f = Vector((math.sin(hr), math.cos(hr), 0.0)); self.r = Vector((math.cos(hr), -math.sin(hr), 0.0))
        self.w, self.d, self.h = w, d, h
        self.z0 = self.c.z if z0 is None else z0
        self.mid = mid            # where the wall sits around it, along f from the centre (m)
        self.margin = margin

    def local(self, p):
        q = p - self.c
        return q.dot(self.r), q.dot(self.f), p.z - self.z0

    def carve(self, p, n_in, d, small):
        k = n_in.dot(self.f)
        if k < 0.25:
            return d
        a, b0, z = self.local(p)
        hw = self.w / 2
        ax = abs(a)
        inset = 0.06
        zlo, zhi = -0.15, self.h - 0.05
        back = -self.d / 2 - (0.18 if self.kind == 'alcove' else 0.04)
        if ax < hw - inset and zlo < z < zhi and b0 < self.d + 0.6:
            if self.kind == 'niche':
                return max(-0.4, min(0.3, (-self.d / 2 + 0.01 - b0) / k)) if k > 0.6 else min(d, 0.0)
            return min(d, (back - b0) / k)
        if self.kind == 'floor':
            return d
        # ring: distance outside the core box
        dx = max(0.0, ax - (hw - inset)); dz = max(0.0, zlo - z, z - zhi)
        dist = math.hypot(dx, dz)
        if dist < self.margin and b0 < self.d + 0.8:
            wgt = 1.0 - (dist / self.margin) ** 2
            wgt = wgt * wgt * (3 - 2 * wgt) if self.kind != 'alcove' else wgt
            target = max(-1.0, min(0.4, (self.mid - b0) / k + 0.35 * small))
            if self.kind == 'alcove':
                target = min(d, (back + 0.1 - b0) / k)
            return d + (target - d) * wgt
        return d

    def footprint_u(self, st, side):
        """if this floor feature overlaps station st on `side` (+1 left / -1 right), the u it reaches toward
        the centre (abs), else None"""
        s, c2, t2, l2 = st
        corners = []
        for sa in (-1, 1):
            for sb in (-1, 1):
                p = self.c + self.r * (sa * self.w / 2) + self.f * (sb * self.d / 2)
                corners.append(Vector((p.x, p.y)))
        along = [(q - c2).dot(t2) for q in corners]
        if min(along) > 0.25 or max(along) < -0.25:
            return None
        us = [(q - c2).dot(l2) for q in corners]
        if side > 0 and min(us) > 0.3:
            return min(us)
        if side < 0 and max(us) < -0.3:
            return -max(us)
        return None


# ------------------------------------------------------------------------------------------------ shell
def build_shell(path, features, open_start, open_end, name, prof=None, flare_end=0.0):
    """returns (bm_walls, bm_vault, stations_info) for one leg"""
    prof = prof or profile()
    nP = len(prof)
    vault_lo = next(i for i, q in enumerate(prof) if q[1] > WALL_V + 0.12)
    vault_hi = max(i for i, q in enumerate(prof) if q[1] > WALL_V + 0.12)
    rings = []
    info = []
    for st in path.st:
        s, c2, t2, l2 = st
        ring = []
        endd = min(s if open_start else 99, (path.length - s) if open_end else 99)
        ramp = min(1.0, endd / 1.3)
        ramp = ramp * ramp * (3 - 2 * ramp)
        inner = {1: 9.0, -1: 9.0}
        fl = 0.0
        if flare_end:
            t = max(0.0, min(1.0, (s - (path.length - 2.2)) / 1.6))
            fl = t * t * (3 - 2 * t)
        for (u, v, n) in prof:
            if fl:          # flare into the hero arch: vault lifted, walls eased out
                u = u * (1 + 0.12 * fl)
                if v > 1.0:
                    v = v + flare_end * fl * min(1.0, (v - 1.0) / (CROWN - 1.0))
            pn = Vector((c2.x + l2.x * u, c2.y + l2.y * u, FLOOR + v))
            n_in = Vector((l2.x * n.x, l2.y * n.x, n.y)).normalized()
            vault = v > WALL_V + 0.05
            d = rock_disp(pn, v, vault)
            small = 0.5 * noise.noise(pn * 2.3)
            if v < 0.55:
                d = min(d, 0.24)
            d = max(d, -0.32)
            if d > 0:
                d *= ramp
            for F in features:
                d = F.carve(pn, n_in, d, small * 0.2)
            d = max(-1.7, min(d, 0.45))
            if vault and v > 2.75:
                d = min(d, 0.22 if not fl else 0.0)                        # keep >= 2.75 m at the crown
            p = pn + n_in * d
            ring.append(p)
            if 0.1 < v < 2.15:
                side = 1 if u > 0 else -1
                inner[side] = min(inner[side], abs((Vector((p.x, p.y)) - c2).dot(l2)))
        rings.append(ring)
        info.append(dict(st=st, inner=inner))
    bw = bmesh.new(); bv = bmesh.new()
    for bm, rng_ in ((bw, [(0, vault_lo), (vault_hi, nP - 1)]), (bv, [(vault_lo, vault_hi)])):
        for (i0, i1) in rng_:
            grid = [[bm.verts.new(rings[j][i]) for i in range(i0, i1 + 1)] for j in range(len(rings))]
            for j in range(len(rings) - 1):
                for i in range(i1 - i0):
                    # winding: normals face into the corridor (the visible side)
                    bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    for bm in (bw, bv):
        _orient_inward(bm, path)
    return bw, bv, info


def _orient_inward(bm, path):
    """the grids are built in one consistent winding; vote on a sample and flip all if they face the rock"""
    bm.normal_update()
    faces = list(bm.faces)
    votes = 0
    for f in faces[::max(1, len(faces) // 60)]:
        c = f.calc_center_median()
        st = path.nearest((c.x, c.y))
        axis = Vector((st[1].x, st[1].y, FLOOR + 1.2))
        votes += 1 if f.normal.dot(axis - c) > 0 else -1
    if votes < 0:
        for f in faces:
            f.normal_flip()
        bm.normal_update()


# ------------------------------------------------------------------------------------------------ floor
def kerb_edges(path, features, dry, info):
    """per station: kerb edge |u| per side (the pool edge), outer |u| per side"""
    out = []
    for k, st in enumerate(path.st):
        s, c2, t2, l2 = st
        row = {}
        for side in (1, -1):
            n = noise.noise(Vector((c2.x * 0.45, c2.y * 0.45, 5.0 + side * 3)))
            n2 = noise.noise(Vector((c2.x * 1.7, c2.y * 1.7, 9.0 + side)))
            kw = 0.5 + 0.14 * n + 0.05 * n2
            edge = W - kw
            outer = W + 0.3
            for F in features:
                if F.kind in ('floor', 'alcove', 'bay', 'trickle'):
                    fu = F.footprint_u(st, side)
                    if fu is not None:
                        edge = min(edge, fu - 0.12)
                        if F.kind == 'alcove':
                            outer = max(outer, W + 1.5)
            dd = dry(s)
            edge = edge * (1 - dd)
            row[side] = (edge, outer)
        out.append(row)
    return out


def build_floor(path, edges, pool_range):
    """kerbs (both sides), bed, water.  pool_range: (s0, s1) where the water exists."""
    bk = bmesh.new(); bb = bmesh.new(); bw = bmesh.new()
    rings_k = {1: [], -1: []}
    for k, st in enumerate(path.st):
        s, c2, t2, l2 = st
        for side in (1, -1):
            edge, outer = edges[k][side]
            def P(u, z):
                return Vector((c2.x + l2.x * u * side, c2.y + l2.y * u * side, FLOOR + z))
            rough = 0.012 * noise.noise(Vector((c2.x * 2.1, c2.y * 2.1, side * 4.0)))
            mid = (edge + outer) / 2
            ring = [P(outer, 0.0), P(mid, min(0.0, rough) * 0.6), P(edge + 0.05, -0.004), P(edge, -0.03),
                    P(edge - 0.05, -0.11), P(edge - 0.09, BED - 0.03)]
            rings_k[side].append(ring)
    for side in (1, -1):
        R = rings_k[side]
        grid = [[bk.verts.new(p) for p in ring] for ring in R]
        for j in range(len(grid) - 1):
            for i in range(len(grid[j]) - 1):
                bk.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    _orient_up(bk)
    # bed: flat under the whole width
    gb = []
    for st in path.st:
        s, c2, t2, l2 = st
        gb.append([bb.verts.new(Vector((c2.x + l2.x * u, c2.y + l2.y * u, FLOOR + BED))) for u in (-(W + 0.2), 0.0, W + 0.2)])
    for j in range(len(gb) - 1):
        for i in range(2):
            bb.faces.new((gb[j][i], gb[j][i + 1], gb[j + 1][i + 1], gb[j + 1][i]))
    _orient_up(bb)
    # water ribbon
    gw = []
    s0, s1 = pool_range
    sts = [st for st in path.st if s0 <= st[0] <= s1]
    if sts and sts[-1][0] < s1 - 0.01:
        sts.append(path.at(s1))
    for st in sts:
        s, c2, t2, l2 = st
        k = min(range(len(path.st)), key=lambda q: abs(path.st[q][0] - s))
        el = max(0.05, edges[k][1][0] + 0.02); er = max(0.05, edges[k][-1][0] + 0.02)
        gw.append([bw.verts.new(Vector((c2.x + l2.x * u, c2.y + l2.y * u, FLOOR + WATER))) for u in (-er, 0.0, el)])
    for j in range(len(gw) - 1):
        for i in range(2):
            bw.faces.new((gw[j][i], gw[j][i + 1], gw[j + 1][i + 1], gw[j + 1][i]))
    _orient_up(bw)
    return bk, bb, bw


def _orient_up(bm):
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < -0.05:
            f.normal_flip()


# ------------------------------------------------------------------------------------------------ walk mesh
def build_walk(path, edges, info, features=(), bm=None, hw=2.2):
    """kerb tops (floor_z), bed (BED), risers, and collision walls (hw high) at the free edge
    (the nearest rock between 0.1 and 2.15 m, or the front of a floor-standing feature)"""
    bm = bm or bmesh.new()
    rows = []
    for k, st in enumerate(path.st):
        s, c2, t2, l2 = st
        fr = {sd: min(info[k]['inner'][sd] - 0.05, W + 0.4) for sd in (1, -1)}
        for F in features:
            if F.kind in ('bay', 'trickle', 'floor'):
                for sd in (1, -1):
                    fu = F.footprint_u(st, sd)
                    if fu is not None:
                        fr[sd] = min(fr[sd], fu)
        el, er = edges[k][1][0], edges[k][-1][0]
        def P(u, z):
            return Vector((c2.x + l2.x * u, c2.y + l2.y * u, FLOOR + z))
        pts = [P(-fr[-1], hw), P(-fr[-1], 0.0)]
        if er > 0.02 or el > 0.02:
            ue_r, ue_l = -min(er, fr[-1] - 0.01), min(el, fr[1] - 0.01)
            pts += [P(ue_r, 0.0), P(ue_r, BED), P(ue_l, BED), P(ue_l, 0.0)]
        else:
            pts += [P(-0.01, 0.0), P(-0.005, 0.0), P(0.005, 0.0), P(0.01, 0.0)]
        pts += [P(fr[1], 0.0), P(fr[1], hw)]
        rows.append([bm.verts.new(p) for p in pts])
    for j in range(len(rows) - 1):
        for i in range(len(rows[j]) - 1):
            try:
                bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            except ValueError:
                pass
    return bm


# ------------------------------------------------------------------------------------------------ lights from props
def realise_lights(P, obj, scale_w=1.0, runtime=False, prefix=None, offset=(0, 0, 0), shadow=True):
    """Blender lights (kz_lights collection) from a generator object's kz_lights / kz_light props"""
    out = []
    M = obj.matrix_world
    R = M.to_3x3().normalized()
    entries = []
    if 'kz_lights' in obj.keys():
        entries = json.loads(obj['kz_lights'])
    elif 'kz_light' in obj.keys():
        entries = [json.loads(obj['kz_light'])]
    for i, e in enumerate(entries):
        pos = M @ (Vector(e['pos']) + Vector(offset))   # generator positions sit inside the closed lantern box
        kind = (e.get('kind') or e.get('type') or 'point').upper()
        watts = e.get('watts', 25) * scale_w
        nm = f'L_{prefix or obj.name}_{i}'
        if kind == 'AREA':
            sz = e.get('size', [1, 1])
            nrm = R @ Vector(e.get('normal', [0, 1, 0]))
            rot = nrm.to_track_quat('-Z', 'Z').to_euler()
            l = P.light(nm, 'AREA', pos, watts, kelvin=e.get('color_k', 2600), size=max(sz), runtime=runtime, rot=rot)
            l.data.shape = 'RECTANGLE'; l.data.size = sz[0]; l.data.size_y = sz[1]
        else:
            l = P.light(nm, 'POINT', pos, watts, kelvin=e.get('color_k', 2400), size=0.05, runtime=runtime)
        if not shadow:
            l.data.use_shadow = False
        l['kz_offset'] = list(offset)
        if 'color' in e:
            l.data.color = e['color'][:3]
        l['kz_source'] = obj.name
        out.append(l)
    return out


# ------------------------------------------------------------------------------------------------ BVH helpers
def bvh_of(objs, depsgraph=None):
    verts, polys = [], []
    for o in objs:
        if o.type != 'MESH':
            continue
        me = o.evaluated_get(depsgraph).to_mesh() if depsgraph else o.data
        M = o.matrix_world
        base = len(verts)
        verts += [M @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        if depsgraph:
            o.evaluated_get(depsgraph).to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0) if polys else None
