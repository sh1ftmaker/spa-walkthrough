"""Build the g_arrival place model (Arrival hall, lava window) -> 3d/places/g_arrival.blend.

    blender -b -P tools/place/build_g_arrival.py                 # build + checks + save
    blender -b -P tools/place/build_g_arrival.py -- --render     # ... + canonical / views renders (Cycles)

Deterministic: every generator call has a fixed seed and parameters; the shell noise is position-seeded.
Realised rules from 3d/spaces/g_arrival.json are listed inline (positions are the space file's unless a
comment says why they moved).
"""
import json
import math
import os
import random
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kzplace_common as P  # noqa: E402
import kzplace_g_arrival as G  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
T0 = time.time()
ROOT = P.ROOT
SID = 'g_arrival'


def log(*a):
    print(f'[{time.time() - T0:6.1f}s]', *a, flush=True)


P.reset()
S = P.space(SID)
lights_src = []           # (object, scale, runtime, skip) for kz_lights conversion

# ------------------------------------------------------------------ stream (built first: the floor cut follows it)
SPATH = [tuple(p) + (-0.15,) for p in S['water'][0]['path']]
stream = G.dress('stream_channel', 1, (0, 0, 0), 0, name='stream_w_hall_stream', role='basin',
                 path=SPATH, width=2.5, style='natural', weir_every=3.2, drop=0.035, bank_density=0.55)
wp0 = json.loads(stream['kz_water_path'])[0]
OFF = Vector((SPATH[0][0] - wp0[0], SPATH[0][1] - wp0[1], -0.15 - wp0[2]))
stream.location = OFF
STREAM_CL = [(c[0] + OFF.x, c[1] + OFF.y, c[2]) for c in json.loads(stream['kz_centerline'])]
log('stream', OFF, 'water end z', json.loads(stream['kz_water_path'])[-1][2] + OFF.z)

# drain slot at the stream foot (sinks toward B1): culvert grate over a rock-lined pit
SLOT = (70.75, 45.0, 73.35, 45.8)


def stream_dist(x, y):
    best = 1e9
    for a, b in zip(STREAM_CL[:-1], STREAM_CL[1:]):
        A, B = Vector(a[:2]), Vector(b[:2]); p = Vector((x, y)); ab = B - A
        t = max(0, min(1, (p - A).dot(ab) / max(ab.length_squared, 1e-9)))
        best = min(best, (A + ab * t - p).length)
    return best


# ------------------------------------------------------------------ shell
wall, vault = G.rock_shell()
log('rock shell', len(wall.data.polygons), len(vault.data.polygons))
floor = G.floor(STREAM_CL, SLOT)
pit = G.drain_pit(SLOT)
fac = G.facade_south()
doors = G.door_frames()
log('floor / facade / doors')

# ------------------------------------------------------------------ hero: lava window + lava field behind the glass
H = S['hero']
win = G.dress('lava_window', 1, tuple(H['at']), H['facing_deg'], name='hero_lava_window', role='glass',
              w=H['dims']['w'], h=H['dims']['h'])
lights_src.append((win, 1.0, True, ()))

# lava world behind the glass: one heated, scaled lava_backdrop (falls + arch) under a high lava-lit cave
back, cav = G.lava_view(win, G.dress)
lights_src.append((back, 1.0, False, (0,)))         # skip its glass-plane area light: the window's light covers it
# molten-field glow on the cave roof and cliff (stand-in for the field's emission in the bake; not runtime)
for k, x in enumerate((50.0, 61.0, 72.0)):
    l = P.light(f'L_lava_field.{k}', 'AREA', (x, 88.0, 0.8), 22000, kelvin=1500, size=10.0)
    l.data.size_y = 8.0; l.data.color = (1.0, 0.32, 0.04); l.visible_camera = False; l.visible_transmission = False
    l.visible_glossy = False
for k, (x, y) in enumerate(((48.0, 95.0), (61.0, 100.0), (74.0, 95.0))):
    l = P.light(f'L_lava_deep.{k}', 'POINT', (x, y, 4.0), 25000, kelvin=1500, size=3.0)
    l.data.color = (1.0, 0.3, 0.04); l.visible_camera = False; l.visible_transmission = False

