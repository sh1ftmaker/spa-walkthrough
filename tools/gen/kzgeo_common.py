"""kzgeo_common: tested geometry helpers for the recipes in tools/gen/GUIDE.md.

Every helper adds faces to a genlib.MeshBuilder bmesh (`mb`) and tags them with a material slot index
(`mi` from `mb.slot(...)`). Nothing here touches materials, UVs or objects except the small `*_props`
helpers at the end. Units are metres, +Y is the front of an asset, z = 0 is the ground.

Proven code, copied or adapted from the generators that passed review:
  kzgeo_oke_bucket (lathe, grooved staves, stick), kzgeo_bridge_arched (frame, sweep, lantern head),
  gen_chozubachi / kzgeo_wall_trickle (tube, hull rocks), kzgeo_stream_channel (crag rock),
  gen_torii_basalt (bevelled box with the _mark_old pattern, rounded rock), gen_stepping_stone r7
  (smooth-noise outline, closed polar cobble), gen_towel_folded r5 (pillow with no knife edge),
  gen_noren (pleated cloth with a belly), kzgeo_kakehi_spout (rope turns, band, knot), gen_chochin
  (twisted cord, robust CJK glyph fill), gen_pine_niwaki (foliage pad with needle cards).

Test: blender -b -P .scratch/guide/test_recipes.py  (builds one of each, checks closedness, renders
.scratch/guide/recipes.jpg).
"""
import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.geometry import interpolate_bezier, tessellate_polygon

import genlib

Z = Vector((0, 0, 1))
FONT_KANJI = '/usr/share/fonts/noto-cjk/NotoSerifCJK-Black.ttc'
FONT_SANS_JP = '/usr/share/fonts/noto-cjk/NotoSansCJK-Black.ttc'
FONT_LATIN = '/usr/share/fonts/noto/NotoSerif-Medium.ttf'


# =============================================================================================== seeds
def rng(seed, salt):
    """One independent random stream per part. Always salt by the part name, never share one stream
    between parts: an extra draw in one part would otherwise reshuffle every part after it."""
    return genlib.rng(seed, salt)


def pick(seed, salt, options):
    """Deterministic per-seed choice that does not depend on how many draws other code made."""
    return options[genlib.rng(seed, salt).randrange(len(options))]


def cycle(seed, options):
    """Seeds 1, 2, 3 ... walk through the options in order (seed 1 -> options[0]). Use it for the style
    so the three sheet seeds always show three different styles."""
    return options[(seed - 1) % len(options)]


def lod_pick(lod, *values):
    """lod_pick(lod, a, b, c, d) -> the value for this LOD (the last one repeats)."""
    return values[min(lod, len(values) - 1)]


# =============================================================================================== frames
def frame(origin, fwd, up=Z):
    """4x4 matrix: local +Y = fwd, +Z = re-orthogonalised up, +X = fwd x up. Profiles are (x, z)."""
    f = Vector(fwd).normalized()
    x = f.cross(Vector(up))
    if x.length < 1e-6:
        x = f.cross(Vector((1, 0, 0)))
    x.normalize()
    u = x.cross(f).normalized()
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = x[i], f[i], u[i], origin[i]
    return M


def ring_verts(bm, M, radius, n, rot=0.0, ell=1.0):
    """n verts on a circle in the local x-z plane of frame M (so the ring is normal to local +Y)."""
    return [bm.verts.new(M @ Vector((radius * math.cos(rot + 2 * math.pi * k / n) * ell, 0,
                                     radius * math.sin(rot + 2 * math.pi * k / n)))) for k in range(n)]


def bridge_rings(bm, A, B, skip=None):
    """quad strip between two rings of equal length"""
    fs = []
    n = len(A)
    for k in range(n):
        if skip and k in skip:
            continue
        fs.append(bm.faces.new((A[k], A[(k + 1) % n], B[(k + 1) % n], B[k])))
    return fs


def _faces_of(vs):
    return list({f for v in vs for f in v.link_faces})


# =============================================================================================== 1. boards and slabs
def board(mb, center, size, mi, bevel=0.006, segs=1, rot=(0, 0, 0)):
    """Box with bevelled (segs=1: chamfered, segs>=2: rounded) edges. Every face, flat and bevel alike,
    gets slot `mi` (found through an int layer, because bmesh.ops.bevel clears BMElem.tag).
    The bevel is clamped to 45 % of the thinnest dimension so thin boards never collapse."""
    bm = mb.bm
    lay = mb._mark_old()
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    bmesh.ops.scale(bm, vec=size, verts=vs)
    M = Matrix.Translation(center) @ (Matrix.Rotation(rot[2], 4, 'Z') @ Matrix.Rotation(rot[1], 4, 'Y')
                                      @ Matrix.Rotation(rot[0], 4, 'X'))
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    b = min(bevel, 0.45 * min(size))
    if b > 1e-5:
        edges = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges + vs, offset=b, segments=segs, affect='EDGES', profile=0.5,
                        clamp_overlap=True)
    faces = mb._new_faces(lay)
    mb._tag(faces, mi)
    return faces


def rounded_rect(W, D, rc, m=3):
    """counter-clockwise outline of a W x D rectangle with corner radius rc (m arc segments per corner)"""
    rc = max(1e-4, min(rc, W / 2 - 1e-4, D / 2 - 1e-4))
    corners = [((W / 2 - rc), (D / 2 - rc), 0.0), ((-W / 2 + rc), (D / 2 - rc), math.pi / 2),
               ((-W / 2 + rc), (-D / 2 + rc), math.pi), ((W / 2 - rc), (-D / 2 + rc), 1.5 * math.pi)]
    pts = []
    for cx, cy, a0 in corners:
        for k in range(m + 1):
            a = a0 + (math.pi / 2) * k / m
            pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    return pts


def slab(mb, center, W, D, T, mi, rc=0.02, m=3):
    """Rounded-corner slab with real thickness T (a closed prism). Corner radius rc in plan."""
    cx, cy, cz = center
    poly = [(cx + x, cy + y) for x, y in rounded_rect(W, D, rc, m)]
    return mb.poly_prism(poly, cz - T / 2, cz + T / 2, mi)


