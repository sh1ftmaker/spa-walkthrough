"""Staff figure: restaurant server, bath attendant, ramen chef. Same base body, rig and weights as guest_figure
(kzgeo_guest_figure); work clothing and props from kzgeo_staff_figure.

Targets (refs/gen/sheet-vs-people.png panels 5-7, 1 m bar = 248 px; lookbook 09 chef, 04 counter attendant):
  * heights (sheet labels): server 1.68 (woman), attendant 1.70 (man), chef 1.75 (man).
  * samue: crossed-collar jacket to the upper thigh (hem ~0.42 H), sleeves to 2/3 of the forearm (attendant: rolled,
    light cuff), obi 0.06-0.09 m; trousers cropped mid-calf (server), gathered at the ankle (attendant) or over
    white leggings (chef). Geta for everyone.
  * server: black samue, tan obi, indigo maekake apron obi-to-knee (0.42 m wide) with the mountain mark and two
    lettering bars, round tray D 0.34 with a sake flask and two cups held at the waist (SERVING).
  * attendant: brown samue, indigo obi, three folded cream towels carried in front (CARRYING TOWELS).
  * chef: black samue (lookbook 09) or white (sheet 7), white apron, white hachimaki with a dark crest disc, pulling
    noodles from a tebo basket (NOODLE PREPARATION).
  Front width 0.55-0.62 m, depth with the apron 0.3-0.35 m; the working poses reach 0.5-0.6 m forward
  (proxy 0.5 x 0.4 x 1.75 holds the bind pose; see report).

Parameters: role server|attendant|chef; body woman|man; height 1.55-1.85; prop tray|noodle_basket|towel_stack|none;
  anim idle|serve|carry|noodle_pull|walk (stored pose; default = the role's working pose); outfit samue|yukata
  (attendant only); chef_colour black|white; build 0-1; skin 0-2.
Seeds: 1 server woman, 2 attendant man, 3 chef man (black), 4 server man, 5 attendant woman in an indigo yukata
  with a linen apron, 6 chef man (white) ... then seeded picks. Height, build, skin from their own streams.
Rig: 24 bones; props are rigid on prop_R / prop_L; obj['kz_anim'] clips idle, walk, serve, carry, noodle_pull.
Budget 3500 / 1400 / 450 / impostor (LOD3 ~200-260 tri skinned silhouette).
"""
import math

from mathutils import Matrix, Vector

import genlib
import kzgeo_common as C
import kzgeo_guest_figure as KG
import kzgeo_staff_figure as KS

ASSET = 'staff_figure'
FEATURES = ['human silhouette', 'dark samue or indigo yukata', 'apron or headband', 'role prop (tray / towels / noodles)']
PARAMS = dict(role=('server', 'attendant', 'chef'), body=('woman', 'man'), height=(1.55, 1.85),
              prop=('tray', 'noodle_basket', 'towel_stack', 'none'), anim=('idle', 'serve', 'carry', 'noodle_pull', 'walk'),
              outfit=('samue', 'yukata'), chef_colour=('black', 'white'))
TABLE = [('server', 'woman', 'samue', 'black'), ('attendant', 'man', 'samue', 'black'), ('chef', 'man', 'samue', 'black'),
         ('server', 'man', 'samue', 'black'), ('attendant', 'woman', 'yukata', 'black'), ('chef', 'man', 'samue', 'white')]
SKIN = [(0.86, 0.6, 0.46), (0.76, 0.5, 0.37), (0.92, 0.7, 0.56)]
ROLE_H = dict(server=1.68, attendant=1.70, chef=1.75)
ROLE_PROP = dict(server='tray', attendant='towel_stack', chef='noodle_basket')
ROLE_ANIM = dict(server='serve', attendant='carry', chef='noodle_pull')


