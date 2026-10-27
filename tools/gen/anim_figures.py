"""anim_figures: the 13 looping figure animation clips (walk, idle, sit, soak, float) on the shared 24-bone rig.

    blender -b -P tools/gen/anim_figures.py -- [--only <clip>] [--stages bake,export,render,mp4,canonical]

Self-made procedural / keyframed actions (owner rule: CC0 or self-made only, nothing downloaded). Every clip is a
pure function of time built from whole-period curves (kzanim_common), sampled at 30 fps and baked to LINEAR loc +
quaternion keys on every bone; the last frame is the first frame. Clips are built in the kit's pose convention
(kzgeo_guest_figure.pose_matrices: world-axis rotations about the bind heads), reusing the static key poses
(standard_pose 'seated' / 'soaking' / 'floating') for the upper body, with analytic two-bone IK for legs and arms
so feet and hands land exactly where the clip puts them (floor, foot rail, zabuton, rim, ring).

Root: the root bone never moves (clips are exported in place). Walk clips travel +Y at action['kz_clip_speed']
m/s: move the figure along the walk graph at that speed and the planted foot stays fixed in the world. The
reference rig is guest_figure body adult_woman 1.65 m; for another figure either re-bake with this script
(build_clips(fig), exact) or play the reference clip and scale kz_clip_speed (and seat / water heights) by
H / 1.65. The pelvis bone carries the body offset (bob, seat drop, float placement).

Per action custom props: kz_clip (JSON: clip, group, duration_s, frames, fps, loop, speed_mps, seat, props_bone,
water, contacts, ref_height, notes), kz_clip_speed (float), kz_water_level (float, m above the root, soak /
float only).

Stages: bake (reference rig -> 3d/assets/figure_anims.blend + 3d/checks/gen/figure_anims.json), export (guest
seed 1 + staff seed 1 with all clips -> .scratch/op28/*.glb, re-import check), render (contact strips per clip),
mp4 (walk preview), canonical (Cycles group views).
"""
import json
import math
import os
import subprocess
import sys
import time

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'gen'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def _arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


ONLY = _arg('--only')
STAGES = _arg('--stages', 'bake,export,render,mp4,canonical').split(',')

bpy.ops.wm.read_factory_settings(use_empty=True)
import genlib  # noqa: E402
import kzgeo_guest_figure as KG  # noqa: E402
import kzanim_common as A  # noqa: E402
from kzanim_common import FPS, TAU, add, addt, rx, ry, rz  # noqa: E402

SCR = os.path.join(ROOT, '.scratch', 'op28')
BLEND = os.path.join(ROOT, '3d', 'assets', 'figure_anims.blend')
CHECKS = os.path.join(ROOT, '3d', 'checks', 'gen', 'figure_anims.json')
RENDERS = os.path.join(ROOT, '3d', 'renders', 'models')
VENV_PY = os.path.join(ROOT, '.venv', 'bin', 'python')
REF = dict(asset='guest_figure', seed=1, height=1.65, build=0.5)
I4 = Matrix.Identity(4)
os.makedirs(SCR, exist_ok=True)


# ============================================================================================ figure context
class Fig:
    """a built figure (mesh + rig) with its skeleton, IK poser and bind skin data"""

    def __init__(self, asset, seed, **kw):
        o = genlib.build(asset, lod=kw.pop('lod', 0), seed=seed, **kw)
        self.o, self.asset, self.seed = o, asset, seed
        self.arm = bpy.data.objects[o['kz_rig']]
        P = json.loads(o['kz_params'])
        self.P = P
        body = P['body'] if asset == 'guest_figure' else ('adult_woman' if P['body'] == 'woman' else 'adult_man')
        sk = KG.Skeleton(body, P['height'], P['build'])
        dy = self.arm.data.bones['pelvis'].head_local.y - sk.heads['pelvis'].y
        for d in (sk.J, sk.heads, sk.tails):
            for key in d:
                d[key] = d[key] + Vector((0, dy, 0))
        self.rest_err = max((self.arm.data.bones[b].head_local - sk.heads[b]).length for b in KG.BONES)
        self.sk, self.dy = sk, dy
        self.poser = A.Poser(sk, KG)
        self.coords, self.weights = A.mesh_bind(o)
        self.edges = [tuple(e.vertices) for e in o.data.edges]
        hh = sk.head_h
        self.head_c = Vector((0, 0.005 + dy, sk.chin + hh * 0.5))
        self.head_r = (hh * 0.36, hh * 0.42, hh * 0.5)
        self.cloth = self._cloth_verts()

    def _cloth_verts(self):
        """vertex ids of the yukata / samue shell (robe, collar, obi, sleeves) by material: everything not skin,
        hair, wood or strap counts as clothing"""
        me = self.o.data
        names = [(m.name if m else '') for m in me.materials]
        skinlike = [i for i, n in enumerate(names) if any(k in n for k in ('ceramic', 'lacquer', 'hinoki'))]
        ids = set()
        for p in me.polygons:
            if p.material_index not in skinlike:
                ids.update(p.vertices)
        return ids

    def posed(self, S):
        return A.lbs(self.coords, self.weights, S)

    def mouth(self, S):
        c, (hx, hy, hz) = self.head_c, self.head_r
        return S['head'] @ (c + Vector((0, hy * 0.9, -hz * 0.42)))

    def L(self, S):
        """leg (thigh + shin) and arm (upper + fore) lengths"""
        h = self.sk.heads
        return dict(leg=(h['shin_' + S] - h['thigh_' + S]).length + (h['foot_' + S] - h['shin_' + S]).length,
                    thigh=(h['shin_' + S] - h['thigh_' + S]).length, shin=(h['foot_' + S] - h['shin_' + S]).length,
                    upper=(h['forearm_' + S] - h['upperarm_' + S]).length, fore=(h['hand_' + S] - h['forearm_' + S]).length)


def side(S):
    return -1 if S == 'L' else 1


def frame_rot(d0, n0, d1, n1):
    """rotation taking direction d0 -> d1 and (orthogonalised) normal n0 -> n1"""
    def basis(d, n):
        d = Vector(d).normalized()
        n = Vector(n) - d * Vector(n).dot(d)
        n.normalize()
        return Matrix((d, n, d.cross(n))).transposed()
    return basis(d1, n1) @ basis(d0, n0).transposed()


# ============================================================================================ clips
class Clip:
    name, group, D = '', '', 1.0
    speed = 0.0
    props_bone = None
    footwear = 'barefoot or geta'
    notes = ''

    def __init__(self, fig):
        self.f, self.sk = fig, fig.sk
        self.meta = {}
        self.water = None
        self.contacts = None
        self.setup()

    @property
    def N(self):
        return int(round(self.D * FPS))

    def setup(self):
        pass

    def pose(self, t):
        raise NotImplementedError

    def solve(self, t):
        rot, trans, ik, plant = self.pose(t)
        S, _, info = self.f.poser.solve(rot, trans, ik)
        return S, plant, info

    # ---- shared pieces
    def stand_feet(self, ik, spread=1.0, toe_out=5.0, pole_up=0.0):
        for S in 'LR':
            s = side(S)
            an = self.sk.J['ankle' + S]
            R = rz(-s * toe_out).to_3x3()
            ik['thigh_' + S] = dict(target=Vector((an.x * spread, an.y, an.z)), pole=R @ Vector((s * 0.08, 1, pole_up)),
                                    end_rot=R)
        return ik

    def hanging_arms(self, rot, t, seed, amp=1.0):
        for S in 'LR':
            s = side(S)
            add(rot, 'upperarm_' + S, rx(1.5 + 2.0 * amp * A.pnoise(t, self.D, seed + s)) @ ry(s * -1.0))
            add(rot, 'forearm_' + S, rx(9 + 3.0 * amp * A.pnoise(t, self.D, seed + 10 + s)))
            add(rot, 'hand_' + S, rx(4 + 2.0 * amp * A.pnoise(t, self.D, seed + 20 + s)))

    def support_min(self, S, bones, exclude=('shin_L', 'shin_R', 'foot_L', 'foot_R', 'toe_L', 'toe_R'), lim=0.25):
        P = self.f.posed(S)
        zs = []
        kz = self.sk.heads['shin_L'].z + 0.06 if exclude else -9.0     # thigh / seat support: only the body above the knee
        for p, p0, ws in zip(P, self.f.coords, self.f.weights):
            if p0.z > kz and A.dominant(ws) in bones and sum(w for b, w in ws if b in exclude) < lim:
                zs.append(p.z)
        return min(zs) if zs else 0.0

    def info(self):
        m = dict(clip=self.name, group=self.group, duration_s=round(self.N / FPS, 4), frames=self.N, fps=FPS, loop=True,
                 speed_mps=self.speed, props_bone=self.props_bone, footwear=self.footwear,
                 ref_height=round(self.sk.H, 3), body=self.sk.body,
                 root='root bone fixed at the origin (in place); pelvis carries the body offset')
        m.update(self.meta)
        if self.water is not None:
            m['water'] = dict(level=round(self.water, 4), contacts=self.contacts)
        if self.notes:
            m['notes'] = self.notes
        return m


