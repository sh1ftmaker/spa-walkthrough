"""kzgeo_staff_figure: work clothing and hand props for staff_figure, on the shared base body and rig of
kzgeo_guest_figure (same skeleton, bones, weights, poses).

  * samue: the crossed-collar jacket (kzgeo_guest_figure.yukata with a hip-length hem, narrow sleeves and no bow)
    plus trousers (seat loft + two wide leg tubes, cropped mid-calf, gathered at the ankle, or over leggings).
  * maekake apron: a curved two-sided cloth panel from the obi to the knee, optionally with the Kazan-yu mountain
    mark and two lettering bars.
  * hachimaki headband: a band round the brow with a knot and two tails at the back (+ a crest disc).
  * props (rigid on prop_R / prop_L): round tray with a sake flask and two cups, a stack of three folded towels,
    a tebo noodle basket on a handle, a bundle of pulled noodles.
Props are built in their own frame (origin = grip) and placed twice: a compact bind placement by the hand, and
the working placement of the pose; the prop bone carries the difference.
"""
import math

from mathutils import Matrix, Vector

import kzgeo_common as C
import kzgeo_guest_figure as KG


def trousers(F, mi, style, mi_legging=None):
    """style: 'cropped' (mid-calf), 'gathered' (monpe, tied at the ankle), 'leggings' (to mid-calf over kyahan)"""
    sk, lod = F.sk, F.lod
    B, z, k, g, J = sk.B, sk.z, sk.k, sk.g, sk.J
    n = KG.nseg(lod, 12, 8, 6, 4)
    hw = B['hips_w']
    F.part(['pelvis', 'thigh_L', 'thigh_R', 'spine'])
    seat = [KG.sring(z['hip'] - 0.07 * k, hw[0] * 1.02 * g, hw[1] * 1.1 * g, n, p=2.4),
            KG.sring(z['hip'] + 0.02, hw[0] * 1.06 * g + 0.012, hw[1] * 1.08 * g + 0.012, n, p=2.4),
            KG.sring(z['waist'] - 0.01, B['waist_w'][0] * g + 0.015, B['waist_w'][1] * g + 0.015, n, p=2.4)]
    if lod >= 2:
        seat = [seat[0], seat[2]]
    F.loft(seat, mi, cap0=True)
    F.close()
    nl = KG.nseg(lod, 10, 6, 5, 4)
    for S in 'LR':
        F.part(['pelvis', 'thigh_' + S, 'shin_' + S])
        hp, kn, an = J['hip' + S], J['knee' + S], J['ankle' + S]
        s = -1 if S == 'L' else 1
        th, sh = (kn - hp).normalized(), (an - kn).normalized()
        st = [(hp + Vector((s * 0.01, 0, 0.0)), th, 0.095, 0.1), (hp.lerp(kn, 0.5), th, 0.088, 0.092),
              (kn, sh, 0.08, 0.085)]
        if style == 'gathered':
            st += [(kn.lerp(an, 0.6), sh, 0.075, 0.078), (an + Vector((0, 0, 0.07 * k)), sh, 0.05, 0.052),
                   (an + Vector((0, 0, 0.045 * k)), sh, 0.042, 0.044)]
        else:
            st += [(kn.lerp(an, 0.45), sh, 0.075, 0.078), (kn.lerp(an, 0.5), sh, 0.068, 0.07)]
        if lod >= 2:
            st = [st[0], st[2], st[-1]]
        rings = [KG.lring(c, a, ru * k * g, rv * k * g, nl) for c, a, ru, rv in st]
        last_c, last_a = st[-1][0], st[-1][1]
        inner = [last_c + (p - last_c) * 0.8 - last_a * 0.03 for p in rings[-1]]
        F.loft(rings + ([inner] if lod <= 1 else []), mi, cap1=True)
        F.close()
        # exposed shin (or legging) below the trouser cuff
        F.part(['shin_' + S, 'foot_' + S])
        if style != 'gathered':
            m = mi_legging if (style == 'leggings' and mi_legging is not None) else None
            if m is not None:
                rr = [KG.lring(kn.lerp(an, 0.4), sh, 0.06 * k * g, 0.062 * k * g, nl),
                      KG.lring(kn.lerp(an, 0.8), sh, 0.045 * k * g, 0.047 * k * g, nl),
                      KG.lring(an + Vector((0, 0, 0.01)), sh, 0.034 * k, 0.036 * k, nl)]
                F.loft(rr, m)
            else:
                KG.leg(F, S, F.mats['skin'], z_from=kn.lerp(an, 0.3).z)
        F.close()


