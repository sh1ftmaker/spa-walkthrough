"""kzgeo_guest_figure: the shared figure kit (base body, rig, weights, poses) for guest_figure and staff_figure.

One base body for every person in Kazan-yu. Proportions come from a body type (adult_woman, adult_man, elder,
child) scaled to a height; girth comes from `build` (0 slim .. 1 heavy) and is also stored as two shape keys
(`build_slim`, `build_heavy`) so the runtime can re-proportion an instance without a rebuild. Clothing layers
are separate shells built on the same skeleton (yukata, towel wrap, swimsuit here; samue, apron, headband in
kzgeo_staff_figure).

Rig: 24 deform bones (root, pelvis, spine, chest, neck, head, clavicle/upperarm/forearm/hand L+R,
thigh/shin/foot/toe L+R, prop_L, prop_R). The mesh data is always the BIND pose (standing, arms 12 deg out,
elbows 10 deg bent). Every part is skinned by distance to the bone segments it may follow (top 3 bones,
1/d^4, normalised); rigid parts (head, hair, hands, geta, props) are 100 % on one bone. A pose (walking,
seated, soaking, floating, serve ...) is stored on the armature, which is parented to the mesh and drives it
through an Armature modifier, so `genlib.check` measures the bind mesh while renders show the pose.
Props (tray, towels, noodle basket) ride the prop bones: they are placed in their own frame, at a compact
bind position by the hand, and the pose moves them to the working position.

Conventions: +Y is the figure's front, +X is the figure's RIGHT (bones *_R at +X), z = 0 is the floor.
"""
import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import genlib
import kzgeo_common as C

# ------------------------------------------------------------------------------------------- proportions
# heights as a fraction of H; widths in metres at the reference height `Href` (scaled by H / Href)
BODIES = {
    'adult_woman': dict(H=1.65, Hr=(1.55, 1.72), Href=1.65, head=0.132, ankle=0.045, knee=0.28, hip=0.515, pelvis=0.54,
                        waist=0.615, chest=0.72, shoulder=0.812, neckb=0.83, sh=0.163, hipj=0.083, upper=0.186, fore=0.148,
                        hand=0.105, foot=0.145, chest_w=(0.135, 0.10), waist_w=(0.115, 0.088), hips_w=(0.165, 0.112),
                        neck_r=0.048, bust=0.03, hem=0.032, obi_c=0.615, obi_w=0.09, sex=1),
    'adult_man': dict(H=1.78, Hr=(1.66, 1.85), Href=1.78, head=0.128, ankle=0.045, knee=0.285, hip=0.52, pelvis=0.545,
                      waist=0.62, chest=0.725, shoulder=0.818, neckb=0.835, sh=0.19, hipj=0.09, upper=0.188, fore=0.15,
                      hand=0.108, foot=0.15, chest_w=(0.165, 0.112), waist_w=(0.142, 0.1), hips_w=(0.16, 0.105),
                      neck_r=0.058, bust=0.0, hem=0.05, obi_c=0.57, obi_w=0.055, sex=0),
    'elder': dict(H=1.58, Hr=(1.48, 1.66), Href=1.58, head=0.135, ankle=0.045, knee=0.28, hip=0.51, pelvis=0.535,
                  waist=0.61, chest=0.715, shoulder=0.805, neckb=0.825, sh=0.158, hipj=0.083, upper=0.186, fore=0.148,
                  hand=0.105, foot=0.145, chest_w=(0.135, 0.105), waist_w=(0.128, 0.098), hips_w=(0.165, 0.112),
                  neck_r=0.046, bust=0.012, hem=0.03, obi_c=0.6, obi_w=0.075, sex=1, stoop=1),
    'child': dict(H=1.12, Hr=(1.02, 1.28), Href=1.12, head=0.185, ankle=0.05, knee=0.265, hip=0.47, pelvis=0.495,
                  waist=0.57, chest=0.655, shoulder=0.745, neckb=0.77, sh=0.118, hipj=0.06, upper=0.172, fore=0.14,
                  hand=0.1, foot=0.15, chest_w=(0.1, 0.075), waist_w=(0.095, 0.072), hips_w=(0.105, 0.075),
                  neck_r=0.036, bust=0.0, hem=0.06, obi_c=0.585, obi_w=0.085, sex=2),
}

BONES = ['root', 'pelvis', 'spine', 'chest', 'neck', 'head', 'clavicle_L', 'upperarm_L', 'forearm_L', 'hand_L',
         'clavicle_R', 'upperarm_R', 'forearm_R', 'hand_R', 'thigh_L', 'shin_L', 'foot_L', 'toe_L',
         'thigh_R', 'shin_R', 'foot_R', 'toe_R', 'prop_L', 'prop_R']
PARENT = dict(pelvis='root', spine='pelvis', chest='spine', neck='chest', head='neck', clavicle_L='chest',
              upperarm_L='clavicle_L', forearm_L='upperarm_L', hand_L='forearm_L', clavicle_R='chest',
              upperarm_R='clavicle_R', forearm_R='upperarm_R', hand_R='forearm_R', thigh_L='pelvis', shin_L='thigh_L',
              foot_L='shin_L', toe_L='foot_L', thigh_R='pelvis', shin_R='thigh_R', foot_R='shin_R', toe_R='foot_R',
              prop_L='hand_L', prop_R='hand_R')
CLIPS_GUEST = ['idle', 'walk', 'sit', 'soak', 'float']
# robe skirt skinning (op28, animation clips): the shins pull the hem less and the falloff is softer, so the
# skirt drapes between the legs instead of tearing between them in walk / sit clips
ROBE_WSCALE = dict(shin_L=0.35, shin_R=0.35)
ROBE_POWER = 2.5


def rx(a):
    return Matrix.Rotation(math.radians(a), 4, 'X')


def ry(a):
    return Matrix.Rotation(math.radians(a), 4, 'Y')


def rz(a):
    return Matrix.Rotation(math.radians(a), 4, 'Z')


