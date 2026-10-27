"""Caldera Crown infinity rim (caldera_rim): the whole rim of the 60 x 40 m summit pool - a black wet basalt
vanishing lip on the south (+Y) side where the teal water slides over into the cloud, a craggy natural
rim with a wide deck coping round the north side, a sinter bowl, and 2-4 rock islands for pines.

Concepts: lookbook 11 (hero: teal water sliding over a black wet craggy basalt lip, the lip broken into
rock blocks 1.5-3 m long with water between them, bathers sitting ~0.9-1.0 m deep, a wide wet rock
ledge at the near side, pines on rock outcrops, lanterns on the rim); lookbook 30 (summit plan E2-I3
'Caldera Crown Infinity Pool': irregular lobed pool ~62 x 38 m measured at 20 m grid = 150 px, two rock
islands with pines (F2 ~6 m, G2 ~8 m), timber deck on the north and east edges, the overflow front along
the south edge ~40 m with falls below).
Targets: footprint 60 x 40 m (proxy), lip path 40 m on the south (+Y) side, overflow height 1.08 m
(water level, bed at 0 -> 1.05 m deep), lip nosing radius 0.18 m, vanishing lip 0.5 m wide sitting
0 mm above water (water slides over), back coping 0.7 m wide 0.12 m above water, deck-edge coping
1.6 m wide where decks attach (north-east), islands 5-10 m across rising 1.0-1.45 m above water (lookbook 11 outcrops ~1-2 m).
Proxy 60 x 40 x 1.0 (assets.json): the rim fits at 1.2 m; the islands need 2.55 m -> proposed h 2.6.

Parameters: lip_len 40 m (arc length of the vanishing lip), lip_r 0.18 (nosing radius), overflow
1.08 (water / lip height), islands 2-4 (footprints seeded, or a list of (x, y, rx, ry)), deck (arc in
degrees where the 1.6 m deck coping runs, default north-east 30..110 deg measured from -Y... see code).
Seeds change: outline lobes (harmonic phases), island count / positions / footprints / heights,
lip block rhythm (1.5-3 m blocks), crag noise on the outer face. Variants: 1 (row) + seeds.

Construction: one polar shell (outer foot -> outer face -> lip nosing -> coping -> inner wall -> bed ->
pole). The rim height, coping width and nosing are functions of the angle: inside the lip arc the rim
drops to the overflow height, its outer face becomes the overflow sheet (`waterfall` slot, the shader
side of the sheet) and the lip is chopped into seeded blocks with up to 6 cm level steps so it reads as
the concept's broken black rock edge. Islands: overlapping crag_rock masses (flat tops) rising from
the bed; kz_pine_anchors gives the flat tops for pine_niwaki instances (pines are their own asset).
Underwater lights: small teal emissive pads on the inner wall (lantern_paper teal tint) + kz_lights.

Materials (slots by part): lip basalt_wet 0.98 polish -0.08; coping/deck edge basalt_wet 0.85;
outer face basalt_wet 0.6; overflow sheet waterfall 0.5; bowl sinter 0.6; island rock basalt_wet 0.7;
underwater light lantern_paper tint (0.3, 1.0, 0.9) emissive 0.8.
Water: kz_water_level / kz_water_outline, kz_overflow (lip polyline for fx_falls_sheet).
Animation: shader (overflow sheet: kz_anim). Lighting: lightmap + emissive.
Budget: per 10 m lip 4000/1600/480/100 -> 40 m lip = 16000/6400/1920/400 (BUDGET_SHEET).
"""
import math

import bmesh
from mathutils import Matrix, Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_plunge_basin as P
from kzgeo_falls_lip_rock import smoothstep

ASSET = 'caldera_rim'
FEATURES = ['black wet basalt vanishing lip with overflow sheet', 'teal pool (sinter bowl)', 'rock islands with pine anchors',
            'craggy natural rim with deck-edge coping']
PROXY_SHEET = dict(w=60.0, d=40.0, h=2.6)            # proposed: islands rise 1.0-1.45 m above water -> 2.55 m
BUDGET_SHEET = [16000, 6400, 1920, 400]              # 4 x the per-10 m budget (40 m lip)


