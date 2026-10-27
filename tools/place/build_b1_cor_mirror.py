"""Build the b1_cor_mirror place model (mist corridor to the Mirror), deterministic.

    blender -b -P tools/place/build_b1_cor_mirror.py                 # build, checks, save 3d/places/b1_cor_mirror.blend
    blender -b -P tools/place/build_b1_cor_mirror.py -- render [concept|views|plan|all]
                                                                     # open the saved place, add preview-only mist and the
                                                                     # Mirror stand-in glow (not saved), render the proofs

Realises 3d/spaces/b1_cor_mirror.json on the concept lookbook/img/05-mist-corridor.jpg.  Deviations are listed in
DEVIATIONS (also written into the checks JSON).
"""
import json, math, os, random, sys
import bpy, bmesh
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'place'))
import kzplace_common as P          # noqa: E402
import kzplace_b1_cor_mirror as K   # noqa: E402
import genlib                       # noqa: E402

SID = 'b1_cor_mirror'
SCR = os.path.join(ROOT, '.scratch', 'pl_b1_cor_mirror')
REN = os.path.join(ROOT, '3d', 'renders', 'places', SID)
CHK = os.path.join(ROOT, '3d', 'checks', 'places', f'{SID}.json')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FL = K.FLOOR

DEVIATIONS = [
    'Mouth noren: w 3.6 -> 3.2, h 1.1 -> 0.7, rod at z -17.38: a 3.6 m rod at -17.05 does not fit under the 2.4 m springing; '
    'the bottom edge stays at 1.92 m clear.',
    'lantern_floor pair and corner lantern stand on the kerb / dry threshold at z -20.0, not -20.2 (in the pool).',
    'Wall items (shoji bays, trickles, niches) are re-seated on the computed wall line (<= 0.15 m from the given xy); '
    'headings follow the wall normal.',
    'wall_trickle widths clamped to the generator range: trickle_n 0.8 -> 0.9, trickle_s 1.4 -> 1.2.',
    'portal_arch (hero, basalt, no noren) built with clear_w 4.3 / clear_h 3.25 and sunk 0.243 m (its threshold height) '
    ' so the threshold is flush with floor_z and ~3.0 m stays clear (same fix as b1_mirror, per the lead). The '
    'last 2.2 m of the vault flares up 0.75 m and out 12 % so the arch face reads instead of vanishing into the 3.0 m crown.',
    'Pool stops 0.1 m short of the arch threshold and 1.9 m inside the lobby mouth (dry stone threshold at floor_z so the '
    'lobby portal meets the stand-in without a step); it stays continuous into the koi junction.',
    'Concept 05 shows teal-lit water all along the straight: dim teal pool-bed lights (kz_runtime false) light it, '
    'stopping 7 m short of the arch like the lanterns, so the Mirror leak stays the brightest thing.',
    'Generator kz_lights sit inside the closed lantern boxes, where Cycles occludes them: niche lights are realised 0.16 m in front of the niche (kz_offset), floor-lantern lights with shadows off.',
    'Extra niche lanterns from the space file "lights" along-rule: two on the straight (x 84.0 N, x 86.2 S, last one '
    '<= 86.5) and one on the west wall of the north leg (y 89.0).',
    'Stepping stones use the stepping_stone generator at LOD1 (240 tris) in kz_render: ~100 stones at LOD0 (972) would '
    'take the corridor over its 80k budget on stones alone.',
]


# ================================================================================================ build
def wall_seat(path, xy, embed, depth):
    """centre xy and heading for an item whose back goes `embed` behind the nominal wall nearest xy"""
    st = path.nearest(xy)
    s, c2, t2, l2 = st
    side = 1 if (Vector(xy[:2]) - c2).dot(l2) > 0 else -1
    u = side * (K.W + embed - depth / 2)
    p = c2 + l2 * u
    inward = -l2 * side
    heading = math.degrees(math.atan2(inward.x, inward.y)) % 360
    return (p.x, p.y), heading, side


