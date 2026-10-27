"""Geometry for gen_tea_set (also used by gen_sake_counter): a tetsubin iron kettle with lid, spout, lugs
and bail handle; a tokkuri sake flask; a rounded-rectangle loft for trays and hearth rims.

All sizes in metres, +Y front, z = 0 at the base of the part. Every helper takes a genlib.MeshBuilder `mb`.
"""
import math

from mathutils import Matrix, Vector

import kzgeo_common as C


# ------------------------------------------------------------------------------------------ rounded-rect loft
def rr_loft(mb, cx, cy, z0, W, D, rc, rings, mi, m=2, cap_bottom=True, cap_top=True):
    """Loft of concentric rounded rectangles. rings = [(inset, z)] bottom -> top; ring k is the W x D
    rounded rectangle shrunk by `inset` at height z0 + z. Same vertex count on every ring, so the strip
    is quads. cap_bottom / cap_top close the first / last ring with one n-gon (a tray floor, a slab top)."""
    bm = mb.bm
    R = []
    for inset, z in rings:
        w2, d2 = W / 2 - inset, D / 2 - inset
        pts = ([(w2, d2), (-w2, d2), (-w2, -d2), (w2, -d2)] if m == 0 else
               C.rounded_rect(W - 2 * inset, D - 2 * inset, max(0.002, rc - inset), m))
        R.append([bm.verts.new((cx + x, cy + y, z0 + z)) for x, y in pts])
    faces = []
    for A, B in zip(R[:-1], R[1:]):
        faces += C.bridge_rings(bm, A, B)
    if cap_bottom:
        faces.append(bm.faces.new(R[0][::-1]))
    if cap_top:
        faces.append(bm.faces.new(R[-1]))
    mb._tag(faces, mi)
    return faces


# ------------------------------------------------------------------------------------------ tetsubin
def kettle_profile(R, Hb, lod):
    """tetsubin body + lid + knob as one closed lathe profile [(r, z)], pole to pole.
    Squat round belly (max r at 0.42 Hb), a turned foot, a flat shoulder, a lid that sits in a 3 mm step
    and a button knob. Never zero thickness at a rim (the lid is solid)."""
    if lod >= 3:                       # flat-bottomed (open underside sits on the tray): no bipyramid 'gem'
        return [(R * 0.62, 0.0), (R, Hb * 0.45), (R * 0.42, Hb * 1.0), (0.0, Hb * 1.15)]
    if lod == 2:
        return [(0.0, 0.0), (R * 0.62, 0.0), (R, Hb * 0.42), (R * 0.72, Hb * 0.92), (R * 0.42, Hb * 1.03),
                (R * 0.12, Hb * 1.12), (0.0, Hb * 1.17)]
    p = [(0.0, 0.0), (R * 0.58, 0.0), (R * 0.64, Hb * 0.04),                    # foot
         (R * 0.88, Hb * 0.14), (R * 0.985, Hb * 0.30), (R, Hb * 0.42), (R * 0.97, Hb * 0.58),   # belly
         (R * 0.86, Hb * 0.76), (R * 0.66, Hb * 0.92), (R * 0.50, Hb * 0.985),      # shoulder
         (R * 0.47, Hb * 1.0), (R * 0.455, Hb * 1.012),                           # lid seat step
         (R * 0.40, Hb * 1.045), (R * 0.22, Hb * 1.08),                           # lid dome
         (R * 0.11, Hb * 1.09), (R * 0.12, Hb * 1.13), (R * 0.09, Hb * 1.17), (0.0, Hb * 1.175)]   # knob
    if lod == 1:
        p = [p[0], p[1], p[3], p[5], p[7], p[8], p[9], p[11], p[13], p[14], p[15], p[17]]
    return p


