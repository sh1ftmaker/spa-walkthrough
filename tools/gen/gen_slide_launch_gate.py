"""Slide launch gate: bronze start gate with six steps up to the tube mouth, a grab bar and a water manifold.

Targets (asset row 3 x 2 x 2.8 m; lookbook 13 shows the slide's dark bronze ring language; plan 33 places the launch
at the B1 'Magma glass slide launch' beside the Lava Stair; measured with 0.17 m risers and a 2.0 m door rule):
  * six 0.17 m risers -> platform top at 1.02 m; 0.24 m treads, stair 1.30 m wide between bronze stringers.
  * platform 0.55 m deep, hinoki deck boards; tube mouth r 0.72 m (matches slide_tube r 0.66-0.74) with a flared
    bronze bell collar 0.16 m proud, mouth axis heading -Y, invert at the platform deck.
  * gate frame: two 0.18 m bronze posts at x = +-1.30, head at h (2.4-3, default 2.8) with a lintel overhanging to
    x = +-1.5 (w 3.0) and a tie beam; grab bar 1.15 m above the deck across the mouth; bronze handrails 0.9 m above
    the nosings on both sides.
  * water manifold: a bronze header pipe (r 0.045) arcing round the lower half of the bell collar with 3-5 nozzles
    aimed into the bore, a supply riser down one post with a valve hand-wheel.

Orientation: +Y front; the guest climbs towards -Y; the slide tube continues from the mouth at -Y (kz_mouth).
Parameters: h 2.4-3.0 (default 2.8 = proxy), steps (default 6), mouth_r (default 0.72), manifold_pipes 3-5
(default seeded), style 'torii' | 'portal' | 'arch' (seed cycles).
Seeds change: head style (upswept torii lintel + tie beam / flat portal with corner brackets / curved arch head),
nozzle count 3-5, supply-riser side, rail end scrolls vs ball finials, tread board count (2 or 3 boards).
Materials: bronze (smooth, dark tint) for all metal, hinoki wet_oiled for treads and deck. Lightmap; no animation.
"""
import math

import bmesh
from mathutils import Vector, Matrix

import genlib
import kzgeo_common as C

ASSET = 'slide_launch_gate'
FEATURES = ['six steps', 'bronze gate frame', 'tube mouth bell collar', 'grab bar', 'water manifold']
STYLES = ['torii', 'portal', 'arch']


