"""Vertical slat screen and fence (b1 grotto partitions, b2 core, suite privacy fences).

Identifying features kept at every LOD: close vertical hinoki slats between a bottom sill and a top rail / cap,
on posts; reads as a partition (tall, narrow slats) or a privacy fence (lower, wider boards, kasagi cap).

Targets (measured):
  * lookbook 16 steam grotto (bather ~1.1 m seated, sign 0.5 m wide): slatted partition behind the 火山湯 sign,
    ~1.6-1.9 m tall, slats ~0.04-0.05 m on ~0.06 m pitch (gap ~1.5 cm), a top rail, dark oiled timber.
  * lookbook 32 suites cliff (plan view, 1 m bar ~ 50 px on the 5 m plan bar): suite privacy fences along the
    veranda, ~1.2-1.5 m tall, wider boards (~0.08-0.10 m) with small gaps, posts ~1.8 m apart, capped.
  * Row: h 0.9-2.2 m, slat w / gap, posts, gate gap; budget is per metre (500/200/60/16).

Parameters (default length 1.0 m = one per-metre module; proposed proxy 1.0 x 0.18 x 1.85):
  length  0.6-20 m  run length (posts at both ends and every post_sp)
  h       0.9-2.2 m height (default by style: partition 1.8, fence 1.3-1.5)
  style   partition | fence   (default cycles with the seed; the row's '2 seeds')
  slat_w  0.03-0.10 m, gap 0.008-0.04 m, slat_t 0.018-0.025 m
  post_sp 1.2-2.4 m post spacing;  post_w 0.09-0.12 m
  gate    None | {'x': centre along the run, 'w': 0.8-1.2}: an open gap with its own jamb posts
Seeds change: style (partition: tall, narrow 0.035-0.05 slats, tight 8-16 mm gaps, top rail; fence: 1.2-1.5 m,
0.08-0.10 boards, 18-35 mm gaps, wide bevelled kasagi cap, 3 back rails), height, slat width / gap / thickness,
post size, post spacing, floor clearance.

Materials: hinoki wet_oiled (slats), hinoki dark_timber (posts, rails, sill, cap).  Lighting: lightmap.
Animation: none.  The run has no ground mass: it stands on the host floor (open bottoms of posts / slabs).
"""
import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_slat_screen as KS

ASSET = 'slat_screen'
FEATURES = ['close vertical hinoki slats', 'top rail or cap and bottom sill', 'posts']
STYLES = ['partition', 'fence']


def params(seed, length=None, h=None, style=None, slat_w=None, gap=None, slat_t=None, post_sp=None, post_w=None,
           gate=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'slats')
    P = dict(style=style, length=float(length or 1.0), gate=gate)
    if style == 'partition':
        P['h'] = float(h or g.uniform(1.72, 1.84))
        P['slat_w'] = float(slat_w or g.uniform(0.035, 0.05))
        P['gap'] = float(gap if gap is not None else g.uniform(0.008, 0.016))
        P['rails'] = 2
        P['cap_t'] = 0.0
    else:
        P['h'] = float(h or g.uniform(1.2, 1.5))
        P['slat_w'] = float(slat_w or g.uniform(0.08, 0.1))
        P['gap'] = float(gap if gap is not None else g.uniform(0.018, 0.035))
        P['rails'] = 3
        P['cap_t'] = round(g.uniform(0.035, 0.045), 3)
    P['slat_t'] = float(slat_t or g.uniform(0.018, 0.025))
    P['post_sp'] = float(post_sp or g.uniform(1.6, 2.0))
    P['post_w'] = float(post_w or g.uniform(0.09, 0.12))
    P['clear'] = round(g.uniform(0.03, 0.08), 3)
    return P


def build(lod, seed, length=None, h=None, style=None, slat_w=None, gap=None, slat_t=None, post_sp=None, post_w=None,
          gate=None, **_):
    P = params(seed, length, h, style, slat_w, gap, slat_t, post_sp, post_w, gate)
    mb = genlib.MeshBuilder()
    mats = dict(slat=mb.slot('hinoki', variant='wet_oiled'), post=mb.slot('hinoki', variant='dark_timber'))
    posts, bays = KS.screen_into(mb, mats, lod, P)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    # LOD2-3 infill slabs keep the box projection (vertical grain); grain-follow would turn them into horizontal boards
    kg.uv_grain(o, [mats['slat'], mats['post']] if lod <= 1 else [mats['post']])
    C.set_json_props(o, kz_params={k: v for k, v in P.items() if v is not None}, kz_lights=[],
                     kz_posts=[round(x, 3) for x in posts], kz_per_metre=True)
    return o