def params_for(seed, **kw):
    role, body, outfit, colour = C.cycle(seed, TABLE)
    if seed > len(TABLE):
        body = C.pick(seed, 'body', ['woman', 'man'])
    role = kw.get('role', role)
    body = kw.get('body', body)
    H0 = ROLE_H[role] if (role != 'server' or body == 'woman') else 1.74
    if body == 'woman' and role != 'server':
        H0 = 1.64
    H = kw.get('height', round(min(1.85, max(1.55, H0 * C.rng(seed, 'height').uniform(0.97, 1.03))), 3))
    prop = kw.get('prop', ROLE_PROP[role])
    anim = kw.get('anim', ROLE_ANIM[role] if prop != 'none' else 'idle')
    return dict(role=role, body=body, height=H, prop=prop, anim=anim, outfit=kw.get('outfit', outfit if role == 'attendant' else 'samue'),
                chef_colour=kw.get('chef_colour', colour), build=kw.get('build', round(C.rng(seed, 'build').uniform(0.2, 0.8), 3)),
                skin=kw.get('skin', C.pick(seed, 'skin', [0, 1, 2])),
                hair=kw.get('hair', {'woman': 'bun', 'man': 'topknot' if role != 'chef' else 'short'}[body]))


def _slots(F, P):
    m = {}
    m['skin'] = F.slot('ceramic', tint=SKIN[P['skin']], roughness_offset=0.38)
    m['hair'] = F.slot('lacquer_black', roughness_offset=0.15)
    role = P['role']
    if role == 'attendant' and P['outfit'] == 'yukata':
        m['jacket'] = F.slot('noren'); m['pants'] = m['jacket']
        m['obi'] = F.slot('linen', tint=(0.74, 0.56, 0.34)); m['apron'] = F.slot('linen')
    elif role == 'attendant':
        m['jacket'] = F.slot('linen', tint=(0.36, 0.23, 0.14)); m['pants'] = m['jacket']
        m['obi'] = F.slot('noren'); m['apron'] = None
    elif role == 'chef' and P['chef_colour'] == 'white':
        m['jacket'] = F.slot('linen'); m['pants'] = m['jacket']
        m['obi'] = F.slot('noren', variant='black'); m['apron'] = F.slot('linen', tint=(1.0, 0.97, 0.92))
    elif role == 'chef':
        m['jacket'] = F.slot('noren', variant='black'); m['pants'] = m['jacket']
        m['obi'] = F.slot('noren'); m['apron'] = F.slot('linen', tint=(1.0, 0.97, 0.92))
    else:
        m['jacket'] = F.slot('noren', variant='black'); m['pants'] = m['jacket']
        m['obi'] = F.slot('linen', tint=(0.74, 0.56, 0.34)); m['apron'] = F.slot('noren')
    m['cuff'] = F.slot('linen')
    m['mark'] = F.slot('linen', tint=(0.85, 0.82, 0.74))
    m['band'] = F.slot('linen', tint=(1.0, 0.97, 0.92))
    m['crest'] = F.slot('noren', variant='black')
    m['wood'] = F.slot('hinoki', variant='natural')
    m['strap'] = F.slot('noren', variant='black')
    m['tray'] = F.slot('hinoki', variant='walnut')
    m['ceramic'] = F.slot('ceramic', variant='tenmoku')
    m['towel'] = F.slot('terry', variant='cream')
    m['basket'] = F.slot('bamboo')
    m['handle'] = F.slot('hinoki', variant='stained')
    m['noodle'] = F.slot('linen', tint=(0.95, 0.82, 0.52))
    m['tie'] = F.slot('noren', variant='vermilion')
    return m


