"""Soy and tea aqueduct (aqueduct): a small hinoki trough on timber stilts or an arched arcade, falling
1:20, with a sluice gate and bamboo spouts at the tables. Per-metre asset.

Targets (measured):
  refs/gen/sheet-mod-kawagiri.png #3 'Soy & tea aqueducts' (crop .scratch/op20/m_aq.png, 2x: 3.0 m bar =
  477 px -> 159 px/m; the 1.6 m bar gives 153 px/m): module 3.0 m long, 1.6 m to the top of the gate
  lever, trough top ~1.48 m; trough ~0.13 m deep on a 0.20 m carrier beam that runs the whole length;
  bents ~1.4 m apart, posts 0.15-0.16 m, two posts per bent in the side view (0.45 m apart), knee
  braces at 45 deg under the beam; cut-stone footings 0.38 x 0.60 x 0.28 m; copper straps (vertical plates
  over trough + beam) at every post; sluice gate at the downstream end: two uprights ~0.3 m above the
  trough, crossbar, a lever arm; the spout pours from the trough underside (side view).
  Soy: darker oiled timber, dark liquid; tea: pale hinoki, green-stained trough lip.
  lookbook 08: the arched version: a hinoki arcade (semicircular arches, ~1.6:1 opening to pier) carrying
  the trough, square posts with caps standing up beside the trough over the piers, bamboo spouts pouring
  soy and tea into the bowls. lookbook 07: aqueducts run along every table row, a spout per table.
  Row: trough w 0.12-0.25, 1:20 fall, support arches | stilts, sluice every n, spout style.
  Built: stilts: trough inner 0.18-0.24 x 0.11 deep (outer +0.06 / 0.15), top 1.48 at the upstream end,
  carrier 0.16 x 0.20, bents every ~1.3 m, posts 0.13, footings 0.38 x 0.60 x 0.28. arches: trough inner
  0.13-0.16, top 1.05, arcade 0.16 deep, piers 0.14 wide at 0.60-0.68 m pitch, basalt sill 0.10.

Proxy (w 0.25, d 2.0, h 1.1): the proxy reads as a 2 m run along Y of the arched type. This module runs
along X (like the other per-metre decks, so the sheet's front view shows the elevation) and the stilts
type is the sheet's 1.6 m. Proposed proxy: w 3.0, d 0.62, h 1.75.
Budget is per metre (800/320/96/24); the default 3.0 m module (the sheet's) is held to the unscaled row
numbers, i.e. a third of the per-metre budget. Longer runs scale linearly.

Parameters build(lod, seed, **p)
  liquid       soy | tea (default cycles with the seed)
  support      stilts | arches (default: seed 1 stilts, 2 arches, 3 arches, 4 stilts)
  length       run length when no path is given (default 3.0)
  path         polyline [(x, y, z), ...] (plan; z offsets the level); the fall is applied along it
  fall         1:20 -> 0.05 (default)
  trough_w     inner width 0.12-0.25 (seeded per support)
  pitch        bent / pier pitch (stilts 1.2-1.45, arches 0.60-0.68)
  height       trough top at the upstream end (stilts 1.48, arches 1.05)
  sluice_every gate every n bents (default: one gate per module, at the downstream bent)
  spout_every  spout spacing along the run (default 1.5 m) ; spout_dip 0.2-0.6 (seeded)
Seeds change shape: support type, trough width, pitch (bent / pier count), height +-4 %, spout dip and
side, gate end; liquid soy / tea swaps the timber variant and trough staining.
LOD0 chamfered members, two-stone footings, copper strap plates with a top bar, 10-sided bamboo spouts
with node bands and a dark mouth, the gate with handle, lever, pivot and link rod; arcade arches at 10
segments. LOD1 same parts and counts, boxes, 6-sided spouts, 6-segment arches, one-stone footings.
LOD2 trough as a block, one post per bent, footings, the gate board + uprights, arcade as one outline
(pointed 2-segment arches, no soffits), spouts as 4-sided tubes. LOD3 trough block, post / arcade cards,
gate card, spout cards.
Materials: trough / arcade hinoki (soy: dark_timber, tea: natural), frame (soy: stained, tea: wet_oiled), trough lining (soy: lacquer_dark, tea: hinoki
natural with a pale green tint 0.85/1.0/0.78), bamboo (spouts) with darker node bands, bronze smooth
(copper straps, as the sheet), iron (gate pivot, link), basalt_dry cooled (footings, sill).
Animation: kz_anim {type rigid + shader}: the gate board / handle (vertex layer '_gate' = 1) lifts 0.10 m,
the lever ('_gate' = 2) turns 25 deg about kz_gate_pivot; shader trickle at each kz_trickles mouth.
Liquid: kz_water_path [[x, y, z], ...] at the liquid level, kz_liquid soy | tea. Lighting lightmap.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_boardwalk as K
import kzgeo_aqueduct as A

ASSET = 'aqueduct'
FEATURES = ['small hinoki trough (1:20 fall)', 'stilts or arched trestles', 'sluice gate', 'bamboo spouts']
TINT_STONE = (0.40, 0.47, 0.64)
SUPPORT = ['stilts', 'arches', 'arches', 'stilts']
Zv = Vector((0, 0, 1))


def build(lod, seed, liquid=None, support=None, length=3.0, path=None, fall=0.05, trough_w=None, pitch=None,
          height=None, sluice_every=None, spout_every=1.5, spout_dip=None):
    liquid = liquid or C.cycle(seed, ['soy', 'tea'])
    support = support or SUPPORT[(seed - 1) % 4]
    g = C.rng(seed, ASSET + ':layout')
    st = support == 'stilts'
    tw = trough_w or (g.uniform(0.18, 0.24) if st else g.uniform(0.13, 0.16))
    wall, flo = 0.03, 0.04
    ow = tw + 2 * wall
    th = 0.15 if st else 0.12                       # trough outer height
    pitch = pitch or (g.uniform(1.2, 1.45) if st else g.uniform(0.60, 0.68))
    Ht = height or (1.48 if st else 1.05) * g.uniform(0.96, 1.04)
    dip = spout_dip or g.uniform(0.2, 0.6)
    spout_side = 1 if g.random() < 0.7 else -1
    gate_down = g.random() < 0.75

    P = K.run_path(path, length)
    L = P.L
    ss = K.stations(P, 0.3)
    fr = [(Vector((p.x, p.y, p.z - fall * s)), t, n, sc) for s, (p, t, n, sc) in zip(ss, K.frames(P, ss))]

    def at(s):
        p, t, _ = P.at(s)
        return Vector((p.x, p.y, p.z - fall * s)), t, K.left(t)

    mb = genlib.MeshBuilder()
    lay = mb.bm.verts.layers.int.new('_gate')
    m_wood = mb.slot('hinoki', variant='dark_timber' if liquid == 'soy' else 'natural')
    m_line = mb.slot('lacquer_dark') if liquid == 'soy' else mb.slot('hinoki', variant='natural', tint=(0.85, 1.0, 0.78))
    m_frame = mb.slot('hinoki', variant='stained' if liquid == 'soy' else 'wet_oiled')
    m_bamboo = mb.slot('bamboo')
    m_node = mb.slot('bamboo', tint=(0.5, 0.45, 0.38), wear=0.5)
    m_copper = mb.slot('bronze', variant='smooth')
    m_iron = mb.slot('iron')
    m_stone = mb.slot('basalt_dry', tint=TINT_STONE)

    # ---------------- trough (U section) on the carrier
    if lod <= 1:
        ch = 0.006 if lod == 0 else 0.0
        U = [(-ow / 2, -th), (ow / 2, -th), (ow / 2, -ch), (ow / 2 - ch, 0.0), (tw / 2, 0.0), (tw / 2, -th + flo),
             (-tw / 2, -th + flo), (-tw / 2, 0.0), (-ow / 2 + ch, 0.0), (-ow / 2, -ch)]
        if ch == 0.0:
            U = [q for i, q in enumerate(U) if i not in (3, 8)]
        K.hsweep(mb, fr, U, m_wood, z=Ht)
        # liner strip on the trough floor (the stained inside)
        if lod == 0:
            K.hsweep(mb, fr, [(-tw / 2 + 0.002, -th + flo), (tw / 2 - 0.002, -th + flo), (tw / 2 - 0.002, -th + flo + 0.004),
                              (-tw / 2 + 0.002, -th + flo + 0.004)], m_line, z=Ht, skip=(0,), caps=(False, False))
    else:                                       # LOD2/3: trough block (stilts: down to the carrier underside)
        zb_ = -th - (0.20 if st and lod == 2 else 0.0)
        K.hsweep(mb, fr, [(-ow / 2, zb_), (ow / 2, zb_), (ow / 2, 0), (-ow / 2, 0)], m_wood, z=Ht, skip=(0,))
        if lod == 2:      # the liquid line shows as a dark top strip
            K.hsweep(mb, fr, [(-tw / 2, 0.002), (tw / 2, 0.002)], m_line, z=Ht, skip=(1,), caps=(False, False))

    z_tb = Ht - th                                   # trough underside (upstream)
    trickles, lights = [], []

    if st:
        # ---------------- carrier beam + bents
        cw, chh = 0.16, 0.20
        if lod <= 1:
            prof = [(x, z - chh / 2) for x, z in K.profile('oct' if lod == 0 else 'rect', cw, chh, 0.012)]
            K.hsweep(mb, fr, prof, m_frame, z=z_tb)
        nb = max(2, int(round((L - 0.5) / pitch)) + 1)
        sb = [0.25 + (L - 0.5) * i / (nb - 1) for i in range(nb)]
        ps, py, fh = 0.13, 0.17, 0.28
        for i, s in enumerate(sb):
            p, t, n = at(s)
            zb = p.z + z_tb - chh                    # carrier underside at this bent
            base = Vector((p.x, p.y, 0.0))
            # footings
            if lod == 0:
                for sg in (-1, 1):
                    C.board(mb, base + n * sg * 0.15 + Zv * fh / 2, (0.38, 0.29, fh), m_stone, bevel=0.025,
                            rot=(0, 0, math.atan2(t.y, t.x) + 0.02 * sg))
            elif lod == 1:
                K.frustum(mb, base, 0.40, 0.60, 0.36, 0.56, 0.0, fh, m_stone, yaw=math.atan2(t.y, t.x))
            elif lod == 2:
                K.frustum(mb, base, 0.40, 0.60, 0.36, 0.56, 0.0, fh, m_stone, yaw=math.atan2(t.y, t.x), top=False)
            # posts
            if lod <= 1:
                for sg in (-1, 1):
                    q = base + n * sg * py
                    K.beam(mb, Vector((q.x, q.y, fh)), Vector((q.x, q.y, zb - 0.10)), t, ps, ps, m_frame,
                           kind='oct' if lod == 0 else 'rect', ch=0.01, caps=(False, False))
                # bent head under the carrier
                K.beam(mb, base + n * -(py + 0.1) + Zv * (zb - 0.05), base + n * (py + 0.1) + Zv * (zb - 0.05), t, 0.12, 0.10,
                       m_frame, caps=(lod == 0, lod == 0))
                # knee braces in the run's plane, both posts, towards the neighbouring bents
                dirs = [d for d in (-1, 1) if (d < 0 and i > 0) or (d > 0 and i < nb - 1)]
                for sg in (-1, 1):
                    q = base + n * sg * py
                    for d in dirs:
                        a = Vector((q.x, q.y, zb - 0.10 - 0.40)) + t * d * ps / 2
                        b = Vector((q.x, q.y, zb - 0.01)) + t * d * 0.42
                        K.beam(mb, a, b, n, 0.06, 0.08, m_frame, caps=(False, False))      # ends buried in post / carrier
                # copper straps over trough + carrier, both faces, with a bar across the top
                for sg in (-1, 1):
                    q = Vector((p.x, p.y, 0)) + n * sg * (ow / 2 + 0.007)
                    K.beam(mb, q + Zv * (zb - 0.02), q + Zv * (p.z + Ht + 0.01), t, 0.07, 0.014, m_copper,
                           caps=(False, False))
                if lod == 0:
                    K.beam(mb, Vector((p.x, p.y, p.z + Ht + 0.008)) - n * (ow / 2 + 0.014),
                           Vector((p.x, p.y, p.z + Ht + 0.008)) + n * (ow / 2 + 0.014), t, 0.07, 0.016, m_copper)
            elif lod == 2:
                K.beam(mb, base + Zv * fh, base + Zv * zb, t, ps, 2 * py + ps, m_frame, caps=(False, False))
            else:
                a = base - t * ps / 2; b = base + t * ps / 2
                K.quad(mb, [a, b, b + Zv * (zb + chh), a + Zv * (zb + chh)], m_frame)
        gate_s = sb[-1] if gate_down else sb[0]
        if sluice_every:
            gate_list = [sb[i] for i in range(0, nb, max(1, sluice_every))]
        else:
            gate_list = [gate_s]
    else:
        # ---------------- arcade + sill
        pw = 0.14
        npier = max(2, int(round((L - pw) / pitch)) + 1)
        piers = [((L - pw) * i / (npier - 1), (L - pw) * i / (npier - 1) + pw) for i in range(npier)]
        r = (piers[1][0] - piers[0][1]) / 2
        sill = 0.10
        dep = 0.16
        z_top0, z_top1 = z_tb, z_tb - fall * L
        spring = min(z_top0, z_top1) - 0.10 - r
        segs = C.lod_pick(lod, 10, 5, 2, 2)
        if path is None:
            p0, t0, n0 = at(0.0)
            A0 = Vector((p0.x, p0.y, 0.0))
            if lod <= 2:
                A.arcade(mb, A0, t0, n0, L, z_top0, z_top1, piers, spring, m_wood, dep, segs, soffits=lod <= 1,
                         base=sill if lod <= 1 else 0.0, bottoms=False)
            else:         # one solid wall under the falling trough (the arches are a few px at the 49 m switch)
                A.arcade(mb, A0, t0, n0, L, z_top0, z_top1, [(0.0, L)], spring, m_wood, dep, 1, soffits=False, base=0.0)
        else:   # one arcade per straight path segment
            for s0, s1, a0, d in P.segs:
                t0 = Vector((d.x, d.y, 0)).normalized(); n0 = K.left(t0)
                Ls = s1 - s0
                k = max(2, int(round((Ls - pw) / pitch)) + 1)
                pr = [((Ls - pw) * i / (k - 1), (Ls - pw) * i / (k - 1) + pw) for i in range(k)]
                A.arcade(mb, Vector((a0.x, a0.y, 0)), t0, n0, Ls, z_tb - fall * s0 + a0.z, z_tb - fall * s1 + a0.z, pr,
                         spring + a0.z, m_wood, dep, segs, soffits=lod <= 1, base=sill)
        # sill
        if lod <= 1:
            K.hsweep(mb, [(Vector((q.x, q.y, 0)), tt, nn, sc) for q, tt, nn, sc in fr],
                     [(-0.13, 0), (0.13, 0), (0.13, sill), (-0.13, sill)], m_stone, skip=(0,))
        # posts with caps beside the trough over every other pier
        if lod <= 1:
            for j, (x0, x1) in enumerate(piers):
                if j % 2:
                    continue
                p, t, n = at((x0 + x1) / 2)
                for sg in (-1, 1):
                    q = Vector((p.x, p.y, 0)) + n * sg * (ow / 2 + 0.03)
                    zt = p.z + Ht + 0.10
                    K.beam(mb, q + Zv * (p.z + z_tb - 0.06), q + Zv * zt, t, 0.055, 0.055, m_wood, caps=(False, lod == 1))
                    if lod == 0:
                        K.beam(mb, q + Zv * zt, q + Zv * (zt + 0.035), t, 0.075, 0.075, m_frame, kind='top', ch=0.012)
        gate_s = (piers[-2][1] + piers[-1][0]) / 2 if gate_down else (piers[0][1] + piers[1][0]) / 2
        gate_list = [gate_s]

    # ---------------- sluice gates
    pivots = []
    for gs in gate_list:
        p, t, n = at(gs)
        pv = A.gate(mb, Vector((p.x, p.y, 0)), t, n, tw, ow, p.z + Ht - th + flo, p.z + Ht, (m_frame, m_wood, m_iron), lod, lay,
                    post=0.05 if st else 0.04, lever=st or lod == 0)
        pivots.append([round(c, 3) for c in pv])

    # ---------------- bamboo spouts (one per table)
    nsp = max(1, int(round(L / spout_every)))
    for k in range(nsp):
        s = L * (k + 0.5) / nsp
        if abs(s - gate_list[0]) < 0.25:
            s += 0.3
        p, t, n = at(s)
        root = Vector((p.x, p.y, p.z + Ht - th + flo + 0.03)) + n * spout_side * (tw / 2 - 0.01)
        tip = A.spout(mb, root, n * spout_side, (0.22 if st else 0.18) + ow / 2, 0.024 if st else 0.018, m_bamboo, m_node, lod,
                      drop=dip)
        trickles.append([round(c, 3) for c in tip])

    dx, dy, dz = C.centre_base(mb, centre_x=path is None, centre_y=path is None)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    K.grain_uv(o, [m_wood, m_frame, m_bamboo] + ([m_line] if liquid == 'tea' else []))
    sh = lambda q: [round(q[0] + dx, 3), round(q[1] + dy, 3), round(q[2] + dz, 3)]
    wpath = []
    for s in ss:
        p, t, n = at(s)
        wpath.append(sh((p.x, p.y, p.z + Ht - th + flo + 0.07)))
    C.set_json_props(o, kz_liquid=liquid, kz_support=support,
                     kz_water_path=wpath, kz_water_level=round(Ht - th + flo + 0.07 + dz, 3),
                     kz_trickles=[sh(q) for q in trickles], kz_gate_pivot=[sh(q) for q in pivots],
                     kz_anim=dict(type='rigid+shader', gate=dict(attr='_gate', lift_value=1, lift=0.10, lever_value=2,
                                                                 lever_deg=25, pivot='kz_gate_pivot', period=14.0),
                                  shader=dict(trickle='kz_trickles', liquid=liquid)),
                     kz_params=dict(liquid=liquid, support=support, length=round(L, 3), fall=fall, trough_w=round(tw, 3),
                                    pitch=round(pitch, 3), height=round(Ht, 3), spouts=nsp, spout_dip=round(dip, 2)))
    return o
