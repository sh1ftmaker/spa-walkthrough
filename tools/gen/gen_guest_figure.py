"""Guest figure: skinned yukata guests and bathers, one shared base body (kzgeo_guest_figure) + clothing layers.

Targets (refs/gen/sheet-vs-people.png, panels 1-4, 1 m bar = 233 px; lookbook 04, 05, 09, 12):
  * heights (sheet labels): woman 1.65, man 1.78, elder 1.58, child 1.12 m. Head = 1/7.5 H (adult), 1/5.4 H (child).
  * front width across the hanging sleeves 0.56-0.62 m (woman 135 px, man 145 px); side depth incl. geta and the
    obi bow 0.30-0.42 m. Proxy 0.5 x 0.3 x 1.7 is too small for a yukata with a bow: see report (proposed 0.62 x 0.45 x 1.8).
  * yukata to the ankle (hem 0.03-0.05 H above the floor), wide tamoto sleeves hanging to the hip, crossed collar
    (left over right, the "y" read from the front), obi: woman 0.15 m at the waist with a butterfly bow at the back
    and a thin cord with a front knot; man 0.10 m low on the hips with a flat side knot; elder 0.12 m red-brown;
    child soft heko sash with a big droopy bow. Geta with two teeth and a thong strap. Hair bun (woman, elder grey),
    short with a small topknot (man), two-bun top knot (child).
  * bathers (lookbook 12, 17): towel wrap (woman chest-to-thigh, man waist-to-knee) or swimsuit (one-piece / trunks).

Parameters (build kwargs): body adult_woman|adult_man|elder|child; height (m, 1.02-1.85 by body);
  build 0-1 (girth); clothing yukata_linen|yukata_indigo|yukata_black|towel_wrap|swimsuit; hair bun|short|topknot|
  bob|grey_bun|buns2; pose standing|walking|seated|soaking|floating; skin 0-2 (tone); pattern plain|hem_band;
  stick (elder cane, bool).
Seeds walk a table of body x clothing combos (1 woman indigo, 2 man black, 3 elder linen + cane, 4 child linen
  with red sash, 5 woman towel wrap, 6 man swimsuit trunks, 7 child swimsuit, 8 woman linen ...), and draw height
  (+-4 %), build, hair, skin tone and pattern from their own streams.
Colour follows depth: yukata_linen (undyed, crater/garden levels), yukata_indigo (caverns), yukata_black (river).

Rig / animation: 24-bone armature (kzgeo_guest_figure.BONES) parented to the mesh with an Armature modifier;
  mesh = bind pose (standing), weights per part, shape keys build_slim / build_heavy. obj['kz_anim'] lists the bones,
  clips idle/walk/sit/soak/float and the stored pose. Poses are stored on the armature (renders show them,
  genlib.check measures the bind mesh). soaking / floating write obj['kz_water_level'] (chest / back height).
Budget 3000 / 1200 / 400 / impostor; LOD3 is a ~150-250 tri skinned silhouette (bake the impostor card from it
  or from LOD0). Materials: noren (indigo / black), linen, skin = ceramic tinted + rough (stand-in for NEW:skin),
  hair = lacquer_black / linen grey (stand-in for NEW:hair), hinoki (geta), terry (towel).
"""
import math

from mathutils import Matrix, Vector

import genlib
import kzgeo_common as C
import kzgeo_guest_figure as KG

ASSET = 'guest_figure'
FEATURES = ['human silhouette', 'yukata colour by depth (linen / indigo / black) or towel / swimsuit', 'obi',
            'hair bun', 'wide sleeves']
PARAMS = dict(body=tuple(KG.BODIES), height=(1.02, 1.85), build=(0.0, 1.0),
              clothing=('yukata_linen', 'yukata_indigo', 'yukata_black', 'towel_wrap', 'swimsuit'),
              hair=('bun', 'short', 'topknot', 'bob', 'grey_bun', 'buns2'),
              pose=('standing', 'walking', 'seated', 'soaking', 'floating'), skin=(0, 1, 2), pattern=('plain', 'hem_band'))
TABLE = [('adult_woman', 'yukata_indigo'), ('adult_man', 'yukata_black'), ('elder', 'yukata_linen'),
         ('child', 'yukata_linen'), ('adult_woman', 'towel_wrap'), ('adult_man', 'swimsuit'), ('child', 'swimsuit'),
         ('adult_woman', 'yukata_linen'), ('adult_man', 'yukata_indigo'), ('adult_man', 'towel_wrap'),
         ('elder', 'yukata_indigo'), ('adult_woman', 'swimsuit')]
