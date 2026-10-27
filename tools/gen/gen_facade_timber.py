"""Lit timber facade (gate, arrival, terrace and changing fronts on G; Kawagiri hall on B2; cavern lodges on B3).

Identifying features kept at every LOD: a multi-bay hinoki post-and-beam front with glowing shoji / lattice or
lit glazing in every bay, balconies with lattice rails, deep tiled eaves (pent roofs and the top roof from
roof_tiled); on B3 the same frontage hangs on the cavern wall on timber brackets.

Targets (measured):
  * lookbook 06 Kawagiri (diners ~1.7 m standing for scale): two-storey hall, bays ~3.0-3.5 m, storey ~3.3-3.6 m,
    upper balcony ~1.2-1.5 m deep with a 0.9-1.0 m baluster rail (balusters ~0.15 m apart), posts ~0.25 m,
    川霧 / KAWAGIRI board ~3.5 x 1.5 m on the upper front, red chochin under the beams, frontage on a timber
    trestle over the river.  sheet-mod-kawagiri #1/#2 (5 m bar): post ~0.25-0.3 m, beams 0.25-0.3 m deep.
  * lookbook 04 / 14 / 18 / 19 / 20 (people for scale): ground and terrace fronts 2-4 bays of shoji or tall
    glazing, storey 3.0-3.4 m, deep eaves 1.2-1.8 m with dark kawara, engawa decks 0.4-0.6 m high; the B3 fronts
    (18 rimstone, 19 thunder curtain, 20 wave grotto) sit on the rock on diagonal timber brackets, 2-3 storeys,
    balconies with lattice rails, pent roofs between storeys.
  * sheet-mod-pavilions #01/#02 (5 m bar): shoji 0.9-0.95 m wide, door head ~2.0-2.1 m, ranma band above,
    roof pitch 25-30 deg, eave 1.0-1.2 m.
  Row ranges: bays 2-12, storeys 1-3, bay_w 2.5-4, storey_h 3-4, balcony 0-1.5, eave 0.6-1.8 m.

Parameters (defaults: the seed's variant preset; proposed proxy 21 x 9 x 12 m, assets.json has no w/d/h yet):
  variant     porch | terrace | changing | kawagiri | beach (default cycles with the seed, seed 1 = porch ...
              seed 4 = kawagiri, seed 5 = beach)
  bays 2-12, storeys 1-3, bay_w 2.5-4 m, storey_h 3-4 m
  infill      shoji | glass | lattice (one value or a list per storey, ground first)
  balcony     0-1.5 m (upper storeys; storey 0 gets the engawa / deck from the preset)
  eave        0.6-1.8 m top-roof eave beyond the wall / balcony line;  roof  any roof_tiled type
  mount       ground | cliff_bracket (cliff: the floor sits on diagonal brackets off the back plane y = -body_d)
  body_d      1-6 m depth of the building body behind the front (the row's d)
Seeds change: the variant preset (storeys, bays, infill, balconies, roof type, mount, sign, lanterns) and within it
bay width +-6 %, storey height, eave depth, pitch, upsweep, tile pitch, ranma style, panel kumiko pattern,
baluster pitch, pent depth.

Materials: hinoki dark_timber (posts, beams, brackets, rafters), hinoki wet_oiled (shoji frames, kumiko, rails,
deck), washi_backlit (lit shoji, ranma, interior glow behind glass at a lower emission), glass_clear (glazing),
lacquer_dark (side / back wall boards, sills, bargeboards), lacquer_black (sign field, chochin caps), gold_leaf
(sign text), lantern_paper red (Kawagiri chochin), kawara (all tiles), iron (finial), paving (footing stones).
lava_glass is in the row but not used: glazing here is clear glass in front of a lit room (guide §7).
Lighting: lightmap + emissive.  obj['kz_lights']: one area entry per lit bay / ranma, points for lanterns and
the sign.  Animation (shader, subtle window flicker): obj['kz_flicker'] = lit paper slots,
obj['kz_anim'] = {'type': 'shader', 'flicker': {'amp': 0.06, 'hz': 0.3, 'slots': [...]}}.
Anchors: obj['kz_facade'] = {front_y, floors, top, W, body_d} after centring (hosts such as cliff_lodge_b3 use them).
"""
import genlib
import gen_shoji_panel as GSP
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_facade_timber as KF

