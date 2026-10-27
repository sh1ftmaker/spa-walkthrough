"""Geometry helpers for gen_zabuton_cushion: a closed square cushion with a rolled edge (never a knife
edge), a domed top, a tufted centre dimple and an optional border ring for two-colour tops.

The top is built from rings scaled from the outline (s = 0 centre .. 1 edge), like kzgeo_common.pillow,
with extra rings for the tuft dimple and the border seam.
"""
import math


def outline_sq(W, D, rc, m):
    """counter-clockwise rounded rectangle; m = 0 gives the plain 4-corner square"""
    if m == 0:
        return [(W / 2, D / 2), (-W / 2, D / 2), (-W / 2, -D / 2), (W / 2, -D / 2)]
    pts = []
    rc = min(rc, W / 2 - 1e-4, D / 2 - 1e-4)
    for cx, cy, a0 in ((W / 2 - rc, D / 2 - rc, 0.0), (-W / 2 + rc, D / 2 - rc, math.pi / 2),
                       (-W / 2 + rc, -D / 2 + rc, math.pi), (W / 2 - rc, -D / 2 + rc, 1.5 * math.pi)):
        for k in range(m + 1):
            a = a0 + (math.pi / 2) * k / m
            pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    return pts


def cushion(mb, W, D, T, mi_top, mi_side, m=2, rc=0.05, puff=0.012, edge_k=0.4, edge_w=0.03,
            tuft_r=0.0, tuft_d=0.0, border_s=None, mi_border=None, bottom_k=1.0, yaw=0.0, top_rings=None, tuft_ring=True, edge_mid=False):
    """Closed cushion on z = 0. Thickness T at the shoulder (s_sh), rolling to edge_k*T at the outline.
    The top domes by `puff` towards the centre; a tuft dimple of radius tuft_r (m) sinks tuft_d at s=0.
    border_s: the faces from that ring out to the shoulder take mi_border (a border band in another
    colour). top_rings: extra s values for smoothness. Returns faces."""
    bm = mb.bm
    out = outline_sq(W, D, rc, m)
    c_, s_ = math.cos(yaw), math.sin(yaw)
    out = [(x * c_ - y * s_, x * s_ + y * c_) for x, y in out]
    half = min(W, D) / 2
    s_sh = 1.0 - edge_w / half
    s_tf = (tuft_r / half) if tuft_r > 0 else None

    def top(s):
        if s <= s_sh:
            z = T + puff * (1 - (s / s_sh) ** 2)
        else:
            u = (s - s_sh) / (1 - s_sh)
            z = T * (0.5 + 0.5 * (edge_k + (1 - edge_k) * math.cos(math.pi / 2 * u)))
        if s_tf:
            z -= tuft_d * max(0.0, 1 - (s / s_tf)) ** 1.5
        return z

    def ring(s, z_of):
        return [bm.verts.new((x * s, y * s, z_of(s))) for x, y in out]
    ss = sorted(set([x for x in ([s_tf] if s_tf and tuft_ring else []) + ([border_s] if border_s else []) + (top_rings or [])
                     if x and 0 < x < s_sh] + [s_sh]))
    chain = [[bm.verts.new((0, 0, top(0.0)))]]
    tags = []
    for s in ss:
        chain.append(ring(s, top)); tags.append('top')
    if edge_mid:                                 # extra ring half-way round the roll: a round, not bevelled, edge
        chain.append(ring(s_sh + 0.55 * (1 - s_sh), top)); tags.append('edge')
    chain.append(ring(1.0, top)); tags.append('edge')
    zb = T * 0.5 * (1 - edge_k) * bottom_k       # lower lip of the rolled edge (bottom_k < 1: flatter base)
    chain.append(ring(1.0, lambda s: zb)); tags.append('side')
    chain.append(ring(s_sh, lambda s: 0.0)); tags.append('side')
    chain.append([bm.verts.new((0, 0, 0.0))]); tags.append('side')
    faces = []
    s_vals = [0.0] + ss + ([s_sh + 0.55 * (1 - s_sh)] if edge_mid else []) + [1.0]
    for i, (A, B) in enumerate(zip(chain[:-1], chain[1:])):
        n = max(len(A), len(B))
        mi = mi_top
        if tags[i] == 'side':
            mi = mi_side
        elif tags[i] == 'edge':
            mi = mi_top if mi_border is None else mi_border
        elif border_s and i < len(s_vals) and s_vals[i] >= border_s - 1e-6 and mi_border is not None:
            mi = mi_border
        fs = []
        for k in range(n):
            if len(A) == 1:
                cand = (A[0], B[(k + 1) % n], B[k])
            elif len(B) == 1:
                cand = (A[k], A[(k + 1) % n], B[0])
            else:
                cand = (A[k], A[(k + 1) % n], B[(k + 1) % n], B[k])
            fs.append(bm.faces.new(cand))
        mb._tag(fs, mi)
        faces += fs
    return faces
