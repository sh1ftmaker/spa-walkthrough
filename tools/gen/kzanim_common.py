"""kzanim_common: shared helpers for the figure animation clips (tools/gen/anim_figures.py).

Everything here works in the figure kit's pose convention (kzgeo_guest_figure.pose_matrices): a pose is a dict
{bone: 4x4 rotation in WORLD axes about the bone's bind head}, composed down the chain, plus optional extra
translations of a bone head (in its parent's posed frame). On top of that:

  * periodic curves (wave, pnoise, pbump, sqwave): every curve repeats exactly over the clip duration D, so a
    clip built from them loops with first frame == last frame by construction;
  * Poser.solve: the chain evaluation with analytic two-bone IK (legs: thigh/shin/foot, arms: upperarm/forearm/
    hand) and world-space end-effector orientation (foot flat on the floor, hand orientation);
  * Gait: the foot-locked walk cycle (heel strike -> flat -> roll on the forefoot tip -> swing), planted pivots
    move backwards at exactly the clip speed in the root frame, so with the root moved at kz_clip_speed the
    planted foot is fixed in the world;
  * breathe: subtle chest / spine breathing;
  * bake: per-frame pose -> pose-bone basis (loc + quaternion) keyframes on a layered Action (Blender 5.x slots),
    quaternion sign continuity, last frame == first frame;
  * measurement helpers (posed mesh by linear blend skinning, water-line contacts, cloth edge strain).

Run outside Blender (`python kzanim_common.py compose spec.json`) it composes the contact-strip renders with PIL.
"""
import json
import math
import os
import random
import sys

try:
    import bpy
    from mathutils import Matrix, Quaternion, Vector
except ImportError:                                  # composing images with the venv python
    bpy = None

FPS = 30
TAU = 2 * math.pi


# ------------------------------------------------------------------------------------------- periodic curves
def wave(t, D, n=1, phase=0.0):
    """sin with n whole cycles over D (phase in cycles)"""
    return math.sin(TAU * (n * t / D + phase))


def cwave(t, D, n=1, phase=0.0):
    return math.cos(TAU * (n * t / D + phase))


def pnoise(t, D, seed, ns=(1, 2, 3), amps=(1.0, 0.5, 0.25)):
    """smooth periodic noise in [-1, 1]: a few whole harmonics with seeded phases"""
    r = random.Random(seed)
    s = norm = 0.0
    for k, a in zip(ns, amps):
        s += a * math.sin(TAU * (k * t / D + r.random()))
        norm += a
    return s / norm


def pbump(t, D, c, width):
    """periodic smooth bump: 1 at t = c, 0.5 at c +- width / 2, ~0 far away (von Mises shape, loops over D)"""
    xh = math.pi * width / D
    k = math.log(2) / max(1e-6, 1 - math.cos(xh))
    return math.exp(k * (math.cos(TAU * (t - c) / D) - 1))


def sqwave(t, D, sharp=2.5, n=1, phase=0.0):
    """smooth square wave in [-1, 1] (holds, then eases across)"""
    return math.tanh(sharp * wave(t, D, n, phase)) / math.tanh(sharp)


def ease(s):
    s = max(0.0, min(1.0, s))
    return s * s * (3 - 2 * s)


def hermite(p0, p1, m0, m1, s):
    """cubic Hermite on [0, 1]; m0 / m1 are derivatives w.r.t. s"""
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1


def rx(a):
    return Matrix.Rotation(math.radians(a), 4, 'X')


def ry(a):
    return Matrix.Rotation(math.radians(a), 4, 'Y')


def rz(a):
    return Matrix.Rotation(math.radians(a), 4, 'Z')


def add(rot, b, M):
    """compose an extra world-axis rotation onto bone b (kit 'extra' convention)"""
    rot[b] = rot.get(b, Matrix.Identity(4)) @ M


def addt(trans, b, v):
    trans[b] = trans.get(b, Vector()) + Vector(v)


def breathe(rot, trans, t, D, amp=1.0, breaths=None):
    """subtle breathing on the chest and spine: chest tips back ~1 deg and lifts 2 mm on the in-breath.
    breaths: whole breaths per clip (default ~ one per 3.5-4 s)."""
    n = breaths or max(1, round(D / 3.8))
    b = 0.5 - 0.5 * math.cos(TAU * n * t / D)                 # 0 exhaled .. 1 inhaled
    b = b ** 0.8                                               # a little quicker in, slower out
    add(rot, 'spine', rx(0.45 * amp * b))
    add(rot, 'chest', rx(0.9 * amp * b))
    addt(trans, 'chest', (0, 0.0012 * amp * b, 0.0022 * amp * b))
    add(rot, 'neck', rx(-0.9 * amp * b))                       # the head does not nod with the breath
    for S in 'LR':
        add(rot, 'clavicle_' + S, ry((-1 if S == 'L' else 1) * -0.6 * amp * b))   # shoulders rise a touch
    return b


