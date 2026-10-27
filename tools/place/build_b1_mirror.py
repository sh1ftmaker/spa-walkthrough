"""Place model: b1_mirror (05 Obsidian Mirror Float Pool). 3d/PLACE_CONTRACT.md v1.

    blender -b -P tools/place/build_b1_mirror.py                    # build + save 3d/places/b1_mirror.blend
    blender -b -P tools/place/build_b1_mirror.py -- build checks     # + 3d/checks/places/b1_mirror.json
    blender -b 3d/places/b1_mirror.blend -P tools/place/build_b1_mirror.py -- render canonical views

Concept: lookbook/img/15-obsidian-mirror.jpg (primary), refs/gen/dh-mirror.png (dollhouse). Space file
3d/spaces/b1_mirror.json gives the anchored items, portals, cameras. Deviations are listed in DEVIATIONS.
"""
import sys, os, json, math, random, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'place'))
import bpy, bmesh
from mathutils import Vector, Matrix, Euler
import kzplace_common as P
import kzplace_b1_mirror as K
import genlib

SID = 'b1_mirror'
OUT_R = os.path.join(ROOT, '3d', 'renders', 'places', SID)
OUT_C = os.path.join(ROOT, '3d', 'checks', 'places', f'{SID}.json')
SCR = os.path.join(ROOT, '.scratch', 'pl_b1_mirror')

DEVIATIONS = [
    'pool_steps: 8 risers x 0.175 m (space file: 4 x 0.17) so the entry reaches the bed at -21.4; the stair '
    'origin sits inside the rim so the top nosing is on the rim.',
    'pine_se: pine_niwaki seed 4 (pale niwaki) stands in for pine_bonsai "niwaki large" (pine_bonsai has no generator).',
    'bench_stone -> bench style slab (bench_stone has no generator).',
    'east_arch: facing 288.4 (space file 270) so the arch sits square to the east portal line of layout b1_cor_east.',
    'Concept wins: 12 extra lantern_niche along the far (east) rim and the north rim, the "line of small lanterns '
    'along the far rim doubled in the water" of concept 15; the space file only pairs 8 at the pavilions/steps/lounges.',
    'Concept wins: NW pavilion (with shoji_glow_0 and rim_lamps_0/1) rotated 8.5 deg clockwise about the pool centre '
    'along the north rim so the concept camera frames it on the left as concept 15 does.',
    'Concept wins: warm wall-wash spot lights at the wall foot (concept 15 rock walls glow amber up to the springing).',
    'Hinoki boardwalk ring r 12.85-15.35 (dollhouse / plan 33 deck ring), floor elsewhere wet basalt.',
    'glowworm_ceiling: one 38 x 38 m patch (w/d beyond the documented 4-30 range) conformed to the dome '
    'instead of tiles: one continuous galaxy band like concept 15, no tile seams.',
]

# --------------------------------------------------------------------------------------------- args
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['build']
MODES = set(argv) or {'build'}


def log(*a):
    print('[b1_mirror]', *a, flush=True)


# --------------------------------------------------------------------------------------------- helpers
def finish_shell(o, angle=40):
    genlib.uv0_metric(o)
    genlib._flat_by_angle(o, angle)
    o['kz_bake'] = o.get('kz_bake', True)
    return o


def bearing_to(a, b):
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360


GROUND = None
NW_SHIFT_DEG = 8.5
DOME_TINT = (0.28, 0.3, 0.36)    # cave_rock tint on the dome only (albedo ~1/3)
SPRITE_K = 2.6        # render-only glowworm sprite scale (see preview_fx)
MIST_D = 1.4         # render-only mist density
WALLWASH_W = 1250.0      # diffuse-only (visible_glossy off): the band must survive a diffuse lightmap
LANTERN_K = 3.6           # rim lamp light multiplier (diffuse-only), 25 W -> 75 W


def hide_source(l):
    """fill / wash lights light the scene but are not seen directly or in the mirror water."""
    l.visible_camera = False; l.visible_glossy = False; l.visible_transmission = False
    l['kz_hidden_source'] = True


def arch_threshold(o):
    """height of the portal_arch threshold top at the opening centre (raycast on the arch alone)."""
    bpy.context.view_layer.update()
    b = K.bvh_of([o])
    best = 0.0
    for u in (-1.0, 0.0, 1.0):
        p = o.matrix_world @ Vector((u, 0.0, 1.5))
        h = b.ray_cast(p, Vector((0, 0, -1)), 3.0)
        if h[0] is not None:
            best = max(best, h[0].z - o.matrix_world.translation.z)
    return best


def ground_z(x, y, z0=-15.0):
    hit = GROUND.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)), 10.0)
    return hit[0].z if hit[0] is not None else K.FLOOR


def kelvin(k):
    return P.kelvin_rgb(k)