# ------------------------------------------------------------------------------------------- skeleton
class Skeleton:
    """Joint positions of the bind pose. side s = -1 for L (figure's left, -X), +1 for R."""

    def __init__(self, body, H, build=0.5):
        B = dict(BODIES[body])
        self.B, self.H, self.body = B, H, body
        self.k = H / B['Href']                      # width scale
        self.g = 0.88 + 0.26 * build                # girth factor (radii only, never joints)
        f = lambda key: B[key] * H
        self.z = {n: f(n) for n in ('ankle', 'knee', 'hip', 'pelvis', 'waist', 'chest', 'shoulder', 'neckb')}
        self.head_h = B['head'] * H
        self.chin = H - self.head_h
        J = {}
        J['root'] = Vector((0, 0, 0))
        J['pelvis'] = Vector((0, 0, self.z['pelvis']))
        J['waist'] = Vector((0, -0.005, self.z['waist']))
        J['chestj'] = Vector((0, -0.01, self.z['chest']))
        J['neckb'] = Vector((0, -0.015, self.z['neckb']))
        J['headb'] = Vector((0, -0.005, self.chin + 0.25 * self.head_h))
        J['top'] = Vector((0, -0.005, H))
        sh, hj = B['sh'] * self.k, B['hipj'] * self.k
        up_l, fo_l, ha_l = B['upper'] * H, B['fore'] * H, B['hand'] * H
        abd = math.radians(6)
        for s, S in ((-1, 'L'), (1, 'R')):
            J['clav' + S] = Vector((s * 0.025 * self.k, -0.005, self.z['shoulder'] - 0.01))
            sj = Vector((s * sh, -0.015, self.z['shoulder'] - 0.035 * self.k))
            J['shoulder' + S] = sj
            d_up = Vector((s * math.sin(abd), 0.04, -math.cos(abd))).normalized()
            J['elbow' + S] = sj + d_up * up_l
            d_fo = Vector((s * math.sin(abd) * 0.8, 0.2, -1)).normalized()
            J['wrist' + S] = J['elbow' + S] + d_fo * fo_l
            J['handtip' + S] = J['wrist' + S] + Vector((s * 0.05, 0.12, -1)).normalized() * ha_l
            J['hip' + S] = Vector((s * hj, 0, self.z['hip']))
            J['knee' + S] = Vector((s * hj * 0.95, 0.012, self.z['knee']))
            J['ankle' + S] = Vector((s * hj * 0.9, -0.005, self.z['ankle']))
            fl = B['foot'] * H
            J['ball' + S] = Vector((s * hj * 0.95, 0.56 * fl, 0.018 * self.k))
            J['toe' + S] = Vector((s * hj, 0.78 * fl, 0.012 * self.k))
            J['heel' + S] = Vector((s * hj * 0.9, -0.24 * fl, 0.0))
        self.J = J
        heads = dict(root=J['root'], pelvis=J['pelvis'], spine=J['waist'], chest=J['chestj'], neck=J['neckb'],
                     head=J['headb'])
        tails = dict(root=J['pelvis'] * 0.5 + Vector((0, 0.1, 0)), pelvis=J['waist'], spine=J['chestj'],
                     chest=J['neckb'], neck=J['headb'], head=J['top'])
        for S in 'LR':
            heads['clavicle_' + S], tails['clavicle_' + S] = J['clav' + S], J['shoulder' + S]
            heads['upperarm_' + S], tails['upperarm_' + S] = J['shoulder' + S], J['elbow' + S]
            heads['forearm_' + S], tails['forearm_' + S] = J['elbow' + S], J['wrist' + S]
            heads['hand_' + S], tails['hand_' + S] = J['wrist' + S], J['handtip' + S]
            heads['thigh_' + S], tails['thigh_' + S] = J['hip' + S], J['knee' + S]
            heads['shin_' + S], tails['shin_' + S] = J['knee' + S], J['ankle' + S]
            heads['foot_' + S], tails['foot_' + S] = J['ankle' + S], J['ball' + S]
            heads['toe_' + S], tails['toe_' + S] = J['ball' + S], J['toe' + S]
            g = J['wrist' + S].lerp(J['handtip' + S], 0.5)
            heads['prop_' + S], tails['prop_' + S] = g, g + Vector((0, 0.08, 0))
        self.heads, self.tails = heads, tails

    def seg(self, b):
        return self.heads[b], self.tails[b]


# ------------------------------------------------------------------------------------------- geometry kit
def sring(z, hw, hd, n, p=2.6, yc=0.0, front=0.0, back=0.0, phase=0.0, xc=0.0):
    """superellipse ring at height z (points, counter-clockwise from +X). front/back push the +Y / -Y side."""
    pts = []
    for k in range(n):
        t = phase + 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        x = hw * math.copysign(abs(c) ** (2 / p), c)
        y = hd * math.copysign(abs(s) ** (2 / p), s)
        if s > 0:
            y += front * s ** 2
        else:
            y -= back * s ** 2
        pts.append(Vector((xc + x, yc + y, z)))
    return pts


def limb_frame(axis):
    a = Vector(axis).normalized()
    X = Vector((1, 0, 0))
    u = X - a * X.dot(a)
    if u.length < 1e-4:
        u = Vector((0, 0, 1)) - a * a.z
    u.normalize()
    v = u.cross(a).normalized()                  # ~ +Y for limbs pointing down, ~ +Z for feet pointing +Y
    return u, v


def lring(c, axis, ru, rv, n, phase=0.0, vpush=0.0):
    """elliptical ring around point c, normal to axis; ru along the limb's sideways (X-ish), rv front."""
    u, v = limb_frame(axis)
    pts = []
    for k in range(n):
        t = phase + 2 * math.pi * k / n
        cs, sn = math.cos(t), math.sin(t)
        pts.append(Vector(c) + u * (ru * cs) + v * (rv * sn + (vpush * sn * sn if sn > 0 else 0)))
    return pts


class Fig:
    """MeshBuilder wrapper: every vertex carries the part id it was built in (for skinning)."""

    def __init__(self, sk, lod):
        self.sk, self.lod = sk, lod
        self.mb = genlib.MeshBuilder()
        self.bm = self.mb.bm
        self.lay = self.bm.verts.layers.int.new('kzpart')
        self.parts = [None]                          # id 0 = unassigned
        self.stats = {}
        self.cur = None

    def part(self, bones, rigid=False, wscale=None, power=4):
        """start a part; bones = candidate bone names (rigid: the single bone). wscale {bone: factor} and the
        distance power soften cloth shells (robe skirts follow the thighs more than the shins)."""
        self.close()
        self.parts.append((tuple(bones), rigid, dict(wscale or {}), power))
        self.cur = len(self.parts) - 1
        self._t0 = C.tri_count(self.bm)

    def close(self):
        if self.cur is not None:
            lab = ','.join(self.parts[self.cur][0][:2])
            self.stats[lab] = self.stats.get(lab, 0) + C.tri_count(self.bm) - self._t0
            for v in self.bm.verts:
                if v[self.lay] == 0:
                    v[self.lay] = self.cur
        self.cur = None

    def shift_y(self, dy):
        for v in self.bm.verts:
            v.co.y += dy
        sk = self.sk
        for d in (sk.J, sk.heads, sk.tails):
            for key in d:
                d[key] = d[key] + Vector((0, dy, 0))

    def slot(self, *a, **k):
        return self.mb.slot(*a, **k)

    # ---- primitives
    def loft(self, rings, mi, cap0=False, cap1=False, mis=None):
        """rings: list of point lists (equal length). mis: optional per-band slot list."""
        bm = self.bm
        R = [[bm.verts.new(p) for p in r] for r in rings]
        faces = []
        for i in range(len(R) - 1):
            fs = C.bridge_rings(bm, R[i], R[i + 1])
            m = mis[i] if mis else mi
            for f in fs:
                f.material_index = m
            faces += fs
        if cap0:
            f = bm.faces.new(R[0][::-1]); f.material_index = mis[0] if mis else mi; faces.append(f)
        if cap1:
            f = bm.faces.new(R[-1]); f.material_index = mis[-1] if mis else mi; faces.append(f)
        return R, faces

    def pole_loft(self, bottom, rings, top, mi):
        """closed blob: bottom pole point, rings, top pole point"""
        bm = self.bm
        R = [[bm.verts.new(p) for p in r] for r in rings]
        faces = []
        for i in range(len(R) - 1):
            faces += C.bridge_rings(bm, R[i], R[i + 1])
        n = len(R[0])
        if bottom is not None:
            b = bm.verts.new(bottom)
            for k in range(n):
                faces.append(bm.faces.new((R[0][(k + 1) % n], R[0][k], b)))
        if top is not None:
            t = bm.verts.new(top)
            for k in range(n):
                faces.append(bm.faces.new((R[-1][k], R[-1][(k + 1) % n], t)))
        for f in faces:
            f.material_index = mi
        return R, faces

    def blob(self, c, r3, mi, segs=8, rings=5, M=None):
        """ellipsoid (radii r3) at c, optional rotation matrix M (3x3)"""
        rr = []
        for i in range(1, rings):
            ph = math.pi * i / rings
            ring = []
            for k in range(segs):
                t = 2 * math.pi * k / segs
                d = Vector((math.sin(ph) * math.cos(t) * r3[0], math.sin(ph) * math.sin(t) * r3[1], -math.cos(ph) * r3[2]))
                ring.append(Vector(c) + (M @ d if M else d))
            rr.append(ring)
        bot = Vector((0, 0, -r3[2])); top = Vector((0, 0, r3[2]))
        if M:
            bot, top = M @ bot, M @ top
        return self.pole_loft(Vector(c) + bot, rr, Vector(c) + top, mi)

    def band(self, pts, nrms, w, t, mi, closed=False):
        """flat strap of width w and thickness t lying on a surface (normals nrms) along pts"""
        bm = self.bm
        n = len(pts)
        rings = []
        for i in range(n):
            if closed:
                tg = pts[(i + 1) % n] - pts[i - 1]
            else:
                tg = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
            nr = Vector(nrms[i]).normalized()
            sd = tg.cross(nr).normalized()
            p = Vector(pts[i])
            rings.append([bm.verts.new(p + sd * (w / 2) - nr * 0.002), bm.verts.new(p + sd * (w / 2) + nr * t),
                          bm.verts.new(p - sd * (w / 2) + nr * t), bm.verts.new(p - sd * (w / 2) - nr * 0.002)])
        faces = []
        for i in range(n if closed else n - 1):
            faces += C.bridge_rings(bm, rings[i], rings[(i + 1) % n])
        if not closed:
            faces.append(bm.faces.new(rings[0][::-1])); faces.append(bm.faces.new(rings[-1]))
        for f in faces:
            f.material_index = mi
        return faces

    def box(self, c, size, mi, M=None):
        bm = self.bm
        r = bmesh.ops.create_cube(bm, size=1.0)
        vs = r['verts']
        bmesh.ops.scale(bm, vec=size, verts=vs)
        T = Matrix.Translation(c) @ (M.to_4x4() if M is not None else Matrix.Identity(4))
        bmesh.ops.transform(bm, matrix=T, verts=vs)
        fs = C._faces_of(vs)
        for f in fs:
            f.material_index = mi
        return fs