# ------------------------------------------------------------------------------------------- pose solver
CHAINS = {'thigh_L': ('shin_L', 'foot_L'), 'thigh_R': ('shin_R', 'foot_R'),
          'upperarm_L': ('forearm_L', 'hand_L'), 'upperarm_R': ('forearm_R', 'hand_R')}


class Poser:
    """S matrices (armature space skin matrices, bind -> posed) for a pose on skeleton sk (kit Skeleton)."""

    def __init__(self, sk, KG):
        self.sk, self.KG = sk, KG
        self.BONES, self.PARENT = KG.BONES, KG.PARENT

    def solve(self, rot, trans=None, ik=None):
        """rot: {bone: 4x4}; trans: {bone: Vector}; ik: {upper: dict(target=Vector (end joint, world),
        pole=Vector (direction) or knee=Vector (point), end_rot=3x3/4x4 world orientation or None)}.
        Returns (S, rot_used, info) with info[upper] = reach error (m, > 0 if the target was out of reach)."""
        h = self.sk.heads
        rot = dict(rot)
        trans = trans or {}
        ik = ik or {}
        S, info = {}, {}
        I = Matrix.Identity(4)
        for b in self.BONES:
            P = S[self.PARENT[b]] if b in self.PARENT else I
            if b in ik:
                lo, end = CHAINS[b]
                req = ik[b]
                tg, kn = req['target'], req.get('knee')
                tg = tg(S) if callable(tg) else tg
                kn = kn(S) if callable(kn) else kn
                out, inf = self.two_bone(P, b, lo, end, tg, req.get('pole'), kn,
                                         req.get('end_rot'), req.get('reach', 0.9995))
                rot.update(out)
                info[b] = inf
            R = rot.get(b, I)
            t = trans.get(b)
            if t is not None:
                S[b] = P @ Matrix.Translation(h[b]) @ Matrix.Translation(t) @ R @ Matrix.Translation(-h[b])
            else:
                S[b] = P @ Matrix.Translation(h[b]) @ R @ Matrix.Translation(-h[b])
        return S, rot, info

    def two_bone(self, Sp, up, lo, end, target, pole=None, knee=None, end_rot=None, reach=0.9995):
        h = self.sk.heads
        A = Sp @ h[up]
        L1 = (h[lo] - h[up]).length
        L2 = (h[end] - h[lo]).length
        d = Vector(target) - A
        D = d.length
        Dc = min(max(D, abs(L1 - L2) + 1e-4), (L1 + L2) * reach)
        dh = d.normalized() if D > 1e-9 else Vector((0, 0, -1))
        ca = max(-1.0, min(1.0, (L1 * L1 + Dc * Dc - L2 * L2) / (2 * L1 * Dc)))
        a = math.acos(ca)
        pv = (Vector(knee) - A) if knee is not None else Vector(pole if pole is not None else (0, 1, 0))
        p = pv - dh * pv.dot(dh)
        if p.length < 1e-6:
            p = Vector((0, 1, 0)) - dh * dh.y
        p.normalize()
        udir = dh * math.cos(a) + p * math.sin(a)
        K = A + udir * L1
        E = A + dh * Dc
        ldir = (E - K).normalized()
        Rp = Sp.to_3x3()
        u0 = (h[lo] - h[up]).normalized()
        l0 = (h[end] - h[lo]).normalized()
        Ru = u0.rotation_difference(Rp.inverted() @ udir).to_matrix()
        Ruw = Rp @ Ru
        Rl = l0.rotation_difference(Ruw.inverted() @ ldir).to_matrix()
        out = {up: Ru.to_4x4(), lo: Rl.to_4x4()}
        if end_rot is not None:
            Rlw = Ruw @ Rl
            out[end] = (Rlw.inverted() @ end_rot.to_3x3()).to_4x4()
        return out, dict(err=max(0.0, D - (L1 + L2) * reach), knee=K)


def hip_centre(sk):
    return (sk.heads['thigh_L'] + sk.heads['thigh_R']) * 0.5