SKIN = [(0.86, 0.6, 0.46), (0.76, 0.5, 0.37), (0.92, 0.7, 0.56)]


def params_for(seed, **kw):
    body, clothing = C.cycle(seed, TABLE)
    body = kw.get('body', body)
    clothing = kw.get('clothing', clothing)
    B = KG.BODIES[body]
    g = C.rng(seed, 'height')
    H = kw.get('height', min(B['Hr'][1], max(B['Hr'][0], B['H'] * g.uniform(0.96, 1.035))))
    build = kw.get('build', round(C.rng(seed, 'build').uniform(0.15, 0.85), 3))
    hair_opts = dict(adult_woman=['bun', 'bun', 'bob'], adult_man=['topknot', 'short'], elder=['grey_bun'],
                     child=['buns2', 'bob'])[body]
    hair = kw.get('hair', hair_opts[0] if seed <= len(TABLE) else C.pick(seed, 'hair', hair_opts))
    skin = kw.get('skin', C.pick(seed, 'skin', [0, 1, 2]))
    pattern = kw.get('pattern', 'hem_band' if seed in (1, 4) else ('plain' if seed <= len(TABLE) else C.pick(seed, 'pattern', ['plain', 'hem_band'])))
    return dict(body=body, clothing=clothing, height=round(H, 3), build=build, hair=hair, skin=skin, pattern=pattern,
                pose=kw.get('pose', 'standing'), stick=kw.get('stick', body == 'elder' and clothing.startswith('yukata')))


def _slots(F, P):
    """every slot created up front in one fixed order (shape-key rebuilds need identical slot indices)"""
    m = {}
    m['skin'] = F.slot('ceramic', tint=SKIN[P['skin']], roughness_offset=0.38)
    m['hair'] = F.slot('linen', tint=(0.4, 0.4, 0.41)) if P['hair'] == 'grey_bun' else F.slot('lacquer_black', roughness_offset=0.15)
    cl = P['clothing']
    if cl == 'yukata_linen':
        m['robe'] = F.slot('linen'); m['pattern'] = F.slot('noren')
    elif cl == 'yukata_black':
        m['robe'] = F.slot('noren', variant='black'); m['pattern'] = F.slot('linen', tint=(0.42, 0.4, 0.37))
    else:
        m['robe'] = F.slot('noren'); m['pattern'] = F.slot('linen', tint=(0.78, 0.74, 0.66))
    body = P['body']
    if body == 'child':
        m['obi'] = F.slot('noren', variant='vermilion', tint=(0.3, 0.02, 0.016))
    elif body == 'elder':
        m['obi'] = F.slot('noren', variant='vermilion')
    elif cl == 'yukata_linen' and body == 'adult_man':
        m['obi'] = F.slot('noren')
    else:
        m['obi'] = F.slot('linen', tint=(0.74, 0.56, 0.34))
    m['cord'] = F.slot('noren', variant='vermilion')
    m['wood'] = F.slot('hinoki', variant='natural')
    m['strap'] = F.slot('noren', variant='black') if body == 'adult_man' else F.slot('noren', variant='vermilion')
    m['towel'] = F.slot('terry', variant='cream')
    m['suit'] = F.slot('noren', variant={'adult_woman': 'black', 'child': 'vermilion'}.get(body)) if body != 'adult_man' and body != 'elder' else F.slot('noren')
    m['stick'] = F.slot('hinoki', variant='walnut')
    m['tie'] = F.slot('noren', variant='vermilion')
    return m