ASSET = 'facade_timber'
FEATURES = ['multi-bay hinoki post-and-beam front', 'glowing shoji / lattice / glazing', 'balconies with lattice rails',
            'deep tiled eaves', 'cliff brackets (B3 mount)']
VARIANTS = ['porch', 'terrace', 'changing', 'kawagiri', 'beach']
PRESETS = {
    'porch': dict(bays=3, storeys=1, bay_w=2.9, storey_h=3.2, infill=['shoji'], balcony=[1.3], roof='irimoya',
                  mount='ground', body_d=3.2, eave=1.3, z0=0.5, rail0=False, steps=True, lanterns='amber', sign=None),
    'terrace': dict(bays=4, storeys=2, bay_w=3.1, storey_h=3.3, infill=['glass', 'shoji'], balcony=[0.0, 1.2],
                    roof='hip', mount='ground', body_d=3.6, eave=1.2, z0=0.35, rail0=False, steps=False,
                    lanterns=None, sign=None),
    'changing': dict(bays=4, storeys=1, bay_w=2.6, storey_h=3.4, infill=['lattice'], balcony=[0.9], roof='gable',
                     mount='ground', body_d=3.0, eave=1.0, z0=0.45, rail0=False, steps=True, lanterns=None, sign=None),
    'kawagiri': dict(bays=5, storeys=2, bay_w=3.2, storey_h=3.4, infill=['shoji', 'shoji'], balcony=[1.4, 1.4],
                     roof='irimoya', mount='cliff_bracket', body_d=4.0, eave=0.9, z0=2.0, rail0=True, steps=False,
                     lanterns='red', sign=('川霧', 'KAWAGIRI')),
    'beach': dict(bays=4, storeys=1, bay_w=3.4, storey_h=3.0, infill=['glass'], balcony=[1.6], roof='hip',
                  mount='ground', body_d=3.4, eave=1.8, z0=0.4, rail0=False, steps=True, lanterns='amber', sign=None),
}


def params(seed, variant=None, **over):
    v = variant or C.cycle(seed, VARIANTS)
    P = dict(PRESETS[v])
    P['variant'] = v
    g = C.rng(seed, 'facade')
    P['bay_w'] *= g.uniform(0.94, 1.06)
    P['storey_h'] *= g.uniform(0.96, 1.05)
    P['eave'] *= g.uniform(0.92, 1.1)
    P['pitch'] = g.uniform(22, 29)
    P['up'] = g.uniform(0.12, 0.25)
    P['tp'] = g.uniform(0.25, 0.3)
    P['p'] = g.uniform(1.12, 1.3)
    P['pent'] = g.uniform(0.9, 1.2)
    P['baluster'] = g.uniform(0.15, 0.19)
    P['glass_pitch'] = g.uniform(1.0, 1.4)
    P['ranma'] = C.pick(seed, 'ranma', ['tate', 'yoko'])
    P['rail_h'] = 0.95
    P['post_w'] = 0.24
    P['door_h'] = 2.1
    for k, val in over.items():
        if val is not None:
            P[k] = val
    ns = int(P['storeys'])
    P['storeys'] = ns
    P['bays'] = int(P['bays'])
    inf = P['infill']
    P['infill'] = [inf] * ns if isinstance(inf, str) else (list(inf) + [inf[-1]] * ns)[:ns]
    bal = P['balcony']
    if isinstance(bal, (int, float)):
        bal = [PRESETS[v]['balcony'][0]] + [float(bal)] * (ns - 1)
    P['balcony'] = (list(bal) + [bal[-1]] * ns)[:ns]
    P['eave_s'] = P['eave'] * 0.85
    # panel count drives the panel LOD used for the infill (resolution, not presence: see facade_into)
    P['n_panels'] = sum(P['bays'] * max(2, round((P['bay_w'] - P['post_w']) / 0.95)) for k in P['infill'] if k != 'glass')
    P['panel'] = GSP.params(seed, 0.95, 2.0, 'shoji' if 'shoji' in P['infill'] else 'lattice')
    P['panel']['koshi'] = 0.25 if v != 'kawagiri' else 0.0
    return P