def lights_from(o, scale=1.0, prefix=None):
    """Blender lights in kz_lights from a dressed object's kz_lights JSON (local -> world)."""
    raw = o.get('kz_lights')
    if not raw:
        return []
    L = json.loads(raw) if isinstance(raw, str) else raw
    out = []
    M = o.matrix_world
    R3 = M.to_3x3().normalized()
    for i, e in enumerate(L):
        kind = (e.get('kind') or e.get('type') or 'point').upper()
        pos = M @ Vector(e['pos'])
        col = e.get('color') or kelvin(e.get('color_k', 2700))
        watts = float(e.get('watts', 12.0)) * scale
        name = f'L_{prefix or o.name}_{i}'
        fwd = (R3 @ Vector(e.get('normal', [0, 1, 0]))).normalized()
        if o.get('kz_asset') == 'lantern_niche':
            pos = pos + (R3 @ Vector((0, 1, 0))) * 0.16           # out of the paper box (a light inside it is trapped)
        elif kind == 'AREA':
            pos = pos + fwd * 0.08
        if kind == 'AREA':
            sz = e.get('size', [0.5, 0.5])
            sz = sz if isinstance(sz, (list, tuple)) else [sz, sz]
            l = P.light(name, 'AREA', pos, watts, kelvin=e.get('color_k', 2600), size=sz[0])
            l.data.shape = 'RECTANGLE'; l.data.size = sz[0]; l.data.size_y = sz[1]
            n = (R3 @ Vector(e.get('normal', [0, 0, -1]))).normalized()
            l.rotation_euler = n.to_track_quat('-Z', 'Y').to_euler()
        else:
            l = P.light(name, 'POINT', pos, watts, kelvin=e.get('color_k', 2400), size=0.05)
        l.data.color = col[:3]
        l['kz_source'] = o.name
        out.append(l)
    return out


def dress(asset, seed, at, heading, snap=True, sink=0.0, coll='kz_render', name=None, **kw):
    x, y, z = at
    if snap:
        z = ground_z(x, y) - sink
    o = P.dress(asset, seed=seed, at=(x, y, z), heading=heading, collection=coll, name=name, **kw)
    o['kz_embed_allowed'] = round(sink + 0.02, 3)
    return o