def chamfered_bar(mb, c, size, mi, ch=0.01, axis='z'):
    """Beam of size (sx, sy, sz) with its four long edges chamfered (octagonal section) along `axis`."""
    sx, sy, sz = size
    cx, cy, cz = c
    bm = mb.bm

    def pts(a, b):
        return [(-a / 2 + ch, -b / 2), (a / 2 - ch, -b / 2), (a / 2, -b / 2 + ch), (a / 2, b / 2 - ch),
                (a / 2 - ch, b / 2), (-a / 2 + ch, b / 2), (-a / 2, b / 2 - ch), (-a / 2, -b / 2 + ch)]
    if axis == 'z':
        A = [bm.verts.new((cx + px, cy + py, cz - sz / 2)) for px, py in pts(sx, sy)]
        B = [bm.verts.new((cx + px, cy + py, cz + sz / 2)) for px, py in pts(sx, sy)]
    elif axis == 'x':
        A = [bm.verts.new((cx - sx / 2, cy + px, cz + py)) for px, py in pts(sy, sz)]
        B = [bm.verts.new((cx + sx / 2, cy + px, cz + py)) for px, py in pts(sy, sz)]
    else:
        A = [bm.verts.new((cx + px, cy - sy / 2, cz + py)) for px, py in pts(sx, sz)]
        B = [bm.verts.new((cx + px, cy + sy / 2, cz + py)) for px, py in pts(sx, sz)]
    faces = [bm.faces.new(A[::-1]), bm.faces.new(B)] + bridge_rings(bm, A, B)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


# =============================================================================================== 2. lathe
def lathe(mb, prof, segs, mi, base=(0, 0, 0), phase=0.0, closed=True):
    """Surface of revolution about local Z at `base`. prof = [(r, z)] from bottom to top; r == 0 is a
    pole. closed=True caps any end ring whose r > 0 (a solid); closed=False leaves an open band (hoop,
    bucket wall). Returns (verts, faces)."""
    bm = mb.bm
    base = Vector(base)
    rings, allv = [], []
    for r, z in prof:
        if r <= 1e-6:
            v = bm.verts.new(base + Vector((0, 0, z))); rings.append([v]); allv.append(v)
        else:
            vs = [bm.verts.new(base + Vector((r * math.cos(phase + 2 * math.pi * k / segs),
                                              r * math.sin(phase + 2 * math.pi * k / segs), z))) for k in range(segs)]
            rings.append(vs); allv += vs
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(segs):
            k2 = (k + 1) % segs
            if len(A) == 1:
                cand = (A[0], B[k], B[k2])
            elif len(B) == 1:
                cand = (A[k], A[k2], B[0])
            else:
                cand = (A[k], A[k2], B[k2], B[k])
            try:
                faces.append(bm.faces.new(cand))
            except ValueError:
                pass
    if closed:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                try:
                    faces.append(bm.faces.new(ring[::-1] if ring is rings[0] else ring))
                except ValueError:
                    pass
    mb._tag(faces, mi)
    return allv, faces


def lathe_grooved(mb, prof, staves, groove, mi, base=(0, 0, 0), phase=0.0, closed=False):
    """Like lathe() with 2*staves verts per ring: the odd verts sit `groove` metres inside the even ones,
    so a bucket wall reads as staves with V-joints (oke_bucket: 30 staves, 1.5 mm groove)."""
    bm = mb.bm
    base = Vector(base)
    n = 2 * staves
    rings, allv = [], []
    for r, z in prof:
        if r <= 1e-6:
            v = bm.verts.new(base + Vector((0, 0, z))); rings.append([v]); allv.append(v)
        else:
            vs = []
            for k in range(n):
                rr = r - groove if k % 2 else r
                a = phase + 2 * math.pi * k / n
                vs.append(bm.verts.new(base + Vector((rr * math.cos(a), rr * math.sin(a), z))))
            rings.append(vs); allv += vs
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(n):
            k2 = (k + 1) % n
            if len(A) == 1:
                cand = (A[0], B[k], B[k2])
            elif len(B) == 1:
                cand = (A[k], A[k2], B[0])
            else:
                cand = (A[k], A[k2], B[k2], B[k])
            try:
                faces.append(bm.faces.new(cand))
            except ValueError:
                pass
    if closed:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                faces.append(bm.faces.new(ring[::-1] if ring is rings[0] else ring))
    mb._tag(faces, mi)
    return allv, faces