# ------------------------------------------------------------------ anchored
AN = {a['id']: a for a in S['anchored']}
a = AN['hall_bridge']
bridge = G.dress('bridge_arched', 1, tuple(a['at']), a['facing_deg'], name='hall_bridge', role='stair', **a['dims'])
lights_src.append((bridge, 1.0, False, ()))
a = AN['slippers']
cub = G.dress('slipper_cubbies', 1, tuple(a['at']), a['facing_deg'], name='slipper_cubbies', **a['dims'])
lights_src.append((cub, 1.0, False, ()))
a = AN['reception']
rec = G.dress('reception_counter', 1, (a['at'][0], a['at'][1], G.TERRACE_Z), a['facing_deg'], name='reception', **a['dims'])
lights_src.append((rec, 1.0, False, ()))
a = AN['basin']
G.dress('chozubachi', 1, tuple(a['at']), a['facing_deg'], name='chozubachi', role='basin', r=a['dims']['r'])
a = AN['basin_tree']
G.dress('sakura_small', 3, (a['at'][0], a['at'][1], 0.3), a['facing_deg'], name='sakura', h=a['dims']['h'], tint='white', density=0.75)
a = AN['spiral_door']
drum = G.dress('lift_core', 1, tuple(a['at']), 0.0, name='lift_core', role='wall', r=a['dims']['r'], h=5.5,
               label='G', doors=[0.0], lattice=3.5)   # door bearing 0 (lift portal north), stair landing 180 (south)
lights_src.append((drum, 1.0, False, ()))
terr = G.reception_terrace()
basin = G.blossom_basin()
log('hero + anchored')

# ------------------------------------------------------------------ lights (lantern rules)
lan = []


def lantern(asset, seed, at, heading, **kw):
    o = G.dress(asset, seed, at, heading, role='lantern', **kw)
    lights_src.append((o, 1.0, False, ()))
    lan.append(o)
    return o


def along(pts, side, offset, spacing, start):
    """points along a polyline at `spacing`, `offset` to the left (+) / right (-) of travel"""
    segs = list(zip(pts[:-1], pts[1:]))
    total = sum((Vector(b) - Vector(a)).length for a, b in segs)
    out, s = [], start
    while s < total - 0.5:
        acc = 0.0
        for a, b in segs:
            A, B = Vector(a), Vector(b); L = (B - A).length
            if acc + L >= s:
                t = (B - A).normalized(); p = A + t * (s - acc)
                n = Vector((-t.y, t.x)) * (1 if side == 'left' else -1)
                q = p + n * offset
                out.append((q.x, q.y, math.degrees(math.atan2(-n.x, -n.y)) % 360))   # face back to the path
                break
            acc += L
        s += spacing
    return out


# 1) chochin cluster over the slipper wall, hung from the gallery deck (z 6.0); rule height 3.5-6.5 -> 3.4-5.2
rr = random.Random('chochin_cluster')
for k, x in enumerate([42.4, 44.2, 46.0, 47.8, 49.6, 51.4, 53.2, 55.0]):
    y = 43.55 if k % 2 == 0 else 44.0
    zb = rr.uniform(3.4, 5.1)
    variant = 'round_logo' if k % 3 else 'tall_cylinder'
    hd = rr.uniform(0, 360)
    o = G.dress('lantern_hanging', 1 + k, (x, y, zb), hd, variant=variant, cord=0.3)
    body = max(v.co.z for v in o.data.vertices) - 0.3              # lantern height without the cord
    bpy.data.objects.remove(o, do_unlink=True)
    hi = zb > 3.8                      # high ones (>= 2.2 m over a guest's head): LOD1, budget
    o = lantern('lantern_hanging', 1 + k, (x, y, zb), hd, variant=variant, cord=round(G.GALLERY_Z - 0.18 - zb - body, 3),
                **({'lod': 1} if hi else {}))
    o['kz_lod_render'] = 1 if hi else 0
    o['kz_hang_z'] = G.GALLERY_Z - 0.18
# 2) pair flanking the spiral-stair door; 3) pair at the lift door
for x in (88.0, 92.0):
    lantern('lantern_floor', 1, (x, 61.4, 0), 180)
for x in (88.4, 91.6):
    lantern('lantern_floor', 1, (x, 79.3, 0), 0)
