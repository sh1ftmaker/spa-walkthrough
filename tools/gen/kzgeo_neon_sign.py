"""Neon kit (op02): single-line stroke centrelines of CJK / kana glyphs for hand-bent neon tubes.

A neon sign bends ONE tube along each brush stroke, so the glyph outline (what text_solid fills) is the
wrong curve. glyph_strokes() rasterises the glyph (per-contour fill from kzgeo_common, so crossing strokes
stay solid), thins it to a 1 px skeleton (Zhang-Suen), traces the skeleton into polylines (m-adjacency,
junction clusters merged), prunes short spurs, and simplifies (Ramer-Douglas-Peucker). Output is in glyph
units, centred on the glyph box, height 1, x running the SAME way as the font (callers mirror x for +Y).

Deterministic and cached per (char, font, eps). Pure numpy + Blender font curves; no PIL.
"""
import math

import numpy as np

import kzgeo_common as C

FONT_NEON = '/usr/share/fonts/noto-cjk/NotoSansCJK-Medium.ttc'
_cache = {}


def _mask(ch, font, G):
    groups, (x0, y0, x1, y1) = C.glyph_tri_groups(ch, font, res=3)
    s = max(x1 - x0, y1 - y0)
    m = 4
    sc = (G - 2 * m) / s
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    img = np.zeros((G, G), dtype=bool)
    ys, xs = np.mgrid[0:G, 0:G]
    px = (xs + 0.5 - G / 2) / sc + cx          # glyph-space coords of pixel centres (row 0 = top)
    py = (G / 2 - (ys + 0.5)) / sc + cy
    for pts, tris in groups:
        P = np.array(pts)
        for t in tris:
            a, b, c = P[t[0]], P[t[1]], P[t[2]]
            bx0, bx1 = min(a[0], b[0], c[0]), max(a[0], b[0], c[0])
            by0, by1 = min(a[1], b[1], c[1]), max(a[1], b[1], c[1])
            sel = (px >= bx0) & (px <= bx1) & (py >= by0) & (py <= by1)
            if not sel.any():
                continue
            qx, qy = px[sel], py[sel]
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((b[1] - c[1]) * (qx - c[0]) + (c[0] - b[0]) * (qy - c[1])) / d
            l2 = ((c[1] - a[1]) * (qx - c[0]) + (a[0] - c[0]) * (qy - c[1])) / d
            inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l1 + l2 <= 1 + 1e-9)
            sub = img[sel]
            sub |= inside
            img[sel] = sub
    return img, sc, (cx, cy), (x1 - x0, y1 - y0)


def _thin(img):
    """Zhang-Suen thinning"""
    I = np.pad(img.astype(np.uint8), 1)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            P2 = I[:-2, 1:-1]; P3 = I[:-2, 2:]; P4 = I[1:-1, 2:]; P5 = I[2:, 2:]
            P6 = I[2:, 1:-1]; P7 = I[2:, :-2]; P8 = I[1:-1, :-2]; P9 = I[:-2, :-2]
            seq = [P2, P3, P4, P5, P6, P7, P8, P9, P2]
            B = sum(seq[:8])
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            core = I[1:-1, 1:-1] == 1
            if step == 0:
                c1 = (P2 * P4 * P6) == 0; c2 = (P4 * P6 * P8) == 0
            else:
                c1 = (P2 * P4 * P8) == 0; c2 = (P2 * P6 * P8) == 0
            rm = core & (B >= 2) & (B <= 6) & (A == 1) & c1 & c2
            if rm.any():
                I[1:-1, 1:-1][rm] = 0
                changed = True
    return I[1:-1, 1:-1].astype(bool)


N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8D = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _nbrs(P, p):
    """m-adjacency: 4-neighbours, plus diagonals not already reachable through a shared 4-neighbour"""
    r, c = p
    out = [(r + dr, c + dc) for dr, dc in N4 if (r + dr, c + dc) in P]
    for dr, dc in N8D:
        q = (r + dr, c + dc)
        if q in P and (r + dr, c) not in P and (r, c + dc) not in P:
            out.append(q)
    return out