def stick(mb, a, b, r1, r2, mi, segs=8):
    """Tapered closed cylinder from point a to point b (legs, handles, rods)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    res = bmesh.ops.create_cone(mb.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r1, radius2=r2,
                                depth=d.length)
    vs = res['verts']
    q = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    bmesh.ops.transform(mb.bm, matrix=Matrix.Translation((a + b) / 2) @ q, verts=vs)
    faces = _faces_of(vs)
    mb._tag(faces, mi)
    return faces


# =============================================================================================== 3. sweeps and tubes
def sweep(mb, pts, prof, mi, up=Z, caps=True, closed_prof=True):
    """Sweep a 2D profile [(x, z)] (x = sideways, z = up) along the polyline `pts`. Joints are mitred
    with the profile scaled so its width stays constant. Returns faces."""
    bm = mb.bm
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        M = frame(p, t, up)
        sc = 1.0
        if 0 < i < n - 1:
            a = (pts[i + 1] - pts[i]).normalized().angle((pts[i] - pts[i - 1]).normalized(), 0.0)
            sc = 1.0 / max(0.5, math.cos(a / 2))
        rings.append([bm.verts.new(M @ Vector((x, 0, z * sc))) for x, z in prof])
    faces = []
    m = len(prof)
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(m if closed_prof else m - 1):
            k2 = (k + 1) % m
            faces.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    if caps and closed_prof:
        faces.append(bm.faces.new(rings[0][::-1]))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


def tube(mb, pts, radii, mi, sides=8, cap0=False, cap1=False, mod=None):
    """Round tube along a polyline with parallel-transport frames (no twist kinks): bamboo culms, rope
    cords, ladle handles, water strands. radii per point (a float, or (ru, rv) for an elliptical
    section). mod(i, k, theta) -> radius factor lets you twist or dent the ring. Returns (rings, faces)."""
    bm = mb.bm
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    u = tans[0].cross(up).normalized()
    rings = []
    for i in range(n):
        if i:
            u = (u - tans[i] * u.dot(tans[i])).normalized()
        v = tans[i].cross(u)
        ring = []
        for k in range(sides):
            th = 2 * math.pi * k / sides
            rr = radii[i]
            if isinstance(rr, tuple):
                off = u * math.cos(th) * rr[0] + v * math.sin(th) * rr[1]
            else:
                off = (u * math.cos(th) + v * math.sin(th)) * rr * (mod(i, k, th) if mod else 1.0)
            ring.append(bm.verts.new(pts[i] + off))
        rings.append(ring)
    faces = []
    for i in range(n - 1):
        faces += bridge_rings(bm, rings[i], rings[i + 1])
    if cap0:
        faces.append(bm.faces.new(rings[0][::-1]))
    if cap1:
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return rings, faces


# =============================================================================================== 4. boulders
def hull_rock(mb, c, size, mi, r, npts=10, ground=None, rot=0.0, flat_top=None, rmin=0.74):
    """Faceted boulder: random points on an ellipsoid shell -> convex hull. Crisp planar facets, 2*npts-4
    tris. size = half-extents (radii) in x, y, z around centre c. ground = z floor (points clamped, the flat base face removed); flat_top = z ceiling.
    Use for rubble, cobbles, broken basalt chunks and anything the concept shows as angular."""
    bm = mb.bm
    pts = []
    for _ in range(npts):
        v = Vector((r.gauss(0, 1), r.gauss(0, 1), r.gauss(0, 1))).normalized() * r.uniform(rmin, 1.0)
        v = Vector((v.x * size[0], v.y * size[1], v.z * size[2]))
        x = v.x * math.cos(rot) - v.y * math.sin(rot)
        y = v.x * math.sin(rot) + v.y * math.cos(rot)
        p = Vector((c[0] + x, c[1] + y, c[2] + v.z))
        if ground is not None:
            p.z = max(p.z, ground)
        if flat_top is not None:
            p.z = min(p.z, flat_top)
        pts.append(bm.verts.new(p))
    res = bmesh.ops.convex_hull(bm, input=pts)
    dead = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid})
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='VERTS')
    faces = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace) and g.is_valid]
    if ground is not None:
        dead = [f for f in faces if f.normal.z < -0.95 and all(v.co.z < ground + 0.002 for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    mb._tag(faces, mi)
    return faces


def crag_rock(mb, M, rx, ry, z0, ztop, mi, r, nside=7, bands=3, tilt=0.04, crag=0.12, top_inset=0.74, bottom=False):
    """Rounded, craggy, flat-topped boulder (the lookbook 04 bank masses): irregular polygon footprint,
    bulging belly, rounded shoulder, slightly tilted lumpy flat top. Per-angle radial factors are shared
    up the rings so the sides break into vertical facets. M = frame at the rock centre (its z is ignored:
    z0 / ztop are absolute local heights). bottom=False leaves the base open (it sits in the ground).
    Use for overlapping bank rocks, plinth boulders and stacked footings; mix 2-3 sizes, overlap 30-40 %."""
    bm = mb.bm
    H = max(0.03, ztop - z0)
    off = Vector((r.uniform(0, 99), r.uniform(0, 99), r.uniform(0, 99)))
    angs = [2 * math.pi * (i + r.uniform(-0.28, 0.28)) / nside for i in range(nside)]
    fac = [r.uniform(0.82, 1.12) for _ in range(nside)]
    ringdef = {3: [(0.0, 0.90), (0.48, 1.0), (0.84, 0.93), (1.0, top_inset)],
               2: [(0.0, 0.94), (0.62, 1.0), (1.0, top_inset + 0.04)],
               1: [(0.0, 1.0), (1.0, top_inset + 0.08)]}[bands]
    tx, ty = r.uniform(-tilt, tilt), r.uniform(-tilt, tilt)
    rings = []
    for hf, rs in ringdef:
        ring = []
        for i, a in enumerate(angs):
            ca, sa = math.cos(a), math.sin(a)
            p0 = Vector((ca * rx, sa * ry, 0))
            nv = noise.noise(Vector((ca * 1.7, sa * 1.7, hf * 2.0)) + off)
            rad = rs * fac[i] * (1.0 + crag * nv)
            x, y = ca * rx * rad, sa * ry * rad
            if hf >= 1.0:
                z = ztop + tx * x / max(rx, 1e-3) * H + ty * y / max(ry, 1e-3) * H + 0.012 * noise.noise(p0 * 5 + off)
            elif hf <= 0.0:
                z = z0
            else:
                z = z0 + H * hf + 0.06 * H * noise.noise(p0 * 3 + off * 1.3)
            ring.append(bm.verts.new(M @ Vector((x, y, z))))
        rings.append(ring)
    faces = []
    for A, B in zip(rings[:-1], rings[1:]):
        faces += bridge_rings(bm, A, B)
    faces.append(bm.faces.new(rings[-1]))
    if bottom:
        faces.append(bm.faces.new(rings[0][::-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


def rounded_rock(mb, center, size, mi, r, cuts=2, round_r=0.18, amp=0.03, freq=2.2, batter=0.0, rot_z=0.0, clamp_z=None):
    """Closed rounded boulder: a subdivided cube mapped onto a rounded box, battered (narrower at the top),
    then displaced along its normal by fractal noise. Pillow-smooth when amp is small; for the concept's
    'chunky fractured basalt' use hull_rock or crag_rock instead (reviewers called pure rounded rocks
    'pillows', 'sandbags' and 'dumplings')."""
    bm = mb.bm
    lay = mb._mark_old()
    res = bmesh.ops.create_cube(bm, size=2.0)
    if cuts > 0:
        edges = list({e for v in res['verts'] for e in v.link_edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    faces = mb._new_faces(lay)
    vs = list({v for f in faces for v in f.verts})
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    rr = min(round_r, hx * 0.9, hy * 0.9, hz * 0.9)
    R = Matrix.Rotation(rot_z, 3, 'Z')
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    for v in vs:
        p = Vector((v.co.x * hx, v.co.y * hy, v.co.z * hz))
        inner = Vector((max(-hx + rr, min(hx - rr, p.x)), max(-hy + rr, min(hy - rr, p.y)), max(-hz + rr, min(hz - rr, p.z))))
        dvec = p - inner
        n = dvec.normalized() if dvec.length > 1e-6 else Vector((p.x / hx, p.y / hy, p.z / hz)).normalized()
        p = inner + n * rr if cuts > 0 else p
        zf = (p.z + hz) / (2 * hz)
        p.x *= 1 - batter * zf
        p.y *= 1 - batter * zf
        p = R @ p + Vector(center)
        if amp > 0:
            p = p + (R @ n) * amp * noise.fractal(p * freq + off, 0.6, 2.0, 3)
        if clamp_z is not None:
            p.z = max(clamp_z, p.z)
        v.co = p
    mb._tag(faces, mi)
    return faces


# =============================================================================================== 5. irregular stone outline + cobble
def stone_outline(r, R, aspect=1.0, harmonics=((2, 0.085), (3, 0.08), (4, 0.06), (5, 0.04), (7, 0.028), (9, 0.016)),
                  bites=1, bite_depth=(0.04, 0.08), bite_width=(0.28, 0.5), rot=None):
    """Smooth lumpy plan outline: returns f(theta) -> (x, y). Radius = R x (1 + sum of low harmonics with
    seeded phases) x gaussian bites x an aspect ellipse. Harmonics 2-9 give lobes, never facets; the
    per-vertex random jitter the stepping stone used in r2-r6 gave 'straight runs' and 'hex wedges'."""
    harm = [(k, r.uniform(0.0, 2 * math.pi), a * r.uniform(0.6, 1.3)) for k, a in harmonics]
    bite = [(r.uniform(0, 2 * math.pi), r.uniform(*bite_width), r.uniform(*bite_depth)) for _ in range(bites)]
    sx, sy = math.sqrt(aspect), 1 / math.sqrt(aspect)
    rot = r.uniform(0, math.pi) if rot is None else rot
    c, s = math.cos(rot), math.sin(rot)

    def f(th):
        k = 1.0 + sum(a * math.sin(n * th + ph) for n, ph, a in harm)
        for bc, bw, bd in bite:
            dd = math.atan2(math.sin(th - bc), math.cos(th - bc))
            k -= bd * math.exp(-(dd / bw) ** 2)
        x, y = R * k * math.cos(th) * sx, R * k * math.sin(th) * sy
        return x * c - y * s, x * s + y * c
    return f


def cobble(mb, outline, N, t, mi_side, mi_top, rings=((0.86, 0.0), (0.96, 0.2), (1.0, 0.45), (0.985, 0.7), (0.95, 0.9)),
           shoulder=(0.9, 0.975), top_scale=0.78, top_fn=None, side_noise=0.0, r=None, mi_shoulder=None,
           centre=(0.0, 0.0, 0.0)):
    """Closed polar-grid solid: a flat-topped stone with a lumpy outline and a convex side profile that runs
    straight into the top (no ledge). `outline(theta)` from stone_outline. rings = (radial scale, z
    fraction) bottom -> top, monotone and convex; shoulder = one more (scale, zf) that rounds into the top;
    then a top ring at `top_scale` and a centre pole. top_fn(x, y) -> z offset for dish / tilt.
    side_noise (m) displaces the side rings with 3D noise (needs r). Materials: sides mi_side, shoulder
    band mi_shoulder (default mi_top), top mi_top. Tris = N * (2 * nrings + 2). centre = base centre."""
    bm = mb.bm
    O = Vector(centre)
    off = Vector((r.uniform(0, 50), r.uniform(0, 50), r.uniform(0, 50))) if r else Vector((0, 0, 0))
    specs = list(rings) + [shoulder, (top_scale, 1.0)]
    rows = []
    for ri, (sc, zf) in enumerate(specs):
        row = []
        for i in range(N):
            th = 2 * math.pi * i / N
            x, y = outline(th)
            z = zf * t
            if side_noise and ri < len(rings) and r is not None:
                p = Vector((x, y, z)) * 5.0 + off
                d = side_noise * (noise.noise(p) + 0.5 * noise.noise(p * 2.3 + Vector((3, 1, 2)))) * (1.3 - 0.8 * zf)
                L = math.hypot(x, y) or 1.0
                sc_i = sc + d / L
            else:
                sc_i = sc
            x, y = x * sc_i, y * sc_i
            if zf >= 0.97 and top_fn:
                z += top_fn(x, y) * min(1.0, (zf - 0.9) / 0.1)
            row.append(bm.verts.new(O + Vector((x, y, z))))
        rows.append(row)
    cb = bm.verts.new(O)
    ct = bm.verts.new(O + Vector((0, 0, t + (top_fn(0, 0) if top_fn else 0.0))))
    faces = []
    for k in range(N):
        f = bm.faces.new((cb, rows[0][(k + 1) % N], rows[0][k])); f.material_index = mi_side; faces.append(f)
    n_side = len(rings) - 1
    for j in range(len(rows) - 1):
        mi = mi_side if j < n_side else (mi_shoulder if (mi_shoulder is not None and j == n_side) else mi_top)
        for k in range(N):
            f = bm.faces.new((rows[j][k], rows[j][(k + 1) % N], rows[j + 1][(k + 1) % N], rows[j + 1][k]))
            f.material_index = mi; faces.append(f)
    for k in range(N):
        f = bm.faces.new((ct, rows[-1][k], rows[-1][(k + 1) % N])); f.material_index = mi_top; faces.append(f)
    return faces


# =============================================================================================== 6. cloth panel with pleats and a belly
def cloth_panel(mb, w, h, mi, r, cols=12, rows=5, pleat0=0.0075, pleat1=0.018, belly=0.022, y0=0.0,
                band_h=0.07, mi_band=None, hem=0.004, x0=0.0, sway_layer=True):
    """Single-sided hanging cloth facing +Y (render double-sided): top edge at z = h, hem at z = 0,
    centred on x0. Columns sit on pleat ridges and valleys (alternating +-, seeded 0.6-1.0 depth) whose
    amplitude grows from pleat0 under the head band to pleat1 at the hem; a forward belly over the lower
    third; a turned hem that stands `hem` proud. The top band_h gets mi_band (same cloth, a hair darker).
    Writes a float vert layer '_sway' (0 at the top, 1 at the hem) for the runtime. Returns faces.
    Noren r2/r3: pleats below ~1 cm 'do not read at all'; use 1.5 cm at the band and 3-4 cm peak-to-peak
    at the hem, 4-6 ripples per panel."""
    bm = mb.bm
    L_sway = (bm.verts.layers.float.get('_sway') or bm.verts.layers.float.new('_sway')) if sway_layer else None
    jit = [0.0] + [r.uniform(-0.18, 0.18) for _ in range(cols - 1)] + [0.0]
    xs = [x0 - w / 2 + w * (k + jit[k]) / cols for k in range(cols + 1)]
    sign = r.choice((-1, 1))
    fvs = [sign * (-1) ** k * r.uniform(0.6, 1.0) * (0.5 if k in (0, cols) else 1.0) for k in range(cols + 1)]
    band_t = min(0.5, band_h / h)
    ts = [0.0, band_t] + [band_t + (1 - band_t) * (k / rows) ** 0.9 for k in range(1, rows + 1)]
    ts = ts[:-1] + [1 - 0.012 / h, 1.0]
    grid = []
    for ci, x in enumerate(xs):
        col = []
        u = (x - xs[0]) / max(1e-6, w)
        for t in ts:
            z = h * (1 - t)
            s = t                                                       # 0 top .. 1 hem
            b = max(0.0, (s - band_t) / max(1e-6, 1 - band_t))          # 0 at the band .. 1 at the hem
            A = pleat0 + (pleat1 - pleat0) * s ** 1.4
            curl = 0.012 * b * (abs(math.cos(math.pi * u)) ** 6)
            bel = belly * math.sin(math.pi * min(1.0, max(0.0, (s - 0.4) / 0.6))) ** 1.2
            hm = hem * max(0.0, 1.0 - z / 0.012)
            v = bm.verts.new((x, y0 + A * fvs[ci] + curl + bel + hm, z))
            if L_sway is not None:
                v[L_sway] = b ** 1.4
            col.append(v)
        grid.append(col)
    faces = []
    nr = len(ts)
    for ci in range(cols):
        for ri in range(nr - 1):
            f = bm.faces.new((grid[ci][ri], grid[ci + 1][ri], grid[ci + 1][ri + 1], grid[ci][ri + 1]))
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
            f.material_index = mi_band if (mi_band is not None and ri == 0) else mi
            faces.append(f)
    return faces


# =============================================================================================== 7. soft folded fabric (no knife edge)
def pillow(mb, center, W, D, T, mi, rc=0.045, m=2, puff=0.016, edge_w=0.007, edge_k=0.35, creases=(),
           sag=0.01, yaw=0.0, tilt=0.0):
    """A folded towel / cushion slab, closed. Full thickness T out to a shoulder edge_w in from the
    outline, then the edge rolls to edge_k x T at the outline (never 0: a zero edge thickness is the
    towel_folded 'knife edge' that cost four review rounds). The centre puffs by `puff`; creases =
    [(x_centre, depth, width)] cut soft fold lines across the top. rc = plan corner radius, m = arc
    segments per corner (LOD0 2, LOD1-2 1). center = (x, y, z of the underside)."""
    bm = mb.bm
    cx, cy, z0 = center
    outline = rounded_rect(W, D, rc, m)
    c_, s_ = math.cos(yaw), math.sin(yaw)
    outline = [(x * c_ - y * s_, x * s_ + y * c_) for x, y in outline]
    tan_t = math.tan(tilt)
    cz = z0 + T / 2
    s_sh = 1.0 - edge_w / (min(W, D) / 2)

    def half(s):
        if s <= s_sh:
            return 1.0
        u = min(1.0, (s - s_sh) / (1.0 - s_sh))
        return edge_k + (1 - edge_k) * math.cos(math.pi / 2 * u)

    def top_z(x, y, s):
        dz = T / 2 * half(s) + puff * (1.0 - min(s, 1.0) ** 2) - sag * (1.0 - s) * s
        for xc, depth, width in creases:
            dz -= depth * math.exp(-((x - xc) / width) ** 2) * (1.0 - s * s)
        return dz

    def ring(s, top):
        vs = []
        for (x, y) in outline:
            px, py = x * s, y * s
            pz = top_z(px, py, s) if top else -(T / 2 * half(s))
            vs.append(bm.verts.new((cx + px, cy + py, cz + pz + px * tan_t)))
        return vs
    chain = [[bm.verts.new((cx, cy, cz + top_z(0.0, 0.0, 0.0)))],
             ring(s_sh, True), ring(1.0, True), ring(1.0, False), ring(s_sh, False),
             [bm.verts.new((cx, cy, cz - T / 2))]]
    faces = []
    for A, B in zip(chain[:-1], chain[1:]):
        n = max(len(A), len(B))
        for k in range(n):
            if len(A) == 1:
                cand = (A[0], B[k], B[(k + 1) % n])
            elif len(B) == 1:
                cand = (A[k], A[(k + 1) % n], B[0])
            else:
                cand = (A[k], A[(k + 1) % n], B[(k + 1) % n], B[k])
            faces.append(bm.faces.new(cand))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


# =============================================================================================== 8. rope
def rope_turns(mb, c, axis, radius, n, mi, cord=0.006, pitch=0.011, N=5, up=None):
    """n tight rope turns round a tube of `radius` (lashings): crest rings at radius + cord with a slight
    twist per ring, thin end rings so the band ends cleanly. 2-4 turns per wrap read at 1.6 m."""
    bm = mb.bm
    axis = Vector(axis).normalized()
    up = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0)))
    half = (n - 1) * pitch / 2
    offs = [-half - pitch * 0.7] + [-half + i * pitch for i in range(n)] + [half + pitch * 0.7]
    rr = []
    for i, off in enumerate(offs):
        rad = radius + (0.002 if i in (0, len(offs) - 1) else cord)
        rr.append(ring_verts(bm, frame(Vector(c) + axis * off, axis, up), rad, N, rot=i * 0.9))
    faces = []
    for a, b in zip(rr[:-1], rr[1:]):
        faces += bridge_rings(bm, a, b)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


def rope_band(mb, c, axis, radius, width, mi, N=7, bulge=0.006, up=None):
    """Rope lashing band: 3 rings, the middle one proud (a wrapped, knotted sleeve)."""
    bm = mb.bm
    axis = Vector(axis).normalized()
    up = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0)))
    rr = []
    for off, rad in ((-width / 2, radius + 0.0015), (0, radius + bulge), (width / 2, radius + 0.0015)):
        rr.append(ring_verts(bm, frame(Vector(c) + axis * off, axis, up), rad, N, rot=off * 40))
    faces = []
    for a, b in zip(rr[:-1], rr[1:]):
        faces += bridge_rings(bm, a, b)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


def rope_knot(mb, c, size, mi):
    """little rope knot: a squashed octahedron (8 tris)"""
    bm = mb.bm
    c = Vector(c)
    vs = [bm.verts.new(c + Vector(v) * size) for v in ((0, 0, 1), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0), (0, 0, -1))]
    fs = []
    for a, b in ((1, 2), (2, 3), (3, 4), (4, 1)):
        fs.append(bm.faces.new((vs[0], vs[a], vs[b])))
        fs.append(bm.faces.new((vs[5], vs[b], vs[a])))
    mb._tag(fs, mi)
    return fs


def rope_cord(mb, p0, p1, rad, mi, sides=6, twist=True, seg_len=0.018, caps=True):
    """Twisted cord from p0 to p1 (lantern cords, hanging ties): a 6-sided tube whose odd verts are pulled
    in to 72 % and rotated one step per segment, so the strands spiral. seg_len sets the twist pitch.
    At LOD2+ use two crossed quads instead (sides <= 2 draws cards)."""
    bm = mb.bm
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    M = frame(p0, d, Z if abs(d.normalized().z) < 0.9 else Vector((1, 0, 0)))
    if sides <= 2:
        fs = []
        for ax in (((1, 0), (0, 1)) if sides == 2 else ((1, 0),)):
            q = [bm.verts.new(M @ Vector((ax[0] * s_ * rad, y, ax[1] * s_ * rad))) for s_, y in ((-1, 0), (1, 0), (1, L), (-1, L))]
            fs.append(bm.faces.new(q))
        mb._tag(fs, mi)
        return fs
    nseg = max(1, int(round(L / seg_len))) if twist else 1
    rings = []
    for i in range(nseg + 1):
        y = L * i / nseg
        tw = i * (2 * math.pi / sides) if twist else 0.0
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + tw
            rr = rad * (1.0 if (k % 2 == 0 or not twist) else 0.72)
            ring.append(bm.verts.new(M @ Vector((rr * math.cos(a), y, rr * math.sin(a)))))
        rings.append(ring)
    faces = []
    for i in range(nseg):
        faces += bridge_rings(bm, rings[i], rings[i + 1])
    if caps:
        faces.append(bm.faces.new(rings[0][::-1]))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces


# =============================================================================================== 9. lantern head
def lantern_head(mb, base, mats, lod, size=0.24, height=0.42, roof='hip', frame_w=0.02, ball=True):
    """Slim iron-framed lantern head on a post top (about 60 tris at LOD0): paper box, 4 corner bars, a
    hip (4-sided) or round (8-sided) iron roof, a finial. LOD1: box + roof. LOD2+: two crossed emissive
    quads. mats = dict(iron=slot, paper=slot); paper should be `lantern_andon` (amber, emissive) for
    square lanterns. Returns the light centre (Vector) for obj['kz_lights']. Concept lanterns are tall
    and slender (w:h about 0.5-0.6); 'fat white cubes' were marked down on three assets."""
    bx, by, bz = base
    iron, paper = mats['iron'], mats['paper']
    s = size
    kz = Vector((bx, by, bz + height / 2))
    if lod >= 2:
        bm = mb.bm
        fs = []
        for dx, dy in ((s / 2, 0), (0, s / 2)):
            q = [bm.verts.new((bx - dx, by - dy, bz)), bm.verts.new((bx + dx, by + dy, bz)),
                 bm.verts.new((bx + dx, by + dy, bz + height)), bm.verts.new((bx - dx, by - dy, bz + height))]
            fs.append(bm.faces.new(q))
        mb._tag(fs, paper)
        return kz
    mb.box((bx, by, bz + height / 2), (s * 0.86, s * 0.86, height - 0.02), paper)
    rh = 0.1
    segs = 4 if roof == 'hip' else 8
    mb.cylinder((bx, by, bz + height + rh / 2 - 0.01), radius=s * (0.86 if segs == 4 else 0.68), radius2=0.012, depth=rh,
                mi=iron, segs=segs, rot=(0, 0, math.pi / 4 if segs == 4 else math.pi / 8), cap=True)
    mb.box((bx, by, bz + 0.01), (s, s, 0.02), iron)                       # base plate
    if lod == 0:
        cb = frame_w
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((bx + sx * (s / 2 - cb / 2), by + sy * (s / 2 - cb / 2), bz + height / 2), (cb, cb, height), iron)
        if ball:
            lathe(mb, [(0.012, 0), (0.03, 0.03), (0.022, 0.055), (0, 0.065)], 6, iron, base=(bx, by, bz + height + rh - 0.02))
        else:
            mb.cylinder((bx, by, bz + height + rh + 0.02), radius=0.02, radius2=0.0, depth=0.06, mi=iron, segs=4)
    return kz


# =============================================================================================== 10. glyphs and text (reads correctly from +Y)
_glyph_cache = {}


def _area2(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def _inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def glyph_contours(text, font, res=2):
    """sampled outline polygons of `text` at font size 1 (baseline y = 0), from Blender's font curves"""
    key = (text, font, res)
    if key in _glyph_cache:
        return _glyph_cache[key]
    f = bpy.data.fonts.load(font, check_existing=True)
    cu = bpy.data.curves.new('kz_txt', 'FONT'); cu.body = text; cu.font = f
    o = bpy.data.objects.new('kz_txt', cu); bpy.context.scene.collection.objects.link(o)
    for ob in list(bpy.context.selected_objects):
        ob.select_set(False)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.convert(target='CURVE')
    polys = []
    for sp in o.data.splines:
        pts = []
        if sp.type == 'BEZIER':
            bp = sp.bezier_points
            n = len(bp)
            for i in range(n):
                a, b = bp[i], bp[(i + 1) % n]
                seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, res + 1)
                pts += [(v.x, v.y) for v in seg[:-1]]
        else:
            pts = [(p.co.x, p.co.y) for p in sp.points]
        clean = []
        for p in pts:
            if not clean or (abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1])) > 1e-6:
                clean.append(p)
        if len(clean) >= 3 and abs(_area2(clean)) > 1e-7:
            polys.append(clean)
    data = o.data
    bpy.data.objects.remove(o)
    try:
        bpy.data.curves.remove(data)
    except Exception:
        pass
    _glyph_cache[key] = polys
    return polys


