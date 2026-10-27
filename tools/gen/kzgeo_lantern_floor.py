"""Lantern family kit (op01): geometry shared by gen_lantern_floor / _niche / _post / _stone.

Everything here adds faces to a genlib.MeshBuilder and tags them with a slot; nothing touches materials.
Helpers:
  open_box      box with chosen faces left out (hidden faces cost nothing)
  sq_ring       square frame ring (rails, trays, collars) as one closed solid: 32 tris instead of 4 boxes (48)
  srings        stack of shaped rings (square superellipse / hexagon / circle) with caps, optional per-vertex
                displacement and corner lift: roofs with upturned corners, rough stone blocks, shafts
  wall_hole     a wall slab with a window (square or round) through it, closed solid
  prism_xz      2D outline in the x-z plane extruded along y (LOD3 leg plinths)
  hip_roof      thin pyramidal / hip / concave lantern roof with a real eave thickness
  andon_frame   the timber box of a square andon: stiles, top/bottom rails, paper core, muntins (lod-aware)
  rough         seeded smooth noise displacement for basalt (deterministic in position -> same at every LOD)
"""
import math

import bmesh
from mathutils import Vector, noise

import kzgeo_common as C

SQ2 = math.sqrt(2.0)


# ------------------------------------------------------------------------------------------- primitives
def open_box(mb, center, size, mi, skip=()):
    """axis box; skip any of 'top', 'bottom', 'front' (+y), 'back' (-y), 'left' (-x), 'right' (+x)"""
    bm = mb.bm
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    v = {}
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                v[(ix, iy, iz)] = bm.verts.new((cx + ix * sx, cy + iy * sy, cz + iz * sz))
    quads = dict(
        top=[(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
        bottom=[(-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1)],
        front=[(-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)],
        back=[(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)],
        right=[(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)],
        left=[(-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)])
    fs = [bm.faces.new([v[k] for k in q]) for name, q in quads.items() if name not in skip]
    used = {x for f in fs for x in f.verts}
    for x in list(v.values()):
        if x not in used:
            bm.verts.remove(x)
    mb._tag(fs, mi)
    return fs


def sq_ring(mb, c, z0, z1, h_out, h_in, mi, hy_out=None, hy_in=None):
    """square (or rectangular) frame ring between z0 and z1: outer half-size h_out, inner h_in. 32 tris."""
    hy_out = h_out if hy_out is None else hy_out
    hy_in = h_in if hy_in is None else hy_in
    bm = mb.bm
    cx, cy = c[0], c[1]

    def ring(hx, hy, z):
        return [bm.verts.new((cx + sx * hx, cy + sy * hy, z)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    oa, ob, ib, ia = ring(h_out, hy_out, z0), ring(h_out, hy_out, z1), ring(h_in, hy_in, z1), ring(h_in, hy_in, z0)
    fs = C.bridge_rings(bm, oa, ob) + C.bridge_rings(bm, ob, ib) + C.bridge_rings(bm, ib, ia) + C.bridge_rings(bm, ia, oa)
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def shape_r(shape, th, p=8.0):
    """radius factor (<= ~1.0 on the mid-edge of a square) of a ring shape at angle th.
    'sq': superellipse |x|^p + |y|^p = 1 (p 2 = circle, p 8 = rounded square, p 40 = square);
    'hex': regular hexagon with its corners at 0, 60, ... deg; 'circle'."""
    if shape == 'circle':
        return 1.0
    if shape == 'hex':
        a = (th % (math.pi / 3)) - math.pi / 6
        return math.cos(math.pi / 6) / math.cos(a)
    c, s = abs(math.cos(th)), abs(math.sin(th))
    return 1.0 / max(1e-6, (c ** p + s ** p)) ** (1.0 / p)


def corner_k(shape, th, p=8.0):
    """0 at mid-edge, 1 at a corner"""
    if shape == 'circle':
        return 0.0
    r = shape_r(shape, th, p)
    rmax = shape_r(shape, 0.0 if shape == 'hex' else math.pi / 4, p)
    return max(0.0, min(1.0, (r - 1.0) / max(1e-6, rmax - 1.0))) if shape != 'hex' else \
        max(0.0, min(1.0, (r - math.cos(math.pi / 6) / 1.0) / (1.0 - math.cos(math.pi / 6))))


def srings(mb, rings, N, mi, shape='sq', p=8.0, phase=None, cap_bot=True, cap_top=True, disp=None, centre=(0, 0)):
    """Stack of shaped rings. rings = [(hx, hy, z, lift)] bottom -> top; hx == 0 makes a pole.
    'sq' rings run x = hx * fx, y = hy * fy; 'hex'/'circle' use hx as the radius (hy as y radius).
    lift raises the ring's corners (roof warabi). disp(v, ring_i, k) -> Vector offset (rough stone).
    Returns (rings_of_verts, faces)."""
    bm = mb.bm
    if phase is None:
        phase = 0.0
    cx, cy = centre
    out, allf = [], []
    for i, rg in enumerate(rings):
        hx, hy, z = rg[0], rg[1], rg[2]
        lift = rg[3] if len(rg) > 3 else 0.0
        if hx <= 1e-6:
            v = bm.verts.new((cx, cy, z))
            if disp:
                v.co += disp(v.co, i, -1)
            out.append([v])
            continue
        ring = []
        for k in range(N):
            th = phase + 2 * math.pi * k / N
            f = shape_r(shape, th, p)
            if shape == 'sq':
                x = hx * f * math.cos(th); y = hy * f * math.sin(th)
            else:
                x = hx * f * math.cos(th); y = hy * f * math.sin(th)
            zz = z + lift * corner_k(shape, th, p) ** 2
            v = bm.verts.new((cx + x, cy + y, zz))
            if disp:
                v.co += disp(v.co, i, k)
            ring.append(v)
        out.append(ring)
    for A, B in zip(out[:-1], out[1:]):
        for k in range(N):
            k2 = (k + 1) % N
            if len(A) == 1 and len(B) == 1:
                continue
            if len(A) == 1:
                q = (A[0], B[k], B[k2])
            elif len(B) == 1:
                q = (A[k], A[k2], B[0])
            else:
                q = (A[k], A[k2], B[k2], B[k])
            allf.append(bm.faces.new(q))
    if cap_bot and len(out[0]) > 1:
        allf.append(bm.faces.new(out[0][::-1]))
    if cap_top and len(out[-1]) > 1:
        allf.append(bm.faces.new(out[-1]))
    mb._tag(allf, mi)
    return out, allf


def wall_hole(mb, M, W, H, T, hole_w, hole_h, mi, N=16, hole='sq', hole_cz=0.0, disp=None, mi_tunnel=None):
    """Wall slab W x H (local x, z), T thick along local +y (front face at y = +T/2), with a hole through it.
    hole 'sq' (rounded square, p 10) or 'round'. Outer edge is a p 40 superellipse sampled at the same N
    angles, so the rings bridge. M: frame matrix (C.frame). Closed solid. ~8N tris."""
    bm = mb.bm
    loops = []
    for y in (T / 2, -T / 2):
        outer, inner = [], []
        for k in range(N):
            th = math.pi / 4 + 2 * math.pi * k / N
            fo = shape_r('sq', th, 40.0)
            fi = shape_r('sq', th, 10.0) if hole == 'sq' else 1.0
            po = Vector((W / 2 * fo * math.cos(th), y, H / 2 * fo * math.sin(th)))
            pi = Vector((hole_w / 2 * fi * math.cos(th), y, hole_cz + hole_h / 2 * fi * math.sin(th)))
            vo, vi = bm.verts.new(M @ po), bm.verts.new(M @ pi)
            if disp:
                vo.co += disp(vo.co, 0, k); vi.co += disp(vi.co, 1, k) * 0.4
            outer.append(vo); inner.append(vi)
        loops.append((outer, inner))
    (fo_, fi_), (bo_, bi_) = loops
    fs = C.bridge_rings(bm, fo_, fi_) + C.bridge_rings(bm, bi_, bo_) + C.bridge_rings(bm, bo_, fo_)
    tun = C.bridge_rings(bm, fi_, bi_)
    bmesh.ops.recalc_face_normals(bm, faces=fs + tun)
    mb._tag(fs, mi)
    mb._tag(tun, mi if mi_tunnel is None else mi_tunnel)
    return fs + tun


def prism_xz(mb, poly, y0, y1, mi):
    """2D outline [(x, z)] extruded from y0 to y1 (closed)."""
    bm = mb.bm
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    if a < 0:
        poly = poly[::-1]
    A = [bm.verts.new((x, y0, z)) for x, z in poly]
    B = [bm.verts.new((x, y1, z)) for x, z in poly]
    fs = [bm.faces.new(A), bm.faces.new(B[::-1])] + C.bridge_rings(bm, B, A)
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def hip_roof(mb, c, z0, half, thick, rise, mi, segs=4, top_half=0.0, concave=0.0, lift=0.0, N=None, simple=False):
    """Lantern roof: eave of half-size `half` (to the mid-edge), `thick` eave edge, rising `rise` to a top
    of half-size top_half (0 = point). concave > 0 sags the slope (hip-and-curve); lift raises the corners.
    segs 4 = square, 6 = hex, 8 = octagonal plan. Built with srings so the plan is a true polygon."""
    shape = 'sq' if segs == 4 else 'hex' if segs == 6 else 'circle'
    N = N or segs
    p = 40.0
    if shape == 'sq':
        ph, h0, tf = (0.0 if N > 4 else math.pi / 4), half, 1.0
    else:
        ph, h0, tf = (0.0, half / math.cos(math.pi / 6), 1.0 / math.cos(math.pi / 6)) if shape == 'hex' else (0.0, half, 1.0)
    if simple == 'min':
        rings = [(h0, h0, z0, 0.0)]
    elif simple:
        rings = [(h0, h0, z0, lift), (h0, h0, z0 + thick, lift)]
    else:
        rings = [(h0 * 0.94, h0 * 0.94, z0, lift * 0.8), (h0, h0, z0 + thick * 0.35, lift), (h0, h0, z0 + thick, lift)]
    if concave > 0:
        for t in (0.35, 0.7):
            hr = h0 + (top_half * tf - h0) * t
            zr = z0 + thick + rise * (t - concave * math.sin(math.pi * t) * 0.6)
            rings.append((hr, hr, zr, lift * (1 - t) * 0.6))
    rings.append((top_half * tf, top_half * tf, z0 + thick + rise, 0.0))
    if top_half > 0 and not simple:
        rings.append((0.0, 0.0, z0 + thick + rise, 0.0))
    return srings(mb, rings, N, mi, shape=shape, p=p, phase=ph, centre=(c[0], c[1]), cap_top=simple)


# ------------------------------------------------------------------------------------------- rough stone
def rough(seed, amp, freq=6.0, octaves=2, zscale=0.35):
    """displacement function for srings / wall_hole: smooth noise in world position, radial in XY plus a
    little Z. Deterministic in position, so every LOD of a seed has the same crags."""
    off = Vector(((seed * 17.31) % 97, (seed * 7.77) % 89, (seed * 3.13) % 83))

    def f(co, i, k):
        q = Vector(co) * freq + off
        n = 0.0; a = 1.0; fq = 1.0; norm = 0.0
        for _ in range(octaves):
            n += a * noise.noise(q * fq); norm += a; a *= 0.5; fq *= 2.1
        n /= norm
        rad = Vector((co.x, co.y, 0.0))
        if rad.length > 1e-6:
            rad.normalize()
        m = noise.noise(q * 1.7 + Vector((5.0, 1.0, 3.0)))
        return rad * (amp * n) + Vector((0, 0, amp * zscale * m))
    return f


# ------------------------------------------------------------------------------------------- andon box
def andon_frame(mb, c, z0, W, H, mats, lod, D=None, stile=0.035, rail=0.035, pattern='plain', bev=0.004,
                n_lattice=(1, 0), open_back=False, muntin_faces=(0, 1, 2, 3), top_rail=True):
    """Square andon body: 4 corner stiles, top and bottom frame rails, an emissive paper core and the
    panel muntins. W (x) x D (y) x H between z0 and z0 + H. mats = dict(wood, paper).
    pattern: 'plain' (n_lattice[0] vertical muntins per face), 'lattice' (grid n_lattice = (nv, nh)),
             'kumiko' (fine 3 x 4 grid at LOD0, 2 x 2 at LOD1).
    LOD0 bevelled stiles; LOD1 plain boxes, same parts; LOD2 stiles as open boxes + paper core;
    LOD3 paper core only (the caller keeps cap and legs). Returns the paper centre."""
    D = W if D is None else D
    wood, paper = mats['wood'], mats['paper']
    cx, cy = c
    hx, hy = W / 2, D / 2
    kz = Vector((cx, cy, z0 + H / 2))
    inset = stile * 0.45
    # paper core: a closed box set in from the stile faces
    if lod >= 3:
        open_box(mb, (cx, cy, z0 + H / 2), (W - 0.004, D - 0.004, H), paper, skip=('top', 'bottom'))
        return kz
    open_box(mb, (cx, cy, z0 + H / 2), (W - 2 * inset, D - 2 * inset, H - 0.004), paper,
             skip=('top', 'bottom') if lod >= 1 else ())
    if lod == 2:
        for sx in (-1, 1):
            for sy in (-1, 1):
                open_box(mb, (cx + sx * (hx - stile / 2), cy + sy * (hy - stile / 2), z0 + H / 2), (stile, stile, H), wood,
                         skip=('top', 'bottom'))
        return kz
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = (cx + sx * (hx - stile / 2), cy + sy * (hy - stile / 2), z0 + H / 2)
            if lod == 0 and bev > 0:
                C.board(mb, p, (stile, stile, H), wood, bevel=bev)
            elif lod == 0:
                mb.box(p, (stile, stile, H), wood)
            else:
                open_box(mb, p, (stile, stile, H), wood, skip=('top', 'bottom'))   # ends hidden by the rails
    sq_ring(mb, c, z0, z0 + rail, hx + 0.003, hx - stile * 0.85, wood, hy + 0.003, hy - stile * 0.85)
    if top_rail:
        sq_ring(mb, c, z0 + H - rail, z0 + H, hx + 0.003, hx - stile * 0.85, wood, hy + 0.003, hy - stile * 0.85)
    # muntins: thin bars 2 mm proud of the paper on each face
    mw = max(0.008, stile * 0.32)
    if pattern == 'kumiko':
        nv, nh = (3, 4) if lod == 0 else (2, 2)
    elif pattern == 'lattice':
        nv, nh = n_lattice
    else:
        nv, nh = n_lattice[0], 0
    zin0, zin1 = z0 + rail, z0 + H - rail
    if nh:
        for j in range(nh):
            z = zin0 + (zin1 - zin0) * (j + 1) / (nh + 1)
            # one ring per horizontal muntin covers all four faces (32 tris instead of 4 bars)
            sq_ring(mb, c, z - mw / 2, z + mw / 2, hx - inset + mw * 0.6, hx - inset - 0.002, wood,
                    hy - inset + mw * 0.6, hy - inset - 0.002)
    for face in range(4):
        if (open_back and face == 2) or face not in muntin_faces:
            continue
        for j in range(nv):
            t = (j + 1) / (nv + 1)
            if face in (0, 2):     # front / back (+y / -y)
                x = cx - (hx - stile) + 2 * (hx - stile) * t
                y = cy + (1 if face == 0 else -1) * (hy - inset + mw * 0.1)
                (_box if lod == 0 else _obox)(mb, (x, y, (zin0 + zin1) / 2), (mw, mw, zin1 - zin0), wood)
            else:
                y = cy - (hy - stile) + 2 * (hy - stile) * t
                x = cx + (1 if face == 1 else -1) * (hx - inset + mw * 0.1)
                (_box if lod == 0 else _obox)(mb, (x, y, (zin0 + zin1) / 2), (mw, mw, zin1 - zin0), wood)
    return kz


def stud(mb, c, n, r, h, mi):
    """4-sided pyramid rivet / stud head (4 tris, no base) at c, pointing along the unit normal n"""
    bm = mb.bm
    n = Vector(n).normalized()
    t = n.cross(Vector((0, 0, 1)))
    if t.length < 1e-6:
        t = Vector((1, 0, 0))
    t.normalize(); b = n.cross(t)
    c = Vector(c)
    base = [bm.verts.new(c + (t * math.cos(a) + b * math.sin(a)) * r) for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
    tip = bm.verts.new(c + n * h)
    fs = [bm.faces.new((base[k], base[(k + 1) % 4], tip)) for k in range(4)]
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def _box(mb, c, size, mi):
    return mb.box(c, size, mi)


def _obox(mb, c, size, mi):
    return open_box(mb, c, size, mi, skip=('top', 'bottom'))


def poly_ring(mb, c, z0, z1, r_out, r_in, segs, mi, phase=0.0):
    """regular-polygon frame ring (hex trays, collars): corner radii r_out / r_in, closed solid, 8*segs tris"""
    bm = mb.bm
    cx, cy = c[0], c[1]

    def ring(r, z):
        return [bm.verts.new((cx + r * math.cos(phase + 2 * math.pi * k / segs), cy + r * math.sin(phase + 2 * math.pi * k / segs), z))
                for k in range(segs)]
    oa, ob, ib, ia = ring(r_out, z0), ring(r_out, z1), ring(r_in, z1), ring(r_in, z0)
    fs = C.bridge_rings(bm, oa, ob) + C.bridge_rings(bm, ob, ib) + C.bridge_rings(bm, ib, ia) + C.bridge_rings(bm, ia, oa)
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    mb._tag(fs, mi)
    return fs


def lights_props(o, centres, color_k, watts, flicker_slots, params, amount=0.1):
    C.set_json_props(o, kz_lights=[C.light_entry(p, color_k=color_k, watts=watts) for p in centres],
                     kz_flicker=list(flicker_slots),
                     kz_anim={'type': 'shader_flicker', 'slots': list(flicker_slots), 'amount': amount, 'hz': [2.7, 6.1]},
                     kz_params=params)
    return o
