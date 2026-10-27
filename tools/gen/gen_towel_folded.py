"""Folded and rolled towels (towel_folded).

Identifying features kept at every LOD: neat stack of folded white towels; rolled towel on a lounger / tray;
towel draped over a tub rim.

Construction (round 5)
  * towel slab: a rounded rectangle (corner radius 40-50 mm) lofted over rings. Full thickness (44 mm) holds out
    to a shoulder 7 mm in from the edge, then rolls over to an edge band 35 % of the half thickness, so there is
    no knife edge. The centre puffs 16-18 mm. A fold crease, 9 mm deep and about 40 mm wide, sits at a seeded
    position across the width; on alternate seeds a second 7 mm crease sits about a third of the width away.
    Stack pitch is 62 mm, so towels rest on each other. LOD0 uses 2 corner segments, LOD1 and LOD2 1 segment,
    LOD3 is boxes.
  * stack: 4 or 5 towels (seeded), yaw +-0.10 rad, offset +-0.02 m, tilt +-2 deg, on a hinoki walnut tray
    that spans the stack footprint. LOD0 has a 3-slat tray, LOD1-3 a single tray box. LOD2 is three rounded
    tiers, LOD3 four slab boxes, so both still read as a stack.
  * roll: rolled towels, about 0.14 m diameter (radius 0.065-0.075 m), laid along X on the tray. The ends are
    tucked: two concentric ridges each side, and a soft fold seam at mid-length.
  * drape: a towel laid over a tub rim. The rim is a parameter (rim_r, rim_h; default the oke_bucket rim,
    r 0.2 m at h 0.30 m). The cloth is 0.30 m wide along X, passes over the rim top with a sag into the opening,
    and drops 0.12-0.15 m down the front (+Y) and about 0.04 m at the back. The generator does not model the
    tub. Its local frame keeps the rim centred on the origin with the rim top at rim_h.
Materials: terry (library, cream) for the cloth; hinoki variant walnut for the tray and rim.
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 0.40 x 0.30 x 0.30 m):
  style  stack | roll | drape   (default stack)
  count  stack 4-5 towels, roll 1-3 rolls (default seeded)
  size   towel width scale, 0.90-0.94 (default seeded)
  rim_r  drape rim radius (default 0.2 m)
  rim_h  drape rim height (default 0.30 m)
Seeds change towel count, puff, corner radius, crease position and count, offsets, yaw, tilt, roll radius,
and drape sag and drop.
"""
import math
import bmesh
from mathutils import Matrix, Vector
import genlib
import kzgeo_towel_folded as K

ASSET = 'towel_folded'
FEATURES = ['neat stack of folded white towels', 'rolled towel on a lounger', 'towel draped on a tub rim']
CORNER_M = {0: 2, 1: 1, 2: 1, 3: 1}  # arc segments per corner of the rounded outline
PITCH = 0.062                        # stack pitch per towel
TOWEL_T = 0.044                      # flat thickness of a towel before the puff
EDGE_W = 0.007                       # width of the rolled edge, measured in from the outline
GAP = 0.006


def _strip(mb, rings, mi):
    """connect consecutive rings (lists of verts, or single-vertex poles)."""
    bm = mb.bm
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        n = max(len(A), len(B))
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(n):
            if len(A) == 1:
                cand = (A[0], B[k], B[(k + 1) % n])
            elif len(B) == 1:
                cand = (A[k], A[(k + 1) % n], B[0])
            else:
                cand = (A[k], A[(k + 1) % n], B[(k + 1) % n], B[k])
            try:
                faces.append(bm.faces.new(cand))
            except ValueError:
                pass
    mb._tag(faces, mi)
    return faces


def _rounded_rect(m, W, D, rc):
    """outline of a rounded rectangle, m arc segments per corner, counter-clockwise"""
    rc = min(rc, W / 2 - 1e-4, D / 2 - 1e-4)
    corners = [((W / 2 - rc), (D / 2 - rc), 0.0), ((-W / 2 + rc), (D / 2 - rc), math.pi / 2),
               ((-W / 2 + rc), (-D / 2 + rc), math.pi), ((W / 2 - rc), (-D / 2 + rc), 1.5 * math.pi)]
    pts = []
    for cx, cy, a0 in corners:
        for k in range(m + 1):
            a = a0 + (math.pi / 2) * k / m
            pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    return pts


