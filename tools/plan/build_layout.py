"""Build 3d/layout.json: the metric layout of Kazan-yu.

Coordinates (metres): x increases east from the west edge of column A, y increases
north from the south edge of row 6, z is elevation. Cell C3 = x 40-60, y 60-80.

This file is the source of truth for level heights, space footprints, vertical
connections (stairs are generated here from their rise) and water levels.
Run:  .venv/bin/python tools/plan/build_layout.py   (writes 3d/layout.json)
"""
import json, math, os, sys
from shapely.geometry import Polygon, LineString, Point, mapping
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLS = 'ABCDEFGHIJ'
CELL = 20.0
RISER, TREAD = 0.17, 0.29          # target step size
LANDING_EVERY, LANDING_LEN = 14, 1.5


def cell(c):
    """'C3' -> (x0, y0, x1, y1)"""
    i = COLS.index(c[0]); r = int(c[1:])
    return (i * CELL, (6 - r) * CELL, (i + 1) * CELL, (7 - r) * CELL)


def cell_of(x, y):
    return f"{COLS[min(9, max(0, int(x // CELL)))]}{6 - min(5, max(0, int(y // CELL)))}"


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def circle(cx, cy, r, n=32):
    return [[round(cx + r * math.cos(2 * math.pi * k / n), 3), round(cy + r * math.sin(2 * math.pi * k / n), 3)] for k in range(n)]


def ellipse(cx, cy, rx, ry, n=40):
    return [[round(cx + rx * math.cos(2 * math.pi * k / n), 3), round(cy + ry * math.sin(2 * math.pi * k / n), 3)] for k in range(n)]


class Band(list):
    """Footprint list that remembers the centreline and width it was made from."""
    centerline = None; width = None


def band(points, width):
    """Corridor footprint: polyline buffered to a width (flat caps)."""
    g = LineString(points).buffer(width / 2, cap_style=2, join_style=2, mitre_limit=3)
    b = Band([[round(x, 3), round(y, 3)] for x, y in list(g.exterior.coords)[:-1]])
    b.centerline = [list(p) for p in points]; b.width = width
    return b


# ---------------------------------------------------------------- stairs
def step_plan(rise):
    n = max(1, round(abs(rise) / RISER))
    return n, abs(rise) / n


def helix(id, center, r_walk, z_top, z_bot, a_start_deg, turn=-1, width=2.4, stops=(), note=''):
    """Helical stair. Angle advances `turn` (+1 ccw / -1 cw) going DOWN. Landings every
    LANDING_EVERY steps and at each stop z (a level doorway)."""
    n, rise = step_plan(z_top - z_bot)
    dth = TREAD / r_walk
    dland = LANDING_LEN / r_walk
    pts, a, z = [], math.radians(a_start_deg), z_top
    cx, cy = center
    stops = sorted(stops, reverse=True)
    landings = 0
    pts.append([cx + r_walk * math.cos(a), cy + r_walk * math.sin(a), z])
    for k in range(1, n + 1):
        a += turn * dth; z -= rise
        pts.append([cx + r_walk * math.cos(a), cy + r_walk * math.sin(a), z])
        at_stop = any(abs(z - s) < rise / 2 for s in stops)
        if (k % LANDING_EVERY == 0 or at_stop) and k < n:
            a += turn * (dland * (2.0 if at_stop else 1.0)); landings += 1
            pts.append([cx + r_walk * math.cos(a), cy + r_walk * math.sin(a), z])
    turns = abs(a - math.radians(a_start_deg)) / (2 * math.pi)
    return dict(id=id, kind='helix', center=list(center), r_walk=r_walk, width=width, z_top=z_top, z_bottom=z_bot,
                steps=n, riser=round(rise, 4), tread=TREAD, landings=landings, turns=round(turns, 3),
                pitch_per_turn=round((z_top - z_bot) / turns, 2), a_start_deg=a_start_deg, turn=turn,
                path=[[round(p, 3) for p in q] for q in pts], note=note)


def path_stair(id, pts2d, z_top, z_bot, width, note='', allow_ramps=True):
    """Stair along a 2D polyline, from z_top at pts2d[0] to z_bot at the end. Steps are spread
    in runs separated by landings; extra length beyond what the steps need becomes level walkway
    (split evenly between the runs) so the riser stays at the target."""
    L = LineString(pts2d).length
    n, rise = step_plan(z_top - z_bot)
    runs = math.ceil(n / LANDING_EVERY)
    need = n * TREAD + (runs - 1) * LANDING_LEN
    if need > L + 1e-6:
        raise ValueError(f'{id}: path {L:.1f} m is shorter than the {need:.1f} m the {n} steps need')
    spare = L - need
    return dict(id=id, kind='path_stair', width=width, z_top=z_top, z_bottom=z_bot, steps=n, riser=round(rise, 4),
                tread=TREAD, runs=runs, landings=runs - 1, length=round(L, 2), level_walk=round(spare, 2),
                plan=[[round(x, 3), round(y, 3)] for x, y in pts2d], note=note)


