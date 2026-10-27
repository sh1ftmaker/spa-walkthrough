"""kzgeo_pool_shell: plan-loop geometry for sunken pools (pool_shell, koi_pond, mirror_pool, stone_tub).

A pool is described by its WATER OUTLINE: a closed CCW polygon in plan (x, y), resampled uniformly by arc
length so every derived loop (offset outward = positive, inward = negative) has the same vertex count and the
loops can be bridged with quad strips. Profiles are (u, z): u = offset from the water outline along the
outward normal, z = height. Everything tags faces with genlib.MeshBuilder slots like kzgeo_common.
"""
import math

import bmesh
from mathutils import Vector, noise

import kzgeo_common as C


# ------------------------------------------------------------------------------------------------ polygons
def area(P):
    return 0.5 * sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))


def ccw(P):
    return list(P) if area(P) > 0 else list(P)[::-1]


def perimeter(P):
    return sum(math.hypot(P[(i + 1) % len(P)][0] - P[i][0], P[(i + 1) % len(P)][1] - P[i][1]) for i in range(len(P)))


def resample(P, N, start=None):
    """N points uniformly by arc length along the closed polygon P (CCW). start: arc length of point 0."""
    P = ccw(P)
    n = len(P)
    seg = [math.hypot(P[(i + 1) % n][0] - P[i][0], P[(i + 1) % n][1] - P[i][1]) for i in range(n)]
    L = sum(seg)
    out = []
    s0 = start or 0.0
    i, acc = 0, 0.0
    targets = [(s0 + L * k / N) % L for k in range(N)]
    for t in targets:
        i, acc = 0, 0.0
        while acc + seg[i] < t and i < n - 1:
            acc += seg[i]; i += 1
        f = (t - acc) / max(seg[i], 1e-9)
        a, b = P[i], P[(i + 1) % n]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def decimate(P, N):
    """Visvalingam: drop the vertex with the smallest triangle area until N remain (keeps corners)"""
    Q = list(ccw(P))
    while len(Q) > N:
        n = len(Q)
        best, bi = None, 0
        for i in range(n):
            a, b, c = Q[i - 1], Q[i], Q[(i + 1) % n]
            ar = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))
            if best is None or ar < best:
                best, bi = ar, i
        Q.pop(bi)
    return Q


def normals(P):
    """outward unit normals (CCW polygon) from the averaged neighbour tangent, plus the miter factor"""
    n = len(P)
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        t1 = Vector((b[0] - a[0], b[1] - a[1])); t2 = Vector((c[0] - b[0], c[1] - b[1]))
        t1.normalize(); t2.normalize()
        t = (t1 + t2)
        if t.length < 1e-6:
            t = t2
        t.normalize()
        nn = Vector((t.y, -t.x))
        miter = 1.0 / max(0.6, Vector((t2.y, -t2.x)).dot(nn))
        out.append((nn.x, nn.y, miter))
    return out


def offset(P, d, nrm=None):
    nrm = nrm or normals(P)
    return [(p[0] + n[0] * d * n[2], p[1] + n[1] * d * n[2]) for p, n in zip(P, nrm)]


def cumlen(P):
    c = [0.0]
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        c.append(c[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return c                                   # len N + 1, c[-1] = perimeter


def at_s(P, cum, s):
    """point, tangent, outward normal at arc length s (wraps)"""
    L = cum[-1]
    s %= L
    lo, hi = 0, len(P)
    while hi - lo > 1:
        m = (lo + hi) // 2
        if cum[m] <= s:
            lo = m
        else:
            hi = m
    i = lo
    a, b = P[i], P[(i + 1) % len(P)]
    f = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
    p = Vector((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, 0))
    t = Vector((b[0] - a[0], b[1] - a[1], 0)).normalized()
    return p, t, Vector((t.y, -t.x, 0))


def s_near(P, cum, xy):
    """arc length of the loop vertex nearest to xy"""
    i = min(range(len(P)), key=lambda k: (P[k][0] - xy[0]) ** 2 + (P[k][1] - xy[1]) ** 2)
    return cum[i]


def sdist(cum, s, a):
    """signed shortest arc distance from a to s on the loop"""
    L = cum[-1]
    d = (s - a) % L
    return d - L if d > L / 2 else d


# ------------------------------------------------------------------------------------------------ footprints
def fp_rect(L, W, rc, m=6):
    return C.rounded_rect(L, W, rc, m)


def fp_round(R, aspect=1.0, r=None, wob=0.0, n=96):
    sx, sy = math.sqrt(aspect), 1 / math.sqrt(aspect)
    ph = [r.uniform(0, 2 * math.pi) for _ in range(3)] if r else [0, 0, 0]
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        k_ = 1 + wob * (math.sin(2 * a + ph[0]) * 0.6 + math.sin(3 * a + ph[1]) * 0.4 + math.sin(5 * a + ph[2]) * 0.25)
        pts.append((R * k_ * math.cos(a) * sx, R * k_ * math.sin(a) * sy))
    return pts


def fp_free(r, R, aspect=1.3, bites=1, n=120, rot=0.0):
    f = C.stone_outline(r, R, aspect=aspect, harmonics=((2, 0.07), (3, 0.07), (4, 0.05), (5, 0.03)),
                        bites=bites, bite_depth=(0.08, 0.14), bite_width=(0.35, 0.6), rot=rot)
    return [f(2 * math.pi * k / n) for k in range(n)]


def superellipse(a, b, e=4.0, n=96, r=None, wob=0.0):
    ph = [r.uniform(0, 2 * math.pi) for _ in range(3)] if r else [0, 0, 0]
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2 / e), c)
        y = b * math.copysign(abs(s) ** (2 / e), s)
        k_ = 1 + wob * (math.sin(2 * t + ph[0]) * 0.5 + math.sin(3 * t + ph[1]) * 0.35 + math.sin(5 * t + ph[2]) * 0.2)
        pts.append((x * k_, y * k_))
    return pts