def kettle(mb, base, R, Hb, yaw, m_iron, lod, handle_h=None):
    """Tetsubin at `base` (x, y, z): lathe body, short upturned spout towards local +X, two lugs at local
    +-X on the shoulder and an iron bail handle arching over the lid in the local X-Z plane, the spout
    under one handle end (as on a Nambu tetsubin and in lookbook 20/21: handle broadside, spout at the side). Returns the spout tip (world) for kz_fx.
    handle_h: height of the handle crown above the base (default 1.75 Hb)."""
    bx, by, bz = base
    segs = C.lod_pick(lod, 16, 10, 6, 5)
    first = mark_verts(mb)
    C.lathe(mb, kettle_profile(R, Hb, lod), segs, m_iron, base=(0, 0, 0), phase=math.pi / segs, closed=lod < 3)
    # spout: tapered tube rising out of the belly towards +X
    sp = [(R * 0.80, Hb * 0.36), (R * 1.04, Hb * 0.46), (R * 1.24, Hb * 0.60), (R * 1.38, Hb * 0.76)]
    rad = [R * 0.17, R * 0.15, R * 0.13, R * 0.115]
    if lod == 1:
        sp, rad = [sp[0], sp[2], sp[3]], [rad[0], rad[2], rad[3]]
    elif lod == 2:
        sp, rad = [sp[0], sp[3]], [rad[0], rad[3]]
    tip = None
    if lod <= 2:
        C.tube(mb, [(x, 0, z) for x, z in sp], rad, m_iron, sides=C.lod_pick(lod, 8, 6, 4), cap0=True, cap1=True)
        tip = Vector((sp[-1][0], 0, sp[-1][1]))
        if lod == 0:                                   # rolled lip on the spout mouth
            d = Vector((sp[-1][0] - sp[-2][0], 0, sp[-1][1] - sp[-2][1])).normalized()
            C.tube(mb, [tip - d * 0.002, tip + d * 0.004], [rad[-1] * 1.18, rad[-1] * 1.12], m_iron, sides=8,
                   cap0=True, cap1=True)
    # lugs (ears) on the shoulder at +-Y, and the bail handle
    hz = Hb * 0.86
    ly = R * 0.80
    hh = handle_h if handle_h else Hb * 1.75
    if lod <= 1:
        for s in (-1, 1):
            C.tube(mb, [(s * ly * 0.9, 0, hz - 0.004), (s * (ly + 0.012), 0, hz + 0.006)], [0.008, 0.007], m_iron,
                   sides=C.lod_pick(lod, 6, 4), cap0=True, cap1=True)
    n = C.lod_pick(lod, 15, 9, 5, 3)
    hw = ly + 0.012
    pts = []
    for k in range(n):
        t = k / (n - 1)
        a = math.pi * t
        y = -math.cos(a) * hw
        # squarish arch: rises steeply from the lugs, flat over the lid (superellipse)
        s = math.sin(a)
        z = hz + 0.006 + (hh - hz - 0.006) * (abs(s) ** 0.45)
        pts.append((y, 0, z))
    hr = C.lod_pick(lod, 0.0055, 0.006, 0.007, 0.008)
    C.tube(mb, pts, [hr] * n, m_iron, sides=C.lod_pick(lod, 6, 4, 3, 3), cap0=lod < 3, cap1=lod < 3)
    if lod == 0:                                       # knuckle where the handle meets each lug
        for s in (-1, 1):
            mb.sphere((s * hw, 0, hz + 0.006), 0.0085, m_iron, segs=6, rings=4)
    # place: yaw about Z, move to base
    M = Matrix.Translation((bx, by, bz)) @ Matrix.Rotation(yaw, 4, 'Z')
    for v in new_verts(mb, first):
        v.co = M @ v.co
    return (M @ tip) if tip is not None else Vector((bx, by, bz + Hb))


def mark_verts(mb):
    """mark every existing vert in an int layer; new_verts() then returns the verts made since. (bmesh
    reuses freed slots after a delete, so 'verts after index n' is not safe once anything was deleted.)"""
    bm = mb.bm
    lay = bm.verts.layers.int.get('_vold') or bm.verts.layers.int.new('_vold')
    for v in bm.verts:
        v[lay] = 1
    return lay


def new_verts(mb, lay):
    return [v for v in mb.bm.verts if v[lay] == 0]


def place_new(mb, first, base, yaw=0.0):
    """move every vert created since mark_verts() returned `first` by yaw about Z and then to base"""
    M = Matrix.Translation(base) @ Matrix.Rotation(yaw, 4, 'Z')
    for v in new_verts(mb, first):
        v.co = M @ v.co


# ------------------------------------------------------------------------------------------ tokkuri + cups
def tokkuri_profile(R, H, lod):
    """sake flask: foot, round belly, long neck, flared lip with a short opening (closed solid)"""
    if lod >= 3:                       # flat-bottomed, open underside, capped mouth
        return [(R * 0.75, 0.0), (R, H * 0.42), (R * 0.28, H)]
    if lod == 2:
        return [(0.0, 0.0), (R * 0.68, 0.0), (R, H * 0.36), (R * 0.42, H * 0.74), (R * 0.36, H * 0.96),
                (R * 0.28, H), (0.0, H * 0.94)]
    p = [(0.0, 0.0), (R * 0.62, 0.0), (R * 0.68, H * 0.03), (R * 0.93, H * 0.16), (R, H * 0.34), (R * 0.88, H * 0.52),
         (R * 0.55, H * 0.68), (R * 0.36, H * 0.80), (R * 0.33, H * 0.93), (R * 0.42, H * 0.985), (R * 0.40, H),
         (R * 0.27, H * 0.995), (R * 0.24, H * 0.95), (0.0, H * 0.94)]
    if lod == 1:
        p = [p[0], p[1], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[11], p[13]]
    return p
