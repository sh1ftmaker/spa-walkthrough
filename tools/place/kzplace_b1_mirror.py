"""Place helpers for b1_mirror (05 Obsidian Mirror Float Pool). Used by tools/place/build_b1_mirror.py.

Shell = one coherent model in layout space (metres, x east, y north, z up):
  * wall   - basalt_wet ring of craggy rock from the floor (-20) to the springing (-13), polar grid with ridged
             noise, undulating strata (knee ledge, recess, overhanging lip) and two clean portal openings
             (corridor W at (93.5, 92), east corridor at (130.5, 90)), each with a short rock reveal.
  * dome   - cave_rock elliptical vault from the springing (r ~19, -13) to the crown (-6.5), smooth-ish,
             continuous with the wall (vertical tangent at the springing), low-amplitude noise.
  * floor  - basalt_wet annulus from the pool edge (water footprint, r 12) to under the wall foot, with a
             fillet rising into the wall; flat at floor_z where people walk.
  * deck   - hinoki boardwalk ring (r 12.85-15.35) of jointed tangential boards on a fascia beam.
  * basin  - obsidian pool basin from the rim (-20.0) to the bed (-21.4).
  * water  - w_mirror surface at -20.05 (kz_water, planar).
  * walk   - kz_walk mesh: floor + deck top, basin, stair treads / risers, curb at the deep water, walls.
"""
import math, json
import bmesh, bpy
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

CX, CY = 112.0, 92.0
FLOOR = -20.0
SPRING = -13.0
CROWN = -6.5
R0 = 19.0
WATER_Z, BED_Z = -20.05, -21.4
HEAD = 3.25                      # clear height at the portal jambs (portal spec 3.0)
HEAD_C = 3.65                    # clear height at the opening centre (segmental head)

# portals: at, outward axis (room -> corridor), clear half width, reveal depth
PORTALS = {
    'p_b1_cor_mirror': dict(at=(93.5, 92.0), axis=(-1.0, 0.0), half=2.15, depth=0.6),
    'p_b1_mirror_east': dict(at=(130.5, 90.0), axis=(0.9487, -0.3162), half=2.15, depth=2.6),
}
for _p in PORTALS.values():
    a = Vector((_p['axis'][0], _p['axis'][1], 0)).normalized()
    _p['ax'] = a
    _p['t'] = Vector((-a.y, a.x, 0))           # CCW tangent: u grows with theta
    _p['r'] = math.hypot(_p['at'][0] - CX, _p['at'][1] - CY)
    _p['theta'] = math.atan2(_p['at'][1] - CY, _p['at'][0] - CX)

WALL_ROWS = [-20.0, -19.6, -19.15, -18.65, -18.15, -17.55, FLOOR + HEAD, -16.15, -15.45, -14.75, -14.05, -13.5, SPRING]
HEAD_ROW = WALL_ROWS.index(FLOOR + HEAD)
DOME_ALPHAS = [3, 7, 11.5, 16, 21, 26.5, 32, 38, 44, 50, 56, 62, 68, 74, 80, 85.5]   # deg, 0 = springing


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


# ------------------------------------------------------------------------------------------------ wall field
def _portal_damp(x, y, z):
    """0 at a portal opening edge (clean jambs / head), 1 more than ~1.6 m away."""
    d = 9.0
    for p in PORTALS.values():
        rel = Vector((x - p['at'][0], y - p['at'][1], 0))
        u = rel.dot(p['t']); v = rel.dot(p['ax'])
        if abs(v) > 4.0:
            continue
        hz = z - FLOOR
        du = max(0.0, abs(u) - p['half'])
        dz = max(0.0, hz - HEAD_C)
        dd = math.hypot(du, dz)
        d = min(d, dd)
    return smooth(0.15, 1.7, d)


