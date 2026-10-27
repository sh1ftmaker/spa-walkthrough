"""Geometry helpers for gen_pavilion_engawa: the tiled roof (a self-contained 'roof_tiled' builder that a later
roof_tiled generator can adopt) and timber joinery bits.

Roof model: the eave outline is a rectangle (half extents hw x hd, tile edge at z_e). Every point of the roof
plane has a distance d to the nearest eave it drains to; the surface height is
        z(d) = z_e + rise * (d / hd) ** p                      (p > 1: concave, flat at the eave, steep at the top)
              + up * a ** 3 * (1 - d / hd) ** 2               (sori: the eave line sweeps up into the corners)
where a in 0..1 is the position along that eave (1 = corner).  Styles:
    'hip'      yosemune: four slopes, hip ridges on the diagonals, short main ridge.
    'irimoya'  hip below the 'gable line' d = dg, a gable roof above it; vertical gable boards (tsuma) with
               bargeboards (hafu) where the two meet - the classic temple / pavilion roof.
    'gable'    kirizuma: two slopes, bargeboards on the ends.
The surface is meshed as concentric eave rings (so hip creases are exact edges), with semi-round tile ribs
(marugawara) swept over it at the tile pitch, round eave-end tiles (tomoe discs), noshi-stacked ridges with
onigawara end blocks, an eave fascia (kayaoi), a soffit and rafter ends (taruki).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import kzgeo_bridge_arched as kg

Z = Vector((0, 0, 1))


class RoofShape:
    def __init__(self, hw, hd, z_e, rise, p=1.35, up=0.25, style='irimoya', dg=None):
        self.hw, self.hd, self.z_e, self.rise, self.p, self.up, self.style = hw, hd, z_e, rise, p, up, style
        if style == 'hip':
            dg = hd
        elif style == 'gable':
            dg = 0.0
        self.dg = hd * 0.55 if dg is None else dg

    def dist(self, x, y):
        """(d, side) side 'f' = drains to the front/back eave, 's' = to an end eave"""
        d_f = self.hd - abs(y)
        if self.style == 'gable' or abs(x) <= self.hw - self.dg:
            return d_f, 'f'
        d_s = self.hw - abs(x)
        return (d_f, 'f') if d_f <= d_s else (d_s, 's')

    def z(self, x, y, d=None, side=None):
        if d is None:
            d, side = self.dist(x, y)
        t = max(0.0, min(1.0, d / self.hd))
        if self.style == 'gable':
            a = abs(x) / self.hw
        elif side == 'f':
            a = abs(x) / max(1e-6, self.hw - d)
        else:
            a = abs(y) / max(1e-6, self.hd - d)
        a = min(1.0, a)
        k = 3 if side == 'f' else 4          # the short end eaves sweep up later (softer)
        return self.z_e + self.rise * t ** self.p + self.up * a ** k * (1 - t) ** 2

    def zd(self, d):
        """height along the middle of a long side (no sori)"""
        return self.z_e + self.rise * max(0.0, min(1.0, d / self.hd)) ** self.p


# ------------------------------------------------------------------ roof
def _face(bm, vs, mi, out):
    if len(set(vs)) < 3:
        return None
    try:
        f = bm.faces.new(vs)
    except ValueError:
        return None
    f.material_index = mi
    out.append(f)
    return f


def roof(mb, S, R, mats, r, wall=None):
    """Build the roof into mb. S = RoofShape. R = resolution dict:
        rings, n_long, n_short, up_rows, ribs (bool), rib_segs, rib_prof (2..4), discs (bool), rafters (bool),
        fascia (bool), soffit (bool), ridge_prof ('full'|'box'), teeth (eave edge zig-zag for low LODs), tp (tile pitch)
    mats: tile, ridge, wood, wood_d.   wall = dict(ov=front overhang, ovs=side overhang) for soffit / rafter depth.
    Returns dict(ridge_z, gable_x)."""
    bm = mb.bm
    tile, ridge_mi, wood, wood_d = mats['tile'], mats['ridge'], mats['wood'], mats['wood_d']
    hw, hd, dg = S.hw, S.hd, S.dg
    faces = []
    lay = mb._mark_old()
    nl, ns = R['n_long'], R['n_short']

    # ---- surface
    def ring_pts(d):
        cx, cy = hw - d, hd - d
        pts = []
        for i in range(nl):                                  # front: left -> right
            pts.append((-cx + 2 * cx * i / nl, cy, 'f'))
        for i in range(ns):                                  # right end: front -> back
            pts.append((cx, cy - 2 * cy * i / ns, 's'))
        for i in range(nl):                                  # back: right -> left
            pts.append((cx - 2 * cx * i / nl, -cy, 'f'))
        for i in range(ns):                                  # left end: back -> front
            pts.append((-cx, -cy + 2 * cy * i / ns, 's'))
        return pts

    if S.style != 'gable':
        nr = R['rings']
        d_top = dg if S.style == 'irimoya' else hd - 1e-4
        rings = []
        for k in range(nr + 1):
            d = d_top * (k / nr) ** 0.92
            row = []
            for x, y, side in ring_pts(d):
                row.append(bm.verts.new((x, y, S.z(x, y, d, side))))
            rings.append(row)
        n = len(rings[0])
        for k in range(nr):
            A, B = rings[k], rings[k + 1]
            for i in range(n):
                i2 = (i + 1) % n
                _face(bm, (A[i], A[i2], B[i2], B[i]), tile, faces)
        top_ring = rings[-1]
        if S.style == 'irimoya':
            # upper gable strips between x = +-(hw - dg): rows from d = dg to hd
            nu = R['up_rows']
            front = top_ring[0:nl + 1]
            back = top_ring[nl + ns:2 * nl + ns + 1]           # right -> left
            back = back[::-1]                                  # left -> right
            prev_f, prev_b = front, back
            for j in range(1, nu + 1):
                d = dg + (hd - dg) * j / nu
                cx = hw - dg
                if j < nu:
                    row_f = [bm.verts.new((-cx + 2 * cx * i / nl, hd - d, S.z(-cx + 2 * cx * i / nl, hd - d, d, 'f')))
                             for i in range(nl + 1)]
                    row_b = [bm.verts.new((-cx + 2 * cx * i / nl, -(hd - d), S.z(-cx + 2 * cx * i / nl, hd - d, d, 'f')))
                             for i in range(nl + 1)]
                else:
                    row_f = [bm.verts.new((-cx + 2 * cx * i / nl, 0.0, S.z(-cx + 2 * cx * i / nl, 0.0, hd, 'f')))
                             for i in range(nl + 1)]
                    row_b = row_f
                for i in range(nl):
                    _face(bm, (prev_f[i], prev_f[i + 1], row_f[i + 1], row_f[i]), tile, faces)
                    _face(bm, (prev_b[i + 1], prev_b[i], row_b[i], row_b[i + 1]), tile, faces)
                prev_f, prev_b = row_f, row_b
            # cap the top ring's end sides (flat ledge under the gable) - the ring at dg has end sides at x = +-(hw-dg)
    else:
        nu = R['rings'] + R['up_rows']
        rows_f, rows_b = [], []
        for j in range(nu + 1):
            d = hd * j / nu
            row_f = [bm.verts.new((-hw + 2 * hw * i / nl, hd - d, S.z(-hw + 2 * hw * i / nl, hd - d, d, 'f')))
                     for i in range(nl + 1)]
            if j == nu:
                row_b = row_f
            else:
                row_b = [bm.verts.new((-hw + 2 * hw * i / nl, -(hd - d), S.z(-hw + 2 * hw * i / nl, hd - d, d, 'f')))
                         for i in range(nl + 1)]
            rows_f.append(row_f); rows_b.append(row_b)
        for j in range(nu):
            for i in range(nl):
                _face(bm, (rows_f[j][i], rows_f[j][i + 1], rows_f[j + 1][i + 1], rows_f[j + 1][i]), tile, faces)
                _face(bm, (rows_b[j][i + 1], rows_b[j][i], rows_b[j + 1][i], rows_b[j + 1][i + 1]), tile, faces)
    new_v = list({v for f in faces for v in f.verts})
    bmesh.ops.remove_doubles(bm, verts=new_v, dist=0.003)
    faces = [f for f in faces if f.is_valid]

    th = R.get('thick', 0.16)
    # ---- tile ribs + eave discs
    tp = R['tp']
    rr = tp * 0.3
    if R['ribs']:
        nseg = R['rib_segs']
        npf = R['rib_prof']
        prof = [(rr * math.cos(math.pi * k / npf), rr * 0.85 * math.sin(math.pi * k / npf)) for k in range(npf + 1)]

        def rib(pts, eave_dir):
            kg.sweep(mb, pts, prof, tile, caps=False, closed_prof=False)
            if R['discs']:
                p0, t0 = pts[0], (pts[0] - pts[1]).normalized()
                disc(mb, p0 + t0 * 0.03 + Z * rr * 0.2, t0, rr * 1.3, 0.06, tile, R['disc_n'])

        def lift(x, y, d, side):
            return Vector((x, y, S.z(x, y, d, side) + rr * 0.05))

        nx = int((2 * hw) / tp)
        x0 = -hw + (2 * hw - (nx - 1) * tp) / 2
        for i in range(nx):
            x = x0 + i * tp
            if S.style == 'gable' or abs(x) <= hw - dg:
                dmax = hd - 0.01
            else:
                dmax = hw - abs(x) - rr * 1.1
            if dmax < tp * 0.8:
                continue
            for sy in (1, -1):
                pts = [lift(x, sy * (hd - dmax * j / nseg), dmax * j / nseg, 'f') for j in range(nseg + 1)]
                rib(pts, Vector((0, sy, 0)))
        if S.style != 'gable':
            ny = int((2 * hd) / tp)
            y0 = -hd + (2 * hd - (ny - 1) * tp) / 2
            for j in range(ny):
                y = y0 + j * tp
                dmax = min(hd - abs(y) - rr * 1.1, dg - 0.01)
                if dmax < tp * 0.8:
                    continue
                for sx in (1, -1):
                    pts = [lift(sx * (hw - dmax * k / nseg), y, dmax * k / nseg, 's') for k in range(nseg + 1)]
                    rib(pts, Vector((sx, 0, 0)))
    if R.get('teeth'):
        _eave_teeth(mb, S, tile, R['teeth'], th)

    # ---- ridges
    rz = S.z(0, 0, hd, 'f')
    rp = R['ridge_prof']
    if rp == 'full':
        rprof = [(-0.17, -0.06), (0.17, -0.06), (0.17, 0.07), (0.13, 0.1), (0.13, 0.24), (0.09, 0.3), (0.0, 0.33),
                 (-0.09, 0.3), (-0.13, 0.24), (-0.13, 0.1), (-0.17, 0.07)]
        hprof = [(-0.1, -0.05), (0.1, -0.05), (0.1, 0.08), (0.06, 0.13), (-0.06, 0.13), (-0.1, 0.08)]
    elif rp == 'box':
        rprof = [(-0.14, -0.06), (0.14, -0.06), (0.12, 0.2), (-0.12, 0.2)]
        hprof = [(-0.09, -0.05), (0.09, -0.05), (0.08, 0.1), (-0.08, 0.1)]
    else:
        rprof = [(-0.13, -0.08), (0.13, -0.08), (0.0, 0.18)]
        hprof = None
    xr = hw - dg if S.style != 'hip' else hw - hd
    if S.style == 'gable':
        xr = hw + 0.02
    kg.sweep(mb, [Vector((-xr - 0.05, 0, rz)), Vector((xr + 0.05, 0, rz))], rprof, ridge_mi, caps=True)
    oni = []
    if rp != 'tri':
        for sx in (-1, 1):
            # onigawara: tall end block with a raised, chamfered top, leaning out a touch
            base = Vector((sx * (xr + 0.05), 0, rz - 0.05))
            M = kg.frame(base, Vector((sx, 0, 0)))
            # low, blocky onigawara (0.3-0.4 m): Japanese, not a horn
            kg.cbox(mb, M @ Matrix.Translation((0, 0.04, 0.17)), (0.4, 0.13, 0.36), ridge_mi,
                    bevel=0.025 if R['ribs'] else 0.0)
            oni.append(base)
    # hip / descending ridges
    if hprof:
        if S.style in ('hip', 'irimoya'):
            dtop = hd if S.style == 'hip' else dg
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts = []
                    nsg = 6 if R['ribs'] else 2
                    for k in range(nsg + 1):
                        d = dtop * k / nsg
                        x, y = sx * (hw - d), sy * (hd - d)
                        pts.append(Vector((x, y, S.z(x, y, d, 'f') + 0.02)))
                    pts[0] = pts[0] + Vector((sx, sy, 0)).normalized() * 0.03 + Vector((0, 0, 0.01))
                    kg.sweep(mb, pts, hprof, ridge_mi, caps=True)
                    if R['ribs']:
                        # small onigawara at the eave end of each hip ridge
                        Mh = kg.frame(pts[0], Vector((sx, sy, 0.2)))
                        kg.cbox(mb, Mh @ Matrix.Translation((0, 0.02, 0.06)), (0.2, 0.08, 0.17), ridge_mi)
        if S.style in ('irimoya', 'gable'):
            # descending ridges along the gable rakes
            xg = hw - dg if S.style == 'irimoya' else hw
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts = []
                    nsg = 5 if R['ribs'] else 2
                    d0 = dg if S.style == 'irimoya' else 0.0
                    for k in range(nsg + 1):
                        d = d0 + (hd - d0) * k / nsg
                        x, y = sx * (xg - 0.06), sy * (hd - d)
                        pts.append(Vector((x, y, S.z(x, y, d, 'f') + 0.02)))
                    kg.sweep(mb, pts, hprof, ridge_mi, caps=True)

    # ---- gable boards (tsuma) + bargeboards (hafu)
    gable_x = None
    if S.style in ('irimoya', 'gable'):
        xg = (hw - dg - 0.04) if S.style == 'irimoya' else (hw - wall['ovs'] + 0.05)
        gable_x = xg
        d0 = dg if S.style == 'irimoya' else wall['ov']
        nsg = 6 if R['ribs'] else 3
        for sx in (-1, 1):
            top = []
            for k in range(nsg + 1):
                d = d0 + (hd - d0) * k / nsg
                top.append((hd - d, S.z(xg, hd - d, d, 'f') - 0.02))
            base_z = S.z(xg, hd - d0, d0, 'f') if S.style == 'irimoya' else wall['z_beam']
            # polygon in (y, z) at x = sx * xg: front-bottom -> up the front rake -> down the back rake -> back-bottom
            yz = [(hd - d0, base_z)] + top[1:] + [(-y, z) for y, z in top[::-1][1:]] + [(-(hd - d0), base_z)]
            vs = [bm.verts.new((sx * xg, y, z)) for y, z in yz]
            f = _face(bm, vs if sx > 0 else vs[::-1], wood_d, faces)
            # kitsure-goshi: vertical slats on the gable board
            if R['ribs']:
                ymax = hd - d0
                nsl = max(4, int(2 * ymax / 0.16))
                for k in range(1, nsl):
                    y = -ymax + 2 * ymax * k / nsl
                    dd = hd - abs(y)
                    zt = S.z(xg, y, dd, 'f') - 0.04
                    if zt - base_z > 0.06:
                        mb.box((sx * (xg + 0.012), y, (zt + base_z) / 2), (0.02, 0.03, zt - base_z), wood)
            # hafu bargeboards along both rakes, slightly proud of the gable, with a little overrun at the foot
            for sy in (-1, 1):
                pts = [Vector((sx * (xg + 0.04), sy * y, z - 0.02)) for y, z in top]
                if S.style == 'gable':
                    pts = [Vector((sx * (hw + 0.01), sy * (hd - (hd) * k / nsg),
                                   S.z(hw, hd - hd * k / nsg, hd * k / nsg, 'f') - 0.03)) for k in range(nsg + 1)]
                kg.sweep(mb, pts, [(-0.035, -0.16), (0.035, -0.16), (0.035, 0.03), (-0.035, 0.03)], wood_d, caps=True)

    # ---- eave fascia (kayaoi) + soffit + rafters
    if R['fascia']:
        nf = R.get('fascia_n', 6)
        if S.style == 'gable':
            for sy in (-1, 1):
                pts = [Vector((-hw + 2 * hw * i / (nf * 2), sy * hd, S.z(-hw + 2 * hw * i / (nf * 2), sy * hd, 0.0, 'f')))
                       for i in range(nf * 2 + 1)]
                kg.sweep(mb, pts, [(-0.0, -th), (0.07, -th), (0.07, 0.0), (0.0, 0.0)] if sy > 0 else
                         [(-0.07, -th), (0.0, -th), (0.0, 0.0), (-0.07, 0.0)], wood, caps=True)
        else:
            # sample the eave ring densely enough to carry the sori
            pts = []
            corners = [(-hw, hd), (hw, hd), (hw, -hd), (-hw, -hd)]
            for c in range(4):
                (ax, ay), (bx, by) = corners[c], corners[(c + 1) % 4]
                for i in range(nf):
                    t = i / nf
                    x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                    pts.append(Vector((x, y, S.z(x, y, 0.0, 'f' if c % 2 == 0 else 's'))))
            _fascia_loop(mb, pts, th, wood, faces, tile_mi=tile)
    if R['soffit']:
        _soffit(mb, S, wall, th, wood, R, faces)
    if R['rafters']:
        _rafters(mb, S, wall, th, wood, R)
    return dict(ridge_z=rz, gable_x=gable_x)


def disc(mb, c, axis, rad, depth, mi, n=6):
    """round eave-end tile: an n-gon prism of `depth` along `axis`, both faces capped"""
    bm = mb.bm
    axis = Vector(axis).normalized()
    a = axis.cross(Z if abs(axis.z) < 0.95 else Vector((1, 0, 0))).normalized()
    b = axis.cross(a)
    A = [bm.verts.new(c + (a * math.cos(2 * math.pi * k / n + 0.3) + b * math.sin(2 * math.pi * k / n + 0.3)) * rad)
         for k in range(n)]
    B = [bm.verts.new(v.co - axis * depth) for v in A]
    fs = [bm.faces.new(A), bm.faces.new(B[::-1])]
    for k in range(n):
        k2 = (k + 1) % n
        fs.append(bm.faces.new((A[k2], A[k], B[k], B[k2])))
    for f in fs:
        f.material_index = mi
    return fs


def _fascia_loop(mb, pts, th, mi, faces, tile_mi=None, edge=0.07):
    """closed loop fascia board hanging under the eave line: outer face (upper `edge` m = the flat eave-tile
    lip in the tile material, below it the wooden kayaoi board) + bottom + inner face"""
    bm = mb.bm
    n = len(pts)
    top_o = [bm.verts.new(p + Vector((0, 0, 0.0))) for p in pts]
    bot_o = [bm.verts.new(p - Vector((0, 0, th))) for p in pts]
    if tile_mi is not None:
        mid_o = [bm.verts.new(p - Vector((0, 0, edge))) for p in pts]
        for i in range(n):
            j = (i + 1) % n
            _face(bm, (top_o[i], mid_o[i], mid_o[j], top_o[j]), tile_mi, faces)
        top_o = mid_o
    inn = []
    for p in pts:
        dx = -math.copysign(0.09, p.x) if abs(abs(p.x) - max(abs(q.x) for q in pts)) < 1e-4 else 0.0
        dy = -math.copysign(0.09, p.y) if abs(abs(p.y) - max(abs(q.y) for q in pts)) < 1e-4 else 0.0
        inn.append(Vector((dx, dy, 0)))
    bot_i = [bm.verts.new(p - Vector((0, 0, th)) + d) for p, d in zip(pts, inn)]
    top_i = [bm.verts.new(p + d + Vector((0, 0, 0.02))) for p, d in zip(pts, inn)]
    for i in range(n):
        j = (i + 1) % n
        _face(bm, (top_o[i], bot_o[i], bot_o[j], top_o[j]), mi, faces)
        _face(bm, (bot_o[i], bot_i[i], bot_i[j], bot_o[j]), mi, faces)
        _face(bm, (bot_i[i], top_i[i], top_i[j], bot_i[j]), mi, faces)


def _soffit(mb, S, wall, th, mi, R, faces):
    """eave underside: concentric strip from the fascia back to just inside the post line"""
    bm = mb.bm
    hw, hd = S.hw, S.hd
    ov, ovs = wall['ov'], wall['ovs']
    nl, ns = max(2, R['n_long'] // 2), max(2, R['n_short'] // 2)
    rows = []
    for k, (ax, ay) in enumerate(((0.09, 0.09), (ovs + 0.15, ov + 0.15))):
        cx, cy = hw - ax, hd - ay
        row = []
        for i in range(nl):
            x, y = -cx + 2 * cx * i / nl, cy
            row.append((x, y, 'f', ay))
        for i in range(ns):
            x, y = cx, cy - 2 * cy * i / ns
            row.append((x, y, 's', ax))
        for i in range(nl):
            x, y = cx - 2 * cx * i / nl, -cy
            row.append((x, y, 'f', ay))
        for i in range(ns):
            x, y = -cx, -cy + 2 * cy * i / ns
            row.append((x, y, 's', ax))
        vs = []
        for x, y, side, dd in row:
            # soffit height: below the tile surface by th at the eave, a bit more inboard
            if S.style == 'gable' and side == 's':
                zz = S.z(x, y, hd - abs(y), 'f') - th - 0.02
            else:
                zz = S.z(x, y, dd, side) - th - (0.0 if k == 0 else 0.1)
            vs.append(bm.verts.new((x, y, zz)))
        rows.append(vs)
    n = len(rows[0])
    for i in range(n):
        j = (i + 1) % n
        _face(bm, (rows[0][i], rows[1][i], rows[1][j], rows[0][j]), mi, faces)


def _rafters(mb, S, wall, th, mi, R):
    """taruki: square rafter ends under the soffit, perpendicular to each eave, stopped short of the corners"""
    hw, hd = S.hw, S.hd
    ov, ovs = wall['ov'], wall['ovs']
    sp = R.get('rafter_sp', 0.3)
    for side in ('f', 'b', 'r', 'l'):
        if side in ('f', 'b'):
            L, depth, sgn = hw, ov, 1 if side == 'f' else -1
        else:
            L, depth, sgn = hd, ovs, 1 if side == 'r' else -1
        n = int(2 * (L - depth - 0.15) / sp)
        if n < 1:
            continue
        for i in range(n + 1):
            u = -(L - depth - 0.15) + 2 * (L - depth - 0.15) * i / n
            d0, d1 = 0.12, depth + 0.1
            if side in ('f', 'b'):
                p0 = Vector((u, sgn * (hd - d0), 0)); p1 = Vector((u, sgn * (hd - d1), 0))
                z0 = S.z(u, p0.y, d0, 'f') - th - 0.04; z1 = S.z(u, p1.y, d1, 'f') - th - 0.12
            else:
                if S.style == 'gable':
                    continue
                p0 = Vector((sgn * (hw - d0), u, 0)); p1 = Vector((sgn * (hw - d1), u, 0))
                z0 = S.z(p0.x, u, d0, 's') - th - 0.04; z1 = S.z(p1.x, u, d1, 's') - th - 0.12
            a = Vector((p0.x, p0.y, z0)); b = Vector((p1.x, p1.y, z1))
            M = kg.frame((a + b) / 2, a - b)
            kg.cbox(mb, M, (0.06, (a - b).length, 0.075), mi)


def _eave_teeth(mb, S, mi, pitch, th):
    """low-LOD stand-in for the tile ends: a zig-zag band along the eave edge (reads as the tile row)"""
    bm = mb.bm
    hw, hd = S.hw, S.hd
    corners = [(-hw, hd), (hw, hd), (hw, -hd), (-hw, -hd)]
    for c in range(4):
        (ax, ay), (bx, by) = corners[c], corners[(c + 1) % 4]
        if S.style == 'gable' and c % 2 == 1:
            continue
        L = math.hypot(bx - ax, by - ay)
        n = max(2, int(L / pitch))
        out = Vector(((ax + bx) / 2, (ay + by) / 2, 0)).normalized()
        out = Vector((round(out.x), round(out.y), 0)) if abs(out.x) != abs(out.y) else out
        prev = None
        for i in range(n * 2 + 1):
            t = i / (2 * n)
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            z = S.z(x, y, 0.0, 'f' if c % 2 == 0 else 's')
            o = out * (0.05 if i % 2 else 0.0)
            top = bm.verts.new((x + o.x, y + o.y, z + 0.06 + (0.03 if i % 2 else 0)))
            bot = bm.verts.new((x + o.x, y + o.y, z - 0.05))
            if prev:
                f = bm.faces.new((prev[1], bot, top, prev[0]))
                f.material_index = mi
            prev = (top, bot)


def lean_to(mb, side, x_in, x_out, y0, y1, z_top, z_eave, tp, R, mats, r):
    """single-slope tiled lean-to (hisashi) running along y, draining toward x_out (side = sign of x_out - x_in):
    roof sheet, tile ribs with eave discs, fascia with tile lip, soffit. Returns nothing."""
    bm = mb.bm
    tile, wood = mats['tile'], mats['wood']
    nx = 3 if R['ribs'] else 1
    ny = max(2, int((y1 - y0) / 0.8))
    def zf(x):
        t = (x - x_in) / (x_out - x_in)
        return z_top + (z_eave - z_top) * (t ** 0.9)
    rows = []
    for i in range(nx + 1):
        x = x_in + (x_out - x_in) * i / nx
        rows.append([bm.verts.new((x, y0 + (y1 - y0) * j / ny, zf(x))) for j in range(ny + 1)])
    for i in range(nx):
        for j in range(ny):
            q = (rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])
            f = bm.faces.new(q if side > 0 else q[::-1]); f.material_index = tile
    th = 0.14
    if not R['fascia']:
        return
    # fascia with tile lip along the eave, end boards
    for (a, b, mi, dz0, dz1) in ((0, 0.06, tile, 0, 0.06), (0.06, th, wood, 0.06, th)):
        q = [bm.verts.new((x_out, y0, z_eave - dz0)), bm.verts.new((x_out, y1, z_eave - dz0)),
             bm.verts.new((x_out, y1, z_eave - dz1)), bm.verts.new((x_out, y0, z_eave - dz1))]
        f = bm.faces.new(q if side < 0 else q[::-1]); f.material_index = mi
    for y in (y0, y1):
        q = [bm.verts.new((x_in, y, z_top)), bm.verts.new((x_out, y, z_eave)),
             bm.verts.new((x_out, y, z_eave - th)), bm.verts.new((x_in, y, z_top - th))]
        f = bm.faces.new(q); f.material_index = wood
    q = [bm.verts.new((x_in, y0, z_top - th)), bm.verts.new((x_out, y0, z_eave - th)),
         bm.verts.new((x_out, y1, z_eave - th)), bm.verts.new((x_in, y1, z_top - th))]
    f = bm.faces.new(q); f.material_index = wood
    if R['ribs']:
        rr = tp * 0.3
        npf = R['rib_prof']
        prof = [(rr * math.cos(math.pi * k / npf), rr * 0.85 * math.sin(math.pi * k / npf)) for k in range(npf + 1)]
        n = int((y1 - y0) / tp)
        for j in range(n):
            y = y0 + (y1 - y0 - (n - 1) * tp) / 2 + j * tp
            pts = [Vector((x_out + (x_in - x_out) * k / 3, y, zf(x_out + (x_in - x_out) * k / 3) + rr * 0.05)) for k in range(4)]
            kg.sweep(mb, pts, prof, tile, caps=False, closed_prof=False)
            if R['discs']:
                t0 = (pts[0] - pts[1]).normalized()
                disc(mb, pts[0] + t0 * 0.03 + Z * rr * 0.2, t0, rr * 1.3, 0.06, tile, R['disc_n'])
