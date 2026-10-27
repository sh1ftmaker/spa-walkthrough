"""Low basalt parapet and kerb wall (parapet_stone). Per metre: one segment, 1.0 m long.

Target dimensions (row: knee-to-waist wall of rough-cut basalt blocks with a flat cap, per metre; the
lookbook 04 / 31 pool kerbs and the sheet-mod-* panels have no measurable parapet, so the proxy and the
row ranges are the targets):
  length 1.0 m (per metre), height 0.8 m total incl. cap (range 0.4-1.1), body thickness 0.36 m
  (row range 0.4-0.8; see the proxy note below), cap 0.09 m tall with 0.02-0.03 m overhang each face.
  Courses 0.19-0.27 m (3-4 per 0.8 m wall), blocks 0.32-0.50 m long with running bond.
  Proxy note: the proxy d 0.4 cannot hold a 0.4 m body plus a cap overhang, so the default body is 0.36 m
  (0.36 + 2 x 0.02 = 0.40). Proposed proxy d = 0.46 for the row thickness 0.4 m + 2 x 0.03 overhang.

Parameters (build kwargs):
  height     0.4-1.1 m total (default 0.8)
  thickness  body thickness 0.36-0.8 m (default 0.36)
  course     course height (default seeded 0.19-0.27)
  block      block length (default seeded 0.32-0.50)
  overhang   cap overhang per face (default seeded 0.02-0.03)
  drains     drain openings in the bottom course, per metre (default seeded 0 or 1)
  wet_base   True puts the bottom course in basalt_wet (use where the wall meets pool water)
  length     metres of wall along +X (default 1.0; the instancer scales/places segments)
  path       optional polyline [(x, y), ...] for a bent run (default straight along X)

Seeds change shape: seed 1 is 3 courses of large blocks, seed 2 is 4 courses of smaller blocks with a
drain, seed 3 has a wider batter and a bigger cap overhang. Layout draws are per part streams and do not
depend on LOD.
Construction: each block is a closed convex hull of jittered corners (rough-cut planar faces, no knife
edges); cap is a swept coping profile with a chamfer at LOD0. LOD0 full joints and drains, LOD1 blocks
paired (every second joint dropped), LOD2 two bands and a 4-sided cap, LOD3 one trapezoid (cap width shows).
Materials: blocks basalt_dry (tint 0.75 x the library's cool default), base course basalt_wet if wet_base, cap paving. Front is +Y.
Animation: none. Lighting: lightmap (UV1 from genlib.finish).
Props: kz_sockets (cap-top lantern/toro mount), kz_params.
"""
import genlib
import kzgeo_common as C
import kzgeo_parapet_stone as P

ASSET = 'parapet_stone'
FEATURES = ['rough-cut basalt block courses', 'flat paving cap with overhang', 'running bond joints']

TINT = (0.40, 0.47, 0.64)      # basalt_dry library default (0.55, 0.65, 0.85) x 0.75: near-black, cool.
#                                 (the old (0.5, 0.5, 0.55) removed the blue and rendered tan-brown)


def build(lod, seed, length=1.0, height=0.8, thickness=0.36, course=None, block=None, overhang=None,
          drains=None, wet_base=False, path=None):
    g = C.rng(seed, ASSET + ':params')
    # seed table: three different wall layouts (course count, block size, batter, overhang, drain)
    T = {1: dict(course=0.27, block=0.48, over=0.025, batter=0.02, drains=0),
         2: dict(course=0.18, block=0.32, over=0.020, batter=0.00, drains=1),
         3: dict(course=0.23, block=0.40, over=0.022, batter=0.06, drains=1)}[(seed - 1) % 3 + 1]
    # draws in fixed order, whatever the LOD; small per-seed jitter on the table values
    course_s = course if course is not None else T['course'] * g.uniform(0.97, 1.03)
    block_s = block if block is not None else T['block'] * g.uniform(0.95, 1.05)
    over_s = overhang if overhang is not None else T['over']
    batter_s = T['batter']
    drains_s = drains if drains is not None else T['drains']

    if path is None:
        path = [(-length / 2.0, 0.0), (length / 2.0, 0.0)]
    r = C.rng(seed, ASSET + ':wall')

    mb = genlib.MeshBuilder()
    m_block = mb.slot('basalt_dry', tint=TINT)
    m_base = mb.slot('basalt_wet', wetness=0.4, tint=TINT)
    m_cap = mb.slot('paving')
    P.wall(mb, path, 0.0, height, thickness, lod, r, m_block, m_base, m_cap,
           course=course_s, blen=block_s, cap_h=0.09, overhang=over_s, batter=batter_s,
           drains=(drains_s if lod == 0 else 0), wet_base=wet_base)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    # sockets on the cap top for lantern posts / toro (the row: "lantern posts or toro sit on it");
    # one per segment at mid-length, the placer uses every Nth.
    C.set_json_props(o, kz_sockets=[dict(kind='lantern_post|toro', pos=[0.0, 0.0, round(height, 3)], up=[0, 0, 1])],
                     kz_params=dict(height=height, thickness=thickness, course=round(course_s, 3),
                                    block=round(block_s, 3), overhang=over_s, drains=drains_s))
    return o