# --------------------------------------------------------------------------------------------- build
def build():
    global GROUND
    t0 = time.time()
    P.reset()
    S = P.space(SID)
    A = {a['id']: a for a in S['anchored']}
    # concept 15 frames the NW pavilion on the left of the concept camera: rotate it (and its glow + lamp pair)
    # 8.5 deg clockwise about the pool centre so it sits inside the frame (see DEVIATIONS)
    def rot(xy, deg):
        t = math.radians(-deg); x, y = xy[0] - K.CX, xy[1] - K.CY
        return [K.CX + x * math.cos(t) - y * math.sin(t), K.CY + x * math.sin(t) + y * math.cos(t)] + list(xy[2:])
    for aid in ('pavilion_nw', 'shoji_glow_0', 'rim_lamps_0', 'rim_lamps_1'):
        A[aid] = dict(A[aid], at=rot(A[aid]['at'], NW_SHIFT_DEG))
        if 'facing_deg' in A[aid]:
            A[aid]['facing_deg'] = (A[aid]['facing_deg'] + NW_SHIFT_DEG) % 360
    keep = [(A['pavilion_nw']['at'][0], A['pavilion_nw']['at'][1], 3.3),
            (A['pavilion_se']['at'][0], A['pavilion_se']['at'][1], 3.3)]
    wall_bm, dome_bm, info = K.build_shell(seed=1, keep_out=keep)
    wall = finish_shell(P.mesh_object('mirror_wall', wall_bm, 'kz_render', role='wall', material='basalt_wet'), 38)
    dome = finish_shell(P.mesh_object('mirror_dome', dome_bm, 'kz_render', role='ceiling', material='cave_rock'), 38)
    # dark dome rock: low albedo so bounce from the lit wall band does not paint the starfield's ground brown
    import matlib
    matlib.assign(dome, 'cave_rock', tint=DOME_TINT)
    dome['kz_material_params'] = json.dumps(dict(tint=DOME_TINT))
    floor = finish_shell(P.mesh_object('mirror_floor', K.build_floor(S, info), 'kz_render', role='floor', material='basalt_wet'), 30)
    basin = finish_shell(P.mesh_object('mirror_basin', K.build_basin(S), 'kz_render', role='basin', material='obsidian'), 30)
    # stair geometry first: its heading / position decide the deck and curb gaps
    st = A['pool_steps']
    th_st = math.atan2(st['at'][1] - K.CY, st['at'][0] - K.CX)
    hd = st['facing_deg']
    fwd = Vector((math.sin(math.radians(hd)), math.cos(math.radians(hd)), 0))     # stair +Y (front) = into the pool
    rim_pt = Vector((K.CX + 12.0 * math.cos(th_st), K.CY + 12.0 * math.sin(th_st), 0))
    deck = finish_shell(P.mesh_object('mirror_deck', K.build_deck(gaps=[(th_st, 1.25)]), 'kz_render', role='floor',
                                      material='hinoki:wet_oiled'), 30)
    wat = P.mesh_object('w_mirror', K.build_water(S), 'kz_water', role='water', material='water_still:mirror', bake=False,
                        water='w_mirror', water_kind='still', planar=True, absorption=[2.6, 2.3, 2.0], flow=[0.0, 0.0])
    genlib.uv0_metric(wat)
    wat['kz_salt'] = True; wat['kz_temp'] = 35
    GROUND = K.bvh_of([floor, deck, basin])
    log('shell', round(time.time() - t0, 1), 's')

    # ---------------------------------------------------------------- hero: glowworm dome
    H = S['hero']
    gw = P.dress('glowworm_ceiling', seed=1, at=tuple(H['at']), heading=H['facing_deg'], w=38.0, d=38.0, skin=True, density=40, cluster=0.85,
                 style='galaxy', name='glowworm_ceiling.dome')
    n_left = K.conform_glowworm(gw, [wall, dome])
    P.tag(gw, role='emissive', bake=False)
    gw['kz_params'] = json.dumps(dict(json.loads(gw['kz_params']), skin_stripped=True, conformed='dome'))
    gw['kz_hero'] = True
    # second patch wrapped round the upper wall (springing band), concept 15: worms run down the walls
    gw2 = P.dress('glowworm_ceiling', seed=2, at=(K.CX, K.CY, -14.6), heading=0, w=118.0, d=3.8, skin=True,
                  style='scatter', density=13, cluster=0.9, name='glowworm_ceiling.wall')
    n2 = K.conform_glowworm_wall(gw2, [wall, dome], z0=-16.3)
    P.tag(gw2, role='emissive', bake=False)
    gw2['kz_params'] = json.dumps(dict(json.loads(gw2['kz_params']), skin_stripped=True, conformed='wall band -16.3..-12.5'))
    log('glowworm wall verts', n2)
    log('glowworm verts', n_left, round(time.time() - t0, 1), 's')

    D = []          # dressing objects
    # ---------------------------------------------------------------- pavilions
    for aid, seed in (('pavilion_nw', 1), ('pavilion_se', 2)):
        a = A[aid]
        o = dress('pavilion_engawa', seed, a['at'], a['facing_deg'], name=aid, variant='mirror', w=a['dims']['w'],
                  d=a['dims']['d'], podium=0.8)
        D.append(o)
    a = A['pine_se']
    D.append(dress('pine_niwaki', 4, a['at'], a['facing_deg'], name='pine_se', h=3.2, style='niwaki', tint='pale'))
    # ---------------------------------------------------------------- pool steps
    stair_at = rim_pt + fwd * 1.53
    stair = P.dress('stair', seed=1, at=(stair_at.x, stair_at.y, K.BED_Z), heading=hd, name='pool_steps',
                    style='pool_entry', steps=8, rise=-(K.FLOOR - K.BED_Z), w=1.8)
    stair['kz_embed_allowed'] = 0.0
    stn = json.loads(stair['kz_stair'])['top_nosing']
    bpy.context.view_layer.update()
    off = stair.matrix_world.to_3x3() @ Vector((stn[0], stn[1], 0))
    stair.location.x = rim_pt.x - off.x; stair.location.y = rim_pt.y - off.y
    D.append(stair)
    # ---------------------------------------------------------------- east arch (west one belongs to b1_cor_mirror)
    pe = K.PORTALS['p_b1_mirror_east']
    arch_head = (math.degrees(math.atan2(-pe['ax'].x, -pe['ax'].y))) % 360
    arch = dress('portal_arch', 1, (pe['at'][0], pe['at'][1], -20), arch_head, name='east_arch', style='basalt',
                 clear_w=4.0, clear_h=3.25, noren=False)
    thr = arch_threshold(arch)
    arch.location.z -= thr
    log('arch threshold', round(thr, 3))
    arch['kz_embed_allowed'] = round(thr + 0.02, 3)
    arch['kz_note'] = f'sunk {thr:.3f} m so its basalt threshold is flush with floor_z (portal joins without a step)'
    D.append(arch)
    # ---------------------------------------------------------------- benches
    for aid, seed in (('lounge_1', 1), ('lounge_2', 2), ('lounge_n', 3)):
        a = A[aid]
        L = a.get('dims', {}).get('l') or a.get('dims', {}).get('w') or 2.4
        D.append(dress('bench', seed, a['at'], a['facing_deg'], name=aid, style='slab', l=L))
    # ---------------------------------------------------------------- lanterns (anchored pairs + the far-rim line)
    lanterns = []
    for k in range(8):
        a = A[f'rim_lamps_{k}']
        lanterns.append((a['at'][0], a['at'][1], a['facing_deg']))
    extra_th = [-62, -50, -38, -27, 14, 25, 36, 47, 59, 72, 101, 123]          # deg about the pool centre
    for th in extra_th:
        t = math.radians(th)
        x, y = K.CX + 12.9 * math.cos(t), K.CY + 12.9 * math.sin(t)
        lanterns.append((x, y, bearing_to((x, y), (K.CX, K.CY))))
    for i, (x, y, f) in enumerate(lanterns):
        o = dress('lantern_niche', 1 + i % 3, (x, y, -20), f, name=f'rim_lamp_{i:02d}', w=0.36, h=0.42)
        o['kz_bake'] = False
        D.append(o)
    # ---------------------------------------------------------------- rocks
    a = A['deck_rock_e']
    D.append(dress('rock_cluster', 1, a['at'], a['facing_deg'], sink=0.12, name='deck_rock_e', w=a['dims']['w']))
    rng = random.Random(61)
    nav = [tuple(p[:2]) for p in S['spine']] + [tuple(p[:2]) for s in S['spurs'] for p in s['points']]
    anchors = [tuple(a['at'][:2]) for a in A.values()]
    portals = [tuple(p['at']) for p in S['portals']]

    def clear_of(x, y, nav_r, anc_r, por_r=4.5, extra=()):
        if any(math.hypot(x - a, y - b) < nav_r for a, b in nav):
            return False
        if any(math.hypot(x - a, y - b) < anc_r for a, b in anchors):
            return False
        if any(math.hypot(x - a, y - b) < por_r for a, b in portals):
            return False
        return all(math.hypot(x - a, y - b) >= r for a, b, r in extra)

    placed = []
    tries = 0
    while len(placed) < 9 and tries < 400:
        tries += 1
        th = rng.uniform(-math.pi, math.pi)
        rr = rng.uniform(16.9, 17.9)
        x, y = K.CX + rr * math.cos(th), K.CY + rr * math.sin(th)
        sc = rng.uniform(0.6, 1.4)
        if not clear_of(x, y, 2.2, 3.4 + sc, extra=[(a, b, 3.2) for a, b in placed]):
            continue
        o = dress('rock_cluster', 2 + len(placed), (x, y, -20), bearing_to((x, y), (K.CX, K.CY)) + rng.uniform(-30, 30),
                  sink=0.15, name=f'wall_rocks_{len(placed):02d}', w=round(2.4 * sc, 2))
        placed.append((x, y)); D.append(o)
    # boulder rim ring (space dressing rule): r 12.15-12.35, spacing 1.0-1.8 (we use 1.3-2.2 for the budget)
    rule = next(r for r in S['dressing'] if r['asset'] == 'boulder_rim')
    lamp_xy = [(x, y) for x, y, _ in lanterns]
    th = -math.pi
    nb = 0
    while th < math.pi:
        rr = rng.uniform(*rule['radius'])
        x, y = K.CX + rr * math.cos(th), K.CY + rr * math.sin(th)
        sc = rng.uniform(*rule['scale'])
        size = round(1.2 * sc, 3)
        ok = abs(K.wrap(th - th_st)) * 12.0 > 1.6 and all(math.hypot(x - a, y - b) > 0.55 + size / 2 for a, b in lamp_xy)
        if ok:
            top = rng.uniform(*rule['top_z'])
            hgt = size * (0.75 if size <= 0.6 else 0.66)
            sink = max(rule['embed'], hgt - (top - K.FLOOR))
            o = dress('boulder_rim', 1 + nb % 4, (x, y, -20), math.degrees(th) + rng.uniform(-40, 40), sink=sink,
                      name=f'rim_boulder_{nb:02d}', size=size)
            D.append(o); nb += 1
        th += rng.uniform(1.3, 2.2) / 12.25
    log('dressing', len(D), round(time.time() - t0, 1), 's')

    # ---------------------------------------------------------------- lights
    for o in D:
        if o.get('kz_asset') == 'lantern_niche':
            # rim lamps carry the rim as baked diffuse light: stronger, and kept out of glossy rays
            for l in lights_from(o, scale=LANTERN_K, prefix=o.name):
                l.visible_glossy = False; l['kz_diffuse_only'] = True
                # downward 150 deg cone: lights the rim stones, deck and water edge, never the dome
                l.data.type = 'SPOT'; l.data.spot_size = math.radians(150); l.data.spot_blend = 0.6
                out_dir = (o.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
                l.rotation_euler = (out_dir * 0.35 + Vector((0, 0, -1))).to_track_quat('-Z', 'Z').to_euler()
        elif o.get('kz_asset') in ('pavilion_engawa', 'stair', 'portal_arch'):
            lights_from(o, prefix=o.name)
    for aid in ('shoji_glow_0', 'shoji_glow_1'):
        a = A[aid]
        P.light(f'L_{aid}', 'POINT', a['at'], 10.0, kelvin=2600, size=0.3)
    a = A['east_spill']
    P.light('L_east_spill', 'POINT', a['at'], 40.0, kelvin=6500, size=0.3)
    # cold glow deep in the east stub (the glacier's light beyond the arch, concept 15 far arch)
    tip = Vector((pe['at'][0], pe['at'][1], -18.4)) + pe['ax'] * (pe['depth'] - 0.3)
    l = P.light('L_east_beyond', 'AREA', tip, 260.0, kelvin=7500, size=3.6)
    l.data.shape = 'RECTANGLE'; l.data.size = 3.6; l.data.size_y = 2.6
    l.rotation_euler = (-pe['ax']).to_track_quat('-Z', 'Y').to_euler()
    hide_source(l)
    # glowworm cyan fill (the hero's own light, from its kz_lights: 9000 K, downward, patch-sized)
    gl = P.light('L_glowworm_fill', 'AREA', (K.CX, K.CY, -9.0), 90.0, kelvin=9000, size=26.0, runtime=False)
    gl.data.shape = 'DISK'; gl.data.size = 26.0
    gl['kz_source'] = gw.name
    hide_source(gl)
    # the worms' own glow on the dome rock around them: a faint cyan up-light (bake only, unseen)
    gu = P.light('L_glowworm_rock', 'AREA', (K.CX, K.CY, -17.5), 60.0, kelvin=9000, size=24.0)
    gu.data.shape = 'DISK'; gu.data.size = 24.0; gu.rotation_euler = (math.pi, 0, 0)
    hide_source(gu)
    # warm wall wash (concept 15: the rock walls glow amber from the rim up to the springing): soft area lights
    # standing off the wall and facing it, unseen by the camera; their backs face the pool so the mirror stays clean
    k = 0
    for thd in range(-171, 189, 15):
        t = math.radians(thd)
        if any(abs(K.wrap(t - p['theta'])) < math.radians(9) for p in K.PORTALS.values()):
            continue
        # horizontal, outward-facing, 80 deg spread: no ray leaves the light more than 40 deg above level, and
        # from 1.8 m off the wall those reach the wall below ~-16.4, so no direct wash reaches the dome
        # (light linking would not survive the bake's merge-by-material, so the geometry of the light does it)
        p0 = Vector((K.CX + 17.2 * math.cos(t), K.CY + 17.2 * math.sin(t), K.FLOOR + 1.7))
        aim = Vector((K.CX + 19.0 * math.cos(t), K.CY + 19.0 * math.sin(t), K.FLOOR + 1.7))
        l = P.light(f'L_wallwash_{k:02d}', 'AREA', p0, WALLWASH_W, kelvin=2300, size=5.0)
        l.data.shape = 'RECTANGLE'; l.data.size = 6.5; l.data.size_y = 1.8; l.data.spread = math.radians(84)
        l.rotation_euler = (aim - p0).to_track_quat('-Z', 'Y').to_euler()
        l.visible_camera = False; l.visible_glossy = False
        l['kz_hidden_source'] = True; l['kz_diffuse_only'] = True
        k += 1
    # ---------------------------------------------------------------- figures (kz_anim)
    figs = [('guest_figure', 12, (105.6, 93.6), 78, dict(pose='floating', clothing='swimsuit'), 'float_back'),
            ('guest_figure', 6, (114.2, 88.2), 105, dict(pose='floating', clothing='swimsuit'), 'float_back'),
            ('guest_figure', 1, (118.8, 94.6), 60, dict(pose='floating', clothing='swimsuit', body='adult_woman'), 'float_back'),
            ('guest_figure', 9, (124.4, 84.0), 300, dict(pose='standing'), 'idle_lookup')]
    for i, (asset, seed, xy, hdg, kw, clip) in enumerate(figs):
        if kw.get('pose') == 'floating':
            z = K.WATER_Z - 0.12
        else:
            z = ground_z(*xy)
        o = P.dress(asset, seed=seed, at=(xy[0], xy[1], z), heading=hdg, collection='kz_anim', name=f'figure_{i}', **kw)
        o['kz_clip'] = clip; o['kz_bake'] = False
        rig = bpy.data.objects.get(o.get('kz_rig', ''))
        if rig:
            P.link(rig, 'kz_anim')
    # ---------------------------------------------------------------- fx: mist on the west + north rims
    for i, thd in enumerate(range(95, 215, 12)):
        t = math.radians(thd)
        P.fx(f'fx_mist_{i:02d}', 'mist', (K.CX + 12.5 * math.cos(t), K.CY + 12.5 * math.sin(t), K.WATER_Z),
             kz_height=0.45, kz_radius=2.6, kz_density=0.55, kz_drift=[0.05, 0.0])
    P.fx('fx_glowworm_twinkle', 'glowworm', (K.CX, K.CY, -8.0), kz_target=gw.name)
    # ---------------------------------------------------------------- cameras, probes
    P.cameras(S)
    P.probe(SID, 0, (112, 92, -18.4), (93, 73, -21.4), (131, 111, -6.5))
    P.probe(SID, 1, (116.0, 104.5, -18.5), (110, 101, -20.0), (122, 111, -14.0))
    P.probe(SID, 2, (121.0, 81.5, -18.5), (115, 74, -20.0), (128, 85, -14.0))
    # ---------------------------------------------------------------- walk mesh
    obstacles = [('mesh', wall, K.FLOOR + 2.6)]
    for o in D:
        if o.get('kz_asset') in ('pavilion_engawa', 'rock_cluster'):
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            xs = [v.x for v in bb]; ys = [v.y for v in bb]
            # oriented footprint from the local bbox corners at z min
            loc = [Vector(c) for c in o.bound_box]
            mn = Vector((min(c.x for c in loc), min(c.y for c in loc), 0)); mx = Vector((max(c.x for c in loc), max(c.y for c in loc), 0))
            sh = 0.85 if o.get('kz_asset') == 'rock_cluster' else 1.0
            ctr = (mn + mx) / 2
            pts = [o.matrix_world @ (ctr + (Vector((x, y, 0)) - ctr) * sh) for x, y in ((mn.x, mn.y), (mx.x, mn.y), (mx.x, mx.y), (mn.x, mx.y))]
            obstacles.append(('prism', [(p.x, p.y) for p in pts], K.FLOOR, K.FLOOR + 1.2))
    walk_bm = K.build_walk(S, info, floor, basin, stair, obstacles, gaps_curb=[(th_st, 1.0)])
    walk = P.mesh_object('walk_b1_mirror', walk_bm, 'kz_walk', role='walk', bake=False)
    for o in bpy.data.collections['kz_lod'].objects:
        o.hide_render = True
    # scene settings (render-ready)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc['kz_space'] = SID
    sc['kz_deviations'] = json.dumps(DEVIATIONS)
    sc.camera = bpy.data.objects.get('cam_concept')
    p = P.save(SID)
    log('saved', p, round(time.time() - t0, 1), 's')


# --------------------------------------------------------------------------------------------- checks
def in_coll(name):
    return [o for o in bpy.data.objects if name in [c.name for c in o.users_collection]]


def render_objs():
    return [o for o in in_coll('kz_render') if o.type == 'MESH']


def tri_count(o):
    if o.get('kz_asset') == 'glowworm_ceiling':
        return 0
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def checks():
    S = P.space(SID)
    res = dict(space=SID, generated=time.strftime('%Y-%m-%d %H:%M'), deviations=DEVIATIONS)
    objs = render_objs()
    anim = [o for o in in_coll('kz_anim') if o.type == 'MESH']
    tris_r = sum(tri_count(o) for o in objs)
    tris_a = sum(tri_count(o) for o in anim)
    tris_w = sum(tri_count(o) for o in bpy.data.collections['kz_water'].objects)
    by = {}
    for o in objs + anim:
        k = o.get('kz_asset') or o.name
        by[k] = by.get(k, 0) + tri_count(o)
    mats = set(); ids = set()
    for o in objs + anim + list(bpy.data.collections['kz_water'].objects):
        for m in o.data.materials:
            if m:
                mats.add(m.name); ids.add(m.get('kz_id') or m.name.split('~')[0])
    nsp = {o.name: sum(1 for a in o.data.attributes['kz_sprite'].data if a.value > 0.9)
           for o in objs if o.get('kz_asset') == 'glowworm_ceiling'}
    res['triangles'] = dict(total=tris_r + tris_a + tris_w, render=tris_r, anim=tris_a, water=tris_w, by_asset=dict(sorted(by.items(), key=lambda kv: -kv[1])),
                            budget=250000, pass_=tris_r + tris_a + tris_w <= 250000)
    res['materials'] = dict(distinct_material_datablocks=len(mats), distinct_library_ids=len(ids), ids=sorted(ids), budget=40,
                            pass_=len(ids) <= 40, note='datablocks include per-slot parameter variants of the same library id')
    res['glowworm_points'] = nsp
    # walk mesh flood fill on a 0.25 m height grid: a move between neighbouring cells needs a step <= 0.2 m and
    # no walk-mesh face crossing a ray 0.22 m above the lower cell (walls, curbs, obstacle prisms)
    walk = bpy.data.objects['walk_b1_mirror']
    wb = K.bvh_of([walk])
    G = 0.25
    x0, y0, nx, ny = 91.0, 70.0, int(42 / G), int(44 / G)
    hz = {}
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + (i + 0.5) * G, y0 + (j + 0.5) * G
            h = wb.ray_cast(Vector((x, y, -17.0)), Vector((0, 0, -1)), 6.0)
            if h[0] is not None and abs(h[1].z) > 0.7:
                hz[(i, j)] = h[0].z
    def cell(x, y):
        i, j = int((x - x0) / G), int((y - y0) / G)
        best = min(hz, key=lambda c: (c[0] - i) ** 2 + (c[1] - j) ** 2 + (0 if hz[c] > -20.2 or (x, y) == (K.CX, K.CY) else 99))
        return best
    from collections import deque
    def flood(c0):
        seen = {c0}; q = deque([c0])
        while q:
            c = q.popleft(); za = hz[c]
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + d[0], c[1] + d[1])
                if n in seen or n not in hz:
                    continue
                zb = hz[n]
                if abs(zb - za) > 0.205:
                    continue
                lo = min(za, zb) + 0.22
                pa = Vector((x0 + (c[0] + 0.5) * G, y0 + (c[1] + 0.5) * G, lo))
                pb = Vector((x0 + (n[0] + 0.5) * G, y0 + (n[1] + 0.5) * G, lo))
                if wb.ray_cast(pa, (pb - pa).normalized(), G)[0] is not None:
                    continue
                seen.add(n); q.append(n)
        return seen
    targets = {p['id']: p['at'] for p in S['portals']}
    targets['hero_view'] = S['cameras']['concept']['pos'][:2]
    targets['pool_bed_centre'] = (K.CX, K.CY)
    seeds = {k: cell(*v) for k, v in targets.items()}
    fill = {}
    for pid in [p['id'] for p in S['portals']]:
        seen = flood(seeds[pid])
        fill[pid] = {k: (seeds[k] in seen) for k in targets if k != pid}
        fill[pid]['cells_reached'] = len(seen)
    res['walk_flood'] = dict(result=fill, grid_m=G, cells=len(hz),
                             pass_=all(v for r in fill.values() for k, v in r.items() if k != 'cells_reached'))
    # clearance above the spine (shell + dressing, figures excluded)
    bvh = K.bvh_of([o for o in objs if o.get('kz_asset') != 'glowworm_ceiling'])
    pts = [Vector(p) for p in S['spine']]
    samples = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int((b - a).length / 0.5))
        for i in range(n):
            samples.append(a.lerp(b, i / n))
    samples.append(pts[-1])
    worst = (99.0, None)
    fails = []
    for s in samples:
        gz = ground_hit(bvh, s.x, s.y)
        h = bvh.ray_cast(Vector((s.x, s.y, gz + 0.03)), Vector((0, 0, 1)), 30.0)
        cl = (h[0].z - gz) if h[0] is not None else 99.0
        if cl < worst[0]:
            worst = (cl, [round(s.x, 2), round(s.y, 2)])
        if cl < 2.1:
            fails.append([round(s.x, 2), round(s.y, 2), round(cl, 2)])
    res['spine_clearance'] = dict(min_m=round(worst[0], 2), at=worst[1], samples=len(samples), fails=fails[:20], pass_=not fails)
    # portals open at floor level
    pr = {}
    for p in S['portals']:
        info = K.PORTALS[p['id']]
        at = Vector((p['at'][0], p['at'][1], 0))
        gz = ground_hit(bvh, at.x, at.y)
        blocked = []
        for u in [-p['width'] / 2 + 0.1 + k * (p['width'] - 0.2) / 6 for k in range(7)]:
            for hz in (0.25, 1.0, 1.8, p['height'] - 0.1):
                o0 = at + info['t'] * u - info['ax'] * 1.0 + Vector((0, 0, K.FLOOR + hz))
                h = bvh.ray_cast(o0, info['ax'], 2.0)
                if h[0] is not None:
                    blocked.append([round(u, 2), hz, h[3] if False else round((h[0] - o0).length, 2)])
        pr[p['id']] = dict(floor_z=round(gz, 3), floor_ok=abs(gz - K.FLOOR) <= 0.03, blocked_rays=blocked,
                           pass_=abs(gz - K.FLOOR) <= 0.03 and not blocked)
    res['portals'] = dict(result=pr, pass_=all(v['pass_'] for v in pr.values()))
    # dressing grounded (raycast at each object's base)
    gb = K.bvh_of([bpy.data.objects[n] for n in ('mirror_floor', 'mirror_deck', 'mirror_basin', 'mirror_wall')])
    bad = []; ok = 0
    for o in objs:
        if not o.get('kz_asset') or o.get('kz_asset') == 'glowworm_ceiling':
            continue
        allowed = float(o.get('kz_embed_allowed', 0.02))
        x, y, z = o.matrix_world.translation
        h = gb.ray_cast(Vector((x, y, z + 0.6)), Vector((0, 0, -1)), 3.0)
        if h[0] is None:
            bad.append([o.name, 'no ground']); continue
        d = z - h[0].z           # + floating, - sunk
        if d > 0.02 or -d > allowed + 0.02:
            bad.append([o.name, round(d, 3), 'allowed sink', allowed])
        else:
            ok += 1
    res['dressing_grounded'] = dict(ok=ok, bad=bad, pass_=not bad,
                                    note='rocks / rim boulders carry an intended embed (kz_embed_allowed); figures float in kz_anim and are not tested')
    res['all_pass'] = all(v.get('pass_', True) for v in res.values() if isinstance(v, dict))
    os.makedirs(os.path.dirname(OUT_C), exist_ok=True)
    json.dump(res, open(OUT_C, 'w'), indent=1)
    log('checks', json.dumps({k: (v.get('pass_') if isinstance(v, dict) else v) for k, v in res.items() if k not in ('deviations',)}))