def _pose(P, sk):
    a = P['anim']
    extra = {}
    if a == 'serve':
        extra = dict(upperarm_L=KG.rx(22) @ KG.ry(-5), upperarm_R=KG.rx(22) @ KG.ry(5), forearm_L=KG.rx(66), forearm_R=KG.rx(66),
                     hand_L=KG.rx(-12), hand_R=KG.rx(-12))
    elif a == 'carry':
        extra = dict(upperarm_L=KG.rx(16) @ KG.ry(-4), upperarm_R=KG.rx(16) @ KG.ry(4), forearm_L=KG.rx(70), forearm_R=KG.rx(70),
                     spine=KG.rx(3))
    elif a == 'noodle_pull':
        extra = dict(upperarm_R=KG.rx(62) @ KG.ry(12), forearm_R=KG.rx(62), upperarm_L=KG.rx(26) @ KG.ry(-4), forearm_L=KG.rx(58),
                     spine=KG.rx(-6), neck=KG.rx(-8))
    base = 'walking' if a == 'walk' else 'standing'
    rot, root_rot = KG.standard_pose(base, sk, extra)
    return rot, root_rot


def _props(F, P, m, rot, root_rot):
    """build the prop(s) at their bind placement; return prop_place {bone: (rest_M, posed_M)}"""
    sk = F.sk
    S = KG.pose_matrices(sk, rot, Vector(), root_rot)
    gR, gL = sk.heads['prop_R'], sk.heads['prop_L']
    pR, pL = S['hand_R'] @ gR, S['hand_L'] @ gL
    working = P['anim'] in ('serve', 'carry', 'noodle_pull')
    place = {}
    T = Matrix.Translation
    roty = Matrix.Rotation(math.radians(-90), 4, 'Y')
    if P['prop'] == 'tray':
        rest = T(gR + Vector((0.035, 0.0, -0.15))) @ roty
        posed = T((pL + pR) / 2 + Vector((0, 0.03, 0.012))) if working else S['hand_R'] @ rest
        KS.place_prop(F, KS.prop_tray, m, 'prop_R', rest)
        place['prop_R'] = (rest, posed)
    elif P['prop'] == 'towel_stack':
        rest = T(gR + Vector((0.035, 0.0, -0.16))) @ roty
        posed = T((pL + pR) / 2 + Vector((0, 0.02, -0.03))) if working else S['hand_R'] @ rest
        KS.place_prop(F, KS.prop_towels, m, 'prop_R', rest)
        place['prop_R'] = (rest, posed)
    elif P['prop'] == 'noodle_basket':
        restL = T(gL) @ Matrix.Rotation(math.radians(-90), 4, 'X')
        posedL = T(pL) if working else S['hand_L'] @ restL
        KS.place_prop(F, KS.prop_basket, m, 'prop_L', restL)
        place['prop_L'] = (restL, posedL)
        if P['anim'] == 'noodle_pull':
            target = pL + Vector((0, 0.26, -0.07))
            d = target - pR
            q = d.normalized().rotation_difference(Vector((0, 0, -1))).to_matrix().to_4x4()
            restR = T(gR) @ q
            posedR = T(pR)
            KS.place_prop(F, lambda F_, mm: KS.prop_noodles(F_, mm, end=d), m, 'prop_R', restR)
            place['prop_R'] = (restR, posedR)
    return place