def glyph_tris(text, font, res=2):
    """2D triangles of `text` (font size 1, baseline 0) and the bbox (x0, y0, x1, y1). Every outer contour
    is filled on its own with only the holes inside it, so overlapping CJK strokes stay solid while real
    counters (口, 日, A, B) stay open. Blender's plain text->mesh uses even-odd fill and punches holes
    where strokes cross (the 'broken 火' seen on signboard_kanji r3 and lift_drum r1)."""
    groups, bb = glyph_tri_groups(text, font, res)
    return [[pts[i] for i in t] for pts, tris in groups for t in tris], bb


def glyph_tri_groups(text, font, res=2):
    """like glyph_tris, but grouped per outer contour: a list of (points, index_triangles), one closed piece
    each. Points are kept per contour (a hole that touches its outer contour does not share a vertex), which
    keeps the extruded solids manifold."""
    polys = glyph_contours(text, font, res)
    if not polys:
        return [], (0, 0, 0, 0)
    big = max(polys, key=lambda p: abs(_area2(p)))
    outer_sign = 1 if _area2(big) > 0 else -1
    outers = [p for p in polys if (1 if _area2(p) > 0 else -1) == outer_sign]
    holes = [p for p in polys if p not in outers]
    groups = []
    for op in outers:
        hs = [h for h in holes if _inside(h[0], op) and abs(_area2(h)) < abs(_area2(op))]
        loops = [[Vector((x, y, 0)) for x, y in op]] + [[Vector((x, y, 0)) for x, y in h] for h in hs]
        flat = [(v.x, v.y) for L in loops for v in L]
        groups.append((flat, [tuple(t) for t in tessellate_polygon(loops)]))
    xs = [q[0] for p in polys for q in p]
    ys = [q[1] for p in polys for q in p]
    return groups, (min(xs), min(ys), max(xs), max(ys))


