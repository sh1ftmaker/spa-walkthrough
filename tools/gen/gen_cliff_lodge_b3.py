"""Cliff-hung lit timber lodges on the B3 cavern walls (backdrop only, not entered).

Identifying features kept at every LOD: a multi-storey hinoki post-and-beam frontage with glowing shoji in every
bay, lattice-railed balconies, deep dark-tiled eaves, the whole block hung on the cavern wall on diagonal
timber brackets (and, on some seeds, timber stilts down to a rock ledge), a row of lit andon lanterns along
every balcony rail.

Targets (measured):
  * refs/gen/sheet-vs-lodges.png #03 "cliff lodge, three storeys" (label W 20 x D 6 x H 10 m; 20 m bar = 315 px,
    ~15.8 px/m): 6 bays of ~3.3 m, three lit storeys ~2.6-2.9 m each, ground platform and two upper balconies
    ~1.0-1.4 m deep with lattice rails ~0.9 m, square andon lanterns on every rail post (~0.25 x 0.4 m),
    irimoya roof with ~0.8-1.0 m eaves, diagonal brackets ~2-3 m below the platform into the rock.
    #01 / #02 (one / two storeys, W 10 / 15 m): same language, 3-5 bays.
  * lookbook 18 / 19 / 20 / 23: lodges cling to the black wall above the pools and the beach; 20 shows a long
    one-storey wing on a timber trestle (stilts) above the rocks; 13 / 14 / 29 show stacked lit fronts high on
    the vault walls.
  * Proxy 20 x 6 x 10 m.  The sheet's #03 measures ~11 m including the brackets; defaults are tuned to fit the
    proxy (storeys 2.55-3.1 m, pitch 22-25 deg), see report for a proposed proxy h of 11.

Construction: kzgeo_facade_timber.facade_into (mount 'cliff_bracket': posts, keta, shoji infill + ranma,
balconies with koran rails, pent roofs, irimoya / hip top roof from roof_tiled, diagonal brackets and the cliff
ledger), plus here: andon lanterns on the rail posts of every deck, timber stilts with X bracing and basalt
footing stones (stilt_h > 0), iron anchor plates on the cliff ledger, a back wall that the cavern rock covers.
Frame: front +Y, the back plane (wall contact) faces -Y.

Parameters (ranges from the row; defaults come from the seed's variant preset):
  variant        falls | terrace | geyser | beach (cycles with the seed: 1 falls, 2 terrace, 3 geyser, 4 beach)
  storeys        1-3;  bays 3-10;  bay_w 2.5-4 m;  storey_h 2.5-3.2 m
  bracket_depth  1-3 m deck projection in front of the body (the brackets reach this far off the wall)
  stilt_h        0-12 m timber stilts under the bracket platform (proxy h is exceeded above ~2.5 m on 2 storeys)
  balcony        0.8-1.5 m upper balcony depth;  infill shoji | lattice | glass (per storey list ok)
  roof           irimoya | hip | gable (roof_tiled types);  eave 0.6-1.2 m
Seeds change: variant (storeys, bays, stilts, infill, roof type, deck depth) and within it bay width, storey
height, eave, pitch, upsweep, tile pitch, ranma style, kumiko pattern, baluster pitch, lantern spacing.

Materials: hinoki dark_timber (posts, beams, brackets, stilts), hinoki wet_oiled (rails, frames, decks),
washi_backlit (shoji, ranma), lantern_andon (rail lanterns), lacquer_dark (walls, sills), lacquer_black (andon
roofs), kawara (tiles), bronze smooth (anchor plates), basalt_wet (stilt footings), glass_clear (beach glazing).
lava_glass (in the row) is not used: guide 7 reserves it; no concept shows it on these fronts.
Lighting: lightmap + emissive; obj['kz_lights'] (area per lit bay, point per lantern).  Animation: shader flicker,
obj['kz_anim'] = {'type': 'shader', 'flicker': {...}}.  obj['kz_wall'] = back plane y, z range and anchor points
for placing against the cavern wall (place model supplies the rock).
"""
import bmesh

