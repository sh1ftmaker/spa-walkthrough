"""Tiled roof component (hip, gable, irimoya, pyramidal, two-tier): dark kawara over upswept eaves.

Identifying features kept at every LOD: dark kawara tile field with an upswept (sori) eave line, ridge with end
caps (onigawara), the roof type's silhouette; LOD0-1 add the tile ribs (marugawara), LOD0 the round eave-end tiles
and rafter tails under the eaves.

Targets (measured):
  * sheet-mod-pavilions #01 (engawa 8 x 5 m, 1 m bar ~ 45 px): roof field 8.6 m eave to eave, ~1.6 m rise over a
    2.5 m half depth (mean pitch ~ 30 deg), eave overhang ~1.0 m beyond the posts, fascia ~0.14 m, ridge ~0.35 m
    tall with low blocky onigawara; irimoya gable in the top ~40 % of the rise.
  * #02 treatment room (6 m): hip-gable, pitch ~28 deg.  #03 tsukimi pavilion (10 m): pyramidal (hokei) with a
    finial ~0.8 m, strong sori (corner tips lifted ~0.3-0.4 m).  #04 warming hut (4 m): irimoya, pitch ~30 deg.
  * sheet-mod-kawagiri #1/#2: shallow gable caps on the dining pod / sign gate (pitch ~20-22 deg).
  * lookbook 12 / 32: two-tier pavilion roofs (lower skirt + upper irimoya) at the river bend and the moon deck.
  Tile pitch (rib spacing) 0.24-0.30 m (sheet #01 shows ~34 ribs across 8.6 m = 0.25 m).

Construction: kzgeo_roof_tiled.roof_into -> kzgeo_pavilion_engawa.roof (concave tile field meshed in eave rings,
semi-round ribs, tomoe eave discs, noshi ridge + onigawara, hip / rake ridges, gable board with slats and
bargeboards, fascia with tile lip, soffit, rafter tails).  Pyramid adds a roban block + iron hoju finial; two_tier
adds a hip skirt roof, a timber frieze storey (posts, lacquer panel, head beam) and an upper irimoya / hip roof.
Open underside inside the wall line: the host's walls and ceiling close it (the component sits on the host).

Parameters (defaults: proposed proxy 7.0 x 5.5 x 4.0 m; assets.json has no w/d/h for this row yet):
  w, d     eave outline (m)  default 6.4 x 4.6, seeded +-10 % (pyramid uses min(w, d) square)
  typ      hip | gable | irimoya | pyramid | two_tier   (default cycles with the seed: irimoya, hip, pyramid, gable,
           two_tier)
  pitch    20-35 deg mean slope (default seeded 24-32; two_tier skirt 0.8x)
  eave     0.4-1.8 m overhang beyond the host wall line (default seeded 0.8-1.3)
  up       0-0.4 m upsweep of the eave corners (default seeded 0.12-0.30; pyramid 0.25-0.38)
  tp       0.24-0.30 m tile row pitch (default seeded)
  upper    upper-tier type for two_tier: irimoya | hip (default seeded)
Seeds change: type, outline aspect, pitch, concavity, upsweep, eave depth, tile pitch, gable line, upper tier type.

Materials: kawara (tiles, ridge, onigawara), hinoki dark_timber (fascia, soffit, rafters, frieze posts),
lacquer_dark (gable board, bargeboards, frieze panels), iron (finial).  Lighting: lightmap.  Animation: none.
Custom props: kz_roof = {type, wall_top, wall_hw, wall_hd, ridge_z, top_z}: z of the host's wall plate and the
wall-line half extents, so a host can sit the roof on its posts.
"""
import math

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_roof_tiled as KR

ASSET = 'roof_tiled'
FEATURES = ['dark kawara tile field', 'upswept eaves', 'ridge with end caps', 'roof-type silhouette',
            'rafter tails under deep eaves (LOD0)']
TYPES = KR.TYPES


def params(seed, w=None, d=None, typ=None, pitch=None, eave=None, up=None, tp=None, upper=None):
    g = C.rng(seed, 'roof')
    P = dict(typ=typ or C.cycle(seed, TYPES))
    P['w'] = float(w) if w else 6.4 * g.uniform(0.9, 1.1)
    P['d'] = float(d) if d else 4.6 * g.uniform(0.9, 1.1)
    P['pitch'] = float(pitch) if pitch else g.uniform(24, 32)
    P['eave'] = float(eave) if eave else g.uniform(0.8, 1.3)
    P['up'] = float(up) if up is not None else (g.uniform(0.25, 0.38) if P['typ'] == 'pyramid' else g.uniform(0.12, 0.3))
    P['tp'] = float(tp) if tp else g.uniform(0.24, 0.3)
    P['p'] = g.uniform(1.12, 1.4)
    P['dg'] = 0.6 ** (1 / P['p']) + g.uniform(-0.04, 0.04)
    P['upper'] = upper or C.pick(seed, 'upper', ['irimoya', 'hip'])
    return P


def build(lod, seed, w=None, d=None, typ=None, pitch=None, eave=None, up=None, tp=None, upper=None, **_):
    P = params(seed, w, d, typ, pitch, eave, up, tp, upper)
    budget = genlib.budget_of(ASSET)
    mb = genlib.MeshBuilder()
    mats = dict(tile=mb.slot('kawara'), wood=mb.slot('hinoki', variant='dark_timber'),
                wood_d=mb.slot('lacquer_dark', wear=0.1), iron=mb.slot('iron', wear=0.2))
    mats['ridge'] = mats['tile']
    r = C.rng(seed, 'roof_geo')
    info = KR.roof_into(mb, mats, lod, P['typ'], P['w'] / 2, P['d'] / 2, z_e=0.0, pitch=P['pitch'], eave=P['eave'],
                        up=P['up'], tp=P['tp'], p=P['p'], dg=P['dg'], budget=budget[lod] if budget else None, r=r,
                        upper=P['upper'])
    if info['notes'] and any(info['notes']):
        print(f'roof_tiled LOD{lod} s{seed} resolution fallback: {info["notes"]}')
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    kg.uv_grain(o, [mats['wood'], mats['wood_d']])
    C.set_json_props(o, kz_roof=dict(type=P['typ'], wall_top=round(info['wall_top'] + dz, 3),
                                     wall_hw=round(info['wall_hw'], 3), wall_hd=round(info['wall_hd'], 3),
                                     ridge_z=round(info['ridge_z'] + dz, 3), top_z=round(info['top_z'] + dz, 3)),
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()},
                     kz_lights=[])
    return o