def pillow(mb, cx, cy, z0, W, D, mi, lod, rnd, bulge, creases, rc, yaw=0.0, tilt=0.0):
    """A towel slab on z0 (bottom). Full thickness to a shoulder, a rolled edge, a centre puff, fold creases."""
    T = TOWEL_T
    outline = _rounded_rect(CORNER_M[lod], W, D, rc)
    c_, s_ = math.cos(yaw), math.sin(yaw)
    outline = [(x * c_ - y * s_, x * s_ + y * c_) for x, y in outline]
    tan_t = math.tan(tilt)
    sag = rnd.uniform(0.008, 0.012)
    cz = z0 + T / 2
    s_sh = 1.0 - EDGE_W / (min(W, D) / 2)           # shoulder: where the rolled edge starts

    def half(s):
        """half thickness at ring scale s: full to the shoulder, then rolls to 35 % at the outline"""
        if s <= s_sh:
            return 1.0
        u = min(1.0, (s - s_sh) / (1.0 - s_sh))
        return 0.35 + 0.65 * math.cos(math.pi / 2 * u)

    def top_z(x, y, s):
        dz = T / 2 * half(s) + bulge * (1.0 - min(s, 1.0) ** 2)
        dz -= sag * (1.0 - s) * s
        for xc, depth, width in creases:
            dz -= depth * math.exp(-((x - xc) / width) ** 2) * (1.0 - s * s)
        return dz

    def ring(s, top):
        vs = []
        for (x, y) in outline:
            px, py = x * s, y * s
            pz = top_z(px, py, s) if top else -(T / 2 * half(s))
            pz += px * tan_t
            vs.append(mb.bm.verts.new((cx + px, cy + py, cz + pz)))
        return vs

    centre_top = mb.bm.verts.new((cx, cy, cz + top_z(0.0, 0.0, 0.0)))
    centre_bot = mb.bm.verts.new((cx, cy, cz - T / 2))
    interior = []                           # no interior rings: the centre pole carries the puff
    chain = [[centre_top]]
    for s in interior:
        chain.append(ring(s, True))
    chain.append(ring(s_sh, True))          # shoulder, top
    chain.append(ring(1.0, True))           # outer edge, top
    chain.append(ring(1.0, False))          # outer edge, bottom
    chain.append(ring(s_sh, False))         # shoulder, bottom
    for s in reversed(interior):
        chain.append(ring(s, False))
    chain.append([centre_bot])
    _strip(mb, chain, mi)


def tray(mb, W, D, wood, lod):
    """3-slat tray spanning the stack footprint (6 mm gaps) at LOD0; one box from LOD1 up"""
    if lod >= 1:
        mb.box((0, 0, 0.01), (W + 0.02, D, 0.02), wood)
        return
    sw = (D - 2 * GAP) / 3
    for k in (-1, 0, 1):
        mb.box((0, k * (sw + GAP), 0.01), (W + 0.02, sw, 0.02), wood)


def _centre(mb):
    vs = mb.bm.verts
    xs = [v.co.x for v in vs]; ys = [v.co.y for v in vs]; zs = [v.co.z for v in vs]
    dx = -(max(xs) + min(xs)) / 2; dy = -(max(ys) + min(ys)) / 2; dz = -min(zs)
    for v in vs:
        v.co.x += dx; v.co.y += dy; v.co.z += dz


def _roll(mb, rad, L, x, cloth, lod):
    """one roll along X: a lathe with tucked ends (concentric ridges) and a soft mid seam"""
    segs = {0: 16, 1: 10, 2: 8, 3: 6}[lod]
    end_lo = [(rad * 0.9, 0.0), (rad * 0.95, 0.004), (rad * 0.8, 0.007), (rad * 0.92, 0.010), (rad * 0.6, 0.012)]
    body = [(rad, 0.012), (rad, L - 0.012)]
    end_hi = [(rad * 0.6, L - 0.012), (rad * 0.92, L - 0.010), (rad * 0.8, L - 0.007), (rad * 0.95, L - 0.004),
              (rad * 0.9, L)]
    prof = [(0.0, 0.0)] + end_lo + body + end_hi + [(0.0, L)]
    if lod >= 2:
        prof = [(0.0, 0.0), (rad * 0.9, 0.0), (rad, 0.012), (rad, L - 0.012), (rad * 0.9, L), (0.0, L)]
    verts, _ = K.revolve(mb, prof, segs, cloth)
    M = Matrix.Translation(Vector((x, 0.0, 0.02 + rad))) @ Matrix.Rotation(math.radians(90), 4, 'Y') \
        @ Matrix.Translation(Vector((0.0, 0.0, -L / 2)))
    bmesh.ops.transform(mb.bm, matrix=M, verts=verts)


