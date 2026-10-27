"""Path post lantern (lantern_post). op01 rewrite of the gen40_l build.

TARGETS (measured before coding)
  Sheet refs/gen/sheet-mod-lights.png panel 4 (label W 0.35 x D 0.35 x H 1.70; crop .scratch/op01/m_post.png,
  the side view at 350 px/m). Fractions of the total height: foot plate 0.03, iron shoe 0.13, shaft 0.55,
  iron collar 0.02, tray 0.015, lattice head 0.15, roof 0.07, finial 0.02.
  Side-view widths: shaft 0.17, shoe 0.21, plate 0.27, head body 0.23, roof eave 0.44 (!) of a 0.35 label.
  The proxy is 0.30 x 0.30, so the build keeps the ratios inside it: shaft 0.15, shoe 0.19, plate 0.25,
  head 0.20, roof 0.31 (2.1 x shaft; sheet 2.6 x). Proposed proxy: w = d = 0.36 (roof 0.36, plate 0.27).
  Sheet panel 4 head: 3 x 3 lattice (2 + 2 muntins), shoe with 2 x 2 rivets a face, a collar under the tray.
  Bonbori and boat pole: refs/gen/sheet-vs-lights-2.png panel 5 (bonbori 1.70 m: hex head 0.25, hex roof 0.33,
  post 0.12 with iron bands; boat pole 2.20 m: bamboo pole 0.08, arm, chochin 0.22 x 0.26, rope lashings).
  Rail lantern: refs/gen/ref-spiral-stair.png (cylindrical paper lantern ~0.2 x 0.32 with dark caps on the newel).

FEATURES kept at every LOD: timber post with iron foot and a glowing head (box / bonbori / cylinder),
  pole lantern hung from an arm.

PARAMETERS
  h          overall height, m (0.6-2.5; default 1.70, cylinder 1.10)
  post       shaft width, m (0.12-0.30; default by head 0.15 / 0.12 / 0.12 / 0.075 bamboo)
  head       'box' | 'bonbori' | 'cylinder' | 'pole_hook' (seeds 1-4 cycle them)
  foot       iron foot plate + shoe on/off (default on for box / bonbori)
  rail_mount clamp straps on the back of the shaft instead of a foot (default on for cylinder)

SEEDS: the head cycles with the seed (4 heads); within a head each seed draws head scale x0.92-1.08,
  roof pitch x0.8-1.3, shoe height x0.8-1.2, height x0.93-1.0, lattice 2 x 2 or 1 x 2, rivet / band count.

MATERIALS (slots by part): shaft = hinoki dark_timber (cylinder: hinoki stained), frame = hinoki stained
  (head frame, tray), roof = hinoki stained (box) / iron (bonbori), iron (plate, shoe, rivets, collar,
  straps, finials), paper = washi_backlit (square / hex / cylinder heads; lantern_andon's printed frame
  does not line up with the muntins), chochin = lantern_paper (pole),
  pole = bamboo, rope = rope (lashings, cord). bamboo / rope / lantern_paper are not in the row list:
  the boat pole needs them (concept), see report.
ANIMATION: shader flicker on the paper slot(s). LIGHT: kz_lights at the head centre, 2400 K, 20 W.
BUDGET 600 / 240 / 80 / 40.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_lantern_floor as L
import kzgeo_lantern_post as P

ASSET = 'lantern_post'
FEATURES = ['timber post', 'iron foot', 'glowing box head', 'bonbori / cylinder / pole heads']
HEADS = ['box', 'bonbori', 'cylinder', 'pole_hook']


def build(lod, seed, h=None, post=None, head=None, foot=None, rail_mount=None):
    head = head or C.cycle(seed, HEADS)
    g = C.rng(seed, 'dims')
    hk = g.uniform(0.92, 1.08)
    pitch = g.uniform(0.8, 1.3)
    shoe_k = g.uniform(0.8, 1.2)
    hj = g.uniform(0.93, 1.0)
    nl = C.pick(seed, 'lattice', [(2, 2), (1, 2), (2, 2)])
    H = h or (1.10 if head == 'cylinder' else 1.70) * hj
    foot = (head in ('box', 'bonbori')) if foot is None else foot
    rail_mount = (head == 'cylinder') if rail_mount is None else rail_mount
    pw = post or dict(box=0.15, bonbori=0.12, cylinder=0.12, pole_hook=0.075)[head]

    mb = genlib.MeshBuilder()
    shaft_m = mb.slot('hinoki', variant='stained' if head == 'cylinder' else 'dark_timber', wear=0.35)
    frame = mb.slot('hinoki', variant='stained', wear=0.3)
    iron = mb.slot('iron')
    paper = mb.slot('washi_backlit', emissive_level=1.0)
    m = dict(wood=frame, paper=paper, iron=iron, roof=frame if head == 'box' else iron)
    lights, flick = [], [paper]

    # ---------------------------------------------------------------- foot
    z = 0.0
    if head == 'pole_hook':
        pass
    elif foot and not rail_mount:
        plate_t, plate_w = 0.04, min(0.25, pw * 1.67)
        shoe_h, shoe_w = 0.20 * shoe_k * (H / 1.7), pw + 0.04
        if lod == 0:
            C.board(mb, (0, 0, plate_t / 2), (plate_w, plate_w, plate_t), iron, bevel=0.006)
            C.board(mb, (0, 0, plate_t + shoe_h / 2), (shoe_w, shoe_w, shoe_h), iron, bevel=0.003)
            nr = C.pick(seed, 'rivets', [2, 2, 1]) if head == 'box' else 1
            for f in range(4):
                a = f * math.pi / 2
                nx, ny = math.sin(a), math.cos(a)
                for i in range(2):
                    for j in range(nr):
                        u = (i - 0.5) * shoe_w * 0.55
                        zz = plate_t + shoe_h * ((j + 1) / (nr + 1))
                        cx, cy = nx * shoe_w / 2 + ny * u, ny * shoe_w / 2 - nx * u
                        L.stud(mb, (cx - nx * 0.001, cy - ny * 0.001, zz), (nx, ny, 0), 0.011, 0.009, iron)
        elif lod == 1:
            mb.box((0, 0, plate_t / 2), (plate_w, plate_w, plate_t), iron)
            mb.box((0, 0, plate_t + shoe_h / 2), (shoe_w, shoe_w, shoe_h), iron)
        else:
            if not (lod == 3 and head == 'bonbori'):
                L.open_box(mb, (0, 0, plate_t / 2), (plate_w, plate_w, plate_t), iron, skip=('bottom',))
            L.open_box(mb, (0, 0, plate_t + shoe_h / 2), (shoe_w, shoe_w, shoe_h), iron, skip=('top', 'bottom'))
        z = plate_t
    elif head != 'pole_hook':
        # no foot: an iron end cap (rail newel / socket)
        if lod <= 1:
            mb.box((0, 0, 0.02), (pw + 0.016, pw + 0.016, 0.04), iron)
        z = 0.0

    # ---------------------------------------------------------------- heads
    if head == 'box':
        Wh = 0.20 * hk
        Hh = 0.26 * hk
        roof_half = min(0.155, Wh * 0.78)
        rise = 0.075 * pitch
        zt = H - (0.016 + rise + 0.035)
        z_head = zt - Hh
        z_collar = z_head - 0.035
        _shaft(mb, z, z_collar, pw, shaft_m, lod)
        _collar(mb, z_collar, 0.035, pw + 0.03, iron, lod)
        lights.append(P.box_head(mb, z_head, Wh, Hh, roof_half, rise, m, lod, nl=nl))
    elif head == 'bonbori':
        R = 0.105 * hk
        Hh = 0.25 * hk
        roofR = 0.15                       # 1.4 x the body (sheet); the proxy width caps it
        rise = 0.065 * pitch
        zt = H - (0.018 + rise + 0.06)
        z_head = zt - Hh
        _shaft(mb, z, z_head, pw, shaft_m, lod)
        nb = C.pick(seed, 'bands', [1, 2, 2])
        if lod <= 1:   # iron bands on the shaft (sheet: top and bottom straps)
            for i in range(nb if lod == 0 else 1):
                zz = z_head - 0.05 - i * 0.07
                L.sq_ring(mb, (0, 0), zz - 0.015, zz + 0.015, pw / 2 + 0.006, pw / 2 - 0.004, iron)
        lights.append(P.hex_head(mb, z_head, R, Hh, roofR, rise, m, lod))
    elif head == 'cylinder':
        r = 0.10 * hk
        Hh = 0.32 * hk
        z_head = H - Hh - 0.06 - (0.035 if lod == 0 else 0.0)
        _shaft(mb, z, z_head, pw, shaft_m, lod)
        if lod <= 1:
            _collar(mb, z_head - 0.02, 0.02, pw + 0.03, iron, lod)
        if rail_mount:
            # two U-straps on the back face that clamp the post to a stair rail (rail at -y)
            for zz in ((z_head * 0.55, z_head * 0.8) if lod == 0 else (z_head * 0.7,)):
                if lod <= 1:
                    L.sq_ring(mb, (0, 0), zz - 0.015, zz + 0.015, pw / 2 + 0.006, pw / 2 - 0.004, iron)
                    mb.box((0, -pw / 2 - 0.02, zz), (0.05, 0.04, 0.03), iron)
                else:
                    L.open_box(mb, (0, -pw / 2 - 0.015, zz), (0.05, 0.03, 0.04), iron, skip=('front',))
        lights.append(P.cyl_head(mb, z_head, r, Hh, m, lod))
    else:   # pole_hook: bamboo pole, arm, hanging chochin
        pole = mb.slot('bamboo')
        rope = mb.slot('rope')
        chochin = mb.slot('lantern_paper', emissive_level=1.0)
        flick = [chochin]
        rr = pw / 2
        px = -0.09
        # pole with node ridges every ~0.32 m
        sides = C.lod_pick(lod, 8, 6, 4, 4)
        if lod <= 1:
            nn = max(2, int(H / 0.32))
            pts, radii = [], []
            for i in range(nn + 1):
                zz = H * i / nn
                if 0 < i < nn and lod == 0:
                    for dz, k in ((-0.004, 1.09), (0.012, 1.0)):
                        pts.append((px, 0, zz + dz)); radii.append(rr * k * (1 - 0.08 * zz / H))
                else:
                    pts.append((px, 0, zz)); radii.append(rr * (1 - 0.08 * zz / H) * (1.04 if 0 < i < nn else 1.0))
            C.tube(mb, pts, radii, pole, sides=sides, cap0=False, cap1=True)
        else:
            C.tube(mb, [(px, 0, 0), (px, 0, H * 0.5), (px, 0, H)], [rr, rr * 1.03, rr * 0.92], pole, sides=sides, cap1=True)
        # arm: a bamboo stick out to +x, lashed to the pole, iron hook at the tip
        za = H - 0.06
        arm_end = 0.05 + 0.02 * hk
        if lod <= 1:
            C.stick(mb, (px - rr * 0.6, 0, za), (arm_end + 0.02, 0, za - 0.012), 0.017, 0.014, pole, segs=C.lod_pick(lod, 6, 5))
        else:
            L.open_box(mb, ((px + arm_end) / 2, 0, za), (arm_end - px, 0.03, 0.03), pole, skip=('left', 'right'))
        if lod == 0:
            C.rope_turns(mb, (px, 0, za), (0, 0, 1), rr + 0.002, 3, rope, cord=0.006, pitch=0.012)
            C.rope_turns(mb, (px, 0, H * 0.45), (0, 0, 1), rr + 0.002, 4, rope, cord=0.006, pitch=0.012)
            C.stick(mb, (arm_end, 0, za - 0.012), (arm_end, 0, za - 0.05), 0.005, 0.005, iron, segs=4)
        elif lod == 1:
            C.rope_band(mb, (px, 0, za), (0, 0, 1), rr, 0.04, rope, N=6)
        lr, lh = 0.10 * hk, 0.26 * hk
        ltop = za - 0.06 - 0.02 * pitch
        if lod <= 1:
            C.rope_cord(mb, (arm_end, 0, za - 0.045), (arm_end, 0, ltop), 0.004, rope, sides=6 if lod == 0 else 4, twist=lod == 0)
        elif lod == 2:
            C.rope_cord(mb, (arm_end, 0, za - 0.01), (arm_end, 0, ltop), 0.005, rope, sides=1)
        lights.append(P.chochin_hang(mb, (arm_end, 0, ltop), lr, lh, dict(paper=chochin, iron=iron), lod))
        if lod <= 1:   # iron socket at the foot of the pole
            if lod == 0:
                L.sq_ring(mb, (px, 0), 0.0, 0.06, rr + 0.012, rr - 0.004, iron)
            else:
                L.open_box(mb, (px, 0, 0.03), (2 * rr + 0.024, 2 * rr + 0.024, 0.06), iron, skip=('bottom',))

    d = Vector(C.centre_base(mb))
    o = mb.to_object(ASSET)
    genlib.finish(o)
    L.lights_props(o, [c + d for c in lights], 2400, 20, flick,
                   dict(head=head, h=round(H, 3), post=round(pw, 3), foot=foot, rail_mount=rail_mount))
    return o


def _shaft(mb, z0, z1, pw, mi, lod):
    hz = z1 - z0
    if lod == 0:
        C.chamfered_bar(mb, (0, 0, (z0 + z1) / 2), (pw, pw, hz), mi, ch=min(0.012, pw * 0.08))
    elif lod == 1:
        mb.box((0, 0, (z0 + z1) / 2), (pw, pw, hz), mi)
    else:
        L.open_box(mb, (0, 0, (z0 + z1) / 2), (pw, pw, hz), mi, skip=('top', 'bottom'))


def _collar(mb, z0, t, w, mi, lod):
    if lod <= 1:
        mb.box((0, 0, z0 + t / 2), (w, w, t), mi)