def _rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float)
    ab = b - a
    L = np.hypot(*ab)
    best, bi = -1, 0
    for i in range(1, len(pts) - 1):
        p = np.array(pts[i], float)
        d = abs(ab[0] * (a[1] - p[1]) - ab[1] * (a[0] - p[0])) / L if L > 1e-9 else np.hypot(*(p - a))
        if d > best:
            best, bi = d, i
    if best > eps:
        return _rdp(pts[:bi + 1], eps)[:-1] + _rdp(pts[bi:], eps)
    return [pts[0], pts[-1]]


def _trace(sk):
    P = {(int(r), int(c)) for r, c in zip(*np.nonzero(sk))}
    nb = {p: _nbrs(P, p) for p in P}
    deg = {p: len(v) for p, v in nb.items()}
    nodes = {p for p in P if deg[p] != 2}
    # merge adjacent junction pixels into clusters
    cl = {}
    cid = 0
    for p in nodes:
        if deg[p] >= 3 and p not in cl:
            stack = [p]; cl[p] = cid
            while stack:
                q = stack.pop()
                for w in nb[q]:
                    if w in nodes and deg[w] >= 3 and w not in cl:
                        cl[w] = cid; stack.append(w)
            cid += 1
    cent = {}
    for p, i in cl.items():
        cent.setdefault(i, []).append(p)
    cent = {i: (sum(q[0] for q in v) / len(v), sum(q[1] for q in v) / len(v)) for i, v in cent.items()}
    seen = set()
    paths = []

    def ek(a, b):
        return (a, b) if a < b else (b, a)
    for u in nodes:
        for v in nb[u]:
            if ek(u, v) in seen:
                continue
            path = [u, v]; seen.add(ek(u, v))
            prev, cur = u, v
            while cur not in nodes:
                nxt = [w for w in nb[cur] if w != prev and ek(cur, w) not in seen]
                if not nxt:
                    break
                seen.add(ek(cur, nxt[0]))
                prev, cur = cur, nxt[0]
                path.append(cur)
            a, b = path[0], path[-1]
            if a in cl and b in cl and cl[a] == cl[b] and len(path) <= 3:
                continue
            pts = [cent[cl[a]] if a in cl else a] + path[1:-1] + [cent[cl[b]] if b in cl else b]
            paths.append(dict(pts=pts, end0=deg[a] == 1, end1=deg[b] == 1, j0=cl.get(a), j1=cl.get(b)))
    # closed loops (no node on them)
    rest = {p for p in P if deg[p] == 2 and not any(ek(p, w) in seen for w in nb[p])}
    while rest:
        s = rest.pop()
        path = [s]; prev, cur = None, s
        while True:
            nxt = [w for w in nb[cur] if w != prev and ek(cur, w) not in seen]
            if not nxt:
                break
            seen.add(ek(cur, nxt[0])); prev, cur = cur, nxt[0]
            rest.discard(cur)
            path.append(cur)
            if cur == s:
                break
        if len(path) > 4:
            paths.append(dict(pts=path, end0=False, end1=False, j0=None, j1=None))
    return paths


def glyph_strokes(ch, font=FONT_NEON, G=88, eps=1.0, spur=0.09):
    """list of polylines [(x, y)] in glyph units (larger side of the glyph box = 1, centred), plus the aspect w/h"""
    key = (ch, font, G, eps, spur)
    if key in _cache:
        return _cache[key]
    img, sc, (cx, cy), (gw, gh) = _mask(ch, font, G)
    sk = _thin(img)
    paths = _trace(sk)
    lim = spur * G
    keep = []
    for p in paths:
        n = len(p['pts'])
        spur_ = (p['end0'] and p['j1'] is not None) or (p['end1'] and p['j0'] is not None)
        if spur_ and n < lim:
            continue
        if n < 3 and not (p['j0'] is None and p['j1'] is None):
            continue
        keep.append(p)
    hpx = max(gw, gh) * sc         # unit box = the glyph's larger side (keeps ー a dash, not a bar)
    out = []
    for p in keep:
        pts = _rdp([(float(c), float(r)) for r, c in p['pts']], eps)
        # pixel (col, row) -> glyph units centred on the box, height 1
        out.append([((x + 0.5 - G / 2) / hpx, (G / 2 - (y + 0.5)) / hpx) for x, y in pts])
    res = (out, gw / gh)
    _cache[key] = res
    return res


def rounded_rect(w, h, r, n_corner):
    """closed polyline of a rounded rectangle centred at 0 (x, z)"""
    pts = []
    for (cx, cz, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n_corner + 1):
            a = math.radians(a0 + 90 * k / n_corner)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts
