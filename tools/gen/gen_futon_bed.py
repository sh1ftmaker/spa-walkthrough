"""Futon bedding (futon_bed) for the cliff suites suite_1a..suite_4c: low thick white futon with pillows
and a dark throw, laid on the tatami (the suite floor supplies the tatami).

Targets (measured before coding)
  * lookbook 21 (private suite, bed at left): a double futon ~2.2 m wide (pillows ~0.65 m each, two side by
    side fill the width), white mattress + puffy duvet ~0.18-0.22 m thick over a thin dark base (~0.06-0.08 m,
    with a shadow-line plinth); duvet rolls over the side and foot edges almost to the base; a dark brown
    throw ~0.6-0.75 m wide lies across the lower half and hangs over the side nearly to the base; two big
    white pillows at the head, a small dark cushion in front of them. Total height ~0.3 m (row).
  * lookbook 32 (suite plan, 38 px/m): futon ~2.0 x 2.3 m in plan, two pillows across the head, a tea tray
    on the foot half (tray is tableware, not built here).
  Built: w 1.6-2.2 (double) / 2 x 0.95-1.0 (twin), l 2.0-2.4, mattress 0.08-0.13, duvet 0.05-0.07,
  base 0.08, h <= 0.31.

Construction (head at -Y, foot at +Y; pivot at the base centre)
  * shikibuton: C.pillow slab (rolled edge, no knife edge), `linen`.
  * kakebuton (duvet): kzgeo_futon_bed.drape over the mattress, rolling over both sides and the foot, puffy
    (thicker on the centre line), `linen`.
  * throw: a second drape across the lower half, hanging over both sides with seeded folds, `noren` black.
  * pillows: C.pillow, 0.6 x 0.4 m, puffed, `linen`; accent cushion `noren` black.
  * base (style platform): walnut board on an inset plinth (shadow line), `hinoki` walnut.
  LOD1: coarser cloth grids, 1-seg corners. LOD2: 3-4 column cloth, all parts kept. LOD3: boxes: base,
  body, pillow row, throw band (~50 tris).
Animation: none. Lighting: lightmap.

Parameters (build kwargs; proxy 2.2 x 2.4 x 0.3 m)
  style      platform | twin | stacked   (default cycles with the seed: 1 platform, 2 twin, 3 stacked)
  w          1.6-2.2 m overall width     l  2.0-2.4 m length
  thickness  mattress thickness 0.08-0.13 m
  pillows    1-3 (double) / 1 per futon (twin)
  throw      True | False                (default True on seeds 1-3, seeded after)
Seeds change: style (dark base / two separate single futons / two stacked mattresses with a folded throw),
width, length, mattress thickness, pillow count, throw width and position, fold phase, accent cushion.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_futon_bed as K

ASSET = 'futon_bed'
FEATURES = ['low thick white futon', 'pillows at the head', 'dark throw', 'on tatami (low base)']
STYLES = ['platform', 'twin', 'stacked']


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _cloth_len(V, rr):
    """cloth length past an edge that rolls round radius rr and falls to V below the top"""
    return rr * math.pi / 2 + max(0.0, V - rr)


def build(lod, seed, style=None, w=None, l=None, thickness=None, pillows=None, throw=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'dims')
    W = _clamp(w, 1.6, 2.2) if w else (g.uniform(1.95, 2.1) if style == 'twin' else g.uniform(1.6, 2.2))
    L = _clamp(l, 2.0, 2.4) if l else g.uniform(2.05, 2.35)
    TM = _clamp(thickness, 0.08, 0.13) if thickness else g.uniform(0.09, 0.115)
    TD = g.uniform(0.05, 0.065)
    gp = C.rng(seed, 'pillows')
    if style == 'twin':
        npil = 1
    else:
        npil = int(_clamp(pillows, 1, 3)) if pillows else gp.choice([2, 2, 3] if W > 1.8 else [1, 2])
    accent = gp.random() < 0.7
    gt = C.rng(seed, 'throw')
    has_throw = throw if throw is not None else (True if seed <= 3 else gt.random() < 0.75)
    tw = gt.uniform(0.55, 0.75)
    tpos = gt.uniform(0.18, 0.32)            # throw centre, fraction of L from the foot
    tphase = gt.uniform(0, 6.28)
    throw_side = gt.choice([0, 1])           # twin: which futon carries the throw

    mb = genlib.MeshBuilder()
    m_cloth = mb.slot('linen')
    m_throw = mb.slot('noren', variant='black')
    m_base = mb.slot('hinoki', variant='walnut')

    base_h = 0.06 if style == 'platform' else 0.0
    units = [(0.0, W)]
    if style == 'twin':
        units = [(-W / 4 - 0.01, W / 2 - 0.06), (W / 4 + 0.01, W / 2 - 0.06)]
    pil_zone = 0.55

    if lod == 3:
        if base_h:
            mb.box((0, 0, base_h / 2), (W + 0.08, L + 0.08, base_h), m_base)
        for i, (cx, wu) in enumerate(units):
            hb = TM * (1.24 if style == 'stacked' else 1) + TD * 0.8
            mb.box((cx, 0, base_h + hb / 2), (wu, L, hb), m_cloth)
            mb.box((cx, -L / 2 + 0.25, base_h + hb + 0.035), (wu * 0.9, 0.38, 0.07), m_cloth)
            if has_throw and (style != 'twin' or i == throw_side):
                yc = L / 2 - tpos * L
                mb.box((cx, yc, base_h + hb / 2 + 0.008), (wu + 0.03, tw, hb + 0.016), m_throw)
        C.centre_base(mb)
        return genlib.finish(mb.to_object(ASSET))

    # base: walnut board on an inset plinth (shadow line)
    if base_h:
        bev = C.lod_pick(lod, 0.008, 0.005, 0.0)
        C.board(mb, (0, 0, 0.03 + 0.025), (W + 0.08, L + 0.08, 0.05), m_base, bevel=bev, segs=C.lod_pick(lod, 2, 1))
        C.board(mb, (0, 0, 0.0165), (W - 0.12, L - 0.12, 0.033), m_base, bevel=0.0)

    m_corner = C.lod_pick(lod, 2, 1, 1)
    nx, ny, na, nh = C.lod_pick(lod, (12, 6, 3, 2), (6, 3, 2, 1), (2, 1, 1, 1))
    if style == 'twin':
        nx, ny = (max(2, nx * 2 // 3), max(2, ny * 5 // 6)) if lod < 2 else (1, 1)
    for i, (cx, wu) in enumerate(units):
        z = base_h
        layers = 2 if style == 'stacked' else 1
        tl = TM * (0.62 if layers == 2 else 1.0)
        for k in range(layers):
            off = (0.025 * (1 if k else 0), 0.02 * (1 if k else 0))
            if lod == 2:
                mb.box((cx + off[0], off[1], z + tl / 2), (wu - 0.03 * k, L - 0.03 * k, tl), m_cloth)   # hidden under the duvet
            else:
                C.pillow(mb, (cx + off[0], off[1], z), wu - 0.03 * k, L - 0.03 * k, tl, m_cloth, rc=0.07, m=m_corner,
                         puff=0.005, edge_w=0.02, edge_k=0.55)
            z += tl
        zt = z + 0.004
        hw = (wu - 0.03 * (layers - 1)) / 2
        hang = _cloth_len(zt - base_h - 0.012, 0.045)

        def t_duv(x, y, hw=hw):
            u = min(1.0, abs(x) / hw)
            v = min(1.0, abs(y - L * 0.1) / (L * 0.5))
            return TD * (0.5 + 0.5 * (1 - u * u) * (1 - 0.4 * v * v)) + 0.004 * math.sin(9.0 * x + 2.0 * tphase) * (1 - u)

        y_head = -L / 2 + pil_zone
        K.drape(mb, cx, 0.0, hw, y_head, L / 2, lambda x, y, zt=zt: zt, t_duv, m_cloth, nx, ny, hang, hang_y=hang,
                rr=0.045, floor_z=base_h, wrinkle=0.006 if lod == 0 else 0.0, wr_freq=7.0, phase=tphase, na=na, nh=nh)
        # pillows at the head
        n = npil
        pw = min(0.62, (wu - 0.12) / n) if n > 1 else min(0.66, wu * 0.6)
        for p in range(n):
            px = cx + (p - (n - 1) / 2) * (pw + 0.03)
            yaw, tilt = gp.uniform(-0.06, 0.06), math.radians(gp.uniform(-3, 3))
            if lod == 2:
                C.slab(mb, (px, -L / 2 + 0.26, zt + 0.04), pw, 0.40, 0.08, m_cloth, rc=0.07, m=1)
            else:
                C.pillow(mb, (px, -L / 2 + 0.26, zt - 0.004), pw, 0.40, 0.075, m_cloth, rc=0.07, m=m_corner, puff=0.025,
                         edge_w=0.03, edge_k=0.45, yaw=yaw, tilt=tilt)
        if accent and lod <= 1 and style != 'twin':
            C.pillow(mb, (cx + gp.uniform(-0.25, 0.25), -L / 2 + 0.47, zt + 0.004), 0.40, 0.26, 0.05, m_throw,
                     rc=0.06, m=m_corner, puff=0.018, edge_w=0.02, yaw=gp.uniform(-0.2, 0.2))
        # throw
        if has_throw and (style != 'twin' or i == throw_side):
            yc = L / 2 - tpos * L
            zt2 = zt + 0.003

            def top2(x, y, zt2=zt2, t_duv=t_duv):
                return zt2 + t_duv(x, y)
            if style == 'stacked':
                # folded throw lying across the foot (a soft slab), not draped
                C.pillow(mb, (cx, yc, zt + TD + 0.002), wu * 0.82, tw * 0.6, 0.035, m_throw, rc=0.04, m=m_corner,
                         puff=0.008, edge_w=0.015, yaw=gt.uniform(-0.04, 0.04))
            else:
                hw2 = hw
                rr2 = 0.045 + TD * 0.5 + 0.004
                hang2 = _cloth_len(zt + TD * 0.5 - base_h - 0.03, rr2)
                K.drape(mb, cx, 0.0, hw2 - 0.0, yc - tw / 2, yc + tw / 2, top2, lambda x, y: 0.012, m_throw,
                        nx, max(1 if lod == 2 else 2, ny // 2), hang2, hang_y=0.0, rr=rr2, floor_z=base_h + 0.02,
                        wrinkle=C.lod_pick(lod, 0.014, 0.008, 0.0), wr_freq=11.0, phase=tphase + 1.0, na=na, nh=nh)

    C.centre_base(mb)
    o = genlib.finish(mb.to_object(ASSET))
    C.set_json_props(o, kz_params=dict(style=style, w=round(W, 3), l=round(L, 3), thickness=round(TM, 3),
                                       pillows=npil, throw=bool(has_throw)), kz_anim=dict(type='none'))
    return o