# ---------------------------------------------------------------------------------------------- walk
class Walk(Clip):
    group = 'walk'
    name, v, T = 'walk', 1.1, 0.9
    duty, arm_swing, yaw, roll, sway = 0.6, 13.0, 4.0, 2.5, 0.014
    clear, head_bow, lean = 0.045, 0.0, -2.0
    notes = 'relaxed hands, short yukata stride; plays in place, move the root at kz_clip_speed'

    def setup(self):
        self.D = self.T
        self.speed = self.v
        sk = self.sk
        hy = A.hip_centre(sk).y
        self.g = {S: A.Gait(sk, S, self.v, self.T, self.duty, u_flat=0.09, u_off=0.33, pitch_hs=10.0, pitch_to=-44.0,
                            clearance=self.clear, y_mid=hy - 0.045, toe_out=4.0) for S in 'LR'}
        # pelvis height: lower envelope of the leg reach, low-passed (harmonics 0, 2, 4 of the cycle)
        self.zc = [(0, 0.0, 0.0)]
        N = self.N
        allowed = []
        for f in range(N):
            rot, trans, ik, _ = self.pose(f / FPS)
            S, _, _ = self.f.poser.solve(rot, trans, {})
            a = 9.0
            for Sd in 'LR':
                Lg = self.f.L(Sd)['leg'] * 0.994
                hip = S['pelvis'] @ sk.heads['thigh_' + Sd]
                tg = ik['thigh_' + Sd]['target']
                d2 = (hip.x - tg.x) ** 2 + (hip.y - tg.y) ** 2
                a = min(a, tg.z + math.sqrt(max(0.0, Lg * Lg - d2)) - hip.z)
            allowed.append(a)
        coef = []
        for k in (0, 2, 4):
            c = sum(allowed[f] * math.cos(TAU * k * f / N) for f in range(N)) * (1 if k == 0 else 2) / N
            s = sum(allowed[f] * math.sin(TAU * k * f / N) for f in range(N)) * (0 if k == 0 else 2) / N
            coef.append((k, c, s))
        rec = [sum(c * math.cos(TAU * k * f / N) + s * math.sin(TAU * k * f / N) for k, c, s in coef) for f in range(N)]
        shift = min(a - r for a, r in zip(allowed, rec))
        top = max(r + shift for r in rec)
        shift -= max(0.0, top + 0.006)                    # always a little knee flex
        self.zc = [(k, c + (shift if k == 0 else 0.0), s) for k, c, s in coef]
        self.meta.update(pelvis_drop_m=[round(min(r + shift for r in rec), 4), round(max(r + shift for r in rec), 4)],
                         stride_m=round(self.v * self.T, 3), cycle_s=self.T, duty=self.duty)

    def pz(self, t):
        x = t / self.T
        return sum(c * math.cos(TAU * k * x) + s * math.sin(TAU * k * x) for k, c, s in self.zc)

    def pose(self, t):
        u = (t / self.T) % 1.0
        aL, RL, pL = self.g['L'].state(u)
        aR, RR, pR = self.g['R'].state(u - 0.5)
        um = self.duty / 2
        rot, trans = {}, {}
        trans['pelvis'] = Vector((-self.sway * math.cos(TAU * (u - um)), 0.0, self.pz(t)))
        c = math.cos(TAU * u)
        cr = math.cos(TAU * (u - um))
        add(rot, 'pelvis', rz(-self.yaw * c) @ ry(self.roll * cr))
        add(rot, 'spine', rz(0.8 * self.yaw * c) @ ry(-0.6 * self.roll * cr) @ rx(self.lean))
        add(rot, 'chest', rz(0.7 * self.yaw * c) @ ry(-0.3 * self.roll * cr))
        add(rot, 'neck', rz(-0.6 * self.yaw * c) @ rx(-self.head_bow - self.lean * 0.6))
        add(rot, 'head', rz(-0.3 * self.yaw * c) @ rx(-0.5 * self.head_bow))
        lag = 0.04
        ca = math.cos(TAU * (u - lag))
        for S in 'LR':
            s = side(S)
            sw = self.arm_swing * ca * (1 if S == 'R' else -1)
            add(rot, 'upperarm_' + S, rx(2.5 + sw) @ ry(-s * 1.5))
            add(rot, 'forearm_' + S, rx(9 + 0.45 * max(0.0, sw) + 0.15 * self.arm_swing))
            add(rot, 'hand_' + S, rx(5 + 0.2 * sw))
        ik = {}
        for S, a, R in (('L', aL, RL), ('R', aR, RR)):
            ik['thigh_' + S] = dict(target=a, pole=R @ Vector((side(S) * 0.05, 1, 0.2)), end_rot=R, reach=0.9999)
        return rot, trans, ik, {'L': pL, 'R': pR}


class WalkSlow(Walk):
    name, v, T = 'walk_slow', 0.7, 1.2
    duty, arm_swing, yaw, roll, sway = 0.65, 7.0, 2.5, 2.0, 0.011
    clear, head_bow, lean = 0.035, 5.0, -1.0
    notes = 'hush-zone walk: shorter stride, small arm swing, head slightly bowed; move the root at kz_clip_speed'


# ---------------------------------------------------------------------------------------------- idle
class IdleShift(Clip):
    group, name, D = 'idle', 'idle_shift', 6.0
    notes = 'standing weight shifts L <-> R, feet planted'

    def pose(self, t):
        D = self.D
        w = A.sqwave(t, D, 2.2)                        # +1 weight on the right foot, -1 on the left
        n = A.pnoise(t, D, 3)
        rot, trans = {}, {}
        trans['pelvis'] = Vector((0.032 * w + 0.004 * n, 0.006 * A.pnoise(t, D, 4), -0.014 - 0.006 * abs(w)))
        add(rot, 'pelvis', rz(2.5 * w) @ ry(-4.0 * w))
        add(rot, 'spine', ry(2.6 * w) @ rx(0.8 * A.pnoise(t, D, 5)))
        add(rot, 'chest', ry(1.6 * w) @ rz(-1.2 * w))
        add(rot, 'neck', ry(-0.8 * w) @ rz(4 * A.pnoise(t, D, 6)))
        add(rot, 'head', rz(5 * A.pnoise(t, D, 7)) @ rx(2 * A.pnoise(t, D, 8)) @ ry(-1.0 * w))
        self.hanging_arms(rot, t, 30)
        A.breathe(rot, trans, t, D)
        ik = self.stand_feet({}, spread=1.05)
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


class IdleLookup(Clip):
    group, name, D = 'idle', 'idle_lookup', 6.0
    notes = 'looking up at a geyser / cliff (above +Y), slow scan; feet planted'

    def pose(self, t):
        D = self.D
        up = 0.8 + 0.2 * A.cwave(t, D, 1)
        scan = 15 * A.wave(t, D, 1) + 3 * A.pnoise(t, D, 11)
        w = -0.45 + 0.15 * A.pnoise(t, D, 12)
        rot, trans = {}, {}
        trans['pelvis'] = Vector((0.032 * w, 0.012 * up, -0.014))
        add(rot, 'pelvis', ry(-4.0 * w) @ rz(2.0 * w + 0.15 * scan))
        add(rot, 'spine', rx(2.5 * up) @ ry(2.4 * w))
        add(rot, 'chest', rx(3.5 * up) @ rz(0.2 * scan) @ ry(1.4 * w))
        add(rot, 'neck', rx(14 * up) @ rz(0.4 * scan))
        add(rot, 'head', rx(15 * up) @ rz(0.3 * scan))
        self.hanging_arms(rot, t, 40, amp=0.7)
        for S in 'LR':
            add(rot, 'upperarm_' + S, rx(-4 * up))                # arms drift back a touch as the chest opens
        A.breathe(rot, trans, t, D)
        ik = self.stand_feet({}, spread=1.05)
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


class IdleTalk(Clip):
    group, name, D = 'idle', 'idle_talk', 8.0
    notes = 'one half of a talking pair, partner 1.1 m ahead (+Y) facing back; play the partner at +0.5 phase'

    def setup(self):
        self.meta.update(pair=dict(partner_offset_m=[0.0, 1.1, 0.0], partner_yaw_deg=180, partner_phase=0.5))

    def pose(self, t):
        D = self.D
        gR = A.pbump(t, D, 1.4, 1.3) + 0.8 * A.pbump(t, D, 5.5, 1.5)
        gL = 0.7 * A.pbump(t, D, 3.6, 1.1)
        nod = A.pbump(t, D, 0.8, 0.45) + A.pbump(t, D, 4.4, 0.45) + 0.7 * A.pbump(t, D, 6.9, 0.4)
        w = 0.35 * A.sqwave(t, D, 1.5, 1, 0.1)
        rot, trans = {}, {}
        trans['pelvis'] = Vector((0.03 * w, 0.004 * A.pnoise(t, D, 21), -0.014))
        add(rot, 'pelvis', ry(-4.0 * w) @ rz(2 * w))
        add(rot, 'spine', ry(2.4 * w))
        add(rot, 'chest', rz(4 * (gR - gL)) @ rx(-1.5 * (gR + gL)))
        add(rot, 'neck', rx(-5 * nod) @ rz(4 * A.pnoise(t, D, 22)))
        add(rot, 'head', rx(-3 * nod) @ ry(3 * A.pnoise(t, D, 23)) @ rz(3 * A.pnoise(t, D, 24)))
        self.hanging_arms(rot, t, 50, amp=0.6)
        for S, g in (('R', gR), ('L', gL)):
            s = side(S)
            g = min(1.0, g)
            pn = A.pnoise(t, D, 60 + s)
            add(rot, 'upperarm_' + S, rx(24 * g) @ ry(-s * 9 * g))
            add(rot, 'forearm_' + S, rx(52 * g + 6 * g * pn) @ rz(s * 25 * g))
            add(rot, 'hand_' + S, rx(-14 * g) @ rz(s * 10 * g * pn))
        A.breathe(rot, trans, t, D)
        ik = self.stand_feet({}, spread=1.05)
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


# ---------------------------------------------------------------------------------------------- sit
class SitBase(Clip):
    group = 'sit'
    seat = 0.45

    def hands_on_thighs(self, S0, t, amp=1.0, fwd=0.62, seed=0):
        """static wrist targets on top of the thighs (from the frame-0 pose), with a little drift"""
        tg = {}
        for S in 'LR':
            s = side(S)
            h = self.sk.heads
            p = S0['thigh_' + S] @ h['thigh_' + S].lerp(h['shin_' + S], fwd)
            tg[S] = p + Vector((-s * 0.02, -0.07, 0.065))
        return tg


