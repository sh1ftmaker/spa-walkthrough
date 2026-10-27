"""Geometry helpers for gen_suite_module: tatami floor, veranda deck, rail, shoji bays, rock masses.
All in world coordinates (metres, front +Y, z = 0 base). Every helper takes `lod` and keeps the same
layout at every LOD, changing only resolution and small parts."""
import math

from mathutils import Matrix, Vector

import kzgeo_common as C
import kzgeo_shoji_panel as KS


def tatami_floor(mb, x0, x1, y0, y1, z_top, m_mat, m_heri, lod, gap=0.012):
    """tatami mats (0.91 x 1.82) in a running bond, 55 mm thick on a dark sub-floor (the gaps read as the
    dark heri borders). LOD2+: one slab with the mat grid as dark strips."""
    T = 0.055
    W, D = x1 - x0, y1 - y0
    if lod >= 2:
        mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z_top - T / 2), (W, D, T), m_mat)
        return
    nrow = max(1, round(D / 0.91))
    rh = D / nrow
    for j in range(nrow):
        ya, yb = y0 + j * rh, y0 + (j + 1) * rh
        n = max(1, round(W / 1.82))
        L = W / n
        off = (L / 2) if j % 2 else 0.0
        xs = sorted({x0, x1} | {x0 + off + k * L for k in range(-1, n + 1) if x0 + 0.05 < x0 + off + k * L < x1 - 0.05})
        for a, b in zip(xs[:-1], xs[1:]):
            mb.box(((a + b) / 2, (ya + yb) / 2, z_top - T / 2), (b - a - gap, rh - gap, T), m_mat)
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z_top - T - 0.005), (W, D, 0.01), m_heri)


def deck(mb, x0, x1, y0, y1, z_top, m_board, lod, board_w=0.14, gap=0.008):
    """deck boards running along X (long side of the veranda), 35 mm thick"""
    T = 0.035
    if lod >= 2:
        mb.box(((x0 + x1) / 2, (y0 + y1) / 2, z_top - T / 2), (x1 - x0, y1 - y0, T), m_board)
        return
    n = max(1, round((y1 - y0) / board_w))
    bw = (y1 - y0) / n
    for k in range(n):
        yc = y0 + bw * (k + 0.5)
        if lod == 0:
            C.board(mb, ((x0 + x1) / 2, yc, z_top - T / 2), (x1 - x0, bw - gap, T), m_board, bevel=0.004, segs=1)
        else:
            mb.box(((x0 + x1) / 2, yc, z_top - T / 2), (x1 - x0, bw - gap, T), m_board)


def rail(mb, pts, z0, m_post, m_top, lod, h=0.9, post_pitch=1.8, open_last=False):
    """veranda rail along a polyline of plan points: square posts, a mid rail and a capped top rail (kasagi)"""
    pts = [Vector((p[0], p[1], 0)) for p in pts]
    bev = C.lod_pick(lod, 0.006, 0.0, 0.0)
    for a, b in zip(pts[:-1], pts[1:]):
        d = b - a
        L = d.length
        ang = math.atan2(d.y, d.x)
        n = max(1, round(L / post_pitch))
        for k in range(n + 1):
            p = a + d * (k / n)
            if lod <= 2:
                if bev:
                    C.chamfered_bar(mb, (p.x, p.y, z0 + h / 2), (0.1, 0.1, h), m_post, ch=0.008, axis='z')
                else:
                    mb.box((p.x, p.y, z0 + h / 2), (0.1, 0.1, h), m_post)
        mid = (a + b) / 2
        # top rail (kasagi) and mid rail
        if lod <= 2:
            C.board(mb, (mid.x, mid.y, z0 + h + 0.025), (L + 0.14, 0.13, 0.05), m_top, bevel=bev, segs=1, rot=(0, 0, ang))
        if lod <= 1:
            mb.box((mid.x, mid.y, z0 + h * 0.45), (L, 0.05, 0.04), m_post, rot=(0, 0, ang))
            mb.box((mid.x, mid.y, z0 + 0.08), (L, 0.05, 0.05), m_post, rot=(0, 0, ang))


def shoji_bay(mb, x0, x1, z0, z1, y, mats, lod, P, state='closed', flip=False):
    """one bay of two sliding shoji between posts on the plane y (panels face +Y). state: closed | open
    (both panels stacked behind one post) | half. Returns lit rects for kz_lights."""
    W = (x1 - x0) / 2 + 0.015
    H = z1 - z0
    lit = []
    if state == 'closed':
        xs = [(x0 + W / 2 - 0.0075, y - 0.02), (x1 - W / 2 + 0.0075, y + 0.02)]
    elif state == 'half':
        xs = [(x0 + W / 2, y - 0.02), (x0 + W / 2 + W * 0.45, y + 0.02)]
    else:
        e = x1 if flip else x0
        s = -1 if flip else 1
        xs = [(e + s * W / 2, y - 0.02), (e + s * (W / 2 + 0.06), y + 0.02)]
    plod = {0: 0, 1: 2, 2: 3}[lod]
    for cx, cy in xs:
        M = Matrix.Translation((cx, cy, z0))
        for a, b, za, zb in KS.panel_into(mb, M, W, H, 'shoji', mats, plod, P):
            lit.append((cx + a, cx + b, z0 + za, z0 + zb, cy))
    return lit


def rock_slab(mb, cx, cy, rx, ry, z_top, thick, mi, r, lod, under=True):
    """an overhang slab of rock: a craggy mass hanging from z_top down by `thick` (flat-ish lumpy underside).
    Built as C.crag_rock in a frame whose local up points down, so the rock's 'top' is the underside."""
    M = C.frame((cx, cy, z_top), (0, 1, 0), up=(0, 0, -1))
    nside = C.lod_pick(lod, 11, 8, 6, 5)
    bands = C.lod_pick(lod, 3, 2, 1, 1)
    # local z = 0 at z_top, ztop = thick (downwards in world)
    return C.crag_rock(mb, M, rx, ry, 0.0, thick, mi, r, nside=nside, bands=bands, tilt=0.08, crag=0.24,
                       top_inset=0.88, bottom=True)        # closed: its flat top is seen from upper tiers


def rock_mass(mb, cx, cy, rx, ry, z0, z1, mi, r, lod, inset=0.78):
    nside = C.lod_pick(lod, 10, 8, 6, 5)
    bands = C.lod_pick(lod, 3, 2, 1, 1)
    return C.crag_rock(mb, C.frame((cx, cy, 0), (0, 1, 0)), rx, ry, z0, z1, mi, r, nside=nside, bands=bands,
                       tilt=0.03, crag=0.14, top_inset=inset, bottom=False)
