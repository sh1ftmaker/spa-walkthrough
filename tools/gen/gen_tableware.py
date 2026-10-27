"""Tableware set (tableware): ramen bowl, tea cup, lidded jar, soy dish, side tray, chopsticks on a rest;
bowl stacks. For the Kawagiri pod tables and the b2_core ramen counter.

Identifying features kept at every LOD: dark speckled ramen bowl, stoneware tea cup, lidded jar, small
soy dish, rectangular side tray, chopsticks on a rest; bowl stacks.

Targets (08 close-up; the chopsticks, 0.23 m, set the scale: 545 px in the 1600 px frame -> ~2370 px/m
at the bowl's depth, foreshortened)
  * ramen bowl: ~0.24 m across (r 0.11-0.13), height ~0.09-0.10 (h/D ~0.40), a 0.08-0.09 m foot ring, deep
    rounded belly with a slight flare, a 3-4 mm rounded lip; near-black speckled glaze (tenmoku).
  * tea cup (yunomi): ~0.085 m across, ~0.08 m tall, near-straight wall, grey-green speckled (celadon).
  * lidded jar: ~0.085 m across, ~0.10 m tall with lid and knob, dark glaze.
  * soy dish: ~0.09 m across, ~0.025 m deep, dark speckled.
  * side tray: black lacquer rectangle ~0.17 x 0.09 x 0.02 m with 3 compartments.
  * chopsticks 0.23 m, tips resting on a small ceramic rest.
  * set footprint 0.4 x 0.3 (row and proxy), height 0.15 (stack).
Construction
  * every vessel is one closed lathe solid with real wall thickness, a turned foot and a rounded lip
    (kzgeo_tableware profiles). Bowl 24 segments at LOD0, cup/dish 16, jar 12.
  * fill (meal layout): a broth surface 28 % below the rim, two halved eggs (white + yolk), a standing nori
    sheet and two chashu slices; records kz_fx = fx_steam above the bowl (runtime steam).
  * layouts (cycle with the seed): meal (filled bowl centre, cup, jar, dish, tray, chopsticks: concept 08),
    tea (empty smaller bowl, two cups, jar, dish, tray, chopsticks), stack (counter stock: 2-3 nested
    bowls, 2-3 stacked dishes, cup, chopsticks on a rest). Nested pieces under the top one are built
    as outer shells (their insides are hidden).
  * LOD1: fewer profile rings and segments, every item kept. LOD2: 6-8-segment silhouettes, the stack as one
    lathe, chopsticks as one bar, no rest or toppings. LOD3: bowl (or stack), cup and tray only.
Materials: ceramic tenmoku (bowl, jar, rest), glaze set by `glaze` for cup and dish (celadon | white |
tenmoku), lacquer_black tray and nori, hinoki stained chopsticks; food on tinted ceramic white (broth,
egg, yolk, chashu): proposed library entry `food_glaze` (see report).
Animation: none (steam: fx_steam anchor in kz_fx). Lighting: lightmap.

Parameters (build kwargs; proxy 0.4 x 0.3 x 0.15 m)
  items   set | bowl | cup | jar | dish | tray | chopsticks  (default set)
  layout  meal | tea | stack                  (default: cycles with the seed: 1 meal, 2 tea, 3 stack)
  bowl_r  0.10-0.15 m (default seeded 0.11-0.125; tea 0.10)
  glaze   celadon | white | tenmoku           (default: walks with the seed, seed 1 celadon as 08)
  fill    True | False (broth and toppings; default True for meal)
  stack_n 2-4 nested bowls (default seeded 2-3; 4 runs ~10 % over the LOD0 budget and to 0.155 m)
Seeds change: layout, glaze, bowl radius and depth, cup height, jar shape, item positions, stack count.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_tableware as P

ASSET = 'tableware'
FEATURES = ['dark speckled ramen bowl', 'stoneware tea cup', 'lidded jar', 'soy dish', 'side tray',
            'chopsticks on a rest', 'bowl stacks']
LAYOUTS = ['meal', 'tea', 'stack']
GLAZES = ['celadon', 'white', 'tenmoku']


def build(lod, seed, items='set', layout=None, bowl_r=None, glaze=None, fill=None, stack_n=None):
    layout = layout or C.cycle(seed, LAYOUTS)
    glaze = glaze or GLAZES[(seed - 1 + (seed - 1) // 3) % 3]
    g = C.rng(seed, 'sizes')
    R = max(0.10, min(0.15, bowl_r)) if bowl_r else (0.10 if layout == 'tea' else g.uniform(0.11, 0.125))
    BH = R * g.uniform(0.74, 0.84)
    CR, CH = g.uniform(0.038, 0.044), g.uniform(0.07, 0.085)
    JR, JH = g.uniform(0.038, 0.044), g.uniform(0.09, 0.105)
    DR, DH = g.uniform(0.042, 0.048), g.uniform(0.022, 0.028)
    n_stack = stack_n or g.randint(2, 3)
    fill = (layout == 'meal') if fill is None else fill
    gp = C.rng(seed, 'layout')

    def j(v=0.008):
        return gp.uniform(-v, v)

    mb = genlib.MeshBuilder()
    m_bowl = mb.slot('ceramic', variant='tenmoku')
    m_glaze = mb.slot('ceramic', variant=glaze)
    m_jar = mb.slot('ceramic', variant='tenmoku' if glaze != 'tenmoku' else 'celadon')
    m_tray = mb.slot('lacquer_black')
    m_chop = mb.slot('hinoki', variant='stained')
    m_broth = mb.slot('ceramic', variant='white', tint=(0.86, 0.62, 0.36))
    m_egg = mb.slot('ceramic', variant='white')
    m_yolk = mb.slot('ceramic', variant='white', tint=(1.0, 0.42, 0.06))
    m_meat = mb.slot('ceramic', variant='white', tint=(0.42, 0.2, 0.1), roughness_offset=0.25)

    S_B = C.lod_pick(lod, 24, 10, 8, 6)
    S_C = C.lod_pick(lod, 16, 8, 6, 4)
    S_J = C.lod_pick(lod, 12, 8, 6, 5)
    S_D = C.lod_pick(lod, 14, 8, 6, 5)
    if layout == 'stack':
        S_B = C.lod_pick(lod, 16, 8, 8, 6)

    def bowl(x, y, z=0.0, r=R, h=BH, nested=False):
        if nested and lod <= 1:
            C.lathe(mb, P.bowl_outer(r, h, lod=lod), S_B, m_bowl, base=(x, y, z))
            return
        if lod >= 2:
            prof = [(0.0, 0.0), (r * 0.4, 0.0), (r * 0.85, h * 0.45), (r, h), (r * 0.72, h * 0.8), (0.0, h * 0.42)]
            if lod == 3:
                prof = [(0.0, 0.0), (r, h), (0.0, h * 0.45)]
        else:
            prof = P.bowl(r, h, lod=lod)
        C.lathe(mb, prof, S_B, m_bowl, base=(x, y, z))

    def cup(x, y, z=0.0):
        if lod >= 2:
            prof = [(0.0, 0.0), (CR * 0.85, 0.0), (CR, CH), (0.0, CH * 0.8)]
        else:
            prof = P.cup(CR, CH, lod=lod)
        C.lathe(mb, prof, S_C, m_glaze, base=(x, y, z))

    def jar(x, y):
        if lod >= 2:
            prof = [(0.0, 0.0), (JR, JH * 0.45), (JR * 0.68, JH * 0.85), (0.0, JH)]
        else:
            prof = P.jar(JR, JH, lod=lod)
        C.lathe(mb, prof, S_J, m_jar, base=(x, y, 0.0))

    def dish(x, y, z=0.0, nested=False):
        if nested and lod <= 1:
            C.lathe(mb, P.dish_outer(DR, DH), S_D, m_glaze, base=(x, y, z))
            return
        if lod >= 2:
            prof = [(0.0, 0.0), (DR, DH), (0.0, DH * 0.45)]
        else:
            prof = P.dish(DR, DH, lod=lod)
        C.lathe(mb, prof, S_D, m_glaze, base=(x, y, z))

    def tray(x, y, w=0.17, d=0.085, h=0.022):
        if lod >= 2:
            mb.box((x, y, h / 2), (w, d, h), m_tray)
            return
        t = 0.006
        bev = 0.002 if lod == 0 else 0.0
        C.board(mb, (x, y, 0.004), (w, d, 0.008), m_tray, bevel=bev)
        for sy in (-1, 1):
            mb.box((x, y + sy * (d / 2 - t / 2), h / 2), (w, t, h), m_tray)
        for sx in (-1, 1):
            mb.box((x + sx * (w / 2 - t / 2), y, h / 2), (t, d - 2 * t, h), m_tray)
        for k in (-1, 1):
            mb.box((x + k * w / 6, y, h * 0.42), (0.004, d - 2 * t, h * 0.84 - 0.008), m_tray)

    def chopsticks(x0, x1, y):
        """pair lying along X, tips (x1 end) raised on a rest"""
        rz = 0.012
        if lod >= 2:
            mb.box(((x0 + x1) / 2, y, 0.006), (x1 - x0, 0.022, 0.012), m_chop)
            return
        xr = x1 - 0.045
        C.board(mb, (xr, y, 0.006), (0.014, 0.05, 0.012), m_bowl, bevel=0.003 if lod == 0 else 0.0)
        for dy in (-0.0065, 0.0065):
            C.stick(mb, (x0, y + dy, 0.0045), (x1, y + dy * 0.6, rz + 0.0025), 0.0045, 0.002, m_chop,
                    segs=C.lod_pick(lod, 6, 4))

    def toppings(x, y, r=R, h=BH):
        zl = h * 0.72
        rb = r * 0.905 - 0.004
        C.lathe(mb, [(rb, zl), (0.0, zl + 0.003)], S_B, m_broth, base=(x, y, 0.0), closed=False)
        if lod >= 2:
            return
        ge = C.rng(seed, 'egg')
        for k in range(2):
            a = math.radians(200 + 35 * k + ge.uniform(-8, 8))
            ex, ey = x + 0.5 * r * math.cos(a), y + 0.5 * r * math.sin(a)
            eprof = [(0.0, -0.004), (0.016, 0.0), (0.02, 0.009), (0.011, 0.0105)]
            if lod == 1:
                eprof = [(0.0, -0.004), (0.02, 0.009), (0.011, 0.0105)]
            vs, _ = C.lathe(mb, eprof,
                            C.lod_pick(lod, 10, 6), m_egg, base=(ex, ey, zl), closed=False)
            vy, _ = C.lathe(mb, [(0.011, 0.0105), (0.0, 0.0135)], C.lod_pick(lod, 10, 6), m_yolk,
                            base=(ex, ey, zl), closed=False)
            for v in vs + vy:                      # oval: stretch along the radial direction
                d = v.co.x - ex, v.co.y - ey
                v.co.x = ex + d[0] * (1 + 0.3 * abs(math.cos(a)))
                v.co.y = ey + d[1] * (1 + 0.3 * abs(math.sin(a)))
        # chashu slices and a standing nori sheet at the back rim
        for k, (dx, dy, yaw) in enumerate(((0.35, -0.2, 0.4), (0.15, 0.25, -0.3))):
            mb.box((x + dx * r, y + dy * r, zl + 0.004), (0.055, 0.04, 0.007), m_meat, rot=(0.12 * (k - 0.5), 0.0, yaw))
        C.board(mb, (x - 0.15 * r, y - 0.72 * r, zl + 0.028), (0.07, 0.0025, 0.06), m_tray, bevel=0.0,
                rot=(0.35, 0.0, 0.15))

    fx = []
    if items != 'set':
        {'bowl': lambda: bowl(0, 0), 'cup': lambda: cup(0, 0), 'jar': lambda: jar(0, 0),
         'dish': lambda: dish(0, 0), 'tray': lambda: tray(0, 0),
         'chopsticks': lambda: chopsticks(-0.115, 0.115, 0)}[items]()
        if items == 'bowl' and fill:
            toppings(0, 0)
    elif layout == 'meal':
        bx, by = j(), 0.03 + j()
        bowl(bx, by)
        if fill and lod <= 2:
            toppings(bx, by)
            fx.append(dict(type='fx_steam', pos=[bx, by, BH + 0.02]))
        if lod <= 2:
            jar(-0.155 + j(0.005), 0.10 + j(0.005))
            dish(0.15 + j(0.005), -0.045 + j(0.005))
            chopsticks(-0.07, 0.165, -0.125)
        cup(0.155 + j(0.004), 0.085 + j(0.004))
        tray(-0.115, -0.065)
    elif layout == 'tea':
        bowl(0.04 + j(), 0.05 + j(), r=R, h=R * 0.7)
        cup(-0.06 + j(0.004), 0.09 + j(0.004))
        if lod <= 2:
            cup(0.16 + j(0.004), -0.03 + j(0.004))
            jar(-0.16 + j(0.004), 0.09 + j(0.004))
            dish(0.155, 0.095)
            chopsticks(-0.06, 0.175, -0.125)
        tray(-0.11, -0.05)
    else:  # stack: nested bowls, stacked dishes, cup, jar
        sx, sy = -0.085 + j(0.005), 0.025 + j(0.005)
        pitch = min(BH * 0.30, (0.155 - BH) / max(1, n_stack - 1))
        if lod >= 2:
            top = BH + pitch * (n_stack - 1)
            prof = [(0.0, 0.0), (R * 0.4, 0.0), (R * 0.85, BH * 0.45), (R, BH), (R * 1.005, top), (R * 0.72, top - BH * 0.2),
                    (0.0, top - BH * 0.58)]
            if lod == 3:
                prof = [(0.0, 0.0), (R, BH), (R, top), (0.0, top - BH * 0.55)]
            C.lathe(mb, prof, S_B, m_bowl, base=(sx, sy, 0.0))
        else:
            for k in range(n_stack):
                bowl(sx, sy, z=k * pitch, nested=k < n_stack - 1)
        cup(0.11 + j(0.004), 0.085 + j(0.004))
        if lod <= 2:
            nd = C.rng(seed, 'dishes').randint(2, 3)
            for k in range(nd if lod <= 1 else 1):
                dish(0.07, -0.085, z=k * DH * 0.6, nested=k < nd - 1)
            chopsticks(-0.17, 0.065, -0.125)

    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    if fx:
        for f in fx:
            f['pos'] = [round(f['pos'][0] + dx, 3), round(f['pos'][1] + dy, 3), round(f['pos'][2] + dz, 3)]
        C.set_json_props(o, kz_fx=fx)
    return genlib.finish(o)