def pelvis_trans_for(sk, R_pelvis, hip_target):
    """pelvis head translation that puts the hip centre at hip_target after rotating the pelvis by R_pelvis"""
    h = sk.heads['pelvis']
    return Vector(hip_target) - h - R_pelvis.to_3x3() @ (hip_centre(sk) - h)


# ------------------------------------------------------------------------------------------- gait
class Gait:
    """Foot-locked walk cycle for one foot. Phase u in [0, 1): 0 = heel strike, [0, u_flat) roll onto the heel
    pivot, [u_flat, u_off) flat, [u_off, duty) roll over the forefoot tip pivot, [duty, 1) swing.
    Pivot points are on the floor (z = 0) under the heel and under the forefoot tip (geta front edge / toe tip),
    so the same clip works barefoot and in geta. In the root frame the planted pivot moves -Y at speed v."""

    def __init__(self, sk, S, v, T, duty=0.62, u_flat=0.09, u_off=0.36, pitch_hs=11.0, pitch_to=-32.0,
                 clearance=0.045, y_mid=0.0, width=1.0, toe_out=5.0):
        J = sk.J
        self.S, self.v, self.T, self.duty = S, v, T, duty
        self.u_flat, self.u_off = u_flat, u_off
        self.p_hs, self.p_to = math.radians(pitch_hs), math.radians(pitch_to)
        self.clear = clearance
        s = -1 if S == 'L' else 1
        an = J['ankle' + S]
        self.ankle_b = an.copy()
        self.heel_b = Vector((an.x, J['heel' + S].y - 0.007, 0.0))
        self.tip_b = Vector((an.x, J['toe' + S].y + 0.025, 0.0))
        self.x = an.x * width
        self.yaw = math.radians(-s * toe_out)                 # toes turn out a little
        # heel position at strike so the ankle is at y_mid at mid-stance (flat foot)
        self.Y0 = y_mid + v * T * duty / 2 - (self.ankle_b.y - self.heel_b.y)
        self._cache = {}

    def Rfoot(self, pitch):
        return Matrix.Rotation(self.yaw, 3, 'Z') @ Matrix.Rotation(pitch, 3, 'X')

    def _stance(self, u):
        """ankle pos, foot rotation, pivot name for a stance phase u in [0, duty]"""
        Rz = Matrix.Rotation(self.yaw, 3, 'Z')
        heel_flat = Vector((self.x, self.Y0 - self.v * u * self.T, 0.0))
        off_ah = Rz @ (self.ankle_b - self.heel_b)
        off_th = Rz @ (self.tip_b - self.heel_b)
        if u < self.u_flat:
            s = u / self.u_flat
            pitch = self.p_hs * (1 - s) ** 2
            R = self.Rfoot(pitch)
            P = heel_flat
            ankle = P + R @ (self.ankle_b - self.heel_b)
            pv = 'heel'
        elif u <= self.u_off:
            R = self.Rfoot(0.0)
            ankle = heel_flat + off_ah
            pv = 'flat'
        else:
            s = (u - self.u_off) / (self.duty - self.u_off)
            pitch = self.p_to * s ** 1.6
            R = self.Rfoot(pitch)
            tip = heel_flat + off_th
            ankle = tip + R @ (self.ankle_b - self.tip_b)
            pv = 'tip'
        return ankle, R, pv

    def state(self, u):
        """(ankle target, foot world rotation 3x3, pivot or None)"""
        u = u % 1.0
        if u <= self.duty:
            a, R, pv = self._stance(u)
            return a, R, pv
        # swing: Hermite from the toe-off state to the next heel strike, matching velocities (C1)
        e = 1e-4
        a0, _, _ = self._stance(self.duty)
        a0m, _, _ = self._stance(self.duty - e)
        a1, _, _ = self._stance(0.0)
        a1p, _, _ = self._stance(e)
        L = 1 - self.duty
        m0 = (a0 - a0m) / e * L                              # d/ds
        m1 = (a1p - a1) / e * L
        s = (u - self.duty) / L
        pos = Vector([hermite(a0[i], a1[i], m0[i], m1[i], s) for i in range(3)])
        pos.z += self.clear * 16 * s * s * (1 - s) * (1 - s)
        pt0, pt1 = self.p_to, self.p_hs
        dp0 = (self.p_to - self.p_to * ((self.duty - e - self.u_off) / (self.duty - self.u_off)) ** 1.6) / e * L
        dp1 = (-2 * self.p_hs / self.u_flat) * L
        pitch = hermite(pt0, pt1, dp0 * 0.5, dp1 * 0.3, s)
        return pos, self.Rfoot(pitch), None