def switchback(id, x0, y_top, y_bot, z_top, z_bot, flight_w, gap, flights, start_dir=-1, note=''):
    """Flights side by side running along y, alternating direction, stepping east by flight_w+gap."""
    n, rise = step_plan(z_top - z_bot)
    per = [n // flights + (1 if i < n % flights else 0) for i in range(flights)]
    fl, z, d = [], z_top, start_dir
    for i, k in enumerate(per):
        x = x0 + i * (flight_w + gap) + flight_w / 2
        mids = math.ceil(k / LANDING_EVERY) - 1
        run = k * TREAD + mids * LANDING_LEN
        ys = y_top if d < 0 else y_bot
        fl.append(dict(x=round(x, 3), y_start=round(ys, 3), y_end=round(ys + d * run, 3), z_start=round(z, 3),
                       z_end=round(z - k * rise, 3), steps=k, mid_landings=mids))
        z -= k * rise; d = -d
    span = max(abs(f['y_end'] - f['y_start']) for f in fl)
    if span > abs(y_top - y_bot) + 1e-6:
        raise ValueError(f'{id}: flights need {span:.1f} m but only {abs(y_top - y_bot):.1f} m given')
    return dict(id=id, kind='switchback', z_top=z_top, z_bottom=z_bot, steps=n, riser=round(rise, 4), tread=TREAD,
                flight_width=flight_w, gap=gap, flights=fl, box=rect(x0, min(y_top, y_bot) - 3,
                x0 + flights * flight_w + (flights - 1) * gap, max(y_top, y_bot) + 3), note=note)


# ---------------------------------------------------------------- levels
LEVELS = [
    dict(id='summit', name='Summit', floor_z=120.0, ceiling_z=None, outdoor=True),
    dict(id='ground', name='Ground', floor_z=0.0, ceiling_z=9.0),
    dict(id='b1', name='B1 Thermal', floor_z=-20.0, ceiling_z=-7.0),
    dict(id='b2', name='B2 River', floor_z=-40.0, ceiling_z=-28.0),
    dict(id='b3', name='B3 Aqua Cavern', floor_z=-67.0, ceiling_z=-50.0),
    dict(id='b4', name='B4 Magma', floor_z=-100.0, ceiling_z=-92.0),
]
SEA = -70.0
LIFT = (90.0, 70.0)            # E3, every level
SHAFT_R = 8.0                  # spiral stair shaft (lift core r 2.2 inside)
SLIDE = (150.0, 50.0)          # H4, B1 -> B3
SLIDE_SHAFT_R = 9.0

S = []                         # spaces


def space(id, name, level, footprint, floor_z, ceiling_z, kind, **kw):
    if isinstance(footprint, Band):
        kw.update(centerline=footprint.centerline, width=footprint.width); footprint = list(footprint)
    S.append(dict(id=id, name=name, level=level, kind=kind, footprint=footprint, floor_z=floor_z,
                  ceiling_z=ceiling_z, **kw))


# ---- Ground (0 m)
space('g_road', 'Approach road', 'ground', band([(0, 57), (14, 55)], 7), 0.0, None, 'outdoor')
space('g_gate', 'Basalt Gate forecourt', 'ground', [[12, 40], [30, 40], [40, 42], [40, 68], [12, 66]], 0.0, None, 'outdoor',
      note='Torii of single basalt columns at A4, facing east toward the hall door.')
space('g_arrival', 'Arrival hall (lava window)', 'ground', rect(40, 42, 100, 80), 0.0, 16.0, 'hall',
      note='Carved into the mountain foot; south facade is timber under the cliff. Lava window on the north wall x 44-78. Spiral/lift core in the NE corner.')
space('g_changing', 'Changing halls', 'ground', rect(100, 42, 140, 80), 0.0, 6.0, 'hall')
space('g_terrace', 'South terrace', 'ground', [[30, 24], [150, 24], [150, 42], [40, 42], [30, 40]], 0.0, None, 'outdoor',
      note='Front of the halls; cable lift base at E5; steps down to the B5 pools.')
space('g_cascade', 'Cascade Terrace pools (lower)', 'ground', [[12, 4], [62, 4], [62, 24], [30, 24], [12, 38]], -1.0, None, 'outdoor',
      note='Lowest terraces, -0.5 to -4 m, stepping down south; drains north into the mountain to B1.')
space('g_east', 'East cliff terrace', 'ground', rect(140, 42, 162, 78), 0.0, None, 'outdoor',
      note='Ledge on the east cliff outside the changing halls; the sea-cliff path leads north from it to the Cliff Stair foot.')

space('g_east_path', 'Sea-cliff path round the NE shoulder', 'ground', band([(160, 74), (192, 80), (194, 110)], 3.0), 0.0, None, 'outdoor',
      note='Cliff-top path along the east edge from the east terrace to the foot of the north cliff.')
space('g_north_ledge', 'North cliff foot ledge', 'ground', rect(122, 108, 200, 119), 0.0, None, 'outdoor',
      note='Foot of the north cliff below the suites; sea cliff beyond.')

# ---- B1 (-20 m). Walk datum -20.0 = stepping-stone tops and pool rims; corridor water -20.05.
space('b1_lobby', 'B1 lift lobby', 'b1', [[round(x, 3), round(y, 3)] for x, y in list(Polygon(circle(*LIFT, 12.5)).difference(Point(112, 92).buffer(20.5, 48)).exterior.coords)[:-1]], -20.0, -15.5, 'hall',
      note='Ring round the spiral well, clipped to keep rock between it and the Mirror dome.')
space('b1_cor_mirror', 'Mist corridor to the Mirror', 'b1', band([(78, 72), (68, 74), (66, 92), (94, 92)], 4.0), -20.0, -17.0, 'corridor',
      note='Compressed passage (4 m wide, 3 m high) before the Mirror reveal.')
space('b1_junction_w', 'Koi junction', 'b1', circle(66, 74, 5.5), -20.0, -16.5, 'corridor')
space('b1_cor_west', 'Mist corridor west', 'b1', band([(62, 76), (56, 80), (47, 80.5)], 4.0), -20.0, -17.0, 'corridor')
space('b1_mirror', '05 Obsidian Mirror Float Pool', 'b1', circle(112, 92, 19), -20.0, -6.5, 'cave',
      note='Dome with glowworm ceiling. Shaped around the lift core: pool centre moved to F2 (logged).')
space('b1_grotto', '06 Fumarole Steam Grotto', 'b1', [[40, 83.5], [62, 83.5], [62, 96], [80, 96], [80, 108], [62, 112], [40, 108]], -20.0, -9.0, 'cave',
      note='Rooms 45/55/65 C, hotter as you go deeper (NW).')
space('b1_cor_north', 'Return corridor (glacier to steam)', 'b1', band([(78, 104), (88, 115), (140, 115), (166, 100)], 4.0), -20.0, -17.0, 'corridor')
space('b1_cor_east', 'Mist corridor east', 'b1', band([(130, 90), (142, 86), (166, 84)], 4.0), -20.0, -17.0, 'corridor')
space('b1_treatment', 'Treatment rooms', 'b1', [[120, 60], [137, 60], [137, 61], [160, 61], [160, 80], [128.6, 80], [127.7, 78.8], [125.2, 76.3], [122.3, 74.3], [120, 73.1]], -20.0, -16.0, 'hall')
space('b1_glacier', '07 Glacier Plunge Ice Cave', 'b1', [[164, 66], [196, 66], [197.875, 96], [164, 96]], -20.0, -8.0, 'cave')
space('b1_cor_south', 'Mist corridor south', 'b1', band([(101, 64), (114, 56), (138, 54)], 4.0), -20.0, -17.0, 'corridor')
space('b1_slide_top', 'Magma Glass Slide launch / Lava Stair head', 'b1', rect(138, 40, 162, 60), -20.0, -12.0, 'hall')
space('b1_outfall', 'Outfall to the river (J2)', 'b1', rect(166, 98, 194, 102), -20.0, -17.0, 'corridor',
      note='Corridor water spills down a shaft at J2 to the B2 river head.')

# ---- B2 (deck -40 m, river -42.0 east -> -43.0 at the lip)
RIVER = [(200, 94, 10), (176, 92, 10), (150, 86, 12), (130, 84, 16), (118, 85, 22), (64, 85, 22), (46, 84, 16), (34, 80, 12), (30, 77, 12)]
space('b2_kawagiri', 'Kawagiri restaurant', 'b2', [[round(x, 3), round(y, 3)] for x, y in list(Polygon(rect(46, 74, 122, 100)).difference(Point(*LIFT).buffer(SHAFT_R + 0.4, 32)).exterior.coords)[:-1]], -40.0, -28.0, 'deck',
      note='Spine deck on beams along y 84 over the widened river; 6 pods each side over the water.')
space('b2_core', 'Kawagiri core (lift, kitchen, ramen)', 'b2', rect(46, 56, 122, 74), -40.0, -28.0, 'hall')
space('b2_boat', 'Boat landing', 'b2', rect(122, 64, 142, 80), -40.0, -30.0, 'deck')
space('b2_boardwalk', 'Riverside boardwalk', 'b2', band([(140, 76), (160, 81), (180, 85), (196, 87)], 3.5), -40.0, -32.0, 'deck')
space('b2_boardwalk_edge', 'Boardwalk river edge (open to the river)', 'b2', band([(140, 78.6), (160, 83.6), (180, 87.6), (196, 89.6)], 2.4), -44.6, -32.0, 'channel', walkable=False,
      note='Opens the rock between the boardwalk and the river so you walk beside the water behind a railing (B2 agent review).')
space('b2_lava_link', 'Passage to the Lava Stair', 'b2', band([(134, 66), (146, 60), (148.5, 58.5)], 3.5), -40.0, -37.0, 'corridor')
space('b2_falls_head', 'Falls Stair head', 'b2', rect(40, 58, 47, 70), -40.0, -32.0, 'deck')

space('b2_river', 'Underground river channel', 'b2', None, -44.6, -32.0, 'channel', walkable=False,
      note='Void of the river from the J2 inflow to the falls lip; floor is the river bed. Footprint = w_river footprint.')

# ---- B3 (deck -67; sea -70)
space('b3_cavern', 'Aqua Cavern vault (envelope)', 'b3', [[46, 14], [160, 12], [160, 16], [164, 64], [120, 82], [76, 84], [46, 80]], -67.0, -50.0, 'envelope', walkable=False,
      note='The one great vault over rimstone, lazy river, geyser plaza and slide foot (roof -50, domed). Sub-spaces sit inside it; the lazy river tube is an asset, not shell.')
space('b3_falls', '09 Thunder Curtain Falls basin', 'b3', [[8, 40], [46, 40], [46, 74.5], [38, 74.5], [38, 76], [8, 76]], -59.5, -40.0, 'cave',
      note='Tall shaft under the river lip. Pool -60.0, curtain from the lip at -43.')
space('b3_rimstone', '08 Rimstone Cascade Terraces', 'b3', [[50, 26], [86, 26], [86, 64], [76, 74], [50, 74]], -60.0, -50.0, 'cave',
      note='Terraces step -60.5 (NW) to -66.5 (SE).')
space('b3_lobby', 'B3 lift lobby', 'b3', circle(*LIFT, 12.5), -67.0, -58.0, 'hall')
space('b3_lazy', '02 Lava Tube Lazy River', 'b3', ellipse(114, 42, 28.5, 18.5), -67.0, -63.0, 'tunnel',
      note='Loop channel 6 m wide in a low lava tube (roof -63.5); island inside is the Geyser Plaza.')
space('b3_geyser', '04 Geyser Plaza', 'b3', ellipse(114, 42, 18, 8.5), -67.0, -50.0, 'cave')
space('b3_slide_foot', 'Slide splashdown / Lava Stair foot', 'b3', rect(140, 34, 162, 64), -67.0, -50.0, 'cave')
space('b3_shore', 'Shore path', 'b3', band([(150, 37), (156, 34), (164, 34)], 4.0), -67.0, -62.5, 'path',
      note='Low compressed passage (4.5 m) before the beach reveal.')
space('b3_wave', '10 Wave Grotto beach', 'b3', [[160, 16], [200, 14], [200, 62], [164, 64]], -71.0, -52.0, 'cave', beach=dict(x_top=165.0, z_top=-68.0, x_water=175.0, z_water=-70.0, z_bed=-70.6, x_bed=178.0),
      note='Black sand beach slopes -67.5 to -70.6; sea mouth on the east edge.')
space('b3_walk_north', 'North walk (lobby to rimstone)', 'b3', band([(78, 70), (70, 70), (66, 66)], 4.0), -67.0, -58.0, 'path')

space('b3_falls_east', 'Falls shaft (east, open to B2)', 'b3', rect(38, 40, 46, 74.5), -59.5, -32.0, 'cave', walkable=False,
      note='The east part of the falls shaft rises to -32 so the B2 falls-head balcony overlooks the curtain (B2 agent review).')
space('b3_falls_gallery', 'Gallery behind the curtain', 'b3', rect(8, 76, 46, 80.5), -55.0, -52.0, 'corridor',
      note='Carved walkway behind Thunder Curtain at -55, under the river (bed -44.6, 7 m of rock above the gallery roof).')

# ---- B4 (-100 m)
space('b4_lobby', 'B4 lift lobby', 'b4', circle(*LIFT, 14), -100.0, -90.0, 'hall')
space('b4_tunnel', 'Tunnel gallery', 'b4', band([(77, 64), (72.8, 62.5), (66.4, 60.3), (61.9, 58.3), (58.7, 55.8), (55.6, 51.7), (53.0, 47.6), (52.3, 44.0), (53.3, 40.0), (54.9, 36.7), (56, 34)], 5.0), -100.0, -96.5, 'corridor')
space('b4_chamber', 'Magma viewing chamber', 'b4', [[40, 6], [122, 6], [122, 30], [48, 36], [40, 30]], -100.0, -92.0, 'hall',
      note='Hush zone. Thick glass wall along y 8 with lava beyond.')

# ---- Summit (+120 m)
space('s_pool', '01 Caldera Crown Infinity Pool', 'summit', [[82, 64], [140, 64], [142, 96], [120, 104], [119.943, 107.236], [84.769, 103.816], [86, 100], [80, 84]], 120.0, None, 'outdoor')
space('s_spring', 'Spring source and egg baskets', 'summit', [[56, 86], [75, 86], [75, 100], [77, 100], [77, 106], [56, 106]], 121.5, None, 'outdoor')
space('s_moon', 'Tsukimi moon deck', 'summit', rect(142, 80, 164, 102), 120.5, None, 'outdoor')
space('s_rim', 'Rim walk', 'summit', band([(98, 62), (80, 62), (74, 66), (76, 80), (80, 101.7), (84, 105.5), (120, 109), (147.6, 104.5), (147.6, 102)], 3.5), 120.0, None, 'outdoor',
      note='Keeps off the south infinity edge and the moon deck (option A, ground/summit agent).')
space('s_rim_west', 'Terrace Path head', 'summit', band([(46, 76), (60, 70), (75, 65)], 3.5), 120.0, None, 'outdoor')

# North cliff suites (Should): 3 suites per tier, tiers at +10/+26/+43/+60, facing north at y ~114
SUITE_TIERS = [10.0, 26.0, 43.0, 60.0]
for t, z in enumerate(SUITE_TIERS):
    for k, x in enumerate((146, 164, 182)):
        space(f'suite_{t + 1}{"abc"[k]}', f'Suite tier {t + 1}{"abc"[k]}', 'cliff', rect(x - 8, 94, x + 8, 106), z, z + 3.2, 'suite', balcony=rect(x - 8, 106, x + (10 if k < 2 else 8), 110))

# ---------------------------------------------------------------- connections
C = []
spiral = helix('spiral_stair', LIFT, 5.6, 0.0, -100.0, 270, turn=-1, width=2.6, stops=(-20.0, -40.0, -67.0),
               note='Carved Spiral Stair around the main lift; doorways at each level stop.')
C.append(dict(spiral, places=['g_arrival', 'b1_lobby', 'b2_core', 'b3_lobby', 'b4_lobby'], walk=True))
C.append(dict(id='main_lift', kind='lift', at=list(LIFT), stops=[0.0, -20.0, -40.0, -67.0, -100.0], walk=False,
              places=['g_arrival', 'b1_lobby', 'b2_core', 'b3_lobby', 'b4_lobby']))

ms = switchback('mist_steps', 47.0, 79.0, 60.5, -20.0, -40.0, 4.0, 0.6, 3, start_dir=-1,
                note='Wide reflecting-pool steps (water sheets down each flight), mist-covered. B1 top landing at y 79, B2 foot inside the Kawagiri core.')
C.append(dict(ms, places=['b1_cor_west', 'b2_core'], walk=True))

# Falls Stair: B2 head (east wall of the falls shaft) -> down the east wall -> along the south wall -> up the
# west wall -> gallery behind the curtain (y 78) -> east to the pool deck.
fs1 = path_stair('falls_stair_1', [(47.5, 66), (43, 66), (43, 43), (11, 43), (10.5, 46), (10.5, 74)], -40.0, -55.0, 2.4,
                 note='Carved into the shaft walls; ends at the west end of the gallery behind the curtain.')
fs_gallery = dict(id='falls_gallery', kind='walkway', z=-55.0, width=2.4, plan=[[10.5, 74], [10.5, 78.5], [43, 78.5]],
                  note='Walkway behind Thunder Curtain Falls (curtain at y 76 from x 20 to 38).')
fs2 = path_stair('falls_stair_2', [(43, 78.5), (41.5, 76), (41.5, 62)], -55.0, -59.5, 2.4, note='Down to the pool deck.')
for c in (fs1, fs_gallery, fs2):
    C.append(dict(c, places=['b2_falls_head', 'b3_falls', 'b3_falls_gallery'], walk=True))
C.append(dict(path_stair('rimstone_stair', [(44.5, 66), (48, 66), (58, 64), (66, 58), (74, 50), (80, 40), (84, 32)], -59.5, -67.0, 2.4,
                         note='Zigzags down beside the rimstone terraces to the main B3 deck.'), places=['b3_falls', 'b3_rimstone', 'b3_lazy'], walk=True))

lava = helix('lava_stair', SLIDE, 7.2, -20.0, -67.0, 90, turn=1, width=2.2, stops=(-40.0,),
             note='Winds around the glass slide shaft; doorway at B2.')
C.append(dict(lava, places=['b1_slide_top', 'b2_lava_link', 'b3_slide_foot'], walk=True))
C.append(dict(id='glass_slide', kind='slide', center=list(SLIDE), r=3.6, z_top=-19.0, z_bottom=-66.8, walk=False,
              places=['b1_slide_top', 'b3_slide_foot']))

# Terrace Path: south-west shoulder, B5 (ground) -> rim beside the pool at D3/E3. Switchbacks.
TP_UP = [(16, 66), (6, 70), (6, 114), (14, 116), (14, 72), (22, 70), (22, 114), (30, 116), (30, 72), (38, 70), (38, 114),
         (46, 116), (46, 76)]
tp = path_stair('terrace_path', TP_UP[::-1], 120.0, 0.0, 2.4, note='Outdoor switchback stair up the west flank (legs run N-S at x 6-46), from the gate court to the plateau at C3; the rim walk leads on to the pool. Cascade pools step down beside it.')
C.append(dict(tp, places=['g_gate', 's_rim_west'], walk=True))
C.append(dict(path_stair('spring_steps', [(77.0, 101.7), (81.5, 101.7)], 121.5, 120.0, 3.0, note='Up from the rim to the spring terrace.'), places=['s_rim', 's_spring'], walk=True))
C.append(dict(path_stair('moon_steps', [(147.6, 100.5), (147.6, 104.0)], 120.5, 120.0, 3.0, note='Three risers up onto the moon deck.'), places=['s_rim', 's_moon'], walk=True))

def cliff_section(id, z0, z1, lane0, top_end=(140.0, 109.15)):
    """even number of 16 m legs between x 124 and 140, starting and ending at the tier landing (140, 109.15)"""
    n, _ = step_plan(z1 - z0)
    need = n * TREAD + (math.ceil(n / LANDING_EVERY) - 1) * LANDING_LEN
    legs = max(2, math.ceil(need / 16.0)); legs += legs % 2
    pts = [(140.0, 109.15)]
    for k in range(legs):
        lane = 111.0 if (k + lane0) % 2 == 0 else 113.4      # both lanes north of the suite balconies (y <= 110)
        pts += [(140.0 if k % 2 == 0 else 124.0, lane), (124.0 if k % 2 == 0 else 140.0, lane)]
    pts.append(top_end)
    return path_stair(id, pts[::-1], z1, z0, 2.0, note='Cliff Stair section between suite tiers.')


CS_STOPS = [0.0] + SUITE_TIERS + [120.0]
for i, (za, zb) in enumerate(zip(CS_STOPS, CS_STOPS[1:])):
    places = (['g_north_ledge'] if i == 0 else [f'suite_{i}a']) + (['s_rim'] if zb == 120.0 else [f'suite_{i + 1}a'])
    C.append(dict(cliff_section(f'cliff_stair_{i}', za, zb, i, top_end=(140.0, 107.0) if zb == 120.0 else (140.0, 109.15)), places=places, walk=True, provisional=True))
C.append(dict(id='cable_lift', kind='cable', bottom=[88, 30, 0.0], top=[96, 60, 120.0], walk=False,
              note='Inclined funicular on the south face: base E5 on the south terrace, top station on the rim at E3.'))
C.append(dict(path_stair('beach_steps', [(156.5, 35.5), (163.5, 35.5)], -67.0, -68.0, 4.0, note='Down from the shore path onto the beach.'),
              places=['b3_shore', 'b3_wave'], walk=True))
C.append(dict(path_stair('north_walk_stair', [(66, 66), (70, 70), (78, 70)], -61.5, -67.0, 3.0, note='Climbs from the lobby to the terrace shelf (32 risers); 3 m roof.'),
              places=['b3_walk_north', 'b3_rimstone', 'b3_lobby'], walk=True))
C.append(dict(id='thunder_falls', kind='fall', walk=False, places=['b2_river', 'b3_falls'], note='The river pours over the lip at (20-38, 76) into the falls shaft.'))
C.append(dict(id='river_boat', kind='boat', walk=False, route='b2 river from J2 to the boat landing', places=['b2_boat']))

# Horizontal portals (doorways between spaces on a level)
P = [
    dict(id='p_gate_hall', a='g_gate', b='g_arrival', at=[40, 55], width=6.0, height=4.5),
    dict(id='p_road_gate', a='g_road', b='g_gate', at=[13, 55], width=7.0),
    dict(id='p_hall_changing', a='g_arrival', b='g_changing', at=[100, 52], width=4.0, height=3.2),
    dict(id='p_hall_terrace', a='g_arrival', b='g_terrace', at=[60, 42], width=5.0, height=4.0),
    dict(id='p_gate_terrace', a='g_gate', b='g_terrace', at=[34, 41], width=5.0),
    dict(id='p_terrace_cascade', a='g_terrace', b='g_cascade', at=[46, 24], width=3.0),
    dict(id='p_changing_east', a='g_changing', b='g_east', at=[140, 70], width=3.0, height=2.6),
    dict(id='p_east_path', a='g_east', b='g_east_path', at=[161, 75], width=3.0),
    dict(id='p_path_ledge', a='g_east_path', b='g_north_ledge', at=[194, 109], width=3.0),
    dict(id='p_hall_spiral', a='g_arrival', b='spiral_stair', at=[90, 62], width=2.6, height=2.6),
    dict(id='p_b1_lobby_cor', a='b1_lobby', b='b1_cor_mirror', at=[78, 72], width=4.0, height=3.0),
    dict(id='p_b1_cor_mirror', a='b1_cor_mirror', b='b1_mirror', at=[93.5, 92], width=4.0, height=3.0),
    dict(id='p_b1_junction_west', a='b1_junction_w', b='b1_cor_west', at=[62, 76], width=4.0, height=3.0),
    dict(id='p_b1_junction_mirror', a='b1_junction_w', b='b1_cor_mirror', at=[70, 76], width=3.2, height=3.0, note='found by the sound research (overlap without a portal)'),
    dict(id='p_b2_core_mist_steps', a='b2_core', b='mist_steps', at=[49, 62], width=4.0, height=3.0, z0=-40.0, note='Mist Steps foot in the Kawagiri core'),
    dict(id='p_b1_cor_grotto', a='b1_cor_west', b='b1_grotto', at=[52, 82.75], width=3.0, height=2.6),
    dict(id='p_b1_cor_ms', a='b1_cor_west', b='mist_steps', at=[49, 79], width=4.0, height=3.0),
    dict(id='p_b1_grotto_north', a='b1_grotto', b='b1_cor_north', at=[78, 104], width=3.0, height=2.6),
    dict(id='p_b1_mirror_east', a='b1_mirror', b='b1_cor_east', at=[130.5, 90], width=4.0, height=3.0),
    dict(id='p_b1_east_glacier', a='b1_cor_east', b='b1_glacier', at=[165, 84], width=3.0, height=2.6),
    dict(id='p_b1_north_outfall', a='b1_cor_north', b='b1_outfall', at=[165.5, 100.2], width=3.0, height=2.6),
    dict(id='p_b1_east_treat', a='b1_cor_east', b='b1_treatment', at=[146, 81.83], width=2.6, height=2.4),
    dict(id='p_b1_lobby_south', a='b1_lobby', b='b1_cor_south', at=[101.5, 64], width=4.0, height=3.0),
    dict(id='p_b1_south_treat', a='b1_cor_south', b='b1_treatment', at=[124, 58.6], width=2.0, height=2.4),
    dict(id='p_b1_south_slide', a='b1_cor_south', b='b1_slide_top', at=[138, 54], width=4.0, height=3.0),
    dict(id='p_b1_glacier_outfall', a='b1_glacier', b='b1_outfall', at=[170, 97], width=3.0, height=2.6),
    dict(id='p_b2_core_kawagiri', a='b2_core', b='b2_kawagiri', at=[70, 74], width=6.0),
    dict(id='p_b2_core_kawagiri_e', a='b2_core', b='b2_kawagiri', at=[110, 74], width=4.0),
    dict(id='p_b2_core_boat', a='b2_core', b='b2_boat', at=[122, 68], width=4.0),
    dict(id='p_b2_boat_board', a='b2_boat', b='b2_boardwalk', at=[141, 76], width=3.5),
    dict(id='p_b2_boat_lava', a='b2_boat', b='b2_lava_link', at=[135, 65.5], width=3.5),
    dict(id='p_b2_core_falls', a='b2_core', b='b2_falls_head', at=[46.5, 64], width=4.0),
    dict(id='p_b2_falls_balcony', a='b2_falls_head', b='b3_falls_east', at=[40, 64], width=12.0, depth=3.0, z0=-40.0, height=8.0, note='railed balcony onto the falls shaft'),
    dict(id='p_b3_falls_rim', a='b3_falls', b='b3_rimstone', at=[48, 66], width=4.0),
    dict(id='p_b3_lobby_walk', a='b3_lobby', b='b3_walk_north', at=[78, 70], width=4.0),
    dict(id='p_b3_walk_rim', a='b3_walk_north', b='b3_rimstone', at=[66, 66], width=4.0, z0=-61.5),
    dict(id='p_b3_lazy_geyser_n', a='b3_lazy', b='b3_geyser', at=[114, 52], width=3.0, note='bridge over the river'),
    dict(id='p_b3_lazy_geyser_s', a='b3_lazy', b='b3_geyser', at=[114, 32], width=3.0, note='bridge over the river'),
    dict(id='p_b3_lobby_lazy', a='b3_lobby', b='b3_lazy', at=[98, 60], width=4.0),
    dict(id='p_b3_lazy_slide', a='b3_lazy', b='b3_slide_foot', at=[141, 42], width=4.0),
    dict(id='p_b3_slide_shore', a='b3_slide_foot', b='b3_shore', at=[151, 36.5], width=4.0),
    dict(id='p_b3_rim_lazy', a='b3_rimstone', b='b3_lazy', at=[88, 32], width=4.0),
    dict(id='p_b3_falls_arch', a='b3_falls', b='b3_cavern', at=[46, 61], width=24.0, depth=3.0, z0=-57.0, height=7.0, note='High view arch: the curtain glow reads across the vault.'),
    dict(id='p_b3_shore_wave', a='b3_shore', b='b3_wave', at=[162, 34], width=4.0),
    dict(id='p_b4_lobby_tunnel', a='b4_lobby', b='b4_tunnel', at=[77, 64], width=5.0, height=3.4),
    dict(id='p_b4_tunnel_chamber', a='b4_tunnel', b='b4_chamber', at=[56, 34], width=5.0, height=3.4),
    dict(id='p_s_rim_west', a='s_rim_west', b='s_rim', at=[75, 65], width=3.5),
    dict(id='p_s_rim_pool_sw', a='s_rim', b='s_pool', at=[89, 63.6], width=4.0),
    dict(id='p_s_rim_pool_n', a='s_rim', b='s_pool', at=[103, 105.6], width=4.0),
    dict(id='p_s_rim_spring', a='s_rim', b='s_spring', at=[77, 101.7], width=3.0),
    dict(id='p_s_rim_moon', a='s_rim', b='s_moon', at=[147.6, 102], width=3.0),
]
for t in range(4):
    P.append(dict(id=f'p_suite_{t + 1}ab', a=f'suite_{t + 1}a', b=f'suite_{t + 1}b', at=[156, 109.15], width=1.6, note='balcony walk'))
    P.append(dict(id=f'p_suite_{t + 1}bc', a=f'suite_{t + 1}b', b=f'suite_{t + 1}c', at=[174, 109.15], width=1.6, note='balcony walk'))
def helix_doors(c, places, shaft_r, zs):
    out = []
    cx, cy = c['center']
    for z, sp in zip(zs, places):
        pts = [p for p in c['path'] if abs(p[2] - z) < 0.09]
        if not pts:
            continue
        a = math.atan2(sum(p[1] - cy for p in pts), sum(p[0] - cx for p in pts))
        out.append(dict(id=f"p_{sp}_{c['id']}", a=sp, b=c['id'], at=[round(cx + shaft_r * math.cos(a), 2), round(cy + shaft_r * math.sin(a), 2)],
                        width=2.6, height=2.6, z0=z, bearing=round((90 - math.degrees(a)) % 360, 1), note='stair landing door (from the helix)'))
        if c['id'] == 'spiral_stair':
            b = a + math.pi
            out.append(dict(id=f"p_{sp}_lift", a=sp, b='main_lift', at=[round(cx + shaft_r * math.cos(b), 2), round(cy + shaft_r * math.sin(b), 2)],
                            width=1.8, height=2.4, z0=z, bearing=round((90 - math.degrees(b)) % 360, 1),
                            bridge=[[round(cx + 2.2 * math.cos(b), 2), round(cy + 2.2 * math.sin(b), 2)], [round(cx + shaft_r * math.cos(b), 2), round(cy + shaft_r * math.sin(b), 2)]],
                            note='lift door + bridge over the well, opposite the stair landing'))
    return out


P = [p for p in P if p['id'] != 'p_hall_spiral']
P += helix_doors(spiral, ['g_arrival', 'b1_lobby', 'b2_core', 'b3_lobby', 'b4_lobby'], SHAFT_R, [0.0, -20.0, -40.0, -67.0, -100.0])
P += helix_doors(lava, ['b1_slide_top', 'b2_lava_link', 'b3_slide_foot'], SLIDE_SHAFT_R, [-20.0, -40.0, -67.0])
P.append(dict(id='p_b1_slide_launch', a='b1_slide_top', b='glass_slide', at=[146.4, 50], width=1.6, height=2.4, z0=-19.0, note='slide start, tube at bearing 270'))
# portal from every connection end to its place is implied by connection.places

# ---------------------------------------------------------------- water
def river_poly():
    polys = []
    for (x0, y0, w0), (x1, y1, w1) in zip(RIVER, RIVER[1:]):
        polys.append(LineString([(x0, y0), (x1, y1)]).buffer((w0 + w1) / 4, cap_style=1))
    g = unary_union(polys).difference(Point(*LIFT).buffer(SHAFT_R + 0.8, 32))   # the river flows round the lift tower
    if g.geom_type != 'Polygon':
        g = max(g.geoms, key=lambda q: q.area)
    return [[round(x, 3), round(y, 3)] for x, y in list(g.exterior.coords)[:-1]]


W = [
    dict(id='w_spring', kind='still', level='summit', z=121.45, rim_z=121.5, temp=44, footprint=circle(66, 96, 6)),
    dict(id='w_caldera', kind='still', level='summit', z=119.95, rim_z=120.0, temp=42, infinity_edge='south rim x 96-136',
         footprint=[[86, 68], [136, 68], [138, 94], [120, 100], [90, 96], [84, 84]]),
    dict(id='w_cascade', kind='cascade', level='south face', z_top=119.0, z_bottom=-4.0, temp=[41, 36],
         note='Terraced pools beside the Terrace Path, each 3-8 cm below its lip; lowest pools in g_cascade.'),
    dict(id='w_culvert', kind='fall', z_top=-4.2, z_bottom=-20.05, at=[46, 40], note='Sink cave at C4 into the B1 corridors.'),
    dict(id='w_b1_corridors', kind='still', level='b1', z=-20.05, rim_z=-20.0, temp=34,
         note='All mist corridors, koi junctions and the lobby rill share one level; drains east to w_outfall and down the Mist Steps.'),
    dict(id='w_mirror', kind='still', level='b1', z=-20.05, rim_z=-20.0, temp=35, footprint=circle(112, 92, 12), salt=True),
    dict(id='w_grotto_pools', kind='still', level='b1', z=-20.06, rim_z=-20.0, temp=[45, 55, 65]),
    dict(id='w_glacier', kind='still', level='b1', z=-20.06, rim_z=-20.0, temp=6, footprint=circle(182, 84, 8)),
    dict(id='w_outfall', kind='fall', z_top=-20.05, z_bottom=-42.0, at=[192, 100], note='Shaft at J2 to the river head.'),
    dict(id='w_mist_steps', kind='cascade', z_top=-20.05, z_bottom=-42.83, note='Thin sheet down each flight of the Mist Steps into the river.'),
    dict(id='w_north_trickle', kind='cascade', z_top=119.9, z_bottom=-42.0, note='North branch: suite tubs at 60/43/26/10, then inside to the river head.'),
    dict(id='w_river', kind='flow', level='b2', z_start=-42.0, z_end=-43.0, bed_z=-44.6, temp=36,
         centerline=[[x, y] for x, y, _ in RIVER], widths=[w for _, _, w in RIVER], footprint=river_poly()),
    dict(id='w_thunder', kind='fall', z_top=-43.0, z_bottom=-60.0, lip=[[23, 76], [35, 76]], temp=39),
    dict(id='w_falls_pool', kind='still', level='b3', z=-60.05, rim_z=-60.0, footprint=[[14, 46], [39.5, 46], [39.5, 75.8], [14, 75.8]]),
    dict(id='w_rimstone', kind='cascade', level='b3', z_top=-60.5, z_bottom=-66.5, tiers=13, temp=[40, 33]),
    dict(id='w_lazy', kind='flow', level='b3', z_start=-67.45, z_end=-67.5, bed_z=-68.4, temp=38, width=6.0,
         centerline=ellipse(114, 42, 23.5, 13.5)),
    dict(id='w_geyser', kind='still', level='b3', z=-67.55, rim_z=-67.5, temp=37, footprint=ellipse(114, 42, 8, 4)),
    dict(id='w_splash', kind='still', level='b3', z=-67.6, rim_z=-67.55, temp=36, footprint=circle(154, 45, 4.5)),
    dict(id='w_sea', kind='sea', level='b3', z=SEA, temp=30, footprint=[[172, 20], [200, 16], [200, 60], [176, 58], [170, 40]],
         note='One level surface, continuous with the open sea beyond the mouth.'),
]

DECKS = [dict(id='falls_head_deck', footprint=rect(40, 63, 47, 70), z=-40.0, note='balcony deck over the falls shaft')]

layout = dict(
    title='Kazan-yu metric layout', units='m',
    axes=dict(x='east from the west edge of column A', y='north from the south edge of row 6', z='elevation'),
    grid=dict(cols=COLS, rows=[1, 2, 3, 4, 5, 6], cell=CELL, size=[200, 120]),
    sea_level=SEA, step=dict(riser=RISER, tread=TREAD, landing_every=LANDING_EVERY, landing_len=LANDING_LEN),
    levels=LEVELS, lift=dict(at=list(LIFT), shaft_r=SHAFT_R), slide_shaft=dict(at=list(SLIDE), r=SLIDE_SHAFT_R),
    spaces=S, connections=C, portals=P, water=W, decks=DECKS)

next(s for s in S if s['id'] == 'b2_river')['footprint'] = river_poly()
# rimstone keeps only the terrace slope: clip out the north walk, lobby and lazy-river loop it overlapped
_rim = next(s for s in S if s['id'] == 'b3_rimstone')
_g = Polygon(_rim['footprint'])
for _o in ('b3_walk_north', 'b3_lobby', 'b3_lazy'):
    _g = _g.difference(Polygon(next(s for s in S if s['id'] == _o)['footprint']).buffer(0.3))
if _g.geom_type != 'Polygon':
    _g = max(_g.geoms, key=lambda q: q.area)
_rim['footprint'] = [[round(x, 3), round(y, 3)] for x, y in list(_g.exterior.coords)[:-1]]
for s in S:
    s['cells'] = sorted({cell_of(x, y) for x, y in s['footprint']} | {cell_of(*Polygon(s['footprint']).centroid.coords[0])})
    s['area_m2'] = round(Polygon(s['footprint']).area, 1)

if __name__ == '__main__':
    out = os.path.join(ROOT, '3d', 'layout.json')
    tmp = os.path.join(ROOT, '.scratch', 'layout.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(layout, f, indent=1)
    os.replace(tmp, out)
    for c in C:
        if c['kind'] in ('helix', 'path_stair', 'switchback'):
            extra = f"turns {c.get('turns')}" if c['kind'] == 'helix' else (f"len {c.get('length')} level-walk {c.get('level_walk')}" if c['kind'] == 'path_stair' else '')
            print(f"{c['id']:16s} {c['kind']:10s} {c['z_top']:7.1f} -> {c['z_bottom']:7.1f}  steps {c['steps']:4d} riser {c['riser']:.3f} {extra}")
    print('spaces', len(S), 'connections', len(C), 'portals', len(P), 'water', len(W))