def text_solid(mb, text, cx, cz, y, height, mi, depth=0.006, font=FONT_KANJI, vertical=False, gap=1.12,
               tracking=0.0, res=2):
    """Raised text as closed extruded solids on a plane facing +Y, centred at (cx, cz). `height` is the
    glyph box height in metres (one character when vertical; the tallest glyph of the line otherwise).
    The back face sits at y, the relief stands `depth` towards +Y (the viewer). Glyph x runs towards
    world -X, so the text reads left-to-right for a viewer standing on +Y looking at the asset's front.
    If the asset's text faces another way, build it facing +Y first, then rotate the verts about Z.
    Returns (width, height) of the laid-out block. tracking adds extra space (em) between letters."""
    bm = mb.bm
    chars = list(text) if vertical else [text]
    items = []
    for ch in chars:
        if ch == ' ':
            items.append(None); continue
        groups, (x0, y0, x1, y1) = glyph_tri_groups(ch, font, res)
        items.append((groups, x0, y0, x1, y1))
    hs = [it[4] - it[2] for it in items if it]
    if not hs:
        return 0.0, 0.0
    s = height / max(hs)
    placed = []
    if vertical:
        n = len(items)
        for i, it in enumerate(items):
            if not it:
                continue
            groups, x0, y0, x1, y1 = it
            gx, gy = (x0 + x1) / 2, (y0 + y1) / 2
            zc = cz + ((n - 1) / 2.0 - i) * gap * height
            for pts, tris in groups:
                placed.append(([(cx - (px - gx) * s, zc + (py - gy) * s) for px, py in pts], tris))
        tw, th = max(it[3] - it[1] for it in items if it) * s, n * gap * height
    else:
        groups, x0, y0, x1, y1 = items[0]
        gx, gy = (x0 + x1) / 2, (y0 + y1) / 2
        for pts, tris in groups:
            placed.append(([(cx - (px - gx) * s, cz + (py - gy) * s) for px, py in pts], tris))
        tw, th = (x1 - x0) * s, (y1 - y0) * s
    faces = []
    for pts, tris in placed:               # one closed solid per outer contour (touching strokes stay separate)
        faces += _extrude_tris(bm, pts, tris, y, depth)
    mb._tag(faces, mi)
    return tw, th