# 4) low cluster at the changing-hall door, hung from the vault
# (hung from the porch lantern bar at x 96.6 instead of long cords from the 10 m vault)
for k, y in enumerate((50.0, 52.0, 54.0)):
    zb = (2.45, 2.75, 2.5)[k]
    o = G.dress('lantern_hanging', 11 + k, (G.PORCH_X, y, zb), 0, variant='round_logo', cord=0.3)
    body = max(v.co.z for v in o.data.vertices) - 0.3
    bpy.data.objects.remove(o, do_unlink=True)
    lantern('lantern_hanging', 11 + k, (G.PORCH_X, y, zb), 0, variant='round_logo', cord=round(G.PORCH_BAR_Z - zb - body, 3))
# 5) south-east bay
lantern('lantern_floor', 2, (81.0, 46.5, 0), 0)
lantern('lantern_floor', 2, (86.5, 49.5, 0), 0)
# 6) west half of the spine, right side; 7) east half, left side (offset 1.9, spacing 7)
for x, y, hd in along([(45.0, 56.0), (50.0, 57.0), (60.0, 60.0), (62.5, 60.8)], 'right', 1.9, 7.0, 2.5):
    lantern('lantern_floor', 4, (x, y, 0), hd)
for x, y, hd in along([(70.0, 62.0), (72.0, 62.0), (82.0, 58.0), (88.0, 58.0)], 'left', 1.9, 7.0, 2.5):
    lantern('lantern_floor', 4, (x, y, 0), hd)
# 8) toro at the bridge ends; moved out of the stream corridor where the rule point lies in the water/banks
TORO = [tuple(p[:2]) for p in next(l for l in S['lights'] if l['asset'] == 'lantern_stone')['at']]
for (x, y) in TORO:
    lantern('lantern_stone', 1, (x, y, 0), math.degrees(math.atan2(61.0 - x, 79.6 - y)) % 360)
# 9) reception ends; 10) window-bay toro
lantern('lantern_floor', 1, (54.0, 48.6, G.TERRACE_Z), 0)
lantern('lantern_floor', 1, (62.0, 48.6, G.TERRACE_Z), 0)
lantern('lantern_stone', 2, (73.0, 75.6, 0), 0)
# 11) fix round: lantern rows lining the whole walk (dollhouse), the other side of rules 6 and 7
for x, y, hd in along([(45.0, 56.0), (50.0, 57.0), (60.0, 60.0), (62.5, 60.8)], 'left', 1.9, 6.0, 5.5):
    lantern('lantern_floor', 4, (x, y, 0), hd)
for x, y, hd in along([(70.0, 62.0), (72.0, 62.0), (82.0, 58.0), (88.0, 58.0)], 'right', 1.9, 6.0, 4.5):
    if stream_dist(x, y) > 2.8:
        lantern('lantern_floor', 4, (x, y, 0), hd)
# 12) fix round: chochin strings high in the vault (dollhouse), LOD1 (>= 6 m over any eye; budget)
for k, (x, y) in enumerate([(47.5, 64.0), (53.0, 70.5), (58.5, 52.5), (64.5, 69.0), (71.5, 57.0), (77.0, 66.0),
                            (52.0, 48.5), (84.0, 53.0), (44.5, 52.0)]):
    zc = G.ceiling_z_at([vault, wall], x, y)
    o = G.dress('lantern_hanging', 21 + k, (x, y, 0), 25 * k, variant='chain', chain_n=5, cord=0.3, lod=1)
    hgt = max(v.co.z for v in o.data.vertices)
    zb = (6.2, 7.0, 6.6)[k % 3]
    bpy.data.objects.remove(o, do_unlink=True)
    o = lantern('lantern_hanging', 21 + k, (x, y, zb), 25 * k, variant='chain', chain_n=5, cord=round(zc + 0.2 - zb - hgt + 0.3, 2), lod=1)
    o['kz_lod_render'] = 1
log('lanterns', len(lan), 'toro moved to', TORO)

