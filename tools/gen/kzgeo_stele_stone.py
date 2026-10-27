"""kzgeo_stele_stone: geometry for gen_stele_stone (carved basalt stele).

Parts (all closed solids):
  body(mb, L, lod, mi_rough, mi_polish)  rough upright slab: a convex hull of per-level sections with one
      flat polished front panel (+Y) inset from a rough rim, a seeded irregular crown, rough back and sides.
      Faces whose normal is +Y and lie on the panel plane get the polish slot.
  plinth(mb, L, lod, mi)                  low rough base stone (hull of a jittered, chamfered box).
  crest(mb, cx, cz, y, R, lod, mi_disc, mi_mark)  bronze roundel with a gilt mountain and three steam wisps
      (the brand-board mark), facing +Y.
  flat_solid(mb, poly, y, depth, mi)      any 2D (x, z) polygon extruded towards +Y (x mirrored so it reads
      correctly from +Y, like kzgeo_common.text_solid).
L is the layout dict from gen_stele_stone.layout(): every number is drawn once per seed, before the LOD
branch, so LOD1-3 are the same stone at lower resolution.
"""
import math

import bmesh
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

import kzgeo_common as C
import kzgeo_parapet_stone as P


def _hull(mb, pts, mi):
    return P.hull(mb, [Vector(p) for p in pts], mi)


def body(mb, L, lod, mi_rough, mi_polish):
    """Rough upright slab standing on z = L['z0']. Returns faces."""
    W, T, H, z0 = L['w'], L['t'], L['h'], L['z0']
    yF = T / 2                              # polished panel plane
    rim = L['rim']                          # rim set back from the panel plane (rough split edge), m
    zt = z0 + H * L['shoulder']             # top of the straight part / start of the crown
    nlev = C.lod_pick(lod, 6, 4, 3, 2)
    pts = []
    jit = L['jit']                          # seeded jitter table (same at every LOD)
    for i in range(nlev):
        f = i / (nlev - 1)
        z = z0 + (zt - z0) * f
        taper = 1.0 - L['taper'] * f
        hw = W / 2 * taper
        j = jit[i * 7 % len(jit)] if lod < 2 else (0, 0, 0)
        pw = hw - L['margin']               # panel half width
        # polished panel corners (only between the panel bottom and top)
        if lod < 3:
            zp = min(max(z, z0 + L['panel_b']), zt - 0.02)
            pts += [(-pw, yF, zp), (pw, yF, zp)]
        # rough rim, sides and back
        pts += [(-hw + j[0], yF - rim, z), (hw + j[1], yF - rim, z)]
        if lod < 3:
            pts += [(-(hw + L['bulge'] * (0.6 + 0.4 * math.sin(3.1 * f + L['ph']))), -T * 0.05 + j[2], z),
                    ((hw + L['bulge'] * (0.6 + 0.4 * math.cos(2.7 * f + L['ph']))), T * 0.02 - j[2], z)]
        bw = hw * L['back']
        pts += [(-bw - j[2], -yF + abs(j[0]), z), (bw + j[2], -yF + abs(j[1]), z)]
    # crown: an irregular rounded top, skewed per seed
    nc = C.lod_pick(lod, 9, 6, 4, 3)
    hwt = W / 2 * (1.0 - L['taper'])
    for k in range(nc):
        u = -1 + 2 * k / (nc - 1)
        zc = zt + (z0 + H - zt) * max(0.0, 1.0 - L['crown_c'] * (u - L['skew']) ** 2 - 0.0)
        zc -= (L['crown_jit'][k % len(L['crown_jit'])] if lod < 2 else 0.0)
        x = u * hwt * 0.98
        if lod < 3:
            pts += [(x, yF - rim * 1.6, zc), (x * 0.95, -T * 0.05, zc + 0.01), (x * 0.9, -yF + 0.03, zc - 0.02)]
        else:
            pts += [(x, yF - rim, zc), (x, -yF + 0.02, zc)]
    if lod < 3:                             # the panel top follows the crown, inset
        for k in range(nc):
            u = -0.85 + 1.7 * k / (nc - 1)
            zc = zt + (z0 + H - zt) * max(0.0, 1.0 - L['crown_c'] * (u - L['skew']) ** 2) - L['margin'] * 1.2
            pts.append((u * (hwt - L['margin']), yF, max(zt - 0.02, zc)))
    faces = _hull(mb, pts, mi_rough)
    for f in faces:
        f.normal_update()
        if f.normal.y > 0.995 and abs(f.calc_center_median().y - yF) < 1e-4:
            f.material_index = mi_polish
    return faces


