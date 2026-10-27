"""Geometry helpers for gen_shoji_wall_bay (also imported by gen_pavilion_engawa).

Everything adds faces to a genlib.MeshBuilder and tags them with a material slot.
Wall-local frames come from kzgeo_bridge_arched.frame(origin, fwd): local x runs along the wall, local +y faces the
viewer (out of the wall), local z is up.  Shoji parts are written in that (u, v, z) frame.

Shoji glow: the library's washi_backlit only glows with a real light behind it, which a bay cut into rock or a baked
pavilion does not have, so the lit paper uses lantern_andon with per-face UVs remapped into the clean centre of the
andon texture (`uv_paper`, below): every paper face gets the centre-bright fall-off, no frame shadow or crossbar.
"""
import math

import bmesh
from mathutils import Matrix, Vector, noise

import kzgeo_bridge_arched as kg

Z = Vector((0, 0, 1))


# ------------------------------------------------------------------ small primitives
def quad(mb, M, pts, mi):
    """one face from local points (counter-clockwise seen from local +y gives a +y normal)"""
    bm = mb.bm
    vs = [bm.verts.new(M @ Vector(p)) for p in pts]
    f = bm.faces.new(vs)
    f.material_index = mi
    return f


def lbox(mb, M, c, size, mi, bevel=0.0, drop_back=False):
    """box centred at local point c (u, v, z) of frame M"""
    T = M @ Matrix.Translation(Vector(c))
    fs = kg.cbox(mb, T, size, mi, bevel=bevel)
    if drop_back:
        n_back = (M.to_3x3() @ Vector((0, -1, 0))).normalized()
        dead = [f for f in fs if f.is_valid and f.normal.dot(n_back) > 0.99]
        if dead and bevel == 0:
            bmesh.ops.delete(mb.bm, geom=dead, context='FACES_ONLY')
    return fs


def bar(mb, M, c, size, mi):
    """lattice bar: only the front face and the two long side faces (ends sit in the frame, back on the paper)"""
    u, v, z = c
    su, sv, sz = size[0] / 2, size[1] / 2, size[2] / 2
    f = v + sv
    b = v - sv
    if size[2] >= size[0]:                       # vertical bar: front + left + right
        quad(mb, M, [(u - su, f, z - sz), (u + su, f, z - sz), (u + su, f, z + sz), (u - su, f, z + sz)], mi)
        quad(mb, M, [(u + su, f, z - sz), (u + su, b, z - sz), (u + su, b, z + sz), (u + su, f, z + sz)], mi)
        quad(mb, M, [(u - su, b, z - sz), (u - su, f, z - sz), (u - su, f, z + sz), (u - su, b, z + sz)], mi)
    else:                                        # horizontal bar: front + top + bottom
        quad(mb, M, [(u - su, f, z - sz), (u + su, f, z - sz), (u + su, f, z + sz), (u - su, f, z + sz)], mi)
        quad(mb, M, [(u - su, f, z + sz), (u + su, f, z + sz), (u + su, b, z + sz), (u - su, b, z + sz)], mi)
        quad(mb, M, [(u - su, b, z - sz), (u + su, b, z - sz), (u + su, f, z - sz), (u - su, f, z - sz)], mi)


