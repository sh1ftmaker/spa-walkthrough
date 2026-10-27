"""Basalt slab bridge (bridge_slab): a thick basalt deck over a stream with low block parapets on both edges.

Target dimensions (row: typical 7.4 x 4 x 0.6 m, parapets add 0.3 m):
  span 7.4 m along X (row 2.6-7.4), deck width 4.0 m along Y (row 1.4-4), deck thickness 0.45 m default
  (row 0.4-0.9; 0.45 so deck + sills + parapet stay in the proxy h 0.9), parapet 0.30 m above the deck
  (row 0-0.8), parapet body 0.30 m thick with a 0.02-0.03 m cap overhang. Bank sills 0.20 m tall, 0.7 m
  long under each end: the deck soffit stands 0.20 m clear over the 6 m between them (the stream gap).
  Total 7.4 x 4.05 x 0.95 m. Front is +Y: the 7.4 m elevation faces the viewer.
  r2 (op13): sills added. Without them the deck sat on the ground as a closed box and did not read as a bridge.
  Sources: lookbook 31-plan-ground (bridge over the stream, C3-E4) and 30-plan-summit; there is no bridge
  elevation sheet, so the row's typical dims are the targets.

Proxy note: assets.json has w 2.6 (the row's span minimum). The default is the row's typical span, so the
check reports w against the old proxy. Proposed proxy: w 7.4, d 4.0, h 0.9.

Parameters (build kwargs):
  span       2.6-7.4 m (default 7.4)
  w          deck width 1.4-4 m (default 4.0)
  thickness  deck thickness 0.4-0.9 m (default per seed 0.40-0.45)
  parapet_h  parapet height above the deck, 0-0.8 m (default 0.3; 0 gives no parapet)
  sill_h     bank sill height / soffit clearance (default 0.2); sill_l sill length per end (default 0.7)
  spaced     parapet as separate kerb blocks (default: seed 3 only)

Seeds: seed 1 has four flags, a 0.45 deck, one parapet course of 1.0 m blocks; seed 2 has three flags, a
0.40 deck, two parapet courses of 1.1 m blocks, a 0.05 batter and a 0.03 cap overhang; seed 3 has five
flags and the parapet broken into separate ~1 m kerb blocks with 0.35 m gaps (spaced=True). Layout draws are per part streams,
the same at every LOD.
Construction: two bank sills (kzgeo_bridge_slab.sills, rough hull blocks), deck = flags
(kzgeo_bridge_slab.flags) on the sills + parapets (kzgeo_parapet_stone.wall, 2 walls).
LOD0 bevelled flags with 2-segment rounds and a roughened top, parapets with full joints. LOD1 chamfered
flags, same parapets. LOD2 two plain flag boxes and 2-band parapets. LOD3 one deck box and two trapezoid
parapets (silhouette only).
Materials: flag sides and soffit basalt_dry (cool tint), sills basalt_wet (low wetness, stream-side), walking surface and parapet caps paving, parapet
blocks basalt_dry.
Props: kz_deck_z (walking level), kz_walk (walkable x/y), kz_clear (gap under the deck), kz_params.
Animation: none. Lighting: lightmap (UV1 from genlib.finish).
"""
import genlib
import kzgeo_common as C
import kzgeo_bridge_slab as B
import kzgeo_parapet_stone as P

ASSET = 'bridge_slab'
FEATURES = ['thick basalt deck slab', 'flag joints across the span', 'low block parapets on both edges']

TINT = (0.40, 0.47, 0.64)          # basalt_dry default (0.55, 0.65, 0.85) x 0.75: near-black and cool
SEEDS = {1: dict(flags=4, course=0.22, batter=0.02, over=0.025, blen=1.0, T=0.45, spaced=False),
         2: dict(flags=3, course=0.10, batter=0.05, over=0.03, blen=1.1, T=0.40, spaced=False),
         3: dict(flags=5, course=0.16, batter=0.00, over=0.02, blen=0.85, T=0.45, spaced=True)}


def build(lod, seed, span=7.4, w=4.0, thickness=None, parapet_h=0.3, sill_h=0.2, sill_l=0.7, spaced=None):
    S = SEEDS[(seed - 1) % 3 + 1]
    thickness = S['T'] if thickness is None else thickness
    spaced = S['spaced'] if spaced is None else spaced
    nflags = S['flags']
    r_deck = C.rng(seed, ASSET + ':deck')
    r_wall = C.rng(seed, ASSET + ':walls')

    r_sill = C.rng(seed, ASSET + ':sills')
    mb = genlib.MeshBuilder()
    m_dry = mb.slot('basalt_dry', tint=TINT)
    m_top = mb.slot('paving')
    m_sill = mb.slot('basalt_wet', wetness=0.35, tint=TINT)
    # bank seats: one rough basalt sill under each end; the deck bears on them and the stream runs in the
    # open gap between (the place model cuts the channel). Shape drawn before the LOD branch.
    sills = B.sill_layout(span, w, sill_h, sill_l, r_sill)
    B.sills(mb, sills, lod, m_sill)
    z0 = sill_h
    if lod == 3:
        C.board(mb, (0.0, 0.0, z0 + thickness / 2), (span, w, thickness), m_dry, bevel=0.0)
    elif lod == 2:
        B.flags(mb, span, w, thickness, 2, r_deck, m_dry, m_top, 2, z0=z0)
    else:
        B.flags(mb, span, w, thickness, lod, r_deck, m_dry, m_top, nflags, z0=z0)

    if parapet_h > 1e-3:
        tp = 0.30
        y = w / 2 - tp / 2
        runs = [(-span / 2, span / 2)]
        if spaced and lod < 3:                       # seed 3: a row of separate kerb blocks, 0.35 m gaps
            #                                          (LOD3: one run per side, the gaps vanish at 80 m)
            n = max(2, round((span + 0.35) / 1.35))
            L = (span - 0.35 * (n - 1)) / n
            runs = [(-span / 2 + i * (L + 0.35), -span / 2 + i * (L + 0.35) + L) for i in range(n)]
        paths = [[(a, yy), (b, yy)] for yy in (y, -y) for a, b in runs]
        wl = 3 if (spaced and lod == 2) else lod      # spaced LOD2: one capped trapezoid block per kerb stone
        for path in paths:
            P.wall(mb, path, z0 + thickness, parapet_h, tp, wl, r_wall, m_dry, m_dry, m_top,
                   course=S['course'], blen=S['blen'], cap_h=0.09, overhang=S['over'], batter=S['batter'],
                   drains=0, wet_base=False)
    C.centre_base(mb, centre_x=True, centre_y=True)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_deck_z=round(z0 + thickness, 3),
                     kz_walk=dict(x=[-span / 2, span / 2], y=[-(w / 2 - 0.30), w / 2 - 0.30] if parapet_h > 1e-3 else [-w / 2, w / 2]),
                     kz_clear=dict(x=[-(span / 2 - sill_l), span / 2 - sill_l], z=[0.0, z0]),
                     kz_params=dict(span=span, w=w, thickness=thickness, parapet_h=parapet_h, sill_h=sill_h, flags=nflags))
    return o
