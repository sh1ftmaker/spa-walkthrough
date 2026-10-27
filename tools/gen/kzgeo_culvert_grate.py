"""kzgeo_culvert_grate: parts for gen_culvert_grate (bronze bar grate flush in paving over a steaming slot).

surround(mb, L, lod, mi_pave, mi_slot)  paving kerb flags around the opening, top at L['H'], seeded joints.
    Inner faces (the slot wall) get mi_slot (wet basalt).
rim(mb, L, lod, mi)                      bronze angle lining the opening: a flat top band flush with the
    paving plus a vertical leg down the slot wall.
bars(mb, L, lod, mi)                     the bar field for the style; returns the bar count.
All numbers come from gen_culvert_grate.layout() (drawn once per seed, before the LOD branch).
"""
import math

import bmesh
from mathutils import Vector

import kzgeo_common as C


def _box(mb, x0, x1, y0, y1, z0, z1, mi, faces='closed'):
    """Axis box. faces='closed' (12 tris), 'open3' (top + two long sides, 6 tris), 'top' (one quad)."""
    bm = mb.bm
    if faces == 'top':
        vs = [bm.verts.new(p) for p in ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        fs = [bm.faces.new(vs)]
    elif faces == 'nobottom':                        # 10 tris: the underside is never seen (dark slot)
        a = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))]
        b = [bm.verts.new(p) for p in ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        fs = [bm.faces.new(b)] + [bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k])) for k in range(4)]
    elif faces == 'open3':
        long_x = (x1 - x0) >= (y1 - y0)
        a = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))]
        b = [bm.verts.new(p) for p in ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        fs = [bm.faces.new(b)]
        if long_x:
            fs += [bm.faces.new((a[0], a[1], b[1], b[0])), bm.faces.new((a[2], a[3], b[3], b[2]))]
        else:
            fs += [bm.faces.new((a[1], a[2], b[2], b[1])), bm.faces.new((a[3], a[0], b[0], b[3]))]
    else:
        return mb.box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), mi)
    for f in fs:
        f.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    for f in fs:                                     # single-sided parts must face out / up
        c = f.calc_center_median()
        mid = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        if f.normal.dot(c - mid) < 0:
            f.normal_flip()
    mb._tag(fs, mi)
    return fs


def surround(mb, L, lod, mi_pave, mi_slot):
    """Kerb flags: two long runs (along x) and two end pieces, joints seeded. Top at H."""
    W, D, H, fw = L['W'], L['D'], L['H'], L['fw']
    ow, od = L['ow'], L['od']
    faces = []
    if lod == 3:                                     # one ring: top + outer + inner walls (24 tris)
        bm = mb.bm
        o = [(-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2)]
        i = [(-ow / 2, -od / 2), (ow / 2, -od / 2), (ow / 2, od / 2), (-ow / 2, od / 2)]
        ot = [bm.verts.new((x, y, H)) for x, y in o]; ob = [bm.verts.new((x, y, 0)) for x, y in o]
        it = [bm.verts.new((x, y, H)) for x, y in i]; ib = [bm.verts.new((x, y, 0)) for x, y in i]
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append(bm.faces.new((ot[k], ot[k2], it[k2], it[k])))
            faces.append(bm.faces.new((ob[k], ob[k2], ot[k2], ot[k])))
            f = bm.faces.new((ib[k2], ib[k], it[k], it[k2])); f.material_index = mi_slot
        mb._tag(faces, mi_pave)
        return faces
    bev, segs = C.lod_pick(lod, (0.015, 1), (0.0, 1), (0.0, 1))
    pieces = []
    for side in (-1, 1):                             # long runs, full length W, split at seeded joints
        cuts = [-W / 2] + [c for c in L['joints'][side]] + [W / 2]
        if lod == 2:
            cuts = [-W / 2, W / 2]
        y0, y1 = (od / 2, D / 2) if side > 0 else (-D / 2, -od / 2)
        for a, b in zip(cuts[:-1], cuts[1:]):
            pieces.append((a, b, y0, y1))
    for side in (-1, 1):                             # end pieces between the long runs
        x0, x1 = (ow / 2, W / 2) if side > 0 else (-W / 2, -ow / 2)
        pieces.append((x0, x1, -od / 2, od / 2))
    J = 0.006 if lod < 2 else 0.0
    for k, (x0, x1, y0, y1) in enumerate(pieces):
        dz = L['flag_dz'][k % len(L['flag_dz'])] if lod == 0 else 0.0     # flags not perfectly level
        c = ((x0 + x1) / 2, (y0 + y1) / 2, (H + dz) / 2)
        sz = (x1 - x0 - J, y1 - y0 - J, H + dz)
        fs = C.board(mb, c, sz, mi_pave, bevel=bev, segs=segs) if bev > 0 else mb.box(c, sz, mi_pave)
        for f in fs:                                 # faces towards the opening = the slot wall
            f.normal_update()
            cc = f.calc_center_median()
            if abs(f.normal.z) < 0.3 and abs(cc.x) <= ow / 2 + 0.02 and abs(cc.y) <= od / 2 + 0.02 \
                    and (f.normal.x * cc.x + f.normal.y * cc.y) < 0:
                f.material_index = mi_slot
        faces += fs
    return faces