# ------------------------------------------------------------------ shoji
def shoji_panel(mb, M, u0, u1, z0, z1, v, mats, lod, cols=3, rows=5, koshi=0.0, depth=0.03, bars=True,
                stile=0.034, top=0.04, bot=0.05, bar=0.009, bar_d=0.016, wood_bev=0.0, both_sides=False):
    """One sliding shoji in wall frame M: stiles, rails, optional koshi board (wooden kick panel) with its rail,
    lit paper (one face per pane band) and a kumiko lattice of (cols x rows) panes in front of the paper.
    Returns the paper faces."""
    wood, paper = mats['wood'], mats['paper']
    W, H = u1 - u0, z1 - z0
    uc = (u0 + u1) / 2
    lbox(mb, M, (u0 + stile / 2, v, z0 + H / 2), (stile, depth, H), wood, bevel=wood_bev)
    lbox(mb, M, (u1 - stile / 2, v, z0 + H / 2), (stile, depth, H), wood, bevel=wood_bev)
    lbox(mb, M, (uc, v, z1 - top / 2), (W - 2 * stile, depth, top), wood)
    lbox(mb, M, (uc, v, z0 + bot / 2), (W - 2 * stile, depth, bot), wood)
    za = z0 + bot
    if koshi > 0:
        lbox(mb, M, (uc, v - depth * 0.15, za + koshi / 2), (W - 2 * stile, depth * 0.45, koshi), wood)
        mr = 0.028
        lbox(mb, M, (uc, v, za + koshi + mr / 2), (W - 2 * stile, depth, mr), wood)
        za += koshi + mr
    zb = z1 - top
    ua, ub = u0 + stile, u1 - stile
    vp = v - depth * 0.3
    pf = [quad(mb, M, [(ua, vp, za), (ub, vp, za), (ub, vp, zb), (ua, vp, zb)], paper)]
    if both_sides:
        pf.append(quad(mb, M, [(ub, vp - 0.004, za), (ua, vp - 0.004, za), (ua, vp - 0.004, zb), (ub, vp - 0.004, zb)], paper))
    if bars and cols >= 1 and rows >= 1:
        vb = v + depth * 0.1
        for k in range(1, cols):
            u = ua + (ub - ua) * k / cols
            globals()['bar'](mb, M, (u, vb, (za + zb) / 2), (bar, bar_d, zb - za), wood)
        for k in range(1, rows):
            z = za + (zb - za) * k / rows
            globals()['bar'](mb, M, ((ua + ub) / 2, vb, z), (ub - ua, bar_d, bar), wood)
    return pf


def shoji_run(mb, M, u0, u1, z0, z1, v, mats, lod, n, r, cols=3, rows=5, koshi=0.0, open_k=None, open_frac=0.0,
              depth=0.03, bars_lod=1, both_sides=False):
    """n sliding shoji filling the opening u0..u1 on two alternating tracks (v, v - depth - gap).
    open_k: index of a panel slid open by open_frac of its width (shows the gap). Returns paper faces."""
    pw = (u1 - u0) / n
    ov = 0.018                              # panels overlap where they meet
    pf = []
    for k in range(n):
        a = u0 + k * pw - (ov if k > 0 else 0)
        b = u0 + (k + 1) * pw + (ov if k < n - 1 else 0)
        track = v if k % 2 == 0 else v - depth - 0.006
        if open_k == k and open_frac > 0:
            sh = pw * open_frac * (1 if k < n - 1 else -1)
            sh = sh if k % 2 == 1 else -sh
            a, b = a + sh, b + sh
        pf += shoji_panel(mb, M, a, b, z0, z1, track, mats, lod, cols=cols, rows=rows, koshi=koshi, depth=depth,
                          bars=lod <= bars_lod, both_sides=both_sides)
    return pf


def lattice_long(mb, M, u0, u1, z0, z1, v, mi, n_u, n_z, bar=0.012, bar_d=0.016):
    """cheap kumiko for lower LODs: long bars spanning the whole opening"""
    for k in range(1, n_u):
        u = u0 + (u1 - u0) * k / n_u
        globals()['bar'](mb, M, (u, v, (z0 + z1) / 2), (bar, bar_d, z1 - z0), mi)
    for k in range(1, n_z):
        z = z0 + (z1 - z0) * k / n_z
        globals()['bar'](mb, M, ((u0 + u1) / 2, v, z), (u1 - u0, bar_d, bar), mi)


def ranma(mb, M, u0, u1, z0, z1, v, mats, lod, style, r):
    """transom over the shoji: lit paper behind a vertical-slat ('tate') or diamond-ish 'ajiro' lattice."""
    wood, paper = mats['wood'], mats['paper']
    quad(mb, M, [(u0, v - 0.012, z0), (u1, v - 0.012, z0), (u1, v - 0.012, z1), (u0, v - 0.012, z1)], paper)
    W = u1 - u0
    if lod >= 2:
        return
    if style == 'tate':
        n = max(4, int(W / (0.09 if lod == 0 else 0.18)))
        for k in range(1, n):
            bar(mb, M, (u0 + W * k / n, v, (z0 + z1) / 2), (0.014, 0.02, z1 - z0), wood)
        bar(mb, M, ((u0 + u1) / 2, v, (z0 + z1) / 2), (W, 0.02, 0.014), wood)
    else:  # 'yoko': widely spaced verticals + 2 horizontals (sukashi)
        n = max(3, int(W / (0.24 if lod == 0 else 0.4)))
        for k in range(1, n):
            bar(mb, M, (u0 + W * k / n, v, (z0 + z1) / 2), (0.016, 0.02, z1 - z0), wood)
        for k in (1, 2):
            bar(mb, M, ((u0 + u1) / 2, v, z0 + (z1 - z0) * k / 3), (W, 0.02, 0.012), wood)