def adiff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def layout(seed, lip_len=40.0, lip_r=0.18, overflow=1.08, islands=None, deck=(200.0, 290.0)):
    g = C.rng(seed, 'outline')
    L = dict(a=29.6, b=19.6, lip_len=lip_len, lip_r=lip_r, ov=overflow, deck=deck)
    L['harm'] = [(k, g.uniform(0, 6.283), amp) for k, amp in ((2, 0.035), (3, 0.05), (4, 0.03), (5, 0.025), (7, 0.012))]
    L['off'] = Vector((g.uniform(0, 90), g.uniform(0, 90), g.uniform(0, 90)))
    gb = C.rng(seed, 'blocks')
    L['blocks'] = [(gb.uniform(1.5, 3.0), gb.uniform(-0.06, 0.06)) for _ in range(40)]
    gi = C.rng(seed, 'islands')
    if islands is None:
        n = gi.choice([2, 2, 3, 4])
        cand = [(-6.0, -6.0), (6.0, -8.0), (-15.0, 2.0), (14.0, 1.0), (0.0, 4.0)]
        gi.shuffle(cand)
        islands = []
        for x, y in cand[:n]:
            islands.append((x + gi.uniform(-2.5, 2.5), y + gi.uniform(-2, 2), gi.uniform(2.6, 4.8), gi.uniform(2.2, 3.6)))
    L['islands'] = islands
    L['isl_h'] = [overflow + gi.uniform(1.0, 1.45) for _ in islands]
    return L


def outline_fn(L):
    a, b = L['a'], L['b']

    def f(th):
        c, s = math.cos(th), math.sin(th)
        R = 1.0 / math.sqrt((c / a) ** 2 + (s / b) ** 2)
        k = 1 + sum(amp * math.sin(m * th + ph) for m, ph, amp in L['harm'])
        # the overflow front (+Y) is flattened into a long gentle arc
        k *= 1 - 0.06 * max(0.0, s) ** 3
        return R * k * c, R * k * s
    return f