def strata(theta, z):
    """radial offset (m, + = outward / recess, - = inward / overhang) of the wall profile at height z."""
    h = z - FLOOR
    ph = noise.noise(Vector((math.cos(theta) * 2.1, math.sin(theta) * 2.1, 7.3)))
    ph2 = noise.noise(Vector((math.cos(theta) * 3.3 + 5, math.sin(theta) * 3.3, 1.1)))
    l1 = 1.25 + 0.35 * ph                       # knee ledge (rock shelf) height
    l2 = 3.3 + 0.6 * ph2                        # overhanging lip
    off = 0.0
    off -= 0.55 * smooth(l1 - 0.35, l1, h) * (1 - smooth(l1 + 0.6, l1 + 1.4, h))     # shelf bulge
    off += 0.45 * smooth(l1 + 0.9, l1 + 1.6, h) * (1 - smooth(l2 - 0.2, l2, h))      # recess under the lip
    off -= 0.5 * smooth(l2 - 0.15, l2 + 0.3, h) * (1 - smooth(l2 + 1.5, l2 + 2.6, h))  # overhang lip
    off += 0.25 * smooth(4.5, 6.2, h)                                                  # shoulder before the vault
    return off


def crag(p, amp):
    """ridged + faceted noise along the surface normal; p world."""
    q = Vector((p.x * 0.23, p.y * 0.23, p.z * 0.31))
    r = noise.ridged_multi_fractal(q, 0.9, 2.1, 4, 0.0, 2.0, noise_basis='PERLIN_ORIGINAL')
    f = noise.fractal(q * 2.3 + Vector((3, 1, 7)), 0.6, 2.0, 3, noise_basis='PERLIN_ORIGINAL')
    return amp * (0.55 * (r - 0.9) + 0.45 * f)


# ------------------------------------------------------------------------------------------------ columns
def columns(n=200):
    """list of column dicts: theta, base point fn (2D, at the wall radius) and the horizontal normal.
    Portal windows get exact columns at the jambs so the openings are clean."""
    win = []
    for pid, p in PORTALS.items():
        h = p['half']
        us = [-h - 2.4, -h - 1.6, -h - 0.9, -h - 0.35, -h] + [-h + 2 * h * k / 6 for k in range(1, 6)] + \
             [h, h + 0.35, h + 0.9, h + 1.6, h + 2.4]
        cols = []
        for u in us:
            pt = Vector((p['at'][0], p['at'][1], 0)) + p['t'] * u
            th = math.atan2(pt.y - CY, pt.x - CX)
            cols.append(dict(theta=th, pid=pid, u=u))
        win.append((cols[0]['theta'], cols[-1]['theta'], cols, pid))
    out = []
    for k in range(n):
        th = wrap(-math.pi + 2 * math.pi * k / n)
        if any(wrap(th - a) >= -0.004 and wrap(b - th) >= -0.004 for a, b, _, _ in win):
            continue
        out.append(dict(theta=th, pid=None, u=None))
    for _, _, cols, _ in win:
        out += cols
    out.sort(key=lambda c: (c['theta'] - math.pi / 2) % (2 * math.pi))     # seam at north, away from both portals
    return out


def r_base(theta):
    """plan radius of the wall's reference circle (portals pull it to the portal point radius)."""
    r = R0 + 0.35 * noise.noise(Vector((math.cos(theta) * 1.4, math.sin(theta) * 1.4, 2.0)))
    for p in PORTALS.values():
        dt = abs(wrap(theta - p['theta']))
        r += (p['r'] - r) * (1 - smooth(0.16, 0.42, dt))
    return r


def col_frame(c):
    """(base point on the reference wall at the column, horizontal inward-normal (towards the room))"""
    th = c['theta']
    rad = Vector((math.cos(th), math.sin(th), 0))
    circ = Vector((CX, CY, 0)) + rad * r_base(th)
    if c['pid'] is None:
        return circ, -rad
    p = PORTALS[c['pid']]
    plane = Vector((p['at'][0], p['at'][1], 0)) + p['t'] * c['u']
    s = smooth(p['half'] + 0.2, p['half'] + 2.4, abs(c['u']))
    base = plane.lerp(circ, s)
    nrm = (-p['ax']).lerp(-rad, s).normalized()
    return base, nrm