def apron(F, z_top, z_bot, wfrac, mi, mark=None, mi_mark=None, bib=False):
    """two-sided curved cloth panel on the front; hangs straight below the hip with a slight outward flare"""
    sk, lod = F.sk, F.lod
    z, k = sk.z, sk.k
    robe = F.robe
    cols, rows = KG.nseg(lod, 8, 4, 3, 2), KG.nseg(lod, 4, 2, 1, 1)
    zh = z['hip'] + 0.02
    grid_f, grid_b = [], []
    for r in range(rows + 1):
        zz = z_top + (z_bot - z_top) * r / rows
        zc = max(zz, zh)
        hw, hd, yc = robe.at(zc)
        rowf, rowb = [], []
        for c in range(cols + 1):
            u = -1 + 2 * c / cols
            x = u * wfrac * hw
            p, nrm = robe.front(x * (1.0 if zz >= zh else 1.04), zc, off=0.014 * k)
            p.z = zz
            if zz < zh:
                p.y += (zh - zz) * 0.035
            rowf.append(F.bm.verts.new(p + nrm * 0.004))
            rowb.append(F.bm.verts.new(p))
        grid_f.append(rowf); grid_b.append(rowb)
    fs = []
    for r in range(rows):
        for c in range(cols):
            fs.append(F.bm.faces.new((grid_f[r][c], grid_f[r + 1][c], grid_f[r + 1][c + 1], grid_f[r][c + 1])))
            fs.append(F.bm.faces.new((grid_b[r][c + 1], grid_b[r + 1][c + 1], grid_b[r + 1][c], grid_b[r][c])))
    border = [(0, c) for c in range(cols)] + [(r, cols) for r in range(rows)] + \
             [(rows, c) for c in range(cols, 0, -1)] + [(r, 0) for r in range(rows, 0, -1)]
    for i, (r, c) in enumerate(border):
        r2, c2 = border[(i + 1) % len(border)]
        fs.append(F.bm.faces.new((grid_f[r][c], grid_b[r][c], grid_b[r2][c2], grid_f[r2][c2])))
    for f in fs:
        f.material_index = mi
    if mark and mi_mark is not None and lod <= 1:
        zc = z_top + (z_bot - z_top) * 0.42
        p, nrm = robe.front(0.0, max(zc, zh), off=0.014 * k)
        p.z = zc
        if zc < zh:
            p.y += (zh - zc) * 0.035
        y = p.y + 0.0045
        s = 0.11 * k
        mtn = [(-1.0, 0.0), (-0.3, 0.55), (-0.12, 0.42), (0.0, 0.62), (0.16, 0.45), (0.38, 0.6), (1.0, 0.0)]
        pts = [(x * s * 0.5, zz * s * 0.5) for x, zz in mtn]
        bm = F.bm
        fr = [bm.verts.new((px, y + 0.003, zc + pz)) for px, pz in pts]
        bk = [bm.verts.new((px, y, zc + pz)) for px, pz in pts]
        mf = [bm.faces.new(fr[::-1]) if False else bm.faces.new(fr), bm.faces.new(bk[::-1])]
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            mf.append(bm.faces.new((fr[i], bk[i], bk[j], fr[j])))
        for zz, w in ((zc - 0.04 * k, 0.11 * k), (zc - 0.07 * k, 0.07 * k)):          # lettering bars
            mf += F.box(Vector((0, y + 0.0015, zz)), (w, 0.003, 0.014 * k), mi_mark)
        for f in mf:
            f.material_index = mi_mark


def headband(F, mi, crest_mi=None):
    """hachimaki round the brow, knot + two tails at the back; rigid on the head"""
    sk, lod = F.sk, F.lod
    c, (hx, hy, hz) = F.head_c, F.head_r
    n = KG.nseg(lod, 14, 8, 5, 4)
    pts, nr = [], []
    for i in range(n):
        t = 2 * math.pi * i / n
        zz = c.z + hz * (0.5 + 0.06 * math.sin(t))                   # brow at the front (+Y), a little lower at the back
        r = 1.075 - 0.01 * math.sin(t)
        pts.append(Vector((c.x + hx * r * math.cos(t), c.y + hy * r * math.sin(t), zz)))
        nr.append(Vector((math.cos(t) / hx, math.sin(t) / hy, 0)))
    F.band(pts, nr, 0.034 * sk.k, 0.006, mi, closed=True)
    if lod <= 1:
        bk = Vector((c.x, c.y - hy * 1.1, c.z + hz * 0.3))
        F.blob(bk + Vector((0, -0.012, 0)), (0.02, 0.014, 0.018), mi, segs=KG.nseg(lod, 6, 4, 4, 4), rings=3)
        if lod == 0:
            for s in (-1, 1):
                F.box(bk + Vector((s * 0.02, -0.02, -0.06)), (0.03, 0.006, 0.09), mi, M=Matrix.Rotation(s * 0.35, 3, 'Y'))
    if crest_mi is not None and lod == 0:
        f = Vector((c.x, c.y + hy * 1.065 + 0.008, c.z + hz * 0.56))
        F.blob(f, (0.016, 0.004, 0.016), crest_mi, segs=8, rings=3)