def assemble(lod, P):
    sk = KG.Skeleton(P['body'], P['height'], P['build'])
    F = KG.Fig(sk, lod)
    m = _slots(F, P)
    B, z, k = sk.B, sk.z, sk.k
    cl = P['clothing']
    yuk = cl.startswith('yukata')
    if P['pattern'] != 'hem_band' or not yuk:
        m_pat = None
    else:
        m_pat = m['pattern']
    # head, hair, neck
    F.part(['head'], rigid=True)
    KG.head_and_face(F, m['skin'], hs=1.0)
    KG.hair(F, P['hair'], m['hair'], m['tie'] if P['hair'] in ('bun', 'grey_bun', 'buns2') else None)
    F.part(['neck', 'head', 'chest'])
    KG.neck(F, m['skin'])
    # arms + hands
    for S in 'LR':
        F.part(['clavicle_' + S, 'upperarm_' + S, 'forearm_' + S, 'hand_' + S, 'chest'] if not yuk else ['upperarm_' + S, 'forearm_' + S, 'hand_' + S])
        if lod <= 2 or not yuk:
            KG.arm(F, S, m['skin'], from_elbow=yuk, cut=0.05 if yuk else None)
        if lod <= 2:
            F.part(['hand_' + S], rigid=True)
            KG.hand(F, S, m['skin'])
    if yuk:
        hem = B['hem'] * sk.H
        bow = {'adult_woman': 'butterfly', 'elder': 'butterfly', 'child': 'heko'}.get(P['body'], 'knot')
        obi_w = B['obi_w'] * sk.H
        cfg = dict(hem_z=hem, obi_c=B['obi_c'] * sk.H, obi_w=obi_w, bow=bow, v_z=z['chest'] + (0.0 if B['sex'] == 1 else -0.02) * k,
                   sleeve_len=0.75 if B['sex'] != 0 else 0.62, nuki=-0.03 if B['sex'] == 1 else -0.012,
                   hem_hw=B['hips_w'][0] * (0.95 if B['sex'] == 1 else 1.12), cross_x=0.07 * k)
        KG.yukata(F, dict(robe=m['robe'], obi=m['obi'], cord=m['cord'] if P['body'] in ('adult_woman',) else None,
                          skin=m['skin'], pattern=m_pat), cfg)
        # shins below the hem, feet, geta
        for S in 'LR':
            F.part(['shin_' + S, 'foot_' + S, 'thigh_' + S])
            if lod <= 1:
                KG.leg(F, S, m['skin'], z_from=hem + 0.16 * k)
            F.part(['foot_' + S, 'toe_' + S, 'shin_' + S])
            if lod <= 1:
                KG.foot(F, S, m['skin'])
            KG.geta(F, S, m['wood'], m['strap'])
    else:
        sex = B['sex']
        # torso / legs with the swimsuit painted on (no extra shell) or a towel wrap shell
        def suit_bands(zs):
            out = []
            for a, b in zip(zs[:-1], zs[1:]):
                if cl != 'swimsuit':
                    out.append(m['skin'])
                elif sex == 0:
                    out.append(m['suit'] if b <= z['waist'] - 0.04 * k else m['skin'])
                else:
                    out.append(m['suit'] if b <= z['chest'] + 0.04 * k else m['skin'])
            return out
        F.part(['pelvis', 'spine', 'chest', 'neck', 'thigh_L', 'thigh_R', 'clavicle_L', 'clavicle_R'])
        KG.torso(F, m['skin'], mis_fn=suit_bands)
        for S in 'LR':
            F.part(['pelvis', 'thigh_' + S, 'shin_' + S, 'foot_' + S])
            nb = 6 if lod <= 1 else 3
            mis = [m['skin']] * nb
            if cl == 'swimsuit' and sex == 0:
                mis[0] = m['suit']
            KG.leg(F, S, m['skin'], mis=mis)
            F.part(['foot_' + S, 'toe_' + S, 'shin_' + S])
            KG.foot(F, S, m['skin'])
        if cl == 'swimsuit' and sex != 0 and lod <= 1:          # shoulder straps
            F.part(['chest', 'clavicle_L', 'clavicle_R'])
            for s in (-1, 1):
                xs = s * 0.075 * k
                pts = [Vector((xs, B['chest_w'][1] * sk.g + 0.01 + B['bust'] * 0.5, z['chest'] + 0.035 * k)),
                       Vector((s * 0.09 * k, 0.04 * k, z['shoulder'] - 0.02 * k)),
                       Vector((s * 0.095 * k, -0.02 * k, z['shoulder'] - 0.012 * k)),
                       Vector((s * 0.085 * k, -B['chest_w'][1] * sk.g - 0.0, z['chest'] + 0.02 * k))]
                nr = [Vector((0, 1, 0.3)), Vector((s * 0.2, 0.3, 1)), Vector((s * 0.2, -0.3, 1)), Vector((0, -1, 0.2))]
                F.band(pts, nr, 0.022 * k, 0.005, m['suit'])
        if cl == 'towel_wrap':
            F.part(['pelvis', 'spine', 'chest', 'thigh_L', 'thigh_R'])
            towel_wrap(F, m['towel'], sex)
    if P['stick']:
        F.part(['prop_R'], rigid=True)
        J = sk.J
        g = sk.heads['prop_R']
        n = KG.nseg(lod, 8, 6, 4, 4)
        top = g + Vector((0, 0.02, 0.03))
        C.stick(F.mb, top, Vector((g.x + 0.03, g.y + 0.1, 0.0)), 0.013 * k, 0.011 * k, m['stick'], segs=n)
        if lod <= 1:
            C.stick(F.mb, top + Vector((0, -0.05, 0.0)), top + Vector((0, 0.04, 0.0)), 0.014 * k, 0.014 * k, m['stick'], segs=6)
    F.close()
    return F