class SitBench(SitBase):
    name, D, seat = 'sit_bench', 8.0, 0.45
    notes = 'seated still on a bench, small gestures (head turns, one hand to the knee), feet on the floor'

    def setup(self):
        sk = self.sk
        self.hip = A.hip_centre(sk).copy()
        self.hip.z = self.seat + 0.12
        self.wrist = None
        for _ in range(4):
            S, _, _ = self.solve(0.0)
            zmin = self.support_min(S, ('pelvis', 'thigh_L', 'thigh_R', 'spine'))
            self.hip.z += self.seat - zmin
        S, _, _ = self.solve(0.0)
        self.wrist = self.hands_on_thighs(S, 0.0)
        Lt = self.f.L('L')['thigh']
        self.meta.update(seat=dict(kind='bench', height=self.seat, front_y=round(self.hip.y + 0.8 * Lt, 3),
                                   depth_min=0.38, note='root on the floor below the hip joints; bench top at height'))

    def pose(self, t):
        D, sk = self.D, self.sk
        rot0, _ = KG.standard_pose('seated', sk)
        rot = {b: m for b, m in rot0.items() if not b.startswith(('thigh', 'shin', 'upperarm', 'forearm'))}
        trans = {}
        add(rot, 'pelvis', rx(-2))
        add(rot, 'spine', rx(-3 + 1.0 * A.pnoise(t, D, 71)))
        add(rot, 'chest', rx(-2) @ rz(2 * A.pnoise(t, D, 72)))
        add(rot, 'neck', rx(-4) @ rz(9 * A.pnoise(t, D, 73)))
        add(rot, 'head', rz(8 * A.pnoise(t, D, 74)) @ rx(3 * A.pnoise(t, D, 75)))
        A.breathe(rot, trans, t, D, 1.1)
        Rp = rot.get('pelvis', I4)
        trans['pelvis'] = A.pelvis_trans_for(sk, Rp, self.hip)
        ik = {}
        for S in 'LR':
            s = side(S)
            an = sk.J['ankle' + S]
            Lt = self.f.L(S)['thigh']
            tgt = Vector((an.x * 1.12, self.hip.y + Lt * 1.02 + 0.05, an.z))
            ik['thigh_' + S] = dict(target=tgt, pole=Vector((s * 0.1, 1, 0.35)), end_rot=rz(-s * 6).to_3x3())
        if self.wrist:
            g = A.pbump(t, D, 5.2, 1.6)                    # right hand slides to the knee and back
            for S in 'LR':
                s = side(S)
                w = self.wrist[S] + Vector((0.006 * A.pnoise(t, D, 80 + s), 0.01 * A.pnoise(t, D, 82 + s), 0))
                if S == 'R':
                    w = w + Vector((-0.01 * g, 0.12 * g, 0.015 * g))
                ik['upperarm_' + S] = dict(target=w, pole=Vector((s * 0.8, -0.5, -0.35)))
                add(rot, 'hand_' + S, rx(-35) @ rz(s * 8))
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


class SitStoolEat(SitBase):
    name, D, seat = 'sit_stool_eat', 6.0, 0.72
    props_bone = 'prop_R'
    notes = 'counter stool, chopsticks (prop_R) bowl -> mouth twice per loop, left hand steadies the bowl; feet on the stool footrest'
    rail, counter_h, counter_y = 0.22, 1.0, 0.30

    def setup(self):
        sk = self.sk
        self.hip = A.hip_centre(sk).copy()
        self.hip.z = self.seat + 0.12
        self.ready = False
        for _ in range(4):
            S, _, _ = self.solve(0.0)
            zmin = self.support_min(S, ('pelvis', 'thigh_L', 'thigh_R', 'spine'))
            self.hip.z += self.seat - zmin
        self.bowl = Vector((-0.02, self.hip.y + self.counter_y + 0.12, self.counter_h + 0.05))
        self.ready = True
        self.meta.update(seat=dict(kind='stool', height=self.seat, footrest_height=self.rail,
                                   counter=dict(height=self.counter_h, front_y=round(self.hip.y + self.counter_y, 3)),
                                   bowl=[round(c, 3) for c in self.bowl],
                                   note='root on the floor below the hip joints (stool centre)'),
                         prop=dict(bone='prop_R', item='chopsticks', grip='prop_R head (mid-hand)',
                                   direction='along the hand (wrist -> fingertip), 0.22 m, 0.05 m behind the grip'))

    def bite(self, t):
        x = t % 3.0
        return A.pbump(x, 3.0, 1.55, 1.0) ** 0.7

    def pose(self, t):
        D, sk = self.D, self.sk
        rot, trans = {}, {}
        b = self.bite(t) if self.ready else 0.0
        add(rot, 'pelvis', rx(-4))
        add(rot, 'spine', rx(-6 - 3 * b))
        add(rot, 'chest', rx(-4 - 2 * b) @ rz(-3 * b))
        add(rot, 'neck', rx(-8 - 6 * b + 6 * (1 - b)) @ rz(3 * A.pnoise(t, D, 91)))
        add(rot, 'head', rx(-12 + 4 * b) @ rz(3 * A.pnoise(t, D, 92)))
        A.breathe(rot, trans, t, D, 0.8)
        trans['pelvis'] = A.pelvis_trans_for(sk, rot['pelvis'], self.hip)
        ik = {}
        for S in 'LR':
            s = side(S)
            tgt = Vector((s * 0.1, self.hip.y + 0.15, self.rail + 0.0125 + sk.J['ankle' + S].z - 0.01))
            ik['thigh_' + S] = dict(target=tgt, pole=Vector((s * 0.12, 1, 0.2)), end_rot=(rz(-s * 8) @ rx(-12)).to_3x3())
        if self.ready:
            s = 1
            hd0 = (sk.J['handtipR'] - sk.J['wristR']).normalized()
            n0 = Vector((-1, 0, 0))
            d_bowl, n_bowl = Vector((-0.35, 0.55, -0.75)), Vector((-0.3, -0.5, 0.3))
            d_mouth, n_mouth = Vector((-0.85, -0.25, 0.32)), Vector((0.1, 0.3, -1))
            R0 = frame_rot(hd0, n0, d_bowl, n_bowl)
            R1 = frame_rot(hd0, n0, d_mouth, n_mouth)
            q = R0.to_quaternion().slerp(R1.to_quaternion(), b)
            Rh = q.to_matrix()
            dcur = Rh @ hd0
            grip = (sk.heads['prop_R'] - sk.J['wristR']).length
            bowl_w = self.bowl + Vector((0.0, 0.0, 0.04)) - d_bowl.normalized() * (grip + 0.17)
            bowl_w += Vector((0.0, 0.0, 0.02 * A.pnoise(t, D, 93)))
            fwd = self.f
            mouth_fn = lambda SS, b=b, dcur=dcur, grip=grip, bw=bowl_w: bw.lerp(fwd.mouth(SS) - dcur * (grip + 0.17) + Vector((0, 0.01, -0.01)), b)
            ik['upperarm_R'] = dict(target=mouth_fn, pole=Vector((1, -0.4, -0.6)), end_rot=Rh)
            lw = self.bowl + Vector((-0.11, -0.07, 0.03))
            ik['upperarm_L'] = dict(target=lw, pole=Vector((-1, -0.6, -0.5)),
                                    end_rot=frame_rot((sk.J['handtipL'] - sk.J['wristL']).normalized(), Vector((1, 0, 0)),
                                                      Vector((0.55, 0.75, -0.25)), Vector((0.4, -0.2, -1))))
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


class SitSeiza(SitBase):
    name, D, seat = 'sit_seiza', 8.0, 0.08
    notes = 'kneeling seiza on a zabuton (top at 0.08 m), hands on the thighs; barefoot (the geta pass under the seat: use a no-geta variant indoors)'
    footwear = 'barefoot (indoor)'

    def setup(self):
        sk = self.sk
        Lt, Ls = self.f.L('L')['thigh'], self.f.L('L')['shin']
        kz = self.seat + 0.055
        az = self.seat + 0.05
        self.hip = A.hip_centre(sk).copy()
        hy = self.hip.y
        dk = math.sqrt(max(1e-6, Ls * Ls - (kz - az) ** 2)) * 0.995
        ky = hy + dk - 0.06                                  # knee ahead of the hip, ankles just behind it
        self.knee_y, self.ankle_y = ky, ky - dk
        self.hip.z = kz + math.sqrt(max(1e-6, Lt * Lt - (ky - hy) ** 2)) * 0.995
        self.dz = 0.0
        self.wrist = None
        # the shin / knee rest on the cushion by construction (knee joint seat + 0.055, ankle seat + 0.05); a mesh
        # calibration here picks up the folded ankle skin and lifts the figure, so it is not used
        S, _, _ = self.solve(0.0)
        self.wrist = self.hands_on_thighs(S, 0.0, fwd=0.45)
        self.meta.update(seat=dict(kind='zabuton', height=self.seat, cushion_centre_y=round((ky + self.ankle_y) / 2, 3),
                                   note='root on the floor below the hip joints; zabuton top at height'))

    def pose(self, t):
        D, sk = self.D, self.sk
        rot, trans = {}, {}
        add(rot, 'pelvis', rx(2))
        add(rot, 'spine', rx(1 + 0.6 * A.pnoise(t, D, 101)))
        add(rot, 'neck', rx(-6) @ rz(5 * A.pnoise(t, D, 102)))
        add(rot, 'head', rx(-3 + 2 * A.pnoise(t, D, 103)) @ rz(4 * A.pnoise(t, D, 104)))
        A.breathe(rot, trans, t, D, 1.0)
        dz = Vector((0, 0, self.dz))
        trans['pelvis'] = A.pelvis_trans_for(sk, rot['pelvis'], self.hip + dz)
        ik = {}
        for S in 'LR':
            s = side(S)
            k = Vector((s * 0.085, self.knee_y, self.seat + 0.055)) + dz
            a = Vector((s * 0.06, self.ankle_y, self.seat + 0.05)) + dz
            ik['thigh_' + S] = dict(target=a, knee=k, end_rot=(rz(s * 6) @ rx(222)).to_3x3(), reach=0.9999)
        if self.wrist:
            for S in 'LR':
                s = side(S)
                ik['upperarm_' + S] = dict(target=self.wrist[S] + Vector((0, 0.008 * A.pnoise(t, D, 110 + s), 0)),
                                           pole=Vector((s * 0.7, -0.6, -0.4)))
                add(rot, 'hand_' + S, rx(-40) @ rz(s * 10))
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