# ------------------------------------------------------------------------------------------- body parts
def nseg(lod, a, b, c, d):
    return C.lod_pick(lod, a, b, c, d)


def head_and_face(F, mi_skin, hs=1.0):
    """skull + face as one closed blob (jaw taper, flat face, nose, chin, ears at LOD0)."""
    sk, lod = F.sk, F.lod
    hh = sk.head_h
    hz = hh * 0.5
    hx, hy = hh * 0.36 * hs, hh * 0.42 * hs
    c = Vector((0, 0.005, sk.chin + hz))
    segs = nseg(lod, 16, 10, 8, 6)
    rings = nseg(lod, 9, 6, 4, 3)
    F.head_c, F.head_r = c, (hx, hy, hz)
    rr = []
    nose_i = None
    for i in range(1, rings):
        ph = math.pi * i / rings
        z = -math.cos(ph)
        ring = []
        for k in range(segs):
            t = 2 * math.pi * k / segs - math.pi / 2         # k = segs/2 -> front (+Y)
            sx, sy = math.sin(ph) * math.cos(t), math.sin(ph) * math.sin(t)
            x, y = sx * hx, sy * hy
            if z < 0:
                x *= 1 - 0.3 * (-z) ** 1.4                    # jaw taper
                if sy > 0:
                    y *= 1 - 0.08 * (-z)
            if sy > 0.2:
                y *= 0.93                                     # flatter face
            if sy < 0 and z > -0.2:
                y *= 1.06                                     # cranium
            ring.append(c + Vector((x, y, z * hz)))
        if lod <= 1 and nose_i is None and z > -0.45:
            nose_i = len(rr)
        rr.append(ring)
    if lod <= 1:
        fr = segs // 2
        rr[nose_i][fr] += Vector((0, 0.022 * hh / 0.22, -0.006))   # nose tip
        nb = rr[nose_i - 1][fr]
        nb += Vector((0, 0.008 * hh / 0.22, 0))                   # chin / philtrum fill
    R, faces = F.pole_loft(c + Vector((0, 0.012, -hz * 0.96)), rr, c + Vector((0, -0.006, hz)), mi_skin)
    if lod == 0:
        for s in (-1, 1):                                          # ears: small flattened blobs
            F.blob(c + Vector((s * hx * 0.97, -0.01, -0.06 * hz)), (0.012, 0.022, 0.03), mi_skin, segs=5, rings=3)
    return R


def hair(F, style, mi_hair, mi_tie=None):
    """hair cap shell cut by a plane tilted back (high at the forehead, low at the nape) + bun / topknot."""
    sk, lod = F.sk, F.lod
    c, (hx, hy, hz) = F.head_c, F.head_r
    vol = dict(bun=1.07, short=1.09, topknot=1.07, bob=1.1, grey_bun=1.07, buns2=1.07).get(style, 1.07)
    tilt = math.radians(dict(bob=28, short=38).get(style, 40))
    phmax = math.radians(dict(bob=118, short=98).get(style, 102))
    n = Vector((0, -math.sin(tilt), math.cos(tilt)))
    a = Vector((1, 0, 0)); b = n.cross(a)
    segs = nseg(lod, 14, 10, 6, 6)
    rings = nseg(lod, 4, 3, 2, 1)
    rr = []
    for i in range(1, rings + 1):
        ph = phmax * i / rings
        ring = []
        for k in range(segs):
            t = 2 * math.pi * k / segs
            d = n * math.cos(ph) + (a * math.cos(t) + b * math.sin(t)) * math.sin(ph)
            sc = vol if i < rings else vol * 0.985
            ring.append(c + Vector((d.x * hx * sc, d.y * hy * sc, d.z * hz * sc)) + Vector((0, -0.004, 0.006)))
        rr.append(ring)
    # rim: tuck the edge into the scalp (no knife edge)
    last = rr[-1]
    rr.append([c + (p - c) * 0.93 for p in last])
    top = c + Vector((n.x * hx * vol, n.y * hy * vol, n.z * hz * vol)) + Vector((0, -0.004, 0.006))
    F.pole_loft(None, rr[::-1], top, mi_hair)
    if style == 'bob' and lod <= 2:
        pass
    knot = dict(bun=(0, -0.85, 0.55, 0.36), grey_bun=(0, -0.8, 0.6, 0.34), topknot=(0, -0.55, 0.9, 0.2),
                buns2=(0, -0.2, 1.0, 0.27)).get(style)
    if knot:
        dx, dy, dz, r = knot
        d = Vector((dx, dy, dz)).normalized()
        pc = c + Vector((d.x * hx, d.y * hy * 1.05, d.z * hz)) * 1.0 + d * (r * hz * 0.7)
        R = r * hz
        bs, br = nseg(lod, 8, 6, 5, 4), nseg(lod, 5, 4, 3, 3)
        if style == 'topknot':
            F.blob(pc, (R * 0.8, R * 1.4, R * 0.75), mi_hair, segs=bs, rings=br, M=Matrix.Rotation(-0.5, 3, 'X'))
        else:
            F.blob(pc, (R * 1.05, R * 0.9, R * 0.95), mi_hair, segs=bs, rings=br)
        if mi_tie is not None and lod == 0:                        # comb / tie band at the bun root
            q = c + Vector((d.x * hx, d.y * hy * 1.05, d.z * hz)) * 1.0 + d * (R * 0.15)
            F.blob(q, (R * 0.7, R * 0.25, R * 0.7), mi_tie, segs=6, rings=3,
                   M=Vector((0, 1, 0)).rotation_difference(d).to_matrix())


