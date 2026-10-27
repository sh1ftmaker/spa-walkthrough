"""Egg basket gantry over the Spring Source (s_spring): the timber frame the bamboo egg baskets hang from.

Identifying features kept at every LOD: timber gantry beam straddling the source on posts, the rope run with
cleats on the posts, lanterns hanging under the beam.

Targets (measured / derived):
  * lookbook 30 (summit plan, Spring Source D2; crop .scratch/op24/c_eggs30.png): a rectangular timber frame over
    the pool: two long beams on posts with cross members, knee braces under the beam, four baskets hanging on single
    ropes, alternating between the front and back beam, small lanterns on the frame. Lookbook 24 (cutaway, "Spring
    Source with Egg Baskets"): tall timber frames standing in the steam with lit lanterns at the top.
  * Row: span 6-11 m, h 3.5-4.8 m, typical 10.6 x 0.6 x 4.8 m, budget 8000/3200/960/150.  The proxy in
    assets.json is 6 x 2.5 x 3.5 m (frame=true), and the proxy is the default build: default span 5.5-6.0 m,
    height 3.3-3.5 m, depth 1.6-2.3 m.  The row's 0.6 m depth only holds a bare beam: a freestanding frame needs
    raking struts or a second beam line, so the build keeps the proxy depth (see report).
  * Scale: posts 0.22-0.26 m square, beam 0.20 x 0.28 m with upswept ends (+6 cm), overhang 0.40-0.55 m past
    the posts, nuki tie beam 0.10 x 0.20 m at 0.75 m under the beam with 0.18 m through-tenon ends, knee braces at
    45 deg, rope 22 mm, cleats 0.30 m horn cleats at 1.1-1.5 m on the post fronts (hand height), sheave blocks
    0.14 m wheels hanging 0.16 m under the beam, lanterns 0.20 x 0.34 m andon on 0.25 m cords.

Construction (one mesh): posts (chamfered at LOD0) on iron shoes, upswept top beam(s) with iron end caps, nuki tie
beam with through ends, knee braces, cross beams (twin / trestle) or raking struts (raked), iron sheave blocks
with hooks at each hang point, a rope run from each cleat up the post and along the beam underside into its
sheave with 3 rope turns on the cleat and a short fall to the hook, hanging andon lanterns between the hang points.

Parameters (defaults inside the proxy):
  span      overall width 4-11 m (default 5.5-6.0, seeded)          h        3.2-4.8 m (default 3.3-3.5)
  post      post size 0.18-0.30 m (default seeded 0.22-0.26)       cleats   number of ropes / cleats / hang points
                                                                              2-6 (default seeded 3-5)
  lanterns  0-5 (default seeded 2-4)                                style    'twin' | 'raked' | 'trestle'
Styles (cycle with the seed): 1 'twin' (two beam lines 1.5-1.8 m apart on four posts with cross beams: the plan-30
frame), 2 'raked' (one beam on two posts braced by raking struts to the ground: the row's single gantry beam),
3 'trestle' (twin with a middle post pair, two bays).  Seeds also change span, height, post size, overhang, number of
hang points / cleats, lantern count and positions, and the depth of the frame.

Materials: hinoki dark_timber (posts, beams, braces), hinoki wet_oiled (cross beams, cleats), iron (shoes, end caps,
sheave straps, hooks), bronze smooth (sheave wheels), rope (rope run, turns), lantern_andon (lantern paper).
Lighting: lightmap + emissive; obj['kz_lights'] = one point light per lantern (2200 K, 18 W).
Custom props: obj['kz_hang_points'] = [[x, y, z]] hook positions for egg_basket instances (their rope top),
obj['kz_params'].  Animation: none.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C

ASSET = 'egg_baskets'
FEATURES = ['timber gantry beam straddling the source', 'rope run with cleats on the posts',
            'lanterns hanging under the beam']
STYLES = ['twin', 'raked', 'trestle']


def params(seed, span=None, h=None, post=None, cleats=None, lanterns=None, style=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'frame')
    P = dict(style=style or C.cycle(seed, STYLES))
    P['span'] = float(span) if span else p['w'] * g.uniform(0.92, 0.995)
    P['h'] = float(h) if h else p['h'] * g.uniform(0.94, 0.995)
    P['post'] = float(post) if post else g.uniform(0.22, 0.26)
    P['ov'] = g.uniform(0.40, 0.55)
    P['depth'] = g.uniform(1.5, 1.8) if P['style'] != 'raked' else g.uniform(1.8, 2.2)
    P['brace'] = g.uniform(0.6, 0.8)
    gh = C.rng(seed, 'hang')
    P['cleats'] = int(cleats) if cleats else gh.randint(3, 5)
    gl = C.rng(seed, 'lanterns')
    P['lanterns'] = int(lanterns) if lanterns is not None else gl.randint(2, 4)
    P['lantern_jit'] = [gl.uniform(-0.15, 0.15) for _ in range(6)]
    P['cleat_z'] = [gh.uniform(1.1, 1.5) for _ in range(8)]
    return P


def _chprof(w, h, ch):
    """chamfered rectangle (x sideways, z up), centred"""
    a, b = w / 2, h / 2
    return [(-a + ch, -b), (a - ch, -b), (a, -b + ch), (a, b - ch), (a - ch, b), (-a + ch, b), (-a, b - ch), (-a, -b + ch)]


def _bar(mb, a, b, w, h, mi, lod, ch=0.012):
    """straight member from a to b (centre line), w sideways x h up; chamfered at LOD0, a box section otherwise"""
    a, b = Vector(a), Vector(b)
    d = b - a
    up = Vector((0, 0, 1)) if abs(d.normalized().z) < 0.95 else Vector((1, 0, 0))
    prof = _chprof(w, h, ch) if lod == 0 else [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    C.sweep(mb, [a, b], prof, mi, up=up)


def build(lod, seed, span=None, h=None, post=None, cleats=None, lanterns=None, style=None, **_):
    P = params(seed, span, h, post, cleats, lanterns, style)
    mb = genlib.MeshBuilder()
    m_post = mb.slot('hinoki', variant='dark_timber')
    m_x = mb.slot('hinoki', variant='wet_oiled', wear=0.25)
    m_iron = mb.slot('iron', wear=0.2)
    m_wheel = mb.slot('bronze', variant='smooth')
    m_rope = mb.slot('rope')
    m_paper = mb.slot('lantern_andon', emissive_level=0.9)
    st = P['style']
    W, H, ps, ov = P['span'], P['h'], P['post'], P['ov']
    bw, bh = 0.20, 0.28
    xp = W / 2 - ov                                  # post centre x
    z_bt = H - 0.06                                  # beam top at mid-span (ends sweep up 6 cm)
    z_bb = z_bt - bh                                 # beam underside
    lines = [0.0] if st == 'raked' else [-P['depth'] / 2 + bw / 2, P['depth'] / 2 - bw / 2]
    xs_post = [-xp, xp] + ([0.0] if st == 'trestle' else [])
    lights = []
    # ---------------------------------------------------------------- posts, shoes, beams, ties, braces
    for y in lines:
        for x in xs_post:
            if lod == 0:
                C.chamfered_bar(mb, (x, y, z_bb / 2), (ps, ps, z_bb), m_post, ch=0.018)
            else:
                mb.box((x, y, z_bb / 2), (ps, ps, z_bb), m_post)
            if lod <= 1:                             # iron shoe: base plate + two side straps
                mb.box((x, y, 0.025), (ps + 0.1, ps + 0.1, 0.05), m_iron)
                for sy in (-1, 1):
                    mb.box((x, y + sy * (ps / 2 + 0.006), 0.2), (ps * 0.7, 0.012, 0.32), m_iron)
        # top beam with upswept ends
        n = C.lod_pick(lod, 13, 7, 3, 2)
        pts = []
        for i in range(n):
            x = -W / 2 + W * i / (n - 1)
            t = abs(x) / (W / 2)
            pts.append(Vector((x, y, z_bt - bh / 2 + 0.06 * t ** 3)))
        prof = _chprof(bw, bh, 0.015) if lod == 0 else [(-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2)]
        C.sweep(mb, pts, prof, m_post)
        if lod == 0:                                 # iron end caps on the beam ends
            for sx in (-1, 1):
                mb.box((sx * (W / 2 - 0.004), y, z_bt - bh / 2 + 0.06), (0.012, bw + 0.012, bh + 0.012), m_iron)
        # nuki tie beam with through-tenon ends
        zt = z_bb - 0.75
        if lod <= 2:
            mb.box((0, y, zt), (2 * xp + ps + 0.36, 0.10, 0.20), m_post)
            if lod <= 1:
                for sx in (-1, 1):                   # wedge pegs
                    mb.box((sx * (xp + ps / 2 + 0.07), y, zt), (0.04, 0.14, 0.24), m_x)
        # knee braces (post -> beam underside), 45 deg
        L = P['brace']
        if lod <= 2:
            for x0 in xs_post:
                for sx in ((-1, 1) if x0 == 0.0 else (1 if x0 < 0 else -1,)):
                    a = (x0 + sx * ps / 2, y, z_bb - L)
                    b = (x0 + sx * (ps / 2 + L), y, z_bb)
                    _bar(mb, (a[0] - sx * 0.02, y, a[2] - 0.02), (b[0] + sx * 0.02, y, b[2] + 0.02), 0.09, 0.12,
                         m_post, lod, ch=0.008)
    # cross beams (twin / trestle): laid over the long beams at each post pair, ends projecting
    if st != 'raked':
        for x in xs_post:
            zc = z_bt + 0.11 + 0.06 * (abs(x) / (W / 2)) ** 3 if lod <= 2 else z_bt + 0.11
            mb.box((x, 0, zc), (0.16, P['depth'] + 0.5, 0.22), m_x) if lod > 0 else \
                C.chamfered_bar(mb, (x, 0, zc), (0.16, P['depth'] + 0.5, 0.22), m_x, ch=0.012, axis='y')
        if lod <= 1:                                 # low cross ties between the frames
            for x in xs_post:
                mb.box((x, 0, z_bb - 0.75), (0.09, P['depth'] - bw, 0.16), m_x)
    else:
        # raking struts from the post (at 0.48 of the height) to the ground, plus a sole plate under each post
        zs = z_bb * 0.48
        for x in xs_post:
            for sy in (-1, 1):
                foot = (x, sy * (P['depth'] / 2 - 0.08), 0.06)
                top = (x, sy * ps / 2, zs)
                if lod <= 2:
                    _bar(mb, foot, top, 0.11, 0.13, m_post, lod, ch=0.01)
                else:
                    _bar(mb, foot, top, 0.11, 0.13, m_post, lod)
            if lod <= 2:
                mb.box((x, 0, 0.06), (0.18, P['depth'], 0.12), m_x)
    # ---------------------------------------------------------------- hang points, sheaves, rope run, cleats
    nh = P['cleats']
    if st == 'trestle':
        bays = [(-xp + ps / 2 + 0.45, -ps / 2 - 0.45), (ps / 2 + 0.45, xp - ps / 2 - 0.45)]
        hx = []
        per = [nh // 2 + nh % 2, nh // 2]
        for (a, b), k in zip(bays, per):
            hx += [a + (b - a) * (i + 0.5) / k for i in range(k)] if k else []
    else:
        a, b = -xp + ps / 2 + 0.5, xp - ps / 2 - 0.5
        hx = [a + (b - a) * (i + 0.5) / nh for i in range(nh)]
    hang = []
    for i, x in enumerate(sorted(hx)):
        y = lines[i % len(lines)] if st != 'raked' else 0.0
        hang.append((x, y))
    hooks = []
    zsh = z_bb - 0.16                                 # sheave centre
    for i, (x, y) in enumerate(hang):
        if lod <= 1:
            for sy in (-1, 1):                       # strap cheeks
                mb.box((x, y + sy * 0.03, z_bb - 0.09), (0.05, 0.008, 0.2), m_iron)
            mb.cylinder((x, y, zsh), 0.07, 0.04, m_wheel, segs=C.lod_pick(lod, 14, 8), rot=(math.pi / 2, 0, 0))
            mb.box((x, y, z_bb - 0.005), (0.12, 0.08, 0.012), m_iron)       # top plate
        elif lod == 2:
            mb.box((x, y, zsh + 0.04), (0.14, 0.06, 0.22), m_iron)
        # rope: cleat on a post front -> up the post -> along the beam underside -> over the sheave -> fall
        side = -1 if x < 0 else 1
        px = side * xp if st != 'trestle' or abs(x) > xp * 0.5 else 0.0
        py = y
        yf = py + ps / 2 + 0.016                     # rope runs down the post's front face
        zc = P['cleat_z'][i]
        dy = 0.022 * (i - (len(hang) - 1) / 2) * 0.5
        ru = z_bb - 0.016
        run = [(px + side * 0.0 + dy, yf, zc + 0.02), (px + dy, yf, ru - 0.02), (px + dy, py + 0.0, ru),
               (x - side * 0.07, py + 0.0, ru), (x - side * 0.07, py, zsh + 0.02)]
        if lod <= 1:
            C.tube(mb, run, [0.011] * len(run), m_rope, sides=C.lod_pick(lod, 6, 4))
            # the fall from the sheave to the hook
            C.tube(mb, [(x + side * 0.07, y, zsh), (x + side * 0.07, y, zsh - 0.3)], [0.011, 0.011], m_rope,
                   sides=C.lod_pick(lod, 6, 4), cap1=True)
            hz = zsh - 0.3
            mb.cylinder((x + side * 0.07, y, hz - 0.04), 0.035, 0.012, m_iron, segs=C.lod_pick(lod, 10, 6),
                        rot=(math.pi / 2, 0, 0))                                  # hook ring
            hooks.append((x + side * 0.07, y, hz - 0.075))
        elif lod == 2:
            C.rope_cord(mb, (px, yf, zc), (px, yf, ru), 0.014, m_rope, sides=2)
            C.rope_cord(mb, (px, py, ru - 0.02), (x, py, ru - 0.02), 0.014, m_rope, sides=2)
            C.rope_cord(mb, (x + side * 0.07, y, zsh), (x + side * 0.07, y, zsh - 0.32), 0.014, m_rope, sides=2)
            hooks.append((x + side * 0.07, y, zsh - 0.375))
        else:
            hooks.append((x + side * 0.07, y, zsh - 0.375))
        # horn cleat on the post front with rope turns
        if lod <= 1:
            cy = yf + 0.03
            mb.box((px + dy, py + ps / 2 + 0.03, zc), (0.06, 0.06, 0.12), m_x)            # stem block
            if lod == 0:
                _bar(mb, (px + dy - 0.15, cy + 0.02, zc - 0.03), (px + dy + 0.15, cy + 0.02, zc - 0.03), 0.05, 0.045,
                     m_x, 0, ch=0.01)
                C.rope_turns(mb, (px + dy, cy + 0.02, zc - 0.03), (1, 0, 0), 0.026, 3, m_rope, cord=0.009, pitch=0.02)
                C.tube(mb, [(px + dy + 0.03, cy + 0.04, zc - 0.05), (px + dy + 0.05, cy + 0.06, zc - 0.2),
                            (px + dy + 0.03, cy + 0.05, zc - 0.36)], [0.01, 0.01, 0.008], m_rope, sides=5, cap1=True)
            else:
                mb.box((px + dy, cy + 0.02, zc - 0.03), (0.3, 0.05, 0.045), m_x)
    # ---------------------------------------------------------------- hanging lanterns between the hang points
    nl = P['lanterns']
    if nl:
        xs_all = sorted([x for x, _ in hang])
        cand = []
        edges = [-xp + ps / 2] + xs_all + [xp - ps / 2]
        gaps = sorted(range(len(edges) - 1), key=lambda k: -(edges[k + 1] - edges[k]))
        for k in sorted(gaps[:nl]):
            cand.append((edges[k] + edges[k + 1]) / 2)
        cand = cand[:nl]
        for j, x in enumerate(cand):
            x += P['lantern_jit'][j] * 0.5
            y = lines[(j + 1) % len(lines)] if st != 'raked' else 0.0
            lh, ls, cord = 0.34, 0.2, 0.25
            base = (x, y, z_bb - cord - lh - 0.12)
            if lod <= 1:
                C.rope_cord(mb, (x, y, base[2] + lh + 0.08), (x, y, z_bb), 0.006, m_rope, sides=C.lod_pick(lod, 6, 4),
                            twist=lod == 0)
                mb.box((x, y, z_bb - 0.008), (0.06, 0.06, 0.016), m_iron)
            elif lod == 2:
                C.rope_cord(mb, (x, y, base[2] + lh + 0.08), (x, y, z_bb), 0.01, m_rope, sides=1)
            if lod <= 2:
                c = C.lantern_head(mb, base, dict(iron=m_iron, paper=m_paper), lod, size=ls, height=lh, roof='hip')
            else:
                bm = mb.bm
                q = [bm.verts.new(v) for v in ((x - ls / 2, y, base[2]), (x + ls / 2, y, base[2]),
                                                (x + ls / 2, y, base[2] + lh), (x - ls / 2, y, base[2] + lh))]
                f = bm.faces.new(q); f.material_index = m_paper
                c = Vector((x, y, base[2] + lh / 2))
            lights.append(C.light_entry(c, color_k=2200, watts=18))
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    kg.uv_grain(o, [m_post, m_x])
    for L in lights:
        L['pos'] = [round(L['pos'][0] + dx, 4), round(L['pos'][1] + dy, 4), round(L['pos'][2] + dz, 4)]
    C.set_json_props(o, kz_lights=lights,
                     kz_hang_points=[[round(a + dx, 3), round(b + dy, 3), round(c + dz, 3)] for a, b, c in hooks],
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()
                                if not isinstance(v, list)})
    return o