import genlib
import gen_facade_timber as GF
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_facade_timber as KF

ASSET = 'cliff_lodge_b3'
FEATURES = ['multi-storey lit hinoki frontage', 'lattice-railed balconies', 'deep tiled eaves',
            'diagonal cliff brackets / stilts', 'andon lantern rows on the balconies']
FLOD = {0: 1, 1: 2, 2: 3, 3: 3}   # facade_timber resolution tier used per LOD (backdrop, mid detail tier)
VARIANTS = ['falls', 'terrace', 'geyser', 'beach']
PRESETS = {
    'falls': dict(storeys=3, bays=6, bay_w=3.1, storey_h=2.55, infill=['shoji'], balcony=[1.4, 1.1, 1.1],
                  roof='irimoya', body_d=2.5, eave=0.8, z0=1.25, stilt_h=0.0, pitch=(22, 24)),
    'terrace': dict(storeys=2, bays=5, bay_w=3.4, storey_h=2.7, infill=['shoji', 'lattice'], balcony=[1.6, 1.2],
                    roof='irimoya', body_d=2.5, eave=0.85, z0=1.2, stilt_h=2.2, pitch=(22, 25)),
    'geyser': dict(storeys=2, bays=4, bay_w=3.8, storey_h=3.0, infill=['lattice', 'shoji'], balcony=[2.4, 1.3],
                   roof='hip', body_d=2.6, eave=0.8, z0=2.4, stilt_h=0.0, pitch=(20, 23)),
    'beach': dict(storeys=1, bays=7, bay_w=2.62, storey_h=3.1, infill=['glass'], balcony=[1.8],
                  roof='hip', body_d=2.6, eave=0.8, z0=1.0, stilt_h=4.3, pitch=(19, 22)),
}


def params(seed, variant=None, storeys=None, bays=None, bay_w=None, storey_h=None, bracket_depth=None,
           stilt_h=None, balcony=None, infill=None, roof=None, eave=None):
    v = variant or C.cycle(seed, VARIANTS)
    pr = dict(PRESETS[v])
    g = C.rng(seed, 'lodge')
    pitch = g.uniform(*pr['pitch'])
    bw = bay_w or pr['bay_w'] * g.uniform(0.95, 1.04)
    sh = storey_h or pr['storey_h'] * g.uniform(0.97, 1.02)
    ns = int(storeys or pr['storeys'])
    bal = list(pr['balcony'])
    if balcony is not None:
        bal = [bal[0]] + [float(balcony)] * (ns - 1)
    if bracket_depth is not None:
        bal[0] = float(bracket_depth)
    bal = (bal + [bal[-1]] * ns)[:ns]
    inf = infill or pr['infill']
    P = GF.params(seed, 'kawagiri', bays=int(bays or pr['bays']), storeys=ns, bay_w=bw, storey_h=sh,
                  infill=inf, balcony=bal, eave=eave or pr['eave'] * g.uniform(0.95, 1.05), roof=roof or pr['roof'],
                  mount='cliff_bracket', body_d=pr['body_d'])
    P.update(variant=v, z0=pr['z0'], sign=None, lanterns=None, rail0=True, steps=False, pitch=pitch,
             stilt_h=float(stilt_h if stilt_h is not None else pr['stilt_h']),
             lantern_every=C.pick(seed, 'lantern_every', [1, 1, 2]) if int(bays or pr['bays']) > 6 else 1)
    P['eave_s'] = P['eave'] * 0.85
    P['n_panels_coarse'] = P['n_panels']
    return P


def _andon(mb, mats, lod, x, y, z):
    """square andon lantern standing on a rail post top: amber paper box + black hip cap (LOD0-1), crossed lit
    quads (LOD2), one lit quad facing +Y (LOD3)"""
    if lod >= 3:
        bm = mb.bm
        s, h = 0.26, 0.4
        f = bm.faces.new([bm.verts.new(p) for p in ((x - s / 2, y + 0.05, z), (x + s / 2, y + 0.05, z),
                                                    (x + s / 2, y + 0.05, z + h), (x - s / 2, y + 0.05, z + h))])
        f.material_index = mats['andon']
        return (x, y, z + h / 2)
    c = C.lantern_head(mb, (x, y, z), dict(iron=mats['cap'], paper=mats['andon']), max(1, lod), size=0.22,
                       height=0.36, roof='hip')
    return tuple(c)