# ------------------------------------------------------------------ dressing
# boulder_rim along the stream (rule: both sides, spacing 0.8-4.5, offset 1.4, embed 0.2): placed at 2.3 m
# from the centre line on the floor edge, because the stream generator's own bank rocks fill 1.3-2.2 m.
AVOID = [(70.6, 47.2, 1.6), (70.0, 50.0, 0.8), (66.0, 62.0, 4.6)] + [(x, y, 1.4) for x, y in TORO] + [(74.0, 52.0, 1.3)]
rb = random.Random('boulders')
cl = [Vector(c[:2]) for c in STREAM_CL]
acc, nxt, side, nb = 0.0, 1.5, 1, 0
for i in range(1, len(cl)):
    acc += (cl[i] - cl[i - 1]).length
    if acc < nxt:
        continue
    t = (cl[min(i + 1, len(cl) - 1)] - cl[i - 1]).normalized(); n = Vector((-t.y, t.x))
    q = cl[i] + n * side * (STREAM_CL[i][2] + 1.05 + rb.uniform(0.0, 0.35))
    side = -side
    nxt = acc + rb.uniform(1.8, 3.6)
    if any((q - Vector((ax, ay))).length < ar for ax, ay, ar in AVOID):
        continue
    if not (41.5 < q.x < 98.5 and 43.0 < q.y < 78.8) or nb >= 7:
        continue
    nb += 1
    o = G.dress('boulder_rim', nb, (q.x, q.y, 0.0), rb.uniform(0, 360), name=f'boulder_rim.{nb}', role='rock',
                size=round(rb.uniform(0.7, 1.5), 2))
    o.location.z = -float(o['kz_embed'])
log('boulders', nb)
# pines at each end of the window (dark silhouettes against the lava)
G.dress('pine_bonsai', 1, (42.6, 74.0, 0), 20, name='pine_w', role='prop', pads=5)
G.dress('pine_bonsai', 2, (80.5, 76.0, 0), 200, name='pine_e', role='prop', pads=5)
# banners: either side of the west door (on the rock) and hung from the gallery fascia on the south bays
for k, (x, y, z, hd) in enumerate([(41.0, 49.4, 1.4, 90), (41.0, 60.6, 1.4, 90),
                                    (70.0, 44.3, 1.75, 0), (82.0, 44.3, 1.75, 0), (94.0, 44.3, 1.75, 0)]):
    G.dress('banner', 1 if k < 2 else 2, (x, y, z), hd, name=f'banner.{k}', role='prop', bake=False, h=4.0, w=1.0,
            colour='cream' if k < 2 else 'indigo')
# rock clusters: edge band (hand-picked, clear of nav / portals / hero / anchored) + the window-bay group
for k, (x, y, w_, hd) in enumerate([(41.6, 67.5, 2.6, 80), (98.6, 45.0, 2.4, 270), (83.5, 66.5, 2.4, 30)]):   # rule point (78, 69) sits 4.5 m in front of the moved concept camera
    G.dress('rock_cluster', k + 1, (x, y, -0.06), hd, name=f'rock_cluster.{k}', role='rock', w=w_)
# the stream's source: a rock spill under the west end of the lava window with a trickle face
G.dress('rock_cluster', 7, (44.6, 78.6, -0.1), 160, name='spill_rocks', role='rock', w=4.2, height=1.5)
G.dress('wall_trickle', 2, (46.2, 78.75, -0.05), 180, name='spill_trickle', role='rock', h=2.4)
# low rocks along the window foot (04: dark rock silhouettes and mist against the glass)
for k, (x, y, w_) in enumerate([(55.5, 78.75, 2.2), (68.5, 78.8, 2.6), (76.4, 78.6, 1.8)]):
    G.dress('rock_cluster', 10 + k, (x, y, -0.06), 180 + 20 * k, name=f'window_rocks.{k}', role='rock', w=w_, height=0.8)
# level board by the stair / lift landing, stone bench in the south-east bay, gilt hall sign on the facade
G.dress('sign_kanji', 3, (93.0, 61.6, 0), 180, name='level_board', role='prop', variant='level', level='GF')
G.dress('bench_stone', 1, (84.5, 44.2, 0), 0, name='bench_se', role='prop', style='slab', l=2.4)
G.dress('sign_kanji', 1, (56.15, 42.42, 3.45), 0, name='hall_sign', role='prop', variant='wall', h=2.4)
# drain grate over the slot at the stream foot
o = G.dress('culvert_grate', 2, ((SLOT[0] + SLOT[2]) / 2, (SLOT[1] + SLOT[3]) / 2, 0), 0, name='drain_grate', role='prop',
            w=3.0, d=1.0)