def neck(F, mi, z0=None, r_scale=1.0):
    sk, lod = F.sk, F.lod
    r = sk.B['neck_r'] * sk.k * r_scale * (0.92 + 0.1 * sk.g)
    a = Vector((0, -0.02, z0 if z0 is not None else sk.z['neckb'] - 0.03))
    b = Vector((0, 0.0, sk.chin + 0.04 * sk.head_h / 0.22))
    n = nseg(lod, 10, 8, 6, 4)
    rings = [sring(a.z, r * 1.15, r * 1.05, n, p=2, yc=a.y), sring(b.z, r, r * 0.95, n, p=2, yc=b.y)]
    F.loft(rings, mi)


def arm(F, S, mi, from_elbow=False, upper_mi=None, fore_r=1.0, cut=None):
    """upper arm (optional) and forearm tube; ends at the wrist. cut: fraction of forearm to start from."""
    sk, lod = F.sk, F.lod
    J, g = sk.J, sk.g
    s = -1 if S == 'L' else 1
    n = nseg(lod, 10, 8, 6, 4)
    k = sk.k * g
    sj, el, wr = J['shoulder' + S], J['elbow' + S], J['wrist' + S]
    ua, fa = (el - sj).normalized(), (wr - el).normalized()
    rings = []
    if not from_elbow:
        rings += [lring(sj + Vector((s * -0.01, 0, 0.02)), ua, 0.052 * k, 0.055 * k, n),
                  lring(sj.lerp(el, 0.3), ua, 0.047 * k, 0.05 * k, n),
                  lring(sj.lerp(el, 0.75), ua, 0.04 * k, 0.042 * k, n)]
    st = cut if cut is not None else (0.0 if not from_elbow else -0.05)
    pe = el + fa * (st * (wr - el).length)
    rings += [lring(pe, fa, 0.037 * k * fore_r, 0.037 * k * fore_r, n),
              lring(el.lerp(wr, max(st, 0.0) * 0.5 + 0.4), fa, 0.036 * k * fore_r, 0.033 * k * fore_r, n),
              lring(wr - fa * 0.01, fa, 0.026 * sk.k, 0.022 * sk.k, n)]
    if lod >= 2:
        rings = rings[::2] if len(rings) > 3 else [rings[0], rings[-1]]
    F.loft(rings, mi, cap1=True)


def hand(F, S, mi):
    """mitten hand: palm loft + thumb, slightly cupped, rigid on hand_S"""
    sk, lod = F.sk, F.lod
    J = sk.J
    s = -1 if S == 'L' else 1
    wr, tip = J['wrist' + S], J['handtip' + S]
    ax = (tip - wr).normalized()
    L = (tip - wr).length
    k = sk.k
    n = nseg(lod, 8, 4, 4, 4)
    rs = [(0.024, 0.014), (0.034, 0.013), (0.033, 0.011), (0.022, 0.008)]
    ts = [0.0, 0.35, 0.72, 1.0]
    if lod >= 1:
        rs, ts = [rs[0], rs[2], rs[3]], [0.0, 0.72, 1.0]
    if lod >= 2:
        rs, ts = [rs[0], rs[2]], [0.0, 0.85]
    rings = [lring(wr + ax * (t * L), ax, r[0] * k, r[1] * k, n, phase=math.pi / 2 * 0) for t, r in zip(ts, rs)]
    # palm faces the thigh: rotate rings so the flat side is along X (u) -> swap: build with ru small
    rings = [lring(wr + ax * (t * L), ax, r[1] * k, r[0] * k, n) for t, r in zip(ts, rs)]
    F.loft(rings, mi, cap0=True, cap1=True)
    if lod == 0:
        a = wr + ax * 0.25 * L + Vector((0, 0.02 * k, 0))
        b = a + (ax * 0.5 + Vector((-s * 0.25, 0.8, 0))).normalized() * 0.045 * k
        C.stick(F.mb, a, b, 0.011 * k, 0.008 * k, mi, segs=5)


def leg(F, S, mi, z_from=None, mis=None):
    """thigh + shin tube from the hip (or from height z_from) to the ankle."""
    sk, lod = F.sk, F.lod
    J, g = sk.J, sk.g
    k = sk.k * g
    n = nseg(lod, 10, 8, 6, 4)
    hp, kn, an = J['hip' + S], J['knee' + S], J['ankle' + S]
    s = -1 if S == 'L' else 1
    th = (kn - hp).normalized(); sh = (an - kn).normalized()
    full = [(hp + Vector((s * 0.008, 0, 0.03)), th, 0.088, 0.09, 1.0),
            (hp.lerp(kn, 0.4), th, 0.074, 0.076, 1.0),
            (hp.lerp(kn, 0.85), th, 0.056, 0.058, 1.0),
            (kn + Vector((0, 0.005, -0.03)), sh, 0.05, 0.052, 1.0),
            (kn.lerp(an, 0.35), sh, 0.05, 0.056, 1.0),
            (kn.lerp(an, 0.75), sh, 0.034, 0.036, 1.0),
            (an + Vector((0, 0, 0.012)), sh, 0.028, 0.03, 0.97)]
    if z_from is not None:
        full = [r for r in full if r[0].z <= z_from + 0.02]
    if lod >= 2:
        full = full[::2] + ([full[-1]] if len(full) % 2 == 0 else [])
    rings = [lring(c, a, ru * k, rv * k, n) for c, a, ru, rv, _ in full]
    F.loft(rings, mi, cap0=z_from is not None, mis=mis)


def foot(F, S, mi):
    sk, lod = F.sk, F.lod
    J, k = sk.J, sk.k
    an, he, ba, to = J['ankle' + S], J['heel' + S], J['ball' + S], J['toe' + S]
    n = nseg(lod, 6, 4, 4, 4)
    fl = sk.B['foot'] * sk.H
    y0 = he.y
    sec = [(y0 + 0.01, 0.022, 0.035, 0.035), (y0 + 0.25 * fl, 0.03, 0.05, 0.055), (ba.y, 0.04, 0.022, 0.03),
           (to.y + 0.03, 0.034, 0.012, 0.014)]
    if lod >= 2:
        sec = [sec[0], sec[2], sec[3]]
    rings = []
    for y, hw, hh, zc in sec:
        rings.append(lring(Vector((an.x, y, zc * k)), Vector((0, 1, 0)), hw * k, hh * k, n))
    F.loft(rings, mi, cap0=True, cap1=True)