class SitLounger(SitBase):
    name, D, seat = 'sit_lounger', 8.0, 0.42
    back_deg = 40.0
    notes = 'reclining on a lounger: back at 40 deg above horizontal (the lounger back board), legs out on the mattress'

    def setup(self):
        sk = self.sk
        self.hip = A.hip_centre(sk).copy()
        self.hip.z = self.seat + 0.12
        self.wrist = None
        for _ in range(4):
            S, _, _ = self.solve(0.0)
            zmin = self.support_min(S, ('pelvis', 'thigh_L', 'thigh_R', 'spine'))
            self.hip.z += self.seat - zmin
        S, _, _ = self.solve(0.0)
        P = self.f.posed(S)
        back = [p for p, ws in zip(P, self.f.weights) if A.dominant(ws) in ('spine', 'chest')]
        # back board line: the board touches the back at 40 deg; record the hinge (where it meets the seat)
        th = math.radians(self.back_deg)
        n = Vector((0, math.sin(th), math.cos(th)))           # board normal (points up-forward)
        off = min((p - Vector((0, self.hip.y, self.seat))).dot(n) for p in back)
        hinge_y = self.hip.y + off / math.sin(th)
        self.meta.update(seat=dict(kind='lounger', height=self.seat, back_angle_deg=self.back_deg,
                                   back_hinge_y=round(hinge_y, 3),
                                   note='root on the floor below the hip joints; mattress top at height, back board '
                                        'plane at back_angle_deg rising towards -Y from back_hinge_y'))

    def pose(self, t):
        D, sk = self.D, self.sk
        rot, trans = {}, {}
        rec = 90 - self.back_deg
        add(rot, 'pelvis', rx(rec * 0.62))
        add(rot, 'spine', rx(rec * 0.22))
        add(rot, 'chest', rx(rec * 0.16 - 2))
        add(rot, 'neck', rx(-rec * 0.5) @ rz(8 * A.pnoise(t, D, 121)))
        add(rot, 'head', rx(-rec * 0.22) @ rz(6 * A.pnoise(t, D, 122)))
        A.breathe(rot, trans, t, D, 1.4)
        trans['pelvis'] = A.pelvis_trans_for(sk, rot['pelvis'], self.hip)
        ik = {}
        for S in 'LR':
            s = side(S)
            Lg = self.f.L(S)['leg']
            wig = A.pnoise(t, D, 130 + s)
            a = Vector((s * 0.12, self.hip.y + Lg * 0.95, self.seat + 0.075))
            ik['thigh_' + S] = dict(target=a, pole=Vector((s * 0.15, 0.3, 1.0)),
                                    end_rot=(rz(-s * (12 + 4 * wig)) @ rx(-18 + 5 * wig)).to_3x3())
        # hands: left resting on the belly, right on the mattress beside the hip
        h = sk.heads
        belly = lambda SS: SS['spine'] @ (h['spine'] + Vector((-0.04, 0.16, 0.02)))
        ik['upperarm_L'] = dict(target=belly, pole=Vector((-1, -0.3, -0.4)))
        ik['upperarm_R'] = dict(target=Vector((0.25, self.hip.y - 0.04, self.seat + 0.04 + 0.012 * A.pnoise(t, D, 133))),
                                pole=Vector((1, -0.5, 0.2)))
        add(rot, 'hand_L', rx(-30))
        add(rot, 'hand_R', rx(10))
        return rot, trans, ik, {'L': None, 'R': None}


# ---------------------------------------------------------------------------------------------- soak
class SoakBase(Clip):
    group = 'soak'

    def water_contacts(self, every=6):
        tracks = {}
        for f in range(0, self.N, every):
            S, _, _ = self.solve(f / FPS)
            P = self.f.posed(S)
            for g, (x, y, r) in A.water_contacts(P, self.f.weights, self.water).items():
                tracks.setdefault(g, []).append([round(f / FPS, 3), round(x, 3), round(y, 3), round(r, 3)])
        self.contacts = [dict(group=g, track_t_x_y_r=tr) for g, tr in sorted(tracks.items())]


class SoakRim(SoakBase):
    name, D, ledge = 'soak_rim', 10.0, 0.42
    notes = 'chest-deep on a submerged ledge, back to the pool wall, arms out along the rim, slow head turns'

    def setup(self):
        sk = self.sk
        self.hip = A.hip_centre(sk).copy()
        self.hip.z = self.ledge + 0.12
        self.rim = None
        for _ in range(4):
            S, _, _ = self.solve(0.0)
            zmin = self.support_min(S, ('pelvis', 'thigh_L', 'thigh_R'))
            self.hip.z += self.ledge - zmin
        S, _, _ = self.solve(0.0)
        P = self.f.posed(S)
        chest_z = (S['chest'] @ sk.heads['chest']).z
        self.water = chest_z + 0.03
        back = [p.y for p, ws in zip(P, self.f.weights) if A.dominant(ws) in ('chest', 'spine') and p.z > self.water - 0.25]
        self.rim = dict(wall_y=min(back) - 0.01, top_z=self.water + 0.04)
        self.water_contacts()
        self.meta.update(seat=dict(kind='submerged ledge', height=self.ledge),
                         rim=dict(wall_y=round(self.rim['wall_y'], 3), top_z=round(self.rim['top_z'], 3),
                                  note='pool wall face behind the figure at wall_y, rim / deck top at top_z'),
                         water_depth_m=round(self.water, 3))

    def pose(self, t):
        D, sk = self.D, self.sk
        rot0, _ = KG.standard_pose('soaking', sk)
        rot, trans = {}, {}
        add(rot, 'pelvis', rx(12))
        add(rot, 'spine', rx(3))
        add(rot, 'chest', rx(-3))
        yaw = 32 * A.sqwave(t, D, 1.8) + 4 * A.pnoise(t, D, 141)
        add(rot, 'neck', rx(-12 + 3 * A.pnoise(t, D, 142)) @ rz(0.45 * yaw))
        add(rot, 'head', rx(-4) @ rz(0.55 * yaw) @ ry(2 * A.pnoise(t, D, 143)))
        A.breathe(rot, trans, t, D, 1.3)
        trans['pelvis'] = A.pelvis_trans_for(sk, rot['pelvis'], self.hip)
        ik = {}
        for S in 'LR':
            s = side(S)
            Lt = self.f.L(S)['thigh']
            an = sk.J['ankle' + S]
            a = Vector((s * 0.14, self.hip.y + Lt * 0.92, an.z))
            ik['thigh_' + S] = dict(target=a, pole=Vector((s * 0.1, 1, 0.5)), end_rot=rz(-s * 10).to_3x3())
        if self.rim:
            wy, tz = self.rim['wall_y'], self.rim['top_z']
            for S in 'LR':
                s = side(S)
                ik['upperarm_' + S] = dict(target=Vector((s * 0.6, wy - 0.17, tz + 0.03)),
                                           knee=Vector((s * 0.4, wy - 0.05, tz + 0.05)))
                add(rot, 'hand_' + S, rx(-10) @ ry(s * 20))
        for b in ('clavicle_L', 'clavicle_R'):
            add(rot, b, ry((1 if b.endswith('L') else -1) * 6))         # shoulders up a little (arms out)
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


class SoakFree(SoakBase):
    name, D, ledge = 'soak_free', 8.0, 0.30
    notes = 'shoulder-deep on a low submerged step, hands drifting in front, slow sway'

    def setup(self):
        sk = self.sk
        self.hip = A.hip_centre(sk).copy()
        self.hip.z = self.ledge + 0.12
        self.ready = False
        for _ in range(4):
            S, _, _ = self.solve(0.0)
            zmin = self.support_min(S, ('pelvis', 'thigh_L', 'thigh_R'))
            self.hip.z += self.ledge - zmin
        S, _, _ = self.solve(0.0)
        sh = (S['upperarm_L'] @ sk.heads['upperarm_L']).z
        self.water = sh - 0.03
        self.ready = True
        self.water_contacts()
        self.meta.update(seat=dict(kind='submerged step', height=self.ledge), water_depth_m=round(self.water, 3))

    def pose(self, t):
        D, sk = self.D, self.sk
        rot, trans = {}, {}
        add(rot, 'pelvis', rx(3 + 2 * A.pnoise(t, D, 161)) @ rz(3 * A.pnoise(t, D, 162)))
        add(rot, 'spine', rx(-2) @ ry(1.5 * A.pnoise(t, D, 163)))
        add(rot, 'chest', rx(-2))
        add(rot, 'neck', rx(-4) @ rz(12 * A.pnoise(t, D, 164)))
        add(rot, 'head', rz(10 * A.pnoise(t, D, 165)) @ rx(2 * A.pnoise(t, D, 166)))
        A.breathe(rot, trans, t, D, 1.2)
        trans['pelvis'] = A.pelvis_trans_for(sk, rot['pelvis'], self.hip)
        ik = {}
        for S in 'LR':
            s = side(S)
            Lt = self.f.L(S)['thigh']
            an = sk.J['ankle' + S]
            a = Vector((s * 0.13, self.hip.y + Lt + 0.12, an.z))
            ik['thigh_' + S] = dict(target=a, pole=Vector((s * 0.1, 1, 0.3)), end_rot=rz(-s * 8).to_3x3())
        if self.ready:
            for S in 'LR':
                s = side(S)
                ph = 0.0 if S == 'L' else 0.37
                c = Vector((s * 0.24, self.hip.y + 0.33, self.water - 0.2))
                d = Vector((0.06 * A.wave(t, D, 1, ph) * s, 0.05 * A.wave(t, D, 2, ph + 0.1), 0.03 * A.wave(t, D, 1, ph + 0.3)))
                ik['upperarm_' + S] = dict(target=c + d, pole=Vector((s * 1, -0.4, -0.6)))
                add(rot, 'hand_' + S, rx(-8 + 10 * A.wave(t, D, 2, ph)) @ rz(s * 15))
        return rot, trans, ik, {'L': 'flat', 'R': 'flat'}


