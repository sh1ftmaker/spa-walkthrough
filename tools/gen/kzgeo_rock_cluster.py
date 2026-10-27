"""kzgeo_rock_cluster: faceted wet-basalt mass helpers shared by the rock family
(rock_cluster, boulder_rim, rock_overhang, sea_stack).

The concept rocks (refs/gen/sheet-mod-nature.png) are glossy and faceted: big planar fracture faces with
many small chips and knobs between them, never smooth pillows. One recipe covers all four assets:

  1. convex hull of seeded points inside an ellipsoid (planar facets, crisp edges);
  2. optional subdivision (cuts) and fractal noise along the vertex normal (knobs and dents);
  3. plane chips: a few seeded planes clip the vertices that stick out past them, giving flat fracture
     faces with crisp rims after the noise (the facet read survives at LOD1-2 on a coarse hull);
  4. material by normal: top faces (n.z > top_thresh) wetter, underside (n.z < under_thresh) optional
     third slot (cave_rock on ceilings), moss on noise-clustered top patches.

Every helper takes its own rng `g` and draws all its random values whatever the LOD (the LOD only picks
how many of the drawn points / chips are used), so LODs of one seed share the same envelope.
Interpenetrating hulls are deliberate (they read as one craggy mass); each hull is closed except the
ground face, which is removed when `ground` is set.
"""
import math

import bmesh
from mathutils import Vector, noise

TINT = (0.32, 0.36, 0.46)      # near-black cooling of the library basalt (stepping_stone r7, arcade_pier)


def draw_points(g, n, rx, ry, rz, rmin=0.78):
    """n unit-ellipsoid shell points (local, not yet rotated or placed); always draws n."""
    out = []
    while len(out) < n:
        v = Vector((g.gauss(0, 1), g.gauss(0, 1), g.gauss(0, 1)))
        if v.length < 1e-6:
            continue
        v = v.normalized() * g.uniform(rmin, 1.0)
        out.append(Vector((v.x * rx, v.y * ry, v.z * rz)))
    return out


def draw_chips(g, n, up_bias=0.0, depth=(0.05, 0.16)):
    """n chip planes: (direction, depth fraction). up_bias > 0 favours upward planes (flat tops)."""
    out = []
    for _ in range(n):
        d = Vector((g.gauss(0, 1), g.gauss(0, 1), g.gauss(0, 1) + up_bias))
        if d.length < 1e-6:
            d = Vector((1, 0, 0))
        out.append((d.normalized(), g.uniform(*depth)))
    return out


def place(pts, centre, rot=0.0, tilt=(0.0, 0.0)):
    """rotate local points about z, lean them by tilt (dx/dz, dy/dz) and move them to centre."""
    c, s = math.cos(rot), math.sin(rot)
    out = []
    for p in pts:
        x = p.x * c - p.y * s
        y = p.x * s + p.y * c
        out.append(Vector((centre[0] + x + tilt[0] * p.z, centre[1] + y + tilt[1] * p.z, centre[2] + p.z)))
    return out