def rim(mb, L, lod, mi):
    """Bronze angle: top band (width rw, 8 mm thick, flush top) + leg (8 mm, depth rd) on all four sides."""
    ow, od, H, rw, rd = L['ow'], L['od'], L['H'], L['rw'], L['rd']
    t = 0.008
    faces = []
    mode = C.lod_pick(lod, 'closed', 'closed', 'top', 'top')
    # top band: two long, two short (short ones between the long ones)
    faces += _box(mb, -ow / 2, ow / 2, od / 2 - rw, od / 2, H - t, H + 0.002, mi, mode)
    faces += _box(mb, -ow / 2, ow / 2, -od / 2, -od / 2 + rw, H - t, H + 0.002, mi, mode)
    faces += _box(mb, ow / 2 - rw, ow / 2, -od / 2 + rw, od / 2 - rw, H - t, H + 0.002, mi, mode)
    faces += _box(mb, -ow / 2, -ow / 2 + rw, -od / 2 + rw, od / 2 - rw, H - t, H + 0.002, mi, mode)
    if lod < 2:                                      # legs down the slot wall
        z0 = H - rd
        faces += _box(mb, -ow / 2, ow / 2, od / 2 - t, od / 2, z0, H - t, mi)
        faces += _box(mb, -ow / 2, ow / 2, -od / 2, -od / 2 + t, z0, H - t, mi)
        faces += _box(mb, ow / 2 - t, ow / 2, -od / 2 + t, od / 2 - t, z0, H - t, mi)
        faces += _box(mb, -ow / 2, -ow / 2 + t, -od / 2 + t, od / 2 - t, z0, H - t, mi)
    return faces


def _field(mb, x0, x1, y0, y1, along_x, pitch, bt, bd, ztop, lod, mi):
    """Parallel flat bars filling [x0, x1] x [y0, y1]; bars run along x if along_x. Returns count."""
    mode = C.lod_pick(lod, 'nobottom', 'open3', 'top', 'top')
    span = (y1 - y0) if along_x else (x1 - x0)
    n = max(2, int(round(span / pitch)))
    step = span / n
    for i in range(n):
        c = (y0 if along_x else x0) + step * (i + 0.5)
        if along_x:
            _box(mb, x0, x1, c - bt / 2, c + bt / 2, ztop - bd, ztop, mi, mode)
        else:
            _box(mb, c - bt / 2, c + bt / 2, y0, y1, ztop - bd, ztop, mi, mode)
    return n


def bars(mb, L, lod, mi):
    """Bar field inside the rim for L['style']. Returns the number of bars."""
    ow, od, H, rw = L['ow'], L['od'], L['H'], L['rw']
    ix0, ix1, iy0, iy1 = -ow / 2 + rw, ow / 2 - rw, -od / 2 + rw, od / 2 - rw
    ztop = H - 0.003                                 # 3 mm under the rim / paving: flush, no z-fight
    st = L['style']
    count = 0
    if st == 'transverse':                           # bars across the slot, tie rods along it
        if lod < 3:
            count += _field(mb, ix0, ix1, iy0 - rw * 0.6, iy1 + rw * 0.6, False, L['pitch'], L['bt'], L['bd'],
                            ztop, lod, mi)
        if lod < 2:
            sides = C.lod_pick(lod, 6, 4)
            for f in L['ties']:
                y = iy0 + (iy1 - iy0) * f
                C.tube(mb, [(ix0, y, ztop - L['bd'] * 0.5), (ix1, y, ztop - L['bd'] * 0.5)], [0.008, 0.008], mi,
                       sides=sides, cap0=True, cap1=True)
    elif st == 'panels':                             # lift-out panels: border frame + bars along x + lift slots
        n = L['npanels']
        pl = (ix1 - ix0) / n
        bw = 0.03
        mode = C.lod_pick(lod, 'nobottom', 'open3', 'top', 'top')
        for k in range(n if lod < 3 else 0):
            a, b = ix0 + k * pl + 0.004, ix0 + (k + 1) * pl - 0.004
            # border: two cross members (y) + two long members (x)
            _box(mb, a, a + bw, iy0, iy1, ztop - L['bd'], ztop, mi, mode)
            _box(mb, b - bw, b, iy0, iy1, ztop - L['bd'], ztop, mi, mode)
            if lod < 3:
                count += _field(mb, a + bw, b - bw, iy0, iy1, True, L['pitch'], L['bt'], L['bd'] * 0.85,
                                ztop, lod, mi)
                if lod == 0:                         # two lifting lugs per panel: small bronze bosses
                    for yy in (iy0 + 0.12, iy1 - 0.12):
                        vs, fs = C.lathe(mb, [(0, 0), (0.022, 0), (0.015, 0.011), (0, 0.011)], 6, mi,
                                         base=((a + b) / 2, yy, ztop - 0.004))
    else:                                            # 'heavy': wide pitch, thick bars across, a centre bearer
        if lod < 3:
            count += _field(mb, ix0, ix1, iy0 - rw * 0.6, iy1 + rw * 0.6, False, L['pitch'], L['bt'], L['bd'],
                            ztop, lod, mi)
        if lod < 3:
            _box(mb, ix0, ix1, -0.03, 0.03, ztop - L['bd'] - 0.015, ztop - L['bd'] + 0.02, mi,
                 'closed' if lod < 2 else 'top')
    if lod == 3:                                     # the grate as one bronze plate just under the rim
        _box(mb, ix0, ix1, iy0, iy1, ztop - 0.02, ztop - 0.002, mi, 'top')
    return count
