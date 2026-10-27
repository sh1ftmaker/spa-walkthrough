"""Head builders for gen_lantern_post (op01 rewrite). Each returns the light centre (Vector).

  box_head      square iron-and-timber head with a 3 x 3 lattice, wide thin hip roof (sheet-mod-lights #4)
  hex_head      six-sided bonbori head, hex tray and roof with lifted corners, ball finial (sheet-vs-lights-2 #5)
  cyl_head      cylindrical paper lantern with dark lacquer top and bottom caps (spiral-stair rail lanterns)
  chochin_hang  round hanging chochin with iron caps on a cord (boat pole, sheet-vs-lights-2 #5)
"""
import math

from mathutils import Vector

import kzgeo_common as C
import kzgeo_lantern_floor as L


def box_head(mb, z0, W, H, roof_half, roof_rise, m, lod, nl=(2, 2)):
    """W: head body width; H: body height (from z0); roof_half: eave half-size. m: dict(wood, paper, iron, roof)."""
    tray_t = 0.025
    if lod <= 1:
        (C.board if lod == 0 else (lambda mb_, c, s, mi, bevel=0: mb_.box(c, s, mi)))(
            mb, (0, 0, z0 + tray_t / 2), (W + 0.04, W + 0.04, tray_t), m['wood'], bevel=0.004)
    zb = z0 + (tray_t if lod <= 1 else 0.0)
    hb = H - (tray_t if lod <= 1 else 0.0)
    kz = L.andon_frame(mb, (0, 0), zb, W, hb, dict(wood=m['wood'], paper=m['paper']), lod, stile=max(0.018, W * 0.1),
                       rail=max(0.016, W * 0.08), pattern='lattice', n_lattice=nl if lod == 0 else (1, 1), bev=0.0)
    thick = 0.016
    L.hip_roof(mb, (0, 0), z0 + H, roof_half, thick, roof_rise + (0.03 if lod >= 3 else 0.0), m['roof'], segs=4,
               top_half=0.025 if lod <= 2 else 0.0, simple='min' if lod >= 3 else lod >= 1)
    if lod == 0:
        C.lathe(mb, [(0.012, 0), (0.022, 0.012), (0.016, 0.03), (0, 0.04)], 6, m['iron'], base=(0, 0, z0 + H + thick + roof_rise - 0.004))
    elif lod == 1:
        mb.box((0, 0, z0 + H + thick + roof_rise + 0.012), (0.03, 0.03, 0.03), m['iron'])
    return kz


def hex_head(mb, z0, R, H, roof_R, roof_rise, m, lod):
    """R: corner radius of the hex body; roof_R: corner radius of the roof eave."""
    tray_t = 0.03
    ph = 0.0               # corners at 0, 60 ... deg: a flat face to the front (+y)
    if lod == 0:
        L.poly_ring(mb, (0, 0), z0, z0 + tray_t, R * 1.16, R * 0.6, 6, m['wood'], phase=ph)
    elif lod == 1:
        L.srings(mb, [(R * 1.16, R * 1.16, z0), (R * 1.16, R * 1.16, z0 + tray_t)], 6, m['wood'], shape='circle', phase=ph)
    zb = z0 + (tray_t if lod <= 1 else 0.0)
    hb = H - (tray_t if lod <= 1 else 0.0)
    rp = R * 0.94
    L.srings(mb, [(rp, rp, zb), (rp, rp, zb + hb)], 6, m['paper'], shape='circle', phase=ph,
             cap_bot=lod == 0, cap_top=lod == 0)
    if lod <= 1:
        for k in range(6):
            a = ph + 2 * math.pi * k / 6
            x, y = R * math.cos(a), R * math.sin(a)
            if lod == 0:
                C.stick(mb, (x, y, zb), (x, y, zb + hb), 0.011, 0.011, m['wood'], segs=4)
            else:
                L.open_box(mb, (x, y, zb + hb / 2), (0.02, 0.02, hb), m['wood'], skip=('top', 'bottom'))
        if lod == 0:
            L.poly_ring(mb, (0, 0), zb + hb - 0.022, zb + hb, R * 1.06, R * 0.86, 6, m['wood'], phase=ph)
        else:
            L.srings(mb, [(R * 1.06, R * 1.06, zb + hb - 0.022), (R * 1.06, R * 1.06, zb + hb)], 6, m['wood'], shape='circle', phase=ph)
    thick = 0.018
    lo = lod <= 1
    top_r = 0.03 if lod <= 2 else 0.0
    lo = lod == 0
    rings = [(roof_R * 0.95, roof_R * 0.95, z0 + H, 0.008 * lo), (roof_R, roof_R, z0 + H + thick, 0.012 * lo)]
    if lod >= 3:
        rings = [(roof_R, roof_R, z0 + H, 0.0)]
    if lo:
        rings.append((roof_R * 0.55, roof_R * 0.55, z0 + H + thick + roof_rise * 0.5, 0.0))
    rings.append((top_r, top_r, z0 + H + thick + roof_rise + (0.04 if lod >= 3 else 0.0), 0.0))
    L.srings(mb, rings, 12 if lo else 6, m['roof'], shape='hex' if lo else 'circle', phase=ph, cap_top=lod <= 2)
    ztop = z0 + H + thick + roof_rise
    if lod == 0:
        C.lathe(mb, [(0.012, 0), (0.026, 0.02), (0.028, 0.035), (0.016, 0.055), (0, 0.07)], 8, m['iron'], base=(0, 0, ztop - 0.004))
    elif lod == 1:
        C.lathe(mb, [(0.02, 0), (0.024, 0.03), (0, 0.06)], 5, m['iron'], base=(0, 0, ztop - 0.004))
    return Vector((0, 0, zb + hb / 2))


