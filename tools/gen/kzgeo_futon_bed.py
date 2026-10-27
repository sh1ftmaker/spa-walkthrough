"""Geometry helpers for gen_futon_bed.

drape: a closed cloth solid laid over a rounded-edged support (mattress, duvet) and hanging over its
sides and, optionally, its foot. A flat sheet grid (sheet coordinates sx, sy) is mapped onto the support:
inside the support it follows top_fn(x, y); past an edge it rolls round an arc of radius rr and falls
straight down. The outer surface uses the same angles with rr + t and top + t, so it is an exact offset:
the hem keeps the full thickness t (no knife edge, GUIDE pitfall 1).
"""
import math

import bmesh
from mathutils import Vector


def _map(e, rr, r):
    """excess e (m of cloth past the edge) -> (outward offset, drop) on an arc then a vertical fall.
    The angle comes from the inner radius rr; r is the radius of this surface (rr inner, rr + t outer)."""
    if e <= 0:
        return 0.0, 0.0
    a = min(e / rr, math.pi / 2)
    straight = max(0.0, e - rr * math.pi / 2)
    return r * math.sin(a), r * (1 - math.cos(a)) + straight


def drape(mb, cx, cy, hw, y_head, y_foot, top_fn, t_fn, mi, nx, ny, hang_x, hang_y=0.0, rr=0.05,
          floor_z=0.0, wrinkle=0.0, wr_freq=9.0, phase=0.0, na=3, nh=2):
    """Cloth over a support with half-width hw (x), lying from y_head (top edge, no hang) to y_foot.
    The foot end hangs hang_y over the edge at y_foot (y_foot < y_head: foot is towards -Y if so).
    hang_x: cloth length hanging past each side edge. top_fn(x, y) -> support top z. t_fn(x, y) -> cloth
    thickness. wrinkle: amplitude (m) of folds on the hanging parts. Returns faces (closed solid)."""
    bm = mb.bm
    fdir = 1.0 if y_foot > y_head else -1.0
    Ltop = abs(y_foot - y_head)
    arc = rr * math.pi / 2
    side = [hw + min(arc, hang_x) * k / na for k in range(1, na + 1)] if hang_x > 0 else []
    if hang_x > arc:
        side += [hw + arc + (hang_x - arc) * k / nh for k in range(1, nh + 1)]
    xs = [-v for v in side[::-1]] + [-hw + 2 * hw * i / nx for i in range(nx + 1)] + side
    ys = [Ltop * j / ny for j in range(ny + 1)]
    if hang_y > 0:
        ys += [Ltop + min(arc, hang_y) * k / na for k in range(1, na + 1)]
        if hang_y > arc:
            ys += [Ltop + arc + (hang_y - arc) * k / nh for k in range(1, nh + 1)]

    def P(sx, sy, outer):
        ex = abs(sx) - hw
        sgx = 1.0 if sx >= 0 else -1.0
        ey = sy - Ltop
        xin = max(-hw, min(hw, sx))
        yin = y_head + fdir * min(sy, Ltop)
        t = t_fn(xin, yin) if outer else 0.0
        top = top_fn(xin, yin) + t
        ox, dx_ = _map(ex, rr, rr + t)
        oy, dy_ = _map(ey, rr, rr + t)
        hang = max(ex, ey, 0.0)
        z = top - max(dx_, dy_)
        x = xin + sgx * ox
        y = yin + fdir * oy
        if wrinkle and hang > 0:
            k = min(1.0, hang / max(rr * 2, 1e-3))
            w = wrinkle * k * (math.sin(wr_freq * (y if ex > 0 else x) + phase) + 0.35 * math.sin(2.3 * wr_freq * (y if ex > 0 else x) + 1.7 * phase))
            if ex > 0 and ex >= ey:
                x += sgx * w
            else:
                y += fdir * w
        z = max(z, floor_z + (t if outer else 0.0) + 0.002)
        return Vector((cx + x, cy + y, z))

    A = [[bm.verts.new(P(sx, sy, False)) for sx in xs] for sy in ys]
    B = [[bm.verts.new(P(sx, sy, True)) for sx in xs] for sy in ys]
    faces = []
    nI, nJ = len(xs), len(ys)
    for j in range(nJ - 1):
        for i in range(nI - 1):
            faces.append(bm.faces.new((A[j][i], A[j + 1][i], A[j + 1][i + 1], A[j][i + 1])))
            faces.append(bm.faces.new((B[j][i], B[j][i + 1], B[j + 1][i + 1], B[j + 1][i])))
    for j in range(nJ - 1):
        for i in (0, nI - 1):
            faces.append(bm.faces.new((A[j][i], B[j][i], B[j + 1][i], A[j + 1][i])))
    for i in range(nI - 1):
        for j in (0, nJ - 1):
            faces.append(bm.faces.new((A[j][i], A[j][i + 1], B[j][i + 1], B[j][i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return faces