def build(lod, seed, variant=None, bays=None, storeys=None, bay_w=None, storey_h=None, infill=None, balcony=None,
          eave=None, roof=None, mount=None, body_d=None, **_):
    P = params(seed, variant, bays=bays, storeys=storeys, bay_w=bay_w, storey_h=storey_h, infill=infill,
               balcony=balcony, eave=eave, roof=roof, mount=mount, body_d=body_d)
    if P['mount'] == 'cliff_bracket' and P['z0'] < 1.2:
        P['z0'] = 2.0
    mb = genlib.MeshBuilder()
    struct = mb.slot('hinoki', variant='dark_timber')
    light = mb.slot('hinoki', variant='wet_oiled')
    paper = mb.slot('washi_backlit', emissive_level=round(C.rng(seed, 'glow').uniform(0.85, 1.0), 2))
    glow = mb.slot('washi_backlit', emissive_level=0.55)
    mats = dict(struct=struct, frame=light, wood=light, rail=light, deck=light, paper=paper, glow=glow,
                washi=mb.slot('washi', tint=(1.0, 0.93, 0.8)), lacquer=mb.slot('lacquer_black'),
                glass=mb.slot('glass_clear'), metal=mb.slot('bronze', variant='smooth'),
                frame_d=mb.slot('lacquer_dark', wear=0.15), wall=mb.slot('lacquer_dark', wear=0.3),
                gap=mb.slot('hinoki', variant='stained'), stone=mb.slot('paving'), tile=mb.slot('kawara'),
                iron=mb.slot('iron', wear=0.2), sign=mb.slot('lacquer_black'), gold=mb.slot('gold_leaf'),
                cap=mb.slot('lacquer_black'))
    if P['lanterns'] == 'red':
        mats['lantern'] = mb.slot('lantern_paper', tint=(1.0, 0.05, 0.02), emissive_level=0.5)
    else:
        mats['lantern'] = mb.slot('lantern_paper', emissive_level=0.95)
    budget = genlib.budget_of(ASSET)
    info = KF.facade_into(mb, mats, lod, P, budget=budget[lod] if budget else None)
    if info['roof_notes']:
        print(f'facade_timber LOD{lod} s{seed} roof resolution fallback: {info["roof_notes"]}')
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    if lod <= 1:
        kg.uv_grain(o, [struct, light, mats['frame_d']])
    lights = info['lights']
    for l in lights:
        l['pos'] = [round(l['pos'][0] + dx, 3), round(l['pos'][1] + dy, 3), round(l['pos'][2] + dz, 3)]
    flick = [paper, glow] + ([mats['lantern']] if P['lanterns'] else [])
    C.set_json_props(o, kz_lights=lights, kz_flicker=flick,
                     kz_anim=dict(type='shader', flicker=dict(amp=0.06, hz=0.3, slots=flick)),
                     kz_facade=dict(front_y=round(dy, 3), floors=[round(f + dz, 3) for f in info['floors']],
                                    top=round(info['top'] + dz, 3), W=round(info['W'], 3), body_d=round(P['body_d'], 3),
                                    variant=P['variant'], mount=P['mount']),
                     kz_params={k: v for k, v in P.items() if k != 'panel'})
    return o