def cyl_head(mb, z0, r, H, m, lod):
    """cylindrical paper lantern standing on a post top, dark caps top and bottom"""
    segs = C.lod_pick(lod, 16, 8, 6, 5)
    bot = 0.03
    if lod <= 1:
        C.lathe(mb, [(r * 0.55, z0), (r + 0.01, z0 + 0.008), (r + 0.01, z0 + bot), (r * 0.6, z0 + bot)], segs, m['roof'])
    elif lod == 2:
        C.lathe(mb, [(r + 0.01, z0), (r + 0.01, z0 + bot)], segs, m['roof'], closed=True)
    C.lathe(mb, [(r, z0 + bot), (r, z0 + H)], segs, m['paper'], closed=lod == 0)
    if lod <= 1:
        C.lathe(mb, [(r + 0.012, z0 + H - 0.005), (r + 0.012, z0 + H + 0.025), (r * 0.55, z0 + H + 0.05), (0.02, z0 + H + 0.058),
                     (0, z0 + H + 0.058)], segs, m['roof'], closed=True)
    elif lod == 2:
        C.lathe(mb, [(r + 0.012, z0 + H - 0.005), (r + 0.012, z0 + H + 0.025), (0, z0 + H + 0.058)], segs, m['roof'], closed=True)
    else:
        C.lathe(mb, [(r + 0.01, z0 + H - 0.005), (0, z0 + H + 0.06)], segs, m['roof'], closed=False)
    if lod <= 1:    # vertical bamboo-strip ribs on the paper
        nrib = 4 if lod == 0 else 2
        for k in range(nrib):
            a = math.pi / 4 + 2 * math.pi * k / nrib
            x, y = (r + 0.003) * math.cos(a), (r + 0.003) * math.sin(a)
            C.stick(mb, (x, y, z0 + bot), (x, y, z0 + H), 0.006, 0.006, m['wood'], segs=4)
        if lod == 0:
            C.lathe(mb, [(0.012, 0), (0.016, 0.02), (0, 0.035)], 6, m['iron'], base=(0, 0, z0 + H + 0.056))
    return Vector((0, 0, z0 + bot + (H - bot) / 2))


def chochin_hang(mb, top, r, h, m, lod):
    """round chochin hanging with its top cap at `top` (x, y, z). Returns its centre."""
    tx, ty, tz = top
    segs = C.lod_pick(lod, 12, 8, 6, 4)
    cap = 0.03
    zt, zb = tz - cap, tz - h + cap
    if lod >= 3:
        C.lathe(mb, [(0, zb - 0.02), (r, (zt + zb) / 2), (0, zt + 0.02)], segs, m['paper'], base=(tx, ty, 0), phase=math.pi / 4)
        return Vector((tx, ty, (zt + zb) / 2))
    nr = C.lod_pick(lod, 7, 4, 3)
    prof = []
    for i in range(nr):
        t = i / (nr - 1)
        prof.append((r * (0.62 + 0.38 * math.sin(math.pi * t)), zb + (zt - zb) * t))
    C.lathe(mb, prof, segs, m['paper'], base=(tx, ty, 0), closed=lod <= 1)
    rc = r * 0.62 + 0.006
    for z0, z1 in ((zt - 0.004, tz), (zb - cap + 0.004, zb + 0.004)):
        C.lathe(mb, [(rc, z0), (rc, z1)], segs, m['iron'], base=(tx, ty, 0), closed=lod == 0)
    return Vector((tx, ty, (zt + zb) / 2))