def ground_hit(bvh, x, y):
    h = bvh.ray_cast(Vector((x, y, K.FLOOR + 1.0)), Vector((0, 0, -1)), 3.0)
    return h[0].z if h[0] is not None else K.FLOOR - 9


# --------------------------------------------------------------------------------------------- render
def setup_cycles(samples=128):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    c = sc.cycles
    c.device = 'GPU'; c.samples = samples; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.02
    c.use_denoising = True; c.denoiser = 'OPTIX'
    c.max_bounces = 8; c.glossy_bounces = 4; c.diffuse_bounces = 3; c.transmission_bounces = 6
    c.caustics_reflective = False; c.caustics_refractive = False; c.blur_glossy = 0.5
    c.light_sampling_threshold = 0.005
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92


def render_cam(cam, path, res, samples=128):
    sc = bpy.context.scene
    setup_cycles(samples)
    sc.camera = bpy.data.objects[cam]
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log('rendered', path, round(time.time() - t, 1), 's')


def portrait_cam(src, name):
    """same pose and vertical fov as the 16:9 camera, rendered 9:16 (phone portrait)."""
    c = bpy.data.objects[src]
    o = bpy.data.objects.new(name, c.data.copy())
    o.matrix_world = c.matrix_world.copy()
    bpy.context.scene.collection.objects.link(o)
    return o