def torso(F, mi, z_top=None, mis_fn=None):
    """full skin torso (crotch to neck base) with bust and shoulder shaping."""
    sk, lod = F.sk, F.lod
    B, k, g, z = sk.B, sk.k, sk.g, sk.z
    n = nseg(lod, 16, 10, 6, 5)
    sh = B['sh'] * k
    cw, ww, hw = B['chest_w'], B['waist_w'], B['hips_w']
    lv = [(z['hip'] - 0.05 * k, hw[0] * 0.82, hw[1] * 0.9, 0, 0.0),
          (z['hip'] + 0.03 * k, hw[0], hw[1], 0, 0.01),
          (z['waist'], ww[0], ww[1], 0.005, 0.0),
          ((z['waist'] + z['chest']) / 2, (ww[0] + cw[0]) / 2, (ww[1] + cw[1]) / 2, 0.005, B['bust'] * 0.4),
          (z['chest'], cw[0], cw[1], 0, B['bust']),
          (z['shoulder'] - 0.04 * k, sh + 0.02 * k, cw[1] * 0.9, -0.005, B['bust'] * 0.2),
          (z['neckb'] - 0.005, B['neck_r'] * k * 1.6, B['neck_r'] * k * 1.25, -0.015, 0)]
    if z_top is not None:
        lv = [l for l in lv if l[0] <= z_top + 0.01]
    if lod >= 2:
        lv = [lv[0], lv[2], lv[4], lv[-1]] if len(lv) == 7 else lv[::2]
    rings = []
    for zz, a, b, yc, fr in lv:
        gg = g if zz < z['shoulder'] - 0.05 else 1.0
        rings.append(sring(zz, a * gg, b * gg, n, p=2.3, yc=yc, front=fr * gg))
    mis = mis_fn([l[0] for l in lv]) if mis_fn else None
    F.loft(rings, mi, cap0=True, cap1=z_top is None, mis=mis)


# ------------------------------------------------------------------------------------------- robe (yukata) kit
class Robe:
    """Wrap robe profile: superellipse rings interpolated over height; front_y(x, z) gives the surface."""

    def __init__(self, sk, levels, p=2.6):
        self.lv = sorted(levels, key=lambda l: l[0])            # (z, hw, hd, yc)
        self.p = p

    def at(self, z):
        lv = self.lv
        if z <= lv[0][0]:
            return lv[0][1:]
        for a, b in zip(lv[:-1], lv[1:]):
            if a[0] <= z <= b[0]:
                t = (z - a[0]) / max(1e-6, b[0] - a[0])
                return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
        return lv[-1][1:]

    def front(self, x, z, off=0.0):
        hw, hd, yc = self.at(z)
        u = min(0.999, abs(x) / hw)
        y = yc + hd * (1 - u ** self.p) ** (1 / self.p)
        nrm = Vector(((abs(x) / hw) ** (self.p - 1) * math.copysign(1, x) / hw, (max(0, y - yc) / hd) ** (self.p - 1) / hd, 0))
        nrm = nrm.normalized() if nrm.length > 1e-6 else Vector((0, 1, 0))
        return Vector((x, y, z)) + nrm * off, nrm