# ---------------------------------------------------------------------------------------------- float
class FloatBack(SoakBase):
    group, name, D = 'float', 'float_back', 8.0
    notes = 'floating on the back, arms out, slight roll / yaw sway and bob; lowest point (the back) at the root z'

    def setup(self):
        self.off = Vector()
        S, _, _ = self.solve(0.0)
        P = self.f.posed(S)
        xs, ys, zs = [p.x for p in P], [p.y for p in P], [p.z for p in P]
        self.off = Vector((-(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, -min(zs)))
        self.water = 0.15 * self.sk.k
        self.water_contacts()
        self.meta.update(note_root='root at the body centre, z = the lowest point of the back at frame 0')

    def pose(self, t):
        D, sk = self.D, self.sk
        rot0, root_rot = KG.standard_pose('floating', sk)
        rot = dict(rot0)
        trans = {}
        rot['pelvis'] = root_rot @ ry(2.5 * A.wave(t, D, 1)) @ rz(1.5 * A.wave(t, D, 1, 0.25)) @ rot.get('pelvis', I4)
        rot['neck'] = rx(-6)
        rot['head'] = rx(-3) @ rz(5 * A.pnoise(t, D, 171))
        for S in 'LR':
            s = side(S)
            ph = 0.0 if S == 'L' else 0.5
            add(rot, 'upperarm_' + S, rx(4 * A.wave(t, D, 2, ph)))
            add(rot, 'forearm_' + S, rx(6 * A.wave(t, D, 2, ph + 0.1)))
            add(rot, 'hand_' + S, rx(10 * A.wave(t, D, 2, ph + 0.2)))
            add(rot, 'thigh_' + S, rx(3 * A.wave(t, D, 2, ph + 0.25)))
            add(rot, 'shin_' + S, rx(-4 - 2 * A.wave(t, D, 2, ph + 0.35)))
            add(rot, 'foot_' + S, rx(-28))
        A.breathe(rot, trans, t, D, 1.5)
        h = sk.heads['pelvis']
        trans['pelvis'] = self.off + Vector((0, 0, 0.008 * A.wave(t, D, 2)))
        return rot, trans, {}, {'L': None, 'R': None}


class FloatRing(SoakBase):
    group, name, D = 'float', 'float_ring', 8.0
    notes = 'seated through a float_ring (seed 1), back on the rear tube, knees over the front tube, legs dangling, arms along the sides'

    def setup(self):
        ring = ring_info()
        self.ring = ring
        Ro, r, H = ring['outer_r'], ring['minor_r'], ring['h']
        self.Rc = Ro - r
        self.top = H
        Lt = self.f.L('L')['thigh']
        sk = self.sk
        self.knee = Vector((0.0, self.Rc - 0.01, self.top + 0.05))
        hip_z = ring['waterline'] - 0.02
        dz = self.knee.z - hip_z
        self.hip = Vector((0.0, self.knee.y - math.sqrt(max(1e-6, Lt * Lt - dz * dz)) * 0.99, hip_z))
        self.recline = 30.0
        best = None
        for rec in range(18, 66, 4):                         # recline until the back meets the rear tube
            self.recline = float(rec)
            S, _, _ = self.solve(0.0)
            P = self.f.posed(S)
            d = min(self.tdist(p) for p, ws in zip(P, self.f.weights) if A.dominant(ws) in ('chest', 'spine', 'neck'))
            if best is None or abs(d - 0.01) < abs(best[1] - 0.01):
                best = (rec, d)
        self.recline = float(best[0])
        S, _, _ = self.solve(0.0)
        P = self.f.posed(S)
        self.water = ring['waterline']
        self.water_contacts()
        pen = min(self.tdist(p) for p in P)
        self.meta.update(ring=ring, back_gap_m=round(best[1], 3), recline_deg=self.recline,
                         ring_penetration_m=round(min(0.0, pen), 3),
                         note_root='root = float_ring origin (base centre); move the ring and the figure together')

    def tdist(self, p):
        rho = math.hypot(p.x, p.y)
        return math.hypot(rho - self.Rc, p.z - self.top / 2) - self.ring['minor_r'] * 0.97

    def pose(self, t):
        D, sk = self.D, self.sk
        rot, trans = {}, {}
        add(rot, 'pelvis', rx(self.recline * 0.7) @ rz(2.0 * A.wave(t, D, 1)) @ ry(1.5 * A.wave(t, D, 1, 0.3)))
        add(rot, 'spine', rx(self.recline * 0.2))
        add(rot, 'chest', rx(self.recline * 0.1))
        add(rot, 'neck', rx(-self.recline * 0.55) @ rz(14 * A.pnoise(t, D, 181)))
        add(rot, 'head', rx(-self.recline * 0.25) @ rz(10 * A.pnoise(t, D, 182)))
        A.breathe(rot, trans, t, D, 1.2)
        trans['pelvis'] = A.pelvis_trans_for(sk, rot['pelvis'], self.hip)
        ik = {}
        for S in 'LR':
            s = side(S)
            Ls = self.f.L(S)['shin']
            ph = 0.0 if S == 'L' else 0.5
            k = self.knee + Vector((s * 0.1, 0, 0))
            sw = 0.06 * A.wave(t, D, 2, ph)
            a = k + Vector((s * 0.02, Ls * (0.22 + sw), -Ls * math.sqrt(max(0.0, 1 - (0.22 + sw) ** 2)) * 0.995))
            ik['thigh_' + S] = dict(target=a, knee=k + Vector((0, 0.02, 0.05)), end_rot=(rz(-s * 8) @ rx(-30)).to_3x3(),
                                    reach=0.9999)
            el = Vector((s * (self.Rc + 0.02), -0.12, self.top + 0.05))
            wr = Vector((s * (self.Rc - 0.02), 0.15 + 0.02 * A.pnoise(t, D, 185 + s), self.top + 0.045))
            ik['upperarm_' + S] = dict(target=wr, knee=el)
            add(rot, 'hand_' + S, rx(-15))
        return rot, trans, ik, {'L': None, 'R': None}


_RING = {}


def ring_info():
    """float_ring seed 1 dimensions (built once, measured, deleted)"""
    if not _RING:
        o = genlib.build('float_ring', lod=0, seed=1)
        b = genlib.bbox(o)
        P = json.loads(o['kz_params']) if 'kz_params' in o else {}
        ro = (b['w'] + b['d']) / 4
        r = P.get('r_minor', b['h'] / 2 / 0.94)
        _RING.update(asset='float_ring', seed=1, outer_r=round(ro, 3), minor_r=round(b['h'] / 2, 3), h=round(b['h'], 3),
                     waterline=round(float(o.get('kz_waterline', b['h'] * 0.45)), 3))
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    return dict(_RING)


CLIPS = [Walk, WalkSlow, IdleShift, IdleLookup, IdleTalk, SitBench, SitStoolEat, SitSeiza, SitLounger, SoakRim, SoakFree,
         FloatBack, FloatRing]
BY_NAME = {c.name: c for c in CLIPS}
GROUPS = ['walk', 'idle', 'sit', 'soak', 'float']


def selected():
    if ONLY:
        if ONLY not in BY_NAME:
            raise SystemExit(f'unknown clip {ONLY}; one of {list(BY_NAME)}')
        return [BY_NAME[ONLY]]
    return CLIPS


# ============================================================================================ bake + checks
def bake_clip(fig, cls):
    c = cls(fig)
    frames, plants, errs, by = [], [], [], {}
    for f in range(c.N + 1):
        S, plant, info = c.solve(f / FPS)
        frames.append(S)
        plants.append(plant)
        errs.append(max([i['err'] for i in info.values()] or [0.0]))
        for k, i in info.items():
            by[k] = max(by.get(k, 0.0), round(i['err'], 4))
    m = c.info()
    props = dict(kz_clip=m, kz_clip_speed=float(c.speed))
    if c.water is not None:
        props['kz_water_level'] = float(round(c.water, 4))
    act = A.bake_action(fig.arm, c.name, frames, KG.BONES, props)
    def_seam = max((frames[0][b] @ fig.sk.heads[b] - frames[-1][b] @ fig.sk.heads[b]).length for b in KG.BONES)
    return c, act, dict(plants=plants, ik_err=max(errs), ik_by={k: v for k, v in by.items() if v > 0}, def_seam=def_seam)


def eval_S(arm, f):
    bpy.context.scene.frame_set(f)
    out = {}
    for b in KG.BONES:
        pb = arm.pose.bones[b]
        out[b] = arm.matrix_world @ pb.matrix @ arm.data.bones[b].matrix_local.inverted()
    return out


def check_clip(fig, c, act, extra):
    """evaluate the baked action on the rig: seam error, seam jerk, foot slide on planted frames, clearance"""
    arm, sk = fig.arm, fig.sk
    arm.animation_data.action = act
    N = c.N
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, N
    Ss = [eval_S(arm, f) for f in range(N + 1)]
    pts = {b: [S[b] @ sk.heads[b] for S in Ss] for b in KG.BONES}
    tails = {b: [S[b] @ sk.tails[b] for S in Ss] for b in KG.BONES}
    seam = max(max((pts[b][0] - pts[b][N]).length, (tails[b][0] - tails[b][N]).length) for b in KG.BONES)
    ang = 0.0
    for b in KG.BONES:
        q0, q1 = Ss[0][b].to_quaternion(), Ss[N][b].to_quaternion()
        ang = max(ang, math.degrees(q0.rotation_difference(q1).angle))
    # jerk across the seam vs the largest second difference elsewhere (cyclic)
    def acc(b, f):
        p = tails[b]
        return (p[(f + 1) % N] - 2 * p[f % N] + p[(f - 1) % N]).length
    seam_acc = max(acc(b, 0) for b in KG.BONES)
    in_acc = max(acc(b, f) for b in KG.BONES for f in range(1, N))
    # feet
    v = c.speed
    slide = 0.0
    slide_by = {}
    clear = 9.0
    pen = 0.0
    planted_frames = 0
    for S in 'LR':
        heel_b = Vector((sk.J['ankle' + S].x, sk.J['heel' + S].y - 0.007, 0.0))
        tip_b = Vector((sk.J['ankle' + S].x, sk.J['toe' + S].y + 0.025, 0.0))
        spans = {'heel': [], 'tip': []}
        prev = None
        for f in range(N + 1):
            pv = extra['plants'][f][S] if extra['plants'][f] else None
            Sf = Ss[f]
            mv = Vector((0, v * f / FPS, 0))
            heel = Sf['foot_' + S] @ heel_b + mv
            tip = Sf['foot_' + S] @ tip_b + mv
            if pv is None:
                if c.group == 'walk':
                    clear = min(clear, heel.z, tip.z)
                prev = None
                continue
            planted_frames += 1
            pen = min(pen, heel.z if pv in ('heel', 'flat') else 0.0, tip.z if pv in ('tip', 'flat') else 0.0)
            if prev is None:
                spans = {'heel': [], 'tip': []}
                anchor = {}
            if pv in ('heel', 'flat'):
                anchor.setdefault('heel', heel)
                slide_by.setdefault(S, 0.0)
                d = (heel - anchor['heel']).length
                slide = max(slide, d)
                slide_by[S] = max(slide_by[S], d)
            if pv in ('tip', 'flat'):
                anchor.setdefault('tip', tip)
                slide_by.setdefault(S, 0.0)
                d = (tip - anchor['tip']).length
                slide = max(slide, d)
                slide_by[S] = max(slide_by[S], d)
            prev = pv
    # clothing strain over 8 sampled frames (yukata / samue shell only)
    strain = None
    if fig.cloth:
        cl_edges = [e for e in fig.edges if e[0] in fig.cloth and e[1] in fig.cloth]
        mx = dict(max=1.0, p99=1.0, min=1.0, p01=1.0)
        for f in range(0, N, max(1, N // 8)):
            P = fig.posed(Ss[f])
            st = A.edge_strain(fig.coords, P, cl_edges)
            mx = dict(max=max(mx['max'], st['max']), p99=max(mx['p99'], st['p99']), min=min(mx['min'], st['min']),
                      p01=min(mx['p01'], st['p01']))
        strain = mx
    return dict(clip=c.name, group=c.group, frames=N, keys=N + 1, duration_s=round(N / FPS, 4), fps=FPS,
                bones=len(arm.data.bones), bones_keyed=len({fc.group.name for fc in _fcurves(act, arm) if fc.group}),
                loop_seam_error_m=round(seam, 6), loop_seam_error_deg=round(ang, 4),
                seam_accel_m=round(seam_acc, 5), max_accel_elsewhere_m=round(in_acc, 5),
                procedural_seam_m=round(extra['def_seam'], 6),
                foot_slide_planted_m=round(slide, 5), foot_slide_by_foot_m={k: round(x, 5) for k, x in slide_by.items()},
                planted_foot_frames=planted_frames,
                swing_clearance_min_m=(round(clear, 4) if clear < 9 else None),
                planted_penetration_m=round(pen, 4), ik_reach_error_m=round(extra['ik_err'], 5),
                ik_reach_error_by_chain=extra['ik_by'],
                speed_mps=c.speed, water_level=(round(c.water, 4) if c.water is not None else None),
                cloth_edge_strain=strain)


def _fcurves(act, arm):
    from bpy_extras import anim_utils
    slot = arm.animation_data.action_slot
    cb = anim_utils.action_get_channelbag_for_slot(act, slot)
    return list(cb.fcurves) if cb else []


def build_clips(fig, classes=None, check=False):
    out, checks = {}, []
    for cls in classes or CLIPS:
        t0 = time.time()
        c, act, extra = bake_clip(fig, cls)
        out[c.name] = (c, act)
        if check:
            r = check_clip(fig, c, act, extra)
            r['bake_s'] = round(time.time() - t0, 1)
            checks.append(r)
            print('CHECK', json.dumps(r))
    fig.arm.animation_data.action = None
    return out, checks


def stage_bake():
    fig = Fig(REF['asset'], REF['seed'], height=REF['height'], build=REF['build'])
    clips, checks = build_clips(fig, selected(), check=True)
    report = dict(asset='figure_anims', rig=dict(asset=REF['asset'], seed=REF['seed'], body=fig.sk.body, height=fig.sk.H,
                                                 bones=len(fig.arm.data.bones), bone_names=KG.BONES,
                                                 rest_vs_skeleton_m=round(fig.rest_err, 6)),
                  fps=FPS, clips=checks)
    if ONLY and os.path.exists(CHECKS):
        old = json.load(open(CHECKS))
        keep = [c for c in old.get('clips', []) if c['clip'] != ONLY]
        report['clips'] = sorted(keep + checks, key=lambda c: [k.name for k in CLIPS].index(c['clip']))
    json.dump(report, open(CHECKS, 'w'), indent=1)
    # save: the reference rig (unparented, no mesh) + every action (fake users)
    arm = fig.arm
    mw = arm.matrix_world.copy()
    arm.parent = None
    arm.matrix_world = mw
    arm.name = 'kz_figure_rig'
    arm.data.name = 'kz_figure_rig'
    arm['kz_rig_ref'] = json.dumps(dict(REF, body=fig.sk.body, bones=KG.BONES,
                                        note='bind = standing; actions are in place; kz_clip on each action'))
    me = fig.o.data
    bpy.data.objects.remove(fig.o)
    bpy.data.meshes.remove(me)
    for o in list(bpy.data.objects):
        if o is not arm:
            bpy.data.objects.remove(o)
    if ONLY and os.path.exists(BLEND):
        # merge: bring the other clips from the existing file
        with bpy.data.libraries.load(BLEND, link=False) as (src, dst):
            dst.actions = [n for n in src.actions if n != ONLY and n in BY_NAME]
        for a in dst.actions:
            if a is not None:
                a.use_fake_user = True
                for sl in a.slots:
                    pass
    arm.animation_data.action = bpy.data.actions.get('walk')
    for a in bpy.data.actions:
        a.use_fake_user = True
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    tmp = os.path.join(SCR, 'figure_anims_tmp.blend')       # (the merge source cannot be overwritten in place)
    bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True)
    os.replace(tmp, BLEND)
    print('SAVED', BLEND, [a.name for a in bpy.data.actions])


# ============================================================================================ export test
def parse_glb(path):
    import struct
    data = open(path, 'rb').read()
    magic, ver, length = struct.unpack('<4sII', data[:12])
    clen, ctype = struct.unpack('<II', data[12:20])
    js = json.loads(data[20:20 + clen])
    anims = []
    for a in js.get('animations', []):
        tmax = 0.0
        for s in a['samplers']:
            acc = js['accessors'][s['input']]
            tmax = max(tmax, acc.get('max', [0])[0])
        anims.append(dict(name=a['name'], duration_s=round(tmax, 4), channels=len(a['channels']), extras=a.get('extras')))
    skins = [dict(name=s.get('name'), joints=len(s['joints'])) for s in js.get('skins', [])]
    return dict(animations=anims, skins=skins, meshes=len(js.get('meshes', [])), nodes=len(js.get('nodes', [])),
                bytes=len(data))


def stage_export():
    results = []
    for asset, seed in (('guest_figure', 1), ('staff_figure', 1)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = FPS              # glTF times = frame / scene fps
        bpy.context.scene.render.fps_base = 1.0
        fig = Fig(asset, seed)
        clips, _ = build_clips(fig)
        expect = {n: c.N / FPS for n, (c, a) in clips.items()}
        o, arm = fig.o, fig.arm
        # glTF wants the armature as the skin root: re-parent mesh under the armature (same world placement)
        arm.parent = None
        o.parent = arm
        arm.animation_data.action = None
        for ob in bpy.data.objects:
            ob.select_set(ob in (o, arm))
        bpy.context.view_layer.objects.active = arm
        path = os.path.join(SCR, f'{asset}_s{seed}_anims.glb')
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_animations=True,
                                  export_animation_mode='ACTIONS', export_force_sampling=True, export_extras=True,
                                  export_def_bones=False, export_skins=True, export_morph=True, export_yup=True,
                                  export_apply=False, export_anim_slide_to_zero=False, export_optimize_animation_size=False)
        g = parse_glb(path)
        # re-import into an empty scene and read back what Blender sees
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=path)
        arms = [ob for ob in bpy.data.objects if ob.type == 'ARMATURE']
        acts = {a.name: (a.frame_range[1] - a.frame_range[0]) / FPS for a in bpy.data.actions}
        got = {a['name']: a['duration_s'] for a in g['animations']}
        missing = sorted(set(expect) - set(got))
        dur_err = max((abs(got[n] - expect[n]) for n in expect if n in got), default=None)
        r = dict(file=os.path.relpath(path, ROOT), asset=asset, seed=seed, params=fig.P, glb=g,
                 reimport=dict(armatures=len(arms), bones=len(arms[0].data.bones) if arms else 0,
                               actions={k: round(v, 3) for k, v in sorted(acts.items())}),
                 expected_clips=sorted(expect), missing=missing, max_duration_error_s=dur_err,
                 ok=(not missing and dur_err is not None and dur_err < 1e-3 and all(s['joints'] == 24 for s in g['skins'])))
        print('EXPORT', json.dumps(dict(r, glb=dict(g, animations=[(a['name'], a['duration_s']) for a in g['animations']]))))
        results.append(r)
    if os.path.exists(CHECKS):
        rep = json.load(open(CHECKS))
        rep['export_test'] = results
        json.dump(rep, open(CHECKS, 'w'), indent=1)


# ============================================================================================ renders
RENDER_FIG = dict(walk=('guest_figure', 1), idle=('guest_figure', 1), sit=('guest_figure', 1), soak=('guest_figure', 5),
                  float=('guest_figure', 12))
REFS = dict(walk=['lookbook/img/04-arrival-gate.jpg', 'lookbook/img/05-mist-corridor.jpg'],
            idle=['lookbook/img/04-arrival-gate.jpg', 'lookbook/img/14-geyser-plaza.jpg'],
            sit=['lookbook/img/09-neon-ramen-counter.jpg', 'lookbook/img/20-wave-grotto.jpg'],
            soak=['lookbook/img/11-caldera-crown.jpg', 'lookbook/img/16-steam-grotto.jpg', 'lookbook/img/18-rimstone-terraces.jpg'],
            float=['lookbook/img/15-obsidian-mirror.jpg', 'lookbook/img/12-lava-tube-lazy-river.jpg'])


def mat(name, col, rough=0.7, alpha=1.0, emit=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = rough
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except AttributeError:
            pass
    return m


def box(name, c, size, m):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    o['kz_prop'] = 1
    return o


def cyl(name, a, b, r, m, segs=16):
    import bmesh
    a, b = Vector(a), Vector(b)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=(b - a).length)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    q = Vector((0, 0, 1)).rotation_difference((b - a).normalized())
    o.matrix_world = Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4()
    o.data.materials.append(m)
    o['kz_prop'] = 1
    return o


def torus(name, c, R, r, m):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=c, major_segments=32, minor_segments=8)
    o = bpy.context.object
    o.data.materials.append(m)
    o['kz_prop'] = 1
    return o