def basalt_hull(mb, pts, mi_side, mi_top, *, ground=None, ceiling=None, cuts=0, amp=0.0, freq=3.0, off=None,
                chips=(), top_thresh=0.6, mi_under=None, under_thresh=-0.35, mi_moss=None, moss=0.0,
                keep_ground_face=False):
    """Closed faceted rock from points (world coords). Returns the list of its faces.
    ground: clamp z >= ground and drop the flat base face. ceiling: clamp z <= ceiling.
    cuts: subdivision cuts before the noise (0 = coarse hull). amp: noise amplitude (m).
    chips: [(dir, depth_frac)] clip planes applied after the noise."""
    bm = mb.bm
    lay = mb._mark_old()
    vs = []
    for p in pts:
        q = Vector(p)
        if ground is not None:
            q.z = max(q.z, ground)
        if ceiling is not None:
            q.z = min(q.z, ceiling)
        vs.append(bm.verts.new(q))
    res = bmesh.ops.convex_hull(bm, input=vs)
    dead = list({e for e in res['geom_interior'] + res['geom_unused']
                 if isinstance(e, bmesh.types.BMVert) and e.is_valid})
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='VERTS')
    faces = [f for f in mb._new_faces(lay) if f.is_valid]
    # merge near-coplanar hull triangles into facets is not needed: the shading marks sharp edges > 35 deg
    if cuts > 0:
        edges = list({e for f in faces for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
        faces = [f for f in mb._new_faces(lay) if f.is_valid]
        bmesh.ops.triangulate(bm, faces=[f for f in faces if len(f.verts) > 3])
        faces = [f for f in mb._new_faces(lay) if f.is_valid]
    verts = list({v for f in faces for v in f.verts})
    ctr = sum((v.co for v in verts), Vector()) / max(1, len(verts))
    bm.normal_update()

    def pinned(v):
        return (ground is not None and v.co.z <= ground + 1e-4) or (ceiling is not None and v.co.z >= ceiling - 1e-4)

    if amp > 0:
        off = off or Vector((0, 0, 0))
        disp = {}
        for v in verts:
            if pinned(v):
                continue
            n = v.normal if v.normal.length > 0.1 else (v.co - ctr).normalized()
            disp[v] = n * amp * noise.fractal(v.co * freq + off, 0.65, 2.1, 3)
        for v, d in disp.items():
            v.co += d
    for d, frac in chips:
        top = max((v.co - ctr).dot(d) for v in verts)
        lim = top * (1.0 - frac)
        for v in verts:
            if pinned(v):
                continue
            k = (v.co - ctr).dot(d)
            if k > lim:
                v.co -= d * (k - lim)
    for v in verts:
        if ground is not None and v.co.z < ground:
            v.co.z = ground
        if ceiling is not None and v.co.z > ceiling:
            v.co.z = ceiling
    bm.normal_update()
    if ground is not None and not keep_ground_face:
        base = [f for f in faces if f.is_valid and f.normal.z < -0.95 and all(v.co.z < ground + 0.003 for v in f.verts)]
        if base:
            bmesh.ops.delete(bm, geom=base, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    tag_by_normal(faces, mi_side, mi_top, top_thresh, mi_under, under_thresh, mi_moss, moss, off)
    return faces


def tag_by_normal(faces, mi_side, mi_top, top_thresh=0.6, mi_under=None, under_thresh=-0.35, mi_moss=None,
                  moss=0.0, off=None):
    off = off or Vector((0, 0, 0))
    for f in faces:
        if not f.is_valid:
            continue
        nz = f.normal.z
        if nz > top_thresh:
            if mi_moss is not None and moss > 0 and noise.noise(f.calc_center_median() * 3.0 + off * 1.7) > 1.0 - 2.4 * moss:
                f.material_index = mi_moss
            else:
                f.material_index = mi_top
        elif mi_under is not None and nz < under_thresh:
            f.material_index = mi_under
        else:
            f.material_index = mi_side


def column_points(g, n_side, rings, r_bottom, r_top, z0, z1, wobble=0.12, aspect=1.0):
    """points for a tall basalt column hull: n_side-gon rings from z0 to z1, radius tapering r_bottom ->
    r_top, per-angle radial factors shared up the rings (vertical fracture facets), a jagged top cluster.
    Always draws the same number of values for given (n_side, rings)."""
    angs = [2 * math.pi * (i + g.uniform(-0.25, 0.25)) / n_side for i in range(n_side)]
    fac = [g.uniform(0.85, 1.1) for _ in range(n_side)]
    pts = []
    for k in range(rings):
        t = k / max(1, rings - 1)
        r = r_bottom + (r_top - r_bottom) * t
        z = z0 + (z1 - z0) * t * (0.9 if k == rings - 1 else 1.0)
        for i, a in enumerate(angs):
            j = fac[i] * (1 + g.uniform(-wobble, wobble))
            pts.append(Vector((math.cos(a) * r * j, math.sin(a) * r * j * aspect, z + g.uniform(-0.04, 0.04) * (z1 - z0) * (0 < k)))
                       )
    # jagged crown: 3 points around a peak offset
    px, py = g.uniform(-0.3, 0.3) * r_top, g.uniform(-0.3, 0.3) * r_top
    pts.append(Vector((px, py, z1)))
    for _ in range(2):
        a = g.uniform(0, 2 * math.pi)
        pts.append(Vector((px + math.cos(a) * r_top * 0.5, py + math.sin(a) * r_top * 0.5 * aspect, z1 - g.uniform(0.04, 0.12) * (z1 - z0))))
    return pts