def towel_wrap(F, mi, sex):
    """terry towel wrapped round the body: woman armpit -> mid thigh, man waist -> knee. Rolled top edge, tuck."""
    sk, lod = F.sk, F.lod
    B, z, k, g = sk.B, sk.z, sk.k, sk.g
    n = KG.nseg(lod, 16, 10, 6, 5)
    cw, ww, hw = B['chest_w'], B['waist_w'], B['hips_w']
    t = 0.016 * k
    if sex == 1:
        lv = [(z['hip'] - 0.17 * sk.H * 0.6, hw[0] * 1.08, hw[1] * 1.12, 0.0), (z['hip'] + 0.02, hw[0] + t, hw[1] + t, 0.0),
              (z['waist'], ww[0] + t, ww[1] + t, 0.0), (z['chest'] + 0.03 * k, cw[0] + t, cw[1] + t + B['bust'] * 0.7, 0.0)]
    else:
        lv = [(z['knee'] + 0.06, hw[0] * 1.18, hw[1] * 1.25, 0.0), (z['hip'] - 0.05, hw[0] * 1.08 + t, hw[1] * 1.1 + t, 0.0),
              (z['hip'] + 0.04, hw[0] + t, hw[1] + t, 0.0), (z['waist'] + 0.02, ww[0] + t * 1.3, ww[1] + t * 1.3, 0.0)]
    if lod >= 2:
        lv = [lv[0], lv[2], lv[3]]
    rings = [KG.sring(zz, a * g, b * g, n, p=2.4, yc=yc) for zz, a, b, yc in lv]
    zt = lv[-1][0]
    a, b = lv[-1][1] * g, lv[-1][2] * g
    rings.append(KG.sring(zt + 0.012, a + 0.012, b + 0.012, n, p=2.4))       # rolled top edge
    rings.append(KG.sring(zt + 0.022, a - 0.004, b - 0.004, n, p=2.4))
    bot = lv[0]
    inner = KG.sring(bot[0] + 0.03, bot[1] * g * 0.93, bot[2] * g * 0.93, n, p=2.4)
    F.loft([inner] + rings, mi)
    if lod <= 1:                                                              # tucked corner at the front-left
        F.blob(Vector((-0.06 * k, (lv[-1][2] * g) + 0.01, zt - 0.02)), (0.035 * k, 0.012 * k, 0.03 * k), mi, segs=6, rings=4)


def centre_dy(F):
    ys = [v.co.y for v in F.bm.verts]
    dy = -(max(ys) + min(ys)) / 2
    F.shift_y(dy)
    return dy


def build(lod=0, seed=1, **kw):
    P = params_for(seed, **kw)
    F = assemble(lod, P)
    dy = centre_dy(F)
    keys = None
    if lod <= 2:
        keys = {}
        for name, bv in (('build_slim', 0.0), ('build_heavy', 1.0)):
            F2 = assemble(lod, dict(P, build=bv))
            F2.shift_y(dy)
            keys[name] = KG.sk_coords(F2)
            F2.mb.bm.free()
    rot, root_rot = KG.standard_pose(P['pose'], F.sk)
    prop_place = None
    if P['stick'] and P['pose'] in ('walking',):
        pass
    o, arm = KG.finish_figure(F, ASSET, P['pose'], rot, root_rot, prop_place, shape_keys=keys, params=P)
    if P['pose'] == 'soaking':
        o['kz_water_level'] = round(F.sk.z['chest'] - F.sk.z['hip'] + 0.06, 3)
    elif P['pose'] == 'floating':
        o['kz_water_level'] = 0.12
    o['kz_impostor'] = 'LOD3 is a skinned silhouette; bake the far impostor card from LOD0' if lod == 3 else ''
    return o