def tracked_text(mb, text, cx, cz, y, cap_h, mi, depth=0.004, font=FONT_LATIN, tracking=0.35, res=2):
    """A horizontal line of letters laid out one by one with wide tracking ('K A Z A N - Y U'), centred at
    cx with cap height cap_h, facing +Y, reading left-to-right from +Y. Returns the total width."""
    bm = mb.bm
    _, (rx0, ry0, rx1, ry1) = glyph_tris('H', font, res)
    s = cap_h / max(1e-6, ry1)
    adv = []
    for ch in text:
        if ch == ' ':
            adv.append(([], 0.0, 0.3)); continue
        groups, (x0, y0, x1, y1) = glyph_tri_groups(ch, font, res)
        adv.append((groups, x0, (x1 - x0) if groups else 0.3))
    total = sum(w for _, _, w in adv) * s + tracking * cap_h * (len(adv) - 1)
    x = -total / 2
    faces = []
    for groups, x0, w in adv:
        for pts, tris in groups:
            if tris:
                faces += _extrude_tris(bm, [(cx - (x + (px - x0) * s), cz + py * s - cap_h / 2) for px, py in pts], tris, y, depth)
        x += w * s + tracking * cap_h
    mb._tag(faces, mi)
    return total


def _extrude_tris(bm, pts, tris, y, depth):
    """2D points (x, z) + index triangles -> closed solid between y (back) and y + depth (front), facing +Y.
    Boundary edges (used by exactly one triangle) get the side walls."""
    vb, vf = {}, {}

    def back(i):
        if i not in vb:
            vb[i] = bm.verts.new((pts[i][0], y, pts[i][1]))
        return vb[i]

    def front(i):
        if i not in vf:
            vf[i] = bm.verts.new((pts[i][0], y + depth, pts[i][1]))
        return vf[i]
    edge_count = {}
    faces = []
    for t in tris:
        if len(set(t)) < 3:
            continue
        for i in range(3):                 # count every triangle, even slivers, or an interior edge looks open
            e = tuple(sorted((t[i], t[(i + 1) % 3])))
            edge_count[e] = edge_count.get(e, 0) + 1
        try:
            faces.append(bm.faces.new([front(i) for i in t]))
            faces.append(bm.faces.new([back(i) for i in t[::-1]]))
        except ValueError:
            pass
    for (a, b), n in edge_count.items():
        if n == 1 and a in vb and b in vb:
            try:
                faces.append(bm.faces.new((vb[a], vb[b], vf[b], vf[a])))
            except ValueError:
                pass
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=list({e for f in faces for e in f.edges}))
    faces = [f for f in faces if f.is_valid]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    fr = [f for f in faces if abs(f.normal.y) > 0.99 and abs(f.calc_center_median().y - (y + depth)) < 1e-6]
    if fr and sum(1 for f in fr if f.normal.y < 0) > len(fr) / 2:
        bmesh.ops.reverse_faces(bm, faces=faces)
    return faces


