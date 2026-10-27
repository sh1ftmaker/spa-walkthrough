"""Geometry for gen_seat_block_carved: a hewn stone block (closed loft of noisy rounded rectangles), carving
line layouts (concept wave with a central curl; seigaiha scales with occlusion) and relief ridges."""
import math

from mathutils import Vector, noise

import kzgeo_common as C


def perimeter(W, D, rc, step, m=2):
    """counter-clockwise rounded-rectangle outline with the straight runs subdivided every ~`step` m.
    Returns [(x, y, nx, ny, kind)] where kind is 'front' on the +Y face run, else 'side'."""
    rc = max(0.005, min(rc, W / 2 - 0.01, D / 2 - 0.01))
    out = []
    corners = [(W / 2 - rc, D / 2 - rc, 0.0), (-W / 2 + rc, D / 2 - rc, math.pi / 2),
               (-W / 2 + rc, -D / 2 + rc, math.pi), (W / 2 - rc, -D / 2 + rc, 1.5 * math.pi)]
    for ci, (cx, cy, a0) in enumerate(corners):
        for k in range(m + 1):
            a = a0 + (math.pi / 2) * k / m
            out.append((cx + rc * math.cos(a), cy + rc * math.sin(a), math.cos(a), math.sin(a), 'side'))
        # straight run to the next corner
        nx_, ny_, _ = corners[(ci + 1) % 4]
        a_end = a0 + math.pi / 2
        p0 = (cx + rc * math.cos(a_end), cy + rc * math.sin(a_end))
        p1 = (nx_ + rc * math.cos(a_end), ny_ + rc * math.sin(a_end))
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = max(1, round(L / step))
        kind = 'front' if ci == 0 else 'side'          # corner 0 -> 1 runs along +Y
        for k in range(1, n):
            t = k / n
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, math.cos(a_end), math.sin(a_end), kind))
    return out


def hewn_block(mb, W, D, H, z0, mi, seed, lod, amp=0.007, amp_front=0.0025, top_inset=0.03, rc=0.04):
    """Closed hewn block: rings of the noisy outline from z0 to z0 + H, a chamfered foot, a rounded top
    shoulder (two rings) and a flat top cap. Smooth 3D noise (no per-vertex jitter); the +Y face is kept
    near-flat (amp_front) so the carving sits on it."""
    bm = mb.bm
    step = C.lod_pick(lod, 0.16, 0.32, 10.0, 10.0)
    m = C.lod_pick(lod, 2, 1, 1, 0)
    if m == 0:
        outline = [(W / 2, D / 2, 0.7, 0.7, 'side'), (-W / 2, D / 2, -0.7, 0.7, 'side'), (-W / 2, -D / 2, -0.7, -0.7, 'side'),
                   (W / 2, -D / 2, 0.7, -0.7, 'side')]
    else:
        outline = perimeter(W, D, rc, step, m)
    if lod == 0:
        rings = [(0.012, 0.0), (0.0, 0.015), (0.0, 0.5 * H), (0.0, H - 0.04), (0.012, H - 0.01), (top_inset, H)]
    elif lod == 1:
        rings = [(0.0, 0.0), (0.0, 0.5 * H), (0.0, H - 0.03), (top_inset, H)]
    elif lod == 2:
        rings = [(0.0, 0.0), (0.0, H - 0.025), (top_inset, H)]
    else:
        rings = [(0.0, 0.0), (0.0, H)]
    off = Vector((seed * 7.31, seed * 3.17, seed * 1.93))
    R = []
    for inset, z in rings:
        ring = []
        for x, y, nx, ny, kind in outline:
            a = amp_front if kind == 'front' else amp
            p = Vector((x, y, z0 + z))
            d = noise.noise(p * 3.2 + off) * a + noise.noise(p * 9.0 + off) * a * 0.35 if lod <= 1 else 0.0
            if z == H:
                d *= 1.6                                   # chipped top arrises
            ring.append(bm.verts.new((x - nx * (inset - d), y - ny * (inset - d), z0 + z)))
        R.append(ring)
    faces = []
    for A, B in zip(R[:-1], R[1:]):
        faces += C.bridge_rings(bm, A, B)
    if lod < 3:
        faces.append(bm.faces.new(R[0][::-1]))
    faces.append(bm.faces.new(R[-1]))
    mb._tag(faces, mi)
    return faces