# ------------------------------------------------------------------------------------------- props (local frames)
def prop_tray(F, mats):
    """round tray D 0.34 m (walnut) with a tenmoku sake flask and two cups; origin = tray centre, top face up"""
    lod = F.lod
    seg = KG.nseg(lod, 24, 12, 8, 6)
    R = 0.17
    C.lathe(F.mb, [(0.0, 0.0), (R - 0.01, 0.0), (R, 0.004), (R + 0.004, 0.026), (R - 0.006, 0.028), (R - 0.009, 0.012),
                   (0.0, 0.012)] if lod == 0 else [(0.0, 0.0), (R, 0.0), (R + 0.003, 0.026), (R - 0.008, 0.026), (0.0, 0.012)]
            if lod == 1 else [(0.0, 0.0), (R, 0.0), (R, 0.026), (0.0, 0.026)], seg, mats['tray'])
    if lod <= 2:
        s2 = KG.nseg(lod, 12, 8, 5, 5)
        C.lathe(F.mb, [(0.0, 0.0), (0.03, 0.0), (0.042, 0.05), (0.038, 0.1), (0.014, 0.14), (0.012, 0.17), (0.016, 0.18),
                       (0.0, 0.18)] if lod == 0 else [(0.0, 0.0), (0.04, 0.0), (0.04, 0.09), (0.013, 0.17), (0.0, 0.17)],
                s2, mats['ceramic'], base=(0.05, 0.03, 0.012))
        if lod == 0:
            for x, y in ((-0.06, 0.05), (-0.03, -0.07)):
                C.lathe(F.mb, [(0.0, 0.0), (0.018, 0.0), (0.028, 0.035), (0.0, 0.035)], 10, mats['ceramic'], base=(x, y, 0.012))


def prop_towels(F, mats):
    """three folded cream towels, 0.34 x 0.24, origin = stack centre bottom"""
    lod = F.lod
    W, D, T = 0.34, 0.24, 0.05
    for i in range(3 if lod <= 2 else 1):
        Tt = T if lod <= 2 else T * 3
        if lod <= 1:
            C.pillow(F.mb, (0.004 * (i - 1), 0.003 * (1 - i), i * (T + 0.004)), W, D, T, mats['towel'], rc=0.04, m=2 if lod == 0 else 1,
                     puff=0.012, creases=[(W / 3, 0.008, 0.02)] if lod == 0 else ())
        else:
            F.box(Vector((0, 0, i * (T + 0.004) + Tt / 2)), (W, D, Tt), mats['towel'])


def prop_basket(F, mats):
    """tebo noodle strainer: open deep basket (bamboo) on a hinoki handle; origin = grip on the handle"""
    lod = F.lod
    seg = KG.nseg(lod, 14, 8, 6, 4)
    L = 0.26
    base = Vector((0, L, -0.06))
    prof = [(0.0, -0.17), (0.03, -0.165), (0.055, -0.1), (0.07, -0.02), (0.075, 0.0), (0.068, 0.0), (0.062, -0.02), (0.048, -0.1),
            (0.026, -0.155), (0.0, -0.16)]
    if lod >= 1:
        prof = [(0.0, -0.17), (0.055, -0.1), (0.075, 0.0), (0.06, -0.02), (0.0, -0.15)]
    C.lathe(F.mb, prof, seg, mats['basket'], base=tuple(base))
    C.stick(F.mb, Vector((0, -0.06, 0.0)), base + Vector((0, -0.07, 0.0)), 0.012, 0.012, mats['handle'], segs=KG.nseg(lod, 6, 5, 4, 4))


def prop_noodles(F, mats, end=Vector((0, 0, -0.42))):
    """bundle of pulled noodles from the grip (origin) to `end` (the basket), sagging slightly"""
    lod = F.lod
    n = KG.nseg(lod, 9, 4, 1, 1)
    r = C.rng(7, 'noodles')
    end = Vector(end)
    for i in range(n):
        a = 2 * math.pi * i / max(1, n)
        rr = 0.012 if n > 1 else 0.0
        top = Vector((rr * math.cos(a), rr * math.sin(a), 0.0))
        mid = end * 0.5 + top * 1.4 + Vector((r.uniform(-0.012, 0.012), r.uniform(-0.012, 0.012), -0.03))
        bot = end + top * 2.2 + Vector((r.uniform(-0.015, 0.015), r.uniform(-0.015, 0.015), 0))
        C.tube(F.mb, [top, mid, bot], [0.0035 if n > 2 else 0.012] * 3, mats['noodle'], sides=3 if n > 2 else 5, cap1=True)


def place_prop(F, builder, mats, bone, rest_M):
    """build a prop in its local frame and move it to its bind placement (rest_M); rigid on `bone`"""
    F.part([bone], rigid=True)
    builder(F, mats)
    for v in F.bm.verts:
        if v[F.lay] == 0:
            v.co = rest_M @ v.co
    F.close()
