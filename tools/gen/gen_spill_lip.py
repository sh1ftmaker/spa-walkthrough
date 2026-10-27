"""Polished basalt spill weir: a polished black lip with a sheet of water sliding over it, lit from below,
flanked by a pair of lantern posts (toro).

Identifying features kept at every LOD: the long polished lip (obsidian round nose) with the water
sheet over it; the warm glow under the lip and at the foot of the sheet; the two flanking lantern posts.

Concepts: refs/gen/sheet-mod-water.png #3 Basalt Spill Weir ("width 4 m"; front view 95 px/m: rock
pillars ~0.65 m wide with iron lanterns on top, the curtain ~2 m wide, a stone kerb at the foot; side
view: the lip projects ~0.15 m and the sheet arcs clear before falling), lookbook 05 (mist corridor:
low weirs and spills between pools, lit warm from below), 25 (water journey). The row's typical size
is the low weir: 4 x 1 x 0.4 m with a 0.3 m drop (the sheet's 2 m drop is the `drop` parameter).
Targets: w 4.0, d 0.95, lip top 0.38 m (drop 0.30 + 0.08), lip radius 0.05-0.10, nose projects
0.07 m over a 0.07 m undercut that hides the light strip, water bed 35 mm under the lip, sheet 15 mm
thick-equivalent offset over the nose, arcing ~0.12 m clear at a 0.3 m drop. Posts: dressed 0.24 m
square basalt post 0.5 m + lantern 0.17 x 0.28 (seed 1) or a 0.42 m craggy pillar 0.6 m + lantern
(seed 2); top of lantern ~0.92 m.
Proxy (3d/assets.json) 4.0 x 1.0 x 0.4: the flanking toro the row names as identifying cannot fit in
0.4 m; built to 0.92 m, proposed proxy 4.0 x 1.0 x 0.95 (posts=False builds 0.40 m).

Parameters:
  w            1-4 m      overall width incl. posts (default 4.0)
  drop         0.3-20 m   lip height above the receiving water (default 0.30-0.34)
  lip_r        0.04-0.12  nose radius (seeded 0.05-0.10)
  posts        bool       flank posts on/off (default on)
  post_style   'dressed' | 'crag'  (cycles with the seed)
  under_light  bool       emissive strips + kz_lights (default on)
Seeds change: post style (dressed post / crag pillar), lip radius, plan bow (seed 2 bows 6-9 cm
forward), drop, post height.
Animation: shader - the `waterfall` slot (sheet) scrolls along UV0 (metric, along the flow); kz_anim.
Materials (slots by part): lip/nose = obsidian; bed = basalt_wet 0.98; body = basalt_wet 0.6; posts =
basalt_wet 0.55; lantern frame = iron; lantern + light strips = lantern_andon; sheet = waterfall.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C
import kzgeo_falls_lip_rock as K

ASSET = 'spill_lip'
FEATURES = ['polished black round lip with a water sheet over it', 'warm glow under the lip', 'two flanking lantern posts']
POSTS = ['dressed', 'crag']


def layout(seed, w=None, drop=None, lip_r=None, posts=None, post_style=None, under_light=None):
    g = C.rng(seed, 'dims')
    L = {}
    L['w'] = w if w is not None else 4.0
    L['drop'] = drop if drop is not None else g.uniform(0.30, 0.34)
    L['rl'] = lip_r if lip_r is not None else g.uniform(0.05, 0.10)
    L['posts'] = True if posts is None else posts
    L['ps'] = post_style or C.cycle(seed, POSTS)
    L['light'] = True if under_light is None else under_light
    L['pw'] = (0.24 if L['ps'] == 'dressed' else 0.42) if L['posts'] else 0.0
    L['ph'] = (g.uniform(0.48, 0.52) if L['ps'] == 'dressed' else g.uniform(0.56, 0.62))
    L['bow'] = 0.0 if L['ps'] == 'dressed' else g.uniform(0.06, 0.09)
    L['zt'] = L['drop'] + 0.08
    L['zb'] = L['zt'] - 0.035
    L['yn'] = 0.22
    L['yb'] = -0.40
    L['und'] = 0.07
    L['clear'] = L['w'] - 2 * L['pw'] + (0.08 if L['posts'] else 0.0)
    gn = C.rng(seed, 'noise')
    L['off'] = Vector((gn.uniform(0, 90), gn.uniform(0, 90), gn.uniform(0, 90)))
    return L


def bow(L, x):
    return L['bow'] * (1 - (2 * x / max(L['clear'], 0.1)) ** 2)


def profile(L, lod):
    """[(y, z, kind)] CCW seen from +X, open at the bottom"""
    yn, zt, zb, rl, und, yb = L['yn'], L['zt'], L['zb'], L['rl'], L['und'], L['yb']
    na = C.lod_pick(lod, 7, 3, 1, 1)
    yface = yn - rl - und
    P = [(yface + 0.03, 0.0, 'face')]
    if lod < 3:
        P.append((yface + 0.01, 0.5 * (zt - 2 * rl), 'face'))
    if lod < 3:
        P.append((yface, zt - 2 * rl - 0.03, 'under'))
    else:
        P.append((yface, zt - 2 * rl, 'under'))
    if lod < 3:
        P.append((yn - rl - 0.01, zt - 2 * rl, 'nose'))
    for k in range(na + 1):
        a = -math.pi / 2 + math.pi * (k + (1 if lod == 3 else 0)) / (na + 1)
        P.append((yn - rl + rl * math.cos(a), zt - rl + rl * math.sin(a), 'nose'))
    P.append((yn - rl, zt, 'nose'))
    if lod < 3:
        P.append((yn - rl - 0.08, zt - 0.004, 'top'))
        P.append((yn - rl - 0.2, zb, 'bed'))
    P.append((yb + 0.12, zb, 'bed'))
    if lod < 2:
        P.append((yb + 0.07, zt + 0.02, 'back'))
    P.append((yb, zt + 0.02, 'back'))
    if lod < 2:
        P.append((yb - 0.01, 0.5 * zt, 'back'))
    P.append((yb, 0.0, 'back'))
    return P


def sheet_path(L, lod):
    """(y, z) along the flow: bed -> over the nose -> free fall to the receiving water"""
    yn, zt, zb, rl, yb = L['yn'], L['zt'], L['zb'], L['rl'], L['yb']
    t = 0.014
    P = []
    P.append((yn - rl - 0.14, zb + t))
    na = C.lod_pick(lod, 4, 2, 1, 0)
    for k in range(na + 1):
        a = math.pi / 2 - (math.pi / 2) * k / max(na, 1) if na else 0.0
        P.append((yn - rl + (rl + t) * math.cos(a), zt - rl + (rl + t) * math.sin(a)))
    v = 0.75
    h = zt - rl - 0.01
    T = math.sqrt(2 * h / 9.81)
    nf = C.lod_pick(lod, 9, 4, 2, 1)
    for k in range(1, nf + 1):
        tt = T * k / nf
        P.append((yn + t + v * tt, zt - rl - 0.5 * 9.81 * tt * tt))
    return P


def build(lod=0, seed=1, w=None, drop=None, lip_r=None, posts=None, post_style=None, under_light=None):
    L = layout(seed, w, drop, lip_r, posts, post_style, under_light)
    mb = genlib.MeshBuilder()
    m_lip = mb.slot('obsidian')
    m_bed = mb.slot('basalt_wet', wetness=0.98, roughness_offset=-0.06)
    m_body = mb.slot('basalt_wet', wetness=0.6)
    m_post = mb.slot('basalt_wet', wetness=0.55)
    m_iron = mb.slot('iron')
    m_glow = mb.slot('lantern_andon', emissive_level=0.9)
    m_water = mb.slot('waterfall')
    cl = L['clear']
    nx = C.lod_pick(lod, 13, 7, 3 if L['bow'] else 2, 2)
    xs = [-cl / 2 + cl * i / (nx - 1) for i in range(nx)]
    pr = profile(L, lod)
    kinds = [k for _, _, k in pr]
    rows = []
    for x in xs:
        row = []
        for (y, z, kind) in pr:
            p = Vector((x, y + bow(L, x), z))
            if lod == 0 and kind in ('face', 'back') and z > 0.01:
                p.y += 0.008 * noise.noise(p * 6 + L['off']) * (1 if kind == 'face' else -1)
            row.append(p)
        rows.append(row)

    def mi_fn(i, j, c):
        k0, k1 = kinds[j], kinds[j + 1]
        if k0 in ('nose',) or (k0 == 'under' and k1 == 'nose') or (k0 == 'nose' and k1 == 'top'):
            return m_lip
        if k0 == 'top' or k0 == 'bed':
            return m_bed
        return m_body
    V, faces = K.grid(mb, rows, mi_fn)
    for end, sgn in ((V[0], -1), (V[-1], 1)):
        cy = sum(v.co.y for v in end) / len(end); cz = sum(v.co.z for v in end) / len(end)
        if lod < 3:
            faces += K.fan_cap(mb, end, (end[0].co.x + sgn * 0.005, cy, cz), m_body)
        else:
            f = mb.bm.faces.new(end); f.material_index = m_body; faces.append(f)

    # water sheet over the lip (single-sided ribbon, render double-sided)
    sp = sheet_path(L, lod)
    inset = 0.03 if L['posts'] else 0.06
    nxs = C.lod_pick(lod, 9, 5, 3 if L['bow'] else 2, 2)
    sx = [-(cl / 2 - inset) + (cl - 2 * inset) * i / (nxs - 1) for i in range(nxs)]
    srows = [[Vector((x, y + bow(L, x), z)) for y, z in sp] for x in sx]
    K.grid(mb, srows, lambda i, j, c: m_water)

    # under-light strips: one under the nose (lights the sheet), one at the foot of the face
    lights = []
    if L['light'] and lod < 3:
        yface = L['yn'] - L['rl'] - L['und']
        zs = L['zt'] - 2 * L['rl'] - 0.03
        mb.box((0, yface + 0.02 + L['bow'] * 0.6, zs - 0.012), (cl - 0.12, 0.03, 0.022), m_glow)
        if lod < 2:
            mb.box((0, yface + 0.05 + L['bow'] * 0.6, 0.016), (cl - 0.12, 0.035, 0.03), m_glow)
        for k in range(3):
            x = -cl / 3 + cl / 3 * k
            lights.append(C.light_entry((x, yface + 0.05 + bow(L, x), zs - 0.03), color_k=2400, watts=round(350 / 3), role='under-lip'))

    # flanking posts with lanterns
    if L['posts']:
        iron_paper = dict(iron=m_iron, paper=m_glow)
        for sgn in (-1, 1):
            px, py = sgn * (L['w'] / 2 - L['pw'] / 2), -0.08
            if L['ps'] == 'dressed':
                if lod == 3:
                    open_box(mb, px, py, L['pw'], L['pw'], L['ph'], m_post)
                else:
                    C.board(mb, (px, py, 0.04), (L['pw'] + 0.1, L['pw'] + 0.1, 0.08), m_post, bevel=C.lod_pick(lod, 0.012, 0.008, 0.0), segs=1)
                    if lod < 2:
                        C.chamfered_bar(mb, (px, py, 0.08 + (L['ph'] - 0.08) / 2), (L['pw'], L['pw'], L['ph'] - 0.08), m_post, ch=0.02)
                    else:
                        mb.box((px, py, 0.08 + (L['ph'] - 0.08) / 2), (L['pw'], L['pw'], L['ph'] - 0.08), m_post)
                top = L['ph']
            else:
                g = C.rng(seed, f'pillar{sgn}')
                if lod == 3:
                    open_box(mb, px, py, L['pw'] * 0.9, L['pw'] * 0.85, L['ph'], m_post)
                else:
                    C.crag_rock(mb, C.frame((px, py, 0), (0, 1, 0)), L['pw'] / 2, L['pw'] * 0.45, 0.0, L['ph'], m_post, g,
                                nside=C.lod_pick(lod, 8, 6, 5), bands=C.lod_pick(lod, 3, 2, 1), crag=0.1, top_inset=0.86)
                top = L['ph'] - 0.01
            if lod == 3:
                bm = mb.bm
                s = 0.17
                q = [bm.verts.new((px - s / 2, py + L['pw'] / 2 + 0.002, top)), bm.verts.new((px + s / 2, py + L['pw'] / 2 + 0.002, top)),
                     bm.verts.new((px + s / 2, py + L['pw'] / 2 + 0.002, top + 0.28)), bm.verts.new((px - s / 2, py + L['pw'] / 2 + 0.002, top + 0.28))]
                f = bm.faces.new(q); f.material_index = m_glow
                lc = Vector((px, py, top + 0.14))
            else:
                lc = C.lantern_head(mb, (px, py, top), iron_paper, lod, size=0.17, height=0.28, roof='hip')
            lights.append(C.light_entry(lc, color_k=2200, watts=15, role='toro'))
    import bmesh
    bmesh.ops.recalc_face_normals(mb.bm, faces=[f for f in faces if f.is_valid])
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    for l_ in lights:
        l_['pos'] = [round(l_['pos'][0] + dx, 4), round(l_['pos'][1] + dy, 4), round(l_['pos'][2] + dz, 4)]
    lip = [[round(x + dx, 3), round(L['yn'] + bow(L, x) + dy, 3), round(L['zt'] - L['rl'] + dz, 3)] for x in sx]
    C.set_json_props(o, kz_lights=lights,
                     kz_anim=dict(type='shader', what='sheet flow over the lip', slot='waterfall', uv='UVMap', speed_mps=0.75),
                     kz_falls=dict(lip=lip, width=round(cl - 2 * inset, 3), drop=round(L['drop'], 3), dir=[0, 1, 0],
                                   fx='fx_falls_sheet (only when drop > 1 m; the sheet mesh covers the low weir)'),
                     kz_double_sided=json_list(['waterfall']),
                     kz_params=dict(w=L['w'], drop=round(L['drop'], 3), lip_r=round(L['rl'], 3), posts=L['posts'],
                                    post_style=L['ps'], under_light=L['light']))
    return o


def json_list(v):
    return v


def open_box(mb, x, y, sx, sy, h, mi):
    """box without a bottom face (sits on the ground): 10 tris"""
    bm = mb.bm
    b = [bm.verts.new((x + a * sx / 2, y + c * sy / 2, 0.0)) for a, c in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    t = [bm.verts.new((v.co.x, v.co.y, h)) for v in b]
    fs = [bm.faces.new(t)] + [bm.faces.new((b[i], b[(i + 1) % 4], t[(i + 1) % 4], t[i])) for i in range(4)]
    for f in fs:
        f.material_index = mi
    return fs