def plinth(mb, L, lod, mi):
    """Low base stone, top flat at L['z0'] + 0.03 (the stele sits 3 cm into it)."""
    bw, bd, bh = L['bw'], L['bd'], L['z0'] + 0.03
    j = L['jit']
    pts = []
    k = 0
    for x in (-bw / 2, bw / 2):
        for y in (-bd / 2, bd / 2):
            jx, jy, jz = j[k % len(j)] if lod < 2 else (0, 0, 0); k += 1
            pts.append((x + jx, y + jy, 0.0))
            if lod < 3:                       # 3 cm chamfer on the top edge, rough corners
                pts.append((x * (1 - 0.06 / bw) + jx, y * (1 - 0.06 / bd) + jy, bh))
                pts.append((x + jx * 0.5, y + jy * 0.5, bh - 0.035 + jz * 0.3))
            else:
                pts.append((x, y, bh))
    if lod == 0:                              # bulges on the four sides
        for (x, y) in ((0, bd / 2), (0, -bd / 2), (bw / 2, 0), (-bw / 2, 0)):
            jx, jy, jz = j[k % len(j)]; k += 1
            pts.append((x * 1.03 + jx * 0.3, y * 1.05 + jy * 0.3, bh * 0.45))
    return _hull(mb, pts, mi)


def flat_solid(mb, poly, y, depth, mi):
    """Closed prism of a 2D polygon (x, z) between y and y + depth, facing +Y. x is mirrored (glyph rule)."""
    pts = [(-x, z) for x, z in poly]
    loops = [[Vector((x, z, 0)) for x, z in pts]]
    tris = [tuple(t) for t in tessellate_polygon(loops)]
    faces = C._extrude_tris(mb.bm, pts, tris, y, depth)
    mb._tag(faces, mi)
    return faces


MOUNTAIN = [(-1.0, 0.0), (-0.55, 0.33), (-0.30, 0.55), (-0.16, 0.66), (-0.08, 0.62), (0.0, 0.67), (0.09, 0.62),
            (0.17, 0.66), (0.32, 0.54), (0.58, 0.31), (1.0, 0.0)]


def crest(mb, cx, cz, y, R, lod, mi_disc, mi_mark):
    """Brand mark on a bronze roundel: disc radius R, 12 mm proud, raised rim, gilt mountain + 3 wisps."""
    bm = mb.bm
    segs = C.lod_pick(lod, 24, 14, 8, 6)
    if lod < 2:
        prof = [(0, 0), (R, 0), (R, 0.012), (R - 0.016, 0.009), (0, 0.009)]     # raised rim
    else:
        prof = [(0, 0), (R, 0), (R, 0.010), (0, 0.010)]
    vs, faces = C.lathe(mb, prof, segs, mi_disc)
    # lathe axis Z -> +Y, then move to the face
    M = Matrix.Translation((cx, y, cz)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    face_y = y + 0.009
    if lod >= 3:
        return faces
    s = R * 0.62
    mz = cz - R * 0.45
    poly = [(cx + x * s, mz + z * s) for x, z in MOUNTAIN]
    faces += flat_solid(mb, poly, face_y, 0.004, mi_mark)
    if lod < 2:                               # three steam wisps above the peak
        sides = C.lod_pick(lod, 5, 3)
        n = C.lod_pick(lod, 7, 4)
        for k, dx in enumerate((-0.28, 0.0, 0.28)):
            top = 0.62 if k == 1 else 0.5
            pts = []
            for i in range(n):
                t = i / (n - 1)
                x = dx * s * (1.0 - 0.15 * t) + 0.07 * s * math.sin(2 * math.pi * (t * 1.1 + 0.15 * k))
                z = mz + s * (0.78 + top * t)
                pts.append(Vector((cx - x, face_y + 0.003, z)))
            _, fs = C.tube(mb, pts, [R * 0.035 * (1 - 0.5 * i / (n - 1)) for i in range(n)], mi_mark,
                           sides=sides, cap0=True, cap1=True)
            faces += fs
    return faces


def text_decal(mb, text, cx, cz, y, height, mi, gap=1.12, font=C.FONT_KANJI, res=1):
    """LOD1 inscription: the same vertical glyph layout as kzgeo_common.text_solid, but only the front
    triangles, 1.5 mm in front of the panel (the 5 mm relief walls are invisible at LOD1 distance and cost
    two thirds of the triangles). Single-sided on purpose."""
    bm = mb.bm
    items = []
    for ch in text:
        groups, (x0, y0, x1, y1) = C.glyph_tri_groups(ch, font, res)
        items.append((groups, x0, y0, x1, y1))
    s = height / max(it[4] - it[2] for it in items)
    n = len(items)
    faces = []
    for i, (groups, x0, y0, x1, y1) in enumerate(items):
        gx, gy = (x0 + x1) / 2, (y0 + y1) / 2
        zc = cz + ((n - 1) / 2.0 - i) * gap * height
        for pts, tris in groups:
            vs = [bm.verts.new((cx - (px - gx) * s, y + 0.0015, zc + (py - gy) * s)) for px, py in pts]
            for t in tris:
                if len(set(t)) == 3:
                    try:
                        f = bm.faces.new([vs[t[0]], vs[t[1]], vs[t[2]]])
                    except ValueError:
                        continue
                    f.normal_update()
                    if f.normal.y < 0:
                        f.normal_flip()
                    faces.append(f)
    mb._tag(faces, mi)
    return faces