def yukata(F, mats, cfg):
    """Robe, collar, front edge, hem, obi with cord and bow, wide tamoto sleeves. cfg keys:
    hem_z, obi_c, obi_w, bow ('butterfly' | 'knot' | 'heko'), sleeve_len (0..1 of arm), v_z (collar cross)."""
    sk, lod = F.sk, F.lod
    B, k, g, z, J = sk.B, sk.k, sk.g, sk.z, sk.J
    m_robe, m_obi, m_cord, m_skin, m_pat = mats['robe'], mats['obi'], mats.get('cord'), mats['skin'], mats.get('pattern')
    F.part(['pelvis', 'spine', 'chest', 'thigh_L', 'thigh_R', 'shin_L', 'shin_R', 'clavicle_L', 'clavicle_R'],
           wscale=ROBE_WSCALE, power=ROBE_POWER)
    n = nseg(lod, 16, 10, 6, 5)
    sh = B['sh'] * k
    cw, ww, hw = B['chest_w'], B['waist_w'], B['hips_w']
    hem = cfg['hem_z']
    hem_hw = cfg.get('hem_hw', hw[0] * 1.02)
    ease = 0.022 * k
    levels = [(hem, hem_hw * g, hw[1] * 1.12 * g, 0.004),
              ((hem + z['knee']) / 2, (hem_hw + hw[0]) / 2 * 1.02 * g, hw[1] * 1.12 * g, 0.006),
              (z['knee'] + 0.05, hw[0] * 1.05 * g + ease * 0.5, hw[1] * 1.1 * g, 0.008),
              (z['hip'] + 0.02 * k, hw[0] * g + ease, hw[1] * g + ease, 0.006),
              (z['waist'], ww[0] * g + ease * 1.2, ww[1] * g + ease, 0.006),
              (z['chest'], cw[0] * g + ease, cw[1] * g + ease + B['bust'] * 0.6, 0.0),
              (z['shoulder'] - 0.045 * k, sh + 0.035 * k, cw[1] * 0.92 * g + ease * 0.6, -0.008),
              (z['neckb'] + 0.01, B['neck_r'] * k * 1.45, B['neck_r'] * k * 1.3, cfg.get('nuki', -0.02))]
    robe = Robe(sk, levels)
    F.robe = robe
    # obi zone: the robe is pulled in slightly under the obi
    oz0, oz1 = cfg['obi_c'] - cfg['obi_w'] / 2, cfg['obi_c'] + cfg['obi_w'] / 2
    zs = [hem, hem + 0.13 * k] + ([(hem + z['knee']) / 2, z['knee'] + 0.05] if lod <= 1 else [z['knee']]) + \
         ([z['hip'] - 0.04, z['hip'] + 0.02 * k] if lod <= 1 else [z['hip']]) + [oz0, oz1] + \
         ([z['chest'] - 0.03, z['chest'] + 0.03] if lod == 0 else [z['chest']]) + \
         [z['shoulder'] - 0.045 * k, z['neckb'] + 0.01]
    if lod == 2:
        zs = [hem, hem + 0.13 * k, z['knee'], z['hip'], oz0, oz1, z['shoulder'] - 0.045 * k, z['neckb'] + 0.01]
    elif lod == 3:
        zs = [hem, z['hip'], oz1, z['shoulder'] - 0.045 * k, z['neckb'] + 0.01]
    zs = sorted(set(round(v, 4) for v in zs if v >= hem - 1e-4))
    rings = []
    vz = cfg['v_z']
    for zz in zs:
        hw_, hd_, yc_ = robe.at(zz)
        ring = sring(zz, hw_, hd_, n, p=2.6, yc=yc_)
        if zz > vz:                                       # V neckline: front-centre points dip towards the cross
            top = z['neckb'] + 0.01
            for i, pnt in enumerate(ring):
                fwd = max(0.0, (pnt.y - yc_) / hd_)
                if fwd > 0.55 and abs(pnt.x) < hw_ * 0.6:
                    w = (fwd - 0.55) / 0.45
                    pnt.z = zz - (zz - vz) * w * ((zz - vz) / max(1e-3, top - vz)) * 0.9
        rings.append(ring)
    mis = [m_robe] * (len(rings) - 1)
    if m_pat is not None and lod <= 2:
        mis[0] = m_pat                                    # dyed hem band (pattern) on the lowest band
    R, faces = F.loft(rings, m_robe, mis=mis)
    # turned hem + inner cap (no see-through)
    if lod <= 2:
        inner = [F.bm.verts.new(Vector((p.x * 0.94, (p.y - 0.004) * 0.94 + 0.004, p.z + 0.035 * k))) for p in rings[0]]
        fs = C.bridge_rings(F.bm, inner, R[0])
        capf = F.bm.faces.new(inner[::-1])
    else:
        fs, capf = [], F.bm.faces.new(R[0][::-1])
    for f in fs + [capf]:
        f.material_index = mis[0]
    # V chest patch (skin) inside the neckline
    F.close()
    F.part(['chest', 'spine', 'neck'])
    nr = B['neck_r'] * k
    vpts = []
    m = nseg(lod, 8, 6, 4, 4)
    for zz, sc in ((z['neckb'] + 0.0, 1.25), (vz - 0.01, 0.0)):
        hw_, hd_, yc_ = robe.at(zz)
        if sc:
            vpts.append(sring(zz, nr * 1.25, nr * 1.15, m, p=2, yc=-0.012))
        else:
            vpts.append(sring(zz, hw_ * 0.8, hd_ * 0.8, m, p=2.4, yc=yc_ - 0.01))
    if lod <= 2:
        F.loft(vpts, m_skin, cap1=True)
    F.close()
    F.part(['chest', 'spine', 'neck', 'pelvis', 'clavicle_L', 'clavicle_R'])
    # collar (eri): outer panel (figure's left over right) from the left neck to the right waist, round the
    # back of the neck, the under panel from the right neck to the cross
    if lod <= 1:
        cwid = 0.042 * k
        ns = nseg(lod, 8, 5, 3, 3)
        nzz = z['neckb'] + 0.012
        nhw, nhd, nyc = robe.at(nzz)
        def run(x0, x1, z0, z1, steps):
            pts, nr_ = [], []
            for i in range(steps + 1):
                t = i / steps
                x = x0 + (x1 - x0) * t; zz = z0 + (z1 - z0) * t
                pp, nn = robe.front(x, zz, off=0.004)
                pts.append(pp); nr_.append(nn)
            return pts, nr_
        p1, n1 = run(-nhw * 0.7, cfg.get('cross_x', 0.075 * k), nzz - 0.005, oz1 - 0.01, ns)       # outer: L neck -> R waist
        back, nb = [], []
        nb_steps = nseg(lod, 6, 4, 3, 3)
        for i in range(nb_steps + 1):
            t = math.pi + math.pi * i / nb_steps                   # left side, round the back, right side
            pt = Vector((nhw * 1.06 * math.cos(t) * -1, nyc + nhd * 1.06 * math.sin(t), nzz + 0.012 * math.sin(math.pi * i / nb_steps)))
            back.append(pt); nb.append(Vector((pt.x, pt.y - nyc, 0.25)))
        p2, n2 = run(nhw * 0.7, 0.0, nzz - 0.005, vz, max(2, ns // 2))                              # under: R neck -> cross
        path = p1[::-1] + back[1:-1] + p2
        nrms = n1[::-1] + nb[1:-1] + n2
        F.band(path, nrms, cwid, 0.009 * k, mats.get('collar', m_robe))
        if lod <= 1:                                              # front panel edge below the obi
            F.close()
            F.part(['pelvis', 'spine', 'thigh_L', 'thigh_R', 'shin_L', 'shin_R'])
            pe, ne = run(cfg.get('cross_x', 0.075 * k) + 0.01, cfg.get('cross_x', 0.075 * k) * 1.25 + 0.01, oz0, hem + 0.004, 4)
            F.band(pe, ne, 0.016 * k, 0.005 * k, mats.get('collar', m_robe))
    F.close()
    # obi band (+ cord) around the robe
    F.part(['spine', 'pelvis'])
    no = nseg(lod, 16, 10, 6, 5)
    ob = []
    for zz, out in ((oz0 + 0.004, 0.003), (oz0 + 0.01, 0.012 * k), ((oz0 + oz1) / 2, 0.016 * k), (oz1 - 0.01, 0.012 * k), (oz1 - 0.004, 0.003)):
        hw_, hd_, yc_ = robe.at(zz)
        ob.append(sring(zz, hw_ + out, hd_ + out, no, p=2.4, yc=yc_))
    if lod >= 2:
        ob = [ob[0], ob[2], ob[4]] if lod == 2 else [ob[1], ob[3]]
    F.loft(ob, m_obi, cap0=False, cap1=False)
    hwm, hdm, ycm = robe.at((oz0 + oz1) / 2)
    if m_cord is not None and lod == 0:                           # obijime cord with a front knot
        cz = (oz0 + oz1) / 2
        cr = sring(cz, hwm + 0.019 * k, hdm + 0.019 * k, 12, p=2.4, yc=ycm)
        C.tube(F.mb, cr + [cr[0]], [0.006 * k] * 13, m_cord, sides=4)
        F.blob(Vector((0.0, ycm + hdm + 0.025 * k, cz)), (0.016 * k, 0.012 * k, 0.014 * k), m_cord, segs=6, rings=4)
    F.close()
    # bow at the back
    F.part(['spine', 'pelvis'], rigid=False)
    bow = cfg.get('bow', 'butterfly')
    by = ycm - hdm - 0.01
    bz = (oz0 + oz1) / 2
    bs, br = nseg(lod, 8, 6, 4, 4), nseg(lod, 4, 4, 3, 3)
    if bow == 'none':
        pass
    elif lod == 3:
        F.blob(Vector((0, by - 0.035 * k, bz)), (0.13 * k if bow != 'knot' else 0.06 * k, 0.04 * k, 0.06 * k), m_obi, segs=4, rings=3)
    elif bow == 'butterfly':
        for s in (-1, 1):
            F.blob(Vector((s * 0.085 * k, by - 0.03 * k, bz + 0.01)), (0.085 * k, 0.04 * k, 0.06 * k), m_obi, segs=bs, rings=br,
                   M=Matrix.Rotation(s * 0.25, 3, 'Y'))
        F.blob(Vector((0, by - 0.04 * k, bz)), (0.035 * k, 0.04 * k, 0.05 * k), m_obi, segs=bs, rings=br)
        if lod <= 2:
            F.box(Vector((0.0, by - 0.035 * k, bz - 0.12 * k)), (0.075 * k, 0.018 * k, 0.17 * k), m_obi, M=Matrix.Rotation(0.1, 3, 'Z'))
    elif bow == 'heko':                                           # child's soft sash bow: big, droopy
        for s in (-1, 1):
            F.blob(Vector((s * 0.07 * k, by - 0.04 * k, bz + 0.015)), (0.08 * k, 0.05 * k, 0.06 * k), m_obi, segs=bs, rings=br,
                   M=Matrix.Rotation(s * 0.35, 3, 'Y'))
            F.blob(Vector((s * 0.035 * k, by - 0.03 * k, bz - 0.13 * k)), (0.035 * k, 0.025 * k, 0.11 * k), m_obi, segs=bs, rings=br,
                   M=Matrix.Rotation(-s * 0.15, 3, 'Y'))
        F.blob(Vector((0, by - 0.045 * k, bz)), (0.035 * k, 0.04 * k, 0.045 * k), m_obi, segs=bs, rings=br)
    elif bow == 'none':
        pass
    else:                                                         # man's kaku-obi knot: a flat cross-knot, offset
        F.box(Vector((0.03 * k, by - 0.012 * k, bz)), (0.12 * k, 0.03 * k, cfg['obi_w'] * 0.85), m_obi)
        F.box(Vector((0.05 * k, by - 0.02 * k, bz - 0.03 * k)), (0.035 * k, 0.025 * k, 0.13 * k), m_obi, M=Matrix.Rotation(0.35, 3, 'Y'))
    F.close()
    # tamoto sleeves: wide, hanging, open cuff with a turned edge and an inner cap
    for S in 'LR':
        if cfg.get('sleeve') == 'narrow':
            sleeve(F, S, m_robe, narrow=True, end=cfg.get('sleeve_end', 0.6), cuff_mi=mats.get('cuff'))
        else:
            sleeve(F, S, m_robe, cfg.get('sleeve_len', 0.8), cfg.get('sleeve_w', 1.0))


def sleeve(F, S, mi, length=0.8, wscale=1.0, narrow=False, cuff_mi=None, end=None):
    sk, lod = F.sk, F.lod
    J, k, g = sk.J, sk.k, sk.g
    s = -1 if S == 'L' else 1
    F.part(['clavicle_' + S, 'upperarm_' + S, 'forearm_' + S, 'chest'])
    n = nseg(lod, 10, 8, 5, 4)
    sj, el, wr = J['shoulder' + S], J['elbow' + S], J['wrist' + S]
    ua = (el - sj).normalized()
    fa = (wr - el).normalized()
    tot_up, tot_fo = (el - sj).length, (wr - el).length
    if narrow:
        e = end if end is not None else 0.7
        stations = [(0.0, 0.07, 0.07), (0.5, 0.062, 0.06), (1.0, 0.055, 0.052), (1 + e * 0.5, 0.05, 0.048), (1 + e, 0.05, 0.05)]
    else:
        stations = [(0.0, 0.058, 0.07), (0.45, 0.068, 0.1), (0.95, 0.07, 0.125), (1.0 + length * 0.5, 0.072, 0.13), (1.0 + length, 0.074, 0.132)]
    if lod == 1:
        stations = [stations[0], stations[2], stations[3], stations[4]]
    if lod >= 2:
        stations = [stations[0], stations[2], stations[4]]
    rings = []
    last_c, last_ax = None, None
    for t, ru, rv in stations:
        if t <= 1.0:
            c = sj.lerp(el, t) + Vector((-s * 0.02 * (1 - t), 0, -0.012 * k * (1 - t)))
            ax = ua
        else:
            c = el + fa * ((t - 1.0) * tot_fo)
            ax = fa
        vp = 0.0 if narrow else 0.03 * k * min(1.0, t)          # pocket hangs to the back-front (tamoto)
        rings.append(lring(c + Vector((0, -0.01 * min(1.0, t), 0)) if not narrow else c, ax, ru * k * wscale * (g if narrow else 1.0),
                           rv * k * wscale * (g if narrow else 1.0), n, vpush=vp))
        last_c, last_ax = c, ax
    # cuff: turned edge then an inner cap set back
    cuff = [last_c + (p - last_c) * 0.86 - last_ax * 0.012 for p in rings[-1]]
    inner = [last_c + (p - last_c) * 0.8 - last_ax * 0.06 for p in rings[-1]]
    R, faces = F.loft(rings + ([cuff, inner] if lod <= 1 else []), mi, cap1=True)
    if cuff_mi is not None:
        for f in faces:
            if all((v.co - last_c).dot(last_ax) > -0.02 for v in f.verts):
                f.material_index = cuff_mi
    F.close()


def geta(F, S, m_wood, m_strap):
    """wooden geta: board with two teeth and a thong strap (hanao); rigid on foot_S."""
    sk, lod = F.sk, F.lod
    J, k = sk.J, sk.k
    F.part(['foot_' + S], rigid=True)
    an, he, to = J['ankle' + S], J['heel' + S], J['toe' + S]
    L = (to.y - he.y) + 0.03
    W = 0.095 * k
    cy = (to.y + he.y) / 2 + 0.008
    T = 0.022 * k
    th = 0.035 * k
    if lod >= 2:
        F.box(Vector((an.x, cy, (th + T) / 2)), (W, L, th + T), m_wood)
    else:
        F.box(Vector((an.x, cy, th + T / 2)), (W, L, T), m_wood)
    if lod <= 1:
        for f in (-0.27, 0.27):
            F.box(Vector((an.x, cy + f * L, th / 2)), (W * 0.96, 0.02 * k, th), m_wood)
    if lod == 0:
        top = th + T
        a = Vector((an.x, cy + 0.36 * L, top))
        mid = Vector((an.x, cy + 0.18 * L, top + 0.03 * k))
        for s in (-1, 1):
            b = Vector((an.x + s * W * 0.48, cy - 0.06 * L, top + 0.005))
            C.tube(F.mb, [a, mid + Vector((s * 0.02 * k, 0, 0.004)), b], [0.0055 * k] * 3, m_strap, sides=4)
    F.close()
    return th + T


# ------------------------------------------------------------------------------------------- skinning
def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(1e-9, ab.length_squared)))
    return (p - (a + ab * t)).length