o.location.z = 0.01 - max(v.co.z for v in o.data.vertices)        # paving surround 1 cm proud of the floor
# noren at the changing-hall door (half noren, bottom 2.37 m)
for k, y in enumerate((50.78, 52.0, 53.22)):
    G.dress('noren', 1, (99.77, y, 2.37), 270, name=f'noren.{k}', role='prop', bake=False, w=1.2, h=1.0, colour='indigo')
# stalactite clusters from the vault (kept off the window view line)
for k, (x, y) in enumerate([(50.0, 66.0), (75.0, 63.0), (84.0, 49.0), (58.0, 53.0)]):
    zc = G.ceiling_z_at([vault, wall], x, y)
    o = G.dress('stalactite_cluster', k + 1, (x, y, 0), 37 * k, name=f'stalactites.{k}', role='rock', bake=True)
    o.location.z = zc - o['kz_attach_z'] + 0.35
# fix round: planted beds / rock gardens along the stream banks (shrubs + moss and fern), clear of the walk
BEDS = []
rg = random.Random('beds')
acc, nxt, side = 0.0, 3.0, -1
for i in range(1, len(cl)):
    acc += (cl[i] - cl[i - 1]).length
    if acc < nxt:
        continue
    t = (cl[min(i + 1, len(cl) - 1)] - cl[i - 1]).normalized(); n = Vector((-t.y, t.x))
    q = cl[i] + n * side * (STREAM_CL[i][2] + 1.9 + rg.uniform(0.0, 0.4))
    side = -side; nxt = acc + rg.uniform(2.6, 3.6)
    if any((q - Vector((ax, ay))).length < ar + 0.6 for ax, ay, ar in AVOID) or not (42.5 < q.x < 97.5 and 43.5 < q.y < 78.0):
        continue
    if any((q - Vector(sp[:2])).length < 2.4 for sp in S['spine']) or (q - Vector((76.3, 45.3))).length < 3.2:
        continue
    k = len(BEDS)
    if k % 2 == 0:
        G.dress('shrub_clump', k + 1, (q.x, q.y, 0.0), rg.uniform(0, 360), name=f'bed_shrub.{k}', role='prop', spread=1.1)
    else:
        G.dress('groundcover', 2 if k % 4 == 1 else 1, (q.x, q.y, 0.0), rg.uniform(0, 360), name=f'bed_cover.{k}', role='prop',
                species='moss' if k % 4 == 1 else 'fern', setting='ground')
    BEDS.append((q.x, q.y))
# moss and fern round the window-foot rocks and the spill
for k, (x, y, sp) in enumerate([(54.2, 77.9, 'moss'), (57.2, 78.0, 'fern'), (67.0, 78.1, 'moss'), (70.3, 78.0, 'fern'),
                                (47.9, 78.2, 'fern'), (43.6, 76.4, 'moss')]):
    G.dress('groundcover', 7 + k, (x, y, 0.0), 40 * k, name=f'window_bed.{k}', role='prop', species=sp, setting='ground')
# benches facing the stream and the lava (dollhouse)
for k, (x, y, hd) in enumerate([(56.0, 64.5, 30), (79.5, 63.5, 330), (60.5, 71.5, 0)]):
    G.dress('bench_stone', 2 + k, (x, y, 0), hd, name=f'bench.{k}', role='prop', style='slatted' if k % 2 else 'slab', l=2.2)
# the basalt gate at the hall's west entrance (dollhouse); g_gate keeps its own big torii
G.dress('torii_small', 3, (43.0, 55.0, 0), 90, name='gate_torii', role='prop', colour='black', base='daiishi', plaque=True,
        h=3.6, w=3.4)
log('dressing done', 'beds', len(BEDS))