# ------------------------------------------------------------------------------------------- baking
def basis_from_S(arm, S, bones):
    """pose-bone basis matrices that reproduce the skin matrices S (same formula as kit finish_figure)"""
    rest = {b: arm.data.bones[b].matrix_local.copy() for b in bones}
    pmat = {b: S[b] @ rest[b] for b in bones}
    out = {}
    for b in bones:
        pb = arm.pose.bones[b]
        par = pb.parent.name if pb.parent else None
        if par:
            out[b] = (rest[par].inverted() @ rest[b]).inverted() @ pmat[par].inverted() @ pmat[b]
        else:
            out[b] = rest[b].inverted() @ pmat[b]
    return out


def bake_action(arm, name, frames_S, bones, props=None):
    """frames_S: list of S dicts, frame 0..N (the last one is replaced by frame 0). Creates a layered Action on
    arm with LINEAR loc + quaternion keys for every bone, fake user, frame range, cyclic, custom props."""
    N = len(frames_S) - 1
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    for b in bones:
        arm.pose.bones[b].rotation_mode = 'QUATERNION'
    locs = {b: [] for b in bones}
    quats = {b: [] for b in bones}
    for f, S in enumerate(frames_S[:N]):
        B = basis_from_S(arm, S, bones)
        for b in bones:
            loc, q, _ = B[b].decompose()
            if quats[b] and q.dot(quats[b][-1]) < 0:
                q = -q
            if abs(loc.x) < 1e-7: loc.x = 0.0
            if abs(loc.y) < 1e-7: loc.y = 0.0
            if abs(loc.z) < 1e-7: loc.z = 0.0
            locs[b].append(loc)
            quats[b].append(q)
    for b in bones:                                       # seam: last key = first key (sign-matched)
        q0 = quats[b][0]
        quats[b].append(q0 if q0.dot(quats[b][-1]) >= 0 else -q0)
        locs[b].append(locs[b][0].copy())
    for b in bones:
        base = f'pose.bones["{b}"]'
        for path, vals, n in (('location', locs[b], 3), ('rotation_quaternion', quats[b], 4)):
            for i in range(n):
                fc = act.fcurve_ensure_for_datablock(arm, base + '.' + path, index=i, group_name=b)
                fc.keyframe_points.clear()
                fc.keyframe_points.add(N + 1)
                co = []
                for f in range(N + 1):
                    co += [float(f), float(vals[f][i])]
                fc.keyframe_points.foreach_set('co', co)
                fc.keyframe_points.foreach_set('interpolation', [1] * (N + 1))     # LINEAR
                fc.update()
    act.use_fake_user = True
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, N
    act.use_cyclic = True
    for k, v in (props or {}).items():
        act[k] = json.dumps(v) if isinstance(v, (dict, list, tuple)) else v
    return act


# ------------------------------------------------------------------------------------------- measuring
def mesh_bind(o):
    """bind coords + per-vertex [(bone, w)] read from the vertex groups"""
    names = {g.index: g.name for g in o.vertex_groups}
    coords, weights = [], []
    for v in o.data.vertices:
        coords.append(v.co.copy())
        ws = [(names[g.group], g.weight) for g in v.groups if g.weight > 0]
        s = sum(w for _, w in ws) or 1.0
        weights.append([(b, w / s) for b, w in ws] or [('root', 1.0)])
    return coords, weights


def lbs(coords, weights, S):
    out = []
    for p, ws in zip(coords, weights):
        q = Vector()
        for b, w in ws:
            q += (S[b] @ p) * w
        out.append(q)
    return out


def dominant(ws):
    return max(ws, key=lambda t: t[1])[0]


GROUPS = dict(pelvis='torso', spine='torso', chest='torso', root='torso', neck='head', head='head',
              clavicle_L='arm_L', upperarm_L='arm_L', forearm_L='arm_L', hand_L='arm_L', prop_L='arm_L',
              clavicle_R='arm_R', upperarm_R='arm_R', forearm_R='arm_R', hand_R='arm_R', prop_R='arm_R',
              thigh_L='leg_L', shin_L='leg_L', foot_L='leg_L', toe_L='leg_L',
              thigh_R='leg_R', shin_R='leg_R', foot_R='leg_R', toe_R='leg_R')