def skin_weights(F):
    """per-vertex [(bone, w)] by part: rigid -> 1.0, else top-3 by 1/d^4 among the part's bones"""
    sk = F.sk
    F.close()
    out = []
    for v in F.bm.verts:
        pid = v[F.lay]
        bones, rigid, wsc, pw = F.parts[pid] if pid > 0 else (('root',), True, {}, 4)
        if rigid or len(bones) == 1:
            out.append([(bones[0], 1.0)])
            continue
        p = v.co
        ws = []
        for b in bones:
            d = _seg_dist(p, *sk.seg(b))
            ws.append((b, wsc.get(b, 1.0) / (d + 0.02) ** pw))
        ws.sort(key=lambda t: -t[1])
        ws = ws[:3]
        s = sum(w for _, w in ws)
        ws = [(b, w / s) for b, w in ws if w / s > 0.03]
        s = sum(w for _, w in ws)
        out.append([(b, w / s) for b, w in ws])
    return out


# ------------------------------------------------------------------------------------------- poses
def pose_matrices(sk, rot, root_off=Vector(), root_rot=None, prop_place=None):
    """skin matrices S_b (armature space): rotation `rot[b]` (world-axis 4x4) about the bone's bind head,
    composed down the chain. prop_place[b] = (rest 4x4, posed 4x4) overrides a prop bone."""
    S = {}
    for b in BONES:
        h = sk.heads[b]
        R = rot.get(b, Matrix.Identity(4))
        if b == 'root':
            RR = root_rot if root_rot is not None else Matrix.Identity(4)
            S[b] = Matrix.Translation(root_off) @ Matrix.Translation(sk.heads['pelvis']) @ RR @ R @ Matrix.Translation(-sk.heads['pelvis'])
        else:
            S[b] = S[PARENT[b]] @ Matrix.Translation(h) @ R @ Matrix.Translation(-h)
        if prop_place and b in prop_place:
            rest, posed = prop_place[b]
            S[b] = Matrix.Translation(root_off) @ posed @ rest.inverted()
    return S