# ------------------------------------------------------------------ people (kz_anim)
FIG = [('staff_figure', 5, (57.4, 46.15, G.TERRACE_Z), 0, 'idle_talk', dict(role='attendant', body='woman', prop='towel_stack', anim='idle')),
       ('guest_figure', 1, (51.0, 57.3, 0), 287, 'walk_slow', dict(pose='walking')),
       ('guest_figure', 2, (46.8, 55.9, 0), 280, 'walk', dict(pose='walking')),
       ('guest_figure', 8, (66.0, 62.2, 0.6), 352, 'idle_lookup', dict(pose='standing')),
       ('guest_figure', 3, (65.0, 75.2, 0), 8, 'idle_lookup', dict(pose='standing')),
       ('guest_figure', 1, (49.5, 43.5, 0), 180, 'idle_shift', dict(pose='standing', clothing='yukata_linen')),
       ('guest_figure', 8, (53.6, 58.1, 0), 73, 'walk_slow', dict(pose='walking', clothing='yukata_indigo')),
       ('guest_figure', 2, (57.8, 59.0, 0), 74, 'walk_slow', dict(pose='walking', clothing='yukata_black')),
       ('guest_figure', 1, (48.6, 56.4, 0), 78, 'walk_slow', dict(pose='walking', clothing='yukata_indigo'))]
for k, (asset, seed, at, hd, clip, kw) in enumerate(FIG):
    o = G.dress(asset, seed, at, hd, name=f'fig.{k}', collection='kz_anim', role='figure', bake=False, gen_kw=kw)
    o['kz_clip'] = clip
log('figures', len(FIG))

# ------------------------------------------------------------------ lights
# Practical lantern sources are scaled x8 over the generators' proxy watts: at 25-30 W the lanterns light only
# their own paper in a 16 m vault; x8 gives the pools of light on the wet floor that 04 shows (same AgX, exposure 0).
PRACTICAL = 8.0
for o, sc, rt, skip in lights_src:
    G.lights_from_props(o, scale=sc * (PRACTICAL if o.get('kz_role') == 'lantern' else 1.0), runtime=rt, skip=skip,
                        push=1.2 if o is win else 0.0)          # window light sits in front of the glass
# hidden coves: uplights on the head-beam top wash the vault (04: warm rock overhead); gate-side rock uplights
for k, x in enumerate([46.0, 56.0, 66.0, 76.0, 86.0, 95.0]):
    l = P.light(f'L_cove.{k}', 'SPOT', (x, 43.0, 9.7), 10000, kelvin=2700, size=0.6)
    l.visible_camera = False
    l.data.spot_size = math.radians(120); l.data.spot_blend = 0.8
    G._aim(l, Vector((0, 0.55, 1)).normalized(), None)
# rock washers: hidden at the wall foot behind rock clusters / lanterns, grazing the basalt up to the vault
WASH = [((41.0, 49.6, 0.3), (-0.3, 0.0, 1.0), 500), ((41.0, 60.4, 0.3), (-0.3, 0.0, 1.0), 500),
        ((41.2, 66.5, 0.3), (-0.35, 0.1, 1.0), 900), ((41.2, 73.0, 0.3), (-0.35, 0.2, 1.0), 900),
        ((43.0, 78.9, 0.3), (-0.1, 0.35, 1.0), 900), ((79.2, 78.9, 0.3), (0.1, 0.35, 1.0), 900),
        ((83.0, 79.0, 0.3), (0.0, 0.35, 1.0), 700), ((97.0, 79.0, 0.3), (0.0, 0.35, 1.0), 700),
        ((98.9, 44.5, 0.3), (0.35, -0.1, 1.0), 900), ((98.9, 58.0, 0.3), (0.35, 0.0, 1.0), 900),
        ((98.9, 66.0, 0.3), (0.35, 0.0, 1.0), 700), ((98.9, 74.0, 0.3), (0.35, 0.1, 1.0), 700)]
for k, (pos, aim, w) in enumerate(WASH):
    l = P.light(f'L_wash.{k}', 'SPOT', pos, w * 2.5, kelvin=2500, size=0.3)
    l.data.spot_size = math.radians(75); l.data.spot_blend = 0.7; l.visible_camera = False
    G._aim(l, Vector(aim).normalized(), None)
# teal underwater glow in the stream pools (04: turquoise water)
for k, c in enumerate(STREAM_CL[6::12]):
    l = P.light(f'L_pool.{k}', 'POINT', (c[0], c[1], -0.5), 450, kelvin=6500, size=0.4)
    l.data.color = (0.25, 0.85, 0.8); l.visible_camera = False