# =============================================================================================== 11. card foliage
def card(mb, base, right, up, w, h, mi):
    """one alpha-tested foliage card (a quad), bottom centre at base, spanning `right` x `up`"""
    bm = mb.bm
    vs = [bm.verts.new(Vector(base) + Vector(right) * (a * w) + Vector(up) * (b * h))
          for a, b in ((-0.5, 0), (0.5, 0), (0.5, 1), (-0.5, 1))]
    f = bm.faces.new(vs)
    f.material_index = mi
    return f


def foliage_pad(mb, centre, R, T, mi_core, mi_card, r, n_cards=60, segs=12, rings=2, lobes=5, flat=1.0,
                card_w=(0.32, 0.45), card_h=(0.22, 0.30), side_band=0.25):
    """Cloud pad: an opaque flat-bottomed, gently domed core (scalloped rim) under a scatter of tilted
    needle cards. R = plan radius, T = thickness (0.25-0.33 R reads as niwaki), flat < 1 squashes along
    x. Cards lie 20-35 deg off the surface, side_band of them hang on the rim. Returns (core_faces,
    card_faces). LOD1: half the cards at 1.35 x size; LOD2: 6-8 big cards; LOD3: core only (n_cards=0)."""
    bm = mb.bm
    c = Vector(centre)
    off = Vector((r.uniform(0, 99), r.uniform(0, 99), r.uniform(0, 99)))
    ph = r.uniform(0, 6.28)

    def edge(th):
        return R * (1 + 0.11 * math.cos(lobes * th + ph) + 0.07 * noise.noise(Vector((math.cos(th) * 1.6, math.sin(th) * 1.6, 0.3)) + off))

    def P_(th, f, z):
        e = edge(th) * f
        return c + Vector((math.cos(th) * e * flat, math.sin(th) * e, z))

    def top_z(th, f):
        return T * (0.3 + 0.7 * (1 - f * f) ** 0.7) + T * 0.1 * noise.noise(Vector((math.cos(th) * f * 2.5, math.sin(th) * f * 2.5, 1.1)) + off)
    ths = [2 * math.pi * i / segs for i in range(segs)]
    rows = []
    for j in range(rings):
        f = 1.0 - 0.7 * (rings - j) / rings
        rows.append([bm.verts.new(P_(th, f, top_z(th, f) * 0.85)) for th in ths])
    rim = [bm.verts.new(P_(th, 1.0, T * 0.3 + T * 0.06 * noise.noise(Vector((math.cos(th) * 3, math.sin(th) * 3, 2.0)) + off))) for th in ths]
    und = [bm.verts.new(P_(th, 0.96, 0.0)) for th in ths]
    rows += [rim, und]
    top = bm.verts.new(c + Vector((0, 0, T * 0.85)))
    bot = bm.verts.new(c + Vector((0, 0, 0.0)))
    core = []
    for k in range(segs):
        core.append(bm.faces.new((top, rows[0][k], rows[0][(k + 1) % segs])))
    for A, B in zip(rows[:-1], rows[1:]):
        core += bridge_rings(bm, A, B)
    for k in range(segs):
        core.append(bm.faces.new((bot, und[(k + 1) % segs], und[k])))
    bmesh.ops.recalc_face_normals(bm, faces=core)
    mb._tag(core, mi_core)
    cards = []
    for _ in range(n_cards):
        th = r.uniform(0, 2 * math.pi)
        side = r.random() < side_band
        if side:
            f, z = 1.0, T * r.uniform(0.08, 0.32)
        else:
            f = math.sqrt(r.uniform(0.0, 0.94)); z = top_z(th, f)
        q = P_(th, f * 0.98, z)
        outward = Vector(((q - c).x, (q - c).y, 0))
        outward = outward.normalized() if outward.length > 1e-4 else Vector((math.cos(th), math.sin(th), 0))
        n = (outward * 0.95 + Vector((0, 0, 0.1))).normalized() if side else (Vector((0, 0, 1)) * (1.05 - 0.8 * f) + outward * f * 0.9).normalized()
        g = outward - Vector((0, 0, 0.9))
        tg = (g - n * g.dot(n)).normalized()
        rot = r.uniform(-0.7, 0.7)
        tg = (tg * math.cos(rot) + n.cross(tg) * math.sin(rot)).normalized()
        a = math.radians(r.uniform(20, 35))
        up = (tg * math.cos(a) + n * math.sin(a)).normalized()
        right = up.cross(n).normalized()
        wc, hc = r.uniform(*card_w), r.uniform(*card_h)
        cards.append(card(mb, q - up * hc * 0.3 + n * 0.012, right, up, wc, hc, mi_card))
    return core, cards


