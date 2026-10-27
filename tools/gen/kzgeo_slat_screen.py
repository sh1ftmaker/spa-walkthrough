"""Geometry for slat_screen: a run of close vertical hinoki slats on back rails between posts.

`screen_into(mb, mats, lod, P)` builds the run along x (centred on x = 0), its slat face towards +y, on z = 0.
Construction per bay (between two posts): two or three horizontal back rails (nuki) set behind the slats, the
slats nailed on their front, a bottom rail (or a stone-free sill) and either a top rail ('partition') or a wider
kasagi cap board ('fence') that covers the slat ends.  Gate gaps get their own jamb posts and stay open.
LOD0 octagonal (chamfered) slats without hidden end caps; LOD1 4-sided slats; LOD2 one infill slab per bay
between the same rails and posts; LOD3 one slab per bay including the posts' footprint.
"""
import math

import bmesh

import kzgeo_common as C


def _oct_open(mb, cx, cy, w, t, z0, z1, mi, ch):
    """8-sided slat without end caps (both ends are hidden under rails)"""
    bm = mb.bm
    pts = [(-w / 2 + ch, -t / 2), (w / 2 - ch, -t / 2), (w / 2, -t / 2 + ch), (w / 2, t / 2 - ch),
           (w / 2 - ch, t / 2), (-w / 2 + ch, t / 2), (-w / 2, t / 2 - ch), (-w / 2, -t / 2 + ch)]
    A = [bm.verts.new((cx + x, cy + y, z0)) for x, y in pts]
    B = [bm.verts.new((cx + x, cy + y, z1)) for x, y in pts]
    fs = C.bridge_rings(bm, A, B)
    mb._tag(fs, mi)
    return fs


def _quad_open(mb, cx, cy, w, t, z0, z1, mi):
    bm = mb.bm
    pts = [(-w / 2, -t / 2), (w / 2, -t / 2), (w / 2, t / 2), (-w / 2, t / 2)]
    A = [bm.verts.new((cx + x, cy + y, z0)) for x, y in pts]
    B = [bm.verts.new((cx + x, cy + y, z1)) for x, y in pts]
    fs = C.bridge_rings(bm, A, B)
    mb._tag(fs, mi)
    return fs


def _box_nobottom(mb, c, s, mi):
    """box without its bottom face (posts and slabs standing on the ground)"""
    fs = mb.box(c, s, mi)
    dead = [f for f in fs if f.normal.z < -0.9]
    bmesh.ops.delete(mb.bm, geom=dead, context='FACES_ONLY')


def layout(P):
    """post x positions and the bays between them (gate bays flagged)"""
    L = P['length']
    x0, x1 = -L / 2, L / 2
    cuts = [x0, x1]
    gate = P.get('gate')
    if gate:
        gx, gw = gate['x'], gate['w']
        cuts += [gx - gw / 2, gx + gw / 2]
    cuts = sorted(cuts)
    posts = []
    bays = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        is_gate = bool(gate) and abs((a + b) / 2 - gate['x']) < 1e-6 + gate['w'] / 2 and (b - a) <= gate['w'] + 1e-6
        if is_gate:
            bays.append((a, b, True))
            continue
        n = max(1, math.ceil((b - a) / P['post_sp'] - 0.15))
        for k in range(n):
            bays.append((a + (b - a) * k / n, a + (b - a) * (k + 1) / n, False))
    for a, b, g in bays:
        posts += [a, b]
    posts = sorted(set(round(p, 5) for p in posts))
    return posts, bays


def screen_into(mb, mats, lod, P):
    wood, post_mi = mats['slat'], mats['post']
    H, pw, st, sw, gap = P['h'], P['post_w'], P['slat_t'], P['slat_w'], P['gap']
    posts, bays = layout(P)
    style = P['style']
    rail_h, rail_t = 0.06, 0.045
    y_rail = -rail_t / 2 - 0.004                      # back rails sit behind the slat plane
    y_slat = st / 2
    z_bot = P['clear']                                # slats start above a small floor gap
    z_top = H - (P['cap_t'] if style == 'fence' else 0.0)
    ph = H + (0.03 if style == 'fence' else 0.0)      # posts stand a touch proud under a cap
    # posts
    for x in posts:
        x = max(-P['length'] / 2 + pw / 2, min(P['length'] / 2 - pw / 2, x))
        if lod <= 1:
            if lod == 0:
                C.chamfered_bar(mb, (x, 0, ph / 2), (pw, pw, ph), post_mi, ch=0.008)
            else:
                _box_nobottom(mb, (x, 0, ph / 2), (pw, pw, ph), post_mi)
        elif lod == 2:
            _box_nobottom(mb, (x, 0, ph / 2), (pw, pw, ph), post_mi)
    for a, b, is_gate in bays:
        if is_gate:
            continue
        xa, xb = a + pw / 2, b - pw / 2
        if lod == 3:
            _box_nobottom(mb, ((a + b) / 2, 0, H / 2), (b - a, max(pw, st + rail_t), H), wood)
            continue
        if lod == 2:
            # one infill slab from the floor to the top rail / cap (sill and back rails merged into it)
            _box_nobottom(mb, ((xa + xb) / 2, y_slat - 0.01, z_top / 2), (xb - xa, st + 0.02, z_top), wood)
        # back rails (nuki) behind the slats, through the posts
        nr = P['rails'] if lod <= 1 else 0
        for k in range(nr):
            z = z_bot + 0.12 + (z_top - z_bot - 0.24) * k / max(1, nr - 1)
            if lod <= 1 or k in (0, nr - 1):
                mb.box(((xa + xb) / 2, y_rail, z), (xb - xa, rail_t, rail_h), post_mi)
        # bottom rail / sill under the slats
        if lod <= 1:
            mb.box(((xa + xb) / 2, 0, z_bot / 2 + 0.004), (xb - xa, max(st + 0.02, rail_t), z_bot + 0.008), post_mi)
        # top: rail (partition) or kasagi cap (fence) covering the slat ends
        if style == 'fence':
            cap_w = max(pw, st + rail_t) + 0.05
            if lod == 0:
                C.board(mb, ((a + b) / 2, -0.004, H - P['cap_t'] / 2 + 0.03), (b - a + 0.04, cap_w, P['cap_t']), post_mi,
                        bevel=0.006, segs=1)
            else:
                mb.box(((a + b) / 2, -0.004, H - P['cap_t'] / 2 + 0.03), (b - a + 0.04, cap_w, P['cap_t']), post_mi)
        else:
            mb.box(((xa + xb) / 2, 0.0, H - 0.035), (xb - xa, st + 0.03, 0.07), post_mi)
            z_top = H - 0.07
        if lod == 2:
            continue
        # slats
        n = max(2, round((xb - xa + gap) / (sw + gap)))
        gg = (xb - xa - n * sw) / max(1, n - 1)
        for k in range(n):
            x = xa + sw / 2 + k * (sw + gg)
            if lod == 0:
                _oct_open(mb, x, y_slat, sw, st, z_bot, z_top, wood, ch=min(0.004, st * 0.2))
            else:
                _quad_open(mb, x, y_slat, sw, st, z_bot, z_top, wood)
    return posts, bays