def assemble(lod, P, rot=None, root_rot=None):
    body = 'adult_woman' if P['body'] == 'woman' else 'adult_man'
    sk = KG.Skeleton(body, P['height'], P['build'])
    F = KG.Fig(sk, lod)
    m = _slots(F, P)
    F.mats = m
    B, z, k = sk.B, sk.z, sk.k
    role = P['role']
    F.part(['head'], rigid=True)
    KG.head_and_face(F, m['skin'])
    KG.hair(F, P['hair'], m['hair'], m['tie'] if P['hair'] == 'bun' else None)
    if role == 'chef':
        KS.headband(F, m['band'], m['crest'])
    F.part(['neck', 'head', 'chest'])
    KG.neck(F, m['skin'])
    yuk = role == 'attendant' and P['outfit'] == 'yukata'
    for S in 'LR':
        F.part(['upperarm_' + S, 'forearm_' + S, 'hand_' + S])
        if lod <= 2:
            KG.arm(F, S, m['skin'], from_elbow=True, cut=0.05 if yuk else 0.3)
            F.part(['hand_' + S], rigid=True)
            KG.hand(F, S, m['skin'])
    obi_w = (0.075 if P['body'] == 'woman' else 0.06) * sk.H
    obi_c = (0.6 if P['body'] == 'woman' else 0.575) * sk.H
    if yuk:
        hem = B['hem'] * sk.H
        cfg = dict(hem_z=hem, obi_c=B['obi_c'] * sk.H, obi_w=B['obi_w'] * sk.H, bow='butterfly', v_z=z['chest'], sleeve_len=0.75,
                   nuki=-0.03, hem_hw=B['hips_w'][0] * 0.95, cross_x=0.07 * k)
        obi_c, obi_w = cfg['obi_c'], cfg['obi_w']
    else:
        hem = z['hip'] - 0.1 * sk.H
        cfg = dict(hem_z=hem, obi_c=obi_c, obi_w=obi_w, bow='none', v_z=z['chest'] - 0.02 * k, sleeve='narrow',
                   sleeve_end=0.62, nuki=-0.012, hem_hw=B['hips_w'][0] * 1.12, cross_x=0.075 * k)
    mats = dict(robe=m['jacket'], obi=m['obi'], skin=m['skin'], cuff=m['cuff'] if role == 'attendant' else None)
    KG.yukata(F, mats, cfg)
    if not yuk:
        KS.trousers(F, m['pants'], dict(server='cropped', attendant='gathered', chef='leggings')[role], m['band'])
    else:
        for S in 'LR':
            F.part(['shin_' + S, 'foot_' + S, 'thigh_' + S])
            if lod <= 1:
                KG.leg(F, S, m['skin'], z_from=hem + 0.16 * k)
    if m['apron'] is not None:
        F.part(['pelvis', 'spine', 'thigh_L', 'thigh_R'])
        bib = role == 'chef'
        KS.apron(F, obi_c + obi_w * 0.3, z['knee'] - (0.02 if role == 'server' else 0.06) * k, 0.62 if role != 'chef' else 0.7,
                 m['apron'], mark=(role == 'server'), mi_mark=m['mark'])
        F.close()
        # re-wrap the obi over the apron top
        F.part(['spine', 'pelvis'])
        hw, hd, yc = F.robe.at(obi_c)
        no = KG.nseg(lod, 16, 10, 6, 5)
        out = 0.024 * k
        rings = [KG.sring(obi_c - obi_w * 0.42, hw + out, hd + out, no, p=2.4, yc=yc),
                 KG.sring(obi_c + obi_w * 0.42, hw + out, hd + out, no, p=2.4, yc=yc)]
        F.loft(rings, m['obi'])
    for S in 'LR':
        F.part(['foot_' + S, 'toe_' + S, 'shin_' + S])
        if lod <= 1:
            KG.foot(F, S, m['skin'])
        KG.geta(F, S, m['wood'], m['strap'])
    F.close()
    return F


def build(lod=0, seed=1, **kw):
    P = params_for(seed, **kw)
    F = assemble(lod, P)
    ys = [v.co.y for v in F.bm.verts]
    dy = -(max(ys) + min(ys)) / 2
    F.shift_y(dy)
    rot, root_rot = _pose(P, F.sk)
    place = _props(F, P, F.mats, rot, root_rot)
    keys = None
    if lod <= 2:
        keys = {}
        for name, bv in (('build_slim', 0.0), ('build_heavy', 1.0)):
            F2 = assemble(lod, dict(P, build=bv))
            F2.shift_y(dy)
            _props(F2, P, F2.mats, rot, root_rot)
            keys[name] = KG.sk_coords(F2)
            F2.mb.bm.free()
    o, arm = KG.finish_figure(F, ASSET, P['anim'], rot, root_rot, place, shape_keys=keys, params=P,
                              anim=['idle', 'walk', 'serve', 'carry', 'noodle_pull'])
    return o