def _drape(mb, cloth, s, g, rim_r, rim_h):
    """cloth over a rim centred on the origin, rim top at rim_h, front (+Y) drop 0.12-0.15, back about 0.04"""
    R = rim_r
    front = g.uniform(0.12, 0.15)
    back = g.uniform(0.035, 0.045)
    half_w = 0.15 * s                       # the sheet is 0.30 m wide, along X
    sag_mid = 0.025 + 0.01 * g.random()     # sag into the opening
    off = R + 0.02
    prof = [(off, rim_h - front)]                      # front bottom
    prof.append((off, rim_h - 0.006))                  # front, up to the rim
    prof.append((R + 0.006, rim_h + 0.002))            # over the rim lip
    n_flap = 6
    for k in range(1, n_flap):
        t = k / n_flap
        y = (R - 0.004) * (1 - 2 * t)                  # from +Y to -Y across the opening
        z = rim_h + 0.002 - sag_mid * (1 - (y / (R - 0.004)) ** 2)
        prof.append((y, z))
    prof.append((-(R + 0.006), rim_h + 0.002))
    prof.append((-off, rim_h - 0.006))
    prof.append((-off, rim_h - back))                  # back bottom
    nu, nv = 10, len(prof) - 1
    grid = []
    for i in range(nu + 1):
        x = -half_w + 2 * half_w * i / nu
        row = []
        for (y, z) in prof:
            row.append(mb.bm.verts.new((x, y, z)))
        grid.append(row)
    faces = []
    for i in range(nu):
        for j in range(nv):
            try:
                faces.append(mb.bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j])))
            except ValueError:
                pass
    mb._tag(faces, cloth)


def build(lod, seed, style=None, count=None, size=None, rim_r=0.2, rim_h=0.30):
    g = genlib.rng(seed, ASSET)
    style = style or 'stack'
    s = size or g.uniform(0.90, 0.94)
    W, D = 0.40 * s, 0.30 * s
    mb = genlib.MeshBuilder()
    cloth = mb.slot('terry', variant='cream')
    wood = mb.slot('hinoki', variant='walnut', wear=0.1)
    two_creases = g.random() < 0.5          # alternate seeds get a second crease

    if style == 'stack':
        n = count or g.randint(4, 5)
        tray_top = 0.02
        tray(mb, W, D, wood, lod)
        rc = g.uniform(0.040, 0.050)
        if lod == 3:
            for k in range(4):
                mb.box((0, 0, tray_top + TOWEL_T / 2 + k * PITCH), (W * 0.97, D * 0.97, TOWEL_T), cloth)
        else:
            tiers = {0: n, 1: 3, 2: 2}[lod]
            per_z = []
            z = tray_top
            for k in range(tiers):
                per_z.append(z)
                z += PITCH
            for k in range(tiers):
                tw = W * g.uniform(0.94, 1.0)
                off = (g.uniform(-0.02, 0.02), g.uniform(-0.02, 0.02))
                yaw = g.uniform(-0.10, 0.10)
                tilt = math.radians(g.uniform(-2, 2))
                c1 = g.uniform(-0.35, 0.35) * W
                creases = [(c1, 0.009, 0.02)]
                if two_creases:
                    creases.append((c1 + (W / 3) * (1 if c1 < 0 else -1), 0.007, 0.02))
                pillow(mb, off[0], off[1], per_z[k], tw, D * g.uniform(0.96, 1.0), cloth, lod, g,
                       bulge=g.uniform(0.016, 0.018), creases=creases, rc=rc, yaw=yaw, tilt=tilt)
    elif style == 'roll':
        n = count or g.randint(1, 3)
        rad = g.uniform(0.065, 0.075) * s
        tray(mb, W, D, wood, lod)
        for k in range(n):
            x = (k - (n - 1) / 2) * (rad * 2.1)
            L = W * 0.95
            _roll(mb, rad * g.uniform(0.97, 1.03), L, x, cloth, lod)
    else:  # drape over a rim (rim is not modelled; the local frame keeps the rim centred on the origin)
        _drape(mb, cloth, s, g, rim_r, rim_h)
        o = mb.to_object(ASSET)
        o['kz_rim_r'] = rim_r
        o['kz_rim_h'] = rim_h
        return genlib.finish(o)
    _centre(mb)
    o = mb.to_object(ASSET)
    return genlib.finish(o)