# ------------------------------------------------------------------------------------------------ shell
def build_shell(seed=1, keep_out=()):
    """returns (wall_bm, dome_bm, info). info: columns, wall verts grid, spring ring, hole boundary per portal.
    keep_out: [(x, y, radius)] where the rock may not bulge into the room (pavilion backs)."""
    cols = columns()
    nc = len(cols)
    wall = bmesh.new()
    grid = []
    for ci, c in enumerate(cols):
        base, nin = col_frame(c)
        th = c['theta']
        colv = []
        for ri, z in enumerate(WALL_ROWS):
            d = _portal_damp(base.x, base.y, z)
            off = strata(th, z) * d
            # floor contact: no inward crawl at the base, wall foot sits at the reference radius
            p = Vector((base.x, base.y, z))
            amp = (0.25 + 0.75 * smooth(-19.9, -19.0, z)) * 0.95
            n = crag(p, amp) * d
            if ri == 0:
                n = max(-0.15, min(0.25, n))
            dd = off + n
            if dd < 0 and keep_out and z < FLOOR + 5.5:
                kf = min(smooth(rr, rr + 1.8, math.hypot(p.x - kx, p.y - ky)) for kx, ky, rr in keep_out)
                dd *= kf
            pos = p - nin * dd                           # + offset = outward (away from the room)
            if c['pid'] is not None and ri <= HEAD_ROW:
                pr = PORTALS[c['pid']]
                if abs(c['u']) <= pr['half'] + 1e-6 and ri == HEAD_ROW:
                    t = c['u'] / pr['half']
                    pos.z = FLOOR + HEAD + (HEAD_C - HEAD) * math.sqrt(max(0.0, 1 - t * t))
            colv.append(wall.verts.new(pos))
        grid.append(colv)
    nr = len(WALL_ROWS)
    holes = {pid: [] for pid in PORTALS}
    hole_cols = {pid: [ci for ci, c in enumerate(cols) if c['pid'] == pid and abs(c['u']) <= PORTALS[pid]['half'] + 1e-6]
                 for pid in PORTALS}
    for ci in range(nc):
        cj = (ci + 1) % nc
        for ri in range(nr - 1):
            skip = False
            for pid, hc in hole_cols.items():
                if ci in hc and cj in hc and ri < HEAD_ROW:
                    skip = True
            if skip:
                continue
            # winding so the normal faces the room (inward)
            wall.faces.new((grid[ci][ri], grid[ci][ri + 1], grid[cj][ri + 1], grid[cj][ri]))
    # portal reveals (rock lining from the opening edge outwards along the corridor axis)
    for pid, hc in hole_cols.items():
        p = PORTALS[pid]
        cL, cR = hc[0], hc[-1]
        loop = [grid[cL][ri] for ri in range(0, HEAD_ROW + 1)] + [grid[ci][HEAD_ROW] for ci in hc[1:-1]] + \
               [grid[cR][ri] for ri in range(HEAD_ROW, -1, -1)]
        outer = []
        g = noise
        for k, v in enumerate(loop):
            q = v.co + p['ax'] * p['depth']
            # slight flare and roughness on the lining away from the inner edge
            rel = v.co - Vector((p['at'][0], p['at'][1], v.co.z))
            u = rel.dot(p['t'])
            jit = 0.08 * g.noise(q * 1.7)
            q += p['t'] * (math.copysign(0.12, u) if abs(u) > 0.5 else 0.0) + Vector((0, 0, 0.1 if v.co.z > FLOOR + 1 else 0))
            q += p['t'] * jit
            outer.append(wall.verts.new(q))
        for k in range(len(loop) - 1):
            wall.faces.new((loop[k], outer[k], outer[k + 1], loop[k + 1]))
        holes[pid] = dict(inner=[v.co.copy() for v in loop], outer=[v.co.copy() for v in outer])
    _orient_inward(wall)
    # dome: elliptical vault from the spring ring to the crown
    dome = bmesh.new()
    ring_prev = [dome.verts.new(grid[ci][-1].co) for ci in range(nc)]
    first = ring_prev
    for a in DOME_ALPHAS:
        al = math.radians(a)
        ring = []
        for ci, c in enumerate(cols):
            sp = grid[ci][-1].co
            rel = Vector((sp.x - CX, sp.y - CY, 0))
            rr = rel.length
            rad = rel / rr
            r = rr * math.cos(al)
            z = SPRING + (CROWN - SPRING) * math.sin(al)
            p = Vector((CX, CY, 0)) + rad * r + Vector((0, 0, z))
            # ellipse normal (pointing into the room = down / inward)
            nrm = Vector((rad.x * math.cos(al) / R0, rad.y * math.cos(al) / R0, math.sin(al) / (CROWN - SPRING))).normalized()
            amp = 0.55 * (1 - smooth(10, 60, a)) + 0.22
            p += nrm * crag(p, amp)
            ring.append(dome.verts.new(p))
        for ci in range(nc):
            cj = (ci + 1) % nc
            dome.faces.new((ring_prev[ci], ring[ci], ring[cj], ring_prev[cj]))
        ring_prev = ring
    top = dome.verts.new((CX, CY, CROWN + 0.05 * noise.noise(Vector((1, 2, 3)))))
    for ci in range(nc):
        cj = (ci + 1) % nc
        dome.faces.new((ring_prev[ci], top, ring_prev[cj]))
    _orient_inward(dome)
    spring = [grid[ci][-1].co.copy() for ci in range(nc)]
    base_ring = [grid[ci][0].co.copy() for ci in range(nc)]
    return wall, dome, dict(cols=cols, spring=spring, base=base_ring, holes=holes, hole_cols=hole_cols)