def preview_fx():
    """RENDER-ONLY previews (never saved to the place .blend):
    * glowworm sprites: the runtime draws kz_sprite points as screen-space sprites of >= ~2 px; the Blender
      preview instances spheres of radius kz_size (5-17 mm), sub-pixel at 15-25 m. Scale them x SPRITE_K so the
      canonical shows what the runtime sprite pass shows.
    * fx_mist: a low scattering volume (0.5 m) round each kz_fx mist empty."""
    ng = bpy.data.node_groups.get('kz_glowworm_preview')
    if ng:
        iop = next(n for n in ng.nodes if n.bl_idname == 'GeometryNodeInstanceOnPoints')
        src = iop.inputs['Scale'].links[0].from_socket
        mul = ng.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = SPRITE_K
        ng.links.new(src, mul.inputs[0]); ng.links.new(mul.outputs[0], iop.inputs['Scale'])
    m = bpy.data.materials.new('preview_mist'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); vol = nt.nodes.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (0.75, 0.78, 0.8, 1)
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.45
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -0.5; mr.inputs['From Max'].default_value = 0.5
    mr.inputs['To Min'].default_value = MIST_D; mr.inputs['To Max'].default_value = 0.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(mr.outputs[0], mul.inputs[0]); nt.links.new(nz.outputs['Fac'], mul.inputs[1])
    nt.links.new(mul.outputs[0], vol.inputs['Density']); nt.links.new(vol.outputs[0], out.inputs['Volume'])
    for e in [o for o in bpy.data.objects if o.get('kz_fx') == 'mist']:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=e.get('kz_radius', 2.5), radius2=e.get('kz_radius', 2.5), depth=1.0)
        me = bpy.data.meshes.new('mist_prev'); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new('preview_' + e.name, me); o.location = e.location + Vector((0, 0, 0.3))
        o.scale = (1.0, 1.0, 0.6)
        me.materials.append(m)
        bpy.context.scene.collection.objects.link(o)


