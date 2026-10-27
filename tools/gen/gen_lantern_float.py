"""Floating paper lantern (lantern_float): the lazy-river lanterns of lookbook 12 and the river release.

TARGETS (measured before coding)
  No sheet. Lookbook 12-lava-tube-lazy-river.jpg: near lanterns (bottom-left square, bottom-right hex) are
  ~230 px wide where a bather's head is ~100 px (0.22 m) at the same depth -> 0.45-0.5 m wide; mid-river ones
  scale the same. Square lanterns are a little taller than wide (h/w ~1.05-1.15), hex ones about as tall as
  wide (h/w ~0.95-1.05). A thin near-black frame runs round the top and the bottom, slim corner posts, the
  float is a dark board just proud of the paper, and the waterline sits on the board. Each face carries a
  dark ink crest (circle + mountain), ~0.55 of the face width.
  Built: w 0.30-0.50 (default 0.40-0.46 by seed), h/w 0.95-1.15, float board 0.03-0.04 m, top frame 0.02 m.

FEATURES kept at every LOD: square or hexagonal glowing washi body, dark top frame, dark float board.
  The crest is kept to LOD1 (LOD2 on the square only: at the 4.6 m switch it is ~6 px).

PARAMETERS
  w       0.30-0.50 m across the flats
  shape   'square' | 'hex'
  crest   True | False
  mode    'drifting' | 'moored' (a short tether cord trailing from one corner + no drift in kz_anim)
  style   'square' | 'hex' (seeds cycle; seed 3 is a moored square, seed 4 a moored hex)

SEEDS change shape: plan (square / hex), width 0.38-0.48, h/w, float board thickness and overhang,
  top-frame depth, crest on alternate faces vs all faces, moored tether.

MATERIALS (slots by part): paper = washi_backlit (walls, double-walled shell so the inside glows from above),
  frame = hinoki stained (float board, posts, top frame), ink = lacquer_black (crest; NOT in the row: proposed).
ANIMATION: kz_anim rigid bob (+ drift when released) and shader flicker on paper.
  LIGHT: kz_lights point at the body centre, 2300 K 8 W (proxy). Water: kz_waterline (m above the base).
BUDGET 300 / 120 / 40 / 20.
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_lantern_floor as L

ASSET = 'lantern_float'
FEATURES = ['square or hex washi body', 'dark top frame', 'dark float board', 'crest print']
STYLES = ['square', 'hex', 'square', 'hex']
MODES = ['drifting', 'drifting', 'moored', 'moored']


def _poly(n, R, z, phase):
    return [Vector((R * math.cos(phase + 2 * math.pi * k / n), R * math.sin(phase + 2 * math.pi * k / n), z)) for k in range(n)]


def prism(mb, n, R, z0, z1, mi, phase, top=True, bottom=True, sides=None):
    """regular n-gon prism (R = corner radius); sides = which side faces to keep (None = all)"""
    bm = mb.bm
    A = [bm.verts.new(p) for p in _poly(n, R, z0, phase)]
    B = [bm.verts.new(p) for p in _poly(n, R, z1, phase)]
    fs = []
    for k in range(n):
        if sides is None or k in sides:
            fs.append(bm.faces.new((A[k], A[(k + 1) % n], B[(k + 1) % n], B[k])))
    if top:
        fs.append(bm.faces.new(B))
    if bottom:
        fs.append(bm.faces.new(A[::-1]))
    for v in A + B:
        if not v.link_faces:
            bm.verts.remove(v)
    fs = [f for f in fs if f.is_valid]
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def crest(mb, c, n, sv, r, mi, segs):
    """flat ink crest facing n at c: a ring (annulus) and a mountain, 1 mm proud. sv = face horizontal axis."""
    bm = mb.bm
    up = Vector((0, 0, 1))
    c = Vector(c) + n * 0.0012
    fs = []
    if segs:
        o = [bm.verts.new(c + (sv * math.cos(2 * math.pi * k / segs) + up * math.sin(2 * math.pi * k / segs)) * r) for k in range(segs)]
        i = [bm.verts.new(c + (sv * math.cos(2 * math.pi * k / segs) + up * math.sin(2 * math.pi * k / segs)) * r * 0.87) for k in range(segs)]
        for k in range(segs):
            k2 = (k + 1) % segs
            fs.append(bm.faces.new((o[k], o[k2], i[k2], i[k])))
    mt = [(-0.6, -0.32), (-0.16, 0.26), (0.0, 0.42), (0.16, 0.26), (0.6, -0.32)] if segs >= 8 else [(-0.6, -0.32), (0.0, 0.42), (0.6, -0.32)]
    vs = [bm.verts.new(c + sv * (x * r) + up * (y * r)) for x, y in mt]
    fs.append(bm.faces.new(vs))
    for f in fs:
        if f.normal.dot(n) < 0:
            f.normal_flip()
    mb._tag(fs, mi)
    return fs


def build(lod, seed, w=None, shape=None, crest_on=None, mode=None, style=None):
    style = style or shape or C.cycle(seed, STYLES)
    shape = style
    mode = mode or C.cycle(seed, MODES)
    g = C.rng(seed, 'dims')
    W = w or g.uniform(0.38, 0.48)
    W = max(0.30, min(0.50, W))
    hw_ratio = g.uniform(1.05, 1.15) if shape == 'square' else g.uniform(0.95, 1.05)
    gf = C.rng(seed, 'float')
    bt = gf.uniform(0.03, 0.04)
    over = gf.uniform(0.012, 0.022)
    ft = gf.uniform(0.016, 0.026)
    all_faces = C.pick(seed, 'crest_faces', [True, True, False])
    crest_on = True if crest_on is None else crest_on

    n = 4 if shape == 'square' else 6
    ph = math.pi / 4 if n == 4 else 0.0
    apo = (W - 2 * over) / 2                    # paper half-width across the flats
    R = apo / math.cos(math.pi / n)             # corner radius
    Rb = (apo + over) / math.cos(math.pi / n)
    H = W * hw_ratio - bt
    face_ang = [ph + math.pi / n + 2 * math.pi * k / n for k in range(n)]   # outward normal angles of the side faces

    mb = genlib.MeshBuilder()
    paper = mb.slot('washi_backlit')
    frame = mb.slot('hinoki', variant='stained')
    ink = mb.slot('lacquer_black', roughness_offset=0.35)

    z0 = bt
    z1 = bt + H
    kz = Vector((0, 0, z0 + H * 0.45))
    if lod <= 1:
        # float board
        prism(mb, n, Rb, 0.0, bt, frame, ph)
        # paper: double-walled shell (outer + inner + top lip) so the inside glows when seen from above
        L.poly_ring(mb, (0, 0), z0, z1 - (0.002 if lod == 0 else 0), R, R - 0.004, n, paper, phase=ph)
        # top frame
        if lod == 0:
            L.poly_ring(mb, (0, 0), z1 - ft, z1 + 0.004, R + 0.006 / math.cos(math.pi / n), R - 0.012, n, frame, phase=ph)
            for k in range(n):        # corner posts
                a = ph + 2 * math.pi * k / n
                p = Vector((math.cos(a), math.sin(a), 0)) * (R + 0.002)
                C.stick(mb, (p.x, p.y, z0), (p.x, p.y, z1 - ft), 0.008, 0.008, frame, segs=4)
        else:
            prism(mb, n, R + 0.006 / math.cos(math.pi / n), z1 - ft, z1 + 0.004, frame, ph, top=False, bottom=False)
        if crest_on:
            for k, a in enumerate(face_ang):
                if lod == 1 and n == 6 and k % 2:
                    continue
                if lod == 0 and not all_faces and k % 2:
                    continue
                nv = Vector((math.cos(a), math.sin(a), 0))
                sv = Vector((-math.sin(a), math.cos(a), 0))
                side = 2 * apo * math.tan(math.pi / n)
                crest(mb, nv * apo + Vector((0, 0, z0 + H * 0.47)), nv, sv, side * 0.27, ink, C.lod_pick(lod, 12 if n == 4 else 8, 6))
        if mode == 'moored' and lod == 0:
            a = ph
            p0 = Vector((math.cos(a), math.sin(a), 0)) * Rb * 0.98 + Vector((0, 0, bt * 0.5))
            d = Vector((math.cos(a), math.sin(a), 0))
            # tether: a short cord off the float corner, dipping to the waterline (the mooring line is runtime)
            pts = [p0 - d * 0.01, p0 + d * 0.025 + Vector((0, 0, -0.004)), p0 + d * 0.045 + Vector((0, 0, -bt * 0.45))]
            C.tube(mb, pts, [0.005] * len(pts), mb.slot('rope'), sides=4, cap1=True)
    elif lod == 2:
        prism(mb, n, Rb, 0.0, bt, frame, ph, bottom=False)
        prism(mb, n, R, z0, z1 - ft, paper, ph, top=False, bottom=False)
        prism(mb, n, R + 0.006 / math.cos(math.pi / n), z1 - ft, z1 + 0.004, frame, ph, top=n == 4, bottom=False)
        if crest_on and n == 4:
            for a in face_ang[:2]:
                nv = Vector((math.cos(a), math.sin(a), 0)); sv = Vector((-math.sin(a), math.cos(a), 0))
                crest(mb, nv * R * math.cos(math.pi / n) + Vector((0, 0, z0 + H * 0.47)), nv, sv, apo * 0.5, ink, 0)
    else:
        # LOD3: one prism, float band dark, body paper, dark top
        keep = None if n == 4 else [0, 1, 2, 3, 4, 5]
        prism(mb, n, Rb, 0.0, bt, frame, ph, top=False, bottom=False, sides=[0, 1, 2] if n == 6 else None)
        prism(mb, n, R, z0, z1, paper, ph, top=n == 4, bottom=False, sides=keep)
    C.centre_base(mb, centre_x=False, centre_y=False)     # symmetric body on the axis; the tether stays off-axis
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=[C.light_entry(kz, color_k=2300, watts=8)],
                     kz_flicker=[paper],
                     kz_waterline=round(bt * 0.6, 4),
                     kz_anim={'type': 'rigid_bob', 'bob_amp': 0.012, 'bob_hz': 0.35, 'roll_deg': 3.0,
                              'drift_mps': 0.0 if mode == 'moored' else 0.15, 'yaw_dps': 0.0 if mode == 'moored' else 4.0,
                              'flicker': {'slots': [paper], 'amount': 0.12, 'hz': [2.9, 6.3]}},
                     kz_params=dict(style=style, w=round(W, 3), h=round(W * hw_ratio, 3), crest=crest_on, mode=mode,
                                    crest_all_faces=all_faces))
    return o
