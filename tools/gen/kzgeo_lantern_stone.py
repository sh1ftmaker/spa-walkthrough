"""Stone toro parts for gen_lantern_stone (op01). Rough basalt blocks are srings stacks (kzgeo_lantern_floor)
with a seeded noise displacement that depends only on world position, so every LOD of a seed has the
same crags. Rings use phase pi/4 and N in (4, 8, 12, 24): the 45 deg corners are always vertices.
"""
import math

import bmesh
from mathutils import Vector, noise

import kzgeo_common as C
import kzgeo_lantern_floor as L

PH = math.pi / 4


def block(mb, rings, N, mi, seed, amp, p=6.0, freq=9.0, lod=0, cap_bot=False):
    """rough stone block: rings [(hx, hy, z, lift)]; amp shrinks with the LOD so the outline stays put"""
    disp = L.rough(seed, amp * C.lod_pick(lod, 1.0, 0.8, 0.5, 0.0), freq, octaves=3) if amp > 0 else None
    return L.srings(mb, rings, N, mi, shape='sq', p=p, phase=PH, disp=disp, cap_bot=cap_bot)


def firebox(mb, z0, W, Hf, t, win, win_side, mats, lod, seed, lattice=(2, 1)):
    """four stone walls with windows round a lit washi core. win / win_side: 'sq' | 'round'.
    Returns the light centre."""
    stone, paper = mats['stone'], mats['paper']
    zc = z0 + Hf / 2
    kz = Vector((0, 0, zc))
    if lod >= 2:
        L.open_box(mb, (0, 0, zc), (W, W, Hf), stone, skip=('top', 'bottom'))
        bm = mb.bm
        fs = []
        ww = W * 0.55
        for f in (range(4) if lod == 2 else (0, 2)):
            a = f * math.pi / 2
            n = Vector((math.sin(a), math.cos(a), 0)); tt = Vector((n.y, -n.x, 0))
            c = Vector((0, 0, zc)) + n * (W / 2 + 0.004)
            q = [bm.verts.new(c + tt * sx * ww / 2 + Vector((0, 0, sz * ww / 2))) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            fs.append(bm.faces.new(q if f % 2 == 0 else q[::-1]))
        mb._tag(fs, paper)
        return kz
    N = 16 if lod == 0 else 8
    disp = L.rough(seed + 11, 0.006 if lod == 0 else 0.0, 12.0)
    hw = W * 0.56
    for f in range(4):
        a = f * math.pi / 2
        fwd = Vector((math.sin(a), math.cos(a), 0))
        front = f % 2 == 0
        wl = W if front else W - 2 * t
        c = fwd * (W / 2 - t / 2) + Vector((0, 0, zc))
        M = C.frame(c, fwd)
        shape = win if front else win_side
        L.wall_hole(mb, M, wl, Hf, t, hw if shape == 'sq' else hw * 0.92, hw if shape == 'sq' else hw * 0.92, stone,
                    N=N, hole='sq' if shape == 'sq' else 'round', disp=disp)
    # lit core
    ci = W - 2 * t + 0.01
    mb.box((0, 0, zc), (ci, ci, Hf - 0.01), paper)
    # stone lattice in the square windows (sheet: 3 x 3 panes)
    if lod == 0:
        bw = 0.016
        for f in (0, 2):
            y = (1 if f == 0 else -1) * (W / 2 - t * 0.45)
            if win != 'sq':
                continue
            for i in range(lattice[0]):
                x = -hw / 2 + hw * (i + 1) / (lattice[0] + 1)
                mb.box((x, y, zc), (bw, t * 0.5, hw), stone)
            for j in range(lattice[1]):
                z = zc - hw / 2 + hw * (j + 1) / (lattice[1] + 1)
                mb.box((0, y, z), (hw, t * 0.5, bw), stone)
    return kz


def hoju(mb, z0, r, h, mi, lod, neck_r):
    """neck disc + onion jewel with a point (lathe)"""
    segs = C.lod_pick(lod, 12, 8, 6, 4)
    nh = h * 0.22
    if lod <= 2:
        C.lathe(mb, [(neck_r, z0), (neck_r * 1.05, z0 + nh * 0.5), (neck_r * 0.8, z0 + nh)], segs, mi, phase=PH)
    zb = z0 + (nh if lod <= 2 else 0.0)
    hb = h - nh if lod <= 2 else h
    if lod == 0:
        prof = [(r * 0.45, zb), (r * 0.85, zb + hb * 0.18), (r, zb + hb * 0.4), (r * 0.9, zb + hb * 0.6),
                (r * 0.55, zb + hb * 0.8), (r * 0.2, zb + hb * 0.93), (0, zb + hb)]
    elif lod == 1:
        prof = [(r * 0.5, zb), (r, zb + hb * 0.4), (r * 0.55, zb + hb * 0.8), (0, zb + hb)]
    else:
        prof = [(r * 0.6, zb), (r, zb + hb * 0.4), (0, zb + hb)]
    C.lathe(mb, prof, segs, mi, phase=PH)


def moss_paint(mb, stone_slots, moss_slot, seed, amount):
    """paint top-facing stone faces with moss where a seeded noise field is high. amount 0..1.
    Faces only: no extra geometry, so the patches stay identical in layout across LODs."""
    if amount <= 0:
        return 0
    bm = mb.bm
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    off = Vector(((seed * 3.7) % 31, (seed * 9.1) % 29, 4.0))
    thr = 0.55 - 0.9 * amount
    n = 0
    for f in bm.faces:
        if f.material_index not in stone_slots:
            continue
        if f.normal.z < 0.45:
            continue
        c = f.calc_center_median()
        v = noise.noise(c * 3.2 + off) + 0.5 * noise.noise(c * 7.0 + off)
        if v > thr + (0.25 if f.normal.z < 0.7 else 0.0):
            f.material_index = moss_slot
            n += 1
    return n