class Props:
    """set dressing for a clip (plain floor + seat / water / ring); chopsticks follow prop_R per frame"""

    def __init__(self, c, fig, at=Vector()):
        self.objs, self.chop = [], []
        self.c, self.fig, self.at = c, fig, Vector(at)
        wood = mat('kz_prev_wood', (0.16, 0.1, 0.06), 0.6)
        stone = mat('kz_prev_stone', (0.12, 0.12, 0.12), 0.8)
        water = mat('kz_prev_water', (0.05, 0.25, 0.3), 0.05, alpha=0.45)
        cloth = mat('kz_prev_cloth', (0.08, 0.09, 0.16), 0.9)
        cer = mat('kz_prev_bowl', (0.5, 0.18, 0.08), 0.3)
        at = self.at
        m = c.meta.get('seat', {})
        kind = m.get('kind')
        hy = A.hip_centre(fig.sk).y
        if kind == 'bench':
            fy = m['front_y']
            self.objs.append(box('bench', at + Vector((0, fy - 0.21, c.seat / 2)), (1.0, 0.42, c.seat), wood))
        elif kind == 'stool':
            self.objs.append(box('stool_seat', at + Vector((0, hy, c.seat - 0.02)), (0.36, 0.36, 0.04), wood))
            self.objs.append(cyl('stool_leg', at + Vector((0, hy, 0)), at + Vector((0, hy, c.seat - 0.04)), 0.05, wood))
            self.objs.append(torus('stool_rail', at + Vector((0, hy, c.rail)), 0.16, 0.0125, wood))
            cy = m['counter']['front_y']
            self.objs.append(box('counter', at + Vector((0, cy + 0.3, c.counter_h / 2)), (1.2, 0.6, c.counter_h), wood))
            self.objs[-1]['kz_front_hide'] = 1
            b = Vector(m['bowl'])
            self.objs.append(cyl('bowl', at + b - Vector((0, 0, 0.05)), at + b + Vector((0, 0, 0.03)), 0.085, cer))
            for k in (-1, 1):
                self.chop.append((cyl(f'chop{k}', Vector((0, 0, -0.05)), Vector((0, 0, 0.17)), 0.0035, wood, segs=6), k))
        elif kind == 'zabuton':
            self.objs.append(box('zabuton', at + Vector((0, m['cushion_centre_y'], c.seat / 2)), (0.6, 0.62, c.seat), cloth))
        elif kind == 'lounger':
            th = math.radians(m['back_angle_deg'])
            hgy = m['back_hinge_y']
            self.objs.append(box('lounger_seat', at + Vector((0, hgy + 0.65, c.seat / 2)), (0.75, 1.3, c.seat), cloth))
            Lb = 0.85
            ob = box('lounger_back', Vector((0, -Lb / 2, 0.04)), (0.75, Lb, 0.08), cloth)
            ob.matrix_world = Matrix.Translation(at + Vector((0, hgy, c.seat - 0.04))) @ Matrix.Rotation(-th, 4, 'X') @ ob.matrix_world
            self.objs.append(ob)
        elif kind in ('submerged ledge', 'submerged step'):
            self.objs.append(box('ledge', at + Vector((0, hy - 0.1, c.ledge / 2)), (1.0, 0.5, c.ledge), stone))
        if c.name == 'soak_rim':
            r = c.meta['rim']
            self.objs.append(box('rim', at + Vector((0, r['wall_y'] - 0.4, r['top_z'] / 2)), (1.8, 0.8, r['top_z']), stone))
        if c.water is not None:                            # water as a tinted volume up to the level
            z0 = 0.0 if c.group == 'soak' else c.water - 0.9
            self.objs.append(box('water', at + Vector((0, 0.2, (z0 + c.water) / 2)), (2.6, 2.6, c.water - z0), water))
        if c.footwear.startswith('barefoot (indoor)'):
            self.mask_geta()
        if c.name == 'float_ring':
            o = genlib.build('float_ring', lod=0, seed=1)
            o.location = at
            o['kz_prop'] = 1
            self.objs.append(o)

    def mask_geta(self):
        """render-only: hide the geta (rigid 100 % on a foot bone, not skin) with a Mask modifier"""
        o = self.fig.o
        me = o.data
        skin = {i for i, m in enumerate(me.materials) if m and 'ceramic' in m.name}
        names = {g.index: g.name for g in o.vertex_groups}
        geta = set()
        for p in me.polygons:
            if p.material_index in skin:
                continue
            for vi in p.vertices:
                gs = [(names[g.group], g.weight) for g in me.vertices[vi].groups if g.weight > 0]
                if len(gs) == 1 and gs[0][0].startswith('foot_') and gs[0][1] > 0.999:
                    geta.add(vi)
        vg = o.vertex_groups.new(name='kz_keep')
        vg.add([v.index for v in me.vertices if v.index not in geta], 1.0, 'REPLACE')
        mm = o.modifiers.new('kz_mask_geta', 'MASK')
        mm.vertex_group = 'kz_keep'
        o.modifiers.move(len(o.modifiers) - 1, 0)
        self.masked = (o, vg, mm)

    def update(self):
        if not self.chop:
            return
        arm, sk = self.fig.arm, self.fig.sk
        pb = arm.pose.bones['prop_R']
        Sp = arm.matrix_world @ pb.matrix @ arm.data.bones['prop_R'].matrix_local.inverted()
        hd0 = (sk.J['handtipR'] - sk.J['wristR']).normalized()
        g = sk.heads['prop_R']
        for o, k in self.chop:
            q = Vector((0, 0, 1)).rotation_difference(hd0).to_matrix().to_4x4()
            o.matrix_world = Sp @ Matrix.Translation(g + hd0 * 0.06 + Vector((0.006 * k, 0.012, 0))) @ q

    def remove(self):
        if getattr(self, 'masked', None):
            o, vg, mm = self.masked
            o.modifiers.remove(mm)
            o.vertex_groups.remove(vg)
        for o in self.objs + [c for c, _ in self.chop]:
            me = o.data
            bpy.data.objects.remove(o)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)