def build():
    S = P.space(SID)
    P.reset()
    legA, legB = K.make_paths()
    log = {'deviations': DEVIATIONS, 'placed': []}

    # ---------------------------------------------------------------- wall / floor features (seat them first)
    feats = []
    items = []            # (asset, seed, at, heading, params, name, kind)

    def seat(name, asset, seed, xy, embed, depth, w, h, kind, params, z=FL, mid=0.0, margin=0.45, path=None, lod=0):
        pth = path or (legA if Vector(xy[:2]).y < 76 and Vector(xy[:2]).x > 70 else legB)
        p, hd, side = wall_seat(pth, xy, embed, depth)
        feats.append(K.Feature(name, (p[0], p[1], z), hd, w, depth, h, kind, mid=mid, margin=margin))
        items.append((asset, seed, (p[0], p[1], z), hd, params, name, kind, lod))
        log['placed'].append(dict(name=name, asset=asset, given=list(xy), at=[round(p[0], 3), round(p[1], 3), z], heading=round(hd, 1)))

    anch = {a['id']: a for a in S['anchored']}
    # shoji bays (north wall of the straight), 'low' layout seed 1 / wider seed 4 (also 'low')
    seat('shoji_bay_1', 'shoji_wall_bay', 1, anch['shoji_bay_1']['at'], 0.15, 0.8, 1.8, 2.4, 'bay',
         dict(w=1.8, h=2.4, d=0.8), mid=-0.12, margin=0.55)
    seat('shoji_bay_2', 'shoji_wall_bay', 4, anch['shoji_bay_2']['at'], 0.15, 0.8, 2.4, 2.4, 'bay',
         dict(w=2.4, h=2.4, d=0.8), mid=-0.12, margin=0.55)
    seat('trickle_n', 'wall_trickle', 1, anch['trickle_n']['at'], 0.12, 0.6, 1.0, 2.6, 'trickle',
         dict(w=0.9, h=2.6), mid=-0.2, margin=0.5)
    seat('trickle_s', 'wall_trickle', 2, anch['trickle_s']['at'], 0.12, 0.6, 1.2, 2.6, 'trickle',
         dict(w=1.2, h=2.6), mid=-0.2, margin=0.5)
    niches = [(k, a['at']) for k, a in anch.items() if a['asset'] == 'lantern_niche']
    niches += [('niches_e_x0', [84.0, 93.85, -19.75]), ('niches_e_x1', [86.2, 90.15, -19.75]),
               ('niches_n_x0', [64.3, 89.0, -19.75])]
    for i, (k, at) in enumerate(niches):
        pth = legA if k.startswith(('mouth', 'niches_w')) else legB
        seat(k, 'lantern_niche', 1 + i % 3, at, 0.03, 0.25, 0.32, 0.4, 'niche', {}, z=at[2], mid=0.0,
             margin=0.32, path=pth, lod=1)
    # corner lantern in a carved alcove at the outside of the turn
    cl = anch['corner_lantern']
    feats.append(K.Feature('corner_alcove', (cl['at'][0], cl['at'][1], FL), 135, 1.7, 0.6, 1.3, 'alcove', margin=0.7))
    items.append(('lantern_floor', 2, (cl['at'][0], cl['at'][1], FL), 135, dict(h=0.8), 'corner_lantern', 'floor', 0))
    # bonsai on the kerb by bay 1
    b1 = anch['bonsai_1']
    feats.append(K.Feature('bonsai_1', (b1['at'][0], b1['at'][1], FL), 180, 0.7, 0.45, 1.0, 'floor'))
    items.append(('bonsai_potted', 1, (b1['at'][0], b1['at'][1], FL), 180, dict(h=1.0), 'bonsai_1', 'floor', 1))
    # lobby-mouth floor lanterns (dry threshold)
    for i, at in enumerate(S['lights'][1]['at']):
        hd = 11.3 if i == 0 else 191.3
        feats.append(K.Feature(f'mouth_lantern_{i}', (at[0], at[1], FL), hd, 0.45, 0.45, 1.05, 'floor'))
        items.append(('lantern_floor', 1, (at[0], at[1], FL), hd, {}, f'mouth_lantern_{i}', 'floor', 0))

    # ---------------------------------------------------------------- shell
    dryA = lambda s: 1.0 if s < 1.6 else (0.0 if s > 2.1 else 1 - (s - 1.6) / 0.5)
    LB = legB.length
    dryB = lambda s: 0.0 if s < LB - 1.15 else (1.0 if s > LB - 0.85 else (s - (LB - 1.15)) / 0.3)
    wallsA, vaultA, infoA = K.build_shell(legA, feats, True, True, 'A')
    wallsB, vaultB, infoB = K.build_shell(legB, feats, True, True, 'B', flare_end=0.75)
    edA = K.kerb_edges(legA, feats, dryA, infoA)
    edB = K.kerb_edges(legB, feats, dryB, infoB)
    kA, bA, wA = K.build_floor(legA, edA, (1.95, legA.length))
    kB, bB, wB = K.build_floor(legB, edB, (0.0, LB - 0.95))

    def obj(name, bms, coll, **tags):
        bm = bmesh.new()
        me_tmp = bpy.data.meshes.new('tmp')
        for b in bms:
            b.to_mesh(me_tmp); bm.from_mesh(me_tmp); b.free()
        bpy.data.meshes.remove(me_tmp)
        o = P.mesh_object(name, bm, coll, **tags)
        genlib._flat_by_angle(o, 32)
        genlib.uv0_metric(o)
        return o

    shell = [
        obj('shell_walls', [wallsA, wallsB], 'kz_render', role='wall', material='basalt_wet', bake=True),
        obj('shell_vault', [vaultA, vaultB], 'kz_render', role='ceiling', material='basalt_wet', bake=True),
        obj('shell_kerbs', [kA, kB], 'kz_render', role='floor', material='basalt_wet', bake=True),
        obj('shell_bed', [bA, bB], 'kz_render', role='basin', material='basalt_wet', bake=True),
    ]
    water = obj('water_w_b1_corridors', [wA, wB], 'kz_water', role='water', material='water_still', bake=False,
                water='w_b1_corridors', water_kind='still', planar=True, absorption=[0.42, 0.10, 0.12], flow=0.0)
    water['kz_level'] = FL + K.WATER; water['kz_space_water'] = 'w_cor_mirror'

    # ---------------------------------------------------------------- walk mesh
    wb = K.build_walk(legA, edA, infoA, feats)
    K.build_walk(legB, edB, infoB, feats, bm=wb)
    walk = P.mesh_object('walk_' + SID, wb, 'kz_walk', role='walk')
    # junction stand-in (owned by b1_junction_w): flat floor linking the two legs so the flood fill can cross
    sA = legA.st[-1]; sB = legB.st[0]
    frA = min(infoA[-1]['inner'][1], infoA[-1]['inner'][-1]) - 0.05
    frB = min(infoB[0]['inner'][1], infoB[0]['inner'][-1]) - 0.05
    A_s = sA[1] + sA[3] * frA; A_n = sA[1] - sA[3] * frA
    B_w = sB[1] + sB[3] * frB; B_e = sB[1] - sB[3] * frB
    inner, outer = Vector((69.826, 75.674)), Vector((66.174, 72.326))
    jb = bmesh.new()
    V = lambda p: jb.verts.new((p.x, p.y, FL))
    a_s, a_n, vi, b_e, b_w, vo = V(A_s), V(A_n), V(inner), V(B_e), V(B_w), V(outer)
    jb.faces.new((a_s, a_n, vi, vo)); jb.faces.new((vo, vi, b_e, b_w))
    K._orient_up(jb)
    js = P.mesh_object('walk_junction_standin', jb, 'kz_walk', role='walk', standin=True,
                       note='stand-in for b1_junction_w: delete when the junction place exists')

    # ---------------------------------------------------------------- hero: portal arch
    hero = S['hero']
    arch = P.dress('portal_arch', seed=1, at=(hero['at'][0], hero['at'][1], FL), heading=270,
                   style='basalt', noren=False, clear_w=4.3, clear_h=3.25, depth=1.4)
    bva = K.bvh_of([arch]); th = bva.ray_cast(Vector((hero['at'][0], hero['at'][1], FL + 1.0)), Vector((0, 0, -1)), 2)
    sink = 0.243     # threshold step height, same as b1_mirror (lead note); the ray probe hits a lower sill plate
    arch.location.z = FL - sink
    arch.name = 'hero_portal_arch'; arch['kz_role'] = 'hero'; arch['kz_embed'] = sink
    arch['kz_shared_with'] = 'b1_mirror'

    # ---------------------------------------------------------------- dressing: wall/floor items
    dressed = []
    for (asset, seed, at, hd, params, name, kind, lod) in items:
        z = at[2]
        o = P.dress(asset, seed=seed, at=(at[0], at[1], z), heading=hd, lod=lod, name=name, **params)
        dressed.append(o)
    # mouth noren (cloth, kz_anim: it sways)
    nor = P.dress('noren', seed=1, at=(77.4, 72.1, 0), heading=95, w=3.2, h=0.7, name='mouth_noren', collection='kz_anim')
    zmax = max((nor.matrix_world @ v.co).z for v in nor.data.vertices)
    nor.location.z = (FL + 2.62) - zmax
    nor['kz_role'] = 'cloth'; nor['kz_bake'] = False; nor['kz_clip'] = 'sway'

    # ---------------------------------------------------------------- stepping stones (two staggered rows)
    stones = []
    rs = random.Random('b1_cor_mirror:stones')
    seed_n = [0]

    def lay_stones(path, edges, s0, s1):
        s = s0
        k = 0
        while s < s1:
            for row, off in ((0, 0.0), (1, 0.41)):
                ss = s + off
                if ss > s1:
                    continue
                st = path.at(ss)
                ki = min(range(len(path.st)), key=lambda q: abs(path.st[q][0] - ss))
                emin = min(edges[ki][1][0], edges[ki][-1][0])
                u = (0.37 if row == 0 else -0.37) + rs.uniform(-0.07, 0.07)
                r = rs.uniform(0.27, 0.34)
                if abs(u) + r > emin - 0.04:
                    u = math.copysign(max(0.0, emin - 0.04 - r), u)
                if abs(u) + r > emin + 0.02 or emin < 0.6:
                    continue
                c = st[1] + st[3] * u + st[2] * rs.uniform(-0.06, 0.06)
                seed_n[0] += 1
                sd = 1 + (seed_n[0] - 1) % 9
                o = P.dress('stepping_stone', seed=sd, at=(c.x, c.y, 0), heading=rs.uniform(0, 360), lod=1,
                            name=f'stone_{len(stones):03d}', r=round(r, 3), thickness=0.18)
                h = max(v.co.z for v in o.data.vertices)
                o.location.z = FL - h            # top flush with floor_z, 5 cm above the water
                o['kz_lod_used'] = 1
                stones.append(o)
            s += 0.82 + rs.uniform(-0.06, 0.08)
            k += 1

    lay_stones(legA, edA, 2.45, legA.length - 0.3)
    lay_stones(legB, edB, 0.35, LB - 1.35)

    # ---------------------------------------------------------------- boulders (space-file rings + kerb rocks of concept 05)
    bvh_floor = K.bvh_of(shell[2:4])
    rb = random.Random('b1_cor_mirror:boulders')
    avoid = [(Vector((o.location.x, o.location.y)), 0.55) for o in dressed] + \
            [(Vector((o.location.x, o.location.y)), 0.42) for o in stones]
    boulders = []

    def ground(x, y):
        hit = bvh_floor.ray_cast(Vector((x, y, FL + 1.0)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] is not None else None

    def boulder(x, y, size, seed, name, embed_k=1.0):
        p = Vector((x, y))
        for c, r in avoid:
            if (p - c).length < r + size * 0.35:
                return None
        g = ground(x, y)
        if g is None:
            return None
        o = P.dress('boulder_rim', seed=seed, at=(x, y, 0), heading=rb.uniform(0, 360), name=name, size=round(size, 2), lod=1)
        o['kz_lod_used'] = 1
        emb = float(o.get('kz_embed', 0.12 * size)) * embed_k
        o.location.z = g - emb
        o['kz_embed'] = emb
        avoid.append((p, size * 0.45))
        boulders.append(o)
        return o

    for i, d in enumerate(S['dressing']):
        cx, cy = d['ring']
        for j in range(d['count'] * 3):
            if sum(1 for b in boulders if b.name.startswith(f'ring{i}_')) >= min(2, d['count']):
                break
            a = rb.uniform(0, 2 * math.pi); rr = rb.uniform(*d['radius'])
            boulder(cx + rr * math.cos(a), cy + rr * math.sin(a), 0.6 * rb.uniform(*d['scale']), 1 + j % 4,
                    f'ring{i}_{j}', embed_k=1.0)
    # kerb rocks along the straight and the north leg: straddling the pool edge, as in concept 05 (right side)
    kerb_spots = [(legB, 0.0, x) for x in ()]
    for x, side, size in [(70.6, -1, 0.95), (75.6, -1, 1.1), (83.3, -1, 1.0),
                          (88.6, -1, 1.15), (78.6, 1, 0.9), (87.5, 1, 1.0), (90.6, 1, 0.8)]:
        st = legB.nearest((x, 92.0)); ki = min(range(len(legB.st)), key=lambda q: abs(legB.st[q][0] - st[0]))
        e = edB[ki][side][0]
        c = st[1] + st[3] * side * (e + 0.12)
        boulder(c.x, c.y, size, 1 + int(x) % 4, f'kerbrock_{x:.0f}_{"N" if side > 0 else "S"}')
    for y, side, size in [(82.6, -1, 0.9), (87.8, -1, 0.75)]:
        st = legB.nearest((66.8, y)); ki = min(range(len(legB.st)), key=lambda q: abs(legB.st[q][0] - st[0]))
        e = edB[ki][side][0]
        c = st[1] + st[3] * side * (e + 0.12)
        boulder(c.x, c.y, size, 2 + int(y) % 3, f'kerbrock_n{y:.0f}')

    # ---------------------------------------------------------------- people (kz_anim)
    figs = []
    def figure(asset, seed, near, clip, **kw):
        tgt = Vector(near)
        st = min(stones, key=lambda o: (Vector((o.location.x, o.location.y)) - tgt).length)
        o = P.dress(asset, seed=seed, at=(st.location.x, st.location.y, FL), heading=90 + random.Random(seed).uniform(-6, 6),
                    collection='kz_anim', name=f'{asset}_{len(figs)}', **kw)
        for c in o.children:
            P.link(c, 'kz_anim')
        o['kz_clip'] = clip; o['kz_bake'] = False; o['kz_role'] = 'figure'; o['kz_on'] = st.name
        figs.append(o)
        return o
    figure('guest_figure', 8, (73.6, 92.2), 'walk_slow', body='adult_woman', clothing='yukata_linen', pose='walking', pattern='plain')
    figure('guest_figure', 2, (79.4, 92.3), 'walk_slow', body='adult_man', clothing='yukata_black', pose='walking')
    figure('guest_figure', 9, (84.6, 91.7), 'walk', body='adult_woman', clothing='yukata_linen', pose='walking', hair='bun')

    # ---------------------------------------------------------------- lights
    bpy.context.view_layer.update()          # matrix_world of the dressed objects (lights are placed from it)
    for o in dressed:
        a = o['kz_asset']
        if a == 'lantern_niche':
            K.realise_lights(P, o, offset=(0, 0.16, 0.02))          # just in front of the niche lip
        elif a == 'lantern_floor':
            K.realise_lights(P, o, shadow=False)                    # the closed andon box would swallow it
        elif a == 'shoji_wall_bay':
            K.realise_lights(P, o)
        elif a == 'wall_trickle':
            K.realise_lights(P, o, scale_w=0.25)
    for k in ('shoji_glow_0', 'shoji_glow_1'):                 # noren_glow markers: warm backlight at each bay foot
        a = anch[k]['at']
        P.light(f'L_{k}', 'POINT', (a[0], a[1] - 0.15, FL + 0.25), 10, kelvin=2600, size=0.1)
    # teal pool-bed glow (concept 05), stopping 7 m short of the arch
    teal = (0.06, 0.78, 0.72)
    n = 0
    for path, s0, s1 in ((legA, 2.4, legA.length - 0.5), (legB, 0.6, LB - 7.6)):
        s = s0
        while s < s1:
            st = path.at(s)
            for uo in (-0.6, 0.6):
                q = st[1] + st[3] * uo
                l = P.light(f'L_poolglow_{n}', 'POINT', (q.x, q.y, FL + K.BED + 0.04), 0.35, kelvin=6500, size=0.05)
                l.data.color = teal; l['kz_role'] = 'pool_glow'
                n += 1
            s += 2.6
    # the Mirror's teal leak (stand-in; the Mirror place supplies it at export)
    leak = P.light('L_mirror_leak_standin', 'AREA', (95.3, 92.0, FL + 1.3), 6, kelvin=6500, size=3.6, runtime=False,
                   rot=Vector((-1, 0, 0)).to_track_quat('-Z', 'Z').to_euler())
    leak.data.shape = 'RECTANGLE'; leak.data.size = 3.6; leak.data.size_y = 2.6; leak.data.color = (0.12, 0.85, 0.82)
    leak.data.spread = math.radians(35); leak.data.specular_factor = 1.0     # broad wet-vault highlights read as a teal ceiling; keep the leak diffuse
    leak['kz_standin'] = True; leak['kz_note'] = 'fake teal leak from the Mirror; b1_mirror supplies the real light'

    # ---------------------------------------------------------------- fx, probes, cameras
    k = 0
    for path, s0, s1 in ((legA, 1.9, legA.length), (legB, 0.0, LB - 0.9)):
        s = s0
        while s <= s1:
            st = path.at(s)
            P.fx(f'fx_mist_{k:02d}', 'mist', (st[1].x, st[1].y, FL + K.WATER), height=0.4, radius=1.6, density=0.8,
                 hug_walls=True, thin_over_stones=True)
            k += 1; s += 2.2
    for o in dressed:
        if o['kz_asset'] == 'wall_trickle':
            P.fx(f'fx_drips_{o.name}', 'drips', tuple(o.matrix_world @ Vector((0, 0.15, 0.5))), rate=6.0)
    for i, (path, s) in enumerate([(legA, legA.length / 2), (legB, 4.0), (legB, 10.5), (legB, 17.0), (legB, 25.0), (legB, 33.0)]):
        st = path.at(s)
        c = Vector((st[1].x, st[1].y, FL + 1.5))
        P.probe(SID, i, c, (c.x - 4.5, c.y - 4.5, FL - 0.2), (c.x + 4.5, c.y + 4.5, FL + 3.1))
    P.cameras(S)

    # ---------------------------------------------------------------- save, then checks
    path = P.save(SID)
    checks = run_checks(S, legA, legB, shell, water, walk, js, arch, dressed, stones, boulders, figs, nor)
    checks['deviations'] = DEVIATIONS
    checks['placed'] = log['placed']
    os.makedirs(os.path.dirname(CHK), exist_ok=True)
    json.dump(checks, open(CHK, 'w'), indent=1)
    print('SAVED', path)
    print(json.dumps({k: v for k, v in checks.items() if k not in ('placed', 'deviations', 'floating_detail')}, indent=1))


# ================================================================================================ checks
def run_checks(S, legA, legB, shell, water, walk, js, arch, dressed, stones, boulders, figs, nor):
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    render_objs = [o for o in P.coll('kz_render').objects if o.type == 'MESH']
    anim_objs = [o for o in P.coll('kz_anim').objects if o.type == 'MESH']
    def tris(objs):
        t = 0
        for o in objs:
            me = o.evaluated_get(dg).to_mesh(); me.calc_loop_triangles(); t += len(me.loop_triangles); o.evaluated_get(dg).to_mesh_clear()
        return t
    t_render, t_anim, t_water = tris(render_objs), tris(anim_objs), tris([water])
    by_asset = {}
    for o in render_objs + anim_objs:
        a = o.get('kz_asset', 'shell')
        by_asset[a] = by_asset.get(a, 0) + tris([o])
    mats = set(); ids = set()
    for o in render_objs + anim_objs + [water]:
        for m in o.data.materials:
            if m:
                mats.add(m.name); ids.add(m.get('kz_id', m.name.split('~')[0]))
    # in view from the concept camera
    from bpy_extras.object_utils import world_to_camera_view
    cam = bpy.data.objects['cam_concept']; sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    def in_view(o):
        for c in o.bound_box:
            p = world_to_camera_view(sc, cam, o.matrix_world @ Vector(c))
            if p.z > 0 and -0.05 <= p.x <= 1.05 and -0.05 <= p.y <= 1.05:
                return True
        return False
    t_view = tris([o for o in render_objs + anim_objs if o.name.startswith('shell') or in_view(o)])
    out['triangles'] = dict(kz_render=t_render, kz_anim=t_anim, kz_water=t_water, total=t_render + t_anim + t_water,
                            in_concept_view_upper_bound=t_view, budget_corridor=80000, by_asset=by_asset,
                            ok=t_render + t_anim + t_water <= 80000)
    out['materials'] = dict(library_ids=sorted(ids), n_library_ids=len(ids), n_blender_materials=len(mats),
                            budget=40, ok=len(ids) <= 40)

    # ---------------- walk raster + flood fill
    walk_objs = [o for o in P.coll('kz_walk').objects if o.type == 'MESH']
    bw = K.bvh_of(walk_objs)
    x0, y0, x1, y1, cs = 61.5, 67.5, 96.5, 96.5, 0.2
    nx, ny = int((x1 - x0) / cs), int((y1 - y0) / cs)
    Z = {}
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + (i + 0.5) * cs, y0 + (j + 0.5) * cs
            hit = bw.ray_cast(Vector((x, y, FL + 2.0)), Vector((0, 0, -1)), 4.0)
            if hit[0] is not None and abs(hit[1].z) > 0.7:
                Z[(i, j)] = hit[0].z
    def cell(xy):
        i, j = int((xy[0] - x0) / cs), int((xy[1] - y0) / cs)
        if (i, j) in Z:
            return (i, j)
        best = None
        for di in range(-3, 4):
            for dj in range(-3, 4):
                q = (i + di, j + dj)
                if q in Z and (best is None or di * di + dj * dj < best[0]):
                    best = (di * di + dj * dj, q)
        return best[1] if best else None
    def flood(c0):
        seen = {c0}; st = [c0]
        while st:
            c = st.pop()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (c[0] + d[0], c[1] + d[1])
                if q in Z and q not in seen and abs(Z[q] - Z[c]) <= 0.21:
                    seen.add(q); st.append(q)
        return seen
    targets = {p['id']: p['at'] for p in S['portals']}
    lobby = targets['p_b1_lobby_cor']
    targets['p_b1_lobby_cor'] = [lobby[0] - 0.3, lobby[1] + 0.06]          # 0.3 m inside the mouth
    targets['p_b1_cor_mirror'] = [93.4, 92.0]
    targets['hero_view_concept_cam'] = S['cameras']['concept']['pos'][:2]
    targets['hero_arch_approach'] = [92.0, 92.0]
    cells = {k: cell(v) for k, v in targets.items()}
    comp = flood(cells['p_b1_lobby_cor'])
    reach = {k: (c is not None and c in comp) for k, c in cells.items()}
    out['flood_fill'] = dict(cell=cs, walkable_cells=len(Z), reached_from_lobby=len(comp), reach=reach,
                             ok=all(reach.values()),
                             note='junction stretch is a stand-in walk patch (walk_junction_standin, owned by b1_junction_w)')
    json.dump(dict(x0=x0, y0=y0, cs=cs, nx=nx, ny=ny, walk=[[k[0], k[1]] for k in Z], reach=[[k[0], k[1]] for k in comp]),
              open(os.path.join(SCR, 'walk_raster.json'), 'w'))

    # ---------------- clearance along the spine (render geometry, cloth excluded)
    solid = [o for o in render_objs if o.get('kz_asset') != 'stepping_stone']     # stones are walk surfaces
    br = K.bvh_of(solid, dg)
    spans = []; n0 = 0
    for o in solid:
        n1 = n0 + len(o.data.polygons); spans.append((n0, n1, o.name)); n0 = n1
    owner = lambda i: next((nm for a, b, nm in spans if a <= i < b), None)
    sp = [Vector(p) for p in S['spine']]
    pts = []
    for a, b in zip(sp, sp[1:]):
        n = max(1, int((b - a).length / 0.5))
        pts += [a.lerp(b, t / n) for t in range(n)]
    pts.append(sp[-1])
    res = []
    for p in pts:
        if (Vector((p.x, p.y)) - K.JUNC_C).length < K.JUNC_R - 0.05:
            continue
        c = cell((p.x, p.y))
        if c is None:
            res.append(dict(at=[round(p.x, 2), round(p.y, 2)], clear=None)); continue
        z = Z[c]
        hit = br.ray_cast(Vector((p.x, p.y, FL + 0.25)), Vector((0, 0, 1)), 10)
        cl = (hit[3] + 0.25 + (FL - z)) if hit[0] is not None else 99
        res.append(dict(at=[round(p.x, 2), round(p.y, 2)], clear=round(cl, 3), hit=owner(hit[2]) if hit[0] is not None else None))
    mins = [r['clear'] for r in res if r['clear'] is not None]
    out['clearance'] = dict(min=min(mins), points=len(res), fails=[r for r in res if r['clear'] is None or r['clear'] < 2.1],
                            ok=all(r['clear'] is not None and r['clear'] >= 2.1 for r in res),
                            note='mouth noren (cloth, kz_anim) excluded: bottom edge 1.92 m by design (space file 1.95)')

    # ---------------- portals open at floor_z
    pres = {}
    for p in S['portals']:
        at = Vector(p['at']); w = p['width']
        if p['to'] == 'b1_lobby':
            line = Vector((0.196, 0.981)); at = at + Vector((-0.05, 0.01))
        elif p['to'] == 'b1_mirror':
            line = Vector((0, 1))
        else:
            rad = (at - K.JUNC_C).normalized(); line = Vector((-rad.y, rad.x))
        c = cell(at)
        z = Z[c] if c else None
        widths = []
        for hz in (0.3, 1.0, 1.8):
            free = 0
            for sgn in (1, -1):
                o3 = Vector((at.x, at.y, FL + hz)); d3 = Vector((line.x * sgn, line.y * sgn, 0))
                hit = br.ray_cast(o3, d3, 10)
                free += hit[3] if hit[0] is not None else 5.0
            widths.append(round(free, 3))
        up = br.ray_cast(Vector((at.x, at.y, FL + 0.3)), Vector((0, 0, 1)), 10)
        hgt = round(up[3] + 0.3, 3) if up[0] is not None else None
        ok = z is not None and abs(z - FL) <= 0.19 and min(widths) >= w - 0.03
        pres[p['id']] = dict(floor_z=round(z, 3) if z is not None else None, width_req=w, free_width_at_0_3_1_0_1_8=widths,
                             height_at_centre=hgt, height_req=p.get('height'), ok=ok)
    out['portals'] = dict(detail=pres, ok=all(v['ok'] for v in pres.values()),
                          note='height: the corridor is a 3.0 m crown / 2.4 m springing tube, so the 3.0 m portal height '
                               'is met only at the crown; arch clear opening 2.7 m (see deviations)')

    # ---------------- dressing floating / sunk (raycast at each base)
    ground_objs = shell[2:4] + stones
    bg = K.bvh_of(ground_objs, dg)
    fl = []
    for o in dressed + stones + boulders + figs + [arch]:
        a = o.get('kz_asset')
        if a == 'lantern_niche':
            # wall item: ray from 0.6 m in front back to the rock (shell walls) at mid height
            f = o.matrix_world.to_3x3() @ Vector((0, 1, 0))
            org = o.matrix_world @ Vector((0, 0.6, 0.2))
            hit = K.bvh_of([shell[0]]).ray_cast(org, -f, 3)
            dist = hit[3] if hit[0] is not None else None
            gap = None if dist is None else round(dist - (0.6 + 0.125), 3)    # >0: wall behind the back plane
            fl.append(dict(obj=o.name, kind='wall', back_gap=gap, ok=gap is not None and -0.3 <= gap <= 0.02))
            continue
        base = o.matrix_world.translation
        if o in stones:
            g = K.bvh_of([shell[3]])
        elif o in figs:
            g = K.bvh_of([s for s in stones if s.name == o['kz_on']])
        else:
            g = bg
        hit = g.ray_cast(Vector((base.x, base.y, base.z + 0.5)), Vector((0, 0, -1)), 3)
        gz = hit[0].z if hit[0] is not None else None
        if gz is None:
            fl.append(dict(obj=o.name, gap=None, ok=False)); continue
        gap = round(base.z - gz, 3)
        emb = float(o.get('kz_embed', 0.0))
        ok = -emb - 0.02 <= gap <= 0.02
        fl.append(dict(obj=o.name, gap=gap, embed=round(emb, 3), ok=ok))
    out['floating'] = dict(n=len(fl), fails=[f for f in fl if not f['ok']], ok=all(f['ok'] for f in fl))
    out['floating_detail'] = fl
    out['counts'] = dict(stones=len(stones), boulders=len(boulders), figures=len(figs),
                         niches=sum(1 for o in dressed if o['kz_asset'] == 'lantern_niche'),
                         lights=len(P.coll('kz_lights').objects), fx=len(P.coll('kz_fx').objects),
                         probes=len(P.coll('kz_probes').objects))
    out['ok'] = all(out[k]['ok'] for k in ('triangles', 'materials', 'flood_fill', 'clearance', 'portals', 'floating'))
    return out


# ================================================================================================ render
def gpu(sc, samples=128):
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    c = sc.cycles
    c.device = 'GPU'; c.samples = samples; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.02
    c.use_denoising = True; c.denoiser = 'OPTIX'
    c.max_bounces = 8; c.glossy_bounces = 4; c.volume_bounces = 1; c.transparent_max_bounces = 12
    c.caustics_reflective = False; c.caustics_refractive = False; c.sample_clamp_indirect = 6.0
    c.volume_step_rate = 2.0
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
    sc.render.resolution_percentage = 100


def preview_mist():
    """preview-only (not saved): knee-high mist layer over the pool + a faint corridor haze; the runtime mist
    comes from the kz_fx emitters."""
    coll = bpy.data.collections.new('preview_only'); bpy.context.scene.collection.children.link(coll)
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.active_object; box.name = 'preview_mist'
    for c in box.users_collection:
        c.objects.unlink(box)
    coll.objects.link(box)
    box.location = (80.0, 82.5, FL + 0.55); box.scale = (36.0, 27.0, 1.3)
    m = bpy.data.materials.new('preview_mist'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    mr = nt.nodes.new('ShaderNodeMapRange'); nz = nt.nodes.new('ShaderNodeTexNoise'); mul = nt.nodes.new('ShaderNodeMath')
    mul2 = nt.nodes.new('ShaderNodeMath'); add = nt.nodes.new('ShaderNodeMath')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    # generated z 0..1 spans 1.3 m from z -20.1: dense up to ~0.25 m, gone by ~0.75 m
    mr.inputs['From Min'].default_value = 0.12; mr.inputs['From Max'].default_value = 0.6
    mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nz.inputs['Scale'].default_value = 0.9
    nz.inputs['Detail'].default_value = 3.0
    mul.operation = 'MULTIPLY'; nt.links.new(mr.outputs[0], mul.inputs[0]); nt.links.new(nz.outputs['Fac'], mul.inputs[1])
    mul2.operation = 'MULTIPLY'; nt.links.new(mul.outputs[0], mul2.inputs[0]); mul2.inputs[1].default_value = 0.5
    add.operation = 'ADD'; nt.links.new(mul2.outputs[0], add.inputs[0]); add.inputs[1].default_value = 0.0
    nt.links.new(add.outputs[0], pv.inputs['Density'])
    pv.inputs['Color'].default_value = (0.9, 0.92, 0.95, 1); pv.inputs['Anisotropy'].default_value = 0.35
    nt.links.new(pv.outputs[0], o.inputs['Volume'])
    box.data.materials.append(m)
    # stand-in for the lit Mirror dome seen through the arch (preview only): a dim teal emissive card
    bpy.ops.mesh.primitive_plane_add(size=1)
    card = bpy.context.active_object; card.name = 'preview_mirror_glow'
    for c in card.users_collection:
        c.objects.unlink(card)
    coll.objects.link(card)
    card.location = (97.5, 92.0, FL + 1.6); card.rotation_euler = (0, math.radians(90), 0); card.scale = (3.2, 4.4, 1)
    me = bpy.data.materials.new('preview_glow'); me.use_nodes = True
    em = me.node_tree.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.1, 0.75, 0.72, 1)
    em.inputs['Strength'].default_value = 0.12
    me.node_tree.links.new(em.outputs[0], me.node_tree.nodes['Material Output'].inputs['Surface'])
    card.data.materials.append(me)
    # faint haze everywhere (world volume)
    w = bpy.context.scene.world
    nt = w.node_tree
    vs = nt.nodes.new('ShaderNodeVolumeScatter'); vs.inputs['Density'].default_value = 0.008
    vs.inputs['Anisotropy'].default_value = 0.4
    nt.links.new(vs.outputs[0], nt.nodes['World Output'].inputs['Volume'])
    return coll


def render_cam(cam_name, path, res, samples=128):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[cam_name]
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('RENDERED', path)


def render(which):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, '3d', 'places', f'{SID}.blend'))
    sc = bpy.context.scene
    gpu(sc)
    os.makedirs(REN, exist_ok=True)
    for c in ('kz_walk', 'kz_lod'):
        bpy.data.collections[c].hide_render = True
    for o in bpy.data.objects:                      # rigs are not rendered
        if o.type == 'ARMATURE':
            o.hide_render = True
    if which in ('concept', 'all', 'views'):
        preview_mist()
    if which in ('concept', 'all'):
        render_cam('cam_concept', os.path.join(SCR, 'r_concept.jpg'), (1600, 900))
    if which in ('views', 'all'):
        render_cam('cam_entry', os.path.join(SCR, 'r_entry_169.jpg'), (1120, 630), 96)
        render_cam('cam_reveal', os.path.join(SCR, 'r_reveal_169.jpg'), (1120, 630), 96)
        render_cam('cam_entry', os.path.join(SCR, 'r_entry_916.jpg'), (432, 768), 96)
        render_cam('cam_reveal', os.path.join(SCR, 'r_reveal_916.jpg'), (432, 768), 96)
    if which in ('plan', 'all'):
        if 'preview_mist' in bpy.data.objects:
            bpy.data.objects['preview_mist'].hide_render = True
        w = sc.world.node_tree
        for l in list(w.links):
            if l.to_socket.name == 'Volume':
                w.links.remove(l)
        for o in bpy.data.objects:
            if o.get('kz_role') == 'ceiling':
                o.hide_render = True
        sun = bpy.data.lights.new('preview_sun', 'SUN'); sun.energy = 1.2
        so = bpy.data.objects.new('preview_sun', sun); sc.collection.objects.link(so)
        cd = bpy.data.cameras.new('plan'); cd.type = 'ORTHO'; cd.ortho_scale = 35.0
        co = bpy.data.objects.new('cam_plan', cd); sc.collection.objects.link(co)
        co.location = (79.0, 82.0, FL + 30); co.rotation_euler = (0, 0, 0); cd.clip_end = 100
        render_cam('cam_plan', os.path.join(SCR, 'r_plan.jpg'), (1000, 1000), 48)
        json.dump(dict(cx=79.0, cy=82.0, scale=35.0, res=1000), open(os.path.join(SCR, 'plan_cam.json'), 'w'))


if __name__ == '__main__':
    if ARGS and ARGS[0] == 'render':
        render(ARGS[1] if len(ARGS) > 1 else 'all')
    else:
        build()
