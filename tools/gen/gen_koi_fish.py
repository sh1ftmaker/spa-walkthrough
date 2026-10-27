"""Koi (black and gold), op06 rewrite of the first Haiku build (that one read as a dart: pointed nose, tiny
floating spot ellipsoids, rigid triangular fins).

Identifying features kept at every LOD: a long tapered koi body with a rounded blunt head, a patterned back
(black / gold / red patches on white, or the reverse), and a flowing forked tail fin.

Concept: refs/gen/sheet-mod-water.png panel 4 "Koi pond" (black-and-gold, white-and-red and orange koi seen
from above and through the glass section), lookbook 33 (b1 plan: 'koi in the wider pools').  Earlier
measurement (refs/gen/sheet-vs-grotto-garden.png #4, label W 0.15 x L 0.6 x H 0.12; the bar disagrees, label
wins): body 0.78 L + tail 0.22 L, widest at 0.3 L from the nose, peduncle 0.22 of the max width, body width
0.1 m (0.21 of the body length in plan), body depth 0.085 m, dorsal fin to 0.115 m, pectorals span 0.15 m.

Parameters: length 0.4-0.8 m (default 0.6, seeded 0.52-0.62), pattern 'mixed' | 'kohaku' | 'black' | 'gold'
  (mixed = white with black and gold patches, kohaku = white with red, black = karasu with gold head/back
  patches, gold = ogon with a few black scales), fin (0.8-1.3, fin and tail length).
Seeds: the pattern cycles (1 mixed, 2 kohaku, 3 black, 4 gold); each seed also changes the body depth
  (0.9-1.12), the patch layout (count 3-6, position, size), the tail bend and length, the pectoral spread.

Materials (proposed library id NEW:koi, glossy wet skin with patch masks; until then):
  skin white `ceramic` variant 'white'; red `ceramic` tint (1.4, 0.22, 0.07); black `ceramic` tint
  (0.045, 0.045, 0.05) (glossy black, not lacquer: same coat as the white); gold `gold_leaf`;
  fins `linen` tinted per pattern (white / smoke / amber); eyes `lacquer_black`.
Fins and tail are single-sided membranes (render double-sided); the body is a closed solid.
Animation: rigid swim paths (runtime) + vertex wiggle: vertex groups 'sway' (0 at the head .. 1 at the tail tip,
  ^1.5) and 'tail' (tail fin + rear 15 % of the body).  kz_anim records axis z, 12 / 25 deg.
Lighting: probe (moving).
LOD: LOD0 20 stations x 14 sides, curved tail 4 x 4, dorsal, pectorals, pelvics, eyes.  LOD1 12 x 10, tail 3 x 2,
  dorsal, pectorals.  LOD2 6 x 6, tail, dorsal, pectorals as one quad each.  LOD3 4 x 4 body, tail, dorsal.
  Patch materials come from one per-seed field, so the pattern is the same at every LOD (coarser).
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'koi_fish'
FEATURES = ['long tapered body with a blunt rounded head', 'black / gold (or red) patterned back', 'flowing forked tail fin']
PATTERNS = ['mixed', 'kohaku', 'black', 'gold']
FIN_TINT = {'mixed': (1.0, 0.95, 0.88), 'kohaku': (1.0, 0.95, 0.9), 'black': (0.16, 0.16, 0.17), 'gold': (1.0, 0.78, 0.42)}
LODS = {0: dict(N=20, M=14, tr=4, tc=4, eyes=True, pelvic=True, fin_r=(3, 2)),
        1: dict(N=12, M=10, tr=3, tc=2, eyes=False, pelvic=False, fin_r=(2, 1)),
        2: dict(N=6, M=6, tr=1, tc=2, eyes=False, pelvic=False, fin_r=(1, 1)),
        3: dict(N=4, M=4, tr=1, tc=1, eyes=False, pelvic=False, fin_r=None)}


def _g(u):
    """half-width factor along the body (0 nose .. 1 peduncle): elliptical blunt head, widest at 0.3"""
    if u < 0.3:
        return math.sqrt(max(0.0, 1 - (1 - u / 0.3) ** 2)) * 0.85 + 0.15 * (u / 0.3)
    return 0.22 + 0.78 * math.cos(math.pi / 2 * (u - 0.3) / 0.7) ** 1.25


def _grid(mb, P, rows, cols, mi):
    """single-sided membrane from a parametric surface P(s, t) -> Vector"""
    bm = mb.bm
    V = [[bm.verts.new(P(i / rows, j / cols)) for j in range(cols + 1)] for i in range(rows + 1)]
    fs = []
    for i in range(rows):
        for j in range(cols):
            fs.append(bm.faces.new((V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j])))
    mb._tag(fs, mi)
    return fs


def build(lod, seed, L=None, length=None, pattern=None, fin=None):
    g = C.rng(seed, ASSET)
    L_seed = 0.6 if seed == 1 else g.uniform(0.52, 0.62)
    L = max(0.4, min(0.8, length or L or L_seed))
    pattern = pattern or C.cycle(seed, PATTERNS)
    depth = g.uniform(0.9, 1.12) if seed != 1 else 1.0
    fin = fin or g.uniform(0.9, 1.2)
    bend = g.uniform(-1, 1)
    spread = g.uniform(0.85, 1.1)
    k = L / 0.6
    Lb = 0.78 * L
    yh = L / 2
    pos = lambda u: yh - u * Lb
    A = 0.05 * k
    UP, DN = 0.047 * k * depth, 0.038 * k * depth
    zc = DN
    Ls = LODS[lod]

    mb = genlib.MeshBuilder()
    white = mb.slot('ceramic', variant='white')
    red = mb.slot('ceramic', tint=(1.4, 0.22, 0.07))
    black = mb.slot('ceramic', tint=(0.045, 0.045, 0.05))
    gold = mb.slot('gold_leaf')
    finm = mb.slot('linen', tint=FIN_TINT[pattern])
    eye = mb.slot('lacquer_black')
    base, spots = {'mixed': (white, [black, gold, black, gold, black, gold]), 'kohaku': (white, [red] * 6),
                   'black': (black, [gold] * 6), 'gold': (gold, [black] * 6)}[pattern]

    # pattern field: blobs in (u, theta) on the back and flanks, from the seed only (same at every LOD)
    pr = C.rng(seed, 'patches')
    n_b = {'mixed': pr.randint(4, 6), 'kohaku': pr.randint(3, 4), 'black': pr.randint(2, 3), 'gold': pr.randint(2, 3)}[pattern]
    blobs = []
    for b in range(n_b):
        u = pr.uniform(0.05, 0.75) if pattern != 'black' or b else pr.uniform(0.02, 0.15)   # karasu: gold on the head
        th = math.pi / 2 + pr.uniform(-0.9, 0.9)
        su, st = pr.uniform(0.11, 0.2) * (0.6 if pattern == 'gold' else 1.0), pr.uniform(0.7, 1.2)
        blobs.append((u, th, su, st, spots[b % len(spots)]))
    off = Vector((pr.uniform(0, 50), pr.uniform(0, 50), 0))

    def patch(u, th):
        best, mi = 0.0, None
        for (bu, bt, su, st, m) in blobs:
            dth = math.atan2(math.sin(th - bt), math.cos(th - bt))
            v = math.exp(-((u - bu) / su) ** 2 - (dth / st) ** 2) + 0.25 * noise.noise(Vector((u * 9, th * 2, 0)) + off)
            if v > best:
                best, mi = v, m
        return mi if best > 0.45 else base

    # ---------------- body: nose pole, N stations, closed peduncle cap
    bm = mb.bm
    N, M = Ls['N'], Ls['M']
    us = [0.0] + [((i / (N - 1)) ** 1.15) for i in range(1, N)]
    if lod < 2:
        us = sorted(set(us + [0.015, 0.04]))
    rings = []
    for u in us:
        if u == 0.0:
            rings.append([bm.verts.new((0.0, pos(0.0) + 0.004 * k, zc + 0.004 * k))])
            continue
        gg = _g(u)
        ring = []
        for j in range(M):
            th = 2 * math.pi * j / M - math.pi / 2
            s, c = math.sin(th), math.cos(th)
            ring.append(bm.verts.new((A * gg * c, pos(u), zc + (UP if s > 0 else DN) * gg * s * (1 - 0.15 * u * (s > 0)))))
        rings.append(ring)
    faces = []
    for ia in range(len(rings) - 1):
        R0, R1 = rings[ia], rings[ia + 1]
        um = (us[ia] + us[ia + 1]) / 2
        for j in range(M):
            j2 = (j + 1) % M
            th = 2 * math.pi * (j + 0.5) / M - math.pi / 2
            mi = patch(um, th)
            f = bm.faces.new((R0[0], R1[j], R1[j2]) if len(R0) == 1 else (R0[j], R0[j2], R1[j2], R1[j]))
            f.material_index = mi
            faces.append(f)
    f = bm.faces.new(rings[-1][::-1]); f.material_index = patch(1.0, math.pi / 2)

    # ---------------- tail: flowing forked fan, bent sideways
    yb = pos(1.0)
    Lt = 0.22 * L * fin
    hz = 0.055 * k * fin

    def tail(s, t):              # s 0 base .. 1 tip, t 0 bottom lobe .. 1 top lobe
        z_half = 0.012 * k + (hz - 0.012 * k) * s ** 0.8
        fork = 0.35 * Lt * (1 - abs(2 * t - 1)) * s ** 1.2          # notch in the middle of the trailing edge
        y = yb + 0.004 * k - (Lt * s * (0.85 + 0.15 * abs(2 * t - 1))) + fork
        z = zc + (2 * t - 1) * z_half + (0.004 * k if t > 0.5 else 0.0)
        x = bend * 0.035 * k * s ** 2
        return Vector((x, y, max(0.002, z)))
    tail_faces = _grid(mb, tail, Ls['tr'], Ls['tc'], finm)

    # ---------------- dorsal fin along the back (u 0.32 .. 0.68), trailing edge longer
    def top_z(u):
        return zc + UP * _g(u) * (1 - 0.15 * u)
    if lod < 3:
        dr, dc = (Ls['fin_r'] or (1, 1))

        def dorsal(s, t):        # s 0 root .. 1 edge, t along
            u = 0.32 + 0.36 * t
            hgt = (0.026 + 0.012 * t) * k * fin * math.sin(math.pi * min(1.0, 0.15 + 0.85 * t)) ** 0.5
            return Vector((0, pos(u) - 0.02 * k * s * t, top_z(u) - 0.002 + hgt * s))
        _grid(mb, dorsal, dr, max(2, dc * 2), finm)
    else:
        u0, u1 = 0.35, 0.65
        q = [bm.verts.new(v) for v in (Vector((0, pos(u0), top_z(u0))), Vector((0, pos(u1), top_z(u1))),
                                        Vector((0, pos(0.6) - 0.01, top_z(0.6) + 0.03 * k)))]
        f = bm.faces.new(q); f.material_index = finm

    # ---------------- pectoral paddles (big, rounded, angled down-out) and pelvics
    if Ls['fin_r']:
        pr_, pc_ = Ls['fin_r']
        for sg in (-1, 1):
            u0 = 0.2
            root = Vector((sg * A * _g(u0) * 0.8, pos(u0), zc - DN * 0.45))

            def pect(s, t, root=root, sg=sg):
                span = 0.068 * k * spread * fin ** 0.5 - A * _g(u0) * 0.8
                chord = 0.05 * k * fin * (1 - 0.35 * abs(2 * t - 1) * s)
                return root + Vector((sg * span * s * (0.9 + 0.1 * math.sin(math.pi * t)), -chord * t - 0.012 * k * s, -0.018 * k * s))
            _grid(mb, pect, pr_, pc_, finm)
            if Ls['pelvic']:
                r2 = Vector((sg * A * _g(0.5) * 0.5, pos(0.5), zc - DN * 0.8))
                _grid(mb, lambda s, t, r2=r2, sg=sg: r2 + Vector((sg * 0.022 * k * s, -0.03 * k * t - 0.008 * k * s, -0.008 * k * s)), 1, 2, finm)

    # ---------------- eyes
    if Ls['eyes']:
        for sg in (-1, 1):
            u = 0.07
            mb.sphere((sg * A * _g(u) * 0.92, pos(u), zc + UP * _g(u) * 0.25), 0.0055 * k, eye, segs=8, rings=4)

    for v in bm.verts:
        if v.co.z < 0:
            v.co.z = 0.0
    _, dy, _ = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=50)
    yh_n, ytip = yh + dy, -L / 2 + dy
    sway = o.vertex_groups.new(name='sway')
    tailg = o.vertex_groups.new(name='tail')
    for v in o.data.vertices:
        w = min(1.0, max(0.0, (yh_n - v.co.y) / max(1e-6, yh_n - ytip)))
        sway.add([v.index], round(w ** 1.5, 4), 'REPLACE')
        if v.co.y < yb + dy + 0.15 * Lb:
            tailg.add([v.index], 1.0, 'REPLACE')
    C.set_json_props(o, kz_anim={'sway': {'group': 'sway', 'axis': 'z', 'max_deg': 12},
                                 'tail': {'group': 'tail', 'axis': 'z', 'max_deg': 25},
                                 'swim': {'rigid': True, 'note': 'path in runtime'}},
                     kz_params=dict(L=round(L, 3), pattern=pattern, depth=round(depth, 3), fin=round(fin, 3)),
                     kz_material_pending={'koi': 'ceramic / gold_leaf patch slots'})
    return o