def render(which):
    import matlib
    matlib.refresh()
    preview_fx()
    os.makedirs(OUT_R, exist_ok=True)
    os.makedirs(SCR, exist_ok=True)
    if 'canonical' in which:
        render_cam('cam_concept', os.path.join(SCR, 'canonical_raw.jpg'), (1600, 900), 128)
    if 'noglossy' in which:
        # diffuse-bake proxy: every light hidden from glossy rays (what the lightmap + 6 live lights can carry)
        for o in bpy.data.objects:
            if o.type == 'LIGHT':
                o.visible_glossy = False
        render_cam('cam_concept', os.path.join(SCR, 'canonical_noglossy.jpg'), (1600, 900), 128)
    if 'views' in which:
        for cam in ('cam_entry', 'cam_reveal'):
            render_cam(cam, os.path.join(SCR, f'{cam}_169.jpg'), (960, 540), 96)
            pc = portrait_cam(cam, cam + '_p')
            render_cam(pc.name, os.path.join(SCR, f'{cam}_916.jpg'), (540, 960), 96)
        plan()


def plan():
    """top-down plan: ceiling + glowworms hidden, walk mesh tinted, soft overhead light (render only, not saved)."""
    sc = bpy.context.scene
    for o in in_coll('kz_render'):
        if o.get('kz_role') == 'ceiling' or o.get('kz_asset') == 'glowworm_ceiling':
            o.hide_render = True
    w = bpy.data.objects['walk_b1_mirror']
    bpy.data.collections['kz_walk'].hide_render = False
    m = bpy.data.materials.new('plan_walk_tint'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); mix = nt.nodes.new('ShaderNodeMixShader')
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.1, 1.0, 0.35, 1); em.inputs['Strength'].default_value = 1.2
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix.inputs['Fac'].default_value = 0.35
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs[0])
    w.data.materials.clear(); w.data.materials.append(m)
    w.location.z += 0.03
    l = P.light('plan_sun', 'SUN', (112, 92, 0), 1.2, kelvin=5200)
    l.data.angle = math.radians(20)
    cd = bpy.data.cameras.new('cam_plan'); cd.type = 'ORTHO'; cd.ortho_scale = 46
    c = bpy.data.objects.new('cam_plan', cd); c.location = (112, 92, 5); sc.collection.objects.link(c)
    render_cam('cam_plan', os.path.join(SCR, 'plan.jpg'), (900, 900), 48)


if 'build' in MODES:
    build()
if 'checks' in MODES:
    if 'build' not in MODES:
        pass
    S0 = P.space(SID)
    GROUND = K.bvh_of([bpy.data.objects[n] for n in ('mirror_floor', 'mirror_deck', 'mirror_basin')])
    checks()
if 'render' in MODES:
    render([m for m in MODES if m in ('canonical', 'views', 'noglossy')] or ['canonical'])