def smooth_slots(obj, slots):
    """clear the sharp flag (set by genlib.finish's angle rule) on edges inside the given slots: organic pads"""
    if not slots:
        return
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    slots = set(slots)
    for e in bm.edges:
        if e.link_faces and all(f.material_index in slots for f in e.link_faces):
            e.smooth = True
    bm.to_mesh(me); bm.free()


def uv_paper(obj, slots, u_rng=(0.05, 0.95), v_rng=(0.06, 0.57)):
    """per-face UVs for lit paper (lantern_andon): each face spans the clean centre of the andon texture."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.get('UVMap')
    slots = set(slots)
    for f in bm.faces:
        if f.material_index not in slots:
            continue
        n = f.normal
        if abs(n.z) > 0.7:
            a, b = Vector((1, 0, 0)), Vector((0, 1, 0))
        else:
            a = Vector((-n.y, n.x, 0)).normalized(); b = Vector((0, 0, 1))
        us = [l.vert.co.dot(a) for l in f.loops]; vs = [l.vert.co.dot(b) for l in f.loops]
        du, dv = max(us) - min(us) or 1, max(vs) - min(vs) or 1
        for l, u_, v_ in zip(f.loops, us, vs):
            l[uv].uv = (u_rng[0] + (u_ - min(us)) / du * (u_rng[1] - u_rng[0]),
                        v_rng[0] + (v_ - min(vs)) / dv * (v_rng[1] - v_rng[0]))
    bm.to_mesh(me); bm.free()


# ------------------------------------------------------------------ rock surround (inverted U band)
def _poly_resample(pts, n):
    """n+1 points evenly by arc length along polyline pts (keeps the ends)"""
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + (b - a).length)
    out = []
    for i in range(n + 1):
        s = L[-1] * i / n
        k = max(0, min(len(pts) - 2, next((j for j in range(len(L) - 1) if L[j + 1] >= s), len(pts) - 2)))
        t = (s - L[k]) / max(1e-9, L[k + 1] - L[k])
        out.append(pts[k].lerp(pts[k + 1], t))
    return out


def rock_band(mb, P_in, P_out, prof, mi, rock, r, k_amp=1.0, k_crack=1.0, lump=0.0, lump_f=2.2,
              y_lim=(-0.2, 0.2), x_lim=None, z_lim=None, glassy_mi=None, wet_mi=None, cap_ends=True):
    """Lofted rough-rock band between an inner and an outer polyline (equal-length lists of wall-plane points
    (x, z)), prof = [(a, y)] across the band (a 0 = inner, 1 = outer, y = depth; first/last rows are the seams).
    Carved by `rock` (gen_torii_basalt.Rock) along the vertex normals, with a low-frequency 'lump' bulge that
    makes the band read as stacked boulders. Returns rows (list over u of list over profile of BMVerts)."""
    bm = mb.bm
    nv = len(prof)
    P_in = [Vector((p[0], 0, p[1])) for p in P_in]
    P_out = [Vector((p[0], 0, p[1])) for p in P_out]
    rows = []
    for pi, po in zip(P_in, P_out):
        row = []
        for a, y in prof:
            p = pi.lerp(po, a)
            row.append(bm.verts.new(Vector((p.x, y, p.z))))
        rows.append(row)
    faces = []
    for i in range(len(rows) - 1):
        for j in range(nv - 1):
            f = bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
            f.material_index = mi
            faces.append(f)
    if cap_ends and nv > 2:
        for row, flip in ((rows[0], False), (rows[-1], True)):
            ring = row[:]
            try:
                f = bm.faces.new(ring[::-1] if flip else ring)
                f.material_index = mi
                faces.append(f)
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    # make normals face +y (toward the viewer) on the band
    if sum(f.normal.y for f in faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=faces)
    bm.normal_update()
    off = Vector((r.uniform(0, 50), r.uniform(0, 50), r.uniform(0, 50)))
    moved = []
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            if j == 0 or j == nv - 1:
                wgt = 0.25
            else:
                wgt = 1.0
            n = v.normal.copy()
            d = 0.0
            if rock is not None:
                d, _ = rock.sample(v.co, k_amp, k_crack)
            if lump > 0:
                d += lump * (noise.noise(v.co * lump_f + off) + 0.35)
            moved.append((v, v.co + n * d * wgt))
    for v, p in moved:
        if y_lim:
            p.y = min(max(p.y, y_lim[0]), y_lim[1])
        if x_lim:
            p.x = min(max(p.x, x_lim[0]), x_lim[1])
        if z_lim:
            p.z = min(max(p.z, z_lim[0]), z_lim[1])
        v.co = p
    if rock is not None and (glassy_mi is not None or wet_mi is not None):
        for f in faces:
            if not f.is_valid:
                continue
            _, hsh = rock.sample(f.calc_center_median(), 0, 0)
            if glassy_mi is not None and hsh < rock.glassy * 0.5:
                f.material_index = glassy_mi
            elif wet_mi is not None and hsh > 0.82:
                f.material_index = wet_mi
    return rows


def stick(mb, p0, p1, rad, mi, n=4, rad1=None, cap=False):
    """n-sided prism between two points"""
    bm = mb.bm
    p0, p1 = Vector(p0), Vector(p1)
    t = (p1 - p0).normalized()
    a = t.cross(Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))).normalized()
    b = t.cross(a)
    r1 = rad if rad1 is None else rad1
    A = [bm.verts.new(p0 + (a * math.cos(2 * math.pi * k / n) + b * math.sin(2 * math.pi * k / n)) * rad) for k in range(n)]
    B = [bm.verts.new(p1 + (a * math.cos(2 * math.pi * k / n) + b * math.sin(2 * math.pi * k / n)) * r1) for k in range(n)]
    fs = []
    for k in range(n):
        k2 = (k + 1) % n
        fs.append(bm.faces.new((A[k], A[k2], B[k2], B[k])))
    if cap:
        fs.append(bm.faces.new(B))
    for f in fs:
        f.material_index = mi
    return fs


# ------------------------------------------------------------------ sill plants (no foliage material yet:
# moss / leaf pads use washi tinted moss-green; see the generator docstring)
def plant(mb, base, mats, lod, r, kind, scale=1.0):
    """small potted plant on a sill: 'bonsai' (pine-like trunk + cloud pads), 'moss' (kokedama ball on a
    saucer), 'sasa' (three bamboo culms + leaf tufts). base = (x, y, z) of the pot bottom."""
    x, y, z = base
    s = scale
    pot, wood, leaf, bamboo = mats['pot'], mats['trunk'], mats['leaf'], mats.get('bamboo', mats['trunk'])
    segs = 8 if lod == 0 else 6 if lod == 1 else 4
    if kind == 'moss':
        kg.lathe(mb, (x, y, z), [(0.05 * s, 0), (0.075 * s, 0.018 * s), (0.068 * s, 0.026 * s), (0, 0.026 * s)], pot,
                 segs=segs)
        fs, vs = mb.ico((x, y, z + 0.085 * s), 0.07 * s, leaf, subdiv=1 if lod == 0 else 0, scale=(1, 1, 0.92))
        off = Vector((r.uniform(0, 9), r.uniform(0, 9), 0))
        for v in vs:
            v.co += (v.co - Vector((x, y, z + 0.085 * s))).normalized() * 0.012 * s * noise.noise(v.co * 40 + off)
        return 0.17 * s
    # pot (lathe, flared rim) for bonsai / sasa
    ph = (0.07 if kind == 'bonsai' else 0.11) * s
    pr = (0.075 if kind == 'bonsai' else 0.06) * s
    kg.lathe(mb, (x, y, z), [(pr * 0.8, 0), (pr, ph * 0.85), (pr * 1.08, ph), (pr * 0.9, ph), (0, ph * 0.86)], pot,
             segs=segs, rot=r.uniform(0, 1))
    if kind == 'sasa':
        H = r.uniform(0.32, 0.42) * s
        for k in range(3 if lod == 0 else 2):
            a = 2.1 * k + r.uniform(-0.3, 0.3)
            bx, by = x + math.cos(a) * pr * 0.4, y + math.sin(a) * pr * 0.4
            lean = Vector((math.cos(a) * 0.12, math.sin(a) * 0.05, 1)).normalized()
            hk = H * (1 - 0.2 * k)
            top = Vector((bx, by, z + ph)) + lean * hk
            stick(mb, Vector((bx, by, z + ph * 0.9)), top, 0.006 * s, bamboo, 4 if lod == 0 else 3)
            fs, vs = mb.ico(tuple(top - Vector((0, 0, 0.03 * s))), 0.05 * s, leaf, subdiv=0, scale=(1.2, 0.8, 0.7))
        return ph + H
    # bonsai: curved trunk (tube) + 2-3 flattened cloud pads
    ht = r.uniform(0.2, 0.28) * s
    lean = r.choice([-1, 1])
    pts = [Vector((x, y, z + ph * 0.9)), Vector((x + lean * 0.03 * s, y, z + ph + ht * 0.35)),
           Vector((x - lean * 0.02 * s, y + 0.01, z + ph + ht * 0.7)), Vector((x + lean * 0.04 * s, y, z + ph + ht))]
    rings = []
    bm = mb.bm
    for i, p in enumerate(pts):
        rad = (0.016 - 0.009 * i / 3) * s
        n = 5 if lod == 0 else 3
        rings.append([bm.verts.new(p + Vector((math.cos(2 * math.pi * k / n) * rad, math.sin(2 * math.pi * k / n) * rad, 0)))
                      for k in range(n)])
    for A, B in zip(rings, rings[1:]):
        for k in range(len(A)):
            k2 = (k + 1) % len(A)
            bm.faces.new((A[k], A[k2], B[k2], B[k])).material_index = wood
    pads = [(pts[-1], 0.085), (pts[2] + Vector((-lean * 0.07 * s, 0, 0)), 0.06)]
    if lod == 0:
        pads.append((pts[1] + Vector((lean * 0.08 * s, 0.01, 0.02 * s)), 0.05))
    for c, rr in pads:
        fs, vs = mb.ico(tuple(c), rr * s, leaf, subdiv=1 if lod == 0 else 0, scale=(1.25, 0.95, 0.5))
        off = Vector((r.uniform(0, 9), r.uniform(0, 9), 0))
        for v in vs:
            v.co.z += 0.012 * s * noise.noise(v.co * 30 + off)
    return ph + ht + 0.04 * s


# ------------------------------------------------------------------ round-2 parts: rounded boulders, potted shrubs
def boulder(mb, c, size, mi, r, lod, y_back=None, x_lim=None, y_lim=None, z_lim=None, lump=0.18, flat_top=None):
    """Rounded basalt boulder: icosphere (subdiv 1 at LOD0, 0 at LOD1) squashed to `size`, low-frequency noise
    lumps (no planar facet cuts: they read as foil shards), clamped into the bounds; faces pressed flat against
    the wall plane (y <= y_back) are deleted. Returns the faces."""
    bm = mb.bm
    res = bmesh.ops.create_icosphere(bm, subdivisions=1 if lod == 0 else 0, radius=1.0)
    vs = res['verts']
    off = Vector((r.uniform(0, 99), r.uniform(0, 99), r.uniform(0, 99)))
    sq = r.uniform(0.0, 0.25)                      # flattened underside / squarer shoulders
    for v in vs:
        n = v.co.normalized()
        d = 1.0 + lump * noise.noise(n * 1.3 + off) + 0.05 * noise.noise(n * 3.1 + off)
        p = n * d
        if p.z < -0.3:
            p.z = -0.3 - (p.z + 0.3) * (1 - sq)
        v.co = Vector((c[0] + p.x * size[0] / 2, c[1] + p.y * size[1] / 2, c[2] + p.z * size[2] / 2))
        if flat_top is not None and v.co.z > flat_top:
            v.co.z = flat_top
    clamp_verts = kg.clamp_verts
    clamp_verts(vs, xlim=x_lim, ylim=y_lim)
    if z_lim:
        for v in vs:
            v.co.z = min(max(v.co.z, z_lim[0]), z_lim[1])
    faces = list({f for v in vs for f in v.link_faces})
    if y_back is not None:
        dead = [f for f in faces if all(v.co.y <= y_back + 0.005 for v in f.verts)]
        if dead:
            bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        faces = [f for f in faces if f.is_valid]
    for f in faces:
        f.material_index = mi
    return faces


def card_cluster(mb, c, rad, mi, r, n_cards=2, tilt=0.35, horiz=True):
    """foliage pad from alpha cards: n crossed vertical-ish cards + an optional horizontal one"""
    bm = mb.bm
    c = Vector(c)
    fs = []
    a0 = r.uniform(0, math.pi)
    for k in range(n_cards):
        a = a0 + math.pi * k / n_cards
        u = Vector((math.cos(a), math.sin(a), 0)) * rad
        up = Vector((-math.sin(a) * tilt, math.cos(a) * tilt, 1)).normalized() * rad * 0.75
        q = [bm.verts.new(c - u - up), bm.verts.new(c + u - up), bm.verts.new(c + u + up), bm.verts.new(c - u + up)]
        fs.append(bm.faces.new(q))
    if horiz:
        a = a0 + 0.4
        u = Vector((math.cos(a), math.sin(a), 0)) * rad * 1.1
        v_ = Vector((-math.sin(a), math.cos(a), 0)) * rad * 0.9
        q = [bm.verts.new(c - u - v_), bm.verts.new(c + u - v_), bm.verts.new(c + u + v_), bm.verts.new(c - u + v_)]
        fs.append(bm.faces.new(q))
    for f in fs:
        f.material_index = mi
    return fs


def shrub(mb, base, mats, lod, r, height=0.65, kind='pine', y_lim=None):
    """potted shrub: round ceramic pot (lathe), bark trunk with 1-2 branches, needle-card pads (foliage_pine).
    kind 'pine' = niwaki-like stacked pads, 'bush' = rounded mound of cards. base = pot bottom centre."""
    x, y, z = base
    pot, bark, leaf = mats['pot'], mats['bark'], mats['leaf']
    H = height
    pr = min(0.13, 0.09 + 0.06 * H)
    ph = pr * 1.15
    segs = 10 if lod == 0 else 6 if lod == 1 else 4
    prof = [(pr * 0.7, 0), (pr * 0.95, ph * 0.25), (pr, ph * 0.7), (pr * 0.92, ph * 0.95), (pr * 1.02, ph), (pr * 0.9, ph),
            (0, ph * 0.9)]
    if lod >= 1:
        prof = [prof[0], prof[2], prof[4], prof[6]]
    kg.lathe(mb, (x, y, z), prof, pot, segs=segs, rot=r.uniform(0, 1))
    top = z + ph
    if lod >= 2:
        fs, vs = mb.ico((x, y, top + (H - ph) * 0.55), (H - ph) * 0.45, leaf, subdiv=0, scale=(1.1, 0.8, 1.0))
        return
    lean = Vector((r.uniform(-0.12, 0.12), r.uniform(-0.05, 0.05), 1)).normalized()
    hT = H - ph
    pts = [Vector((x, y, top - 0.02))]
    for k in (1, 2, 3):
        p = pts[0] + lean * hT * 0.8 * k / 3
        p.x += math.sin(k * 1.7 + r.uniform(0, 3)) * 0.03
        pts.append(p)
    for a, b, rad in zip(pts, pts[1:], (0.022, 0.017, 0.012)):
        stick(mb, a, b, rad * (0.8 + 0.4 * H), bark, 5 if lod == 0 else 3, rad1=rad * 0.8 * (0.8 + 0.4 * H))
    pads = []
    if kind == 'pine':
        npd = 4 if lod == 0 else 2
        for k in range(npd):
            t = 0.35 + 0.65 * k / max(1, npd - 1)
            side = 1 if k % 2 else -1
            c = pts[0] + lean * hT * t * 0.85 + Vector((side * r.uniform(0.06, 0.14) * (1 - t * 0.6), r.uniform(-0.03, 0.03), 0))
            rad = (0.16 - 0.06 * t) * (0.7 + 0.5 * H)
            if k < npd - 1 and lod == 0:
                stick(mb, pts[0] + lean * hT * t * 0.8, c, 0.008, bark, 3)
            pads.append((c, rad, 0.25))
    else:
        npd = 5 if lod == 0 else 2
        for k in range(npd):
            a = 2 * math.pi * k / npd + r.uniform(-0.3, 0.3)
            c = pts[0] + lean * hT * r.uniform(0.45, 0.85) + Vector((math.cos(a) * 0.1, math.sin(a) * 0.06, 0)) * (0.6 + H)
            pads.append((c, 0.15 * (0.7 + 0.5 * H), 0.5))
    for c, rad, tilt in pads:
        if y_lim:
            c.y = min(max(c.y, y_lim[0] + rad * 0.6), y_lim[1] - rad * 0.6)
        card_cluster(mb, c, rad, leaf, r, n_cards=2 if lod == 0 else 1, tilt=tilt, horiz=True)


def orient_slot(obj, slots, direction):
    """flip faces of the given slots whose normal points away from `direction` (washi_backlit emits from the
    front face only; recalc_face_normals may turn lone paper quads around)"""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    d = Vector(direction).normalized()
    slots = set(slots)
    bad = [f for f in bm.faces if f.material_index in slots and f.normal.dot(d) < 0]
    if bad:
        bmesh.ops.reverse_faces(bm, faces=bad)
    bm.to_mesh(me); bm.free()


def bonsai_geo(mb, base, mats, lod, r, height=0.5, tall=False, y_lim=None):
    """geometric bonsai / niwaki shrub: dark glazed pot (lathe), twisted trunk tube, 3-5 clumped foliage blobs
    (flattened faceted icospheres in the moss material), no alpha cards. base = pot bottom centre."""
    x, y, z = base
    pot, bark, leaf = mats['pot'], mats['bark'], mats['leaf']
    H = height
    pr = 0.1 if not tall else 0.14
    ph = pr * (0.9 if not tall else 1.1)
    segs = 10 if lod == 0 else 6 if lod == 1 else 4
    prof = [(pr * 0.72, 0), (pr * 0.98, ph * 0.3), (pr, ph * 0.75), (pr * 1.05, ph), (pr * 0.92, ph), (0, ph * 0.9)]
    if lod >= 1:
        prof = [prof[0], prof[2], prof[3], prof[5]]
    kg.lathe(mb, (x, y, z), prof, pot, segs=segs, rot=r.uniform(0, 1))
    top = z + ph
    if lod >= 2:
        mb.ico((x, y, top + (H - ph) * 0.6), (H - ph) * 0.42, leaf, subdiv=0, scale=(1.2, 0.8, 0.9))
        return
    # twisted trunk: a few segments that swing side to side and taper
    hT = H - ph
    n = 4 if lod == 0 else 3
    lean = r.choice([-1, 1])
    pts = [Vector((x, y, top - 0.01))]
    for k in range(1, n + 1):
        t = k / n
        pts.append(Vector((x + lean * math.sin(t * 2.4 + 0.3) * 0.07 * (1 + H), y + 0.02 * math.sin(t * 5.0),
                           top + hT * 0.78 * t)))
    rad0 = 0.022 if not tall else 0.032
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        stick(mb, a, b, rad0 * (1 - 0.18 * k), bark, 5 if lod == 0 else 4, rad1=rad0 * (1 - 0.18 * (k + 1)))
    # foliage clumps: tiered pads off the trunk + a crown pad
    nb = (5 if tall else 3 + (1 if r.random() < 0.5 else 0)) if lod == 0 else 2 + (1 if tall else 0)
    for k in range(nb):
        t = 0.45 + 0.55 * k / max(1, nb - 1)
        p = pts[0].lerp(pts[-1], t)
        side = -1 if k % 2 else 1
        if k < nb - 1:
            p = p + Vector((side * r.uniform(0.07, 0.14) * (0.6 + H), r.uniform(-0.02, 0.02), 0))
            if lod == 0:
                stick(mb, pts[0].lerp(pts[-1], t - 0.05), p, 0.008 if not tall else 0.012, bark, 3)
        rad = (0.11 - 0.025 * t) * (0.7 + 0.6 * H)
        if y_lim:
            p.y = min(max(p.y, y_lim[0] + rad * 0.5), y_lim[1] - rad * 0.5)
        fs, vs = mb.ico(tuple(p), rad, leaf, subdiv=1 if lod == 0 else 0, scale=(1.25, 0.9, 0.55))
        off = Vector((r.uniform(0, 9), r.uniform(0, 9), r.uniform(0, 9)))
        for v in vs:
            v.co += (v.co - p).normalized() * rad * 0.18 * noise.noise(v.co * 9 + off)
