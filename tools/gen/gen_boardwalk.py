"""Boardwalk and pontoon deck (boardwalk): hinoki plank deck on posts, floats or rock, with edge beams and
iron railing sockets, along any path. Per-metre asset.

Targets (no elevation sheet exists for the boardwalk; measured off the lookbook):
  lookbook 34 (B2 river plan, 20 m grid = 147 px): timber walkways 1.6-3.0 m wide (11-22 px), planks laid
  across the walking direction, lantern posts at the edges every few metres, winding polylines.
  lookbook 35 (B3 plan): the long loop walkways are the same plank decks, 2-3 m wide, on low posts at the
  water's edge. lookbook 13 (left foreground): plank deck 0.13-0.16 m boards with a dark edge beam ~0.2 m
  deep and a timber railing (railing is its own asset: this deck carries the sockets for it).
  lookbook 29 (river section): boat landing pontoons sit low on the water.
  Built: deck width 1.5-1.9 m default (row 1.2-4), planks 0.12-0.20 m wide x 0.045 thick with 8-12 mm gaps,
  edge beam 0.08 thick x 0.22-0.25 deep flush with the deck top, interior stringers 0.08 x 0.12,
  bearers 0.12 x 0.14 under the stringers at every support station, posts 0.15-0.18 square with an iron
  shoe; railing sockets (iron sleeve 0.07 x 0.06 x 0.18 on a 0.12 x 0.20 back plate) on both edge beams at
  every station. Deck top over z = 0 (water or ground): posts 0.60, rock 0.30, floats 0.30 (waterline 0.10).

Proxy (w 3.0, d 2.0, h 0.3): the module runs along X. h 0.3 holds the float and rock styles; the posts
style is built at the concept's 0.6 m over the water. Proposed proxy h 0.65.
Per-metre: the default module is 1.0 m long so genlib.check measures the row's per-metre budget directly
(500/200/60/16). Long runs pass `path` (or `length`); triangles scale linearly with length.

Parameters build(lod, seed, **p)
  support     posts | floats | rock (default cycles with the seed: 1 posts, 2 floats, 3 rock)
  length      run length when no path is given (default 1.0)
  path        polyline [(x, y, z), ...] of the deck centreline; z is added to the deck height
  width       1.2-4.0 (default per seed: 1.8 / 1.9 / 1.5)
  plank       plank width 0.12-0.20 (seeded)
  spacing     support station spacing 1.5-2.5 m along the run (default per seed); a 1 m module has one
  height      deck top over z = 0 (default 0.60 posts, 0.30 floats, 0.30 rock)
Seeds change shape: the support style, deck width, plank width (0.13 / 0.18 / 0.15), station spacing,
post size, float size, rock sizes and plank jitter; each part draws from its own stream before LOD.
LOD0 top-chamfered planks with seeded height / yaw jitter, chamfered posts with iron shoes, edge beams,
stringers, bearers, sockets with back plates, rounded floats with two iron straps, 14-point rocks.
LOD1 same parts and counts, plain boxes, no shoes / straps / back plates. LOD2 one deck block (planks
merged, edge beams kept as its sides), posts / floats / rocks as boxes or 6-point hulls, sockets as boxes.
LOD3 deck block without underside + the supports as single cards / one hull; sockets dropped (16 tris).
Materials: planks hinoki natural (aged: wear 0.35), edge beam / stringers / bearers / posts hinoki
dark_timber, floats hinoki dark_timber, sockets / shoes / straps iron, rocks basalt_wet.
Props: kz_deck_z, kz_walk (half width), kz_sockets [[x, y, z], ...], kz_params; pontoon: kz_waterline and
kz_anim {type rigid, bob 0.03 m, 5.5 s, roll 1.2 deg}. Lighting: lightmap (pontoon: probe, kz_light_mode).
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_boardwalk as K

ASSET = 'boardwalk'
FEATURES = ['hinoki plank deck (planks across the walk)', 'edge beam', 'railing sockets', 'posts / floats / rock supports']
STYLES = ['posts', 'floats', 'rock']
SEED_DEF = {'posts': dict(width=1.8, height=0.60, spacing=1.8),
            'floats': dict(width=1.9, height=0.30, spacing=2.2),
            'rock': dict(width=1.5, height=0.30, spacing=1.6)}
PLANK_T = 0.045


def build(lod, seed, support=None, length=1.0, path=None, width=None, plank=None, spacing=None, height=None):
    support = support or C.cycle(seed, STYLES)
    D = SEED_DEF[support]
    g = C.rng(seed, ASSET + ':layout')
    W = width or D['width']
    pw = plank or [0.13, 0.18, 0.15][(seed - 1) % 3] + g.uniform(-0.005, 0.005)
    gap = g.uniform(0.008, 0.012)
    spacing = spacing or D['spacing'] * g.uniform(0.92, 1.08)
    H = height if height is not None else D['height']
    post = g.uniform(0.15, 0.18)
    P = K.run_path(path, length)
    L = P.L

    mb = genlib.MeshBuilder()
    m_plank = mb.slot('hinoki', variant='natural', wear=0.35)
    m_frame = mb.slot('hinoki', variant='dark_timber')
    m_iron = mb.slot('iron')
    m_rock = mb.slot('basalt_wet', wetness=0.55)

    ft, fd = 0.08, (0.25 if support == 'posts' else 0.20)          # edge beam thickness, depth
    st_h = 0.12 if support == 'posts' else 0.09                      # stringer depth
    bh = 0.14                                                        # bearer depth (posts only)
    inner = W / 2 - ft                                               # plank half length
    zt = H                                                           # deck top
    z_pl = zt - PLANK_T
    z_st = z_pl - st_h
    n_st = max(1, int(round((W - 2 * ft) / 0.9)) - 1)                # interior stringers
    st_off = [(-inner + (2 * inner) * (k + 1) / (n_st + 1)) for k in range(n_st)]

    # support stations: evenly spread, one per bay, centred (modules chain at the same pitch)
    nst = max(1, int(round(L / spacing)))
    s_sta = [L * (i + 0.5) / nst for i in range(nst)]

    # ------------------------------------------------------------------ layout drawn before any LOD branch
    rp = C.rng(seed, ASSET + ':planks')
    planks = [(s, w, rp.uniform(-0.002, 0.002), rp.uniform(-0.006, 0.006), rp.uniform(-0.012, 0.012))
              for s, w in K.plank_layout(L, lambda: (pw, gap))]
    rr = C.rng(seed, ASSET + ':rocks')
    rocks = []
    if support == 'rock':
        for s in s_sta:
            for side in (-1, 1):
                rocks.append((s + rr.uniform(-0.15, 0.15), side * (inner + rr.uniform(-0.05, 0.12)),
                              rr.uniform(0.34, 0.50), rr.uniform(0.28, 0.40), rr.uniform(0, math.pi), rr.random()))
    rf = C.rng(seed, ASSET + ':floats')
    fw = rf.uniform(0.42, 0.52); fh = H - 0.12 + 0.02             # float width, height (top just above stringer base)

    fr = K.frames(P, K.stations(P, 0.25))
    sockets = []

    if lod >= 2:
        # ---------------- deck block: planks merged, edge beams are its sides
        prof = [(-W / 2, -fd), (W / 2, -fd), (W / 2, 0.0), (-W / 2, 0.0)]
        K.hsweep(mb, fr, prof, m_frame, z=zt, skip=(0, 2) if lod == 3 else ())
        if lod == 3:      # walking surface as one skin in the plank material (same slots as LOD0-2)
            K.hsweep(mb, fr, [(-W / 2, 0.0), (W / 2, 0.0)], m_plank, z=zt, skip=(1,), caps=(False, False))
        if lod == 2:      # the walking surface keeps the plank material: a top skin 5 mm proud
            K.hsweep(mb, fr, [(-inner, -0.01), (inner, -0.01), (inner, 0.005), (-inner, 0.005)], m_plank, z=zt, skip=(0,))
    else:
        # ---------------- planks across the walk
        for s, w, dz, yaw, dl in planks:
            p, t = K.fan_tangent(P, s, W * 0.6)
            n = K.left(t)
            ty = Vector((math.cos(yaw) * t.x - math.sin(yaw) * t.y, math.sin(yaw) * t.x + math.cos(yaw) * t.y, 0))
            ny = K.left(ty)
            zc = p.z + z_pl + PLANK_T / 2 + dz
            c = Vector((p.x, p.y, zc)) + n * dl * 0.3
            a = c - ny * (inner + dl * 0.2); b = c + ny * (inner - dl * 0.2)
            if lod == 0:
                K.beam(mb, a, b, ty, w, PLANK_T, m_plank, kind='top', ch=0.006)
            else:
                K.beam(mb, a, b, ty, w, PLANK_T, m_plank)
        # ---------------- edge beams (fascia), flush with the deck top
        for side in (-1, 1):
            off = side * (W / 2 - ft / 2)
            kind = 'top' if lod == 0 else 'rect'
            prof = K.profile(kind, ft, fd, 0.008)
            prof = [(x, z - fd / 2) for x, z in prof]
            K.hsweep(mb, fr, prof, m_frame, off=off, z=zt)
        # ---------------- interior stringers
        for off in st_off:
            K.hsweep(mb, fr, [(-0.04, -st_h), (0.04, -st_h), (0.04, 0), (-0.04, 0)], m_frame, off=off, z=z_pl)

    # ---------------- supports
    for i, s in enumerate(s_sta):
        p, t, _ = P.at(s)
        n = K.left(t)
        base = Vector((p.x, p.y, p.z))
        if support == 'posts':
            zb = p.z + z_st - bh
            if lod <= 1:
                K.beam(mb, base + n * (-inner) + Vector((0, 0, z_st - bh / 2)), base + n * inner + Vector((0, 0, z_st - bh / 2)),
                       t, 0.12, bh, m_frame)
            for side in (-1, 1):
                q = base + n * side * (inner - post / 2 - 0.01)
                top = Vector((q.x, q.y, zb + 0.02))                     # 2 cm into the bearer
                bot = Vector((q.x, q.y, 0.0))
                if lod == 0:
                    K.beam(mb, bot, top, t, post, post, m_frame, kind='oct', ch=0.012, caps=(False, True))
                    K.beam(mb, bot, bot + Vector((0, 0, 0.09)), t, post + 0.02, post + 0.02, m_iron, caps=(False, True))
                elif lod == 1:
                    K.beam(mb, bot, top, t, post, post, m_frame, caps=(False, True))
                elif lod == 2:
                    K.beam(mb, bot, Vector((q.x, q.y, p.z + zt - fd)), t, post, post, m_frame, caps=(False, False))
                else:
                    a = bot - t * post / 2; b = bot + t * post / 2
                    K.quad(mb, [a, b, b + Vector((0, 0, zt - fd)), a + Vector((0, 0, zt - fd))], m_frame)
        elif support == 'floats':
            fl = min(spacing, L) * 0.86
            for side in (-1, 1):
                q = base + n * side * (W / 2 - fw / 2 + 0.04)
                if lod <= 1:
                    c = Vector((q.x, q.y, fh / 2))
                    if lod == 0:
                        C.board(mb, c, (fl, fw, fh), m_frame, bevel=0.035, segs=2, rot=(0, 0, math.atan2(t.y, t.x)))
                        for k in (-1, 1):
                            cc = c + t * k * fl * 0.3
                            C.board(mb, cc, (0.05, fw + 0.012, fh + 0.012), m_iron, bevel=0.0, rot=(0, 0, math.atan2(t.y, t.x)))
                    else:
                        C.board(mb, c, (fl, fw, fh), m_frame, bevel=0.0, rot=(0, 0, math.atan2(t.y, t.x)))
                elif lod == 2:
                    K.frustum(mb, (q.x, q.y), fl, fw, fl, fw, 0.0, zt - fd + 0.02, m_frame, yaw=math.atan2(t.y, t.x), top=False)
                else:
                    a = q - t * fl / 2 + n * side * fw / 2; b = q + t * fl / 2 + n * side * fw / 2
                    K.quad(mb, [a, b, b + Vector((0, 0, zt - fd + 0.02)), a + Vector((0, 0, zt - fd + 0.02))], m_frame)
            if lod <= 1:       # cross ties between the floats at the station ends (carry the stringers)
                for k in (-1, 1):
                    q = base + t * k * fl * 0.42
                    K.beam(mb, q + n * (-inner) + Vector((0, 0, fh - 0.03)), q + n * inner + Vector((0, 0, fh - 0.03)),
                           t, 0.09, 0.08, m_frame)
    if support == 'rock':
        for k, (s, o, rx, ry, rot, sel) in enumerate(rocks):
            if lod == 3 and k % 2:
                continue
            p, t, _ = P.at(s)
            n = K.left(t)
            q = Vector((p.x, p.y, 0)) + n * o
            top = p.z + z_st + 0.015
            npts = C.lod_pick(lod, 14, 10, 6, 5)
            rk = C.rng(seed, ASSET + ':rock%d' % k)
            C.hull_rock(mb, (q.x, q.y, top * 0.45), (rx, ry, top * 0.6), m_rock, rk, npts=npts, ground=0.0,
                        rot=rot, flat_top=top, rmin=0.8)

    # ---------------- railing sockets on both edge beams at every station
    for s in s_sta:
        p, t, _ = P.at(s)
        n = K.left(t)
        for side in (-1, 1):
            q = Vector((p.x, p.y, p.z + zt)) + n * side * (W / 2 + 0.03)
            sockets.append([round(q.x, 3), round(q.y, 3), round(q.z, 3)])
            if lod == 3:
                continue
            K.beam(mb, q - Vector((0, 0, 0.18)), q + Vector((0, 0, 0.005)), t, 0.07, 0.06, m_iron, caps=(True, True))
            if lod == 0:
                pq = Vector((p.x, p.y, p.z + zt)) + n * side * (W / 2 + 0.006)
                K.beam(mb, pq - Vector((0, 0, 0.21)), pq - Vector((0, 0, 0.01)), t, 0.12, 0.012, m_iron)

    C.centre_base(mb, centre_x=path is None, centre_y=path is None)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    K.grain_uv(o, [m_plank, m_frame])
    C.set_json_props(o, kz_deck_z=round(zt, 3), kz_walk=dict(half_width=round(W / 2 - 0.02, 3), length=round(L, 3)),
                     kz_sockets=sockets, kz_support=support,
                     kz_params=dict(support=support, width=round(W, 3), plank=round(pw, 3), gap=round(gap, 3),
                                    spacing=round(spacing, 3), height=H, stations=nst, planks=len(planks)))
    if support == 'floats':
        C.set_json_props(o, kz_waterline=0.10, kz_light_mode='probe',
                         kz_anim=dict(type='rigid', bob=0.03, period=5.5, roll_deg=1.2, note='pontoon bobs on the waterline'))
    else:
        C.set_json_props(o, kz_light_mode='lightmap', kz_anim=dict(type='none'))
    return o