def build(lod, seed, variant=None, storeys=None, bays=None, bay_w=None, storey_h=None, bracket_depth=None,
          stilt_h=None, balcony=None, infill=None, roof=None, eave=None, _fine=True, **_):
    P = params(seed, variant, storeys, bays, bay_w, storey_h, bracket_depth, stilt_h, balcony, infill, roof, eave)
    # LOD0: shoji with kumiko strips (panel tier below the facade's crowded-front default) when the budget holds;
    # otherwise fall back on that resolution only (printed), never on parts
    P['n_panels'] = 0 if (_fine and lod == 0) else P['n_panels_coarse']
    mb = genlib.MeshBuilder()
    struct = mb.slot('hinoki', variant='dark_timber')
    light = mb.slot('hinoki', variant='wet_oiled')
    paper = mb.slot('washi_backlit', emissive_level=round(C.rng(seed, 'glow').uniform(0.8, 0.95), 2))
    glow = mb.slot('washi_backlit', emissive_level=0.5)
    mats = dict(struct=struct, frame=light, wood=light, rail=light, deck=light, paper=paper, glow=glow,
                washi=mb.slot('washi', tint=(1.0, 0.93, 0.8)), lacquer=mb.slot('lacquer_black'),
                glass=mb.slot('glass_clear'), metal=mb.slot('bronze', variant='smooth'),
                frame_d=mb.slot('lacquer_dark', wear=0.15), wall=mb.slot('lacquer_dark', wear=0.3),
                gap=mb.slot('hinoki', variant='stained'), stone=mb.slot('basalt_wet', wetness=0.5),
                tile=mb.slot('kawara'), iron=mb.slot('iron', wear=0.2), sign=mb.slot('lacquer_black'),
                gold=mb.slot('gold_leaf'), cap=mb.slot('lacquer_black'), lantern=mb.slot('lantern_paper'),
                andon=mb.slot('lantern_andon', emissive_level=0.6))
    budget = genlib.budget_of(ASSET)
    B = budget[lod] if budget else None
    # facade + roof: leave ~12 % of the budget for lanterns, stilts and anchors (roof ladder falls back on resolution)
    import os
    flod = int(os.environ.get('KZ_FLOD_%d' % lod, FLOD[lod]))
    info = KF.facade_into(mb, mats, flod, P, budget=int(B * 0.88) if B else None)
    if info['roof_notes'] and any(info['roof_notes']):
        print(f'cliff_lodge_b3 LOD{lod} s{seed} roof resolution fallback: {info["roof_notes"]}')
    floors = info['floors']
    W = info['W']
    nb = P['bays']
    xs = [-W / 2 + k * P['bay_w'] for k in range(nb + 1)]
    bd = P['body_d']
    lights = list(info['lights'])

    # ---- andon lanterns on the front rail posts of every deck (kept at every LOD)
    for k, d in enumerate(P['balcony']):
        if d <= 0:
            continue
        zt = floors[k] + P['rail_h'] + 0.06
        for i, x in enumerate(xs):
            if i % P['lantern_every'] and 0 < i < nb:
                continue
            c = _andon(mb, mats, lod, x, d - 0.06, zt)
            lights.append(C.light_entry(c, color_k=2200, watts=10))

    # ---- iron anchor plates on the cliff ledger (LOD0)
    if lod == 0:
        for x in xs:
            mb.box((x, -bd - 0.01, 0.3), (0.34, 0.03, 0.42), mats['metal'])

    # ---- lift onto stilts
    sth = P['stilt_h']
    if sth > 0:
        vs = mb.bm.verts[:]
        bmesh.ops.translate(mb.bm, vec=(0, 0, sth), verts=vs)
        for l in lights:
            l['pos'] = [l['pos'][0], l['pos'][1], l['pos'][2] + sth]
        yf = max(P['balcony'][0], 0.3) - 0.3
        ys = (yf, -bd * 0.45)
        top = sth + P['z0'] - 0.33                       # underside of the bracket platform (front)
        sx = xs if lod <= 1 else xs[::2] + ([xs[-1]] if len(xs) % 2 == 0 else [])
        for x in sx:
            for y in ys:
                zt = top if y == yf else sth + 0.25
                if lod == 0:
                    C.chamfered_bar(mb, (x, y, zt / 2), (0.24, 0.24, zt), struct, ch=0.02, axis='z')
                elif lod <= 2:
                    mb.box((x, y, zt / 2), (0.24, 0.24, zt), struct)
                else:
                    bm = mb.bm
                    f = bm.faces.new([bm.verts.new(p) for p in ((x - 0.12, y + 0.12, 0), (x + 0.12, y + 0.12, 0),
                                                                (x + 0.12, y + 0.12, zt), (x - 0.12, y + 0.12, zt))])
                    f.material_index = struct
                if lod <= 1:
                    C.slab(mb, (x, y, 0.09), 0.5, 0.5, 0.18, mats['stone'], rc=0.06, m=C.lod_pick(lod, 3, 1))
        if lod <= 2:
            # tie beams along the front stilt line, X braces between stilt pairs (LOD0-1)
            nties = max(1, int(sth / 2.2))
            for t in range(1, nties + 1):
                zz = sth * t / (nties + 1)
                mb.box((0, yf + 0.16, zz), (W + 0.3, 0.1, 0.18), struct)
            if lod <= 1:
                for a, b in zip(sx[:-1], sx[1:]):
                    KF._strut(mb, (a, yf + 0.14, 0.25), (b, yf + 0.14, top - 0.15), 0.1, 0.08, struct)
                    KF._strut(mb, (b, yf + 0.2, 0.25), (a, yf + 0.2, top - 0.15), 0.1, 0.08, struct)

    if _fine and lod == 0 and B and C.tri_count(mb.bm) > B * 1.08:
        print(f'cliff_lodge_b3 LOD0 s{seed}: {C.tri_count(mb.bm)} tris with kumiko shoji, falling back to plain shoji panels')
        mb.bm.free()
        return build(lod, seed, variant, storeys, bays, bay_w, storey_h, bracket_depth, stilt_h, balcony, infill, roof,
                     eave, _fine=False)
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    if lod <= 1:
        kg.uv_grain(o, [struct, light, mats['frame_d']])
    for l in lights:
        l['pos'] = [round(l['pos'][0] + dx, 3), round(l['pos'][1] + dy, 3), round(l['pos'][2] + dz, 3)]
    flick = [paper, glow, mats['andon']]
    anchors = [[round(x + dx, 3), round(-bd + dy, 3), round(sth + 0.3 + dz, 3)] for x in (xs[0], xs[-1])]
    anchors += [[round(xs[0] + dx, 3), round(-bd + dy, 3), round(info['top'] + sth + dz, 3)],
                [round(xs[-1] + dx, 3), round(-bd + dy, 3), round(info['top'] + sth + dz, 3)]]
    C.set_json_props(o, kz_lights=lights, kz_flicker=flick,
                     kz_anim=dict(type='shader', flicker=dict(amp=0.06, hz=0.3, slots=flick)),
                     kz_wall=dict(back_y=round(-bd + dy, 3), z0=round(dz, 3), z1=round(info['top'] + sth + dz, 3),
                                  anchors=anchors, note='back plane meets the cavern rock; place model supplies rock'),
                     kz_facade=dict(front_y=round(dy, 3), floors=[round(f + sth + dz, 3) for f in floors],
                                    W=round(W, 3), body_d=round(bd, 3), variant=P['variant']),
                     kz_params={k: v for k, v in P.items() if k != 'panel'})
    return o