# ------------------------------------------------------------------------------------------ carving layouts
def wave_lines(pw, ph, nlines, curl_r, flip, lod):
    """Concept-14 wave relief on a pw x ph panel centred at (0, 0) in face coords (u = across, v = up):
    `nlines` parallel swells that break around a central curl (a 2-turn spiral). Returns polylines [(u, v)]."""
    npts = C.lod_pick(lod, 26, 11, 7, 5)
    lam = pw * 0.62
    A = ph * 0.11
    sp = ph * 0.86 / max(1, nlines - 1)
    lines = []
    for k in range(nlines):
        v0 = -ph * 0.43 + k * sp
        cur = []
        for i in range(npts):
            u = -pw / 2 + pw * i / (npts - 1)
            v = v0 + A * math.sin(2 * math.pi * u / lam + 0.6 + 0.35 * k) * (1.0 - 0.25 * abs(u) / (pw / 2))
            if math.hypot(u, v) < curl_r * 1.25:      # break around the curl
                if len(cur) > 1:
                    lines.append(cur)
                cur = []
                continue
            cur.append((u * flip, v))
        if len(cur) > 1:
            lines.append(cur)
    if lod <= 2:
        n = C.lod_pick(lod, 40, 18, 8)
        turns = 2.6 if lod <= 1 else 1.4
        sp_ = [(curl_r * (0.18 + 0.82 * t) * math.cos(-turns * 2 * math.pi * t + 1.2) * flip,
                curl_r * (0.18 + 0.82 * t) * math.sin(-turns * 2 * math.pi * t + 1.2)) for t in [i / (n - 1) for i in range(n)]]
        lines.append(sp_)
    return lines


def seigaiha_lines(pw, ph, R, lod):
    """Seigaiha scales on a pw x ph panel: rows of concentric semicircles (outer + inner arc; LOD0 also a
    third), each row offset by R and stepped R/2 up; arcs hidden behind the scales of the row below are
    removed. Returns polylines [(u, v)] in face coords."""
    arcs = C.lod_pick(lod, (1.0, 0.66, 0.34), (1.0, 0.6), (1.0,), (1.0,))
    nseg = C.lod_pick(lod, 12, 6, 4, 3)
    rows = []
    v = -ph / 2 + R * 0.5
    j = 0
    while v + R * 0.95 <= ph / 2 + 1e-6:
        cs = []
        u = -pw / 2 + (R if j % 2 else 0.0) + R
        while u <= pw / 2 - R + 1e-6:
            cs.append((u, v))
            u += 2 * R
        rows.append(cs)
        v += R / 2
        j += 1
    lines = []
    for ri, cs in enumerate(rows):
        front = rows[ri - 1] if ri > 0 else []           # the row below is in front
        for cu, cv in cs:
            for f in arcs:
                cur = []
                for i in range(nseg + 1):
                    a = math.pi * i / nseg
                    p = (cu + f * R * math.cos(a), cv + f * R * math.sin(a))
                    hidden = any(math.hypot(p[0] - fu, p[1] - fv) < R * 0.98 and p[1] > fv - 1e-6 for fu, fv in front)
                    if hidden:
                        if len(cur) > 1:
                            lines.append(cur)
                        cur = []
                    else:
                        cur.append(p)
                if len(cur) > 1:
                    lines.append(cur)
    return lines


def ridges(mb, lines, origin, y_face, mi, lod, w=0.022, h=0.007):
    """Relief ridges along face polylines on the +Y face (u -> world -X so the design is not mirrored,
    v -> world Z). LOD0-1: a V-ridge (triangle section) sunk 5 mm into the stone; LOD2-3: flat ribbons
    2 mm proud (single-sided)."""
    ox, oz = origin
    up = Vector((0, 1, 0))
    for L in lines:
        pts = [Vector((ox - u, y_face, oz + v)) for u, v in L]
        if len(pts) < 2:
            continue
        if lod <= 1:
            prof = [(-w / 2, -0.005), (w / 2, -0.005), (0.0, h)]
            C.sweep(mb, pts, prof, mi, up=up)
        else:
            bm = mb.bm
            A, B = [], []
            for i, p in enumerate(pts):
                t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
                s = t.cross(up).normalized() * (w * 0.75)
                A.append(bm.verts.new(p + s + up * 0.002)); B.append(bm.verts.new(p - s + up * 0.002))
            fs = [bm.faces.new((A[i], B[i], B[i + 1], A[i + 1])) for i in range(len(pts) - 1)]
            mb._tag(fs, mi)
