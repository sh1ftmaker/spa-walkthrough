"""Kawagiri kit (op18): small parts shared by gen_kawagiri_pod, gen_kawagiri_sign_gate, gen_ramen_counter and
gen_kitchen_block. Every helper adds faces to a genlib.MeshBuilder and takes `lod` so the callers derive their
LODs from one layout (positions and counts are decided by the caller, the helper only picks resolution).

  timber(...)        beam / post / board: bevelled at LOD0, plain box after
  post(...)          chamfered (octagonal) post at LOD0-1, box at LOD2-3
  chochin(...)       red paper lantern: lathe body, dark caps, cord, circle crest (LOD0-1)
  andon(...)         small square iron lantern on a bracket (C.lantern_head)
  stone_footing(...) dry-laid basalt footing: tapered core + faceted cobble courses
  bowl(...), bowl_stack(...), pot(...), ladle(...)   ceramic / iron kitchenware (lathe)
  bar_stool(...)     ramen stool: 4 splayed legs, apron, footrest, red cushion
  zabuton(...)       floor cushion (C.pillow)
  neon_text(...)     hand-bent neon tubes from kzgeo_neon_sign.glyph_strokes (tubes LOD0-1, ribbons LOD2)
  water_trough(...)  open timber U-trough swept along a polyline (aqueducts, ceiling troughs)
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C


# ------------------------------------------------------------------------------------------- timber
def timber(mb, lod, c, size, mi, bev=0.012):
    if lod == 0 and bev > 0:
        return C.board(mb, c, size, mi, bevel=bev, segs=1)
    return mb.box(c, size, mi)


def post(mb, lod, x, y, z0, z1, s, mi, ch=None):
    ch = ch if ch is not None else s * 0.12
    if lod <= 1:
        return C.chamfered_bar(mb, (x, y, (z0 + z1) / 2), (s, s, z1 - z0), mi, ch=ch, axis='z')
    return mb.box((x, y, (z0 + z1) / 2), (s, s, z1 - z0), mi)


def beam_x(mb, lod, x0, x1, y, z0, z1, d, mi, ch=None):
    ch = ch if ch is not None else min(d, z1 - z0) * 0.1
    c = ((x0 + x1) / 2, y, (z0 + z1) / 2)
    if lod <= 1:
        return C.chamfered_bar(mb, c, (x1 - x0, d, z1 - z0), mi, ch=ch, axis='x')
    return mb.box(c, (x1 - x0, d, z1 - z0), mi)


def beam_y(mb, lod, y0, y1, x, z0, z1, w, mi, ch=None):
    ch = ch if ch is not None else min(w, z1 - z0) * 0.1
    c = (x, (y0 + y1) / 2, (z0 + z1) / 2)
    if lod <= 1:
        return C.chamfered_bar(mb, c, (w, y1 - y0, z1 - z0), mi, ch=ch, axis='y')
    return mb.box(c, (w, y1 - y0, z1 - z0), mi)


def brace(mb, lod, a, b, s, mi):
    """square-section diagonal strut from a to b"""
    a, b = Vector(a), Vector(b)
    d = b - a
    segs = 4
    res = bmesh.ops.create_cone(mb.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=s * 0.707,
                                radius2=s * 0.707, depth=d.length)
    vs = res['verts']
    from mathutils import Matrix
    q = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    bmesh.ops.transform(mb.bm, matrix=Matrix.Translation((a + b) / 2) @ q @ Matrix.Rotation(math.pi / 4, 4, 'Z'), verts=vs)
    fs = C._faces_of(vs)
    mb._tag(fs, mi)
    return fs


# ------------------------------------------------------------------------------------------- lanterns
CHO_SEGS = {0: 16, 1: 10, 2: 6, 3: 4}


def chochin(mb, mats, lod, top, r=0.2, h=0.55, cord=0.12, crest=True, lod3_caps=True, segs=None, crest_lod=1, cord_lod=2):
    """Hanging red chochin. `top` = (x, y, z) where the cord meets its support; the body hangs below it.
    mats: paper (lantern_paper red), cap (lacquer_black), ink (lacquer_black), cord (rope or iron).
    Body h/w ~1.3 (sheet-mod-kawagiri: 0.45 x 0.6-0.7 m on the pod corners). Returns the light centre."""
    x, y, zt = top
    segs = (segs or CHO_SEGS)[lod]
    capr, caph = r * 0.62, 0.045 if lod < 3 else 0.06
    z1 = zt - cord - caph                    # top of the paper
    z0 = z1 - h                              # bottom of the paper
    if lod <= 1:
        nr = C.lod_pick(lod, 9, 5)
        prof = []
        for k in range(nr + 1):
            t = k / nr
            rr = capr + (r - capr) * math.sin(math.pi * t) ** 0.55
            prof.append((rr, z0 + h * t))
        C.lathe(mb, prof, segs, mats['paper'], base=(x, y, 0))
        if lod == 0:                       # raised bamboo ribs every other ring (thin paper bands)
            for k in range(2, nr - 1, 2):
                rr, zz = prof[k]
                C.lathe(mb, [(rr + 0.002, zz - 0.005), (rr + 0.006, zz), (rr + 0.002, zz + 0.005)], segs,
                        mats['cap'], base=(x, y, 0), closed=False)
    elif lod == 2:
        C.lathe(mb, [(capr, z0), (r, z0 + h * 0.5), (capr, z1)], segs, mats['paper'], base=(x, y, 0))
    elif not lod3_caps:                      # LOD3 lean: one 4-sided lathe, paper only
        C.lathe(mb, [(capr, z0 - caph), (r, z0 + h * 0.5), (capr, z1 + caph)], segs, mats['paper'], base=(x, y, 0))
        return Vector((x, y, z0 + h * 0.5))
    else:                                    # LOD3: one lathe, dark cap bands top and bottom
        _, fs = C.lathe(mb, [(capr * 1.06, z0 - caph), (capr * 1.06, z0), (r, z0 + h * 0.5), (capr * 1.06, z1), (capr * 1.06, z1 + caph)],
                        segs, mats['paper'], base=(x, y, 0))
        for f in fs:
            zc = f.calc_center_median().z
            if zc < z0 or zc > z1:
                f.material_index = mats['cap']
        return Vector((x, y, z0 + h * 0.5))
    # caps (dark rims top and bottom): kept at every LOD (they name the chochin)
    C.lathe(mb, [(capr * 1.06, z0 - caph), (capr * 1.06, z0 + 0.01)], segs, mats['cap'], base=(x, y, 0))
    C.lathe(mb, [(capr * 1.06, z1 - 0.01), (capr * 1.06, z1 + caph)], segs, mats['cap'], base=(x, y, 0))
    if lod <= cord_lod and cord > 0.01:
        C.stick(mb, (x, y, z1 + caph), (x, y, zt), 0.008, 0.008, mats['cord'], segs=4 if lod else 6)
    if crest and lod <= crest_lod:
        # black circle crest on the front, conformed to the body: ring + centre disc
        zc = z0 + h * 0.5
        R0 = r * 0.42
        n = min(segs, C.lod_pick(lod, 16, 10))

        def onbody(dx, dz, off):
            t = (dz + zc - z0) / h
            rr = capr + (r - capr) * math.sin(math.pi * min(1, max(0, t))) ** 0.55
            yy = math.sqrt(max(1e-6, rr * rr - dx * dx))
            return Vector((x + dx * (rr + off) / rr, y + yy * (rr + off) / rr, zc + dz))
        bm = mb.bm
        fs = []
        for (ra, rb) in ((R0 * 0.82, R0), (0.0, R0 * 0.35)):
            if ra == 0:
                cen = bm.verts.new(onbody(0, 0, 0.004))
                ring = [bm.verts.new(onbody(rb * math.cos(2 * math.pi * k / n), rb * math.sin(2 * math.pi * k / n), 0.004)) for k in range(n)]
                for k in range(n):
                    fs.append(bm.faces.new((cen, ring[k], ring[(k + 1) % n])))
            else:
                A = [bm.verts.new(onbody(ra * math.cos(2 * math.pi * k / n), ra * math.sin(2 * math.pi * k / n), 0.004)) for k in range(n)]
                B = [bm.verts.new(onbody(rb * math.cos(2 * math.pi * k / n), rb * math.sin(2 * math.pi * k / n), 0.004)) for k in range(n)]
                fs += C.bridge_rings(bm, A, B)
        for f in fs:
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
        mb._tag(fs, mats['ink'])
    return Vector((x, y, z0 + h * 0.5))


def andon(mb, mats, lod, base, size=0.22, height=0.36, arm=None):
    """small iron-framed andon on a base point (x, y, z); arm=(dx, dy) adds an iron L-bracket back to the post."""
    x, y, z = base
    if lod >= 3:
        mb.box((x, y, z + height / 2), (size, size, height), mats['paper'])
        return Vector((x, y, z + height / 2))
    cen = C.lantern_head(mb, (x, y, z), dict(iron=mats['iron'], paper=mats['paper']), lod, size=size, height=height, roof='hip')
    if arm and lod <= 2:
        dx, dy = arm
        mb.box((x + dx / 2, y + dy / 2, z - 0.02), (abs(dx) + 0.04, abs(dy) + 0.04, 0.03), mats['iron'])
        if lod <= 1:
            C.stick(mb, (x + dx * 0.95, y + dy * 0.95, z - 0.02), (x + dx * 0.95, y + dy * 0.95, z - 0.28), 0.012, 0.012, mats['iron'], segs=4)
            brace(mb, lod, (x + dx * 0.95, y + dy * 0.95, z - 0.26), (x + dx * 0.35, y + dy * 0.35, z - 0.03), 0.02, mats['iron'])
    return cen


def quad_y(mb, cx, y, cz, w, h, mi):
    """one quad facing +Y (glow faces, LOD3 sign fields)"""
    bm = mb.bm
    vs = [bm.verts.new((cx + w / 2, y, cz - h / 2)), bm.verts.new((cx - w / 2, y, cz - h / 2)),
          bm.verts.new((cx - w / 2, y, cz + h / 2)), bm.verts.new((cx + w / 2, y, cz + h / 2))]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.y < 0:
        f.normal_flip()
    f.material_index = mi
    return [f]


# ------------------------------------------------------------------------------------------- stone
def frustum(mb, c, w, d, h, k, mi):
    x, y, z = c
    bm = mb.bm
    B = [bm.verts.new((x + sx * w / 2, y + sy * d / 2, z)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    T = [bm.verts.new((x + sx * w * k / 2, y + sy * d * k / 2, z + h)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    fs = [bm.faces.new(B[::-1]), bm.faces.new(T)] + C.bridge_rings(bm, B, T)
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def stone_footing(mb, lod, r, c, w, d, h, mi, courses=None, top_mi=None, lod2_course=True, npts1=8, npts0=11):
    """Dry-laid basalt footing (sheet-mod-kawagiri: rough cobble piers under every post). A tapered core
    carries the silhouette at every LOD; LOD0-1 lay faceted cobbles in courses round the four faces, LOD2 keeps
    the biggest course only (one ring), LOD3 is the core. Seeded by `r` (draws are made for every LOD, so
    the layout is identical between LODs)."""
    x, y, z = c
    k = 0.82
    frustum(mb, (x, y, z), w * 0.92, d * 0.92, h, k, mi)
    if top_mi is not None:
        mb.box((x, y, z + h - 0.02), (w * 0.92 * k + 0.02, d * 0.92 * k + 0.02, 0.06), top_mi)
    nc = courses or max(2, int(round(h / 0.32)))
    stones = []
    for ci in range(nc):
        zc = z + (ci + 0.5) * h / nc
        f = 1 - (1 - k) * (ci + 0.5) / nc
        sh = h / nc * 0.62
        for side in range(4):
            L = (w if side % 2 == 0 else d) * 0.92 * f
            n = max(2, int(round(L / 0.34)))
            for j in range(n):
                u = -L / 2 + (j + 0.5) * L / n + r.uniform(-0.04, 0.04)
                sz = (L / n * 0.55 * r.uniform(0.85, 1.1), 0.12 * r.uniform(0.8, 1.2), sh * r.uniform(0.85, 1.1))
                off = (w if side % 2 else d) * 0.92 * f / 2 + 0.02
                if side == 0:
                    p, s = (x + u, y - off, zc), (sz[0], sz[1], sz[2])
                elif side == 1:
                    p, s = (x + off, y + u, zc), (sz[1], sz[0], sz[2])
                elif side == 2:
                    p, s = (x - u, y + off, zc), (sz[0], sz[1], sz[2])
                else:
                    p, s = (x - off, y - u, zc), (sz[1], sz[0], sz[2])
                stones.append((ci, p, s, r.randrange(1 << 30)))
    import random
    for ci, p, s, sd in stones:
        if lod >= 3 or (lod == 2 and (ci != 0 or not lod2_course)):
            continue
        rr = random.Random(sd)
        C.hull_rock(mb, p, s, mi, rr, npts=C.lod_pick(lod, npts0, npts1, 6), ground=z if ci == 0 else None)


# ------------------------------------------------------------------------------------------- kitchenware
def bowl(mb, lod, c, R, H, mi, foot=True):
    segs = C.lod_pick(lod, 12, 10, 6, 4)
    x, y, z = c
    if lod >= 1:
        C.lathe(mb, [(R * 0.4, 0), (R, H), (R * 0.9, H), (0, H * 0.4)], segs, mi, base=(x, y, z))
        return
    t = 0.006
    prof = [(R * 0.38, 0), (R * 0.38, H * 0.08), (R * 0.55, H * 0.15), (R * 0.85, H * 0.45), (R, H),
            (R - t, H), (R * 0.82 - t, H * 0.5), (0.0, H * 0.18)]
    C.lathe(mb, prof, segs, mi, base=(x, y, z))


def bowl_stack(mb, lod, c, R, H, n, mi, segs=None, steps=None, simple_from=2):
    """a stack of n bowls as ONE stepped lathe: each bowl rim shows as a small step (reads as a stack at every
    LOD for a fraction of n separate bowls)"""
    x, y, z = c
    pitch = H * 0.32
    segs = segs or C.lod_pick(lod, 12, 8, 6, 4)
    top = H + pitch * (n - 1)
    if lod >= simple_from:
        C.lathe(mb, [(R * 0.45, 0), (R, H * 0.6), (R, top), (0, top)], segs, mi, base=(x, y, z))
        return
    prof = [(R * 0.4, 0), (R * 0.75, H * 0.35)]
    steps = n if steps is None else min(n, steps)
    if steps < n:
        prof.append((R * 0.99, H + (n - steps - 1) * pitch))
    for i in range(n - steps, n):
        zr = H + i * pitch
        prof += [(R * 0.97, zr - 0.012), (R, zr)]
    prof += [(R * 0.8, top + 0.002), (0, top - H * 0.5)]
    C.lathe(mb, prof, segs, mi, base=(x, y, z))


def pot(mb, lod, c, R, H, mi, lid_mi=None, handles=True):
    segs = C.lod_pick(lod, 16, 10, 6, 4)
    x, y, z = c
    prof = [(R * 0.95, 0), (R, 0.02), (R, H), (R + 0.012, H), (R + 0.012, H + 0.015), (R * 0.2, H + 0.03), (0, H + 0.05)]
    if lod >= 2:
        prof = [(R, 0), (R, H), (0, H + 0.03)]
    C.lathe(mb, prof, segs, mi if lid_mi is None else mi, base=(x, y, z))
    if handles and lod == 0:
        for s in (-1, 1):
            mb.box((x + s * (R + 0.03), y, z + H * 0.8), (0.05, 0.03, 0.02), mi)


def ladle(mb, lod, top, L, mi):
    """hanging ladle: handle from `top` straight down, cup at the bottom"""
    x, y, z = top
    if lod >= 2:
        return
    C.stick(mb, (x, y, z), (x, y, z - L), 0.007, 0.007, mi, segs=4)
    C.lathe(mb, [(0.0, 0), (0.035, 0.012), (0.045, 0.04), (0.04, 0.045), (0.0, 0.02)] if lod == 0 else
            [(0.0, 0), (0.045, 0.035), (0.0, 0.02)], C.lod_pick(lod, 8, 5), mi,
            base=(x, y + 0.02, z - L - 0.04))


# ------------------------------------------------------------------------------------------- seating
def bar_stool(mb, lod, c, mats, h=0.72, r=0.17, yaw=0.0):
    """ramen stool (sheet panel 4: 0.72 m, red cushion, splayed legs, footrest ring). LOD0 ~200 tris, LOD1 ~120,
    LOD2 ~60 (legs as two crossed boards), LOD3 a seat lathe on one box."""
    x, y, z = c
    segs = C.lod_pick(lod, 12, 8, 5, 4)
    cush_h = 0.05
    zs = z + h - cush_h
    if lod == 0:
        C.lathe(mb, [(r * 0.96, zs - 0.035), (r, zs - 0.028), (r, zs)], segs, mats['wood'], base=(x, y, 0))
        C.lathe(mb, [(r * 0.99, zs), (r, zs + cush_h * 0.6), (r * 0.8, zs + cush_h), (0, zs + cush_h)], segs, mats['cushion'], base=(x, y, 0))
    else:
        C.lathe(mb, [(r, zs - 0.035), (r, zs)], segs, mats['wood'], base=(x, y, 0))
        C.lathe(mb, [(r, zs), (r * 0.88, zs + cush_h), (0, zs + cush_h)], segs, mats['cushion'], base=(x, y, 0), closed=False)
    if lod >= 3:
        mb.box((x, y, z + (zs - 0.035 - z) / 2), (r * 1.2, r * 1.2, zs - 0.035 - z), mats['wood'])
        return
    sp = 0.04
    if lod == 2:
        for k in range(2):
            a = yaw + math.pi / 4 + k * math.pi / 2
            mb.box((x, y, z + (zs - 0.035 - z) / 2), (2 * (r * 0.62 + sp * 0.5), 0.03, zs - 0.035 - z), mats['wood'], rot=(0, 0, a))
        return
    lr = 0.02
    for k in range(4):
        a = yaw + math.pi / 4 + k * math.pi / 2
        top = (x + math.cos(a) * r * 0.62, y + math.sin(a) * r * 0.62, zs - 0.035)
        bot = (x + math.cos(a) * (r * 0.62 + sp), y + math.sin(a) * (r * 0.62 + sp), z)
        C.stick(mb, bot, top, lr, lr, mats['wood'], segs=C.lod_pick(lod, 6, 4))
    rf = r * 0.62 + sp * 0.62
    zf = z + 0.24
    for k in (range(4) if lod == 0 else ()):          # footrest ring: LOD0 only (budget)
        a0 = yaw + math.pi / 4 + k * math.pi / 2
        a1 = a0 + math.pi / 2
        C.stick(mb, (x + math.cos(a0) * rf, y + math.sin(a0) * rf, zf), (x + math.cos(a1) * rf, y + math.sin(a1) * rf, zf),
                0.012, 0.012, mats['wood'], segs=4)


def zabuton(mb, lod, c, s, mi, yaw=0.0):
    x, y, z = c
    if lod >= 2:
        mb.box((x, y, z + 0.04), (s, s, 0.08), mi)
        return
    C.pillow(mb, (x, y, z), s, s, 0.06, mi, rc=0.05, m=C.lod_pick(lod, 2, 1), puff=0.03, yaw=yaw)


# ------------------------------------------------------------------------------------------- neon
def ribbon(mb, pts, half, y, mi):
    """flat strip facing +Y along a polyline in (x, z): LOD2 neon"""
    bm = mb.bm
    n = len(pts)
    L_, R_ = [], []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        tx, tz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, tz) or 1.0
        nx, nz = -tz / ln, tx / ln
        L_.append(bm.verts.new((pts[i][0] + nx * half, y, pts[i][1] + nz * half)))
        R_.append(bm.verts.new((pts[i][0] - nx * half, y, pts[i][1] - nz * half)))
    fs = []
    for i in range(n - 1):
        f = bm.faces.new((L_[i], R_[i], R_[i + 1], L_[i + 1]))
        f.normal_update()
        if f.normal.y < 0:
            f.normal_flip()
        fs.append(f)
    mb._tag(fs, mi)
    return fs


def neon_line(mb, lod, pts, y, r, mi, closed=False):
    if closed:
        pts = list(pts) + [pts[0]]
    if lod <= 1:
        C.tube(mb, [(px, y, pz) for px, pz in pts], [r] * len(pts), mi, sides=C.lod_pick(lod, 6, 4),
               cap0=not closed, cap1=not closed)
    else:
        ribbon(mb, pts, r * 1.3, y + r, mi)


def neon_glyph(mb, lod, ch, cx, cz, size, y, r, mi):
    import kzgeo_neon_sign as K
    strokes, _ = K.glyph_strokes(ch, eps=C.lod_pick(lod, 1.0, 1.6, 2.6))
    for s in strokes:
        if len(s) >= 2:
            neon_line(mb, lod, [(cx - px * size, cz + py * size) for px, py in s], y, r, mi)   # glyph x -> -X


def rrect_pts(w, h, rc, n):
    pts = []
    for (cx, cz, a0) in ((w / 2 - rc, h / 2 - rc, 0), (-w / 2 + rc, h / 2 - rc, 90), (-w / 2 + rc, -h / 2 + rc, 180), (w / 2 - rc, -h / 2 + rc, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + rc * math.cos(a), cz + rc * math.sin(a)))
    return pts


# ------------------------------------------------------------------------------------------- water
def water_trough(mb, lod, pts, w, h, t, mi, caps=True):
    """open U-trough swept along pts (outer w x h, wall t): aqueducts and ceiling troughs. Water is data."""
    if lod >= 2:
        prof = [(-w / 2, 0), (w / 2, 0), (w / 2, h), (-w / 2, h)]
        return C.sweep(mb, pts, prof, mi, caps=caps)
    prof = [(-w / 2, 0), (w / 2, 0), (w / 2, h), (w / 2 - t, h), (w / 2 - t, t), (-w / 2 + t, t), (-w / 2 + t, h), (-w / 2, h)]
    prof = prof[::-1]
    return C.sweep(mb, pts, prof, mi, caps=caps)


def shift_points(off, lights=(), *point_lists):
    """apply a centre_base offset (dx, dy, dz) to recorded kz_lights entries and [x, y, z] point lists"""
    dx, dy, dz = off
    for L in lights:
        L['pos'] = [round(L['pos'][0] + dx, 4), round(L['pos'][1] + dy, 4), round(L['pos'][2] + dz, 4)]
    for pl in point_lists:
        for p in pl:
            p[0] = round(p[0] + dx, 4); p[1] = round(p[1] + dy, 4); p[2] = round(p[2] + dz, 4)


def flat_text(mb, text, cx, cz, y, height, mi, font=C.FONT_KANJI, vertical=True, gap=1.08, res=1):
    """LOD1 text: the same glyph fill as C.text_solid, front faces only (a print on the board, no side walls),
    about a third of the triangles. Reads left-to-right / top-down from +Y."""
    bm = mb.bm
    chars = list(text) if vertical else [text]
    items = []
    for ch in chars:
        groups, (x0, y0, x1, y1) = C.glyph_tri_groups(ch, font, res)
        items.append((groups, x0, y0, x1, y1))
    hs = [it[4] - it[2] for it in items if it[0]]
    if not hs:
        return
    s = height / max(hs)
    n = len(items)
    fs = []
    for i, (groups, x0, y0, x1, y1) in enumerate(items):
        gx, gy = (x0 + x1) / 2, (y0 + y1) / 2
        zc = cz + ((n - 1) / 2.0 - i) * gap * height if vertical else cz
        for pts, tris in groups:
            vs = [bm.verts.new((cx - (px - gx) * s, y, zc + (py - gy) * s)) for px, py in pts]
            for t in tris:
                if len(set(t)) < 3:
                    continue
                try:
                    f = bm.faces.new([vs[j] for j in t])
                except ValueError:
                    continue
                f.normal_update()
                if f.normal.y < 0:
                    f.normal_flip()
                fs.append(f)
    mb._tag(fs, mi)
    return fs