def water_contacts(posed, weights, level, band=0.02):
    """ripple contact rings where the body crosses the water plane: per body group, the centroid (x, y) and
    radius of the vertices within +-band of the level."""
    acc = {}
    for p, ws in zip(posed, weights):
        if abs(p.z - level) <= band:
            g = GROUPS.get(dominant(ws), 'torso')
            acc.setdefault(g, []).append(p)
    out = {}
    for g, pts in acc.items():
        if len(pts) < 3:
            continue
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        r = max(math.hypot(p.x - cx, p.y - cy) for p in pts)
        out[g] = (cx, cy, r)
    return out


def edge_strain(bind, posed, edges):
    """max and 99th-percentile edge length ratio posed / bind (stretch > 1, squash < 1)"""
    rs = []
    for a, b in edges:
        l0 = (bind[a] - bind[b]).length
        if l0 > 1e-5:
            rs.append((posed[a] - posed[b]).length / l0)
    rs.sort()
    if not rs:
        return dict(max=1.0, p99=1.0, min=1.0)
    return dict(max=round(rs[-1], 3), p99=round(rs[int(0.99 * (len(rs) - 1))], 3), min=round(rs[0], 3),
                p01=round(rs[int(0.01 * (len(rs) - 1))], 3))


# ------------------------------------------------------------------------------------------- compose (PIL)
def compose(spec_path):
    """spec: {out, title, rows: [{label, cells: [png...], captions: [...]}], cell: [w, h]} -> labelled jpg"""
    from PIL import Image, ImageDraw, ImageFont
    sp = json.load(open(spec_path))
    cw, ch = sp['cell']
    rows = sp['rows']
    ncol = max(len(r['cells']) for r in rows)
    lab_w = 90
    head = 54
    W = lab_w + ncol * cw
    Hh = head + len(rows) * (ch + 26)
    im = Image.new('RGB', (W, Hh), (18, 18, 20))
    dr = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Bold.ttf', 26)
        f2 = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', 17)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    dr.text((14, 12), sp['title'], fill=(235, 225, 205), font=f1)
    for ri, r in enumerate(rows):
        y = head + ri * (ch + 26)
        dr.text((10, y + ch // 2 - 10), r['label'], fill=(200, 200, 200), font=f2)
        for ci, (p, cap) in enumerate(zip(r['cells'], r['captions'])):
            x = lab_w + ci * cw
            if os.path.exists(p):
                c = Image.open(p).convert('RGB').resize((cw, ch))
                im.paste(c, (x, y))
            dr.text((x + 6, y + ch + 3), cap, fill=(170, 170, 170), font=f2)
            dr.line([(x, y), (x, y + ch)], fill=(40, 40, 44), width=1)
    im.save(sp['out'], quality=90)
    return sp['out']


def compose_canonical(spec_path):
    """spec: {out, render, title, refs: [jpg...], captions} -> 3/4 render + concept strip on the right"""
    from PIL import Image, ImageDraw, ImageFont
    sp = json.load(open(spec_path))
    base = Image.open(sp['render']).convert('RGB')
    W, H = base.size
    strip_w = 360
    im = Image.new('RGB', (W + strip_w, H), (18, 18, 20))
    im.paste(base, (0, 0))
    dr = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Bold.ttf', 30)
        f2 = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', 18)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    dr.text((20, 16), sp['title'], fill=(240, 230, 210), font=f1)
    for i, cap in enumerate(sp.get('captions', [])):
        dr.text((20, 60 + i * 24), cap, fill=(215, 210, 200), font=f2)
    y = 10
    refs = [r for r in sp.get('refs', []) if os.path.exists(r)]
    each = (H - 20 - 30 * len(refs)) // max(1, len(refs))
    for r in refs:
        c = Image.open(r).convert('RGB')
        sc = min((strip_w - 20) / c.width, each / c.height)
        c = c.resize((int(c.width * sc), int(c.height * sc)))
        im.paste(c, (W + 10, y))
        dr.text((W + 12, y + c.height + 2), 'concept ' + os.path.basename(r), fill=(170, 170, 170), font=f2)
        y += c.height + 30
    im.save(sp['out'], quality=90)
    return sp['out']


if __name__ == '__main__' and bpy is None:
    if len(sys.argv) >= 3 and sys.argv[1] == 'compose':
        print(compose(sys.argv[2]))
    elif len(sys.argv) >= 3 and sys.argv[1] == 'canonical':
        print(compose_canonical(sys.argv[2]))