def eevee_scene(res):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 32
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.fps = FPS
    w = sc.world or bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.018, 1)
    return sc


def sheet_lights(centre, span):
    """warm lantern key + dim teal fill + rim (the sheet rig of render_lod_sheet)"""
    out = []
    for name, kind, off, energy, col, size in (('key', 'AREA', (2.2, 2.6, 3.0), 650, (1.0, 0.72, 0.42), 2.0),
                                               ('fill', 'AREA', (-2.6, 1.8, 1.6), 140, (0.35, 0.8, 0.85), 3.0),
                                               ('rim', 'AREA', (-1.0, -2.6, 2.6), 260, (1.0, 0.8, 0.6), 1.5)):
        l = bpy.data.lights.new(name, kind)
        l.energy = energy * max(1.0, span / 1.8) ** 2
        l.color = col
        l.size = size
        lo = bpy.data.objects.new(name, l)
        bpy.context.scene.collection.objects.link(lo)
        lo.location = Vector(centre) + Vector(off) * max(1.0, span / 1.8)
        lo.rotation_euler = (Vector(centre) - lo.location).to_track_quat('-Z', 'Y').to_euler()
        out.append(lo)
    return out


def floor(z=0.0, size=8.0, grid=False):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    fl = bpy.context.object
    m = bpy.data.materials.new('kz_prev_floor')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.85
    if grid:
        nt = m.node_tree
        ch = nt.nodes.new('ShaderNodeTexChecker')
        ch.inputs['Scale'].default_value = size * 2.5
        ch.inputs['Color1'].default_value = (0.11, 0.105, 0.1, 1)
        ch.inputs['Color2'].default_value = (0.075, 0.072, 0.07, 1)
        nt.links.new(ch.outputs['Color'], b.inputs['Base Color'])
    else:
        b.inputs['Base Color'].default_value = (0.09, 0.09, 0.095, 1)
    fl.data.materials.append(m)
    return fl


def world_bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        mw = oe.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            lo = Vector((min(lo[i], p[i]) for i in range(3)))
            hi = Vector((max(hi[i], p[i]) for i in range(3)))
        oe.to_mesh_clear()
    return lo, hi