def xprism(mb, poly_yz, x0, x1, mi):
    """extrude a (y, z) polygon along X between x0 and x1 (closed solid)"""
    bm = mb.bm
    a = sum(poly_yz[i][0] * poly_yz[(i + 1) % len(poly_yz)][1] - poly_yz[(i + 1) % len(poly_yz)][0] * poly_yz[i][1]
            for i in range(len(poly_yz)))
    if a < 0:
        poly_yz = poly_yz[::-1]
    A = [bm.verts.new((x0, y, z)) for y, z in poly_yz]
    B = [bm.verts.new((x1, y, z)) for y, z in poly_yz]
    fs = [bm.faces.new(A[::-1]), bm.faces.new(B)]
    n = len(poly_yz)
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def ring_y(mb, cy, cz, prof, segs, mi, a0=0.0, a1=2 * math.pi, closed_loop=True):
    """lathe about an axis parallel to Y through (0, cy, cz); prof = [(r, dy)] closed section"""
    bm = mb.bm
    n = segs if closed_loop else segs + 1
    rings = []
    for k in range(n):
        t = a0 + (a1 - a0) * k / segs
        rings.append([bm.verts.new((r * math.cos(t), cy + dy, cz + r * math.sin(t))) for r, dy in prof])
    fs = []
    m = len(prof)
    for k in range(segs):
        A, B = rings[k], rings[(k + 1) % n]
        for q in range(m):
            fs.append(bm.faces.new((A[q], A[(q + 1) % m], B[(q + 1) % m], B[q])))
    if not closed_loop:
        fs.append(bm.faces.new(rings[0])); fs.append(bm.faces.new(rings[-1][::-1]))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def build(lod, seed, h=None, w=None, d=None, steps=6, mouth_r=0.72, manifold_pipes=None, style=None):
    p = genlib.proxy(ASSET)
    H = h or p['h']
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    n_noz = manifold_pipes or g.randint(3, 5)
    riser_side = g.choice([-1, 1])
    finial = g.choice(['scroll', 'ball'])
    boards = g.choice([2, 3])
    mb = genlib.MeshBuilder()
    m_br = mb.slot('bronze', variant='smooth', tint=(0.30, 0.26, 0.22), wear=0.05)
    m_br2 = mb.slot('bronze', variant='smooth', tint=(0.55, 0.46, 0.36), wear=0.05)     # polished grab bar / rails
    m_wd = mb.slot('hinoki', variant='wet_oiled', wetness=0.5)
    bev = C.lod_pick(lod, 0.008, 0.0, 0.0, 0.0)
    seg = C.lod_pick(lod, 24, 14, 8, 6)

    RISE, TREAD = 0.17, 0.24
    zp = RISE * steps                       # deck top
    y_front = 1.0
    y_plat = y_front - TREAD * (steps - 1)  # front edge of the deck (last riser)
    y_back = -0.78                          # back edge of the deck = mouth plane
    SW = 1.30                               # stair clear width
    px = 1.30                               # gate post centre x
    mcz = zp + mouth_r - 0.06               # mouth centre: invert just under the deck

    # ---------------------------------------------------------------- stair: stringers, treads
    st_t = 0.08
    prof = []                               # stepped stringer outline (y, z), front at +y
    for i in range(steps):
        y0 = y_front - TREAD * i
        prof += [(y0, RISE * i), (y0, RISE * (i + 1))]
    prof += [(y_back, zp), (y_back, zp - 0.30), (y_front - 0.30, 0.0)]
    if lod >= 3:      # far: three notches stand in for the six risers (a stepped wedge, 32 tris)
        prof3 = []
        for i in range(3):
            y0 = y_front - 2 * TREAD * i
            prof3 += [(y0, 2 * RISE * i), (y0, 2 * RISE * (i + 1))]
        prof3 += [(y_back, zp), (y_back, zp - 0.30), (y_front - 0.30, 0.0)]
        xprism(mb, prof3, -SW / 2 - st_t, SW / 2 + st_t, m_br)
    else:
        for sx in (-1, 1):
            xprism(mb, prof, sx * SW / 2, sx * (SW / 2 + st_t), m_br)
            if lod < 2:      # stringer top flange: a proud lip that reads as a channel section
                for i in range(steps):
                    y0 = y_front - TREAD * i
                    mb.box((sx * (SW / 2 + st_t / 2), y0 - TREAD / 2 - 0.02, RISE * (i + 1) - 0.06),
                           (st_t + 0.03, 0.05, 0.05), m_br, bevel=bev)
        for i in range(steps - 1):
            y0 = y_front - TREAD * i
            zt = RISE * (i + 1)
            if lod == 0:
                nb = boards
                for b in range(nb):
                    bw = (TREAD + 0.02) / nb
                    C.board(mb, (0, y0 + 0.02 - bw * (b + 0.5), zt - 0.0225), (SW, bw - 0.008, 0.045), m_wd,
                            bevel=0.006 if lod == 0 else 0.003, segs=1)
                # bronze nosing
                mb.box((0, y0 + 0.012, zt - 0.03), (SW, 0.03, 0.06), m_br, bevel=bev)
                # riser plate (bronze, set back)
                mb.box((0, y0 - 0.01, zt - RISE / 2 - 0.03), (SW, 0.012, RISE - 0.06), m_br)
            else:
                mb.box((0, y0 - TREAD / 2 + 0.01, zt - 0.025), (SW, TREAD + 0.02, 0.05), m_wd)

    # ---------------------------------------------------------------- deck
    dw = 2 * px - 0.1
    if lod <= 1:
        nb = 5
        bw = (y_plat - y_back) / nb
        for b in range(nb):
            if lod == 0:
                C.board(mb, (0, y_plat - bw * (b + 0.5), zp - 0.0225), (dw, bw - 0.008, 0.045), m_wd, bevel=0.006)
            else:
                mb.box((0, y_plat - bw * (b + 0.5), zp - 0.0225), (dw, bw - 0.008, 0.045), m_wd)
        mb.box((0, y_plat + 0.012, zp - 0.03), (SW, 0.03, 0.06), m_br, bevel=bev)
        mb.box((0, (y_plat + y_back) / 2, zp - 0.12), (dw, y_plat - y_back, 0.14), m_br)        # deck frame
        for sx in (-1, 1):                                                                           # deck legs
            mb.box((sx * (dw / 2 - 0.06), y_back + 0.08, (zp - 0.19) / 2), (0.1, 0.1, zp - 0.19), m_br, bevel=bev)
    elif lod == 2:
        mb.box((0, (y_plat + y_back) / 2, zp - 0.1), (dw, y_plat - y_back, 0.2), m_wd)

    # ---------------------------------------------------------------- mouth bell collar (axis along -Y)
    mr = mouth_r
    if lod <= 1:
        bell = [(mr + 0.01, 0.05), (mr + 0.16, 0.02), (mr + 0.17, -0.05), (mr + 0.08, -0.10), (mr + 0.07, -0.22), (mr + 0.01, -0.22)]
    elif lod == 2:
        bell = [(mr + 0.01, 0.03), (mr + 0.16, 0.03), (mr + 0.12, -0.2), (mr + 0.01, -0.2)]
    else:
        bell = [(mr, 0.0), (mr + 0.16, -0.09), (mr, -0.18)]
    ring_y(mb, y_back, mcz, bell, seg if lod < 3 else 6, m_br)
    if lod == 0:      # bolt bosses on the collar face
        for k in range(12):
            t = 2 * math.pi * k / 12
            mb.cylinder(((mr + 0.11) * math.cos(t), y_back + 0.035, mcz + (mr + 0.11) * math.sin(t)), 0.022, 0.03, m_br2,
                        segs=6, rot=(math.pi / 2, 0, 0))

    # ---------------------------------------------------------------- gate posts + head
    pw = 0.18
    py = y_back + 0.12
    for sx in (-1, 1):
        if lod <= 1:
            C.chamfered_bar(mb, (sx * px, py, H / 2), (pw, pw, H), m_br, ch=0.02 if lod == 0 else 0.0, axis='z')
            mb.box((sx * px, py, 0.06), (pw + 0.12, pw + 0.12, 0.12), m_br, bevel=bev)                 # base shoe
        else:
            mb.box((sx * px, py, H / 2), (pw, pw, H), m_br)
    head_t = 0.2
    if style == 'torii':
        # kasagi-like lintel with upswept ends + tie beam (nuki) + centre strut
        n = C.lod_pick(lod, 12, 6, 3, 1)
        xs = [-1.5 + 3.0 * i / n for i in range(n + 1)]
        top = [(x, H - 0.04 * (abs(x) / 1.5) ** 2 * 0 - 0.0 + 0.10 * (abs(x) / 1.5) ** 3) for x in xs]
        pts = [Vector((x, py, z - head_t / 2 - 0.2)) for x, z in top]
        if lod <= 2:
            C.sweep(mb, pts, [(-0.13, 0), (0.13, 0), (0.15, head_t), (-0.15, head_t)], m_br, up=Vector((0, 0, 1)))
        else:
            mb.box((0, py, H - head_t / 2), (3.0, 0.26, head_t), m_br)
        if lod <= 2:
            mb.box((0, py, H - 0.62), (2 * px + 0.5, 0.12, 0.16), m_br, bevel=bev)                      # tie beam
            mb.box((0, py, H - 0.42), (0.16, 0.10, 0.26), m_br, bevel=bev)                              # gakuzuka strut
    elif style == 'portal':
        mb.box((0, py, H - head_t / 2 - 0.04), (2 * px + pw + 0.12, 0.24, head_t), m_br, bevel=bev)
        if lod <= 1:
            mb.box((0, py, H - 0.02), (2 * px + pw + 0.22, 0.30, 0.04), m_br, bevel=bev)               # cap plate
            for sx in (-1, 1):                                                                           # corner brackets
                tri = [(py - 0.05, H - head_t - 0.04), (py + 0.05, H - head_t - 0.04), (py + 0.05, H - head_t - 0.46)]
                for dx in (0.0,):
                    C.board(mb, (sx * (px - pw / 2 - 0.16), py, H - head_t - 0.2), (0.32, 0.06, 0.06), m_br,
                            bevel=0.004 if lod == 0 else 0.0, rot=(0, sx * math.radians(45), 0))
    else:   # arch: curved head between the posts
        n = C.lod_pick(lod, 16, 8, 4, 2)
        pts = []
        for i in range(n + 1):
            t = math.pi * i / n
            pts.append(Vector((-px * math.cos(t), py, H - 0.42 + 0.30 * math.sin(t))))
        if lod <= 2:
            C.sweep(mb, pts, [(-0.1, -0.09), (0.1, -0.09), (0.1, 0.09), (-0.1, 0.09)], m_br, up=Vector((0, 1, 0)))
            mb.box((0, py, H - 0.06), (2 * px + pw + 0.1, 0.22, 0.12), m_br, bevel=bev)                  # crown beam
            if lod <= 1:
                for x in (-0.6, 0.0, 0.6):                                                              # spandrel studs
                    zc = H - 0.42 + 0.30 * math.sin(math.acos(max(-1, min(1, -x / px))))
                    mb.box((x, py, (zc + H - 0.12) / 2 + 0.04), (0.06, 0.08, max(0.05, H - 0.12 - zc - 0.08)), m_br)
        else:
            mb.box((0, py, H - head_t / 2), (2 * px + pw, 0.22, head_t), m_br)

    # ---------------------------------------------------------------- grab bar (across the mouth)
    gz = zp + 1.15
    gy = py + 0.16
    if lod <= 2:
        C.stick(mb, (-px + pw / 2, gy, gz), (px - pw / 2, gy, gz), 0.032, 0.032, m_br2, segs=C.lod_pick(lod, 12, 8, 6))
        if lod <= 1:
            for sx in (-1, 1):
                C.stick(mb, (sx * (px - pw / 2), py, gz), (sx * (px - pw / 2), gy + 0.03, gz), 0.04, 0.04, m_br,
                        segs=C.lod_pick(lod, 10, 6))
                mb.box((sx * (px - pw / 2 - 0.01), py, gz), (0.03, 0.16, 0.16), m_br, bevel=bev)       # mount plate

    # ---------------------------------------------------------------- handrails: stair + deck
    if lod <= 2:
        rz = 0.9
        rr = C.lod_pick(lod, 0.024, 0.024, 0.03)
        for sx in (-1, 1):
            x = sx * (SW / 2 + st_t / 2)
            ya, za = y_front - 0.12, RISE + rz
            yb, zb = y_plat, zp + rz
            yc = py + pw / 2 + 0.02
            rail = [Vector((x, ya, za)), Vector((x, yb, zb)), Vector((sx * (px - pw / 2 - 0.02), yc, zb))]
            C.stick(mb, rail[0], rail[1], rr, rr, m_br2, segs=C.lod_pick(lod, 10, 6, 4))
            C.stick(mb, rail[1], rail[2], rr, rr, m_br2, segs=C.lod_pick(lod, 10, 6, 4))
            npost = C.lod_pick(lod, 3, 3, 2)
            for k in range(npost):
                t = k / (npost - 1)
                yy = ya + (yb - ya) * t; zz = za + (zb - za) * t
                i_step = min(steps - 1, max(0, int((y_front - yy) / TREAD)))
                zbase = RISE * (i_step + 1) - 0.06
                C.stick(mb, (x, yy, zbase), (x, yy, zz), 0.022, 0.022, m_br, segs=C.lod_pick(lod, 8, 6, 4))
            if lod <= 1:   # rail end
                if finial == 'ball':
                    mb.sphere(rail[0] + Vector((0, 0.03, 0)), 0.045, m_br2, segs=10 if lod == 0 else 6, rings=6 if lod == 0 else 4)
                else:
                    C.stick(mb, rail[0], rail[0] + Vector((0, 0.08, -0.12)), rr, rr * 0.9, m_br2, segs=C.lod_pick(lod, 10, 6))

    # ---------------------------------------------------------------- water manifold
    if lod <= 2:
        mr_h = mr + 0.28
        my = y_back + 0.08
        n = C.lod_pick(lod, 18, 10, 6)
        a0, a1 = math.radians(200), math.radians(340)
        arc = [Vector((mr_h * math.cos(a0 + (a1 - a0) * i / n), my, mcz + mr_h * math.sin(a0 + (a1 - a0) * i / n)))
               for i in range(n + 1)]
        C.tube(mb, arc, [0.045] * len(arc), m_br, sides=C.lod_pick(lod, 10, 6, 5), cap0=True, cap1=True)
        if lod <= 1:
            for k in range(n_noz):
                t = a0 + (a1 - a0) * (k + 0.5) / n_noz
                p0 = Vector((mr_h * math.cos(t), my, mcz + mr_h * math.sin(t)))
                p1 = Vector(((mr + 0.06) * math.cos(t), my - 0.14, mcz + (mr + 0.06) * math.sin(t)))
                C.stick(mb, p0, p1, 0.022, 0.016, m_br2, segs=C.lod_pick(lod, 8, 5))
            # supply riser down one post, with an elbow and a valve hand-wheel
            sx = riser_side
            pe = arc[0] if sx < 0 else arc[-1]
            xr = sx * (px - pw / 2 - 0.08)
            C.stick(mb, pe, Vector((xr, my, pe.z)), 0.045, 0.045, m_br, segs=C.lod_pick(lod, 10, 6))
            C.stick(mb, Vector((xr, my, pe.z + 0.04)), Vector((xr, my, 0.0)), 0.05, 0.05, m_br, segs=C.lod_pick(lod, 10, 6))
            vz = 0.75
            mb.cylinder((xr, my, vz), 0.075, 0.16, m_br, segs=C.lod_pick(lod, 10, 6))                    # valve body
            C.stick(mb, (xr, my, vz), (xr, my + 0.2, vz), 0.015, 0.015, m_br, segs=6)
            hw = [Vector((xr + 0.13 * math.cos(2 * math.pi * i / 12), my + 0.2, vz + 0.13 * math.sin(2 * math.pi * i / 12)))
                  for i in range(13)]
            C.tube(mb, hw, [0.014] * 13, m_br2, sides=C.lod_pick(lod, 6, 4))
    else:
        pass

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    C.set_json_props(o, kz_mouth={'pos': [round(dx, 3), round(y_back + dy, 3), round(mcz + dz, 3)], 'dir': [0, -1, 0], 'r': mouth_r},
                     kz_params=dict(style=style, h=H, steps=steps, mouth_r=mouth_r, manifold_pipes=n_noz,
                                    riser_side=riser_side, finial=finial, tread_boards=boards, deck_z=round(zp, 3)),
                     kz_stair={'rise': round(zp, 3), 'riser': RISE, 'tread': TREAD, 'steps': steps})
    genlib.finish(o, smooth_angle=35)
    return o