for k, a_ in enumerate((0.0, 2.1, 4.2)):
    l = P.light(f'L_basin.{k}', 'POINT', (76.3 + 1.4 * math.cos(a_), 45.3 + 1.4 * math.sin(a_), 0.05), 250, kelvin=6500, size=0.3)
    l.data.color = (0.25, 0.85, 0.8); l.visible_camera = False
# warm washes up the facade posts and the rock columns either side of the window
for k, x in enumerate(G.POSTS[1:-1:2]):
    l = P.light(f'L_post.{k}', 'SPOT', (x, 43.0, 0.15), 1500, kelvin=2600, size=0.2)
    l.data.spot_size = math.radians(35); l.data.spot_blend = 0.6; l.visible_camera = False
    G._aim(l, Vector((0, -0.12, 1)).normalized(), None)
haze = G.haze_volume()
log('lights', len(P.coll('kz_lights').objects))

# ------------------------------------------------------------------ water, fx, probes, cameras
water = G.water_ribbon(stream, OFF)
for k, c in enumerate(STREAM_CL[::16]):
    P.fx(f'fx_steam.{k}', 'steam', (c[0], c[1], 0.0), kz_rate=0.6, kz_height=1.2, kz_note='low steam over the stream only')
P.fx('fx_spill', 'spray', (46.2, 78.4, 0.6), kz_rate=1.0)
P.fx('fx_window_mist', 'mist', (61.0, 78.5, 0.4), kz_extent=[34.0, 1.6, 1.2], kz_rate=0.4)
P.fx('fx_chozubachi', 'drips', (74.0, 52.0, 0.75))
P.fx('fx_drain', 'steam', ((SLOT[0] + SLOT[2]) / 2, (SLOT[1] + SLOT[3]) / 2, -0.2), kz_rate=0.8)
P.probe(SID, 0, (49.0, 58.0, 2.5), (40, 42, 0), (58, 80, 16))
P.probe(SID, 1, (66.0, 64.0, 2.5), (58, 42, 0), (80, 80, 16))
P.probe(SID, 2, (88.0, 52.0, 2.5), (80, 42, 0), (100, 80, 16))
P.cameras(S)

# ------------------------------------------------------------------ walk mesh
# bridge deck centre line sampled on the bridge mesh
bv = G._bvh(bridge)
deck = []
for k in range(29):
    x = 62.5 + 7.0 * k / 28
    h = bv.ray_cast(Vector((x, 62.0, 3.0)), Vector((0, 0, -1)), 6.0)
    deck.append((x, 62.0, round(h[0].z, 3) if h[0] else 0.0))
DECKS = [('hall_bridge', deck, 1.0), ('lift_bridge', [(90.0, 78.2, 0.0), (90.0, 72.4, 0.0)], 0.85)]
BLOCK = [(41.0, 42.0, 55.0, 42.9), (54.4, 46.4, 61.6, 47.6), (42.5, 76.5, 47.6, 80.0),    # cubbies, counter, spill
         (73.6, 42.6, 79.0, 48.0)]                                                          # blossom basin
BLOCK += [(x - 0.5, y - 0.5, x + 0.5, y + 0.5) for x, y in BEDS]
walk_r, WI = G.walk_mesh(STREAM_CL, 0.35, SLOT, DECKS, BLOCK, S['portals'])      # raster graph for the flood fill
bpy.data.objects.remove(walk_r, do_unlink=True)
walk, WI['walls'] = G.walk_from_floor(floor, BLOCK, S['portals'], DECKS, raise_box=G.TERRACE_BOX, raise_z=G.TERRACE_Z)
log('walk cells', len(WI['cells']), 'walls', WI['walls'])

# ------------------------------------------------------------------ checks
checks = G.run_checks(S, WI, DECKS, floor=floor, stream=stream, bridge=bridge, drum=drum, extra_ground=[terr[0], basin[1]])
os.makedirs(os.path.join(ROOT, '3d', 'checks', 'places'), exist_ok=True)
with open(os.path.join(ROOT, '3d', 'checks', 'places', f'{SID}.json'), 'w') as f:
    json.dump(checks, f, indent=1)
log('checks', json.dumps(checks['summary']))

path = P.save(SID)
log('saved', path)

if '--render' in ARGS:
    G.renders(S, only=[a for a in ARGS if a.startswith('cam=')])
log('done')