def render_strip(fig, c, act, outdir):
    sc = bpy.context.scene
    fig.arm.animation_data.action = act
    props = Props(c, fig)
    N = c.N
    frames = [round(i * N / 8) for i in range(8)]
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for f in frames:
        sc.frame_set(f)
        props.update()
        a, b = world_bbox([fig.o] + [o for o, _ in props.chop])
        lo = Vector((min(lo[i], a[i]) for i in range(3)))
        hi = Vector((max(hi[i], b[i]) for i in range(3)))
    lo.z = min(lo.z, 0.0)
    ctr = (lo + hi) / 2
    ext = hi - lo
    span = max(ext.y, ext.x, ext.z)
    asp = max(0.55, min(1.6, max(ext.y, ext.x) / max(ext.z, 0.3)))
    cw = 300
    ch = int(round(cw / asp / 2) * 2)
    ch = max(220, min(520, ch))
    eevee_scene((cw, ch))
    lights = sheet_lights(ctr, span)
    cam_d = bpy.data.cameras.new('cam')
    cam_d.type = 'ORTHO'
    cam = bpy.data.objects.new('cam', cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    eh = max(ext.x, ext.y) * 1.1 + 0.08
    ev = ext.z * 1.1 + 0.08
    cam_d.ortho_scale = max(ev, eh * ch / cw) if ch >= cw else max(eh, ev * cw / ch)
    tmp = os.path.join(SCR, 'cells', c.name)
    os.makedirs(tmp, exist_ok=True)
    rows = []
    for view, loc in (('side', Vector((8, ctr.y, ctr.z))), ('front', Vector((ctr.x, 8, ctr.z)))):
        cam.location = loc
        cam.rotation_euler = (Vector((ctr.x if view == 'side' else ctr.x, ctr.y, ctr.z)) - loc).to_track_quat('-Z', 'Y').to_euler()
        for o in props.objs:
            if o.get('kz_front_hide'):
                o.hide_render = view == 'front'
        cells, caps = [], []
        for f in frames:
            sc.frame_set(f)
            props.update()
            p = os.path.join(tmp, f'{view}_{f:03d}.png')
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            cells.append(p)
            caps.append(f'f{f}  {f / FPS:.2f}s')
        rows.append(dict(label=view, cells=cells, captions=caps))
    m = c.info()
    extra = []
    if c.speed:
        extra.append(f'{c.speed} m/s in place')
    if 'seat' in m:
        extra.append(f"{m['seat']['kind']} {m['seat']['height']} m")
    if c.water is not None:
        extra.append(f'water {c.water:.2f} m')
    title = f"{c.name}  ({c.group})  {m['duration_s']} s / {c.N} f @30, loop  " + '  '.join(extra) + \
            f"   |  {fig.asset} seed {fig.seed} LOD0"
    spec = dict(out=os.path.join(outdir, f'{c.name}.jpg'), title=title, rows=rows, cell=[cw, ch])
    sp = os.path.join(tmp, 'spec.json')
    json.dump(spec, open(sp, 'w'))
    subprocess.run([VENV_PY, os.path.join(ROOT, 'tools', 'gen', 'kzanim_common.py'), 'compose', sp], check=True)
    props.remove()
    for lo_ in lights:
        bpy.data.objects.remove(lo_)
    bpy.data.objects.remove(cam)
    print('STRIP', spec['out'])


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def stage_render():
    todo = selected()
    for g in GROUPS:
        cl = [c for c in todo if c.group == g]
        if not cl:
            continue
        clear_scene()
        floor()
        asset, seed = RENDER_FIG[g]
        fig = Fig(asset, seed)
        outdir = os.path.join(RENDERS, f'figure_anim_{g}')
        os.makedirs(outdir, exist_ok=True)
        clips, _ = build_clips(fig, cl)
        for name, (c, act) in clips.items():
            render_strip(fig, c, act, outdir)


def stage_mp4():
    if ONLY and ONLY != 'walk':
        return
    clear_scene()
    sc = eevee_scene((854, 480))
    sc.eevee.taa_render_samples = 24
    floor(size=30, grid=True)
    fig = Fig('guest_figure', 1)
    clips, _ = build_clips(fig, [Walk])
    c, act = clips['walk']
    fig.arm.animation_data.action = act
    # root motion: the figure object travels +Y at kz_clip_speed, the action plays in place
    nf = 2 * FPS
    o = fig.o
    o.animation_data_create()
    o.location = (0, 0, 0)
    o.keyframe_insert('location', frame=0)
    o.location = (0, c.speed * nf / FPS, 0)
    o.keyframe_insert('location', frame=nf)
    for fc in A_fcurves_obj(o):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    # the walk action loops: NLA-free cyclic via an F-modifier on every curve
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, fig.arm.animation_data.action_slot)
    for fc in cb.fcurves:
        fc.modifiers.new('CYCLES')
    sheet_lights(Vector((0, 1.1, 0.9)), 2.4)
    cam_d = bpy.data.cameras.new('cam')
    cam_d.lens = 38
    cam = bpy.data.objects.new('cam', cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    em = bpy.data.objects.new('track', None)
    sc.collection.objects.link(em)
    em.parent = o
    em.location = (0, 0, 0.85)
    cam.location = (3.4, -1.2 + c.speed * 0.0, 1.55)
    con = cam.constraints.new('TRACK_TO')
    con.target = em
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    cam.animation_data_create()
    cam.location = (3.4, -1.6, 1.55)
    cam.keyframe_insert('location', frame=0)
    cam.location = (3.4, -1.6 + c.speed * nf / FPS, 1.55)
    cam.keyframe_insert('location', frame=nf)
    for fc in A_fcurves_obj(cam):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    sc.frame_start, sc.frame_end = 0, nf - 1
    tmp = os.path.join(SCR, 'mp4')
    os.makedirs(tmp, exist_ok=True)
    sc.render.filepath = os.path.join(tmp, 'f_')
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(animation=True)
    out = os.path.join(RENDERS, 'figure_anim_walk', 'walk.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', '0', '-i',
                    os.path.join(tmp, 'f_%04d.png'), '-vf', 'scale=-2:480', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    '-crf', '20', out], check=True)
    print('MP4', out)


def A_fcurves_obj(ob):
    from bpy_extras import anim_utils
    ad = ob.animation_data
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(cb.fcurves) if cb else []


def stage_canonical():
    todo = selected()
    for g in GROUPS:
        cl = [c for c in todo if c.group == g]
        if not cl or (ONLY and len(cl) < len([c for c in CLIPS if c.group == g]) and False):
            continue
        cl = [c for c in CLIPS if c.group == g]          # the canonical always shows the whole group
        clear_scene()
        sc = bpy.context.scene
        sc.render.engine = 'CYCLES'
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
        sc.cycles.device = 'GPU'
        sc.cycles.samples = 96
        sc.cycles.use_denoising = True
        sc.cycles.denoiser = 'OPTIX'
        sc.view_settings.view_transform = 'AgX'
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900
        sc.render.image_settings.file_format = 'PNG'
        w = bpy.data.worlds.new('w')
        sc.world = w
        w.use_nodes = True
        w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.006, 0.007, 0.009, 1)
        floor(z=0.0, size=20)
        asset, seed = RENDER_FIG[g]
        gap = 1.5 if g in ('walk', 'idle') else (2.7 if g == 'soak' else 2.0)
        xs = [(i - (len(cl) - 1) / 2) * gap for i in range(len(cl))]
        caps = []
        allobjs = []
        for x, cls in zip(xs, cl):
            fig = Fig(asset, seed)
            clips, _ = build_clips(fig, [cls])
            c, act = clips[cls.name]
            fig.arm.animation_data.action = act
            fr = dict(walk=round(c.N * 0.1), walk_slow=round(c.N * 0.1), sit_stool_eat=round(1.6 * FPS)).get(c.name, round(c.N * 0.3))
            # bake the frame into the mesh pose: keep the action but evaluate at fr via a constant frame
            fig.o.location = (-x, 0, 0)                   # camera looks from +Y/+X: lay out to -X (screen-left)
            p = Props(c, fig, at=Vector((-x, 0, 0)))
            for ob in p.objs:
                if ob.name.startswith('float_ring'):
                    pass
            fig._fr = fr
            allobjs.append((fig, p, c, fr))
            caps.append(f'{c.name} (f{fr})')
        # a single frame can only be one scene frame: give each rig its own frame offset via NLA-free time remap
        for fig, p, c, fr in allobjs:
            act = fig.arm.animation_data.action
            from bpy_extras import anim_utils
            cb = anim_utils.action_get_channelbag_for_slot(act, fig.arm.animation_data.action_slot)
            for fc in cb.fcurves:
                vals = [k.co[1] for k in fc.keyframe_points]
                v = vals[fr]
                for k in fc.keyframe_points:
                    k.co[1] = v
                fc.update()
        sc.frame_set(0)
        for fig, p, c, fr in allobjs:
            p.update()
        lo, hi = Vector((min(xs) - 0.8, -1, 0)), Vector((max(xs) + 0.8, 1.5, 1.8))
        ctr = (lo + hi) / 2
        ctr.x = -ctr.x
        span = hi.x - lo.x
        for name, off, energy, col, size in (('key', (2.5, 4.0, 3.5), 900, (1.0, 0.7, 0.42), 2.5),
                                             ('rim', (-1.5, -3.5, 3.0), 500, (1.0, 0.82, 0.62), 2.0),
                                             ('fill', (-4.0, 3.0, 1.5), 120, (0.35, 0.8, 0.85), 4.0)):
            l = bpy.data.lights.new(name, 'AREA')
            l.energy = energy * max(1.0, span / 3.0)
            l.color = col
            l.size = size * max(1.0, span / 4)
            lo_ = bpy.data.objects.new(name, l)
            sc.collection.objects.link(lo_)
            lo_.location = Vector((ctr.x + off[0] * max(1, span / 4), off[1], off[2]))
            lo_.rotation_euler = (Vector((ctr.x, 0, 0.6)) - lo_.location).to_track_quat('-Z', 'Y').to_euler()
        for i, x in enumerate(xs):
            pl = bpy.data.lights.new(f'glint{i}', 'POINT')
            pl.energy = 25
            pl.color = (1.0, 0.65, 0.35)
            pl.shadow_soft_size = 0.05
            po = bpy.data.objects.new(f'glint{i}', pl)
            sc.collection.objects.link(po)
            po.location = (-x + 0.6, 1.0, 1.9)
        cam_d = bpy.data.cameras.new('cam')
        cam_d.lens = 40
        cam = bpy.data.objects.new('cam', cam_d)
        sc.collection.objects.link(cam)
        sc.camera = cam
        dist = max(4.6, span * 1.3) * (1.25 if g in ('walk', 'idle') else 1.0)
        target = Vector((ctr.x, 0.15, dict(walk=0.95, idle=0.95, float=0.35).get(g, 0.65)))
        cam.location = target + Vector((dist * 0.45, dist * 0.89, 1.6 - target.z))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        raw = os.path.join(SCR, f'canonical_{g}.png')
        sc.render.filepath = raw
        bpy.ops.render.render(write_still=True)
        spec = dict(out=os.path.join(RENDERS, f'figure_anim_{g}', 'canonical.jpg'), render=raw,
                    title=f'figure_anim_{g}: ' + ', '.join(c.name for c in cl),
                    captions=['left to right: ' + '  |  '.join(caps), f'{asset} seed {seed}, LOD0, Cycles, 3/4 view at 1.6 m'],
                    refs=[os.path.join(ROOT, r) for r in REFS[g]])
        sp = os.path.join(SCR, f'canonical_{g}.json')
        json.dump(spec, open(sp, 'w'))
        subprocess.run([VENV_PY, os.path.join(ROOT, 'tools', 'gen', 'kzanim_common.py'), 'canonical', sp], check=True)
        print('CANONICAL', spec['out'])


if __name__ == '__main__':
    t0 = time.time()
    for st in ('bake', 'export', 'render', 'mp4', 'canonical'):
        if st in STAGES:
            ts = time.time()
            globals()['stage_' + st]()
            print(f'STAGE {st} done in {time.time() - ts:.1f}s')
    print(f'ALL DONE {time.time() - t0:.1f}s')