# =============================================================================================== 12. water-hosting geometry
def water_props(o, level_z, outline_xy=None, path=None, **extra):
    """Record the water as data, not as a mesh: obj['kz_water_level'] (m above the base), an optional
    plan outline [(x, y)] of the surface, an optional [(x, y, z)] path for channels, plus any extra keys
    (kz_spout_mouth, kz_overflow_dir ...). The runtime water (fx_water_surface) is built from these.
    A preview disc belongs in your canonical render script, not in build()."""
    o['kz_water_level'] = round(float(level_z), 4)
    if outline_xy is not None:
        o['kz_water_outline'] = json.dumps([[round(x, 4), round(y, 4)] for x, y in outline_xy])
    if path is not None:
        o['kz_water_path'] = json.dumps([[round(c, 4) for c in p] for p in path])
    for k, v in extra.items():
        o[k] = json.dumps(v) if isinstance(v, (list, dict, tuple)) else v
    return o


def light_entry(pos, color_k=2200, watts=25, kind='point', **kw):
    """one obj['kz_lights'] entry (JSON-serialisable)"""
    d = dict(kind=kind, pos=[round(float(c), 4) for c in pos], color_k=color_k, watts=watts)
    d.update(kw)
    return d


def set_json_props(o, **props):
    """obj[key] = JSON for lists / dicts, plain values otherwise (kz_lights, kz_params, kz_anim ...)"""
    for k, v in props.items():
        o[k] = json.dumps(v) if isinstance(v, (list, dict, tuple)) else v
    return o


# =============================================================================================== checks and placement
def centre_base(mb, centre_x=True, centre_y=True):
    """Shift the whole mesh so its bbox sits on z = 0 and (optionally) is centred on x / y. Call it last.
    Note for props with a natural axis (buckets): centre on the body axis, not the bbox, and keep the
    off-axis parts (ladle) inside the 5 % pivot tolerance of genlib.check."""
    vs = mb.bm.verts
    xs = [v.co.x for v in vs]; ys = [v.co.y for v in vs]; zs = [v.co.z for v in vs]
    dx = -(max(xs) + min(xs)) / 2 if centre_x else 0.0
    dy = -(max(ys) + min(ys)) / 2 if centre_y else 0.0
    dz = -min(zs)
    for v in vs:
        v.co.x += dx; v.co.y += dy; v.co.z += dz
    return dx, dy, dz


def tri_count(bm):
    return sum(len(f.verts) - 2 for f in bm.faces)


def check_closed(bm_or_faces):
    """dict(open_edges, nonmanifold_edges, faces, tris). Pass a bmesh (whole mesh) or a list of faces (one
    part). Closed solids should report 0 / 0; single-sided sheets (cloth, cards, open hoops) will not, and
    that is fine as long as it is deliberate."""
    if isinstance(bm_or_faces, bmesh.types.BMesh):
        faces = list(bm_or_faces.faces)
    else:
        faces = [f for f in bm_or_faces if f.is_valid]
    fs = set(faces)
    edges = {e for f in faces for e in f.edges}
    open_e = sum(1 for e in edges if len([f for f in e.link_faces if f in fs]) == 1)
    nm = sum(1 for e in edges if len([f for f in e.link_faces if f in fs]) > 2)
    return dict(open_edges=open_e, nonmanifold_edges=nm, faces=len(faces), tris=sum(len(f.verts) - 2 for f in faces))


def bbox(bm):
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    return dict(w=max(xs) - min(xs), d=max(ys) - min(ys), h=max(zs) - min(zs), zmin=min(zs))