# ------------------------------------------------------------------------------------------------ surfaces
def strip(mb, A, B, mi, closed=True):
    """quad strip between two equal-length vertex loops (lists of BMVerts)"""
    bm = mb.bm
    fs = []
    n = len(A)
    for k in range(n if closed else n - 1):
        k2 = (k + 1) % n
        try:
            f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = mi
            fs.append(f)
        except ValueError:
            pass
    return fs


def loop_verts(mb, P, z):
    """P: [(x, y)] ; z: float or list per vertex"""
    zz = z if isinstance(z, (list, tuple)) else [z] * len(P)
    return [mb.bm.verts.new((p[0], p[1], h)) for p, h in zip(P, zz)]


def fill(mb, V, mi, up=True):
    """cap a vertex loop with an ngon, then beauty-triangulate it (robust for concave outlines)"""
    bm = mb.bm
    f = bm.faces.new(V if up else V[::-1])
    f.material_index = mi
    if (f.normal.z < 0) == up:
        f.normal_flip()
    res = bmesh.ops.triangulate(bm, faces=[f], quad_method='BEAUTY', ngon_method='BEAUTY')
    fs = res['faces']
    for g in fs:
        g.material_index = mi
    return fs


def shell(mb, P, rings, mis, bed_mi=None, bed_z=None, nrm=None):
    """Bridge offset loops of the water outline P. rings = [(u, z or [z per vert])] in order (outer top ->
    inner bottom, any order as long as consecutive rings are neighbours); mis[i] = slot of the strip between
    ring i and i+1. bed_mi: fill the last ring as the bed (faces up). Returns the vertex loops."""
    nrm = nrm or normals(P)
    loops = [loop_verts(mb, offset(P, u, nrm), z) for u, z in rings]
    faces = []
    for i in range(len(loops) - 1):
        faces += strip(mb, loops[i], loops[i + 1], mis[i])
    if bed_mi is not None:
        faces += fill(mb, loops[-1], bed_mi, up=True)
    return loops, faces


def segment_sweep(mb, P, cum, s0, s1, prof, mis, step=0.15, caps=True, zfn=None, bulge=None):
    """Sweep a closed (u, z) profile along the outline from arc length s0 to s1 (a kerb / coping block).
    prof is CCW in the (u, z) plane; mis[k] = slot of the profile edge k -> k+1. zfn(s) adds a height offset.
    bulge(s, k) -> extra u offset for profile vertex k (stone irregularity). Returns faces."""
    bm = mb.bm
    L = s1 - s0
    n = max(1, int(math.ceil(L / step)))
    rings = []
    for j in range(n + 1):
        s = s0 + L * j / n
        p, t, nn = at_s(P, cum, s)
        dz = zfn(s) if zfn else 0.0
        ring = []
        for k, (u, z) in enumerate(prof):
            uu = u + (bulge(s, k) if bulge else 0.0)
            ring.append(bm.verts.new(p + nn * uu + Vector((0, 0, z + dz))))
        rings.append(ring)
    m = len(prof)
    faces = []
    for j in range(n):
        A, B = rings[j], rings[j + 1]
        for k in range(m):
            k2 = (k + 1) % m
            f = bm.faces.new((A[k], B[k], B[k2], A[k2]))
            f.material_index = mis[k]
            faces.append(f)
    if caps:
        for ring, rev in ((rings[0], False), (rings[-1], True)):
            f = bm.faces.new(ring[::-1] if rev else ring)
            f.material_index = mis[-1]
            faces.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def block_spans(cum, r, lmin, lmax, gap, skips=(), start=None):
    """split the loop into blocks [s0, s1] of length lmin..lmax with `gap` joints, avoiding skip spans
    [(centre s, half width)]. Returns a list of (s0, s1)."""
    L = cum[-1]
    s = start if start is not None else r.uniform(0, lmax)
    end = s + L
    spans = []
    while s < end - lmin * 0.5:
        ln = r.uniform(lmin, lmax)
        if end - (s + ln) < lmin * 0.6:
            ln = end - s
        spans.append((s, s + ln - gap))
        s += ln
    out = []
    for a, b in spans:
        parts = [(a, b)]
        for c, hw in skips:
            nxt = []
            for x, y in parts:
                # move skip centre into this lap
                cc = c
                while cc < x - hw:
                    cc += L
                while cc > y + hw:
                    cc -= L
                lo, hi = cc - hw, cc + hw
                if hi <= x or lo >= y:
                    nxt.append((x, y)); continue
                if lo - x > 0.12:
                    nxt.append((x, lo - gap))
                if y - hi > 0.12:
                    nxt.append((hi + gap, y))
            parts = nxt
        out += parts
    return out