def build(lod=0, seed=1, lip_len=40.0, lip_r=0.18, overflow=1.08, islands=None, deck=(200.0, 290.0)):
    L = layout(seed, lip_len, lip_r, overflow, islands, deck)
    f = outline_fn(L)
    mb = genlib.MeshBuilder()
    m_lip = mb.slot('basalt_wet', wetness=0.98, roughness_offset=-0.08)
    m_cope = mb.slot('basalt_wet', wetness=0.85)
    m_face = mb.slot('basalt_wet', wetness=0.6)
    m_sheet = mb.slot('waterfall', emissive_level=0.5)
    m_bowl = mb.slot('sinter', wetness=0.6)
    m_isl = mb.slot('basalt_wet', wetness=0.7)
    m_led = mb.slot('lantern_paper', tint=(0.3, 1.0, 0.9), emissive_level=0.8)
    ov = L['ov']
    # lip arc: centred on +Y (th = pi/2), half-angle from the arc length along the outline
    samples = 720
    ths = [2 * math.pi * k / samples for k in range(samples)]
    pts = [f(t) for t in ths]
    seg = [math.hypot(pts[(k + 1) % samples][0] - pts[k][0], pts[(k + 1) % samples][1] - pts[k][1]) for k in range(samples)]
    k0 = samples // 4
    acc, k = 0.0, 0
    while acc < L['lip_len'] / 2 and k < samples // 2:
        acc += seg[(k0 + k) % samples]; k += 1
    half = 2 * math.pi * k / samples
    L['half'] = half

    def lipw(th):          # 1 inside the vanishing-lip arc, smooth 2 m ends
        d = abs(adiff(th, math.pi / 2))
        e = 2.0 / 25.0
        return 1 - smoothstep(half - e, half + e, d)
    # lip blocks: arc position -> small level step (broken rock edge)
    edges = []
    s = -L['lip_len'] / 2
    for bl, dz in L['blocks']:
        edges.append((s, dz)); s += bl
        if s > L['lip_len'] / 2:
            break

    def block_dz(th):
        sarc = adiff(th, math.pi / 2) / half * L['lip_len'] / 2
        dz = 0.0
        for s0, d in edges:
            if sarc >= s0:
                dz = d
        return dz if lod <= 1 else 0.0

    def deckw(th):
        a0, a1 = math.radians(L['deck'][0]), math.radians(L['deck'][1])
        t = th % (2 * math.pi)
        return smoothstep(a0 - 0.08, a0 + 0.04, t) * (1 - smoothstep(a1 - 0.04, a1 + 0.08, t))

    def cope_w(th):
        return 0.7 + 0.9 * deckw(th) - 0.2 * lipw(th)

    def ztop(th):
        lw = lipw(th)
        return (ov + 0.12) * (1 - lw) + (ov + block_dz(th) * 0.5) * lw

    nr = L['lip_r']
    rows_all = {
        0: [(1, -0.5, 0.0, 'foot'), (1, -0.32, lambda t: 0.35 * ztop(t), 'out'), (1, -0.16, lambda t: 0.7 * ztop(t), 'out'),
            (1, -0.05, lambda t: ztop(t) - nr, 'out'), (1, lambda t: -0.05 + nr * 0.3, lambda t: ztop(t) - nr * 0.3, 'nose'),
            (1, lambda t: nr * 0.5, ztop, 'top'), (1, cope_w, ztop, 'top'),
            (1, lambda t: cope_w(t) + 0.06, lambda t: ztop(t) - 0.07, 'in'), (1, lambda t: cope_w(t) + 0.16, lambda t: 0.5 * ov, 'in'),
            (1, lambda t: cope_w(t) + 0.6, 0.05, 'bed'), (0.93, 0.0, 0.02, 'bed'), (0.6, 0.0, 0.0, 'bed'), (0.3, 0.0, 0.0, 'bed'),
            (0, 0, 0.0, 'bed')],
        1: [(1, -0.5, 0.0, 'foot'), (1, -0.25, lambda t: 0.5 * ztop(t), 'out'), (1, -0.05, lambda t: ztop(t) - nr, 'out'),
            (1, lambda t: nr * 0.5, ztop, 'top'), (1, cope_w, ztop, 'top'), (1, lambda t: cope_w(t) + 0.15, lambda t: 0.5 * ov, 'in'),
            (1, lambda t: cope_w(t) + 0.6, 0.05, 'bed'), (0.5, 0.0, 0.0, 'bed'), (0, 0, 0.0, 'bed')],
        2: [(1, -0.5, 0.0, 'foot'), (1, -0.05, lambda t: ztop(t) - nr, 'out'), (1, cope_w, ztop, 'top'),
            (1, lambda t: cope_w(t) + 0.4, 0.3, 'in'), (0.6, 0.0, 0.0, 'bed'), (0, 0, 0.0, 'bed')],
        3: [(1, -0.5, 0.0, 'foot'), (1, 0.0, ztop, 'top'), (1, cope_w, ztop, 'top'), (0, 0, 0.0, 'bed')],
    }
    rows = rows_all[lod]
    N = C.lod_pick(lod, 400, 300, 140, 28)

    def disp(th, j, tag, p):
        if tag not in ('out', 'foot'):
            return Vector()
        lw = lipw(th)
        ux, uy = math.cos(th), math.sin(th)
        amp = (0.22 * (1 - lw) + 0.06 * lw) * (lod <= 2)
        o = amp * noise.noise(Vector((p.x * 0.35, p.y * 0.35, p.z * 0.8)) + L['off'])
        return Vector((ux * o, uy * o, 0.0))

    def mi_fn(j, t0, t1, th):
        lw = lipw(th) > 0.5
        if t0 in ('foot', 'out'):
            if t1 in ('nose', 'top') and lw:
                return m_lip
            return m_sheet if lw else m_face
        if t0 == 'nose':
            return m_lip if lw else m_cope
        if t0 == 'top':
            if t1 == 'top':
                return m_lip if lw else m_cope
            return m_bowl if lw else m_cope
        return m_bowl
    P.polar_basin(mb, f, N, rows, mi_fn, disp=disp, phase=math.pi / N)
    # ---------------------------------------------------------------- islands (crag masses from the bed)
    anchors = []
    for i, ((x, y, rx, ry), ztop_i) in enumerate(zip(L['islands'], L['isl_h'])):
        r = C.rng(seed, f'island{i}')
        nrock = C.lod_pick(lod, 3, 3, 2, 1)
        parts = [(0.0, 0.0, 1.0, 1.0, ztop_i)]
        for k in range(2):
            a = r.uniform(0, 6.283)
            parts.append((math.cos(a) * rx * 0.55, math.sin(a) * ry * 0.55, r.uniform(0.45, 0.6), r.uniform(0.45, 0.6),
                          ztop_i - r.uniform(0.12, 0.3)))
        for px, py, sx, sy, zt in parts[:nrock]:
            M = Matrix.Translation((x + px, y + py, 0.0)) @ Matrix.Rotation(r.uniform(0, 6.283), 4, 'Z')
            C.crag_rock(mb, M, rx * sx, ry * sy, 0.0, zt, m_isl, r, nside=C.lod_pick(lod, 14, 9, 7, 5),
                        bands=C.lod_pick(lod, 3, 2, 1, 1), crag=0.14)
        anchors.append(dict(pos=[x, y, ztop_i], r=round(min(rx, ry) * 0.6, 2), pines=1 if rx * ry < 9 else 2))
    # ---------------------------------------------------------------- underwater lights on the inner wall
    lights = []
    nled = 18
    for k in range(nled):
        th = 2 * math.pi * (k + 0.5) / nled
        x, y = f(th); R = math.hypot(x, y); ux, uy = x / R, y / R
        rr = R - cope_w(th) - 0.18
        c = Vector((ux * rr, uy * rr, 0.55 * ov))
        if lod <= 2:
            t = Vector((-uy, ux, 0.0))
            n = Vector((-ux, -uy, 0.0))
            hw = 0.16
            bm = mb.bm
            q = [bm.verts.new(c - t * hw - Vector((0, 0, 0.08)) + n * 0.03), bm.verts.new(c + t * hw - Vector((0, 0, 0.08)) + n * 0.03),
                 bm.verts.new(c + t * hw + Vector((0, 0, 0.08)) + n * 0.03), bm.verts.new(c - t * hw + Vector((0, 0, 0.08)) + n * 0.03)]
            fc = bm.faces.new(q); fc.material_index = m_led
        lights.append(C.light_entry(c, color_k=6500, watts=40, underwater=True))
    bmesh.ops.recalc_face_normals(mb.bm, faces=mb.bm.faces[:])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    sh = Vector((dx, dy, dz))
    for e in lights:
        e['pos'] = [round(e['pos'][0] + dx, 3), round(e['pos'][1] + dy, 3), round(e['pos'][2] + dz, 3)]
    for a in anchors:
        a['pos'] = [round(a['pos'][0] + dx, 3), round(a['pos'][1] + dy, 3), round(a['pos'][2] + dz, 3)]
    ol = []
    for k in range(96):
        th = 2 * math.pi * k / 96
        x, y = f(th); R = math.hypot(x, y); r_ = R - cope_w(th) + 0.02
        ol.append((x / R * r_ + dx, y / R * r_ + dy))
    lip = []
    for k in range(21):
        th = math.pi / 2 - half + 2 * half * k / 20
        x, y = f(th); R = math.hypot(x, y)
        lip.append([round(x / R * (R + 0.05) + dx, 3), round(y / R * (R + 0.05) + dy, 3), round(ztop(th) + 0.01 + dz, 3)])
    C.water_props(o, level_z=ov + 0.005 + dz, outline_xy=ol,
                  kz_overflow=dict(lip=lip, length=L['lip_len'], fx='fx_falls_sheet', dir='outward', to='cliff (place model)'))
    C.set_json_props(o, kz_lights=lights, kz_pine_anchors=anchors,
                     kz_anim=dict(type='shader', what='overflow sheet on the outer lip face', slots=[m_sheet]),
                     kz_params=dict(lip_len=L['lip_len'], lip_r=L['lip_r'], overflow=ov, islands=len(L['islands']),
                                    deck=list(L['deck'])))
    return o