def lbs(coords, weights, S):
    out = []
    for p, ws in zip(coords, weights):
        q = Vector()
        for b, w in ws:
            q += (S[b] @ p) * w
        out.append(q)
    return out


def standard_pose(name, sk, extra=None):
    """world-axis rotations per bone for the named pose. Rotation about +X: + swings a down-pointing limb
    forward and tilts an up-pointing chain backward."""
    r = {}
    if name in ('standing', 'idle', 'bind'):
        pass
    elif name == 'walking':
        r.update(thigh_L=rx(22), shin_L=rx(-6), foot_L=rx(-8), thigh_R=rx(-16), shin_R=rx(-28), foot_R=rx(18),
                 upperarm_L=rx(-14), upperarm_R=rx(16), forearm_L=rx(8), forearm_R=rx(18), pelvis=rz(-4),
                 spine=rx(-3) @ rz(5), chest=rz(3), head=rz(-4))
    elif name == 'seated':
        r.update(thigh_L=rx(86) @ ry(-3), thigh_R=rx(86) @ ry(3), shin_L=rx(-84), shin_R=rx(-84),
                 spine=rx(-4), upperarm_L=rx(24), upperarm_R=rx(24), forearm_L=rx(38), forearm_R=rx(38))
    elif name == 'soaking':
        r.update(thigh_L=rx(78) @ ry(-8), thigh_R=rx(78) @ ry(8), shin_L=rx(-22), shin_R=rx(-22), foot_L=rx(20), foot_R=rx(20),
                 pelvis=rx(14), spine=rx(4), neck=rx(-10), head=rx(-6),
                 upperarm_L=ry(34) @ rx(-6), upperarm_R=ry(-34) @ rx(-6), forearm_L=rx(32), forearm_R=rx(32))
    elif name == 'floating':
        r.update(upperarm_L=ry(52), upperarm_R=ry(-52), forearm_L=rx(10), forearm_R=rx(10),
                 thigh_L=ry(-7), thigh_R=ry(7), neck=rx(-12), head=rx(-8))
    if sk.B.get('stoop') and name in ('standing', 'idle', 'walking', 'seated'):
        r['spine'] = r.get('spine', Matrix.Identity(4)) @ rx(-7)
        r['chest'] = r.get('chest', Matrix.Identity(4)) @ rx(-10)
        r['neck'] = r.get('neck', Matrix.Identity(4)) @ rx(8)
        r['head'] = r.get('head', Matrix.Identity(4)) @ rx(6)
        r['thigh_L'] = r.get('thigh_L', Matrix.Identity(4)) @ rx(4)
        r['thigh_R'] = r.get('thigh_R', Matrix.Identity(4)) @ rx(4)
        r['shin_L'] = r.get('shin_L', Matrix.Identity(4)) @ rx(-6)
        r['shin_R'] = r.get('shin_R', Matrix.Identity(4)) @ rx(-6)
    if extra:
        for b, m in extra.items():
            r[b] = r.get(b, Matrix.Identity(4)) @ m
    root_rot = rx(86) if name == 'floating' else None
    return r, root_rot


# ------------------------------------------------------------------------------------------- object + rig
def finish_figure(F, name, pose_name, rot, root_rot=None, prop_place=None, shape_keys=None, anim=None, params=None,
                  ground='min'):
    """build the mesh object (bind pose), the armature (parented to the mesh), weights, shape keys and the
    pose. ground='min': the posed figure's lowest point is put on z = 0 (and floating poses are centred)."""
    sk = F.sk
    weights = skin_weights(F)
    coords = [v.co.copy() for v in F.bm.verts]
    # posed root offset so the figure stands / sits / floats on z = 0
    S = pose_matrices(sk, rot, Vector(), root_rot, prop_place)
    posed = lbs(coords, weights, S)
    zmin = min(p.z for p in posed)
    off = Vector((0, 0, -zmin))
    if pose_name == 'floating':
        xs = [p.x for p in posed]; ys = [p.y for p in posed]
        off.x = -(max(xs) + min(xs)) / 2; off.y = -(max(ys) + min(ys)) / 2
    S = pose_matrices(sk, rot, off, root_rot, prop_place)
    o = F.mb.to_object(name)
    genlib.finish(o, smooth_angle=72)
    me = o.data
    # vertex groups
    vg = {b: o.vertex_groups.new(name=b) for b in BONES}
    for i, ws in enumerate(weights):
        for b, w in ws:
            vg[b].add([i], w, 'REPLACE')
    # shape keys (girth): same topology, other build values
    if shape_keys:
        o.shape_key_add(name='Basis', from_mix=False)
        for kname, pts in shape_keys.items():
            if len(pts) != len(me.vertices):
                print('WARN shape key', kname, 'vertex count mismatch', len(pts), len(me.vertices))
                continue
            kb = o.shape_key_add(name=kname, from_mix=False)
            for i, p in enumerate(pts):
                kb.data[i].co = p
            kb.slider_min, kb.slider_max = 0.0, 1.0
    # armature
    ad = bpy.data.armatures.new(name + '_rig')
    arm = bpy.data.objects.new(name + '_rig', ad)
    bpy.context.scene.collection.objects.link(arm)
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for b in BONES:
        e = ad.edit_bones.new(b)
        e.head, e.tail = sk.heads[b], sk.tails[b]
        if (e.tail - e.head).length < 1e-3:
            e.tail = e.head + Vector((0, 0, 0.05))
        e.roll = 0.0
        eb[b] = e
    for b in BONES:
        if b in PARENT:
            eb[b].parent = eb[PARENT[b]]
            eb[b].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.select_set(False)
    ad.display_type = 'STICK'
    arm.show_in_front = True
    # pose: pose_mat_b = S_b @ rest_b ; basis = (parent_rest^-1 rest)^-1 parent_pose^-1 pose_mat
    rest = {b: ad.bones[b].matrix_local.copy() for b in BONES}
    pmat = {b: S[b] @ rest[b] for b in BONES}
    for b in BONES:
        pb = arm.pose.bones[b]
        pb.rotation_mode = 'QUATERNION'
        if b in PARENT:
            p = PARENT[b]
            basis = (rest[p].inverted() @ rest[b]).inverted() @ pmat[p].inverted() @ pmat[b]
        else:
            basis = rest[b].inverted() @ pmat[b]
        pb.matrix_basis = basis
    arm.parent = o
    mod = o.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    o['kz_rig'] = arm.name
    o['kz_pose'] = pose_name
    a = dict(type='skinned', rig=arm.name, bones=BONES, bind='standing', pose=pose_name,
             clips=anim or CLIPS_GUEST, shape_keys=list((shape_keys or {}).keys()),
             root_offset=[round(c, 4) for c in off], note='mesh data = bind pose; pose lives on the armature')
    C.set_json_props(o, kz_anim=a, kz_params=params or {}, kz_probe='moving')
    return o, arm


def sk_coords(F):
    """vertex coordinates in creation order (for shape keys)"""
    F.close()
    return [v.co.copy() for v in F.bm.verts]