# ------------------------------------------------------------------------------------------------ rim rocks
def rock_layout(P, cum, r, sizes, u_range, z0, top_fn, overlap=(0.30, 0.42), skips=(), start=None):
    """Seeded rim rocks along the loop. sizes = [(weight, rmin, rmax)] size classes; u_range = centre offset
    from the water edge (outward positive); top_fn(r_, rng) -> top z. Returns dicts (s, u, rx, ry, z0, ztop,
    seed_salt) sorted by volume, so lower LODs keep the largest."""
    L = cum[-1]
    s = start if start is not None else r.uniform(0, 1)
    end = s + L
    tot = sum(w for w, _, _ in sizes)
    prev = None
    rocks = []
    while True:
        x = r.uniform(0, tot)
        for w, a, b in sizes:
            x -= w
            if x <= 0:
                break
        rr = r.uniform(a, b)
        if prev is not None:
            s += (prev + rr) * (1 - r.uniform(*overlap))
        if s > end - rr * 0.6:
            break
        blocked = any(abs(sdist(cum, s, c)) < hw + rr * 0.55 for c, hw in skips)
        if not blocked:
            rocks.append(dict(s=s % L, u=r.uniform(*u_range) + rr * 0.25, rx=rr * r.uniform(0.75, 0.95), ry=rr,
                              z0=z0, ztop=top_fn(rr, r), salt=len(rocks) + 1, rot=r.uniform(-0.25, 0.25)))
        prev = rr
    rocks.sort(key=lambda k: -(k['rx'] * k['ry'] * (k['ztop'] - k['z0'])))
    return rocks


def build_rocks(mb, P, cum, rocks, mi, seed, lod, nside=(8, 6), bands=(3, 2), crag=0.13, top_inset=0.74):
    import genlib
    for k in rocks:
        p, t, nn = at_s(P, cum, k['s'])
        c = p + nn * k['u']
        fwd = (t * math.cos(k['rot']) + nn * math.sin(k['rot']))
        M = C.frame((c.x, c.y, 0.0), fwd)
        rr = genlib.rng(seed, 'rock%d' % k['salt'])
        C.crag_rock(mb, M, k['rx'], k['ry'], k['z0'], k['ztop'], mi, rr, nside=C.lod_pick(lod, *nside),
                    bands=C.lod_pick(lod, *bands), crag=crag, top_inset=top_inset)


def rock_envelope(P, cum, rocks, base):
    """per-vertex rim height from the rock layout (for LOD2/3 bands derived from the same rocks)"""
    out = []
    for i in range(len(P)):
        s = cum[i]
        h = base
        for k in rocks:
            d = abs(sdist(cum, s, k['s']))
            if d < k['ry'] * 0.95:
                h = max(h, k['ztop'] - (k['ztop'] - base) * (d / k['ry']) ** 2 * 0.6)
        out.append(h)
    return out


def jitter_z(P, amp, r, freq=1.3):
    off = Vector((r.uniform(0, 50), r.uniform(0, 50), r.uniform(0, 50)))
    return [amp * noise.noise(Vector((p[0] * freq, p[1] * freq, 0)) + off) for p in P]


# ------------------------------------------------------------------------------------------------ steps
def steps(mb, P, cum, s, n, width, z_top, z_bed, tread, mi, lod, embed=0.04, bevel=0.012, mi_side=None):
    """n entry steps going INTO the pool at arc length s: step k (1..n) top at z_top - k*h, reaching
    k*tread in from the wall; boxes rest on the bed. Returns the step tops [(x, y, z)]."""
    p, t, nn = at_s(P, cum, s)
    h = (z_top - z_bed) / (n + 1)
    ang = math.atan2(t.y, t.x)
    tops = []
    for k in range(1, n + 1):
        zt = z_top - k * h
        depth = k * tread + embed
        c = p - nn * (depth / 2 - embed)
        size = (width, depth, zt - z_bed)
        cen = (c.x, c.y, z_bed + size[2] / 2)
        if lod <= 1 and bevel > 0:
            C.board(mb, cen, size, mi, bevel=bevel if lod == 0 else bevel * 0.6, segs=2 if lod == 0 else 1, rot=(0, 0, ang))
        else:
            mb.box(cen, size, mi, rot=(0, 0, ang))
        q = p - nn * (k * tread - tread / 2)
        tops.append((q.x, q.y, zt))
    return tops