def _orient_inward(bm):
    """consistent winding, then flip everything if most faces point away from the room axis."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    score = 0.0
    for f in bm.faces:
        c = f.calc_center_median()
        to_axis = Vector((CX - c.x, CY - c.y, (-12.0 - c.z) * 0.6))
        score += f.normal.dot(to_axis.normalized()) * f.calc_area()
    if score < 0:
        for f in bm.faces:
            f.normal_flip()


# ------------------------------------------------------------------------------------------------ floor / basin / water
def water_outline(S):
    w = next(w for w in S['water'] if w['id'] == 'w_mirror')
    return [tuple(p) for p in w['footprint']]


def outline_r(outline):
    """theta -> radius of the (star-shaped) water outline about the pool centre, linear in theta."""
    pts = sorted(((math.atan2(y - CY, x - CX), math.hypot(x - CX, y - CY)) for x, y in outline))
    def f(th):
        th = wrap(th)
        for k in range(len(pts)):
            a0, r0 = pts[k - 1]; a1, r1 = pts[k]
            if k == 0:
                a0 -= 2 * math.pi
            if a0 <= th <= a1:
                t = (th - a0) / (a1 - a0)
                return r0 + (r1 - r0) * t
        a0, r0 = pts[-1]; a1, r1 = pts[0]
        a1 += 2 * math.pi
        t = (th - a0) / (a1 - a0) if th >= a0 else (th + 2 * math.pi - a0) / (a1 - a0)
        return r0 + (r1 - r0) * t
    return f


def build_floor(S, info, n=192):
    """floor annulus: water edge -> wall foot (+0.6 m under the rock); flat at FLOOR, fillet rising at the wall."""
    rw = outline_r(water_outline(S))
    bm = bmesh.new()
    fr = [0.0, 0.25, 0.85, 1.6, 2.6, 3.6, 4.6, 5.5, 6.2, 6.7]       # metres out from the water edge
    rings = []
    for k in range(n):
        th = -math.pi + 2 * math.pi * k / n
        r_in = rw(th)
        r_wall = _wall_foot_r(info, th)
        r_end, inport, pdamp = r_wall + 0.7, False, 1.0
        dirv = Vector((math.cos(th), math.sin(th), 0))
        for p in PORTALS.values():
            den = dirv.dot(p['ax'])
            if den <= 0.2:
                continue
            rp = (Vector((p['at'][0] - CX, p['at'][1] - CY, 0))).dot(p['ax']) / den
            hit = Vector((CX, CY, 0)) + dirv * rp
            u = (hit - Vector((p['at'][0], p['at'][1], 0))).dot(p['t'])
            pdamp = min(pdamp, smooth(p['half'] + 0.3, p['half'] + 2.0, abs(u)))
            if abs(u) <= p['half'] + 0.3:
                r_end, inport = rp, True
        ring = []
        for j, f in enumerate(fr):
            r = r_in + f * (r_end - r_in) / fr[-1] if inport else r_in + f
            last = j == len(fr) - 1
            if last and not inport:
                r = max(r, r_end)
            z = FLOOR
            if r > r_wall - 0.8 and not inport:
                z += 0.28 * pdamp * smooth(r_wall - 0.8, r_wall + 0.4, r)   # fillet into the wall foot
            if j > 0 and r > r_in + 4.8 and not inport:
                z += 0.03 * noise.noise(Vector((math.cos(th) * 9, math.sin(th) * 9, r)))
            ring.append(bm.verts.new((CX + r * math.cos(th), CY + r * math.sin(th), z)))
        rings.append(ring)
    for k in range(n):
        a, b = rings[k], rings[(k + 1) % n]
        for j in range(len(fr) - 1):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    # portal floors: under each reveal, out to the reveal depth
    for pid, p in PORTALS.items():
        at = Vector((p['at'][0], p['at'][1], FLOOR))
        h = p['half'] + 0.3
        quads = []
        for v0, v1 in ((0.0, p['depth'] + 0.2),):
            q = [at + p['t'] * (-h) + p['ax'] * v0, at + p['t'] * h + p['ax'] * v0,
                 at + p['t'] * h + p['ax'] * v1, at + p['t'] * (-h) + p['ax'] * v1]
            vs = [bm.verts.new(x) for x in q]
            f = bm.faces.new(vs)
    face_up(bm)
    return bm


def face_up(bm):
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()


def _wall_foot_r(info, th):
    best, br = 9, R0
    for p in info['base']:
        a = math.atan2(p.y - CY, p.x - CX)
        d = abs(wrap(a - th))
        if d < best:
            best, br = d, math.hypot(p.x - CX, p.y - CY)
    return br


def build_basin(S, n=192):
    rw = outline_r(water_outline(S))
    bm = bmesh.new()
    prof = [(0.0, FLOOR), (-0.03, -20.18), (-0.12, -20.6), (-0.3, -21.15), (-0.6, BED_Z), (-1.6, BED_Z)]
    rings = []
    for k in range(n):
        th = -math.pi + 2 * math.pi * k / n
        r0 = rw(th)
        ring = [bm.verts.new((CX + (r0 + dr) * math.cos(th), CY + (r0 + dr) * math.sin(th), z)) for dr, z in prof]
        rings.append(ring)
    for k in range(n):
        a, b = rings[k], rings[(k + 1) % n]
        for j in range(len(prof) - 1):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    # bed: concentric rings to the centre
    inner = [rings[k][-1] for k in range(n)]
    for rr in (0.75, 0.5, 0.25):
        ring = []
        for k in range(n):
            co = inner[k].co
            ring.append(bm.verts.new((CX + (co.x - CX) * rr / (rr + 0.25), CY + (co.y - CY) * rr / (rr + 0.25), BED_Z)))
        for k in range(n):
            bm.faces.new((inner[k], inner[(k + 1) % n], ring[(k + 1) % n], ring[k]))
        inner = ring
    c = bm.verts.new((CX, CY, BED_Z))
    for k in range(n):
        bm.faces.new((inner[k], inner[(k + 1) % n], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:                      # face up / into the pool
        cc = f.calc_center_median()
        if f.normal.dot(Vector((CX - cc.x, CY - cc.y, 3.0))) < 0:
            f.normal_flip()
    return bm


def build_water(S):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, WATER_Z)) for x, y in water_outline(S)]
    f = bm.faces.new(vs)
    face_up(bm)
    bmesh.ops.triangulate(bm, faces=[f])
    return bm


# ------------------------------------------------------------------------------------------------ deck ring
def build_deck(r_in=12.85, r_out=15.35, board=0.14, gap=0.012, thick=0.045, seg_len=3.6, gaps=()):
    """hinoki boardwalk ring: tangential boards with staggered butt joints over a fascia beam; `gaps` = list
    of (theta, half_width_m) where the deck is cut (stair head, portal path)."""
    bm = bmesh.new()
    top = FLOOR + 0.02
    nb = int((r_out - r_in) / (board + gap))
    for b in range(nb):
        r0 = r_in + b * (board + gap)
        r1 = r0 + board
        rm = (r0 + r1) / 2
        circ = 2 * math.pi * rm
        nseg = max(8, round(circ / seg_len))
        off = ((b * 0.37) % 1.0) * (2 * math.pi / nseg)
        for s in range(nseg):
            a0 = off + 2 * math.pi * s / nseg + (0.004 / rm)
            a1 = off + 2 * math.pi * (s + 1) / nseg - (0.004 / rm)
            # cut at gaps
            bad = False
            for th, hw in gaps:
                am = (a0 + a1) / 2
                if abs(wrap(am - th)) * rm < hw + (a1 - a0) * rm / 2:
                    bad = True
            if bad:
                continue
            m = 4
            ring_t, ring_b = [], []
            for i in range(m + 1):
                a = a0 + (a1 - a0) * i / m
                ca, sa = math.cos(a), math.sin(a)
                vt = [bm.verts.new((CX + r * ca, CY + r * sa, top - (0.004 if e else 0))) for r, e in ((r0, 1), (r0 + 0.006, 0), (r1 - 0.006, 0), (r1, 1))]
                vb = [bm.verts.new((CX + r * ca, CY + r * sa, top - thick)) for r in (r0, r1)]
                ring_t.append(vt); ring_b.append(vb)
            for i in range(m):
                A, B = ring_t[i], ring_t[i + 1]
                for j in range(3):
                    bm.faces.new((A[j], B[j], B[j + 1], A[j + 1]))
                bm.faces.new((ring_b[i][0], ring_b[i + 1][0], B[0], A[0]))      # inner side
                bm.faces.new((A[3], B[3], ring_b[i + 1][1], ring_b[i][1]))      # outer side
            for i, sgn in ((0, 1), (m, -1)):
                T, Bt = ring_t[i], ring_b[i]
                f = bm.faces.new((Bt[0], T[0], T[1], T[2], T[3], Bt[1]))
    # fascia beam on the pool side and a sill beam at the back (jointed edge members)
    for r, hgt, w in ((r_in - 0.06, 0.16, 0.08), (r_out + 0.05, 0.09, 0.07)):
        n = 160
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            ca, sa = math.cos(a), math.sin(a)
            gapped = any(abs(wrap(a - th)) * r < hw for th, hw in gaps)
            ring.append(None if gapped else [bm.verts.new((CX + (r + dr) * ca, CY + (r + dr) * sa, z))
                                             for dr, z in ((-w / 2, FLOOR - 0.02), (-w / 2, top - 0.005), (w / 2, top - 0.005), (w / 2, FLOOR - 0.02))])
        for i in range(n):
            A, B = ring[i], ring[(i + 1) % n]
            if A is None or B is None:
                continue
            for j in range(3):
                bm.faces.new((A[j], A[j + 1], B[j + 1], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# ------------------------------------------------------------------------------------------------ glowworm conform
def conform_glowworm(obj, shell_objs, gap=0.03, r_max=18.6, z_min=-13.6):
    """Move every glowworm point / thread vertex onto the dome: new z = dome surface above (x, y) minus the
    vertex's depth under the patch attach plane. Points with no dome above, outside r_max or below z_min are
    removed (with their threads)."""
    bvh = bvh_of(shell_objs)
    me = obj.data
    attach = float(obj['kz_attach_z']) if 'kz_attach_z' in obj else max(v.co.z for v in me.vertices)
    mw = obj.matrix_world
    bm = bmesh.new(); bm.from_mesh(me)
    kill = []
    inv = mw.inverted()
    spr = bm.verts.layers.float.get('kz_sprite')
    for v in bm.verts:
        if spr is not None and v[spr] <= 0.0:          # rock skin vertex (the dome carries the rock)
            kill.append(v); continue
        w = mw @ v.co
        depth = attach - v.co.z
        r = math.hypot(w.x - CX, w.y - CY)
        if r > r_max:
            kill.append(v); continue
        hit = bvh.ray_cast(Vector((w.x, w.y, -15.0)), Vector((0, 0, 1)), 20.0)
        if hit[0] is None or hit[0].z < z_min:
            kill.append(v); continue
        nw = Vector((w.x, w.y, hit[0].z - gap - depth))
        v.co = inv @ nw
    # a thread whose top or bead died: remove both ends
    dead = set(kill)
    for e in bm.edges:
        if e.verts[0] in dead or e.verts[1] in dead:
            dead.update(e.verts)
    bmesh.ops.delete(bm, geom=list(dead), context='VERTS')
    bm.to_mesh(me); bm.free()
    me.update()
    return len(me.vertices)


def conform_glowworm_wall(obj, shell_objs, R_ref=19.0, z0=-16.0, gap=0.04, skip_portals=True):
    """Wrap a long thin glowworm patch round the wall: local x -> arc length (theta = x / R_ref), local y -> height
    (z = z0 + y + D/2), the point sits on the wall (horizontal ray from the room axis) and its thread hangs straight
    down by its depth under the attach plane. Skin vertices and points inside the portal heads are removed."""
    bvh = bvh_of(shell_objs)
    me = obj.data
    attach = float(obj['kz_attach_z'])
    D = float(json.loads(obj['kz_params'])['d'])
    mw = obj.matrix_world
    inv = mw.inverted()
    bm = bmesh.new(); bm.from_mesh(me)
    spr = bm.verts.layers.float.get('kz_sprite')
    loc = mw.translation
    kill = []
    for v in bm.verts:
        if spr is not None and v[spr] <= 0.0:
            kill.append(v); continue
        lx, ly = v.co.x, v.co.y            # object is placed with zero rotation at (CX, CY, z)
        th = lx / R_ref
        z = z0 + ly + D / 2
        depth = attach - v.co.z
        d = Vector((math.cos(th), math.sin(th), 0))
        o = Vector((CX, CY, z))
        hit = bvh.ray_cast(o, d, 30.0)
        if hit[0] is None or hit[1].dot(d) > 0.2:
            kill.append(v); continue
        p = hit[0] - d * gap - Vector((0, 0, depth))
        if skip_portals and _portal_damp(p.x, p.y, p.z + depth) < 0.6:
            kill.append(v); continue
        v.co = inv @ p
    dead = set(kill)
    for e in bm.edges:
        if e.verts[0] in dead or e.verts[1] in dead:
            dead.update(e.verts)
    bmesh.ops.delete(bm, geom=list(dead), context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    return len(me.vertices)


def bvh_of(objs):
    bm = bmesh.new()
    for o in objs:
        tmp = bmesh.new()
        dg = bpy.context.evaluated_depsgraph_get()
        tmp.from_object(o, dg) if o.modifiers else tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        me = bpy.data.meshes.new('_tmp'); tmp.to_mesh(me); tmp.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


# ------------------------------------------------------------------------------------------------ walk mesh
def build_walk(S, info, floor_obj, basin_obj, stair_obj, obstacles, gaps_curb):
    """kz_walk mesh (positions only): floor top (copied from the floor), basin, stair treads + risers from
    kz_stair, curb (0.3 m) round the deep water except at the stair head, wall band (2.5 m) as collision,
    obstacle prisms (pavilion podiums, rock clusters) as vertical walls."""
    bm = bmesh.new()
    for o in (floor_obj, basin_obj):
        me = o.data
        vs = [bm.verts.new(o.matrix_world @ v.co) for v in me.vertices]
        for p in me.polygons:
            try:
                bm.faces.new([vs[i] for i in p.vertices])
            except ValueError:
                pass
    # stair: treads and risers from kz_stair (local: climbs towards -Y; bottom nosing +Y)
    st = json.loads(stair_obj['kz_stair'])
    M = stair_obj.matrix_world
    n, R, T = st['steps'], st['riser'], st['tread']
    hw = 0.8
    y_top = st['top_nosing'][1]; z_top = st['top_nosing'][2]
    for k in range(n + 1):
        y0 = y_top + k * T
        y1 = y0 + T if k < n else y0 + 1.2
        z = z_top - k * R
        q = [M @ Vector((-hw, y0, z)), M @ Vector((hw, y0, z)), M @ Vector((hw, y1, z)), M @ Vector((-hw, y1, z))]
        bm.faces.new([bm.verts.new(x) for x in q])
        if k < n:
            q = [M @ Vector((-hw, y1, z)), M @ Vector((hw, y1, z)), M @ Vector((hw, y1, z - R)), M @ Vector((-hw, y1, z - R))]
            bm.faces.new([bm.verts.new(x) for x in q])
    # head landing from the rim to the first tread
    q = [M @ Vector((-hw, y_top - 1.0, z_top)), M @ Vector((hw, y_top - 1.0, z_top)), M @ Vector((hw, y_top, z_top)), M @ Vector((-hw, y_top, z_top))]
    bm.faces.new([bm.verts.new(x) for x in q])
    # curb at the deep water
    rw = outline_r(water_outline(S))
    nn = 192
    prev = None
    for k in range(nn + 1):
        th = -math.pi + 2 * math.pi * k / nn
        x = CX + (rw(th) + 0.05) * math.cos(th); y = CY + (rw(th) + 0.05) * math.sin(th)
        gap = any(abs(wrap(th - a)) * 12.0 < h for a, h in gaps_curb)
        cur = None if gap else (bm.verts.new((x, y, FLOOR)), bm.verts.new((x, y, FLOOR + 0.3)))
        if prev and cur:
            bm.faces.new((prev[0], cur[0], cur[1], prev[1]))
        prev = cur
    # wall band: the shell's bottom rows as collision (copied from the wall mesh, up to 2.6 m)
    for o in obstacles:
        kind = o[0]
        if kind == 'prism':
            pts, z0, z1 = o[1], o[2], o[3]
            ring = [(bm.verts.new((x, y, z0)), bm.verts.new((x, y, z1))) for x, y in pts]
            for i in range(len(ring)):
                a, b = ring[i], ring[(i + 1) % len(ring)]
                bm.faces.new((a[0], b[0], b[1], a[1]))
            bm.faces.new([r[1] for r in ring])
        elif kind == 'mesh':
            ob, zcap = o[1], o[2]
            me = ob.data
            vs = [bm.verts.new(ob.matrix_world @ v.co) for v in me.vertices]
            for p in me.polygons:
                if all((ob.matrix_world @ me.vertices[i].co).z <= zcap for i in p.vertices):
                    try:
                        bm.faces.new([vs[i] for i in p.vertices])
                    except ValueError:
                        pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    return bm
